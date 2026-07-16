# PooleOS Bounded Native Models

Status: Cycle 89 pre-production evidence
Date: 2026-07-16
Selected move: `N4-MODEL-001`
Contract: `POOLEOS-N4-MODELS-1`

## Scope

This cycle adds the first executable state-model slice required by N4.5-N4.6 and `ADD-ASSURE-001`. It uses the TLC explicit-state model checker to exhaust every reachable state within two small frozen configurations and to demonstrate that two deliberate unsafe mutations produce the required counterexample traces.

This is bounded model checking, not a formal proof of PooleOS or its future implementation. The models do not execute PooleBoot, PooleKernel, firmware, drivers, storage, or hardware.

## Frozen Toolchain

`specs/native-model-toolchain-lock.json` freezes:

- latest stable TLA+ release `v1.7.4`, source commit `5a47802b5c391f59ecdd44117981f4ff8c0656ba`;
- `tla2tools.jar` at 2,274,532 bytes, published SHA-1 `BEE4A54F3EE3D4AFC347C3240EC2D9E93B075104`, and locally strengthened SHA-256 `936A262061C914694DFD669A543BE24573C45D5AA0FF20A8B96B23D01E050E88`;
- Eclipse Temurin JRE `jdk-21.0.11+10`, official package SHA-256 `BE26677AAA20B39A62EDCAAB4C8857A8B76673B0F45ABC0B6143B142B62717E4`;
- the 315-file, 151,530,953-byte extracted JRE closure at tree SHA-256 `057E582B6FAC90535C1A51A66856C7D7DCCE27B03536FA0FB019A7C7ADA56DC9`;
- single-worker breadth-first TLC, fingerprint polynomial 0, tool-message output, UTF-8, and two exact repeats per run.

The rolling TLA+ `v1.8.0` prerelease is explicitly rejected as a silent substitute. The `v1.7.4` tag commit is unsigned and its release has no detached JAR signature. Temurin publishes a detached package signature, but no pinned OpenPGP verifier/signer-key ceremony is qualified locally. Source builds, second-host reproduction, SBOM, vulnerability, license-completeness, and redistribution reviews remain open.

Primary references:

- TLA+ command-line tools and license: `https://github.com/tlaplus/tlaplus`;
- stable release and published checksum: `https://github.com/tlaplus/tlaplus/releases/tag/v1.7.4`;
- TLC current-tool behavior and limitations: `https://github.com/tlaplus/tlaplus/blob/master/general/docs/current-tools.md`;
- Temurin release selection: `https://adoptium.net/temurin/releases/`.

## Reproduction

The bootstrap is workspace-local and does not install software globally or mutate `PATH`:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\bootstrap_native_models.ps1
python .\tools\qualify_native_models.py
python -m unittest tests.test_native_models
```

Raw TLC output and metadata stay under ignored `.toolchains/native-models/evidence/`. The public readiness ledger contains only relative source bindings, deterministic counts, normalized counterexample states, and hashes.

## Executed Models

| Model | Frozen finite bounds | Safe result | Required hostile result |
| --- | --- | --- | --- |
| `PooleBootSlots` | Two slots; two trial attempts; atomic stage/trial/success/failure/discard transitions | 46 generated, 20 distinct, queue drained, depth 7 | `UnsafeRollback=TRUE` violates `Recoverable`; 14 generated, 8 distinct, depth 4; trace `Init -> Stage -> StartTrial -> TrialFailure` |
| `PooleCapabilities` | Three capability IDs; two principals; two rights; one object; no ID reuse | 7,963 generated, 1,316 distinct, queue drained, depth 6 | `UnsafeLocalRevoke=TRUE` violates `NoLiveDescendantOfRevoked`; 36 generated, 31 distinct, depth 3; trace `Init -> Derive -> Revoke` |

Both safe and hostile cases execute twice. All four normalized results match exactly. A hostile TLC exit code is accepted only when the exact named invariant, state counts, depth, and normalized trace length match the contract.

## Safety Properties

The boot-slot model checks type closure, nonempty known-good recovery state, known-good active state outside trials, an available fallback during trials, candidate/phase consistency, and bounded attempts.

The capability model checks type closure, immutable root metadata, rights attenuation, object continuity, ancestry consistency, acyclic derivation, no live descendant beneath a revoked ancestor, and transitive revocation closure.

Twelve fail-closed controls cover prerelease substitution, TLC/JRE hashes, unsigned-input overclaims, runtime closure, both executed mutants, unexpected safe violations, path escape, arbitrary TLC modes, and implementation-trace overclaim.

## Assumptions And Non-Claims

- Transitions are atomic. No concurrency, torn write, crash persistence, cryptography, firmware, DMA, or physical attacker is modeled.
- The boot model abstracts persistent metadata, exactly two slots, and one candidate-installation lifecycle without slot erasure or reuse. It does not model image verification, storage ordering, power loss, Secure Boot, anti-rollback counters, or real update formats.
- The capability model does not model IPC, scheduling, memory maps, identifier reuse, quotas, timing, revocation races, or kernel data structures.
- TLC uses 64-bit state fingerprints. A drained queue within frozen constants is not a collision-free theorem.
- No liveness, fairness, real-time, probabilistic, refinement, or implementation-equivalence property is checked.
- Counterexamples show that the model's named invariant detects the deliberate mutation. They do not prove that every real defect maps to the mutation.

## Open Gates

`FLAG-N4-MODELS-001` remains open. The current slice covers three of seven required domains: capability derivation/revocation, boot-slot state, and update rollback. IPC, scheduler, VM map/unmap, and PooleFS transaction recovery remain unmodeled. Both model traces still require cross-checking against exact native implementation traces before any dependent ABI freeze. N4 remains partial and `production_promotion_allowed=false`.
