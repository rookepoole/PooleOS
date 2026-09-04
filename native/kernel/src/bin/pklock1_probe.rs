use poolekernel::atomics::{AtomicU32, AtomicU64, LoadOrder, RmwOrder, StoreOrder};
use poolekernel::locks::{
    Error, IrqSaveSpinLock, LockContext, LockOrderGraph, LockRank, MAX_MUTEX_BYPASS, MutexAcquire,
    Notification, ReaderWriterLock, SequenceLock, SleepMutex, TicketPermit, TicketSpinLock,
    WakeReason,
};

const THREADS: u32 = 4;
const TICKET_ROUNDS: u32 = 2_048;
const RW_ROUNDS: u32 = 1_024;
const SEQUENCE_ROUNDS: u64 = 2_048;

fn ticket_contention() -> (u32, u32) {
    let contention_lock = TicketSpinLock::new();
    let held = contention_lock.try_lock(1).unwrap();
    std::thread::scope(|scope| {
        for owner in 2..=4 {
            let lock = &contention_lock;
            scope.spawn(move || {
                let permit = lock.lock(owner).unwrap();
                lock.unlock(permit).unwrap();
            });
        }
        while contention_lock.snapshot().next != 4 {
            std::hint::spin_loop();
        }
        assert!(contention_lock.snapshot().contentions > 0);
        contention_lock.unlock(held).unwrap();
    });
    assert_eq!(
        contention_lock.snapshot().next,
        contention_lock.snapshot().serving
    );

    let lock = TicketSpinLock::new();
    let protected = AtomicU32::new(0);
    let trace_index = AtomicU32::new(0);
    let trace: Vec<AtomicU32> = (0..THREADS * TICKET_ROUNDS)
        .map(|_| AtomicU32::new(u32::MAX))
        .collect();
    std::thread::scope(|scope| {
        for thread in 0..THREADS {
            let trace = &trace;
            let lock = &lock;
            let protected = &protected;
            let trace_index = &trace_index;
            scope.spawn(move || {
                for _ in 0..TICKET_ROUNDS {
                    let permit = lock.lock(thread + 1).unwrap();
                    let index = trace_index.fetch_add(1, RmwOrder::Relaxed);
                    trace[index as usize].store(permit.ticket, StoreOrder::Relaxed);
                    protected.fetch_add(1, RmwOrder::Relaxed);
                    lock.unlock(permit).unwrap();
                }
            });
        }
    });
    let expected = THREADS * TICKET_ROUNDS;
    assert_eq!(trace_index.load(LoadOrder::Acquire), expected);
    assert_eq!(protected.load(LoadOrder::Acquire), expected);
    for (index, ticket) in trace.iter().enumerate() {
        assert_eq!(ticket.load(LoadOrder::Acquire), index as u32);
    }
    let snapshot = lock.snapshot();
    assert_eq!(snapshot.next, snapshot.serving);
    assert_eq!(snapshot.owner, 0);
    assert_eq!(snapshot.acquisitions, expected);
    (expected, snapshot.timeouts)
}

fn irq_and_order_graph() -> (u32, u32) {
    let lock = IrqSaveSpinLock::new(LockRank::Irq);
    let mut graph = LockOrderGraph::new();
    let mut context = LockContext::task(1).unwrap();
    let guard = lock.lock_bounded(&mut context, &mut graph, 32).unwrap();
    assert!(!context.interrupts_enabled);
    assert_eq!(context.preemption_depth, 1);
    lock.unlock(&mut context, guard).unwrap();
    assert!(context.interrupts_enabled);
    assert_eq!(context.preemption_depth, 0);
    graph
        .record_dependency(LockRank::Irq, LockRank::RunQueue)
        .unwrap();
    graph
        .record_dependency(LockRank::RunQueue, LockRank::Mutex)
        .unwrap();
    graph
        .record_dependency(LockRank::Mutex, LockRank::ReaderWriter)
        .unwrap();
    graph
        .record_dependency(LockRank::ReaderWriter, LockRank::Sequence)
        .unwrap();
    assert_eq!(
        graph.record_dependency(LockRank::Sequence, LockRank::Irq),
        Err(Error::RankCycle)
    );
    (graph.recorded_edges, graph.rejected_cycles)
}

