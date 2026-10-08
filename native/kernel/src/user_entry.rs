//! Inactive, two-page user-image admission for the first native user-space lane.
//!
//! This does not activate CR3, install descriptors, execute IRETQ, or confer
//! authority. The caller must hold exclusive address-space/allocation ownership
//! throughout admission and the eventual architectural transition. A snapshot
//! cannot authorize a later transition after mappings or ownership change.

use poole_handoff::PAGE_BYTES;

use crate::physical_memory::PhysicalMemoryManager;
use crate::virtual_memory::{
    self as vm, AddressSpace, TableMemory, USER_WINDOW_END_EXCLUSIVE, USER_WINDOW_START,
};

pub mod bootstrap;
pub mod preemption;
pub mod prepared;
pub mod privilege;
pub mod timer;

pub const CONTRACT_ID: &str = "PKUSER1";
// Preserve the existing kernel code/data and two-slot TSS at GDT indices 1..4.
// Data before code also leaves the required ordering for a later SYSRET ABI.
pub const USER_DATA_SELECTOR: u64 = (5 << 3) | 3;
pub const USER_CODE_SELECTOR: u64 = (6 << 3) | 3;
pub const USER_DATA_DESCRIPTOR: u64 = 0x00cf_f200_0000_ffff;
pub const USER_CODE_DESCRIPTOR: u64 = 0x00af_fa00_0000_ffff;
pub const USER_GDT_LIMIT: u16 = 7 * 8 - 1;
pub const INITIAL_RFLAGS: u64 = (1 << 9) | (1 << 1);

const PRESENT: u64 = 1;
const WRITE: u64 = 1 << 1;
const USER: u64 = 1 << 2;
const ACCESSED: u64 = 1 << 5;
const DIRTY: u64 = 1 << 6;
const NX: u64 = 1 << 63;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    Layout,
    PhysicalWidth,
    SpaceState,
    Ownership,
    TableAccess,
    ParentEntry,
    LeafEntry,
    UnexpectedMapping,
    PhysicalAlias,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct InitialImage {
    pub code_page: u64,
    pub entry: u64,
    pub stack_page: u64,
}

impl InitialImage {
    fn validate(self) -> Result<(), Error> {
        for page in [self.code_page, self.stack_page] {
            if !page.is_multiple_of(PAGE_BYTES)
                || !(USER_WINDOW_START..USER_WINDOW_END_EXCLUSIVE).contains(&page)
            {
                return Err(Error::Layout);
            }
        }
        if !(self.code_page..self.code_page + PAGE_BYTES).contains(&self.entry)
            || self.stack_page == USER_WINDOW_START
            || self.stack_page + 2 * PAGE_BYTES > USER_WINDOW_END_EXCLUSIVE
            || (self.stack_page - PAGE_BYTES..self.stack_page + 2 * PAGE_BYTES)
                .contains(&self.code_page)
        {
            return Err(Error::Layout);
        }
        Ok(())
    }
}

