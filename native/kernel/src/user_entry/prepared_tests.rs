use super::*;
use crate::physical_memory::PhysicalMemoryError;
use crate::user_entry::timer;
use crate::virtual_memory::{CachePolicy, Permissions, USER_WINDOW_START};
use std::collections::BTreeMap;

#[path = "cpu_tests.rs"]
mod cpu_tests;

#[path = "spawn_tests.rs"]
mod spawn_tests;

#[derive(Clone)]
struct Memory {
    pages: BTreeMap<u64, [u64; 512]>,
    reads: usize,
    writes: usize,
    fail_read: Option<usize>,
    fail_write: Option<usize>,
    corrupt_write: Option<usize>,
    fail_finish: bool,
    corrupt_user_on_finish: Option<u64>,
}

impl TableMemory for Memory {
    fn prepare_page(&mut self, address: u64) -> Result<(), vm::Error> {
        self.pages.entry(address).or_insert([0xdead; 512]);
        Ok(())
    }
    fn read_entry(&mut self, address: u64, index: usize) -> Result<u64, vm::Error> {
        let count = self.reads;
        self.reads += 1;
        if self.fail_read == Some(count) {
            return Err(vm::Error::MemoryAccess);
        }
        self.pages
            .get(&address)
            .and_then(|p| p.get(index))
            .copied()
            .ok_or(vm::Error::MemoryAccess)
    }
    fn write_entry(&mut self, address: u64, index: usize, value: u64) -> Result<(), vm::Error> {
        let count = self.writes;
        self.writes += 1;
        let page = self
            .pages
            .get_mut(&address)
            .ok_or(vm::Error::MemoryAccess)?;
        // A failing write may have taken effect: cleanup must not assume otherwise.
        page[index] = if self.corrupt_write == Some(count) {
            value ^ 1
        } else {
            value
        };
        if self.fail_write == Some(count) {
            return Err(vm::Error::MemoryAccess);
        }
        Ok(())
    }
    fn finish(&mut self) -> Result<(), vm::Error> {
        if let Some(root) = self.corrupt_user_on_finish.take() {
            self.pages.get_mut(&root).unwrap()[0] = 0;
        }
        if self.fail_finish {
            Err(vm::Error::MemoryAccess)
        } else {
            Ok(())
        }
    }
    fn physical_write_count(&self) -> u64 {
        self.writes as u64
    }
    fn temporary_pte_write_count(&self) -> u64 {
        0
    }
    fn hardware_invalidation_count(&self) -> u64 {
        0
    }
}

struct Fixture {
    manager: PhysicalMemoryManager,
    parts: DetachedImage,
    memory: Memory,
    image: InitialImage,
    core: CoreRecord,
}

