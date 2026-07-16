"""Published boundary and metamorphic corpus for PDC-GOLDEN-0.2."""

from __future__ import annotations

import itertools
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

from runtime import pdc_reference
from runtime import pdc_representation as rep
from runtime import pdc_verifier_intake


CORPUS_VERSION = "PDC-GOLDEN-0.2"
THRESHOLD_PAIR_COUNT = 54
ADVERSARIAL_CASE_COUNT = 8
TRANSLATION_RELATION_COUNT = 32
AXIS_PERMUTATION_RELATION_COUNT = 40
METAMORPHIC_RELATION_COUNT = 72
NON_RELATION_COUNT = 6
NEGATIVE_CHECK_COUNT = 10
ROUND_TRIPS_PER_FIELD = 4
ORACLE_FIELD_EVALUATION_COUNT = 206
REPRESENTATION_ROUND_TRIP_COUNT = 824

Shape3 = tuple[int, int, int]
Coord3 = tuple[int, int, int]


class PdcGoldenMetamorphicError(ValueError):
    """Raised when the published corpus or its receipt cannot be reproduced."""


def _created_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _relative(path: Path, workspace: Path) -> str:
    return path.resolve().relative_to(workspace.resolve()).as_posix()


def _json_digest(value: object) -> str:
    return pdc_verifier_intake.sha256_json(value)


def _normalize_shape(shape: Sequence[int]) -> Shape3:
    normalized, _ = pdc_reference.validate_periodic_shape(tuple(shape), dimensions=3)
    return normalized  # type: ignore[return-value]


def _normalize_values(values: Sequence[int], shape: Sequence[int]) -> tuple[tuple[int, ...], Shape3]:
    normalized = _normalize_shape(shape)
    count = pdc_reference.checked_product(normalized)
    if len(values) != count:
        raise pdc_reference.PdcShapeError("value count does not match transform shape")
    return tuple(values), normalized


def _flat(coord: Sequence[int], shape: Shape3) -> int:
    if len(coord) != 3:
        raise pdc_reference.PdcShapeError("coordinate must have three axes")
    x, y, z = coord
    if any(isinstance(value, bool) or not isinstance(value, int) for value in coord):
        raise pdc_reference.PdcShapeError("coordinate values must be integers")
    if not (0 <= x < shape[0] and 0 <= y < shape[1] and 0 <= z < shape[2]):
        raise pdc_reference.PdcShapeError("coordinate is outside transform shape")
    return (z * shape[1] + y) * shape[0] + x


def _coords(shape: Shape3):
    for z in range(shape[2]):
        for y in range(shape[1]):
            for x in range(shape[0]):
                yield x, y, z


def _neighbor_coords(coord: Coord3, shape: Shape3) -> tuple[Coord3, ...]:
    x, y, z = coord
    return tuple(
        ((x + dx) % shape[0], (y + dy) % shape[1], (z + dz) % shape[2])
        for dz in (-1, 0, 1)
        for dy in (-1, 0, 1)
        for dx in (-1, 0, 1)
        if (dx, dy, dz) != (0, 0, 0)
    )


def translate_values(values: Sequence[int], shape: Sequence[int], shift: Sequence[int]) -> tuple[int, ...]:
    """Translate an x-fastest periodic field or vector without assuming binary values."""

    normalized_values, normalized_shape = _normalize_values(values, shape)
    if len(shift) != 3:
        raise pdc_reference.PdcShapeError("translation must contain three axis offsets")
    if any(isinstance(value, bool) or not isinstance(value, int) for value in shift):
        raise pdc_reference.PdcContractError("translation offsets must be integers")
    output = [0] * len(normalized_values)
    for coord in _coords(normalized_shape):
        target = tuple((coord[axis] + shift[axis]) % normalized_shape[axis] for axis in range(3))
        output[_flat(target, normalized_shape)] = normalized_values[_flat(coord, normalized_shape)]
    return tuple(output)


def permute_axes(
    values: Sequence[int],
    shape: Sequence[int],
    order: Sequence[int],
) -> tuple[tuple[int, ...], Shape3]:
    """Permute shape and coordinates together using old-axis indices in new-axis order."""

    normalized_values, normalized_shape = _normalize_values(values, shape)
    if len(order) != 3 or any(isinstance(value, bool) or not isinstance(value, int) for value in order):
        raise pdc_reference.PdcContractError("axis order must contain three integer axes")
    if tuple(sorted(order)) != (0, 1, 2):
        raise pdc_reference.PdcContractError("axis order must be a permutation of (0,1,2)")
    new_shape = tuple(normalized_shape[axis] for axis in order)
    output = [0] * len(normalized_values)
    for coord in _coords(normalized_shape):
        target = tuple(coord[axis] for axis in order)
        output[_flat(target, new_shape)] = normalized_values[_flat(coord, normalized_shape)]
    return tuple(output), new_shape  # type: ignore[return-value]


def require_supported_boundary(boundary_mode: str) -> None:
    if boundary_mode != "periodic":
        raise pdc_reference.PdcContractError("PDC-GOLDEN-0.2 supports only the tagged periodic boundary")


def independent_support(values: Sequence[int], shape: Sequence[int]) -> tuple[int, ...]:
    """Direct stencil kept separate from both pdc_reference support implementations."""

    normalized_values, normalized_shape = _normalize_values(values, shape)
    if any(value not in (0, 1) for value in normalized_values):
        raise pdc_reference.PdcContractError("independent support requires a binary field")
    output = [0] * len(normalized_values)
    for coord in _coords(normalized_shape):
        output[_flat(coord, normalized_shape)] = sum(
            normalized_values[_flat(neighbor, normalized_shape)]
            for neighbor in _neighbor_coords(coord, normalized_shape)
        )
    return tuple(output)


