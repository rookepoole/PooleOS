# PooleOS Bounded Native Models

Status: Cycle 94 pre-production evidence
Date: 2026-07-16
Selected move: `N4-IPC-MODEL-001`
Contract: `POOLEOS-N4-MODELS-3`

## Scope

This cycle extends the executable state-model slice required by N4.5-N4.6 and `ADD-ASSURE-001`. It uses the TLC explicit-state model checker to exhaust every reachable state within four small frozen safe configurations and to demonstrate that eight deliberate unsafe mutations produce their required counterexample traces. The new IPC model covers capability-mediated enqueue, bounded endpoint queues, dispatch and reply-token lifecycle, cancellation, timeout, endpoint teardown/reopen epochs, stale-reply rejection, and quiescent teardown.

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

| Model | Frozen finite bounds | Safe result | Required hostile result(s) |
| --- | --- | --- | --- |
| `PooleBootSlots` | Two slots; two trial attempts; atomic stage/trial/success/failure/discard transitions | 46 generated, 20 distinct, queue drained, depth 7 | `UnsafeRollback=TRUE` violates `Recoverable`; 14 generated, 8 distinct, depth 4; trace `Init -> Stage -> StartTrial -> TrialFailure` |
| `PooleCapabilities` | Three capability IDs; two principals; two rights; one object; no ID reuse | 7,963 generated, 1,316 distinct, queue drained, depth 6 | `UnsafeLocalRevoke=TRUE` violates `NoLiveDescendantOfRevoked`; 36 generated, 31 distinct, depth 3; trace `Init -> Derive -> Revoke` |
| `PooleVirtualMemory` | Two domains; two CPUs; two pages; one virtual address; generations 0 through 1 | 10,210 generated, 1,422 distinct, queue drained, depth 13 | `UnsafeStaleMapping=TRUE` violates `PageTableSafety`; 136 generated, 75 distinct, depth 4; trace `Init -> Map -> BeginTransfer -> CompleteTransfer`. Separately, `UnsafeEarlyReuse=TRUE` violates `TlbSafety`; 1,128 generated, 339 distinct, depth 6; trace `Init -> Map -> TlbFill -> BeginTransfer -> Unmap -> CompleteTransfer` |
| `PooleIPC` | Two principals; one endpoint; two calls; two reply tokens; one queued call; endpoint epochs 0 through 1 | 1,402 generated, 621 distinct, queue drained, depth 9 | Independent mutants reject unauthorized enqueue via `QueuedCallAuthorized`, reply-token reuse via `LiveTokenConsistent`, stale post-cancel reply via `AcceptedRepliesFresh`, and queued-state leakage across teardown via `ClosedEndpointQuiescent`; traces have 2, 4, 5, and 3 states respectively |

Every safe and hostile case executes twice. All twelve normalized results match exactly. A hostile TLC exit code is accepted only when the exact named case, invariant, state counts, depth, normalized trace actions, and trace digest match the contract.

## Safety Properties

The boot-slot model checks type closure, nonempty known-good recovery state, known-good active state outside trials, an available fallback during trials, candidate/phase consistency, and bounded attempts.

The capability model checks type closure, immutable root metadata, rights attenuation, object continuity, ancestry consistency, acyclic derivation, no live descendant beneath a revoked ancestor, and transitive revocation closure.

The virtual-memory model checks type closure, valid transfer targets, ownership and generation agreement for page-table, TLB, and retired translations, exact retired-translation/shootdown-pending consistency, and the requirement that pending shootdowns follow unmapping. The safe transfer transition cannot change ownership or generation until page-table, TLB, and retired references are clear.

The IPC model checks queue bounds and state agreement, enqueue authorization, in-flight call/reply-token consistency, single live-token ownership, terminal token retirement, accepted-reply freshness, and endpoint quiescence after teardown. Endpoint epochs prevent a token issued before teardown from becoming fresh after reopen.

Eighteen fail-closed controls cover prerelease substitution, TLC/JRE hashes, unsigned-input overclaims, runtime closure, all eight executed mutants, unexpected safe violations, path escape, arbitrary TLC modes, and implementation-trace overclaim.

## Assumptions And Non-Claims

- Transitions are atomic. No concurrency, torn write, crash persistence, cryptography, firmware, DMA, or physical attacker is modeled.
- The boot model abstracts persistent metadata, exactly two slots, and one candidate-installation lifecycle without slot erasure or reuse. It does not model image verification, storage ordering, power loss, Secure Boot, anti-rollback counters, or real update formats.
- The capability model does not model IPC, scheduling, memory maps, identifier reuse, quotas, timing, revocation races, or kernel data structures.
- The virtual-memory model does not model page-table levels, PCID/ASID, interrupts, weak-memory ordering, concurrent page-table writers, hardware page walks, huge pages, copy-on-write, swap, NUMA, DMA, or an IOMMU. Its generation range permits only one ownership-changing reuse per page.
- IPC call and reply-token identifiers are one-shot and never recycled. `CanCall` is an abstract authorization predicate, not a composition with the capability derivation/revocation model. The queue is an unordered set abstraction. The model does not represent payload bytes, message copying, scheduling, priorities, fairness, blocked threads, interrupts, SMP or weak-memory interleavings, quotas, endpoint transfer, kernel object layouts, or ABI encoding.
- TLC uses 64-bit state fingerprints. A drained queue within frozen constants is not a collision-free theorem.
- No liveness, fairness, real-time, probabilistic, refinement, or implementation-equivalence property is checked.
- Counterexamples show that the model's named invariant detects the deliberate mutation. They do not prove that every real defect maps to the mutation.

## Open Gates

`FLAG-N4-MODELS-001` remains open. The current slice covers five of seven required domains: capability derivation/revocation, IPC state, virtual-memory map/unmap, boot-slot state, and update rollback. Scheduler transitions and PooleFS transaction recovery remain unmodeled. All four model families still require cross-checking against exact native implementation traces before any dependent ABI freeze. N4 remains partial and `production_promotion_allowed=false`.
