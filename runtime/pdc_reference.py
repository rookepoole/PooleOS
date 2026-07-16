"""Independent scalar and dense-matrix reference oracles for canonical PDC math."""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Iterable, Sequence


Shape2 = tuple[int, int]
Shape3 = tuple[int, int, int]
Coord2 = tuple[int, int]
Coord3 = tuple[int, int, int]
DenseMatrix = tuple[tuple[int, ...], ...]

MIN_PERIODIC_EXTENT = 3
MAX_REFERENCE_CELLS = 16_777_216
MAX_DENSE_MATRIX_CELLS = 512
BASE_BIRTH_WINDOW = (5, 7)
BASE_SURVIVAL_WINDOW = (5, 9)


class PdcContractError(ValueError):
    """Base exception for inputs outside the frozen reference contract."""


class PdcShapeError(PdcContractError):
    """Raised when a shape or coordinate violates the contract."""


class PdcOverflowError(PdcContractError):
    """Raised before a shape or byte calculation can overflow its bound."""


class PdcMatrixLimitError(PdcContractError):
    """Raised when the dense specification oracle would be impractically large."""


@dataclass(frozen=True)
class SiteMeasurement:
    support: int
    capacity: int
    deficit: int
    excess: int
    strain: int
    channel: str
    accepted: bool
    next_state: int

    def to_dict(self) -> dict[str, int | str | bool]:
        return asdict(self)


@dataclass(frozen=True)
class PlanarFirstStepSummary:
    birth_spectrum: dict[str, int]
    in_plane_births: int
    normal_layer_births: int
    deaths: int
    total_births: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SparseFirstResponseSummary:
    initial_active: int
    births: int
    deaths: int
    events: int
    final_active: int
    birth_spectrum: dict[str, int]
    death_spectrum: dict[str, int]
    survival_spectrum: dict[str, int]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def checked_product(values: Sequence[int], *, limit: int = MAX_REFERENCE_CELLS) -> int:
    if not values:
        raise PdcShapeError("shape must contain at least one extent")
    product = 1
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int):
            raise PdcShapeError("shape extents must be integers")
        if value <= 0:
            raise PdcShapeError("shape extents must be positive")
        if product > limit // value:
            raise PdcOverflowError(f"shape product exceeds contract limit {limit}")
        product *= value
    return product


def validate_periodic_shape(shape: Sequence[int], *, dimensions: int) -> tuple[tuple[int, ...], int]:
    if len(shape) != dimensions:
        raise PdcShapeError(f"expected a {dimensions}D shape")
    normalized = tuple(shape)
    for extent in normalized:
        if isinstance(extent, bool) or not isinstance(extent, int):
            raise PdcShapeError("shape extents must be integers")
        if extent < MIN_PERIODIC_EXTENT:
            raise PdcShapeError(
                f"periodic extents must be at least {MIN_PERIODIC_EXTENT} so Moore neighbors are distinct"
            )
    return normalized, checked_product(normalized)


def validate_binary_field(field: Sequence[int], shape: Sequence[int], *, dimensions: int) -> tuple[int, ...]:
    normalized_shape, count = validate_periodic_shape(shape, dimensions=dimensions)
    if len(field) != count:
        raise PdcShapeError(f"field length {len(field)} does not match shape {normalized_shape} ({count})")
    out: list[int] = []
    for value in field:
        if value not in (0, 1):
            raise PdcContractError(f"binary field value must be 0 or 1, got {value!r}")
        out.append(int(value))
    return tuple(out)


def _validate_coord(coord: Sequence[int], shape: Sequence[int]) -> tuple[int, ...]:
    if len(coord) != len(shape):
        raise PdcShapeError("coordinate dimensionality does not match shape")
    normalized: list[int] = []
    for value, extent in zip(coord, shape, strict=True):
        if isinstance(value, bool) or not isinstance(value, int):
            raise PdcShapeError("coordinates must be integers")
        if not 0 <= value < extent:
            raise PdcShapeError(f"coordinate {tuple(coord)} is outside shape {tuple(shape)}")
        normalized.append(value)
    return tuple(normalized)


def flat_index_2d(coord: Coord2, shape: Shape2) -> int:
    (x, y) = _validate_coord(coord, shape)
    sx, _ = shape
    return y * sx + x


def flat_index_3d(coord: Coord3, shape: Shape3) -> int:
    (x, y, z) = _validate_coord(coord, shape)
    sx, sy, _ = shape
    return (z * sy + y) * sx + x


