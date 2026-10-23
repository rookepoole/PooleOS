use super::*;
use job_tests::at;
use task::job::{
    Job,
    registry::{Registry, Work},
};

#[test]
fn registry_bounds_and_capacity_reject_before_claiming_owner() {
    assert!(Registry::<0, 2>::new().is_err());
    assert!(Registry::<2, 0>::new().is_err());
    assert!(Registry::<{ crate::scheduler::MAX_TASKS + 1 }, 2>::new().is_err());
    let p = setup_at(false, 4096);
    let q = setup_at(false, 4224);
    let (mut parent, _, pid) = at(p.owner, 2);
    let (mut other, _, oid) = at(q.owner, 3);
    let mut r = Registry::<1, 2>::new().unwrap();
    assert!(
        r.create(
            &mut parent,
            TaskId::new(pid.slot, pid.generation + 1).unwrap()
        )
        .is_err()
    );
    r.create(&mut parent, pid).unwrap();
    assert!(r.create(&mut parent, pid).is_err());
    assert!(r.create(&mut other, oid).is_err());
    assert_eq!(r.job_count(), 1);
    assert!(Job::<2>::new(&mut other, oid).is_ok());
}

#[test]
fn registry_rejects_multihop_cycles_without_mutating_claims() {
    let a = setup_at(false, 4096);
    let b = setup_at(false, 4224);
    let c = setup_at(false, 4352);
    let (mut a, _, aid) = at(a.owner, 2);
    let (mut b, _, bid) = at(b.owner, 3);
    let (mut c, _, cid) = at(c.owner, 4);
    let mut r = Registry::<3, 2>::new().unwrap();
    r.create(&mut a, aid).unwrap();
    r.create(&mut b, bid).unwrap();
    r.create(&mut c, cid).unwrap();
    r.owner(aid).unwrap().adopt(&mut b, bid).unwrap();
    r.owner(bid).unwrap().adopt(&mut c, cid).unwrap();
    assert!(r.owner(cid).unwrap().adopt(&mut a, aid).is_err());
    assert!(r.owner(cid).unwrap().adopt(&mut b, bid).is_err());
    assert!(r.owner(aid).unwrap().adopt(&mut a, aid).is_err());
    assert_eq!(r.owner(aid).unwrap().child_count(), 1);
    assert_eq!(r.owner(bid).unwrap().child_count(), 1);
    assert_eq!(r.owner(cid).unwrap().child_count(), 0);
    assert_eq!(r.next_orphan(), None);
    assert_eq!(a.state(aid), Ok(task::State::Prepared));
}

#[test]
fn registry_blocks_cross_registry_and_standalone_graph_escape() {
    let a = setup_at(false, 4096);
    let b = setup_at(false, 4224);
    let c = setup_at(false, 4352);
    let d = setup_at(false, 4480);
    let (mut a, _, aid) = at(a.owner, 2);
    let (mut b, _, bid) = at(b.owner, 3);
    let (mut c, _, cid) = at(c.owner, 4);
    let (mut d, _, did) = at(d.owner, 5);
    let mut r = Registry::<3, 2>::new().unwrap();
    let mut other = Registry::<2, 2>::new().unwrap();
    r.create(&mut a, aid).unwrap();
    other.create(&mut b, bid).unwrap();
    let mut standalone = Job::<2>::new(&mut d, did).unwrap();
    assert!(standalone.adopt(&mut a, aid).is_err());
    assert!(r.owner(aid).unwrap().adopt(&mut b, bid).is_err());
    assert!(r.owner(aid).unwrap().adopt(&mut d, did).is_err());
    r.owner(aid).unwrap().adopt(&mut c, cid).unwrap();
    assert!(Job::<2>::new(&mut c, cid).is_err());
    assert!(other.create(&mut c, cid).is_err());
    r.create(&mut c, cid).unwrap();
    assert!(r.owner(cid).unwrap().adopt(&mut a, aid).is_err());
    assert_eq!(r.job_count(), 2);
}