impl Fixture {
    fn new() -> Self {
        let mut manager = PhysicalMemoryManager::test_manager(4096, 64, 32);
        let tables = manager.allocate(Zone::Dma32, 4, vm::TABLE_OWNER).unwrap();
        let code = manager.allocate(Zone::Dma32, 1, vm::DATA_OWNER).unwrap();
        let user_stack = manager.allocate(Zone::Dma32, 1, vm::DATA_OWNER).unwrap();
        let stack = manager
            .allocate(Zone::Dma32, STACK_PAGE_COUNT, STACK_OWNER)
            .unwrap();
        let stack_tables = manager
            .allocate(Zone::Dma32, STACK_TABLE_PAGES, STACK_TABLE_OWNER)
            .unwrap();
        let mut memory = Memory {
            pages: BTreeMap::new(),
            reads: 0,
            writes: 0,
            fail_read: None,
            fail_write: None,
            corrupt_write: None,
            fail_finish: false,
            corrupt_user_on_finish: None,
        };
        let mut space = AddressSpace::initialize(&manager, tables, &mut memory).unwrap();
        let image = InitialImage {
            code_page: USER_WINDOW_START,
            entry: USER_WINDOW_START + 16,
            stack_page: USER_WINDOW_START + 3 * PAGE_BYTES,
        };
        for (address, frame, permissions) in [
            (image.code_page, code, Permissions::USER_RX),
            (image.stack_page, user_stack, Permissions::USER_RW),
        ] {
            space
                .map(
                    &manager,
                    &mut memory,
                    address,
                    frame,
                    permissions,
                    CachePolicy::WriteBack,
                )
                .unwrap();
        }
        let root = 0x100000;
        let core = CoreRecord {
            boot_flags: 0,
            kernel_physical_base: 0x200000,
            kernel_physical_size: 3 * PAGE_BYTES,
            kernel_virtual_base: vm::KERNEL_IMAGE_START,
            kernel_virtual_size: 3 * PAGE_BYTES,
            kernel_entry_virtual: vm::KERNEL_IMAGE_START + 16,
            initial_stack_top_virtual: vm::KERNEL_IMAGE_START
                + kmap::STACK_GUARD_HIGH_PAGE as u64 * PAGE_BYTES,
            page_table_root_physical: root,
            handoff_physical_base: 0x400000,
            handoff_virtual_base: vm::KERNEL_IMAGE_START
                + kmap::HANDOFF_FIRST_PAGE as u64 * PAGE_BYTES,
            handoff_byte_count: 512,
            uefi_system_table_physical: 0,
            uefi_runtime_services_physical: 0,
            boot_attempt: 1,
            boot_attempt_limit: 3,
            boot_slot: 0,
            selected_entry: 0,
            uefi_revision: 0,
        };
        for page in 0..5 {
            memory.pages.insert(root + page * PAGE_BYTES, [0; 512]);
        }
        memory.pages.get_mut(&root).unwrap()[511] = (root + PAGE_BYTES) | P | W | A;
        // Firmware identity mappings are deliberately not inherited.
        memory.pages.get_mut(&root).unwrap()[0] = 0x900003;
        memory.pages.get_mut(&(root + PAGE_BYTES)).unwrap()[510] =
            (root + 2 * PAGE_BYTES) | P | W | A;
        for index in 0..2 {
            memory.pages.get_mut(&(root + 2 * PAGE_BYTES)).unwrap()[index] =
                (root + (3 + index as u64) * PAGE_BYTES) | P | W;
        }
        for index in 0..kmap::RETAINED_TABLE_ENTRIES {
            let entry = if index < 3 {
                core.kernel_physical_base + index as u64 * PAGE_BYTES
                    | [P, P | NX, P | W | NX][index]
            } else if (kmap::STACK_FIRST_PAGE..kmap::STACK_GUARD_HIGH_PAGE).contains(&index) {
                (0x300000 + (index - kmap::STACK_FIRST_PAGE) as u64 * PAGE_BYTES) | P | W | NX
            } else if (kmap::HANDOFF_FIRST_PAGE..kmap::TEMPORARY_PAGE_INDEX).contains(&index) {
                (core.handoff_physical_base
                    + (index - kmap::HANDOFF_FIRST_PAGE) as u64 * PAGE_BYTES)
                    | P
                    | NX
            } else {
                0
            };
            memory
                .pages
                .get_mut(&(root + (3 + index / 512) as u64 * PAGE_BYTES))
                .unwrap()[index % 512] = entry;
        }
        memory.reads = 0;
        memory.writes = 0;
        Self {
            manager,
            parts: DetachedImage {
                space,
                stack,
                stack_tables,
            },
            memory,
            image,
            core,
        }
    }

    fn handles(&self) -> std::vec::Vec<AllocationHandle> {
        let mut handles: std::vec::Vec<_> = self
            .parts
            .space
            .allocation_handles()
            .into_iter()
            .flatten()
            .collect();
        handles.extend([self.parts.stack, self.parts.stack_tables]);
        handles
    }
}

fn ready(f: Fixture) -> (PhysicalMemoryManager, Memory, PreparedImage) {
    let Fixture {
        mut manager,
        parts,
        mut memory,
        image,
        core,
    } = f;
    let prepared = PreparedImage::prepare(parts, &mut manager, &mut memory, image, core, 36)
        .unwrap_or_else(|(e, _)| panic!("prepare: {e:?}"));
    (manager, memory, prepared)
}

