use poolekernel::reclamation::{Error, Limits, Owner, Pool};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, Barrier};

const OWNER: Owner = Owner {
    task_generation: 1,
    address_space_generation: 2,
};

fn retry<T>(mut operation: impl FnMut() -> Result<T, Error>) -> T {
    for _ in 0..1_000_000 {
        match operation() {
            Ok(value) => return value,
            Err(Error::Busy) => std::thread::yield_now(),
            Err(error) => panic!("unexpected result: {error:?}"),
        }
    }
    panic!("bounded host retry exhausted");
}

#[test]
fn retire_waits_for_all_pins_and_rejects_new_readers() {
    let pool = Pool::<u64, 1>::new(Limits::default()).unwrap();
    let h = pool.publish(OWNER, 37).ok().unwrap();
    let a = pool.pin(h).ok().unwrap();
    let b = pool.pin(h).ok().unwrap();
    assert_eq!(pool.reclaim(h, OWNER), Err(Error::NotRetired));
    pool.retire(h, OWNER).unwrap();
    assert!(matches!(pool.pin(h), Err(Error::Retired)));
    assert_eq!(pool.reclaim(h, OWNER), Err(Error::Pinned));
    assert_eq!((*a, *b), (37, 37));
    drop(a);
    assert_eq!(pool.reclaim(h, OWNER), Err(Error::Pinned));
    drop(b);
    assert_eq!(pool.reclaim(h, OWNER), Ok(37));
    assert_eq!(pool.reclaim(h, OWNER), Err(Error::Stale));
}

#[test]
fn stale_handle_cannot_observe_or_retire_reused_slot() {
    let pool = Pool::<u64, 1>::new(Limits::default()).unwrap();
    let old = pool.publish(OWNER, 11).ok().unwrap();
    pool.retire(old, OWNER).unwrap();
    assert_eq!(pool.reclaim(old, OWNER), Ok(11));
    let new = pool.publish(OWNER, 22).ok().unwrap();
    assert_eq!(old.slot(), new.slot());
    assert_eq!((old.generation(), new.generation()), (1, 2));
    assert!(matches!(pool.pin(old), Err(Error::Stale)));
    assert_eq!(pool.retire(old, OWNER), Err(Error::Stale));
    assert_eq!(pool.reclaim(old, OWNER), Err(Error::Stale));
    assert_eq!(*pool.pin(new).ok().unwrap(), 22);
}

#[test]
fn foreign_pool_and_stale_owner_generations_are_rejected() {
    let a = Pool::<u64, 1>::new(Limits::default()).unwrap();
    let b = Pool::<u64, 1>::new(Limits::default()).unwrap();
    let h = a.publish(OWNER, 9).ok().unwrap();
    let _other = b.publish(OWNER, 10).ok().unwrap();
    assert!(matches!(b.pin(h), Err(Error::ForeignPool)));
    assert_eq!(b.retire(h, OWNER), Err(Error::ForeignPool));
    assert_eq!(b.reclaim(h, OWNER), Err(Error::ForeignPool));
    for wrong in [
        Owner {
            task_generation: 2,
            ..OWNER
        },
        Owner {
            address_space_generation: 3,
            ..OWNER
        },
    ] {
        assert_eq!(a.retire(h, wrong), Err(Error::Owner));
    }
    a.retire(h, OWNER).unwrap();
    assert_eq!(a.retire(h, OWNER), Err(Error::Retired));
    assert_eq!(
        a.reclaim(
            h,
            Owner {
                task_generation: 2,
                ..OWNER
            }
        ),
        Err(Error::Owner)
    );
    assert_eq!(a.reclaim(h, OWNER), Ok(9));
}

#[test]
fn pressure_does_not_evict_pinned_or_retired_values() {
    let pool = Pool::<u64, 1>::new(Limits::default()).unwrap();
    let h = pool.publish(OWNER, 1).ok().unwrap();
    let pin = pool.pin(h).ok().unwrap();
    assert!(matches!(pool.publish(OWNER, 2), Err((Error::Capacity, 2))));
    pool.retire(h, OWNER).unwrap();
    assert!(matches!(pool.publish(OWNER, 3), Err((Error::Capacity, 3))));
    drop(pin);
    assert!(matches!(pool.publish(OWNER, 4), Err((Error::Capacity, 4))));
    assert_eq!(pool.reclaim(h, OWNER), Ok(1));
    assert!(pool.publish(OWNER, 5).is_ok());
}