def unflatten_2d(index: int, shape: Shape2) -> Coord2:
    _, count = validate_periodic_shape(shape, dimensions=2)
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < count:
        raise PdcShapeError("flat index is outside the 2D field")
    sx, _ = shape
    y, x = divmod(index, sx)
    return x, y


def unflatten_3d(index: int, shape: Shape3) -> Coord3:
    _, count = validate_periodic_shape(shape, dimensions=3)
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < count:
        raise PdcShapeError("flat index is outside the 3D field")
    sx, sy, _ = shape
    z, rem = divmod(index, sx * sy)
    y, x = divmod(rem, sx)
    return x, y, z


def moore_neighbor_coords(coord: Coord3, shape: Shape3) -> tuple[Coord3, ...]:
    validate_periodic_shape(shape, dimensions=3)
    x, y, z = _validate_coord(coord, shape)
    sx, sy, sz = shape
    return tuple(
        ((x + dx) % sx, (y + dy) % sy, (z + dz) % sz)
        for dz in (-1, 0, 1)
        for dy in (-1, 0, 1)
        for dx in (-1, 0, 1)
        if not (dx == 0 and dy == 0 and dz == 0)
    )


def scalar_moore_support(field: Sequence[int], shape: Shape3) -> tuple[int, ...]:
    values = validate_binary_field(field, shape, dimensions=3)
    sx, sy, sz = shape
    out = [0] * len(values)
    for z in range(sz):
        for y in range(sy):
            for x in range(sx):
                total = 0
                for dz in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            if dx == 0 and dy == 0 and dz == 0:
                                continue
                            source = ((z + dz) % sz, (y + dy) % sy, (x + dx) % sx)
                            total += values[(source[0] * sy + source[1]) * sx + source[2]]
                out[(z * sy + y) * sx + x] = total
    return tuple(out)


@lru_cache(maxsize=32)
def cyclic_closed_matrix(extent: int) -> DenseMatrix:
    validate_periodic_shape((extent,), dimensions=1)
    rows = [[0] * extent for _ in range(extent)]
    for row in range(extent):
        for delta in (-1, 0, 1):
            rows[row][(row + delta) % extent] += 1
    return tuple(tuple(row) for row in rows)


def kronecker(left: DenseMatrix, right: DenseMatrix) -> DenseMatrix:
    if not left or not right or not left[0] or not right[0]:
        raise PdcContractError("Kronecker operands must be non-empty matrices")
    left_cols = len(left[0])
    right_cols = len(right[0])
    if any(len(row) != left_cols for row in left) or any(len(row) != right_cols for row in right):
        raise PdcContractError("Kronecker operands must be rectangular")
    rows = [[0] * (left_cols * right_cols) for _ in range(len(left) * len(right))]
    for li, left_row in enumerate(left):
        for ri, right_row in enumerate(right):
            output_row = rows[li * len(right) + ri]
            for lj, left_value in enumerate(left_row):
                if left_value == 0:
                    continue
                base = lj * right_cols
                for rj, right_value in enumerate(right_row):
                    output_row[base + rj] = left_value * right_value
    return tuple(tuple(row) for row in rows)


def _subtract_identity(matrix: DenseMatrix) -> DenseMatrix:
    if len(matrix) != len(matrix[0]) or any(len(row) != len(matrix) for row in matrix):
        raise PdcContractError("identity subtraction requires a square matrix")
    rows = [list(row) for row in matrix]
    for index in range(len(rows)):
        rows[index][index] -= 1
    return tuple(tuple(row) for row in rows)


@lru_cache(maxsize=16)
def moore_matrix_3d(shape: Shape3) -> DenseMatrix:
    normalized, count = validate_periodic_shape(shape, dimensions=3)
    if count > MAX_DENSE_MATRIX_CELLS:
        raise PdcMatrixLimitError(
            f"dense A26 oracle is limited to {MAX_DENSE_MATRIX_CELLS} cells; requested {count}"
        )
    sx, sy, sz = normalized
    closed = kronecker(cyclic_closed_matrix(sz), kronecker(cyclic_closed_matrix(sy), cyclic_closed_matrix(sx)))
    return _subtract_identity(closed)


@lru_cache(maxsize=16)
def planar_matrices_2d(shape: Shape2) -> tuple[DenseMatrix, DenseMatrix]:
    normalized, count = validate_periodic_shape(shape, dimensions=2)
    if count > MAX_DENSE_MATRIX_CELLS:
        raise PdcMatrixLimitError(
            f"dense A8/A9 oracle is limited to {MAX_DENSE_MATRIX_CELLS} cells; requested {count}"
        )
    sx, sy = normalized
    a9 = kronecker(cyclic_closed_matrix(sy), cyclic_closed_matrix(sx))
    return _subtract_identity(a9), a9


