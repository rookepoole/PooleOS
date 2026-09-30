// Appended to the unchanged native module so private state can be fault-injected.
fn control_cpu(value: u8) -> CpuId { CpuId::new(value).unwrap() }

fn control_task(s: &mut SmpScheduler, slot: u8, owner: u8) -> TaskId {
    let id = s.create_task(slot, 1, 16, ONLINE_MASK).unwrap();
    s.activate(id, control_cpu(owner)).unwrap();
    id
}

fn control_ack(t: TransferTicket) -> RemoteAck {
    RemoteAck { target_cpu: t.target_cpu, attempt: t.request_attempt,
        sequence: t.request_sequence, operation: CALL_FUNCTION_OPERATION,
        status: ACK_ACCEPTED, error: ERROR_NONE, result: CALL_FUNCTION_RESULT }
}

fn control_unchanged(a: &SmpScheduler, b: &SmpScheduler) {
    assert_eq!(a.summary(), b.summary());
    assert_eq!(a.transaction, b.transaction);
    assert_eq!(a.current, b.current);
    assert_eq!(a.pending.map(|p| p.ticket), b.pending.map(|p| p.ticket));
    for i in 0..CPU_COUNT {
        assert_eq!(a.queues[i].entries, b.queues[i].entries);
        assert_eq!(a.queues[i].len, b.queues[i].len);
    }
    for i in 0..TASK_CAPACITY {
        let (a, b) = (a.tasks[i], b.tasks[i]);
        assert_eq!((a.generation, a.state, a.priority, a.affinity_mask, a.owner_cpu,
                    a.owner_epoch, a.queued_cpu, a.bypass_count, a.dispatch_count),
                   (b.generation, b.state, b.priority, b.affinity_mask, b.owner_cpu,
                    b.owner_epoch, b.queued_cpu, b.bypass_count, b.dispatch_count));
    }
}

fn control_topology() -> usize {
    for value in [4, 255] { assert_eq!(CpuId::new(value), Err(Error::CpuRange)); }
    let mut s = SmpScheduler::new();
    for mask in [0, 16, 255] { assert_eq!(s.create_task(0, 1, 16, mask), Err(Error::Affinity)); }
    assert_eq!((s.summary().online_mask, s.summary().idle_cpu_count), (15, 4));
    assert_eq!(s.validate(), Ok(()));
    6
}

fn control_duplicate() -> usize {
    let mut s = SmpScheduler::new();
    let id = control_task(&mut s, 0, 1);
    let before = s;
    assert_eq!(s.queues[1].push(id), Err(Error::DuplicateRunnable));
    control_unchanged(&before, &s);
    assert_eq!(s.activate(id, control_cpu(2)), Err(Error::State));
    control_unchanged(&before, &s);
    s.queues[2].push(id).unwrap();
    assert!(s.validate().is_err());
    3
}

fn control_generation() -> usize {
    assert_eq!(TaskId::new(0, 0), Err(Error::Generation));
    let mut s = SmpScheduler::new();
    let id = control_task(&mut s, 0, 0);
    s.cancel_task(id).unwrap();
    assert_eq!(s.create_task(0, 1, 16, ONLINE_MASK), Err(Error::GenerationStale));
    let new = s.create_task(0, 2, 16, ONLINE_MASK).unwrap();
    s.activate(new, control_cpu(0)).unwrap();
    s.block_runnable(new).unwrap();
    assert_eq!(s.task_snapshot(id), Err(Error::GenerationStale));
    let before = s;
    assert_eq!(s.stage_wake(id, control_cpu(1), 1, 1), Err(Error::GenerationStale));
    control_unchanged(&before, &s);
    4
}

fn control_epoch() -> usize {
    let mut s = SmpScheduler::new();
    let id = control_task(&mut s, 0, 0);
    s.block_runnable(id).unwrap();
    let t = s.stage_wake(id, control_cpu(1), 1, 1).unwrap();
    let before = s;
    let mut forged = t;
    forged.owner_epoch += 1;
    assert_eq!(s.acknowledge(forged, control_ack(t)), Err(Error::TicketMismatch));
    control_unchanged(&before, &s);
    s.tasks[0].owner_epoch += 1;
    let before = s;
    assert_eq!(s.acknowledge(t, control_ack(t)), Err(Error::GenerationStale));
    control_unchanged(&before, &s);
    s.pending = None;
    s.tasks[0].owner_epoch = u32::MAX;
    let before = s;
    assert_eq!(s.stage_wake(id, control_cpu(1), 2, 2), Err(Error::Counter));
    control_unchanged(&before, &s);
    3
}

