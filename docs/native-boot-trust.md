# PBTRUST1 Native Boot Trust Boundary

## Status

PBTRUST1 is a bounded N5 development contract. It defines and independently
validates the shape and ordering of boot trust policy and boot acceptance state.
It does not authenticate either object, establish monotonic persistence, use a
private key, grant authority, write state, or make PooleOS production ready.

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

Two-copy metadata and a complete commit marker are mandatory. The current code
does not implement selection, repair, or writing. A production backend must add
transactional copy update, authenticated copy selection, previous-state chain
verification, interrupted-write recovery, wear/error handling, and power-loss
fault evidence. An ordinary ESP file cannot meet that requirement.

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

This is fail-closed parser and binding evidence. PooleKernel does not yet reparse
PBTRUST1, consume it, create capabilities from it, or enter the kernel.

## Qualification

`tools/qualify_native_boot_trust.py` runs:

- Rust host tests, rustfmt, clippy, no-std builds for bare-metal and UEFI, and a
  PooleBoot UEFI integration build;
- fixed development, signed-shape, and generation-chain cases;
- independent Python/Rust parser and authorization differential campaigns;
- malformed, substitution, rollback, incomplete-copy, chain, missing-evidence,
  and transport hostile controls;
- exact implementation, toolchain, and target-profile bindings.

The generated readiness receipt remains `production_ready=false`.

## Production Work Still Open

Production acceptance requires a reviewed signature suite and key hierarchy,
real threshold verification, authenticated revocation state, a monotonic
transactional backend, Secure Boot and TPM policy integration, state migration
and recovery rules, PooleKernel independent revalidation, fault injection,
target-firmware and physical-hardware qualification, and signed release evidence.
Key generation, signing, firmware mutation, driver loading, and physical-media
writes are outside this slice and require separate owner authorization.

## Primary References

- UEFI Specification 2.11, Runtime Services and authenticated variables:
  <https://uefi.org/specs/UEFI/2.11/08_Services_Runtime_Services.html>
- The Update Framework Specification:
  <https://theupdateframework.github.io/specification/latest/>
- NIST SP 800-193, Platform Firmware Resiliency Guidelines:
  <https://csrc.nist.gov/pubs/sp/800/193/final>
- TCG TPM 2.0 Library Specification:
  <https://trustedcomputinggroup.org/resource/tpm-library-specification/>
