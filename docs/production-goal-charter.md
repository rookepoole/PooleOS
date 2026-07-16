# PooleOS Native Production Goal Charter

Charter version: 2.0.0-native-reset  
Status date: 2026-07-16  
Owner and IP holder: Rooke Poole  
Parent objective: production-ready native PooleOS with a Poole-authored microkernel  
Authoritative Build Plan: `docs/pdc-production-build-plan.md`  
Machine ledger: `runs/pdc_production_roadmap.json`  
Master-checklist coverage: `runs/pooleos_native_checklist_coverage.json`  
Last roadmap reconciliation: PooleOS Cycle 91

Current reconciliation: the seven-record native constitution, public/private boundary, architecture baseline, and conformance policy remain partial evidence. The public `rookepoole/PooleOS` repository has protected `main`; PRs #1 through #5 are merged, with Cycle 90 public at `3f364a4a06e0ce3eb676e98fe6444669c4e2b3d7`. The owner-controlled ADR ceremony binds six exact decision sources and all 38 target definitions while accepting zero measurements. Cycle 91 adds a deterministic 16-source owner packet that presents both proposed ADRs, all 38 target definitions, every allowed custody profile, an unfilled response form, and 12/12 fail-closed packet controls. Every owner selection remains `UNSELECTED`; there are zero trusted keys, no owner signature, no merge or publication authorization, and no production-promotion power. Cycle 87 closed the bounded unprivileged CPUID portion of `N2-HW-002` with 16 allowlisted records, 24/24 identity checks, 14/14 hostile controls, and zero public privacy violations; no driver or privileged probe was loaded. Cycle 88 closed `FLAG-N4-PROFILE-001` and partially advanced N4.1-N4.4 with 4/4 paused QMP machine probes and 18/18 negative controls without starting a guest CPU. Cycles 89-90 added bounded boot-slot rollback, capability derivation/revocation, page ownership, virtual map/unmap, TLB shootdown, and generation-transfer state; across all three models, 3/3 safe searches drain, 4/4 required hostile counterexamples are detected, 7/7 repeat pairs match, and 14/14 negative controls pass. `FLAG-N4-MODELS-001` remains open: IPC, scheduler, PooleFS recovery, and all three native implementation-trace comparisons are unfinished. The checks are not theorem proofs, liveness or refinement checks, fingerprint-collision guarantees, ABI-freeze authority, or PooleKernel evidence. Current QEMU and EDK II source rebuilds, provider patch-delta review, license/SBOM/vulnerability closure, real PooleBoot evidence, fault campaigns, and second-host reproduction also remain open. `N0-RATIFY-001` remains blocked on Rooke Poole's completed packet response, objective/ADR disposition, and custody choice; all 38 values await owner acceptance or amendment and all 38 targets remain unmeasured. The next owner-independent move remains `N4-IPC-MODEL-001`, but the chronological lane pauses there while the packet is under owner review. The one-host Rust 1.97.0/LLD 22.1.6, QEMU 11.0.0, and bounded model evidence remains non-promoting. No functional PooleBoot, PooleKernel, userspace, driver, desktop, or ISO exists.

## 1. Objective

Build and deliver production-ready PooleOS as an original x86-64 UEFI operating system and reproducible, signed, bootable `.iso` image.

The production system consists of a Poole-authored `PooleBoot.efi`, a Poole-authored capability-based PooleKernel microkernel, native system servers and isolated driver domains, native storage/network/graphics/audio/user services, PooleGlyph with frozen PGB2/PGVM2 execution, canonical Poole Defect Calculus runtimes and bounded control lanes, and an accessible original Liquid Glass PooleGlass desktop and boot identity.

Linux, Debian, Buildroot, GRUB, Limine, systemd, and Linux userland are not the production foundation. They may be host tools, historical scaffolds, behavioral references, or comparison environments only. No artifact containing those production substitutions may satisfy a PooleOS native phase, boot, kernel, driver, media, or release gate.

## 2. Normative Requirements

The locked `PooleOS_From_Scratch_Master_Checklist.md` is the leaf-requirement authority:

- path: `sources/requirements/sha256/a8c94719faf9428c1f133010ba2603c0270c4e1efd7327af8eab9c8c362abb3d/PooleOS_From_Scratch_Master_Checklist.md`;
- SHA-256: `A8C94719FAF9428C1F133010BA2603C0270C4E1EFD7327AF8EAB9C8C362ABB3D`;
- 416,063 bytes;
- 10,512 lines;
- 171 sections numbered `000-170`;
- 8,998 checkbox lines;
- 8,996 implementation requirements after excluding the two generated-metadata checkbox lines.

