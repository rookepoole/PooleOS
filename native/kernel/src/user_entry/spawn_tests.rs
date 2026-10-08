use super::*;
use crate::user_entry::spawn::{Construction, Error as SpawnError};

fn setup() -> (Fixture, Construction) {
    let mut f = Fixture::new();
    for h in f.handles() {
        f.manager.free(h).unwrap();
    }
    let mut owner = Construction::new();
    for _ in 0..5 {
        owner.allocate_next(&mut f.manager).unwrap();
    }
    (f, owner)
}
fn retained(f: &mut Fixture, c: &Construction) {
    for h in c.handles().into_iter().flatten() {
        assert_eq!(
            f.manager.free(h),
            Err(PhysicalMemoryError::AllocationRetained)
        );
    }
}
fn rollback(f: &mut Fixture, c: &mut Construction) {
    let handles = c.handles();
    c.abort(&mut f.manager, &mut f.memory).unwrap();
    assert_eq!(f.manager.summary().allocated_pages, 0);
    for h in handles.into_iter().flatten() {
        for p in h.start_page..h.start_page + h.page_count {
            assert_eq!(f.memory.pages[&(p * PAGE_BYTES)], [0; 512]);
        }
    }
    assert!(c.handles().iter().all(Option::is_none));
    c.abort(&mut f.manager, &mut f.memory).unwrap();
    assert_eq!(c.allocate_next(&mut f.manager), Err(SpawnError::State));
}

#[test]
fn partial_allocation_failure_at_each_boundary_retains_then_scrubs() {
    for (limit, successful) in [(3, 0), (4, 1), (5, 2), (9, 3), (12, 4)] {
        let mut p = PhysicalMemoryManager::test_manager(4096, limit, 32);
        let mut c = Construction::new();
        for _ in 0..successful {
            c.allocate_next(&mut p).unwrap();
        }
        assert_eq!(c.allocate_next(&mut p), Err(SpawnError::Allocation));
        let mut memory = Fixture::new().memory;
        for h in c.handles().into_iter().flatten() {
            assert_eq!(p.free(h), Err(PhysicalMemoryError::AllocationRetained));
        }
        c.abort(&mut p, &mut memory).unwrap();
        assert_eq!(p.summary().allocated_pages, 0);
    }
}

#[test]
fn success_transfers_tokens_without_an_unretained_interval() {
    let (mut f, mut c) = setup();
    let handles = c.handles();
    let p = c
        .build(
            &mut f.manager,
            &mut f.memory,
            &[0x90; 17],
            f.image,
            f.core,
            36,
            None,
        )
        .ok()
        .unwrap();
    for h in handles.into_iter().flatten() {
        assert_eq!(
            f.manager.free(h),
            Err(PhysicalMemoryError::AllocationRetained)
        );
    }
    assert!(c.handles().iter().all(Option::is_none));
    assert_eq!(
        c.abort(&mut f.manager, &mut f.memory),
        Err(SpawnError::State)
    );
    assert_eq!(c.allocate_next(&mut f.manager), Err(SpawnError::State));
    let parts = p.abort(&mut f.manager, &mut f.memory).ok().unwrap();
    assert_eq!(parts.stack.page_count, 4);
    for h in handles.into_iter().flatten() {
        f.manager.free(h).unwrap();
    }
}

#[test]
fn invalid_payload_shapes_preserve_owner_without_writes() {
    for case in 0..4 {
        let (mut f, mut c) = setup();
        let payload = [0x90; 4097];
        let (size, delta) = match case {
            0 => (0, 0),
            1 => (4097, 0),
            2 => (1, 1),
            _ => (1, 4096),
        };
        f.image.entry += delta;
        let writes = f.memory.writes;
        assert!(
            c.build(
                &mut f.manager,
                &mut f.memory,
                &payload[..size],
                f.image,
                f.core,
                36,
                None
            )
            .is_err()
        );
        assert_eq!(f.memory.writes, writes);
        retained(&mut f, &c);
        rollback(&mut f, &mut c);
    }
}

