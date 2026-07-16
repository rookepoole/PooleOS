# PDC-MATH-0.1 Canonical Executable Contract

Status: reference contract for PooleOS P1  
Model: raw binary `B5-7/S5-9` unless a different model tag is explicit  
Machine artifact: `runs/pdc_math_contract.json`  
Golden vectors: `runs/pdc_golden_vectors.json`

## Scope

This contract freezes the first executable PooleOS meaning of the binary and planar Poole Defect Calculus core. It covers:

- periodic 3D binary fields;
- 26-neighbor support and B5-7/S5-9 update;
- capacity, deficit, excess, and signed strain;
- typed birth/survival/overflow channels;
- periodic planar open and closed defect counts;
- first-step planar births/deaths;
- rectangle, line-hole, solid-cuboid, and closed-shell formula oracles; and
- canonical array hashing for reference evidence.

It does not yet freeze Q/P probability, signed-state update dynamics, optimized CPU/RAM/GPU routes, PooleGlyph intrinsics, PGB2/PGVM2 encoding, kernel enforcement, UI behavior, or ISO behavior.

## Source Binding

The contract is bound to `runs/pdc_source_intake.json`. That artifact verifies content-addressed copies of all seven user-designated sources. Raw benchmark candidates in the same intake are only indexed; they are not promoted to source authority or reproduction evidence.

## Coordinates and Flattening

Coordinates are written `(x,y,z)`. Shapes are written `(x_extent,y_extent,z_extent)`. `x` is the fastest-varying axis.

```text
flat_3d(x,y,z) = ((z * y_extent) + y) * x_extent + x
flat_2d(x,y)   = y * x_extent + x
```

The origin is `(0,0,0)`. Array payloads, matrix rows/columns, trace coordinates, and hashes use this convention.

## Boundary Contract

PDC-MATH-0.1 supports `periodic` boundaries. Every periodic extent must be at least 3.

Extents 1 and 2 are rejected because distinct offsets in `{-1,0,+1}` alias to the same periodic site. Rejecting them avoids an ambiguity between weighted-offset and unique-neighbor interpretations. A later contract may add an explicitly tagged small-torus mode, but it cannot silently change this contract.

## Binary 3D Model

For binary state vector `x` and support vector `n`:

```text
C_i   = 7 + 2*x_i
D_i   = max(5 - n_i, 0)
E_i   = max(n_i - C_i, 0)
psi_i = E_i - D_i

x_next_i = 1{5 <= n_i <= 7 + 2*x_i}
```

Equivalently:

- a void site is born when support is 5, 6, or 7;
- an active site survives when support is 5 through 9; and
- all other sites are void at the next step.

`D` and `E` are retained separately. `psi=0` is not used as a universal acceptance predicate.

## Matrix Specification

Let `S_n` be the one-step cyclic shift and:

```text
T_n = S_n^-1 + I_n + S_n
```

With `x` fastest in the flattened vector:

```text
A26 = kron(T_z, kron(T_y, T_x)) - I_(x*y*z)
n   = A26 * x
```

For a cubic `L x L x L` lattice this reduces to:

```text
A26 = kron(T_L, T_L, T_L) - I_(L^3)
```

The dense matrix is a specification oracle only. Production routes use stencils, packing, SIMD, or device kernels and must match the scalar and matrix oracles.

## Typed Channels

For each support value `k`:

```text
B_k  = (1-x) .* 1{n=k}
S_k  = x .* 1{n=k}
O10+ = x .* 1{n>=10}
```

The preserved Q/P-facing order is:

```text
(B5,B6,B7,S5,S6,S7,S8,S9,O10+,psi)
```

The raw next-state bit is many-to-one and never substitutes for typed channel evidence.

## Planar Defect Matrices

For planar defect mask `d`:

```text
A8 = kron(T_y, T_x) - I_(x*y)
A9 = kron(T_y, T_x)
q  = A8 * d
r  = A9 * d
```

