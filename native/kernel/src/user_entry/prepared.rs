//! Owned, still-inactive user root with a guarded supervisor entry stack.
//! Boot mappings must remain retained and serialized by their boot-lifetime
//! owner. This object neither installs CPU state nor permits CR3 activation.

#![forbid(unsafe_code)]

use poole_handoff::{CoreRecord, PAGE_BYTES};
use poole_kmap as kmap;

use super::{ImageAdmission, InitialImage, admit_initial_image, physical_mask};
use crate::physical_memory::{AllocationHandle, PhysicalMemoryManager, RetainedAllocation, Zone};
use crate::reclamation::task_lifetimes::{STACK_OWNER, STACK_PAGE_COUNT};
use crate::virtual_memory::{self as vm, AddressSpace, TableMemory};

pub const CONTRACT_ID: &str = "PKUSER2";
pub const STACK_TABLE_OWNER: u16 = 0x1301;
pub const STACK_TABLE_PAGES: u64 = 3;
pub const STACK_BOTTOM: u64 = vm::KERNEL_START + PAGE_BYTES;
pub const STACK_TOP: u64 = STACK_BOTTOM + STACK_PAGE_COUNT * PAGE_BYTES;
const STACK_SLOT: usize = 256;
const KERNEL_SLOT: usize = 511;
const P: u64 = 1;
const W: u64 = 1 << 1;
const A: u64 = 1 << 5;
const D: u64 = 1 << 6;
const NX: u64 = 1 << 63;
const OWNED_COUNT: usize = vm::MAX_FRAMES + 3;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    Image(super::Error),
    Ownership,
    Layout,
    Supervisor,
    Memory,
    Readback,
}

/// Construction and abort return all objects on failure. No mutable address-space
/// access, retention token, activation or release of an active root is exposed.
/// A dropped/forgotten prepared object deliberately leaves PMM retention live.
///
/// ```compile_fail
/// use poolekernel::user_entry::prepared::PreparedImage;
/// fn duplicate(owner: &PreparedImage) -> PreparedImage { owner.clone() }
/// ```
///
/// ```compile_fail
/// use poolekernel::user_entry::prepared::PreparedImage;
/// use poolekernel::virtual_memory::AddressSpace;
/// fn mutate(owner: &mut PreparedImage) -> &mut AddressSpace { &mut owner.space }
/// ```
pub struct PreparedImage {
    space: AddressSpace,
    stack: AllocationHandle,
    stack_tables: AllocationHandle,
    retained: [Option<RetainedAllocation>; OWNED_COUNT],
    image: InitialImage,
    bits: u8,
    admission: Option<ImageAdmission>,
}

pub struct DetachedImage {
    pub space: AddressSpace,
    pub stack: AllocationHandle,
    pub stack_tables: AllocationHandle,
}

fn read<M: TableMemory>(memory: &mut M, table: u64, index: usize) -> Result<u64, Error> {
    memory.read_entry(table, index).map_err(|_| Error::Memory)
}

fn write<M: TableMemory>(
    memory: &mut M,
    table: u64,
    index: usize,
    value: u64,
) -> Result<(), Error> {
    memory
        .write_entry(table, index, value)
        .map_err(|_| Error::Memory)?;
    if read(memory, table, index)? != value {
        return Err(Error::Readback);
    }
    Ok(())
}

fn overlap(start: u64, pages: u64, handle: AllocationHandle) -> bool {
    let end = start.saturating_add(pages.saturating_mul(PAGE_BYTES));
    let owned = handle.start_page.saturating_mul(PAGE_BYTES);
    let owned_end = owned.saturating_add(handle.page_count.saturating_mul(PAGE_BYTES));
    start < owned_end && owned < end
}

impl PreparedImage {
    /// The caller supplies a validated, boot-retained PKMAP2 core and serialized
    /// physical table access. Boot ownership/authentication is not created here.
    #[allow(clippy::result_large_err)]
    pub fn prepare<M: TableMemory>(
        parts: DetachedImage,
        manager: &mut PhysicalMemoryManager,
        memory: &mut M,
        image: InitialImage,
        core: CoreRecord,
        physical_bits: u8,
    ) -> Result<Self, (Error, Self)> {
        let mut prepared = Self {
            space: parts.space,
            stack: parts.stack,
            stack_tables: parts.stack_tables,
            retained: core::array::from_fn(|_| None),
            image,
            bits: physical_bits,
            admission: None,
        };
        match prepared.build(manager, memory, core) {
            Ok(admission) => {
                prepared.admission = Some(admission);
                Ok(prepared)
            }
            Err(error) => Err((error, prepared)),
        }
    }

