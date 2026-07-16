"""Checked reference representations and conversions for PDC-REP-0.1."""

from __future__ import annotations

import hashlib
import json
import math
import struct
from array import array
from dataclasses import dataclass
from typing import Sequence

from runtime import pdc_reference


ABI_VERSION = "PDC-REP-0.1"
BOUNDARY_MODE = "periodic"
AXIS_ORDER = "x_fastest_then_y_then_z"
BYTE_ORDER = "little"
BIT_ORDER = "least_significant_bit_first"
MAX_U64 = 2**64 - 1
SUPPORTED_DIMENSIONS = (2, 3)
SUPPORTED_NATIVE_DTYPES = ("u8", "f64")


class PdcRepresentationError(pdc_reference.PdcContractError):
    """Base exception for representation ABI violations."""


class PdcConversionError(PdcRepresentationError):
    """Raised when a requested conversion is not lossless."""


class PdcStrideError(PdcRepresentationError):
    """Raised for unsupported, overlapping, or out-of-range native strides."""


class PdcAlignmentError(PdcRepresentationError):
    """Raised when a native descriptor does not meet its dtype alignment."""


class PdcOwnershipError(PdcRepresentationError):
    """Raised when borrowed mutable storage is used without a stable snapshot."""


def _normalize_shape(shape: Sequence[int]) -> tuple[tuple[int, ...], int]:
    if len(shape) not in SUPPORTED_DIMENSIONS:
        raise pdc_reference.PdcShapeError("PDC-REP-0.1 supports only 2D and 3D fields")
    return pdc_reference.validate_periodic_shape(tuple(shape), dimensions=len(shape))


def checked_u64_add(left: int, right: int) -> int:
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in (left, right)):
        raise pdc_reference.PdcOverflowError("checked u64 addition requires non-negative integers")
    if left > MAX_U64 - right:
        raise pdc_reference.PdcOverflowError("u64 addition overflow")
    return left + right


def checked_u64_multiply(left: int, right: int) -> int:
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in (left, right)):
        raise pdc_reference.PdcOverflowError("checked u64 multiplication requires non-negative integers")
    if left and right > MAX_U64 // left:
        raise pdc_reference.PdcOverflowError("u64 multiplication overflow")
    return left * right