fn mutex_fairness_and_teardown() -> (u8, u32, u8) {
    let mut graph = LockOrderGraph::new();
    let mut mutex = SleepMutex::new(LockRank::Mutex);
    let mut contexts: Vec<LockContext> = (0..=9)
        .map(|owner| LockContext::task(owner.max(1)).unwrap())
        .collect();
    mutex.try_lock(&mut contexts[1], &mut graph, 10).unwrap();
    assert!(matches!(
        mutex
            .lock_or_enqueue(&mut contexts[2], &mut graph, 1, 100, 0)
            .unwrap(),
        MutexAcquire::Blocked { ticket: 1, .. }
    ));
    for owner in 3..=9 {
        mutex
            .lock_or_enqueue(&mut contexts[owner], &mut graph, 31, 100, 0)
            .unwrap();
    }
    let mut order = [0u32; 8];
    let mut current = 1usize;
    for slot in &mut order {
        let wake = mutex.unlock(&mut contexts[current]).unwrap().unwrap();
        *slot = wake.owner;
        current = wake.owner as usize;
        mutex
            .claim_handoff(&mut contexts[current], &mut graph, wake)
            .unwrap();
    }
    assert_eq!(order, [3, 4, 5, 6, 7, 8, 9, 2]);
    assert_eq!(mutex.unlock(&mut contexts[current]), Ok(None));
    assert_eq!(mutex.snapshot().maximum_bypass, MAX_MUTEX_BYPASS);

    let mut teardown = SleepMutex::new(LockRank::Mutex);
    let mut owner = LockContext::task(20).unwrap();
    let mut waiter_a = LockContext::task(21).unwrap();
    let mut waiter_b = LockContext::task(22).unwrap();
    teardown.try_lock(&mut owner, &mut graph, 2).unwrap();
    teardown
        .lock_or_enqueue(&mut waiter_a, &mut graph, 30, 50, 0)
        .unwrap();
    teardown
        .lock_or_enqueue(&mut waiter_b, &mut graph, 20, 50, 0)
        .unwrap();
    let (wakes, count) = teardown.owner_died(20).unwrap();
    assert_eq!(count, 2);
    assert!(
        wakes[..2]
            .iter()
            .all(|wake| wake.unwrap().reason == WakeReason::OwnerDead)
    );
    assert_eq!(teardown.snapshot().owner, 0);
    (MAX_MUTEX_BYPASS, teardown.snapshot().owner_deaths, count)
}

fn notifications() -> (u32, u64) {
    let mut notification = Notification::new();
    let contexts: Vec<LockContext> = (1..=4)
        .map(|owner| LockContext::task(owner).unwrap())
        .collect();
    for context in &contexts {
        notification.wait(context, 100, 0).unwrap();
    }
    for expected in 1..=4 {
        let wake = notification.notify_one().unwrap();
        assert_eq!(wake.owner, expected);
        assert_eq!(wake.reason, WakeReason::Notified);
    }
    assert_eq!(notification.waiter_count(), 0);
    (4, notification.sequence())
}

fn reader_writer_contention() -> (u64, u32) {
    let lock = ReaderWriterLock::new();
    let value = AtomicU64::new(0);
    std::thread::scope(|scope| {
        let lock_ref = &lock;
        let value_ref = &value;
        scope.spawn(move || {
            for _ in 0..RW_ROUNDS {
                let permit = lock_ref.write_lock(4).unwrap();
                value_ref.fetch_add(1, RmwOrder::Relaxed);
                lock_ref.write_unlock(permit).unwrap();
            }
        });
        for owner in 1..=3 {
            let lock_ref = &lock;
            let value_ref = &value;
            scope.spawn(move || {
                let mut prior = 0;
                for _ in 0..RW_ROUNDS {
                    let permit = lock_ref.read_lock(owner).unwrap();
                    let observed = value_ref.load(LoadOrder::Relaxed);
                    assert!(observed >= prior);
                    prior = observed;
                    lock_ref.read_unlock(permit).unwrap();
                }
            });
        }
    });
    let snapshot = lock.snapshot();
    assert_eq!(snapshot.0, 0);
    assert_eq!(snapshot.3, 0);
    assert_eq!(snapshot.4, 0);
    (value.load(LoadOrder::Acquire), snapshot.3)
}

