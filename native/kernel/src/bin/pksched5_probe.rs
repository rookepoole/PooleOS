use poolekernel::{
    scheduler_ap_workers::{
        AP_COUNT, AP_MASK, ApWorkerController, Consumer, DispatchTicket, OFFLINE_PROBE_CPU,
        ONLINE_MASK, Priority, RemoteAck, TopHalfContext, WORK_CAPACITY, WORKER_STACK_BYTES,
        WorkId, WorkRequest,
    },
    smp_ipi,
};

const WORK_ITEMS: usize = 13;

fn top_half() -> TopHalfContext {
    TopHalfContext {
        interrupt_depth: 1,
        interrupts_disabled: true,
        queue_lock_held: false,
        worker_context: false,
    }
}

fn service(key: u16, cpu: u8, retired: u32) -> WorkRequest {
    WorkRequest {
        key,
        source_cpu: 0,
        target_cpu: cpu,
        priority: Priority::Normal,
        consumer: Consumer::ServiceGenerationReclaim {
            retired_generation: retired,
            active_generation: retired + 1,
        },
    }
}

fn driver(key: u16, cpu: u8, sample: u32) -> WorkRequest {
    WorkRequest {
        key,
        source_cpu: 0,
        target_cpu: cpu,
        priority: Priority::High,
        consumer: Consumer::DriverTimerBottomHalf { vector: 64, sample },
    }
}

fn ack(ticket: DispatchTicket) -> RemoteAck {
    RemoteAck {
        target_cpu: ticket.target_cpu,
        attempt: ticket.request_attempt,
        sequence: ticket.request_sequence,
        operation: smp_ipi::Operation::CallFunction as u32,
        status: smp_ipi::ACK_ACCEPTED,
        error: smp_ipi::ERROR_NONE,
        result: ticket.expected_result,
    }
}

fn main() {
    let mut controller = ApWorkerController::new();
    let mut ids = [WorkId::new(0, 1).expect("identity"); WORK_ITEMS];
    let mut index = 0usize;
    for cpu in 1..=AP_COUNT as u8 {
        ids[index] = controller
            .enqueue_from_top_half(top_half(), service(100 + u16::from(cpu), cpu, cpu.into()))
            .expect("service enqueue");
        index += 1;
        for lane in 1..=3u8 {
            ids[index] = controller
                .enqueue_from_top_half(
                    top_half(),
                    driver(
                        200 + u16::from(cpu) * 10 + u16::from(lane),
                        cpu,
                        u32::from(cpu) * 10 + u32::from(lane),
                    ),
                )
                .expect("driver enqueue");
            index += 1;
        }
    }
    ids[index] = controller
        .enqueue_from_top_half(top_half(), driver(299, 1, 99))
        .expect("queued cancellation enqueue");
    assert_eq!(index + 1, WORK_ITEMS);
    assert_eq!(
        controller
            .enqueue_from_top_half(top_half(), driver(211, 1, 11))
            .unwrap_err()
            .label(),
        "duplicate"
    );
    controller.cancel(ids[12]).expect("queued cancellation");
    let flush = controller.begin_flush();
    let permit = controller.observe_eoi().expect("EOI permit");

    println!(
        "PKSCHED5:TOPOLOGY PASS cpus=4 aps={} online_mask=0x{:02X} ap_mask=0x{:02X} workers={} queues={} capacity={} stack_bytes_each={}",
        AP_COUNT, ONLINE_MASK, AP_MASK, AP_COUNT, AP_COUNT, WORK_CAPACITY, WORKER_STACK_BYTES,
    );
    println!(
        "PKSCHED5:QUEUE PASS enqueued={} duplicate_suppressed={} eoi_epoch={} flush_watermark={} queued_cancelled={}",
        controller.summary().enqueued,
        controller.summary().duplicate_suppressed,
        permit.eoi_epoch,
        flush.enqueue_watermark,
        controller.summary().queued_cancellations,
    );

    let offline = controller
        .stage_offline_probe(ids[5], OFFLINE_PROBE_CPU, permit, 3, 2)
        .expect("offline probe");
    controller.timeout(offline).expect("offline rollback");
    controller
        .reject_stale_ack(offline, ack(offline))
        .expect("late acknowledgement rejection");

    let mut trace = [[u8::MAX; 4]; AP_COUNT];
    for cpu in 1..=AP_COUNT as u8 {
        for local_index in 0..4usize {
            let ticket = controller
                .stage_dispatch(cpu, permit, 3 + local_index as u64, 2 + local_index as u64)
                .expect("stage AP worker");
            trace[cpu as usize - 1][local_index] = ticket.id.slot;
            if cpu == 2 && local_index == 0 {
                controller
                    .cancel(ticket.id)
                    .expect("in-flight remote cancellation");
            }
            controller
                .acknowledge(ticket, ack(ticket))
                .expect("AP worker acknowledgement");
        }
    }
    let dispatched = controller.summary();
    println!(
        "PKSCHED5:DISPATCH PASS trace=1:{},1:{},1:{},1:{};2:{},2:{},2:{},2:{};3:{},3:{},3:{},3:{} worker_entries={},{},{} ap_calls={} driver_calls={} service_calls={} maximum_high_bypass={}",
        trace[0][0],
        trace[0][1],
        trace[0][2],
        trace[0][3],
        trace[1][0],
        trace[1][1],
        trace[1][2],
        trace[1][3],
        trace[2][0],
        trace[2][1],
        trace[2][2],
        trace[2][3],
        dispatched.worker_entries[0],
        dispatched.worker_entries[1],
        dispatched.worker_entries[2],
        dispatched.remote_acks,
        dispatched.driver_executions,
        dispatched.service_executions,
        dispatched.maximum_high_bypass,
    );
    println!(
        "PKSCHED5:CANCEL PASS offline_cpu={} timeouts={} rollbacks={} queued={} remote_requests={} remote_completions={} stale_rejections={} source_queue_restored=1",
        OFFLINE_PROBE_CPU,
        dispatched.timeout_count,
        dispatched.rollback_count,
        dispatched.queued_cancellations,
        dispatched.remote_cancel_requests,
        dispatched.remote_cancel_completions,
        dispatched.stale_rejections,
    );

    assert!(controller.flush_complete(flush));
    let stale = ids[0];
    assert_eq!(
        controller
            .retire_all_terminal(flush)
            .expect("terminal reclamation"),
        WORK_ITEMS as u8
    );
    assert_eq!(controller.request(stale).unwrap_err().label(), "stale_id");
    let reclaimed = controller.summary();
    println!(
        "PKSCHED5:FLUSH PASS complete=1 completed={} cancelled={} driver_sum={} service_generation={} reclaimed={} stale_id_rejected=1",
        reclaimed.completed,
        reclaimed.cancelled,
        reclaimed.driver_sample_sum,
        reclaimed.active_service_generation,
        reclaimed.reclaimed,
    );

    for cpu in (1..=AP_COUNT as u8).rev() {
        controller.offline_worker(cpu).expect("worker retirement");
    }
    controller.finish_shutdown().expect("shutdown");
    let final_summary = controller.summary();
    println!(
        "PKSCHED5:CLEANUP PASS online_after=0x{:02X} workers_retired={} free={} queued={} dispatching={} terminal={} stack_bytes_cleared={} valid={}",
        final_summary.online_mask,
        final_summary.worker_retirements,
        final_summary.free,
        final_summary.queued,
        final_summary.dispatching,
        final_summary.terminal,
        u32::try_from(AP_COUNT).expect("AP count") * WORKER_STACK_BYTES,
        usize::from(controller.validate().is_ok()),
    );
}
