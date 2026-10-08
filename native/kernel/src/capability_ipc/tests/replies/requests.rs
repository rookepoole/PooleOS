use super::*;
use crate::capability_ipc::request::Operation as Control;
mod deadlines;

fn begin(s: &mut Space, send: u64, m: &mut Wire) -> u64 {
    let (status, handle) = s.request_operation(caller(0), send, BASE, MAX_BYTES, Control::Begin, m);
    assert_eq!(status, Status::Ok);
    handle
}
fn take(s: &mut Space, handle: u64, m: &mut Wire) -> (Status, u64) {
    s.request_operation(caller(0), handle, BASE, RECEIVE_BYTES, Control::Take, m)
}

#[test]
fn completion_is_requester_owned_capacity_reserved_and_consumed_once() {
    let (mut s, back, endpoint, send, mut m) = setup();
    let request = begin(&mut s, send, &mut m);
    assert_eq!(request, 0x100030001);
    assert_eq!(take(&mut s, request, &mut m), (Status::Again, 0));
    let token = receive(&mut s, endpoint, &mut m);
    for _ in 0..DEPTH {
        assert_eq!(
            s.transfer(caller(0), back, BASE, 8, true, &mut m),
            (Status::Ok, 8)
        );
    }
    assert_eq!(
        s.message(caller(1), token, BASE, MAX_BYTES, Operation::Reply, &mut m),
        (Status::Ok, MAX_BYTES as u64)
    );
    assert_eq!(
        s.request_operation(caller(0), request, 0, 0, Control::Cancel, &mut m),
        (Status::Denied, 0)
    );
    s.detach(id(1)).unwrap();
    assert_eq!(
        s.prepare_request_wait(caller(0), request),
        Ok(Admission::Complete(Status::Ok))
    );
    assert_eq!(
        take(&mut s, request, &mut m),
        (Status::Ok, RECEIVE_BYTES as u64)
    );
    assert_eq!((m.word(0), m.word(1), m.word(2)), (1, 1, 0));
    assert_eq!(take(&mut s, request, &mut m), (Status::Denied, 0));
    assert_eq!(
        s.message(caller(1), token, BASE, 8, Operation::Reply, &mut m),
        (Status::Denied, 0)
    );
}

#[test]
fn every_completion_copy_fault_retains_success_and_retry_exactly_once() {
    for offset in 0..RECEIVE_BYTES {
        let (mut s, _, endpoint, send, mut m) = setup();
        let request = begin(&mut s, send, &mut m);
        let token = receive(&mut s, endpoint, &mut m);
        m.data.fill(0x4c);
        assert_eq!(
            s.message(caller(1), token, BASE, MAX_BYTES, Operation::Reply, &mut m),
            (Status::Ok, 64)
        );
        let before = (s.tables, s.objects);
        m.write_fault = Some(offset);
        assert_eq!(
            take(&mut s, request, &mut m),
            (Status::Fault, offset as u64)
        );
        assert_eq!((s.tables, s.objects), before);
        m.write_fault = None;
        assert_eq!(take(&mut s, request, &mut m), (Status::Ok, 96));
        assert_eq!(&m.data[32..], &[0x4c; 64]);
    }
}

#[test]
fn client_cancel_before_or_after_delivery_wins_once_and_revokes_reply() {
    for delivered in [false, true] {
        let (mut s, _, endpoint, send, mut m) = setup();
        let request = begin(&mut s, send, &mut m);
        let token = if delivered {
            receive(&mut s, endpoint, &mut m)
        } else {
            0
        };
        assert_eq!(
            s.request_operation(caller(0), request, 0, 0, Control::Cancel, &mut m),
            (Status::Ok, 0)
        );
        assert_eq!(
            s.request_operation(caller(0), request, 0, 0, Control::Cancel, &mut m),
            (Status::Denied, 0)
        );
        if delivered {
            assert_eq!(
                s.message(caller(1), token, BASE, 8, Operation::Reply, &mut m),
                (Status::Denied, 0)
            );
        }
        assert_eq!(take(&mut s, request, &mut m), (Status::Cancelled, 0));
        let next = begin(&mut s, send, &mut m);
        assert_eq!(next, request + (1 << 32));
        if !delivered {
            assert_eq!(receive(&mut s, endpoint, &mut m), 0);
        }
        assert_ne!(receive(&mut s, endpoint, &mut m), 0);
    }
}

