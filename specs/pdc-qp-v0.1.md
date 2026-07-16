# PDC-QP-0.1 Typed Q/P and Probability Contract

Status: frozen reference contract for Cycle 78  
Machine contract: `runs/pdc_qp_contract.json`  
Verification receipt: `runs/pdc_qp_receipt.json`  
Reference runtime: `runtime/pdc_qp.py`

## Scope

`PDC-QP-0.1` freezes the typed local PooleQ/P feature, independent Bernoulli probability layer, local correlation residue, first-update defect-footprint logic, and geometry-score definitions used by PooleOS. It is a classical transform on already measured binary fields or declared probabilities. It is not an unknown-state reconstruction or cloning interface.

The contract covers:

- the ordered feature vector `(B5,B6,B7,S5,S6,S7,S8,S9,O10+,psi)`;
- all 54 binary `(center state, neighbor support)` pairs;
- exactly 26 independently modeled Moore-neighbor probabilities;
- Poisson-binomial coefficients, activation probability, and center/neighbor derivatives;
- first-update sheet-footprint cardinality, raw gates, and typed adder readouts;
- empirical channel residues, Poole coherence, robust score groups, geometry signature, and normalized non-null spectrum; and
- fail-closed numerical, shape, footprint, normalization, source-binding, and null-signal behavior.

It does not freeze routing, fanout, timing, reset, gate isolation, channel demultiplexing, a dynamic Q/P update model, PooleGlyph lowering, native ABI, kernel enforcement, or hardware execution.

## Authorities

Formula and claim precedence is bound through `runs/pdc_source_intake.json` to:

1. `SRC-LG-1`, *The Poole Local-Geometry Program*.
2. `SRC-MAG-1`, *Poole Local Geometry Magnum Opus v1.4*.

The 42 published typed cases are imported read-only from the content-addressed v1.7.1 ancillary archive selected by `runs/pdc_verifier_intake.json`. The receipt verifies each embedded member SHA-256 and independently recomputes every row without accepting its existing `match` column as proof.

## Typed Feature

For center state `x_i` and support `N_i`:

```text
B_k   = (1 - x_i) * 1{N_i = k}, k in {5,6,7}
S_k   = x_i * 1{N_i = k},       k in {5,6,7,8,9}
O10+  = x_i * 1{N_i >= 10}
psi   = max(0, N_i - (7 + 2*x_i)) - max(0, 5 - N_i)
```

`PDC.QP.Feature.v0.1` preserves those channels. `PDC.CollapsedState.v0.1` contains only the accepted next bit:

```text
P(x)_i = OR(B5,B6,B7,S5,S6,S7,S8,S9)
```

The two types are not interchangeable. A collapsed bit cannot identify whether a birth occurred in `B5`, `B6`, or `B7`.

## Probability Layer

The center is excluded from the neighbor count. For neighbor probabilities in their caller-provided Moore order:

```text
G_i(z) = product_j (1 - p_j + p_j*z)
Pr[N_i = k] = [z^k]G_i(z)
```

The production reference recurrence is:

```text
F_0(0) = 1
F_(m+1)(k) = (1 - p_jm)*F_m(k) + p_jm*F_m(k-1)
```

After 26 factors:

```text
C_i^(a:b) = sum(k=a..b) F_26(k)
q_i = C_i^(5:7) + p_i*C_i^(8:9)
dq_i/dp_i = C_i^(8:9)
```

For neighbor `l`:

```text
d[z^k]G_i/dp_l = [z^k](z - 1) product_(j != l)(1 - p_j + p_j*z)
```

The receipt compares the fixed-order in-place DP with balanced polynomial convolution on full 26-neighbor cases, brute-force outcome enumeration on bounded small cases, an independently formed leave-one-out derivative polynomial, and central finite differences on interior points.

## Floating Point

- Format: IEEE-754 binary64.
- Inputs: finite and within `[0,1]`; booleans are rejected as probabilities.
- Neighbor cardinality: exactly 26 for `probability_layer`.
- DP ordering: factors left to right, coefficients descending in place.
- Independent polynomial ordering: balanced recursive factor convolution.
- Normalization: `math.fsum`, absolute and relative tolerance `5e-13`.
- Outputs are not silently clipped.
- Nonfinite, out-of-range, wrong-cardinality, or non-normalized values fail closed.

## Footprint Readouts

For an inactive normal-layer candidate adjacent to a stable sheet on the first update:

```text
r = bias + sum(input defects)
N = 9 - r
B7 <=> r = 2
B6 <=> r = 3
B5 <=> r = 4
raw birth = 1{2 <= r <= 4}
```

With two inputs, biases `0,1,3,4` implement collapsed `AND`, `OR`, `NAND`, and `NOR`. Bias `1` implements one-input identity; bias `4` implements one-input NOT.

Typed arithmetic uses one fixed bias defect:

```text
half-adder: SUM = B7, CARRY = B6
full-adder: SUM = B7 OR B5, CARRY = B6 OR B5
```

The full-adder collapsed bit is only `A OR B OR Cin`. Therefore typed arithmetic cannot be exposed through a one-bit state API.

## Correlation And Spectrum

Empirical rates and local product-model predictions define:

```text
Delta_i = qhat_i - q_i^ind
R_i = (B5hat-EindB5, B6hat-EindB6, B7hat-EindB7,
       S8hat-EindS8, S9hat-EindS9)
C_P = sum_i ||R_i||_2^2
```

For channel set `K`:

```text
R_K = sqrt(sum_k asinh(((mu_hat_k - mu0_k)/(sigma0_k + epsilon))/lambda)^2)
```

The default groups are:

- `K_B = {B5,B6,B7}`
- `K_H = {S8,S9,O10+}`
- `K_psi = {psi_abs}`
- `K_C = K_B union K_H union K_psi`

The signature is `S_P=(R_B,R_H,R_psi)`. For non-null `R_C >= 2`, the spectrum is:

```text
Sigma_P = (R_B^2,R_H^2,R_psi^2)/(R_B^2+R_H^2+R_psi^2+epsilon)
```

The API rejects share interpretation for null-like signals. The collapsed update rate is excluded from `K_C` because it overlaps the typed channels.

## Evidence Boundary

The Cycle 78 receipt proves exact source binding, 54 feature threshold checks, DP/polynomial/brute-force agreement, analytic derivative agreement, finite-difference checks, normalization, 42 imported typed cases, residue/coherence identities, robust-score decomposition, and malformed-input rejection within this declared reference scope.

It does not reproduce the v5.5 field benchmark, prove perturbation stability, expose Q/P through PooleGlyph/PGB2, or establish autonomous logic, kernel, hardware, quantum, or production-ISO behavior.