#[test]
fn pin_limit_rejection_preserves_existing_readers_and_recovers() {
    let pool = Pool::<u64, 1>::new(Limits {
        pins_per_object: 2,
        ..Limits::default()
    })
    .unwrap();
    let h = pool.publish(OWNER, 5).ok().unwrap();
    let a = pool.pin(h).ok().unwrap();
    let b = pool.pin(h).ok().unwrap();
    assert!(matches!(pool.pin(h), Err(Error::PinLimit)));
    drop(a);
    let c = pool.pin(h).ok().unwrap();
    pool.retire(h, OWNER).unwrap();
    drop(b);
    assert_eq!(pool.reclaim(h, OWNER), Err(Error::Pinned));
    assert_eq!(*c, 5);
    drop(c);
    assert_eq!(pool.reclaim(h, OWNER), Ok(5));
}

#[test]
fn generation_budget_exhausts_without_wrapping_and_uses_other_slots() {
    let pool = Pool::<u64, 2>::new(Limits {
        generations_per_slot: 2,
        ..Limits::default()
    })
    .unwrap();
    for (slot, generation) in [(0, 1), (0, 2), (1, 1), (1, 2)] {
        let h = pool.publish(OWNER, 42).ok().unwrap();
        assert_eq!((h.slot(), h.generation()), (slot, generation));
        pool.retire(h, OWNER).unwrap();
        assert_eq!(pool.reclaim(h, OWNER), Ok(42));
    }
    assert!(matches!(
        pool.publish(OWNER, 7),
        Err((Error::GenerationExhausted, 7))
    ));
}

#[test]
fn invalid_limits_and_zero_owner_labels_are_rejected() {
    assert!(matches!(
        Pool::<u64, 0>::new(Limits::default()),
        Err(Error::Limits)
    ));
    for limits in [
        Limits {
            pins_per_object: 0,
            ..Limits::default()
        },
        Limits {
            generations_per_slot: 0,
            ..Limits::default()
        },
    ] {
        assert!(matches!(Pool::<u64, 1>::new(limits), Err(Error::Limits)));
    }
    let pool = Pool::<u64, 1>::new(Limits::default()).unwrap();
    for owner in [
        Owner {
            task_generation: 0,
            ..OWNER
        },
        Owner {
            address_space_generation: 0,
            ..OWNER
        },
    ] {
        assert!(matches!(pool.publish(owner, 7), Err((Error::Owner, 7))));
    }
    assert_eq!(pool.publish(OWNER, 9).ok().unwrap().generation(), 1);
}

#[test]
fn shutdown_seals_admission_without_invalidating_existing_pins() {
    let pool = Pool::<u64, 1>::new(Limits::default()).unwrap();
    assert_eq!(pool.is_drained(), Ok(false));
    let h = pool.publish(OWNER, 3).ok().unwrap();
    let pin = pool.pin(h).ok().unwrap();
    pool.begin_shutdown().unwrap();
    pool.begin_shutdown().unwrap();
    assert!(matches!(pool.pin(h), Err(Error::Draining)));
    assert!(matches!(pool.publish(OWNER, 4), Err((Error::Draining, 4))));
    assert_eq!(*pin, 3);
    pool.retire(h, OWNER).unwrap();
    assert_eq!(pool.reclaim(h, OWNER), Err(Error::Pinned));
    assert_eq!(pool.is_drained(), Ok(false));
    drop(pin);
    assert_eq!(pool.reclaim(h, OWNER), Ok(3));
    assert_eq!(pool.is_drained(), Ok(true));
}

struct DropCount(Arc<AtomicUsize>);

impl Drop for DropCount {
    fn drop(&mut self) {
        self.0.fetch_add(1, Ordering::SeqCst);
    }
}

#[test]
fn destructor_runs_exactly_once_after_ownership_transfer() {
    let drops = Arc::new(AtomicUsize::new(0));
    let pool = Pool::<DropCount, 1>::new(Limits::default()).unwrap();
    let h = pool.publish(OWNER, DropCount(drops.clone())).ok().unwrap();
    let pin = pool.pin(h).ok().unwrap();
    pool.retire(h, OWNER).unwrap();
    assert!(matches!(pool.reclaim(h, OWNER), Err(Error::Pinned)));
    assert_eq!(drops.load(Ordering::SeqCst), 0);
    drop(pin);
    let value = pool.reclaim(h, OWNER).ok().unwrap();
    assert_eq!(drops.load(Ordering::SeqCst), 0);
    drop(value);
    drop(pool);
    assert_eq!(drops.load(Ordering::SeqCst), 1);
}

