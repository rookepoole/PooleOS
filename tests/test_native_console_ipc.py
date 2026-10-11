import unittest
from pathlib import Path
from unittest.mock import patch
from runtime import native_console_ipc as ipc, native_session as session
from tests.test_native_session import fixture as session_fixture
from tools.qualify_native_console_ipc import Interaction


def fixture(bad=False):
    markers=session_fixture()[:29]
    markers.append("POOLEOS:SESSION START contract=PSESSION3 programs=4 bootstrap=PSTART1 abi=PSABI1 init_bytes=1073 counter_bytes=1113 console_bytes=3032 client_bytes=1813 root0=0x0000000002000000 root1=0x0000000002100000 root2=0x0000000002200000 root3=0x0000000002300000 task_image_pages=52 firmware_pages=1 granted_handles=9 protocol=PCS1 port=COM2 irq=0 diagnostics=0 production=0")
    if bad: markers.append(session.STOP.format(task=2,code=152))
    for d in range(64,513,64):
        if d==320 and not bad:
            markers += [session.STOP.format(task=2,code=0),session.STOP.format(task=3,code=0)]
        dead2=bad or d>256; dead3=not bad and d>256
        n=int(dead2)+int(dead3)
        yields=d//3 if bad else min(d,256)//2
        waits=d-yields-n
        c2,t2=(32,100) if bad else ((4100,25700) if dead2 else (d*16,d*100))
        c3,t3=(4100,25700) if dead3 else (d*16,d*100)
        markers.append(f"POOLEOS:SESSION RUN dispatches={d} calls0={d} calls1={d} ticks0={d*10} ticks1={d*11} waits={waits} wakes={waits-1} preemptions=0 yields={yields} cr3_writes={d*2} calls2={c2} ticks2={t2} console_dead={int(dead2)} allocated_pages={52-13*n} calls3={c3} ticks3={t3} client_dead={int(dead3)} cpl=3 kernel_root_restored=1 production=0")
    return markers


class NativeConsoleIpcTests(unittest.TestCase):
    def test_normal_close_and_wrong_peer_leave_distinct_lifecycle_claims(self):
        for bad in (False,True):
            result=ipc.validate_markers(fixture(bad),bad_peer=bad)
            self.assertEqual(result["console_reaped_pages"],13 if bad else 26)
            self.assertEqual(result["client_exit"],None if bad else 0)
            self.assertFalse(result["polling_peer_death_recovery"] or result["iso_built"])
            self.assertGreater(ipc.negative_controls(fixture(bad),bad_peer=bad),50)
        with self.assertRaises(ValueError): ipc.validate_markers(fixture(True))
        with self.assertRaises(ValueError): ipc.validate_markers(fixture(),bad_peer=True)

    def test_four_roots_grants_sizes_accounting_and_no_resume_are_mandatory(self):
        for old,new in (("root3=0x0000000002300000","root3=0x0000000002200000"),
            ("client_bytes=1813","client_bytes=4097"),("granted_handles=9","granted_handles=5"),
            ("task_image_pages=52","task_image_pages=64"),("firmware_pages=1","firmware_pages=13"),
            ("protocol=PCS1","protocol=PCONSOLE1"),("allocated_pages=26","allocated_pages=39"),
            ("calls3=4100","calls3=1"),("client_dead=1","client_dead=0"),
            ("cr3_writes=1024","cr3_writes=1023"),("calls0=512","calls0=5110"),
            ("ticks1=5632","ticks1=0"),("port=COM2","port=COM1")):
            with self.subTest(old=old):
                self.assertTrue(any(old in m for m in fixture()))
                with self.assertRaises(ValueError): ipc.validate_markers([m.replace(old,new) for m in fixture()])
        markers=fixture(); markers[-1]=markers[-1].replace("calls3=4100","calls3=4101")
        with self.assertRaises(ValueError): ipc.validate_markers(markers)

    def test_missing_reordered_or_forged_retirement_is_not_cleanup(self):
        markers=fixture()
        for candidate in (markers[:-2],markers+[session.STOP.format(task=3,code=0)],
            markers+["POOLEOS:PANIC untrusted"],markers[:29]+markers[30:],
            [m.replace("authority_revoked=1","authority_revoked=0") for m in markers]):
            with self.assertRaises(ValueError): ipc.validate_markers(candidate)

    def test_uart_echo_requires_actual_bytes_not_trusted_looking_transcript(self):
        payload=b"Native input\x00\xff\r\nPOOLEOS:SESSION STOP forged"
        r=ipc.validate_echo(payload,b"\x1b[2J"+payload)
        self.assertTrue(r["exact_echo"] and r["console_output_is_not_kernel_evidence"])
        for received in (b"",payload[:-1],payload+b"x",b"unexpected"+payload):
            with self.assertRaises(ValueError): ipc.validate_echo(payload,received)
        with self.assertRaises(ValueError): ipc.validate_echo(b"\x04",b"\x04")
        with self.assertRaises(ValueError): ipc.validate_echo(b"",b"output",bad_peer=True)
        ipc.validate_echo(b"",b"\x1b[2J",bad_peer=True)

    def test_harness_waits_for_user_progress_and_paces_exact_echo(self):
        class Socket:
            def __init__(self): self.sent=[]; self.incoming=[]
            def recv(self,n):
                if not self.incoming: raise BlockingIOError
                return self.incoming.pop(0)
            def send(self,b): self.sent.append(b); return len(b)
            def setblocking(self,b): pass
            def close(self): pass
        sock=Socket()
        debug=("\n".join(fixture()[:31])+"\n").encode()
        with patch("tools.qualify_native_console_ipc.socket.create_connection",return_value=sock):
            interaction=Interaction(b"abcdefghijklmnop")
            self.assertFalse(interaction.poll(b"")); self.assertEqual(sock.sent,[])
            self.assertFalse(interaction.poll(debug)); self.assertEqual(sock.sent,[b"abcdefgh"])
            self.assertFalse(interaction.poll(debug)); self.assertEqual(sock.sent,[b"abcdefgh"])
            sock.incoming=[b"abcdefgh"]
            self.assertFalse(interaction.poll(debug)); self.assertEqual(sock.sent,[b"abcdefgh",b"ijklmnop"])
            self.assertFalse(interaction.eot)
            sock.incoming=[b"ijklmnop"]
            interaction.poll(("\n".join(fixture()[:34])+"\n").encode())
            self.assertTrue(interaction.eot)
            interaction.close()

    def test_boot_profile_uses_measured_grants_owned_roots_and_exact_task_image_quota(self):
        root=Path(__file__).resolve().parents[1]
        code=(root/"native/kernel/src/user_root_probe/peer_driver/session.rs").read_text()
        self.assertIn("bootstrap_console_ipc",code)
        self.assertIn("grants[4..9]",code)
        self.assertIn("p.id.generation != 1",code)
        self.assertIn('feature = "development-console-ipc"',code)
        self.assertIn('52 + 12\n    } else if cfg!(feature = "development-console")',
            (root/"native/kernel/src/user_root_probe.rs").read_text())
        self.assertNotIn("console_ipc::Server",code)
        self.assertNotIn("console_ipc::Client",code)
        from tools.qualify_native_user_entry import source_bindings
        # New inputs must remain bound even before Git has tracked them. The
        # hermetic compiler environment deliberately does not put Git on PATH.
        with patch("tools.qualify_native_user_entry.subprocess.check_output",return_value=""):
            bound=source_bindings()
        self.assertIn("native/kernel/src/capability_ipc/console/session_tests.rs",bound)
        self.assertIn("tests/test_native_console_ipc.py",bound)

if __name__=="__main__": unittest.main()