fn retained(manager: &mut PhysicalMemoryManager, handles: &[AllocationHandle]) {
    for &h in handles {
        assert_eq!(
            manager.free(h),
            Err(PhysicalMemoryError::AllocationRetained)
        );
    }
}

fn ready_timer(f: Fixture) -> (PhysicalMemoryManager, Memory, PreparedImage) {
    let Fixture {
        mut manager,
        parts,
        mut memory,
        image,
        core,
    } = f;
    let prepared = PreparedImage::prepare_with_timer(
        parts,
        &mut manager,
        &mut memory,
        image,
        core,
        36,
        timer::Mappings::fixture(),
    )
    .unwrap_or_else(|(e, _)| panic!("{e:?}"));
    (manager, memory, prepared)
}

#[test]
fn attached_hardware_accessed_dirty_bits_survive_read_only_revalidation() {
    let f = Fixture::new();
    let core = f.core;
    let root = f.parts.space.summary().root_physical;
    let tables = f.parts.stack_tables.start_page * PAGE_BYTES;
    let (manager, mut memory, prepared) = ready_timer(f);
    for index in [STACK_SLOT, KERNEL_SLOT] {
        memory.pages.get_mut(&root).unwrap()[index] |= A;
    }
    for page in 0..2 {
        memory.pages.get_mut(&(tables + page * PAGE_BYTES)).unwrap()[0] |= A;
    }
    for entry in memory.pages.get_mut(&(tables + 2 * PAGE_BYTES)).unwrap() {
        if *entry & P != 0 {
            *entry |= A | D;
        }
    }
    let before = memory.pages.clone();
    let writes = memory.writes;
    assert_eq!(
        prepared.revalidate(&manager, &mut memory, core).unwrap(),
        prepared.admission().unwrap()
    );
    assert_eq!(memory.pages, before);
    assert_eq!(memory.writes, writes);
}

#[test]
fn attached_resume_rejects_dirty_parents_guard_bits_and_permission_drift() {
    for (page, index, bit) in [
        (3, STACK_SLOT, D),
        (3, KERNEL_SLOT, D),
        (3, 255, A),
        (0, 0, D),
        (1, 0, D),
        (0, 1, A),
        (1, 1, D),
        (2, 0, A),
        (2, 5, D),
        (2, 15, A),
        (2, 17, D),
        (2, 19, A),
        (2, 1, W),
        (2, 1, NX),
        (2, 1, 1 << 2),
        (2, 16, W),
        (2, 18, NX),
        (2, 18, 1 << 2),
    ] {
        let f = Fixture::new();
        let core = f.core;
        let root = f.parts.space.summary().root_physical;
        let tables = f.parts.stack_tables.start_page * PAGE_BYTES;
        let (manager, mut memory, prepared) = ready_timer(f);
        let table = if page == 3 {
            root
        } else {
            tables + page * PAGE_BYTES
        };
        memory.pages.get_mut(&table).unwrap()[index] ^= bit;
        assert!(
            prepared.revalidate(&manager, &mut memory, core).is_err(),
            "{page}/{index}/{bit}"
        );
    }
}

#[test]
fn timer_leaves_and_guards_are_replayed_before_admission() {
    for index in [15, 16, 17, 18, 19] {
        let f = Fixture::new();
        let pt = (f.parts.stack_tables.start_page + 2) * PAGE_BYTES;
        let core = f.core;
        let (manager, mut memory, prepared) = ready_timer(f);
        prepared.revalidate(&manager, &mut memory, core).unwrap();
        memory.pages.get_mut(&pt).unwrap()[index] ^= 1 << 2;
        assert!(prepared.revalidate(&manager, &mut memory, core).is_err());
    }
}

