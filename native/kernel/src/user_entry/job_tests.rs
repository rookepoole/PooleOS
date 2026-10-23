use super::*;
use task::job::Job;

#[test]
fn exclusive_job_owner_cannot_create_a_second_job() {
    let p = setup_at(false, 4096);
    let (mut parent, _, pid) = at(p.owner, 3);
    let _job = Job::<2>::new(&mut parent, pid).unwrap();
    assert!(Job::<2>::new(&mut parent, pid).is_err());
}

#[test]
fn exclusive_job_child_cannot_be_enrolled_by_two_owners() {
    let p = setup_at(false, 4096);
    let q = setup_at(false, 4224);
    let c = setup_at(false, 4352);
    let (mut parent, _, pid) = at(p.owner, 2);
    let (mut other, _, oid) = at(q.owner, 3);
    let (mut child, _, cid) = at(c.owner, 4);
    let mut job = Job::<2>::new(&mut parent, pid).unwrap();
    let mut peer = Job::<2>::new(&mut other, oid).unwrap();
    job.adopt(&mut child, cid).unwrap();
    assert!(peer.adopt(&mut child, cid).is_err());
    assert_eq!((job.child_count(), peer.child_count()), (1, 0));
}

#[test]
fn exclusive_job_open_owner_cannot_be_reclaimed_before_closure() {
    let mut p = setup_at(false, 4096);
    let (mut parent, _, pid) = at(p.owner, 3);
    let _job = Job::<2>::new(&mut parent, pid).unwrap();
    parent.cancel_prepared(pid).unwrap();
    assert!(parent.reclaim(pid, &mut p.manager, &mut p.memory).is_err());
    retained(&mut p.manager, &p.handles);
}

pub(super) fn at(
    owner: CpuImage<Hardware>,
    index: u8,
) -> (Slot<Hardware, StopDriver>, Rc<RefCell<StopControl>>, TaskId) {
    let mut slot = Slot::new(index).unwrap();
    let c = Rc::new(RefCell::new(StopControl::default()));
    let id = slot
        .insert(owner, StopDriver(c.clone()))
        .unwrap_or_else(|_| panic!("prepared"));
    (slot, c, id)
}

#[test]
fn job_closing_survives_parent_cleanup_and_keeps_unused_prepared_children() {
    let mut p = setup_at(false, 4096);
    let mut c = setup_at(false, 4224);
    let (mut parent, _, pid) = at(p.owner, 3);
    let (mut child, control, cid) = at(c.owner, 4);
    let mut job = Job::<2>::new(&mut parent, pid).unwrap();
    job.adopt(&mut child, cid).unwrap();
    assert_eq!(job.next_orphan(), None);
    assert_eq!(
        job.cancel_orphan(&mut child, cid, None),
        Err(task::Error::State)
    );
    parent.cancel_prepared(pid).unwrap();
    let ended = job.owner_stopped(&mut parent, pid).unwrap();
    assert_eq!(job.owner_stopped(&mut parent, pid), Ok(ended));
    parent.reclaim(pid, &mut p.manager, &mut p.memory).unwrap();
    assert_eq!(job.next_orphan(), Some(cid));
    assert!(job.adopt(&mut child, cid).is_err());
    let out = job.cancel_orphan(&mut child, cid, None).unwrap();
    c.memory.fail_finish = true;
    assert!(
        job.reclaim_child(&mut child, cid, &mut c.manager, &mut c.memory)
            .is_err()
    );
    assert_eq!(job.child_count(), 1);
    assert_eq!(job.cancel_orphan(&mut child, cid, None), Ok(out));
    retained(&mut c.manager, &c.handles);
    c.memory.fail_finish = false;
    assert_eq!(
        job.reclaim_child(&mut child, cid, &mut c.manager, &mut c.memory),
        Ok(out)
    );
    assert_eq!(job.next_orphan(), None);
    assert!(job.is_closing());
    assert_eq!(job.child_count(), 0);
    assert_eq!(control.borrow().entries, 0);
    assert!(c.machine.borrow().writes.is_empty());
    assert_eq!(c.manager.summary().allocated_pages, 0);
}

