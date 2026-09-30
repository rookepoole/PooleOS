#![allow(dead_code)]

#[path = "../../native/kernel/src/scheduler_deferred.rs"]
mod deferred;

use deferred::{DeferredWorkController as Controller, DispatchPermit, Error, FaultPoint as Fault,
    Operation, Priority, TopHalfContext, WorkId, WorkRequest, WorkState};

fn context() -> TopHalfContext {
    TopHalfContext { interrupt_depth: 1, interrupts_disabled: true, queue_lock_held: true, worker_context: false }
}

fn request(key: u16) -> WorkRequest {
    WorkRequest { key, source: 1, priority: Priority::Normal, operation: Operation::Add(7) }
}

fn enqueue(c: &mut Controller, key: u16) -> WorkId {
    c.enqueue_from_top_half(request(key), &context(), Fault::None).unwrap()
}

fn valid(c: &Controller) {
    assert_eq!(c.validate(), Ok(()));
}

fn fixed_capacity() -> usize {
    let mut c = Controller::new();
    let mut ids = Vec::new();
    for key in 1..=8 { ids.push(enqueue(&mut c, key)); }
    let mut cases = 0;
    let before = c.summary();
    assert_eq!(c.enqueue_from_top_half(request(9), &context(), Fault::None), Err(Error::Capacity));
    assert_eq!(c.summary(), before);
    cases += 1;
    let permit = c.observe_eoi().unwrap();
    for _ in 0..8 { c.dispatch_one(0, permit).unwrap(); }
    let before = c.summary();
    assert_eq!(c.enqueue_from_top_half(request(9), &context(), Fault::None), Err(Error::Capacity));
    assert_eq!(c.summary(), before);
    cases += 1;
    c.retire(ids[0], Fault::None).unwrap();
    enqueue(&mut c, 9);
    let before = c.summary();
    assert_eq!(c.enqueue_from_top_half(request(10), &context(), Fault::None), Err(Error::Capacity));
    assert_eq!(c.summary(), before);
    valid(&c);
    cases + 1
}

fn duplicate_suppression() -> usize {
    let mut cases = 0;
    for state in 0..4 {
        let mut c = Controller::new();
        let id = enqueue(&mut c, 1);
        if state == 2 { let p = c.observe_eoi().unwrap(); c.dispatch_one(0, p).unwrap(); }
        if state == 3 { c.cancel(id).unwrap(); }
        let mut duplicate = request(1);
        if state == 1 { duplicate.operation = Operation::Xor(99); duplicate.priority = Priority::High; }
        let mut expected = c.summary();
        expected.duplicate_suppressed += 1;
        assert_eq!(c.enqueue_from_top_half(duplicate, &context(), Fault::None), Err(Error::Duplicate));
        assert_eq!(c.summary(), expected);
        let mut other_source = request(1);
        other_source.source = 2;
        c.enqueue_from_top_half(other_source, &context(), Fault::None).unwrap();
        valid(&c);
        cases += 1;
    }
    cases
}

fn top_half_context() -> usize {
    let mut cases = 0;
    for index in 0..5 {
        let mut c = Controller::new();
        let mut bad = context();
        match index { 0 => bad.interrupt_depth = 0, 1 => bad.interrupt_depth = 2,
            2 => bad.interrupt_depth = 255, 3 => bad.interrupts_disabled = false,
            _ => bad.queue_lock_held = false }
        let before = c.summary();
        assert_eq!(c.enqueue_from_top_half(request(1), &bad, Fault::None), Err(Error::TopHalfContext));
        assert_eq!(c.summary(), before);
        enqueue(&mut c, 1);
        valid(&c);
        cases += 1;
    }
    cases
}

fn recursion() -> usize {
    let mut c = Controller::new();
    let mut bad = context();
    bad.worker_context = true;
    let before = c.summary();
    assert_eq!(c.enqueue_from_top_half(request(1), &bad, Fault::None), Err(Error::Recursion));
    assert_eq!(c.summary(), before);
    let id = enqueue(&mut c, 1);
    let p = c.observe_eoi().unwrap();
    assert_eq!(c.claim_one(0, p, Fault::None), Ok(id));
    let before = c.summary();
    assert_eq!(c.enqueue_from_top_half(request(2), &context(), Fault::None), Err(Error::Recursion));
    assert_eq!(c.summary(), before);
    c.finish_claimed(0, id, Fault::None).unwrap();
    enqueue(&mut c, 2);
    valid(&c);
    2
}

