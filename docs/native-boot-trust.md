# PBTRUST1 Native Boot Trust Boundary

## Status

PBTRUST1 is a bounded N5 development contract. It defines and independently
validates the shape and ordering of boot trust policy and boot acceptance state.
Its PBSTATE1 sub-contract now models redundant authenticated-state selection,
repair/migration planning, and interrupted-transition recovery. It does not
implement backend cryptography or persistence, establish a real monotonic
anchor, use a private key, grant authority, write state, or make PooleOS
production ready.

The current PooleBoot integration reads `\EFI\POOLEOS\TRUST.PBT` and
`\EFI\POOLEOS\TRUSTST.PBS`, validates every fixed-format and cross-binding gate,
and must stop at `pbtrust_policy_unsigned`. The state file is an ESP candidate
used to exercise parsing and binding. It is never accepted as persistent or
rollback-resistant authority.

## Separated Objects

PBTRUST1 keeps three state classes separate:

1. Immutable boot trust policy (`PBTP1`) names the trusted root/signer sets,
   threshold shape, artifact identities, revocation-set identity, policy epoch,
   and minimum accepted versions.
2. Mutable boot acceptance state (`PBTS1`) records the exact accepted policy,
   manifest, kernel, retained inner set, secure-version floor, policy version,
   generation, store epoch, redundant-copy identity, and previous-state chain.
3. PREC1 boot-attempt and slot-recovery state remains a different contract. A
   successful or failed boot attempt cannot silently rewrite trust policy or
   monotonic acceptance state.

Combining these objects would make recovery counters capable of changing trust
roots or rollback floors. PBTRUST1 rejects that design.

## PBTP1 Policy Record

The policy record is exactly 320 bytes. The authenticated body is bytes 0..223,
its SHA-256 is bytes 224..255, and the bounded signature field is bytes 256..319.
The record binds:

- exact PSM1 manifest SHA-256;
- exact PooleKernel ELF SHA-256;
- domain-separated retained six-artifact set SHA-256;
- exact revocation-set SHA-256;
- the complete seven-role artifact mask;
- policy version, trust epoch, secure-version floor, and state-generation floor;
- root-set and signer-set identifiers, signer count, threshold, and auth profile.

Exactly one policy profile is legal. `development_unsigned` has no signer fields
or signature bytes and always denies. `signed` has a structurally valid bounded
signature field but still requires an external cryptographic verifier. Parsing a
signed shape is not signature verification.

## PBTS1 Acceptance-State Record

The state record is exactly 256 bytes. Bytes 0..223 form its hashed body and
bytes 224..255 contain the body SHA-256. It binds the full policy-file SHA-256,
manifest, kernel, retained set, accepted versions, secure floor, generation,
store epoch, copy index/count, commit marker, authentication profile, and the
previous committed state SHA-256 for every generation after one.

Exactly one state profile is legal:

- `development_candidate` is complete enough to exercise parsing, but has no
  authentication profile and cannot be authority.
- `authenticated_backend` is only a record shape. Acceptance additionally
  requires independently supplied evidence that the record came from an
  authenticated, monotonic, writable backend.

Two-copy metadata and a complete commit marker are mandatory. PBSTATE1 models
selection and produces repair/migration plans, but does not perform writes. A
production backend must still add cryptographic authentication, a monotonic
anchor provider, transactional storage I/O, durability barriers, media-specific
wear/error handling, and hardware-backed fault evidence. An ordinary ESP file
cannot meet that requirement.

## PBSTATE1 Backend Model

PBSTATE1 accepts exactly two physical copy slots plus an externally supplied
anchor and backend-capability record. The anchor must itself be authenticated
and monotonic. It binds the accepted generation, store epoch, authentication
profile, domain-separated logical-state SHA-256, and previous logical-state
SHA-256. Generation and epoch floors are checked before any copy is eligible.

Each present copy is parsed independently. Its physical `copy_index` must match
the slot, its PBTS1 profile must be `authenticated_backend`, and the caller must
provide per-copy authentication evidence. The selector classifies authenticated
copies as stale, future, mismatched, or exactly anchored. It chooses the
lowest-index exact match, requires a writable backend and enough capacity to
repair every non-anchored slot, and returns only metadata. A future copy written
before anchor advancement is never selected; an old copy after anchor
advancement is never selected.

