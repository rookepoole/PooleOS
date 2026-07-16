"""Source locks and independent receipt generation for PDC-QP-STABILITY-0.1."""

from __future__ import annotations

import hashlib
import json
import math
import platform
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

import numpy as np

from runtime import pdc_qp as qp
from runtime import pdc_qp_stability as stability
from runtime import pdc_verifier_intake


CONTRACT_VERSION = stability.CONTRACT_VERSION
RUNNER_PACKAGE_SHA256 = "C5DE80C53F8E7F475D9D7D3CD4C63F62EC086BDFCC2A8D806762B069E6349720"
RESULT_PACKAGE_SHA256 = "5EDAC791B9D56FC74BFA4F595569BE9D654D8C06B12548DF56E3582B0A5484F9"
RUNNER_PACKAGE_RELATIVE_PATH = f"sources/pdc/qp_stability/sha256/{RUNNER_PACKAGE_SHA256.lower()}.zip"
RESULT_PACKAGE_RELATIVE_PATH = f"sources/pdc/qp_stability/sha256/{RESULT_PACKAGE_SHA256.lower()}.zip"
RESULT_MEMBER = "package/poole_qp_v5_5_full_results.json"
SCORE_ABS_TOLERANCE = 2e-12
SUMMARY_ABS_TOLERANCE = 2e-12

RUNNER_MEMBERS = (
    (
        "runner",
        "poole_qp_v5_4_verification_runner/poole_qp_v5_4_colab_verification_runner.py",
        "3A608BA55821C10B7D60002B2966A411DC79E1B1B62D86238A1E68AB094BAFED",
        38633,
        "Source-compatible field generators, channel rates, calibration, and v5.4 verification logic.",
    ),
    (
        "runner_readme",
        "poole_qp_v5_4_verification_runner/README.md",
        "AAC8C2A810C5851897498ED8CFB65E055E3C218F7A1C6DBE68D877CAF60C8C52",
        625,
        "Runner scope and claim boundary.",
    ),
)
RESULT_MEMBERS = (
    ("readme", "package/README_QP_AMENDED_v5_5.md", "1C5C4F53E9B7816940D02079175A17FDBA01EB40B4AF53FC48AFE0FC68B9A348", 1097, "Package instructions and version scope."),
    ("paper_pdf", "package/poole_qp_capture_math_v3_AMENDED_v5_5.pdf", "55C4B82CDC243B69C91AFE91E1273BDCE834C8B948EB1072F3B6ED12FCF3A83C", 654540, "Rendered v5.5 benchmark authority."),
    ("paper_tex", "package/poole_qp_capture_math_v3_AMENDED_v5_5.tex", "F47652F6797728224F4F299469A94EC37F8103B358C42B0B502555928A6945EB", 39446, "Machine-readable v5.5 manuscript formulas."),
    ("decomposition_tex", "package/poole_qp_v5_5_decomposed_capture_amendment.tex", "538DB0CB99B3D932119BC1591C3198940890610911626D24AD7984344285C51F", 1688, "Decomposed robust-score and geometry-share definitions."),
    ("full_results", RESULT_MEMBER, "8299A8E8A7E12793C47331EDF33C72DD08BAE9074A95AE3C1876DFD4760D768C", 577369, "All 550 published per-sample channel and score rows."),
    ("verification_report", "package/poole_qp_v5_5_verification_report.json", "05472EFD73791113240D7AE4637A70EE6E9BB611D436DB29486267E70991A7F2", 1332, "Published finite pass/fail summary."),
    ("summary", "package/poole_qp_v5_5_summary.csv", "580A737EC5A9E7D807DC6EBEF8234BFCC49CA9223E96DC424C203DF079BFD12B", 10528, "Published class-level statistics."),
    ("paired_controls", "package/poole_qp_v5_5_paired_shuffled_controls.csv", "9A1244717322FDD4DA71D4F2E56DE088305BFDD4724CE63335993C2A3E88B931", 1355, "Published structured/shuffled class pairs."),
    ("shuffle_audit", "package/poole_qp_v5_5_shuffle_audit.csv", "E89CD805120B6C249A30E90A00483C3E1FFEEF60848168F1B5A4844A6DD71DE9", 10650, "Published exact-density shuffle audit."),
    ("active_audit", "package/poole_qp_v5_5_active_count_audit.csv", "64F985EFA796461BF5154BD6F139A80AECA00C8ADB1A9E4FD82A9754FCCC30A6", 9790, "Published exact active-count audit."),
    ("single_channel", "package/poole_qp_v5_5_single_channel_effects.csv", "9F42918F1504573312CA95C5AB0C9B0402E77736EF9A37CE99BD20398D7AD144", 9014, "Published channel-level effects."),
)


class PdcQpStabilityEvidenceError(ValueError):
    """Raised when a source, binding, reproduction, or stability check fails."""


def _created_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PdcQpStabilityEvidenceError(f"artifact root must be an object: {path}")
    return value