#[test]
fn job_rejects_stale_identity_wrong_root_and_unrelated_slots_before_mutation() {
    let p = setup_at(false, 4096);
    let c = setup_at(false, 4224);
    let other = setup_at(false, 4352);
    let (mut parent, _, pid) = at(p.owner, 3);
    let (mut child, _, cid) = at(c.owner, 4);
    let (mut unrelated, control, same_id) = at(other.owner, 4);
    let mut job = Job::<2>::new(&mut parent, pid).unwrap();
    job.adopt(&mut child, cid).unwrap();
    parent.cancel_prepared(pid).unwrap();
    job.owner_stopped(&mut parent, pid).unwrap();
    assert_eq!(
        job.cancel_orphan(&mut unrelated, same_id, None),
        Err(task::Error::Identity)
    );
    assert_eq!(unrelated.state(same_id), Ok(task::State::Prepared));
    assert_eq!(control.borrow().entries, 0);
    let wrong = TaskId::new(cid.slot, cid.generation + 1).unwrap();
    assert!(job.cancel_orphan(&mut unrelated, wrong, None).is_err());
    assert_eq!(job.child_count(), 1);
    assert!(job.owner_stopped(&mut unrelated, same_id).is_err());
}

#[test]
fn job_membership_and_parent_terminal_require_exact_prepared_and_settled_states() {
    let mut p = setup_at(false, 4096);
    let mut c = setup_at(false, 4224);
    let other = setup_at(false, 4352);
    let (mut parent, pc, pid) = at(p.owner, 3);
    let (mut child, _, cid) = at(c.owner, 4);
    let (mut other, _, oid) = at(other.owner, 5);
    assert!(Job::<0>::new(&mut parent, pid).is_err());
    let mut job = Job::<1>::new(&mut parent, pid).unwrap();
    assert!(job.adopt(&mut parent, pid).is_err());
    assert!(job.owner_stopped(&mut parent, pid).is_err());
    job.adopt(&mut child, cid).unwrap();
    assert!(job.adopt(&mut child, cid).is_err());
    assert_eq!(job.adopt(&mut other, oid), Err(task::Error::Occupied));
    let mut empty = Job::<1>::new(&mut other, oid).unwrap();
    child.activate(cid, &c.manager, &mut c.memory).unwrap();
    assert!(empty.adopt(&mut child, cid).is_err());
    pc.borrow_mut().slice_terminal = true;
    let (mut scheduler, cpu) = running_scheduler(pid);
    parent.activate(pid, &p.manager, &mut p.memory).unwrap();
    parent.run_slice(pid).unwrap();
    assert!(job.owner_stopped(&mut parent, pid).is_err());
    assert!(!job.is_closing());
    parent.account_slice(pid, &mut scheduler, cpu).unwrap();
    job.owner_stopped(&mut parent, pid).unwrap();
}

#[test]
fn job_suspended_orphan_requires_settled_accounting_and_never_reenters() {
    let p = setup_at(false, 4096);
    let mut c = setup_at(false, 4224);
    let (mut parent, _, pid) = at(p.owner, 3);
    let (mut child, control, cid) = at(c.owner, 4);
    let mut job = Job::<2>::new(&mut parent, pid).unwrap();
    job.adopt(&mut child, cid).unwrap();
    parent.cancel_prepared(pid).unwrap();
    job.owner_stopped(&mut parent, pid).unwrap();
    let (mut scheduler, cpu) = running_scheduler(cid);
    child.activate(cid, &c.manager, &mut c.memory).unwrap();
    assert!(job.cancel_orphan(&mut child, cid, None).is_err());
    child.run_slice(cid).unwrap();
    assert!(job.cancel_orphan(&mut child, cid, None).is_err());
    child.account_slice(cid, &mut scheduler, cpu).unwrap();
    let out = job.cancel_orphan(&mut child, cid, None).unwrap();
    assert_eq!(out.reason, Reason::Cancelled);
    job.reclaim_child(&mut child, cid, &mut c.manager, &mut c.memory)
        .unwrap();
    assert_eq!(control.borrow().entries, 1);
    assert_eq!(job.child_count(), 0);
    assert_eq!(c.manager.summary().allocated_pages, 0);
}