/// Stack order consumed by a future 64-bit privilege-changing IRETQ.
/// Initial entry is a process `_start`, not a function call with a return address.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(C)]
pub struct InitialReturnFrame {
    pub rip: u64,
    pub cs: u64,
    pub rflags: u64,
    pub rsp: u64,
    pub ss: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ImageAdmission {
    pub root_physical: u64,
    pub root_generation: u64,
    pub code_physical: u64,
    pub stack_physical: u64,
    pub initial_frame: InitialReturnFrame,
}

fn physical_mask(bits: u8) -> Result<u64, Error> {
    if !(36..=52).contains(&bits) {
        return Err(Error::PhysicalWidth);
    }
    Ok(((1u64 << bits) - 1) & !(PAGE_BYTES - 1))
}

/// Read back the entire owned four-page tree, not just the intended two leaves.
/// Only this inactive PKVM1 image is accepted; kernel-half attachment, active
/// roots, executable loading, zeroing and architectural state are later gates.
pub fn admit_initial_image<M: TableMemory>(
    manager: &PhysicalMemoryManager,
    space: &AddressSpace,
    memory: &mut M,
    image: InitialImage,
    physical_address_bits: u8,
) -> Result<ImageAdmission, Error> {
    admit_image_with_roots(manager, space, memory, image, physical_address_bits, &[])
}

fn admit_image_with_roots<M: TableMemory>(
    manager: &PhysicalMemoryManager,
    space: &AddressSpace,
    memory: &mut M,
    image: InitialImage,
    physical_address_bits: u8,
    roots: &[(usize, u64)],
) -> Result<ImageAdmission, Error> {
    image.validate()?;
    let mask = physical_mask(physical_address_bits)?;
    let summary = space.summary();
    if summary.root_active
        || summary.root_released
        || summary.root_generation == 0
        || summary.pending_invalidations != 0
        || summary.table_pages != vm::TABLE_PAGE_COUNT
        || summary.active_mappings != 2
        || summary.bound_frames != 2
    {
        return Err(Error::SpaceState);
    }
    let handles = space.allocation_handles();
    for handle in handles.iter().flatten() {
        manager
            .validate_allocation(*handle)
            .map_err(|_| Error::Ownership)?;
        let first = handle
            .start_page
            .checked_mul(PAGE_BYTES)
            .ok_or(Error::Ownership)?;
        let last = handle
            .start_page
            .checked_add(handle.page_count.checked_sub(1).ok_or(Error::Ownership)?)
            .and_then(|page| page.checked_mul(PAGE_BYTES))
            .ok_or(Error::Ownership)?;
        if first == 0 || first & !mask != 0 || last & !mask != 0 {
            return Err(Error::Ownership);
        }
    }
    let root = summary.root_physical;
    let path = [
        ((image.code_page >> 39) & 511) as usize,
        ((image.code_page >> 30) & 511) as usize,
        ((image.code_page >> 21) & 511) as usize,
    ];
    for (level, selected) in path.into_iter().enumerate() {
        let table = root + level as u64 * PAGE_BYTES;
        for index in 0..vm::TABLE_ENTRIES {
            let entry = memory
                .read_entry(table, index)
                .map_err(|_| Error::TableAccess)?;
            if index == selected {
                let expected = table + PAGE_BYTES | PRESENT | WRITE | USER;
                if entry & !ACCESSED != expected {
                    return Err(Error::ParentEntry);
                }
            } else {
                let expected = if level == 0 {
                    roots
                        .iter()
                        .find_map(|&(slot, value)| (slot == index).then_some(value))
                        .unwrap_or(0)
                } else {
                    0
                };
                if entry != expected {
                    return Err(Error::UnexpectedMapping);
                }
            }
        }
    }
    let leaf_table = root + 3 * PAGE_BYTES;
    let code_index = ((image.code_page >> 12) & 511) as usize;
    let stack_index = ((image.stack_page >> 12) & 511) as usize;
    let mut code_physical = 0;
    let mut stack_physical = 0;
    for index in 0..vm::TABLE_ENTRIES {
        let entry = memory
            .read_entry(leaf_table, index)
            .map_err(|_| Error::TableAccess)?;
        if index != code_index && index != stack_index {
            if entry != 0 {
                return Err(Error::UnexpectedMapping);
            }
            continue;
        }
        let expected_flags = if index == code_index {
            PRESENT | USER
        } else {
            PRESENT | WRITE | USER | NX
        };
        if entry & !(mask | ACCESSED | DIRTY) != expected_flags {
            return Err(Error::LeafEntry);
        }
        let physical = entry & mask;
        if !handles[1..]
            .iter()
            .flatten()
            .any(|handle| handle.page_count == 1 && handle.start_page * PAGE_BYTES == physical)
        {
            return Err(Error::Ownership);
        }
        // Compare against the owner's mapping, in addition to the raw PTE flags.
        let virtual_address = if index == code_index {
            image.code_page
        } else {
            image.stack_page
        };
        let (owned_frame, permissions, cache) = space
            .owned_mapping(virtual_address)
            .ok_or(Error::Ownership)?;
        let expected_permissions = if index == code_index {
            vm::Permissions::USER_RX
        } else {
            vm::Permissions::USER_RW
        };
        if owned_frame.start_page * PAGE_BYTES != physical
            || permissions != expected_permissions
            || cache != vm::CachePolicy::WriteBack
        {
            return Err(Error::Ownership);
        }
        if index == code_index {
            code_physical = physical;
        } else {
            stack_physical = physical;
        }
    }
    if code_physical == stack_physical {
        return Err(Error::PhysicalAlias);
    }
    Ok(ImageAdmission {
        root_physical: root,
        root_generation: summary.root_generation,
        code_physical,
        stack_physical,
        initial_frame: InitialReturnFrame {
            rip: image.entry,
            cs: USER_CODE_SELECTOR,
            rflags: INITIAL_RFLAGS,
            rsp: image.stack_page + PAGE_BYTES,
            ss: USER_DATA_SELECTOR,
        },
    })
}

#[cfg(test)]
#[path = "user_entry/tests.rs"]
mod tests;