def matrix_vector_multiply(matrix: DenseMatrix, vector: Sequence[int]) -> tuple[int, ...]:
    if not matrix:
        raise PdcContractError("matrix must not be empty")
    width = len(matrix[0])
    if len(vector) != width or any(len(row) != width for row in matrix):
        raise PdcShapeError("matrix and vector dimensions do not agree")
    return tuple(sum(coefficient * value for coefficient, value in zip(row, vector, strict=True)) for row in matrix)


def matrix_moore_support(field: Sequence[int], shape: Shape3) -> tuple[int, ...]:
    values = validate_binary_field(field, shape, dimensions=3)
    return matrix_vector_multiply(moore_matrix_3d(shape), values)


def measure_binary_field(field: Sequence[int], shape: Shape3, *, support: Sequence[int] | None = None) -> tuple[SiteMeasurement, ...]:
    values = validate_binary_field(field, shape, dimensions=3)
    support_values = tuple(support) if support is not None else scalar_moore_support(values, shape)
    if len(support_values) != len(values):
        raise PdcShapeError("support vector length does not match field")
    measurements: list[SiteMeasurement] = []
    for state, count in zip(values, support_values, strict=True):
        if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= 26:
            raise PdcContractError(f"support count must be an integer in [0, 26], got {count!r}")
        active = state == 1
        capacity = 9 if active else 7
        deficit = max(5 - count, 0)
        excess = max(count - capacity, 0)
        strain = excess - deficit
        accepted = (5 <= count <= 9) if active else (5 <= count <= 7)
        channel = ("O10+" if count >= 10 else f"S{count}") if active else f"B{count}"
        measurements.append(
            SiteMeasurement(
                support=count,
                capacity=capacity,
                deficit=deficit,
                excess=excess,
                strain=strain,
                channel=channel,
                accepted=accepted,
                next_state=int(accepted),
            )
        )
    return tuple(measurements)


def binary_next_state(field: Sequence[int], shape: Shape3, *, support: Sequence[int] | None = None) -> tuple[int, ...]:
    return tuple(item.next_state for item in measure_binary_field(field, shape, support=support))


def channel_counts(measurements: Iterable[SiteMeasurement], *, accepted_only: bool = False) -> dict[str, int]:
    counts: dict[str, int] = {}
    for measurement in measurements:
        if accepted_only and not measurement.accepted:
            continue
        counts[measurement.channel] = counts.get(measurement.channel, 0) + 1
    return dict(sorted(counts.items()))


def scalar_planar_counts(defects: Sequence[int], shape: Shape2) -> tuple[tuple[int, ...], tuple[int, ...]]:
    values = validate_binary_field(defects, shape, dimensions=2)
    sx, sy = shape
    open_counts = [0] * len(values)
    closed_counts = [0] * len(values)
    for y in range(sy):
        for x in range(sx):
            closed = 0
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    closed += values[((y + dy) % sy) * sx + ((x + dx) % sx)]
            index = y * sx + x
            closed_counts[index] = closed
            open_counts[index] = closed - values[index]
    return tuple(open_counts), tuple(closed_counts)


def matrix_planar_counts(defects: Sequence[int], shape: Shape2) -> tuple[tuple[int, ...], tuple[int, ...]]:
    values = validate_binary_field(defects, shape, dimensions=2)
    a8, a9 = planar_matrices_2d(shape)
    return matrix_vector_multiply(a8, values), matrix_vector_multiply(a9, values)


def planar_first_step_summary(defects: Sequence[int], shape: Shape2) -> PlanarFirstStepSummary:
    values = validate_binary_field(defects, shape, dimensions=2)
    q_values, r_values = scalar_planar_counts(values, shape)
    spectrum = {"B5": 0, "B6": 0, "B7": 0}
    in_plane_births = 0
    deaths = 0
    for defect, q_value in zip(values, q_values, strict=True):
        if defect and 1 <= q_value <= 3:
            channel = f"B{8 - q_value}"
            spectrum[channel] += 1
            in_plane_births += 1
        elif not defect and q_value >= 4:
            deaths += 1

    normal_births = 0
    for r_value in r_values:
        if 2 <= r_value <= 4:
            channel = f"B{9 - r_value}"
            spectrum[channel] += 2
            normal_births += 2

    return PlanarFirstStepSummary(
        birth_spectrum=spectrum,
        in_plane_births=in_plane_births,
        normal_layer_births=normal_births,
        deaths=deaths,
        total_births=in_plane_births + normal_births,
    )


