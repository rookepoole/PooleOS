use poolekernel::scheduler_deferred::{
    DeferredWorkController, DispatchPermit, Error, FaultPoint, Operation, Priority, TopHalfContext,
    WorkRequest, WorkState,
};

fn top_half() -> TopHalfContext {
    TopHalfContext {
        interrupt_depth: 1,
        interrupts_disabled: true,
        queue_lock_held: true,
        worker_context: false,
    }
}

fn request(key: u16, priority: Priority, operation: Operation) -> WorkRequest {
    WorkRequest {
        key,
        source: 1,
        priority,
        operation,
    }
}

fn state_label(state: WorkState) -> &'static str {
    match state {
        WorkState::Completed => "completed",
        WorkState::Cancelled => "cancelled",
        _ => "invalid",
    }
}

fn fault_profile() -> DeferredWorkController {
    let mut controller = DeferredWorkController::new();
    for (key, fault) in [(10, FaultPoint::AfterReserve), (11, FaultPoint::AfterQueue)] {
        assert_eq!(
            controller.enqueue_from_top_half(
                request(key, Priority::High, Operation::Add(1)),
                &top_half(),
                fault,
            ),
            Err(Error::FaultInjected)
        );
    }
    let id = controller
        .enqueue_from_top_half(
            request(12, Priority::High, Operation::Add(1)),
            &top_half(),
            FaultPoint::None,
        )
        .expect("fault work");
    let permit = controller.observe_eoi().expect("fault EOI");
    assert_eq!(
        controller.claim_one(0, permit, FaultPoint::BeforeExecute),
        Err(Error::FaultInjected)
    );
    assert_eq!(controller.claim_one(0, permit, FaultPoint::None), Ok(id));
    assert_eq!(
        controller.finish_claimed(0, id, FaultPoint::BeforeCommit),
        Err(Error::FaultInjected)
    );
    controller.dispatch_one(1, permit).expect("fault recovery");
    assert_eq!(
        controller.retire(id, FaultPoint::Cleanup),
        Err(Error::FaultInjected)
    );
    controller.retire(id, FaultPoint::None).expect("retire");
    controller
}

fn main() {
    let requests = [
        request(1, Priority::High, Operation::Add(10)),
        request(2, Priority::Normal, Operation::Xor(90)),
        request(3, Priority::High, Operation::Add(20)),
        request(4, Priority::High, Operation::Add(30)),
        request(5, Priority::High, Operation::Add(40)),
        request(6, Priority::Normal, Operation::Add(50)),
        request(7, Priority::Normal, Operation::Fence(7)),
        request(8, Priority::Normal, Operation::Add(60)),
    ];
    let mut controller = DeferredWorkController::new();
    let mut ids = [None; 8];
    for (index, work) in requests.into_iter().enumerate() {
        ids[index] = Some(
            controller
                .enqueue_from_top_half(work, &top_half(), FaultPoint::None)
                .expect("top-half enqueue"),
        );
    }
    assert_eq!(
        controller.enqueue_from_top_half(requests[2], &top_half(), FaultPoint::None),
        Err(Error::Duplicate)
    );
    controller
        .cancel(ids[3].expect("queued ID"))
        .expect("cancel queued");
    assert_eq!(
        controller.claim_one(0, DispatchPermit { eoi_epoch: 0 }, FaultPoint::None,),
        Err(Error::DispatchBeforeEoi)
    );
    let permit = controller.observe_eoi().expect("EOI");
    let flush = controller.begin_flush();
    println!(
        "PKSCHED3:QUEUE PASS enqueued={} duplicate={} queued_cancelled={} eoi={} pending={} flush_before={}",
        controller.summary().enqueued,
        controller.summary().duplicate_suppressed,
        controller.summary().cancelled,
        controller.summary().eoi_epoch,
        controller.summary().pending,
        usize::from(controller.flush_complete(flush)),
    );

    let mut slots = [u8::MAX; 6];
    let mut workers = [u8::MAX; 6];
    let mut states = [WorkState::Free; 6];
    for (index, worker) in [0u8, 1, 0, 1, 0, 1].into_iter().enumerate() {
        let id = controller
            .claim_one(worker, permit, FaultPoint::None)
            .expect("claim");
        if matches!(
            controller.request(id),
            Ok(WorkRequest {
                operation: Operation::Fence(_),
                ..
            })
        ) {
            controller.cancel(id).expect("running cancel");
        }
        let receipt = controller
            .finish_claimed(worker, id, FaultPoint::None)
            .expect("finish");
        slots[index] = id.slot;
        workers[index] = worker;
        states[index] = receipt.state;
    }
    println!(
        "PKSCHED3:WORK PASS slots={},{},{},{},{},{} workers={},{},{},{},{},{} states={},{},{},{},{},{} max_bypass={}",
        slots[0],
        slots[1],
        slots[2],
        slots[3],
        slots[4],
        slots[5],
        workers[0],
        workers[1],
        workers[2],
        workers[3],
        workers[4],
        workers[5],
        state_label(states[0]),
        state_label(states[1]),
        state_label(states[2]),
        state_label(states[3]),
        state_label(states[4]),
        state_label(states[5]),
        controller.summary().max_high_bypass_observed,
    );

    assert!(!controller.flush_complete(flush));
    assert_eq!(controller.begin_shutdown(), Ok(1));
    assert!(controller.flush_complete(flush));
    assert_eq!(controller.finish_shutdown(), Ok(8));
    let stale_rejected = matches!(
        ids[0].and_then(|id| controller.cancel(id).err()),
        Some(Error::StaleId)
    );
    let recursion_rejected = controller.enqueue_from_top_half(
        request(9, Priority::Normal, Operation::Add(1)),
        &TopHalfContext {
            worker_context: true,
            ..top_half()
        },
        FaultPoint::None,
    ) == Err(Error::Recursion);
    let intake_rejected = controller.enqueue_from_top_half(
        request(9, Priority::Normal, Operation::Add(1)),
        &top_half(),
        FaultPoint::None,
    ) == Err(Error::IntakeClosed);
    let summary = controller.summary();
    println!(
        "PKSCHED3:FLUSH PASS watermark={} completion={} sum={} xor={} fence={} completed={} cancelled={} running_cancel={} retired={} free={}",
        flush.enqueue_watermark,
        summary.completion_sequence,
        summary.sum_lane,
        summary.xor_lane,
        summary.fence_lane,
        summary.completed,
        summary.cancelled,
        summary.running_cancel_requests,
        summary.retired,
        summary.free,
    );

    let fault = fault_profile();
    let fault_summary = fault.summary();
    println!(
        "PKSCHED3:FAULT PASS rollbacks={} free={} valid={}",
        fault_summary.rollback_count,
        fault_summary.free,
        usize::from(fault.validate().is_ok()),
    );
    println!(
        "PKSCHED3:BOUNDARY PASS pre_eoi_rejected=1 recursion_rejected={} stale_rejected={} intake_rejected={} arbitrary_callbacks=0",
        usize::from(recursion_rejected),
        usize::from(stale_rejected),
        usize::from(intake_rejected),
    );
}
