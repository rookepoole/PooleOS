#![allow(dead_code)]

mod deferred {
    include!("../../native/kernel/src/scheduler_deferred.rs");

    #[cfg(test)]
    mod transaction_controls {
        use super::*;

        fn enqueue(c: &mut DeferredWorkController, key: u16, priority: Priority) -> WorkId {
            c.enqueue_from_top_half(
                WorkRequest {
                    key,
                    source: 7,
                    priority,
                    operation: Operation::Add(1),
                },
                &context(),
                FaultPoint::None,
            )
            .unwrap()
        }

        fn context() -> TopHalfContext {
            TopHalfContext {
                interrupt_depth: 1,
                interrupts_disabled: true,
                queue_lock_held: true,
                worker_context: false,
            }
        }

        fn unchanged(c: &DeferredWorkController, before: &DeferredWorkController) {
            assert_eq!(c.summary(), before.summary());
            assert_eq!(c.active_worker, before.active_worker);
            assert_eq!(c.high_bypass, before.high_bypass);
            for (a, b) in c.slots.iter().zip(before.slots.iter()) {
                assert_eq!(
                    (
                        a.generation,
                        a.state,
                        a.request,
                        a.enqueue_sequence,
                        a.completion_sequence,
                        a.owner,
                        a.cancel_requested,
                        a.result
                    ),
                    (
                        b.generation,
                        b.state,
                        b.request,
                        b.enqueue_sequence,
                        b.completion_sequence,
                        b.owner,
                        b.cancel_requested,
                        b.result
                    )
                );
            }
            assert_eq!(c.validate(), Ok(()));
        }

        fn running() -> (DeferredWorkController, WorkId) {
            let mut c = DeferredWorkController::new();
            let id = enqueue(&mut c, 1, Priority::Normal);
            let permit = c.observe_eoi().unwrap();
            assert_eq!(c.claim_one(0, permit, FaultPoint::None), Ok(id));
            (c, id)
        }

        fn terminal_pair() -> (DeferredWorkController, [WorkId; 2]) {
            let mut c = DeferredWorkController::new();
            let first = enqueue(&mut c, 1, Priority::Normal);
            let second = enqueue(&mut c, 2, Priority::Normal);
            let permit = c.observe_eoi().unwrap();
            c.dispatch_one(0, permit).unwrap();
            c.dispatch_one(1, permit).unwrap();
            (c, [first, second])
        }

        #[test]
        fn shutdown_requires_closed_intake_even_when_empty() {
            let mut c = DeferredWorkController::new();
            let before = c;
            assert_eq!(c.finish_shutdown(), Err(Error::ShutdownPending));
            unchanged(&c, &before);
            assert_eq!(c.begin_shutdown(), Ok(0));
            assert_eq!(c.finish_shutdown(), Ok(0));
            assert!(c.summary().shutdown_complete);
            assert_eq!(c.finish_shutdown(), Ok(0));
        }

        #[test]
        fn shutdown_cannot_retire_terminal_work_before_intake_closes() {
            let (mut c, ids) = terminal_pair();
            let before = c;
            assert_eq!(c.finish_shutdown(), Err(Error::ShutdownPending));
            unchanged(&c, &before);
            assert!(c.request(ids[0]).is_ok());
            assert!(c.request(ids[1]).is_ok());
        }

        #[test]
        fn before_execute_fault_does_not_consume_priority_budget() {
            let mut c = DeferredWorkController::new();
            for key in 1..=5 {
                enqueue(
                    &mut c,
                    key,
                    if key == 2 {
                        Priority::Normal
                    } else {
                        Priority::High
                    },
                );
            }
            let permit = c.observe_eoi().unwrap();
            for _ in 0..4 {
                let before = c;
                assert_eq!(
                    c.claim_one(0, permit, FaultPoint::BeforeExecute),
                    Err(Error::FaultInjected)
                );
                let mut expected = before;
                expected.rollback_count += 1;
                unchanged(&c, &expected);
            }
            let slots: Vec<_> = (0..5)
                .map(|i| c.dispatch_one(i % 2, permit).unwrap().id.slot)
                .collect();
            assert_eq!(slots, [0, 2, 3, 1, 4]);
        }