#[test]
fn job_waiting_orphan_requires_exact_ticket_and_preserves_failed_revocation() {
    use crate::capability_ipc::{
        Caller, Space,
        wait::{Admission, Readiness},
    };
    let p = setup_at(false, 4096);
    let mut c = setup_at(false, 4224);
    let (mut parent, _, pid) = at(p.owner, 3);
    let (mut child, control, cid) = at(c.owner, 4);
    let mut job = Job::<2>::new(&mut parent, pid).unwrap();
    job.adopt(&mut child, cid).unwrap();
    let mut space = Space::new();
    space.attach(cid, c.image).unwrap();
    let h = space.create_endpoint(cid).unwrap();
    let Admission::Pending(ticket) = space
        .prepare_wait(Caller::new(cid, c.image), h, Readiness::Readable)
        .unwrap()
    else {
        panic!("pending")
    };
    control.borrow_mut().wait = Some(ticket);
    let (mut scheduler, cpu) = running_scheduler(cid);
    child.activate(cid, &c.manager, &mut c.memory).unwrap();
    child.run_slice(cid).unwrap();
    child.account_slice(cid, &mut scheduler, cpu).unwrap();
    space.park_wait(ticket, &mut scheduler, cpu).unwrap();
    parent.cancel_prepared(pid).unwrap();
    job.owner_stopped(&mut parent, pid).unwrap();
    assert!(job.cancel_orphan(&mut child, cid, None).is_err());
    let out = job.cancel_orphan(&mut child, cid, Some(ticket)).unwrap();
    control.borrow_mut().fail_revoke = true;
    assert!(
        job.reclaim_child(&mut child, cid, &mut c.manager, &mut c.memory)
            .is_err()
    );
    assert_eq!(job.next_orphan(), Some(cid));
    retained(&mut c.manager, &c.handles);
    control.borrow_mut().fail_revoke = false;
    assert_eq!(
        job.reclaim_child(&mut child, cid, &mut c.manager, &mut c.memory),
        Ok(out)
    );
    assert_eq!(control.borrow().completions, 0);
    assert_eq!(control.borrow().entries, 1);
}

#[test]
fn job_retirement_works_with_live_parent_and_readmits_only_after_reclamation() {
    let p = setup_at(false, 4096);
    let mut c = setup_at(false, 4224);
    let next = setup_at(false, 4352);
    let (mut parent, _, pid) = at(p.owner, 3);
    let (mut child, _, cid) = at(c.owner, 4);
    let mut job = Job::<2>::new(&mut parent, pid).unwrap();
    job.adopt(&mut child, cid).unwrap();
    assert!(
        job.reclaim_child(&mut child, cid, &mut c.manager, &mut c.memory)
            .is_err()
    );
    child.cancel_prepared(cid).unwrap();
    c.memory.fail_write = Some(c.memory.writes);
    assert!(
        job.reclaim_child(&mut child, cid, &mut c.manager, &mut c.memory)
            .is_err()
    );
    assert_eq!(job.child_count(), 1);
    c.memory.fail_write = None;
    job.reclaim_child(&mut child, cid, &mut c.manager, &mut c.memory)
        .unwrap();
    let next_id = child
        .insert(
            next.owner,
            StopDriver(Rc::new(RefCell::new(StopControl::default()))),
        )
        .unwrap_or_else(|_| panic!("reusable"));
    assert!(job.adopt(&mut child, cid).is_err());
    job.adopt(&mut child, next_id).unwrap();
    assert_eq!(next_id.generation, cid.generation + 1);
    assert_eq!(job.child_count(), 1);
    assert!(!job.is_closing());
}

#[test]
fn job_drop_never_frees_an_owned_child() {
    let p = setup_at(false, 4096);
    let mut c = setup_at(false, 4224);
    let (mut parent, _, pid) = at(p.owner, 3);
    let (mut child, _, cid) = at(c.owner, 4);
    let mut job = Job::<2>::new(&mut parent, pid).unwrap();
    job.adopt(&mut child, cid).unwrap();
    drop(job);
    assert!(Job::<2>::new(&mut parent, pid).is_err());
    assert!(child.abandon(cid, &mut c.manager, &mut c.memory).is_err());
    let q = setup_at(false, 4352);
    let (mut other, _, oid) = at(q.owner, 5);
    let mut other_job = Job::<2>::new(&mut other, oid).unwrap();
    assert!(other_job.adopt(&mut child, cid).is_err());
    retained(&mut c.manager, &c.handles);
    assert_eq!(child.state(cid), Ok(task::State::Prepared));
}

