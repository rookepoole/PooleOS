#[cfg(test)]
mod transaction_controls {
    use super::*;

    fn cpu(value: u8) -> CpuId {
        CpuId::new(value).unwrap()
    }

    fn ack(ticket: TransferTicket) -> RemoteAck {
        RemoteAck {
            target_cpu: ticket.target_cpu,
            attempt: ticket.request_attempt,
            sequence: ticket.request_sequence,
            operation: CALL_FUNCTION_OPERATION,
            status: ACK_ACCEPTED,
            error: ERROR_NONE,
            result: CALL_FUNCTION_RESULT,
        }
    }

    fn task(c: &mut SmpScheduler, slot: u8, owner: u8) -> TaskId {
        let id = c.create_task(slot, 1, 16, ONLINE_MASK).unwrap();
        c.activate(id, cpu(owner)).unwrap();
        id
    }

    fn unchanged(c: &SmpScheduler, before: &SmpScheduler) {
        assert_eq!(c.summary(), before.summary());
        assert_eq!(c.transaction, before.transaction);
        assert_eq!(c.current, before.current);
        assert_eq!(c.pending.map(|p| p.ticket), before.pending.map(|p| p.ticket));
        for (a, b) in c.queues.iter().zip(before.queues.iter()) {
            assert_eq!((a.entries, a.len), (b.entries, b.len));
        }
        for (a, b) in c.tasks.iter().zip(before.tasks.iter()) {
            assert_eq!(
                (a.generation, a.state, a.priority, a.affinity_mask, a.owner_cpu,
                 a.owner_epoch, a.queued_cpu, a.bypass_count, a.dispatch_count),
                (b.generation, b.state, b.priority, b.affinity_mask, b.owner_cpu,
                 b.owner_epoch, b.queued_cpu, b.bypass_count, b.dispatch_count)
            );
        }
        assert_eq!(c.validate(), Ok(()));
    }

    fn ready(kind: TransferKind, owner: u8) -> (SmpScheduler, TaskId) {
        let mut c = SmpScheduler::new();
        let id = task(&mut c, 0, owner);
        if kind == TransferKind::Wake {
            c.block_runnable(id).unwrap();
        } else if kind == TransferKind::Preempt {
            task(&mut c, 1, owner);
            let ticket = c.stage_dispatch(cpu(owner), 1, 1).unwrap();
            c.acknowledge(ticket, ack(ticket)).unwrap();
        }
        (c, id)
    }

    fn stage(c: &mut SmpScheduler, id: TaskId, kind: TransferKind, owner: u8) -> Result<TransferTicket, Error> {
        match kind {
            TransferKind::Wake => c.stage_wake(id, cpu(2), 2, 3),
            TransferKind::Migration => c.stage_migration(id, cpu(2), 2, 3),
            TransferKind::Dispatch => c.stage_dispatch(cpu(owner), 2, 3),
            TransferKind::Preempt => c.stage_preempt(cpu(owner), 2, 3),
            TransferKind::OfflineProbe => c.stage_offline_probe(id, OFFLINE_PROBE_CPU, 2, 3),
        }
    }

    fn faults(kind: TransferKind) -> u8 {
        match kind {
            TransferKind::Wake | TransferKind::Migration => 3,
            TransferKind::Dispatch => 5,
            TransferKind::Preempt => 6,
            TransferKind::OfflineProbe => unreachable!(),
        }
    }

    fn exhaust(c: &mut SmpScheduler, kind: TransferKind, owner: u8, field: u8) {
        let selected = usize::from(kind == TransferKind::Preempt);
        match field {
            0 => c.tasks[selected].owner_epoch = u32::MAX,
            1 => c.remote_ack_count = u32::MAX,
            2 if kind == TransferKind::Wake => c.remote_wake_count = u32::MAX,
            2 if kind == TransferKind::Migration => c.migration_count = u32::MAX,
            2 => c.tasks[selected].dispatch_count = u32::MAX,
            3 => c.dispatch_count = u32::MAX,
            4 if owner == 0 => c.bsp_dispatch_count = u32::MAX,
            4 => c.ap_dispatch_count = u32::MAX,
            5 => {
                c.tasks[0].bypass_count = MAX_EQUAL_PRIORITY_BYPASS;
                c.tasks[1].bypass_count = MAX_EQUAL_PRIORITY_BYPASS;
            }
            _ => unreachable!(),
        }
    }

    #[test]
    fn acknowledgement_exhaustion_preserves_pending_and_entire_state() {
        for kind in [TransferKind::Wake, TransferKind::Migration, TransferKind::Dispatch, TransferKind::Preempt] {
            for owner in [0, 1] {
                for field in 0..faults(kind) {
                    let (mut c, id) = ready(kind, owner);
                    let mut ticket = stage(&mut c, id, kind, owner).unwrap();
                    let healthy = c;
                    exhaust(&mut c, kind, owner, field);
                    if field == 0 && kind != TransferKind::Preempt {
                        ticket.owner_epoch = u32::MAX;
                        c.pending.as_mut().unwrap().ticket = ticket;
                    }
                    let before = c;
                    assert_eq!(c.acknowledge(ticket, ack(ticket)), Err(Error::Counter));
                    unchanged(&c, &before);
                    c = healthy;
                    let ticket = c.pending.unwrap().ticket;
                    c.acknowledge(ticket, ack(ticket)).unwrap();
                    assert!(!c.has_pending());
                    c.validate().unwrap();
                }
            }
        }
    }