def independent_measurement(state: int, support: int) -> dict[str, int | str | bool]:
    if isinstance(state, bool) or state not in (0, 1):
        raise pdc_reference.PdcContractError("threshold state must be integer zero or one")
    if isinstance(support, bool) or not isinstance(support, int) or not 0 <= support <= 26:
        raise pdc_reference.PdcContractError("threshold support must be an integer in [0,26]")
    capacity = 9 if state else 7
    deficit = max(5 - support, 0)
    excess = max(support - capacity, 0)
    accepted = 5 <= support <= capacity
    channel = ("O10+" if support >= 10 else f"S{support}") if state else f"B{support}"
    return {
        "support": support,
        "capacity": capacity,
        "deficit": deficit,
        "excess": excess,
        "strain": excess - deficit,
        "channel": channel,
        "accepted": accepted,
        "next_state": int(accepted),
    }


def independent_next(values: Sequence[int], shape: Sequence[int], support: Sequence[int] | None = None) -> tuple[int, ...]:
    normalized_values, normalized_shape = _normalize_values(values, shape)
    support_values = tuple(support) if support is not None else independent_support(normalized_values, normalized_shape)
    if len(support_values) != len(normalized_values):
        raise pdc_reference.PdcShapeError("support vector does not match field")
    return tuple(
        int(independent_measurement(state, count)["next_state"])
        for state, count in zip(normalized_values, support_values, strict=True)
    )


def _values_hash(values: Sequence[int], shape: Shape3) -> str:
    return pdc_reference.canonical_array_hash(tuple(values), shape, dtype="u8")


def _threshold_field(state: int, support: int) -> tuple[tuple[int, ...], Shape3, Coord3]:
    independent_measurement(state, support)
    shape: Shape3 = (5, 5, 5)
    target: Coord3 = (2, 2, 2)
    field = [0] * 125
    field[_flat(target, shape)] = state
    for neighbor in _neighbor_coords(target, shape)[:support]:
        field[_flat(neighbor, shape)] = 1
    return tuple(field), shape, target


def _field_from_active_indices(shape: Shape3, active_indices: Sequence[int]) -> tuple[int, ...]:
    count = pdc_reference.checked_product(shape)
    if tuple(active_indices) != tuple(sorted(set(active_indices))):
        raise PdcGoldenMetamorphicError("fixture active indices must be sorted and unique")
    if any(isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < count for index in active_indices):
        raise PdcGoldenMetamorphicError("fixture active index is outside the field")
    field = [0] * count
    for index in active_indices:
        field[index] = 1
    return tuple(field)


def _pattern_indices(shape: Shape3, seed: int) -> tuple[int, ...]:
    indices = []
    for x, y, z in _coords(shape):
        score = (17 * x + 11 * y + 7 * z + x * y + 2 * y * z + 3 * z * x + seed) % 19
        if score in (0, 1, 4, 7):
            indices.append(_flat((x, y, z), shape))
    return tuple(indices)


def _fixture_specs() -> tuple[dict[str, object], ...]:
    specifications = [
        {"id": "empty-minimum", "shape": (3, 3, 3), "boundary_focus": "empty", "pattern_id": "empty", "active_indices": ()},
        {"id": "full-minimum", "shape": (3, 3, 3), "boundary_focus": "full", "pattern_id": "full", "active_indices": tuple(range(27))},
        {
            "id": "singleton-corner",
            "shape": (3, 4, 5),
            "boundary_focus": "singleton_wrap_corner",
            "pattern_id": "explicit",
            "active_indices": (_flat((2, 3, 4), (3, 4, 5)),),
            "wraparound_probe": {"target": (0, 0, 0), "source": (2, 3, 4), "wrapped_axis_count": 3},
        },
        {
            "id": "wrap-face-pair",
            "shape": (4, 3, 5),
            "boundary_focus": "wrap_face",
            "pattern_id": "explicit",
            "active_indices": tuple(sorted((_flat((0, 1, 2), (4, 3, 5)), _flat((3, 1, 2), (4, 3, 5))))),
            "wraparound_probe": {"target": (0, 1, 2), "source": (3, 1, 2), "wrapped_axis_count": 1},
        },
        {
            "id": "wrap-edge-cluster",
            "shape": (4, 5, 3),
            "boundary_focus": "wrap_edge",
            "pattern_id": "explicit",
            "active_indices": tuple(
                sorted(_flat(coord, (4, 5, 3)) for coord in ((0, 0, 1), (3, 4, 1), (1, 4, 2), (3, 1, 0)))
            ),
            "wraparound_probe": {"target": (0, 0, 1), "source": (3, 4, 1), "wrapped_axis_count": 2},
        },
        {
            "id": "wrap-corner-cluster",
            "shape": (5, 4, 3),
            "boundary_focus": "wrap_corner",
            "pattern_id": "explicit",
            "active_indices": tuple(
                sorted(_flat(coord, (5, 4, 3)) for coord in ((0, 0, 0), (4, 3, 2), (1, 3, 2), (4, 1, 2)))
            ),
            "wraparound_probe": {"target": (0, 0, 0), "source": (4, 3, 2), "wrapped_axis_count": 3},
        },
        {
            "id": "byte-aligned-asymmetric",
            "shape": (4, 4, 4),
            "boundary_focus": "zero_bit_padding",
            "pattern_id": "deterministic_mod19_seed3",
            "active_indices": _pattern_indices((4, 4, 4), 3),
        },
        {
            "id": "bitpad-asymmetric",
            "shape": (5, 5, 5),
            "boundary_focus": "nonzero_bit_padding_width",
            "pattern_id": "deterministic_mod19_seed11",
            "active_indices": _pattern_indices((5, 5, 5), 11),
        },
    ]
    return tuple(specifications)


def _expected_field_record(field: tuple[int, ...], shape: Shape3) -> dict[str, object]:
    support = independent_support(field, shape)
    next_state = independent_next(field, shape, support)
    packed_bytes = (len(field) + 7) // 8
    return {
        "field_sha256": _values_hash(field, shape),
        "support_sha256": _values_hash(support, shape),
        "next_state_sha256": _values_hash(next_state, shape),
        "active_count": sum(field),
        "next_active_count": sum(next_state),
        "cell_count": len(field),
        "bitpacked_byte_count": packed_bytes,
        "bitpacked_padding_bit_count": packed_bytes * 8 - len(field),
    }


