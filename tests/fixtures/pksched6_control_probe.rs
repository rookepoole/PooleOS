
mod boundary_controls {
    use super::*;

    impl std::fmt::Debug for SmpPreemption {
        fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
            let lanes: Vec<_> = self.lanes.iter().map(|l| (l.cpu, l.apic_id, l.online,
                l.frame_epoch, l.timer_ticks, l.quantum_remaining, l.watchdog_age, l.events, l.event_count)).collect();
            let mut copy = *self;
            let tasks: Vec<_> = (0..8).map(|i| copy.task_snapshot(TaskId::new(i, 1).unwrap())).collect();
            let cpus: Vec<_> = (0..4).map(|i| (copy.scheduler.current(cpu(i)), copy.scheduler.queue_len(cpu(i)))).collect();
            f.debug_tuple("ControllerState").field(&self.summary()).field(&self.pending_remote)
                .field(&self.active_tick).field(&lanes).field(&tasks).field(&cpus).finish()
        }
    }

    fn cpu(value: u8) -> CpuId { CpuId::new(value).unwrap() }

    fn fixture() -> (SmpPreemption, [TaskId; TASK_CAPACITY]) {
        let mut s = SmpScheduler::new();
        let mut tasks = [TaskId::new(0, 1).unwrap(); TASK_CAPACITY];
        for slot in 0..TASK_CAPACITY {
            let task = s.create_task(slot as u8, 1, 16, ONLINE_MASK).unwrap();
            s.activate(task, cpu((slot / 2) as u8)).unwrap();
            tasks[slot] = task;
        }
        for lane in 0..4 {
            let ticket = s.stage_dispatch(cpu(lane), 1, 1).unwrap();
            s.acknowledge_reschedule(ticket, canonical_reschedule_ack(ticket)).unwrap();
        }
        s.block_runnable(tasks[1]).unwrap();
        (SmpPreemption::new(s).unwrap(), tasks)
    }

    fn frame(c: &SmpPreemption, lane: u8) -> FrameContract {
        let i = lane as usize;
        canonical_frame(cpu(lane), c.current(cpu(lane)).unwrap(), c.lanes[i].frame_epoch + 1, c.lanes[i].timer_ticks + 1)
    }

    fn reject_frame(mut c: SmpPreemption, f: FrameContract, error: Error) {
        let before = format!("{c:?}");
        assert_eq!(c.handle_tick(&f, 3, 2), Err(error));
        assert_eq!(format!("{c:?}"), before, "failed frame must preserve observed controller state");
    }

    fn wake(c: &mut SmpPreemption, task: TaskId, target: u8, sequence: u64) {
        c.queue_event(cpu(target), Event { due_tick: 1, sequence,
            kind: EventKind::Wake { task, target: cpu(target) } }).unwrap();
    }

    fn ticket(kind: u8) -> (SmpPreemption, [TaskId; TASK_CAPACITY], TransferTicket) {
        let (mut c, tasks) = fixture();
        let lane = match kind {
            0 => { wake(&mut c, tasks[1], 1, 1); 1 }
            1 => {
                c.queue_event(cpu(2), Event { due_tick: 1, sequence: 1,
                    kind: EventKind::Migrate { task: tasks[5], target: cpu(3) } }).unwrap();
                2
            }
            _ => { c.handle_tick(&frame(&c, 3), 3, 2).unwrap(); 3 }
        };
        let t = c.handle_tick(&frame(&c, lane), 4, 3).unwrap().remote_ticket.unwrap();
        (c, tasks, t)
    }

    fn frame_cpu() {
        assert!(CpuId::new(4).is_err());
        assert!(CpuId::new(255).is_err());
        let (mut c, _) = fixture();
        let f = frame(&c, 1);
        c.lanes[1].online = false;
        reject_frame(c, f, Error::FrameCpu);
    }

    fn frame_apic() {
        for lane in 0..4 {
            let (c, _) = fixture();
            let mut f = frame(&c, lane);
            f.apic_id = (f.apic_id + 1) % 4;
            reject_frame(c, f, Error::FrameApic);
        }
    }

    fn epoch(timer: bool) {
        for value in [0, 2, u64::MAX] {
            let (c, _) = fixture();
            let mut f = frame(&c, 1);
            if timer { f.timer_epoch = value; } else { f.frame_epoch = value; }
            reject_frame(c, f, Error::FrameEpoch);
        }
        let (mut c, _) = fixture();
        let f = frame(&c, 1);
        if timer { c.lanes[1].timer_ticks = u64::MAX; } else { c.lanes[1].frame_epoch = u64::MAX; }
        reject_frame(c, f, Error::Counter);
    }

    fn stack() {
        for mutation in 0..7 {
            let (c, _) = fixture();
            let mut f = frame(&c, 1);
            match mutation {
                0 => f.ist_bottom += 1,
                1 => f.ist_top -= 1,
                2 => f.frame_bytes = 0,
                3 => f.handler_rsp = f.ist_bottom - 1,
                4 => f.handler_rsp = u64::MAX,
                5 => f.frame_bytes = u64::MAX,
                _ => f.handler_rsp = f.ist_top - f.frame_bytes + 1,
            }
            reject_frame(c, f, Error::FrameStack);
        }
        let (mut c, _) = fixture();
        let mut f = frame(&c, 1);
        f.handler_rsp = f.ist_top - f.frame_bytes;
        c.handle_tick(&f, 3, 2).unwrap();
    }

    fn deadline() {
        for (advance, due_tick, sequence, expected) in [
            (false, 0, 1, Error::EventDeadline), (true, 1, 1, Error::EventDeadline),
            (false, 1, 0, Error::EventSequence),
        ] {
            let (mut c, tasks) = fixture();
            if advance { c.handle_tick(&frame(&c, 1), 3, 2).unwrap(); }
            let before = format!("{c:?}");
            assert_eq!(c.queue_event(cpu(1), Event { due_tick, sequence,
                kind: EventKind::Cancel { task: tasks[3] } }), Err(expected));
            assert_eq!(format!("{c:?}"), before);
        }
    }

    fn order() {
        let (mut c, tasks) = fixture();
        wake(&mut c, tasks[1], 1, 1);
        c.queue_event(cpu(1), Event { due_tick: 1, sequence: 2,
            kind: EventKind::Cancel { task: tasks[3] } }).unwrap();
        let result = c.handle_tick(&frame(&c, 1), 3, 2).unwrap();
        assert_eq!(result.event_order[..2], [1, 2]);

        let (mut c, tasks) = fixture();
        c.scheduler.block_runnable(tasks[3]).unwrap();
        wake(&mut c, tasks[1], 2, 2);
        wake(&mut c, tasks[3], 2, 1);
        assert_eq!(c.lanes[2].events[0].unwrap().sequence, 1);
        let bad_order = c.lanes[2].events;
        c.lanes[2].events.swap(0, 1);
        assert_eq!(c.validate(), Err(Error::Invariant));
        c.lanes[2].events = bad_order;
        c.validate().unwrap();

        let (mut c, tasks) = fixture();
        c.queue_event(cpu(1), Event { due_tick: 2, sequence: 1,
            kind: EventKind::Cancel { task: tasks[3] } }).unwrap();
        wake(&mut c, tasks[1], 1, 2);
        assert_eq!(c.lanes[1].events[0].unwrap().due_tick, 1);
    }

    fn ack_binding() {
        for mutation in 0..8 {
            let (mut c, _, mut t) = ticket(0);
            let before = format!("{c:?}");
            let mut ack = canonical_reschedule_ack(t);
            match mutation {
                0 => ack.target_cpu += 1, 1 => ack.attempt += 1, 2 => ack.sequence += 1,
                3 => ack.operation += 1, 4 => ack.status = 0, 5 => ack.error = 1,
                6 => ack.result += 1, _ => t.request_sequence += 1,
            }
            assert!(c.acknowledge_reschedule(t, ack).is_err());
            assert_eq!(format!("{c:?}"), before);
        }
    }

    fn ack_owner() {
        for kind in 0..3 {
            let (mut c, tasks, t) = ticket(kind);
            let task = if kind == 0 { tasks[1] } else if kind == 1 { tasks[5] } else { tasks[7] };
            let before = c.task_snapshot(task).unwrap();
            if kind == 0 { assert_eq!(before.state, TaskState::Blocked); }
            if kind == 1 { assert_eq!(before.owner_cpu, Some(cpu(2))); }
            if kind == 2 { assert_eq!(c.current(cpu(3)).unwrap(), tasks[6]); }
            c.acknowledge_reschedule(t, canonical_reschedule_ack(t)).unwrap();
            let after = c.task_snapshot(task).unwrap();
            assert_eq!(after.owner_cpu, Some(cpu(if kind == 0 { 1 } else { 3 })));
            if kind == 2 { assert_eq!(c.current(cpu(3)).unwrap(), task); }
            else { assert_eq!(after.state, TaskState::Runnable); }
            c.validate().unwrap();
        }
    }

    fn offline() {
        let (mut c, tasks) = fixture();
        let t = c.stage_offline_probe(tasks[5], 3, 2).unwrap();
        let mut bad = t;
        bad.request_sequence += 1;
        let before = format!("{c:?}");
        assert!(c.timeout_offline(bad).is_err());
        assert_eq!(format!("{c:?}"), before);
        c.timeout_offline(t).unwrap();
        assert_eq!(c.summary().timeout_rollbacks, 1);
        assert!(!c.scheduler.has_pending());
        assert_eq!(c.summary().online_mask, ONLINE_MASK);
        let before = format!("{c:?}");
        assert!(c.timeout_offline(t).is_err());
        assert_eq!(format!("{c:?}"), before);
    }

    fn rollback() {
        for index in [3, 5, 7] {
            let (mut c, tasks) = fixture();
            let before = c.task_snapshot(tasks[index]).unwrap();
            let length = c.scheduler.queue_len(cpu((index / 2) as u8)).unwrap();
            let t = c.stage_offline_probe(tasks[index], 3, 2).unwrap();
            c.timeout_offline(t).unwrap();
            assert_eq!(c.task_snapshot(tasks[index]).unwrap(), before);
            assert_eq!(c.scheduler.queue_len(cpu((index / 2) as u8)).unwrap(), length);
            c.validate().unwrap();
        }
    }

    fn late_ack() {
        for kind in 0..3 {
            let (mut c, _, t) = if kind == 0 {
                let (mut c, tasks) = fixture();
                let t = c.stage_offline_probe(tasks[5], 3, 2).unwrap();
                c.timeout_offline(t).unwrap();
                (c, tasks, t)
            } else {
                let (mut c, tasks, t) = ticket(kind - 1);
                c.acknowledge_reschedule(t, canonical_reschedule_ack(t)).unwrap();
                (c, tasks, t)
            };
            let before = format!("{c:?}");
            assert!(c.acknowledge_reschedule(t, canonical_reschedule_ack(t)).is_err());
            assert_eq!(format!("{c:?}"), before);
        }
    }

    fn watchdog() {
        let (mut c, _) = fixture();
        c.lanes[1].watchdog_age = MAX_WATCHDOG_TICKS;
        let f = frame(&c, 1);
        reject_frame(c, f, Error::Watchdog);
        let (mut c, _) = fixture();
        c.maximum_watchdog_age = MAX_WATCHDOG_TICKS + 1;
        assert_eq!(c.validate(), Err(Error::Watchdog));
        let (mut c, _) = fixture();
        c.lanes[1].watchdog_age = MAX_WATCHDOG_TICKS + 1;
        assert_eq!(c.validate(), Err(Error::Invariant));
    }

    fn starvation() {
        for lane in 0..4 {
            let (mut c, tasks) = fixture();
            if lane == 0 {
                let t = c.scheduler.stage_wake(tasks[1], cpu(0), 2, 2).unwrap();
                c.scheduler.acknowledge_reschedule(t, canonical_reschedule_ack(t)).unwrap();
            }
            for tick in 1..=16 {
                let owner = c.current(cpu(lane)).unwrap();
                let outcome = c.handle_tick(&frame(&c, lane), tick + 3, tick + 3).unwrap();
                if tick % 2 == 0 {
                    let t = outcome.remote_ticket.expect("runnable task must receive a quantum");
                    assert_eq!(c.current(cpu(lane)).unwrap(), owner);
                    c.acknowledge_reschedule(t, canonical_reschedule_ack(t)).unwrap();
                    assert_ne!(c.current(cpu(lane)).unwrap(), owner);
                } else { assert!(outcome.remote_ticket.is_none()); }
                assert!(!c.tick_pending());
                assert!(c.summary().maximum_watchdog_age <= MAX_WATCHDOG_TICKS);
                assert!(c.summary().scheduler.maximum_bypass <= 2);
                c.validate().unwrap();
            }
        }
    }

    fn duplicate() {
        for variant in 0..3 {
            let (mut c, tasks) = fixture();
            wake(&mut c, tasks[1], 1, 1);
            let before = format!("{c:?}");
            let (owner, event) = match variant {
                0 => (cpu(1), Event { due_tick: 1, sequence: 1, kind: EventKind::Wake { task: tasks[1], target: cpu(1) } }),
                1 => (cpu(1), Event { due_tick: 2, sequence: 1, kind: EventKind::Cancel { task: tasks[3] } }),
                _ => (cpu(2), Event { due_tick: 2, sequence: 2, kind: EventKind::Wake { task: tasks[1], target: cpu(2) } }),
            };
            assert_eq!(c.queue_event(owner, event), Err(Error::EventDuplicate));
            assert_eq!(format!("{c:?}"), before);
        }
        let (mut c, tasks) = fixture();
        let before = format!("{c:?}");
        assert!(c.scheduler.activate(tasks[3], cpu(1)).is_err());
        assert_eq!(format!("{c:?}"), before);
    }

    pub fn run() {
        let groups: [(&str, usize, fn()); 15] = [
            ("FRAME-CPU", 3, frame_cpu), ("FRAME-APIC", 4, frame_apic),
            ("FRAME-EPOCH", 4, || epoch(false)), ("FRAME-STACK", 8, stack),
            ("TIMER-EPOCH", 4, || epoch(true)), ("EVENT-DEADLINE", 3, deadline),
            ("EVENT-ORDER", 4, order), ("ACK-BINDING", 8, ack_binding),
            ("ACK-GATED-OWNER", 3, ack_owner), ("OFFLINE-TIMEOUT", 3, offline),
            ("SOURCE-QUEUE-ROLLBACK", 3, rollback), ("LATE-ACK", 3, late_ack),
            ("WATCHDOG-BOUND", 3, watchdog), ("STARVATION-BOUND", 4, starvation),
            ("DUPLICATE-RUNNABLE", 4, duplicate),
        ];
        let selected = std::env::args().nth(1);
        assert!(selected.as_ref().is_none_or(|name| groups.iter().any(|g| g.0 == name)));
        for (name, count, operation) in groups {
            if selected.as_ref().is_some_and(|s| s != name) { continue; }
            operation();
            println!("PKSCHED6:CONTROL PASS group={name} verified={count}");
        }
    }
}

pub fn controls_main() { boundary_controls::run(); }
