
#[cfg(test)]
mod event_progress_controls {
    use super::*;

    fn cpu(value: u8) -> CpuId { CpuId::new(value).unwrap() }

    fn fixture() -> (SmpPreemption, [TaskId; TASK_CAPACITY]) {
        let mut scheduler = SmpScheduler::new();
        let mut tasks = [TaskId::new(0, 1).unwrap(); TASK_CAPACITY];
        for slot in 0..TASK_CAPACITY {
            let id = scheduler.create_task(slot as u8, 1, 16, ONLINE_MASK).unwrap();
            scheduler.activate(id, cpu((slot / 2) as u8)).unwrap();
            tasks[slot] = id;
        }
        for value in 0..CPU_COUNT as u8 {
            let ticket = scheduler.stage_dispatch(cpu(value), 1, 1).unwrap();
            scheduler.acknowledge_reschedule(ticket, canonical_reschedule_ack(ticket)).unwrap();
        }
        scheduler.block_runnable(tasks[1]).unwrap();
        (SmpPreemption::new(scheduler).unwrap(), tasks)
    }

    fn drain(c: &mut SmpPreemption, mut outcome: TickOutcome) -> TickOutcome {
        for _ in 0..=EVENT_CAPACITY_PER_CPU {
            if let Some(ticket) = outcome.remote_ticket {
                c.acknowledge_reschedule(ticket, canonical_reschedule_ack(ticket)).unwrap();
            }
            if !c.tick_pending() { c.validate().unwrap(); return outcome; }
            let ticket = outcome.remote_ticket.unwrap();
            outcome = c.resume_tick(ticket.request_attempt, ticket.request_sequence.checked_add(1).unwrap()).unwrap();
        }
        panic!("fixed continuation bound exceeded")
    }

    #[test]
    fn admitted_wake_on_quantum_boundary_must_make_progress() {
        let (mut c, tasks) = fixture();
        c.queue_event(cpu(1), Event { due_tick: 2, sequence: 1,
            kind: EventKind::Wake { task: tasks[1], target: cpu(1) } }).unwrap();
        let owner = c.current(cpu(1)).unwrap();
        c.handle_tick(&canonical_frame(cpu(1), owner, 1, 1), 3, 2).unwrap();
        let outcome = c.handle_tick(&canonical_frame(cpu(1), owner, 2, 2), 4, 3)
            .expect("an admitted wake may not permanently roll the same tick back");
        assert_eq!(c.summary().remote_reschedule_acks, 0);
        assert_eq!(c.current(cpu(1)).unwrap(), owner);
        assert_eq!(c.task_snapshot(tasks[1]).unwrap().state, TaskState::Blocked);
        let result = drain(&mut c, outcome);
        assert_eq!(result.cause, Cause::Quantum);
        assert_eq!(result.event_order[0], 2);
        assert_eq!(c.summary().remote_reschedule_acks, 2);
        assert_eq!(c.summary().context_switches, 1);
        assert_eq!(c.summary().timer_ticks[1], 2);
        assert_eq!(c.summary().frame_epochs[1], 2);
    }

    #[test]
    fn admitted_same_deadline_remote_events_must_make_progress() {
        let (mut c, tasks) = fixture();
        c.scheduler.block_runnable(tasks[3]).unwrap();
        for (sequence, task) in [(1, tasks[1]), (2, tasks[3])] {
            c.queue_event(cpu(2), Event { due_tick: 1, sequence,
                kind: EventKind::Wake { task, target: cpu(2) } }).unwrap();
        }
        let owner = c.current(cpu(2)).unwrap();
        let outcome = c.handle_tick(&canonical_frame(cpu(2), owner, 1, 1), 3, 2)
            .expect("an admitted event batch must not be stranded by its first remote ticket");
        let result = drain(&mut c, outcome);
        assert_eq!(result.events_processed, 2);
        assert_eq!(result.event_order[..2], [2, 2]);
        assert_eq!(c.summary().remote_reschedule_acks, 2);
        assert_eq!(c.summary().timer_ticks[2], 1);
        assert_eq!(c.summary().frame_epochs[2], 1);
        assert_eq!(c.summary().pending_events, 0);
    }

    #[test]
    fn four_remote_events_and_quantum_drain_in_five_acknowledged_operations() {
        let (mut c, tasks) = fixture();
        for index in [3, 5, 7] { c.scheduler.block_runnable(tasks[index]).unwrap(); }
        for (sequence, index) in [(1, 1), (2, 3), (3, 5), (4, 7)] {
            c.queue_event(cpu(2), Event { due_tick: 2, sequence,
                kind: EventKind::Wake { task: tasks[index], target: cpu(2) } }).unwrap();
        }
        let owner = c.current(cpu(2)).unwrap();
        c.handle_tick(&canonical_frame(cpu(2), owner, 1, 1), 3, 2).unwrap();
        let outcome = c.handle_tick(&canonical_frame(cpu(2), owner, 2, 2), 4, 3).unwrap();
        let result = drain(&mut c, outcome);
        assert_eq!(result.events_processed, 4);
        assert_eq!(result.event_order, [2, 2, 2, 2]);
        assert_eq!(c.summary().remote_reschedule_acks, 5);
        assert_eq!(c.summary().context_switches, 1);
        assert_eq!(c.summary().frame_epochs[2], 2);
    }

