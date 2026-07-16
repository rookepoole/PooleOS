# PDC-QP-STABILITY-0.1

Status: frozen finite benchmark protocol  
Parent: `PDC-QP-0.1`  
Scope: PooleQ/P v5.4 field generator, v5.5 decomposed-score corpus, and controlled exact-density perturbations

## Source Authority

The contract binds two immutable packages:

1. The v5.4 paper-locked verification runner supplies the synthetic field generators, exact-density adjustment, shuffled-control construction, periodic channel map, and null calibration procedure.
2. The amended v5.5 package supplies the decomposed score formulas and all 550 published per-sample channel/score rows.

The locked package and member hashes in `runs/pdc_qp_stability_contract.json` are normative. Existing report booleans are comparison targets, not proof; PooleOS regenerates every field and recomputes every accepted result.

## Benchmark Protocol

- Shape: `28 x 28 x 28`, periodic boundaries.
- Target density: `p=0.06`, represented by exactly 1,317 active voxels.
- Samples: 50 per raw class.
- Seed: 23 with NumPy `default_rng` source-compatible generation.
- Raw classes: IID null, straight lines, random-walk chains, branching chains, compact bursts, and sheets.
- Controls: one exact-active-count shuffled field for every structured field.
- Channels: `B5,B6,B7,S5,S6,S7,S8,S9,O10+,psi_mean,psi_abs,active,poole_active`.
- Combined score channels: `B5,B6,B7,S8,S9,O10+,psi_abs`; `poole_active` is reported but excluded as redundant.
- Null calibration: the 50 IID fields only, with the v5.4 finite-size standard-deviation floor.
- Robust transform: `asinh(z/5)` with binary64 epsilon `1e-12` in the standardization denominator.
- Null-like boundary: `R_C < 2`.

Every fresh field must agree with both an explicit-roll 26-neighbor stencil and an independent modular-index stencil. Every published channel value must reproduce exactly; scores and summaries must agree within the binary64 tolerances in the contract.

## Controlled Perturbations

Every one of the 550 regenerated fields is tested at 1, 4, 16, and 64 swaps. One swap turns one active voxel off and one inactive voxel on, so active count is unchanged and Hamming distance is exactly twice the swap count. Index selection is deterministic from the SHA-256-derived seed specified in the contract.

For Hamming fraction `h`, the finite empirical gates are:

```text
structured absolute R_C drift <= 0.06 + 125 h
control absolute R_C drift    <= 0.08 + 125 h
structured relative R_C drift <= 0.01 + 25 h
structured spectrum L1 drift  <= 0.03 + 50 h
```

Structured rows must remain non-null and controls must remain null-like. Dominant-label retention is recorded but is not a gate because near-tied spectrum components can exchange order while their shares remain close.

## Claim Boundary

This protocol establishes deterministic finite evidence for the named synthetic corpus and perturbation levels. The envelopes are acceptance criteria, not universal stability constants or an all-field theorem. Same-density controls isolate local geometry from active-count changes only within this experiment. Q/P remains a classical transform on measured or simulated binary fields and does not reconstruct unknown quantum state. No decoder, hardware, native-backend, kernel, safety, physical, or production-ISO claim follows.
