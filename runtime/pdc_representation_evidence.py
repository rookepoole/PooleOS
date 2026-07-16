"""Contract and differential evidence builders for PDC-REP-0.1."""

from __future__ import annotations

import csv
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Iterator

import numpy as np

from runtime import pdc_reference
from runtime import pdc_representation as rep
from runtime import pdc_verifier_intake


DECLARED_EXACT_COUNTS = {
    "rectangle": 841,
    "line_hole": 80,
    "arbitrary_mask": 720,
    "inversion": 1225,
    "solid_cuboid": 729,
    "surface_shell": 729,
}
REPRESENTATION_APPLICABLE_EXACT_COUNT = 3099
GOLDEN_DECLARED_COUNT = 13
GOLDEN_APPLICABLE_COUNT = 10
ROUND_TRIPS_PER_CASE = 4


class PdcRepresentationEvidenceError(ValueError):
    """Raised when representation evidence cannot be reproduced exactly."""


def _created_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _relative(path: Path, workspace: Path) -> str:
    return path.resolve().relative_to(workspace.resolve()).as_posix()


def _json_digest(value: object) -> str:
    return pdc_verifier_intake.sha256_json(value)


def make_representation_contract(
    *,
    workspace: Path,
    math_contract_path: Path,
    golden_vectors_path: Path,
    verifier_reproduction_path: Path,
) -> dict[str, object]:
    math_contract = _load_json(math_contract_path)
    golden = _load_json(golden_vectors_path)
    verifier = _load_json(verifier_reproduction_path)
    reference_implementation_path = workspace / "runtime" / "pdc_representation.py"
    if math_contract.get("contract_version") != "PDC-MATH-0.1" or math_contract.get("status") != "pass":
        raise PdcRepresentationEvidenceError("PDC-REP-0.1 requires the passing PDC-MATH-0.1 contract")
    if golden.get("status") != "pass" or golden["math_contract_binding"]["artifact_sha256"] != pdc_verifier_intake.sha256_file(math_contract_path):
        raise PdcRepresentationEvidenceError("golden vectors are not bound to the supplied math contract")
    if verifier.get("status") != "pass_with_documented_serialization_drift":
        raise PdcRepresentationEvidenceError("exact verifier reproduction is not passing")
    if verifier["bindings"]["math_contract_sha256"] != pdc_verifier_intake.sha256_file(math_contract_path):
        raise PdcRepresentationEvidenceError("exact verifier reproduction is not bound to the supplied math contract")

    representations = [
        {
            "id": "dense_binary",
            "logical_dtype": "u8",
            "storage": "one immutable byte per x-fastest logical cell",
            "ownership": "runtime-owned immutable bytes",
            "canonicalization": "payload length equals cell count and every byte is exactly 0 or 1",
            "failure_boundary": "wrong length, nonbinary byte, malformed shape, or overflow",
        },
        {
            "id": "sparse_binary",
            "logical_dtype": "u8",
            "storage": "strictly increasing unique little-endian u64 active flat indices",
            "ownership": "runtime-owned immutable tuple",
            "canonicalization": "active value is implicit one and omitted values are zero",
            "failure_boundary": "negative, duplicate, unsorted, noninteger, or out-of-range index",
        },
        {
            "id": "bitpacked_binary",
            "logical_dtype": "u8",
            "storage": "least-significant-bit-first x-fastest packing",
            "ownership": "runtime-owned immutable bytes",
            "canonicalization": "ceil(cell_count/8) bytes with zero unused high bits",
            "failure_boundary": "wrong length, unsupported bit order, or nonzero padding bit",
        },
        {
            "id": "probability_field",
            "logical_dtype": "f64",
            "storage": "canonical little-endian IEEE-754 binary64 logical values",
            "ownership": "runtime-owned immutable tuple",
            "canonicalization": "finite [0,1] values with negative zero normalized to positive zero",
            "failure_boundary": "NaN, infinity, out-of-range value, wrong length, or implicit lossy threshold",
        },
        {
            "id": "native_buffer_snapshot",
            "logical_dtype": "u8_or_f64",
            "storage": "immutable logical snapshot plus checked offset, x-fastest padded strides, and provenance",
            "ownership": "runtime-owned or explicitly snapshotted caller-borrowed source",
            "canonicalization": "hash validated descriptor and logical payload while excluding unused backing padding",
            "failure_boundary": "unproved borrow, overlap, misalignment, span overflow, unsupported dtype, or short backing buffer",
        },
    ]
    conversion_paths = [
        {"id": "dense_to_sparse", "source": "dense_binary", "target": "sparse_binary", "lossless_condition": "always"},
        {"id": "sparse_to_dense", "source": "sparse_binary", "target": "dense_binary", "lossless_condition": "canonical validated indices"},
        {"id": "dense_to_bitpacked", "source": "dense_binary", "target": "bitpacked_binary", "lossless_condition": "always"},
        {"id": "bitpacked_to_dense", "source": "bitpacked_binary", "target": "dense_binary", "lossless_condition": "canonical zero padding"},
        {"id": "dense_to_probability", "source": "dense_binary", "target": "probability_field", "lossless_condition": "exact 0 to 0.0 and 1 to 1.0 embedding"},
        {"id": "probability_to_dense", "source": "probability_field", "target": "dense_binary", "lossless_condition": "every value is exactly 0.0 or 1.0"},
        {"id": "dense_to_native_u8", "source": "dense_binary", "target": "native_buffer_snapshot", "lossless_condition": "validated u8 descriptor and immutable snapshot"},
        {"id": "native_u8_to_dense", "source": "native_buffer_snapshot", "target": "dense_binary", "lossless_condition": "native snapshot dtype is u8"},
        {"id": "probability_to_native_f64", "source": "probability_field", "target": "native_buffer_snapshot", "lossless_condition": "validated f64 descriptor and immutable snapshot"},
        {"id": "native_f64_to_probability", "source": "native_buffer_snapshot", "target": "probability_field", "lossless_condition": "native snapshot dtype is f64"},
    ]
    failure_modes = [
        "invalid_dimensions",
        "periodic_extent_aliasing",
        "shape_product_overflow",
        "payload_length_mismatch",
        "invalid_binary_value",
        "sparse_order_or_duplicate",
        "sparse_index_out_of_range",
        "bit_padding_nonzero",
        "probability_nonfinite_or_out_of_range",
        "lossy_probability_to_binary",
        "native_dtype_unsupported",
        "native_backing_noncontiguous",
        "native_stride_overlap",
        "native_alignment_invalid",
        "native_descriptor_span_overflow_or_short_buffer",
        "caller_borrow_without_snapshot",
    ]
    return {
        "schema_version": "0.1",
        "artifact_kind": "pdc_representation_contract",
        "abi_version": rep.ABI_VERSION,
        "created_utc": _created_utc(),
        "status": "pass",
        "bindings": {
            "reference_implementation_path": _relative(reference_implementation_path, workspace),
            "reference_implementation_sha256": pdc_verifier_intake.sha256_file(reference_implementation_path),
            "math_contract_path": _relative(math_contract_path, workspace),
            "math_contract_sha256": pdc_verifier_intake.sha256_file(math_contract_path),
            "math_contract_version": math_contract["contract_version"],
            "golden_vectors_path": _relative(golden_vectors_path, workspace),
            "golden_vectors_sha256": pdc_verifier_intake.sha256_file(golden_vectors_path),
            "golden_vector_set_version": golden["vector_set_version"],
            "verifier_reproduction_path": _relative(verifier_reproduction_path, workspace),
            "verifier_reproduction_sha256": pdc_verifier_intake.sha256_file(verifier_reproduction_path),
            "verifier_case_count": verifier["summary"]["independent_case_count"],
        },
        "coordinate_contract": {
            "dimensions": [2, 3],
            "shape_order": "x_extent,y_extent,z_extent_when_present",
            "axis_order": rep.AXIS_ORDER,
            "origin": "zero",
            "boundary": rep.BOUNDARY_MODE,
            "minimum_periodic_extent": pdc_reference.MIN_PERIODIC_EXTENT,
            "maximum_reference_cells": pdc_reference.MAX_REFERENCE_CELLS,
        },
        "representations": representations,
        "conversion_paths": conversion_paths,
        "native_buffer_contract": {
            "supported_dtypes": ["u8", "f64"],
            "stride_unit": "bytes",
            "x_stride": "dtype_item_size",
            "row_stride": "at_least_x_extent_times_x_stride",
            "slice_stride": "at_least_y_extent_times_row_stride",
            "negative_or_broadcast_or_transposed_or_overlapping_strides": "rejected",
            "declared_base_alignment": "power_of_two_1_to_4096_and_at_least_dtype_alignment",
            "actual_pointer_alignment": "must_be_revalidated_by_future_native_or_kernel_boundary",
            "borrowed_input": "requires_immutable_logical_snapshot_before_validation_or_execution",
            "mutable_output": "unsupported_in_rep_0_1",
        },
        "canonical_hash_contract": {
            "algorithm": "SHA-256",
            "framing": "canonical_ascii_json_header_then_00_then_logical_payload",
            "binary_semantic_hash": "exact_PDC_MATH_0_1_dense_u8_hash_for_all_binary_forms",
            "probability_semantic_hash": "representation_neutral_f64_hash_tagged_probability_field",
            "storage_hash": "representation_specific_header_and_canonical_logical_payload",
            "native_padding_bytes_hashed": False,
        },
        "arithmetic_contract": {
            "width": "u64",
            "checked_operations": ["shape_product", "byte_count", "stride_product", "offset_addition", "final_span"],
            "failure": "reject_before_access_or_allocation",
        },
        "failure_modes": failure_modes,
        "summary": {
            "representation_count": len(representations),
            "conversion_path_count": len(conversion_paths),
            "native_dtype_count": 2,
            "failure_mode_count": len(failure_modes),
        },
        "unsupported": [
            "nonperiodic boundaries and extents below three",
            "implicit probability thresholding or stochastic sampling",
            "negative, broadcast, transposed, overlapping, or device strides",
            "borrowed execution without snapshot and mutable output aliases",
            "device pointers, DMA, pinning, unified memory, and zero-copy execution",
            "portable C17, SIMD, RAM-pool, GPU, kernel, PooleGlyph, and PGB2 bindings",
        ],
        "claim_boundary": [
            "PDC-REP-0.1 freezes a checked Python reference ABI and does not claim a completed native C or kernel ABI.",
            "Representation agreement is verifier evidence, not performance, hardware, memory-safety, or booted-enforcement evidence.",
            "Probability storage is frozen, while Q/P probability dynamics remain P3 work.",
        ],
    }