#[test]
fn registry_rejects_alias_slot_and_root_across_independent_jobs() {
    let p = setup_at(false, 4096);
    let q = setup_at(false, 4224);
    let a = setup_at(false, 4352);
    let alias = setup_at(false, 4480);
    let same_root = setup_at(false, 4352);
    let (mut p, _, pid) = at(p.owner, 1);
    let (mut q, _, qid) = at(q.owner, 2);
    let (mut a, _, aid) = at(a.owner, 3);
    let (mut alias, _, alias_id) = at(alias.owner, 3);
    let (mut same_root, _, root_id) = at(same_root.owner, 4);
    let mut r = Registry::<3, 2>::new().unwrap();
    r.create(&mut p, pid).unwrap();
    r.create(&mut q, qid).unwrap();
    r.owner(pid).unwrap().adopt(&mut a, aid).unwrap();
    assert!(r.owner(qid).unwrap().adopt(&mut alias, alias_id).is_err());
    assert!(
        r.owner(qid)
            .unwrap()
            .adopt(&mut same_root, root_id)
            .is_err()
    );
    assert!(r.create(&mut alias, alias_id).is_err());
    assert!(r.create(&mut same_root, root_id).is_err());
    assert!(Job::<2>::new(&mut alias, alias_id).is_ok());
    assert_eq!(r.owner(qid).unwrap().child_count(), 0);
}

#[test]
fn registry_round_robin_rotates_owners_and_children_despite_failed_cleanup() {
    let p = setup_at(false, 4096);
    let q = setup_at(false, 4224);
    let mut a = setup_at(false, 4352);
    let mut b = setup_at(false, 4480);
    let c = setup_at(false, 4608);
    let d = setup_at(false, 4736);
    let (mut p, _, pid) = at(p.owner, 0);
    let (mut q, _, qid) = at(q.owner, 1);
    let (mut sa, _, aid) = at(a.owner, 2);
    let (mut sb, _, bid) = at(b.owner, 3);
    let (mut sc, _, cid) = at(c.owner, 4);
    let (mut sd, _, did) = at(d.owner, 5);
    let mut r = Registry::<3, 2>::new().unwrap();
    r.create(&mut p, pid).unwrap();
    r.create(&mut q, qid).unwrap();
    r.owner(pid).unwrap().adopt(&mut sa, aid).unwrap();
    r.owner(pid).unwrap().adopt(&mut sc, cid).unwrap();
    r.owner(qid).unwrap().adopt(&mut sb, bid).unwrap();
    r.owner(qid).unwrap().adopt(&mut sd, did).unwrap();
    assert_eq!(r.next_orphan(), None);
    p.cancel_prepared(pid).unwrap();
    q.cancel_prepared(qid).unwrap();
    r.owner(pid).unwrap().owner_stopped(&mut p, pid).unwrap();
    r.owner(qid).unwrap().owner_stopped(&mut q, qid).unwrap();
    let expected = [
        Work {
            owner: pid,
            child: aid,
        },
        Work {
            owner: qid,
            child: bid,
        },
        Work {
            owner: pid,
            child: cid,
        },
        Work {
            owner: qid,
            child: did,
        },
    ];
    let writes = (a.memory.writes, b.memory.writes);
    for _ in 0..8 {
        for work in expected {
            assert_eq!(r.next_orphan(), Some(work));
        }
    }
    assert_eq!((a.memory.writes, b.memory.writes), writes);
    assert_eq!(sa.runtime(aid), Ok(task::Runtime::default()));
    assert_eq!(sa.cleanup_status(aid), Ok(None));
    assert_eq!(r.next_orphan(), Some(expected[0]));
    r.owner(pid)
        .unwrap()
        .cancel_orphan(&mut sa, aid, None)
        .unwrap();
    a.memory.fail_finish = true;
    assert!(
        r.owner(pid)
            .unwrap()
            .reclaim_child(&mut sa, aid, &mut a.manager, &mut a.memory)
            .is_err()
    );
    assert_eq!(r.next_orphan(), Some(expected[1]));
    r.owner(qid)
        .unwrap()
        .cancel_orphan(&mut sb, bid, None)
        .unwrap();
    r.owner(qid)
        .unwrap()
        .reclaim_child(&mut sb, bid, &mut b.manager, &mut b.memory)
        .unwrap();
    retained(&mut a.manager, &a.handles);
    assert_eq!(b.manager.summary().allocated_pages, 0);
    assert_eq!(r.owner(pid).unwrap().child_count(), 2);
    assert_eq!(r.owner(qid).unwrap().child_count(), 1);
    for expected in [cid, did, aid, did, cid, did] {
        assert_eq!(r.next_orphan().unwrap().child, expected);
    }
}