#[test]
fn discard_and_server_death_deliver_durable_failures_without_mailbox_space() {
    for mode in 0..4 {
        let (mut s, back, endpoint, send, mut m) = setup();
        let request = begin(&mut s, send, &mut m);
        let token = if mode == 0 {
            0
        } else {
            receive(&mut s, endpoint, &mut m)
        };
        for _ in 0..DEPTH {
            s.transfer(caller(0), back, BASE, 8, true, &mut m);
        }
        let expected = if mode == 1 {
            assert_eq!(
                s.message(caller(1), token, 0, 0, Operation::Discard, &mut m),
                (Status::Ok, 0)
            );
            Status::Cancelled
        } else {
            if mode == 3 {
                s.destroy(id(1), endpoint).unwrap();
            } else {
                s.detach(id(1)).unwrap();
            }
            Status::Revoked
        };
        assert_eq!(
            s.prepare_request_wait(caller(0), request),
            Ok(Admission::Complete(expected))
        );
        m.write_fault = Some(0);
        let accesses = m.accesses;
        assert_eq!(take(&mut s, request, &mut m), (expected, 0));
        assert_eq!(m.accesses, accesses);
        assert_eq!(take(&mut s, request, &mut m), (Status::Denied, 0));
    }
}

#[test]
fn delegated_receiver_death_terminates_delivered_request_but_not_completed_reply() {
    for replied in [false, true] {
        let (mut s, _, endpoint, send, mut m) = setup();
        let recv = s.derive(id(1), endpoint, id(2), Rights::RECEIVE).unwrap();
        let request = begin(&mut s, send, &mut m);
        assert_eq!(
            s.message(caller(2), recv, BASE, 96, Operation::Receive, &mut m),
            (Status::Ok, 96)
        );
        if replied {
            assert_eq!(
                s.message(caller(2), m.word(2), BASE, 8, Operation::Reply, &mut m),
                (Status::Ok, 8)
            );
        }
        s.detach(id(2)).unwrap();
        assert_eq!(
            take(&mut s, request, &mut m),
            if replied {
                (Status::Ok, 40)
            } else {
                (Status::Revoked, 0)
            }
        );
    }
}

#[test]
fn request_quota_retains_terminal_records_until_consumed_and_generations_never_wrap() {
    let (mut s, _, endpoint, send, mut m) = setup();
    let mut requests = [0; CAPS];
    for r in &mut requests {
        *r = begin(&mut s, send, &mut m);
        let token = receive(&mut s, endpoint, &mut m);
        s.message(caller(1), token, 0, 0, Operation::Discard, &mut m);
    }
    let before = (s.tables, s.objects);
    assert_eq!(
        s.request_operation(caller(0), send, BASE, 64, Control::Begin, &mut m),
        (Status::Again, 0)
    );
    assert_eq!((s.tables, s.objects), before);
    assert_eq!(take(&mut s, requests[0], &mut m), (Status::Cancelled, 0));
    assert_eq!(begin(&mut s, send, &mut m), requests[0] + (1 << 32));
    s.detach(id(0)).unwrap();
    assert!(s.tables[0].requests.iter().all(|r| !r.occupied()));
    assert_eq!(s.tables[0].requests[0].generation, 2);
    let (mut s, _, _, send, mut m) = setup();
    for r in &mut s.tables[0].requests {
        r.generation = u32::MAX;
    }
    assert_eq!(
        s.request_operation(caller(0), send, BASE, 8, Control::Begin, &mut m),
        (Status::Again, 0)
    );
    assert_eq!(m.accesses, 0);
}

