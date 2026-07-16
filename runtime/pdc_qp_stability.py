"""Source-compatible Q/P field benchmark and finite perturbation runtime."""

from __future__ import annotations

import hashlib
import math
import random
from collections.abc import Mapping, Sequence
from typing import Callable

import numpy as np

from runtime import pdc_qp as qp


CONTRACT_VERSION = "PDC-QP-STABILITY-0.1"
LATTICE_SIZE = 28
ACTIVE_PROBABILITY = 0.06
SAMPLE_COUNT = 50
BENCHMARK_SEED = 23
TARGET_ACTIVE_COUNT = 1317
ROBUST_Z_SCALE = 5.0
STD_FLOOR_MULTIPLIER = 2.0
NULL_LIKE_THRESHOLD = 2.0
PERTURBATION_SWAP_LEVELS = (1, 4, 16, 64)
MAX_LATTICE_SIZE = 64
MAX_SAMPLE_COUNT = 1000

RAW_CLASS_ORDER = (
    "iid_null",
    "straight_lines",
    "random_walk_chains",
    "branching_chains",
    "compact_bursts",
    "sheets",
)
STRUCTURED_CLASS_ORDER = RAW_CLASS_ORDER[1:]
CONTROL_CLASS_ORDER = (
    "iid_null",
    "straight_lines_shuffled",
    "random_walk_chains_shuffled",
    "branching_chains_shuffled",
    "compact_bursts_shuffled",
    "sheets_shuffled",
)
SCORED_CLASS_ORDER = RAW_CLASS_ORDER + CONTROL_CLASS_ORDER[1:]
SUMMARY_CLASS_ORDER = (
    "iid_null",
    "straight_lines",
    "straight_lines_shuffled",
    "random_walk_chains",
    "random_walk_chains_shuffled",
    "branching_chains",
    "branching_chains_shuffled",
    "compact_bursts",
    "compact_bursts_shuffled",
    "sheets",
    "sheets_shuffled",
)
CHANNEL_ORDER = (
    "B5",
    "B6",
    "B7",
    "S5",
    "S6",
    "S7",
    "S8",
    "S9",
    "O10+",
    "psi_mean",
    "psi_abs",
    "active",
    "poole_active",
)
GROUP_CHANNELS = {
    "birth": qp.BIRTH_GEOMETRY_CHANNELS,
    "high_support": qp.HIGH_SUPPORT_GEOMETRY_CHANNELS,
    "strain": qp.STRAIN_GEOMETRY_CHANNELS,
}
COMBINED_CHANNELS = qp.COMBINED_GEOMETRY_CHANNELS


class PdcQpStabilityError(ValueError):
    """Raised when a field benchmark or perturbation input violates the contract."""


