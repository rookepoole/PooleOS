#[cfg(test)]
mod transaction_controls {
    use super::*;

    fn context() -> TopHalfContext {
        TopHalfContext { interrupt_depth: 1, interrupts_disabled: true,
            queue_lock_held: false, worker_context: false }
    }

    fn driver(key: u16, cpu: u8, priority: Priority) -> WorkRequest {
        WorkRequest { key, source_cpu: 0, target_cpu: cpu, priority,
            consumer: Consumer::DriverTimerBottomHalf { vector: 64, sample: 7 } }
    }

    fn enqueue(c: &mut ApWorkerController, key: u16, cpu: u8) -> WorkId {
        c.enqueue_from_top_half(context(), driver(key, cpu, Priority::Normal)).unwrap()
    }

    fn ack(t: DispatchTicket) -> RemoteAck {
        RemoteAck { target_cpu: t.target_cpu, attempt: t.request_attempt,
            sequence: t.request_sequence, operation: smp_ipi::Operation::CallFunction as u32,
            status: smp_ipi::ACK_ACCEPTED, error: smp_ipi::ERROR_NONE, result: t.expected_result }
    }

    fn pending() -> (ApWorkerController, DispatchTicket) {
        let mut c = ApWorkerController::new();
        enqueue(&mut c, 1, 1);
        let permit = c.observe_eoi().unwrap();
        let ticket = c.stage_dispatch(1, permit, 1, 1).unwrap();
        (c, ticket)
    }

    fn unchanged(c: &ApWorkerController, before: &ApWorkerController) {
        assert_eq!(c.summary(), before.summary());
        assert_eq!(c.pending, before.pending);
        assert_eq!(c.offline_pending, before.offline_pending);
        assert_eq!(c.last_timed_out, before.last_timed_out);
        assert_eq!(c.worker_generation, before.worker_generation);
        assert_eq!(c.high_bypass, before.high_bypass);
        assert_eq!(c.transaction_sequence, before.transaction_sequence);
        for (a, b) in c.slots.iter().zip(before.slots.iter()) {
            assert_eq!((a.generation, a.state, a.request, a.enqueue_sequence,
                        a.completion_sequence, a.cancel_requested, a.result),
                       (b.generation, b.state, b.request, b.enqueue_sequence,
                        b.completion_sequence, b.cancel_requested, b.result));
        }
    }

    #[test]
    fn enqueue_exhaustion_preserves_generation_queue_and_watermark() {
        for field in 0..3 {
            let mut c = ApWorkerController::new();
            match field { 0 => c.enqueued = u32::MAX, 1 => c.slots[0].generation = u32::MAX,
                _ => c.enqueue_sequence = u64::MAX }
            let before = c;
            assert_eq!(c.enqueue_from_top_half(context(), driver(1, 1, Priority::High)), Err(Error::Counter));
            unchanged(&c, &before);
        }
    }

    #[test]
    fn rejected_dispatch_preserves_priority_budget_and_all_ownership() {
        for field in 0..4 {
            let mut c = ApWorkerController::new();
            enqueue(&mut c, 1, 1);
            let mut permit = c.observe_eoi().unwrap();
            c.enqueue_from_top_half(context(), driver(2, 1, Priority::High)).unwrap();
            if field != 0 { permit = c.observe_eoi().unwrap(); }
            if field == 2 { c.transaction_sequence = u64::MAX; }
            if field == 3 { c.dispatches = u32::MAX; }
            let before = c;
            let result = c.stage_dispatch(1, permit, if field == 1 { 0 } else { 1 }, 1);
            assert_eq!(result, Err(match field { 0 => Error::DispatchBeforeEoi,
                1 => Error::InvalidRequest, _ => Error::Counter }));
            unchanged(&c, &before);
        }
    }

    #[test]
    fn acknowledgement_exhaustion_preserves_ticket_result_and_counters() {
        for field in 0..6 {
            let (mut c, ticket) = pending();
            match field { 0 => c.worker_entries[0] = u32::MAX, 1 => c.remote_acks = u32::MAX,
                2 => c.driver_executions = u32::MAX, 3 => c.completed = u32::MAX,
                4 => c.completion_sequence = u64::MAX, _ => c.driver_sample_sum = u32::MAX }
            let before = c;
            assert_eq!(c.acknowledge(ticket, ack(ticket)), Err(Error::Counter));
            unchanged(&c, &before);
        }
        let (mut c, ticket) = pending();
        c.driver_sample_sum = u32::MAX;
        let before = c;
        assert_eq!(c.acknowledge(ticket, ack(ticket)), Err(Error::Counter));
        unchanged(&c, &before);
        c.driver_sample_sum = 0;
        assert_eq!(c.acknowledge(ticket, ack(ticket)).unwrap().state, WorkState::Completed);
        assert_eq!(c.driver_sample_sum, 7);
        assert_eq!(c.acknowledge(ticket, ack(ticket)), Err(Error::TicketMismatch));
    }

