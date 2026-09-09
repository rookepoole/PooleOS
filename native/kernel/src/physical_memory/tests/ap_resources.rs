use super::*;
use crate::reclamation::ap_resources::{ApResources, Error as ApError, Part, State};
use crate::smp_runtime;

const PARTS: [Part; 3] = [Part::Runtime, Part::OldFrame, Part::NewFrame];

fn fixture() -> (PhysicalMemoryManager, FakePageAccess, [AllocationHandle; 3]) {
    let mut manager = PhysicalMemoryManager::test_manager(16, 200, 200);
    let runtime = manager
        .allocate(Zone::Dma, smp_runtime::RESOURCE_PAGE_COUNT, 7)
        .unwrap();
    let old = manager.allocate(Zone::Dma, 1, 8).unwrap();
    let new = manager.allocate(Zone::Dma, 1, 8).unwrap();
    (
        manager,
        FakePageAccess::new(16, 200, STALE_PATTERN),
        [runtime, old, new],
    )
}

fn owner(manager: &mut PhysicalMemoryManager, handles: [AllocationHandle; 3]) -> ApResources {
    ApResources::new(manager, 1, handles[0], handles[1], handles[2]).unwrap()
}

fn retained(
    manager: &mut PhysicalMemoryManager,
    access: &mut FakePageAccess,
    handles: &[AllocationHandle],
) {
    let before = manager.summary();
    let effects = (access.read_count, access.write_count);
    for &handle in handles {
        assert_eq!(
            manager.free(handle),
            Err(PhysicalMemoryError::AllocationRetained)
        );
        assert_eq!(
            manager.free_scrubbed(handle, access),
            Err(PhysicalMemoryError::AllocationRetained)
        );
        assert_eq!(
            manager.free_scrubbed_automatic(handle, access),
            Err(PhysicalMemoryError::AllocationRetained)
        );
    }
    assert_eq!(manager.summary(), before);
    assert_eq!((access.read_count, access.write_count), effects);
}

fn release(
    owner: &mut ApResources,
    part: Part,
    manager: &mut PhysicalMemoryManager,
    access: &mut FakePageAccess,
    automatic: bool,
) -> Result<ScrubReceipt, ApError> {
    if automatic {
        owner.release_scrubbed_automatic(part, manager, access)
    } else {
        owner.release_scrubbed(part, manager, access)
    }
}

#[test]
fn ap_admission_retains_runtime_stacks_and_both_frames() {
    let (mut manager, mut access, handles) = fixture();
    let owner = owner(&mut manager, handles);
    assert_eq!(owner.target_apic_id(), 1);
    assert_eq!(owner.state(), State::Prepared);
    assert_eq!(owner.possible_cpu_mask(), 0);
    for (part, handle) in PARTS.into_iter().zip(handles) {
        assert_eq!(owner.handle(part), handle);
        assert_eq!(owner.release_receipt(part), None);
    }
    retained(&mut manager, &mut access, &handles);
}

#[test]
fn ap_bad_targets_layout_and_late_conflicts_leave_earlier_members_unretained() {
    let (mut manager, _, handles) = fixture();
    for target in [0, 4, 63, 64, u32::MAX] {
        assert_eq!(
            ApResources::new(&mut manager, target, handles[0], handles[1], handles[2]).err(),
            Some(ApError::Target)
        );
    }
    assert_eq!(
        ApResources::new(&mut manager, 1, handles[1], handles[0], handles[2]).err(),
        Some(ApError::Layout)
    );
    assert_eq!(
        ApResources::new(&mut manager, 1, handles[0], handles[1], handles[1]).err(),
        Some(ApError::PhysicalMemory(
            PhysicalMemoryError::RetentionIdentity
        ))
    );
    let token = manager.retain_allocation(handles[2]).unwrap();
    assert_eq!(
        ApResources::new(&mut manager, 1, handles[0], handles[1], handles[2]).err(),
        Some(ApError::PhysicalMemory(
            PhysicalMemoryError::AllocationRetained
        ))
    );
    for &handle in &handles[..2] {
        let proof = manager.retain_allocation(handle).unwrap();
        manager.release_retention(proof).unwrap();
    }
    manager.release_retention(token).unwrap();
    for handle in handles {
        manager.free(handle).unwrap();
    }
}

