# PDC-REP-0.1 Representation and Conversion ABI

Status: checked Python reference ABI for PooleOS P1.3 and P1.4  
Parent mathematics: `PDC-MATH-0.1`  
Reference implementation: `runtime/pdc_representation.py`  
Machine contract: `runs/pdc_representation_contract.json`  
Differential receipt: `runs/pdc_representation_receipt.json`

## Scope

`PDC-REP-0.1` freezes the logical and serialized boundary for periodic 2D and 3D fields used by the current binary PDC reference. It adds no update rule and does not alter `PDC-MATH-0.1`.

The ABI supports:

1. immutable dense binary `u8` payloads;
2. immutable sparse binary fields as strictly increasing unique `u64` flat indices;
3. immutable bit-packed binary fields with flat index zero in the least-significant bit;
4. immutable probability fields as finite canonical IEEE-754 binary64 values in `[0,1]`; and
5. immutable native-buffer snapshots with explicit dtype, offset, padded x-fastest strides, ownership provenance, mutability provenance, and declared base alignment.

All shapes use `(x_extent,y_extent[,z_extent])`, periodic extents of at least three, origin zero, and x-fastest flattening. The reference limit remains 16,777,216 logical cells.

## Binary Semantic Identity

Dense, sparse, bit-packed, and native `u8` forms are semantically identical only when they decode to the exact same binary field. Their representation-independent semantic hash is the existing `PDC-MATH-0.1` canonical dense `u8` hash.

Each form also has a representation-specific storage hash:

```text
SHA-256(canonical ASCII JSON header || 0x00 || canonical logical payload)
```

The header binds `PDC-REP-0.1`, representation kind, shape, boundary, axis order, dtype, byte order, and representation-specific metadata. Native hashes include the validated view descriptor but exclude unused backing-buffer padding bytes, which may be uninitialized and are not logical data.

## Dense Binary

- Dtype is `u8`.
- Exactly one byte is stored per logical cell.
- Every byte is exactly `0` or `1`.
- Payload length equals the checked shape product.
- The object owns immutable bytes.

## Sparse Binary

- Active sites are implicit value `1`; all omitted sites are `0`.
- Indices are canonical x-fastest flat indices serialized as little-endian `u64`.
- Indices must be strictly increasing, unique, and less than the checked cell count.
- Duplicate, negative, unsorted, noninteger, and out-of-range indices fail closed.

## Bit-Packed Binary

- Flat index `i` occupies bit `(i mod 8)` of byte `floor(i/8)`.
- Bit order is least-significant-bit first.
- Payload length is `ceil(cell_count/8)`.
- Unused high bits in the final byte are zero and are validated.

## Probability Field

- Logical dtype is little-endian IEEE-754 binary64 (`f64`).
- Every value is finite and in `[0,1]`.
- Negative zero canonicalizes to positive zero.
- NaN, infinities, values outside `[0,1]`, and malformed lengths fail closed.
- Binary-to-probability maps `0 -> 0.0` and `1 -> 1.0` exactly.
- Probability-to-binary is allowed only when every value is exactly `0.0` or `1.0`; thresholding is a different model operation and is not an implicit conversion.
- This ABI freezes storage and conversion only. Q/P probability dynamics remain P3 work.

## Native Buffer Snapshot

The Python reference validates a byte-contiguous backing object and copies its logical cells into an immutable snapshot before execution or hashing. This establishes descriptor behavior without claiming a finished C ABI or kernel pointer validator.

Supported dtypes are binary `u8` and probability `f64`.

For item size `s`, strides are in bytes and must satisfy:

```text
stride_x = s
stride_y >= x_extent * stride_x
stride_z >= y_extent * stride_y          # 3D only
```

Every stride is positive and divisible by `s`. This permits row/slice padding while rejecting negative, broadcast, transposed, and overlapping views in v0.1. Offset, shape, stride, item-size, and final-span arithmetic use checked `u64` operations before touching the buffer.

The descriptor carries a declared power-of-two base-alignment guarantee in `[1,4096]`. It must be at least the dtype alignment, and offset/strides must preserve that alignment. The Python receipt proves descriptor-relative checks; a future C/kernel implementation must validate the actual mapped pointer and must not trust the declaration.

Ownership modes:

- `runtime_owned`: the runtime controls the source and snapshots logical bytes;
- `caller_borrowed`: accepted only when `snapshot_borrowed=true`; and
- mutable sources are recorded as `mutable_snapshotted`, then detached from later mutations.

Borrowed use without a snapshot fails closed. Native output views, in-place mutation, retained mutable aliases, device pointers, DMA, pinning, and zero-copy execution remain outside v0.1 and require later P6/P8/P9/P13 ownership and lifetime evidence.

## Conversion Graph

Lossless required paths are:

```text
dense_binary <-> sparse_binary
dense_binary <-> bitpacked_binary
dense_binary -> probability_field -> dense_binary  # exact binary embedding only
dense_binary <-> native_buffer_snapshot[u8]
probability_field <-> native_buffer_snapshot[f64]
```

Every binary round trip must preserve exact dense bytes, the `PDC-MATH-0.1` semantic hash, and the applicable scalar PDC result. Storage hashes are expected to differ between representation kinds.

## Failure Boundary

The reference rejects malformed dimensions, extents below three, shape-product overflow, payload-length mismatch, invalid binary values, sparse duplicates/order/range errors, nonzero bit padding, nonfinite probabilities, lossy probability conversion, unsupported dtype, noncontiguous backing storage, overlapping or misaligned strides, descriptor span beyond the backing object, unsupported ownership, and borrowed storage without a snapshot.

## Honest Boundary

`PDC-REP-0.1` is a checked reference ABI and conversion oracle. It is not the portable C17 `libpdc` ABI, an optimized route, a mutable RAM pool, a device buffer contract, a kernel memory-safety proof, or booted enforcement. Those remain P6-P9 and P13 obligations.