#[test]
fn exclusive_job_rejected_enrollment_leaves_both_claims_available() {
    let p = setup_at(false, 4096);
    let q = setup_at(false, 4224);
    let a = setup_at(false, 4352);
    let b = setup_at(false, 4480);
    let (mut parent, _, pid) = at(p.owner, 2);
    let (mut other, _, oid) = at(q.owner, 3);
    let (mut first, _, aid) = at(a.owner, 4);
    let (mut second, _, bid) = at(b.owner, 5);
    let stale = TaskId::new(pid.slot, pid.generation + 1).unwrap();
    assert!(Job::<1>::new(&mut parent, stale).is_err());
    assert!(Job::<0>::new(&mut parent, pid).is_err());
    assert!(Job::<{ crate::scheduler::MAX_TASKS + 1 }>::new(&mut parent, pid).is_err());
    let mut job = Job::<1>::new(&mut parent, pid).unwrap();
    let mut peer = Job::<1>::new(&mut other, oid).unwrap();
    assert!(
        job.adopt(
            &mut first,
            TaskId::new(aid.slot, aid.generation + 1).unwrap()
        )
        .is_err()
    );
    job.adopt(&mut first, aid).unwrap();
    assert_eq!(job.adopt(&mut second, bid), Err(task::Error::Occupied));
    peer.adopt(&mut second, bid).unwrap();
    assert_eq!((job.child_count(), peer.child_count()), (1, 1));
}

#[test]
fn exclusive_job_raw_cleanup_rejects_before_any_state_or_device_effect() {
    let mut p = setup_at(false, 4096);
    let mut c = setup_at(false, 4224);
    let (mut parent, pc, pid) = at(p.owner, 3);
    let (mut child, cc, cid) = at(c.owner, 4);
    let mut job = Job::<1>::new(&mut parent, pid).unwrap();
    job.adopt(&mut child, cid).unwrap();
    let pw = p.memory.writes;
    let cw = c.memory.writes;
    assert!(parent.abandon(pid, &mut p.manager, &mut p.memory).is_err());
    assert!(child.abandon(cid, &mut c.manager, &mut c.memory).is_err());
    assert_eq!(parent.state(pid), Ok(task::State::Prepared));
    assert_eq!(child.state(cid), Ok(task::State::Prepared));
    parent.cancel_prepared(pid).unwrap();
    child.cancel_prepared(cid).unwrap();
    assert!(parent.reap(pid, &mut p.manager, &mut p.memory).is_err());
    assert!(parent.reclaim(pid, &mut p.manager, &mut p.memory).is_err());
    assert!(child.reap(cid, &mut c.manager, &mut c.memory).is_err());
    assert!(child.reclaim(cid, &mut c.manager, &mut c.memory).is_err());
    assert_eq!((p.memory.writes, c.memory.writes), (pw, cw));
    assert_eq!((pc.borrow().revocations, cc.borrow().revocations), (0, 0));
    assert_eq!((pc.borrow().shutdowns, cc.borrow().shutdowns), (0, 0));
    assert!(p.machine.borrow().writes.is_empty());
    assert!(c.machine.borrow().writes.is_empty());
    retained(&mut p.manager, &p.handles);
    retained(&mut c.manager, &c.handles);
    job.owner_stopped(&mut parent, pid).unwrap();
    parent.reclaim(pid, &mut p.manager, &mut p.memory).unwrap();
    job.reclaim_child(&mut child, cid, &mut c.manager, &mut c.memory)
        .unwrap();
}

#[test]
fn exclusive_job_failure_keeps_claim_without_blocking_independent_job() {
    let p = setup_at(false, 4096);
    let q = setup_at(false, 4224);
    let mut a = setup_at(false, 4352);
    let mut b = setup_at(false, 4480);
    let (mut parent, _, pid) = at(p.owner, 2);
    let (mut other, _, oid) = at(q.owner, 3);
    let (mut first, ac, aid) = at(a.owner, 4);
    let (mut second, _, bid) = at(b.owner, 5);
    let mut job = Job::<1>::new(&mut parent, pid).unwrap();
    let mut peer = Job::<1>::new(&mut other, oid).unwrap();
    job.adopt(&mut first, aid).unwrap();
    peer.adopt(&mut second, bid).unwrap();
    first.cancel_prepared(aid).unwrap();
    second.cancel_prepared(bid).unwrap();
    ac.borrow_mut().fail_revoke = true;
    let writes = a.memory.writes;
    assert!(
        job.reclaim_child(&mut first, aid, &mut a.manager, &mut a.memory)
            .is_err()
    );
    assert!(
        peer.reclaim_child(&mut first, aid, &mut a.manager, &mut a.memory)
            .is_err()
    );
    assert_eq!(a.memory.writes, writes);
    ac.borrow_mut().fail_revoke = false;
    a.memory.fail_finish = true;
    assert!(
        job.reclaim_child(&mut first, aid, &mut a.manager, &mut a.memory)
            .is_err()
    );
    assert!(peer.adopt(&mut first, aid).is_err());
    peer.reclaim_child(&mut second, bid, &mut b.manager, &mut b.memory)
        .unwrap();
    assert_eq!((job.child_count(), peer.child_count()), (1, 0));
    retained(&mut a.manager, &a.handles);
    assert_eq!(b.manager.summary().allocated_pages, 0);
    a.memory.fail_finish = false;
    job.reclaim_child(&mut first, aid, &mut a.manager, &mut a.memory)
        .unwrap();
    assert_eq!(a.manager.summary().allocated_pages, 0);
}

