# PFWM1 native firmware manifest

Status: bounded N5 development evidence; synthetic and never applicable to
hardware.

PFWM1 v1 defines a fixed, allocation-free representation of normalized
firmware inventory and update intent. It closes only the manifest semantics,
dependency planning, prerequisite gating, and post-reset receipt slice of
`N5-FIRMWARE-SEMANTICS-001`. It does not implement an updater.

## Claim boundary

The canonical manifest contains three synthetic component records and two
synthetic dependency records. It contains no firmware payload bytes. The
payload fields are declared external byte counts and identity digests used to
exercise bounded parsing and policy checks.

The following operations are absent and prohibited in this slice:

- live UEFI Firmware Management Protocol discovery or method calls;
- live ESRT discovery or variable reads;
- capsule parsing, staging, submission, cancellation, or reset scheduling;
- PLDM endpoint discovery, component transfer, activation, or reset;
- loading or invoking a device updater driver or plugin;
- detaching storage, quiescing a real device, or changing power policy;
- validating a production vendor payload or signature;
- firmware, embedded-controller, option-ROM, or device mutation;
- physical-media or disk writes;
- creation of production update authority.

`parse()` proves only structural conformance. `authorize_dry_run_plan()` is a
pure qualification function and requires `qualification_only=true`, no live
firmware-call request, no driver-load request, no media-write request, and no
firmware-mutation request. The canonical PBART1 development artifact fails
first at `pfwm_activation_outer_signature`.

## Binary format

All integers are little-endian. The manifest consists of one 512-byte header,
a contiguous fixed-size component table, and a contiguous fixed-size
dependency table. Trailing data is forbidden.

| Region | Size | Purpose |
| --- | ---: | --- |
| header | 512 bytes | profile, limits, policy identities, table layout, body digest |
| component | 256 bytes each | exact target, versions, transport, external payload and trust identities |
| dependency | 16 bytes each | source component, required component, required target version |

The header binds:

- the synthetic qualification profile and manifest version;
- exact component and dependency counts and offsets;
- one-component-at-a-time transaction policy;
- battery, retry, apply-timeout, and reset-timeout limits;
- target profile, normalized inventory schema, package policy, license
  manifest, revocation state, recovery profile, updater allowlist, trust policy,
  and receipt schema SHA-256 identities;
- the SHA-256 digest of both fixed tables;
- a canonical ASCII manifest identifier.

Every component binds:

- a unique nonzero component identifier;
- a supported component kind and non-generic transport;
- a deterministic topological phase and exact dependency range;
- all mandatory safety and recovery flags;
- a nonzero 16-byte resource GUID and nonzero hardware instance;
- current, target, lowest-supported, rollback-floor, and known-good versions;
- an external payload byte limit and SHA-256 identity;
- exact device, vendor signer, updater plugin, and recovery identities.

The hardware instance is signed by the outer manifest identity. This closes a
specific target-substitution gap: the UEFI FMP capsule image header's hardware
instance is not necessarily part of the authenticated image data, so PFWM1
does not rely on that field alone.

## Structural invariants

The parser rejects:

- unknown versions, profiles, flags, kinds, transports, or record sizes;
- zero, duplicate, wildcard, or reordered component identities;
- duplicate `(resource GUID, hardware instance)` pairs;
- non-contiguous tables, arithmetic overflow, trailing bytes, or stale body
  digests;
- zero policy or component digests;
- version relations outside
  `lowest <= rollback floor <= known good <= current < target`;
- missing, orphaned, duplicated, unordered, or forward dependencies;
- dependency minimum versions that differ from the required component target;
- phase gaps or dependency cycles;
- more than one component in an active transaction;
- a per-component payload declaration above the manifest or contract bound.

Dependency records require a strictly earlier phase. Component records are
ordered by `(phase, component_id)`, and every phase from zero through the
maximum is represented. That gives the native parser a bounded topological
order without heap allocation or recursive graph traversal.

## Dry-run prerequisites