        #[test]
        fn enqueue_counter_exhaustion_is_atomic() {
            for case in 0..4 {
                let mut c = DeferredWorkController::new();
                let fault = match case {
                    0 => {
                        c.enqueue_sequence = u64::MAX;
                        FaultPoint::None
                    }
                    1 => {
                        c.enqueued = u32::MAX;
                        FaultPoint::None
                    }
                    2 => {
                        c.rollback_count = u32::MAX;
                        FaultPoint::AfterReserve
                    }
                    _ => {
                        c.rollback_count = u32::MAX;
                        FaultPoint::AfterQueue
                    }
                };
                let before = c;
                assert_eq!(
                    c.enqueue_from_top_half(
                        WorkRequest {
                            key: 1,
                            source: 7,
                            priority: Priority::Normal,
                            operation: Operation::Add(1)
                        },
                        &context(),
                        fault
                    ),
                    Err(Error::Counter)
                );
                unchanged(&c, &before);
            }
        }

        #[test]
        fn dispatch_counter_exhaustion_preserves_queue_and_worker() {
            for rollback in [false, true] {
                let mut c = DeferredWorkController::new();
                enqueue(&mut c, 1, Priority::High);
                enqueue(&mut c, 2, Priority::Normal);
                let permit = c.observe_eoi().unwrap();
                let fault = if rollback {
                    c.rollback_count = u32::MAX;
                    FaultPoint::BeforeExecute
                } else {
                    c.dispatches = u32::MAX;
                    FaultPoint::None
                };
                let before = c;
                assert_eq!(c.claim_one(0, permit, fault), Err(Error::Counter));
                unchanged(&c, &before);
            }
        }

        #[test]
        fn completion_counter_exhaustion_preserves_running_ownership_and_lanes() {
            for case in 0..6 {
                let (mut c, id) = running();
                let fault = match case {
                    0 => {
                        c.completion_sequence = u64::MAX;
                        FaultPoint::None
                    }
                    1 => {
                        c.completed = u32::MAX;
                        FaultPoint::None
                    }
                    2 => {
                        c.sum_lane = u32::MAX;
                        FaultPoint::None
                    }
                    3 => {
                        c.slots[0].request.operation = Operation::Fence(1);
                        c.fence_lane = u32::MAX;
                        FaultPoint::None
                    }
                    4 => {
                        c.cancel(id).unwrap();
                        c.cancelled = u32::MAX;
                        FaultPoint::None
                    }
                    _ => {
                        c.rollback_count = u32::MAX;
                        FaultPoint::BeforeCommit
                    }
                };
                let before = c;
                assert_eq!(c.finish_claimed(0, id, fault), Err(Error::Counter));
                unchanged(&c, &before);
            }
        }

        #[test]
        fn combined_dispatch_failure_restores_unclaimed_work() {
            let mut c = DeferredWorkController::new();
            let id = enqueue(&mut c, 1, Priority::High);
            enqueue(&mut c, 2, Priority::Normal);
            let permit = c.observe_eoi().unwrap();
            c.sum_lane = u32::MAX;
            let before = c;
            assert_eq!(c.dispatch_one(0, permit), Err(Error::Counter));
            unchanged(&c, &before);
            c.sum_lane = 0;
            assert_eq!(c.dispatch_one(1, permit).unwrap().id, id);
        }

        #[test]
        fn eoi_duplicate_and_cleanup_exhaustion_preserve_state() {
            let mut c = DeferredWorkController::new();
            let id = enqueue(&mut c, 1, Priority::Normal);
            c.eoi_epoch = u64::MAX;
            let before = c;
            assert_eq!(c.observe_eoi(), Err(Error::Counter));
            unchanged(&c, &before);
            c.duplicate_suppressed = u32::MAX;
            let before = c;
            assert_eq!(
                c.enqueue_from_top_half(c.request(id).unwrap(), &context(), FaultPoint::None),
                Err(Error::Counter)
            );
            unchanged(&c, &before);
            let (mut c, ids) = terminal_pair();
            c.rollback_count = u32::MAX;
            let before = c;
            assert_eq!(c.retire(ids[0], FaultPoint::Cleanup), Err(Error::Counter));
            unchanged(&c, &before);
        }