def _make_threshold_records() -> list[dict[str, object]]:
    records = []
    for state, support in itertools.product((0, 1), range(27)):
        field, shape, target = _threshold_field(state, support)
        support_vector = independent_support(field, shape)
        next_state = independent_next(field, shape, support_vector)
        records.append(
            {
                "id": f"threshold-s{state}-n{support:02d}",
                "claim_class": "verifier",
                "state": state,
                "support": support,
                "shape": list(shape),
                "target": list(target),
                "field_generator": {
                    "kind": "target_plus_neighbor_prefix",
                    "neighbor_order": "dz_then_dy_then_dx_with_dx_fastest",
                    "selected_neighbor_count": support,
                },
                "expected": {
                    "measurement": independent_measurement(state, support),
                    "field_sha256": _values_hash(field, shape),
                    "support_vector_sha256": _values_hash(support_vector, shape),
                    "next_state_sha256": _values_hash(next_state, shape),
                },
            }
        )
    return records


def _make_adversarial_records() -> list[dict[str, object]]:
    records = []
    for spec in _fixture_specs():
        shape = tuple(spec["shape"])
        active_indices = tuple(spec["active_indices"])
        field = _field_from_active_indices(shape, active_indices)
        support = independent_support(field, shape)
        probe = spec.get("wraparound_probe")
        normalized_probe = None
        if probe is not None:
            target = tuple(probe["target"])
            source = tuple(probe["source"])
            if source not in _neighbor_coords(target, shape) or not field[_flat(source, shape)]:
                raise PdcGoldenMetamorphicError(f"invalid wraparound witness for {spec['id']}")
            normalized_probe = {
                "target": list(target),
                "source": list(source),
                "wrapped_axis_count": probe["wrapped_axis_count"],
                "target_support": support[_flat(target, shape)],
                "source_contributes": True,
            }
        records.append(
            {
                "id": spec["id"],
                "claim_class": "verifier",
                "shape": list(shape),
                "boundary_focus": spec["boundary_focus"],
                "pattern_id": spec["pattern_id"],
                "active_indices": list(active_indices),
                "wraparound_probe": normalized_probe,
                "expected": _expected_field_record(field, shape),
            }
        )
    return records


def _relation_expected(
    field: tuple[int, ...],
    shape: Shape3,
    transformed: tuple[int, ...],
    transformed_shape: Shape3,
    transform_vector: Callable[[Sequence[int]], tuple[int, ...]],
) -> dict[str, object]:
    base_support = independent_support(field, shape)
    base_next = independent_next(field, shape, base_support)
    transformed_support = independent_support(transformed, transformed_shape)
    transformed_next = independent_next(transformed, transformed_shape, transformed_support)
    expected_support = transform_vector(base_support)
    expected_next = transform_vector(base_next)
    if transformed_support != expected_support or transformed_next != expected_next:
        raise PdcGoldenMetamorphicError("independent oracle rejected a declared metamorphic relation")
    return {
        "transformed_shape": list(transformed_shape),
        "base_field_sha256": _values_hash(field, shape),
        "transformed_field_sha256": _values_hash(transformed, transformed_shape),
        "base_support_sha256": _values_hash(base_support, shape),
        "transformed_support_sha256": _values_hash(transformed_support, transformed_shape),
        "base_next_state_sha256": _values_hash(base_next, shape),
        "transformed_next_state_sha256": _values_hash(transformed_next, transformed_shape),
        "support_equivariant": True,
        "next_state_equivariant": True,
    }