A dry-run plan is returned only when all of the following evidence is supplied
to the pure oracle:

- outer, manifest, package, and vendor signatures verified by future trusted
  implementations;
- exact PBART1 role, inner version, payload digest, and outer file digest;
- authenticated target profile and complete hardware inventory;
- exact device identities and current versions;
- supported transport and firmware-service inventory;
- allowlisted updater plugin and separately granted plugin authority;
- all external payloads present and digest-verified;
- license and redistribution policy satisfied;
- authenticated, current revocation and anti-rollback state;
- ready recovery path and verified backup;
- protected staging with sufficient capacity;
- stable AC power and the declared battery floor;
- durable single-component transaction journal;
- quiescence, storage, suspend, and shutdown guards;
- separate reset, reboot, user-confirmation, physical-presence, and firmware
  change authorization;
- post-reset verifier and durable receipt storage.

Transport security alone is insufficient. Manifest, package, vendor signer,
revocation, target identity, and payload digest evidence are independently
required.

## Transaction and recovery model

PFWM1 permits only one active component per transaction. Components are
processed in the normalized topological order. A failed component halts all
later phases. A future executor must durably record at least staged, committed,
reset-pending, verified, failed, and recovered states and must prevent a failed
capsule or plugin operation from becoming a reboot loop.

Cancellation is meaningful only before commit. A future executor must never
interrupt an update after the platform or device reports commit. Power-loss
testing remains restricted to separately authorized sacrificial hardware.

PFWM1 requires a vendor recovery identity for every component. A future
production profile must additionally prove the exact board and device recovery
procedures, recovery media, rollback state, and power prerequisites before any
updater is enabled.

## Post-reset verification

The normalized post-reset receipt must bind every component in manifest order
and prove:

- the same resource GUID and hardware instance;
- observed and last-attempt versions equal the target version;
- a success last-attempt status;
- successful re-enumeration and self-test;
- intact recovery capability;
- durable receipt, committed state, and reboot-loop prevention;
- driver rebinding only after all prior checks pass.

The current implementation verifies synthetic records only. It does not read
ESRT variables, FMP descriptors, device registers, or production receipts.

## Canonical qualification profile

The canonical profile uses synthetic identities for:

1. platform firmware over a normalized UEFI capsule/ESRT transport;
2. controller firmware over an exact updater-plugin transport;
3. device firmware over a normalized PLDM transport.

The controller depends on the platform target version, and the device depends
on the controller target version. These are test identities, not vendor image
identifiers or claims about current Tier-1 hardware firmware.

`specs/native-firmware-golden-vectors.json` contains canonical, minimal, and
maximum-component valid vectors. `tools/qualify_native_firmware.py` compares
the independent Python and `no_std` Rust implementations across golden,
hostile, parser differential, prerequisite differential, and post-reset
differential cases. The readiness report is
`runs/native_firmware_readiness.json`.

Cycle 114 PooleBoot reparses the exact retained PFWM1 bytes and requires the
development gate to fail at `pfwm_activation_outer_signature`. It performs no
live inventory, loads no updater, authorizes no transaction, writes no state,
and submits no capsule. PooleKernel revalidation and all device-changing work
remain open.

## Primary references

- UEFI 2.11, Chapter 23, Firmware Update and Reporting:
  https://uefi.org/specs/UEFI/2.11/23_Firmware_Update_and_Reporting.html
- NIST SP 800-193, Platform Firmware Resiliency Guidelines:
  https://csrc.nist.gov/pubs/sp/800/193/final
- DMTF DSP0267 1.3.0, PLDM for Firmware Update:
  https://www.dmtf.org/sites/default/files/standards/documents/DSP0267_1.3.0.pdf
- TCG PC Client Reference Integrity Manifest specification:
  https://trustedcomputinggroup.org/resource/tcg-pc-client-reference-integrity-manifest-specification/

These references inform the normalized fields and failure policy. Compliance
with any complete external specification is not claimed by this bounded slice.