#[test]
fn timer_boot_alias_rejects_before_any_candidate_write() {
    let mut f = Fixture::new();
    f.core.kernel_physical_base = timer::Mappings::fixture().pages()[0];
    let before = f.memory.writes;
    assert!(
        PreparedImage::prepare_with_timer(
            f.parts,
            &mut f.manager,
            &mut f.memory,
            f.image,
            f.core,
            36,
            timer::Mappings::fixture()
        )
        .is_err()
    );
    assert_eq!(f.memory.writes, before);
}

#[test]
fn installs_exact_supervisor_root_and_guarded_entry_stack_then_detaches() {
    let f = Fixture::new();
    let handles = f.handles();
    let user_root = f.parts.space.summary().root_physical;
    let original = f.memory.pages.clone();
    let (mut manager, mut memory, prepared) = ready(f);
    assert!(prepared.admission().is_some());
    assert_eq!(STACK_TOP - STACK_BOTTOM, 16384);
    let tables = prepared.stack_tables.start_page * PAGE_BYTES;
    assert_eq!(memory.pages[&user_root][256], tables | P | W | NX);
    assert_eq!(memory.pages[&user_root][511], 0x101003);
    assert_eq!(memory.pages[&user_root][0], original[&user_root][0]);
    for (&table, page) in &original {
        if table != user_root {
            assert_eq!(&memory.pages[&table], page);
        }
    }
    assert_eq!(memory.pages[&(tables + 2 * PAGE_BYTES)][0], 0);
    assert_eq!(memory.pages[&(tables + 2 * PAGE_BYTES)][5], 0);
    retained(&mut manager, &handles);
    let parts = prepared
        .abort(&mut manager, &mut memory)
        .unwrap_or_else(|(e, _)| panic!("abort: {e:?}"));
    assert_eq!(memory.pages[&user_root], original[&user_root]);
    for page in 0..3 {
        assert_eq!(memory.pages[&(tables + page * PAGE_BYTES)], [0; 512]);
    }
    assert!(
        super::super::admit_initial_image(
            &manager,
            &parts.space,
            &mut memory,
            InitialImage {
                code_page: USER_WINDOW_START,
                entry: USER_WINDOW_START + 16,
                stack_page: USER_WINDOW_START + 3 * PAGE_BYTES
            },
            36
        )
        .is_ok()
    );
    for h in handles {
        manager.free(h).unwrap();
    }
}

#[test]
fn forgotten_owner_keeps_all_allocations_retained() {
    let f = Fixture::new();
    let handles = f.handles();
    let (mut manager, _, prepared) = ready(f);
    drop(prepared);
    retained(&mut manager, &handles);
}

#[test]
fn rejects_stale_and_competing_ownership_without_any_write() {
    for mode in 0..3 {
        let mut f = Fixture::new();
        if mode == 0 {
            f.manager.free(f.parts.stack).unwrap();
        }
        if mode == 1 {
            let _held = f.manager.retain_allocation(f.parts.stack_tables).unwrap();
        }
        if mode == 2 {
            f.parts.stack = f.parts.stack_tables;
        }
        let (error, owner) =
            PreparedImage::prepare(f.parts, &mut f.manager, &mut f.memory, f.image, f.core, 36)
                .err()
                .unwrap();
        assert_eq!(error, Error::Ownership);
        assert_eq!(f.memory.writes, 0);
        assert!(owner.admission().is_none());
    }
}

#[test]
fn rejects_bad_entry_stack_layout_without_any_write() {
    for mode in 0..3 {
        let mut f = Fixture::new();
        let h = match mode {
            0 => f.manager.allocate(Zone::Dma32, 3, STACK_OWNER).unwrap(),
            1 => f.manager.allocate(Zone::Dma32, 4, STACK_OWNER + 1).unwrap(),
            _ => f
                .manager
                .allocate(Zone::Dma32, 4, STACK_TABLE_OWNER)
                .unwrap(),
        };
        if mode < 2 {
            f.parts.stack = h;
        } else {
            f.parts.stack_tables = h;
        }
        let (error, _) =
            PreparedImage::prepare(f.parts, &mut f.manager, &mut f.memory, f.image, f.core, 36)
                .err()
                .unwrap();
        assert_eq!(error, Error::Layout);
        assert_eq!(f.memory.writes, 0);
    }
}