def _dense_from_coords(shape: tuple[int, ...], coords: Iterable[tuple[int, ...]]) -> rep.DenseBinaryField:
    normalized, count = pdc_reference.validate_periodic_shape(shape, dimensions=len(shape))
    payload = bytearray(count)
    for coord in coords:
        if len(shape) == 2:
            index = pdc_reference.flat_index_2d(coord, normalized)  # type: ignore[arg-type]
        else:
            index = pdc_reference.flat_index_3d(coord, normalized)  # type: ignore[arg-type]
        if payload[index]:
            raise PdcRepresentationEvidenceError(f"duplicate coordinate in representation case: {coord}")
        payload[index] = 1
    return rep.DenseBinaryField(normalized, bytes(payload))


def _planar_outcome(field: rep.DenseBinaryField) -> dict[str, object]:
    q_values, r_values = pdc_reference.scalar_planar_counts(field.payload, field.shape)  # type: ignore[arg-type]
    summary = pdc_reference.planar_first_step_summary(field.payload, field.shape).to_dict()  # type: ignore[arg-type]
    return {
        "q_hash": pdc_reference.canonical_array_hash(q_values, field.shape, dtype="u8"),
        "r_hash": pdc_reference.canonical_array_hash(r_values, field.shape, dtype="u8"),
        "first_step": summary,
    }