#[test]
fn failed_begin_and_reply_input_leave_all_request_state_unchanged() {
    for offset in 0..MAX_BYTES {
        let (mut s, _, endpoint, send, mut m) = setup();
        let before = (s.tables, s.objects);
        m.read_fault = Some(offset);
        assert_eq!(
            s.request_operation(caller(0), send, BASE, 64, Control::Begin, &mut m),
            (Status::Fault, 0)
        );
        assert_eq!((s.tables, s.objects), before);
        m.read_fault = None;
        let request = begin(&mut s, send, &mut m);
        let token = receive(&mut s, endpoint, &mut m);
        m.read_fault = Some(offset);
        let before = (s.tables, s.objects);
        assert_eq!(
            s.message(caller(1), token, BASE, 64, Operation::Reply, &mut m),
            (Status::Fault, 0)
        );
        assert_eq!((s.tables, s.objects), before);
        assert_eq!(take(&mut s, request, &mut m), (Status::Again, 0));
    }
}

#[test]
fn forged_foreign_and_retired_request_handles_never_acquire_authority() {
    let (mut s, _, endpoint, send, mut m) = setup();
    let request = begin(&mut s, send, &mut m);
    let before = (s.tables, s.objects);
    let accesses = m.accesses;
    for (c, h) in [
        (caller(1), request),
        (caller(0), endpoint),
        (caller(0), request ^ (1 << 32)),
        (
            Caller {
                root: 0x999000,
                ..caller(0)
            },
            request,
        ),
        (caller(0), request | 1 << 24),
    ] {
        assert_eq!(
            s.request_operation(c, h, 0, 0, Control::Cancel, &mut m),
            (Status::Denied, 0)
        );
        assert_eq!(s.prepare_request_wait(c, h), Err(Status::Denied));
    }
    assert_eq!((s.tables, s.objects), before);
    assert_eq!(m.accesses, accesses);
    let token = receive(&mut s, endpoint, &mut m);
    s.detach(id(0)).unwrap();
    assert_eq!(
        s.message(caller(1), token, BASE, 8, Operation::Reply, &mut m),
        (Status::Denied, 0)
    );
}

#[test]
fn request_completion_between_arm_and_park_is_not_lost_and_wakes_once() {
    for cause in 0..3 {
        let (mut s, _, endpoint, send, mut m) = setup();
        let request = begin(&mut s, send, &mut m);
        let Admission::Pending(ticket) = s.prepare_request_wait(caller(0), request).unwrap() else {
            panic!()
        };
        let token = receive(&mut s, endpoint, &mut m);
        let expected = match cause {
            0 => {
                s.message(caller(1), token, BASE, 8, Operation::Reply, &mut m);
                Status::Ok
            }
            1 => {
                s.message(caller(1), token, 0, 0, Operation::Discard, &mut m);
                Status::Cancelled
            }
            _ => {
                s.detach(id(1)).unwrap();
                Status::Revoked
            }
        };
        let (mut scheduler, cpu) = running(0);
        charge(&mut scheduler, cpu, 0);
        s.park_wait(ticket, &mut scheduler, cpu).unwrap();
        assert_eq!(s.poll_wakes(&mut scheduler, cpu), Ok(1));
        assert_eq!(s.poll_wakes(&mut scheduler, cpu), Ok(0));
        scheduler.dispatch(cpu).unwrap();
        assert_eq!(
            s.complete_wait(ticket, &mut scheduler, cpu, |status| {
                assert_eq!(status, expected);
                Ok(())
            }),
            Ok(expected)
        );
        assert_eq!(take(&mut s, request, &mut m).0, expected);
        assert!(
            s.complete_wait(ticket, &mut scheduler, cpu, |_| panic!())
                .is_err()
        );
    }
}

#[test]
fn tracked_request_syscalls_have_strict_buffers_versions_and_reserved_fields() {
    use crate::user_entry::syscall::request as parse;
    for n in 10..=13 {
        let bytes = if n == 10 {
            64
        } else if n == 11 {
            96
        } else {
            0
        };
        let address = if bytes == 0 { 0 } else { BASE };
        assert!(parse(n, 1, 123, address, bytes, 0, 0).is_ok());
        assert_eq!(parse(n, 2, 123, address, bytes, 0, 0), Err(Status::Version));
        assert_eq!(
            parse(n, 1, 123, address, bytes, 1, 0),
            Err(Status::Arguments)
        );
        assert_eq!(
            parse(n, 1, 123, address, bytes, 0, 1),
            Err(Status::Arguments)
        );
        assert_eq!(
            parse(n, 1, 123, address, bytes + 1, 0, 0),
            Err(Status::Arguments)
        );
    }
}