#[test]
fn failed_publication_returns_value_without_destructor_under_gate() {
    let drops = Arc::new(AtomicUsize::new(0));
    let pool = Pool::<DropCount, 1>::new(Limits::default()).unwrap();
    let h = pool.publish(OWNER, DropCount(drops.clone())).ok().unwrap();
    let (error, returned) = pool.publish(OWNER, DropCount(drops.clone())).err().unwrap();
    assert_eq!(error, Error::Capacity);
    assert_eq!(drops.load(Ordering::SeqCst), 0);
    // A returned destructor may reenter the pool; the gate is already released.
    pool.retire(h, OWNER).unwrap();
    drop(returned);
    drop(pool);
    assert_eq!(drops.load(Ordering::SeqCst), 2);
}

#[test]
fn forgotten_pin_retains_storage_until_exclusive_pool_drop() {
    let drops = Arc::new(AtomicUsize::new(0));
    let pool = Pool::<DropCount, 1>::new(Limits::default()).unwrap();
    let h = pool.publish(OWNER, DropCount(drops.clone())).ok().unwrap();
    std::mem::forget(pool.pin(h).ok().unwrap());
    pool.retire(h, OWNER).unwrap();
    pool.begin_shutdown().unwrap();
    assert!(matches!(pool.reclaim(h, OWNER), Err(Error::Pinned)));
    assert_eq!(pool.is_drained(), Ok(false));
    assert_eq!(drops.load(Ordering::SeqCst), 0);
    drop(pool);
    assert_eq!(drops.load(Ordering::SeqCst), 1);
}

#[test]
fn pool_drop_cleans_live_and_retired_but_not_reclaimed_values() {
    let drops = Arc::new(AtomicUsize::new(0));
    let pool = Pool::<DropCount, 3>::new(Limits::default()).unwrap();
    let _live = pool.publish(OWNER, DropCount(drops.clone())).ok().unwrap();
    let retired = pool.publish(OWNER, DropCount(drops.clone())).ok().unwrap();
    let reclaimed = pool.publish(OWNER, DropCount(drops.clone())).ok().unwrap();
    pool.retire(retired, OWNER).unwrap();
    pool.retire(reclaimed, OWNER).unwrap();
    drop(pool.reclaim(reclaimed, OWNER).ok().unwrap());
    drop(pool);
    assert_eq!(drops.load(Ordering::SeqCst), 3);
}

#[test]
fn four_readers_hold_real_payload_across_retirement() {
    let pool = Pool::<[u64; 32], 1>::new(Limits::default()).unwrap();
    let h = pool.publish(OWNER, [0x1234_5678; 32]).ok().unwrap();
    let pinned = Barrier::new(5);
    let release = Barrier::new(5);
    std::thread::scope(|scope| {
        for _ in 0..4 {
            let (pool, pinned, release) = (&pool, &pinned, &release);
            scope.spawn(move || {
                let pin = retry(|| pool.pin(h));
                pinned.wait();
                release.wait();
                assert_eq!(*pin, [0x1234_5678; 32]);
            });
        }
        pinned.wait();
        retry(|| pool.retire(h, OWNER));
        assert_eq!(pool.reclaim(h, OWNER), Err(Error::Pinned));
        assert!(matches!(pool.pin(h), Err(Error::Retired)));
        release.wait();
    });
    assert_eq!(pool.reclaim(h, OWNER), Ok([0x1234_5678; 32]));
}

#[test]
fn repeated_publish_pin_retire_races_preserve_payload_and_stale_rejection() {
    let pool = Pool::<[u64; 8], 1>::new(Limits::default()).unwrap();
    for generation in 1..=128 {
        let h = pool.publish(OWNER, [generation; 8]).ok().unwrap();
        let start = Barrier::new(5);
        std::thread::scope(|scope| {
            for _ in 0..4 {
                let (pool, start) = (&pool, &start);
                scope.spawn(move || {
                    start.wait();
                    for _ in 0..64 {
                        match pool.pin(h) {
                            Ok(pin) => assert_eq!(*pin, [generation; 8]),
                            Err(Error::Busy) => std::thread::yield_now(),
                            Err(Error::Retired) => break,
                            Err(error) => panic!("unexpected pin error: {error:?}"),
                        }
                    }
                });
            }
            start.wait();
            retry(|| pool.retire(h, OWNER));
        });
        assert_eq!(pool.reclaim(h, OWNER), Ok([generation; 8]));
        assert!(matches!(pool.pin(h), Err(Error::Stale)));
        assert_eq!(h.generation(), generation);
    }
}

