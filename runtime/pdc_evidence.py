"""Schema-ready PDC math-contract and golden-vector artifacts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from . import pdc_reference
from .pdc_source_intake import sha256_file


def _created_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"artifact root must be an object: {path}")
    return value


def make_math_contract(*, source_intake_path: Path, workspace: Path) -> dict[str, object]:
    intake = _load_json(source_intake_path)
    if intake.get("artifact_kind") != "pdc_source_intake" or intake.get("status") != "pass":
        raise ValueError("math contract requires a passing PDC source intake")
    relative_intake = source_intake_path.resolve().relative_to(workspace.resolve()).as_posix()
    source_set_digest = intake["digests"]["designated_source_set_sha256"]
    return {
        "schema_version": "0.1",
        "artifact_kind": "pdc_math_contract",
        "contract_version": "PDC-MATH-0.1",
        "created_utc": _created_utc(),
        "status": "pass",
        "source_binding": {
            "artifact_path": relative_intake,
            "artifact_sha256": sha256_file(source_intake_path),
            "designated_source_set_sha256": source_set_digest,
        },
        "binary_model": {
            "model_tag": "B5-7/S5-9",
            "state_set": [0, 1],
            "update_expression": "x_next[i] = 1{5 <= n[i] <= 7 + 2*x[i]}",
            "birth_window": [5, 7],
            "survival_window": [5, 9],
            "capacity_expression": "C[i] = 7 + 2*x[i]",
            "deficit_expression": "D[i] = max(5 - n[i], 0)",
            "excess_expression": "E[i] = max(n[i] - C[i], 0)",
            "strain_expression": "psi[i] = E[i] - D[i]",
            "strain_is_not_acceptance_predicate": True,
        },
        "coordinates": {
            "coordinate_order": ["x", "y", "z"],
            "shape_order": ["x_extent", "y_extent", "z_extent"],
            "flat_order": "x_fastest_then_y_then_z",
            "flat_index_3d": "((z*y_extent)+y)*x_extent+x",
            "flat_index_2d": "y*x_extent+x",
            "origin": [0, 0, 0],
        },
        "boundary": {
            "mode": "periodic",
            "minimum_extent": pdc_reference.MIN_PERIODIC_EXTENT,
            "small_extent_policy": "reject",
            "reason": "Extents below 3 alias distinct Moore offsets and are outside PDC-MATH-0.1.",
        },
        "matrices": [
            {
                "id": "T_n",
                "dimensions": 1,
                "expression": "T_n = S_n^-1 + I_n + S_n",
                "semantics": "closed periodic radius-one support",
            },
            {
                "id": "A26",
                "dimensions": 3,
                "expression": "A26 = kron(T_z, kron(T_y, T_x)) - I_(x*y*z)",
                "semantics": "26-neighbor Moore support with x-fastest flattening",
            },
            {
                "id": "A8",
                "dimensions": 2,
                "expression": "A8 = kron(T_y, T_x) - I_(x*y)",
                "semantics": "open planar 8-neighbor defect count q",
            },
            {
                "id": "A9",
                "dimensions": 2,
                "expression": "A9 = kron(T_y, T_x)",
                "semantics": "closed planar 3x3 defect count r",
            },
        ],
        "typed_channels": {
            "birth": "B_k = (1-x) .* 1{n=k}",
            "survival": "S_k = x .* 1{n=k}",
            "overflow": "O10+ = x .* 1{n>=10}",
            "preserved_feature_order": ["B5", "B6", "B7", "S5", "S6", "S7", "S8", "S9", "O10+", "psi"],
        },
        "planar_first_step": {
            "active_survival": "q <= 3",
            "active_death": "q >= 4",
            "in_plane_birth": "1 <= q <= 3",
            "normal_layer_birth": "2 <= r <= 4",
            "far_layer_behavior": "inactive at first step",
            "normal_channel_map": {"r=2": "B7", "r=3": "B6", "r=4": "B5"},
        },
        "numerical_contract": {
            "state": "u8",
            "support_n": "u8",
            "capacity": "u8",
            "deficit": "u8",
            "excess": "u8",
            "strain": "i8",
            "aggregate_counts": "u64",
            "maximum_support": 26,
            "maximum_strain": 19,
            "minimum_strain": -5,
            "maximum_reference_cells": pdc_reference.MAX_REFERENCE_CELLS,
            "maximum_dense_matrix_cells": pdc_reference.MAX_DENSE_MATRIX_CELLS,
            "checked_shape_and_byte_arithmetic": True,
        },
        "canonical_hash": {
            "algorithm": "SHA-256",
            "header_encoding": "canonical ASCII JSON with sorted keys and compact separators",
            "separator_hex": "00",
            "payload_order": "x_fastest_then_y_then_z",
            "byte_order": "little",
            "header_fields": ["axis_order", "byte_order", "dtype", "shape"],
        },
        "variant_policy": {
            "raw_model_tag": "B5-7/S5-9",
            "pmphi_model_tag": "PMphi.default.remove_B7",
            "pmphi_is_distinct_model": True,
            "implicit_variant_conversion": False,
        },
        "reference_oracles": {
            "scalar": "runtime.pdc_reference.scalar_moore_support/scalar_planar_counts",
            "matrix": "runtime.pdc_reference.matrix_moore_support/matrix_planar_counts",
            "matrix_is_specification_only": True,
            "optimized_routes_must_match_both": True,
        },
        "claim_boundary": [
            "The contract freezes executable discrete mathematics, not a physical spacetime or hardware law.",
            "PMphi is model-tagged and must not be represented as the raw B5-7/S5-9 rule.",
            "Golden vectors are verifier evidence, not all-size theorem proofs or production backend evidence.",
            "Q/P, signed dynamics, optimized backends, PooleGlyph lowering, kernel enforcement, UI, and ISO remain later phase obligations.",
        ],
    }


def _field_3d(shape: pdc_reference.Shape3, active_coords: Iterable[pdc_reference.Coord3]) -> tuple[int, ...]:
    _, count = pdc_reference.validate_periodic_shape(shape, dimensions=3)
    field = [0] * count
    for coord in active_coords:
        field[pdc_reference.flat_index_3d(coord, shape)] = 1
    return tuple(field)


def _binary_case(
    case_id: str,
    *,
    shape: pdc_reference.Shape3,
    active_coords: Iterable[pdc_reference.Coord3],
    selected_coords: Iterable[pdc_reference.Coord3],
) -> dict[str, object]:
    active = tuple(active_coords)
    field = _field_3d(shape, active)
    scalar = pdc_reference.scalar_moore_support(field, shape)
    matrix = pdc_reference.matrix_moore_support(field, shape)
    if scalar != matrix:
        raise AssertionError(f"scalar/matrix mismatch in {case_id}")
    measurements = pdc_reference.measure_binary_field(field, shape, support=scalar)
    next_state = tuple(item.next_state for item in measurements)
    selected = []
    for coord in selected_coords:
        index = pdc_reference.flat_index_3d(coord, shape)
        selected.append({"coord": list(coord), **measurements[index].to_dict()})
    return {
        "id": case_id,
        "family": "binary_3d",
        "claim_class": "verifier",
        "model_tag": "B5-7/S5-9",
        "shape": list(shape),
        "input": {"encoding": "sparse_active_coords", "active_coords": [list(coord) for coord in active]},
        "expected": {
            "input_hash": pdc_reference.canonical_array_hash(field, shape, dtype="u8"),
            "support_hash": pdc_reference.canonical_array_hash(scalar, shape, dtype="u8"),
            "next_state_hash": pdc_reference.canonical_array_hash(next_state, shape, dtype="u8"),
            "active_count": sum(field),
            "next_active_count": sum(next_state),
            "accepted_channels": pdc_reference.channel_counts(measurements, accepted_only=True),
            "selected_sites": selected,
        },
        "oracle": {"scalar": "scalar_moore_support", "matrix": "matrix_moore_support", "agreement": True},
        "source_ids": ["SRC-LG-1", "SRC-MAG-1"],
    }


def _planar_case(
    case_id: str,
    *,
    shape: pdc_reference.Shape2,
    defects: tuple[int, ...],
    expected_formula: dict[str, object] | None = None,
) -> dict[str, object]:
    scalar_q, scalar_r = pdc_reference.scalar_planar_counts(defects, shape)
    matrix_q, matrix_r = pdc_reference.matrix_planar_counts(defects, shape)
    if scalar_q != matrix_q or scalar_r != matrix_r:
        raise AssertionError(f"scalar/matrix planar mismatch in {case_id}")
    summary = pdc_reference.planar_first_step_summary(defects, shape).to_dict()
    if expected_formula is not None:
        for key in ("births", "deaths", "birth_spectrum"):
            summary_key = "total_births" if key == "births" else key
            if summary[summary_key] != expected_formula[key]:
                raise AssertionError(f"planar formula mismatch in {case_id}: {key}")
    coords = [list(pdc_reference.unflatten_2d(index, shape)) for index, value in enumerate(defects) if value]
    return {
        "id": case_id,
        "family": "planar_first_step",
        "claim_class": "verifier",
        "model_tag": "B5-7/S5-9",
        "shape": list(shape),
        "input": {"encoding": "sparse_defect_coords", "defect_coords": coords},
        "expected": {
            "input_hash": pdc_reference.canonical_array_hash(defects, shape, dtype="u8"),
            "q_hash": pdc_reference.canonical_array_hash(scalar_q, shape, dtype="u8"),
            "r_hash": pdc_reference.canonical_array_hash(scalar_r, shape, dtype="u8"),
            "first_step": summary,
        },
        "oracle": {"scalar": "scalar_planar_counts", "matrix": "matrix_planar_counts", "agreement": True},
        "source_ids": ["SRC-LG-1", "SRC-MAG-1"],
    }


def _formula_case(case_id: str, family: str, model_tag: str, inputs: dict[str, int], result: dict[str, object]) -> dict[str, object]:
    return {
        "id": case_id,
        "family": family,
        "claim_class": "verifier",
        "model_tag": model_tag,
        "shape": [],
        "input": inputs,
        "expected": result,
        "oracle": {"scalar": "closed_formula", "matrix": "not_applicable", "agreement": True},
        "source_ids": ["SRC-LG-1", "SRC-MAG-1"],
    }


def make_golden_vectors(*, math_contract_path: Path, workspace: Path) -> dict[str, object]:
    contract = _load_json(math_contract_path)
    if contract.get("artifact_kind") != "pdc_math_contract" or contract.get("status") != "pass":
        raise ValueError("golden vectors require a passing PDC math contract")
    relative_contract = math_contract_path.resolve().relative_to(workspace.resolve()).as_posix()

    center5 = (2, 2, 2)
    axis_neighbors = ((1, 2, 2), (3, 2, 2), (2, 1, 2), (2, 3, 2), (2, 2, 1), (2, 2, 3))
    cases: list[dict[str, object]] = [
        _binary_case("binary-empty-l3", shape=(3, 3, 3), active_coords=(), selected_coords=((1, 1, 1),)),
        _binary_case(
            "binary-full-l3",
            shape=(3, 3, 3),
            active_coords=((x, y, z) for z in range(3) for y in range(3) for x in range(3)),
            selected_coords=((1, 1, 1),),
        ),
        _binary_case("binary-singleton-l5", shape=(5, 5, 5), active_coords=(center5,), selected_coords=(center5, (2, 2, 1))),
        _binary_case(
            "binary-six-support-birth-l5",
            shape=(5, 5, 5),
            active_coords=axis_neighbors,
            selected_coords=(center5,),
        ),
        _binary_case(
            "binary-periodic-wrap-l5",
            shape=(5, 5, 5),
            active_coords=((4, 0, 0),),
            selected_coords=((0, 0, 0), (4, 0, 0)),
        ),
    ]

    singleton_shape = (5, 5)
    singleton = pdc_reference.defect_field_2d(singleton_shape, ((2, 2),))
    cases.append(_planar_case("planar-singleton-l5", shape=singleton_shape, defects=singleton, expected_formula=pdc_reference.line_hole_formula(1)))

    rectangle2_shape = (6, 6)
    rectangle2 = pdc_reference.rectangle_defect_field(2, 2, rectangle2_shape, origin=(2, 2))
    cases.append(
        _planar_case(
            "planar-rectangle-2x2",
            shape=rectangle2_shape,
            defects=rectangle2,
            expected_formula=pdc_reference.rectangle_formula(2, 2),
        )
    )
    rectangle34_shape = (7, 8)
    rectangle34 = pdc_reference.rectangle_defect_field(3, 4, rectangle34_shape, origin=(2, 2))
    cases.append(
        _planar_case(
            "planar-rectangle-3x4",
            shape=rectangle34_shape,
            defects=rectangle34,
            expected_formula=pdc_reference.rectangle_formula(3, 4),
        )
    )

    for length in (2, 5):
        line_shape = (length + 4, 5)
        line = pdc_reference.line_defect_field(length, line_shape, origin=(2, 2), axis="x")
        cases.append(
            _planar_case(
                f"planar-line-{length}",
                shape=line_shape,
                defects=line,
                expected_formula=pdc_reference.line_hole_formula(length),
            )
        )

    cases.extend(
        [
            _formula_case(
                "formula-rectangle-pmphi-3x4",
                "rectangle_variant",
                "PMphi.default.remove_B7",
                {"width": 3, "height": 4},
                pdc_reference.rectangle_formula(3, 4, model_tag="PMphi.default.remove_B7"),
            ),
            _formula_case(
                "formula-cuboid-4x5x6",
                "solid_cuboid",
                "B5-7/S5-9",
                {"a": 4, "b": 5, "c": 6},
                pdc_reference.cuboid_formula(4, 5, 6),
            ),
            _formula_case(
                "formula-shell-4x5x6",
                "closed_shell",
                "B5-7/S5-9",
                {"a": 4, "b": 5, "c": 6},
                pdc_reference.closed_shell_formula(4, 5, 6),
            ),
        ]
    )

    matrix_scalar_cases = sum(case["oracle"]["matrix"] != "not_applicable" for case in cases)
    return {
        "schema_version": "0.1",
        "artifact_kind": "pdc_golden_vectors",
        "vector_set_version": "PDC-GOLDEN-0.1",
        "created_utc": _created_utc(),
        "status": "pass",
        "math_contract_binding": {
            "artifact_path": relative_contract,
            "artifact_sha256": sha256_file(math_contract_path),
            "contract_version": contract["contract_version"],
        },
        "cases": cases,
        "summary": {
            "case_count": len(cases),
            "passed_count": len(cases),
            "failed_count": 0,
            "matrix_scalar_agreement_case_count": matrix_scalar_cases,
            "binary_case_count": sum(case["family"] == "binary_3d" for case in cases),
            "planar_case_count": sum(case["family"] == "planar_first_step" for case in cases),
            "formula_case_count": sum(case["oracle"]["matrix"] == "not_applicable" for case in cases),
        },
        "limitations": [
            "The dense matrix oracle is intentionally bounded and is not a production execution route.",
            "The vectors cover canonical edge and theorem examples but do not replace the full imported verifier corpus.",
            "Q/P probability, signed dynamics, optimized backends, PooleGlyph lowering, kernel enforcement, UI, and ISO are out of this vector-set scope.",
        ],
    }