Every source line is covered by the machine ledger. Every implementation requirement must be completed or explicitly dispositioned through a signed release-profile decision. No source line may be silently deleted, summarized away, or treated as completed merely because it is mapped into the plan.

Research additions in the coverage ledger are separately identified as `ADD-*`. They extend the master checklist without pretending to be original checklist text.

## 3. Native Architecture Contract

The production boot chain is:

```text
UEFI firmware
  -> signed PooleBoot.efi
  -> verified boot manifest
  -> verified PooleKernel and initial system/recovery bundles
  -> PooleKernel microkernel
  -> root resource manager and service supervisor
  -> isolated driver domains and native system servers
  -> PooleGlyph / PGB2 / PGVM2 and PDC services
  -> PooleGlass compositor, desktop, applications, installer, and recovery
```

PooleKernel is a minimal mechanism-only TCB. It owns privileged CPU entry, exceptions, interrupts, timers, SMP, address spaces, page ownership, threads, neutral scheduling, IPC, capabilities, IRQ/MMIO/I/O/DMA delegation, IOMMU enforcement, and minimal panic/audit foundations.

PooleKernel does not own general filesystems, networking, USB policy, storage protocols, GPU commands, audio policy, package management, authentication policy, PDC planning, PGVM2 execution, or desktop behavior. Those execute in capability-confined user-space domains. Production loadable kernel modules are prohibited in v1 unless a later reviewed ADR reopens the TCB and its assurance case.

No process receives ambient authority. Every file, endpoint, service, device, memory region, interrupt, DMA mapping, portal, PDC action, and policy operation is reached through explicit attenuable and revocable capabilities.

## 4. Initial Supported Scope

The initial target is:

- x86-64 long mode, little endian;
- UEFI only; no legacy BIOS requirement;
- GPT and a deterministic UEFI-bootable ISO/ESP layout;
- QEMU/OVMF Tier 0 reference profile;
- one exact Tier 1 physical profile based on the inventoried Gigabyte B650M GAMING PLUS WIFI, AMD Ryzen 7 9800X3D, NVIDIA RTX 5070 GOP path, Samsung 970 PRO NVMe, Realtek RTL8125 Ethernet, exact USB input, and selected audio path;
- permanent serial and GOP/software-rendered recovery;
- native accelerated RTX graphics as research until separately qualified;
- exact hardware identifiers and firmware revisions, not generic family claims.

The release profile decides whether Wi-Fi, Bluetooth, suspend, hibernation, AHCI, cameras, printers, scanners, USB4, Thunderbolt, advanced volume management, and other optional classes are required. Unsupported features must fail predictably and be published.

## 5. PooleGlyph Contract

Develop PooleOS and the live `<POOLEGYPH_REPO>` checkout in tandem.

At the start of each active cycle:

1. inspect the newest checkpoint, manifest, hashes, release notes, conformance evidence, and repository status;
2. preserve user changes and never rewrite the dirty generated conformance report merely to obtain a clean tree;
3. update the PooleGlyph source anchor and boundary records only from observed evidence;
4. keep parser-to-kernel/system promotion blocked until Phase 66 executable Core IR evidence is accepted;
5. never promote metadata-only declarations into executable or privileged authority.

PGB2 must become a canonical signed binary package format. PGVM2 must become a bounded deterministic virtual machine with independent verification, typed effects, explicit capabilities, quotas, deadlines, cancellation, cleanup, traps, replay, and version negotiation. PooleGlyph policy may narrow existing authority but cannot create kernel/device authority.

Recovery and safe mode must not require PooleGlyph.

## 6. PDC Contract

Preserve and extend the existing source-bound PDC evidence without expanding its claims.

Required work includes:

- canonical binary, planar, geometric, Q/P, probability, signed, and matrix contracts;
- exact source intake and finite verifier reproduction;
- representation, metamorphic, perturbation, and negative corpora;
- source-bound signed-dynamics benchmark reproduction;
- portable deterministic `libpdc` with stable native ABI;
- differential scalar, CPU, RAM, GPU, PooleOS, and bounded rescue paths;
- guarded promotion, invalidation, regret, fallback, and receipts;
- observation-first PDC system control, independent policy gate, lane-specific actuators, watchdog, rollback, and safe neutral controls.

PDC and Q/P results remain bounded to exact models, workloads, data, hardware, and tests. Q/P is a classical transform over measured or simulated fields, not unknown-state reconstruction. Finite empirical results do not establish universal physical, quantum, medical, legal, financial, security, or hardware behavior.

PDC must never control boot trust, signing roots, key storage, recovery availability, firmware flashing, undocumented voltage/clock operations, or hard thermal safety limits.