def _canonical_hash(header: dict[str, object], payload: bytes) -> str:
    encoded = json.dumps(header, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(encoded + b"\x00" + payload).hexdigest().upper()


def _shape_header(shape: Sequence[int], *, dtype: str) -> dict[str, object]:
    return {
        "axis_order": AXIS_ORDER,
        "boundary": BOUNDARY_MODE,
        "byte_order": BYTE_ORDER,
        "dtype": dtype,
        "shape": list(shape),
    }


@dataclass(frozen=True)
class DenseBinaryField:
    shape: tuple[int, ...]
    payload: bytes

    def __post_init__(self) -> None:
        shape, count = _normalize_shape(self.shape)
        if not isinstance(self.payload, bytes):
            raise PdcRepresentationError("dense binary payload must be immutable bytes")
        if len(self.payload) != count:
            raise pdc_reference.PdcShapeError("dense binary payload length does not match shape")
        if any(value not in (0, 1) for value in self.payload):
            raise PdcRepresentationError("dense binary payload values must be 0 or 1")
        object.__setattr__(self, "shape", shape)


@dataclass(frozen=True)
class SparseBinaryField:
    shape: tuple[int, ...]
    active_indices: tuple[int, ...]

    def __post_init__(self) -> None:
        shape, count = _normalize_shape(self.shape)
        indices = tuple(self.active_indices)
        previous = -1
        for index in indices:
            if isinstance(index, bool) or not isinstance(index, int):
                raise PdcRepresentationError("sparse indices must be integers")
            if not 0 <= index < count:
                raise pdc_reference.PdcShapeError("sparse index is outside the field")
            if index <= previous:
                raise PdcRepresentationError("sparse indices must be strictly increasing and unique")
            previous = index
        object.__setattr__(self, "shape", shape)
        object.__setattr__(self, "active_indices", indices)


@dataclass(frozen=True)
class BitPackedBinaryField:
    shape: tuple[int, ...]
    payload: bytes

    def __post_init__(self) -> None:
        shape, count = _normalize_shape(self.shape)
        expected = (count + 7) // 8
        if not isinstance(self.payload, bytes):
            raise PdcRepresentationError("bit-packed payload must be immutable bytes")
        if len(self.payload) != expected:
            raise pdc_reference.PdcShapeError("bit-packed payload length does not match shape")
        remainder = count % 8
        if remainder and self.payload and self.payload[-1] & ~((1 << remainder) - 1):
            raise PdcRepresentationError("unused high padding bits must be zero")
        object.__setattr__(self, "shape", shape)


@dataclass(frozen=True)
class ProbabilityField:
    shape: tuple[int, ...]
    values: tuple[float, ...]

    def __post_init__(self) -> None:
        shape, count = _normalize_shape(self.shape)
        if len(self.values) != count:
            raise pdc_reference.PdcShapeError("probability field length does not match shape")
        normalized: list[float] = []
        for value in self.values:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise PdcRepresentationError("probabilities must be real numbers")
            converted = float(value)
            if not math.isfinite(converted) or not 0.0 <= converted <= 1.0:
                raise PdcRepresentationError("probabilities must be finite values in [0,1]")
            normalized.append(0.0 if converted == 0.0 else converted)
        object.__setattr__(self, "shape", shape)
        object.__setattr__(self, "values", tuple(normalized))


@dataclass(frozen=True)
class NativeBufferSnapshot:
    shape: tuple[int, ...]
    dtype: str
    byte_offset: int
    strides: tuple[int, ...]
    source_ownership: str
    source_mutability: str
    declared_base_alignment: int
    source_nbytes: int
    logical_payload: bytes

    def __post_init__(self) -> None:
        shape, count = _normalize_shape(self.shape)
        if self.dtype not in SUPPORTED_NATIVE_DTYPES:
            raise PdcRepresentationError(f"unsupported native dtype {self.dtype!r}")
        item_size = native_item_size(self.dtype)
        if len(self.strides) != len(shape):
            raise PdcStrideError("native stride dimensionality does not match shape")
        if not isinstance(self.logical_payload, bytes):
            raise PdcRepresentationError("native logical payload must be immutable bytes")
        if len(self.logical_payload) != checked_u64_multiply(count, item_size):
            raise pdc_reference.PdcShapeError("native logical payload length does not match shape and dtype")
        if self.source_ownership not in ("runtime_owned", "caller_borrowed"):
            raise PdcOwnershipError("unsupported native source ownership")
        if self.source_mutability not in ("read_only", "mutable_snapshotted"):
            raise PdcOwnershipError("unsupported native source mutability state")
        _validate_alignment(self.dtype, self.byte_offset, self.strides, self.declared_base_alignment)
        _validate_strides(shape, self.dtype, self.strides)
        required = required_native_span(shape, self.dtype, self.byte_offset, self.strides)
        if (
            isinstance(self.source_nbytes, bool)
            or not isinstance(self.source_nbytes, int)
            or self.source_nbytes < required
        ):
            raise pdc_reference.PdcShapeError("native source size does not cover the validated descriptor span")
        if self.dtype == "u8" and any(value not in (0, 1) for value in self.logical_payload):
            raise PdcRepresentationError("native u8 binary payload values must be 0 or 1")
        if self.dtype == "f64":
            values = array("d")
            values.frombytes(self.logical_payload)
            if struct.pack("=H", 1) != struct.pack("<H", 1):  # pragma: no cover - big-endian host
                values.byteswap()
            if any(not math.isfinite(value) or not 0.0 <= value <= 1.0 for value in values):
                raise PdcRepresentationError("native f64 probabilities must be finite values in [0,1]")
            canonical_values = array("d", (0.0 if value == 0.0 else value for value in values))
            if struct.pack("=H", 1) != struct.pack("<H", 1):  # pragma: no cover - big-endian host
                canonical_values.byteswap()
            object.__setattr__(self, "logical_payload", canonical_values.tobytes())
        object.__setattr__(self, "shape", shape)


def dense_binary_field(values: Sequence[int], shape: Sequence[int]) -> DenseBinaryField:
    normalized_shape, count = _normalize_shape(shape)
    if len(values) != count:
        raise pdc_reference.PdcShapeError("dense binary value count does not match shape")
    output = bytearray(count)
    for index, value in enumerate(values):
        if isinstance(value, bool) or not isinstance(value, int) or value not in (0, 1):
            raise PdcRepresentationError("dense binary values must be integer 0 or 1")
        output[index] = value
    return DenseBinaryField(normalized_shape, bytes(output))


def sparse_from_dense(field: DenseBinaryField) -> SparseBinaryField:
    return SparseBinaryField(field.shape, tuple(index for index, value in enumerate(field.payload) if value))


def dense_from_sparse(field: SparseBinaryField) -> DenseBinaryField:
    _, count = _normalize_shape(field.shape)
    payload = bytearray(count)
    for index in field.active_indices:
        payload[index] = 1
    return DenseBinaryField(field.shape, bytes(payload))


def bitpacked_from_dense(field: DenseBinaryField) -> BitPackedBinaryField:
    packed = bytearray((len(field.payload) + 7) // 8)
    for index, value in enumerate(field.payload):
        packed[index // 8] |= value << (index % 8)
    return BitPackedBinaryField(field.shape, bytes(packed))


def bitpacked_from_sparse(field: SparseBinaryField) -> BitPackedBinaryField:
    _, count = _normalize_shape(field.shape)
    packed = bytearray((count + 7) // 8)
    for index in field.active_indices:
        packed[index // 8] |= 1 << (index % 8)
    return BitPackedBinaryField(field.shape, bytes(packed))


_UNPACKED_BYTES = tuple(bytes((value >> bit) & 1 for bit in range(8)) for value in range(256))


def dense_from_bitpacked(field: BitPackedBinaryField) -> DenseBinaryField:
    _, count = _normalize_shape(field.shape)
    payload = b"".join(_UNPACKED_BYTES[value] for value in field.payload)[:count]
    return DenseBinaryField(field.shape, payload)


def probability_from_dense(field: DenseBinaryField) -> ProbabilityField:
    return ProbabilityField(field.shape, tuple(float(value) for value in field.payload))


def dense_from_probability(field: ProbabilityField) -> DenseBinaryField:
    payload = bytearray(len(field.values))
    for index, value in enumerate(field.values):
        if value not in (0.0, 1.0):
            raise PdcConversionError("probability-to-binary conversion is lossless only for exact 0.0/1.0 fields")
        payload[index] = int(value)
    return DenseBinaryField(field.shape, bytes(payload))


def native_item_size(dtype: str) -> int:
    if dtype == "u8":
        return 1
    if dtype == "f64":
        return 8
    raise PdcRepresentationError(f"unsupported native dtype {dtype!r}")


def contiguous_strides(shape: Sequence[int], dtype: str) -> tuple[int, ...]:
    normalized, _ = _normalize_shape(shape)
    item_size = native_item_size(dtype)
    strides = [item_size]
    for extent in normalized[:-1]:
        strides.append(checked_u64_multiply(strides[-1], extent))
    return tuple(strides)


def _validate_strides(shape: Sequence[int], dtype: str, strides: Sequence[int]) -> None:
    item_size = native_item_size(dtype)
    if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in strides):
        raise PdcStrideError("native strides must be positive integers")
    if strides[0] != item_size:
        raise PdcStrideError("x stride must equal dtype item size")
    minimum = item_size
    for axis, extent in enumerate(shape[:-1]):
        minimum = checked_u64_multiply(strides[axis], extent)
        if strides[axis + 1] < minimum:
            raise PdcStrideError("native strides overlap logical rows or slices")


def _validate_alignment(dtype: str, byte_offset: int, strides: Sequence[int], declared_base_alignment: int) -> None:
    item_size = native_item_size(dtype)
    if isinstance(byte_offset, bool) or not isinstance(byte_offset, int) or byte_offset < 0:
        raise PdcAlignmentError("native byte offset must be a non-negative integer")
    if (
        isinstance(declared_base_alignment, bool)
        or not isinstance(declared_base_alignment, int)
        or declared_base_alignment <= 0
        or declared_base_alignment > 4096
        or declared_base_alignment & (declared_base_alignment - 1)
    ):
        raise PdcAlignmentError("declared base alignment must be a power of two in [1,4096]")
    if declared_base_alignment < item_size or byte_offset % item_size:
        raise PdcAlignmentError("native base guarantee and byte offset do not satisfy dtype alignment")
    if any(stride % item_size for stride in strides):
        raise PdcAlignmentError("native strides must preserve dtype alignment")


def required_native_span(shape: Sequence[int], dtype: str, byte_offset: int, strides: Sequence[int]) -> int:
    normalized, _ = _normalize_shape(shape)
    if len(strides) != len(normalized):
        raise PdcStrideError("native stride dimensionality does not match shape")
    _validate_strides(normalized, dtype, strides)
    if isinstance(byte_offset, bool) or not isinstance(byte_offset, int) or byte_offset < 0:
        raise PdcAlignmentError("native byte offset must be a non-negative integer")
    last = byte_offset
    for extent, stride in zip(normalized, strides, strict=True):
        last = checked_u64_add(last, checked_u64_multiply(extent - 1, stride))
    return checked_u64_add(last, native_item_size(dtype))


def make_native_buffer_snapshot(
    buffer: object,
    *,
    shape: Sequence[int],
    dtype: str,
    byte_offset: int = 0,
    strides: Sequence[int] | None = None,
    source_ownership: str,
    declared_base_alignment: int,
    snapshot_borrowed: bool = False,
) -> NativeBufferSnapshot:
    normalized_shape, _ = _normalize_shape(shape)
    normalized_strides = tuple(strides) if strides is not None else contiguous_strides(normalized_shape, dtype)
    _validate_alignment(dtype, byte_offset, normalized_strides, declared_base_alignment)
    required = required_native_span(normalized_shape, dtype, byte_offset, normalized_strides)
    try:
        view = memoryview(buffer)
    except TypeError as exc:
        raise PdcRepresentationError("native source must support the buffer protocol") from exc
    if not view.c_contiguous:
        raise PdcStrideError("native backing buffer must be byte-contiguous")
    byte_view = view.cast("B")
    if byte_view.nbytes < required:
        raise pdc_reference.PdcShapeError("native descriptor exceeds the backing buffer")
    if source_ownership == "caller_borrowed" and not snapshot_borrowed:
        raise PdcOwnershipError("caller-borrowed buffers must be snapshotted before validation or execution")
    if source_ownership not in ("runtime_owned", "caller_borrowed"):
        raise PdcOwnershipError("unsupported native source ownership")

    item_size = native_item_size(dtype)
    row_bytes = checked_u64_multiply(normalized_shape[0], item_size)
    logical = bytearray()
    if len(normalized_shape) == 2:
        sx, sy = normalized_shape
        del sx
        for y in range(sy):
            start = byte_offset + y * normalized_strides[1]
            logical.extend(byte_view[start : start + row_bytes])
    else:
        sx, sy, sz = normalized_shape
        del sx
        for z in range(sz):
            for y in range(sy):
                start = byte_offset + z * normalized_strides[2] + y * normalized_strides[1]
                logical.extend(byte_view[start : start + row_bytes])
    source_mutability = "read_only" if view.readonly else "mutable_snapshotted"
    payload = bytes(logical)
    if dtype == "u8" and any(value not in (0, 1) for value in payload):
        raise PdcRepresentationError("native u8 binary payload values must be 0 or 1")
    if dtype == "f64":
        values = array("d")
        values.frombytes(payload)
        if struct.pack("=H", 1) != struct.pack("<H", 1):  # pragma: no cover - big-endian host
            values.byteswap()
        for value in values:
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise PdcRepresentationError("native f64 probabilities must be finite values in [0,1]")
    return NativeBufferSnapshot(
        shape=normalized_shape,
        dtype=dtype,
        byte_offset=byte_offset,
        strides=normalized_strides,
        source_ownership=source_ownership,
        source_mutability=source_mutability,
        declared_base_alignment=declared_base_alignment,
        source_nbytes=byte_view.nbytes,
        logical_payload=payload,
    )


def native_snapshot_from_dense(
    field: DenseBinaryField,
    *,
    byte_offset: int = 0,
    row_padding_bytes: int = 0,
    slice_padding_bytes: int = 0,
    declared_base_alignment: int = 8,
) -> NativeBufferSnapshot:
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in (row_padding_bytes, slice_padding_bytes)
    ):
        raise PdcStrideError("native padding values must be non-negative integers")
    sx, sy, *rest = field.shape
    row_stride = checked_u64_add(sx, row_padding_bytes)
    strides = [1, row_stride]
    if rest:
        slice_stride = checked_u64_add(checked_u64_multiply(row_stride, sy), slice_padding_bytes)
        strides.append(slice_stride)
    required = required_native_span(field.shape, "u8", byte_offset, strides)
    backing = bytearray(required)
    source_offset = 0
    row_bytes = sx
    if len(field.shape) == 2:
        for y in range(sy):
            destination = byte_offset + y * row_stride
            backing[destination : destination + row_bytes] = field.payload[source_offset : source_offset + row_bytes]
            source_offset += row_bytes
    else:
        sz = rest[0]
        for z in range(sz):
            for y in range(sy):
                destination = byte_offset + z * strides[2] + y * row_stride
                backing[destination : destination + row_bytes] = field.payload[source_offset : source_offset + row_bytes]
                source_offset += row_bytes
    return make_native_buffer_snapshot(
        backing,
        shape=field.shape,
        dtype="u8",
        byte_offset=byte_offset,
        strides=strides,
        source_ownership="runtime_owned",
        declared_base_alignment=declared_base_alignment,
    )


def dense_from_native(snapshot: NativeBufferSnapshot) -> DenseBinaryField:
    if snapshot.dtype != "u8":
        raise PdcConversionError("native-to-binary conversion requires dtype u8")
    return DenseBinaryField(snapshot.shape, snapshot.logical_payload)


def native_snapshot_from_probability(
    field: ProbabilityField,
    *,
    byte_offset: int = 0,
    row_padding_bytes: int = 0,
    slice_padding_bytes: int = 0,
    declared_base_alignment: int = 8,
) -> NativeBufferSnapshot:
    if byte_offset % 8 or row_padding_bytes % 8 or slice_padding_bytes % 8:
        raise PdcAlignmentError("f64 offsets and padding must be multiples of eight bytes")
    values = array("d", field.values)
    if struct.pack("=H", 1) != struct.pack("<H", 1):  # pragma: no cover - big-endian host
        values.byteswap()
    logical = values.tobytes()
    sx, sy, *rest = field.shape
    row_bytes = checked_u64_multiply(sx, 8)
    row_stride = checked_u64_add(row_bytes, row_padding_bytes)
    strides = [8, row_stride]
    if rest:
        strides.append(checked_u64_add(checked_u64_multiply(row_stride, sy), slice_padding_bytes))
    required = required_native_span(field.shape, "f64", byte_offset, strides)
    backing = bytearray(required)
    source_offset = 0
    if len(field.shape) == 2:
        for y in range(sy):
            destination = byte_offset + y * row_stride
            backing[destination : destination + row_bytes] = logical[source_offset : source_offset + row_bytes]
            source_offset += row_bytes
    else:
        sz = rest[0]
        for z in range(sz):
            for y in range(sy):
                destination = byte_offset + z * strides[2] + y * row_stride
                backing[destination : destination + row_bytes] = logical[source_offset : source_offset + row_bytes]
                source_offset += row_bytes
    return make_native_buffer_snapshot(
        backing,
        shape=field.shape,
        dtype="f64",
        byte_offset=byte_offset,
        strides=strides,
        source_ownership="runtime_owned",
        declared_base_alignment=declared_base_alignment,
    )


def probability_from_native(snapshot: NativeBufferSnapshot) -> ProbabilityField:
    if snapshot.dtype != "f64":
        raise PdcConversionError("native-to-probability conversion requires dtype f64")
    values = array("d")
    values.frombytes(snapshot.logical_payload)
    if struct.pack("=H", 1) != struct.pack("<H", 1):  # pragma: no cover - big-endian host
        values.byteswap()
    return ProbabilityField(snapshot.shape, tuple(values))


BinaryRepresentation = DenseBinaryField | SparseBinaryField | BitPackedBinaryField | NativeBufferSnapshot
Representation = BinaryRepresentation | ProbabilityField


def dense_binary_semantic_hash(field: BinaryRepresentation) -> str:
    if isinstance(field, DenseBinaryField):
        dense = field
    elif isinstance(field, SparseBinaryField):
        dense = dense_from_sparse(field)
    elif isinstance(field, BitPackedBinaryField):
        dense = dense_from_bitpacked(field)
    elif isinstance(field, NativeBufferSnapshot):
        dense = dense_from_native(field)
    else:  # pragma: no cover - guarded by the union and runtime checks
        raise PdcRepresentationError("unsupported binary representation")
    return pdc_reference.canonical_array_hash(dense.payload, dense.shape, dtype="u8")


def probability_semantic_hash(field: ProbabilityField | NativeBufferSnapshot) -> str:
    probability = probability_from_native(field) if isinstance(field, NativeBufferSnapshot) else field
    values = array("d", probability.values)
    if struct.pack("=H", 1) != struct.pack("<H", 1):  # pragma: no cover - big-endian host
        values.byteswap()
    header = _shape_header(probability.shape, dtype="f64")
    header["semantic_kind"] = "probability_field"
    return _canonical_hash(header, values.tobytes())


def representation_storage_hash(field: Representation) -> str:
    if isinstance(field, DenseBinaryField):
        header = _shape_header(field.shape, dtype="u8")
        header.update({"abi_version": ABI_VERSION, "representation": "dense_binary"})
        payload = field.payload
    elif isinstance(field, SparseBinaryField):
        header = _shape_header(field.shape, dtype="u8")
        header.update(
            {
                "abi_version": ABI_VERSION,
                "index_dtype": "u64",
                "implicit_active_value": 1,
                "representation": "sparse_binary",
            }
        )
        payload = b"".join(struct.pack("<Q", index) for index in field.active_indices)
    elif isinstance(field, BitPackedBinaryField):
        header = _shape_header(field.shape, dtype="u8")
        header.update(
            {
                "abi_version": ABI_VERSION,
                "bit_order": BIT_ORDER,
                "padding_bits": "zero",
                "representation": "bitpacked_binary",
            }
        )
        payload = field.payload
    elif isinstance(field, ProbabilityField):
        header = _shape_header(field.shape, dtype="f64")
        header.update({"abi_version": ABI_VERSION, "representation": "probability_field"})
        values = array("d", field.values)
        if struct.pack("=H", 1) != struct.pack("<H", 1):  # pragma: no cover - big-endian host
            values.byteswap()
        payload = values.tobytes()
    elif isinstance(field, NativeBufferSnapshot):
        header = _shape_header(field.shape, dtype=field.dtype)
        header.update(
            {
                "abi_version": ABI_VERSION,
                "byte_offset": field.byte_offset,
                "declared_base_alignment": field.declared_base_alignment,
                "representation": "native_buffer_snapshot",
                "source_mutability": field.source_mutability,
                "source_ownership": field.source_ownership,
                "strides": list(field.strides),
            }
        )
        payload = field.logical_payload
    else:  # pragma: no cover - exhaustive runtime guard
        raise PdcRepresentationError("unsupported representation")
    return _canonical_hash(header, payload)