def defect_field_2d(shape: Shape2, coords: Iterable[Coord2]) -> tuple[int, ...]:
    _, count = validate_periodic_shape(shape, dimensions=2)
    field = [0] * count
    for coord in coords:
        field[flat_index_2d(coord, shape)] = 1
    return tuple(field)


def rectangle_defect_field(width: int, height: int, shape: Shape2, *, origin: Coord2 = (0, 0)) -> tuple[int, ...]:
    if isinstance(width, bool) or isinstance(height, bool) or not isinstance(width, int) or not isinstance(height, int):
        raise PdcShapeError("rectangle dimensions must be integers")
    if width <= 0 or height <= 0:
        raise PdcShapeError("rectangle dimensions must be positive")
    ox, oy = origin
    if ox < 0 or oy < 0 or ox + width > shape[0] or oy + height > shape[1]:
        raise PdcShapeError("rectangle must fit without wrapping in the requested field")
    return defect_field_2d(shape, ((ox + x, oy + y) for y in range(height) for x in range(width)))


def line_defect_field(length: int, shape: Shape2, *, origin: Coord2 = (0, 0), axis: str = "x") -> tuple[int, ...]:
    if isinstance(length, bool) or not isinstance(length, int) or length <= 0:
        raise PdcShapeError("line length must be a positive integer")
    ox, oy = origin
    if axis == "x":
        coords = ((ox + offset, oy) for offset in range(length))
        end = (ox + length, oy + 1)
    elif axis == "y":
        coords = ((ox, oy + offset) for offset in range(length))
        end = (ox + 1, oy + length)
    else:
        raise PdcShapeError("line axis must be 'x' or 'y'")
    if ox < 0 or oy < 0 or end[0] > shape[0] or end[1] > shape[1]:
        raise PdcShapeError("line must fit without wrapping in the requested field")
    return defect_field_2d(shape, coords)


def centered_box_origin(shape: Shape3, extents: Shape3) -> Coord3:
    validate_periodic_shape(shape, dimensions=3)
    if len(extents) != 3 or any(
        isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in extents
    ):
        raise PdcShapeError("box extents must be three positive integers")
    if any(extent + 2 > bound for extent, bound in zip(extents, shape, strict=True)):
        raise PdcShapeError("box must have at least one inactive cell of margin on every periodic face")
    return tuple(bound // 2 - extent // 2 for bound, extent in zip(shape, extents, strict=True))  # type: ignore[return-value]


def solid_cuboid_coords(a: int, b: int, c: int, shape: Shape3) -> tuple[Coord3, ...]:
    cuboid_formula(a, b, c)
    ox, oy, oz = centered_box_origin(shape, (a, b, c))
    return tuple((ox + x, oy + y, oz + z) for x in range(a) for y in range(b) for z in range(c))


def closed_surface_shell_coords(a: int, b: int, c: int, shape: Shape3) -> tuple[Coord3, ...]:
    closed_shell_formula(a, b, c)
    ox, oy, oz = centered_box_origin(shape, (a, b, c))
    return tuple(
        (ox + x, oy + y, oz + z)
        for x in range(a)
        for y in range(b)
        for z in range(c)
        if x in (0, a - 1) or y in (0, b - 1) or z in (0, c - 1)
    )


def sparse_first_response(active_coords: Iterable[Coord3], shape: Shape3) -> SparseFirstResponseSummary:
    normalized_shape, _ = validate_periodic_shape(shape, dimensions=3)
    active: set[Coord3] = set()
    for coord in active_coords:
        normalized = _validate_coord(coord, normalized_shape)
        typed = (normalized[0], normalized[1], normalized[2])
        if typed in active:
            raise PdcContractError(f"duplicate active coordinate {typed}")
        active.add(typed)

    sx, sy, sz = normalized_shape
    support: dict[Coord3, int] = {}
    for x, y, z in active:
        for dz in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0 and dz == 0:
                        continue
                    target = ((x + dx) % sx, (y + dy) % sy, (z + dz) % sz)
                    support[target] = support.get(target, 0) + 1

    births = 0
    deaths = 0
    birth_spectrum = {"B5": 0, "B6": 0, "B7": 0}
    death_spectrum = {"D_low": 0, "D_high": 0}
    survival_spectrum = {f"S{count}": 0 for count in range(5, 10)}
    for coord in support.keys() | active:
        count = support.get(coord, 0)
        if coord in active:
            if 5 <= count <= 9:
                survival_spectrum[f"S{count}"] += 1
            else:
                deaths += 1
                death_spectrum["D_low" if count < 5 else "D_high"] += 1
        elif 5 <= count <= 7:
            births += 1
            birth_spectrum[f"B{count}"] += 1

    initial_active = len(active)
    return SparseFirstResponseSummary(
        initial_active=initial_active,
        births=births,
        deaths=deaths,
        events=births + deaths,
        final_active=initial_active + births - deaths,
        birth_spectrum=birth_spectrum,
        death_spectrum=death_spectrum,
        survival_spectrum=survival_spectrum,
    )


def rectangle_formula(width: int, height: int, *, model_tag: str = "B5-7/S5-9") -> dict[str, object]:
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 2 for value in (width, height)):
        raise PdcShapeError("rectangle theorem requires integer width,height >= 2")
    raw_spectrum = {"B5": 12, "B6": 4 * width + 4 * height - 16, "B7": 16}
    if model_tag == "B5-7/S5-9":
        return {"births": sum(raw_spectrum.values()), "deaths": 0, "birth_spectrum": raw_spectrum}
    if model_tag == "PMphi.default.remove_B7":
        return {
            "births": raw_spectrum["B5"] + raw_spectrum["B6"],
            "deaths": 0,
            "birth_spectrum": {"B5": raw_spectrum["B5"], "B6": raw_spectrum["B6"], "B7": 0},
        }
    raise PdcContractError(f"unsupported rectangle model tag {model_tag!r}")