def _require_int(value: object, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise PdcQpStabilityError(f"{name} must be an integer in [{minimum},{maximum}]")
    return value


def _require_probability(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PdcQpStabilityError(f"{name} must be a finite probability")
    result = float(value)
    if not math.isfinite(result) or not 0.0 < result < 1.0:
        raise PdcQpStabilityError(f"{name} must be finite and strictly between zero and one")
    return result


def _validated_field(field: object) -> np.ndarray:
    if not isinstance(field, np.ndarray):
        raise PdcQpStabilityError("field must be a NumPy array")
    if field.ndim != 3 or len(set(field.shape)) != 1:
        raise PdcQpStabilityError("field must be a cubic three-dimensional array")
    if not 3 <= field.shape[0] <= MAX_LATTICE_SIZE:
        raise PdcQpStabilityError(f"field extent must be in [3,{MAX_LATTICE_SIZE}]")
    if not np.all((field == 0) | (field == 1)):
        raise PdcQpStabilityError("field entries must be binary")
    return np.asarray(field, dtype=np.uint8)


def field_sha256(field: object) -> str:
    normalized = _validated_field(field)
    return hashlib.sha256(np.ascontiguousarray(normalized).tobytes()).hexdigest().upper()


def neighbor_count_roll(field: object) -> np.ndarray:
    """Source-compatible 26-neighbor periodic stencil using explicit rolls."""

    normalized = _validated_field(field)
    counts = np.zeros_like(normalized, dtype=np.int16)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                if dx == dy == dz == 0:
                    continue
                shifted = np.roll(normalized, dx, axis=0)
                shifted = np.roll(shifted, dy, axis=1)
                shifted = np.roll(shifted, dz, axis=2)
                counts += shifted
    return counts


def neighbor_count_indexed(field: object) -> np.ndarray:
    """Independent periodic stencil using modular index arrays, never ``np.roll``."""

    normalized = _validated_field(field)
    extent = normalized.shape[0]
    base = np.arange(extent)
    counts = np.zeros_like(normalized, dtype=np.int16)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                if dx == dy == dz == 0:
                    continue
                ix = (base - dx) % extent
                iy = (base - dy) % extent
                iz = (base - dz) % extent
                counts += normalized[np.ix_(ix, iy, iz)]
    return counts


def channel_rates_from_counts(field: object, counts: object) -> dict[str, float]:
    normalized = _validated_field(field)
    if not isinstance(counts, np.ndarray) or counts.shape != normalized.shape:
        raise PdcQpStabilityError("neighbor counts must be an array with the field shape")
    if not np.issubdtype(counts.dtype, np.integer) or np.any(counts < 0) or np.any(counts > 26):
        raise PdcQpStabilityError("neighbor counts must be integers in [0,26]")
    rates: dict[str, float] = {}
    for support in (5, 6, 7):
        rates[f"B{support}"] = float(np.mean((normalized == 0) & (counts == support)))
    for support in (5, 6, 7, 8, 9):
        rates[f"S{support}"] = float(np.mean((normalized == 1) & (counts == support)))
    rates["O10+"] = float(np.mean((normalized == 1) & (counts >= 10)))
    strain = np.maximum(0, counts - (7 + 2 * normalized)) - np.maximum(0, 5 - counts)
    rates["psi_mean"] = float(np.mean(strain))
    rates["psi_abs"] = float(np.mean(np.abs(strain)))
    rates["active"] = float(np.mean(normalized))
    rates["poole_active"] = float(
        rates["B5"]
        + rates["B6"]
        + rates["B7"]
        + rates["S5"]
        + rates["S6"]
        + rates["S7"]
        + rates["S8"]
        + rates["S9"]
    )
    return rates


def channel_rates_roll(field: object) -> dict[str, float]:
    normalized = _validated_field(field)
    return channel_rates_from_counts(normalized, neighbor_count_roll(normalized))


def channel_rates_indexed(field: object) -> dict[str, float]:
    normalized = _validated_field(field)
    return channel_rates_from_counts(normalized, neighbor_count_indexed(normalized))


def _exact_active_adjust(field: np.ndarray, target: int, rng: np.random.Generator) -> np.ndarray:
    result = np.asarray(field, dtype=np.uint8).copy()
    flat = result.ravel()
    current = int(flat.sum())
    if current > target:
        flat[rng.choice(np.flatnonzero(flat), size=current - target, replace=False)] = 0
    elif current < target:
        flat[rng.choice(np.flatnonzero(flat == 0), size=target - current, replace=False)] = 1
    return flat.reshape(result.shape)


def _add_point(field: np.ndarray, i: int, j: int, k: int) -> None:
    extent = field.shape[0]
    field[i % extent, j % extent, k % extent] = 1


def _iid_sample(extent: int, probability: float, rng: np.random.Generator) -> np.ndarray:
    target = int(round(probability * extent**3))
    return _exact_active_adjust((rng.random((extent, extent, extent)) < probability).astype(np.uint8), target, rng)


def _line_sample(extent: int, probability: float, rng: np.random.Generator) -> np.ndarray:
    target = int(round(probability * extent**3))
    field = np.zeros((extent, extent, extent), dtype=np.uint8)
    for _ in range(max(1, int(target * 0.80 / 9))):
        i, j, k = rng.integers(0, extent, size=3)
        axis = int(rng.integers(0, 3))
        for step in range(9):
            point = [int(i), int(j), int(k)]
            point[axis] += step
            _add_point(field, *point)
    return _exact_active_adjust(field, target, rng)


def _random_walk_sample(extent: int, probability: float, rng: np.random.Generator) -> np.ndarray:
    target = int(round(probability * extent**3))
    field = np.zeros((extent, extent, extent), dtype=np.uint8)
    steps = np.array(((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)), dtype=int)
    for _ in range(max(1, int(target * 0.82 / 13))):
        position = rng.integers(0, extent, size=3)
        for _step in range(13):
            _add_point(field, int(position[0]), int(position[1]), int(position[2]))
            position = (position + steps[int(rng.integers(0, len(steps)))]) % extent
    return _exact_active_adjust(field, target, rng)


def _branch_sample(extent: int, probability: float, rng: np.random.Generator) -> np.ndarray:
    target = int(round(probability * extent**3))
    field = np.zeros((extent, extent, extent), dtype=np.uint8)
    axes = np.eye(3, dtype=int)
    for _ in range(max(1, int(target * 0.80 / 20))):
        position = rng.integers(0, extent, size=3)
        main_axis = axes[int(rng.integers(0, 3))]
        main_step = (1 if rng.random() < 0.5 else -1) * main_axis
        path = []
        for step in range(10):
            point = (position + step * main_step) % extent
            path.append(point)
            _add_point(field, int(point[0]), int(point[1]), int(point[2]))
        split = path[len(path) // 2]
        for branch_axis in (axis for axis in axes if not np.array_equal(axis, main_axis)):
            branch_step = (1 if rng.random() < 0.5 else -1) * branch_axis
            for step in range(1, 6):
                point = (split + step * branch_step) % extent
                _add_point(field, int(point[0]), int(point[1]), int(point[2]))
    return _exact_active_adjust(field, target, rng)


def _compact_burst_sample(extent: int, probability: float, rng: np.random.Generator) -> np.ndarray:
    target = int(round(probability * extent**3))
    field = np.zeros((extent, extent, extent), dtype=np.uint8)
    for _ in range(max(1, int(target * 0.75 / 27))):
        center = rng.integers(0, extent, size=3)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    if rng.random() < 0.78:
                        _add_point(field, int(center[0]) + dx, int(center[1]) + dy, int(center[2]) + dz)
    return _exact_active_adjust(field, target, rng)


def _sheet_sample(extent: int, probability: float, rng: np.random.Generator) -> np.ndarray:
    target = int(round(probability * extent**3))
    field = np.zeros((extent, extent, extent), dtype=np.uint8)
    for _ in range(max(1, int(target * 0.80) // 49)):
        axis = int(rng.integers(0, 3))
        coordinate, first, second = (int(value) for value in rng.integers(0, extent, size=3))
        for u in range(7):
            for v in range(7):
                if axis == 0:
                    _add_point(field, coordinate, first + u, second + v)
                elif axis == 1:
                    _add_point(field, first + u, coordinate, second + v)
                else:
                    _add_point(field, first + u, second + v, coordinate)
    return _exact_active_adjust(field, target, rng)


def _shuffled_copy(field: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    flat = field.ravel().copy()
    rng.shuffle(flat)
    return flat.reshape(field.shape)


def generate_benchmark_fields(
    *, extent: int = LATTICE_SIZE, probability: float = ACTIVE_PROBABILITY, sample_count: int = SAMPLE_COUNT, seed: int = BENCHMARK_SEED
) -> dict[str, list[np.ndarray]]:
    normalized_extent = _require_int(extent, "extent", 3, MAX_LATTICE_SIZE)
    normalized_probability = _require_probability(probability, "probability")
    normalized_samples = _require_int(sample_count, "sample_count", 1, MAX_SAMPLE_COUNT)
    normalized_seed = _require_int(seed, "seed", 0, 2**63 - 1)
    rng = np.random.default_rng(normalized_seed)
    generators: Mapping[str, Callable[[], np.ndarray]] = {
        "iid_null": lambda: _iid_sample(normalized_extent, normalized_probability, rng),
        "straight_lines": lambda: _line_sample(normalized_extent, normalized_probability, rng),
        "random_walk_chains": lambda: _random_walk_sample(normalized_extent, normalized_probability, rng),
        "branching_chains": lambda: _branch_sample(normalized_extent, normalized_probability, rng),
        "compact_bursts": lambda: _compact_burst_sample(normalized_extent, normalized_probability, rng),
        "sheets": lambda: _sheet_sample(normalized_extent, normalized_probability, rng),
    }
    fields = {name: [generator() for _ in range(normalized_samples)] for name, generator in generators.items()}
    for name in STRUCTURED_CLASS_ORDER:
        fields[f"{name}_shuffled"] = [_shuffled_copy(field, rng) for field in fields[name]]
    return fields


def null_calibration(rows: Sequence[Mapping[str, float]], *, extent: int) -> tuple[dict[str, float], dict[str, float]]:
    if not rows:
        raise PdcQpStabilityError("null calibration requires at least one row")
    normalized_extent = _require_int(extent, "extent", 3, MAX_LATTICE_SIZE)
    volume = normalized_extent**3
    means: dict[str, float] = {}
    deviations: dict[str, float] = {}
    for channel in COMBINED_CHANNELS:
        values = np.array([float(row[channel]) for row in rows], dtype=float)
        if np.any(~np.isfinite(values)):
            raise PdcQpStabilityError(f"null channel {channel} contains nonfinite values")
        mean = float(values.mean())
        empirical = float(values.std(ddof=1)) if len(values) > 1 else 0.0
        floor = 1e-6 if channel == "psi_abs" else STD_FLOOR_MULTIPLIER * math.sqrt(max(mean * (1.0 - mean), 1.0 / (4.0 * volume)) / volume)
        means[channel] = mean
        deviations[channel] = max(empirical, floor, 1e-12)
    return means, deviations


def _raw_score(row: Mapping[str, float], means: Mapping[str, float], deviations: Mapping[str, float], channels: Sequence[str]) -> float:
    values = [((float(row[channel]) - float(means[channel])) / (float(deviations[channel]) + qp.DEFAULT_EPSILON)) for channel in channels]
    return math.sqrt(math.fsum(value * value for value in values))


def score_row(row: Mapping[str, float], means: Mapping[str, float], deviations: Mapping[str, float]) -> dict[str, float]:
    signature = qp.geometry_signature(row, means, deviations, epsilon=qp.DEFAULT_EPSILON, softening=ROBUST_Z_SCALE)
    result = dict(row)
    for group, channels in GROUP_CHANNELS.items():
        result[f"Z_{group}"] = _raw_score(row, means, deviations, channels)
    result["Z_combined"] = _raw_score(row, means, deviations, COMBINED_CHANNELS)
    result.update(
        {
            "R_birth": signature.birth_window,
            "R_high_support": signature.high_support,
            "R_strain": signature.strain,
            "R_combined": signature.combined,
        }
    )
    return result


def geometry_spectrum(row: Mapping[str, float], means: Mapping[str, float], deviations: Mapping[str, float]) -> dict[str, object]:
    signature = qp.geometry_signature(row, means, deviations, epsilon=qp.DEFAULT_EPSILON, softening=ROBUST_Z_SCALE)
    return qp.normalized_geometry_spectrum(signature, epsilon=qp.DEFAULT_EPSILON, null_threshold=NULL_LIKE_THRESHOLD)


def class_summary(class_name: str, rows: Sequence[Mapping[str, float]]) -> dict[str, object]:
    if not rows:
        raise PdcQpStabilityError("class summary requires at least one scored row")
    result: dict[str, object] = {
        "class": class_name,
        "mean_active": float(np.mean([row["active"] for row in rows])),
        "mean_poole_active": float(np.mean([row["poole_active"] for row in rows])),
    }
    for group in ("combined", "birth", "high_support", "strain"):
        for prefix in ("Z", "R"):
            values = np.array([row[f"{prefix}_{group}"] for row in rows], dtype=float)
            result[f"mean_{prefix}_{group}"] = float(values.mean())
            result[f"std_{prefix}_{group}"] = float(values.std(ddof=1)) if len(values) > 1 else 0.0
            result[f"min_{prefix}_{group}"] = float(values.min())
            result[f"median_{prefix}_{group}"] = float(np.median(values))
            result[f"max_{prefix}_{group}"] = float(values.max())
    components = {group: float(result[f"mean_R_{group}"]) for group in ("birth", "high_support", "strain")}
    denominator = math.fsum(value * value for value in components.values()) + qp.DEFAULT_EPSILON
    shares = {group: value * value / denominator for group, value in components.items()}
    result.update({f"{group}_share": value for group, value in shares.items()})
    if float(result["mean_R_combined"]) < NULL_LIKE_THRESHOLD:
        result["dominant_signature"] = "null-like"
    else:
        dominant = max(shares, key=shares.__getitem__)
        result["dominant_signature"] = f"{dominant.replace('_', '-')}-led" if shares[dominant] >= 0.5 else "mixed geometry"
    return result


def deterministic_density_swap(field: object, *, class_name: str, sample_index: int, swaps: int) -> np.ndarray:
    normalized = _validated_field(field)
    normalized_sample = _require_int(sample_index, "sample_index", 0, MAX_SAMPLE_COUNT - 1)
    if not isinstance(class_name, str) or class_name not in SCORED_CLASS_ORDER:
        raise PdcQpStabilityError("class_name is not a benchmark class")
    active = np.flatnonzero(normalized.ravel() == 1).tolist()
    inactive = np.flatnonzero(normalized.ravel() == 0).tolist()
    normalized_swaps = _require_int(swaps, "swaps", 1, min(len(active), len(inactive)))
    seed_material = f"{class_name}:{normalized_sample}:{normalized_swaps}:{CONTRACT_VERSION}".encode("ascii")
    deterministic_seed = int.from_bytes(hashlib.sha256(seed_material).digest()[:8], "big")
    generator = random.Random(deterministic_seed)
    result = normalized.copy().ravel()
    for index in generator.sample(active, normalized_swaps):
        result[index] = 0
    for index in generator.sample(inactive, normalized_swaps):
        result[index] = 1
    return result.reshape(normalized.shape)


def stability_tolerances(*, hamming_fraction: float, control: bool) -> dict[str, float | None]:
    if not math.isfinite(hamming_fraction) or not 0.0 < hamming_fraction <= 1.0:
        raise PdcQpStabilityError("hamming_fraction must be finite and in (0,1]")
    return {
        "max_abs_R_drift": (0.08 if control else 0.06) + 125.0 * hamming_fraction,
        "max_relative_R_drift": None if control else 0.01 + 25.0 * hamming_fraction,
        "max_spectrum_l1_drift": None if control else 0.03 + 50.0 * hamming_fraction,
    }
