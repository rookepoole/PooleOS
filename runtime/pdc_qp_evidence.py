"""Source-bound contract and independent verification receipt for PDC-QP-0.1."""

from __future__ import annotations

import csv
import io
import json
import math
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping, Sequence
from zipfile import ZipFile

from runtime import pdc_qp as qp
from runtime import pdc_verifier_intake


CONTRACT_VERSION = qp.CONTRACT_VERSION
FORMULA_SOURCE_IDS = ("SRC-LG-1", "SRC-MAG-1")
CASE_ARCHIVE_SOURCE_ID = "VER-SRC-LOCAL-GEOMETRY-ANCILLARY-V1_7_1"
CASE_MEMBERS = (
    (
        "raw_gate",
        "data/qp_verifier/qp_raw_gate_truth_table_v1_2.csv",
        16,
        "Collapsed AND/OR/NAND/NOR first-update footprint cases.",
    ),
    (
        "one_input",
        "data/qp_verifier/qp_one_input_truth_table_v1_2.csv",
        4,
        "Collapsed identity and NOT first-update footprint cases.",
    ),
    (
        "half_adder",
        "data/qp_verifier/qp_half_adder_truth_table_v1_2.csv",
        4,
        "Typed B7/B6 half-adder readout cases.",
    ),
    (
        "full_adder",
        "data/qp_verifier/qp_full_adder_truth_table_v1_2.csv",
        8,
        "Typed B7/B6/B5 full-adder readout cases.",
    ),
    (
        "cardinality",
        "data/qp_verifier/qp_cardinality_channel_table_v1_2.csv",
        10,
        "Exact r=0..9 footprint cardinality and birth-channel cases.",
    ),
)
SUPPORT_THRESHOLD_CASE_COUNT = 54
IMPORTED_TYPED_CASE_COUNT = sum(item[2] for item in CASE_MEMBERS)
FULL_PROBABILITY_CASE_COUNT = 10
SMALL_BRUTE_FORCE_CASE_COUNT = 12
NEGATIVE_CHECK_COUNT = 16
FINITE_DIFFERENCE_CASE_IDS = {
    "full-half",
    "full-ramp",
    "full-alternating",
    "full-modular-fractions",
}
FINITE_DIFFERENCE_STEP = 1e-6
FINITE_DIFFERENCE_TOLERANCE = 2e-8


class PdcQpEvidenceError(RuntimeError):
    """Raised when source binding or independent Q/P verification fails."""


def _created_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PdcQpEvidenceError(f"artifact root must be an object: {path}")
    return value


def _relative(path: Path, workspace: Path) -> str:
    return path.resolve().relative_to(workspace.resolve()).as_posix()


def _source_by_id(source_intake: Mapping[str, object], source_id: str) -> dict[str, object]:
    for source in source_intake["designated_sources"]:  # type: ignore[index]
        if source["id"] == source_id:
            return source
    raise PdcQpEvidenceError(f"source intake is missing {source_id}")


def _verifier_source_by_id(verifier_intake: Mapping[str, object], source_id: str) -> dict[str, object]:
    for source in verifier_intake["selected_sources"]:  # type: ignore[index]
        if source["id"] == source_id:
            return source
    raise PdcQpEvidenceError(f"verifier intake is missing {source_id}")


def _csv_rows(payload: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))))


def _integer(row: Mapping[str, str], name: str) -> int:
    try:
        value = int(row[name])
    except (KeyError, ValueError) as exc:
        raise PdcQpEvidenceError(f"invalid integer field {name!r} in imported Q/P row") from exc
    return value


def _member_records(archive_path: Path) -> list[dict[str, object]]:
    records = []
    with ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        for member_id, member_path, expected_rows, role in CASE_MEMBERS:
            if member_path not in names:
                raise PdcQpEvidenceError(f"Q/P source archive is missing {member_path}")
            payload = archive.read(member_path)
            rows = _csv_rows(payload)
            if len(rows) != expected_rows:
                raise PdcQpEvidenceError(
                    f"Q/P source member {member_id} has {len(rows)} rows, expected {expected_rows}"
                )
            records.append(
                {
                    "id": member_id,
                    "member_path": member_path,
                    "sha256": pdc_verifier_intake.sha256_bytes(payload),
                    "size_bytes": len(payload),
                    "row_count": len(rows),
                    "role": role,
                }
            )
    return records