    #[test]
    fn queued_cancellation_is_atomic_on_late_exhaustion() {
        for field in 0..3 {
            let mut c = ApWorkerController::new();
            let id = enqueue(&mut c, 1, 1);
            match field { 0 => c.queued_cancellations = u32::MAX,
                1 => c.cancelled = u32::MAX, _ => c.completion_sequence = u64::MAX }
            let before = c;
            assert_eq!(c.cancel(id), Err(Error::Counter));
            unchanged(&c, &before);
        }
    }

    #[test]
    fn remote_cancellation_request_is_atomic() {
        let (mut c, ticket) = pending();
        c.remote_cancel_requests = u32::MAX;
        let before = c;
        assert_eq!(c.cancel(ticket.id), Err(Error::Counter));
        unchanged(&c, &before);
    }

    #[test]
    fn cancelled_acknowledgement_preserves_state_on_late_exhaustion() {
        for field in 0..3 {
            let (mut c, ticket) = pending();
            c.cancel(ticket.id).unwrap();
            match field { 0 => c.remote_cancel_completions = u32::MAX,
                1 => c.cancelled = u32::MAX, _ => c.completion_sequence = u64::MAX }
            let before = c;
            assert_eq!(c.acknowledge(ticket, ack(ticket)), Err(Error::Counter));
            unchanged(&c, &before);
        }
    }

    #[test]
    fn timeout_exhaustion_preserves_offline_ticket_and_source_queue() {
        for field in 0..2 {
            let mut c = ApWorkerController::new();
            let id = enqueue(&mut c, 1, 1);
            let permit = c.observe_eoi().unwrap();
            let ticket = c.stage_offline_probe(id, OFFLINE_PROBE_CPU, permit, 1, 1).unwrap();
            if field == 0 { c.timeout_count = u32::MAX; } else { c.rollback_count = u32::MAX; }
            let before = c;
            assert_eq!(c.timeout(ticket), Err(Error::Counter));
            unchanged(&c, &before);
        }
    }

    #[test]
    fn reclaim_exhaustion_does_not_free_terminal_identity() {
        let mut c = ApWorkerController::new();
        let id = enqueue(&mut c, 1, 1);
        c.cancel(id).unwrap();
        let token = c.begin_flush();
        c.reclaimed = u32::MAX;
        let before = c;
        assert_eq!(c.reclaim(id, token), Err(Error::Counter));
        unchanged(&c, &before);
    }

    #[test]
    fn terminal_batch_retirement_is_atomic() {
        let mut c = ApWorkerController::new();
        let a = enqueue(&mut c, 1, 1);
        let b = enqueue(&mut c, 2, 2);
        c.cancel(a).unwrap(); c.cancel(b).unwrap();
        let token = c.begin_flush();
        c.reclaimed = u32::MAX - 1;
        let before = c;
        assert_eq!(c.retire_all_terminal(token), Err(Error::Counter));
        unchanged(&c, &before);
    }

    #[test]
    fn offline_exhaustion_preserves_worker_authority() {
        for field in 0..2 {
            let mut c = ApWorkerController::new();
            if field == 0 { c.worker_generation[1] = u32::MAX; } else { c.worker_retirements = u32::MAX; }
            let before = c;
            assert_eq!(c.offline_worker(1), Err(Error::Counter));
            unchanged(&c, &before);
        }
    }

    #[test]
    fn failed_shutdown_does_not_close_intake() {
        let mut c = ApWorkerController::new();
        let before = c;
        assert_eq!(c.finish_shutdown(), Err(Error::WorkerBusy));
        unchanged(&c, &before);
        for cpu in 1..4 { c.offline_worker(cpu).unwrap(); }
        c.finish_shutdown().unwrap();
        assert!(c.shutdown_complete && !c.intake_open);
        assert_eq!(c.validate(), Ok(()));
    }

    #[test]
    fn generation_wrap_is_rejected_before_enqueue() {
        let mut c = ApWorkerController::new();
        let mut request = driver(1, 1, Priority::Normal);
        request.consumer = Consumer::ServiceGenerationReclaim {
            retired_generation: u32::MAX, active_generation: 0 };
        let before = c;
        assert_eq!(c.enqueue_from_top_half(context(), request), Err(Error::InvalidRequest));
        unchanged(&c, &before);
    }

    #[test]
    fn validation_handles_wide_counter_sums_without_wrap_or_panic() {
        let mut c = ApWorkerController::new();
        c.enqueued = u32::MAX; c.completed = u32::MAX; c.cancelled = 1;
        assert_eq!(c.validate(), Err(Error::Invariant));
        let mut c = ApWorkerController::new();
        c.worker_entries = [u32::MAX, 1, 0]; c.remote_acks = 0;
        assert_eq!(c.validate(), Err(Error::Invariant));
        let mut c = ApWorkerController::new();
        c.enqueued = u32::MAX; c.completed = u32::MAX; c.reclaimed = u32::MAX;
        assert_eq!(c.validate(), Ok(()));
    }