#[test]
fn exclusive_job_generation_reuse_cannot_transfer_old_claims() {
    let mut p = setup_at(false, 4096);
    let mut c = setup_at(false, 4224);
    let next_parent = setup_at(false, 4352);
    let next_child = setup_at(false, 4480);
    let (mut parent, _, pid) = at(p.owner, 3);
    let (mut child, _, cid) = at(c.owner, 4);
    let mut old = Job::<1>::new(&mut parent, pid).unwrap();
    old.adopt(&mut child, cid).unwrap();
    parent.cancel_prepared(pid).unwrap();
    old.owner_stopped(&mut parent, pid).unwrap();
    parent.reclaim(pid, &mut p.manager, &mut p.memory).unwrap();
    let pid2 = parent
        .insert(
            next_parent.owner,
            StopDriver(Rc::new(RefCell::new(StopControl::default()))),
        )
        .unwrap_or_else(|_| panic!("new parent"));
    let mut new = Job::<1>::new(&mut parent, pid2).unwrap();
    assert!(new.adopt(&mut child, cid).is_err());
    assert!(old.owner_stopped(&mut parent, pid2).is_err());
    old.cancel_orphan(&mut child, cid, None).unwrap();
    old.reclaim_child(&mut child, cid, &mut c.manager, &mut c.memory)
        .unwrap();
    let cid2 = child
        .insert(
            next_child.owner,
            StopDriver(Rc::new(RefCell::new(StopControl::default()))),
        )
        .unwrap_or_else(|_| panic!("new child"));
    assert_eq!(
        (pid2.generation, cid2.generation),
        (pid.generation + 1, cid.generation + 1)
    );
    assert!(old.cancel_orphan(&mut child, cid2, None).is_err());
    assert!(new.adopt(&mut child, cid).is_err());
    new.adopt(&mut child, cid2).unwrap();
    assert_eq!((old.child_count(), new.child_count()), (0, 1));
}

#[test]
fn exclusive_job_nested_owner_requires_own_closure_before_parent_reclaims() {
    let p = setup_at(false, 4096);
    let mut c = setup_at(false, 4224);
    let mut g = setup_at(false, 4352);
    let (mut parent, _, pid) = at(p.owner, 2);
    let (mut child, cc, cid) = at(c.owner, 3);
    let (mut grandchild, _, gid) = at(g.owner, 4);
    let mut outer = Job::<1>::new(&mut parent, pid).unwrap();
    let mut inner = Job::<1>::new(&mut child, cid).unwrap();
    outer.adopt(&mut child, cid).unwrap();
    inner.adopt(&mut grandchild, gid).unwrap();
    child.cancel_prepared(cid).unwrap();
    let writes = c.memory.writes;
    assert!(
        outer
            .reclaim_child(&mut child, cid, &mut c.manager, &mut c.memory)
            .is_err()
    );
    assert_eq!(c.memory.writes, writes);
    assert_eq!(cc.borrow().revocations, 0);
    inner.owner_stopped(&mut child, cid).unwrap();
    outer
        .reclaim_child(&mut child, cid, &mut c.manager, &mut c.memory)
        .unwrap();
    inner.cancel_orphan(&mut grandchild, gid, None).unwrap();
    inner
        .reclaim_child(&mut grandchild, gid, &mut g.manager, &mut g.memory)
        .unwrap();
    assert_eq!((outer.child_count(), inner.child_count()), (0, 0));
}