def make_qp_contract(
    *,
    workspace: Path,
    source_intake_path: Path,
    verifier_intake_path: Path,
    math_contract_path: Path,
) -> dict[str, object]:
    source_intake = _load_json(source_intake_path)
    verifier_intake = _load_json(verifier_intake_path)
    math_contract = _load_json(math_contract_path)
    if source_intake.get("artifact_kind") != "pdc_source_intake" or source_intake.get("status") != "pass":
        raise PdcQpEvidenceError("PDC-QP-0.1 requires a passing source intake")
    if verifier_intake.get("artifact_kind") != "pdc_verifier_intake" or not str(
        verifier_intake.get("status", "")
    ).startswith("pass"):
        raise PdcQpEvidenceError("PDC-QP-0.1 requires a passing verifier intake")
    if math_contract.get("artifact_kind") != "pdc_math_contract" or math_contract.get("status") != "pass":
        raise PdcQpEvidenceError("PDC-QP-0.1 requires a passing PDC math contract")

    formula_sources = []
    for source_id in FORMULA_SOURCE_IDS:
        source = _source_by_id(source_intake, source_id)
        stored_path = workspace / source["stored_path"]
        if not stored_path.is_file() or pdc_verifier_intake.sha256_file(stored_path) != source["sha256"]:
            raise PdcQpEvidenceError(f"formula authority {source_id} is not a valid locked copy")
        formula_sources.append(
            {
                "id": source_id,
                "stored_path": source["stored_path"],
                "sha256": source["sha256"],
                "role": source["claim_role"],
            }
        )

    archive_source = _verifier_source_by_id(verifier_intake, CASE_ARCHIVE_SOURCE_ID)
    archive_path = workspace / archive_source["stored_path"]
    if not archive_path.is_file() or pdc_verifier_intake.sha256_file(archive_path) != archive_source["sha256"]:
        raise PdcQpEvidenceError("typed Q/P case archive is not a valid locked copy")
    members = _member_records(archive_path)
    implementation_path = workspace / "runtime" / "pdc_qp.py"

    return {
        "schema_version": "0.1",
        "artifact_kind": "pdc_qp_contract",
        "contract_version": CONTRACT_VERSION,
        "created_utc": _created_utc(),
        "status": "frozen_reference_contract",
        "bindings": {
            "reference_implementation_path": _relative(implementation_path, workspace),
            "reference_implementation_sha256": pdc_verifier_intake.sha256_file(implementation_path),
            "source_intake_path": _relative(source_intake_path, workspace),
            "source_intake_sha256": pdc_verifier_intake.sha256_file(source_intake_path),
            "verifier_intake_path": _relative(verifier_intake_path, workspace),
            "verifier_intake_sha256": pdc_verifier_intake.sha256_file(verifier_intake_path),
            "math_contract_path": _relative(math_contract_path, workspace),
            "math_contract_sha256": pdc_verifier_intake.sha256_file(math_contract_path),
            "math_contract_version": math_contract["contract_version"],
            "formula_sources": formula_sources,
            "typed_case_archive": {
                "source_id": archive_source["id"],
                "stored_path": archive_source["stored_path"],
                "sha256": archive_source["sha256"],
                "size_bytes": archive_source["size_bytes"],
            },
            "typed_case_members": members,
        },
        "feature_contract": {
            "type_tag": qp.FEATURE_TYPE_TAG,
            "model_tag": "B5-7/S5-9",
            "input_state_set": [0, 1],
            "support_range": [0, 26],
            "channel_order": list(qp.FEATURE_CHANNEL_ORDER),
            "definitions": {
                "B_k": "(1-x_i) * 1{N_i=k}, k in {5,6,7}",
                "S_k": "x_i * 1{N_i=k}, k in {5,6,7,8,9}",
                "O10+": "x_i * 1{N_i>=10}",
                "psi": "max(0,N_i-(7+2*x_i))-max(0,5-N_i)",
            },
            "collapsed_type_tag": qp.COLLAPSED_TYPE_TAG,
            "collapsed_expression": "P(x)_i = OR(B5,B6,B7,S5,S6,S7,S8,S9)",
            "collapsed_state_preserves_channel_identity": False,
            "typed_and_collapsed_outputs_are_interchangeable": False,
        },
        "probability_contract": {
            "type_tag": qp.PROBABILITY_TYPE_TAG,
            "model_tag": "B5-7/S5-9.independent_bernoulli_product",
            "center_excluded_from_neighbor_count": True,
            "neighbor_probability_count": qp.NEIGHBOR_COUNT,
            "generating_function": "G_i(z)=product_j(1-p_j+p_j*z)",
            "coefficient_definition": "Pr[N_i=k]=[z^k]G_i(z)",
            "dynamic_program": "F_(m+1)(k)=(1-p_jm)*F_m(k)+p_jm*F_m(k-1)",
            "activation_probability": "q_i=C_i^(5:7)+p_i*C_i^(8:9)",
            "center_derivative": "dq_i/dp_i=C_i^(8:9)",
            "neighbor_coefficient_derivative": "d[z^k]G/dp_l=[z^k](z-1)*product_(j!=l)(1-p_j+p_j*z)",
            "oracles": [
                "fixed_order_in_place_dynamic_program",
                "balanced_generating_polynomial_convolution",
                "bounded_brute_force_enumeration",
            ],
            "floating_point_policy": {
                "format": "IEEE-754 binary64",
                "input_order": "caller-provided Moore-neighbor order, unchanged",
                "dp_order": "left-to-right factors and descending coefficient update",
                "polynomial_order": "balanced recursive factor convolution",
                "normalization_sum": "math.fsum",
                "absolute_tolerance": qp.FLOAT_ABS_TOLERANCE,
                "relative_tolerance": qp.FLOAT_REL_TOLERANCE,
                "invalid_input_policy": "reject_nonfinite_out_of_range_wrong_cardinality",
                "output_clipping": False,
            },
        },
        "correlation_contract": {
            "residue_channels": list(qp.RESIDUE_CHANNEL_ORDER),
            "activation_residue": "Delta_i=qhat_i-q_i^ind",
            "channel_residue": "R_i=(B5hat-EindB5,B6hat-EindB6,B7hat-EindB7,S8hat-EindS8,S9hat-EindS9)",
            "coherence": "C_P=sum_i ||R_i||_2^2",
            "interpretation": "departure from the independent-site local model, not proof of entanglement or a physical noise source",
        },
        "cardinality_contract": {
            "scope": "first update, inactive normal-layer candidate, stable-sheet 3x3 footprint, no pre-existing adjacent normal activity",
            "support_expression": "N=9-r",
            "channel_map": {"r=2": "B7", "r=3": "B6", "r=4": "B5"},
            "raw_birth_expression": "1{2<=bias+sum(inputs)<=4}",
            "half_adder": {"bias": 1, "sum": "B7", "carry": "B6"},
            "full_adder": {"bias": 1, "sum": "B7 OR B5", "carry": "B6 OR B5"},
            "routing_fanout_timing_reset_isolation_and_demultiplexing_proved": False,
        },
        "spectrometry_contract": {
            "robust_score": "R_K=sqrt(sum_(k in K) asinh(((mu_hat_k-mu0_k)/(sigma0_k+epsilon))/lambda)^2)",
            "default_softening_lambda": qp.DEFAULT_SOFTENING,
            "default_epsilon": qp.DEFAULT_EPSILON,
            "birth_group": list(qp.BIRTH_GEOMETRY_CHANNELS),
            "high_support_group": list(qp.HIGH_SUPPORT_GEOMETRY_CHANNELS),
            "strain_group": list(qp.STRAIN_GEOMETRY_CHANNELS),
            "combined_group": list(qp.COMBINED_GEOMETRY_CHANNELS),
            "geometry_signature": "S_P=(R_B,R_H,R_psi)",
            "normalized_spectrum": "Sigma_P=(R_B^2,R_H^2,R_psi^2)/(R_B^2+R_H^2+R_psi^2+epsilon)",
            "null_like_threshold": qp.NULL_SIGNAL_THRESHOLD,
            "null_like_spectrum_policy": "reject_before_share_interpretation",
            "collapsed_update_rate_excluded_from_combined_group": True,
        },
        "imported_case_families": [
            {"id": member["id"], "case_count": member["row_count"], "member_sha256": member["sha256"]}
            for member in members
        ],
        "digests": {
            "formula_source_set_sha256": pdc_verifier_intake.sha256_json(formula_sources),
            "typed_case_member_set_sha256": pdc_verifier_intake.sha256_json(members),
        },
        "summary": {
            "feature_channel_count": len(qp.FEATURE_CHANNEL_ORDER),
            "residue_channel_count": len(qp.RESIDUE_CHANNEL_ORDER),
            "probability_neighbor_count": qp.NEIGHBOR_COUNT,
            "typed_case_family_count": len(CASE_MEMBERS),
            "imported_typed_case_count": IMPORTED_TYPED_CASE_COUNT,
            "formula_source_count": len(FORMULA_SOURCE_IDS),
        },
        "claim_boundary": [
            "PooleQ/P is a classical transform on already measured binary fields and probabilities under a declared product approximation.",
            "It does not copy, clone, infer, or reconstruct an unknown quantum state or unmeasured amplitudes.",
            "Typed B5/B6/B7 arithmetic identities are richer than a collapsed one-bit next-state observation.",
            "Gate and adder cases are exact local first-update footprint statements, not autonomous routing, timing, fanout, reset, or computer evidence.",
            "Robust scores and geometry spectra are model-tagged diagnostics relative to selected same-density controls, not physical sigma claims.",
        ],
    }