#[test]
fn rejects_each_disallowed_supervisor_parent_and_leaf_bit() {
    for (page, index, permitted) in [
        (0, 511, A),
        (1, 510, A),
        (2, 0, A),
        (3, 0, A | D),
        (3, kmap::STACK_FIRST_PAGE, A | D),
        (3, kmap::HANDOFF_FIRST_PAGE, A | D),
    ] {
        for bit in 0..64 {
            if permitted & (1u64 << bit) != 0 {
                continue;
            }
            let mut f = Fixture::new();
            f.memory
                .pages
                .get_mut(&(f.core.page_table_root_physical + page * PAGE_BYTES))
                .unwrap()[index] ^= 1u64 << bit;
            let result =
                PreparedImage::prepare(f.parts, &mut f.manager, &mut f.memory, f.image, f.core, 36);
            assert!(result.is_err(), "page={page} index={index} bit={bit}");
            assert_eq!(f.memory.writes, 0);
        }
    }
}

#[test]
fn rejects_hidden_supervisor_branches_guards_and_boot_aliases() {
    for mode in 0..7 {
        let mut f = Fixture::new();
        let root = f.core.page_table_root_physical;
        match mode {
            0 => f.memory.pages.get_mut(&(root + PAGE_BYTES)).unwrap()[0] = 0x1003,
            1 => f.memory.pages.get_mut(&(root + 2 * PAGE_BYTES)).unwrap()[2] = 0x1003,
            2 => {
                f.memory.pages.get_mut(&(root + 3 * PAGE_BYTES)).unwrap()
                    [kmap::STACK_GUARD_LOW_PAGE] = 0x1003 | NX
            }
            3 => {
                f.memory.pages.get_mut(&(root + 3 * PAGE_BYTES)).unwrap()
                    [kmap::STACK_GUARD_HIGH_PAGE] = 0x1003 | NX
            }
            4 => f.memory.pages.get_mut(&(root + 4 * PAGE_BYTES)).unwrap()[511] = 0x1003 | NX,
            5 => f.core.kernel_physical_base = f.parts.stack.start_page * PAGE_BYTES,
            _ => {
                f.memory.pages.get_mut(&(root + 3 * PAGE_BYTES)).unwrap()[kmap::STACK_FIRST_PAGE] =
                    f.core.kernel_physical_base | P | W | NX
            }
        }
        assert!(
            PreparedImage::prepare(f.parts, &mut f.manager, &mut f.memory, f.image, f.core, 36)
                .is_err()
        );
        assert_eq!(f.memory.writes, 0);
    }
}

#[test]
fn every_partial_write_and_silent_corruption_quarantines_then_retries_cleanup() {
    let (_, memory, _) = ready(Fixture::new());
    assert_eq!(memory.writes, 1544);
    for corrupt in [false, true] {
        for fail in 0..memory.writes {
            let mut f = Fixture::new();
            let handles = f.handles();
            if corrupt {
                f.memory.corrupt_write = Some(fail);
            } else {
                f.memory.fail_write = Some(fail);
            }
            let (error, owner) =
                PreparedImage::prepare(f.parts, &mut f.manager, &mut f.memory, f.image, f.core, 36)
                    .err()
                    .unwrap();
            assert_eq!(
                error,
                if corrupt {
                    Error::Readback
                } else {
                    Error::Memory
                }
            );
            assert!(owner.admission().is_none());
            retained(&mut f.manager, &handles);
            f.memory.fail_write = None;
            f.memory.corrupt_write = None;
            owner
                .abort(&mut f.manager, &mut f.memory)
                .unwrap_or_else(|(e, _)| panic!("{fail}: {e:?}"));
            for h in handles {
                f.manager.free(h).unwrap();
            }
        }
    }
}