`q` counts defects in the open 8-neighborhood. `r` counts defects in the closed 3x3 footprint.

The first-step selector is:

- active sheet site survives iff `q <= 3` and dies iff `q >= 4`;
- in-plane defect site is born iff `1 <= q <= 3`;
- either adjacent normal layer is born iff `2 <= r <= 4`; and
- farther layers remain inactive at the first step.

Normal-layer channel identity is:

```text
r=2 -> B7
r=3 -> B6
r=4 -> B5
```

## Formula Oracles

### Rectangle

For integer `a,b >= 2` under the raw model:

```text
births = 4a + 4b + 12
deaths = 0
(B5,B6,B7) = (12, 4a + 4b - 16, 16)
```

For model tag `PMphi.default.remove_B7`:

```text
births = 4a + 4b - 4
(B5,B6,B7) = (12, 4a + 4b - 16, 0)
```

PMphi is a separate model tag. Rectangle response alone fixes `a+b`; area or another independent measurement is needed to recover unordered side lengths under the rectangle prior.

### Line Hole

For integer length `n >= 1`:

```text
n=1: births=0, deaths=0
n>=2: births=7n, deaths=0, (B5,B6,B7)=(0,7n-14,14)
```

### Solid Cuboid

For integers `a,b,c >= 4`:

```text
A0 = abc
B0 = 8(a+b+c-6)
D0 = abc-8
A1 = 8(a+b+c)-40
```

All births are `B6` in this formula family.

### Closed Shell

For integers `a,b,c >= 4` in the locked family:

```text
A0 = 2(ab+ac+bc) - 4(a+b+c) + 8
B0 = 8(a+b+c-6)
D0 = 8(a+b+c-9)
A1 = 2(ab+ac+bc) - 4(a+b+c) + 32
```

All births are `B6` in this formula family.

Ports, slits, tunnels, walls, and the all-size isolated-pore converse remain outside the closed formula registry.

## Numerical Contract

| Quantity | Reference type | Proven range in this contract |
|---|---|---|
| state | `u8` | 0 or 1 |
| support `n` | `u8` | 0 through 26 |
| capacity | `u8` | 7 or 9 |
| deficit | `u8` | 0 through 5 |
| excess | `u8` | 0 through 19 |
| strain | `i8` | -5 through 19 |
| aggregate counts | `u64` | checked before addition/serialization |

The Python reference rejects shape products above 16,777,216 cells. The dense matrix oracle rejects shapes above 512 cells. These are reference implementation safety bounds, not mathematical size claims.

Every implementation must check shape multiplication, byte-size multiplication, stride calculation, offset addition, and allocation before use.

## Canonical Array Hash

The canonical hash is SHA-256 over:

```text
canonical_ascii_json(header) || 0x00 || payload
```

The header contains sorted compact fields:

```json
{
  "axis_order": "x_fastest_then_y_then_z",
  "byte_order": "little",
  "dtype": "u8|i8|u64",
  "shape": ["extents in contract order"]
}
```

The payload is the fixed-width array in flattened order. Dtype, shape, byte order, and axis order are therefore part of content identity.

## Oracle Independence

`runtime/pdc_reference.py` provides:

1. a scalar periodic stencil that visits coordinate offsets directly; and
2. a dense matrix path built from cyclic `T` matrices and Kronecker products.

Golden vectors require exact equality between these paths. The matrix implementation is bounded and intentionally unsuitable as a production backend.

## Claim Boundary

This contract and its golden vectors are executable verifier evidence for the stated finite cases and definitions. They are not:

- a proof of every manuscript theorem;
- a reproduction of all reported verifier or benchmark rows;
- a physical, quantum, medical, financial, legal, or hardware claim;
- evidence that PooleGlyph Phase 66, a production backend, kernel enforcement, Liquid Glass UI, or bootable ISO is complete.