def _full_probability_cases() -> tuple[dict[str, object], ...]:
    return (
        {"id": "full-zero", "center": 0.0, "probabilities": (0.0,) * 26, "generator": "all_zero"},
        {"id": "full-one", "center": 1.0, "probabilities": (1.0,) * 26, "generator": "all_one"},
        {"id": "full-half", "center": 0.5, "probabilities": (0.5,) * 26, "generator": "all_half"},
        {
            "id": "full-ramp",
            "center": 0.25,
            "probabilities": tuple((index + 1) / 27 for index in range(26)),
            "generator": "p_j=(j+1)/27",
        },
        {
            "id": "full-alternating",
            "center": 0.75,
            "probabilities": tuple(0.125 if index % 2 == 0 else 0.875 for index in range(26)),
            "generator": "alternating_0.125_0.875",
        },
        {
            "id": "full-boundary-mix",
            "center": 0.375,
            "probabilities": tuple((0.0, 1.0, 0.2, 0.8, 0.5)[index % 5] for index in range(26)),
            "generator": "repeating_0_1_0.2_0.8_0.5",
        },
        {
            "id": "full-deterministic-seven",
            "center": 0.0,
            "probabilities": (1.0,) * 7 + (0.0,) * 19,
            "generator": "seven_certain_active",
        },
        {
            "id": "full-deterministic-eight",
            "center": 0.5,
            "probabilities": (1.0,) * 8 + (0.0,) * 18,
            "generator": "eight_certain_active",
        },
        {
            "id": "full-deterministic-nine",
            "center": 1.0,
            "probabilities": (1.0,) * 9 + (0.0,) * 17,
            "generator": "nine_certain_active",
        },
        {
            "id": "full-modular-fractions",
            "center": 0.625,
            "probabilities": tuple((((index * 11) % 28) + 1) / 30 for index in range(26)),
            "generator": "p_j=(((11*j) mod 28)+1)/30",
        },
    )