#[test]
fn concurrent_reclaim_has_exactly_one_winner() {
    let drops = Arc::new(AtomicUsize::new(0));
    let pool = Pool::<DropCount, 1>::new(Limits::default()).unwrap();
    let h = pool.publish(OWNER, DropCount(drops.clone())).ok().unwrap();
    pool.retire(h, OWNER).unwrap();
    let winners = AtomicUsize::new(0);
    let start = Barrier::new(5);
    std::thread::scope(|scope| {
        for _ in 0..4 {
            let (pool, winners, start) = (&pool, &winners, &start);
            scope.spawn(move || {
                start.wait();
                for _ in 0..1_000_000 {
                    match pool.reclaim(h, OWNER) {
                        Ok(value) => {
                            winners.fetch_add(1, Ordering::SeqCst);
                            drop(value);
                            return;
                        }
                        Err(Error::Stale) => return,
                        Err(Error::Busy) => std::thread::yield_now(),
                        Err(error) => panic!("unexpected reclaim result: {error:?}"),
                    }
                }
                panic!("bounded host retry exhausted");
            });
        }
        start.wait();
    });
    assert_eq!(winners.load(Ordering::SeqCst), 1);
    assert_eq!(drops.load(Ordering::SeqCst), 1);
    drop(pool);
    assert_eq!(drops.load(Ordering::SeqCst), 1);
}

#[test]
fn independent_objects_do_not_share_pin_lifetimes() {
    let pool = Pool::<u64, 2>::new(Limits::default()).unwrap();
    let a = pool.publish(OWNER, 1).ok().unwrap();
    let b = pool.publish(OWNER, 2).ok().unwrap();
    let pin = pool.pin(a).ok().unwrap();
    pool.retire(a, OWNER).unwrap();
    pool.retire(b, OWNER).unwrap();
    assert_eq!(pool.reclaim(b, OWNER), Ok(2));
    assert_eq!(pool.reclaim(a, OWNER), Err(Error::Pinned));
    assert_eq!(*pin, 1);
}

#[test]
fn payload_destructor_can_reenter_same_pool_after_reclaim() {
    struct Reentrant;
    static POOL: std::sync::OnceLock<Pool<Reentrant, 1>> = std::sync::OnceLock::new();
    impl Drop for Reentrant {
        fn drop(&mut self) {
            POOL.get().unwrap().begin_shutdown().unwrap();
        }
    }
    let pool = POOL.get_or_init(|| Pool::new(Limits::default()).unwrap());
    let h = pool.publish(OWNER, Reentrant).ok().unwrap();
    pool.retire(h, OWNER).unwrap();
    drop(pool.reclaim(h, OWNER).ok().unwrap());
    assert_eq!(pool.is_drained(), Ok(true));
}

#[test]
fn unwind_drops_pin_and_preserves_reclaimability() {
    let pool = Pool::<u64, 1>::new(Limits::default()).unwrap();
    let h = pool.publish(OWNER, 8).ok().unwrap();
    let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        let _pin = pool.pin(h).ok().unwrap();
        pool.retire(h, OWNER).unwrap();
        panic!("host-only unwind injection");
    }));
    assert!(result.is_err());
    assert_eq!(pool.reclaim(h, OWNER), Ok(8));
}

#[test]
fn last_pin_release_orders_reader_access_before_concurrent_reclaim() {
    let pool = Pool::<AtomicUsize, 1>::new(Limits::default()).unwrap();
    let h = pool.publish(OWNER, AtomicUsize::new(0)).ok().unwrap();
    let start = Barrier::new(2);
    let retired = Barrier::new(2);
    std::thread::scope(|scope| {
        let reader = scope.spawn(|| {
            let pin = pool.pin(h).ok().unwrap();
            start.wait();
            retired.wait();
            pin.store(123, Ordering::Relaxed);
        });
        start.wait();
        pool.retire(h, OWNER).unwrap();
        assert!(matches!(pool.reclaim(h, OWNER), Err(Error::Pinned)));
        retired.wait();
        let mut reclaimed = None;
        for _ in 0..1_000_000 {
            match pool.reclaim(h, OWNER) {
                Ok(value) => {
                    reclaimed = Some(value);
                    break;
                }
                Err(Error::Pinned | Error::Busy) => std::thread::yield_now(),
                Err(error) => panic!("unexpected reclaim result: {error:?}"),
            }
        }
        // Check before joining: the pin release/acquire, not thread join,
        // provides the ordering needed to observe the reader's relaxed store.
        assert_eq!(reclaimed.unwrap().load(Ordering::Relaxed), 123);
        reader.join().unwrap();
    });
}