def _binary_outcome(field: rep.DenseBinaryField) -> dict[str, object]:
    support = pdc_reference.scalar_moore_support(field.payload, field.shape)  # type: ignore[arg-type]
    next_state = pdc_reference.binary_next_state(field.payload, field.shape, support=support)  # type: ignore[arg-type]
    return {
        "support_hash": pdc_reference.canonical_array_hash(support, field.shape, dtype="u8"),
        "next_state_hash": pdc_reference.canonical_array_hash(next_state, field.shape, dtype="u8"),
        "next_active_count": sum(next_state),
    }


def _sparse_outcome(field: rep.DenseBinaryField) -> dict[str, object]:
    sparse = rep.sparse_from_dense(field)
    coords = tuple(pdc_reference.unflatten_3d(index, field.shape) for index in sparse.active_indices)  # type: ignore[arg-type]
    return pdc_reference.sparse_first_response(coords, field.shape).to_dict()  # type: ignore[arg-type]


ExpectedMatcher = Callable[[dict[str, object]], bool]
OutcomeFunction = Callable[[rep.DenseBinaryField], dict[str, object]]


def _evaluate_case(
    *,
    case_id: str,
    family: str,
    dense: rep.DenseBinaryField,
    outcome_function: OutcomeFunction,
    expected_matcher: ExpectedMatcher,
    ordinal: int,
) -> tuple[dict[str, object], list[str]]:
    failures: list[str] = []
    sparse = rep.sparse_from_dense(dense)
    bitpacked = rep.bitpacked_from_dense(dense)
    probability = rep.probability_from_dense(dense)
    native = rep.native_snapshot_from_dense(
        dense,
        byte_offset=ordinal % 8,
        row_padding_bytes=ordinal % 4,
        slice_padding_bytes=(ordinal // 4) % 4,
        declared_base_alignment=8,
    )
    restored = {
        "sparse": rep.dense_from_sparse(sparse),
        "bitpacked": rep.dense_from_bitpacked(bitpacked),
        "probability": rep.dense_from_probability(probability),
        "native": rep.dense_from_native(native),
    }
    baseline_hash = rep.dense_binary_semantic_hash(dense)
    for conversion, candidate in restored.items():
        if candidate != dense:
            failures.append(f"{conversion}_round_trip")
        if rep.dense_binary_semantic_hash(candidate) != baseline_hash:
            failures.append(f"{conversion}_semantic_hash")
    storage_hashes = {
        rep.representation_storage_hash(dense),
        rep.representation_storage_hash(sparse),
        rep.representation_storage_hash(bitpacked),
        rep.representation_storage_hash(probability),
        rep.representation_storage_hash(native),
    }
    if len(storage_hashes) != 5:
        failures.append("storage_hash_domain_separation")
    baseline_outcome = outcome_function(dense)
    converted_outcome = outcome_function(restored["native"])
    if baseline_outcome != converted_outcome:
        failures.append("pdc_result")
    if not expected_matcher(baseline_outcome):
        failures.append("source_expected_result")
    observation = {
        "id": case_id,
        "family": family,
        "shape": list(dense.shape),
        "active_count": sum(dense.payload),
        "semantic_hash": baseline_hash,
        "outcome_sha256": _json_digest(baseline_outcome),
        "storage_hash_set_sha256": _json_digest(sorted(storage_hashes)),
        "native_descriptor": {
            "byte_offset": native.byte_offset,
            "strides": list(native.strides),
            "source_mutability": native.source_mutability,
        },
        "failure_count": len(failures),
    }
    return observation, failures


def _golden_cases(golden: dict[str, object]) -> Iterator[tuple[str, str, rep.DenseBinaryField, OutcomeFunction, ExpectedMatcher]]:
    for case in golden["cases"]:  # type: ignore[index]
        family = case["family"]
        if family == "binary_3d":
            shape = tuple(case["shape"])
            coords = (tuple(coord) for coord in case["input"]["active_coords"])
            dense = _dense_from_coords(shape, coords)
            expected = case["expected"]
            matcher = lambda outcome, expected=expected: (
                outcome["support_hash"] == expected["support_hash"]
                and outcome["next_state_hash"] == expected["next_state_hash"]
                and outcome["next_active_count"] == expected["next_active_count"]
            )
            yield case["id"], "golden_binary_3d", dense, _binary_outcome, matcher
        elif family == "planar_first_step":
            shape = tuple(case["shape"])
            coords = (tuple(coord) for coord in case["input"]["defect_coords"])
            dense = _dense_from_coords(shape, coords)
            expected = case["expected"]
            matcher = lambda outcome, expected=expected: (
                outcome["q_hash"] == expected["q_hash"]
                and outcome["r_hash"] == expected["r_hash"]
                and outcome["first_step"] == expected["first_step"]
            )
            yield case["id"], "golden_planar", dense, _planar_outcome, matcher


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def _source_output_paths(workspace: Path, verifier: dict[str, object]) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for execution in verifier["source_executions"]:  # type: ignore[index]
        for output in execution["required_outputs"]:
            paths[output["id"]] = workspace / output["preserved_path"]
    return paths


def _rectangle_cases(rows: list[dict[str, str]]) -> Iterator[tuple[str, rep.DenseBinaryField, OutcomeFunction, ExpectedMatcher]]:
    if len(rows) != DECLARED_EXACT_COUNTS["rectangle"]:
        raise PdcRepresentationEvidenceError("rectangle source-row count changed")
    for ordinal, row in enumerate(rows):
        a, b = int(row["a"]), int(row["b"])
        shape = (a + 6, b + 6)
        dense = rep.DenseBinaryField(shape, bytes(pdc_reference.rectangle_defect_field(a, b, shape, origin=(3, 3))))
        matcher = lambda outcome, row=row: (
            outcome["first_step"]["total_births"] == int(row["births_raw_actual"])
            and outcome["first_step"]["deaths"] == int(row["deaths_actual"])
            and outcome["first_step"]["birth_spectrum"]
            == {"B5": int(row["n5_actual"]), "B6": int(row["n6_actual"]), "B7": int(row["n7_actual"])}
        )
        yield f"rectangle-{ordinal + 1:04d}", dense, _planar_outcome, matcher


def _line_cases(rows: list[dict[str, str]]) -> Iterator[tuple[str, rep.DenseBinaryField, OutcomeFunction, ExpectedMatcher]]:
    if len(rows) != DECLARED_EXACT_COUNTS["line_hole"]:
        raise PdcRepresentationEvidenceError("line source-row count changed")
    for row in rows:
        length = int(row["n"])
        shape = (7, length + 6)
        dense = rep.DenseBinaryField(shape, bytes(pdc_reference.line_defect_field(length, shape, origin=(3, 3), axis="y")))
        matcher = lambda outcome, row=row: (
            outcome["first_step"]["total_births"] == int(row["births_raw_actual"])
            and outcome["first_step"]["deaths"] == int(row["deaths_actual"])
            and outcome["first_step"]["birth_spectrum"]
            == {"B5": int(row["n5_actual"]), "B6": int(row["n6_actual"]), "B7": int(row["n7_actual"])}
        )
        yield f"line-hole-{length:03d}", dense, _planar_outcome, matcher


def _arbitrary_cases(rows: list[dict[str, str]]) -> Iterator[tuple[str, rep.DenseBinaryField, OutcomeFunction, ExpectedMatcher]]:
    if len(rows) != DECLARED_EXACT_COUNTS["arbitrary_mask"]:
        raise PdcRepresentationEvidenceError("arbitrary-mask source-row count changed")
    rng = np.random.default_rng(20260620)
    for case_id, row in enumerate(rows, start=1):
        box_w = int(rng.integers(3, 13))
        box_h = int(rng.integers(3, 13))
        density = float(rng.uniform(0.07, 0.62))
        coords = set()
        for x in range(box_w):
            for y in range(box_h):
                if rng.random() < density:
                    coords.add((x, y))
        if not coords:
            coords.add((box_w // 2, box_h // 2))
        if len(coords) == box_w * box_h:
            coords.remove((box_w // 2, box_h // 2))
        if (
            int(row["case_id"]) != case_id
            or int(row["box_w"]) != box_w
            or int(row["box_h"]) != box_h
            or abs(float(row["density"]) - round(density, 6)) > 5e-13
            or int(row["removed_count"]) != len(coords)
        ):
            raise PdcRepresentationEvidenceError(f"arbitrary-mask generator drift at case {case_id}")
        shape = (box_w + 6, box_h + 6)
        dense = _dense_from_coords(shape, ((x + 3, y + 3) for x, y in coords))
        matcher = lambda outcome, row=row: (
            outcome["first_step"]["total_births"] == int(row["actual_births"])
            and outcome["first_step"]["deaths"] == int(row["actual_deaths"])
            and outcome["first_step"]["in_plane_births"] == int(row["actual_plane_births"])
            and outcome["first_step"]["normal_layer_births"] == int(row["actual_adjacent_births"])
        )
        yield f"arbitrary-mask-{case_id:04d}", dense, _planar_outcome, matcher


def _nonplanar_cases(
    family: str, rows: list[dict[str, str]]
) -> Iterator[tuple[str, rep.DenseBinaryField, OutcomeFunction, ExpectedMatcher]]:
    selected = [row for row in rows if row["family"] == family]
    if len(selected) != DECLARED_EXACT_COUNTS[family]:
        raise PdcRepresentationEvidenceError(f"{family} source-row count changed")
    shape = (40, 40, 40)
    for ordinal, row in enumerate(selected, start=1):
        a, b, c = int(row["a"]), int(row["b"]), int(row["c"])
        coords = (
            pdc_reference.solid_cuboid_coords(a, b, c, shape)
            if family == "solid_cuboid"
            else pdc_reference.closed_surface_shell_coords(a, b, c, shape)
        )
        dense = _dense_from_coords(shape, coords)
        matcher = lambda outcome, row=row: (
            outcome["initial_active"] == int(row["initial_active"])
            and outcome["births"] == int(row["births"])
            and outcome["deaths"] == int(row["deaths"])
            and outcome["final_active"] == int(row["final_active"])
            and outcome["birth_spectrum"]
            == {"B5": int(row["B5"]), "B6": int(row["B6"]), "B7": int(row["B7"])}
        )
        yield f"{family}-{ordinal:04d}", dense, _sparse_outcome, matcher


def _run_negative_checks() -> list[dict[str, object]]:
    def invalid_dense() -> None:
        rep.dense_binary_field((0,) * 24 + (2,), (5, 5))

    def duplicate_sparse() -> None:
        rep.SparseBinaryField((5, 5), (1, 1))

    def out_of_range_sparse() -> None:
        rep.SparseBinaryField((5, 5), (25,))

    def nonzero_padding() -> None:
        rep.BitPackedBinaryField((5, 5), b"\x00\x00\x00\x80")

    def nonfinite_probability() -> None:
        rep.ProbabilityField((5, 5), (float("nan"),) + (0.0,) * 24)

    def lossy_probability() -> None:
        rep.dense_from_probability(rep.ProbabilityField((5, 5), (0.5,) + (0.0,) * 24))

    def borrowed_without_snapshot() -> None:
        rep.make_native_buffer_snapshot(
            bytearray(25),
            shape=(5, 5),
            dtype="u8",
            source_ownership="caller_borrowed",
            declared_base_alignment=1,
        )

    def overlapping_stride() -> None:
        rep.make_native_buffer_snapshot(
            bytearray(64),
            shape=(5, 5),
            dtype="u8",
            strides=(1, 4),
            source_ownership="runtime_owned",
            declared_base_alignment=1,
        )

    def misaligned_f64() -> None:
        rep.make_native_buffer_snapshot(
            bytearray(256),
            shape=(5, 5),
            dtype="f64",
            byte_offset=1,
            strides=(8, 40),
            source_ownership="runtime_owned",
            declared_base_alignment=8,
        )

    def short_buffer() -> None:
        rep.make_native_buffer_snapshot(
            bytearray(24),
            shape=(5, 5),
            dtype="u8",
            source_ownership="runtime_owned",
            declared_base_alignment=1,
        )

    def noncontiguous_buffer() -> None:
        rep.make_native_buffer_snapshot(
            memoryview(bytearray(64))[::2],
            shape=(5, 5),
            dtype="u8",
            source_ownership="runtime_owned",
            declared_base_alignment=1,
        )

    checks = [
        ("invalid_dense_value", invalid_dense),
        ("duplicate_sparse_index", duplicate_sparse),
        ("out_of_range_sparse_index", out_of_range_sparse),
        ("nonzero_bit_padding", nonzero_padding),
        ("nonfinite_probability", nonfinite_probability),
        ("lossy_probability_conversion", lossy_probability),
        ("borrowed_without_snapshot", borrowed_without_snapshot),
        ("overlapping_native_stride", overlapping_stride),
        ("misaligned_native_f64", misaligned_f64),
        ("short_native_buffer", short_buffer),
        ("noncontiguous_native_buffer", noncontiguous_buffer),
        ("u64_add_overflow", lambda: rep.checked_u64_add(rep.MAX_U64, 1)),
        ("u64_multiply_overflow", lambda: rep.checked_u64_multiply(2**63, 2)),
    ]
    results = []
    for check_id, function in checks:
        try:
            function()
        except pdc_reference.PdcContractError as exc:
            results.append({"id": check_id, "passed": True, "error_type": type(exc).__name__})
        else:
            results.append({"id": check_id, "passed": False, "error_type": "none"})
    return results


def make_representation_receipt(
    *,
    workspace: Path,
    representation_contract_path: Path,
    math_contract_path: Path,
    golden_vectors_path: Path,
    verifier_reproduction_path: Path,
) -> dict[str, object]:
    contract = _load_json(representation_contract_path)
    math_contract = _load_json(math_contract_path)
    golden = _load_json(golden_vectors_path)
    verifier = _load_json(verifier_reproduction_path)
    if contract.get("abi_version") != rep.ABI_VERSION or contract.get("status") != "pass":
        raise PdcRepresentationEvidenceError("representation receipt requires a passing PDC-REP-0.1 contract")
    expected_bindings = {
        "reference_implementation_sha256": pdc_verifier_intake.sha256_file(
            workspace / "runtime" / "pdc_representation.py"
        ),
        "math_contract_sha256": pdc_verifier_intake.sha256_file(math_contract_path),
        "golden_vectors_sha256": pdc_verifier_intake.sha256_file(golden_vectors_path),
        "verifier_reproduction_sha256": pdc_verifier_intake.sha256_file(verifier_reproduction_path),
    }
    if any(contract["bindings"].get(name) != digest for name, digest in expected_bindings.items()):
        raise PdcRepresentationEvidenceError("representation contract parent binding changed")
    if math_contract.get("contract_version") != "PDC-MATH-0.1":
        raise PdcRepresentationEvidenceError("unsupported math contract")
    if golden["summary"]["case_count"] != GOLDEN_DECLARED_COUNT:
        raise PdcRepresentationEvidenceError("golden vector count changed")
    if verifier["summary"]["independent_case_count"] != sum(DECLARED_EXACT_COUNTS.values()):
        raise PdcRepresentationEvidenceError("exact verifier case count changed")

    family_observations: dict[str, list[dict[str, object]]] = {}
    family_failures: dict[str, list[str]] = {}
    ordinal = 0

    for case_id, family, dense, outcome_function, matcher in _golden_cases(golden):
        observation, failures = _evaluate_case(
            case_id=case_id,
            family=family,
            dense=dense,
            outcome_function=outcome_function,
            expected_matcher=matcher,
            ordinal=ordinal,
        )
        family_observations.setdefault(family, []).append(observation)
        family_failures.setdefault(family, []).extend(f"{case_id}:{failure}" for failure in failures)
        ordinal += 1

    outputs = _source_output_paths(workspace, verifier)
    exact_generators = {
        "rectangle": _rectangle_cases(_csv_rows(outputs["rectangle"])),
        "line_hole": _line_cases(_csv_rows(outputs["line_hole"])),
        "arbitrary_mask": _arbitrary_cases(_csv_rows(outputs["arbitrary_mask"])),
    }
    nonplanar_rows = _csv_rows(outputs["nonplanar_rows"])
    exact_generators["solid_cuboid"] = _nonplanar_cases("solid_cuboid", nonplanar_rows)
    exact_generators["surface_shell"] = _nonplanar_cases("surface_shell", nonplanar_rows)

    exact_results = []
    for family, cases in exact_generators.items():
        observations: list[dict[str, object]] = []
        failures: list[str] = []
        for case_id, dense, outcome_function, matcher in cases:
            observation, case_failures = _evaluate_case(
                case_id=case_id,
                family=family,
                dense=dense,
                outcome_function=outcome_function,
                expected_matcher=matcher,
                ordinal=ordinal,
            )
            observations.append(observation)
            failures.extend(f"{case_id}:{failure}" for failure in case_failures)
            ordinal += 1
        declared = DECLARED_EXACT_COUNTS[family]
        exact_results.append(
            {
                "id": family,
                "declared_case_count": declared,
                "tested_case_count": len(observations),
                "excluded_case_count": 0,
                "round_trip_count": len(observations) * ROUND_TRIPS_PER_CASE,
                "pdc_result_match_count": len(observations) - sum("pdc_result" in failure for failure in failures),
                "source_result_match_count": len(observations) - sum("source_expected_result" in failure for failure in failures),
                "mismatch_count": len(failures),
                "cases_digest_sha256": _json_digest(observations),
                "status": "pass" if not failures and len(observations) == declared else "fail",
            }
        )

    inversion_rows = _csv_rows(outputs["inversion"])
    inversion_source_failures = sum(
        row.get("raw_match") != "True" or row.get("prime_match") != "True" for row in inversion_rows
    )
    exact_results.insert(
        3,
        {
            "id": "inversion",
            "declared_case_count": DECLARED_EXACT_COUNTS["inversion"],
            "tested_case_count": 0,
            "excluded_case_count": len(inversion_rows),
            "round_trip_count": 0,
            "pdc_result_match_count": 0,
            "source_result_match_count": len(inversion_rows) - inversion_source_failures,
            "mismatch_count": inversion_source_failures,
            "cases_digest_sha256": _json_digest(inversion_rows),
            "status": "excluded_non_field_formula_family" if not inversion_source_failures else "fail",
        },
    )

    golden_observations = [item for items in family_observations.values() for item in items]
    golden_failures = [failure for failures in family_failures.values() for failure in failures]
    negative_checks = _run_negative_checks()

    probability_probe = rep.ProbabilityField((5, 5), tuple(index / 24 for index in range(25)))
    probability_native = rep.native_snapshot_from_probability(
        probability_probe,
        byte_offset=8,
        row_padding_bytes=16,
        declared_base_alignment=16,
    )
    probability_probe_ok = (
        rep.probability_from_native(probability_native) == probability_probe
        and rep.probability_semantic_hash(probability_native) == rep.probability_semantic_hash(probability_probe)
    )

    exact_tested = sum(item["tested_case_count"] for item in exact_results)
    exact_excluded = sum(item["excluded_case_count"] for item in exact_results)
    exact_mismatches = sum(item["mismatch_count"] for item in exact_results)
    total_mismatches = exact_mismatches + len(golden_failures) + sum(not item["passed"] for item in negative_checks) + int(not probability_probe_ok)
    status = "pass_with_explicit_formula_exclusions" if total_mismatches == 0 else "fail"
    if status == "fail":
        raise PdcRepresentationEvidenceError(
            f"representation differential evidence failed: exact={exact_mismatches}, golden={golden_failures[:3]}, "
            f"negative={sum(not item['passed'] for item in negative_checks)}, probability_probe={probability_probe_ok}"
        )
    return {
        "schema_version": "0.1",
        "artifact_kind": "pdc_representation_receipt",
        "abi_version": rep.ABI_VERSION,
        "created_utc": _created_utc(),
        "status": status,
        "bindings": {
            "reference_implementation_path": "runtime/pdc_representation.py",
            "reference_implementation_sha256": pdc_verifier_intake.sha256_file(
                workspace / "runtime" / "pdc_representation.py"
            ),
            "representation_contract_path": _relative(representation_contract_path, workspace),
            "representation_contract_sha256": pdc_verifier_intake.sha256_file(representation_contract_path),
            "math_contract_path": _relative(math_contract_path, workspace),
            "math_contract_sha256": pdc_verifier_intake.sha256_file(math_contract_path),
            "golden_vectors_path": _relative(golden_vectors_path, workspace),
            "golden_vectors_sha256": pdc_verifier_intake.sha256_file(golden_vectors_path),
            "verifier_reproduction_path": _relative(verifier_reproduction_path, workspace),
            "verifier_reproduction_sha256": pdc_verifier_intake.sha256_file(verifier_reproduction_path),
        },
        "environment": {
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "executable": sys.executable,
            "numpy_version": np.__version__,
        },
        "golden_corpus": {
            "declared_case_count": GOLDEN_DECLARED_COUNT,
            "representation_applicable_case_count": len(golden_observations),
            "excluded_formula_case_count": GOLDEN_DECLARED_COUNT - len(golden_observations),
            "round_trip_count": len(golden_observations) * ROUND_TRIPS_PER_CASE,
            "pdc_result_match_count": len(golden_observations),
            "mismatch_count": len(golden_failures),
            "cases_digest_sha256": _json_digest(golden_observations),
            "status": "pass_with_formula_exclusions",
        },
        "exact_family_results": exact_results,
        "probability_native_probe": {
            "case_count": 1,
            "round_trip_match": probability_probe_ok,
            "semantic_hash_match": probability_probe_ok,
            "storage_hash_sha256": rep.representation_storage_hash(probability_native),
            "status": "pass" if probability_probe_ok else "fail",
        },
        "negative_checks": negative_checks,
        "digests": {
            "exact_family_set_sha256": _json_digest(exact_results),
            "negative_check_set_sha256": _json_digest(negative_checks),
        },
        "summary": {
            "representation_count": 5,
            "conversion_path_count": 10,
            "round_trips_per_applicable_binary_case": ROUND_TRIPS_PER_CASE,
            "golden_declared_case_count": GOLDEN_DECLARED_COUNT,
            "golden_applicable_case_count": len(golden_observations),
            "golden_excluded_formula_case_count": GOLDEN_DECLARED_COUNT - len(golden_observations),
            "exact_declared_case_count": sum(DECLARED_EXACT_COUNTS.values()),
            "exact_applicable_case_count": exact_tested,
            "exact_excluded_formula_case_count": exact_excluded,
            "differential_case_count": len(golden_observations) + exact_tested,
            "round_trip_count": (len(golden_observations) + exact_tested) * ROUND_TRIPS_PER_CASE,
            "pdc_result_match_count": len(golden_observations) + exact_tested,
            "negative_check_count": len(negative_checks),
            "failed_negative_check_count": sum(not item["passed"] for item in negative_checks),
            "mismatch_count": total_mismatches,
        },
        "exclusions": [
            "Three golden formula-only cases have no lattice payload to convert.",
            "The 1,225 inversion rows are scalar area/response formula records with no lattice payload; their source pass fields and digest remain bound and verified.",
        ],
        "claim_boundary": [
            "The receipt proves checked Python reference conversions over all representation-applicable golden and exact verifier cases.",
            "Exact dense equality plus a repeated scalar PDC evaluation proves semantic preservation for each applicable case.",
            "This is not a native C ABI, performance result, mutable-buffer safety proof, device-memory contract, kernel enforcement, or all-size theorem.",
        ],
    }
