from __future__ import annotations
import json
import unittest
from pathlib import Path
from runtime import native_session as session
from tools import qualify_native_kernel_entry as entry

ROOT = Path(__file__).resolve().parents[1]


def fixture(bad=False):
    old = json.loads((ROOT / "tests/fixtures/cycle237-user-root-markers.json").read_bytes())
    prefix = old if isinstance(old, list) else old["markers"]
    # Synthetic current-layout prefix, not a replacement for fresh guest evidence.
    prefix = [m.replace("stack_pt=193", "stack_pt=209").replace("handoff_pt=230", "handoff_pt=246")
              .replace("FFFFFFFF800E5000", "FFFFFFFF800F5000")
              .replace("FFFFFFFF800E6000", "FFFFFFFF800F6000") for m in prefix]
    markers = prefix[:29] + [
        "POOLEOS:SESSION START contract=PSESSION1 programs=2 bootstrap=PSTART1 abi=PSABI1 init_bytes=1054 counter_bytes=1094 root0=0x0000000002000000 root1=0x0000000002100000 granted_handles=4 diagnostics=0 production=0"]
    if bad:
        return markers + [session.STOP.format(task=1, code=120), session.STOP.format(task=0, code=111), session.EMPTY]
    for d in range(64, 513, 64):
        markers.append(f"POOLEOS:SESSION RUN dispatches={d} calls0={d*2-1} calls1={d*2} ticks0={d*100} ticks1={d*100} waits={d} wakes={d-1} preemptions=0 yields=0 cr3_writes={d*2} cpl=3 kernel_root_restored=1 production=0")
    return markers


class NativeSessionTests(unittest.TestCase):
    def test_positive_observations_keep_execution_binding_and_iso_open(self):
        result = session.validate_markers(fixture())
        self.assertEqual(result["samples"][-1][0], 512)
        self.assertTrue(result["native_execution_requires_guest_binding"])
        self.assertFalse(result["production_ready"] or result["iso_built"])
        self.assertEqual(result["program_bytes"], [1054, 1094])

    def test_bad_startup_requires_user_rejection_dependent_retirement_and_empty_kernel(self):
        self.assertTrue(session.validate_markers(fixture(True), bad_startup=True)["malformed_startup_denied"])
        for index in (30, 31, 32):
            markers = fixture(True)
            markers[index] = markers[index].replace("=1", "=0", 1)
            with self.assertRaises(ValueError):
                session.validate_markers(markers, bad_startup=True)
        with self.assertRaises(ValueError):
            session.validate_markers(fixture(True))

    def test_hostile_omission_replay_and_each_numeric_field_reject(self):
        self.assertGreater(session.negative_controls(fixture()), 100)
        self.assertGreater(session.negative_controls(fixture(True), bad_startup=True), 40)

    def test_wrong_selector_and_diagnostic_tail_are_not_session_execution(self):
        for replacement in ("trap_scenario=0", "trap_scenario=22"):
            markers = fixture()
            markers[23] = markers[23].replace("trap_scenario=23", replacement)
            with self.assertRaises(ValueError):
                session.validate_markers(markers)
        with self.assertRaises(ValueError):
            session.validate_markers(fixture() + ["POOLEOS:KERNEL:USER-ROOT PASS"])

    def test_both_tasks_must_grow_and_roots_cannot_alias(self):
        for index, before, after in ((29, "0x0000000002100000", "0x0000000002000000"),
                                     (37, "calls0=1023", "calls0=1"),
                                     (37, "ticks1=51200", "ticks1=44800"),
                                     (37, "cr3_writes=1024", "cr3_writes=1023")):
            markers = fixture()
            self.assertIn(before, markers[index])
            markers[index] = markers[index].replace(before, after)
            with self.assertRaises(ValueError):
                session.validate_markers(markers)

    def test_extractor_keeps_complete_panic_records_and_drops_only_partial_tail(self):
        raw = b"noise\r\nPOOLEOS:SESSION RUN complete\nPOOLEOS:PANIC code=1\nPOOLEOS:SESSION RU"
        self.assertEqual(session.extract_markers(raw), ["POOLEOS:SESSION RUN complete", "POOLEOS:PANIC code=1"])
        with self.assertRaises(UnicodeDecodeError):
            session.extract_markers(b"\xff\n")

    def test_unreviewed_kernel_feature_sets_fail_before_compilation(self):
        for features in (("unknown",), ("development-session", "host-probe")):
            with self.assertRaises(entry.QualificationError):
                entry._build_product(Path("missing"), {}, Path("missing"), features=features)

    def test_session_adapter_uses_owned_grants_and_has_no_diagnostic_dispatch_limit(self):
        source = (ROOT / "native/kernel/src/user_root_probe/peer_driver/session.rs").read_text()
        self.assertLess(source.index("user_ipc::bootstrap"), source.index("slot.activate"))
        self.assertLess(source.index("let elapsed = checked!(p.slot.account_slice"), source.index("let slice = checked!(result)"))
        self.assertNotIn("for _ in 0..", source)
        self.assertNotIn("inject_", source)
        self.assertNotIn("Peer::new(", source)
        self.assertIn("space.cancel_wait(ticket, &mut scheduler, cpu)", source)
        self.assertIn("dead[dependent ^ 1] && !dead[dependent]", source)
        self.assertIn("matches!(dependent, 2 | 3)", source)
        timer = (ROOT / "native/kernel/src/user_root_probe/timer_driver.rs").read_text()
        self.assertLess(timer.index("hardware.apic_write(0x3e0, 3)"), timer.index("cache.lookup(key)"))
        self.assertIn("calibration: None", timer)
        self.assertIn('#[cfg(feature = "development-session")]\n    calibration:', timer)
        self.assertIn('#[cfg(not(feature = "development-session"))]\n        let cached: Option<u64> = None;', timer)
        self.assertIn("include_bytes!(env!(\"POOLEOS_INIT_CODE\"))", source)
        main = (ROOT / "native/kernel/src/user_root_probe.rs").read_text()
        self.assertLess(main.index("peer_driver::session::run"), main.index("let mut timer = checked!(38"))


if __name__ == "__main__":
    unittest.main()