    #[test]
    fn staging_rejects_uncommittable_ack_before_exposing_ticket() {
        for kind in [TransferKind::Wake, TransferKind::Migration, TransferKind::Dispatch, TransferKind::Preempt] {
            for owner in [0, 1] {
                for field in 0..faults(kind) {
                    let (mut c, id) = ready(kind, owner);
                    exhaust(&mut c, kind, owner, field);
                    let before = c;
                    assert_eq!(stage(&mut c, id, kind, owner), Err(Error::Counter));
                    unchanged(&c, &before);
                    assert!(!c.has_pending());
                }
            }
        }
    }

    #[test]
    fn cancellation_exhaustion_preserves_runnable_and_blocked_tasks() {
        for blocked in [false, true] {
            let (mut c, id) = ready(if blocked { TransferKind::Wake } else { TransferKind::Migration }, 1);
            c.teardown_count = u32::MAX;
            let before = c;
            assert_eq!(c.cancel_task(id), Err(Error::Counter));
            unchanged(&c, &before);
            c.teardown_count = 0;
            c.cancel_task(id).unwrap();
            assert_eq!(c.task_snapshot(id).unwrap().state, TaskState::Dead);
        }
    }

    #[test]
    fn timeout_exhaustion_preserves_ticket_and_source_queue() {
        for field in 0..2 {
            let (mut c, id) = ready(TransferKind::OfflineProbe, 1);
            let ticket = stage(&mut c, id, TransferKind::OfflineProbe, 1).unwrap();
            if field == 0 { c.timeout_count = u32::MAX; } else { c.rollback_count = u32::MAX; }
            let before = c;
            assert_eq!(c.timeout(ticket), Err(Error::Counter));
            unchanged(&c, &before);
            c.timeout_count = 0;
            c.rollback_count = 0;
            c.timeout(ticket).unwrap();
            assert_eq!(c.queue_len(cpu(1)), Ok(1));
            assert_eq!(c.acknowledge(ticket, ack(ticket)), Err(Error::PendingMissing));
        }
    }

    #[test]
    fn offline_probe_reserves_timeout_capacity_before_issuing_ticket() {
        for field in 0..2 {
            let (mut c, id) = ready(TransferKind::OfflineProbe, 1);
            if field == 0 { c.timeout_count = u32::MAX; } else { c.rollback_count = u32::MAX; }
            let before = c;
            assert_eq!(stage(&mut c, id, TransferKind::OfflineProbe, 1), Err(Error::Counter));
            unchanged(&c, &before);
            assert!(!c.has_pending());
        }
    }

    #[test]
    fn completion_exhaustion_preserves_running_owner_for_retry() {
        let (mut c, id) = ready(TransferKind::Dispatch, 1);
        let ticket = stage(&mut c, id, TransferKind::Dispatch, 1).unwrap();
        c.acknowledge(ticket, ack(ticket)).unwrap();
        c.teardown_count = u32::MAX;
        let before = c;
        assert_eq!(c.complete_current(cpu(1)), Err(Error::Counter));
        unchanged(&c, &before);
        c.teardown_count = 0;
        assert_eq!(c.complete_current(cpu(1)), Ok(id));
    }

    #[test]
    fn local_dispatch_and_teardown_are_one_atomic_operation() {
        for field in 0..5 {
            let (mut c, id) = ready(TransferKind::Dispatch, 0);
            match field {
                0 => c.tasks[0].owner_epoch = u32::MAX,
                1 => c.tasks[0].dispatch_count = u32::MAX,
                2 => c.dispatch_count = u32::MAX,
                3 => c.bsp_dispatch_count = u32::MAX,
                _ => c.teardown_count = u32::MAX,
            }
            let before = c;
            assert_eq!(c.dispatch_local(cpu(0)), Err(Error::Counter));
            unchanged(&c, &before);
            c.tasks[0].owner_epoch = 1;
            c.tasks[0].dispatch_count = 0;
            c.dispatch_count = 0;
            c.bsp_dispatch_count = 0;
            c.teardown_count = 0;
            assert_eq!(c.dispatch_local(cpu(0)), Ok(id));
            assert_eq!(c.summary().teardown_count, 1);
        }
    }

    #[test]
    fn exact_ack_field_binding_preserves_state_and_allows_valid_retry() {
        for kind in [TransferKind::Wake, TransferKind::Migration, TransferKind::Dispatch, TransferKind::Preempt] {
            let (mut c, id) = ready(kind, 1);
            let ticket = stage(&mut c, id, kind, 1).unwrap();
            for field in 0..7 {
                let mut hostile = ack(ticket);
                match field {
                    0 => hostile.target_cpu ^= 1,
                    1 => hostile.attempt += 1,
                    2 => hostile.sequence += 1,
                    3 => hostile.operation = RESCHEDULE_OPERATION,
                    4 => hostile.status = 0,
                    5 => hostile.error = 1,
                    _ => hostile.result ^= 1,
                }
                let before = c;
                assert_eq!(c.acknowledge(ticket, hostile), Err(Error::Acknowledgement));
                unchanged(&c, &before);
            }
            c.acknowledge(ticket, ack(ticket)).unwrap();
            c.validate().unwrap();
        }
    }

    #[test]
    fn reschedule_acknowledgement_preserves_state_on_late_failure() {
        let (mut c, id) = ready(TransferKind::Preempt, 1);
        let ticket = stage(&mut c, id, TransferKind::Preempt, 1).unwrap();
        let mut response = ack(ticket);
        response.operation = RESCHEDULE_OPERATION;
        response.result = RESCHEDULE_RESULT;
        c.remote_ack_count = u32::MAX;
        let before = c;
        assert_eq!(c.acknowledge_reschedule(ticket, response), Err(Error::Counter));
        unchanged(&c, &before);
        c.remote_ack_count = 0;
        c.acknowledge_reschedule(ticket, response).unwrap();
        assert_eq!(c.current(cpu(1)).unwrap().unwrap().slot, 1);
    }
}
