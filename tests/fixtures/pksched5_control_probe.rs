// Appended to the actual controller module; all operations use native code.
fn control_context() -> TopHalfContext {
    TopHalfContext { interrupt_depth: 1, interrupts_disabled: true, queue_lock_held: false, worker_context: false }
}

fn control_request(key: u16, cpu: u8, priority: Priority) -> WorkRequest {
    WorkRequest { key, source_cpu: 0, target_cpu: cpu, priority,
        consumer: Consumer::DriverTimerBottomHalf { vector: 64, sample: 7 } }
}

fn control_ack(ticket: DispatchTicket) -> RemoteAck {
    RemoteAck { target_cpu: ticket.target_cpu, attempt: ticket.request_attempt,
        sequence: ticket.request_sequence, operation: smp_ipi::Operation::CallFunction as u32,
        status: smp_ipi::ACK_ACCEPTED, error: smp_ipi::ERROR_NONE, result: ticket.expected_result }
}

fn control_queue(cpu: u8) -> (ApWorkerController, WorkId, DispatchPermit) {
    let mut c = ApWorkerController::new();
    let id = c.enqueue_from_top_half(control_context(), control_request(1, cpu, Priority::Normal)).unwrap();
    let permit = c.observe_eoi().unwrap();
    (c, id, permit)
}