def _make_metamorphic_records(adversarial_records: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for case in adversarial_records:
        shape: Shape3 = tuple(case["shape"])  # type: ignore[assignment]
        field = _field_from_active_indices(shape, case["active_indices"])
        shifts = ((1, 0, 0), (0, 1, 0), (0, 0, 1), tuple(extent - 1 for extent in shape))
        for relation_index, shift in enumerate(shifts):
            transformed = translate_values(field, shape, shift)
            records.append(
                {
                    "id": f"translate-{case['id']}-{relation_index}",
                    "claim_class": "verifier",
                    "base_case_id": case["id"],
                    "relation": "periodic_translation_equivariance",
                    "parameters": {"shift": list(shift)},
                    "expected": _relation_expected(
                        field,
                        shape,
                        transformed,
                        shape,
                        lambda values, shift=shift: translate_values(values, shape, shift),
                    ),
                }
            )

        for relation_index, order in enumerate(((0, 2, 1), (1, 0, 2), (1, 2, 0), (2, 0, 1), (2, 1, 0))):
            transformed, transformed_shape = permute_axes(field, shape, order)
            records.append(
                {
                    "id": f"axis-{case['id']}-{relation_index}",
                    "claim_class": "verifier",
                    "base_case_id": case["id"],
                    "relation": "axis_permutation_equivariance",
                    "parameters": {"order": list(order)},
                    "expected": _relation_expected(
                        field,
                        shape,
                        transformed,
                        transformed_shape,
                        lambda values, order=order: permute_axes(values, shape, order)[0],
                    ),
                }
            )
    return records


def _make_non_relations() -> list[dict[str, object]]:
    shape: Shape3 = (3, 3, 3)
    empty = (0,) * 27
    full = (1,) * 27
    empty_next = independent_next(empty, shape)
    full_next = independent_next(full, shape)
    complement_of_empty_next = tuple(1 - value for value in empty_next)
    complement_mismatch = sum(
        left != right for left, right in zip(complement_of_empty_next, full_next, strict=True)
    )

    shape_a: Shape3 = (3, 4, 5)
    shape_b: Shape3 = (5, 4, 3)
    reinterpreted = tuple(
        int((index * 13 + index // 3 + 5) % 17 in (0, 1, 4, 8)) for index in range(60)
    )
    support_a = independent_support(reinterpreted, shape_a)
    support_b = independent_support(reinterpreted, shape_b)
    support_mismatch = sum(left != right for left, right in zip(support_a, support_b, strict=True))
    if complement_mismatch == 0 or support_mismatch == 0:
        raise PdcGoldenMetamorphicError("finite non-relation witness unexpectedly became equivariant")

    raw = pdc_reference.rectangle_formula(3, 4)
    pmphi = pdc_reference.rectangle_formula(3, 4, model_tag="PMphi.default.remove_B7")
    return [
        {
            "id": "complement-is-not-a-symmetry",
            "evidence_type": "finite_counterexample",
            "relation": "binary_complement_equivariance",
            "expected_relation": False,
            "description": "Complementing a field is not a symmetry of the hysteretic B5-7/S5-9 update.",
            "witness": {
                "shape": list(shape),
                "input_sha256": _values_hash(empty, shape),
                "complement_input_sha256": _values_hash(full, shape),
                "complement_of_output_sha256": _values_hash(complement_of_empty_next, shape),
                "output_of_complement_sha256": _values_hash(full_next, shape),
                "mismatch_count": complement_mismatch,
            },
        },
        {
            "id": "shape-reinterpretation-is-not-invariant",
            "evidence_type": "finite_counterexample",
            "relation": "same_bytes_different_shape",
            "expected_relation": False,
            "description": "Shape metadata is semantic and the same 60 bytes cannot be reinterpreted as an equivalent lattice.",
            "witness": {
                "shape_a": list(shape_a),
                "shape_b": list(shape_b),
                "field_hash_a": _values_hash(reinterpreted, shape_a),
                "field_hash_b": _values_hash(reinterpreted, shape_b),
                "support_mismatch_count": support_mismatch,
            },
        },
        {
            "id": "pmphi-is-not-a-representation-transform",
            "evidence_type": "contract_exclusion",
            "relation": "raw_model_to_pmphi_by_storage_conversion",
            "expected_relation": False,
            "description": "PMphi removes a model-tagged B7 channel and cannot be obtained by changing storage representation.",
            "witness": {
                "rectangle": [3, 4],
                "raw_births": raw["births"],
                "pmphi_births": pmphi["births"],
                "removed_b7_events": raw["births"] - pmphi["births"],
            },
        },
        {
            "id": "nonperiodic-translation-not-declared",
            "evidence_type": "contract_exclusion",
            "relation": "nonperiodic_translation_equivariance",
            "expected_relation": False,
            "description": "Translation equivariance is declared only for the tagged periodic boundary mode.",
            "witness": {"supported_boundary": "periodic", "unsupported_examples": ["fixed_zero", "clamped", "reflect"]},
        },
        {
            "id": "two-dimensional-storage-is-not-a26-execution",
            "evidence_type": "contract_exclusion",
            "relation": "2d_representation_implies_3d_a26",
            "expected_relation": False,
            "description": "PDC-REP-0.1 can store 2D fields, but PDC-MATH-0.1 A26 execution requires a 3D shape.",
            "witness": {"representation_dimensions": [2, 3], "a26_dimensions": 3},
        },
        {
            "id": "fractional-probability-is-not-binary-state",
            "evidence_type": "contract_exclusion",
            "relation": "fractional_probability_exact_binary_embedding",
            "expected_relation": False,
            "description": "Only exact 0.0 and 1.0 probability values convert to the binary update contract.",
            "witness": {"fractional_value": 0.5, "expected_error": "PdcConversionError"},
        },
    ]


def _validate_inputs(
    *,
    workspace: Path,
    math_contract_path: Path,
    predecessor_golden_path: Path,
    representation_contract_path: Path,
    representation_receipt_path: Path,
) -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
    math_contract = _load_json(math_contract_path)
    predecessor = _load_json(predecessor_golden_path)
    representation_contract = _load_json(representation_contract_path)
    representation_receipt = _load_json(representation_receipt_path)
    math_hash = pdc_verifier_intake.sha256_file(math_contract_path)
    representation_hash = pdc_verifier_intake.sha256_file(representation_contract_path)
    if math_contract.get("contract_version") != "PDC-MATH-0.1" or math_contract.get("status") != "pass":
        raise PdcGoldenMetamorphicError("PDC-GOLDEN-0.2 requires the passing PDC-MATH-0.1 contract")
    if predecessor.get("vector_set_version") != "PDC-GOLDEN-0.1" or predecessor.get("status") != "pass":
        raise PdcGoldenMetamorphicError("PDC-GOLDEN-0.2 requires the passing predecessor vector set")
    if predecessor["math_contract_binding"]["artifact_sha256"] != math_hash:
        raise PdcGoldenMetamorphicError("predecessor vectors are not bound to the supplied math contract")
    if representation_contract.get("abi_version") != "PDC-REP-0.1" or representation_contract.get("status") != "pass":
        raise PdcGoldenMetamorphicError("PDC-GOLDEN-0.2 requires the passing PDC-REP-0.1 contract")
    if representation_contract["bindings"]["math_contract_sha256"] != math_hash:
        raise PdcGoldenMetamorphicError("representation contract is not bound to the supplied math contract")
    if representation_receipt.get("status") != "pass_with_explicit_formula_exclusions":
        raise PdcGoldenMetamorphicError("PDC-GOLDEN-0.2 requires the passing PDC-REP-0.1 receipt")
    if representation_receipt["bindings"]["representation_contract_sha256"] != representation_hash:
        raise PdcGoldenMetamorphicError("representation receipt is not bound to the supplied representation contract")
    if representation_receipt["summary"]["mismatch_count"] != 0:
        raise PdcGoldenMetamorphicError("representation receipt contains mismatches")
    implementation_path = workspace / "runtime" / "pdc_golden_metamorphic.py"
    if not implementation_path.is_file():
        raise PdcGoldenMetamorphicError("golden metamorphic implementation is missing")
    return math_contract, predecessor, representation_contract, representation_receipt


def make_golden_metamorphic_corpus(
    *,
    workspace: Path,
    math_contract_path: Path,
    predecessor_golden_path: Path,
    representation_contract_path: Path,
    representation_receipt_path: Path,
) -> dict[str, object]:
    math_contract, predecessor, representation_contract, _ = _validate_inputs(
        workspace=workspace,
        math_contract_path=math_contract_path,
        predecessor_golden_path=predecessor_golden_path,
        representation_contract_path=representation_contract_path,
        representation_receipt_path=representation_receipt_path,
    )
    threshold_records = _make_threshold_records()
    adversarial_records = _make_adversarial_records()
    metamorphic_records = _make_metamorphic_records(adversarial_records)
    non_relations = _make_non_relations()
    translation_count = sum(item["relation"] == "periodic_translation_equivariance" for item in metamorphic_records)
    axis_count = sum(item["relation"] == "axis_permutation_equivariance" for item in metamorphic_records)
    if (
        len(threshold_records) != THRESHOLD_PAIR_COUNT
        or len(adversarial_records) != ADVERSARIAL_CASE_COUNT
        or translation_count != TRANSLATION_RELATION_COUNT
        or axis_count != AXIS_PERMUTATION_RELATION_COUNT
        or len(non_relations) != NON_RELATION_COUNT
    ):
        raise PdcGoldenMetamorphicError("published corpus cardinality drifted from its versioned contract")
    record_set = {
        "threshold_records": threshold_records,
        "adversarial_records": adversarial_records,
        "metamorphic_records": metamorphic_records,
        "non_relations": non_relations,
    }
    return {
        "schema_version": "0.2",
        "artifact_kind": "pdc_golden_metamorphic_corpus",
        "corpus_version": CORPUS_VERSION,
        "created_utc": _created_utc(),
        "status": "published_expected",
        "bindings": {
            "reference_implementation_path": "runtime/pdc_golden_metamorphic.py",
            "reference_implementation_sha256": pdc_verifier_intake.sha256_file(
                workspace / "runtime" / "pdc_golden_metamorphic.py"
            ),
            "math_contract_path": _relative(math_contract_path, workspace),
            "math_contract_sha256": pdc_verifier_intake.sha256_file(math_contract_path),
            "math_contract_version": math_contract["contract_version"],
            "predecessor_golden_path": _relative(predecessor_golden_path, workspace),
            "predecessor_golden_sha256": pdc_verifier_intake.sha256_file(predecessor_golden_path),
            "predecessor_golden_version": predecessor["vector_set_version"],
            "representation_contract_path": _relative(representation_contract_path, workspace),
            "representation_contract_sha256": pdc_verifier_intake.sha256_file(representation_contract_path),
            "representation_abi_version": representation_contract["abi_version"],
            "representation_receipt_path": _relative(representation_receipt_path, workspace),
            "representation_receipt_sha256": pdc_verifier_intake.sha256_file(representation_receipt_path),
        },
        "scope": {
            "boundary_mode": "periodic",
            "dimensions": 3,
            "model_tag": "B5-7/S5-9",
            "finite_verifier_not_all_size_theorem": True,
            "predecessor_is_preserved": True,
        },
        **record_set,
        "digests": {
            "threshold_set_sha256": _json_digest(threshold_records),
            "adversarial_set_sha256": _json_digest(adversarial_records),
            "metamorphic_set_sha256": _json_digest(metamorphic_records),
            "non_relation_set_sha256": _json_digest(non_relations),
            "record_set_sha256": _json_digest(record_set),
        },
        "summary": {
            "threshold_pair_count": len(threshold_records),
            "adversarial_case_count": len(adversarial_records),
            "translation_relation_count": translation_count,
            "axis_permutation_relation_count": axis_count,
            "metamorphic_relation_count": len(metamorphic_records),
            "non_relation_count": len(non_relations),
            "published_record_count": sum(len(value) for value in record_set.values()),
        },
        "oracle_policy": [
            "Expected values are generated by a direct stencil and direct threshold formula separate from both frozen pdc_reference support paths.",
            "The receipt must independently agree through scalar stencil, dense matrix, direct stencil, and all five PDC-REP-0.1 forms.",
            "Semantic hashes bind dtype, shape, axis order, byte order, and logical values; a symmetry does not imply equal untransformed storage hashes.",
        ],
        "limitations": [
            "This is a finite published verifier corpus, not an all-size theorem or production-backend qualification.",
            "Only the tagged periodic 3D B5-7/S5-9 contract is in scope; nonperiodic and small-aliasing tori are explicit exclusions.",
            "PMphi, Q/P dynamics, signed-state dynamics, native C pointers, optimized routes, kernel enforcement, UI, and ISO behavior remain separate contracts.",
        ],
    }


def _representation_probe(field: tuple[int, ...], shape: Shape3, seed: int) -> dict[str, object]:
    dense = rep.dense_binary_field(field, shape)
    sparse = rep.sparse_from_dense(dense)
    bitpacked = rep.bitpacked_from_dense(dense)
    probability = rep.probability_from_dense(dense)
    native = rep.native_snapshot_from_dense(
        dense,
        byte_offset=seed % 4,
        row_padding_bytes=seed % 3 + 1,
        slice_padding_bytes=seed % 5 + 1,
    )
    restored = (
        rep.dense_from_sparse(sparse),
        rep.dense_from_bitpacked(bitpacked),
        rep.dense_from_probability(probability),
        rep.dense_from_native(native),
    )
    semantic_hash = rep.dense_binary_semantic_hash(dense)
    binary_hashes = [rep.dense_binary_semantic_hash(item) for item in (dense, sparse, bitpacked, native)]
    if any(item != dense for item in restored) or any(digest != semantic_hash for digest in binary_hashes):
        raise PdcGoldenMetamorphicError("PDC-REP-0.1 failed a golden corpus representation probe")
    storage_hashes = {
        "dense": rep.representation_storage_hash(dense),
        "sparse": rep.representation_storage_hash(sparse),
        "bitpacked": rep.representation_storage_hash(bitpacked),
        "probability": rep.representation_storage_hash(probability),
        "native": rep.representation_storage_hash(native),
    }
    return {
        "representation_count": 5,
        "round_trip_count": ROUND_TRIPS_PER_FIELD,
        "binary_semantic_hash_sha256": semantic_hash,
        "storage_hash_set_sha256": _json_digest(storage_hashes),
        "bitpacked_padding_bit_count": len(bitpacked.payload) * 8 - len(field),
        "native_strides": list(native.strides),
    }


def _negative_check(identifier: str, action: Callable[[], object], expected: type[BaseException]) -> dict[str, object]:
    try:
        action()
    except expected as exc:
        return {"id": identifier, "passed": True, "error_type": type(exc).__name__}
    except Exception as exc:  # pragma: no cover - diagnostic mismatch path
        return {"id": identifier, "passed": False, "error_type": type(exc).__name__}
    return {"id": identifier, "passed": False, "error_type": "no_error"}


def _make_negative_checks() -> list[dict[str, object]]:
    packed = rep.bitpacked_from_dense(rep.dense_binary_field((0,) * 27, (3, 3, 3)))
    bad_padding = packed.payload[:-1] + bytes((packed.payload[-1] | 0x80,))
    checks = [
        _negative_check(
            "extent-below-periodic-minimum",
            lambda: pdc_reference.scalar_moore_support((0,) * 18, (2, 3, 3)),
            pdc_reference.PdcShapeError,
        ),
        _negative_check("translation-wrong-dimensionality", lambda: translate_values((0,) * 27, (3, 3, 3), (1, 0)), pdc_reference.PdcShapeError),
        _negative_check("translation-bool-offset", lambda: translate_values((0,) * 27, (3, 3, 3), (True, 0, 0)), pdc_reference.PdcContractError),
        _negative_check("axis-permutation-duplicate", lambda: permute_axes((0,) * 27, (3, 3, 3), (0, 0, 2)), pdc_reference.PdcContractError),
        _negative_check("axis-permutation-out-of-range", lambda: permute_axes((0,) * 27, (3, 3, 3), (0, 1, 3)), pdc_reference.PdcContractError),
        _negative_check(
            "fractional-probability-to-binary",
            lambda: rep.dense_from_probability(rep.ProbabilityField((3, 3), (0.5,) + (0.0,) * 8)),
            rep.PdcConversionError,
        ),
        _negative_check("nonzero-bit-padding", lambda: rep.BitPackedBinaryField((3, 3, 3), bad_padding), rep.PdcRepresentationError),
        _negative_check("unknown-model-tag", lambda: pdc_reference.rectangle_formula(3, 4, model_tag="untagged"), pdc_reference.PdcContractError),
        _negative_check("support-above-26", lambda: _threshold_field(0, 27), pdc_reference.PdcContractError),
        _negative_check("unsupported-boundary-mode", lambda: require_supported_boundary("fixed_zero"), pdc_reference.PdcContractError),
    ]
    if len(checks) != NEGATIVE_CHECK_COUNT:
        raise PdcGoldenMetamorphicError("negative-check cardinality drifted")
    return checks


def make_golden_metamorphic_receipt(
    *,
    workspace: Path,
    corpus_path: Path,
    math_contract_path: Path,
    predecessor_golden_path: Path,
    representation_contract_path: Path,
    representation_receipt_path: Path,
) -> dict[str, object]:
    _validate_inputs(
        workspace=workspace,
        math_contract_path=math_contract_path,
        predecessor_golden_path=predecessor_golden_path,
        representation_contract_path=representation_contract_path,
        representation_receipt_path=representation_receipt_path,
    )
    corpus = _load_json(corpus_path)
    bindings = corpus.get("bindings", {})
    expected_bindings = {
        "reference_implementation_path": "runtime/pdc_golden_metamorphic.py",
        "reference_implementation_sha256": pdc_verifier_intake.sha256_file(workspace / "runtime" / "pdc_golden_metamorphic.py"),
        "math_contract_path": _relative(math_contract_path, workspace),
        "math_contract_sha256": pdc_verifier_intake.sha256_file(math_contract_path),
        "math_contract_version": "PDC-MATH-0.1",
        "predecessor_golden_path": _relative(predecessor_golden_path, workspace),
        "predecessor_golden_sha256": pdc_verifier_intake.sha256_file(predecessor_golden_path),
        "predecessor_golden_version": "PDC-GOLDEN-0.1",
        "representation_contract_path": _relative(representation_contract_path, workspace),
        "representation_contract_sha256": pdc_verifier_intake.sha256_file(representation_contract_path),
        "representation_abi_version": "PDC-REP-0.1",
        "representation_receipt_path": _relative(representation_receipt_path, workspace),
        "representation_receipt_sha256": pdc_verifier_intake.sha256_file(representation_receipt_path),
    }
    if corpus.get("corpus_version") != CORPUS_VERSION or corpus.get("status") != "published_expected":
        raise PdcGoldenMetamorphicError("supplied golden metamorphic corpus is not the published PDC-GOLDEN-0.2 artifact")
    if bindings != expected_bindings:
        raise PdcGoldenMetamorphicError("golden metamorphic corpus bindings do not match current authoritative inputs")
    record_set = {
        "threshold_records": corpus["threshold_records"],
        "adversarial_records": corpus["adversarial_records"],
        "metamorphic_records": corpus["metamorphic_records"],
        "non_relations": corpus["non_relations"],
    }
    expected_digests = {
        "threshold_set_sha256": _json_digest(corpus["threshold_records"]),
        "adversarial_set_sha256": _json_digest(corpus["adversarial_records"]),
        "metamorphic_set_sha256": _json_digest(corpus["metamorphic_records"]),
        "non_relation_set_sha256": _json_digest(corpus["non_relations"]),
        "record_set_sha256": _json_digest(record_set),
    }
    if corpus.get("digests") != expected_digests:
        raise PdcGoldenMetamorphicError("golden metamorphic corpus record digest does not verify")

    threshold_results = []
    threshold_round_trips = 0
    expected_threshold_records = _make_threshold_records()
    for index, record in enumerate(corpus["threshold_records"]):
        field, shape, target = _threshold_field(record["state"], record["support"])
        target_index = _flat(target, shape)
        direct_support = independent_support(field, shape)
        scalar_support = pdc_reference.scalar_moore_support(field, shape)
        matrix_support = pdc_reference.matrix_moore_support(field, shape)
        direct_next = independent_next(field, shape, direct_support)
        scalar_next = pdc_reference.binary_next_state(field, shape, support=scalar_support)
        matrix_next = pdc_reference.binary_next_state(field, shape, support=matrix_support)
        measurement = pdc_reference.measure_binary_field(field, shape, support=scalar_support)[target_index].to_dict()
        expected = record["expected"]
        passed = (
            record == expected_threshold_records[index]
            and direct_support == scalar_support == matrix_support
            and direct_next == scalar_next == matrix_next
            and direct_support[target_index] == record["support"]
            and measurement == expected["measurement"]
            and _values_hash(field, shape) == expected["field_sha256"]
            and _values_hash(direct_support, shape) == expected["support_vector_sha256"]
            and _values_hash(direct_next, shape) == expected["next_state_sha256"]
        )
        probe = _representation_probe(field, shape, index)
        threshold_round_trips += probe["round_trip_count"]
        threshold_results.append({"id": record["id"], "passed": passed, "representation_probe": probe})

    adversarial_results = []
    adversarial_round_trips = 0
    expected_adversarial = _make_adversarial_records()
    for index, record in enumerate(corpus["adversarial_records"]):
        shape: Shape3 = tuple(record["shape"])
        field = _field_from_active_indices(shape, record["active_indices"])
        direct_support = independent_support(field, shape)
        scalar_support = pdc_reference.scalar_moore_support(field, shape)
        matrix_support = pdc_reference.matrix_moore_support(field, shape)
        direct_next = independent_next(field, shape, direct_support)
        scalar_next = pdc_reference.binary_next_state(field, shape, support=scalar_support)
        matrix_next = pdc_reference.binary_next_state(field, shape, support=matrix_support)
        probe_record = record["wraparound_probe"]
        wrap_ok = True
        if probe_record is not None:
            target = tuple(probe_record["target"])
            source = tuple(probe_record["source"])
            wrap_ok = (
                source in _neighbor_coords(target, shape)
                and field[_flat(source, shape)] == 1
                and direct_support[_flat(target, shape)] == probe_record["target_support"]
                and probe_record["source_contributes"] is True
            )
        passed = (
            record == expected_adversarial[index]
            and direct_support == scalar_support == matrix_support
            and direct_next == scalar_next == matrix_next
            and _expected_field_record(field, shape) == record["expected"]
            and wrap_ok
        )
        probe = _representation_probe(field, shape, 100 + index)
        adversarial_round_trips += probe["round_trip_count"]
        adversarial_results.append({"id": record["id"], "passed": passed, "representation_probe": probe})

    fixture_map = {record["id"]: record for record in corpus["adversarial_records"]}
    metamorphic_results = []
    metamorphic_round_trips = 0
    for index, record in enumerate(corpus["metamorphic_records"]):
        base = fixture_map[record["base_case_id"]]
        shape: Shape3 = tuple(base["shape"])
        field = _field_from_active_indices(shape, base["active_indices"])
        if record["relation"] == "periodic_translation_equivariance":
            shift = tuple(record["parameters"]["shift"])
            transformed = translate_values(field, shape, shift)
            transformed_shape = shape
            transform = lambda values, shift=shift: translate_values(values, shape, shift)
        elif record["relation"] == "axis_permutation_equivariance":
            order = tuple(record["parameters"]["order"])
            transformed, transformed_shape = permute_axes(field, shape, order)
            transform = lambda values, order=order: permute_axes(values, shape, order)[0]
        else:
            raise PdcGoldenMetamorphicError(f"unknown declared relation {record['relation']!r}")
        base_direct = independent_support(field, shape)
        transformed_direct = independent_support(transformed, transformed_shape)
        base_scalar = pdc_reference.scalar_moore_support(field, shape)
        transformed_scalar = pdc_reference.scalar_moore_support(transformed, transformed_shape)
        base_matrix = pdc_reference.matrix_moore_support(field, shape)
        transformed_matrix = pdc_reference.matrix_moore_support(transformed, transformed_shape)
        base_next = independent_next(field, shape, base_direct)
        transformed_next = independent_next(transformed, transformed_shape, transformed_direct)
        passed = (
            base_direct == base_scalar == base_matrix
            and transformed_direct == transformed_scalar == transformed_matrix
            and transformed_direct == transform(base_direct)
            and transformed_next == transform(base_next)
            and record["expected"] == _relation_expected(field, shape, transformed, transformed_shape, transform)
        )
        base_probe = _representation_probe(field, shape, 200 + index * 2)
        transformed_probe = _representation_probe(transformed, transformed_shape, 201 + index * 2)
        metamorphic_round_trips += base_probe["round_trip_count"] + transformed_probe["round_trip_count"]
        metamorphic_results.append(
            {
                "id": record["id"],
                "relation": record["relation"],
                "passed": passed,
                "base_representation_probe": base_probe,
                "transformed_representation_probe": transformed_probe,
            }
        )

    recomputed_non_relations = _make_non_relations()
    non_relation_results = [
        {"id": record["id"], "passed": record == recomputed_non_relations[index], "evidence_type": record["evidence_type"]}
        for index, record in enumerate(corpus["non_relations"])
    ]
    negative_checks = _make_negative_checks()
    failed_negative = sum(not item["passed"] for item in negative_checks)
    failed_records = (
        sum(not item["passed"] for item in threshold_results)
        + sum(not item["passed"] for item in adversarial_results)
        + sum(not item["passed"] for item in metamorphic_results)
        + sum(not item["passed"] for item in non_relation_results)
    )
    total_round_trips = threshold_round_trips + adversarial_round_trips + metamorphic_round_trips
    mismatch_count = failed_records + failed_negative
    if total_round_trips != REPRESENTATION_ROUND_TRIP_COUNT or mismatch_count != 0:
        raise PdcGoldenMetamorphicError(
            f"golden metamorphic receipt failed: records={failed_records}, negative={failed_negative}, round_trips={total_round_trips}"
        )
    translation_count = sum(item["relation"] == "periodic_translation_equivariance" for item in metamorphic_results)
    axis_count = sum(item["relation"] == "axis_permutation_equivariance" for item in metamorphic_results)
    return {
        "schema_version": "0.2",
        "artifact_kind": "pdc_golden_metamorphic_receipt",
        "corpus_version": CORPUS_VERSION,
        "created_utc": _created_utc(),
        "status": "pass",
        "bindings": {
            "verifier_implementation_path": "runtime/pdc_golden_metamorphic.py",
            "verifier_implementation_sha256": pdc_verifier_intake.sha256_file(
                workspace / "runtime" / "pdc_golden_metamorphic.py"
            ),
            "corpus_path": _relative(corpus_path, workspace),
            "corpus_sha256": pdc_verifier_intake.sha256_file(corpus_path),
            "math_contract_path": _relative(math_contract_path, workspace),
            "math_contract_sha256": pdc_verifier_intake.sha256_file(math_contract_path),
            "predecessor_golden_path": _relative(predecessor_golden_path, workspace),
            "predecessor_golden_sha256": pdc_verifier_intake.sha256_file(predecessor_golden_path),
            "representation_contract_path": _relative(representation_contract_path, workspace),
            "representation_contract_sha256": pdc_verifier_intake.sha256_file(representation_contract_path),
            "representation_receipt_path": _relative(representation_receipt_path, workspace),
            "representation_receipt_sha256": pdc_verifier_intake.sha256_file(representation_receipt_path),
        },
        "environment": {
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "executable": sys.executable,
        },
        "results": {
            "threshold": {
                "case_count": len(threshold_results),
                "passed_count": sum(item["passed"] for item in threshold_results),
                "scalar_matrix_direct_agreement_count": sum(item["passed"] for item in threshold_results),
                "representation_round_trip_count": threshold_round_trips,
                "mismatch_count": sum(not item["passed"] for item in threshold_results),
                "result_set_sha256": _json_digest(threshold_results),
            },
            "adversarial": {
                "case_count": len(adversarial_results),
                "passed_count": sum(item["passed"] for item in adversarial_results),
                "wraparound_probe_count": sum(item["wraparound_probe"] is not None for item in corpus["adversarial_records"]),
                "representation_round_trip_count": adversarial_round_trips,
                "mismatch_count": sum(not item["passed"] for item in adversarial_results),
                "result_set_sha256": _json_digest(adversarial_results),
            },
            "metamorphic": {
                "relation_count": len(metamorphic_results),
                "translation_relation_count": translation_count,
                "axis_permutation_relation_count": axis_count,
                "passed_count": sum(item["passed"] for item in metamorphic_results),
                "representation_round_trip_count": metamorphic_round_trips,
                "mismatch_count": sum(not item["passed"] for item in metamorphic_results),
                "result_set_sha256": _json_digest(metamorphic_results),
            },
            "non_relations": {
                "record_count": len(non_relation_results),
                "passed_count": sum(item["passed"] for item in non_relation_results),
                "finite_counterexample_count": sum(item["evidence_type"] == "finite_counterexample" for item in non_relation_results),
                "contract_exclusion_count": sum(item["evidence_type"] == "contract_exclusion" for item in non_relation_results),
                "mismatch_count": sum(not item["passed"] for item in non_relation_results),
                "result_set_sha256": _json_digest(non_relation_results),
            },
        },
        "negative_checks": negative_checks,
        "digests": {
            "corpus_record_set_sha256": corpus["digests"]["record_set_sha256"],
            "receipt_result_set_sha256": _json_digest(
                {
                    "threshold": threshold_results,
                    "adversarial": adversarial_results,
                    "metamorphic": metamorphic_results,
                    "non_relations": non_relation_results,
                }
            ),
            "negative_check_set_sha256": _json_digest(negative_checks),
        },
        "summary": {
            "threshold_pair_count": len(threshold_results),
            "adversarial_case_count": len(adversarial_results),
            "translation_relation_count": translation_count,
            "axis_permutation_relation_count": axis_count,
            "metamorphic_relation_count": len(metamorphic_results),
            "non_relation_count": len(non_relation_results),
            "oracle_field_evaluation_count": ORACLE_FIELD_EVALUATION_COUNT,
            "representation_round_trip_count": total_round_trips,
            "negative_check_count": len(negative_checks),
            "failed_negative_check_count": failed_negative,
            "mismatch_count": mismatch_count,
        },
        "claim_boundary": [
            "The receipt proves exact finite agreement over the published PDC-GOLDEN-0.2 records under PDC-MATH-0.1 and PDC-REP-0.1.",
            "Translation and axis-permutation evidence applies only to the tagged periodic isotropic Moore contract and declared finite fixtures.",
            "Counterexamples and contract exclusions prevent complement, shape reinterpretation, PMphi, nonperiodic, 2D-A26, and fractional-probability promotion.",
            "This is not an all-size theorem, optimized-backend qualification, native C proof, kernel enforcement, UI validation, or bootable ISO evidence.",
        ],
    }
