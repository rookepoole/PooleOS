use super::*;
use task::job::Job;

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
    let mut job = Job::<2>::new(&parent, pid).unwrap();
    job.adopt(&child, cid).unwrap();
    assert_eq!(job.next_orphan(), None);
    assert_eq!(
        job.cancel_orphan(&mut child, cid, None),
        Err(task::Error::State)
    );
    parent.cancel_prepared(pid).unwrap();
    let ended = job.owner_stopped(&parent, pid).unwrap();
    assert_eq!(job.owner_stopped(&parent, pid), Ok(ended));
    parent.reclaim(pid, &mut p.manager, &mut p.memory).unwrap();
    assert_eq!(job.next_orphan(), Some(cid));
    assert!(job.adopt(&child, cid).is_err());
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
    let (child, _, cid) = at(c.owner, 4);
    let (mut unrelated, control, same_id) = at(other.owner, 4);
    let mut job = Job::<2>::new(&parent, pid).unwrap();
    job.adopt(&child, cid).unwrap();
    parent.cancel_prepared(pid).unwrap();
    job.owner_stopped(&parent, pid).unwrap();
    assert_eq!(
        job.cancel_orphan(&mut unrelated, same_id, None),
        Err(task::Error::Identity)
    );
    assert_eq!(unrelated.state(same_id), Ok(task::State::Prepared));
    assert_eq!(control.borrow().entries, 0);
    let wrong = TaskId::new(cid.slot, cid.generation + 1).unwrap();
    assert!(job.cancel_orphan(&mut unrelated, wrong, None).is_err());
    assert_eq!(job.child_count(), 1);
    assert!(job.owner_stopped(&unrelated, same_id).is_err());
}

#[test]
fn job_membership_and_parent_terminal_require_exact_prepared_and_settled_states() {
    let mut p = setup_at(false, 4096);
    let mut c = setup_at(false, 4224);
    let other = setup_at(false, 4352);
    let (mut parent, pc, pid) = at(p.owner, 3);
    let (mut child, _, cid) = at(c.owner, 4);
    let (other, _, oid) = at(other.owner, 5);
    assert!(Job::<0>::new(&parent, pid).is_err());
    let mut job = Job::<1>::new(&parent, pid).unwrap();
    assert!(job.adopt(&parent, pid).is_err());
    assert!(job.owner_stopped(&parent, pid).is_err());
    job.adopt(&child, cid).unwrap();
    assert!(job.adopt(&child, cid).is_err());
    assert_eq!(job.adopt(&other, oid), Err(task::Error::Occupied));
    let mut empty = Job::<1>::new(&parent, pid).unwrap();
    child.activate(cid, &c.manager, &mut c.memory).unwrap();
    assert!(empty.adopt(&child, cid).is_err());
    pc.borrow_mut().slice_terminal = true;
    let (mut scheduler, cpu) = running_scheduler(pid);
    parent.activate(pid, &p.manager, &mut p.memory).unwrap();
    parent.run_slice(pid).unwrap();
    assert!(job.owner_stopped(&parent, pid).is_err());
    assert!(!job.is_closing());
    parent.account_slice(pid, &mut scheduler, cpu).unwrap();
    job.owner_stopped(&parent, pid).unwrap();
}

#[test]
fn job_suspended_orphan_requires_settled_accounting_and_never_reenters() {
    let p = setup_at(false, 4096);
    let mut c = setup_at(false, 4224);
    let (mut parent, _, pid) = at(p.owner, 3);
    let (mut child, control, cid) = at(c.owner, 4);
    let mut job = Job::<2>::new(&parent, pid).unwrap();
    job.adopt(&child, cid).unwrap();
    parent.cancel_prepared(pid).unwrap();
    job.owner_stopped(&parent, pid).unwrap();
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
    let mut job = Job::<2>::new(&parent, pid).unwrap();
    job.adopt(&child, cid).unwrap();
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
    job.owner_stopped(&parent, pid).unwrap();
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
    let (parent, _, pid) = at(p.owner, 3);
    let (mut child, _, cid) = at(c.owner, 4);
    let mut job = Job::<2>::new(&parent, pid).unwrap();
    job.adopt(&child, cid).unwrap();
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
    assert!(job.adopt(&child, cid).is_err());
    job.adopt(&child, next_id).unwrap();
    assert_eq!(next_id.generation, cid.generation + 1);
    assert_eq!(job.child_count(), 1);
    assert!(!job.is_closing());
}

#[test]
fn job_drop_never_frees_an_owned_child() {
    let p = setup_at(false, 4096);
    let mut c = setup_at(false, 4224);
    let (parent, _, pid) = at(p.owner, 3);
    let (child, _, cid) = at(c.owner, 4);
    let mut job = Job::<2>::new(&parent, pid).unwrap();
    job.adopt(&child, cid).unwrap();
    drop(job);
    retained(&mut c.manager, &c.handles);
    assert_eq!(child.state(cid), Ok(task::State::Prepared));
}