    fn handles(&self) -> [Option<AllocationHandle>; OWNED_COUNT] {
        let space = self.space.allocation_handles();
        core::array::from_fn(|i| match i {
            i if i <= vm::MAX_FRAMES => space[i],
            i if i == vm::MAX_FRAMES + 1 => Some(self.stack),
            _ => Some(self.stack_tables),
        })
    }

    fn build<M: TableMemory>(
        &mut self,
        manager: &mut PhysicalMemoryManager,
        memory: &mut M,
        core: CoreRecord,
    ) -> Result<ImageAdmission, Error> {
        let image = admit_initial_image(manager, &self.space, memory, self.image, self.bits)
            .map_err(Error::Image)?;
        let mask = physical_mask(self.bits).map_err(Error::Image)?;
        let handles = self.handles();
        manager
            .check_retainable_allocations(&handles)
            .map_err(|_| Error::Ownership)?;
        for handle in handles.iter().flatten() {
            let start = handle
                .start_page
                .checked_mul(PAGE_BYTES)
                .ok_or(Error::Ownership)?;
            let last = handle
                .start_page
                .checked_add(handle.page_count.checked_sub(1).ok_or(Error::Ownership)?)
                .and_then(|p| p.checked_mul(PAGE_BYTES))
                .ok_or(Error::Ownership)?;
            if start == 0 || start & !mask != 0 || last & !mask != 0 {
                return Err(Error::Ownership);
            }
        }
        if self.stack.owner != STACK_OWNER
            || self.stack.page_count != STACK_PAGE_COUNT
            || self.stack.zone != Zone::Dma32
            || self.stack_tables.owner != STACK_TABLE_OWNER
            || self.stack_tables.page_count != STACK_TABLE_PAGES
            || self.stack_tables.zone != Zone::Dma32
        {
            return Err(Error::Layout);
        }
        let supervisor = audit_supervisor(memory, core, mask, &handles)?;
        // Retain the entire set atomically before the first write. Every later
        // failure returns this quarantined owner, including a failed readback.
        self.retained = manager
            .retain_allocations(handles)
            .map_err(|_| Error::Ownership)?;
        let tables = self.stack_tables.start_page * PAGE_BYTES;
        for page in 0..STACK_TABLE_PAGES {
            let table = tables + page * PAGE_BYTES;
            memory.prepare_page(table).map_err(|_| Error::Memory)?;
            for index in 0..vm::TABLE_ENTRIES {
                write(memory, table, index, 0)?;
            }
        }
        write(memory, tables, 0, (tables + PAGE_BYTES) | P | W | NX)?;
        write(
            memory,
            tables + PAGE_BYTES,
            0,
            (tables + 2 * PAGE_BYTES) | P | W | NX,
        )?;
        for page in 0..STACK_PAGE_COUNT {
            write(
                memory,
                tables + 2 * PAGE_BYTES,
                (page + 1) as usize,
                ((self.stack.start_page + page) * PAGE_BYTES) | P | W | NX,
            )?;
        }
        write(memory, image.root_physical, STACK_SLOT, tables | P | W | NX)?;
        write(memory, image.root_physical, KERNEL_SLOT, supervisor)?;
        memory.finish().map_err(|_| Error::Memory)?;
        self.audit_attached(memory, image, supervisor)?;
        let replay = super::admit_image_with_roots(
            manager,
            &self.space,
            memory,
            self.image,
            self.bits,
            &[(STACK_SLOT, tables | P | W | NX), (KERNEL_SLOT, supervisor)],
        )
        .map_err(Error::Image)?;
        if replay != image {
            return Err(Error::Readback);
        }
        if audit_supervisor(memory, core, mask, &handles)? != supervisor {
            return Err(Error::Readback);
        }
        Ok(image)
    }