#[test]
fn after_effect_write_and_corrupt_readback_at_each_construction_region_roll_back() {
    // data erase, payload, user tables, user leaves, private stack tables,
    // private leaves and root attachment. Final count comes from a clean build.
    let (mut f, mut c) = setup();
    let p = c
        .build(
            &mut f.manager,
            &mut f.memory,
            &[0x90; 17],
            f.image,
            f.core,
            36,
            None,
        )
        .ok()
        .unwrap();
    let count = f.memory.writes;
    drop(p);
    for index in [
        0,
        511,
        512,
        1024,
        3071,
        3072,
        3074,
        3075,
        5122,
        5123,
        5124,
        5125,
        5126,
        count - 2,
        count - 1,
    ] {
        for corrupt in [false, true] {
            let (mut f, mut c) = setup();
            if corrupt {
                f.memory.corrupt_write = Some(index);
            } else {
                f.memory.fail_write = Some(index);
            }
            assert!(
                c.build(
                    &mut f.manager,
                    &mut f.memory,
                    &[0x90; 17],
                    f.image,
                    f.core,
                    36,
                    None
                )
                .is_err(),
                "write {index}/{count} corrupt {corrupt}"
            );
            retained(&mut f, &c);
            f.memory.corrupt_write = None;
            f.memory.fail_write = None;
            rollback(&mut f, &mut c);
        }
    }
}

#[test]
fn read_and_finish_failures_keep_complete_rollback_owner() {
    let (mut f, mut c) = setup();
    let p = c
        .build(
            &mut f.manager,
            &mut f.memory,
            &[0x90; 17],
            f.image,
            f.core,
            36,
            None,
        )
        .ok()
        .unwrap();
    let reads = f.memory.reads;
    drop(p);
    for index in [0, 3071, 3072, 3075, 5123, reads - 1] {
        let (mut f, mut c) = setup();
        f.memory.fail_read = Some(index);
        assert!(
            c.build(
                &mut f.manager,
                &mut f.memory,
                &[0x90; 17],
                f.image,
                f.core,
                36,
                None
            )
            .is_err()
        );
        retained(&mut f, &c);
        f.memory.fail_read = None;
        rollback(&mut f, &mut c);
    }
    let (mut f, mut c) = setup();
    f.memory.fail_finish = true;
    assert!(
        c.build(
            &mut f.manager,
            &mut f.memory,
            &[0x90; 17],
            f.image,
            f.core,
            36,
            None
        )
        .is_err()
    );
    retained(&mut f, &c);
    f.memory.fail_finish = false;
    rollback(&mut f, &mut c);
}

#[test]
fn failed_cleanup_never_frees_any_page_and_can_retry() {
    for mode in 0..4 {
        let (mut f, mut c) = setup();
        match mode {
            0 => f.memory.fail_write = Some(700),
            1 => f.memory.corrupt_write = Some(700),
            2 => f.memory.fail_read = Some(700),
            _ => f.memory.fail_finish = true,
        }
        assert!(c.abort(&mut f.manager, &mut f.memory).is_err());
        assert_eq!(f.manager.summary().allocated_pages, 13);
        retained(&mut f, &c);
        f.memory.fail_write = None;
        f.memory.corrupt_write = None;
        f.memory.fail_read = None;
        f.memory.fail_finish = false;
        rollback(&mut f, &mut c);
    }
}

#[test]
fn identical_foreign_manager_handles_never_authorize_memory_access() {
    let (mut f, mut c) = setup();
    let (mut other, _) = setup();
    for h in c.handles().into_iter().flatten() {
        assert!(other.manager.validate_allocation(h).is_ok());
    }
    let writes = f.memory.writes;
    assert_eq!(
        c.allocate_next(&mut other.manager),
        Err(SpawnError::Ownership)
    );
    assert!(
        c.build(
            &mut other.manager,
            &mut f.memory,
            &[0x90],
            f.image,
            f.core,
            36,
            None
        )
        .is_err()
    );
    assert_eq!(
        c.abort(&mut other.manager, &mut f.memory),
        Err(SpawnError::Ownership)
    );
    assert_eq!(f.memory.writes, writes);
    rollback(&mut f, &mut c);
}
