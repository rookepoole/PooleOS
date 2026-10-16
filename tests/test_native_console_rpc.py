import unittest
from pathlib import Path
from unittest.mock import patch
from runtime import native_console_ipc as ipc, native_session as session
from tests.test_native_console_ipc import fixture as legacy_fixture
from tools.qualify_native_console_ipc import Interaction


def fixture(bad=False):
    markers=legacy_fixture()[:30]
    markers[29]=markers[29].replace("PSESSION3","PSESSION4").replace("protocol=PCS1 ","protocol=PCS1 transport=PRPC1 ")
    markers[29]=markers[29].replace("console_bytes=3032","console_bytes=3096").replace("client_bytes=1813","client_bytes=1900")
    if bad:
        markers += [session.STOP.format(task=2,code=152)+" dispatches=3", session.STOP.format(task=3,code=163)+" dispatches=4"]
    for d in range(64,513,64):
        if d==320 and not bad:
            markers += [session.STOP.format(task=2,code=0)+" dispatches=257", session.STOP.format(task=3,code=0)+" dispatches=258"]
        dead=bad or d>256
        yields=d//3 if bad else min(d,256)//2
        waits=d-yields-2*int(dead)
        c2,t2=(32,100) if bad else ((4100,25700) if dead else (d*16,d*100))
        c3,t3=(4,40) if bad else ((4100,25700) if dead else (d*16,d*100))
        markers.append(f"POOLEOS:SESSION RUN dispatches={d} calls0={d} calls1={d} ticks0={d*10} ticks1={d*11} waits={waits} wakes={waits-1} preemptions=0 yields={yields} cr3_writes={d*2} calls2={c2} ticks2={t2} console_dead={int(dead)} allocated_pages={26 if dead else 52} calls3={c3} ticks3={t3} client_dead={int(dead)} cpl=3 kernel_root_restored=1 production=0")
    return markers


class NativeConsoleRpcTests(unittest.TestCase):
    def test_tracked_close_and_revocation_are_not_service_restart_or_iso(self):
        for bad in (False,True):
            result=ipc.validate_tracked_markers(fixture(bad),bad_peer=bad)
            self.assertEqual((result["client_exit"],result["console_reaped_pages"]),(163 if bad else 0,26))
            self.assertEqual(result["peer_death_termination"],bad)
            self.assertFalse(result["polling_peer_death_recovery"] or result["service_restart"] or result["iso_built"])
            self.assertGreater(ipc.negative_controls(fixture(bad),bad_peer=bad,tracked=True),60)
            with self.assertRaises(ValueError): ipc.validate_markers(fixture(bad),bad_peer=bad)
            with self.assertRaises(ValueError): ipc.validate_tracked_markers(legacy_fixture(bad),bad_peer=bad)

    def test_retirement_dispatch_bounds_are_exact_and_not_observation_timing(self):
        markers=fixture(True)
        self.assertEqual(ipc.validate_tracked_markers(markers,bad_peer=True)["stop_dispatches"],{"2":3,"3":4})
        at_limit=markers.copy();at_limit[31]=at_limit[31].replace("dispatches=4","dispatches=11")
        ipc.validate_tracked_markers(at_limit,bad_peer=True)
        for changed in ["dispatches=0","dispatches=3","dispatches=12","dispatches=65","dispatches=18446744073709551616",""]:
            bad=markers.copy();bad[31]=bad[31].replace("dispatches=4",changed).rstrip()
            with self.assertRaises(ValueError): ipc.validate_tracked_markers(bad,bad_peer=True)
        markers[30],markers[31]=markers[31],markers[30]
        with self.assertRaises(ValueError): ipc.validate_tracked_markers(markers,bad_peer=True)

    def test_missing_client_retirement_wrong_exit_or_live_polling_never_passes(self):
        markers=fixture(True)
        for old,new in (("value=163","value=0"),("value=152","value=0"),
            ("transport=PRPC1","transport=NONE"),("allocated_pages=26","allocated_pages=39"),
            ("client_dead=1","client_dead=0"),("authority_revoked=1","authority_revoked=0")):
            with self.assertRaises(ValueError): ipc.validate_tracked_markers([m.replace(old,new) for m in markers],bad_peer=True)
        with self.assertRaises(ValueError): ipc.validate_tracked_markers(markers[:31]+markers[32:],bad_peer=True)
        markers[-1]=markers[-1].replace("calls3=4","calls3=5")
        with self.assertRaises(ValueError): ipc.validate_tracked_markers(markers,bad_peer=True)

    def test_syscall_adapter_reuses_tracked_kernel_authority_and_binds_new_sources(self):
        root=Path(__file__).resolve().parents[1]
        rpc=(root/"native/userspace/src/console_ipc/rpc.rs").read_text()
        kernel=(root/"native/kernel/src/user_entry/syscall.rs").read_text()
        for text in ("(8, self.pending)","(10, self.endpoint)","(7, self.endpoint)","(11, self.pending)","(9, 0) if !self.server"):
            self.assertIn(text,rpc)
        self.assertIn("Revoked = 9",kernel)
        self.assertIn("10 | 11 | 14",kernel)
        self.assertIn("request::Operation::Take",kernel)
        self.assertNotIn("unsafe",rpc)
        self.assertNotIn("call(3, self.send",(root/"native/userspace/src/process.rs").read_text())
        self.assertIn("Error::Revoked) => process::exit(163)",(root/"native/userspace/src/bin/console_client.rs").read_text())
        from tools.qualify_native_user_entry import source_bindings
        with patch("tools.qualify_native_user_entry.subprocess.check_output",return_value=""):
            bound=source_bindings()
        for path in ("native/userspace/src/console_ipc/rpc.rs","native/userspace/src/console_ipc/rpc/tests.rs","tests/test_native_console_rpc.py"):
            self.assertIn(path,bound)

    def test_harness_requires_both_retirements_before_finishing_wrong_peer_guest(self):
        class Socket:
            def recv(self,n): raise BlockingIOError
            def close(self): pass
        interaction=Interaction(b"",True);interaction.sock=Socket()
        complete=fixture(True)
        self.assertTrue(interaction.poll(("\n".join(complete)+"\n").encode()))
        for removed in (30,31):
            partial=complete[:removed]+complete[removed+1:]
            self.assertFalse(interaction.poll(("\n".join(partial)+"\n").encode()))
        interaction.close()


if __name__=="__main__": unittest.main()
