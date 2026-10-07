
#[cfg(test)]
mod transaction_controls {
    use super::*;

    fn cpu(value: u8) -> CpuId {
        CpuId::new(value).unwrap()
    }

    fn fixture() -> (SmpPreemption, [TaskId; TASK_CAPACITY]) {
        let mut scheduler = SmpScheduler::new();
        let mut tasks = [TaskId::new(0, 1).unwrap(); TASK_CAPACITY];
        for slot in 0..TASK_CAPACITY {
            let owner = (slot / 2) as u8;
            let affinity = match slot { 1 => 0x03, 5 => 0x0c, _ => 1 << owner };
            let id = scheduler.create_task(slot as u8, 1, 16, affinity).unwrap();
            scheduler.activate(id, cpu(owner)).unwrap();
            tasks[slot] = id;
        }
        for value in 0..CPU_COUNT as u8 {
            let ticket = scheduler.stage_dispatch(cpu(value), 1, 1).unwrap();
            scheduler.acknowledge_reschedule(ticket, canonical_reschedule_ack(ticket)).unwrap();
        }
        scheduler.block_runnable(tasks[1]).unwrap();
        (SmpPreemption::new(scheduler).unwrap(), tasks)
    }

    fn assert_same(actual: &SmpPreemption, before: &SmpPreemption) {
        assert_eq!(actual.summary(), before.summary());
        assert_eq!(actual.pending_remote, before.pending_remote);
        assert_eq!(actual.active_tick, before.active_tick);
        for (a, b) in actual.lanes.iter().zip(before.lanes.iter()) {
            assert_eq!((a.cpu, a.apic_id, a.online, a.frame_epoch, a.timer_ticks),
                       (b.cpu, b.apic_id, b.online, b.frame_epoch, b.timer_ticks));
            assert_eq!((a.quantum_remaining, a.watchdog_age, a.events, a.event_count),
                       (b.quantum_remaining, b.watchdog_age, b.events, b.event_count));
        }
        let (mut a, mut b) = (*actual, *before);
        for value in 0..CPU_COUNT as u8 {
            assert_eq!(a.scheduler.current(cpu(value)), b.scheduler.current(cpu(value)));
            assert_eq!(a.scheduler.queue_len(cpu(value)), b.scheduler.queue_len(cpu(value)));
        }
        for value in 0..TASK_CAPACITY as u8 {
            let id = TaskId::new(value, 1).unwrap();
            assert_eq!(a.task_snapshot(id), b.task_snapshot(id));
        }
    }

    fn tick(c: &mut SmpPreemption, value: u8) -> Result<TickOutcome, Error> {
        let lane = c.lanes[value as usize];
        let epoch = lane.timer_ticks.checked_add(1).unwrap();
        let frame = canonical_frame(cpu(value), c.current(cpu(value)).unwrap(), epoch, epoch);
        c.handle_tick(&frame, epoch + 2, epoch + 1)
    }

    fn preemption(c: &mut SmpPreemption) -> TransferTicket {
        assert!(tick(c, 3).unwrap().remote_ticket.is_none());
        tick(c, 3).unwrap().remote_ticket.unwrap()
    }

    #[test]
    fn ack_counter_exhaustion_preserves_exact_pending_owner_and_retry() {
        let (mut c, _) = fixture();
        let ticket = preemption(&mut c);
        c.remote_reschedule_acks = u32::MAX;
        let before = c;
        assert_eq!(c.acknowledge_reschedule(ticket, canonical_reschedule_ack(ticket)), Err(Error::Counter));
        assert_same(&c, &before);
        c.remote_reschedule_acks = 0;
        c.acknowledge_reschedule(ticket, canonical_reschedule_ack(ticket)).unwrap();
        c.validate().unwrap();
    }

    #[test]
    fn context_switch_exhaustion_preserves_exact_pending_owner_and_retry() {
        let (mut c, _) = fixture();
        let ticket = preemption(&mut c);
        c.context_switches = u32::MAX;
        let before = c;
        assert_eq!(c.acknowledge_reschedule(ticket, canonical_reschedule_ack(ticket)), Err(Error::Counter));
        assert_same(&c, &before);
        c.context_switches = 0;
        c.acknowledge_reschedule(ticket, canonical_reschedule_ack(ticket)).unwrap();
    }

    #[test]
    fn timeout_exhaustion_preserves_offline_ticket_and_source_queue() {
        let (mut c, tasks) = fixture();
        let ticket = c.stage_offline_probe(tasks[5], 3, 2).unwrap();
        c.timeout_rollbacks = u32::MAX;
        let before = c;
        assert_eq!(c.timeout_offline(ticket), Err(Error::Counter));
        assert_same(&c, &before);
        c.timeout_rollbacks = 0;
        c.timeout_offline(ticket).unwrap();
    }

    #[test]
    fn stale_ack_counter_exhaustion_preserves_offline_ticket_and_source_queue() {
        let (mut c, tasks) = fixture();
        let ticket = c.stage_offline_probe(tasks[5], 3, 2).unwrap();
        c.stale_ack_rejections = u32::MAX;
        let before = c;
        assert_eq!(c.timeout_offline(ticket), Err(Error::Counter));
        assert_same(&c, &before);
        c.stale_ack_rejections = 0;
        c.timeout_offline(ticket).unwrap();
    }

    #[test]
    fn failed_shutdown_preserves_all_tasks_and_cpu_owners() {
        let (mut c, mut tasks) = fixture();
        tasks[7] = TaskId::new(7, 2).unwrap();
        let before = c;
        assert!(c.finish_shutdown(tasks).is_err());
        assert_same(&c, &before);
    }

