# PREC1 Recovery Policy and State

## Status

`PREC1` is the candidate, pre-ABI recovery-policy format carried inside the
`recovery` role of a `PBART1` artifact. Cycle 109 freezes the bounded bytes and
pure state transitions so later PooleBoot and PooleKernel work has one
independently testable contract.

This work is non-promoting. The repository has no recovery executable, trusted
signatures, authenticated persistent state store, UEFI variable transport,
PooleKernel recovery service, installer, or physical-media result.

## Architecture Boundary

Recovery has two deliberately separate objects:

1. An immutable, exactly 992-byte policy bundle describes eligible slots,
   failure routing, activation requirements, and recovery authority
   requirements.
2. An exactly 128-byte mutable record describes attempts, known-good state,
   pending state, requests, the current in-flight boot, and receipt bindings.

The mutable record's truncated SHA-256 checksum detects accidental corruption.
It is not authentication, anti-rollback storage, a signature, or authority.
Any production transport must authenticate the entire record and enforce a
monotonic generation outside `PREC1`.

Parsing either object confers no capability. Authority rows are requirements a
future recovery service must satisfy before requesting narrow kernel-mediated
operations.

## Immutable Policy Layout

All integers are little-endian. The policy is exactly 992 bytes and has no
trailing data.

| Region | Offset | Bytes | Count |
| --- | ---: | ---: | ---: |
| Header | 0 | 256 | 1 |
| Slot records | 256 | 96 | 2 |
| Failure records | 448 | 32 | 10 |
| Authority records | 768 | 32 | 7 |

The header binds:

- `PREC1` magic and version 1.0;
- exact table geometry and a SHA-256 digest of bytes 256 through 991;
- bundle and minimum-secure versions;
- required PBP1 and PooleKernel ABI versions;
- maximum trial attempts, one safe attempt per slot, and a health deadline;
- authenticated-state, decrement-before-handoff, known-good fallback,
  fail-closed, signature, version-floor, offline, PDC-disabled,
  PooleGlyph-independent, display-path, evidence, and physical-presence rules;
- a future recovery-component digest and abstract state-store identifier;
- exact fallback actions, required handoff fields, authority ceiling, and
  serial plus GOP/software display requirements.

Reserved bytes must be zero. Unknown flags, reordered tables, substituted
counts, duplicate slot digests, and noncanonical policy rows fail closed.

## Slot Rules

Exactly two slots exist. Each slot binds a manifest digest, kernel digest,
version, minimum recovery version, priority, and eligibility flags. The two
manifest digests and two kernel digests must be nonzero and distinct.

A pending candidate is eligible only when it is bootable, not marked
unbootable, at or above both secure-version floors, and has an attempt
remaining. The transition decrements its attempt count and creates the
in-flight receipt binding before handoff. A caller must durably persist that
new authenticated state before transferring control.

The current known-good slot is never replaced by candidate selection. A
candidate becomes known-good only after an authenticated success receipt
matches generation, slot, mode, and nonce. Exhausted or policy-invalid
candidates are retired before previous-known-good selection.

## Failure Rules

The ten ordered failures are:

1. configuration invalid;
2. mutable state invalid;
3. signature invalid;
4. version rollback;
5. artifact integrity failure;
6. kernel entry failure;
7. initial health deadline exceeded;
8. attempt budget exhausted;
9. known-good runtime failure;
10. operator recovery request.

The six actions are retry candidate, safe mode, previous known-good, recovery,
firmware setup, and halt. Every rule preserves evidence. Signature, rollback,
and artifact failures retire the affected candidate. A retry with no remaining
attempts becomes the rule's fallback. A repeated safe attempt becomes recovery.
Previous selection requires another eligible known-good slot; otherwise it
becomes recovery.

State write failure never permits a normal handoff. The pure model returns a
recovery decision with `persistence_required=false`, recording that a future
transport must enter recovery without treating unpersisted attempt state as a
boot authorization.

## Boot Entry Selection

The modeled entries are normal, PDC-disabled safe, previous known-good,
recovery, diagnostic, and firmware setup. Authenticated recovery and safe
requests override a caller's normal request. Firmware setup requires physical
presence. Recovery and firmware entries carry no OS slot.

Each slot handoff records the selected slot and mode, boot nonce, state
generation, policy version, and previous failure. An in-flight state cannot be
selected again. This mirrors the UEFI principle of consuming one-shot state
before transfer and A/B systems that decrement retry state before attempting a
candidate.

## Success and Failure Receipts

A success receipt must be externally authenticated and exactly match the
in-flight generation, slot, mode, and nonce. A matching candidate success:

- makes the slot active and known-good;
- clears pending and unbootable state for that slot;
- replenishes its attempt budget;
- clears the in-flight binding and requests;
- advances generation and evidence sequence.

A failure receipt must also be authenticated. It applies the exact policy row,
retires candidates where required, bounds retry and safe loops, clears the
in-flight binding, records the failure and next mode, and advances generation.

No clock, signature primitive, persistent store, or firmware service is hidden
inside these pure functions.

## Recovery Authority

Seven declarative operations are ordered: inspect, export evidence, select a
fallback, request reboot, unlock an encrypted volume, repair, and reinstall.

All operations are offline and audited. Inspect and evidence export are
read-only. Repair and reinstall are destructive and require physical presence,
operator authentication, a verified backup, and verified signatures. No row
grants ambient firmware, raw-disk, or network access. A future kernel service
must mediate narrower capabilities and preserve the evidence trail.

## Activation Gate

Synthetic activation succeeds only when all of these inputs are true:

- outer role, outer version, payload digest, and file digest match;
- outer, inner, and manifest signatures verify;
- mutable state is authenticated and its generation is monotonic;
- the version floor is durably persisted;
- manifests and recovery components verify;
- PBP1 and PooleKernel ABI versions match;
- the execution path is offline, PDC-disabled, and independent of PooleGlyph;
- serial or GOP/software rendering is available;
- transaction capacity, evidence preservation, rollback, and writable
  authenticated state are available.

The current unsigned development context fails this gate. The synthetic
all-true context is a test vector and is not trust evidence.

## Research Basis

The policy uses primary specifications and project documentation:

- UEFI 2.11 Boot Manager behavior for `BootNext`, OS recovery, platform
  recovery, authenticated recovery order, and security-policy rejection;
- Android A/B slot state and post-reboot successful marking;
- Android's boot-control HAL contract;
- The Update Framework rollback, freeze, threshold, and trusted-metadata rules;
- ChromiumOS try counters, successful flags, priority, read-only current root,
  and fallback partition behavior.

These sources inform the candidate design. They do not certify PooleOS.

## Qualification Boundary

The Python reference model and Rust `no_std` implementation must agree on three
golden policy/state/transition vectors, 144 named controls, 16,384 malformed
parser/state cases, and 8,192 generated transitions. Rust must pass three host
tests and compile allocation-free for `x86_64-unknown-uefi` and
`x86_64-unknown-none`.

The host probe is an ephemeral qualification transport. Its binary identity and
the differential corpus are not public production artifacts.

## Explicit Nonclaims

- `PREC1` is not ratified or stable.
- PooleBoot does not parse or enforce `PREC1`.
- PooleKernel does not consume state, grant authority, or execute recovery.
- The checksum is not authentication.
- No UEFI variable has been defined, read, or written by this implementation.
- No firmware setting, driver, key, signature, disk, or physical medium was
  modified.
- No repair, reinstall, rollback, or recovery UI executes.
- N5 and production readiness remain open.
