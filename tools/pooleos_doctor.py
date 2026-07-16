#!/usr/bin/env python3
"""PooleOS scaffold and PooleGlyph baseline verifier."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime import pooleglyph_bridge_manifest  # noqa: E402
from runtime import pooleglyph_core_ir_boundary_receipt  # noqa: E402
from runtime import pooleglyph_core_ir_executable_audit  # noqa: E402
from runtime import pooleglyph_parser_kernel_promotion_receipt  # noqa: E402
from runtime import pooleglyph_source_anchor  # noqa: E402
from runtime import permission_capability_matrix  # noqa: E402
from runtime import boot_trap_bundle_manifest  # noqa: E402
from runtime import qemu_shared_folder_contract  # noqa: E402
from runtime import lab_manifest  # noqa: E402
from runtime import lab_guest_autostart  # noqa: E402
from runtime import boot_log  # noqa: E402
from runtime import qemu_boot_evidence  # noqa: E402
from runtime import qemu_captured_boot_preflight  # noqa: E402
from runtime import qemu_captured_boot_launch_bundle  # noqa: E402
from runtime import qemu_captured_boot_dry_run_checklist  # noqa: E402
from runtime import qemu_boot_marker_contract  # noqa: E402
from runtime import qemu_boot_marker_image_binding  # noqa: E402
from runtime import rootfs_content_manifest  # noqa: E402
from runtime import rootfs_extraction_handoff  # noqa: E402
from runtime import rootfs_extraction_receipt  # noqa: E402
from runtime import qemu_captured_boot_receipt  # noqa: E402
from runtime import qemu_captured_boot_readiness  # noqa: E402
from runtime import kernel_boot_handoff  # noqa: E402
from runtime import kernel_pgvm2_loader_output  # noqa: E402
from runtime import lab_kernel_transcript_export_receipt  # noqa: E402
from runtime import kernel_pgvm2_loader_evidence  # noqa: E402
from runtime import capability_trap_fuzz  # noqa: E402
from runtime import microkernel_isolation  # noqa: E402
from runtime import capability_traps  # noqa: E402
from runtime import pgb2_trap_encoding  # noqa: E402
from runtime import pgb2_trap_execution  # noqa: E402
from runtime import pgb2_trap_abi_boundary_receipt  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
WORK_ROOT = ROOT.parent


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


def print_result(result: CheckResult) -> None:
    status = "PASS" if result.ok else "FAIL"
    print(f"{status} {result.name}: {result.detail}")


def load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def check_required_files(paths: Iterable[Path]) -> list[CheckResult]:
    results: list[CheckResult] = []
    for path in paths:
        results.append(
            CheckResult(
                name=f"file:{path.relative_to(ROOT)}",
                ok=path.exists(),
                detail="exists" if path.exists() else "missing",
            )
        )
    return results


def check_native_architecture_plan() -> CheckResult:
    from tools import pooleos_release_gate

    check = pooleos_release_gate.check_native_architecture_plan()
    return CheckResult(
        name=check["name"],
        ok=check["ok"],
        detail=check["detail"],
    )


def check_native_architecture_baseline() -> CheckResult:
    from tools import pooleos_release_gate

    check = pooleos_release_gate.check_native_architecture_baseline()
    return CheckResult(
        name=check["name"],
        ok=check["ok"],
        detail=check["detail"],
    )


def check_native_v1_objectives_readiness() -> CheckResult:
    from tools import pooleos_release_gate

    check = pooleos_release_gate.check_native_v1_objectives_readiness()
    return CheckResult(
        name=check["name"],
        ok=check["ok"],
        detail=check["detail"],
    )


def check_adr_ratification_readiness() -> CheckResult:
    from tools import pooleos_release_gate

    check = pooleos_release_gate.check_adr_ratification_readiness()
    return CheckResult(
        name=check["name"],
        ok=check["ok"],
        detail=check["detail"],
    )


def check_n0_owner_decision_packet() -> CheckResult:
    from tools import pooleos_release_gate

    check = pooleos_release_gate.check_n0_owner_decision_packet()
    return CheckResult(
        name=check["name"],
        ok=check["ok"],
        detail=check["detail"],
    )


def check_n0_owner_response_receipt() -> CheckResult:
    from tools import pooleos_release_gate

    check = pooleos_release_gate.check_n0_owner_response_receipt()
    return CheckResult(
        name=check["name"],
        ok=check["ok"],
        detail=check["detail"],
    )


def check_native_toolchain_qualification() -> CheckResult:
    from tools import pooleos_release_gate

    check = pooleos_release_gate.check_native_toolchain_qualification()
    return CheckResult(
        name=check["name"],
        ok=check["ok"],
        detail=check["detail"],
    )


def check_hardware_target_readiness() -> CheckResult:
    from tools import pooleos_release_gate

    check = pooleos_release_gate.check_hardware_target_readiness()
    return CheckResult(
        name=check["name"],
        ok=check["ok"],
        detail=check["detail"],
    )


def check_native_tier0_readiness() -> CheckResult:
    from tools import pooleos_release_gate

    check = pooleos_release_gate.check_native_tier0_readiness()
    return CheckResult(
        name=check["name"],
        ok=check["ok"],
        detail=check["detail"],
    )


def check_native_model_readiness() -> CheckResult:
    from tools import pooleos_release_gate

    check = pooleos_release_gate.check_native_model_readiness()
    return CheckResult(
        name=check["name"],
        ok=check["ok"],
        detail=check["detail"],
    )


def check_publication_boundary() -> CheckResult:
    from tools import pooleos_release_gate

    check = pooleos_release_gate.check_publication_boundary()
    return CheckResult(
        name=check["name"],
        ok=check["ok"],
        detail=check["detail"],
    )


def check_claim_schema() -> list[CheckResult]:
    schema_path = ROOT / "specs" / "claim-lanes.schema.json"
    schema = load_json(schema_path)
    results = [CheckResult("claim_schema:json", True, "parsed")]

    if not isinstance(schema, dict):
        return [CheckResult("claim_schema:shape", False, "schema root is not an object")]

    required = schema.get("required", [])
    properties = schema.get("properties", {})
    required_fields = {
        "id",
        "title",
        "owner",
        "claim_lane",
        "evidence_kind",
        "rule",
        "model_tag",
        "source_hash",
        "limitations",
        "created_utc",
    }
    missing = sorted(required_fields.difference(required))
    results.append(
        CheckResult(
            "claim_schema:required_fields",
            not missing,
            "required fields present" if not missing else f"missing {missing}",
        )
    )

    lane_enum = properties.get("claim_lane", {}).get("enum", [])
    expected_lanes = {"theorem", "verifier", "benchmark", "atlas", "bridge_open"}
    missing_lanes = sorted(expected_lanes.difference(lane_enum))
    results.append(
        CheckResult(
            "claim_schema:lanes",
            not missing_lanes,
            "all lanes present" if not missing_lanes else f"missing {missing_lanes}",
        )
    )
    return results


def validate_claim_record(path: Path, schema: dict) -> CheckResult:
    try:
        record = load_json(path)
    except Exception as exc:  # pragma: no cover - diagnostic path
        return CheckResult(f"claim_record:{path.name}", False, f"json parse failed: {exc}")

    if not isinstance(record, dict):
        return CheckResult(f"claim_record:{path.name}", False, "record root is not an object")

    missing = sorted(set(schema["required"]).difference(record))
    if missing:
        return CheckResult(f"claim_record:{path.name}", False, f"missing {missing}")

    properties = schema.get("properties", {})
    for field in ("claim_lane", "evidence_kind", "model_tag"):
        allowed = set(properties.get(field, {}).get("enum", []))
        if allowed and record.get(field) not in allowed:
            return CheckResult(f"claim_record:{path.name}", False, f"bad {field}: {record.get(field)!r}")

    if len(str(record.get("limitations", ""))) < 10:
        return CheckResult(f"claim_record:{path.name}", False, "limitations too short")

    return CheckResult(f"claim_record:{path.name}", True, "valid minimal record")


def check_claim_examples() -> list[CheckResult]:
    schema = load_json(ROOT / "specs" / "claim-lanes.schema.json")
    if not isinstance(schema, dict):
        return [CheckResult("claim_examples", False, "schema root is not an object")]

    examples = sorted((ROOT / "tests" / "claim_lane_examples").glob("*.json"))
    results = [CheckResult("claim_examples:count", bool(examples), f"{len(examples)} example(s)")]
    results.extend(validate_claim_record(path, schema) for path in examples)
    return results


def check_trace_schema() -> list[CheckResult]:
    schema_path = ROOT / "specs" / "channel-trace.schema.json"
    schema = load_json(schema_path)
    if not isinstance(schema, dict):
        return [CheckResult("trace_schema:shape", False, "schema root is not an object")]
    required = {"schema_version", "artifact_kind", "rule", "claim", "summary", "events"}
    missing = sorted(required.difference(schema.get("required", [])))
    return [
        CheckResult(
            "trace_schema:required_fields",
            not missing,
            "required fields present" if not missing else f"missing {missing}",
        )
    ]


def check_generated_trace_validation() -> CheckResult:
    from runtime import channel_telemetry as ct
    from runtime import channel_trace as tr

    class MiniLattice:
        def __init__(self) -> None:
            self.body = {
                (-1, 0, 0),
                (1, 0, 0),
                (0, -1, 0),
                (0, 1, 0),
                (0, 0, -1),
                (0, 0, 1),
            }

        def state(self, coord):
            return "body" if coord in self.body else "void"

        def support_count(self, coord):
            return sum(
                (coord[0] + dx, coord[1] + dy, coord[2] + dz) in self.body
                for dx in (-1, 0, 1)
                for dy in (-1, 0, 1)
                for dz in (-1, 0, 1)
                if not (dx == 0 and dy == 0 and dz == 0)
            )

        def evaluation_region(self, margin=None):
            return {(0, 0, 0)}

    summary = ct.measure_channels(MiniLattice())
    claim = tr.make_claim_record(
        claim_id="TRACE-DOCTOR-001",
        title="Doctor generated channel trace",
        source_descriptor="doctor:six-support-center",
        limitations="Doctor-generated validation artifact only.",
    )
    artifact = tr.make_channel_trace(summary, claim=claim)
    schema = load_json(ROOT / "specs" / "channel-trace.schema.json")
    if not isinstance(schema, dict):
        return CheckResult("trace_artifact:validation", False, "schema root is not an object")
    errors = validate_json(artifact, schema)
    return CheckResult(
        "trace_artifact:validation",
        not errors,
        "generated trace validates" if not errors else "; ".join(f"{e.path}: {e.message}" for e in errors[:5]),
    )


def check_pdc_math_artifacts() -> list[CheckResult]:
    from runtime import pdc_source_intake

    paths = {
        "source_intake": (ROOT / "runs" / "pdc_source_intake.json", ROOT / "specs" / "pdc-source-intake.schema.json"),
        "math_contract": (ROOT / "runs" / "pdc_math_contract.json", ROOT / "specs" / "pdc-math-contract.schema.json"),
        "golden_vectors": (ROOT / "runs" / "pdc_golden_vectors.json", ROOT / "specs" / "pdc-golden-vectors.schema.json"),
        "verifier_intake": (
            ROOT / "runs" / "pdc_verifier_intake.json",
            ROOT / "specs" / "pdc-verifier-intake.schema.json",
        ),
        "verifier_reproduction": (
            ROOT / "runs" / "pdc_verifier_reproduction.json",
            ROOT / "specs" / "pdc-verifier-reproduction.schema.json",
        ),
        "representation_contract": (
            ROOT / "runs" / "pdc_representation_contract.json",
            ROOT / "specs" / "pdc-representation-contract.schema.json",
        ),
        "representation_receipt": (
            ROOT / "runs" / "pdc_representation_receipt.json",
            ROOT / "specs" / "pdc-representation-receipt.schema.json",
        ),
        "golden_metamorphic_corpus": (
            ROOT / "runs" / "pdc_golden_metamorphic_corpus.json",
            ROOT / "specs" / "pdc-golden-metamorphic-corpus.schema.json",
        ),
        "golden_metamorphic_receipt": (
            ROOT / "runs" / "pdc_golden_metamorphic_receipt.json",
            ROOT / "specs" / "pdc-golden-metamorphic-receipt.schema.json",
        ),
        "qp_contract": (
            ROOT / "runs" / "pdc_qp_contract.json",
            ROOT / "specs" / "pdc-qp-contract.schema.json",
        ),
        "qp_receipt": (
            ROOT / "runs" / "pdc_qp_receipt.json",
            ROOT / "specs" / "pdc-qp-receipt.schema.json",
        ),
        "qp_stability_contract": (
            ROOT / "runs" / "pdc_qp_stability_contract.json",
            ROOT / "specs" / "pdc-qp-stability-contract.schema.json",
        ),
        "qp_stability_receipt": (
            ROOT / "runs" / "pdc_qp_stability_receipt.json",
            ROOT / "specs" / "pdc-qp-stability-receipt.schema.json",
        ),
    }
    loaded: dict[str, dict] = {}
    results: list[CheckResult] = []
    for name, (artifact_path, schema_path) in paths.items():
        try:
            artifact = load_json(artifact_path)
            schema = load_json(schema_path)
            errors = validate_json(artifact, schema)
        except Exception as exc:  # pragma: no cover - doctor diagnostic path
            results.append(CheckResult(f"pdc:{name}", False, f"load/validation failed: {exc}"))
            continue
        loaded[name] = artifact
        results.append(
            CheckResult(
                f"pdc:{name}",
                not errors,
                "schema-valid" if not errors else "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
            )
        )

    intake = loaded.get("source_intake")
    if intake is not None:
        copy_failures = []
        for source in intake["designated_sources"]:
            stored = ROOT / source["stored_path"]
            if not stored.is_file() or pdc_source_intake.sha256_file(stored) != source["sha256"]:
                copy_failures.append(source["id"])
        summary = intake["summary"]
        results.append(
            CheckResult(
                "pdc:source_copies",
                not copy_failures,
                (
                    f"locked={summary['locked_source_count']}; verified={summary['verified_copy_count']}; "
                    f"raw_indexed={summary['raw_candidate_count']}; raw_imported={summary['raw_imported_count']}"
                    if not copy_failures
                    else f"bad copies={copy_failures}"
                ),
            )
        )

    contract = loaded.get("math_contract")
    if intake is not None and contract is not None:
        expected = pdc_source_intake.sha256_file(paths["source_intake"][0])
        actual = contract["source_binding"]["artifact_sha256"]
        results.append(
            CheckResult(
                "pdc:contract_source_binding",
                actual == expected,
                f"contract={contract['contract_version']}; source_bound={actual == expected}",
            )
        )

    vectors = loaded.get("golden_vectors")
    if contract is not None and vectors is not None:
        expected = pdc_source_intake.sha256_file(paths["math_contract"][0])
        actual = vectors["math_contract_binding"]["artifact_sha256"]
        summary = vectors["summary"]
        bound = actual == expected
        healthy = bound and summary["failed_count"] == 0 and summary["case_count"] == summary["passed_count"]
        results.append(
            CheckResult(
                "pdc:golden_vector_binding",
                healthy,
                (
                    f"bound={bound}; cases={summary['passed_count']}/{summary['case_count']}; "
                    f"matrix_scalar={summary['matrix_scalar_agreement_case_count']}"
                ),
            )
        )

    verifier_intake = loaded.get("verifier_intake")
    if intake is not None and contract is not None and verifier_intake is not None:
        bindings = verifier_intake["bindings"]
        source_bound = bindings["source_intake_sha256"] == pdc_source_intake.sha256_file(paths["source_intake"][0])
        contract_bound = bindings["math_contract_sha256"] == pdc_source_intake.sha256_file(paths["math_contract"][0])
        copy_failures = []
        for source in verifier_intake["selected_sources"]:
            stored = ROOT / source["stored_path"]
            if not stored.is_file() or pdc_source_intake.sha256_file(stored) != source["sha256"]:
                copy_failures.append(source["id"])
        summary = verifier_intake["summary"]
        healthy = (
            source_bound
            and contract_bound
            and not copy_failures
            and summary["verified_copy_count"] == summary["selected_source_count"] == 4
            and summary["verified_manifest_entry_count"] == summary["manifest_entry_count"] == 46
            and summary["failed_check_count"] == 0
        )
        results.append(
            CheckResult(
                "pdc:verifier_intake_bindings",
                healthy,
                (
                    f"source_bound={source_bound}; contract_bound={contract_bound}; "
                    f"sources={summary['verified_copy_count']}/{summary['selected_source_count']}; "
                    f"manifest_entries={summary['verified_manifest_entry_count']}/{summary['manifest_entry_count']}; "
                    f"bad_copies={len(copy_failures)}"
                ),
            )
        )

    reproduction = loaded.get("verifier_reproduction")
    if verifier_intake is not None and contract is not None and reproduction is not None:
        bindings = reproduction["bindings"]
        intake_bound = bindings["verifier_intake_sha256"] == pdc_source_intake.sha256_file(paths["verifier_intake"][0])
        contract_bound = bindings["math_contract_sha256"] == pdc_source_intake.sha256_file(paths["math_contract"][0])
        source_set_bound = bindings["selected_source_set_sha256"] == verifier_intake["digests"]["selected_source_set_sha256"]
        output_failures = []
        for execution in reproduction["source_executions"]:
            for output in execution["required_outputs"]:
                preserved = ROOT / output["preserved_path"]
                if not preserved.is_file() or pdc_source_intake.sha256_file(preserved) != output["sha256"]:
                    output_failures.append(output["id"])
        summary = reproduction["summary"]
        healthy = (
            intake_bound
            and contract_bound
            and source_set_bound
            and not output_failures
            and summary["independent_case_count"] == summary["source_execution_case_count"] == 4324
            and summary["canonical_lf_match_file_count"] == summary["source_output_file_count"] == 6
            and summary["mismatch_count"] == summary["failed_check_count"] == 0
        )
        results.append(
            CheckResult(
                "pdc:verifier_reproduction_bindings",
                healthy,
                (
                    f"intake_bound={intake_bound}; contract_bound={contract_bound}; source_set_bound={source_set_bound}; "
                    f"cases={summary['independent_case_count']}; canonical_lf={summary['canonical_lf_match_file_count']}/6; "
                    f"mismatches={summary['mismatch_count']}; bad_outputs={len(output_failures)}"
                ),
            )
        )

    representation_contract = loaded.get("representation_contract")
    if contract is not None and vectors is not None and reproduction is not None and representation_contract is not None:
        bindings = representation_contract["bindings"]
        implementation_bound = bindings["reference_implementation_sha256"] == pdc_source_intake.sha256_file(
            ROOT / bindings["reference_implementation_path"]
        )
        math_bound = bindings["math_contract_sha256"] == pdc_source_intake.sha256_file(paths["math_contract"][0])
        golden_bound = bindings["golden_vectors_sha256"] == pdc_source_intake.sha256_file(paths["golden_vectors"][0])
        verifier_bound = bindings["verifier_reproduction_sha256"] == pdc_source_intake.sha256_file(
            paths["verifier_reproduction"][0]
        )
        summary = representation_contract["summary"]
        healthy = (
            implementation_bound
            and math_bound
            and golden_bound
            and verifier_bound
            and summary["representation_count"] == 5
            and summary["conversion_path_count"] == 10
            and summary["failure_mode_count"] == 16
        )
        results.append(
            CheckResult(
                "pdc:representation_contract_bindings",
                healthy,
                (
                    f"implementation_bound={implementation_bound}; math_bound={math_bound}; "
                    f"golden_bound={golden_bound}; verifier_bound={verifier_bound}; "
                    f"representations={summary['representation_count']}; conversions={summary['conversion_path_count']}; "
                    f"failures={summary['failure_mode_count']}"
                ),
            )
        )

    representation_receipt = loaded.get("representation_receipt")
    if representation_contract is not None and representation_receipt is not None:
        bindings = representation_receipt["bindings"]
        implementation_bound = bindings["reference_implementation_sha256"] == pdc_source_intake.sha256_file(
            ROOT / bindings["reference_implementation_path"]
        )
        contract_bound = bindings["representation_contract_sha256"] == pdc_source_intake.sha256_file(
            paths["representation_contract"][0]
        )
        math_bound = bindings["math_contract_sha256"] == pdc_source_intake.sha256_file(paths["math_contract"][0])
        golden_bound = bindings["golden_vectors_sha256"] == pdc_source_intake.sha256_file(paths["golden_vectors"][0])
        verifier_bound = bindings["verifier_reproduction_sha256"] == pdc_source_intake.sha256_file(
            paths["verifier_reproduction"][0]
        )
        summary = representation_receipt["summary"]
        healthy = (
            implementation_bound
            and contract_bound
            and math_bound
            and golden_bound
            and verifier_bound
            and summary["differential_case_count"] == summary["pdc_result_match_count"] == 3109
            and summary["round_trip_count"] == 12436
            and summary["failed_negative_check_count"] == summary["mismatch_count"] == 0
        )
        results.append(
            CheckResult(
                "pdc:representation_receipt_bindings",
                healthy,
                (
                    f"implementation_bound={implementation_bound}; contract_bound={contract_bound}; "
                    f"math_bound={math_bound}; golden_bound={golden_bound}; "
                    f"verifier_bound={verifier_bound}; cases={summary['differential_case_count']}; "
                    f"round_trips={summary['round_trip_count']}; negative={summary['negative_check_count']}; "
                    f"mismatches={summary['mismatch_count']}"
                ),
            )
        )

    golden_metamorphic_corpus = loaded.get("golden_metamorphic_corpus")
    if (
        contract is not None
        and vectors is not None
        and representation_contract is not None
        and representation_receipt is not None
        and golden_metamorphic_corpus is not None
    ):
        bindings = golden_metamorphic_corpus["bindings"]
        implementation_path = ROOT / bindings["reference_implementation_path"]
        implementation_bound = implementation_path.is_file() and bindings[
            "reference_implementation_sha256"
        ] == pdc_source_intake.sha256_file(implementation_path)
        math_bound = bindings["math_contract_sha256"] == pdc_source_intake.sha256_file(paths["math_contract"][0])
        predecessor_bound = bindings["predecessor_golden_sha256"] == pdc_source_intake.sha256_file(
            paths["golden_vectors"][0]
        )
        representation_bound = bindings["representation_contract_sha256"] == pdc_source_intake.sha256_file(
            paths["representation_contract"][0]
        )
        receipt_bound = bindings["representation_receipt_sha256"] == pdc_source_intake.sha256_file(
            paths["representation_receipt"][0]
        )
        record_set = {
            "threshold_records": golden_metamorphic_corpus["threshold_records"],
            "adversarial_records": golden_metamorphic_corpus["adversarial_records"],
            "metamorphic_records": golden_metamorphic_corpus["metamorphic_records"],
            "non_relations": golden_metamorphic_corpus["non_relations"],
        }
        digest_bound = golden_metamorphic_corpus["digests"]["record_set_sha256"] == pdc_source_intake.sha256_json(
            record_set
        )
        summary = golden_metamorphic_corpus["summary"]
        healthy = (
            implementation_bound
            and math_bound
            and predecessor_bound
            and representation_bound
            and receipt_bound
            and digest_bound
            and summary["threshold_pair_count"] == 54
            and summary["adversarial_case_count"] == 8
            and summary["metamorphic_relation_count"] == 72
            and summary["non_relation_count"] == 6
        )
        results.append(
            CheckResult(
                "pdc:golden_metamorphic_corpus_bindings",
                healthy,
                (
                    f"implementation_bound={implementation_bound}; math_bound={math_bound}; "
                    f"predecessor_bound={predecessor_bound}; representation_bound={representation_bound}; "
                    f"receipt_bound={receipt_bound}; digest_bound={digest_bound}; "
                    f"thresholds={summary['threshold_pair_count']}; relations={summary['metamorphic_relation_count']}"
                ),
            )
        )

    golden_metamorphic_receipt = loaded.get("golden_metamorphic_receipt")
    if golden_metamorphic_corpus is not None and golden_metamorphic_receipt is not None:
        bindings = golden_metamorphic_receipt["bindings"]
        implementation_path = ROOT / bindings["verifier_implementation_path"]
        implementation_bound = implementation_path.is_file() and bindings[
            "verifier_implementation_sha256"
        ] == pdc_source_intake.sha256_file(implementation_path)
        corpus_bound = bindings["corpus_sha256"] == pdc_source_intake.sha256_file(
            paths["golden_metamorphic_corpus"][0]
        )
        math_bound = bindings["math_contract_sha256"] == pdc_source_intake.sha256_file(paths["math_contract"][0])
        predecessor_bound = bindings["predecessor_golden_sha256"] == pdc_source_intake.sha256_file(
            paths["golden_vectors"][0]
        )
        representation_bound = bindings["representation_contract_sha256"] == pdc_source_intake.sha256_file(
            paths["representation_contract"][0]
        )
        representation_receipt_bound = bindings[
            "representation_receipt_sha256"
        ] == pdc_source_intake.sha256_file(paths["representation_receipt"][0])
        summary = golden_metamorphic_receipt["summary"]
        healthy = (
            implementation_bound
            and corpus_bound
            and math_bound
            and predecessor_bound
            and representation_bound
            and representation_receipt_bound
            and summary["threshold_pair_count"] == 54
            and summary["metamorphic_relation_count"] == 72
            and summary["representation_round_trip_count"] == 824
            and summary["failed_negative_check_count"] == summary["mismatch_count"] == 0
        )
        results.append(
            CheckResult(
                "pdc:golden_metamorphic_receipt_bindings",
                healthy,
                (
                    f"implementation_bound={implementation_bound}; corpus_bound={corpus_bound}; "
                    f"math_bound={math_bound}; predecessor_bound={predecessor_bound}; "
                    f"representation_bound={representation_bound}; representation_receipt_bound={representation_receipt_bound}; "
                    f"thresholds={summary['threshold_pair_count']}; "
                    f"relations={summary['metamorphic_relation_count']}; round_trips={summary['representation_round_trip_count']}; "
                    f"negative={summary['negative_check_count']}; mismatches={summary['mismatch_count']}"
                ),
            )
        )

    qp_contract = loaded.get("qp_contract")
    qp_receipt = loaded.get("qp_receipt")
    if qp_contract is not None and qp_receipt is not None:
        from tools import pooleos_release_gate

        contract_check = pooleos_release_gate.check_pdc_qp_contract(
            paths["qp_contract"][0],
            paths["source_intake"][0],
            paths["verifier_intake"][0],
            paths["math_contract"][0],
        )
        receipt_check = pooleos_release_gate.check_pdc_qp_receipt(
            paths["qp_receipt"][0],
            paths["qp_contract"][0],
            paths["source_intake"][0],
            paths["verifier_intake"][0],
            paths["math_contract"][0],
        )
        results.extend(
            [
                CheckResult("pdc:qp_contract_bindings", contract_check["ok"], contract_check["detail"]),
                CheckResult("pdc:qp_receipt_bindings", receipt_check["ok"], receipt_check["detail"]),
            ]
        )
    qp_stability_contract = loaded.get("qp_stability_contract")
    qp_stability_receipt = loaded.get("qp_stability_receipt")
    if qp_stability_contract is not None and qp_stability_receipt is not None:
        from tools import pooleos_release_gate

        contract_check = pooleos_release_gate.check_pdc_qp_stability_contract(
            paths["qp_stability_contract"][0],
            paths["qp_contract"][0],
            paths["qp_receipt"][0],
        )
        receipt_check = pooleos_release_gate.check_pdc_qp_stability_receipt(
            paths["qp_stability_receipt"][0],
            paths["qp_stability_contract"][0],
            paths["qp_contract"][0],
            paths["qp_receipt"][0],
        )
        results.extend(
            [
                CheckResult("pdc:qp_stability_contract_bindings", contract_check["ok"], contract_check["detail"]),
                CheckResult("pdc:qp_stability_receipt_bindings", receipt_check["ok"], receipt_check["detail"]),
            ]
        )
    return results


def check_generated_bundle_validation() -> CheckResult:
    from runtime import channel_telemetry as ct
    from runtime import channel_trace as tr
    from runtime import pgb2_bundle as pgb2

    class MiniLattice:
        def state(self, coord):
            return "void"

        def support_count(self, coord):
            return 6 if coord == (0, 0, 0) else 0

        def evaluation_region(self, margin=None):
            return {(0, 0, 0)}

    summary = ct.measure_channels(MiniLattice())
    claim = tr.make_claim_record(
        claim_id="PGB2-DOCTOR-001",
        title="Doctor generated PGB2 bundle",
        source_descriptor="doctor:pgb2-birth",
        limitations="Doctor-generated validation artifact only.",
    )
    trace_artifact = tr.make_channel_trace(summary, claim=claim)
    code_body = pgb2.make_code_body(raw_hex="10 00 20 06 30 01 36 FF", source_label="doctor:pgasm")
    bundle = pgb2.make_bundle(code_body=code_body, trace_artifact=trace_artifact)
    result = pgb2.validate_bundle(bundle, specs_dir=ROOT / "specs")
    return CheckResult(
        "pgb2_bundle:validation",
        result.ok,
        "generated bundle validates" if result.ok else "; ".join(result.errors[:5]),
    )


def check_generated_bundle_trap_evidence_validation() -> CheckResult:
    from runtime import channel_telemetry as ct
    from runtime import channel_trace as tr
    from runtime import pgb2_bundle as pgb2

    class MiniLattice:
        def state(self, coord):
            return "void"

        def support_count(self, coord):
            return 6 if coord == (0, 0, 0) else 0

        def evaluation_region(self, margin=None):
            return {(0, 0, 0)}

    summary = ct.measure_channels(MiniLattice())
    claim = tr.make_claim_record(
        claim_id="PGB2-TRAP-BUNDLE-DOCTOR-001",
        title="Doctor generated PGB2 trap evidence bundle",
        source_descriptor="doctor:pgb2-trap-evidence",
        limitations="Doctor-generated validation artifact only.",
    )
    trace_artifact = tr.make_channel_trace(summary, claim=claim)
    code_body = pgb2.make_code_body(raw_hex="10 00 20 06 30 01 36 FF", source_label="doctor:pgasm")
    policy = microkernel_isolation.make_isolation_proof()
    matrix = {
        "status": "pass",
        "summary": {
            "failed_check_count": 0,
            "core_ir_binding_mode": "metadata_only_non_promoting",
            "core_ir_phase66_audit_present": False,
            "core_ir_executable_audit_bound": True,
            "core_ir_executable_audit_status": "audited_non_promoting",
            "core_ir_executable_candidate_count": 2,
            "core_ir_metadata_zero_count": 1,
            "core_ir_kernel_handoff_allowed": False,
            "parser_kernel_promotion_receipt_bound": True,
            "parser_kernel_promotion_receipt_status": "blocked_until_phase66",
            "parser_kernel_promotion_kernel_handoff_allowed": False,
            "parser_to_kernel_promotion_allowed": False,
            "kernel_enforcement_claimed": False,
        },
        "core_ir_boundary_receipt": {
            "artifact_path": "doctor:core_ir_receipt",
            "status": "phase66_pending",
        },
        "core_ir_executable_audit": {
            "artifact_path": "doctor:core_ir_executable_audit",
            "status": "audited_non_promoting",
        },
        "parser_kernel_promotion_receipt": {
            "artifact_path": "doctor:parser_kernel_promotion_receipt",
            "status": "blocked_until_phase66",
        },
        "trap_operations": [
            {
                "opcode": "ASSERT_MATRIX_PERMISSION",
                "region": "grid.main_grid",
                "source": "pgvm_guest",
                "target": "geometry_kernel",
                "capability": "read_grid",
                "matrix_allowed": True,
                "expected_trap": False,
                "reason": "doctor allowed matrix edge",
            }
        ],
    }
    fuzz = capability_trap_fuzz.make_capability_trap_fuzz(
        policy=policy,
        permission_matrix={"status": "pass", "summary": {"failed_check_count": 0}, "resources": [{"id": "grid.main_grid"}]},
        unknown_capability_count=2,
        unknown_permission_count=1,
    )
    proof = capability_traps.make_capability_trap_proof(policy=policy, permission_matrix=matrix, trap_fuzz=fuzz)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        proof_path = tmp_path / "capability_trap_proof.json"
        encoding_path = tmp_path / "pgb2_trap_encoding.json"
        capability_traps.write_proof(proof, proof_path)
        encoding = pgb2_trap_encoding.make_pgb2_trap_encoding(trap_proof_path=proof_path)
        pgb2_trap_encoding.write_encoding(encoding, encoding_path)
        execution = pgb2_trap_execution.make_pgb2_trap_execution(trap_encoding_path=encoding_path)
    extra_sections = pgb2.make_trap_evidence_sections(trap_encoding=encoding, trap_execution=execution)
    bundle = pgb2.make_bundle(code_body=code_body, trace_artifact=trace_artifact, extra_sections=extra_sections)
    result = pgb2.validate_bundle(bundle, specs_dir=ROOT / "specs")
    section_names = [section.get("name") for section in bundle.get("sections", [])]
    detail = (
        "generated trap evidence bundle validates"
        if result.ok
        else "; ".join(result.errors[:5])
    )
    if result.ok:
        detail = f"{detail}; sections={section_names}"
    return CheckResult("pgb2_bundle_trap_evidence:validation", result.ok, detail)


def check_generated_boot_trap_bundle_manifest_validation() -> CheckResult:
    from runtime import channel_telemetry as ct
    from runtime import channel_trace as tr
    from runtime import pgb2_bundle as pgb2
    from runtime import replay_proof as rp

    class MiniLattice:
        def state(self, coord):
            return "void"

        def support_count(self, coord):
            return 6 if coord == (0, 0, 0) else 0

        def evaluation_region(self, margin=None):
            return {(0, 0, 0)}

    summary = ct.measure_channels(MiniLattice())
    claim = tr.make_claim_record(
        claim_id="PGB2-BOOT-TRAP-MANIFEST-DOCTOR-001",
        title="Doctor generated boot trap bundle manifest",
        source_descriptor="doctor:boot-trap-bundle-manifest",
        limitations="Doctor-generated validation artifact only.",
    )
    trace_artifact = tr.make_channel_trace(summary, claim=claim)
    code_body = pgb2.make_code_body(raw_hex="10 00 20 06 30 01 36 FF", source_label="doctor:pgasm")
    policy = microkernel_isolation.make_isolation_proof()
    matrix = {
        "status": "pass",
        "summary": {
            "failed_check_count": 0,
            "core_ir_binding_mode": "metadata_only_non_promoting",
            "core_ir_phase66_audit_present": False,
            "core_ir_executable_audit_bound": True,
            "core_ir_executable_audit_status": "audited_non_promoting",
            "core_ir_executable_candidate_count": 2,
            "core_ir_metadata_zero_count": 1,
            "core_ir_kernel_handoff_allowed": False,
            "parser_kernel_promotion_receipt_bound": True,
            "parser_kernel_promotion_receipt_status": "blocked_until_phase66",
            "parser_kernel_promotion_kernel_handoff_allowed": False,
            "parser_to_kernel_promotion_allowed": False,
            "kernel_enforcement_claimed": False,
        },
        "core_ir_boundary_receipt": {
            "artifact_path": "doctor:core_ir_receipt",
            "status": "phase66_pending",
        },
        "core_ir_executable_audit": {
            "artifact_path": "doctor:core_ir_executable_audit",
            "status": "audited_non_promoting",
        },
        "parser_kernel_promotion_receipt": {
            "artifact_path": "doctor:parser_kernel_promotion_receipt",
            "status": "blocked_until_phase66",
        },
        "trap_operations": [
            {
                "opcode": "ASSERT_MATRIX_PERMISSION",
                "region": "grid.main_grid",
                "source": "pgvm_guest",
                "target": "geometry_kernel",
                "capability": "read_grid",
                "matrix_allowed": True,
                "expected_trap": False,
                "reason": "doctor allowed matrix edge",
            }
        ],
        "resources": [{"id": "grid.main_grid"}],
    }
    fuzz = capability_trap_fuzz.make_capability_trap_fuzz(
        policy=policy,
        permission_matrix=matrix,
        unknown_capability_count=2,
        unknown_permission_count=1,
    )
    proof = capability_traps.make_capability_trap_proof(policy=policy, permission_matrix=matrix, trap_fuzz=fuzz)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        proof_path = tmp_path / "capability_trap_proof.json"
        encoding_path = tmp_path / "pgb2_trap_encoding.json"
        bundle_path = tmp_path / "input.pgb2.json"
        replay_path = tmp_path / "input.replay.json"
        manifest_path = tmp_path / "pooleos_boot_trap_bundle_manifest.json"
        capability_traps.write_proof(proof, proof_path)
        encoding = pgb2_trap_encoding.make_pgb2_trap_encoding(trap_proof_path=proof_path)
        pgb2_trap_encoding.write_encoding(encoding, encoding_path)
        execution = pgb2_trap_execution.make_pgb2_trap_execution(trap_encoding_path=encoding_path)
        extra_sections = pgb2.make_trap_evidence_sections(trap_encoding=encoding, trap_execution=execution)
        bundle = pgb2.make_bundle(code_body=code_body, trace_artifact=trace_artifact, extra_sections=extra_sections)
        pgb2.write_bundle(bundle, bundle_path)
        replay = rp.make_replay_proof(
            case="six-support",
            bundle_path=bundle_path,
            bundle=bundle,
            pgvm_report={"halted": True, "trap": "", "final_body_count": 7, "instruction_count": 5},
            recomputed_channel_summary=tr.summary_to_json(summary),
        )
        rp.write_replay_proof(replay, replay_path)
        manifest = boot_trap_bundle_manifest.make_boot_trap_bundle_manifest(
            bundle_path=bundle_path,
            replay_proof_path=replay_path,
            specs_dir=ROOT / "specs",
            bundle_target_path=str(bundle_path),
            replay_target_path=str(replay_path),
            manifest_target_path=str(manifest_path),
        )
        boot_trap_bundle_manifest.write_manifest(manifest, manifest_path)
        verification = boot_trap_bundle_manifest.verify_mounted_manifest(manifest_path)
    schema = load_json(ROOT / "specs" / "boot-trap-bundle-manifest.schema.json")
    if not isinstance(schema, dict):
        return CheckResult("boot_trap_bundle_manifest:validation", False, "schema root is not an object")
    errors = validate_json(manifest, schema)
    ok = (
        not errors
        and manifest.get("status") == "pass"
        and manifest.get("summary", {}).get("failed_check_count") == 0
        and verification.get("status") == "pass"
    )
    detail = (
        f"status={manifest.get('status')}; sections={manifest.get('summary', {}).get('bundle_section_count')}; "
        f"executed={manifest.get('summary', {}).get('expected_executed_instruction_count')}; "
        f"verify={verification.get('status')}"
    )
    if errors:
        detail = "; ".join(f"{e.path}: {e.message}" for e in errors[:5])
    return CheckResult("boot_trap_bundle_manifest:validation", ok, detail)


def check_generated_qemu_shared_folder_contract_validation() -> CheckResult:
    from runtime import channel_telemetry as ct
    from runtime import channel_trace as tr
    from runtime import pgb2_bundle as pgb2
    from runtime import replay_proof as rp

    class MiniLattice:
        def state(self, coord):
            return "void"

        def support_count(self, coord):
            return 6 if coord == (0, 0, 0) else 0

        def evaluation_region(self, margin=None):
            return {(0, 0, 0)}

    summary = ct.measure_channels(MiniLattice())
    claim = tr.make_claim_record(
        claim_id="PGB2-QEMU-SHARED-DOCTOR-001",
        title="Doctor generated QEMU shared folder contract",
        source_descriptor="doctor:qemu-shared-folder-contract",
        limitations="Doctor-generated validation artifact only.",
    )
    trace_artifact = tr.make_channel_trace(summary, claim=claim)
    code_body = pgb2.make_code_body(raw_hex="10 00 20 06 30 01 36 FF", source_label="doctor:pgasm")
    policy = microkernel_isolation.make_isolation_proof()
    matrix = {
        "status": "pass",
        "summary": {
            "failed_check_count": 0,
            "core_ir_binding_mode": "metadata_only_non_promoting",
            "core_ir_phase66_audit_present": False,
            "core_ir_executable_audit_bound": True,
            "core_ir_executable_audit_status": "audited_non_promoting",
            "core_ir_executable_candidate_count": 2,
            "core_ir_metadata_zero_count": 1,
            "core_ir_kernel_handoff_allowed": False,
            "parser_kernel_promotion_receipt_bound": True,
            "parser_kernel_promotion_receipt_status": "blocked_until_phase66",
            "parser_kernel_promotion_kernel_handoff_allowed": False,
            "parser_to_kernel_promotion_allowed": False,
            "kernel_enforcement_claimed": False,
        },
        "core_ir_boundary_receipt": {
            "artifact_path": "doctor:core_ir_receipt",
            "status": "phase66_pending",
        },
        "core_ir_executable_audit": {
            "artifact_path": "doctor:core_ir_executable_audit",
            "status": "audited_non_promoting",
        },
        "parser_kernel_promotion_receipt": {
            "artifact_path": "doctor:parser_kernel_promotion_receipt",
            "status": "blocked_until_phase66",
        },
        "trap_operations": [
            {
                "opcode": "ASSERT_MATRIX_PERMISSION",
                "region": "grid.main_grid",
                "source": "pgvm_guest",
                "target": "geometry_kernel",
                "capability": "read_grid",
                "matrix_allowed": True,
                "expected_trap": False,
                "reason": "doctor allowed matrix edge",
            }
        ],
        "resources": [{"id": "grid.main_grid"}],
    }
    fuzz = capability_trap_fuzz.make_capability_trap_fuzz(
        policy=policy,
        permission_matrix=matrix,
        unknown_capability_count=2,
        unknown_permission_count=1,
    )
    proof = capability_traps.make_capability_trap_proof(policy=policy, permission_matrix=matrix, trap_fuzz=fuzz)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        proof_path = tmp_path / "capability_trap_proof.json"
        encoding_path = tmp_path / "pgb2_trap_encoding.json"
        bundle_path = tmp_path / "input.pgb2.json"
        replay_path = tmp_path / "input.replay.json"
        manifest_path = tmp_path / "pooleos_boot_trap_bundle_manifest.json"
        shared_dir = tmp_path / "shared"
        capability_traps.write_proof(proof, proof_path)
        encoding = pgb2_trap_encoding.make_pgb2_trap_encoding(trap_proof_path=proof_path)
        pgb2_trap_encoding.write_encoding(encoding, encoding_path)
        execution = pgb2_trap_execution.make_pgb2_trap_execution(trap_encoding_path=encoding_path)
        extra_sections = pgb2.make_trap_evidence_sections(trap_encoding=encoding, trap_execution=execution)
        bundle = pgb2.make_bundle(code_body=code_body, trace_artifact=trace_artifact, extra_sections=extra_sections)
        pgb2.write_bundle(bundle, bundle_path)
        replay = rp.make_replay_proof(
            case="six-support",
            bundle_path=bundle_path,
            bundle=bundle,
            pgvm_report={"halted": True, "trap": "", "final_body_count": 7, "instruction_count": 5},
            recomputed_channel_summary=tr.summary_to_json(summary),
        )
        rp.write_replay_proof(replay, replay_path)
        manifest = boot_trap_bundle_manifest.make_boot_trap_bundle_manifest(
            bundle_path=bundle_path,
            replay_proof_path=replay_path,
            specs_dir=ROOT / "specs",
        )
        boot_trap_bundle_manifest.write_manifest(manifest, manifest_path)
        contract = qemu_shared_folder_contract.make_qemu_shared_folder_contract(
            shared_dir=shared_dir,
            bundle_path=bundle_path,
            replay_proof_path=replay_path,
            boot_trap_manifest_path=manifest_path,
            specs_dir=ROOT / "specs",
        )
    schema = load_json(ROOT / "specs" / "qemu-shared-folder-contract.schema.json")
    if not isinstance(schema, dict):
        return CheckResult("qemu_shared_folder_contract:validation", False, "schema root is not an object")
    errors = validate_json(contract, schema)
    ok = not errors and contract.get("status") == "pass" and contract.get("summary", {}).get("failed_check_count") == 0
    detail = (
        f"status={contract.get('status')}; staged={contract.get('summary', {}).get('staged_file_count')}; "
        f"expected_executed={contract.get('summary', {}).get('expected_executed_instruction_count')}"
    )
    if errors:
        detail = "; ".join(f"{e.path}: {e.message}" for e in errors[:5])
    return CheckResult("qemu_shared_folder_contract:validation", ok, detail)


def check_generated_pgb2_trap_abi_boundary_receipt_validation() -> CheckResult:
    from runtime import channel_telemetry as ct
    from runtime import channel_trace as tr
    from runtime import pgb2_bundle as pgb2
    from runtime import replay_proof as rp

    class MiniLattice:
        def state(self, coord):
            return "void"

        def support_count(self, coord):
            return 6 if coord == (0, 0, 0) else 0

        def evaluation_region(self, margin=None):
            return {(0, 0, 0)}

    summary = ct.measure_channels(MiniLattice())
    claim = tr.make_claim_record(
        claim_id="PGB2-TRAP-ABI-DOCTOR-001",
        title="Doctor generated PGB2 trap ABI boundary receipt",
        source_descriptor="doctor:pgb2-trap-abi-boundary",
        limitations="Doctor-generated validation artifact only.",
    )
    trace_artifact = tr.make_channel_trace(summary, claim=claim)
    code_body = pgb2.make_code_body(raw_hex="10 00 20 06 30 01 36 FF", source_label="doctor:pgasm")
    policy = microkernel_isolation.make_isolation_proof()
    matrix = {
        "status": "pass",
        "summary": {
            "failed_check_count": 0,
            "core_ir_binding_mode": "metadata_only_non_promoting",
            "core_ir_phase66_audit_present": False,
            "core_ir_executable_audit_bound": True,
            "core_ir_executable_audit_status": "audited_non_promoting",
            "core_ir_executable_candidate_count": 2,
            "core_ir_metadata_zero_count": 1,
            "core_ir_kernel_handoff_allowed": False,
            "parser_kernel_promotion_receipt_bound": True,
            "parser_kernel_promotion_receipt_status": "blocked_until_phase66",
            "parser_kernel_promotion_kernel_handoff_allowed": False,
            "parser_to_kernel_promotion_allowed": False,
            "kernel_enforcement_claimed": False,
        },
        "core_ir_boundary_receipt": {
            "artifact_path": "doctor:core_ir_receipt",
            "status": "phase66_pending",
        },
        "core_ir_executable_audit": {
            "artifact_path": "doctor:core_ir_executable_audit",
            "status": "audited_non_promoting",
        },
        "parser_kernel_promotion_receipt": {
            "artifact_path": "doctor:parser_kernel_promotion_receipt",
            "status": "blocked_until_phase66",
        },
        "trap_operations": [
            {
                "opcode": "ASSERT_MATRIX_PERMISSION",
                "region": "grid.main_grid",
                "source": "pgvm_guest",
                "target": "geometry_kernel",
                "capability": "read_grid",
                "matrix_allowed": True,
                "expected_trap": False,
                "reason": "doctor allowed matrix edge",
            }
        ],
        "resources": [{"id": "grid.main_grid"}],
    }
    fuzz = capability_trap_fuzz.make_capability_trap_fuzz(
        policy=policy,
        permission_matrix=matrix,
        unknown_capability_count=2,
        unknown_permission_count=1,
    )
    proof = capability_traps.make_capability_trap_proof(policy=policy, permission_matrix=matrix, trap_fuzz=fuzz)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        proof_path = tmp_path / "capability_trap_proof.json"
        encoding_path = tmp_path / "pgb2_trap_encoding.json"
        execution_path = tmp_path / "pgb2_trap_execution.json"
        bundle_path = tmp_path / "input.pgb2.json"
        replay_path = tmp_path / "input.replay.json"
        manifest_path = tmp_path / "pooleos_boot_trap_bundle_manifest.json"
        contract_path = tmp_path / "qemu_shared_folder_contract.json"
        shared_dir = tmp_path / "shared"
        capability_traps.write_proof(proof, proof_path)
        encoding = pgb2_trap_encoding.make_pgb2_trap_encoding(trap_proof_path=proof_path)
        pgb2_trap_encoding.write_encoding(encoding, encoding_path)
        execution = pgb2_trap_execution.make_pgb2_trap_execution(trap_encoding_path=encoding_path)
        pgb2_trap_execution.write_execution(execution, execution_path)
        extra_sections = pgb2.make_trap_evidence_sections(trap_encoding=encoding, trap_execution=execution)
        bundle = pgb2.make_bundle(code_body=code_body, trace_artifact=trace_artifact, extra_sections=extra_sections)
        pgb2.write_bundle(bundle, bundle_path)
        replay = rp.make_replay_proof(
            case="six-support",
            bundle_path=bundle_path,
            bundle=bundle,
            pgvm_report={"halted": True, "trap": "", "final_body_count": 7, "instruction_count": 5},
            recomputed_channel_summary=tr.summary_to_json(summary),
        )
        rp.write_replay_proof(replay, replay_path)
        manifest = boot_trap_bundle_manifest.make_boot_trap_bundle_manifest(
            bundle_path=bundle_path,
            replay_proof_path=replay_path,
            trap_execution_path=execution_path,
            specs_dir=ROOT / "specs",
        )
        boot_trap_bundle_manifest.write_manifest(manifest, manifest_path)
        contract = qemu_shared_folder_contract.make_qemu_shared_folder_contract(
            shared_dir=shared_dir,
            bundle_path=bundle_path,
            replay_proof_path=replay_path,
            boot_trap_manifest_path=manifest_path,
            specs_dir=ROOT / "specs",
        )
        qemu_shared_folder_contract.write_contract(contract, contract_path)
        receipt = pgb2_trap_abi_boundary_receipt.make_pgb2_trap_abi_boundary_receipt(
            trap_encoding_path=encoding_path,
            trap_execution_path=execution_path,
            bundle_path=bundle_path,
            boot_trap_bundle_manifest_path=manifest_path,
            qemu_shared_folder_contract_path=contract_path,
            specs_dir=ROOT / "specs",
        )
    schema = load_json(ROOT / "specs" / "pgb2-trap-abi-boundary-receipt.schema.json")
    if not isinstance(schema, dict):
        return CheckResult("pgb2_trap_abi_boundary_receipt:validation", False, "schema root is not an object")
    errors = validate_json(receipt, schema)
    ok = (
        not errors
        and receipt.get("status") == "draft_verified"
        and receipt.get("summary", {}).get("failed_check_count") == 0
        and receipt.get("summary", {}).get("kernel_abi_promotion_allowed") is False
    )
    detail = (
        f"status={receipt.get('status')}; instructions={receipt.get('summary', {}).get('instruction_count')}; "
        f"bytes={receipt.get('summary', {}).get('byte_length')}; "
        f"promotion={receipt.get('summary', {}).get('kernel_abi_promotion_allowed')}"
    )
    if errors:
        detail = "; ".join(f"{e.path}: {e.message}" for e in errors[:5])
    return CheckResult("pgb2_trap_abi_boundary_receipt:validation", ok, detail)


def check_generated_lab_guest_autostart_validation() -> CheckResult:
    with tempfile.TemporaryDirectory() as tmp:
        contract_path = Path(tmp) / "qemu_shared_folder_contract.json"
        contract_path.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "shared_folder": {
                        "mount_tag": "pooleos_output",
                        "host_path": str(Path(tmp) / "qemu_shared"),
                    },
                }
            ),
            encoding="utf-8",
        )
        manifest = lab_guest_autostart.make_lab_guest_autostart(
            root=ROOT,
            qemu_shared_folder_contract_path=contract_path,
        )
    schema = load_json(ROOT / "specs" / "lab-guest-autostart.schema.json")
    if not isinstance(schema, dict):
        return CheckResult("lab_guest_autostart:validation", False, "schema root is not an object")
    errors = validate_json(manifest, schema)
    ok = not errors and manifest.get("status") == "pass" and manifest.get("summary", {}).get("failed_check_count") == 0
    detail = (
        f"status={manifest.get('status')}; mount_tag={manifest.get('guest_autostart', {}).get('mount_tag')}; "
        f"profile={manifest.get('boot_log_profile', {}).get('profile')}"
    )
    if errors:
        detail = "; ".join(f"{e.path}: {e.message}" for e in errors[:5])
    return CheckResult("lab_guest_autostart:validation", ok, detail)


def check_generated_qemu_boot_evidence_validation() -> CheckResult:
    evidence = qemu_boot_evidence.make_qemu_boot_evidence(root=ROOT)
    schema = load_json(ROOT / "specs" / "qemu-boot-evidence.schema.json")
    if not isinstance(schema, dict):
        return CheckResult("qemu_boot_evidence:validation", False, "schema root is not an object")
    errors = validate_json(evidence, schema)
    ok = (
        not errors
        and evidence.get("status") == "pass"
        and evidence.get("evidence_source") == "fixture"
        and evidence.get("boot_evidence_claimed") is False
        and evidence.get("summary", {}).get("failed_check_count") == 0
    )
    detail = (
        f"status={evidence.get('status')}; source={evidence.get('evidence_source')}; "
        f"profile={evidence.get('summary', {}).get('profile')}; "
        f"boot_evidence_claimed={evidence.get('boot_evidence_claimed')}"
    )
    if errors:
        detail = "; ".join(f"{e.path}: {e.message}" for e in errors[:5])
    return CheckResult("qemu_boot_evidence:validation", ok, detail)


def check_generated_qemu_captured_boot_preflight_validation() -> CheckResult:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        image_path = tmp_path / "rootfs.ext4"
        shared_path = tmp_path / "qemu_shared"
        image_path.write_text("fake image", encoding="utf-8")
        shared_path.mkdir()
        report = qemu_captured_boot_preflight.make_qemu_captured_boot_preflight(
            root=ROOT,
            image_path=image_path,
            shared_output_path=shared_path,
            serial_log_path=tmp_path / "pooleos-lab-serial.log",
            boot_validation_output=tmp_path / "boot_log_validation.captured.json",
            qemu_boot_evidence_output=tmp_path / "qemu_boot_evidence.captured.json",
            qemu_captured_boot_receipt_output=tmp_path / "qemu_captured_boot_receipt.json",
            qemu_command="python",
        )
    schema = load_json(ROOT / "specs" / "qemu-captured-boot-preflight.schema.json")
    if not isinstance(schema, dict):
        return CheckResult("qemu_captured_boot_preflight:validation", False, "schema root is not an object")
    errors = validate_json(report, schema)
    ok = (
        not errors
        and report.get("status") == "pass"
        and report.get("launch_ready") is True
        and report.get("execution_performed") is False
        and report.get("summary", {}).get("safety_failure_count") == 0
    )
    detail = (
        f"status={report.get('status')}; launch_ready={report.get('launch_ready')}; "
        f"blocking={report.get('summary', {}).get('blocking_check_count')}; "
        f"safety={report.get('summary', {}).get('safety_failure_count')}"
    )
    if errors:
        detail = "; ".join(f"{e.path}: {e.message}" for e in errors[:5])
    return CheckResult("qemu_captured_boot_preflight:validation", ok, detail)


def check_generated_qemu_captured_boot_launch_bundle_validation() -> CheckResult:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        image_path = tmp_path / "rootfs.ext4"
        shared_path = tmp_path / "qemu_shared"
        preflight_path = tmp_path / "qemu_captured_boot_preflight.json"
        shared_contract_path = tmp_path / "qemu_shared_folder_contract.json"
        fixture_path = tmp_path / "qemu_boot_evidence.json"
        receipt_path = tmp_path / "qemu_captured_boot_receipt.json"
        captured_path = tmp_path / "qemu_boot_evidence.captured.json"
        bundle_path = tmp_path / "qemu_captured_boot_launch_bundle.json"
        image_path.write_text("fake image", encoding="utf-8")
        shared_path.mkdir()
        preflight = qemu_captured_boot_preflight.make_qemu_captured_boot_preflight(
            root=ROOT,
            image_path=image_path,
            shared_output_path=shared_path,
            serial_log_path=tmp_path / "pooleos-lab-serial.log",
            boot_validation_output=tmp_path / "boot_log_validation.captured.json",
            qemu_boot_evidence_output=captured_path,
            qemu_captured_boot_receipt_output=receipt_path,
            qemu_command=sys.executable,
        )
        qemu_captured_boot_preflight.write_preflight(preflight, preflight_path)
        shared_contract_path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1",
                    "artifact_kind": "pooleos.qemu_shared_folder_contract",
                    "status": "pass",
                    "shared_folder": {
                        "host_path": str(shared_path),
                        "mount_tag": "pooleos_output",
                        "guest_mount_path": "/mnt/pooleos-output",
                        "qemu_args": [
                            "-virtfs",
                            f"local,path={shared_path},mount_tag=pooleos_output,security_model=none,id=pooleos_output",
                        ],
                        "prepared_for_launch": True,
                    },
                    "staged_files": [
                        {
                            "role": "trap_bundle",
                            "source_path": str(tmp_path / "input.pgb2.json"),
                            "host_path": str(shared_path / "input.pgb2.json"),
                            "guest_path": "/mnt/pooleos-output/input.pgb2.json",
                            "sha256": "a" * 64,
                            "expected_sha256": "a" * 64,
                        },
                        {
                            "role": "replay_proof",
                            "source_path": str(tmp_path / "input.replay.json"),
                            "host_path": str(shared_path / "input.replay.json"),
                            "guest_path": "/mnt/pooleos-output/input.replay.json",
                            "sha256": "b" * 64,
                            "expected_sha256": "b" * 64,
                        },
                        {
                            "role": "boot_trap_bundle_manifest",
                            "source_path": str(tmp_path / "pooleos_boot_trap_bundle_manifest.json"),
                            "host_path": str(shared_path / "pooleos_boot_trap_bundle_manifest.json"),
                            "guest_path": "/mnt/pooleos-output/pooleos_boot_trap_bundle_manifest.json",
                            "sha256": "c" * 64,
                            "expected_sha256": "c" * 64,
                        },
                    ],
                    "expected_guest_verification": {
                        "command": "pooleos-lab-verify-input",
                        "result_path": "/var/lib/pooleos/runs/boot_trap_bundle_verification.json",
                        "expected_executed_instruction_count": 1,
                        "expected_trapped_count": 0,
                        "expected_allowed_count": 1,
                        "abi_boundary_receipt_guest_path": "",
                        "expected_abi_boundary_status": "",
                        "expected_abi_frozen": False,
                        "expected_kernel_abi_promotion_allowed": False,
                        "expected_kernel_enforcement_claimed": False,
                    },
                    "checks": [{"name": "unit", "ok": True, "detail": "ok"}],
                    "summary": {
                        "staged_file_count": 3,
                        "failed_check_count": 0,
                        "perform_copy": True,
                        "expected_executed_instruction_count": 1,
                        "abi_boundary_receipt_staged": False,
                        "expected_abi_boundary_status": "",
                    },
                    "limitations": ["doctor-generated"],
                    "next_steps": ["boot"],
                }
            ),
            encoding="utf-8",
        )
        qemu_boot_evidence.write_evidence(qemu_boot_evidence.make_qemu_boot_evidence(root=ROOT), fixture_path)
        receipt = qemu_captured_boot_receipt.make_qemu_captured_boot_receipt(
            fixture_evidence_path=fixture_path,
            captured_evidence_path=captured_path,
        )
        qemu_captured_boot_receipt.write_receipt(receipt, receipt_path)
        bundle = qemu_captured_boot_launch_bundle.make_qemu_captured_boot_launch_bundle(
            root=ROOT,
            preflight_path=preflight_path,
            qemu_shared_folder_contract_path=shared_contract_path,
            qemu_captured_boot_receipt_path=receipt_path,
            fixture_evidence_path=fixture_path,
            launch_bundle_output_path=bundle_path,
            release_gate_output_path=tmp_path / "release_gate.json",
        )
    schema = load_json(ROOT / "specs" / "qemu-captured-boot-launch-bundle.schema.json")
    if not isinstance(schema, dict):
        return CheckResult("qemu_captured_boot_launch_bundle:validation", False, "schema root is not an object")
    errors = validate_json(bundle, schema)
    ok = (
        not errors
        and bundle.get("status") == "pass"
        and bundle.get("launch_ready") is True
        and bundle.get("execution_performed") is False
        and bundle.get("summary", {}).get("failed_check_count") == 0
        and bundle.get("summary", {}).get("command_count", 0) >= 5
    )
    detail = (
        f"status={bundle.get('status')}; launch_ready={bundle.get('launch_ready')}; "
        f"commands={bundle.get('summary', {}).get('command_count')}; "
        f"failed={bundle.get('summary', {}).get('failed_check_count')}"
    )
    if errors:
        detail = "; ".join(f"{e.path}: {e.message}" for e in errors[:5])
    return CheckResult("qemu_captured_boot_launch_bundle:validation", ok, detail)


def check_generated_qemu_captured_boot_dry_run_checklist_validation() -> CheckResult:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        image_path = tmp_path / "rootfs.ext4"
        shared_path = tmp_path / "qemu_shared"
        preflight_path = tmp_path / "qemu_captured_boot_preflight.json"
        launch_bundle_path = tmp_path / "qemu_captured_boot_launch_bundle.json"
        checklist_path = tmp_path / "qemu_captured_boot_dry_run_checklist.json"
        release_gate_path = tmp_path / "release_gate.json"
        image_path.write_text("fake image", encoding="utf-8")
        shared_path.mkdir()
        preflight = qemu_captured_boot_preflight.make_qemu_captured_boot_preflight(
            root=ROOT,
            image_path=image_path,
            shared_output_path=shared_path,
            serial_log_path=tmp_path / "pooleos-lab-serial.log",
            boot_validation_output=tmp_path / "boot_log_validation.captured.json",
            qemu_boot_evidence_output=tmp_path / "qemu_boot_evidence.captured.json",
            qemu_captured_boot_receipt_output=tmp_path / "qemu_captured_boot_receipt.json",
            qemu_command=sys.executable,
        )
        qemu_captured_boot_preflight.write_preflight(preflight, preflight_path)
        commands = [
            ("prepare_shared_folder", "stage"),
            ("captured_preflight", "preflight"),
            ("qemu_launch", "launch"),
            ("emit_captured_evidence_only", "evidence"),
            ("captured_receipt", "receipt"),
        ]
        launch_bundle_path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1",
                    "artifact_kind": "pooleos.qemu_captured_boot_launch_bundle",
                    "status": "pass",
                    "launch_ready": True,
                    "execution_performed": False,
                    "pooleos_root": str(ROOT),
                    "inputs": {
                        "preflight": str(preflight_path),
                        "qemu_shared_folder_contract": str(tmp_path / "qemu_shared_folder_contract.json"),
                        "qemu_captured_boot_receipt": str(tmp_path / "qemu_captured_boot_receipt.json"),
                        "fixture_evidence": str(tmp_path / "qemu_boot_evidence.json"),
                        "launcher_script": str(ROOT / "lab-os" / "qemu" / "scripts" / "run-pooleos-lab.ps1"),
                    },
                    "expected_outputs": {
                        "serial_log_path": str(tmp_path / "pooleos-lab-serial.log"),
                        "boot_validation_output": str(tmp_path / "boot_log_validation.captured.json"),
                        "qemu_boot_evidence_output": str(tmp_path / "qemu_boot_evidence.captured.json"),
                        "qemu_captured_boot_receipt_output": str(tmp_path / "qemu_captured_boot_receipt.json"),
                        "launch_bundle_output": str(launch_bundle_path),
                        "release_gate_output": str(release_gate_path),
                    },
                    "command_plan": [
                        {
                            "role": role,
                            "description": description,
                            "argv": ["python", role],
                            "powershell": f"python {role}",
                        }
                        for role, description in commands
                    ],
                    "release_gate_arguments": [
                        "--qemu-captured-boot-preflight",
                        str(preflight_path),
                        "--qemu-captured-boot-launch-bundle",
                        str(launch_bundle_path),
                    ],
                    "checks": [{"name": "unit", "severity": "fail", "ok": True, "detail": "ok"}],
                    "summary": {
                        "failed_check_count": 0,
                        "blocking_check_count": 0,
                        "command_count": 5,
                        "preflight_status": "pass",
                        "preflight_launch_ready": True,
                        "shared_folder_status": "pass",
                        "shared_folder_ready": True,
                        "receipt_status": "pending_capture",
                        "captured_outputs_separate": True,
                        "execution_performed": False,
                    },
                    "limitations": ["doctor-generated"],
                    "next_steps": ["dry run"],
                }
            ),
            encoding="utf-8",
        )
        checklist = qemu_captured_boot_dry_run_checklist.make_qemu_captured_boot_dry_run_checklist(
            root=ROOT,
            launch_bundle_path=launch_bundle_path,
            checklist_output_path=checklist_path,
            release_gate_output_path=release_gate_path,
        )
    schema = load_json(ROOT / "specs" / "qemu-captured-boot-dry-run-checklist.schema.json")
    if not isinstance(schema, dict):
        return CheckResult("qemu_captured_boot_dry_run_checklist:validation", False, "schema root is not an object")
    errors = validate_json(checklist, schema)
    expected_marker_count = len(boot_log.required_markers_for_profile("trap-input"))
    ok = (
        not errors
        and checklist.get("status") == "pass"
        and checklist.get("launch_ready") is True
        and checklist.get("execution_performed") is False
        and checklist.get("summary", {}).get("failed_check_count") == 0
        and checklist.get("summary", {}).get("checklist_step_count", 0) >= 8
        and checklist.get("summary", {}).get("expected_marker_count", 0) == expected_marker_count
        and "POOLEOS_LAB_TRAP_ABI_BOUNDARY_PASS" in checklist.get("expected_serial_markers", [])
        and checklist.get("operator_receipt_template", {}).get("codex_execution_performed") is False
        and "--qemu-captured-boot-dry-run-checklist" in checklist.get("release_gate_reconciliation", {}).get("checklist_arguments", [])
    )
    detail = (
        f"status={checklist.get('status')}; launch_ready={checklist.get('launch_ready')}; "
        f"steps={checklist.get('summary', {}).get('checklist_step_count')}; "
        f"markers={checklist.get('summary', {}).get('expected_marker_count')}; "
        f"failed={checklist.get('summary', {}).get('failed_check_count')}"
    )
    if errors:
        detail = "; ".join(f"{e.path}: {e.message}" for e in errors[:5])
    return CheckResult("qemu_captured_boot_dry_run_checklist:validation", ok, detail)


def check_generated_qemu_boot_marker_contract_validation() -> CheckResult:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        dry_run_path = tmp_path / "qemu_captured_boot_dry_run_checklist.json"
        autostart_path = tmp_path / "lab_guest_autostart.json"
        markers = boot_log.required_markers_for_profile("trap-input")
        dry_run_path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1",
                    "artifact_kind": "pooleos.qemu_captured_boot_dry_run_checklist",
                    "status": "pass",
                    "launch_ready": True,
                    "execution_performed": False,
                    "expected_serial_markers": markers,
                    "post_capture_files": [
                        {"role": "serial_log", "path": str(tmp_path / "pooleos-lab-serial.log")},
                        {"role": "boot_validation", "path": str(tmp_path / "boot_log_validation.captured.json")},
                        {"role": "captured_boot_evidence", "path": str(tmp_path / "qemu_boot_evidence.captured.json")},
                        {"role": "captured_boot_receipt", "path": str(tmp_path / "qemu_captured_boot_receipt.json")},
                        {"role": "release_gate", "path": str(tmp_path / "release_gate.json")},
                    ],
                    "summary": {
                        "failed_check_count": 0,
                        "blocking_check_count": 0,
                    },
                }
            ),
            encoding="utf-8",
        )
        autostart_path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1",
                    "artifact_kind": "pooleos.lab_guest_autostart",
                    "status": "pass",
                    "boot_evidence_claimed": False,
                    "boot_log_profile": {
                        "profile": "trap-input",
                        "required_markers": markers,
                    },
                    "summary": {
                        "failed_check_count": 0,
                        "required_marker_count": len(markers),
                    },
                }
            ),
            encoding="utf-8",
        )
        contract = qemu_boot_marker_contract.make_qemu_boot_marker_contract(
            root=ROOT,
            dry_run_checklist_path=dry_run_path,
            lab_guest_autostart_path=autostart_path,
        )
    schema = load_json(ROOT / "specs" / "qemu-boot-marker-contract.schema.json")
    if not isinstance(schema, dict):
        return CheckResult("qemu_boot_marker_contract:validation", False, "schema root is not an object")
    errors = validate_json(contract, schema)
    ok = (
        not errors
        and contract.get("status") == "pass"
        and contract.get("execution_performed") is False
        and contract.get("boot_evidence_claimed") is False
        and contract.get("security_boundary_claimed") is False
        and contract.get("summary", {}).get("failed_check_count") == 0
        and contract.get("summary", {}).get("marker_count") == len(boot_log.required_markers_for_profile("trap-input"))
        and contract.get("summary", {}).get("boundary_count") == len(boot_log.required_markers_for_profile("trap-input"))
    )
    detail = (
        f"status={contract.get('status')}; markers={contract.get('summary', {}).get('marker_count')}; "
        f"boundaries={contract.get('summary', {}).get('boundary_count')}; "
        f"failed={contract.get('summary', {}).get('failed_check_count')}"
    )
    if errors:
        detail = "; ".join(f"{e.path}: {e.message}" for e in errors[:5])
    return CheckResult("qemu_boot_marker_contract:validation", ok, detail)


def check_generated_qemu_boot_marker_image_binding_validation() -> CheckResult:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        dry_run_path = tmp_path / "qemu_captured_boot_dry_run_checklist.json"
        autostart_path = tmp_path / "lab_guest_autostart.json"
        marker_contract_path = tmp_path / "qemu_boot_marker_contract.json"
        lab_manifest_path = tmp_path / "lab_image_manifest.json"
        markers = boot_log.required_markers_for_profile("trap-input")
        dry_run_path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1",
                    "artifact_kind": "pooleos.qemu_captured_boot_dry_run_checklist",
                    "status": "pass",
                    "launch_ready": True,
                    "execution_performed": False,
                    "expected_serial_markers": markers,
                    "post_capture_files": [
                        {"role": "serial_log", "path": str(tmp_path / "pooleos-lab-serial.log")},
                        {"role": "boot_validation", "path": str(tmp_path / "boot_log_validation.captured.json")},
                        {"role": "captured_boot_evidence", "path": str(tmp_path / "qemu_boot_evidence.captured.json")},
                        {"role": "captured_boot_receipt", "path": str(tmp_path / "qemu_captured_boot_receipt.json")},
                        {"role": "release_gate", "path": str(tmp_path / "release_gate.json")},
                    ],
                    "summary": {
                        "failed_check_count": 0,
                        "blocking_check_count": 0,
                    },
                }
            ),
            encoding="utf-8",
        )
        autostart_path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1",
                    "artifact_kind": "pooleos.lab_guest_autostart",
                    "status": "pass",
                    "boot_evidence_claimed": False,
                    "boot_log_profile": {
                        "profile": "trap-input",
                        "required_markers": markers,
                    },
                    "summary": {
                        "failed_check_count": 0,
                        "required_marker_count": len(markers),
                    },
                }
            ),
            encoding="utf-8",
        )
        qemu_boot_marker_contract.write_contract(
            qemu_boot_marker_contract.make_qemu_boot_marker_contract(
                root=ROOT,
                dry_run_checklist_path=dry_run_path,
                lab_guest_autostart_path=autostart_path,
            ),
            marker_contract_path,
        )
        lab_manifest.write_lab_manifest(lab_manifest.make_lab_manifest(root=ROOT), lab_manifest_path)
        binding = qemu_boot_marker_image_binding.make_qemu_boot_marker_image_binding(
            root=ROOT,
            marker_contract_path=marker_contract_path,
            lab_image_manifest_path=lab_manifest_path,
        )
    schema = load_json(ROOT / "specs" / "qemu-boot-marker-image-binding.schema.json")
    if not isinstance(schema, dict):
        return CheckResult("qemu_boot_marker_image_binding:validation", False, "schema root is not an object")
    errors = validate_json(binding, schema)
    bound_markers = {
        marker
        for file_binding in binding.get("marker_file_bindings", [])
        if isinstance(file_binding, dict)
        for marker in file_binding.get("markers", [])
    }
    ok = (
        not errors
        and binding.get("status") == "pass"
        and binding.get("execution_performed") is False
        and binding.get("boot_evidence_claimed") is False
        and binding.get("security_boundary_claimed") is False
        and binding.get("summary", {}).get("failed_check_count") == 0
        and binding.get("summary", {}).get("marker_count") == len(boot_log.required_markers_for_profile("trap-input"))
        and "POOLEOS_LAB_TRAP_ABI_BOUNDARY_PASS" in bound_markers
        and binding.get("summary", {}).get("marker_source_file_count", 0) >= 2
        and binding.get("summary", {}).get("support_file_count", 0) >= 3
        and binding.get("summary", {}).get("buildroot_manifest_file_count", 0) >= 5
    )
    detail = (
        f"status={binding.get('status')}; markers={binding.get('summary', {}).get('marker_count')}; "
        f"marker_sources={binding.get('summary', {}).get('marker_source_file_count')}; "
        f"hashed={binding.get('summary', {}).get('hashed_file_count')}; "
        f"failed={binding.get('summary', {}).get('failed_check_count')}"
    )
    if errors:
        detail = "; ".join(f"{e.path}: {e.message}" for e in errors[:5])
    return CheckResult("qemu_boot_marker_image_binding:validation", ok, detail)


def check_generated_rootfs_content_manifest_validation() -> CheckResult:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        dry_run_path = tmp_path / "qemu_captured_boot_dry_run_checklist.json"
        autostart_path = tmp_path / "lab_guest_autostart.json"
        marker_contract_path = tmp_path / "qemu_boot_marker_contract.json"
        lab_manifest_path = tmp_path / "lab_image_manifest.json"
        image_binding_path = tmp_path / "qemu_boot_marker_image_binding.json"
        image_path = tmp_path / "rootfs.ext4"
        extracted_rootfs = tmp_path / "extracted-rootfs"
        markers = boot_log.required_markers_for_profile("trap-input")
        dry_run_path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1",
                    "artifact_kind": "pooleos.qemu_captured_boot_dry_run_checklist",
                    "status": "pass",
                    "launch_ready": True,
                    "execution_performed": False,
                    "expected_serial_markers": markers,
                    "post_capture_files": [
                        {"role": "serial_log", "path": str(tmp_path / "pooleos-lab-serial.log")},
                        {"role": "boot_validation", "path": str(tmp_path / "boot_log_validation.captured.json")},
                        {"role": "captured_boot_evidence", "path": str(tmp_path / "qemu_boot_evidence.captured.json")},
                        {"role": "captured_boot_receipt", "path": str(tmp_path / "qemu_captured_boot_receipt.json")},
                        {"role": "release_gate", "path": str(tmp_path / "release_gate.json")},
                    ],
                    "summary": {
                        "failed_check_count": 0,
                        "blocking_check_count": 0,
                    },
                }
            ),
            encoding="utf-8",
        )
        autostart_path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1",
                    "artifact_kind": "pooleos.lab_guest_autostart",
                    "status": "pass",
                    "boot_evidence_claimed": False,
                    "boot_log_profile": {
                        "profile": "trap-input",
                        "required_markers": markers,
                    },
                    "summary": {
                        "failed_check_count": 0,
                        "required_marker_count": len(markers),
                    },
                }
            ),
            encoding="utf-8",
        )
        qemu_boot_marker_contract.write_contract(
            qemu_boot_marker_contract.make_qemu_boot_marker_contract(
                root=ROOT,
                dry_run_checklist_path=dry_run_path,
                lab_guest_autostart_path=autostart_path,
            ),
            marker_contract_path,
        )
        lab_manifest.write_lab_manifest(lab_manifest.make_lab_manifest(root=ROOT), lab_manifest_path)
        binding = qemu_boot_marker_image_binding.make_qemu_boot_marker_image_binding(
            root=ROOT,
            marker_contract_path=marker_contract_path,
            lab_image_manifest_path=lab_manifest_path,
        )
        qemu_boot_marker_image_binding.write_binding(binding, image_binding_path)
        image_path.write_text("doctor fake rootfs image", encoding="utf-8")
        extracted_rootfs.mkdir()
        for source in binding["marker_file_bindings"] + binding["support_file_bindings"]:
            guest_path = str(source["guest_path"]).lstrip("/")
            destination = extracted_rootfs.joinpath(*guest_path.split("/"))
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(Path(source["path"]).read_bytes())
        manifest = rootfs_content_manifest.make_rootfs_content_manifest(
            root=ROOT,
            image_binding_path=image_binding_path,
            image_path=image_path,
            extracted_rootfs_path=extracted_rootfs,
        )
    schema = load_json(ROOT / "specs" / "rootfs-content-manifest.schema.json")
    if not isinstance(schema, dict):
        return CheckResult("rootfs_content_manifest:validation", False, "schema root is not an object")
    errors = validate_json(manifest, schema)
    ok = (
        not errors
        and manifest.get("status") == "pass"
        and manifest.get("execution_performed") is False
        and manifest.get("rootfs_extraction_performed") is False
        and manifest.get("boot_evidence_claimed") is False
        and manifest.get("security_boundary_claimed") is False
        and manifest.get("summary", {}).get("failed_check_count") == 0
        and manifest.get("summary", {}).get("source_file_count", 0) >= 5
        and manifest.get("summary", {}).get("matched_source_file_count") == manifest.get("summary", {}).get("source_file_count")
    )
    detail = (
        f"status={manifest.get('status')}; image_exists={manifest.get('summary', {}).get('image_exists')}; "
        f"matched={manifest.get('summary', {}).get('matched_source_file_count')}/{manifest.get('summary', {}).get('source_file_count')}; "
        f"failed={manifest.get('summary', {}).get('failed_check_count')}"
    )
    if errors:
        detail = "; ".join(f"{e.path}: {e.message}" for e in errors[:5])
    return CheckResult("rootfs_content_manifest:validation", ok, detail)


def check_generated_rootfs_extraction_handoff_validation() -> CheckResult:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        image_path = tmp_path / "rootfs.ext4"
        image_binding_path = tmp_path / "qemu_boot_marker_image_binding.json"
        manifest_path = tmp_path / "rootfs_content_manifest.json"
        handoff_path = tmp_path / "rootfs_extraction_handoff.json"
        note_path = tmp_path / "rootfs_extraction_handoff.md"
        image_path.write_text("doctor fake rootfs image", encoding="utf-8")
        image_binding_path.write_text('{"artifact_kind":"pooleos.qemu_boot_marker_image_binding"}\n', encoding="utf-8")
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1",
                    "artifact_kind": "pooleos.rootfs_content_manifest",
                    "status": "blocked",
                    "execution_performed": False,
                    "rootfs_extraction_performed": False,
                    "boot_evidence_claimed": False,
                    "security_boundary_claimed": False,
                    "source_inputs": {
                        "image_binding_path": str(image_binding_path),
                        "image_binding_status": "pass",
                    },
                    "rootfs_image": {
                        "path": str(image_path),
                        "exists": True,
                        "sha256": "a" * 64,
                        "byte_count": image_path.stat().st_size,
                    },
                    "extracted_rootfs": {
                        "path": str(tmp_path / "rootfs_extracted"),
                        "exists": False,
                    },
                    "content_file_bindings": [],
                    "checks": [],
                    "summary": {
                        "failed_check_count": 0,
                        "blocking_check_count": 1,
                        "source_file_count": 5,
                        "source_hashed_file_count": 5,
                        "rootfs_file_count": 0,
                        "matched_source_file_count": 0,
                        "image_exists": True,
                        "image_sha256": "a" * 64,
                        "extracted_rootfs_exists": False,
                        "image_binding_status": "pass",
                        "execution_performed": False,
                        "rootfs_extraction_performed": False,
                        "boot_evidence_claimed": False,
                        "security_boundary_claimed": False,
                    },
                    "limitations": ["doctor synthetic source manifest"],
                    "next_steps": ["extract"],
                }
            ),
            encoding="utf-8",
        )
        handoff = rootfs_extraction_handoff.make_rootfs_extraction_handoff(
            root=ROOT,
            rootfs_content_manifest_path=manifest_path,
            handoff_output_path=handoff_path,
            note_output_path=note_path,
        )
    schema = load_json(ROOT / "specs" / "rootfs-extraction-handoff.schema.json")
    if not isinstance(schema, dict):
        return CheckResult("rootfs_extraction_handoff:validation", False, "schema root is not an object")
    errors = validate_json(handoff, schema)
    ok = (
        not errors
        and handoff.get("status") == "pass"
        and handoff.get("execution_performed") is False
        and handoff.get("codex_execution_allowed") is False
        and handoff.get("rootfs_extraction_performed") is False
        and handoff.get("summary", {}).get("failed_check_count") == 0
        and handoff.get("summary", {}).get("command_count", 0) >= 7
        and "mount -o ro,loop" in handoff.get("bash_script", "")
        and "emit_rootfs_content_manifest.py" in handoff.get("bash_script", "")
        and "rm -rf" not in handoff.get("bash_script", "")
        and "--delete" not in handoff.get("bash_script", "")
    )
    detail = (
        f"status={handoff.get('status')}; image_exists={handoff.get('summary', {}).get('rootfs_image_exists')}; "
        f"commands={handoff.get('summary', {}).get('command_count')}; "
        f"failed={handoff.get('summary', {}).get('failed_check_count')}"
    )
    if errors:
        detail = "; ".join(f"{e.path}: {e.message}" for e in errors[:5])
    return CheckResult("rootfs_extraction_handoff:validation", ok, detail)


def check_generated_rootfs_extraction_receipt_validation() -> CheckResult:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        handoff_path = tmp_path / "rootfs_extraction_handoff.json"
        manifest_path = tmp_path / "rootfs_content_manifest.json"
        handoff_path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1",
                    "artifact_kind": "pooleos.rootfs_extraction_handoff",
                    "status": "pass",
                    "execution_performed": False,
                    "codex_execution_allowed": False,
                    "rootfs_extraction_performed": False,
                    "bash_script_sha256": "b" * 64,
                    "operator_receipt_template": {
                        "operator_executed": False,
                        "codex_execution_performed": False,
                    },
                    "summary": {
                        "failed_check_count": 0,
                        "blocking_check_count": 0,
                        "command_count": 7,
                        "source_manifest_status": "blocked",
                        "source_manifest_failed_check_count": 0,
                        "source_file_count": 5,
                        "rootfs_image_exists": True,
                        "extracted_rootfs_exists": False,
                        "bash_script_sha256": "b" * 64,
                        "operator_executed": False,
                        "execution_performed": False,
                        "rootfs_extraction_performed": False,
                    },
                }
            ),
            encoding="utf-8",
        )
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1",
                    "artifact_kind": "pooleos.rootfs_content_manifest",
                    "status": "pass",
                    "execution_performed": False,
                    "rootfs_extraction_performed": False,
                    "boot_evidence_claimed": False,
                    "security_boundary_claimed": False,
                    "summary": {
                        "failed_check_count": 0,
                        "blocking_check_count": 0,
                        "source_file_count": 5,
                        "source_hashed_file_count": 5,
                        "rootfs_file_count": 5,
                        "matched_source_file_count": 5,
                        "image_exists": True,
                        "image_sha256": "a" * 64,
                        "extracted_rootfs_exists": True,
                        "image_binding_status": "pass",
                        "execution_performed": False,
                        "rootfs_extraction_performed": False,
                        "boot_evidence_claimed": False,
                        "security_boundary_claimed": False,
                    },
                }
            ),
            encoding="utf-8",
        )
        receipt = rootfs_extraction_receipt.make_rootfs_extraction_receipt(
            handoff_path=handoff_path,
            rootfs_content_manifest_path=manifest_path,
            operator_executed=True,
            operator_notes="doctor synthetic receipt",
        )
    schema = load_json(ROOT / "specs" / "rootfs-extraction-receipt.schema.json")
    if not isinstance(schema, dict):
        return CheckResult("rootfs_extraction_receipt:validation", False, "schema root is not an object")
    errors = validate_json(receipt, schema)
    ok = (
        not errors
        and receipt.get("status") == "verified"
        and receipt.get("operator_executed") is True
        and receipt.get("codex_execution_performed") is False
        and receipt.get("rootfs_extraction_performed") is True
        and receipt.get("captured_qemu_promotion_allowed") is True
        and receipt.get("summary", {}).get("matched_source_file_count") == receipt.get("summary", {}).get("source_file_count")
    )
    detail = (
        f"status={receipt.get('status')}; operator_executed={receipt.get('operator_executed')}; "
        f"promotion={receipt.get('captured_qemu_promotion_allowed')}; "
        f"matched={receipt.get('summary', {}).get('matched_source_file_count')}/{receipt.get('summary', {}).get('source_file_count')}"
    )
    if errors:
        detail = "; ".join(f"{e.path}: {e.message}" for e in errors[:5])
    return CheckResult("rootfs_extraction_receipt:validation", ok, detail)


def check_generated_qemu_captured_boot_receipt_validation() -> CheckResult:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        fixture_path = tmp_path / "qemu_boot_evidence.json"
        captured_path = tmp_path / "qemu_boot_evidence.captured.json"
        qemu_boot_evidence.write_evidence(qemu_boot_evidence.make_qemu_boot_evidence(root=ROOT), fixture_path)
        receipt = qemu_captured_boot_receipt.make_qemu_captured_boot_receipt(
            fixture_evidence_path=fixture_path,
            captured_evidence_path=captured_path,
        )
    schema = load_json(ROOT / "specs" / "qemu-captured-boot-receipt.schema.json")
    if not isinstance(schema, dict):
        return CheckResult("qemu_captured_boot_receipt:validation", False, "schema root is not an object")
    errors = validate_json(receipt, schema)
    ok = (
        not errors
        and receipt.get("status") == "pending_capture"
        and receipt.get("summary", {}).get("failed_check_count") == 0
        and receipt.get("summary", {}).get("fixture_preserved") is True
        and receipt.get("boot_evidence_ingested") is False
    )
    detail = (
        f"status={receipt.get('status')}; fixture_preserved={receipt.get('summary', {}).get('fixture_preserved')}; "
        f"captured_exists={receipt.get('summary', {}).get('captured_evidence_exists')}; "
        f"ingested={receipt.get('boot_evidence_ingested')}"
    )
    if errors:
        detail = "; ".join(f"{e.path}: {e.message}" for e in errors[:5])
    return CheckResult("qemu_captured_boot_receipt:validation", ok, detail)


def check_generated_qemu_captured_boot_readiness_validation() -> CheckResult:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        rootfs_handoff_path = tmp_path / "rootfs_extraction_handoff.json"
        rootfs_manifest_path = tmp_path / "rootfs_content_manifest.json"
        rootfs_receipt_path = tmp_path / "rootfs_extraction_receipt.json"
        fixture_path = tmp_path / "qemu_boot_evidence.json"
        captured_path = tmp_path / "qemu_boot_evidence.captured.json"
        captured_receipt_path = tmp_path / "qemu_captured_boot_receipt.json"
        rootfs_handoff_path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1",
                    "artifact_kind": "pooleos.rootfs_extraction_handoff",
                    "status": "pass",
                    "execution_performed": False,
                    "codex_execution_allowed": False,
                    "rootfs_extraction_performed": False,
                    "bash_script_sha256": "b" * 64,
                    "summary": {"failed_check_count": 0, "command_count": 7},
                }
            ),
            encoding="utf-8",
        )
        rootfs_manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1",
                    "artifact_kind": "pooleos.rootfs_content_manifest",
                    "status": "pass",
                    "summary": {
                        "failed_check_count": 0,
                        "source_file_count": 5,
                        "matched_source_file_count": 5,
                        "image_exists": True,
                        "image_sha256": "a" * 64,
                        "extracted_rootfs_exists": True,
                    },
                }
            ),
            encoding="utf-8",
        )
        rootfs_receipt = rootfs_extraction_receipt.make_rootfs_extraction_receipt(
            handoff_path=rootfs_handoff_path,
            rootfs_content_manifest_path=rootfs_manifest_path,
            operator_executed=True,
        )
        rootfs_extraction_receipt.write_receipt(rootfs_receipt, rootfs_receipt_path)
        qemu_boot_evidence.write_evidence(qemu_boot_evidence.make_qemu_boot_evidence(root=ROOT), fixture_path)
        qemu_boot_evidence.write_evidence(
            qemu_boot_evidence.make_qemu_boot_evidence(root=ROOT, evidence_source="captured_qemu_serial"),
            captured_path,
        )
        captured_receipt = qemu_captured_boot_receipt.make_qemu_captured_boot_receipt(
            fixture_evidence_path=fixture_path,
            captured_evidence_path=captured_path,
            operator_executed=True,
        )
        qemu_captured_boot_receipt.write_receipt(captured_receipt, captured_receipt_path)
        report = qemu_captured_boot_readiness.make_qemu_captured_boot_readiness(
            rootfs_extraction_receipt_path=rootfs_receipt_path,
            qemu_captured_boot_receipt_path=captured_receipt_path,
            qemu_captured_boot_evidence_path=captured_path,
        )
    schema = load_json(ROOT / "specs" / "qemu-captured-boot-readiness.schema.json")
    if not isinstance(schema, dict):
        return CheckResult("qemu_captured_boot_readiness:validation", False, "schema root is not an object")
    errors = validate_json(report, schema)
    ok = (
        not errors
        and report.get("status") == "ready_for_promotion"
        and report.get("promotion_language_allowed") is True
        and report.get("summary", {}).get("failed_check_count") == 0
        and report.get("summary", {}).get("unmet_requirement_count") == 0
        and report.get("summary", {}).get("captured_evidence_valid") is True
    )
    detail = (
        f"status={report.get('status')}; promotion={report.get('promotion_language_allowed')}; "
        f"unmet={report.get('summary', {}).get('unmet_requirement_count')}; "
        f"captured_valid={report.get('summary', {}).get('captured_evidence_valid')}"
    )
    if errors:
        detail = "; ".join(f"{e.path}: {e.message}" for e in errors[:5])
    return CheckResult("qemu_captured_boot_readiness:validation", ok, detail)


def check_generated_kernel_boot_handoff_validation() -> CheckResult:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        readiness_path = tmp_path / "qemu_captured_boot_readiness.json"
        marker_contract_path = tmp_path / "qemu_boot_marker_contract.json"
        boot_manifest_path = tmp_path / "pooleos_boot_trap_bundle_manifest.json"
        guest_verification_path = tmp_path / "boot_trap_bundle_verification.json"
        readiness_path.write_text(
            json.dumps(
                {
                    "artifact_kind": "pooleos.qemu_captured_boot_readiness",
                    "status": "ready_for_promotion",
                    "promotion_language_allowed": True,
                    "summary": {
                        "failed_check_count": 0,
                        "unmet_requirement_count": 0,
                        "captured_evidence_valid": True,
                    },
                }
            ),
            encoding="utf-8",
        )
        marker_contract_path.write_text(
            json.dumps(
                {
                    "artifact_kind": "pooleos.qemu_boot_marker_contract",
                    "status": "pass",
                    "boot_evidence_claimed": False,
                    "security_boundary_claimed": False,
                    "kernel_pgvm2_boundary": {
                        "kernel_boundary_claimed": False,
                        "pgvm2_execution_claimed": False,
                    },
                    "summary": {
                        "failed_check_count": 0,
                        "blocking_check_count": 0,
                        "marker_count": 10,
                        "expected_marker_count": 10,
                        "boundary_count": 10,
                    },
                }
            ),
            encoding="utf-8",
        )
        boot_manifest_path.write_text(
            json.dumps(
                {
                    "artifact_kind": "pooleos.boot_trap_bundle_manifest",
                    "status": "pass",
                    "lab_mount": {
                        "verification_result_path": "/var/lib/pooleos/runs/boot_trap_bundle_verification.json",
                    },
                    "summary": {
                        "failed_check_count": 0,
                        "trap_evidence_present": True,
                        "expected_executed_instruction_count": 29,
                    },
                }
            ),
            encoding="utf-8",
        )
        guest_verification_path.write_text(
            json.dumps(
                {
                    "artifact_kind": "pooleos.boot_trap_bundle_verification",
                    "status": "pass",
                    "summary": {
                        "failed_check_count": 0,
                        "expected_executed_instruction_count": 29,
                    },
                }
            ),
            encoding="utf-8",
        )
        handoff = kernel_boot_handoff.make_kernel_boot_handoff(
            qemu_captured_boot_readiness_path=readiness_path,
            qemu_boot_marker_contract_path=marker_contract_path,
            boot_trap_bundle_manifest_path=boot_manifest_path,
            guest_loader_verification_path=guest_verification_path,
        )
    schema = load_json(ROOT / "specs" / "kernel-boot-handoff.schema.json")
    if not isinstance(schema, dict):
        return CheckResult("kernel_boot_handoff:validation", False, "schema root is not an object")
    errors = validate_json(handoff, schema)
    ok = (
        not errors
        and handoff.get("status") == "ready_for_kernel_handoff"
        and handoff.get("kernel_handoff_allowed") is True
        and handoff.get("kernel_boundary_claimed") is False
        and handoff.get("pgvm2_execution_claimed") is False
        and handoff.get("summary", {}).get("failed_check_count") == 0
        and handoff.get("summary", {}).get("unmet_requirement_count") == 0
    )
    detail = (
        f"status={handoff.get('status')}; handoff_allowed={handoff.get('kernel_handoff_allowed')}; "
        f"unmet={handoff.get('summary', {}).get('unmet_requirement_count')}; "
        f"loader_exists={handoff.get('summary', {}).get('guest_loader_verification_exists')}"
    )
    if errors:
        detail = "; ".join(f"{e.path}: {e.message}" for e in errors[:5])
    return CheckResult("kernel_boot_handoff:validation", ok, detail)


def check_generated_kernel_pgvm2_loader_output_validation() -> CheckResult:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        handoff_path = tmp_path / "kernel_boot_handoff.json"
        handoff_path.write_text(
            json.dumps(
                {
                    "artifact_kind": "pooleos.kernel_boot_handoff",
                    "status": "ready_for_kernel_handoff",
                    "kernel_handoff_allowed": True,
                    "kernel_boundary_claimed": False,
                    "pgvm2_execution_claimed": False,
                    "guest_loader_outputs": [
                        {
                            "expected_executed_instruction_count": 29,
                            "actual_executed_instruction_count": 29,
                        }
                    ],
                    "summary": {
                        "failed_check_count": 0,
                        "unmet_requirement_count": 0,
                    },
                }
            ),
            encoding="utf-8",
        )
        source_anchor_path = tmp_path / "pooleglyph_source_anchor.json"
        source_anchor_path.write_text(
            json.dumps(
                {
                    "artifact_kind": "pooleos.pooleglyph_source_anchor",
                    "status": "warn",
                    "summary": {
                        "dirty_file_count": 1,
                        "failed_check_count": 0,
                    },
                }
            ),
            encoding="utf-8",
        )
        promotion_path = tmp_path / "pooleglyph_parser_kernel_promotion_receipt.json"
        promotion_path.write_text(
            json.dumps(
                {
                    "artifact_kind": "pooleos.pooleglyph_parser_kernel_promotion_receipt",
                    "status": "blocked_until_phase66",
                    "summary": {
                        "failed_check_count": 0,
                        "phase66_audit_present": False,
                        "parser_to_kernel_promotion_allowed": False,
                        "kernel_handoff_allowed": False,
                        "kernel_enforcement_claimed": False,
                    },
                }
            ),
            encoding="utf-8",
        )
        negative = kernel_pgvm2_loader_output.make_kernel_pgvm2_loader_output(
            kernel_boot_handoff_path=handoff_path,
            pooleglyph_source_anchor_path=source_anchor_path,
            parser_kernel_promotion_receipt_path=promotion_path,
            kernel_build_id="doctor-negative-fixture",
        )
        synthetic_pass = kernel_pgvm2_loader_output.make_kernel_pgvm2_loader_output(
            kernel_boot_handoff_path=handoff_path,
            pooleglyph_source_anchor_path=source_anchor_path,
            parser_kernel_promotion_receipt_path=promotion_path,
            kernel_build_id="doctor-synthetic-kernel",
            mode="synthetic_pass",
        )
        handoff_sha256 = hashlib.sha256(handoff_path.read_bytes()).hexdigest()
        source_anchor_sha256 = hashlib.sha256(source_anchor_path.read_bytes()).hexdigest()
        promotion_sha256 = hashlib.sha256(promotion_path.read_bytes()).hexdigest()
        transcript_path = tmp_path / "kernel_pgvm2_loader.transcript.txt"
        transcript_lines = [
            "POOLEOS_KERNEL_LOADER_START",
            "POOLEOS_KERNEL_BUILD_ID doctor-transcript-kernel",
            f"POOLEOS_KERNEL_HANDOFF_SHA256 {handoff_sha256}",
            f"POOLEOS_POOLEGLYPH_SOURCE_ANCHOR_SHA256 {source_anchor_sha256}",
            f"POOLEOS_POOLEGLYPH_PARSER_PROMOTION_RECEIPT_SHA256 {promotion_sha256}",
            "POOLEOS_KERNEL_BOOTED_PATH true",
            "POOLEOS_KERNEL_ENFORCEMENT_CLAIM true",
            "POOLEOS_PGVM2_EXECUTION_CLAIM true",
            "POOLEOS_KERNEL_EXPECTED_INSTRUCTIONS 29",
            "POOLEOS_KERNEL_ACTUAL_INSTRUCTIONS 29",
        ]
        transcript_lines.extend(
            f"POOLEOS_KERNEL_CHECK {check['name']} PASS"
            for check in kernel_pgvm2_loader_evidence.PLANNED_KERNEL_CHECKS
        )
        transcript_lines.append("POOLEOS_KERNEL_LOADER_DONE")
        transcript_path.write_text("\n".join(transcript_lines) + "\n", encoding="utf-8")
        transcript_pass = kernel_pgvm2_loader_output.make_kernel_pgvm2_loader_output_from_transcript(
            kernel_boot_handoff_path=handoff_path,
            transcript_path=transcript_path,
            pooleglyph_source_anchor_path=source_anchor_path,
            parser_kernel_promotion_receipt_path=promotion_path,
        )
    schema = load_json(ROOT / "specs" / "kernel-pgvm2-loader-output.schema.json")
    if not isinstance(schema, dict):
        return CheckResult("kernel_pgvm2_loader_output:validation", False, "schema root is not an object")
    negative_errors = validate_json(negative, schema)
    pass_errors = validate_json(synthetic_pass, schema)
    transcript_errors = validate_json(transcript_pass, schema)
    ok = (
        not negative_errors
        and not pass_errors
        and not transcript_errors
        and negative.get("status") == "blocked"
        and negative.get("kernel_enforcement_claimed") is False
        and negative.get("summary", {}).get("negative_claim_guard_held") is True
        and synthetic_pass.get("status") == "pass"
        and synthetic_pass.get("kernel_enforcement_claimed") is True
        and synthetic_pass.get("summary", {}).get("satisfied_kernel_check_count")
        == len(kernel_pgvm2_loader_evidence.PLANNED_KERNEL_CHECKS)
        and synthetic_pass.get("summary", {}).get("actual_executed_instruction_count") == 29
        and transcript_pass.get("status") == "pass"
        and transcript_pass.get("kernel_enforcement_claimed") is True
        and transcript_pass.get("transcript_source", {}).get("exists") is True
    )
    detail = (
        f"negative={negative.get('status')}; claim={negative.get('kernel_enforcement_claimed')}; "
        f"pass={synthetic_pass.get('status')}; checks={synthetic_pass.get('summary', {}).get('satisfied_kernel_check_count')}/"
        f"{synthetic_pass.get('summary', {}).get('kernel_check_count')}; transcript={transcript_pass.get('status')}"
    )
    errors = negative_errors or pass_errors or transcript_errors
    if errors:
        detail = "; ".join(f"{e.path}: {e.message}" for e in errors[:5])
    return CheckResult("kernel_pgvm2_loader_output:validation", ok, detail)


def check_generated_lab_kernel_transcript_export_receipt_validation() -> CheckResult:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        contract_source = tmp_path / "pooleos-kernel-pgvm2-transcript-contract"
        transcript_path = tmp_path / "kernel_pgvm2_loader.transcript.txt"
        loader_output_path = tmp_path / "kernel_pgvm2_loader_output.json"
        contract_source.write_text("#!/bin/sh\n", encoding="utf-8")
        transcript_path.write_text(
            "\n".join(
                [
                    "POOLEOS_KERNEL_LOADER_START",
                    "POOLEOS_KERNEL_GUEST_ENV POOLEOS_POOLEGLYPH_SOURCE_ANCHOR_SHA256 " + "b" * 64,
                    "POOLEOS_KERNEL_GUEST_ENV POOLEOS_POOLEGLYPH_PARSER_PROMOTION_RECEIPT_SHA256 "
                    + "c" * 64,
                    "POOLEOS_KERNEL_LOADER_DONE",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        loader_output = {
            "artifact_kind": "pooleos.kernel_pgvm2_loader_output",
            "status": "blocked",
            "booted_kernel_path": False,
            "kernel_enforcement_claimed": False,
            "pgvm2_execution_claimed": False,
            "source_handoff_sha256": "a" * 64,
            "pooleglyph_source_anchor_sha256": "b" * 64,
            "pooleglyph_parser_kernel_promotion_receipt_sha256": "c" * 64,
            "summary": {
                "failed_check_count": 0,
                "blocking_check_count": len(kernel_pgvm2_loader_evidence.PLANNED_KERNEL_CHECKS) - 1,
                "kernel_check_count": len(kernel_pgvm2_loader_evidence.PLANNED_KERNEL_CHECKS),
                "satisfied_kernel_check_count": 1,
                "negative_claim_guard_held": True,
            },
            "transcript_claims": {
                "booted_kernel_path": False,
                "kernel_enforcement_claimed": False,
                "pgvm2_execution_claimed": False,
            },
            "transcript_source": {
                "path": str(transcript_path),
                "exists": True,
                "sha256": hashlib.sha256(transcript_path.read_bytes()).hexdigest(),
                "line_count": len(transcript_path.read_text(encoding="utf-8").splitlines()),
            },
        }
        loader_output_path.write_text(json.dumps(loader_output), encoding="utf-8")
        pending = lab_kernel_transcript_export_receipt.make_lab_kernel_transcript_export_receipt(
            contract_source_path=contract_source,
            transcript_path=transcript_path,
            kernel_loader_output_path=loader_output_path,
        )
        disabled = lab_kernel_transcript_export_receipt.make_lab_kernel_transcript_export_receipt(
            contract_source_path=contract_source,
            transcript_path=transcript_path,
            kernel_loader_output_path=loader_output_path,
            contract_run_recorded=True,
            contract_mode="disabled",
        )
    schema = load_json(ROOT / "specs" / "lab-kernel-transcript-export-receipt.schema.json")
    if not isinstance(schema, dict):
        return CheckResult("lab_kernel_transcript_export_receipt:validation", False, "schema root is not an object")
    pending_errors = validate_json(pending, schema)
    disabled_errors = validate_json(disabled, schema)
    ok = (
        not pending_errors
        and not disabled_errors
        and pending.get("status") == "pending_contract_run"
        and pending.get("kernel_enforcement_promotion_allowed") is False
        and disabled.get("status") == "disabled_verified"
        and disabled.get("verifier_accepted_export") is True
        and disabled.get("guest_environment_digest_pair_attested") is True
        and disabled.get("transcript_digest_matches_verifier") is True
        and disabled.get("kernel_enforcement_promotion_allowed") is False
    )
    detail = (
        f"pending={pending.get('status')}; disabled={disabled.get('status')}; "
        f"accepted={disabled.get('verifier_accepted_export')}; "
        f"guest_digest_pair={disabled.get('guest_environment_digest_pair_attested')}; "
        f"transcript_bound={disabled.get('transcript_digest_matches_verifier')}; "
        f"promotion={disabled.get('kernel_enforcement_promotion_allowed')}"
    )
    errors = pending_errors or disabled_errors
    if errors:
        detail = "; ".join(f"{e.path}: {e.message}" for e in errors[:5])
    return CheckResult("lab_kernel_transcript_export_receipt:validation", ok, detail)


def check_generated_kernel_pgvm2_loader_evidence_validation() -> CheckResult:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        handoff_path = tmp_path / "kernel_boot_handoff.json"
        loader_output_path = tmp_path / "kernel_pgvm2_loader_output.json"
        source_anchor_path = tmp_path / "pooleglyph_source_anchor.json"
        promotion_path = tmp_path / "pooleglyph_parser_kernel_promotion_receipt.json"
        handoff_path.write_text(
            json.dumps(
                {
                    "artifact_kind": "pooleos.kernel_boot_handoff",
                    "status": "ready_for_kernel_handoff",
                    "kernel_handoff_allowed": True,
                    "kernel_boundary_claimed": False,
                    "pgvm2_execution_claimed": False,
                    "guest_loader_outputs": [
                        {
                            "expected_executed_instruction_count": 29,
                            "actual_executed_instruction_count": 29,
                        }
                    ],
                    "summary": {
                        "failed_check_count": 0,
                        "unmet_requirement_count": 0,
                    },
                }
            ),
            encoding="utf-8",
        )
        source_anchor_path.write_text(
            json.dumps(
                {
                    "artifact_kind": "pooleos.pooleglyph_source_anchor",
                    "status": "warn",
                    "summary": {
                        "dirty_file_count": 1,
                        "failed_check_count": 0,
                    },
                }
            ),
            encoding="utf-8",
        )
        promotion_path.write_text(
            json.dumps(
                {
                    "artifact_kind": "pooleos.pooleglyph_parser_kernel_promotion_receipt",
                    "status": "parser_to_kernel_ready",
                    "summary": {
                        "failed_check_count": 0,
                        "phase66_audit_present": True,
                        "parser_to_kernel_promotion_allowed": True,
                        "kernel_handoff_allowed": True,
                        "kernel_enforcement_claimed": False,
                    },
                }
            ),
            encoding="utf-8",
        )
        stub = kernel_pgvm2_loader_evidence.make_kernel_pgvm2_loader_evidence(
            kernel_boot_handoff_path=handoff_path,
            kernel_loader_output_path=loader_output_path,
            pooleglyph_source_anchor_path=source_anchor_path,
            parser_kernel_promotion_receipt_path=promotion_path,
        )
        handoff_sha256 = hashlib.sha256(handoff_path.read_bytes()).hexdigest()
        source_anchor_sha256 = hashlib.sha256(source_anchor_path.read_bytes()).hexdigest()
        promotion_sha256 = hashlib.sha256(promotion_path.read_bytes()).hexdigest()
        planned_names = [check["name"] for check in kernel_pgvm2_loader_evidence.PLANNED_KERNEL_CHECKS]
        loader_output_path.write_text(
            json.dumps(
                {
                    "artifact_kind": "pooleos.kernel_pgvm2_loader_output",
                    "status": "pass",
                    "booted_kernel_path": True,
                    "kernel_enforcement_claimed": True,
                    "pgvm2_execution_claimed": True,
                    "source_handoff_sha256": handoff_sha256,
                    "pooleglyph_source_anchor_sha256": source_anchor_sha256,
                    "pooleglyph_parser_kernel_promotion_receipt_sha256": promotion_sha256,
                    "kernel_build_id": "doctor-synthetic-kernel",
                    "kernel_checks": [
                        {"name": name, "ok": True, "detail": "synthetic booted kernel check"}
                        for name in planned_names
                    ],
                    "summary": {
                        "failed_check_count": 0,
                        "kernel_check_count": len(planned_names),
                        "satisfied_kernel_check_count": len(planned_names),
                        "expected_executed_instruction_count": 29,
                        "actual_executed_instruction_count": 29,
                    },
                }
            ),
            encoding="utf-8",
        )
        enforced = kernel_pgvm2_loader_evidence.make_kernel_pgvm2_loader_evidence(
            kernel_boot_handoff_path=handoff_path,
            kernel_loader_output_path=loader_output_path,
            pooleglyph_source_anchor_path=source_anchor_path,
            parser_kernel_promotion_receipt_path=promotion_path,
        )
    schema = load_json(ROOT / "specs" / "kernel-pgvm2-loader-evidence.schema.json")
    if not isinstance(schema, dict):
        return CheckResult("kernel_pgvm2_loader_evidence:validation", False, "schema root is not an object")
    stub_errors = validate_json(stub, schema)
    enforced_errors = validate_json(enforced, schema)
    ok = (
        not stub_errors
        and not enforced_errors
        and stub.get("status") == "ready_for_kernel_loader"
        and stub.get("kernel_enforcement_claimed") is False
        and enforced.get("status") == "kernel_enforced"
        and enforced.get("kernel_enforcement_claimed") is True
        and enforced.get("pgvm2_execution_claimed") is True
        and enforced.get("summary", {}).get("parser_promotion_ready_for_enforcement") is True
        and enforced.get("summary", {}).get("unmet_requirement_count") == 0
        and enforced.get("summary", {}).get("all_kernel_checks_satisfied") is True
    )
    detail = (
        f"stub={stub.get('status')}; enforced={enforced.get('status')}; "
        f"checks={enforced.get('summary', {}).get('satisfied_kernel_check_count')}/"
        f"{enforced.get('summary', {}).get('planned_kernel_check_count')}; "
        f"enforcement={enforced.get('kernel_enforcement_claimed')}"
    )
    errors = stub_errors or enforced_errors
    if errors:
        detail = "; ".join(f"{e.path}: {e.message}" for e in errors[:5])
    return CheckResult("kernel_pgvm2_loader_evidence:validation", ok, detail)


def check_generated_isolation_validation() -> CheckResult:
    from runtime import microkernel_isolation

    proof = microkernel_isolation.make_isolation_proof()
    schema = load_json(ROOT / "specs" / "isolation-proof.schema.json")
    if not isinstance(schema, dict):
        return CheckResult("isolation_proof:validation", False, "schema root is not an object")
    errors = validate_json(proof, schema)
    if proof.get("status") != "pass":
        return CheckResult("isolation_proof:validation", False, f"status={proof.get('status')}")
    return CheckResult(
        "isolation_proof:validation",
        not errors,
        "generated isolation proof validates" if not errors else "; ".join(f"{e.path}: {e.message}" for e in errors[:5]),
    )


def check_generated_capability_trap_validation() -> CheckResult:
    from runtime import capability_traps
    from runtime import microkernel_isolation

    proof = capability_traps.make_capability_trap_proof(policy=microkernel_isolation.make_isolation_proof())
    schema = load_json(ROOT / "specs" / "capability-trap-proof.schema.json")
    if not isinstance(schema, dict):
        return CheckResult("capability_trap_proof:validation", False, "schema root is not an object")
    errors = validate_json(proof, schema)
    if proof.get("status") != "pass":
        return CheckResult("capability_trap_proof:validation", False, f"status={proof.get('status')}")
    return CheckResult(
        "capability_trap_proof:validation",
        not errors,
        "generated capability trap proof validates" if not errors else "; ".join(f"{e.path}: {e.message}" for e in errors[:5]),
    )


def check_generated_pooleglyph_bridge_validation(pooleglyph: Path) -> CheckResult:
    anchor = pooleglyph_source_anchor.make_source_anchor(pooleglyph_path=pooleglyph)
    with tempfile.TemporaryDirectory() as tmp:
        anchor_path = Path(tmp) / "pooleglyph_source_anchor.json"
        pooleglyph_source_anchor.write_anchor(anchor, anchor_path)
        manifest = pooleglyph_bridge_manifest.make_bridge_manifest(
            source_anchor_path=anchor_path,
            pooleglyph_path=pooleglyph,
        )
    schema = load_json(ROOT / "specs" / "pooleglyph-bridge-manifest.schema.json")
    if not isinstance(schema, dict):
        return CheckResult("pooleglyph_bridge_manifest:validation", False, "schema root is not an object")
    errors = validate_json(manifest, schema)
    ok = not errors and manifest.get("status") in {"pass", "warn"} and manifest.get("summary", {}).get("failed_check_count") == 0
    detail = (
        f"status={manifest.get('status')}; latest_phase={manifest.get('source_anchor', {}).get('latest_phase')}; "
        f"bridge_maps={manifest.get('summary', {}).get('bridge_map_count')}"
    )
    if errors:
        detail = "; ".join(f"{e.path}: {e.message}" for e in errors[:5])
    return CheckResult("pooleglyph_bridge_manifest:validation", ok, detail)


def check_generated_pooleglyph_core_ir_boundary_receipt_validation(pooleglyph: Path) -> CheckResult:
    anchor = pooleglyph_source_anchor.make_source_anchor(pooleglyph_path=pooleglyph)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        anchor_path = tmp_path / "pooleglyph_source_anchor.json"
        bridge_path = tmp_path / "pooleglyph_bridge_manifest.json"
        pooleglyph_source_anchor.write_anchor(anchor, anchor_path)
        bridge = pooleglyph_bridge_manifest.make_bridge_manifest(
            source_anchor_path=anchor_path,
            pooleglyph_path=pooleglyph,
        )
        pooleglyph_bridge_manifest.write_bridge_manifest(bridge, bridge_path)
        receipt = pooleglyph_core_ir_boundary_receipt.make_pooleglyph_core_ir_boundary_receipt(
            bridge_manifest_path=bridge_path,
            pooleglyph_path=pooleglyph,
        )
    schema = load_json(ROOT / "specs" / "pooleglyph-core-ir-boundary-receipt.schema.json")
    if not isinstance(schema, dict):
        return CheckResult("pooleglyph_core_ir_boundary_receipt:validation", False, "schema root is not an object")
    errors = validate_json(receipt, schema)
    ok = (
        not errors
        and receipt.get("status") in {"phase66_pending", "validated_non_promoting", "parser_to_kernel_ready"}
        and receipt.get("summary", {}).get("failed_check_count") == 0
        and receipt.get("kernel_enforcement_claimed") is False
    )
    detail = (
        f"status={receipt.get('status')}; phase66={receipt.get('summary', {}).get('phase66_audit_present')}; "
        f"promotion={receipt.get('summary', {}).get('parser_to_kernel_promotion_allowed')}; "
        f"exec_candidates={receipt.get('summary', {}).get('validated_executable_candidate_count')}; "
        f"metadata_zero={receipt.get('summary', {}).get('validated_metadata_zero_program_count')}"
    )
    if errors:
        detail = "; ".join(f"{e.path}: {e.message}" for e in errors[:5])
    return CheckResult("pooleglyph_core_ir_boundary_receipt:validation", ok, detail)


def check_generated_pooleglyph_core_ir_executable_audit_validation(pooleglyph: Path) -> CheckResult:
    anchor = pooleglyph_source_anchor.make_source_anchor(pooleglyph_path=pooleglyph)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        anchor_path = tmp_path / "pooleglyph_source_anchor.json"
        bridge_path = tmp_path / "pooleglyph_bridge_manifest.json"
        receipt_path = tmp_path / "pooleglyph_core_ir_boundary_receipt.json"
        audit_path = tmp_path / "pooleglyph_core_ir_executable_audit.json"
        promotion_path = tmp_path / "pooleglyph_parser_kernel_promotion_receipt.json"
        pooleglyph_source_anchor.write_anchor(anchor, anchor_path)
        bridge = pooleglyph_bridge_manifest.make_bridge_manifest(
            source_anchor_path=anchor_path,
            pooleglyph_path=pooleglyph,
        )
        pooleglyph_bridge_manifest.write_bridge_manifest(bridge, bridge_path)
        receipt = pooleglyph_core_ir_boundary_receipt.make_pooleglyph_core_ir_boundary_receipt(
            bridge_manifest_path=bridge_path,
            pooleglyph_path=pooleglyph,
        )
        pooleglyph_core_ir_boundary_receipt.write_receipt(receipt, receipt_path)
        audit = pooleglyph_core_ir_executable_audit.make_pooleglyph_core_ir_executable_audit(
            core_ir_boundary_receipt_path=receipt_path,
        )
    schema = load_json(ROOT / "specs" / "pooleglyph-core-ir-executable-audit.schema.json")
    if not isinstance(schema, dict):
        return CheckResult("pooleglyph_core_ir_executable_audit:validation", False, "schema root is not an object")
    errors = validate_json(audit, schema)
    ok = (
        not errors
        and audit.get("status") in {"audited_non_promoting", "parser_to_kernel_ready"}
        and audit.get("summary", {}).get("failed_check_count") == 0
        and audit.get("summary", {}).get("kernel_enforcement_claimed") is False
    )
    detail = (
        f"status={audit.get('status')}; phase66={audit.get('summary', {}).get('phase66_audit_present')}; "
        f"promotion={audit.get('summary', {}).get('parser_to_kernel_promotion_allowed')}; "
        f"exec_candidates={audit.get('summary', {}).get('executable_candidate_count')}; "
        f"metadata_zero={audit.get('summary', {}).get('metadata_zero_count')}"
    )
    if errors:
        detail = "; ".join(f"{e.path}: {e.message}" for e in errors[:5])
    return CheckResult("pooleglyph_core_ir_executable_audit:validation", ok, detail)


def check_generated_pooleglyph_parser_kernel_promotion_receipt_validation(pooleglyph: Path) -> CheckResult:
    anchor = pooleglyph_source_anchor.make_source_anchor(pooleglyph_path=pooleglyph)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        anchor_path = tmp_path / "pooleglyph_source_anchor.json"
        bridge_path = tmp_path / "pooleglyph_bridge_manifest.json"
        receipt_path = tmp_path / "pooleglyph_core_ir_boundary_receipt.json"
        audit_path = tmp_path / "pooleglyph_core_ir_executable_audit.json"
        promotion_path = tmp_path / "pooleglyph_parser_kernel_promotion_receipt.json"
        pooleglyph_source_anchor.write_anchor(anchor, anchor_path)
        bridge = pooleglyph_bridge_manifest.make_bridge_manifest(
            source_anchor_path=anchor_path,
            pooleglyph_path=pooleglyph,
        )
        pooleglyph_bridge_manifest.write_bridge_manifest(bridge, bridge_path)
        receipt = pooleglyph_core_ir_boundary_receipt.make_pooleglyph_core_ir_boundary_receipt(
            bridge_manifest_path=bridge_path,
            pooleglyph_path=pooleglyph,
        )
        pooleglyph_core_ir_boundary_receipt.write_receipt(receipt, receipt_path)
        audit = pooleglyph_core_ir_executable_audit.make_pooleglyph_core_ir_executable_audit(
            core_ir_boundary_receipt_path=receipt_path,
        )
        pooleglyph_core_ir_executable_audit.write_audit(audit, audit_path)
        promotion = pooleglyph_parser_kernel_promotion_receipt.make_pooleglyph_parser_kernel_promotion_receipt(
            core_ir_executable_audit_path=audit_path,
        )
    schema = load_json(ROOT / "specs" / "pooleglyph-parser-kernel-promotion-receipt.schema.json")
    if not isinstance(schema, dict):
        return CheckResult("pooleglyph_parser_kernel_promotion_receipt:validation", False, "schema root is not an object")
    errors = validate_json(promotion, schema)
    ok = (
        not errors
        and promotion.get("status") in {"blocked_until_phase66", "parser_to_kernel_ready"}
        and promotion.get("summary", {}).get("failed_check_count") == 0
        and promotion.get("summary", {}).get("kernel_enforcement_claimed") is False
    )
    detail = (
        f"status={promotion.get('status')}; phase66={promotion.get('summary', {}).get('phase66_audit_present')}; "
        f"promotion={promotion.get('summary', {}).get('parser_to_kernel_promotion_allowed')}; "
        f"handoff={promotion.get('summary', {}).get('kernel_handoff_allowed')}; "
        f"exec_candidates={promotion.get('summary', {}).get('executable_candidate_count')}"
    )
    if errors:
        detail = "; ".join(f"{e.path}: {e.message}" for e in errors[:5])
    return CheckResult("pooleglyph_parser_kernel_promotion_receipt:validation", ok, detail)


def check_generated_permission_matrix_validation(pooleglyph: Path) -> CheckResult:
    anchor = pooleglyph_source_anchor.make_source_anchor(pooleglyph_path=pooleglyph)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        anchor_path = tmp_path / "pooleglyph_source_anchor.json"
        bridge_path = tmp_path / "pooleglyph_bridge_manifest.json"
        receipt_path = tmp_path / "pooleglyph_core_ir_boundary_receipt.json"
        audit_path = tmp_path / "pooleglyph_core_ir_executable_audit.json"
        promotion_path = tmp_path / "pooleglyph_parser_kernel_promotion_receipt.json"
        pooleglyph_source_anchor.write_anchor(anchor, anchor_path)
        bridge = pooleglyph_bridge_manifest.make_bridge_manifest(
            source_anchor_path=anchor_path,
            pooleglyph_path=pooleglyph,
        )
        pooleglyph_bridge_manifest.write_bridge_manifest(bridge, bridge_path)
        receipt = pooleglyph_core_ir_boundary_receipt.make_pooleglyph_core_ir_boundary_receipt(
            bridge_manifest_path=bridge_path,
            pooleglyph_path=pooleglyph,
        )
        pooleglyph_core_ir_boundary_receipt.write_receipt(receipt, receipt_path)
        audit = pooleglyph_core_ir_executable_audit.make_pooleglyph_core_ir_executable_audit(
            core_ir_boundary_receipt_path=receipt_path,
        )
        pooleglyph_core_ir_executable_audit.write_audit(audit, audit_path)
        promotion = pooleglyph_parser_kernel_promotion_receipt.make_pooleglyph_parser_kernel_promotion_receipt(
            core_ir_executable_audit_path=audit_path,
        )
        pooleglyph_parser_kernel_promotion_receipt.write_receipt(promotion, promotion_path)
        matrix = permission_capability_matrix.make_permission_capability_matrix(
            bridge_manifest_path=bridge_path,
            core_ir_boundary_receipt_path=receipt_path,
            core_ir_executable_audit_path=audit_path,
            parser_kernel_promotion_receipt_path=promotion_path,
            pooleglyph_path=pooleglyph,
        )
    schema = load_json(ROOT / "specs" / "permission-capability-matrix.schema.json")
    if not isinstance(schema, dict):
        return CheckResult("permission_capability_matrix:validation", False, "schema root is not an object")
    errors = validate_json(matrix, schema)
    ok = not errors and matrix.get("status") in {"pass", "warn"} and matrix.get("summary", {}).get("failed_check_count") == 0
    detail = (
        f"status={matrix.get('status')}; resources={matrix.get('summary', {}).get('resource_count')}; "
        f"permissions={matrix.get('summary', {}).get('permission_count')}; trap_ops={matrix.get('summary', {}).get('trap_operation_count')}; "
        f"audit={matrix.get('summary', {}).get('core_ir_executable_audit_status')}; "
        f"promotion={matrix.get('summary', {}).get('parser_kernel_promotion_receipt_status')}"
    )
    if errors:
        detail = "; ".join(f"{e.path}: {e.message}" for e in errors[:5])
    return CheckResult("permission_capability_matrix:validation", ok, detail)


def check_generated_capability_trap_fuzz_validation(pooleglyph: Path) -> CheckResult:
    policy = microkernel_isolation.make_isolation_proof()
    anchor = pooleglyph_source_anchor.make_source_anchor(pooleglyph_path=pooleglyph)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        anchor_path = tmp_path / "pooleglyph_source_anchor.json"
        bridge_path = tmp_path / "pooleglyph_bridge_manifest.json"
        receipt_path = tmp_path / "pooleglyph_core_ir_boundary_receipt.json"
        audit_path = tmp_path / "pooleglyph_core_ir_executable_audit.json"
        promotion_path = tmp_path / "pooleglyph_parser_kernel_promotion_receipt.json"
        pooleglyph_source_anchor.write_anchor(anchor, anchor_path)
        bridge = pooleglyph_bridge_manifest.make_bridge_manifest(
            source_anchor_path=anchor_path,
            pooleglyph_path=pooleglyph,
        )
        pooleglyph_bridge_manifest.write_bridge_manifest(bridge, bridge_path)
        receipt = pooleglyph_core_ir_boundary_receipt.make_pooleglyph_core_ir_boundary_receipt(
            bridge_manifest_path=bridge_path,
            pooleglyph_path=pooleglyph,
        )
        pooleglyph_core_ir_boundary_receipt.write_receipt(receipt, receipt_path)
        audit = pooleglyph_core_ir_executable_audit.make_pooleglyph_core_ir_executable_audit(
            core_ir_boundary_receipt_path=receipt_path,
        )
        pooleglyph_core_ir_executable_audit.write_audit(audit, audit_path)
        promotion = pooleglyph_parser_kernel_promotion_receipt.make_pooleglyph_parser_kernel_promotion_receipt(
            core_ir_executable_audit_path=audit_path,
        )
        pooleglyph_parser_kernel_promotion_receipt.write_receipt(promotion, promotion_path)
        matrix = permission_capability_matrix.make_permission_capability_matrix(
            bridge_manifest_path=bridge_path,
            core_ir_boundary_receipt_path=receipt_path,
            core_ir_executable_audit_path=audit_path,
            parser_kernel_promotion_receipt_path=promotion_path,
            pooleglyph_path=pooleglyph,
        )
    fuzz = capability_trap_fuzz.make_capability_trap_fuzz(policy=policy, permission_matrix=matrix)
    schema = load_json(ROOT / "specs" / "capability-trap-fuzz.schema.json")
    if not isinstance(schema, dict):
        return CheckResult("capability_trap_fuzz:validation", False, "schema root is not an object")
    errors = validate_json(fuzz, schema)
    ok = not errors and fuzz.get("status") == "pass" and fuzz.get("summary", {}).get("failed_check_count") == 0
    detail = (
        f"status={fuzz.get('status')}; operations={fuzz.get('summary', {}).get('operation_count')}; "
        f"unknown_caps={fuzz.get('summary', {}).get('unknown_capability_count')}; "
        f"unknown_permissions={fuzz.get('summary', {}).get('unknown_permission_count')}"
    )
    if errors:
        detail = "; ".join(f"{e.path}: {e.message}" for e in errors[:5])
    return CheckResult("capability_trap_fuzz:validation", ok, detail)


def check_generated_pgb2_trap_encoding_validation(pooleglyph: Path) -> CheckResult:
    policy = microkernel_isolation.make_isolation_proof()
    anchor = pooleglyph_source_anchor.make_source_anchor(pooleglyph_path=pooleglyph)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        anchor_path = tmp_path / "pooleglyph_source_anchor.json"
        bridge_path = tmp_path / "pooleglyph_bridge_manifest.json"
        receipt_path = tmp_path / "pooleglyph_core_ir_boundary_receipt.json"
        audit_path = tmp_path / "pooleglyph_core_ir_executable_audit.json"
        promotion_path = tmp_path / "pooleglyph_parser_kernel_promotion_receipt.json"
        proof_path = tmp_path / "capability_trap_proof.json"
        pooleglyph_source_anchor.write_anchor(anchor, anchor_path)
        bridge = pooleglyph_bridge_manifest.make_bridge_manifest(
            source_anchor_path=anchor_path,
            pooleglyph_path=pooleglyph,
        )
        pooleglyph_bridge_manifest.write_bridge_manifest(bridge, bridge_path)
        receipt = pooleglyph_core_ir_boundary_receipt.make_pooleglyph_core_ir_boundary_receipt(
            bridge_manifest_path=bridge_path,
            pooleglyph_path=pooleglyph,
        )
        pooleglyph_core_ir_boundary_receipt.write_receipt(receipt, receipt_path)
        audit = pooleglyph_core_ir_executable_audit.make_pooleglyph_core_ir_executable_audit(
            core_ir_boundary_receipt_path=receipt_path,
        )
        pooleglyph_core_ir_executable_audit.write_audit(audit, audit_path)
        promotion = pooleglyph_parser_kernel_promotion_receipt.make_pooleglyph_parser_kernel_promotion_receipt(
            core_ir_executable_audit_path=audit_path,
        )
        pooleglyph_parser_kernel_promotion_receipt.write_receipt(promotion, promotion_path)
        matrix = permission_capability_matrix.make_permission_capability_matrix(
            bridge_manifest_path=bridge_path,
            core_ir_boundary_receipt_path=receipt_path,
            core_ir_executable_audit_path=audit_path,
            parser_kernel_promotion_receipt_path=promotion_path,
            pooleglyph_path=pooleglyph,
        )
        fuzz = capability_trap_fuzz.make_capability_trap_fuzz(policy=policy, permission_matrix=matrix)
        proof = capability_traps.make_capability_trap_proof(policy=policy, permission_matrix=matrix, trap_fuzz=fuzz)
        capability_traps.write_proof(proof, proof_path)
        encoding = pgb2_trap_encoding.make_pgb2_trap_encoding(trap_proof_path=proof_path)
    schema = load_json(ROOT / "specs" / "pgb2-trap-encoding.schema.json")
    if not isinstance(schema, dict):
        return CheckResult("pgb2_trap_encoding:validation", False, "schema root is not an object")
    errors = validate_json(encoding, schema)
    ok = not errors and encoding.get("status") == "pass" and encoding.get("summary", {}).get("failed_check_count") == 0
    detail = (
        f"status={encoding.get('status')}; instructions={encoding.get('summary', {}).get('instruction_count')}; "
        f"bytes={encoding.get('summary', {}).get('byte_length')}"
    )
    if errors:
        detail = "; ".join(f"{e.path}: {e.message}" for e in errors[:5])
    return CheckResult("pgb2_trap_encoding:validation", ok, detail)


def check_generated_pgb2_trap_execution_validation(pooleglyph: Path) -> CheckResult:
    policy = microkernel_isolation.make_isolation_proof()
    anchor = pooleglyph_source_anchor.make_source_anchor(pooleglyph_path=pooleglyph)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        anchor_path = tmp_path / "pooleglyph_source_anchor.json"
        bridge_path = tmp_path / "pooleglyph_bridge_manifest.json"
        receipt_path = tmp_path / "pooleglyph_core_ir_boundary_receipt.json"
        audit_path = tmp_path / "pooleglyph_core_ir_executable_audit.json"
        promotion_path = tmp_path / "pooleglyph_parser_kernel_promotion_receipt.json"
        proof_path = tmp_path / "capability_trap_proof.json"
        encoding_path = tmp_path / "pgb2_trap_encoding.json"
        pooleglyph_source_anchor.write_anchor(anchor, anchor_path)
        bridge = pooleglyph_bridge_manifest.make_bridge_manifest(
            source_anchor_path=anchor_path,
            pooleglyph_path=pooleglyph,
        )
        pooleglyph_bridge_manifest.write_bridge_manifest(bridge, bridge_path)
        receipt = pooleglyph_core_ir_boundary_receipt.make_pooleglyph_core_ir_boundary_receipt(
            bridge_manifest_path=bridge_path,
            pooleglyph_path=pooleglyph,
        )
        pooleglyph_core_ir_boundary_receipt.write_receipt(receipt, receipt_path)
        audit = pooleglyph_core_ir_executable_audit.make_pooleglyph_core_ir_executable_audit(
            core_ir_boundary_receipt_path=receipt_path,
        )
        pooleglyph_core_ir_executable_audit.write_audit(audit, audit_path)
        promotion = pooleglyph_parser_kernel_promotion_receipt.make_pooleglyph_parser_kernel_promotion_receipt(
            core_ir_executable_audit_path=audit_path,
        )
        pooleglyph_parser_kernel_promotion_receipt.write_receipt(promotion, promotion_path)
        matrix = permission_capability_matrix.make_permission_capability_matrix(
            bridge_manifest_path=bridge_path,
            core_ir_boundary_receipt_path=receipt_path,
            core_ir_executable_audit_path=audit_path,
            parser_kernel_promotion_receipt_path=promotion_path,
            pooleglyph_path=pooleglyph,
        )
        fuzz = capability_trap_fuzz.make_capability_trap_fuzz(policy=policy, permission_matrix=matrix)
        proof = capability_traps.make_capability_trap_proof(policy=policy, permission_matrix=matrix, trap_fuzz=fuzz)
        capability_traps.write_proof(proof, proof_path)
        encoding = pgb2_trap_encoding.make_pgb2_trap_encoding(trap_proof_path=proof_path)
        pgb2_trap_encoding.write_encoding(encoding, encoding_path)
        execution = pgb2_trap_execution.make_pgb2_trap_execution(trap_encoding_path=encoding_path)
    schema = load_json(ROOT / "specs" / "pgb2-trap-execution.schema.json")
    if not isinstance(schema, dict):
        return CheckResult("pgb2_trap_execution:validation", False, "schema root is not an object")
    errors = validate_json(execution, schema)
    ok = not errors and execution.get("status") == "pass" and execution.get("summary", {}).get("failed_check_count") == 0
    detail = (
        f"status={execution.get('status')}; executed={execution.get('summary', {}).get('executed_instruction_count')}; "
        f"bytes={execution.get('summary', {}).get('byte_length')}; "
        f"outcomes={execution.get('summary', {}).get('outcome_mismatch_count')}"
    )
    if errors:
        detail = "; ".join(f"{e.path}: {e.message}" for e in errors[:5])
    return CheckResult("pgb2_trap_execution:validation", ok, detail)


def check_pooleglyph_tree(pooleglyph: Path) -> list[CheckResult]:
    required = [
        pooleglyph / "pooleglyph_pgvm.py",
        pooleglyph / "pooleglyph_pgvm_conformance.py",
        pooleglyph / "pooleglyph_source_compiler_tests.py",
        pooleglyph / "pooleglyph_gallery.py",
        pooleglyph / "conformance_cases_v0_1.json",
        pooleglyph / "docs" / "PGVM_BYTECODE_SPEC.md",
        pooleglyph / "docs" / "LANGUAGE_SPEC.md",
    ]
    results: list[CheckResult] = []
    for path in required:
        results.append(
            CheckResult(
                name=f"pooleglyph:{path.name}",
                ok=path.exists(),
                detail=str(path),
            )
        )
    return results


def run_command(name: str, cmd: list[str], cwd: Path, timeout: int) -> CheckResult:
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
    except Exception as exc:  # pragma: no cover - diagnostic path
        return CheckResult(name, False, f"failed to start: {exc}")

    tail = "\n".join(completed.stdout.splitlines()[-6:])
    if completed.returncode == 0:
        return CheckResult(name, True, tail or "ok")
    return CheckResult(name, False, f"exit={completed.returncode}\n{tail}")


def run_pooleglyph_baseline(pooleglyph: Path, full: bool) -> list[CheckResult]:
    if full:
        return [
            run_command(
                "pooleglyph:full_test",
                [str(pooleglyph / "pooleglyph.bat"), "test"],
                pooleglyph,
                timeout=180,
            )
        ]

    return [
        run_command(
            "pooleglyph:pgvm_selftest",
            [sys.executable, str(pooleglyph / "pooleglyph_pgvm.py"), "test"],
            pooleglyph,
            timeout=60,
        ),
        run_command(
            "pooleglyph:conformance",
            [sys.executable, str(pooleglyph / "pooleglyph_pgvm_conformance.py"), "run"],
            pooleglyph,
            timeout=60,
        ),
    ]


def run_pooleos_tests() -> CheckResult:
    return run_command(
        "pooleos:unittest",
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
        ROOT,
        timeout=120,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the PooleOS scaffold and PooleGlyph baseline.")
    parser.add_argument(
        "--pooleglyph",
        type=Path,
        default=pooleglyph_source_anchor.default_pooleglyph_path(workspace_root=WORK_ROOT),
        help="Path to the PooleGlyph checkout. Defaults to ~/PooleGlyph when present, otherwise ../PooleGlyph.",
    )
    parser.add_argument("--full", action="store_true", help="Run the full PooleGlyph local test stack.")
    parser.add_argument("--no-runtime", action="store_true", help="Skip PooleGlyph runtime commands.")
    args = parser.parse_args(argv)

    checks: list[CheckResult] = []
    checks.extend(
        check_required_files(
            [
                ROOT / "README.md",
                ROOT / "docs" / "production-goal-charter.md",
                ROOT / "docs" / "pdc-production-build-plan.md",
                ROOT / "docs" / "publication-boundary.md",
                ROOT / "docs" / "adr-ratification-ceremony.md",
                ROOT / "docs" / "native-toolchain-qualification.md",
                ROOT / "docs" / "hardware-target-and-lab-safety.md",
                ROOT / "docs" / "native-v1-objectives.md",
                ROOT
                / "sources"
                / "requirements"
                / "sha256"
                / "a8c94719faf9428c1f133010ba2603c0270c4e1efd7327af8eab9c8c362abb3d"
                / "PooleOS_From_Scratch_Master_Checklist.md",
                ROOT / "specs" / "pooleos-kernel-charter.md",
                ROOT / "specs" / "pdc-production-roadmap.schema.json",
                ROOT / "specs" / "pooleos-native-checklist-coverage.schema.json",
                ROOT / "specs" / "native-architecture-constitution.json",
                ROOT / "specs" / "native-architecture-constitution.schema.json",
                ROOT / "specs" / "native-architecture-baseline.schema.json",
                ROOT / "specs" / "native-v1-objectives.json",
                ROOT / "specs" / "native-v1-objectives.schema.json",
                ROOT / "specs" / "native-v1-objectives-readiness.schema.json",
                ROOT / "specs" / "adr-ratification-policy.json",
                ROOT / "specs" / "adr-ratification-policy.schema.json",
                ROOT / "specs" / "adr-ratification-manifest.schema.json",
                ROOT / "specs" / "adr-ratification-readiness.schema.json",
                ROOT / "specs" / "adr-ratification-receipt.schema.json",
                ROOT / "specs" / "native-toolchain-lock.json",
                ROOT / "specs" / "native-toolchain-lock.schema.json",
                ROOT / "specs" / "native-target-contract.json",
                ROOT / "specs" / "native-target-contract.schema.json",
                ROOT / "specs" / "native-toolchain-qualification.schema.json",
                ROOT / "specs" / "hardware-support-policy.json",
                ROOT / "specs" / "hardware-support-policy.schema.json",
                ROOT / "specs" / "native-standards-register.json",
                ROOT / "specs" / "native-standards-register.schema.json",
                ROOT / "specs" / "tier1-hardware-target.json",
                ROOT / "specs" / "tier1-hardware-target.schema.json",
                ROOT / "specs" / "tier1-hardware-capture.schema.json",
                ROOT / "specs" / "tier1-hardware-observation.schema.json",
                ROOT / "specs" / "hardware-target-readiness.schema.json",
                ROOT / "specs" / "native-tier0-lock.json",
                ROOT / "specs" / "native-tier0-lock.schema.json",
                ROOT / "specs" / "native-tier0-profile.json",
                ROOT / "specs" / "native-tier0-profile.schema.json",
                ROOT / "specs" / "native-tier0-readiness.schema.json",
                ROOT / "specs" / "native-tier0-launch-receipt.schema.json",
                ROOT / "docs" / "native-tier0-qemu.md",
                ROOT / "specs" / "native-model-toolchain-lock.json",
                ROOT / "specs" / "native-model-toolchain-lock.schema.json",
                ROOT / "specs" / "native-model-contract.json",
                ROOT / "specs" / "native-model-contract.schema.json",
                ROOT / "specs" / "native-model-readiness.schema.json",
                ROOT / "docs" / "native-formal-models.md",
                ROOT / "models" / "tla" / "PooleBootSlots.tla",
                ROOT / "models" / "tla" / "PooleBootSlots.safe.cfg",
                ROOT / "models" / "tla" / "PooleBootSlots.hostile.cfg",
                ROOT / "models" / "tla" / "PooleCapabilities.tla",
                ROOT / "models" / "tla" / "PooleCapabilities.safe.cfg",
                ROOT / "models" / "tla" / "PooleCapabilities.hostile.cfg",
                ROOT / "models" / "tla" / "PooleVirtualMemory.tla",
                ROOT / "models" / "tla" / "PooleVirtualMemory.safe.cfg",
                ROOT / "models" / "tla" / "PooleVirtualMemory.stale_mapping.cfg",
                ROOT / "models" / "tla" / "PooleVirtualMemory.early_reuse.cfg",
                ROOT / "models" / "tla" / "PooleIPC.tla",
                ROOT / "models" / "tla" / "PooleIPC.safe.cfg",
                ROOT / "models" / "tla" / "PooleIPC.unauthorized_call.cfg",
                ROOT / "models" / "tla" / "PooleIPC.token_reuse.cfg",
                ROOT / "models" / "tla" / "PooleIPC.stale_reply.cfg",
                ROOT / "models" / "tla" / "PooleIPC.leaky_teardown.cfg",
                ROOT / "specs" / "native-release-architecture-policy.json",
                ROOT / "specs" / "native-release-architecture-policy.schema.json",
                ROOT / "specs" / "native-release-architecture-report.schema.json",
                ROOT / "tools" / "generate_native_checklist_coverage.py",
                ROOT / "tools" / "generate_native_production_roadmap.py",
                ROOT / "tools" / "generate_native_architecture_baseline.py",
                ROOT / "tools" / "generate_native_v1_objectives_readiness.py",
                ROOT / "tools" / "verify_native_v1_objectives.py",
                ROOT / "tools" / "generate_adr_ratification_readiness.py",
                ROOT / "tools" / "generate_n0_owner_decision_packet.py",
                ROOT / "tools" / "generate_n0_owner_response_receipt.py",
                ROOT / "tools" / "prepare_adr_ratification.py",
                ROOT / "tools" / "verify_adr_ratification.py",
                ROOT / "tools" / "check_native_release_architecture.py",
                ROOT / "tools" / "check_publication_boundary.py",
                ROOT / "tools" / "bootstrap_native_toolchain.ps1",
                ROOT / "tools" / "qualify_native_toolchain.py",
                ROOT / "tools" / "collect_tier1_hardware.ps1",
                ROOT / "tools" / "sanitize_tier1_hardware_capture.py",
                ROOT / "tools" / "generate_hardware_target_readiness.py",
                ROOT / "tools" / "verify_hardware_target.py",
                ROOT / "tools" / "qualify_native_tier0.py",
                ROOT / "tools" / "run_native_tier0.py",
                ROOT / "tools" / "bootstrap_native_models.ps1",
                ROOT / "tools" / "qualify_native_models.py",
                ROOT / "runtime" / "native_binary.py",
                ROOT / "runtime" / "native_v1_objectives.py",
                ROOT / "runtime" / "adr_ratification.py",
                ROOT / "runtime" / "n0_owner_decision_packet.py",
                ROOT / "runtime" / "n0_owner_response.py",
                ROOT / "runtime" / "hardware_target.py",
                ROOT / "runtime" / "native_tier0.py",
                ROOT / "runtime" / "native_models.py",
                ROOT / "security" / "README.md",
                ROOT / "security" / "owner-adr-signers.allowed",
                ROOT / "security" / "revoked-adr-signers",
                ROOT / "native" / "Cargo.toml",
                ROOT / "native" / "Cargo.lock",
                ROOT / "native" / "rust-toolchain.toml",
                ROOT / "native" / ".cargo" / "config.toml",
                ROOT / "native" / "boot" / "Cargo.toml",
                ROOT / "native" / "boot" / "src" / "main.rs",
                ROOT / "native" / "kernel" / "Cargo.toml",
                ROOT / "native" / "kernel" / "src" / "main.rs",
                ROOT / "runs" / "pooleos_native_checklist_coverage.json",
                ROOT / "runs" / "pdc_production_roadmap.json",
                ROOT / "runs" / "native_architecture_baseline.json",
                ROOT / "runs" / "native_v1_objectives_readiness.json",
                ROOT / "runs" / "adr_ratification_readiness.json",
                ROOT / "runs" / "n0_owner_decision_packet.json",
                ROOT / "specs" / "n0-owner-decision-packet.schema.json",
                ROOT / "docs" / "n0-owner-decision-packet.md",
                ROOT / "specs" / "n0-owner-response.json",
                ROOT / "specs" / "n0-owner-response.schema.json",
                ROOT / "specs" / "n0-owner-response-receipt.schema.json",
                ROOT / "runs" / "n0_owner_response_receipt.json",
                ROOT / "docs" / "n0-owner-response-receipt.md",
                ROOT / "runs" / "native_toolchain_qualification.json",
                ROOT / "runs" / "tier1_hardware_observation.json",
                ROOT / "runs" / "hardware_target_readiness.json",
                ROOT / "runs" / "native_tier0_readiness.json",
                ROOT / "runs" / "native_model_readiness.json",
                ROOT / "specs" / "pdc-source-intake.schema.json",
                ROOT / "specs" / "pdc-math-contract.schema.json",
                ROOT / "specs" / "pdc-golden-vectors.schema.json",
                ROOT / "specs" / "pdc-verifier-intake.schema.json",
                ROOT / "specs" / "pdc-verifier-reproduction.schema.json",
                ROOT / "specs" / "pdc-representation-contract.schema.json",
                ROOT / "specs" / "pdc-representation-receipt.schema.json",
                ROOT / "specs" / "pdc-golden-metamorphic-corpus.schema.json",
                ROOT / "specs" / "pdc-golden-metamorphic-receipt.schema.json",
                ROOT / "specs" / "pdc-qp-contract.schema.json",
                ROOT / "specs" / "pdc-qp-receipt.schema.json",
                ROOT / "specs" / "pdc-qp-stability-contract.schema.json",
                ROOT / "specs" / "pdc-qp-stability-receipt.schema.json",
                ROOT / "specs" / "pdc-math-contract-v0.1.md",
                ROOT / "specs" / "pdc-representation-abi-v0.1.md",
                ROOT / "specs" / "pdc-golden-metamorphic-v0.2.md",
                ROOT / "specs" / "pdc-qp-v0.1.md",
                ROOT / "specs" / "pdc-qp-stability-v0.1.md",
                ROOT / "specs" / "claim-lanes.schema.json",
                ROOT / "specs" / "channel-trace.schema.json",
                ROOT / "specs" / "pgb2-bundle.schema.json",
                ROOT / "specs" / "signed-membrane.schema.json",
                ROOT / "specs" / "replay-proof.schema.json",
                ROOT / "specs" / "boot-log.schema.json",
                ROOT / "specs" / "lab-image-manifest.schema.json",
                ROOT / "specs" / "boot-trap-bundle-manifest.schema.json",
                ROOT / "specs" / "qemu-shared-folder-contract.schema.json",
                ROOT / "specs" / "lab-guest-autostart.schema.json",
                ROOT / "specs" / "qemu-boot-evidence.schema.json",
                ROOT / "specs" / "qemu-captured-boot-preflight.schema.json",
                ROOT / "specs" / "qemu-captured-boot-launch-bundle.schema.json",
                ROOT / "specs" / "qemu-captured-boot-dry-run-checklist.schema.json",
                ROOT / "specs" / "qemu-boot-marker-contract.schema.json",
                ROOT / "specs" / "qemu-boot-marker-image-binding.schema.json",
                ROOT / "specs" / "rootfs-content-manifest.schema.json",
                ROOT / "specs" / "rootfs-extraction-handoff.schema.json",
                ROOT / "specs" / "rootfs-extraction-receipt.schema.json",
                ROOT / "specs" / "qemu-captured-boot-receipt.schema.json",
                ROOT / "specs" / "qemu-captured-boot-readiness.schema.json",
                ROOT / "specs" / "kernel-boot-handoff.schema.json",
                ROOT / "specs" / "kernel-pgvm2-loader-output.schema.json",
                ROOT / "specs" / "lab-kernel-transcript-export-receipt.schema.json",
                ROOT / "specs" / "kernel-pgvm2-loader-evidence.schema.json",
                ROOT / "specs" / "host-preflight.schema.json",
                ROOT / "specs" / "buildroot-probe.schema.json",
                ROOT / "specs" / "buildroot-configure.schema.json",
                ROOT / "specs" / "buildroot-build.schema.json",
                ROOT / "specs" / "wsl-prerequisites.schema.json",
                ROOT / "specs" / "operator-action-request.schema.json",
                ROOT / "specs" / "operator-action-receipt.schema.json",
                ROOT / "specs" / "host-prep-note.schema.json",
                ROOT / "specs" / "isolation-proof.schema.json",
                ROOT / "specs" / "capability-trap-proof.schema.json",
                ROOT / "specs" / "capability-trap-fuzz.schema.json",
                ROOT / "specs" / "pgb2-trap-encoding.schema.json",
                ROOT / "specs" / "pgb2-trap-execution.schema.json",
                ROOT / "specs" / "pgb2-trap-abi-boundary-receipt.schema.json",
                ROOT / "specs" / "pooleglyph-source-anchor.schema.json",
                ROOT / "specs" / "pooleglyph-bridge-manifest.schema.json",
                ROOT / "specs" / "pooleglyph-core-ir-boundary-receipt.schema.json",
                ROOT / "specs" / "pooleglyph-core-ir-executable-audit.schema.json",
                ROOT / "specs" / "pooleglyph-parser-kernel-promotion-receipt.schema.json",
                ROOT / "specs" / "permission-capability-matrix.schema.json",
                ROOT / "specs" / "pgb2-draft.md",
            ]
        )
    )
    checks.append(check_native_architecture_plan())
    checks.append(check_native_architecture_baseline())
    checks.append(check_native_v1_objectives_readiness())
    checks.append(check_adr_ratification_readiness())
    checks.append(check_n0_owner_decision_packet())
    checks.append(check_n0_owner_response_receipt())
    checks.append(check_native_toolchain_qualification())
    checks.append(check_hardware_target_readiness())
    checks.append(check_native_tier0_readiness())
    checks.append(check_native_model_readiness())
    checks.append(check_publication_boundary())
    checks.extend(check_claim_schema())
    checks.extend(check_claim_examples())
    checks.extend(check_trace_schema())
    checks.append(check_generated_trace_validation())
    checks.extend(check_pdc_math_artifacts())
    checks.append(check_generated_bundle_validation())
    checks.append(check_generated_bundle_trap_evidence_validation())
    checks.append(check_generated_boot_trap_bundle_manifest_validation())
    checks.append(check_generated_qemu_shared_folder_contract_validation())
    checks.append(check_generated_pgb2_trap_abi_boundary_receipt_validation())
    checks.append(check_generated_lab_guest_autostart_validation())
    checks.append(check_generated_qemu_boot_evidence_validation())
    checks.append(check_generated_qemu_captured_boot_preflight_validation())
    checks.append(check_generated_qemu_captured_boot_launch_bundle_validation())
    checks.append(check_generated_qemu_captured_boot_dry_run_checklist_validation())
    checks.append(check_generated_qemu_boot_marker_contract_validation())
    checks.append(check_generated_qemu_boot_marker_image_binding_validation())
    checks.append(check_generated_rootfs_content_manifest_validation())
    checks.append(check_generated_rootfs_extraction_handoff_validation())
    checks.append(check_generated_rootfs_extraction_receipt_validation())
    checks.append(check_generated_qemu_captured_boot_receipt_validation())
    checks.append(check_generated_qemu_captured_boot_readiness_validation())
    checks.append(check_generated_kernel_boot_handoff_validation())
    checks.append(check_generated_kernel_pgvm2_loader_output_validation())
    checks.append(check_generated_lab_kernel_transcript_export_receipt_validation())
    checks.append(check_generated_kernel_pgvm2_loader_evidence_validation())
    checks.append(check_generated_isolation_validation())
    checks.append(check_generated_capability_trap_validation())
    checks.append(check_generated_pooleglyph_bridge_validation(args.pooleglyph))
    checks.append(check_generated_pooleglyph_core_ir_boundary_receipt_validation(args.pooleglyph))
    checks.append(check_generated_pooleglyph_core_ir_executable_audit_validation(args.pooleglyph))
    checks.append(check_generated_pooleglyph_parser_kernel_promotion_receipt_validation(args.pooleglyph))
    checks.append(check_generated_permission_matrix_validation(args.pooleglyph))
    checks.append(check_generated_capability_trap_fuzz_validation(args.pooleglyph))
    checks.append(check_generated_pgb2_trap_encoding_validation(args.pooleglyph))
    checks.append(check_generated_pgb2_trap_execution_validation(args.pooleglyph))
    checks.append(run_pooleos_tests())
    checks.extend(check_pooleglyph_tree(args.pooleglyph))
    if not args.no_runtime:
        checks.extend(run_pooleglyph_baseline(args.pooleglyph, args.full))

    for check in checks:
        print_result(check)

    failed = [check for check in checks if not check.ok]
    print(json.dumps({"ok": not failed, "total": len(checks), "failed": len(failed)}, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