#[test]
fn registry_views_recover_records_but_dropped_registry_keeps_claims() {
    let p = setup_at(false, 4096);
    let mut c = setup_at(false, 4224);
    let (mut p, _, pid) = at(p.owner, 3);
    let (mut cslot, _, cid) = at(c.owner, 4);
    let mut r = Registry::<2, 2>::new().unwrap();
    r.create(&mut p, pid).unwrap();
    {
        let mut owner = r.owner(pid).unwrap();
        owner.adopt(&mut cslot, cid).unwrap();
    }
    assert_eq!(r.owner(pid).unwrap().child_count(), 1);
    assert!(r.retire(pid).is_err());
    p.cancel_prepared(pid).unwrap();
    r.owner(pid).unwrap().owner_stopped(&mut p, pid).unwrap();
    assert!(r.retire(pid).is_err());
    drop(r);
    assert!(
        Registry::<2, 2>::new()
            .unwrap()
            .create(&mut p, pid)
            .is_err()
    );
    assert!(Job::<2>::new(&mut cslot, cid).is_err());
    assert!(cslot.abandon(cid, &mut c.manager, &mut c.memory).is_err());
    retained(&mut c.manager, &c.handles);
}

#[test]
fn registry_retirement_requires_closed_drained_job_and_rejects_stale_generation() {
    let mut p = setup_at(false, 4096);
    let next = setup_at(false, 4224);
    let (mut parent, _, pid) = at(p.owner, 3);
    let mut r = Registry::<1, 1>::new().unwrap();
    r.create(&mut parent, pid).unwrap();
    assert!(r.retire(pid).is_err());
    parent.cancel_prepared(pid).unwrap();
    r.owner(pid)
        .unwrap()
        .owner_stopped(&mut parent, pid)
        .unwrap();
    parent.reclaim(pid, &mut p.manager, &mut p.memory).unwrap();
    let fresh = parent
        .insert(
            next.owner,
            StopDriver(Rc::new(RefCell::new(StopControl::default()))),
        )
        .unwrap_or_else(|_| panic!("new generation"));
    assert!(r.create(&mut parent, fresh).is_err());
    r.retire(pid).unwrap();
    assert!(r.owner(pid).is_err());
    r.create(&mut parent, fresh).unwrap();
    assert!(r.retire(pid).is_err());
    assert!(
        r.owner(fresh)
            .unwrap()
            .owner_stopped(&mut parent, pid)
            .is_err()
    );
    assert_eq!(r.job_count(), 1);
    assert_eq!(r.next_orphan(), None);
}

#[test]
fn registry_nested_obligations_survive_owner_reclamation() {
    let p = setup_at(false, 4096);
    let mut c = setup_at(false, 4224);
    let mut g = setup_at(false, 4352);
    let (mut p, _, pid) = at(p.owner, 2);
    let (mut cslot, _, cid) = at(c.owner, 3);
    let (mut gslot, _, gid) = at(g.owner, 4);
    let mut r = Registry::<3, 2>::new().unwrap();
    r.create(&mut p, pid).unwrap();
    r.owner(pid).unwrap().adopt(&mut cslot, cid).unwrap();
    r.create(&mut cslot, cid).unwrap();
    r.owner(cid).unwrap().adopt(&mut gslot, gid).unwrap();
    cslot.cancel_prepared(cid).unwrap();
    assert!(
        r.owner(pid)
            .unwrap()
            .reclaim_child(&mut cslot, cid, &mut c.manager, &mut c.memory)
            .is_err()
    );
    r.owner(cid)
        .unwrap()
        .owner_stopped(&mut cslot, cid)
        .unwrap();
    r.owner(pid)
        .unwrap()
        .reclaim_child(&mut cslot, cid, &mut c.manager, &mut c.memory)
        .unwrap();
    assert_eq!(
        r.next_orphan(),
        Some(Work {
            owner: cid,
            child: gid
        })
    );
    r.owner(cid)
        .unwrap()
        .cancel_orphan(&mut gslot, gid, None)
        .unwrap();
    r.owner(cid)
        .unwrap()
        .reclaim_child(&mut gslot, gid, &mut g.manager, &mut g.memory)
        .unwrap();
    r.retire(cid).unwrap();
    assert_eq!(r.job_count(), 1);
    assert_eq!(r.next_orphan(), None);
    assert_eq!(
        (
            c.manager.summary().allocated_pages,
            g.manager.summary().allocated_pages
        ),
        (0, 0)
    );
}