fn eoi_permit() -> usize {
    let mut c = Controller::new();
    let id = enqueue(&mut c, 1);
    let mut cases = 0;
    for epoch in [0, 1] {
        let before = c.summary();
        assert_eq!(c.claim_one(0, DispatchPermit { eoi_epoch: epoch }, Fault::None), Err(Error::DispatchBeforeEoi));
        assert_eq!(c.summary(), before);
        cases += 1;
    }
    let old = c.observe_eoi().unwrap();
    let p = c.observe_eoi().unwrap();
    for invalid in [old, DispatchPermit { eoi_epoch: p.eoi_epoch + 1 }] {
        let before = c.summary();
        assert_eq!(c.claim_one(0, invalid, Fault::None), Err(Error::DispatchBeforeEoi));
        assert_eq!(c.summary(), before);
        cases += 1;
    }
    assert_eq!(c.claim_one(0, p, Fault::None), Ok(id));
    let before = c.summary();
    assert_eq!(c.observe_eoi(), Err(Error::WorkerOwnership));
    assert_eq!(c.summary(), before);
    c.finish_claimed(0, id, Fault::None).unwrap();
    valid(&c);
    cases + 1
}

fn priority_bypass() -> usize {
    let mut c = Controller::new();
    for key in 1..=5 {
        let mut work = request(key);
        work.priority = if key == 2 { Priority::Normal } else { Priority::High };
        c.enqueue_from_top_half(work, &context(), Fault::None).unwrap();
    }
    let p = c.observe_eoi().unwrap();
    let mut cases = 0;
    for slot in [0, 2, 3, 1, 4] {
        let receipt = c.dispatch_one(0, p).unwrap();
        assert_eq!(receipt.id.slot, slot);
        assert!(c.summary().max_high_bypass_observed <= 3);
        valid(&c);
        cases += 1;
    }
    assert_eq!(c.summary().max_high_bypass_observed, 3);
    cases
}

fn queued_cancel() -> usize {
    let mut cases = 0;
    for op in [Operation::Add(7), Operation::Xor(7), Operation::Fence(7)] {
        let mut c = Controller::new();
        let id = c.enqueue_from_top_half(WorkRequest { operation: op, ..request(1) }, &context(), Fault::None).unwrap();
        c.cancel(id).unwrap();
        let p = c.observe_eoi().unwrap();
        let before = c.summary();
        assert_eq!(c.dispatch_one(0, p), Err(Error::Empty));
        assert_eq!(c.cancel(id), Err(Error::State));
        assert_eq!(c.summary(), before);
        assert_eq!((before.sum_lane, before.xor_lane, before.fence_lane, before.cancelled), (0, 0, 0, 1));
        c.retire(id, Fault::None).unwrap();
        valid(&c);
        cases += 1;
    }
    cases
}

fn running_cancel() -> usize {
    let mut cases = 0;
    for op in [Operation::Add(7), Operation::Xor(7), Operation::Fence(7)] {
        let mut c = Controller::new();
        let id = c.enqueue_from_top_half(WorkRequest { operation: op, ..request(1) }, &context(), Fault::None).unwrap();
        let p = c.observe_eoi().unwrap();
        c.claim_one(0, p, Fault::None).unwrap();
        c.cancel(id).unwrap();
        let before = c.summary();
        assert_eq!(c.cancel(id), Err(Error::State));
        assert_eq!(c.retire(id, Fault::None), Err(Error::State));
        assert_eq!(c.summary(), before);
        let receipt = c.finish_claimed(0, id, Fault::None).unwrap();
        assert_eq!((receipt.state, receipt.result), (WorkState::Cancelled, 0));
        let after = c.summary();
        assert_eq!((after.sum_lane, after.xor_lane, after.fence_lane), (0, 0, 0));
        valid(&c);
        cases += 1;
    }
    let mut c = Controller::new();
    let id = enqueue(&mut c, 1);
    let p = c.observe_eoi().unwrap();
    c.claim_one(0, p, Fault::None).unwrap();
    c.cancel(id).unwrap();
    let before = c.summary();
    assert_eq!(c.finish_claimed(1, id, Fault::None), Err(Error::WorkerOwnership));
    assert_eq!(c.summary(), before);
    c.finish_claimed(0, id, Fault::None).unwrap();
    valid(&c);
    cases + 1
}

fn flush_watermark() -> usize {
    let mut c = Controller::new();
    let id = enqueue(&mut c, 1);
    let token = c.begin_flush();
    assert!(!c.flush_complete(token));
    let p = c.observe_eoi().unwrap();
    c.claim_one(0, p, Fault::None).unwrap();
    assert!(!c.flush_complete(token));
    c.cancel(id).unwrap();
    assert!(!c.flush_complete(token));
    c.finish_claimed(0, id, Fault::None).unwrap();
    enqueue(&mut c, 2);
    assert!(c.flush_complete(token));
    assert!(!c.flush_complete(c.begin_flush()));
    valid(&c);
    4
}