    fn two_wakes() -> (SmpPreemption, [TaskId; TASK_CAPACITY]) {
        let (mut c, tasks) = fixture();
        c.scheduler.block_runnable(tasks[3]).unwrap();
        for (sequence, index) in [(1, 1), (2, 3)] {
            c.queue_event(cpu(2), Event { due_tick: 1, sequence,
                kind: EventKind::Wake { task: tasks[index], target: cpu(2) } }).unwrap();
        }
        (c, tasks)
    }

    #[test]
    fn complete_tick_capacity_is_checked_before_the_first_remote_request() {
        for sequence_limit in [false, true] {
            let (mut c, _) = two_wakes();
            if !sequence_limit { c.remote_reschedule_acks = u32::MAX - 1; }
            let before = c.summary();
            let frame = canonical_frame(cpu(2), c.current(cpu(2)).unwrap(), 1, 1);
            let sequence = if sequence_limit { u64::MAX } else { 2 };
            assert_eq!(c.handle_tick(&frame, 3, sequence), Err(Error::Counter));
            assert_eq!(c.summary(), before);
            assert!(!c.tick_pending());
            assert!(!c.scheduler.has_pending());
        }
    }

    #[test]
    fn continuation_requires_exact_ack_then_a_fresh_sequence() {
        let (mut c, tasks) = two_wakes();
        let frame = canonical_frame(cpu(2), c.current(cpu(2)).unwrap(), 1, 1);
        let outcome = c.handle_tick(&frame, 3, 2).unwrap();
        let ticket = outcome.remote_ticket.unwrap();
        let before = c.summary();
        assert_eq!(c.resume_tick(3, 3), Err(Error::PendingRemote));
        let mut bad = canonical_reschedule_ack(ticket);
        bad.sequence += 1;
        assert!(c.acknowledge_reschedule(ticket, bad).is_err());
        assert_eq!(c.summary(), before);
        assert_eq!(c.task_snapshot(tasks[1]).unwrap().state, TaskState::Blocked);
        c.acknowledge_reschedule(ticket, canonical_reschedule_ack(ticket)).unwrap();
        let before = c.summary();
        assert_eq!(c.resume_tick(3, 2), Err(Error::EventSequence));
        assert_eq!(c.resume_tick(2, 3), Err(Error::EventSequence));
        assert_eq!(c.summary(), before);
        let next = c.resume_tick(3, 3).unwrap();
        drain(&mut c, next);
    }

    #[test]
    fn active_tick_blocks_interleaving_and_failed_resume_preserves_retry() {
        let (mut c, tasks) = two_wakes();
        let frame = canonical_frame(cpu(2), c.current(cpu(2)).unwrap(), 1, 1);
        let ticket = c.handle_tick(&frame, 3, 2).unwrap().remote_ticket.unwrap();
        c.acknowledge_reschedule(ticket, canonical_reschedule_ack(ticket)).unwrap();
        let before = c.summary();
        assert_eq!(c.handle_tick(&frame, 4, 3), Err(Error::PendingRemote));
        assert_eq!(c.stage_offline_probe(tasks[5], 4, 3), Err(Error::PendingRemote));
        assert_eq!(c.finish_shutdown(tasks), Err(Error::Shutdown));
        assert_eq!(c.queue_event(cpu(3), Event { due_tick: 1, sequence: 1,
            kind: EventKind::Cancel { task: tasks[7] } }), Err(Error::PendingRemote));
        assert_eq!(c.summary(), before);
        c.wake_events = u32::MAX;
        let before = c.summary();
        let progress = c.active_tick;
        assert_eq!(c.resume_tick(3, 3), Err(Error::Counter));
        assert_eq!(c.summary(), before);
        assert_eq!(c.active_tick, progress);
        c.wake_events = 1;
        let next = c.resume_tick(3, 3).unwrap();
        drain(&mut c, next);
    }

    #[test]
    fn conflicting_event_identity_and_sequence_reject_before_admission() {
        let (mut c, tasks) = two_wakes();
        let before = c.summary();
        assert_eq!(c.queue_event(cpu(1), Event { due_tick: 2, sequence: 8,
            kind: EventKind::Wake { task: tasks[1], target: cpu(1) } }), Err(Error::EventDuplicate));
        assert_eq!(c.queue_event(cpu(2), Event { due_tick: 2, sequence: 1,
            kind: EventKind::Cancel { task: tasks[5] } }), Err(Error::EventDuplicate));
        assert_eq!(c.summary(), before);
    }
}