def _relative(path: Path, workspace: Path) -> str:
    try:
        return path.resolve().relative_to(workspace.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _member_records(path: Path, expected_members: Sequence[tuple[str, str, str, int, str]]) -> list[dict[str, object]]:
    records = []
    with ZipFile(path) as archive:
        names = set(archive.namelist())
        for member_id, member_path, expected_hash, expected_size, role in expected_members:
            if member_path not in names:
                raise PdcQpStabilityEvidenceError(f"source package is missing {member_path}")
            payload = archive.read(member_path)
            actual_hash = hashlib.sha256(payload).hexdigest().upper()
            if actual_hash != expected_hash or len(payload) != expected_size:
                raise PdcQpStabilityEvidenceError(f"source member substitution detected: {member_path}")
            records.append(
                {
                    "id": member_id,
                    "path": member_path,
                    "sha256": actual_hash,
                    "size_bytes": len(payload),
                    "role": role,
                }
            )
    return records


def _package_record(
    *, workspace: Path, path: Path, expected_hash: str, version: str, role: str, members: Sequence[tuple[str, str, str, int, str]]
) -> dict[str, object]:
    if not path.is_file() or pdc_verifier_intake.sha256_file(path) != expected_hash:
        raise PdcQpStabilityEvidenceError(f"locked Q/P package substitution detected: {path}")
    return {
        "version": version,
        "stored_path": _relative(path, workspace),
        "sha256": expected_hash,
        "size_bytes": path.stat().st_size,
        "role": role,
        "members": _member_records(path, members),
    }


def make_stability_contract(
    *,
    workspace: Path,
    qp_contract_path: Path,
    qp_receipt_path: Path,
    runner_package_path: Path | None = None,
    result_package_path: Path | None = None,
) -> dict[str, object]:
    qp_contract = _load_json(qp_contract_path)
    qp_receipt = _load_json(qp_receipt_path)
    if qp_contract.get("artifact_kind") != "pdc_qp_contract" or qp_contract.get("status") != "frozen_reference_contract":
        raise PdcQpStabilityEvidenceError("stability contract requires the frozen PDC-QP-0.1 contract")
    if qp_receipt.get("artifact_kind") != "pdc_qp_receipt" or qp_receipt.get("status") != "pass":
        raise PdcQpStabilityEvidenceError("stability contract requires the passing PDC-QP-0.1 receipt")
    if qp_receipt["bindings"]["contract_sha256"] != pdc_verifier_intake.sha256_file(qp_contract_path):
        raise PdcQpStabilityEvidenceError("Q/P receipt is not bound to the selected Q/P contract")
    runner_path = runner_package_path or workspace / RUNNER_PACKAGE_RELATIVE_PATH
    result_path = result_package_path or workspace / RESULT_PACKAGE_RELATIVE_PATH
    packages = [
        _package_record(
            workspace=workspace,
            path=runner_path,
            expected_hash=RUNNER_PACKAGE_SHA256,
            version="PooleQ/P v5.4 paper-locked verification runner",
            role="Field-generation and same-density control source authority.",
            members=RUNNER_MEMBERS,
        ),
        _package_record(
            workspace=workspace,
            path=result_path,
            expected_hash=RESULT_PACKAGE_SHA256,
            version="PooleQ/P amended v5.5 result package",
            role="Decomposed-score formulas and published field-level benchmark authority.",
            members=RESULT_MEMBERS,
        ),
    ]
    implementation_path = workspace / "runtime" / "pdc_qp_stability.py"
    return {
        "schema_version": "0.1",
        "artifact_kind": "pdc_qp_stability_contract",
        "contract_version": CONTRACT_VERSION,
        "created_utc": _created_utc(),
        "status": "frozen_benchmark_protocol",
        "bindings": {
            "reference_implementation_path": _relative(implementation_path, workspace),
            "reference_implementation_sha256": pdc_verifier_intake.sha256_file(implementation_path),
            "qp_contract_path": _relative(qp_contract_path, workspace),
            "qp_contract_sha256": pdc_verifier_intake.sha256_file(qp_contract_path),
            "qp_receipt_path": _relative(qp_receipt_path, workspace),
            "qp_receipt_sha256": pdc_verifier_intake.sha256_file(qp_receipt_path),
            "source_packages": packages,
        },
        "benchmark_protocol": {
            "lattice_shape": [stability.LATTICE_SIZE] * 3,
            "boundary_mode": "periodic",
            "active_probability": stability.ACTIVE_PROBABILITY,
            "target_active_count": stability.TARGET_ACTIVE_COUNT,
            "sample_count_per_raw_class": stability.SAMPLE_COUNT,
            "seed": stability.BENCHMARK_SEED,
            "raw_classes": list(stability.RAW_CLASS_ORDER),
            "structured_classes": list(stability.STRUCTURED_CLASS_ORDER),
            "control_classes": list(stability.CONTROL_CLASS_ORDER),
            "channel_order": list(stability.CHANNEL_ORDER),
            "channel_groups": {name: list(channels) for name, channels in stability.GROUP_CHANNELS.items()},
            "combined_channels": list(stability.COMBINED_CHANNELS),
            "robust_z_scale": stability.ROBUST_Z_SCALE,
            "std_floor_multiplier": stability.STD_FLOOR_MULTIPLIER,
            "null_like_R_threshold": stability.NULL_LIKE_THRESHOLD,
            "score_epsilon": qp.DEFAULT_EPSILON,
            "score_abs_tolerance": SCORE_ABS_TOLERANCE,
            "summary_abs_tolerance": SUMMARY_ABS_TOLERANCE,
            "poole_active_excluded_from_combined_score": True,
        },
        "perturbation_protocol": {
            "type": "exact-density active/inactive index swaps",
            "swap_levels": list(stability.PERTURBATION_SWAP_LEVELS),
            "field_scope": "all 550 freshly regenerated benchmark fields",
            "seed_derivation": "first 64 bits of SHA-256(class:sample:swaps:PDC-QP-STABILITY-0.1), then Python MT19937 sampling",
            "hamming_count": "exactly two changed voxels per swap",
            "structured_abs_R_envelope": "0.06 + 125*hamming_fraction",
            "control_abs_R_envelope": "0.08 + 125*hamming_fraction",
            "structured_relative_R_envelope": "0.01 + 25*hamming_fraction",
            "structured_spectrum_l1_envelope": "0.03 + 50*hamming_fraction",
            "classification_gate": "structured remains R_C>=2; controls remain R_C<2",
            "dominant_label_retention_is_diagnostic_not_gate": True,
        },
        "claim_boundary": [
            "This is a deterministic finite benchmark over synthetic measured binary fields, not an all-distribution theorem.",
            "Same-density shuffling and density-preserving swaps isolate local geometry from active-count changes only within the declared protocol.",
            "The robustness envelopes are predeclared empirical acceptance bounds for this corpus, not universal Lipschitz constants.",
            "PooleQ/P remains a classical measurement-side transform and does not reconstruct an unknown quantum state.",
            "No decoder, hardware, kernel, safety, physical, or production-ISO claim follows from this benchmark.",
        ],
    }


def _published_results(result_package_path: Path) -> dict[str, object]:
    with ZipFile(result_package_path) as archive:
        payload = archive.read(RESULT_MEMBER)
    result = json.loads(payload.decode("utf-8"))
    if not isinstance(result, dict):
        raise PdcQpStabilityEvidenceError("published v5.5 result root is not an object")
    return result


def _compare_numeric(left: object, right: object, tolerance: float) -> float | None:
    if isinstance(left, bool) or isinstance(right, bool) or not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
        return None
    left_value = float(left)
    right_value = float(right)
    if not math.isfinite(left_value) or not math.isfinite(right_value):
        raise PdcQpStabilityEvidenceError("nonfinite value in benchmark comparison")
    return abs(left_value - right_value) if abs(left_value - right_value) > tolerance else 0.0


def _benchmark_reproduction(published: Mapping[str, object]) -> tuple[dict[str, object], dict[str, list[np.ndarray]], dict[str, list[dict[str, float]]]]:
    expected_params = {
        "L": stability.LATTICE_SIZE,
        "p": stability.ACTIVE_PROBABILITY,
        "M": stability.SAMPLE_COUNT,
        "seed": stability.BENCHMARK_SEED,
        "target_active_count": stability.TARGET_ACTIVE_COUNT,
    }
    params = published.get("params")
    if not isinstance(params, Mapping) or any(params.get(key) != value for key, value in expected_params.items()):
        raise PdcQpStabilityEvidenceError("published v5.5 benchmark parameters do not match the frozen protocol")
    fields = stability.generate_benchmark_fields()
    published_rows = published.get("scored_rows")
    if not isinstance(published_rows, Mapping) or set(published_rows) != set(stability.SCORED_CLASS_ORDER):
        raise PdcQpStabilityEvidenceError("published scored-row classes do not match the protocol")
    fresh_rates: dict[str, list[dict[str, float]]] = {}
    field_records = []
    oracle_mismatches = 0
    published_rate_mismatches = 0
    max_oracle_rate_error = 0.0
    max_published_rate_error = 0.0
    neighbor_mismatch_voxels = 0
    for class_name in stability.SCORED_CLASS_ORDER:
        rows = published_rows[class_name]
        if not isinstance(rows, list) or len(rows) != stability.SAMPLE_COUNT:
            raise PdcQpStabilityEvidenceError(f"published class {class_name} does not contain 50 rows")
        class_rates = []
        for sample_index, field in enumerate(fields[class_name]):
            roll_counts = stability.neighbor_count_roll(field)
            indexed_counts = stability.neighbor_count_indexed(field)
            count_mismatches = int(np.count_nonzero(roll_counts != indexed_counts))
            neighbor_mismatch_voxels += count_mismatches
            roll_rates = stability.channel_rates_from_counts(field, roll_counts)
            indexed_rates = stability.channel_rates_from_counts(field, indexed_counts)
            for channel in stability.CHANNEL_ORDER:
                oracle_error = abs(roll_rates[channel] - indexed_rates[channel])
                published_error = abs(roll_rates[channel] - float(rows[sample_index][channel]))
                max_oracle_rate_error = max(max_oracle_rate_error, oracle_error)
                max_published_rate_error = max(max_published_rate_error, published_error)
                oracle_mismatches += int(oracle_error != 0.0)
                published_rate_mismatches += int(published_error != 0.0)
            active_count = int(field.sum())
            class_rates.append(roll_rates)
            field_records.append(
                {
                    "class": class_name,
                    "sample": sample_index,
                    "field_sha256": stability.field_sha256(field),
                    "active_count": active_count,
                    "active_count_pass": active_count == stability.TARGET_ACTIVE_COUNT,
                    "channel_row_sha256": pdc_verifier_intake.sha256_json(roll_rates),
                    "neighbor_oracle_match": count_mismatches == 0,
                }
            )
        fresh_rates[class_name] = class_rates
    if neighbor_mismatch_voxels or oracle_mismatches or published_rate_mismatches:
        raise PdcQpStabilityEvidenceError("fresh field/channel reproduction mismatch")
    if any(not record["active_count_pass"] for record in field_records):
        raise PdcQpStabilityEvidenceError("fresh benchmark field violates the exact-density gate")

    fresh_mu, fresh_sd = stability.null_calibration(fresh_rates["iid_null"], extent=stability.LATTICE_SIZE)
    published_mu = published.get("null_mu")
    published_sd = published.get("null_sd")
    if not isinstance(published_mu, Mapping) or not isinstance(published_sd, Mapping):
        raise PdcQpStabilityEvidenceError("published null calibration is malformed")
    max_calibration_error = 0.0
    calibration_mismatches = 0
    for channel in stability.COMBINED_CHANNELS:
        for fresh, expected in ((fresh_mu[channel], published_mu[channel]), (fresh_sd[channel], published_sd[channel])):
            error = abs(float(fresh) - float(expected))
            max_calibration_error = max(max_calibration_error, error)
            calibration_mismatches += int(error > 2e-15)

    scored_rows: dict[str, list[dict[str, float]]] = {}
    score_mismatches = 0
    max_score_error = 0.0
    score_fields = ("Z_birth", "R_birth", "Z_high_support", "R_high_support", "Z_strain", "R_strain", "Z_combined", "R_combined")
    for class_name in stability.SCORED_CLASS_ORDER:
        class_rows = []
        for sample_index, rates in enumerate(fresh_rates[class_name]):
            scored = stability.score_row(rates, fresh_mu, fresh_sd)
            for field in score_fields:
                error = abs(scored[field] - float(published_rows[class_name][sample_index][field]))
                max_score_error = max(max_score_error, error)
                score_mismatches += int(error > SCORE_ABS_TOLERANCE)
            class_rows.append(scored)
        scored_rows[class_name] = class_rows

    fresh_summaries = [stability.class_summary(name, scored_rows[name]) for name in stability.SUMMARY_CLASS_ORDER]
    published_summaries = published.get("summary")
    if not isinstance(published_summaries, list) or len(published_summaries) != len(fresh_summaries):
        raise PdcQpStabilityEvidenceError("published class summary is malformed")
    summary_checks = 0
    summary_mismatches = 0
    max_summary_error = 0.0
    for fresh, expected in zip(fresh_summaries, published_summaries, strict=True):
        if fresh.keys() != expected.keys():
            raise PdcQpStabilityEvidenceError(f"summary field mismatch for {fresh['class']}")
        for field, value in fresh.items():
            summary_checks += 1
            error = _compare_numeric(value, expected[field], SUMMARY_ABS_TOLERANCE)
            if error is None:
                summary_mismatches += int(value != expected[field])
            else:
                max_summary_error = max(max_summary_error, error)
                summary_mismatches += int(error > 0.0)

    controls = [row for name in stability.CONTROL_CLASS_ORDER for row in scored_rows[name]]
    structured = [row for name in stability.STRUCTURED_CLASS_ORDER for row in scored_rows[name]]
    max_control = max(row["R_combined"] for row in controls)
    min_structured = min(row["R_combined"] for row in structured)
    pair_details = []
    for class_name in stability.STRUCTURED_CLASS_ORDER:
        control_name = f"{class_name}_shuffled"
        structured_mean = float(np.mean([row["R_combined"] for row in scored_rows[class_name]]))
        control_mean = float(np.mean([row["R_combined"] for row in scored_rows[control_name]]))
        pair_details.append(
            {
                "class": class_name,
                "control": control_name,
                "structured_R_combined": structured_mean,
                "shuffled_R_combined": control_mean,
                "ok": structured_mean > control_mean,
            }
        )
    verification = {
        "same_density_ok": all(record["active_count_pass"] for record in field_records),
        "active_count_audit_ok": all(record["active_count_pass"] for record in field_records),
        "shuffle_audit_ok": all(record["active_count_pass"] for record in field_records if str(record["class"]).endswith("_shuffled")),
        "clean_robust_separation": min_structured > max_control,
        "structured_beats_shuffled": all(pair["ok"] for pair in pair_details),
        "max_control_R_combined": max_control,
        "min_structured_R_combined": min_structured,
        "pair_details": pair_details,
    }
    verification["overall_pass"] = all(
        verification[key]
        for key in ("same_density_ok", "active_count_audit_ok", "shuffle_audit_ok", "clean_robust_separation", "structured_beats_shuffled")
    )
    published_verification = published.get("verification")
    if not isinstance(published_verification, Mapping):
        raise PdcQpStabilityEvidenceError("published verification summary is malformed")
    verification_mismatches = 0
    max_verification_error = 0.0
    for field, value in verification.items():
        expected = published_verification[field]
        if field == "pair_details":
            if not isinstance(expected, list) or len(value) != len(expected):
                verification_mismatches += 1
                continue
            for fresh_pair, expected_pair in zip(value, expected, strict=True):
                if fresh_pair.keys() != expected_pair.keys():
                    verification_mismatches += 1
                    continue
                for pair_field, pair_value in fresh_pair.items():
                    pair_error = _compare_numeric(pair_value, expected_pair[pair_field], SUMMARY_ABS_TOLERANCE)
                    if pair_error is None:
                        verification_mismatches += int(pair_value != expected_pair[pair_field])
                    else:
                        max_verification_error = max(max_verification_error, pair_error)
                        verification_mismatches += int(pair_error > 0.0)
            continue
        error = _compare_numeric(value, expected, SUMMARY_ABS_TOLERANCE)
        if error is None:
            verification_mismatches += int(value != expected)
        else:
            max_verification_error = max(max_verification_error, error)
            verification_mismatches += int(error > 0.0)

    total_mismatches = calibration_mismatches + score_mismatches + summary_mismatches + verification_mismatches
    if total_mismatches:
        raise PdcQpStabilityEvidenceError(
            f"v5.5 score/summary reproduction has {total_mismatches} mismatches; max score error={max_score_error}"
        )
    result = {
        "parameters_match": True,
        "class_count": len(fields),
        "field_count": len(field_records),
        "active_count_check_count": len(field_records),
        "neighbor_oracle_field_count": len(field_records),
        "neighbor_oracle_voxel_count": len(field_records) * stability.LATTICE_SIZE**3,
        "neighbor_mismatch_voxel_count": 0,
        "channel_rate_oracle_check_count": len(field_records) * len(stability.CHANNEL_ORDER),
        "published_channel_rate_check_count": len(field_records) * len(stability.CHANNEL_ORDER),
        "calibration_check_count": len(stability.COMBINED_CHANNELS) * 2,
        "score_check_count": len(field_records) * len(score_fields),
        "summary_check_count": summary_checks,
        "verification_check_count": len(verification) - 1 + len(pair_details),
        "max_oracle_rate_abs_error": max_oracle_rate_error,
        "max_published_rate_abs_error": max_published_rate_error,
        "max_calibration_abs_error": max_calibration_error,
        "max_score_abs_error": max_score_error,
        "max_summary_abs_error": max_summary_error,
        "max_verification_abs_error": max_verification_error,
        "verification": verification,
        "field_records": field_records,
        "field_record_set_sha256": pdc_verifier_intake.sha256_json(field_records),
        "fresh_summary_sha256": pdc_verifier_intake.sha256_json(fresh_summaries),
        "fresh_scored_row_sha256": pdc_verifier_intake.sha256_json(scored_rows),
        "mismatch_count": 0,
    }
    return result, fields, fresh_rates


def _perturbation_evidence(
    fields: Mapping[str, Sequence[np.ndarray]], fresh_rates: Mapping[str, Sequence[Mapping[str, float]]], published: Mapping[str, object]
) -> dict[str, object]:
    means = published["null_mu"]
    deviations = published["null_sd"]
    if not isinstance(means, Mapping) or not isinstance(deviations, Mapping):
        raise PdcQpStabilityEvidenceError("published calibration is malformed")
    records = []
    oracle_mismatch_voxels = 0
    for class_name in stability.SCORED_CLASS_ORDER:
        is_control = class_name in stability.CONTROL_CLASS_ORDER
        for sample_index, field in enumerate(fields[class_name]):
            base_rates = fresh_rates[class_name][sample_index]
            base_signature = qp.geometry_signature(base_rates, means, deviations)
            base_spectrum = None
            if not is_control:
                base_spectrum = stability.geometry_spectrum(base_rates, means, deviations)
            for swaps in stability.PERTURBATION_SWAP_LEVELS:
                perturbed = stability.deterministic_density_swap(
                    field, class_name=class_name, sample_index=sample_index, swaps=swaps
                )
                roll_counts = stability.neighbor_count_roll(perturbed)
                indexed_counts = stability.neighbor_count_indexed(perturbed)
                count_mismatch = int(np.count_nonzero(roll_counts != indexed_counts))
                oracle_mismatch_voxels += count_mismatch
                rates = stability.channel_rates_from_counts(perturbed, roll_counts)
                oracle_rates = stability.channel_rates_from_counts(perturbed, indexed_counts)
                oracle_rate_match = all(rates[channel] == oracle_rates[channel] for channel in stability.CHANNEL_ORDER)
                signature = qp.geometry_signature(rates, means, deviations)
                hamming_count = int(np.count_nonzero(field != perturbed))
                hamming_fraction = hamming_count / field.size
                tolerances = stability.stability_tolerances(hamming_fraction=hamming_fraction, control=is_control)
                absolute_drift = abs(signature.combined - base_signature.combined)
                relative_drift = absolute_drift / max(base_signature.combined, qp.DEFAULT_EPSILON)
                spectrum_l1 = None
                dominant_retained = None
                if is_control:
                    classification_pass = base_signature.combined < stability.NULL_LIKE_THRESHOLD and signature.combined < stability.NULL_LIKE_THRESHOLD
                    spectrum_pass = True
                else:
                    perturbed_spectrum = stability.geometry_spectrum(rates, means, deviations)
                    assert base_spectrum is not None
                    spectrum_l1 = math.fsum(
                        abs(float(base_spectrum["shares"][key]) - float(perturbed_spectrum["shares"][key]))
                        for key in ("B", "H", "psi")
                    )
                    dominant_retained = max(base_spectrum["shares"], key=base_spectrum["shares"].__getitem__) == max(
                        perturbed_spectrum["shares"], key=perturbed_spectrum["shares"].__getitem__
                    )
                    classification_pass = base_signature.combined >= stability.NULL_LIKE_THRESHOLD and signature.combined >= stability.NULL_LIKE_THRESHOLD
                    spectrum_pass = spectrum_l1 <= float(tolerances["max_spectrum_l1_drift"])
                absolute_pass = absolute_drift <= float(tolerances["max_abs_R_drift"])
                relative_pass = True if is_control else relative_drift <= float(tolerances["max_relative_R_drift"])
                density_pass = int(field.sum()) == int(perturbed.sum()) == stability.TARGET_ACTIVE_COUNT
                hamming_pass = hamming_count == 2 * swaps
                passed = all(
                    (count_mismatch == 0, oracle_rate_match, density_pass, hamming_pass, classification_pass, absolute_pass, relative_pass, spectrum_pass)
                )
                records.append(
                    {
                        "class": class_name,
                        "sample": sample_index,
                        "scope": "control" if is_control else "structured",
                        "swaps": swaps,
                        "base_field_sha256": stability.field_sha256(field),
                        "perturbed_field_sha256": stability.field_sha256(perturbed),
                        "active_count": int(perturbed.sum()),
                        "hamming_count": hamming_count,
                        "hamming_fraction": hamming_fraction,
                        "base_R_combined": base_signature.combined,
                        "perturbed_R_combined": signature.combined,
                        "absolute_R_drift": absolute_drift,
                        "relative_R_drift": relative_drift,
                        "spectrum_l1_drift": spectrum_l1,
                        "dominant_label_retained": dominant_retained,
                        "tolerances": tolerances,
                        "density_pass": density_pass,
                        "hamming_pass": hamming_pass,
                        "independent_oracle_pass": count_mismatch == 0 and oracle_rate_match,
                        "classification_pass": classification_pass,
                        "absolute_R_bound_pass": absolute_pass,
                        "relative_R_bound_pass": relative_pass,
                        "spectrum_bound_pass": spectrum_pass,
                        "passed": passed,
                    }
                )
    failed = [record for record in records if not record["passed"]]
    if failed or oracle_mismatch_voxels:
        raise PdcQpStabilityEvidenceError(f"controlled perturbation checks failed: {failed[:3]}")
    level_summaries = []
    for scope in ("structured", "control"):
        for swaps in stability.PERTURBATION_SWAP_LEVELS:
            selected = [record for record in records if record["scope"] == scope and record["swaps"] == swaps]
            spectrum_values = [float(record["spectrum_l1_drift"]) for record in selected if record["spectrum_l1_drift"] is not None]
            retained = [bool(record["dominant_label_retained"]) for record in selected if record["dominant_label_retained"] is not None]
            level_summaries.append(
                {
                    "scope": scope,
                    "swaps": swaps,
                    "case_count": len(selected),
                    "max_absolute_R_drift": max(float(record["absolute_R_drift"]) for record in selected),
                    "max_relative_R_drift": max(float(record["relative_R_drift"]) for record in selected),
                    "max_spectrum_l1_drift": max(spectrum_values) if spectrum_values else None,
                    "minimum_perturbed_R": min(float(record["perturbed_R_combined"]) for record in selected),
                    "maximum_perturbed_R": max(float(record["perturbed_R_combined"]) for record in selected),
                    "dominant_label_retention_rate": (sum(retained) / len(retained)) if retained else None,
                    "passed_count": sum(bool(record["passed"]) for record in selected),
                    "mismatch_count": 0,
                }
            )
    return {
        "records": records,
        "level_summaries": level_summaries,
        "record_set_sha256": pdc_verifier_intake.sha256_json(records),
        "summary_sha256": pdc_verifier_intake.sha256_json(level_summaries),
        "summary": {
            "field_count": sum(len(values) for values in fields.values()),
            "swap_level_count": len(stability.PERTURBATION_SWAP_LEVELS),
            "case_count": len(records),
            "structured_case_count": sum(record["scope"] == "structured" for record in records),
            "control_case_count": sum(record["scope"] == "control" for record in records),
            "density_check_count": len(records),
            "hamming_check_count": len(records),
            "independent_oracle_field_count": len(records),
            "classification_check_count": len(records),
            "absolute_R_bound_check_count": len(records),
            "relative_R_bound_check_count": sum(record["scope"] == "structured" for record in records),
            "spectrum_bound_check_count": sum(record["scope"] == "structured" for record in records),
            "passed_count": len(records),
            "mismatch_count": 0,
        },
    }


def _negative_checks() -> list[dict[str, object]]:
    valid = np.zeros((3, 3, 3), dtype=np.uint8)
    valid[0, 0, 0] = 1
    checks: tuple[tuple[str, Callable[[], object], type[Exception]], ...] = (
        ("reject-nonarray-field", lambda: stability.neighbor_count_roll([0, 1]), stability.PdcQpStabilityError),
        ("reject-two-dimensional-field", lambda: stability.neighbor_count_roll(np.zeros((3, 3), dtype=np.uint8)), stability.PdcQpStabilityError),
        ("reject-noncubic-field", lambda: stability.neighbor_count_roll(np.zeros((3, 3, 4), dtype=np.uint8)), stability.PdcQpStabilityError),
        ("reject-extent-two", lambda: stability.neighbor_count_roll(np.zeros((2, 2, 2), dtype=np.uint8)), stability.PdcQpStabilityError),
        ("reject-nonbinary-field", lambda: stability.neighbor_count_roll(np.full((3, 3, 3), 2, dtype=np.uint8)), stability.PdcQpStabilityError),
        ("reject-count-shape", lambda: stability.channel_rates_from_counts(valid, np.zeros((3, 3), dtype=np.int16)), stability.PdcQpStabilityError),
        ("reject-count-range", lambda: stability.channel_rates_from_counts(valid, np.full((3, 3, 3), 27, dtype=np.int16)), stability.PdcQpStabilityError),
        ("reject-zero-swaps", lambda: stability.deterministic_density_swap(valid, class_name="iid_null", sample_index=0, swaps=0), stability.PdcQpStabilityError),
        ("reject-unknown-class", lambda: stability.deterministic_density_swap(valid, class_name="unknown", sample_index=0, swaps=1), stability.PdcQpStabilityError),
        ("reject-too-many-swaps", lambda: stability.deterministic_density_swap(valid, class_name="iid_null", sample_index=0, swaps=2), stability.PdcQpStabilityError),
        ("reject-zero-probability", lambda: stability.generate_benchmark_fields(probability=0.0), stability.PdcQpStabilityError),
        ("reject-zero-samples", lambda: stability.generate_benchmark_fields(sample_count=0), stability.PdcQpStabilityError),
        ("reject-invalid-hamming-fraction", lambda: stability.stability_tolerances(hamming_fraction=0.0, control=False), stability.PdcQpStabilityError),
        ("reject-null-spectrum", lambda: qp.normalized_geometry_spectrum(qp.GeometrySignature(0.1, 0.1, 0.1, 0.2)), qp.PdcQpNullSignalError),
    )
    results = []
    for check_id, operation, expected_error in checks:
        try:
            operation()
        except expected_error as exc:
            results.append({"id": check_id, "passed": True, "error_type": type(exc).__name__})
        except Exception as exc:  # pragma: no cover
            results.append({"id": check_id, "passed": False, "error_type": type(exc).__name__})
        else:
            results.append({"id": check_id, "passed": False, "error_type": "no_error"})
    return results


def make_stability_receipt(
    *,
    workspace: Path,
    contract_path: Path,
    qp_contract_path: Path,
    qp_receipt_path: Path,
    runner_package_path: Path | None = None,
    result_package_path: Path | None = None,
) -> dict[str, object]:
    contract = _load_json(contract_path)
    if contract.get("artifact_kind") != "pdc_qp_stability_contract" or contract.get("status") != "frozen_benchmark_protocol":
        raise PdcQpStabilityEvidenceError("stability receipt requires the frozen benchmark contract")
    bindings = contract["bindings"]
    runner_path = runner_package_path or workspace / RUNNER_PACKAGE_RELATIVE_PATH
    result_path = result_package_path or workspace / RESULT_PACKAGE_RELATIVE_PATH
    expected_contract = make_stability_contract(
        workspace=workspace,
        qp_contract_path=qp_contract_path,
        qp_receipt_path=qp_receipt_path,
        runner_package_path=runner_path,
        result_package_path=result_path,
    )
    expected_contract["created_utc"] = contract.get("created_utc")
    if pdc_verifier_intake.sha256_json(expected_contract) != pdc_verifier_intake.sha256_json(contract):
        raise PdcQpStabilityEvidenceError("stability contract content substitution detected")
    expected_bindings = {
        "qp_contract_sha256": pdc_verifier_intake.sha256_file(qp_contract_path),
        "qp_receipt_sha256": pdc_verifier_intake.sha256_file(qp_receipt_path),
    }
    for field, expected in expected_bindings.items():
        if bindings[field] != expected:
            raise PdcQpStabilityEvidenceError(f"stability contract binding mismatch: {field}")
    implementation_path = workspace / bindings["reference_implementation_path"]
    if pdc_verifier_intake.sha256_file(implementation_path) != bindings["reference_implementation_sha256"]:
        raise PdcQpStabilityEvidenceError("stability implementation substitution detected")
    package_paths = (runner_path, result_path)
    for package, path in zip(bindings["source_packages"], package_paths, strict=True):
        if pdc_verifier_intake.sha256_file(path) != package["sha256"]:
            raise PdcQpStabilityEvidenceError(f"stability source package substitution detected: {path}")
        actual_members = _member_records(path, RUNNER_MEMBERS if package["sha256"] == RUNNER_PACKAGE_SHA256 else RESULT_MEMBERS)
        if pdc_verifier_intake.sha256_json(actual_members) != pdc_verifier_intake.sha256_json(package["members"]):
            raise PdcQpStabilityEvidenceError("stability source member binding mismatch")
    published = _published_results(result_path)
    reproduction, fields, fresh_rates = _benchmark_reproduction(published)
    perturbation = _perturbation_evidence(fields, fresh_rates, published)
    negative_checks = _negative_checks()
    failed_negative = [check for check in negative_checks if not check["passed"]]
    if failed_negative:
        raise PdcQpStabilityEvidenceError(f"stability negative checks failed: {failed_negative}")
    evidence_path = workspace / "runtime" / "pdc_qp_stability_evidence.py"
    return {
        "schema_version": "0.1",
        "artifact_kind": "pdc_qp_stability_receipt",
        "contract_version": CONTRACT_VERSION,
        "created_utc": _created_utc(),
        "status": "pass",
        "bindings": {
            "reference_implementation_path": bindings["reference_implementation_path"],
            "reference_implementation_sha256": bindings["reference_implementation_sha256"],
            "evidence_implementation_path": _relative(evidence_path, workspace),
            "evidence_implementation_sha256": pdc_verifier_intake.sha256_file(evidence_path),
            "contract_path": _relative(contract_path, workspace),
            "contract_sha256": pdc_verifier_intake.sha256_file(contract_path),
            "qp_contract_path": _relative(qp_contract_path, workspace),
            "qp_contract_sha256": expected_bindings["qp_contract_sha256"],
            "qp_receipt_path": _relative(qp_receipt_path, workspace),
            "qp_receipt_sha256": expected_bindings["qp_receipt_sha256"],
            "runner_package_path": _relative(runner_path, workspace),
            "runner_package_sha256": RUNNER_PACKAGE_SHA256,
            "result_package_path": _relative(result_path, workspace),
            "result_package_sha256": RESULT_PACKAGE_SHA256,
        },
        "environment": {
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "numpy_version": np.__version__,
            "platform": platform.platform(),
            "executable": sys.executable,
            "floating_point_format": "IEEE-754 binary64",
        },
        "benchmark_reproduction": reproduction,
        "controlled_perturbations": perturbation,
        "negative_checks": negative_checks,
        "digests": {
            "benchmark_reproduction_sha256": pdc_verifier_intake.sha256_json(reproduction),
            "controlled_perturbation_sha256": pdc_verifier_intake.sha256_json(perturbation),
            "negative_check_set_sha256": pdc_verifier_intake.sha256_json(negative_checks),
        },
        "summary": {
            "source_package_count": len(bindings["source_packages"]),
            "verified_source_member_count": sum(len(package["members"]) for package in bindings["source_packages"]),
            "fresh_field_count": reproduction["field_count"],
            "published_channel_rate_check_count": reproduction["published_channel_rate_check_count"],
            "independent_channel_rate_check_count": reproduction["channel_rate_oracle_check_count"],
            "score_check_count": reproduction["score_check_count"],
            "summary_check_count": reproduction["summary_check_count"],
            "perturbation_case_count": perturbation["summary"]["case_count"],
            "structured_perturbation_case_count": perturbation["summary"]["structured_case_count"],
            "control_perturbation_case_count": perturbation["summary"]["control_case_count"],
            "negative_check_count": len(negative_checks),
            "failed_negative_check_count": 0,
            "mismatch_count": 0,
        },
        "claim_boundary": contract["claim_boundary"],
        "remaining_scope": [
            "The result is finite evidence for the declared synthetic field corpus and four perturbation levels, not an all-field stability theorem.",
            "PooleGlyph typed exposure and PGB2 trace integration remain blocked on P5 and PooleGlyph Phase 66.",
            "No signed dynamics, native backend, kernel enforcement, hardware, decoder, or production-ISO claim is made.",
        ],
    }