The logical digest normalizes only redundant physical-copy representation and
other already-validated fixed or derived fields. It binds every mutable trust
semantic field, including generation, epoch, authentication profile, rollback
floors, accepted versions, artifact digests, and the previous-state link. This
allows byte-distinct copy zero and copy one records to match one authenticated
anchor without weakening their semantic identity.

The transition planner first revalidates selector-origin copy masks, selected
slot, chain shape, logical identity, migration intent, and zero-effect fields.
It then targets the alternate slot, increments generation with overflow
rejection, and freezes this order:

1. Write the target record as uncommitted.
2. Flush target data.
3. Write the target commit marker and authentication material.
4. Flush the target commit.
5. Advance the monotonic anchor.
6. Verify the advanced anchor.
7. Repair the other copy.
8. Flush the repaired copy.
9. Verify both redundant copies.

The anchor is the commit point. Before it advances, recovery selects the old
anchored generation and treats any new copy as future. After it advances,
recovery selects the new generation and treats the old or torn copy as needing
repair. The nine-case corpus interrupts every meaningful boundary, including a
torn repair before its flush. Every case is checked against independent Rust and
Python selectors and records zero authority grants and zero performed writes.

## Ordered Decision

The validator fails closed in this order:

1. Parse and validate the policy record.
2. Parse and validate the state record.
3. Cross-bind policy to observed manifest, kernel, retained set, revocations,
   and role mask.
4. Cross-bind state to the full policy and the same observed artifact set.
5. Enforce accepted manifest/policy versions, secure-version floors, state
   generation, and trust epoch.
6. Deny an unsigned development policy.
7. Require external policy signature and threshold evidence.
8. Require authenticated revocation evidence and a non-revoked decision.
9. Reject a development state candidate.
10. Require external state authentication, monotonicity, writable-backend, and
    verified Secure Boot state evidence.

Only a caller that supplies every external fact can receive the model's
`AuthorizedTrust` value. The `synthetic_qualified` helper and host-probe evidence
mask exist solely for differential qualification. They do not perform crypto,
query firmware variables, inspect TPM state, or authorize firmware behavior.

## PooleBoot Integration

PooleBoot reads both files after loading and reparsing the exact six retained
PBART1 artifacts. It validates PBTRUST1 against the full PSM1 bytes, full kernel
bytes, retained-set digest, manifest version, and secure-version floor. The only
accepted development outcome is the exact unsigned-policy denial. PooleBoot then
frees both candidate pools, emits one `TRUST_STATE DENY` marker with zero
signatures, authority grants, and state writes, and continues to its permanent
pre-transfer stop.

This is fail-closed parser and binding evidence. Cycle 117 independently
reparses PBTP1 and PBTS1 and reconstructs exact unsigned-policy denial in
host-executed PooleKernel code. The live caller still stops before entry, so
PooleKernel does not consume authenticated state or create capabilities.

## Qualification

`tools/qualify_native_boot_trust.py` runs:

- Rust host tests, rustfmt, clippy, no-std builds for bare-metal and UEFI, and a
  PooleBoot UEFI integration build;
- fixed development, signed-shape, generation-chain, redundant-copy, and
  migration-plan cases;
- four independent 8,192-case Python/Rust differential campaigns covering the
  policy parser, state parser, authorization order, and backend selector;
- malformed, substitution, rollback, future-state, incomplete-copy, chain,
  anchor, repair-capacity, missing-evidence, and transport hostile controls;
- nine deterministic interrupted-transition recovery cases;
- exact implementation, toolchain, and target-profile bindings.

The generated readiness receipt remains `production_ready=false`.

## Production Work Still Open

Production acceptance requires a reviewed signature suite and key hierarchy,
real threshold verification, authenticated revocation state, a monotonic
transactional backend implementation, Secure Boot and TPM policy integration,
executed state migration and repair, PooleKernel independent revalidation,
storage fault injection, target-firmware and physical-hardware qualification,
and signed release evidence. Key generation, signing, firmware mutation, driver
loading, and physical-media writes are outside this slice and require separate
owner authorization.

## Primary References

- UEFI Specification 2.11, Runtime Services and authenticated variables:
  <https://uefi.org/specs/UEFI/2.11/08_Services_Runtime_Services.html>
- The Update Framework Specification:
  <https://theupdateframework.github.io/specification/latest/>
- NIST SP 800-193, Platform Firmware Resiliency Guidelines:
  <https://csrc.nist.gov/pubs/sp/800-193/final>
- TCG TPM 2.0 Library Specification:
  <https://trustedcomputinggroup.org/resource/tpm-library-specification/>