fn control_binding(kind: TransferKind) -> usize {
    for field in 0..7 {
        let mut s = SmpScheduler::new();
        let id = control_task(&mut s, 0, 1);
        let t = match kind {
            TransferKind::Wake => { s.block_runnable(id).unwrap(); s.stage_wake(id, control_cpu(2), 3, 4).unwrap() }
            TransferKind::Migration => s.stage_migration(id, control_cpu(2), 3, 4).unwrap(),
            TransferKind::Dispatch => s.stage_dispatch(control_cpu(1), 3, 4).unwrap(),
            _ => panic!("unsupported control"),
        };
        assert_eq!(s.current(control_cpu(t.target_cpu)), Ok(None));
        let before = s;
        let mut ack = control_ack(t);
        match field {
            0 => ack.target_cpu ^= 1, 1 => ack.attempt += 1, 2 => ack.sequence += 1,
            3 => ack.operation = 0, 4 => ack.status = 0, 5 => ack.error = 1,
            6 => ack.result ^= 1, _ => unreachable!(),
        }
        assert_eq!(s.acknowledge(t, ack), Err(Error::Acknowledgement));
        control_unchanged(&before, &s);
        s.acknowledge(t, control_ack(t)).unwrap();
        assert_eq!(s.task_snapshot(id).unwrap().owner_cpu, Some(control_cpu(t.target_cpu)));
        assert_eq!(s.summary().remote_ack_count, 1);
        assert!(!s.has_pending());
        s.validate().unwrap();
    }
    7
}

fn control_timeout() -> usize {
    let mut s = SmpScheduler::new();
    let id = control_task(&mut s, 0, 1);
    for target in [0, 3] {
        let before = s;
        assert_eq!(s.stage_offline_probe(id, target, 1, 1), Err(Error::TimeoutTarget));
        control_unchanged(&before, &s);
    }
    let t = s.stage_offline_probe(id, 4, 1, 1).unwrap();
    let before = s;
    assert_eq!(s.acknowledge(t, control_ack(t)), Err(Error::CpuRange));
    control_unchanged(&before, &s);
    s.timeout(t).unwrap();
    assert_eq!((s.summary().timeout_count, s.summary().rollback_count), (1, 1));
    assert_eq!(s.queue_len(control_cpu(1)), Ok(1));
    assert!(!s.has_pending());
    4
}

fn control_late() -> usize {
    let mut s = SmpScheduler::new();
    let id = control_task(&mut s, 0, 1);
    let old = s.stage_offline_probe(id, 4, 1, 1).unwrap();
    s.timeout(old).unwrap();
    let before = s;
    assert_eq!(s.acknowledge(old, control_ack(old)), Err(Error::PendingMissing));
    control_unchanged(&before, &s);
    let fresh = s.stage_migration(id, control_cpu(2), 2, 2).unwrap();
    let before = s;
    assert_eq!(s.acknowledge(old, control_ack(old)), Err(Error::TicketMismatch));
    control_unchanged(&before, &s);
    assert_eq!(s.reject_stale_ack(old, control_ack(old)), Err(Error::Invariant));
    control_unchanged(&before, &s);
    s.acknowledge(fresh, control_ack(fresh)).unwrap();
    3
}

fn control_rollback() -> usize {
    let mut s = SmpScheduler::new();
    let a = control_task(&mut s, 0, 1);
    let b = control_task(&mut s, 1, 1);
    let staged = s.stage_migration(a, control_cpu(2), 1, 1);
    assert!(staged.is_ok());
    let t = staged.unwrap();
    let before = s;
    let mut ack = control_ack(t); ack.status = 0;
    assert_eq!(s.acknowledge(t, ack), Err(Error::Acknowledgement));
    control_unchanged(&before, &s);
    s.acknowledge(t, control_ack(t)).unwrap();
    let t = s.stage_offline_probe(b, 4, 2, 2).unwrap();
    s.timeout(t).unwrap();
    assert_eq!((s.queues[1].entries[0], s.queues[2].entries[0]), (Some(b), Some(a)));
    s.transaction = u64::MAX;
    let before = s;
    assert_eq!(s.stage_dispatch(control_cpu(1), 3, 3), Err(Error::Counter));
    control_unchanged(&before, &s);
    3
}