fn stale_generation() -> usize {
    let mut c = Controller::new();
    let old = enqueue(&mut c, 1);
    c.cancel(old).unwrap();
    c.retire(old, Fault::None).unwrap();
    let current = enqueue(&mut c, 1);
    assert_eq!(old.slot, current.slot);
    assert_ne!(old.generation, current.generation);
    let before = c.summary();
    assert_eq!(c.request(old), Err(Error::StaleId));
    assert_eq!(c.cancel(old), Err(Error::StaleId));
    assert_eq!(c.retire(old, Fault::None), Err(Error::StaleId));
    assert_eq!(c.finish_claimed(0, old, Fault::None), Err(Error::StaleId));
    assert_eq!(c.request(WorkId { slot: 255, ..current }), Err(Error::StaleId));
    assert_eq!(c.summary(), before);
    assert_eq!(c.request(current), Ok(request(1)));
    valid(&c);
    5
}

fn fault_rollback() -> usize {
    let mut cases = 0;
    for fault in [Fault::AfterReserve, Fault::AfterQueue] {
        let mut c = Controller::new();
        assert_eq!(c.enqueue_from_top_half(request(1), &context(), fault), Err(Error::FaultInjected));
        let after = c.summary();
        assert_eq!((after.free, after.pending, after.rollback_count, after.enqueued), (8, 0, 1, 0));
        enqueue(&mut c, 1);
        valid(&c);
        cases += 1;
    }
    let mut c = Controller::new();
    let id = enqueue(&mut c, 1);
    let p = c.observe_eoi().unwrap();
    let mut expected = c.summary();
    expected.rollback_count += 1;
    assert_eq!(c.claim_one(0, p, Fault::BeforeExecute), Err(Error::FaultInjected));
    assert_eq!(c.summary(), expected);
    cases += 1;
    assert_eq!(c.claim_one(0, p, Fault::None), Ok(id));
    assert_eq!(c.finish_claimed(0, id, Fault::BeforeCommit), Err(Error::FaultInjected));
    let after = c.summary();
    assert_eq!((after.pending, after.running, after.rollback_count, after.sum_lane), (1, 0, 2, 0));
    cases += 1;
    assert_eq!(c.dispatch_one(0, p).unwrap().id, id);
    let mut expected = c.summary();
    expected.rollback_count += 1;
    assert_eq!(c.retire(id, Fault::Cleanup), Err(Error::FaultInjected));
    assert_eq!(c.summary(), expected);
    c.retire(id, Fault::None).unwrap();
    assert_eq!(c.summary().free, 8);
    valid(&c);
    cases + 1
}

fn shutdown_order() -> usize {
    let mut c = Controller::new();
    let before = c.summary();
    assert_eq!(c.finish_shutdown(), Err(Error::ShutdownPending));
    assert_eq!(c.summary(), before);
    let first = enqueue(&mut c, 1);
    let before = c.summary();
    assert_eq!(c.finish_shutdown(), Err(Error::ShutdownPending));
    assert_eq!(c.summary(), before);
    enqueue(&mut c, 2);
    let p = c.observe_eoi().unwrap();
    c.claim_one(0, p, Fault::None).unwrap();
    assert_eq!(c.begin_shutdown(), Ok(1));
    let before = c.summary();
    assert_eq!(c.finish_shutdown(), Err(Error::ShutdownPending));
    assert_eq!(c.summary(), before);
    c.finish_claimed(0, first, Fault::None).unwrap();
    let before = c.summary();
    assert_eq!(c.enqueue_from_top_half(request(3), &context(), Fault::None), Err(Error::IntakeClosed));
    assert_eq!(c.summary(), before);
    assert_eq!(c.finish_shutdown(), Ok(2));
    let before = c.summary();
    assert_eq!(c.enqueue_from_top_half(request(3), &context(), Fault::None), Err(Error::IntakeClosed));
    assert_eq!(c.summary(), before);
    assert!(before.shutdown_complete);
    assert_eq!(before.free, 8);
    valid(&c);
    5
}

fn main() {
    let groups: &[(&str, fn() -> usize)] = &[
        ("FIXED-CAPACITY", fixed_capacity), ("DUPLICATE-SUPPRESSION", duplicate_suppression),
        ("TOP-HALF-CONTEXT", top_half_context), ("RECURSION", recursion), ("EOI-PERMIT", eoi_permit),
        ("PRIORITY-BYPASS", priority_bypass), ("QUEUED-CANCEL", queued_cancel),
        ("RUNNING-CANCEL", running_cancel), ("FLUSH-WATERMARK", flush_watermark),
        ("STALE-GENERATION", stale_generation), ("FAULT-ROLLBACK", fault_rollback),
        ("SHUTDOWN-ORDER", shutdown_order),
    ];
    let args: Vec<String> = std::env::args().skip(1).collect();
    assert!(args.len() <= 1);
    assert!(args.is_empty() || groups.iter().any(|(name, _)| *name == args[0]));
    for (name, run) in groups {
        if args.is_empty() || args[0] == *name {
            let cases = run();
            println!("PKSCHED3:CONTROL PASS id=NEG-N12-PKSCHED3-{name} cases={cases} verified={cases}");
        }
    }
}
