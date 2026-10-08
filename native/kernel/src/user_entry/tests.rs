use super::*;
use crate::physical_memory::Zone;
use crate::virtual_memory::{CachePolicy, Permissions};

#[derive(Clone)]
struct Memory {
    base: u64,
    pages: [[u64; 512]; 4],
    reads: usize,
    writes: usize,
    fail_at: Option<usize>,
}

impl Memory {
    fn location(&self, table: u64, index: usize) -> Result<usize, vm::Error> {
        let offset = table
            .checked_sub(self.base)
            .ok_or(vm::Error::MemoryAccess)?;
        if !offset.is_multiple_of(PAGE_BYTES) || offset >= 4 * PAGE_BYTES || index >= 512 {
            return Err(vm::Error::MemoryAccess);
        }
        Ok((offset / PAGE_BYTES) as usize)
    }
}

impl TableMemory for Memory {
    fn prepare_page(&mut self, address: u64) -> Result<(), vm::Error> {
        self.location(address, 0).map(|_| ())
    }
    fn read_entry(&mut self, address: u64, index: usize) -> Result<u64, vm::Error> {
        if self.fail_at == Some(self.reads) {
            return Err(vm::Error::MemoryAccess);
        }
        self.reads += 1;
        Ok(self.pages[self.location(address, index)?][index])
    }
    fn write_entry(&mut self, address: u64, index: usize, value: u64) -> Result<(), vm::Error> {
        let page = self.location(address, index)?;
        self.pages[page][index] = value;
        self.writes += 1;
        Ok(())
    }
    fn finish(&mut self) -> Result<(), vm::Error> {
        Ok(())
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

fn fixture() -> (PhysicalMemoryManager, AddressSpace, Memory, InitialImage) {
    let mut manager = PhysicalMemoryManager::test_manager(4096, 64, 16);
    let tables = manager
        .allocate(Zone::Dma32, vm::TABLE_PAGE_COUNT, vm::TABLE_OWNER)
        .unwrap();
    let code = manager.allocate(Zone::Dma32, 1, vm::DATA_OWNER).unwrap();
    let stack = manager.allocate(Zone::Dma32, 1, vm::DATA_OWNER).unwrap();
    let mut memory = Memory {
        base: tables.start_page * PAGE_BYTES,
        pages: [[0; 512]; 4],
        reads: 0,
        writes: 0,
        fail_at: None,
    };
    let image = InitialImage {
        code_page: USER_WINDOW_START,
        entry: USER_WINDOW_START + 16,
        stack_page: USER_WINDOW_START + 3 * PAGE_BYTES,
    };
    let mut space = AddressSpace::initialize(&manager, tables, &mut memory).unwrap();
    space
        .map(
            &manager,
            &mut memory,
            image.code_page,
            code,
            Permissions::USER_RX,
            CachePolicy::WriteBack,
        )
        .unwrap();
    space
        .map(
            &manager,
            &mut memory,
            image.stack_page,
            stack,
            Permissions::USER_RW,
            CachePolicy::WriteBack,
        )
        .unwrap();
    memory.reads = 0;
    (manager, space, memory, image)
}

#[test]
fn admits_real_vm_tree_with_guarded_stack_and_fixed_unprivileged_frame() {
    let (manager, space, mut memory, image) = fixture();
    let before = memory.pages;
    let writes = memory.writes;
    let admitted = admit_initial_image(&manager, &space, &mut memory, image, 36).unwrap();
    assert_eq!(admitted.root_physical, space.summary().root_physical);
    assert_eq!(admitted.root_generation, space.summary().root_generation);
    assert_ne!(admitted.code_physical, admitted.stack_physical);
    assert_eq!(
        admitted.initial_frame,
        InitialReturnFrame {
            rip: image.entry,
            cs: 0x33,
            rflags: 0x202,
            rsp: image.stack_page + PAGE_BYTES,
            ss: 0x2b,
        }
    );
    assert_eq!(admitted.initial_frame.rsp % 16, 0);
    assert_eq!(memory.reads, 2048);
    assert_eq!(memory.writes, writes);
    assert_eq!(memory.pages, before);
}

#[test]
fn freezes_iret_frame_layout_and_user_descriptors_without_changing_kernel_gdt() {
    use core::mem::{offset_of, size_of};
    assert_eq!(size_of::<InitialReturnFrame>(), 40);
    assert_eq!(offset_of!(InitialReturnFrame, rip), 0);
    assert_eq!(offset_of!(InitialReturnFrame, cs), 8);
    assert_eq!(offset_of!(InitialReturnFrame, rflags), 16);
    assert_eq!(offset_of!(InitialReturnFrame, rsp), 24);
    assert_eq!(offset_of!(InitialReturnFrame, ss), 32);
    assert_eq!(crate::GDT_LIMIT, 39);
    assert_eq!(USER_GDT_LIMIT, 55);
    assert_eq!(USER_DATA_SELECTOR & 7, 3);
    assert_eq!(USER_CODE_SELECTOR, USER_DATA_SELECTOR + 8);
    assert_eq!((USER_CODE_DESCRIPTOR >> 40) & 0xff, 0xfa);
    assert_eq!((USER_DATA_DESCRIPTOR >> 40) & 0xff, 0xf2);
    assert_eq!((USER_CODE_DESCRIPTOR >> 53) & 3, 1); // L=1, D=0.
    assert_eq!(
        INITIAL_RFLAGS & ((3 << 12) | (1 << 14) | (1 << 17) | (1 << 18)),
        0
    );
}

#[test]
fn rejects_every_invalid_physical_width_before_reading() {
    let (manager, space, mut memory, image) = fixture();
    for bits in 0..=u8::MAX {
        let result = admit_initial_image(&manager, &space, &mut memory, image, bits);
        if (36..=52).contains(&bits) {
            assert!(result.is_ok());
        } else {
            assert_eq!(result, Err(Error::PhysicalWidth));
        }
    }
}

#[test]
fn rejects_layout_overflows_noncanonical_kernel_and_guard_addresses() {
    let (manager, space, mut memory, image) = fixture();
    for address in [
        0,
        1,
        u64::MAX,
        vm::KERNEL_IMAGE_START,
        vm::USER_END_EXCLUSIVE,
        USER_WINDOW_START - PAGE_BYTES,
        USER_WINDOW_END_EXCLUSIVE,
        USER_WINDOW_START + 1,
    ] {
        for bad in [
            InitialImage {
                code_page: address,
                ..image
            },
            InitialImage {
                stack_page: address,
                ..image
            },
        ] {
            assert_eq!(
                admit_initial_image(&manager, &space, &mut memory, bad, 36),
                Err(Error::Layout)
            );
        }
    }
    assert_eq!(memory.reads, 0);
    for entry in [
        image.code_page - 1,
        image.code_page + PAGE_BYTES,
        u64::MAX,
        vm::KERNEL_IMAGE_START,
    ] {
        assert_eq!(
            admit_initial_image(
                &manager,
                &space,
                &mut memory,
                InitialImage { entry, ..image },
                36
            ),
            Err(Error::Layout)
        );
    }
}

#[test]
fn requires_both_stack_guards_and_separate_code() {
    let (manager, space, mut memory, image) = fixture();
    for stack_page in [USER_WINDOW_START, USER_WINDOW_END_EXCLUSIVE - PAGE_BYTES] {
        assert_eq!(
            admit_initial_image(
                &manager,
                &space,
                &mut memory,
                InitialImage {
                    stack_page,
                    ..image
                },
                36
            ),
            Err(Error::Layout)
        );
    }
    for code_page in [
        image.stack_page - PAGE_BYTES,
        image.stack_page,
        image.stack_page + PAGE_BYTES,
    ] {
        assert_eq!(
            admit_initial_image(
                &manager,
                &space,
                &mut memory,
                InitialImage {
                    code_page,
                    entry: code_page,
                    ..image
                },
                36
            ),
            Err(Error::Layout)
        );
    }
}

#[test]
fn rejects_each_parent_bit_mutation_except_hardware_accessed() {
    let (manager, space, memory, image) = fixture();
    for (level, index) in [0, 1, 0].into_iter().enumerate() {
        for bit in 0..64 {
            let mut changed = memory.clone();
            changed.pages[level][index] ^= 1 << bit;
            let result = admit_initial_image(&manager, &space, &mut changed, image, 36);
            if bit == 5 {
                assert!(result.is_ok());
            } else {
                assert_eq!(result, Err(Error::ParentEntry), "level={level} bit={bit}");
            }
        }
    }
}

#[test]
fn rejects_each_leaf_bit_mutation_except_hardware_accessed_dirty() {
    let (manager, space, memory, image) = fixture();
    for leaf in [0, 3] {
        for bit in 0..64 {
            let mut changed = memory.clone();
            changed.pages[3][leaf] ^= 1 << bit;
            let result = admit_initial_image(&manager, &space, &mut changed, image, 36);
            if bit == 5 || bit == 6 {
                assert!(result.is_ok());
            } else {
                assert!(result.is_err(), "leaf={leaf} bit={bit}");
            }
        }
    }
}

#[test]
fn rejects_hidden_mappings_and_nonzero_nonpresent_entries_at_every_level() {
    let (manager, space, memory, image) = fixture();
    for level in 0..4 {
        for index in [2, 4, 255, 256, 511] {
            for value in [PRESENT, USER, 1 << 7, NX, u64::MAX] {
                let mut changed = memory.clone();
                changed.pages[level][index] = value;
                assert_eq!(
                    admit_initial_image(&manager, &space, &mut changed, image, 36),
                    Err(Error::UnexpectedMapping)
                );
            }
        }
    }
}

#[test]
fn rejects_every_read_failure_without_writing_or_admitting() {
    let (manager, space, memory, image) = fixture();
    for read in 0..2048 {
        let mut changed = memory.clone();
        changed.fail_at = Some(read);
        assert_eq!(
            admit_initial_image(&manager, &space, &mut changed, image, 36),
            Err(Error::TableAccess)
        );
        assert_eq!(changed.pages, memory.pages);
        assert_eq!(changed.writes, memory.writes);
    }
}

#[test]
fn rejects_physically_swapped_owned_frames_and_writable_executable_alias() {
    let (manager, space, memory, image) = fixture();
    let mask = physical_mask(36).unwrap();
    let code = memory.pages[3][0] & mask;
    let stack = memory.pages[3][3] & mask;
    for (code_target, stack_target) in [
        (stack, code),
        (code, code),
        (stack, stack),
        (memory.base, stack),
    ] {
        let mut changed = memory.clone();
        changed.pages[3][0] = code_target | PRESENT | USER;
        changed.pages[3][3] = stack_target | PRESENT | USER | WRITE | NX;
        assert_eq!(
            admit_initial_image(&manager, &space, &mut changed, image, 36),
            Err(Error::Ownership)
        );
    }
}

#[test]
fn rejects_freed_or_reused_table_and_data_allocations() {
    for index in 0..3 {
        let (mut manager, space, mut memory, image) = fixture();
        let handle = space.allocation_handles()[index].unwrap();
        manager.free(handle).unwrap();
        assert_eq!(
            admit_initial_image(&manager, &space, &mut memory, image, 36),
            Err(Error::Ownership)
        );
        let _replacement = manager
            .allocate(handle.zone, handle.page_count, handle.owner)
            .unwrap();
        assert_eq!(
            admit_initial_image(&manager, &space, &mut memory, image, 36),
            Err(Error::Ownership)
        );
    }
}

#[test]
fn rejects_pending_teardown_missing_or_extra_mapping() {
    let (manager, mut space, mut memory, image) = fixture();
    space.begin_unmap(&mut memory, image.stack_page).unwrap();
    assert_eq!(
        admit_initial_image(&manager, &space, &mut memory, image, 36),
        Err(Error::SpaceState)
    );
    let (manager, mut space, mut memory, image) = fixture();
    let frame = space.allocation_handles()[1].unwrap();
    space
        .map(
            &manager,
            &mut memory,
            USER_WINDOW_START + 7 * PAGE_BYTES,
            frame,
            Permissions::USER_RX,
            CachePolicy::WriteBack,
        )
        .unwrap();
    assert_eq!(
        admit_initial_image(&manager, &space, &mut memory, image, 36),
        Err(Error::SpaceState)
    );
}

#[test]
fn rejects_owner_permission_drift_even_if_raw_bytes_are_repaired() {
    let (manager, mut space, mut memory, image) = fixture();
    let original = memory.pages[3][0];
    space
        .protect(&mut memory, image.code_page, Permissions::USER_RW)
        .unwrap();
    memory.pages[3][0] = original;
    assert_eq!(
        admit_initial_image(&manager, &space, &mut memory, image, 36),
        Err(Error::Ownership)
    );
}

#[test]
fn permits_entry_byte_boundaries_and_records_no_execution_authority() {
    let (manager, space, mut memory, image) = fixture();
    for entry in [image.code_page, image.code_page + PAGE_BYTES - 1] {
        let admitted = admit_initial_image(
            &manager,
            &space,
            &mut memory,
            InitialImage { entry, ..image },
            36,
        )
        .unwrap();
        assert_eq!(admitted.initial_frame.rip, entry);
    }
    assert!(!space.summary().root_active);
}