## 7. UI and Boot Identity Contract

PooleOS must provide an original coherent Liquid Glass visual system across desktop, shell, applications, installer, settings, permissions, diagnostics, and recovery.

Required properties include:

- stable layouts and restrained effects appropriate to a production workstation;
- balanced palette and semantic status colors;
- keyboard, pointer, touch where supported, focus, text scaling, magnification, screen reader, captions/speech boundary, braille boundary, high contrast, and color-vision support;
- reduced transparency, reduced motion, software rendering, safe graphics, and non-composited recovery;
- frame time, startup, memory, CPU, GPU, thermal, and power budgets;
- trusted UI for authentication, permissions, secrets, updates, destructive actions, and recovery;
- no visual effect that obscures errors, security state, destructive consequences, or focus;
- compositor/asset/shader/native-GPU failure must not prevent serial/GOP recovery.

The boot identity consists of a static firmware-safe PooleOS mark and a later early-userspace animated Liquid Glass transition. Animation is presentation only. Signed machine-readable stage markers prove boot progress independently. Reduced-motion and static fallback are mandatory.

## 8. Security, Recovery, and Update Contract

The project must define and test:

- offline and intermediate signing roots, development-key isolation, rotation, revocation, expiry, compromise, and release ceremony;
- UEFI PK/KEK/db/dbx state, Secure Boot, artifact verification, minimum secure version, measured boot, TPM event log, and recovery keys;
- capability attenuation, derivation, transfer, revocation, generation safety, quotas, teardown, and no ambient authority;
- W^X, NX, SMEP, SMAP, control-flow and transient-execution mitigations tied to exact CPU/microcode;
- IOMMU and interrupt-remapping confinement before bus mastering;
- reviewed cryptography, entropy health, CSPRNG readiness, secret stores, trust stores, MAC, and privacy defaults;
- signed packages and compromise-resilient update roles with threshold keys, expiry, rollback, freeze, and mix-and-match protection;
- immutable A/B system slots, bounded boot attempts, previous-known-good, safe mode, recovery, installer interruption handling, backup, and restore;
- recovery that remains simpler and less dependent than normal operation.

Any unresolved data-loss, privilege, boot-loop, signing, rollback, firmware, recovery, secret, or DMA escape defect is stop-ship.

## 9. Build and Supply-Chain Contract

Release-critical builds must be hermetic, offline where declared, source-controlled, dependency-complete, and reproducible.

The release chain must bind:

- exact source revision and tree hash;
- compiler, assembler, linker, sysroot, host tools, configuration, environment, and flags;
- generated ABI and standards data;
- third-party source, patches, firmware, microcode, fonts, Unicode/timezone/root-certificate data, and licenses;
- PooleBoot, PooleKernel, every server/driver/library/application, PooleGlyph/PGB2/PGVM2, PDC, UI assets, system/recovery images, and ISO;
- tests, raw failures, fuzz corpora, power-cut images, hardware profile, benchmark data, SBOM, provenance, signatures, and approvals.

Use SPDX 3.0.1-compatible SBOM, SLSA 1.2-compatible provenance, and in-toto-style signed supply-chain links or a reviewed equivalent. Verification must be independent from the build that produced the artifact.

Two clean independent builders must reproduce declared unsigned artifacts and ISO bytes. Any unavoidable signing nondeterminism must be specified and bound so the exact signed distributed bytes remain traceable to reproducible unsigned inputs.

## 10. Evidence and Claim Discipline

Never convert a fixture, mockup, schema pass, static proof, model, host test, simulator, Buildroot image, ISO filename, one QEMU boot, one physical boot, visual animation, or finite benchmark into a broader production claim.

For every promoted requirement:

- retain specification/ADR, source revision, implementation, positive and hostile tests, raw outputs, environment, hardware/firmware identity, toolchain, hashes, recovery evidence, documentation, and signed receipt;
- bind evidence to the exact input and output artifacts;
- preserve failed runs and negative results;
- distinguish normative conformance, tested behavior, observed behavior, hypothesis, research, and unsupported behavior;
- require independent reproduction where the Build Plan or release profile says so.

## 11. Per-Turn Next-Best-Move Loop

Every active goal turn must:

