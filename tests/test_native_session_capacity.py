import unittest
from pathlib import Path
from unittest.mock import patch
from runtime import native_session_capacity as capacity, native_console_ipc as ipc, native_session as session
from tests.test_native_console_rpc import fixture as rpc_fixture
from tools.qualify_native_session_capacity import Interaction


def fixture(bad=False):
    markers = rpc_fixture()[:30]
    markers[29] = (markers[29].replace("PSESSION4 programs=4", "PSESSION5 programs=6")
        .replace(" task_image_pages=52", " root4=0x0000000000410000 root5=0x0000000000420000 task_image_pages=78")
        .replace("granted_handles=9", "granted_handles=13")
        .replace("transport=PRPC1 ", "transport=PRPC1 capacity=PCAP8 "))
    if bad:
        markers += [session.STOP.format(task=5,code=120)+" dispatches=6",
                    session.STOP.format(task=4,code=111)+" dispatches=7"]
    for d in range(64,513,64):
        if d == 320:
            markers += [session.STOP.format(task=2,code=0)+" dispatches=300",
                        session.STOP.format(task=3,code=0)+" dispatches=301"]
        dead = d > 256
        stops = 2*int(dead) + 2*int(bad)
        waits = d//4
        calls = min(d, 256)
        c4,c5,t4,t5 = (2,1,40,20) if bad else (d,d,10*d,11*d)
        markers.append(f"POOLEOS:SESSION RUN dispatches={d} calls0={d} calls1={d} ticks0={d*10} ticks1={d*11} waits={waits} wakes={waits-1} preemptions=0 yields={d-waits-stops} cr3_writes={d*2} calls2={calls} ticks2={calls*10} console_dead={int(dead)} allocated_pages={78-13*stops} calls3={calls} ticks3={calls*11} client_dead={int(dead)} calls4={c4} ticks4={t4} worker0_dead={int(bad)} calls5={c5} ticks5={t5} worker1_dead={int(bad)} cpl=3 kernel_root_restored=1 production=0")
    return markers


class NativeSessionCapacityTests(unittest.TestCase):
    def test_six_roots_progress_cleanup_and_bad_worker_are_distinct_from_useful_apps(self):
        for bad in (False, True):
            r = capacity.validate_markers(fixture(bad), bad_worker=bad)
            self.assertEqual((len(r["roots"]), r["task_image_pages"], r["released_pages"]), (6,78,52 if bad else 26))
            self.assertEqual((r["worker_startup_rejected"], r["extra_pair_survives"]), (bad,not bad))
            self.assertEqual(r["useful_application_count"], 0)
            self.assertFalse(r["user_lifecycle_authority"] or r["shell"] or r["iso_built"] or r["production_ready"])
            self.assertGreater(capacity.negative_controls(fixture(bad),bad_worker=bad), 70)
            with self.assertRaises(ValueError): ipc.validate_tracked_markers(fixture(bad))
            with self.assertRaises(ValueError): capacity.validate_markers(rpc_fixture())

    def test_six_root_identity_and_all_resource_bounds_cannot_be_relabelled(self):
        markers = fixture()
        for old,new in (("root5=0x0000000000420000","root5=0x0000000000410000"),
                ("root4=0x0000000000410000","root4=0x0000000000410001"),
                ("task_image_pages=78","task_image_pages=52"), ("capacity=PCAP8","capacity=PCAP4"),
                ("granted_handles=13","granted_handles=9"), ("programs=6","programs=4"),
                ("firmware_pages=1","firmware_pages=13")):
            self.assertTrue(any(old in m for m in markers), old)
            with self.assertRaises(ValueError): capacity.validate_markers([m.replace(old,new) for m in markers])

    def test_worker_bounds_missing_order_frozen_counters_and_overflow_reject(self):
        markers = fixture(True)
        for old,new in (("dispatches=7", "dispatches=15"), ("dispatches=6", "dispatches=7"),
                        ("reason=exit value=120", "reason=exit value=0"),
                        ("worker0_dead=1", "worker0_dead=0"),
                        ("calls5=1 ", "calls5=18446744073709551616 ")):
            with self.assertRaises(ValueError): capacity.validate_markers([m.replace(old,new) for m in markers],bad_worker=True)
        for task in (4,5):
            with self.assertRaises(ValueError):
                capacity.validate_markers([m for m in markers if f"STOP task={task} " not in m],bad_worker=True)
        changed = markers.copy()
        changed[-1] = changed[-1].replace("calls4=2 ", "calls4=3 ")
        with self.assertRaises(ValueError): capacity.validate_markers(changed,bad_worker=True)
        boundary = [m.replace("dispatches=7", "dispatches=14") for m in markers]
        capacity.validate_markers(boundary,bad_worker=True)

    def test_survivor_stall_early_console_close_or_false_memory_reclaim_reject(self):
        markers = fixture()
        for old,new in (("calls4=512 ","calls4=448 "), ("ticks5=5632 ","ticks5=4928 "),
                        ("allocated_pages=52 ","allocated_pages=26 "),
                        ("worker1_dead=0 ","worker1_dead=1 "), ("cr3_writes=1024 ","cr3_writes=1022 ")):
            changed = markers.copy()
            self.assertIn(old, changed[-1])
            changed[-1] = changed[-1].replace(old,new)
            with self.assertRaises(ValueError): capacity.validate_markers(changed)
        with self.assertRaises(ValueError): capacity.validate_markers(markers[:-1])

    def test_harness_cannot_complete_worker_control_without_both_retirements(self):
        class Socket:
            def recv(self,n): raise BlockingIOError
            def close(self): pass
        for task in (4,5):
            interaction = Interaction(b"x", True)
            interaction.sock = Socket()
            interaction.received.extend(b"x")
            interaction.sent = 1
            interaction.eot = True
            markers = [m for m in fixture(True) if f"STOP task={task} " not in m]
            self.assertFalse(interaction.poll(("\n".join(markers)+"\n").encode()))
            self.assertTrue(interaction.poll(("\n".join(fixture(True))+"\n").encode()))

    def test_capacity_dependencies_are_bound_before_git_tracks_new_files(self):
        root = Path(__file__).resolve().parents[1]
        code = (root/"native/kernel/src/capability_ipc.rs").read_text()
        self.assertIn("pub const TASKS: usize = crate::scheduler::MAX_TASKS;", code)
        self.assertIn("pub const ENDPOINTS: usize = TASKS;", code)
        self.assertIn("pub const CAPS: usize = 4;", code)
        self.assertIn("78 + 12", (root/"native/kernel/src/user_root_probe.rs").read_text())
        self.assertIn("grants[9..]", (root/"native/kernel/src/user_root_probe/peer_driver/session.rs").read_text())
        from tools.qualify_native_session_capacity import sources
        with patch("tools.qualify_native_user_entry.subprocess.check_output",return_value=""):
            bound = sources()
        for path in ("native/kernel/src/capability_ipc/tests/admission/capacity.rs",
                     "tests/test_native_session_capacity.py", "runtime/native_session_capacity.py"):
            self.assertIn(path, bound)


if __name__ == "__main__": unittest.main()