#[test]
fn ap_never_started_cleanup_scrubs_and_commits_every_part_once() {
    for automatic in [false, true] {
        let (mut manager, mut access, handles) = fixture();
        let mut owner = owner(&mut manager, handles);
        for part in [Part::OldFrame, Part::NewFrame, Part::Runtime] {
            let receipt = release(&mut owner, part, &mut manager, &mut access, automatic).unwrap();
            assert_eq!(receipt.page_count, owner.handle(part).page_count);
            assert_eq!(receipt.zeroed_bytes, receipt.page_count * PAGE_BYTES);
            assert_eq!(receipt.verified_bytes, receipt.zeroed_bytes);
            assert_eq!(owner.release_receipt(part), Some(receipt));
            assert_eq!(
                release(&mut owner, part, &mut manager, &mut access, automatic),
                Err(ApError::Released)
            );
        }
        assert_eq!(owner.state(), State::Released);
        assert_eq!(manager.summary().allocated_pages, 0);
        assert_eq!(access.write_count, 34 * SCRUB_WORDS_PER_PAGE as u64);
        assert_eq!(access.read_count, access.write_count);
    }
}

#[test]
fn ap_possible_execution_rejects_every_release_without_memory_access() {
    let (mut manager, mut access, handles) = fixture();
    let mut owner = owner(&mut manager, handles);
    for target in [1, 2, 3] {
        owner.expose_to_cpu(target).unwrap();
    }
    assert_eq!(owner.possible_cpu_mask(), 14);
    for automatic in [false, true] {
        for part in PARTS {
            assert_eq!(
                release(&mut owner, part, &mut manager, &mut access, automatic),
                Err(ApError::State)
            );
        }
    }
    assert_eq!((access.write_count, access.read_count), (0, 0));
    retained(&mut manager, &mut access, &handles);
}

#[test]
fn ap_park_confirmation_requires_the_complete_exact_shared_alias_mask() {
    let (mut manager, mut access, handles) = fixture();
    let mut owner = owner(&mut manager, handles);
    for target in [1, 2, 3] {
        owner.expose_to_cpu(target).unwrap();
    }
    for mask in 0..32 {
        if mask != 14 {
            // SAFETY: this host test has never started a CPU on these pages.
            assert_eq!(
                unsafe { owner.confirm_parked(mask) },
                Err(ApError::ParkMask)
            );
            assert_eq!(owner.state(), State::MayExecute);
        }
    }
    retained(&mut manager, &mut access, &handles);
    // SAFETY: host-only pages have no executing CPUs or hardware aliases.
    unsafe { owner.confirm_parked(14) }.unwrap();
    assert_eq!(owner.state(), State::Parked);
    assert_eq!(owner.expose_to_cpu(1), Err(ApError::State));
    release(&mut owner, Part::OldFrame, &mut manager, &mut access, false).unwrap();
    retained(&mut manager, &mut access, &[handles[0], handles[2]]);
}

#[test]
fn ap_unknown_cpu_rejection_does_not_change_exposure() {
    let (mut manager, _, handles) = fixture();
    let mut owner = owner(&mut manager, handles);
    for target in [0, 4, 63, 64, u32::MAX] {
        assert_eq!(owner.expose_to_cpu(target), Err(ApError::Target));
        assert_eq!(owner.state(), State::Prepared);
        assert_eq!(owner.possible_cpu_mask(), 0);
    }
    owner.expose_to_cpu(2).unwrap();
    owner.expose_to_cpu(2).unwrap();
    assert_eq!(owner.possible_cpu_mask(), 4);
}

#[test]
fn ap_partial_start_and_missing_confirmation_preserve_all_resource_regions() {
    let mut manager = PhysicalMemoryManager::test_manager(16, 200, 200);
    let mut access = FakePageAccess::new(16, 200, STALE_PATTERN);
    let mut owners = [1, 2, 3].map(|target| {
        let runtime = manager.allocate(Zone::Dma, 32, 7).unwrap();
        let old = manager.allocate(Zone::Dma, 1, 8).unwrap();
        let new = manager.allocate(Zone::Dma, 1, 8).unwrap();
        ApResources::new(&mut manager, target, runtime, old, new).unwrap()
    });
    for target in [1, 2] {
        for owner in &mut owners {
            owner.expose_to_cpu(target).unwrap();
        }
    }
    for owner in &mut owners {
        assert_eq!(owner.possible_cpu_mask(), 6);
        // SAFETY: no physical CPU was started in this bounded host harness.
        assert_eq!(unsafe { owner.confirm_parked(2) }, Err(ApError::ParkMask));
        assert_eq!(
            release(owner, Part::Runtime, &mut manager, &mut access, true),
            Err(ApError::State)
        );
        retained(
            &mut manager,
            &mut access,
            &PARTS.map(|part| owner.handle(part)),
        );
        // SAFETY: all simulated users, including the uncertain second start, ended.
        unsafe { owner.confirm_parked(6) }.unwrap();
        for part in PARTS {
            release(owner, part, &mut manager, &mut access, true).unwrap();
        }
    }
    assert_eq!(manager.summary().allocated_pages, 0);
}