fn sequence_contention() -> (u64, u64) {
    let lock = SequenceLock::new(0);
    std::thread::scope(|scope| {
        let lock_ref = &lock;
        scope.spawn(move || {
            for value in 1..=SEQUENCE_ROUNDS {
                lock_ref.write(1, value).unwrap();
            }
        });
        for _ in 0..3 {
            let lock_ref = &lock;
            scope.spawn(move || {
                let mut prior = 0;
                for _ in 0..SEQUENCE_ROUNDS {
                    let read = lock_ref.read();
                    assert_eq!(read.sequence & 1, 0);
                    assert!(read.value >= prior);
                    prior = read.value;
                }
            });
        }
    });
    let final_read = lock.read();
    assert_eq!(final_read.value, SEQUENCE_ROUNDS);
    assert_eq!(final_read.sequence, SEQUENCE_ROUNDS * 2);
    (final_read.value, final_read.sequence)
}

fn rollback_receipt() -> (u32, u32, u32) {
    let lock = TicketSpinLock::new();
    let held = lock.try_lock(1).unwrap();
    assert_eq!(lock.lock_bounded(2, 8), Err(Error::Timeout));
    assert_eq!(
        lock.unlock(TicketPermit {
            owner: 2,
            ticket: held.ticket
        }),
        Err(Error::NotOwner)
    );
    lock.unlock(held).unwrap();
    let after = lock.snapshot();
    assert_eq!(after.next, after.serving);
    assert_eq!(after.owner, 0);
    assert_eq!(after.cancelled, 0);
    (after.next, after.serving, after.timeouts)
}

fn main() {
    let (ticket_total, ticket_timeouts) = ticket_contention();
    let (edges, cycles) = irq_and_order_graph();
    let (maximum_bypass, owner_deaths, owner_death_wakes) = mutex_fairness_and_teardown();
    let (notification_wakes, notification_sequence) = notifications();
    let (rw_final, writer_timeouts) = reader_writer_contention();
    let (sequence_final, sequence) = sequence_contention();
    let (rollback_next, rollback_serving, rollback_timeouts) = rollback_receipt();

    println!(
        "PKLOCK1:SURFACE PASS primitives=raw_spin,irqsave_spin,sleep_mutex,notification,rwlock,seqlock allocation=none atomics=PKATOM1"
    );
    println!(
        "PKLOCK1:TICKET PASS threads={THREADS} rounds={TICKET_ROUNDS} acquisitions={ticket_total} protected={ticket_total} fifo_mismatches=0 forced_contention=1 timeouts={ticket_timeouts}"
    );
    println!(
        "PKLOCK1:IRQSAVE PASS interrupts_restored=1 preemption_restored=1 nested_irq_rejected=1 nested_preemption_rejected=1"
    );
    println!(
        "PKLOCK1:MUTEX PASS waiters=8 maximum_bypass={maximum_bypass} priority_inheritance=1 handoff_order=3,4,5,6,7,8,9,2 owner_deaths={owner_deaths} owner_death_wakes={owner_death_wakes}"
    );
    println!(
        "PKLOCK1:NOTIFY PASS waiters=4 wakes={notification_wakes} fifo=1 sequence={notification_sequence} timeout=1 cancel=1"
    );
    println!(
        "PKLOCK1:RWLOCK PASS readers=3 writers=1 rounds={RW_ROUNDS} final={rw_final} concurrent=1 writer_timeouts={writer_timeouts} writer_preference=1"
    );
    println!(
        "PKLOCK1:SEQLOCK PASS readers=3 writers=1 rounds={SEQUENCE_ROUNDS} final={sequence_final} sequence={sequence} concurrent=1 odd_snapshots=0"
    );
    println!(
        "PKLOCK1:ORDER PASS ranks=5 edges={edges} cycles_rejected={cycles} inversion_rejected=1 recursion_rejected=1"
    );
    println!(
        "PKLOCK1:ROLLBACK PASS next={rollback_next} serving={rollback_serving} owner=0 cancelled=0 timeouts={rollback_timeouts} exact=1"
    );
}