    #[test]
    fn revocation_exhaustion_preserves_shutdown_state() {
        for timer in [false, true] {
            let (mut c, tasks) = fixture();
            if timer { c.timer_owner_revocations = u32::MAX - 1; }
            else { c.frame_owner_revocations = u32::MAX - 1; }
            let before = c;
            assert_eq!(c.finish_shutdown(tasks), Err(Error::Counter));
            assert_same(&c, &before);
        }
    }

    #[test]
    fn exhausted_frame_epoch_rejects_without_wrapping_or_panicking() {
        for (frame_epoch, timer_ticks) in [(u64::MAX, u64::MAX), (u64::MAX, 0), (0, u64::MAX)] {
            let (mut c, _) = fixture();
            c.lanes[1].frame_epoch = frame_epoch;
            c.lanes[1].timer_ticks = timer_ticks;
            if frame_epoch == timer_ticks { c.validate().unwrap(); }
            let frame = canonical_frame(cpu(1), c.current(cpu(1)).unwrap(), 0, 0);
            let before = c;
            assert_eq!(c.handle_tick(&frame, 3, 2), Err(Error::Counter));
            assert_same(&c, &before);
        }
    }

    #[test]
    fn rejected_event_identity_preserves_queue_and_diagnostics() {
        let (mut c, _) = fixture();
        let before = c;
        let event = Event { due_tick: 1, sequence: 1,
            kind: EventKind::Cancel { task: TaskId::new(3, 2).unwrap() } };
        assert!(c.queue_event(cpu(1), event).is_err());
        assert_same(&c, &before);
    }

    #[test]
    fn failed_tick_counter_already_preserves_event_and_owner() {
        let (mut c, tasks) = fixture();
        c.queue_event(cpu(1), Event { due_tick: 1, sequence: 1,
            kind: EventKind::Cancel { task: tasks[3] } }).unwrap();
        c.cancelled_events = u32::MAX;
        let before = c;
        assert_eq!(tick(&mut c, 1), Err(Error::Counter));
        assert_same(&c, &before);
    }

    #[test]
    fn preemption_reserves_ack_and_switch_capacity_before_publication() {
        for switch in [false, true] {
            let (mut c, _) = fixture();
            tick(&mut c, 3).unwrap();
            if switch { c.context_switches = u32::MAX; }
            else { c.remote_reschedule_acks = u32::MAX; }
            let before = c;
            assert_eq!(tick(&mut c, 3), Err(Error::Counter));
            assert_same(&c, &before);
            assert!(!c.scheduler.has_pending());
        }
    }

    #[test]
    fn wake_reserves_ack_capacity_before_publication() {
        let (mut c, tasks) = fixture();
        c.queue_event(cpu(1), Event { due_tick: 1, sequence: 1,
            kind: EventKind::Wake { task: tasks[1], target: cpu(1) } }).unwrap();
        c.remote_reschedule_acks = u32::MAX;
        let before = c;
        assert_eq!(tick(&mut c, 1), Err(Error::Counter));
        assert_same(&c, &before);
        assert!(!c.scheduler.has_pending());
    }

    #[test]
    fn offline_probe_reserves_both_completion_counters_before_publication() {
        for stale in [false, true] {
            let (mut c, tasks) = fixture();
            if stale { c.stale_ack_rejections = u32::MAX; }
            else { c.timeout_rollbacks = u32::MAX; }
            let before = c;
            assert_eq!(c.stage_offline_probe(tasks[5], 3, 2), Err(Error::Counter));
            assert_same(&c, &before);
            assert_eq!(c.prove_offline_rollback(tasks[5], 3, 2), Err(Error::Counter));
            assert_same(&c, &before);
        }
    }

    #[test]
    fn every_bad_ack_field_preserves_pending_ownership_then_allows_retry() {
        let (mut c, _) = fixture();
        let ticket = preemption(&mut c);
        let good = canonical_reschedule_ack(ticket);
        let mut bad = [good; 7];
        bad[0].target_cpu = 2;
        bad[1].attempt += 1;
        bad[2].sequence += 1;
        bad[3].operation += 1;
        bad[4].status = 0;
        bad[5].error = 1;
        bad[6].result ^= 1;
        for ack in bad {
            let before = c;
            assert!(c.acknowledge_reschedule(ticket, ack).is_err());
            assert_same(&c, &before);
        }
        c.acknowledge_reschedule(ticket, good).unwrap();
    }

    #[test]
    fn read_only_task_query_does_not_consume_pending_diagnostic_capacity() {
        let (mut c, tasks) = fixture();
        let ticket = c.stage_offline_probe(tasks[5], 3, 2).unwrap();
        let before = c;
        assert!(c.task_snapshot(TaskId::new(5, 2).unwrap()).is_err());
        assert_same(&c, &before);
        c.timeout_offline(ticket).unwrap();
    }

    #[test]
    fn offline_stage_and_combined_proof_preserve_state_on_final_validation_failure() {
        let (mut c, tasks) = fixture();
        c.maximum_watchdog_age = MAX_WATCHDOG_TICKS + 1;
        let before = c;
        assert_eq!(c.stage_offline_probe(tasks[5], 3, 2), Err(Error::Watchdog));
        assert_same(&c, &before);
        assert_eq!(c.prove_offline_rollback(tasks[5], 3, 2), Err(Error::Watchdog));
        assert_same(&c, &before);
    }
}
