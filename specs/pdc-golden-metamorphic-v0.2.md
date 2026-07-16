# PDC-GOLDEN-0.2 Boundary and Metamorphic Corpus

Status: published finite verifier contract  
Math dependency: `PDC-MATH-0.1`  
Representation dependency: `PDC-REP-0.1`  
Predecessor: additive to, and does not replace, `PDC-GOLDEN-0.1`

## Scope

`PDC-GOLDEN-0.2` publishes the boundary and transformation cases required by P1.6 for the supported periodic 3D `B5-7/S5-9` model. It binds every record to shape, x-fastest axes, dtype, model tag, boundary tag, and canonical logical hashes.

The corpus contains:

- all 54 `(state, support)` pairs for states `0,1` and support `0..26`;
- eight explicit empty, full, singleton, minimum-extent, face/edge/corner wrap, byte-aligned, and bit-padding fixtures;
- 32 periodic translation relations;
- 40 joint shape/coordinate axis-permutation relations; and
- six explicit non-relations or contract exclusions.

The expected local measurement is:

```text
capacity = 7 + 2*state
deficit  = max(5 - support, 0)
excess   = max(support - capacity, 0)
strain   = excess - deficit
accepted = 5 <= support <= capacity
```

Inactive channels are `B0..B26`. Active channels are `S0..S9`, then `O10+`. Strain remains a diagnostic quantity and is not substituted for the acceptance predicate.

## Declared Relations

For a periodic translation `T` and a joint axis/shape permutation `Pi`, the corpus requires:

```text
A26(T x)  = T(A26 x)
P(T x)    = T(P x)
A26(Pi x) = Pi(A26 x)
P(Pi x)   = Pi(P x)
```

The receipt evaluates both sides through the independent direct stencil, the frozen scalar stencil, the dense Kronecker matrix, and exact round trips through dense, sparse, bit-packed, probability, and native-snapshot representations. A relation binds transformed hashes; it does not claim that untranslated storage hashes are equal.

## Non-Relations

The corpus deliberately records boundaries that must not be inferred:

- binary complement is not a symmetry of the hysteretic update;
- identical bytes under a different shape are not the same lattice;
- `PMphi` is a distinct model transform, not a storage conversion;
- periodic translation evidence does not apply to nonperiodic boundaries;
- 2D storage support does not imply 3D `A26` execution; and
- fractional probability values are not exact binary states.

Finite counterexamples are used where an executable witness exists. Contract exclusions are used where the operation is deliberately outside the supported ABI. Neither kind is represented as a theorem about a different model.

## Failure Boundary

The receipt fails on a changed source binding, record digest, cardinality, expected hash, scalar/matrix/direct disagreement, representation round-trip mismatch, malformed transform, noncanonical padding, unsupported model tag, unsupported boundary, or any failed negative check.

## Claim Boundary

This corpus closes the published periodic boundary/metamorphic evidence gap for P1.6. It is finite verifier evidence, not an all-size proof, production C ABI, backend performance result, kernel-enforcement result, Liquid Glass validation, ISO evidence, or physical claim.