def line_hole_formula(length: int) -> dict[str, object]:
    if isinstance(length, bool) or not isinstance(length, int) or length < 1:
        raise PdcShapeError("line theorem requires integer length >= 1")
    if length == 1:
        return {"births": 0, "deaths": 0, "birth_spectrum": {"B5": 0, "B6": 0, "B7": 0}}
    spectrum = {"B5": 0, "B6": 7 * length - 14, "B7": 14}
    return {"births": sum(spectrum.values()), "deaths": 0, "birth_spectrum": spectrum}


def cuboid_formula(a: int, b: int, c: int) -> dict[str, object]:
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 4 for value in (a, b, c)):
        raise PdcShapeError("solid cuboid theorem requires integer a,b,c >= 4")
    active_0 = a * b * c
    births = 8 * (a + b + c - 6)
    deaths = active_0 - 8
    return {
        "active_0": active_0,
        "births": births,
        "deaths": deaths,
        "active_1": active_0 + births - deaths,
        "birth_spectrum": {"B5": 0, "B6": births, "B7": 0},
    }


def closed_shell_formula(a: int, b: int, c: int) -> dict[str, object]:
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 4 for value in (a, b, c)):
        raise PdcShapeError("closed shell theorem requires integer a,b,c >= 4")
    active_0 = 2 * (a * b + a * c + b * c) - 4 * (a + b + c) + 8
    births = 8 * (a + b + c - 6)
    deaths = 8 * (a + b + c - 9)
    return {
        "active_0": active_0,
        "births": births,
        "deaths": deaths,
        "active_1": active_0 + births - deaths,
        "birth_spectrum": {"B5": 0, "B6": births, "B7": 0},
    }


def canonical_array_hash(values: Sequence[int], shape: Sequence[int], *, dtype: str = "u8") -> str:
    count = checked_product(tuple(shape))
    if len(values) != count:
        raise PdcShapeError("array length does not match hash shape")
    if dtype == "u8":
        if any(isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 255 for value in values):
            raise PdcContractError("u8 hash values must be integers in [0,255]")
        payload = bytes(values)
    elif dtype == "i8":
        if any(isinstance(value, bool) or not isinstance(value, int) or not -128 <= value <= 127 for value in values):
            raise PdcContractError("i8 hash values must be integers in [-128,127]")
        payload = struct.pack(f"<{len(values)}b", *values)
    elif dtype == "u64":
        if any(isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 2**64 for value in values):
            raise PdcContractError("u64 hash values must be integers in [0,2^64)")
        payload = struct.pack(f"<{len(values)}Q", *values)
    else:
        raise PdcContractError(f"unsupported canonical hash dtype {dtype!r}")

    header = {
        "axis_order": "x_fastest_then_y_then_z",
        "byte_order": "little",
        "dtype": dtype,
        "shape": list(shape),
    }
    encoded_header = json.dumps(header, sort_keys=True, separators=(",", ":")).encode("ascii")
    return hashlib.sha256(encoded_header + b"\x00" + payload).hexdigest().upper()