1. Read this charter, the Build Plan, machine roadmap, checklist coverage ledger, current flags, release gaps, latest cycle log, and previous handoff.
2. Reinspect the live PooleGlyph checkpoint folder and repository state.
3. Confirm the locked master checklist and coverage manifest still match their expected hashes/counts.
4. Determine the earliest unmet dependency and highest-risk unblocked native requirement.
5. Select the smallest proof-strengthening move that advances the native critical path without relying on an unfrozen downstream interface.
6. State the selected phase, subphase, requirement IDs, entry evidence, expected artifact, negative cases, and exit criterion.
7. Implement in the smallest ownership boundary and preserve unrelated user changes.
8. Run proportionate unit, integration, malformed, adversarial, concurrency, fault, recovery, and regression tests.
9. Validate all touched schemas/artifacts and rerun the checklist coverage guard when source or mapping changes.
10. Update the Build Plan, machine roadmap, phase/subphase status, item dispositions, implementation flags, gaps, risks, evidence hashes, release gate, cycle log, README, and handoff.
11. Record honest non-claims and any newly discovered required work. Never hide a blocker to preserve a schedule or phase count.
12. End with the exact next dependency-ordered move.

Architecture work N0-N5 outranks downstream optimization while those foundations remain unclosed. PDC signed dynamics and PooleGlyph Phase 66 may proceed in parallel but cannot substitute for native boot progress.

## 12. Phase Contract

The authoritative completion range is `N0-N39`.

- N0-N4 establish constitution, governance, hardware, toolchain, emulation, reference devices, and formal models.
- N5-N11 establish PooleBoot, boot trust, CPU, interrupts/time/SMP, memory, platform discovery, and IOMMU.
- N12-N16 establish scheduling, capability objects, IPC/isolation, security, and user-space driver domains.
- N17-N24 establish storage, input, PooleFS, user ABI, services, sessions, update/recovery, and power/firmware health.
- N25-N30 establish networking, graphics, audio, desktop/accessibility, and application platform.
- N31-N35 establish observability, PDC, PooleGlyph, reliability, watchdogs, and fault containment.
- N36-N39 establish full verification, supply chain, qualification, and exact signed native ISO release.

A phase may be marked complete only when every mapped required item and applicable research addition passes its Build Plan exit gate with immutable evidence.

## 13. Bootable ISO Contract

The production `.iso` is UEFI-native and PooleOS-owned. It must define and verify:

- deterministic El Torito EFI/GPT/ESP layout and volume metadata;
- signed PooleBoot, manifest, PooleKernel, initial system, recovery, native drivers/services, PooleGlyph/PGB2/PGVM2, PDC, PooleGlass, installer, packages, and evidence;
- architecture-conformance rejection of Linux kernels, Buildroot/Debian rootfs, GRUB/Limine, systemd, and undeclared host artifacts;
- exact root/system/recovery continuity and boot-stage hashes;
- normal, safe, previous-known-good, diagnostic, live, installer, recovery, shutdown, and reboot paths;
- clean QEMU/OVMF matrix and exact Tier 1 physical-media boots;
- damaged media, unsupported hardware, low memory, missing devices, failed drivers/services, failed update, rollback, and recovery;
- independent reproducibility, signatures, checksums, SBOM, provenance, source, support matrix, limitations, and release receipt;
- proof that tested and signed ISO bytes are the distributed ISO bytes.

## 14. Completion Gate

Do not mark this goal complete until all of the following are true for the exact supported release profile:

- all 8,996 implementation requirements are complete or explicitly excluded by signed scope disposition;
- all applicable `ADD-*` requirements are complete;
- all required N0-N39 phases and subphases are complete;
- PooleOS is source-controlled and every release byte has provenance and licensing records;
- PooleBoot and PooleKernel are original, reviewed, reproducible, signed native components;
- capability, IPC, memory, scheduler, IOMMU, driver isolation, storage, PooleFS, network, security, update, recovery, and fault-containment gates pass;
- PooleGlyph Phase 66 promotion is accepted and PGB2/PGVM2 v1 is frozen and enforced;
- PDC reference and native/backends agree within declared contracts and bounded control lanes pass rollback/watchdog gates;
- accessible PooleGlass Liquid Glass, software-rendered fallback, static/animated boot identity, installer, and recovery pass;
- external review closes all critical and high findings;
- two clean independent builders reproduce declared bytes;
- the exact signed ISO boots and operates from clean media in every supported QEMU and physical hardware profile;
- live/install/recovery/update/rollback/power-loss/soak/security/accessibility/support tests pass;
- exact source, SBOM, provenance, signatures, hardware matrix, limitations, recovery, support, and incident records ship;
- no `STOP_SHIP` flag is open;
- the signed release receipt sets `production_ready=true` for one exact ISO SHA-256.

Until then, every artifact is explicitly a research build, developer preview, lab image, alpha, beta, or release candidate. The goal persists across cycles and must not be marked complete merely because one milestone, phase, boot, UI demonstration, benchmark, or ISO assembly succeeds.