    #[test]
    fn every_ack_field_rejects_without_mutation_then_allows_retry() {
        for field in 0..7 {
            let (mut c, ticket) = pending();
            let mut forged = ack(ticket);
            match field { 0 => forged.target_cpu ^= 1, 1 => forged.attempt += 1,
                2 => forged.sequence += 1, 3 => forged.operation = 0,
                4 => forged.status = 0, 5 => forged.error = 1, _ => forged.result ^= 1 }
            let before = c;
            assert_eq!(c.acknowledge(ticket, forged), Err(Error::Acknowledgement));
            unchanged(&c, &before);
            c.acknowledge(ticket, ack(ticket)).unwrap();
            assert_eq!(c.validate(), Ok(()));
        }
    }

    #[test]
    fn eoi_and_stale_rejection_exhaustion_preserve_state() {
        let mut c = ApWorkerController::new();
        c.eoi_epoch = u64::MAX;
        let before = c;
        assert_eq!(c.observe_eoi(), Err(Error::Counter));
        unchanged(&c, &before);
        let mut c = ApWorkerController::new();
        let id = enqueue(&mut c, 1, 1);
        let permit = c.observe_eoi().unwrap();
        let t = c.stage_offline_probe(id, 4, permit, 1, 1).unwrap();
        c.timeout(t).unwrap(); c.stale_rejections = u32::MAX;
        let before = c;
        assert_eq!(c.reject_stale_ack(t, ack(t)), Err(Error::Counter));
        unchanged(&c, &before);
    }

    #[test]
    fn dispatch_preflight_denies_uncommittable_remote_work() {
        let mut c = ApWorkerController::new();
        enqueue(&mut c, 1, 1);
        let permit = c.observe_eoi().unwrap();
        c.driver_executions = u32::MAX;
        let before = c;
        assert_eq!(c.stage_dispatch(1, permit, 1, 1), Err(Error::Counter));
        unchanged(&c, &before);
    }

    #[test]
    fn offline_preflight_reserves_timeout_capacity() {
        for field in 0..2 {
            let mut c = ApWorkerController::new();
            let id = enqueue(&mut c, 1, 1);
            let permit = c.observe_eoi().unwrap();
            if field == 0 { c.timeout_count = u32::MAX; } else { c.rollback_count = u32::MAX; }
            let before = c;
            assert_eq!(c.stage_offline_probe(id, 4, permit, 1, 1), Err(Error::Counter));
            unchanged(&c, &before);
        }
    }

    #[test]
    fn preflight_accounts_for_other_pending_workers() {
        let mut c = ApWorkerController::new();
        enqueue(&mut c, 1, 1); enqueue(&mut c, 2, 2);
        let permit = c.observe_eoi().unwrap();
        c.remote_acks = u32::MAX - 1; c.worker_entries[0] = u32::MAX - 1;
        let first = c.stage_dispatch(1, permit, 1, 1).unwrap();
        let before = c;
        assert_eq!(c.stage_dispatch(2, permit, 1, 2), Err(Error::Counter));
        unchanged(&c, &before);
        c.acknowledge(first, ack(first)).unwrap();
        assert_eq!(c.remote_acks, u32::MAX);
    }

    #[test]
    fn service_preflight_uses_transaction_order_not_cpu_order() {
        let mut c = ApWorkerController::new();
        for (key, cpu, retired) in [(1, 3, 1), (2, 1, 2)] {
            let mut request = driver(key, cpu, Priority::Normal);
            request.consumer = Consumer::ServiceGenerationReclaim {
                retired_generation: retired, active_generation: retired + 1 };
            c.enqueue_from_top_half(context(), request).unwrap();
        }
        let permit = c.observe_eoi().unwrap();
        let first = c.stage_dispatch(3, permit, 1, 1).unwrap();
        let second = c.stage_dispatch(1, permit, 1, 2).unwrap();
        let before = c;
        assert_eq!(c.acknowledge(second, ack(second)), Err(Error::ReclaimOrder));
        unchanged(&c, &before);
        c.acknowledge(first, ack(first)).unwrap();
        c.acknowledge(second, ack(second)).unwrap();
        assert_eq!(c.active_service_generation, 3);
        assert_eq!(c.validate(), Ok(()));
    }

    #[test]
    fn duplicate_rejection_preserves_ownership_and_accounts_only_suppression() {
        assert!(core::mem::size_of::<ApWorkerController>() <= 2048);
        let mut c = ApWorkerController::new();
        enqueue(&mut c, 1, 1);
        let mut before = c;
        assert_eq!(c.enqueue_from_top_half(context(), driver(1, 1, Priority::Normal)), Err(Error::Duplicate));
        before.duplicate_suppressed += 1;
        unchanged(&c, &before);
        c.duplicate_suppressed = u32::MAX;
        let before = c;
        assert_eq!(c.enqueue_from_top_half(context(), driver(1, 1, Priority::Normal)), Err(Error::Counter));
        unchanged(&c, &before);
    }
}