pub fn controls_main() {
    let selected = std::env::args().nth(1);
    for group in ["TYPED-CALL-ALLOWLIST", "TOP-HALF-CONTEXT", "DISPATCH-BEFORE-EOI",
        "DUPLICATE-WORK", "QUEUED-CANCEL", "REMOTE-CANCEL", "ACK-BINDING", "OFFLINE-TIMEOUT",
        "SOURCE-QUEUE-ROLLBACK", "LATE-ACK", "FAIRNESS-BOUND", "FLUSH-WATERMARK",
        "RECLAIM-GENERATION", "STALE-ID"] {
        if selected.as_ref().is_some_and(|s| s != group) { continue; }
        let mut count = 0;
        match group {
            "TYPED-CALL-ALLOWLIST" => {
                for case in 0..8 {
                    let mut c = ApWorkerController::new();
                    let mut r = control_request(1, 1, Priority::Normal);
                    match case {
                        0 => r.consumer = Consumer::DriverTimerBottomHalf { vector: 63, sample: 1 },
                        1 => r.consumer = Consumer::DriverTimerBottomHalf { vector: 64, sample: 0 },
                        2 => r.consumer = Consumer::ServiceGenerationReclaim { retired_generation: 0, active_generation: 1 },
                        3 => r.consumer = Consumer::ServiceGenerationReclaim { retired_generation: 1, active_generation: 3 },
                        4 => r.consumer = Consumer::ServiceGenerationReclaim { retired_generation: u32::MAX, active_generation: 0 },
                        5 => r.source_cpu = 1,
                        6 => r.target_cpu = 0,
                        _ => r.key = 0,
                    }
                    let before = c.summary();
                    assert_eq!(c.enqueue_from_top_half(control_context(), r), Err(Error::InvalidRequest));
                    assert_eq!(c.summary(), before);
                    count += 1;
                }
            }
            "TOP-HALF-CONTEXT" => {
                for case in 0..5 {
                    let mut c = ApWorkerController::new();
                    let mut context = control_context();
                    match case { 0 => context.interrupt_depth = 0, 1 => context.interrupt_depth = 2,
                        2 => context.interrupts_disabled = false, 3 => context.queue_lock_held = true,
                        _ => context.worker_context = true }
                    let before = c.summary();
                    assert_eq!(c.enqueue_from_top_half(context, control_request(1, 1, Priority::Normal)), Err(Error::TopHalfContext));
                    assert_eq!(c.summary(), before);
                    count += 1;
                }
            }
            "DISPATCH-BEFORE-EOI" => {
                for case in 0..4 {
                    let (mut c, _, mut permit) = control_queue(1);
                    match case { 0 => permit.eoi_epoch = 0, 1 => permit.eoi_epoch += 1,
                        2 => permit.enqueue_watermark += 1, _ => permit.enqueue_watermark = 0 }
                    let before = c.summary();
                    assert_eq!(c.stage_dispatch(1, permit, 1, 1), Err(Error::DispatchBeforeEoi));
                    assert_eq!(c.summary(), before);
                    count += 1;
                }
            }
            "DUPLICATE-WORK" => {
                for cpu in 1..=3 {
                    let (mut c, id, _) = control_queue(cpu);
                    assert_eq!(c.enqueue_from_top_half(control_context(), control_request(1, cpu, Priority::Normal)), Err(Error::Duplicate));
                    assert_eq!(c.summary().enqueued, 1);
                    assert_eq!(c.summary().duplicate_suppressed, 1);
                    assert_eq!(c.request(id).unwrap().target_cpu, cpu);
                    count += 1;
                }
            }
            "QUEUED-CANCEL" => {
                for cpu in 1..=3 {
                    let (mut c, id, permit) = control_queue(cpu);
                    c.cancel(id).unwrap();
                    assert_eq!(c.cancel(id), Err(Error::State));
                    assert_eq!(c.stage_dispatch(cpu, permit, 1, 1), Err(Error::Empty));
                    assert_eq!(c.summary().cancelled, 1);
                    assert_eq!(c.summary().queued_cancellations, 1);
                    count += 1;
                }
            }
            "REMOTE-CANCEL" => {
                for cpu in 1..=3 {
                    let (mut c, id, permit) = control_queue(cpu);
                    let ticket = c.stage_dispatch(cpu, permit, 1, 1).unwrap();
                    c.cancel(id).unwrap();
                    assert_eq!(c.cancel(id), Err(Error::State));
                    assert_eq!(c.acknowledge(ticket, control_ack(ticket)).unwrap().state, WorkState::Cancelled);
                    assert_eq!(c.summary().driver_sample_sum, 0);
                    assert_eq!(c.summary().remote_cancel_completions, 1);
                    count += 1;
                }
            }
            "ACK-BINDING" => {
                for case in 0..8 {
                    let (mut c, _, permit) = control_queue(1);
                    let ticket = c.stage_dispatch(1, permit, 1, 1).unwrap();
                    let mut supplied = ticket;
                    let mut ack = control_ack(ticket);
                    match case { 0 => ack.target_cpu = 2, 1 => ack.attempt += 1, 2 => ack.sequence += 1,
                        3 => ack.operation ^= 1, 4 => ack.status ^= 1, 5 => ack.error ^= 1,
                        6 => ack.result ^= 1, _ => supplied.transaction += 1 }
                    let before = c.summary();
                    assert_eq!(c.acknowledge(supplied, ack), Err(if case == 7 { Error::TicketMismatch } else { Error::Acknowledgement }));
                    assert_eq!(c.summary(), before);
                    assert_eq!(c.pending[1], Some(ticket));
                    c.acknowledge(ticket, control_ack(ticket)).unwrap();
                    count += 1;
                }
            }
            "OFFLINE-TIMEOUT" => {
                for wrong in 0..4 {
                    let (mut c, id, permit) = control_queue(1);
                    let before = c.summary();
                    assert_eq!(c.stage_offline_probe(id, wrong, permit, 1, 1), Err(Error::TimeoutTarget));
                    assert_eq!(c.summary(), before);
                    let ticket = c.stage_offline_probe(id, 4, permit, 1, 1).unwrap();
                    let mut forged = ticket;
                    forged.transaction += 1;
                    assert_eq!(c.timeout(forged), Err(Error::TimeoutTarget));
                    c.timeout(ticket).unwrap();
                    count += 1;
                }
            }
            "SOURCE-QUEUE-ROLLBACK" => {
                for cpu in 1..=3 {
                    let (mut c, id, permit) = control_queue(cpu);
                    let ticket = c.stage_offline_probe(id, 4, permit, 1, 1).unwrap();
                    c.timeout(ticket).unwrap();
                    assert_eq!(c.summary().queued, 1);
                    assert_eq!(c.request(id).unwrap().target_cpu, cpu);
                    let live = c.stage_dispatch(cpu, permit, 2, 2).unwrap();
                    assert_eq!(live.id, id);
                    c.acknowledge(live, control_ack(live)).unwrap();
                    assert_eq!(c.summary().rollback_count, 1);
                    count += 1;
                }
            }
            "LATE-ACK" => {
                for case in 0..3 {
                    let (mut c, id, permit) = control_queue(1);
                    let ticket = c.stage_offline_probe(id, 4, permit, 1, 1).unwrap();
                    c.timeout(ticket).unwrap();
                    let mut ack = control_ack(ticket);
                    match case { 0 => ack.attempt += 1, 1 => ack.sequence += 1, _ => ack.target_cpu = 1 }
                    let before = c.summary();
                    assert_eq!(c.reject_stale_ack(ticket, ack), Err(Error::TicketMismatch));
                    assert_eq!(c.summary(), before);
                    c.reject_stale_ack(ticket, control_ack(ticket)).unwrap();
                    assert_eq!(c.summary().queued, 1);
                    count += 1;
                }
            }
            "FAIRNESS-BOUND" => {
                for cpu in 1..=3 {
                    let (mut c, normal, _) = control_queue(cpu);
                    for key in 2..=4 { c.enqueue_from_top_half(control_context(), control_request(key, cpu, Priority::High)).unwrap(); }
                    let permit = c.observe_eoi().unwrap();
                    for sequence in 1..=3 {
                        let t = c.stage_dispatch(cpu, permit, 1, sequence).unwrap();
                        assert_eq!(t.id == normal, sequence == 3);
                        c.acknowledge(t, control_ack(t)).unwrap();
                    }
                    assert_eq!(c.summary().maximum_high_bypass, 2);
                    count += 1;
                }
            }
            "FLUSH-WATERMARK" => {
                for cpu in 1..=3 {
                    let (mut c, id, permit) = control_queue(cpu);
                    let token = c.begin_flush();
                    assert!(!c.flush_complete(token));
                    assert_eq!(c.reclaim(id, token), Err(Error::FlushPending));
                    let t = c.stage_dispatch(cpu, permit, 1, 1).unwrap();
                    assert!(!c.flush_complete(token));
                    c.acknowledge(t, control_ack(t)).unwrap();
                    assert!(c.flush_complete(token));
                    c.reclaim(id, token).unwrap();
                    assert_eq!(c.request(id), Err(Error::StaleId));
                    count += 1;
                }
            }
            "RECLAIM-GENERATION" => {
                for retired in [2, 3, 4, 5, u32::MAX - 1] {
                    let mut c = ApWorkerController::new();
                    let mut r = control_request(1, 1, Priority::Normal);
                    r.consumer = Consumer::ServiceGenerationReclaim { retired_generation: retired, active_generation: retired + 1 };
                    c.enqueue_from_top_half(control_context(), r).unwrap();
                    let permit = c.observe_eoi().unwrap();
                    let before = c.summary();
                    assert_eq!(c.stage_dispatch(1, permit, 1, 1), Err(Error::ReclaimOrder));
                    assert_eq!(c.summary(), before);
                    assert!(c.pending.iter().all(Option::is_none));
                    count += 1;
                }
            }
            "STALE-ID" => {
                let (mut c, id, _) = control_queue(1);
                for wrong in [WorkId { slot: 15, ..id }, WorkId { generation: 0, ..id }, WorkId { generation: id.generation + 1, ..id }] {
                    assert_eq!(c.request(wrong), Err(Error::StaleId));
                    count += 1;
                }
                c.cancel(id).unwrap();
                c.reclaim(id, c.begin_flush()).unwrap();
                assert_eq!(c.request(id), Err(Error::StaleId));
                count += 1;
            }
            _ => unreachable!(),
        }
        assert!(count > 0);
        println!("PKSCHED5:CONTROL PASS group={group} verified={count}");
    }
}