    fn audit_attached<M: TableMemory>(
        &self,
        memory: &mut M,
        image: ImageAdmission,
        supervisor: u64,
    ) -> Result<(), Error> {
        let tables = self.stack_tables.start_page * PAGE_BYTES;
        for index in 1..vm::TABLE_ENTRIES {
            let expected = match index {
                STACK_SLOT => tables | P | W | NX,
                KERNEL_SLOT => supervisor,
                _ => 0,
            };
            if read(memory, image.root_physical, index)? != expected {
                return Err(Error::Readback);
            }
        }
        for page in 0..STACK_TABLE_PAGES {
            for index in 0..vm::TABLE_ENTRIES {
                let expected = match (page, index) {
                    (0, 0) | (1, 0) => (tables + (page + 1) * PAGE_BYTES) | P | W | NX,
                    (2, i) if i >= 1 && i <= STACK_PAGE_COUNT as usize => {
                        ((self.stack.start_page + i as u64 - 1) * PAGE_BYTES) | P | W | NX
                    }
                    _ => 0,
                };
                if read(memory, tables + page * PAGE_BYTES, index)? != expected {
                    return Err(Error::Readback);
                }
            }
        }
        Ok(())
    }

    /// Diagnostic only. The future CPU adapter must consume ownership and audit
    /// current mappings/state; this copied snapshot cannot authorize execution.
    pub const fn admission(&self) -> Option<ImageAdmission> {
        self.admission
    }

    /// Only inactive objects exist in this API. Detach both root edges and verify
    /// all private stack tables are zero before releasing retention atomically.
    #[allow(clippy::result_large_err)]
    pub fn abort<M: TableMemory>(
        mut self,
        manager: &mut PhysicalMemoryManager,
        memory: &mut M,
    ) -> Result<DetachedImage, (Error, Self)> {
        self.admission = None;
        if self.retained.iter().any(Option::is_some) {
            let result = (|| {
                manager
                    .validate_retentions(&self.retained)
                    .map_err(|_| Error::Ownership)?;
                let root = self.space.summary().root_physical;
                write(memory, root, STACK_SLOT, 0)?;
                write(memory, root, KERNEL_SLOT, 0)?;
                for page in 0..STACK_TABLE_PAGES {
                    memory
                        .prepare_page((self.stack_tables.start_page + page) * PAGE_BYTES)
                        .map_err(|_| Error::Memory)?;
                    for index in 0..vm::TABLE_ENTRIES {
                        write(
                            memory,
                            (self.stack_tables.start_page + page) * PAGE_BYTES,
                            index,
                            0,
                        )?;
                    }
                }
                memory.finish().map_err(|_| Error::Memory)?;
                admit_initial_image(manager, &self.space, memory, self.image, self.bits)
                    .map_err(Error::Image)?;
                Ok(())
            })();
            if let Err(error) = result {
                return Err((error, self));
            }
            let retained = core::mem::replace(&mut self.retained, core::array::from_fn(|_| None));
            if let Err((_, retained)) = manager.release_retentions(retained) {
                self.retained = retained;
                return Err((Error::Ownership, self));
            }
        }
        Ok(DetachedImage {
            space: self.space,
            stack: self.stack,
            stack_tables: self.stack_tables,
        })
    }
}