def _small_probability_cases() -> tuple[tuple[str, tuple[float, ...]], ...]:
    return (
        ("small-empty", ()),
        ("small-one", (0.2,)),
        ("small-two", (0.25, 0.75)),
        ("small-boundary", (0.0, 1.0, 0.5)),
        ("small-four", (0.1, 0.2, 0.3, 0.4)),
        ("small-five", (0.05, 0.15, 0.35, 0.65, 0.95)),
        ("small-six", tuple((index + 1) / 7 for index in range(6))),
        ("small-seven", tuple(0.3 if index % 2 == 0 else 0.7 for index in range(7))),
        ("small-eight", tuple((((index * 5) % 9) + 1) / 10 for index in range(8))),
        ("small-nine", (0.5,) * 9),
        ("small-ten", tuple((index + 1) / 11 for index in range(10))),
        ("small-twelve", tuple((((index * 7) % 12) + 1) / 13 for index in range(12))),
    )


def _max_abs(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise PdcQpEvidenceError("numeric comparison vectors have different lengths")
    return max((abs(a - b) for a, b in zip(left, right, strict=True)), default=0.0)


def _polynomial_derivatives(probabilities: Sequence[float]) -> tuple[tuple[float, ...], ...]:
    rows = []
    for removed_index in range(len(probabilities)):
        excluded = qp.poisson_binomial_polynomial(
            tuple(probabilities[:removed_index]) + tuple(probabilities[removed_index + 1 :])
        )
        rows.append(
            tuple(
                (excluded[count - 1] if count > 0 else 0.0)
                - (excluded[count] if count < len(excluded) else 0.0)
                for count in range(len(probabilities) + 1)
            )
        )
    return tuple(rows)


def _probability_evidence() -> dict[str, object]:
    full_records = []
    max_dp_polynomial_error = 0.0
    max_derivative_oracle_error = 0.0
    max_finite_difference_error = 0.0
    finite_difference_check_count = 0
    derivative_oracle_check_count = 0
    center_derivative_check_count = 0
    expected_channel_sum_check_count = 0
    normalization_check_count = 0

    for case in _full_probability_cases():
        probabilities = case["probabilities"]
        center = case["center"]
        dp = qp.poisson_binomial_dp(probabilities)
        polynomial = qp.poisson_binomial_polynomial(probabilities)
        coefficient_error = _max_abs(dp, polynomial)
        max_dp_polynomial_error = max(max_dp_polynomial_error, coefficient_error)
        normalization_check_count += 2
        if coefficient_error > qp.FLOAT_ABS_TOLERANCE:
            raise PdcQpEvidenceError(f"DP/polynomial mismatch in {case['id']}: {coefficient_error}")

        result = qp.probability_layer(center, probabilities)
        polynomial_gradient = _polynomial_derivatives(probabilities)
        derivative_errors = [
            _max_abs(dp_row, polynomial_row)
            for dp_row, polynomial_row in zip(qp.coefficient_derivatives(probabilities), polynomial_gradient, strict=True)
        ]
        derivative_error = max(derivative_errors, default=0.0)
        max_derivative_oracle_error = max(max_derivative_oracle_error, derivative_error)
        derivative_oracle_check_count += 26
        if derivative_error > 2e-12:
            raise PdcQpEvidenceError(f"derivative oracle mismatch in {case['id']}: {derivative_error}")

        center_delta = qp.activation_probability(dp, 1.0) - qp.activation_probability(dp, 0.0)
        center_error = abs(center_delta - result.center_derivative)
        center_derivative_check_count += 1
        if center_error > qp.FLOAT_ABS_TOLERANCE:
            raise PdcQpEvidenceError(f"center derivative mismatch in {case['id']}: {center_error}")

        activation_from_channels = math.fsum(
            result.expected_channels[channel]
            for channel in ("B5", "B6", "B7", "S5", "S6", "S7", "S8", "S9")
        )
        channel_error = abs(activation_from_channels - result.activation_probability)
        expected_channel_sum_check_count += 1
        if channel_error > qp.FLOAT_ABS_TOLERANCE:
            raise PdcQpEvidenceError(f"expected channel sum mismatch in {case['id']}: {channel_error}")

        case_finite_difference_error = 0.0
        if case["id"] in FINITE_DIFFERENCE_CASE_IDS:
            for index, probability in enumerate(probabilities):
                lower = list(probabilities)
                upper = list(probabilities)
                lower[index] = probability - FINITE_DIFFERENCE_STEP
                upper[index] = probability + FINITE_DIFFERENCE_STEP
                low_q = qp.activation_probability(qp.poisson_binomial_polynomial(lower), center)
                high_q = qp.activation_probability(qp.poisson_binomial_polynomial(upper), center)
                finite_difference = (high_q - low_q) / (2.0 * FINITE_DIFFERENCE_STEP)
                error = abs(finite_difference - result.neighbor_derivatives[index])
                case_finite_difference_error = max(case_finite_difference_error, error)
                max_finite_difference_error = max(max_finite_difference_error, error)
                finite_difference_check_count += 1
            if case_finite_difference_error > FINITE_DIFFERENCE_TOLERANCE:
                raise PdcQpEvidenceError(
                    f"finite-difference derivative mismatch in {case['id']}: {case_finite_difference_error}"
                )

        full_records.append(
            {
                "id": case["id"],
                "generator": case["generator"],
                "center_probability": center,
                "coefficient_sha256": pdc_verifier_intake.sha256_json(list(dp)),
                "neighbor_derivative_sha256": pdc_verifier_intake.sha256_json(list(result.neighbor_derivatives)),
                "activation_probability": result.activation_probability,
                "center_derivative": result.center_derivative,
                "coefficient_dp_polynomial_max_abs_error": coefficient_error,
                "derivative_dp_polynomial_max_abs_error": derivative_error,
                "finite_difference_max_abs_error": case_finite_difference_error,
            }
        )

    small_records = []
    max_brute_force_error = 0.0
    for case_id, probabilities in _small_probability_cases():
        dp = qp.poisson_binomial_dp(probabilities)
        polynomial = qp.poisson_binomial_polynomial(probabilities)
        brute_force = qp.poisson_binomial_bruteforce(probabilities)
        error = max(_max_abs(dp, polynomial), _max_abs(dp, brute_force), _max_abs(polynomial, brute_force))
        max_brute_force_error = max(max_brute_force_error, error)
        normalization_check_count += 3
        if error > 2e-12:
            raise PdcQpEvidenceError(f"small-neighborhood oracle mismatch in {case_id}: {error}")
        small_records.append(
            {
                "id": case_id,
                "neighbor_count": len(probabilities),
                "coefficient_sha256": pdc_verifier_intake.sha256_json(list(dp)),
                "max_abs_error": error,
            }
        )

    return {
        "full_neighborhood_cases": full_records,
        "small_neighborhood_cases": small_records,
        "summary": {
            "full_neighborhood_case_count": len(full_records),
            "small_brute_force_case_count": len(small_records),
            "dp_polynomial_coefficient_check_count": len(full_records) * 27,
            "brute_force_coefficient_check_count": sum(record["neighbor_count"] + 1 for record in small_records),
            "derivative_oracle_check_count": derivative_oracle_check_count,
            "center_derivative_check_count": center_derivative_check_count,
            "finite_difference_check_count": finite_difference_check_count,
            "expected_channel_sum_check_count": expected_channel_sum_check_count,
            "normalization_check_count": normalization_check_count,
            "max_dp_polynomial_abs_error": max_dp_polynomial_error,
            "max_brute_force_abs_error": max_brute_force_error,
            "max_derivative_oracle_abs_error": max_derivative_oracle_error,
            "max_finite_difference_abs_error": max_finite_difference_error,
            "mismatch_count": 0,
        },
    }


def _feature_evidence() -> dict[str, object]:
    records = []
    for state in (0, 1):
        for support in range(27):
            measured = qp.feature(state, support)
            channels = measured.channel_map()
            accepted_channel_sum = sum(channels[channel] for channel in channels if channel != "psi" and channel != "O10+")
            expected_next = int(5 <= support <= 7 + 2 * state)
            if accepted_channel_sum != expected_next or measured.collapsed_next_state != expected_next:
                raise PdcQpEvidenceError(f"feature/collapsed mismatch for state={state}, support={support}")
            if sum(channels[channel] for channel in qp.FEATURE_CHANNEL_ORDER[:-2]) > 1:
                raise PdcQpEvidenceError(f"feature channels are not disjoint for state={state}, support={support}")
            records.append(measured.to_dict())
    return {
        "case_count": len(records),
        "passed_count": len(records),
        "channel_disjointness_count": len(records),
        "collapsed_equivalence_count": len(records),
        "record_set_sha256": pdc_verifier_intake.sha256_json(records),
        "mismatch_count": 0,
    }


def _compare_fields(actual: Mapping[str, object], expected: Mapping[str, object]) -> list[str]:
    return sorted(name for name, expected_value in expected.items() if actual.get(name) != expected_value)


def _verify_raw_gate(rows: Sequence[Mapping[str, str]]) -> list[dict[str, object]]:
    truth = {
        "AND": lambda a, b: a & b,
        "OR": lambda a, b: a | b,
        "NAND": lambda a, b: 1 - (a & b),
        "NOR": lambda a, b: 1 - (a | b),
    }
    records = []
    for index, row in enumerate(rows):
        gate = row["gate"]
        if gate not in truth:
            raise PdcQpEvidenceError(f"unknown imported raw gate {gate!r}")
        a, b, bias = _integer(row, "A"), _integer(row, "B"), _integer(row, "bias_c")
        readout = qp.footprint_readout((a, b), bias)
        actual = {"raw_birth_Y": readout.raw_birth, "expected": truth[gate](a, b)}
        expected = {name: _integer(row, name) for name in actual}
        records.append({"index": index, "gate": gate, "actual": actual, "expected": expected, "mismatches": _compare_fields(actual, expected)})
    return records


def _verify_one_input(rows: Sequence[Mapping[str, str]]) -> list[dict[str, object]]:
    records = []
    for index, row in enumerate(rows):
        gate = row["gate"]
        a, bias = _integer(row, "A"), _integer(row, "bias_c")
        expected_logic = a if gate == "IDENTITY" else 1 - a if gate == "NOT" else None
        if expected_logic is None:
            raise PdcQpEvidenceError(f"unknown imported one-input gate {gate!r}")
        readout = qp.footprint_readout((a,), bias)
        actual = {"raw_birth_Y": readout.raw_birth, "expected": expected_logic}
        expected = {name: _integer(row, name) for name in actual}
        records.append({"index": index, "gate": gate, "actual": actual, "expected": expected, "mismatches": _compare_fields(actual, expected)})
    return records


def _verify_half_adder(rows: Sequence[Mapping[str, str]]) -> list[dict[str, object]]:
    records = []
    for index, row in enumerate(rows):
        a, b = _integer(row, "A"), _integer(row, "B")
        bias = _integer(row, "bias_b")
        if bias != 1:
            raise PdcQpEvidenceError("imported half-adder bias is not one")
        result = qp.half_adder((a, b))
        readout = result["footprint"]
        actual = {
            "s": a + b,
            "r": readout["total_defects"],
            "N": readout["active_neighbor_support"],
            **readout["birth_channels"],
            "SUM": result["sum"],
            "CARRY": result["carry"],
            "expected_SUM": (a + b) % 2,
            "expected_CARRY": int(a + b >= 2),
        }
        expected = {name: _integer(row, name) for name in actual}
        records.append({"index": index, "actual": actual, "expected": expected, "mismatches": _compare_fields(actual, expected)})
    return records


def _verify_full_adder(rows: Sequence[Mapping[str, str]]) -> list[dict[str, object]]:
    records = []
    for index, row in enumerate(rows):
        inputs = (_integer(row, "A"), _integer(row, "B"), _integer(row, "Cin"))
        bias = _integer(row, "bias_b")
        if bias != 1:
            raise PdcQpEvidenceError("imported full-adder bias is not one")
        result = qp.full_adder(inputs)
        readout = result["footprint"]
        total = sum(inputs)
        actual = {
            "s": total,
            "r": readout["total_defects"],
            "N": readout["active_neighbor_support"],
            **readout["birth_channels"],
            "SUM": result["sum"],
            "CARRY": result["carry"],
            "expected_SUM": total % 2,
            "expected_CARRY": int(total >= 2),
        }
        expected = {name: _integer(row, name) for name in actual}
        records.append({"index": index, "actual": actual, "expected": expected, "mismatches": _compare_fields(actual, expected)})
    return records


def _verify_cardinality(rows: Sequence[Mapping[str, str]]) -> list[dict[str, object]]:
    records = []
    for index, row in enumerate(rows):
        defects = _integer(row, "r_defects")
        readout = qp.footprint_readout((), defects)
        actual = {
            "N_active_neighbors": readout.active_neighbor_support,
            "B5": readout.B5,
            "B6": readout.B6,
            "B7": readout.B7,
            "raw_birth_Y": readout.raw_birth,
            "birth_allowed": int(2 <= defects <= 4),
        }
        expected = {name: _integer(row, name) for name in actual}
        records.append({"index": index, "defects": defects, "actual": actual, "expected": expected, "mismatches": _compare_fields(actual, expected)})
    return records


CASE_VERIFIERS: Mapping[str, Callable[[Sequence[Mapping[str, str]]], list[dict[str, object]]]] = {
    "raw_gate": _verify_raw_gate,
    "one_input": _verify_one_input,
    "half_adder": _verify_half_adder,
    "full_adder": _verify_full_adder,
    "cardinality": _verify_cardinality,
}


def _typed_case_evidence(archive_path: Path, contract_members: Sequence[Mapping[str, object]]) -> dict[str, object]:
    family_results = []
    all_mismatches = []
    with ZipFile(archive_path) as archive:
        for member in contract_members:
            payload = archive.read(member["member_path"])
            payload_hash = pdc_verifier_intake.sha256_bytes(payload)
            if payload_hash != member["sha256"] or len(payload) != member["size_bytes"]:
                raise PdcQpEvidenceError(f"typed Q/P source member substitution detected: {member['id']}")
            rows = _csv_rows(payload)
            records = CASE_VERIFIERS[member["id"]](rows)
            mismatches = [record for record in records if record["mismatches"]]
            all_mismatches.extend({"family": member["id"], **record} for record in mismatches)
            family_results.append(
                {
                    "id": member["id"],
                    "source_member_sha256": payload_hash,
                    "case_count": len(records),
                    "passed_count": len(records) - len(mismatches),
                    "mismatch_count": len(mismatches),
                    "recomputed_record_set_sha256": pdc_verifier_intake.sha256_json(records),
                }
            )
    if all_mismatches:
        raise PdcQpEvidenceError(f"typed Q/P case mismatches: {all_mismatches[:3]}")
    return {
        "families": family_results,
        "summary": {
            "family_count": len(family_results),
            "case_count": sum(record["case_count"] for record in family_results),
            "passed_count": sum(record["passed_count"] for record in family_results),
            "mismatch_count": 0,
        },
        "recomputed_family_set_sha256": pdc_verifier_intake.sha256_json(family_results),
    }


def _correlation_and_spectrometry_evidence() -> dict[str, object]:
    centers = (0, 0, 1, 1, 1, 0)
    neighborhoods = []
    for sample_index in range(len(centers)):
        neighborhoods.append(
            tuple(int((index * 7 + sample_index * 5 + index * sample_index) % 17 < 5) for index in range(26))
        )
    empirical = qp.empirical_site_statistics(centers, neighborhoods)
    coherence = qp.poole_coherence([empirical["channel_residue"]])
    if not math.isclose(coherence, empirical["coherence_contribution"], rel_tol=0.0, abs_tol=1e-15):
        raise PdcQpEvidenceError("correlation residue and coherence contribution disagree")

    observed = {channel: 0.02 * (index + 1) for index, channel in enumerate(qp.COMBINED_GEOMETRY_CHANNELS)}
    null_means = {channel: 0.001 * index for index, channel in enumerate(qp.COMBINED_GEOMETRY_CHANNELS)}
    null_stds = {channel: 0.003 + 0.0005 * index for index, channel in enumerate(qp.COMBINED_GEOMETRY_CHANNELS)}
    signature = qp.geometry_signature(observed, null_means, null_stds)
    component_norm = math.sqrt(
        signature.birth_window**2 + signature.high_support**2 + signature.strain**2
    )
    if not math.isclose(component_norm, signature.combined, rel_tol=1e-14, abs_tol=1e-14):
        raise PdcQpEvidenceError("decomposed and combined robust scores disagree")
    spectrum = qp.normalized_geometry_spectrum(signature)
    expected_share_sum = component_norm**2 / (component_norm**2 + qp.DEFAULT_EPSILON)
    if not math.isclose(spectrum["share_sum"], expected_share_sum, rel_tol=1e-14, abs_tol=1e-14):
        raise PdcQpEvidenceError("normalized geometry spectrum does not match the frozen formula")
    return {
        "empirical_site": {
            "sample_count": empirical["sample_count"],
            "activation_residue": empirical["activation_residue"],
            "channel_residue": empirical["channel_residue"],
            "coherence_contribution": empirical["coherence_contribution"],
            "record_sha256": pdc_verifier_intake.sha256_json(empirical),
        },
        "spectrometry": {
            "signature": signature.to_dict(),
            "spectrum": spectrum,
            "component_combined_abs_error": abs(component_norm - signature.combined),
            "share_sum_abs_error": abs(spectrum["share_sum"] - expected_share_sum),
        },
        "summary": {
            "correlation_residue_check_count": 1,
            "coherence_check_count": 1,
            "robust_component_check_count": 4,
            "normalized_spectrum_check_count": 1,
            "mismatch_count": 0,
        },
    }


def _negative_checks() -> list[dict[str, object]]:
    zero_signature = qp.GeometrySignature(0.0, 0.0, 0.0, 0.0)
    checks: tuple[tuple[str, Callable[[], object], type[Exception]], ...] = (
        ("reject-bool-state", lambda: qp.feature(True, 5), qp.PdcQpError),
        ("reject-support-27", lambda: qp.feature(0, 27), qp.PdcQpError),
        ("reject-probability-nan", lambda: qp.poisson_binomial_dp((float("nan"),)), qp.PdcQpProbabilityError),
        ("reject-probability-inf", lambda: qp.poisson_binomial_dp((float("inf"),)), qp.PdcQpProbabilityError),
        ("reject-probability-below-zero", lambda: qp.poisson_binomial_dp((-0.01,)), qp.PdcQpProbabilityError),
        ("reject-probability-above-one", lambda: qp.poisson_binomial_dp((1.01,)), qp.PdcQpProbabilityError),
        ("reject-25-neighbor-layer", lambda: qp.probability_layer(0.5, (0.5,) * 25), qp.PdcQpProbabilityError),
        ("reject-27-neighbor-layer", lambda: qp.probability_layer(0.5, (0.5,) * 27), qp.PdcQpProbabilityError),
        ("reject-bruteforce-17", lambda: qp.poisson_binomial_bruteforce((0.5,) * 17), qp.PdcQpProbabilityError),
        ("reject-negative-bias", lambda: qp.footprint_readout((0, 1), -1), qp.PdcQpFootprintError),
        ("reject-footprint-over-capacity", lambda: qp.footprint_readout((0,) * 9, 1), qp.PdcQpFootprintError),
        ("reject-half-adder-arity", lambda: qp.half_adder((0,)), qp.PdcQpFootprintError),
        ("reject-full-adder-arity", lambda: qp.full_adder((0, 1)), qp.PdcQpFootprintError),
        ("reject-unnormalized-distribution", lambda: qp.activation_probability((1.0,) * 27, 0.5), qp.PdcQpProbabilityError),
        (
            "reject-zero-robust-epsilon",
            lambda: qp.robust_score(
                {"B5": 0.1}, {"B5": 0.0}, {"B5": 0.01}, ("B5",), epsilon=0.0
            ),
            qp.PdcQpProbabilityError,
        ),
        ("reject-null-spectrum", lambda: qp.normalized_geometry_spectrum(zero_signature), qp.PdcQpNullSignalError),
    )
    results = []
    for check_id, operation, expected_error in checks:
        try:
            operation()
        except expected_error as exc:
            results.append({"id": check_id, "passed": True, "error_type": type(exc).__name__})
        except Exception as exc:  # pragma: no cover - receipt should expose unexpected failure class
            results.append({"id": check_id, "passed": False, "error_type": type(exc).__name__})
        else:
            results.append({"id": check_id, "passed": False, "error_type": "no_error"})
    return results


def make_qp_receipt(
    *,
    workspace: Path,
    contract_path: Path,
    source_intake_path: Path,
    verifier_intake_path: Path,
    math_contract_path: Path,
) -> dict[str, object]:
    contract = _load_json(contract_path)
    if contract.get("artifact_kind") != "pdc_qp_contract" or contract.get("status") != "frozen_reference_contract":
        raise PdcQpEvidenceError("Q/P receipt requires the frozen PDC-QP-0.1 contract")
    bindings = contract["bindings"]
    expected_bindings = {
        "source_intake_sha256": pdc_verifier_intake.sha256_file(source_intake_path),
        "verifier_intake_sha256": pdc_verifier_intake.sha256_file(verifier_intake_path),
        "math_contract_sha256": pdc_verifier_intake.sha256_file(math_contract_path),
    }
    for field, expected in expected_bindings.items():
        if bindings[field] != expected:
            raise PdcQpEvidenceError(f"Q/P contract binding mismatch: {field}")
    implementation_path = workspace / bindings["reference_implementation_path"]
    if pdc_verifier_intake.sha256_file(implementation_path) != bindings["reference_implementation_sha256"]:
        raise PdcQpEvidenceError("Q/P reference implementation substitution detected")
    archive_binding = bindings["typed_case_archive"]
    archive_path = workspace / archive_binding["stored_path"]
    if pdc_verifier_intake.sha256_file(archive_path) != archive_binding["sha256"]:
        raise PdcQpEvidenceError("Q/P typed-case archive substitution detected")

    feature_result = _feature_evidence()
    probability_result = _probability_evidence()
    typed_case_result = _typed_case_evidence(archive_path, bindings["typed_case_members"])
    correlation_result = _correlation_and_spectrometry_evidence()
    negative_checks = _negative_checks()
    failed_negative = [check for check in negative_checks if not check["passed"]]
    if failed_negative:
        raise PdcQpEvidenceError(f"Q/P negative checks failed: {failed_negative}")
    evidence_path = workspace / "runtime" / "pdc_qp_evidence.py"
    summary = probability_result["summary"]
    total_mismatches = (
        feature_result["mismatch_count"]
        + summary["mismatch_count"]
        + typed_case_result["summary"]["mismatch_count"]
        + correlation_result["summary"]["mismatch_count"]
    )
    if total_mismatches:
        raise PdcQpEvidenceError(f"Q/P receipt has {total_mismatches} mismatches")

    return {
        "schema_version": "0.1",
        "artifact_kind": "pdc_qp_receipt",
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
            "source_intake_path": _relative(source_intake_path, workspace),
            "source_intake_sha256": expected_bindings["source_intake_sha256"],
            "verifier_intake_path": _relative(verifier_intake_path, workspace),
            "verifier_intake_sha256": expected_bindings["verifier_intake_sha256"],
            "math_contract_path": _relative(math_contract_path, workspace),
            "math_contract_sha256": expected_bindings["math_contract_sha256"],
            "typed_case_archive_path": archive_binding["stored_path"],
            "typed_case_archive_sha256": archive_binding["sha256"],
        },
        "environment": {
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "executable": sys.executable,
            "floating_point_format": "IEEE-754 binary64",
        },
        "feature_thresholds": feature_result,
        "probability": probability_result,
        "typed_cases": typed_case_result,
        "correlation_and_spectrometry": correlation_result,
        "negative_checks": negative_checks,
        "digests": {
            "feature_result_sha256": pdc_verifier_intake.sha256_json(feature_result),
            "probability_result_sha256": pdc_verifier_intake.sha256_json(probability_result),
            "typed_case_result_sha256": pdc_verifier_intake.sha256_json(typed_case_result),
            "correlation_result_sha256": pdc_verifier_intake.sha256_json(correlation_result),
            "negative_check_set_sha256": pdc_verifier_intake.sha256_json(negative_checks),
        },
        "summary": {
            "feature_threshold_case_count": feature_result["case_count"],
            "full_probability_case_count": summary["full_neighborhood_case_count"],
            "small_brute_force_case_count": summary["small_brute_force_case_count"],
            "dp_polynomial_coefficient_check_count": summary["dp_polynomial_coefficient_check_count"],
            "brute_force_coefficient_check_count": summary["brute_force_coefficient_check_count"],
            "derivative_oracle_check_count": summary["derivative_oracle_check_count"],
            "center_derivative_check_count": summary["center_derivative_check_count"],
            "finite_difference_check_count": summary["finite_difference_check_count"],
            "normalization_check_count": summary["normalization_check_count"],
            "typed_case_family_count": typed_case_result["summary"]["family_count"],
            "imported_typed_case_count": typed_case_result["summary"]["case_count"],
            "negative_check_count": len(negative_checks),
            "failed_negative_check_count": 0,
            "mismatch_count": 0,
        },
        "claim_boundary": contract["claim_boundary"],
        "remaining_scope": [
            "This receipt does not reproduce the v5.5 field benchmark or establish perturbation stability for robust spectra.",
            "PooleGlyph typed exposure and PGB2 trace integration remain blocked on the P5 type/effect review and Phase 66 boundary.",
            "No gate-routing, fanout, timing, reset, isolation, hardware, kernel, or production-ISO claim is made.",
        ],
    }