#[test]
fn failed_detach_and_finish_keep_retention_until_verified_retry() {
    for mode in 0..3 {
        let f = Fixture::new();
        let handles = f.handles();
        let (mut manager, mut memory, owner) = ready(f);
        if mode == 0 {
            memory.fail_write = Some(memory.writes);
        }
        if mode == 1 {
            memory.corrupt_write = Some(memory.writes + 1);
        }
        if mode == 2 {
            memory.fail_finish = true;
        }
        let (_, owner) = owner.abort(&mut manager, &mut memory).err().unwrap();
        retained(&mut manager, &handles);
        assert!(owner.admission().is_none());
        memory.fail_write = None;
        memory.corrupt_write = None;
        memory.fail_finish = false;
        assert!(owner.abort(&mut manager, &mut memory).is_ok());
        for h in handles {
            manager.free(h).unwrap();
        }
    }
}

#[test]
fn post_write_user_corruption_rejects_and_stays_quarantined() {
    let mut f = Fixture::new();
    let handles = f.handles();
    f.memory.corrupt_user_on_finish = Some(f.parts.space.summary().root_physical);
    let (error, owner) =
        PreparedImage::prepare(f.parts, &mut f.manager, &mut f.memory, f.image, f.core, 36)
            .err()
            .unwrap();
    assert_eq!(error, Error::Image(super::super::Error::ParentEntry));
    retained(&mut f.manager, &handles);
    assert!(owner.abort(&mut f.manager, &mut f.memory).is_err());
    retained(&mut f.manager, &handles);
}

#[test]
fn wrong_manager_cannot_write_during_abort() {
    let other = Fixture::new();
    let (mut foreign, _, foreign_owner) = ready(other);
    let (_, mut memory, owner) = ready(Fixture::new());
    let writes = memory.writes;
    let (error, _) = owner.abort(&mut foreign, &mut memory).err().unwrap();
    assert_eq!(error, Error::Ownership);
    assert_eq!(memory.writes, writes);
    drop(foreign_owner);
}

#[test]
fn fails_closed_at_every_table_read_without_releasing_owned_pages() {
    let (_, memory, _) = ready(Fixture::new());
    for fail in 0..memory.reads {
        let mut f = Fixture::new();
        let handles = f.handles();
        f.memory.fail_read = Some(fail);
        let (_, owner) =
            PreparedImage::prepare(f.parts, &mut f.manager, &mut f.memory, f.image, f.core, 36)
                .err()
                .unwrap();
        assert!(owner.admission().is_none());
        if owner.retained.iter().any(Option::is_some) {
            retained(&mut f.manager, &handles);
        }
        f.memory.fail_read = None;
        assert!(
            owner.abort(&mut f.manager, &mut f.memory).is_ok(),
            "read {fail}"
        );
    }
}

#[test]
fn finish_failure_and_malformed_core_never_produce_admission() {
    for mode in 0..9 {
        let mut f = Fixture::new();
        match mode {
            0 => f.core.kernel_entry_virtual = vm::USER_WINDOW_START,
            1 => f.core.kernel_physical_size = u64::MAX,
            2 => f.core.page_table_root_physical = u64::MAX,
            3 => f.core.handoff_physical_base = (1 << 36) - PAGE_BYTES,
            4 => f.core.initial_stack_top_virtual += 16,
            5 => f.core.kernel_virtual_size += 1,
            6 => f.core.handoff_byte_count = 0,
            7 => f.core.handoff_physical_base = f.core.kernel_physical_base,
            _ => f.memory.fail_finish = true,
        }
        let (_, owner) =
            PreparedImage::prepare(f.parts, &mut f.manager, &mut f.memory, f.image, f.core, 36)
                .err()
                .unwrap();
        assert!(owner.admission().is_none());
        if mode != 8 {
            assert_eq!(f.memory.writes, 0);
        }
        f.memory.fail_finish = false;
        assert!(owner.abort(&mut f.manager, &mut f.memory).is_ok());
    }
}
