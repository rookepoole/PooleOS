from __future__ import annotations

import json
from pathlib import Path

import unittest

from runtime import native_kernel_scheduler_smp_preempt as smp_preempt
from tools import pooleos_release_gate


ROOT = Path(__file__).resolve().parents[1]


def _raises(error: type[BaseException]):
    return unittest.TestCase().assertRaises(error)


def _skip(reason: str) -> None:
    raise unittest.SkipTest(reason)


def load_tests(loader, standard_tests, pattern):
    suite = unittest.TestSuite()
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            suite.addTest(unittest.FunctionTestCase(value, description=name))
    return suite


def _probe_lines() -> list[str]:
    return [
        "PKSCHED6:TOPOLOGY PASS cpus=4 aps=3 online_mask=0x0F queues=4 tasks=8 timer_lanes=4 frame_lanes=4 event_capacity=16 quantum=2",
        "PKSCHED6:EVENT PASS cpu1_order=1,2 cpu2_order=3 cancelled=1 wake=1 migration=1 pending=0 deterministic=1",
        "PKSCHED6:RESCHEDULE PASS acks=5 wake=1 migration=1 quantum=3 context_switches=3 ack_gated=1",
        "PKSCHED6:OWNERSHIP PASS frame_epochs=2,2,2,4 timer_ticks=2,2,2,4 trace=1:2>1;3:6>7>5 per_cpu=1",
        "PKSCHED6:ROLLBACK PASS offline_cpu=4 timeouts=1 rollbacks=1 stale_rejections=1 source_queue_restored=1 late_ack_rejected=1",
        "PKSCHED6:BOUNDS PASS quantum=2 event_latency=0 watchdog_age=2 maximum_bypass=2 starvation=0 lost_wake=0 duplicate_runnable=0",
        "PKSCHED6:CLEANUP PASS online_after=0x01 dead=8 teardown=8 frame_owners_revoked=3 timer_owners_revoked=3 pending_events=0 pending_remote=0 valid=1",
    ]


def test_contract_matches_schema_controls_and_claims() -> None:
    contract = smp_preempt.read_json(ROOT / smp_preempt.CONTRACT_RELATIVE)
    assert smp_preempt.contract_errors(contract, ROOT) == []
    assert len(contract["required_negative_controls"]) == 34
    assert contract["claims"] == smp_preempt.expected_claims()


def test_independent_oracle_has_exact_bounded_trace() -> None:
    assert smp_preempt.trace_oracle() == {
        "event_order": ((1, 2), (3,)),
        "frame_epochs": (2, 2, 2, 4),
        "timer_ticks": (2, 2, 2, 4),
        "trace": "1:2>1;3:6>7>5",
        "model_acks": 5,
        "live_ipis": 8,
        "quantum_preemptions": 3,
        "context_switches": 3,
        "maximum_event_latency": 0,
        "maximum_watchdog_age": 2,
        "maximum_bypass": 2,
    }


def test_probe_parser_accepts_only_exact_receipts() -> None:
    parsed = smp_preempt.parse_probe_output("\n".join(_probe_lines()) + "\n")
    assert parsed["receipt_count"] == 7
    assert parsed["rust_python_exact_agreement"] is True
    for index in range(7):
        hostile = _probe_lines()
        hostile.pop(index)
        with _raises(smp_preempt.KernelSchedulerSmpPreemptError):
            smp_preempt.parse_probe_output("\n".join(hostile) + "\n")


def test_probe_parser_rejects_order_ack_watchdog_and_cleanup_drift() -> None:
    for index, old, new in [
        (1, "cpu1_order=1,2", "cpu1_order=2,1"),
        (2, "acks=5", "acks=4"),
        (3, "frame_epochs=2,2,2,4", "frame_epochs=2,2,2,3"),
        (4, "rollbacks=1", "rollbacks=0"),
        (5, "watchdog_age=2", "watchdog_age=3"),
        (6, "frame_owners_revoked=3", "frame_owners_revoked=2"),
    ]:
        hostile = _probe_lines()
        hostile[index] = hostile[index].replace(old, new)
        with _raises(smp_preempt.KernelSchedulerSmpPreemptError):
            smp_preempt.parse_probe_output("\n".join(hostile) + "\n")


def test_live_serial_transcript_matches_independent_oracle_when_present() -> None:
    path = ROOT / "tmp/pksched6-debug-run-2/pooleos.serial.log"
    if not path.is_file():
        _skip("local QEMU transcript is not a repository input")
    markers = smp_preempt.extract_markers(path.read_bytes())
    summary = smp_preempt.validate_markers(markers)
    assert len(markers) == 38
    assert summary["reschedule"] == {
        "live_ipis": 8,
        "model_acks": 5,
        "quantum_preemptions": 3,
    }


def test_input_binding_rejects_escape_and_is_complete() -> None:
    inputs = smp_preempt.expected_inputs(ROOT)
    assert len(inputs["implementation"]) == len(smp_preempt.IMPLEMENTATION_INPUTS)
    with _raises(smp_preempt.KernelSchedulerSmpPreemptError):
        smp_preempt.file_binding(ROOT, "../outside")


def test_readiness_schema_rejects_promotion() -> None:
    schema = smp_preempt.read_json(ROOT / smp_preempt.READINESS_SCHEMA_RELATIVE)
    assert schema["properties"]["production_ready"] == {"const": False}
    assert schema["properties"]["production_promotion_allowed"] == {"const": False}
    contract = json.loads((ROOT / smp_preempt.CONTRACT_RELATIVE).read_text(encoding="utf-8"))
    assert contract["production_ready"] is False


def test_release_gate_accepts_only_the_bound_non_promoting_receipt() -> None:
    path = ROOT / smp_preempt.READINESS_RELATIVE
    if not path.is_file():
        _skip("readiness is generated by the qualifier")
    check = pooleos_release_gate.check_native_kernel_scheduler_smp_preempt_readiness(path)
    assert check["ok"], check["detail"]
