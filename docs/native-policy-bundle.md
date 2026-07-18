# PPOL1 Native Policy Bundle

## Status and scope

PPOL1 version 1 is the deterministic policy semantics contract for PBART1 role 7. This slice freezes a bounded binary format, independent Python and allocation-free Rust validators, PINIT1 capability-route cross-binding, six boot-mode ceilings, dry-run authorization decisions, and durable receipt validation.

PPOL1 is qualification-only. Parsing a bundle, validating its bindings, producing a decision, or verifying a receipt creates no authority and performs no boot, kernel, firmware, driver, storage, network, PDC, PooleGlyph, or physical-media operation.

## Authority equation

The effective authority represented by a dry-run decision is:

```text
built-in ceiling
  AND signed PPOL1 ceiling
  AND selected-mode ceiling
  AND already-issued capability
  AND current request
```

Every term is an intersection. PPOL1 has no union, wildcard, implicit route, ambient authority, or parser-created authority operation. A child capability must be a subset of its parent in rights, flags, modes, and effects.

## Binary layout

All integers are little-endian. Tables are contiguous and trailing bytes are rejected.

| Region | Size | Purpose |
| --- | ---: | --- |
| Header | 512 bytes | Version, flags, limits, ten SHA-256 identities, body digest, policy ID |
| Mode table | 6 x 128 bytes | Exact normal, safe, previous, recovery, diagnostic, and firmware ceilings |
| Capability table | 1-256 x 64 bytes | Complete PINIT1 route declarations and attenuation ceilings |

The header binds the Tier-1 target profile; canonical PINIT1, PREC1, PSYM1, PMCU1, and PFWM1 payloads; trust policy; authenticated revocation and rollback schemas; and durable audit schema. The policy does not bind PSM1 because PSM1 already binds the outer `POLICY.PBA`, avoiding a circular digest dependency.

## Mode semantics

`normal` permits the broadest modeled non-firmware development effects, but still denies PDC actuation, firmware mutation, DMA, secret access, and update authority.

`safe` is constrained by a compiled-in ceiling. External policy cannot add persistent writes, network, debug, PDC, update, firmware, DMA, secret, or power effects.

`previous` models an authenticated rollback selection. It remains PDC-disabled and cannot perform firmware or update effects.

`recovery` has no PINIT1 capability routes. It is explicitly independent of normal services, PooleGlyph, PDC, and network service and is constrained by a compiled-in recovery ceiling.

`diagnostic` permits bounded debug effects while denying persistence, network, PDC, update, firmware, DMA, secret, and power effects.

`firmware` has no PINIT1 capability routes and requires both physical presence and separate authority evidence. In this slice it can only produce a qualification-only plan; live firmware calls, updater drivers, mutation, and media writes are unconditionally rejected.

## PINIT1 cross-binding

The canonical PPOL1 capability table has one rule for each of the 11 canonical PINIT1 capabilities. Validation compares capability ID, parent, holder service, resource, declared rights, declared flags, revoke group, availability, derivation limit, and resource generation. It then proves that policy rights and flags are subsets and that resource-kind effects match the frozen mapping.

The policy route set is complete and exact. Missing, duplicate, reordered, substituted, widened, or parent-amplified routes fail closed.

## Activation prerequisites

Activation qualification requires the outer PBART1 role, version, payload digest, file digest, and signature; policy, manifest, and artifact signatures; target profile; exact role 2-6 digests; authenticated trust, revocation, and rollback state; audit schema; all inner contracts; PINIT1 cross-binding; kernel ABI and PBP compatibility; mode and transition authority; capability allocator; resource broker; audit sink; and receipt store.

Firmware mode additionally requires physical presence and separate authority. Capability decisions additionally require a current, non-revoked generation and requested rights/effects contained by every ceiling.

The checked-in development context intentionally fails first at `ppol_activation_outer_signature` because no approved key or signature exists.

## Receipts

A dry-run decision receipt binds the policy digest, mode, capability, effective rights, effective effects, mode generation, capability generation, authenticated revocation epoch, and audit sequence. The decision ID is SHA-256 over those canonical fields. Zero epochs, zero sequence numbers, non-durable storage, substitutions, and non-qualification receipts fail closed.

## PooleGlyph boundary

PooleGlyph remains data-only and non-authoritative in PPOL1. The live source audit still reports its Core IR promotion boundary as pending. No PooleGlyph output, checkpoint, matrix, or model result is converted into executable policy, a capability, a boot decision, or kernel authority by this contract.

## Non-claims and deferred work

- No signatures or private keys are generated or used.
- No live revocation, rollback, physical-presence, or persistent audit source is implemented.
- No PooleBoot or PooleKernel interpreter enforces PPOL1 yet.
- No capability allocator, resource broker, policy daemon, or mode-transition engine exists yet.
- No live execution, state write, firmware call, driver load, or media write occurs.
- No production-readiness claim is made.

## Primary references

- seL4 capDL language specification: <https://docs.sel4.systems/projects/capdl/lang-spec.html>
- Fuchsia capability routing: <https://fuchsia.dev/fuchsia-src/concepts/components/v2/capabilities>
- Fuchsia component lifecycle: <https://fuchsia.dev/fuchsia-src/concepts/components/v2/lifecycle>
- UEFI 2.11 Boot Manager: <https://uefi.org/specs/UEFI/2.11/03_Boot_Manager.html>
- The Update Framework 1.0.35: <https://theupdateframework.github.io/specification/v1.0.35/>
- NIST SP 800-193: <https://csrc.nist.gov/pubs/sp/800/193/final>
- NIST SP 800-207: <https://csrc.nist.gov/pubs/sp/800/207/final>