// Admit only the existing bounded PKMAP2 supervisor subtree, not firmware's
// identity mappings. All other root entries stay absent except the owned user
// subtree and the private entry-stack subtree. Unsupported bootstrap extensions
// are rejected until they receive their own lifetime and cache-policy contract.
fn audit_supervisor<M: TableMemory>(
    memory: &mut M,
    core: CoreRecord,
    mask: u64,
    owned: &[Option<AllocationHandle>],
) -> Result<u64, Error> {
    let root = core.page_table_root_physical;
    let kernel_pages = core.kernel_physical_size.div_ceil(PAGE_BYTES);
    if root == 0
        || root & !mask != 0
        || root
            .checked_add(4 * PAGE_BYTES)
            .is_none_or(|last| last & !mask != 0)
        || core.kernel_virtual_base != vm::KERNEL_IMAGE_START
        || kernel_pages == 0
        || kernel_pages > kmap::KERNEL_PAGE_CAPACITY as u64
        || core.kernel_physical_base == 0
        || core.kernel_physical_base & !mask != 0
        || core
            .kernel_physical_base
            .checked_add((kernel_pages - 1) * PAGE_BYTES)
            .is_none_or(|p| p & !mask != 0)
        || core.kernel_virtual_size != core.kernel_physical_size
        || !(core.kernel_virtual_base..core.kernel_virtual_base + core.kernel_physical_size)
            .contains(&core.kernel_entry_virtual)
        || core.initial_stack_top_virtual
            != vm::KERNEL_IMAGE_START + kmap::STACK_GUARD_HIGH_PAGE as u64 * PAGE_BYTES
        || core.handoff_virtual_base
            != vm::KERNEL_IMAGE_START + kmap::HANDOFF_FIRST_PAGE as u64 * PAGE_BYTES
        || core.handoff_byte_count == 0
        || core.handoff_byte_count > kmap::HANDOFF_CAPACITY_BYTES
        || core.handoff_physical_base == 0
        || core.handoff_physical_base & !mask != 0
        || core
            .handoff_physical_base
            .checked_add(kmap::HANDOFF_CAPACITY_BYTES - PAGE_BYTES)
            .is_none_or(|p| p & !mask != 0)
    {
        return Err(Error::Supervisor);
    }
    for handle in owned.iter().flatten() {
        if overlap(root, 5, *handle)
            || overlap(core.kernel_physical_base, kernel_pages, *handle)
            || overlap(
                core.handoff_physical_base,
                kmap::HANDOFF_PAGE_COUNT as u64,
                *handle,
            )
        {
            return Err(Error::Ownership);
        }
    }
    let root_entry = read(memory, root, KERNEL_SLOT)?;
    if root_entry & !A != (root + PAGE_BYTES) | P | W {
        return Err(Error::Supervisor);
    }
    for index in 0..vm::TABLE_ENTRIES {
        let pdpt = if index == 510 {
            (root + 2 * PAGE_BYTES) | P | W
        } else {
            0
        };
        let directory = if index < 2 {
            (root + (3 + index as u64) * PAGE_BYTES) | P | W
        } else {
            0
        };
        for (table, expected) in [
            (root + PAGE_BYTES, pdpt),
            (root + 2 * PAGE_BYTES, directory),
        ] {
            let observed = read(memory, table, index)?;
            if observed & !A != expected || (expected == 0 && observed != 0) {
                return Err(Error::Supervisor);
            }
        }
    }
    let stack_first = read(memory, root + 3 * PAGE_BYTES, kmap::STACK_FIRST_PAGE)? & mask;
    if stack_first == 0 {
        return Err(Error::Supervisor);
    }
    let boot_ranges = [
        (root, 5),
        (core.kernel_physical_base, kernel_pages),
        (core.handoff_physical_base, kmap::HANDOFF_PAGE_COUNT as u64),
        (stack_first, kmap::STACK_PAGE_COUNT as u64),
    ];
    for (i, &(start, pages)) in boot_ranges.iter().enumerate() {
        let end = start
            .checked_add(pages * PAGE_BYTES)
            .ok_or(Error::Supervisor)?;
        for &(other, other_pages) in &boot_ranges[..i] {
            let other_end = other
                .checked_add(other_pages * PAGE_BYTES)
                .ok_or(Error::Supervisor)?;
            if start < other_end && other < end {
                return Err(Error::Supervisor);
            }
        }
    }
    for handle in owned.iter().flatten() {
        if overlap(stack_first, kmap::STACK_PAGE_COUNT as u64, *handle) {
            return Err(Error::Ownership);
        }
    }
    for index in 0..kmap::RETAINED_TABLE_ENTRIES {
        let entry = read(
            memory,
            root + (3 + index / 512) as u64 * PAGE_BYTES,
            index % 512,
        )?;
        let physical = entry & mask;
        let flags = entry & !(mask | A | D);
        let valid = if index < kernel_pages as usize {
            physical == core.kernel_physical_base + index as u64 * PAGE_BYTES
                && (flags == P || flags == P | NX || flags == P | W | NX)
                && (index
                    != ((core.kernel_entry_virtual - core.kernel_virtual_base) / PAGE_BYTES)
                        as usize
                    || flags == P)
        } else if (kmap::STACK_FIRST_PAGE..kmap::STACK_GUARD_HIGH_PAGE).contains(&index) {
            stack_first
                .checked_add((index - kmap::STACK_FIRST_PAGE) as u64 * PAGE_BYTES)
                .is_some_and(|expected| expected & !mask == 0 && physical == expected)
                && flags == P | W | NX
        } else if (kmap::HANDOFF_FIRST_PAGE..kmap::TEMPORARY_PAGE_INDEX).contains(&index) {
            physical
                == core.handoff_physical_base
                    + (index - kmap::HANDOFF_FIRST_PAGE) as u64 * PAGE_BYTES
                && flags == P | NX
        } else {
            entry == 0
        };
        if !valid {
            return Err(Error::Supervisor);
        }
    }
    Ok(root_entry & !A)
}

#[cfg(test)]
#[path = "prepared_tests.rs"]
mod tests;