fn control_balance() -> usize {
    let mut s = SmpScheduler::new();
    assert_eq!(s.select_least_loaded(15), Ok(control_cpu(0)));
    control_task(&mut s, 0, 0);
    assert_eq!(s.select_least_loaded(15), Ok(control_cpu(1)));
    assert_eq!(s.select_least_loaded(12), Ok(control_cpu(2)));
    s.offline_idle_cpu(control_cpu(3)).unwrap();
    assert_eq!(s.select_least_loaded(8), Err(Error::CpuOffline));
    4
}

fn control_fairness() -> usize {
    let mut s = SmpScheduler::new();
    let a = control_task(&mut s, 0, 1);
    let b = control_task(&mut s, 1, 1);
    let t = s.stage_dispatch(control_cpu(1), 1, 1).unwrap();
    assert_eq!(t.task, a);
    s.acknowledge(t, control_ack(t)).unwrap();
    assert_eq!(s.complete_current(control_cpu(1)), Ok(a));
    let t = s.stage_dispatch(control_cpu(1), 2, 2).unwrap();
    assert_eq!(t.task, b);
    assert_eq!(s.summary().maximum_bypass, 1);
    let mut s = SmpScheduler::new();
    control_task(&mut s, 0, 1); control_task(&mut s, 1, 1);
    s.tasks[0].bypass_count = MAX_EQUAL_PRIORITY_BYPASS;
    s.tasks[1].bypass_count = MAX_EQUAL_PRIORITY_BYPASS;
    let before = s;
    assert_eq!(s.stage_dispatch(control_cpu(1), 1, 1), Err(Error::Counter));
    control_unchanged(&before, &s);
    let mut s = SmpScheduler::new();
    control_task(&mut s, 0, 1); let high = control_task(&mut s, 1, 1);
    s.tasks[1].priority = 31;
    assert_eq!(s.stage_dispatch(control_cpu(1), 1, 1).unwrap().task, high);
    3
}

fn control_idle() -> usize {
    let mut s = SmpScheduler::new();
    assert_eq!(s.offline_idle_cpu(control_cpu(0)), Err(Error::CpuNotIdle));
    control_task(&mut s, 0, 1);
    let before = s;
    assert_eq!(s.offline_idle_cpu(control_cpu(1)), Err(Error::CpuNotIdle));
    control_unchanged(&before, &s);
    let t = s.stage_dispatch(control_cpu(1), 1, 1).unwrap();
    let before = s;
    assert_eq!(s.offline_idle_cpu(control_cpu(1)), Err(Error::PendingBusy));
    control_unchanged(&before, &s);
    s.acknowledge(t, control_ack(t)).unwrap();
    let before = s;
    assert_eq!(s.offline_idle_cpu(control_cpu(1)), Err(Error::CpuNotIdle));
    control_unchanged(&before, &s);
    s.complete_current(control_cpu(1)).unwrap();
    s.offline_idle_cpu(control_cpu(1)).unwrap();
    assert_eq!(s.queue_len(control_cpu(1)), Err(Error::CpuOffline));
    s.validate().unwrap();
    5
}

fn main() {
    let selected = std::env::args().nth(1);
    let groups: [(&str, fn() -> usize); 13] = [
        ("EXACT-TOPOLOGY", control_topology), ("DUPLICATE-RUNNABLE", control_duplicate),
        ("STALE-GENERATION", control_generation), ("OWNER-EPOCH", control_epoch),
        ("WAKE-ACK-BINDING", || control_binding(TransferKind::Wake)),
        ("MIGRATION-ACK-BINDING", || control_binding(TransferKind::Migration)),
        ("DISPATCH-ACK-BINDING", || control_binding(TransferKind::Dispatch)),
        ("OFFLINE-TIMEOUT", control_timeout), ("LATE-ACK", control_late),
        ("SOURCE-QUEUE-ROLLBACK", control_rollback), ("TOPOLOGY-BALANCING", control_balance),
        ("FAIRNESS-BOUND", control_fairness), ("IDLE-OWNERSHIP", control_idle),
    ];
    assert!(selected.as_ref().map_or(true, |name| groups.iter().any(|(id, _)| id == name)));
    for (id, run) in groups {
        if selected.as_ref().map_or(true, |name| name == id) {
            let count = run();
            println!("PKSCHED4:CONTROL PASS id=NEG-N12-PKSCHED4-{id} cases={count} verified={count}");
        }
    }
}