        #[test]
        fn cancellation_counter_exhaustion_is_atomic() {
            for case in 0..3 {
                let (mut c, id) = if case == 2 {
                    running()
                } else {
                    let mut c = DeferredWorkController::new();
                    let id = enqueue(&mut c, 1, Priority::Normal);
                    (c, id)
                };
                match case {
                    0 => c.completion_sequence = u64::MAX,
                    1 => c.cancelled = u32::MAX,
                    _ => c.running_cancel_requests = u32::MAX,
                }
                let before = c;
                assert_eq!(c.cancel(id), Err(Error::Counter));
                unchanged(&c, &before);
            }
        }

        #[test]
        fn retirement_counter_exhaustion_retains_terminal_identity() {
            let (mut c, ids) = terminal_pair();
            c.retired = u32::MAX;
            let before = c;
            assert_eq!(c.retire(ids[0], FaultPoint::None), Err(Error::Counter));
            unchanged(&c, &before);
        }

        #[test]
        fn terminal_batch_retirement_is_atomic_on_late_exhaustion() {
            let (mut c, _) = terminal_pair();
            c.retired = u32::MAX - 1;
            let before = c;
            assert_eq!(c.retire_all_terminal(), Err(Error::Counter));
            unchanged(&c, &before);
        }

        #[test]
        fn shutdown_begin_is_atomic_on_late_cancellation_exhaustion() {
            for running_case in [false, true] {
                let mut c = DeferredWorkController::new();
                enqueue(&mut c, 1, Priority::Normal);
                enqueue(&mut c, 2, Priority::Normal);
                if running_case {
                    let permit = c.observe_eoi().unwrap();
                    c.claim_one(0, permit, FaultPoint::None).unwrap();
                    c.running_cancel_requests = u32::MAX;
                } else {
                    c.cancelled = u32::MAX - 1;
                }
                let before = c;
                assert_eq!(c.begin_shutdown(), Err(Error::Counter));
                unchanged(&c, &before);
            }
        }

        #[test]
        fn shutdown_finish_is_atomic_on_late_retirement_exhaustion() {
            let (mut c, _) = terminal_pair();
            c.begin_shutdown().unwrap();
            c.retired = u32::MAX - 1;
            let before = c;
            assert_eq!(c.finish_shutdown(), Err(Error::Counter));
            unchanged(&c, &before);
        }

        #[test]
        fn injected_faults_recover_without_reusing_generation_or_committing_work() {
            let mut c = DeferredWorkController::new();
            for fault in [FaultPoint::AfterReserve, FaultPoint::AfterQueue] {
                assert_eq!(
                    c.enqueue_from_top_half(
                        WorkRequest {
                            key: 1,
                            source: 7,
                            priority: Priority::High,
                            operation: Operation::Add(1)
                        },
                        &context(),
                        fault
                    ),
                    Err(Error::FaultInjected)
                );
                assert_eq!(c.validate(), Ok(()));
                assert_eq!(c.summary().free, 8);
            }
            let id = enqueue(&mut c, 1, Priority::High);
            assert_eq!(id.generation, 3);
            let permit = c.observe_eoi().unwrap();
            for _ in 0..2 {
                assert_eq!(c.claim_one(0, permit, FaultPoint::None), Ok(id));
                assert_eq!(
                    c.finish_claimed(0, id, FaultPoint::BeforeCommit),
                    Err(Error::FaultInjected)
                );
                assert_eq!(c.summary().sum_lane, 0);
                assert_eq!(c.summary().running, 0);
                assert_eq!(c.summary().pending, 1);
            }
            let receipt = c.dispatch_one(1, permit).unwrap();
            assert_eq!(receipt.result, 1);
            assert_eq!(c.retire(id, FaultPoint::Cleanup), Err(Error::FaultInjected));
            assert!(c.request(id).is_ok());
            c.retire(id, FaultPoint::None).unwrap();
            assert_eq!(c.cancel(id), Err(Error::StaleId));
            assert_eq!(c.summary().rollback_count, 5);
            assert_eq!(c.validate(), Ok(()));
        }
    }
}
