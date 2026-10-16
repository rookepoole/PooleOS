import unittest
from pathlib import Path
from unittest.mock import patch
from runtime import native_console as console, native_session as session
from tests.test_native_session import fixture as session_fixture
from tools.qualify_native_console import Interaction


def fixture(bad=False):
    markers = session_fixture()[:29]
    markers += ["POOLEOS:SESSION START contract=PSESSION2 programs=3 bootstrap=PSTART1 abi=PSABI1 init_bytes=1073 counter_bytes=1113 console_bytes=1288 root0=0x0000000002000000 root1=0x0000000002100000 root2=0x0000000002200000 granted_handles=5 port=COM2 irq=0 diagnostics=0 production=0"]
    stop = session.STOP.format(task=2,code=131 if bad else 0)
    if bad: markers.append(stop)
    for d in range(64,513,64):
        dead = bad or d > 256
        if d == 320 and not bad: markers.append(stop)
        yields = 0 if bad else min(d,256)//4
        waits = d-yields-int(dead)
        c2 = 2 if bad else (4100 if dead else d*16)
        t2 = 100 if bad else (25700 if dead else d*100)
        markers.append(f"POOLEOS:SESSION RUN dispatches={d} calls0={d} calls1={d} ticks0={d*10} ticks1={d*11} waits={waits} wakes={waits-1} preemptions=0 yields={yields} cr3_writes={d*2} calls2={c2} ticks2={t2} console_dead={int(dead)} allocated_pages={26 if dead else 39} cpl=3 kernel_root_restored=1 production=0")
    return markers


class NativeConsoleTests(unittest.TestCase):
    def test_positive_and_denied_handle_have_independent_survivor_evidence(self):
        for bad in (False,True):
            r = console.validate_markers(fixture(bad),bad_handle=bad)
            self.assertEqual(r["console_exit"],131 if bad else 0)
            self.assertTrue(r["surviving_pair_verified"])
            self.assertFalse(r["iso_built"])
            self.assertGreater(console.negative_controls(fixture(bad),bad_handle=bad),50)

    def test_reap_roots_progress_authority_and_channel_claim_mutations_reject(self):
        mutations = [("root2=0x0000000002200000","root2=0x0000000002000000"),
            ("granted_handles=5","granted_handles=4"),("port=COM2","port=COM1"),
            ("irq=0","irq=1"),("allocated_pages=26","allocated_pages=39"),
            ("console_dead=1","console_dead=0"),("value=0 authority","value=133 authority"),
            ("calls2=4100","calls2=1"),("ticks0=5120","ticks0=0"),
            ("cr3_writes=1024","cr3_writes=1023")]
        for old,new in mutations:
            with self.subTest(old=old):
                self.assertTrue(any(old in m for m in fixture()))
                with self.assertRaises(ValueError):
                    console.validate_markers([m.replace(old,new) for m in fixture()])
        with self.assertRaises(ValueError): console.validate_markers(fixture(True))
        with self.assertRaises(ValueError): console.validate_markers(fixture(),bad_handle=True)
        with self.assertRaises(ValueError): console.validate_markers(fixture()[:-2])

    def test_console_marker_like_data_is_echo_bytes_not_diagnostic_evidence(self):
        payload=b"POOLEOS:PANIC untrusted\r\n\x00\xff"
        result=console.validate_echo(payload,console.BANNER+payload)
        self.assertTrue(result["console_output_is_not_kernel_evidence"])
        for received in (payload,console.BANNER,console.BANNER+payload+b"x",console.BANNER+payload[:-1]):
            with self.assertRaises(ValueError): console.validate_echo(payload,received)
        with self.assertRaises(ValueError): console.validate_markers(fixture()+[payload.decode("latin1")])
        console.validate_echo(b"",b"",bad_handle=True)
        with self.assertRaises(ValueError): console.validate_echo(b"",b"x",bad_handle=True)
        with self.assertRaises(ValueError): console.validate_echo(b"\x04",console.BANNER+b"\x04")

    def test_one_byte_port_authority_is_feature_gated_and_no_user_in_out_instructions(self):
        root=Path(__file__).resolve().parents[1]
        code=(root/"native/userspace/src/process.rs").read_text()
        self.assertIn('call(15, self.0',code)
        self.assertIn('call(16, self.0',code)
        self.assertNotIn('asm!("out',code)
        self.assertNotIn('asm!("in ',code)
        self.assertIn('development-console = ["development-session"]', (root/"native/kernel/Cargo.toml").read_text())

    def test_pre_session_controls_are_exact_bounded_preserved_and_never_arbitrary_text(self):
        prefix=b"\x1b[2J\x1b[01;01H\x1b[=3h"
        r=console.validate_echo(b"x",prefix+console.BANNER+b"x")
        self.assertEqual(r["control_prefix_hex"],prefix.hex())
        self.assertEqual(r["application_output_bytes"],len(console.BANNER)+1)
        console.validate_echo(b"",prefix,bad_handle=True)
        for raw in (b"firmware?"+console.BANNER+b"x",b"\x1b[evil"+console.BANNER+b"x",
                    b"\x1b[2J"*1025+console.BANNER+b"x"):
            with self.assertRaises(ValueError): console.validate_echo(b"x",raw)
        self.assertEqual(console.split_output(b"\x1b[01;",partial=True),(b"\x1b[01;",b""))
        with self.assertRaises(ValueError): console.split_output(b"\x1b[01;")

    def test_harness_paces_input_and_cannot_accept_banner_without_actual_echo(self):
        class Socket:
            def __init__(self): self.incoming=[console.BANNER]; self.sent=[]
            def recv(self,n):
                if not self.incoming: raise BlockingIOError
                return self.incoming.pop(0)
            def send(self,b): self.sent.append(b); return len(b)
            def setblocking(self,b): pass
            def close(self): pass
        sock=Socket()
        with patch("tools.qualify_native_console.socket.create_connection",return_value=sock):
            interaction=Interaction(b"abcdefghijklmnop")
            self.assertFalse(interaction.poll(b""))
            self.assertEqual(sock.sent,[b"abcdefgh"])
            self.assertFalse(interaction.poll(b""))
            self.assertEqual(sock.sent,[b"abcdefgh"])
            sock.incoming=[b"abcdefgh"]
            self.assertFalse(interaction.poll(b""))
            self.assertEqual(sock.sent,[b"abcdefgh",b"ijklmnop"])
            interaction.close()

    def test_console_option_mismatch_rejects_before_any_guest_or_file_effect(self):
        from tools.qualify_native_pooleboot import _execute_once
        for kwargs in ({"console_port":42}, {"console_poll":lambda _:True},
                {"console_port":True,"console_poll":lambda _:True,"pause_on_completion":True},
                {"console_port":70000,"console_poll":lambda _:True,"pause_on_completion":True},
                {"console_port":42,"console_poll":lambda _:True}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    _execute_once("bad",{}, {},Path(),Path(),Path(),1,**kwargs)

if __name__ == "__main__": unittest.main()