#[test]
fn ap_lost_owner_never_turns_drop_or_forget_into_cpu_quiescence() {
    for forget in [false, true] {
        let (mut manager, mut access, handles) = fixture();
        {
            let mut owner = owner(&mut manager, handles);
            owner.expose_to_cpu(1).unwrap();
            if forget {
                core::mem::forget(owner);
            }
        }
        retained(&mut manager, &mut access, &handles);
        assert_eq!(manager.summary().allocated_pages, 34);
    }
}

#[test]
fn ap_wrong_manager_cleanup_returns_the_owner_without_touching_memory() {
    for automatic in [false, true] {
        let (mut manager, mut access, handles) = fixture();
        let (mut other, _, matching) = fixture();
        assert_eq!(handles, matching);
        let mut owner = owner(&mut manager, handles);
        assert_eq!(
            release(
                &mut owner,
                Part::Runtime,
                &mut other,
                &mut access,
                automatic
            ),
            Err(ApError::PhysicalMemory(
                PhysicalMemoryError::RetentionIdentity
            ))
        );
        assert_eq!((access.read_count, access.write_count), (0, 0));
        retained(&mut manager, &mut access, &handles);
        for handle in matching {
            other.validate_allocation(handle).unwrap();
        }
        assert_eq!(owner.expose_to_cpu(1), Err(ApError::State));
        release(
            &mut owner,
            Part::Runtime,
            &mut manager,
            &mut access,
            automatic,
        )
        .unwrap();
    }
}

#[test]
fn ap_partial_scrub_failures_keep_ownership_and_close_startup_until_retry() {
    for automatic in [false, true] {
        for fault in 0..3 {
            let (mut manager, mut access, handles) = fixture();
            let mut owner = owner(&mut manager, handles);
            let page = handles[0].start_page + 1;
            match fault {
                0 => access.fail_write = Some((page, 9)),
                1 => access.fail_read = Some((page, 9)),
                _ => access.drop_write = Some((page, 9)),
            }
            let expected = if fault == 2 {
                PhysicalMemoryError::ScrubVerification
            } else {
                PhysicalMemoryError::ScrubAccess
            };
            assert_eq!(
                release(
                    &mut owner,
                    Part::Runtime,
                    &mut manager,
                    &mut access,
                    automatic
                ),
                Err(ApError::PhysicalMemory(expected))
            );
            assert_eq!(owner.state(), State::Releasing);
            assert_eq!(owner.release_receipt(Part::Runtime), None);
            assert_eq!(owner.expose_to_cpu(1), Err(ApError::State));
            assert_eq!(manager.summary().allocated_pages, 34);
            assert_eq!(manager.summary().release_scrub_pages, 0);
            retained(&mut manager, &mut access, &handles);
            access.fail_write = None;
            access.fail_read = None;
            access.drop_write = None;
            let receipt = release(
                &mut owner,
                Part::Runtime,
                &mut manager,
                &mut access,
                automatic,
            )
            .unwrap();
            assert_eq!(receipt.verified_bytes, 32 * PAGE_BYTES);
            retained(&mut manager, &mut access, &[handles[1], handles[2]]);
        }
    }
}

#[test]
fn ap_scrub_receipt_capacity_failure_preserves_retention_before_any_write() {
    let (mut manager, mut access, handles) = fixture();
    let mut owner = owner(&mut manager, handles);
    manager.receipt_ledger_count = manager.ledger_capacities().scrub;
    assert_eq!(
        release(&mut owner, Part::Runtime, &mut manager, &mut access, false),
        Err(ApError::PhysicalMemory(
            PhysicalMemoryError::ReceiptCapacity
        ))
    );
    assert_eq!((access.read_count, access.write_count), (0, 0));
    retained(&mut manager, &mut access, &handles);
    manager.receipt_ledger_count = 0;
    release(&mut owner, Part::Runtime, &mut manager, &mut access, false).unwrap();
}
