# PooleOS Native Architecture Production Build Plan

Status date: 2026-07-16  
Plan version: 2.0.0-native-reset  
Roadmap cycle: PooleOS Cycle 83
Implementation baseline entering this revision: PooleOS Cycle 79, PooleGlyph Phase 65  
Author and IP owner: Rooke Poole  
Machine ledger: `runs/pdc_production_roadmap.json`  
Checklist coverage ledger: `runs/pooleos_native_checklist_coverage.json`  
Coverage schema: `specs/pooleos-native-checklist-coverage.schema.json`

## 1. Architecture Decision

PooleOS v1 is an original x86-64 operating system. Its production artifact is not Linux-based, Debian-based, Buildroot-based, or a customized distribution. The production boot chain is:

```text
UEFI firmware
  -> signed PooleBoot.efi
  -> verified Poole boot manifest
  -> verified PooleKernel ELF64 image and initial system bundle
  -> PooleKernel capability-based microkernel
  -> root resource manager and service supervisor
  -> isolated user-space driver domains and system servers
  -> PooleGlyph / PGB2 / PGVM2 runtime and policy services
  -> libpdc and guarded CPU / RAM / GPU services
  -> PooleGlass compositor, shell, applications, installer, and recovery
```

Linux, Debian, WSL, Buildroot, QEMU, OVMF, EDK II, host compilers, and host test libraries may be development tools, behavioral references, or comparison environments. None may appear as the production kernel, init system, driver substrate, root filesystem, package manager, compositor, or bootloader. Existing Buildroot artifacts are preserved under the Cycle 79 historical baseline and cannot satisfy a native phase or release gate.

The first production scope is x86-64 little-endian, UEFI-only, GPT media, QEMU/OVMF Tier 0, and one exact physical Tier 1 machine. Legacy BIOS, a Linux ABI, Windows-driver compatibility, broad commodity hardware, native RTX acceleration, Wi-Fi, Bluetooth audio, suspend, hibernation, and optional peripheral classes are not permitted to block the earliest native milestones. They become release requirements only when their support tier is explicitly included in a release profile.

## 2. Complete Checklist Integration

The exact source is locked at:

`sources/requirements/sha256/a8c94719faf9428c1f133010ba2603c0270c4e1efd7327af8eab9c8c362abb3d/PooleOS_From_Scratch_Master_Checklist.md`

Source SHA-256: `A8C94719FAF9428C1F133010BA2603C0270C4E1EFD7327AF8EAB9C8C362ABB3D`  
Source bytes: `416,063`  
Source lines: `10,512`  
Top-level numbered sections: `171` (`000-170`)  
Checkbox lines: `8,998`

The source's declared `8,996` implementation-item count is correct under its own implied counting rule: the 8,998 checkbox lines include two generated-metadata checkboxes on lines 3-4, which are not implementation requirements. The remaining count is ten governing preamble requirements plus 8,986 requirements inside sections `000-170`.

No checklist text is summarized away. The locked source remains the normative leaf-requirement register. This plan supplies dependency order, architecture placement, scope, gates, current status, and evidence rules. `runs/pooleos_native_checklist_coverage.json` maps every source line and every numbered section to exactly one phase. `tools/generate_native_checklist_coverage.py` fails on source hash drift, duplicate section assignment, missing sections, changed counts, or unmapped lines.

Rules:

1. Every mapped checkbox is inherited by its phase even when this plan does not repeat its prose.
2. Mapping an item does not mark it complete.
3. A requirement may be `required_v1`, `required_later`, `profile_required`, `research`, `optional`, or `unsupported_v1`; it may never disappear silently.
4. A phase cannot close until every mapped required item has implementation, positive tests, negative tests, failure handling, recovery, documentation, and evidence.
5. Deferral requires an ADR, rationale, target milestone, risk owner, and a release profile that excludes the feature.
6. Research additions are recorded separately as `ADD-*`; they are not misrepresented as lines from the master checklist.
7. The ten preamble requirements and all lines 1-16 are governed by N0 even though phase statistics below report numbered-section counts only.

## 3. From-Scratch Reuse Boundary

### 3.1 Poole-authored production components

The following are authored as PooleOS components: PooleBoot, PooleKernel, the boot protocol, system-call ABI, capability and IPC model, driver-domain protocol, root task, service supervisor, device manager, VFS, PooleFS, core user runtime, core utilities, package and update formats, installer, recovery environment, compositor protocol, PooleGlass desktop, PooleGlyph system integration, PGB2, PGVM2, PDC control plane, native receipts, and image/release tooling.

### 3.2 Permitted external inputs

Compilers, assemblers, linkers, debuggers, emulators, firmware, microcode, normative specifications, conformance vectors, Unicode/CLDR/timezone data, root certificates, fonts, audited cryptography, rasterization/shaping libraries, codecs, and optional application libraries may be used or ported only after the reuse ADR records source, version, hash, license, patch set, attack surface, update owner, and independent verification strategy.

PooleOS must not invent security cryptography merely to satisfy a from-scratch slogan. A reviewed cryptographic implementation may be ported behind a Poole-owned provider API. Vendor firmware and microcode may be loaded only when redistribution, signature, version, rollback, failure, and recovery policy are explicit.

### 3.3 Code-study boundary

Public specifications and public hardware documentation are primary implementation authorities. Studying permissively licensed code, copyleft code, vendor code, or reverse-engineered code requires an ADR and provenance policy before implementation begins. NDA-derived knowledge must remain segregated where required. No Linux source may be copied into PooleKernel or represented as original PooleOS code.

### 3.4 Compatibility boundary

POSIX.1-2024 is an interface reference and selective compatibility target, not the native architecture. The native ABI is capability-oriented. Linux ABI compatibility and Windows application compatibility are post-v1 optional compatibility servers, never kernel design constraints. PooleGlyph is not required to compile the first bootloader or kernel. It enters production policy only after Phase 66 evidence, PGB2/PGVM2 freeze, and fail-closed promotion gates.

## 4. Trusted Computing Base

### 4.1 Ring 0 PooleKernel

PooleKernel contains only mechanisms that require privilege:

- CPU entry, traps, exceptions, interrupt routing, timers, SMP startup, and context switching;
- physical and virtual address-space control, page ownership, and safe user-memory transfer;
- threads, bounded neutral scheduling, IPC, notifications, and capability enforcement;
- IRQ, MMIO, I/O-port, DMA-domain, and device-reset authority delegation;
- IOMMU and interrupt-remapping control required to confine user-space drivers;
- minimal boot, panic, crash, monotonic-time, entropy-seed, and audit foundations;
- bounded rescue operations that are independently justified and tested.

PooleKernel excludes filesystems, networking, USB policy, storage protocols, GPU command generation, PDC planners, PGVM2 execution, package management, authentication policy, desktop policy, and general device drivers. Production loadable kernel modules are prohibited in v1. New functionality normally ships as a signed, restartable user-space server or driver package.

### 4.2 Privileged user-space servers

The initial system bundle creates a root resource manager with one-time authority to construct the system capability graph. Dedicated servers own process policy, device enumeration, driver supervision, VFS, storage, network, input, display, audio, logging, identity, secrets, package/update, PDC, PGVM2, and recovery functions. Each receives only the capabilities, memory quotas, CPU budgets, and peers required for its role.

### 4.3 Driver domains

Each driver domain receives revocable leases for exact PCI functions, BAR ranges, port ranges, IRQ vectors, DMA mappings, firmware blobs, and reset methods. Bus mastering stays disabled until an IOMMU domain and valid DMA buffers exist. Driver crash, timeout, process death, reset, or revocation must release mappings and reject stale completions without rebooting the kernel when hardware permits.

### 4.4 Ordinary applications

Applications receive no ambient authority. Files, services, devices, network endpoints, clipboard channels, portals, and PDC operations are explicit capabilities issued through signed package declarations and user/session policy. The PooleGlyph policy layer may narrow authority but cannot grant authority absent from the capability graph.

### 4.5 Recovery TCB

Recovery boots from a separately signed immutable image and remains usable without PooleGlyph, PDC, the package service, network, native GPU acceleration, the normal compositor, or the mutable system slot. A static GOP/serial path is permanent.

## 5. Current Evidence Baseline

Cycle 80 reset architecture claims without discarding validated component evidence. Cycle 81 established the first byte-bound native constitution and repository boundary. Cycle 82 published the baseline repository, protected `main`, and qualified the first pinned freestanding PE32+/ELF64 compiler path on one host. Cycle 83 freezes and tests the owner-controlled ADR ceremony without generating a key, signing as the owner, or promoting any unsigned decision.

| Area | Current evidence | Native status | Boundary |
|---|---|---|---|
| Master checklist | Exact 416,063-byte source locked; 10,512 lines, 171 sections, 8,998 checkbox lines mapped | Partial | Coverage is planning evidence, not implementation |
| PDC binary reference | `PDC-MATH-0.1`, 13 golden cases, scalar/matrix agreement | Partial N32 | Python reference, not native execution |
| Finite geometric verifiers | 4,324 declared cases reproduced with zero semantic mismatch | Partial N32 | Finite supported domains, not all-size proof |
| Representation | `PDC-REP-0.1`, 3,109 differential cases, 12,436 round trips | Partial N32 | No native pointers, DMA, or kernel mapping proof |
| Metamorphic corpus | `PDC-GOLDEN-0.2`, 72 relations, 824 representation round trips | Partial N32 | Periodic reference scope |
| Q/P | `PDC-QP-0.1` and `PDC-QP-STABILITY-0.1`; 550 fields and 2,200 perturbations | Partial N32 | Classical measured/simulated-field diagnostics only |
| PooleGlyph | Phase 65 checkpoint, 97/97 conformance, ZIP SHA-256 `F3CCEB701CF76274D9464A0958BF6106888FB34F3C0BFBD55DE4ACE03C427ABC` | Blocked N34 | Phase 66 blocks executable Core IR promotion |
| PGB2/PGVM2 | JSON draft, byte/trap simulator, capability planning receipts | Partial N34/N35 | No frozen binary ABI or native execution |
| Isolation | Static microkernel/capability simulations and bounded fuzz evidence | Partial N15/N35 | Not enforced by PooleKernel |
| QEMU/Buildroot | Historical lab scaffolding and evidence contracts | Reference only | Cannot satisfy native boot, kernel, driver, or ISO gates |
| Test suite | Cycle 83: 397 tests pass with one Windows symlink-permission skip, including ten real/adversarial ADR-signing tests | Partial N36 | Predominantly host/reference and artifact tests |
| Release gate | Cycle 83: 63/63 consistency checks over 58 artifacts; 20 native gaps | Partial N37 | `production_ready=false`; not a release acceptance gate |
| Source control | Public `rookepoole/PooleOS`, protected `main`, topic-branch workflow, private vulnerability reporting | Partial N1/N37 | Initial commit unsigned; signed tags, immutable release refs, retained CI, and full review policy remain open |
| ADR ratification | Canonical OpenSSH `SSHSIG` manifest, domain-separated namespace, public trust/revocation files, signed-tag/remote verifier, ten negative controls | Partial N0/N1/N37 | Zero trusted owner keys; ADR-0003/0004 disposition, signature, tag, and publication receipt remain owner actions |
| Native toolchain | Rust 1.97.0/Cargo 1.97.0/LLD 22.1.6; two clean PE32+ and ELF64 builds match exactly on one host | Partial N3 | Empty non-booting fixtures; second host and remaining tool families are open |
| Native bootloader | No Poole-authored PE32+ UEFI image | Not started N5 | No native UEFI proof of life |
| Native kernel | No PooleKernel source, ELF image, boot, ring 3, IPC, capability, or driver-domain execution | Not started N6-N16 | Zero native-kernel production claims |
| Native media | No native signed ISO or physical boot | Not started N39 | Existing image names are non-promoting fixtures |

### 5.1 Exact Tier 1 machine facts observed on 2026-07-15

| Component | Observed identity | Qualification status |
|---|---|---|
| Motherboard | Gigabyte `B650M GAMING PLUS WIFI`, board version `x.x` | Partial inventory; ACPI/PCI/firmware dumps still required |
| Firmware | AMI BIOS `F32`, reported release date 2025-02-04 | Not qualified |
| CPU | AMD Ryzen 7 9800X3D, 8 cores / 16 logical processors | Exact initial CPU target |
| RAM | 16 GiB, two TeamGroup `UD5-6000` 8 GiB modules at 6000 | Exact current profile; SPD/topology evidence pending |
| GPU | NVIDIA GeForce RTX 5070, `VEN_10DE&DEV_2F04&SUBSYS_89E71043&REV_A1` | GOP required; native acceleration research only |
| NVMe | Samsung SSD 970 PRO 512GB, firmware `1B2QEXP7`, controller `VEN_144D&DEV_A808` | Candidate read-only/boot target; never use as sole destructive test disk |
| SATA SSD | Crucial CT2000BX500SSD1, firmware `M6CR061` | Not automatically sacrificial; ownership must be confirmed |
| Ethernet | Realtek RTL8125 family, `VEN_10EC&DEV_8125&REV_05` | Candidate Tier 1 network target |
| Wi-Fi | Realtek 8851BE, `VEN_10EC&DEV_B851` | Later profile; firmware/regulatory work required |
| Bluetooth | Realtek USB `VID_0BDA&PID_B850` | Later profile |
| Audio | Realtek codec `VEN_10EC&DEV_0897`, NVIDIA HDA, Focusrite USB device observed | Start with one explicitly selected path |
| USB | AMD xHCI functions `DEV_15B6`, `15B7`, `15B8`, and `43F7` observed | Exact register/firmware qualification pending |

No destructive operation is authorized by this inventory. A separately identified spare SSD, verified backup, recovery media, and explicit operator approval remain mandatory.

## 6. Status and Evidence Rules

Phase statuses are `not_started`, `partial`, `blocked`, and `complete`. Work-item dispositions are `required_v1`, `required_later`, `profile_required`, `research`, `optional`, `unsupported_v1`, and `superseded`. Flags are `STOP_SHIP`, `BLOCKER`, `REQUIRED`, `RISK`, `RESEARCH`, `OPTIONAL`, `DEFERRED`, or `SUPERSEDED`.

An item is complete only when all applicable evidence exists:

1. reviewed specification or ADR;
2. implementation tied to an immutable source revision;
3. positive, boundary, malformed, adversarial, concurrency, and failure tests;
4. deterministic or controlled test inputs and raw output retention;
5. recovery and rollback behavior;
6. security and capability review;
7. performance and resource-budget measurement where relevant;
8. user, developer, operator, and support documentation;
9. artifact hashes, toolchain identity, environment, and signed receipt;
10. independent reproduction for release-critical claims.

Passing a schema, fixture, host simulation, model, visual mockup, one boot, or one benchmark cannot close a native implementation item.

## 7. Phase Coverage Summary

The exact section titles, start/end lines, subheading counts, and checkbox counts are in the coverage ledger.

| Phase | Status | Checklist sections | Section items | Added requirements |
|---|---|---:|---:|---:|
| N0 | Partial | `000,001,170` | 167 | 2 |
| N1 | Partial | `002-004` | 181 | 1 |
| N2 | Partial | `005-007,146,169` | 236 | 0 |
| N3 | Partial | `008-011` | 200 | 0 |
| N4 | Partial | `012` | 34 | 2 |
| N5 | Not started | `013-015` | 241 | 1 |
| N6 | Not started | `016-019,148-149` | 291 | 1 |
| N7 | Not started | `020-022` | 192 | 0 |
| N8 | Not started | `023-025` | 204 | 1 |
| N9 | Not started | `026-029,151` | 410 | 0 |
| N10 | Not started | `042-046,152` | 447 | 0 |
| N11 | Not started | `030` | 42 | 0 |
| N12 | Not started | `031-034` | 193 | 0 |
| N13 | Not started | `035-038` | 183 | 1 |
| N14 | Not started | `039-041,163-164` | 261 | 1 |
| N15 | Partial | `107-112,155` | 240 | 1 |
| N16 | Not started | `150` | 96 | 3 |
| N17 | Not started | `047-050,166` | 268 | 0 |
| N18 | Not started | `051-057,165` | 443 | 0 |
| N19 | Not started | `076-081` | 329 | 1 |
| N20 | Not started | `082-087` | 238 | 0 |
| N21 | Not started | `088-092,141,158,168` | 467 | 0 |
| N22 | Not started | `093-094,157,162,167` | 308 | 0 |
| N23 | Not started | `095-098,159` | 315 | 2 |
| N24 | Not started | `099-100,153-154` | 260 | 0 |
| N25 | Not started | `063-066` | 210 | 0 |
| N26 | Not started | `067-075,156` | 455 | 0 |
| N27 | Not started | `058-061` | 172 | 1 |
| N28 | Not started | `062,104-105` | 96 | 0 |
| N29 | Not started | `101-103,160-161` | 322 | 1 |
| N30 | Not started | `106` | 70 | 0 |
| N31 | Partial | `113-116` | 193 | 0 |
| N32 | Partial | Added PDC workstream | 0 | 1 |
| N33 | Partial | `117-123` | 337 | 0 |
| N34 | Blocked | `124` | 102 | 1 |
| N35 | Partial | `125-127` | 61 | 0 |
| N36 | Partial | `128-134,140` | 272 | 2 |
| N37 | Partial | `135-139,147` | 203 | 1 |
| N38 | Not started | `142-145` | 247 | 0 |
| N39 | Not started | Aggregate release phase | 0 | 1 |

Current summary: 40 phases, 0 complete, 12 partial, 1 blocked, and 27 not started. This conservative reset is intentional: previous reference evidence is credited, but no Linux-oriented scaffold is counted as native implementation.

## 8. Dependency Waves

```text
Wave A  Constitution and reproducible laboratory
  N0 -> N1 -> N2/N3 -> N4

Wave B  Trusted native boot and machine foundation
  N4 -> N5 -> N6 -> N7 -> N8/N9 -> N10 -> N11

Wave C  Microkernel mechanism and isolation
  N8/N9 -> N12 -> N13 -> N14 -> N15 -> N16

Wave D  Native storage and userland
  N16 -> N17/N18 -> N19 -> N20 -> N21 -> N22

Wave E  Lifecycle, devices, and connectivity
  N15/N19/N21 -> N23/N24
  N16 -> N25 -> N26

Wave F  Human interface and application platform
  N18/N20 -> N27/N28 -> N29 -> N30

Wave G  Poole computation and policy
  N20/N31/N32/N34 -> N33

Wave H  Assurance, release, and qualification
  all implemented phases -> N35/N36 -> N37 -> N38 -> N39
```

Parallel work is allowed only when interfaces are still versioned drafts and no downstream phase is promoted on an unfrozen dependency. PDC mathematical research and PooleGlyph Phase 66 may advance in parallel with native boot, but neither may enter the kernel trust path before its promotion gate.

## 9. Native Phase Plan

### N0 - Native Architecture Constitution (`partial`)

Inherited sections: `000`, `001`, `170`, preamble lines 1-16.  
Goal: remove all ambiguity about what PooleOS is, what “from scratch” means, and what constitutes completion.

Subphases:

- N0.1 Ratify ADR-0001: PooleOS v1 is PooleBoot plus a Poole-authored capability microkernel and native userspace.
- N0.2 Ratify the reuse, clean-room, firmware, microcode, cryptography, font, Unicode, and third-party data boundary.
- N0.3 Freeze canonical names and version namespaces for boot protocol, kernel, syscall ABI, IPC ABI, driver protocol, executable ABI, PGB2, PGVM2, package, filesystem, receipt, and ISO manifest.
- N0.4 Freeze the kernel TCB and the kernel/server/driver/application/recovery placement table.
- N0.5 Freeze x86-64 UEFI-only v1 scope, QEMU Tier 0, exact Tier 1 machine, and explicit non-goals.
- N0.6 Define editions, users, use cases, threat model, reliability, accessibility, compatibility, privacy, and performance objectives.
- N0.7 Define release claims and independent-reproduction requirements.
- N0.8 Add architecture-conformance tests that reject Linux kernels, Buildroot rootfs markers, GRUB/Limine, systemd, and other prohibited production dependencies from release media.

Cycle 81-83 evidence:

- ADR-0001 through ADR-0007 record the native constitution, reuse/publication boundary, proposed language split, proposed namespace registry, v1 scope, TCB placement, and repository governance.
- `specs/native-architecture-constitution.json` and `runs/native_architecture_baseline.json` bind exact architecture constants, seven ADR byte hashes, source hashes, owner direction, repository identity, 20 version namespaces, and eight TCB domains.
- `specs/native-release-architecture-policy.json` and `tools/check_native_release_architecture.py` reject missing native release objects, prohibited substitute paths/content, symbolic links, case-fold collisions, non-NFC paths, unreadable objects, and unscanned oversized binaries.
- Negative tests execute every prohibited path glob and every prohibited binary marker. A passing extracted-tree report remains non-promoting because it does not parse ISO, GPT, ESP, El Torito, signatures, hidden sectors, or source provenance.
- `specs/adr-ratification-policy.json` freezes canonical sorted UTF-8/LF JSON, the owner principal, a PooleOS-specific SSH signature namespace, allowed key profiles, public trust/revocation paths, immutable tag name, and exact remote-publication contract.
- `tools/prepare_adr_ratification.py` refuses inferred acceptance, zero/multiple signers, unsupported keys, and unacknowledged provisional software-key risk. `tools/verify_adr_ratification.py` verifies exact manifest bytes, owner principal, namespace, revocation, signed annotated tag, tag-contained evidence, remote tag object, peeled commit, and exact remote `main` tip.
- Ten focused tests exercise a throwaway test-only key and Git repository plus tampered ADRs, wrong namespaces, unknown signers, malformed signatures, noncanonical bytes, revocation, missing disposition, and tag/publication gates. No test key is retained.
- `runs/adr_ratification_readiness.json` deterministically records seven bound ADRs, two proposed records, zero cryptographically ratified records, zero trusted signers, five owner actions, and `production_promotion_allowed=false`.

Open N0 work:

- No ADR has an owner-controlled cryptographic signature. ADR-0003 and ADR-0004 remain proposals pending explicit owner disposition; trademark and full toolchain review also remain open.
- Rooke Poole must choose governance-key custody, approve the public key/fingerprint, physically authorize the detached signature and tag, and publish the exact receipt. Codex has performed none of those owner actions.
- Quantitative reliability, accessibility, compatibility, privacy, and performance targets remain open.
- N0 therefore remains `partial`; no bootloader, kernel, driver, userspace, desktop, or ISO implementation is inferred from this evidence.

Exit gate: signed ADRs resolve every section 000.2 choice; names and version identifiers are reserved; exact supported scope and completion conditions are machine-readable; no production document describes PooleOS as Linux-based.

### N1 - Requirements, Governance, Legal, and Provenance (`partial`)

Inherited sections: `002-004`.  
Goal: make every decision, source line, implementation, test, claim, and release artifact traceable to accountable ownership.

Subphases:

- N1.1 Initialize PooleOS source control with protected main, signed tags, immutable release refs, review rules, and retention policy.
- N1.2 Assign stable requirement IDs and generate requirement-to-code, test, documentation, threat, evidence, and release mappings.
- N1.3 Create ADR templates and required ADRs for kernel, privilege rings, capabilities, IPC, scheduler, memory, drivers, filesystems, graphics, networking, audio, crypto, PDC, and PooleGlyph.
- N1.4 Establish repository/source-tree boundaries, generated-file policy, ABI generation, third-party patches, firmware storage, and conformance corpora.
- N1.5 Record Rooke Poole ownership and choose source-available licenses for every component class without presuming identical terms for code, specifications, data, models, or visual assets.
- N1.6 Establish contributor, SPDX, provenance, export, patent, trademark, privacy, vulnerability disclosure, security contact, and NDA segregation policies.
- N1.7 Define maintainers, signing custodians, release authority, severity, emergency change, deprecation, compatibility, and incident postmortem processes.

Cycle 81-83 evidence:

- The public repository is published at `https://github.com/rookepoole/PooleOS`, with `main` as the default branch and the Cycle 81 bootstrap commit as its root.
- `main` requires pull requests, stale-review dismissal, resolved conversations, and linear history; force-push and deletion are denied. Private vulnerability reporting is enabled. Cycle 83 remains in draft PR #1 on the existing topic branch.
- PolyForm Noncommercial 1.0.0 terms, owner notice, security policy, trademark notice, CODEOWNERS, ADR template, public/private evidence boundary, and native source-tree ownership skeleton are present.
- `.gitignore` excludes raw internal PDC inputs, private/local run evidence, historical Buildroot sources and lab images, archives, credentials, private signing material, firmware without redistribution clearance, and release-media binaries.
- `tools/check_publication_boundary.py` scans exact indexed bytes for prohibited paths, unapproved run artifacts, release media, credential containers, secret signatures, and workstation-specific paths.
- `security/owner-adr-signers.allowed` and `security/revoked-adr-signers` are public-only trust inputs and intentionally contain no key. Private signing material remains prohibited by path, suffix, and content scans.

Open N1 work: owner custody choice, owner-controlled commit/tag signing, a signed baseline tag, immutable release references, retained CI evidence, reviewer quorum, contributor policy, and legal/patent/export/trademark/component-license review remain open. Required signed commits must not be enabled until the existing unsigned setup history and merge strategy are resolved. Administrator enforcement and approval count must be revisited when another maintainer is configured.

Exit gate: PooleOS is source-controlled; every required decision has an owner and due gate; deletions and deferrals are reviewable; no component lacks licensing/provenance classification.

### N2 - Hardware Target, Laboratory, and Standards (`partial`)

Inherited sections: `005-007`, `146`, `169`.  
Goal: replace generic hardware assumptions with exact devices, lawful specifications, errata, safe test equipment, and support tiers.

Subphases:

- N2.1 Capture full PCIe, USB, ACPI, SMBIOS, UEFI, CPU feature, IOMMU, EDID, storage, firmware, topology, sensor, and power inventories for Tier 1.
- N2.2 Assign Tier 0 emulator, Tier 1 exact machine, Tier 2 controller-family, Tier 3 community-tested, Tier 4 best-effort, unsupported, and quarantined states.
- N2.3 Acquire a confirmed sacrificial SSD, two labeled USB devices, immutable recovery media, serial path, second-machine recovery, backups, UPS/power-cut apparatus, packet capture, and thermal/power measurement.
- N2.4 Build the standards register with revision, publication date, hash, license/access terms, errata, assumptions, supersession, and implementation owner.
- N2.5 Lock UEFI 2.11, ACPI 6.6, exact AMD64/AMD IOMMU manuals, SMBIOS 3.9, NVMe 2.2, xHCI 1.2, applicable USB/HID, TPM, network RFC, Unicode 17, POSIX Issue 8, VIRTIO 1.3, and exact device documents unless superseded through review.
- N2.6 Turn every undocumented register or observed firmware behavior into an explicit blocker or hardware-specific tested assumption.

Exit gate: Tier 0 and Tier 1 manifests are complete and hashed; destructive-test safety is accepted; every implementation phase has lawful normative references and errata tracking.

### N3 - Toolchain, Build, CI, and Low-Level Safety (`partial`)

Inherited sections: `008-011`.  
Goal: produce hermetic freestanding artifacts without host leakage and enforce low-level safety before hardware execution.

Subphases:

- N3.1 Decide the implementation-language split. Working candidate: memory-safe `no_std` Rust for architecture-independent kernel/services, constrained assembly for entry/switch paths, and C17 for `libpdc`; the ADR must compare assurance, ABI, compiler maturity, runtime, and from-scratch provenance.
- N3.2 Freeze target triples, calling conventions, object formats, code models, relocation, red-zone, floating/vector state, and debug/release profiles.
- N3.3 Build hermetic host tools, cross compiler, assembler, linker, archiver, sysroot, builtins, ABI headers, and image utilities with pinned hashes.
- N3.4 Generate structure offsets, syscall tables, capability rights, boot ABI, IPC layouts, error enums, and static assertions from canonical schemas.
- N3.5 Implement a dependency-accurate build graph for PooleBoot, PooleKernel, servers, drivers, libraries, assets, system/recovery images, tests, and ISO.
- N3.6 Enforce deterministic timestamps, archive order, paths, locale, timezone, user IDs, filesystem metadata, flags, environment, and offline release builds.
- N3.7 Add formatting, lint, static analysis, warning-as-error, UB/address/thread/memory sanitizers for host-portable code, stack reports, ABI checks, and artifact size budgets.
- N3.8 Define unsafe-code inventory, checked arithmetic, parser limits, MMIO access rules, volatile/atomic policy, lock rules, interrupt-context restrictions, and fatal undefined behavior policy.

Cycle 81 proposal evidence: ADR-0003 proposes Rust 2024 `no_std` for PooleBoot, PooleKernel, and privileged native services; bounded x86-64 assembly for architectural entry/switch paths; freestanding C17 for the portable PDC reference; and Python only for non-production host oracles. Official Rust documentation confirms the available `x86_64-unknown-uefi` PE32+ target, `efiapi` convention, and freestanding `x86_64-unknown-none` ELF64 target.

Cycle 82 qualification evidence:

- `specs/native-toolchain-lock.json` freezes the official dated Rust 1.97.0 channel manifest, rustup-init, rustc, Cargo, host standard library, and both target standard-library archive hashes.
- `specs/native-target-contract.json` freezes Rust 2024, `no_std`, panic abort, static link, calling conventions, PE32+/ELF64 formats, entry symbols, code/relocation models, red-zone policy, and pre-context floating/vector prohibition.
- `tools/bootstrap_native_toolchain.ps1` verifies official SHA-256 records and installs only under ignored workspace-local Rust/Cargo homes without global `PATH` mutation.
- Dependency-free empty PooleBoot and PooleKernel qualification crates build offline and locked in two distinct clean target directories.
- The PE32+ fixture is 3,072 bytes at `41E212DE8ADFF8F673B857C46EA9913F94A6B09C35567E2B5F289BDEB756DE45`; the ELF64 fixture is 984 bytes at `806660E6276777DC0023ED89379B0F94FDB5FF354325F5CABB6E808F94B27322`. Both pairs are byte-identical.
- The independent parser verifies machine, format, subsystem/type, entry, timestamp, imports/debug state, static segments, and bounded section layout. Host-path/runtime-library scans find zero hits. Injected host leakage, PE-for-ELF substitution, and truncated ELF controls are rejected.
- `runs/native_toolchain_qualification.json` is schema-validated and explicitly records one host, no functional boot, no kernel execution, no two-host completion, and no production promotion.

Open N3 work: a second clean host, detached-signature and source-rebuild provenance, freestanding C17, bounded assembly, ABI probes/headers, archive and image tools, QEMU/OVMF, generated ABI tables, complete build graph, static analysis, unsafe inventory, and the remaining section 008-011 requirements.

Cycle 83 control-plane validation passes 397 tests with one Windows symlink-permission skip, Doctor passes 198/198 checks against live PooleGlyph Phase 65, and the complete consistency release gate passes 63/63 checks over 58 artifacts while retaining 20 explicit gaps and `production_ready=false`. Exact public-index, release-gate, and handoff hashes are recorded in the Cycle 83 log after staging.

Exit gate: two clean host environments reproduce bootstrap tools and empty native images; host headers/libraries cannot leak; ABI fixtures pass independently; all generated inputs are declared.

### N4 - Emulation, Reference Devices, and Formal Models (`partial`)

Inherited section: `012`. Added: `ADD-ASSURE-001`, `ADD-VIRTIO-001`.  
Goal: create the disposable, observable environment in which native mechanisms can fail safely and repeatably.

Subphases:

- N4.1 Freeze QEMU machine, CPU, RAM, OVMF code/variables, q35 PCIe topology, serial, debug exit, and deterministic launch profiles.
- N4.2 Add OASIS VIRTIO 1.3 PCI transport and staged console, block, net, input, GPU, RNG, balloon, and IOMMU profiles.
- N4.3 Provide GDB/LLDB remote debugging, symbols, disassembly, QEMU tracing, serial capture, monitor control, deterministic seeds, snapshots, and packet/disk capture.
- N4.4 Provide malformed ACPI/SMBIOS/PCI/virtio/USB/storage/network fixtures and hardware-fault injection profiles.
- N4.5 Model capability derivation/revocation, IPC, scheduler, page mapping, boot slots, update rollback, and PooleFS transaction state before ABI freeze.
- N4.6 Record model assumptions and cross-check model traces against implementation traces; no proof claim extends beyond its configuration and assumptions.

Exit gate: one command launches each pinned native test profile; logs and artifacts are deterministic where declared; formal models have executable counterexample checks; no Buildroot guest is required.

### N5 - Boot Media, Boot Protocol, and PooleBoot UEFI Loader (`not_started`)

Inherited sections: `013-015`. Added: `ADD-BOOT-001`.  
Goal: author the complete firmware-to-kernel transition without third-party bootloader code in the production chain.

Subphases:

- N5.1 Define deterministic GPT/ESP/El Torito EFI media, partition GUIDs, labels, paths, alignment, and image inspection.
- N5.2 Build a PE32+ `PooleBoot.efi` with correct Microsoft x64 UEFI calling convention and no host runtime dependency.
- N5.3 Implement console, serial, watchdog, allocation, filesystem, GOP, RNG, TCG2, configuration-table, and protocol discovery with absent/malformed handling.
- N5.4 Define and fuzz a bounded boot configuration grammar; reject traversal, overflow, duplicate/unknown keys, truncation, incompatible versions, and oversized artifacts.
- N5.5 Validate and load relocatable ELF64 PooleKernel segments with bounds, alignment, BSS, relocations, W^X plan, physical/virtual bounds, and entry point.
- N5.6 Load signed initial-system, recovery, symbol, microcode, firmware-manifest, and policy artifacts according to profile.
- N5.7 Select a safe GOP mode, record exact framebuffer metadata, and retain text/serial fallback.
- N5.8 Retrieve and normalize the UEFI memory map, copy required tables, retry `ExitBootServices`, prohibit later boot-service use, and hand off only validated immutable records.
- N5.9 Implement normal, safe, previous-known-good, recovery, diagnostic, and firmware-setup entries with bounded boot attempts and physical-presence policy.

Exit gate: PooleBoot reproducibly boots under pinned OVMF and target firmware, validates all artifacts, exits boot services, transfers through a versioned golden-tested handoff, and rejects the complete hostile loader corpus.

### N6 - Boot Trust, Kernel Image, Early Runtime, and Emergency Diagnostics (`not_started`)

Inherited sections: `016-019`, `148-149`. Added: `ADD-BOOT-002`.  
Goal: make the earliest native path authenticated, measurable, diagnosable, and recoverable before higher services exist.

Subphases:

- N6.1 Define offline root, release intermediates, development keys, PK/KEK/db/dbx interaction, key rotation, revocation, compromised-key response, and development-mode visibility.
- N6.2 Verify boot manifest, kernel, initial system, recovery, modules if ever allowed, firmware, PDC, and PooleGlyph policy by artifact type and minimum secure version.
- N6.3 Measure configuration and artifacts through TCG2 with documented PCR/event semantics and preserve the event log for local verification.
- N6.4 Freeze kernel ELF layout, relocation, KASLR policy, section permissions, debug symbols, map files, build ID, unwind strategy, and read-only-after-init behavior.
- N6.5 Enter on a known stack with interrupts disabled; validate handoff, reserve every range, establish canonical mappings, initialize bootstrap GDT/IDT/TSS, and run early self-tests.
- N6.6 Implement allocation-independent serial, framebuffer, and ring-buffer logs; bounded formatting; panic codes; register/control-state/page-fault dumps; nested panic; double-fault/NMI paths; and next-boot panic summary.
- N6.7 Implement 16550-compatible emergency serial discovery plus RTC/CMOS and UEFI-variable access with locking, validation, write limits, rollback state, and wake-alarm boundaries.

Exit gate: every accepted boot is signature/digest/version bound; revocation and malformed signatures fail closed into recovery; deliberate failures at every early stage yield retained serial evidence without silent reset loops.

### N7 - x86-64 CPU, Privilege, Descriptor, and Fault Foundation (`not_started`)

Inherited sections: `020-022`.  
Goal: establish a correct processor contract before concurrency or user execution.

Subphases:

- N7.1 Enumerate CPUID leaves, topology, address widths, caches, APIC, NX, PCID, SMEP/SMAP/UMIP, FSGSBASE, XSAVE, entropy, virtualization, encryption, RAS, PMU, and thermal features.
- N7.2 Validate exact Ryzen 7 9800X3D family/model/stepping and microcode against errata; reject missing mandatory features precisely.
- N7.3 Define CR0/CR4/EFER, PAT/MTRR, syscall, GS, TSC_AUX, APIC, machine-check, and performance MSR policy with reserved-bit discipline.
- N7.4 Initialize x87/SSE/XSAVE state, per-thread vector areas, exception behavior, sensitive-state clearing, and kernel SIMD restrictions.
- N7.5 Build per-CPU GDT, TSS, RSP0, IST stacks, IDT stubs, uniform trap frames, and entry/exit assembly with generated offset validation.
- N7.6 Handle every architectural exception with user delivery or kernel panic policy, recursion limits, stack guards, and adversarial tests.

Exit gate: independent ABI fixtures validate every frame; deliberate exceptions behave correctly in kernel and user contexts; no reserved-bit, stack, vector-state, or privilege transition defect remains.

### N8 - Interrupts, Time, SMP, and CPU Lifecycle (`not_started`)

Inherited sections: `023-025`. Added: `ADD-TIME-001`.  
Goal: operate all target CPUs with correct interrupt routing and time domains.

Subphases:

- N8.1 Mask legacy PIC; initialize local APIC/x2APIC; parse MADT and overrides; configure I/O APIC; allocate vectors; handle spurious/error interrupts.
- N8.2 Implement MSI/MSI-X allocation, affinity, masking, teardown, and stale interrupt defense through capability-authorized operations.
- N8.3 Calibrate invariant TSC against HPET/PM timer as applicable; implement clocksource watchdog, timer queues, TSC deadline, and monotonic nanosecond APIs.
- N8.4 Separate monotonic, boottime, UTC, RTC, and civil time; handle invalid RTC, clock step, leap-second policy, suspend, and network synchronization without corrupting deadlines.
- N8.5 Discover CPU topology; allocate guarded per-CPU areas/stacks; start APs through trampoline/mailbox; verify features and time synchronization.
- N8.6 Implement IPIs for reschedule, TLB shootdown, call function, stop, panic, and diagnostics with timeout/failure behavior.
- N8.7 Implement idle states conservatively; defer hotplug until required by a later profile.

Exit gate: all 16 logical processors repeatedly start under Tier 0 and Tier 1 profiles; timer monotonicity, interrupt routing, IPI, and SMP stress tests pass with bounded skew and no lost/duplicate work.

### N9 - Physical and Virtual Memory, MMIO, Allocation, and Reclaim (`not_started`)

Inherited sections: `026-029`, `151`.  
Goal: make ownership, mapping, cacheability, allocation, reclaim, and OOM behavior explicit and testable.

Subphases:

- N9.1 Normalize overlapping UEFI/ACPI/firmware/kernel/framebuffer/device ranges with precedence rules and a reserved-range audit.
- N9.2 Implement a bounded bootstrap allocator and main physical-page allocator with zones, metadata protection, poisoning, double-free detection, quotas, and fragmentation metrics.
- N9.3 Freeze kernel/user virtual layouts, canonical-address policy, direct map, recursive/temp mappings if used, guard regions, and KASLR interactions.
- N9.4 Implement page-table allocation, map/unmap/protect, huge pages, PCID, shootdown, copy-on-write, user faults, stack growth, and pager protocol.
- N9.5 Implement kernel heap/object caches/stacks with red zones, quarantine, overflow checks, failure injection, and no hidden allocation in atomic paths.
- N9.6 Centralize PAT/MTRR/cacheability aliases and MMIO mapping; reject conflicting memory types.
- N9.7 Implement reclaim classes, watermarks, working-set replacement, slab reclaim, compaction, compressed memory/swap policy, pressure events, and deterministic OOM selection.

Exit gate: allocator/page-table invariants survive randomized and concurrent stress; no alias-cache conflict, stale mapping, use-after-free, unbounded reclaim, or OOM deadlock remains in supported profiles.

### N10 - Platform Discovery, ACPI, SMBIOS, PCIe, and Low-Speed Buses (`not_started`)

Inherited sections: `042-046`, `152`.  
Goal: create an authoritative hardware resource graph while keeping complex firmware parsing outside the microkernel where possible.

Subphases:

- N10.1 Define device objects, buses, resources, dependencies, firmware nodes, stable identities, driver matching, hotplug, quirk, power, and diagnostics schemas.
- N10.2 Validate RSDP/XSDT and required ACPI tables; parse MADT, MCFG, FADT, HPET, IVRS, TPM2, HEST, SRAT/SLIT/PPTT, SPCR/DBG2 as profile requires.
- N10.3 Run AML evaluation in a resource-bounded user-space service with namespace, region, mutex, recursion, timeout, side-effect, and fuzz controls.
- N10.4 Parse SMBIOS defensively for platform identity without treating strings as authorization.
- N10.5 Implement ECAM PCIe enumeration, bridges, BAR sizing/allocation, capabilities, MSI/MSI-X, AER, ACS, reset, power, and bus-master enable policy.
- N10.6 Add I2C/SMBus/SPI/GPIO/embedded-controller/Super I/O frameworks only for exact target needs, with electrical and firmware safety boundaries.
- N10.7 Publish the complete device/resource graph to the driver manager through a versioned read-only protocol.

Exit gate: Tier 0 and Tier 1 device graphs match independent host captures; malformed tables cannot escape parsers; PCI writes and ACPI methods require explicit capability and policy.

### N11 - DMA, IOMMU, and Interrupt Remapping (`not_started`)

Inherited section: `030`.  
Goal: make every device DMA operation an explicitly owned, revocable mapping.

Subphases:

- N11.1 Specify coherent and streaming DMA buffers, scatter/gather, boundaries, widths, bounce buffers, synchronization, ownership, and outstanding-map accounting.
- N11.2 Parse AMD IVRS, discover IOMMU units and aliases, create per-device/trust-group domains, and preserve only required firmware mappings.
- N11.3 Implement I/O page tables, map/unmap, invalidation, interrupt remapping, fault reporting, and quarantine.
- N11.4 Keep bus mastering disabled until domain attachment and buffers are valid; revoke before reset, driver death, or reassignment.
- N11.5 Test 32/64-bit DMA, stale descriptors, malicious addresses, reset races, mapping failure, IOMMU faults, and no-IOMMU restricted mode.

Exit gate: a hostile driver/device cannot DMA outside its granted pages or inject unowned interrupts; all mappings disappear on teardown; fault evidence names exact requester and authority.

### N12 - Concurrency, Scheduler, Deferred Work, and Context Switching (`not_started`)

Inherited sections: `031-034`.  
Goal: provide a deterministic neutral scheduler and auditable concurrency primitives before experimental policy.

Subphases:

- N12.1 Implement typed atomics and x86/compiler memory-order litmus tests with generated-assembly review.
- N12.2 Implement minimal spin/mutex/wait/notification primitives with ownership, rank, recursion, IRQ, sleep, priority-inheritance, contention, and deadlock diagnostics.
- N12.3 Select reclamation mechanisms only when required and state progress guarantees; prove and stress deferred reclamation.
- N12.4 Implement bounded interrupt-deferred work and kernel-internal workers with cancellation, flush, duplicate-queue, recursion, and reclaim safety.
- N12.5 Freeze scheduler entities, states, classes, priorities, fairness/starvation bounds, affinity, topology, preemption, accounting, and neutral fallback.
- N12.6 Implement run queues, wake/block/exit/migration, balancing, preemption entry points, stall watchdog, and invariant checks.
- N12.7 Implement context switching for general, segment, FS/GS, address-space, PCID, vector, debug, PMU, mitigation, and kernel-stack state.
- N12.8 Keep PDC scheduler proposals outside the kernel; admit only bounded policy requests through validated scheduler capabilities after N33 gates.

Exit gate: deterministic and randomized SMP schedule tests show no lost wakeup, duplicate runnable task, dead task, priority inversion violation, register leak, or starvation beyond declared bounds.

### N13 - Tasks, Syscalls, Events, and Capability Object Model (`not_started`)

Inherited sections: `035-038`. Added: `ADD-CAP-001`.  
Goal: enter user mode with an unforgeable authority model rather than Unix ambient privilege.

Subphases:

- N13.1 Define process/thread/task identity, ownership, lifecycle, address space, scheduling, accounting, audit, and generation-safe identifier behavior.
- N13.2 Implement spawn, thread create, executable replacement, exit, wait/reap, process-death cleanup, and failure at every allocation step.
- N13.3 Freeze `SYSCALL/SYSRET` entry ABI, register frame, error model, cancellation/restart semantics, tracing, compatibility negotiation, and safe `IRETQ` fallback.
- N13.4 Implement hardened copyin/copyout with canonicality, overflow, page-fault recovery, partial-copy policy, SMAP, and TOCTOU-safe pin/copy semantics.
- N13.5 Specify kernel object types and unforgeable capabilities with rights attenuation, derivation, transfer, revocation, generations, quotas, destruction, and audit provenance.
- N13.6 Define user exception, cancellation, process event, notification, and debugger delivery without Unix signals becoming the native authority model.
- N13.7 Prove and test no capability forging, rights amplification, stale-handle reuse, cross-process object confusion, or cleanup leak.

Exit gate: a static user task enters ring 3, performs capability-mediated syscalls, receives exceptions, exits cleanly, and cannot access any ungranted kernel object or memory.

### N14 - IPC, Identity, Isolation, Async I/O, and Resource Control (`not_started`)

Inherited sections: `039-041`, `163-164`. Added: `ADD-ABI-001`.  
Goal: make service composition fast, bounded, cancellable, and least-authority.

Subphases:

- N14.1 Define synchronous call/reply, one-way message, notification, shared-memory, stream, and local RPC primitives with explicit maximum sizes.
- N14.2 Define endpoint capabilities, sender identity, reply tokens, capability-transfer slots, delegation limits, deadline/cancellation, and priority propagation.
- N14.3 Implement generated IPC wire layouts and independent encode/decode fixtures; reject version, length, alignment, count, and capability mismatches.
- N14.4 Define credentials, users/groups, executable identity, service identity, audit identity, and login/session context as user-space policy over kernel identities.
- N14.5 Implement process/service/application isolation groups with CPU, memory, handle, IPC, storage, and device quotas and pressure notifications.
- N14.6 Implement readiness multiplexing, event objects, filesystem notification, and asynchronous completion queues without stale completions or lifetime ambiguity.
- N14.7 Add deterministic IPC trace/replay, saturation, priority inversion, dead peer, confused deputy, queue exhaustion, and cancellation-race tests.

Exit gate: isolated services communicate only through granted endpoints; quotas bound denial of service; cancellation and process death release all resources; capability flow is reconstructable from receipts.

### N15 - Security, Cryptography, TPM, Secrets, MAC, and Firmware Boundaries (`partial`)

Inherited sections: `107-112`, `155`. Added: `ADD-CPU-001`.  
Goal: establish threat-driven defense independently from PDC and presentation layers.

Subphases:

- N15.1 Threat-model malicious apps, parsers, devices, DMA, radios, networks, packages, builders, keys, firmware, physical access, rollback, side channels, denial, and PDC/PooleGlyph compromise.
- N15.2 Enforce W^X, NX, SMEP, SMAP, UMIP, KASLR, protected page tables, hardened copies, stack guards, read-only metadata, pointer redaction, CFI/control-flow defenses, and exact CPU mitigation policy.
- N15.3 Build entropy-source health, boot seeding, persistent reseed, readiness, fork/snapshot safety, and reviewed CSPRNG behavior.
- N15.4 Port or implement a reviewed crypto provider API for hash, MAC, AEAD, KDF, signatures, key agreement, constant-time operation, vector tests, and algorithm deprecation.
- N15.5 Implement TPM 2.0 discovery, bounded framing, PCR/event-log use, sealing with recovery, and parser fuzzing without making TPM the sole recovery path.
- N15.6 Implement secret and certificate stores, separate trust domains, trusted prompts, zeroization, dump/swap/log protection, distrust and update processes, and audited key use.
- N15.7 Define default-deny MAC labels and PooleGlyph policy compilation only after equivalent simulator, downgrade, signing, recovery, and fuzz gates.
- N15.8 Keep telemetry disabled by default and minimize, consent, bound, encrypt, retain, export, and delete any enabled data.
- N15.9 Bound UEFI runtime services, SMM, PSP/security coprocessor, firmware interfaces, and privileged update commands; treat opaque platform components as explicit assumptions.

Exit gate: independent review closes critical threat-model findings; crypto and RNG vectors/health pass; capability/MAC recovery cannot lock out the owner; exact CPU/firmware mitigation state is attested.

### N16 - Isolated Driver Domains and Extension Lifecycle (`not_started`)

Inherited section: `150`. Added: `ADD-VIRTIO-002`, `ADD-DRIVER-001`, `ADD-MODULE-001`.  
Goal: make every driver replaceable, bounded, revocable, and outside the kernel unless privilege is mathematically unavoidable.

Subphases:

- N16.1 Freeze driver manifest, match, protocol, resource request, firmware, dependency, version, health, reset, and compatibility schemas.
- N16.2 Implement driver manager creation of isolated address spaces and revocable MMIO/port/IRQ/DMA/reset capabilities.
- N16.3 Implement versioned bus/device service protocols and generated bindings; prohibit arbitrary register access through high-level policy.
- N16.4 Implement signed user-space driver packages, dependency resolution, staged activation, rollback, quarantine, crash-loop limits, and safe removal.
- N16.5 Implement virtio PCI transport and isolated console/RNG/balloon foundation, then shared queue libraries for block/net/input/GPU without trusting device lengths.
- N16.6 Revoke capabilities, disable bus mastering, drain/cancel work, invalidate DMA, reset hardware, and reject stale completions on driver death or upgrade.
- N16.7 Keep production kernel-module loading disabled. Any future exception requires a new TCB proof and release-profile review.

Exit gate: a deliberately crashed or hostile reference driver cannot corrupt kernel or peer memory; supervisor restart restores service or cleanly degrades without stale authority.

### N17 - Block Storage, Partitions, and Volume Management (`not_started`)

Inherited sections: `047-050`, `166`.  
Goal: establish correct durable block I/O before any native writable filesystem.

Subphases:

- N17.1 Define asynchronous block request, scatter/gather, flush, FUA, discard, zero, cancellation, timeout, retry, barrier, and completion semantics.
- N17.2 Implement virtio-blk reference driver and deterministic error device before physical storage.
- N17.3 Implement isolated NVMe controller discovery, admin queue, identify, namespace, I/O queues, PRP/SGL, MSI-X, reset, shutdown, SMART/health, and fault recovery for the Samsung 970 PRO profile.
- N17.4 Keep AHCI/SATA/ATAPI as profile-dependent later work; never let it delay the NVMe-first critical path.
- N17.5 Parse GPT/MBR defensively with overlap, overflow, duplicate GUID, hybrid, and malformed table handling.
- N17.6 Implement stacked volumes, loop images, RAID, snapshots, thin provisioning, encryption, and multipath only behind separately scoped profiles.
- N17.7 Preserve raw I/O traces and test timeout, reset, surprise removal, full device, corrupt completion, flush failure, and power loss on sacrificial media.

Exit gate: reference and Tier 1 storage read/write/flush semantics match independent tests; no production write occurs without explicit target identity and recovery evidence.

### N18 - USB, Input, and Removable Media (`not_started`)

Inherited sections: `051-057`, `165`.  
Goal: provide safe interactive input and removable-media handling without trusting device descriptors.

Subphases:

- N18.1 Implement virtio-input reference keyboard/pointer before physical USB.
- N18.2 Define USB device/config/interface/endpoint objects, descriptors, enumeration state, transfer ownership, and disconnect cancellation.
- N18.3 Implement isolated xHCI discovery, reset, rings, TRBs, contexts, events, root hubs, ports, timeouts, and controller recovery for exact AMD functions.
- N18.4 Implement hubs, HID parser, boot keyboard, pointer, generic input events, focus/security attribution, and simple PS/2 recovery input if target hardware exposes it.
- N18.5 Implement USB mass-storage BOT/SCSI subset after block-layer maturity; UASP remains optional.
- N18.6 Classify audio, CDC, camera, game controllers, printers, scanners, SD/eMMC, optical, Type-C/PD, USB4, and Thunderbolt by release profile and security boundary.
- N18.7 Fuzz all descriptors and events; test disconnect/reconnect, stalls, short packets, malicious lengths, hub depth, power budget, DMA, and device identity changes.

Exit gate: basic keyboard and pointer work through virtio and exact Tier 1 USB paths; malicious devices cannot escape driver domains; recovery input remains available.

### N19 - VFS, PooleFS, Page Cache, Encryption, and Persistent Data (`not_started`)

Inherited sections: `076-081`. Added: `ADD-FS-001`.  
Goal: provide a native crash-consistent storage model with explicit durability and repair semantics.

Subphases:

- N19.1 Define user-space VFS vnode/inode/file/mount/path/name-cache semantics, capabilities, metadata, links, rename, mount namespaces, and TOCTOU behavior.
- N19.2 Implement initramfs, tmpfs, device/system pseudo-filesystems, and read-only FAT32 ESP access first.
- N19.3 Specify PooleFS on-disk superblocks, checksummed metadata, allocation, directories, extents, files, sparse data, timestamps, xattrs, snapshots, quotas, and feature negotiation.
- N19.4 Specify transaction ordering, journal or copy-on-write choice, flush/FUA boundaries, fsync, rename atomicity, mount recovery, repair, bad blocks, and version upgrade.
- N19.5 Implement page cache, read-ahead, dirty accounting, writeback, file mappings, coherency, truncation, pressure integration, and direct-I/O exclusions.
- N19.6 Implement encryption and key lifecycle with recovery; swap/paging store stays disabled until encryption, crash, and secret-leak behavior is proven.
- N19.7 Run randomized model comparison, filesystem image fuzzing, full-volume/ENOSPC, corruption, repair, and automated power-cut matrices; retain every failing image.

Exit gate: PooleFS meets declared crash semantics on reference and sacrificial Tier 1 storage; repair is idempotent; no cross-file disclosure or silent durability downgrade remains.

### N20 - Executable Loader, User ABI, C Runtime, Threads, and Language Runtimes (`not_started`)

Inherited sections: `082-087`.  
Goal: run native static applications through stable, documented, capability-aware user interfaces.

Subphases:

- N20.1 Freeze user ELF64 validation, segment mapping, W^X, ASLR, stack/aux vector, capability bootstrap, TLS, relocations, and interpreter policy.
- N20.2 Start with static PIE executables; add a dynamic linker only after symbol/version/relocation/unload/thread safety and attack surface are justified.
- N20.3 Implement Poole-authored startup, termination, fundamental libc, checked memory/string, allocation, stdio, math, time, locale, Unicode, and error APIs.
- N20.4 Implement thread creation, TLS, mutex/condition/semaphore/once, cancellation, robust owner death, and scheduler interaction.
- N20.5 Publish a native API and POSIX compatibility matrix with exact semantics, omissions, errno mapping, conformance tests, and no implicit Linux ABI.
- N20.6 Support Rust and later language runtimes through the native ABI; keep runtime unwinding, GC, JIT, executable memory, and signal assumptions explicit.
- N20.7 Build ABI compatibility, symbol, layout, syscall, and independent assembly fixtures into CI.

Exit gate: static native programs spawn, allocate, use files/IPC/threads, fail cleanly, and remain ABI-compatible across the declared version range.

### N21 - Init, Services, Utilities, Logging, Device Policy, and Integrity Maintenance (`not_started`)

Inherited sections: `088-092`, `141`, `158`, `168`.  
Goal: boot the native system deterministically into supervised services with observable health and repair.

Subphases:

- N21.1 Build essential filesystem, process, text, diagnostic, and recovery utilities without requiring a shell for system operation.
- N21.2 Implement PID 1/root supervisor responsibilities, declarative service graph, transactions, readiness, dependencies, timeouts, restart, crash loops, resource groups, and emergency mode.
- N21.3 Define exact boot order from kernel handoff through resource manager, driver manager, storage, VFS, logging, identity, network, display, session, PDC, and optional services.
- N21.4 Implement structured logging, persistent journal, security audit, rate limiting, rotation, redaction, integrity, support bundles, and serial fallback.
- N21.5 Implement user-space device policy, firmware loading, hotplug, seat/session attribution, and driver quarantine.
- N21.6 Implement system/session IPC bus, service naming, activation, discovery, introspection, authorization, bounded messages, and cycle detection.
- N21.7 Implement scheduled maintenance and integrity health service for boot images, filesystem, packages, configuration, certificates, updates, backups, PDC rollback, and bounded self-tests.

Exit gate: repeated boot reaches the same service graph; failures degrade or recover according to policy; no service can silently claim readiness; support evidence identifies every transition.

### N22 - Authentication, Sessions, Shell, Terminal, Accounts, and User Data (`not_started`)

Inherited sections: `093-094`, `157`, `162`, `167`.  
Goal: provide a usable local multi-process environment without collapsing authority into a universal root shell.

Subphases:

- N22.1 Define local accounts/groups, stable IDs, password/credential hashing, lockout, recovery, TPM-assisted options, and migration.
- N22.2 Implement trusted login, session creation, seat/device assignment, environment, capability grants, lock, logout, and privilege elevation with audit.
- N22.3 Implement kernel virtual console, PTYs, terminal line discipline, signals/job-control compatibility, shell parser/execution, pipelines, redirection, quoting, and bounded startup files.
- N22.4 Implement terminal emulator parsing, Unicode cell model, grapheme width, bidi safety policy, input methods, selection, clipboard, resizing, and accessibility semantics.
- N22.5 Implement name-service/account database interfaces and optional directory integration without making network identity necessary for local recovery.
- N22.6 Define home directory, XDG-like data/config/cache/state, MIME, associations, recent documents, session restore, privacy, and backup inclusion.

Exit gate: an authenticated user can operate shell and terminal, launch isolated services/apps, lock/logout, recover credentials, and never inherit undeclared device or system authority.

### N23 - Packages, Updates, Installer, Recovery, Backup, and Migration (`not_started`)

Inherited sections: `095-098`, `159`. Added: `ADD-UPDATE-001`, `ADD-RECOVERY-001`.  
Goal: install, update, roll back, recover, and restore without trusting the network or mutable system under repair.

Subphases:

- N23.1 Freeze signed package format, canonical metadata, dependencies, capabilities, services, files, scripts or script prohibition, conflicts, receipts, uninstall, and transactional database.
- N23.2 Implement repository roles modeled on TUF root/targets/snapshot/timestamp with threshold keys, expiry, consistent snapshots, delegated targets, rollback/freeze/mix-and-match protection, and offline root rotation.
- N23.3 Implement immutable A/B system images, pending/healthy state, boot attempts, minimum secure versions, configuration/data migration, automatic rollback, and failed-update diagnostics.
- N23.4 Build installer in an isolated environment with exact-disk identity, backup checks, partition plan preview, encryption, format/populate/verify, boot entry, first boot, cancellation, and power-loss recovery.
- N23.5 Build separately signed recovery with read-only diagnostics, slot selection, boot repair, filesystem check, package rollback, key recovery, data export, reinstall/reset, and serial/GOP operation.
- N23.6 Implement snapshots, backup policy, encrypted/deduplicated backup, application quiescence, integrity verification, restore sampling, disaster recovery, synchronization, and migration.
- N23.7 Test malicious metadata, compromised online keys, stale mirrors, full disks, interruption at every transaction step, broken configuration, and recovery without normal services.

Exit gate: no single online key or mirror can install arbitrary/stale software; every failed install/update returns to a bootable signed state; sampled backups restore correctly.

### N24 - Shutdown, Power, Firmware Updates, Sensors, and Hardware Health (`not_started`)

Inherited sections: `099-100`, `153-154`.  
Goal: control power and firmware only through exact, fail-safe platform knowledge.

Subphases:

- N24.1 Implement ordered shutdown/reboot with session notice, service stop, storage flush, device quiesce, watchdog handling, ACPI reset/power-off, and timeout escalation.
- N24.2 Add suspend only after device save/restore, wake routing, time correction, key handling, and repeated target-hardware tests; hibernation remains post-v1 unless explicitly promoted.
- N24.3 Implement CPU idle/frequency, PCI/device power, thermal zones, fans, energy accounting, and conservative failsafe limits without undocumented voltage/clock writes.
- N24.4 Inventory firmware/microcode; implement signed staged CPU microcode and device update frameworks with compatibility, antirollback, power prerequisites, progress, recovery, and audit.
- N24.5 Treat UEFI capsule/ESRT updates as profile-dependent high-risk work requiring exact board documentation and an independent firmware recovery path.
- N24.6 Implement sensor, fan, battery/storage/chassis health, hardware watchdog, missing-sensor semantics, rate limiting, and user notification.

Exit gate: shutdown/reboot never corrupt supported filesystems; thermal and watchdog safety does not depend on PDC; interrupted firmware update cannot silently brick a supported profile.

### N25 - Ethernet, Wi-Fi, Bluetooth, and Link Drivers (`not_started`)

Inherited sections: `063-066`.  
Goal: expose network links through isolated drivers with exact firmware/regulatory scope.

Subphases:

- N25.1 Define network-device queues, buffers, offloads, MTU, addresses, link state, statistics, cancellation, reset, and zero-copy ownership.
- N25.2 Implement virtio-net as the Tier 0 reference path with hostile descriptor/device tests.
- N25.3 Implement an isolated Realtek RTL8125 Tier 1 driver using lawful documentation, DMA confinement, MSI-X, PHY/link state, reset, and packet checks.
- N25.4 Implement Ethernet framing, VLAN boundary, multicast filters, MTU, checksums, and capture interfaces.
- N25.5 Treat Realtek 8851BE Wi-Fi as a later profile: firmware rights, regulatory database, radio kill, scan/auth/association, WPA2/WPA3, replay protection, data path, roaming, and hostile AP tests are all mandatory before support.
- N25.6 Treat Realtek USB Bluetooth as a later profile: HCI transport, L2CAP, security manager, GATT, HID, privacy, pairing, key storage, and hostile peer tests precede optional audio.

Exit gate: virtio-net and selected Tier 1 Ethernet maintain isolation and recover from driver/device failure; radio features are absent or explicitly unsupported until fully qualified.

### N26 - Network Protocols, Services, Firewall, TLS, and Virtual Links (`not_started`)

Inherited sections: `067-075`, `156`.  
Goal: implement a standards-bound interoperable stack with adversarial packet safety.

Subphases:

- N26.1 Define reference-counted packet buffers, interface/route tables, neighbor state, checksums, MTU, fragmentation, reassembly bounds, queueing, and tracing.
- N26.2 Implement ARP, IPv4, ICMPv4, IPv6, ICMPv6, Neighbor Discovery, SLAAC, PMTU, duplicate-address detection, and extension-header policy.
- N26.3 Implement UDP and TCP state, options, retransmission, congestion/flow control, timers, windows, teardown, resource bounds, and interoperability.
- N26.4 Implement capability-aware sockets, names, readiness/async I/O, local binding, ancillary data, raw access policy, and error queues.
- N26.5 Implement DHCPv4/v6, DNS with cache and DNSSEC policy, NTP/NTS policy, network manager, profiles, captive/metered state, and offline behavior.
- N26.6 Implement firewall/packet filtering, connection tracking only if justified, NAT, VPN interface boundary, loopback, packet capture, multicast, VLAN/bridge, tunnels, QoS, and traffic control by profile.
- N26.7 Port reviewed TLS 1.3 and certificate validation through N15; package authenticity remains independent of transport security.
- N26.8 Fuzz every protocol and test loss, reordering, duplication, fragmentation, exhaustion, hostile peers, and independent-stack interoperability.

Exit gate: supported protocols interoperate and survive hostile corpora without memory/authority escape; signed packages fetch over untrusted networks and still verify offline.

### N27 - Display Bootstrap, Virtio GPU, and Native Graphics Research (`not_started`)

Inherited sections: `058-061`. Added: `ADD-GPU-001`.  
Goal: deliver reliable software graphics first and isolate all accelerated graphics risk.

Subphases:

- N27.1 Preserve GOP framebuffer metadata and a permanent safe mode independent of native GPU code.
- N27.2 Implement pixel formats, clipping, damage, blits, alpha, scaling, color conversion, text primitives, double buffering, and deterministic reference images in a software renderer.
- N27.3 Parse EDID/DisplayID only from lawful specs with strict bounds and safe fallback modes.
- N27.4 Implement isolated virtio-gpu 2D resource/scanout/cursor/fence path before physical acceleration.
- N27.5 Define native GPU kernel mediation only for capabilities, MMIO/IRQ/DMA assignment, memory objects, command buffers, fences, reset, and accounting; command validation lives outside PooleKernel.
- N27.6 Keep RTX 5070 work a legal/documentation/firmware research lane: connector/scanout, memory, copy, command submission, synchronization, reset, and conformance cannot gate recovery or initial release.
- N27.7 Define native graphics API and shader/SPIR-V/Vulkan/OpenGL compatibility only after security, memory, synchronization, and conformance strategy is accepted.

Exit gate: software and virtio graphics display deterministic frames, recover from compositor/driver failure, and preserve serial/GOP recovery. RTX claims require exact hardware and independent output evidence.

### N28 - Audio, Media Policy, and Optional Peripherals (`not_started`)

Inherited sections: `062`, `104-105`.  
Goal: provide safe bounded audio while keeping optional device classes out of the boot path.

Subphases:

- N28.1 Define audio device/stream/buffer/format/clock/xrun/mixer/capture/security APIs and DMA ownership.
- N28.2 Select one exact Tier 1 HDA controller/codec path, likely Realtek `DEV_0897`, before NVIDIA HDA or USB audio expansion.
- N28.3 Implement isolated HDA reset, CORB/RIRB, codec discovery, widgets/routes, stream descriptors, interrupts, jack state, and timeout recovery.
- N28.4 Implement user-space audio server with per-app permissions, mixing, resampling, routing, volume limits, privacy indicators, latency and glitch budgets.
- N28.5 Treat printing, scanning, camera, capture, codecs, and media services as profile-scoped ports with sandboxed parsers and explicit patent/license review.

Exit gate: selected playback/capture path meets glitch, latency, privacy, and crash-recovery gates; malformed streams/codecs cannot escape service sandboxes.

### N29 - Compositor, Text, Desktop, GUI Toolkit, and Accessibility (`not_started`)

Inherited sections: `101-103`, `160-161`. Added: `ADD-UI-001`.  
Goal: build the original PooleGlass desktop and Liquid Glass identity on native services with accessible fallbacks.

Subphases:

- N29.1 Freeze a capability-authenticated display protocol for surfaces, buffers, damage, input, focus, clipboard, drag/drop, portals, security labels, and version negotiation.
- N29.2 Implement compositor scene graph, software composition, occlusion, transforms, clipping, frame callbacks, presentation timing, direct scanout gates, and crash recovery.
- N29.3 Implement window/session policy, trusted system UI, notifications, settings, task switching, multi-display rules, safe mode, and anti-spoofing boundaries.
- N29.4 Port or implement font rasterization/shaping with Unicode 17 segmentation, normalization, bidi, line breaking, fallback, locale, input method, and security handling.
- N29.5 Build the native GUI toolkit, layout, controls, theming, accessibility semantics, clipboard, drag/drop, portals, and desktop IPC.
- N29.6 Implement original Liquid Glass materials with bounded blur/transparency, balanced palette, stable dimensions, no information-obscuring effects, and CPU/GPU/memory/power budgets.
- N29.7 Implement keyboard-only operation, focus, magnification, high contrast, text scaling, color-vision modes, screen reader, speech/captions, braille boundary, reduced transparency/motion, and automated/manual accessibility suites.
- N29.8 Implement a static firmware-safe PooleOS mark, early-userspace animated Liquid Glass boot identity, reduced-motion/static fallback, serial diagnostics, and signed stage markers outside presentation.

Exit gate: the complete desktop runs through software rendering at minimum profile, survives compositor/GPU failure, passes accessibility and anti-spoofing gates, and never makes animation evidence of boot correctness.

### N30 - Application Model, SDK, Sandboxing, and Porting (`not_started`)

Inherited section: `106`.  
Goal: let developers build native applications without bypassing capabilities, packages, portals, or update policy.

Subphases:

- N30.1 Freeze native application ABI, executable/package identity, lifecycle, activation, single-instance, background, URL/MIME, notification, and settings contracts.
- N30.2 Build SDK/sysroot, headers, generated IPC bindings, templates, compiler/linker profiles, debugger, emulator, docs, examples, and ABI checker.
- N30.3 Define signed capability manifests, sandbox roots, device/network/file/clipboard portals, user consent, revocation, quotas, and audit.
- N30.4 Add application crash, update, migration, uninstall, data retention, backup, and compatibility behavior.
- N30.5 Port third-party libraries/apps only through provenance, license, sandbox, test, and native-ABI adaptation; emulation/compatibility layers remain optional post-v1 services.

Exit gate: an independently built sample app installs, runs, updates, rolls back, and uninstalls without undeclared authority or host dependencies.

### N31 - Debugging, Crash Analysis, Tracing, and Performance Methodology (`partial`)

Inherited sections: `113-116`.  
Goal: make native failures and performance claims reproducible from retained evidence.

Subphases:

- N31.1 Generate split symbols, build IDs, source maps, unwind data, symbol server/index, and release/debug correspondence.
- N31.2 Implement serial and remote kernel debugger with CPU/task/memory/register/breakpoint/watchpoint controls and authentication boundary.
- N31.3 Implement user debugger, core dumps, secret redaction/encryption, quotas, and symbolized postmortem tools.
- N31.4 Implement kernel crash dumps to reserved memory/storage/network only after recursion, corruption, and privacy behavior is tested.
- N31.5 Build trace buffers, event schemas, clock correlation, loss accounting, privilege filters, required scheduler/IPC/memory/IRQ/driver/storage/network/PDC events, and export.
- N31.6 Expose PMU and system metrics with virtualization, multiplexing, overflow, side-channel, and measurement-overhead controls.
- N31.7 Freeze benchmark hypotheses, controls, warmup, sample size, statistics, outliers, thermal/power state, correctness equivalence, total cost, raw data, and independent reproduction.

Exit gate: every release crash and performance result is tied to exact symbols, build, hardware, trace loss, methodology, raw data, and claim boundary.

### N32 - PDC Canonical Mathematics, Portable Runtime, and Guarded Backends (`partial`)

Added requirement: `ADD-PDC-001`.  
Goal: carry validated PDC mathematics into native deterministic execution without changing its claim boundaries.

Subphases:

- N32.1 Preserve locked source intake, formulas, matrices, exact verifier packages, representation tags, golden/metamorphic vectors, Q/P, and finite claim boundaries.
- N32.2 Complete source-bound signed dynamics and benchmark reproduction before native port promotion.
- N32.3 Freeze a portable deterministic C17 `libpdc` ABI with fixed widths, explicit buffers, no hidden allocation, checked arithmetic, scalar reference, and stable errors.
- N32.4 Differentially test host Python, portable C, PooleOS user-space scalar, SIMD, RAM-pool, GPU, and bounded rescue paths against identical vectors.
- N32.5 Implement CPU route candidates only after output equivalence, setup cost, repetitions, confidence, invalidation, regret, and rollback gates.
- N32.6 Implement RAM pools with ownership, alignment, NUMA, lifetime, zeroization, poisoning, retention, pressure, and fallback gates.
- N32.7 Implement GPU routes only after resident eager kernels, transfer accounting, guard profiles, reset/failure recovery, deterministic outputs where declared, and CPU fallback.
- N32.8 Keep Q/P classical and measured-field scoped; no finite benchmark becomes a universal physical, quantum, medical, financial, or hardware claim.

Exit gate: every supported native backend matches the canonical oracle and survives invalidation/failure; signed dynamics are reproduced; no optimizer can bypass capabilities or correctness checks.

### N33 - PDC Native Control Plane and Bounded Actuation Lanes (`partial`)

Inherited sections: `117-123`.  
Goal: integrate PDC as observable, proposal-first, capability-separated services rather than kernel policy.

Subphases:

- N33.1 Define immutable versioned observations, units, validity, uncertainty, missing data, sampling, overhead, and privacy.
- N33.2 Build topology/model service for CPUs, memory, devices, queues, workloads, locality, dependency, contention, defect confidence, decay, divergence, and bounded snapshots.
- N33.3 Run planner with no hardware authority; produce signed immutable proposals with preconditions, expected benefit, cost, duration, invariants, rollback, conflicts, evidence, and expiry.
- N33.4 Run independent policy gate to authenticate, validate schema/target/ownership/action/state/budget/fairness/thermal/security/consent/rollback/watchdog and fail closed.
- N33.5 Give each actuator only lane-specific capabilities; capture prestate, lease resource, apply the smallest action, verify, expire, cancel, restore, and receipt every operation.
- N33.6 Run an independent watchdog that can roll back and disable a lane without planner, actuator, GUI, or network.
- N33.7 Implement observation first, proposal second, then one reversible actuator at a time across CPU, memory, storage, network, GPU/display, and startup lanes.
- N33.8 Require neutral/conventional controls, total-cost accounting, output equivalence, repeated trials, bounded promotion, expiry, and automatic demotion.

Exit gate: observation and proposal modes are safe under hostile inputs; each promoted actuator has independent rollback and watchdog; PDC has no authority over boot trust, recovery, keys, thermal hard limits, or firmware flashing.

### N34 - PooleGlyph, PGB2, PGVM2, and System Policy (`blocked`)

Inherited section: `124`. Added: `ADD-PGL-001`.  
Goal: turn PooleGlyph from metadata-rich language evidence into a bounded executable system language and policy layer.

Subphases:

- N34.1 Continue tandem development from live Phase 65 and complete Phase 66 executable Core IR audit without rewriting user-generated evidence.
- N34.2 Freeze grammar, Unicode, tokens, precedence, declarations, modules, visibility, types/effects, capabilities, resources, permissions, lifecycle, services, packages, deployment, policy, contracts, and compatibility.
- N34.3 Harden source loader, lexer, parser, recovery, spans, AST, name/module resolution, type/effect/capability checks, constant evaluation, cycle checks, lint/format/LSP, and fuzz/differential tests.
- N34.4 Freeze deterministic Core IR and independently validate lowering, canonical serialization, policy/service/resource/deployment forms, explanations, hashes, and signatures.
- N34.5 Freeze PGB2 binary package framing, sections, canonical bytes, digests, signatures, version/feature negotiation, capability declarations, resource limits, trace and replay.
- N34.6 Implement PGVM2 verifier and bounded deterministic runtime with typed instructions, memory, stack, calls, traps, quotas, deadlines, cancellation, cleanup, host calls, and no ambient kernel/device access.
- N34.7 Generate only declarative kernel boot policy and user-space service manifests; policy application is transactional, signed, simulated, rollbackable, bounded, and safe-mode optional.
- N34.8 Build compiler, package, formatter, linter, simulator, debugger, trace, diff, migration, test, docs, standard library, compatibility, and publisher tools.

Exit gate: Phase 66 promotion is accepted; PGB2/PGVM2 v1 is frozen; independent verifier rejects malformed/over-authorized programs; native runtime passes replay, resource, cancellation, and hostile host-call tests; recovery does not require PooleGlyph.

### N35 - Reliability, Watchdogs, Fault Containment, Virtualization, and RAS (`partial`)

Inherited sections: `125-127`.  
Goal: contain failure locally and preserve evidence before considering reboot.

Subphases:

- N35.1 Implement scheduler, service, storage, GPU, network firmware, PDC, and exact hardware watchdogs with independent ownership and false-positive tests.
- N35.2 Escalate from local cancel/restart/reset through degraded mode, quarantine, safe-mode reboot, and loop prevention; persist exact reason and counts.
- N35.3 Define service and driver state-reconstruction contracts so restart never reuses stale handles, DMA, transactions, or completions.
- N35.4 Initialize machine-check/RAS, APEI/HEST, PCIe AER, NVMe health, ECC if exposed, bad-page retirement, device quarantine, and persistent error records.
- N35.5 Keep AMD SVM/hypervisor support optional and outside v1 TCB unless a later profile needs it; fuzz VM exits, hypercalls, emulation, assignment, and snapshots.
- N35.6 Run long-duration failure storms and verify bounded recovery, no reboot loops, no hidden data loss, and useful user diagnostics.

Exit gate: supported failures either recover locally or enter a known safe state; integrity uncertainty stops operation; no watchdog/planner/actuator can suppress independent recovery.

### N36 - Verification, Fuzzing, Fault Injection, Security, and Conformance (`partial`)

Inherited sections: `128-134`, `140`. Added: `ADD-ASSURE-002`, `ADD-TEST-001`.  
Goal: apply a universal evidence contract to every component and the integrated system.

Subphases:

- N36.1 Build host unit, kernel in-situ, user-space, property, model-based, ABI, parser, crypto, time, Unicode, PooleGlyph, and PDC tests.
- N36.2 Build bootloader-kernel, kernel-init, process/IPC, driver/device, storage/FS, network/TLS, display/input/audio, package/update, installer/recovery, and PDC integration tests.
- N36.3 Build cold/warm/repeated boot, CPU/RAM bounds, full disk, missing/failed devices, malformed media, revoked update, service/driver crash, safe mode, previous slot, recovery, and soak tests.
- N36.4 Fuzz every parser and boundary listed in section 129 with seed retention, coverage, minimization, deduplication, sanitizer and disposable-native-VM execution.
- N36.5 Inject every failure listed in section 130 plus schedule, capability revocation, stale reply, DMA lease, driver restart, and model divergence failures.
- N36.6 Run automated storage power-cut/corruption tests across all declared durability boundaries and retain disk images/health logs.
- N36.7 Run static and dynamic security, privilege, auth, permission, sandbox, package/update/boot, DMA/USB/network/radio, TOCTOU, secret, dump/log, and external review.
- N36.8 Run exact firmware/hardware, protocol interoperability, POSIX subset, graphics API, upgrade, accessibility, and published support conformance.
- N36.9 Add schedule exploration, mutation testing, symbolic execution where tractable, formal model counterexamples, and proof-assumption checks.
- N36.10 Apply section 140 definition of done to every component; no happy-path-only promotion.

Exit gate: all required suites pass from clean inputs; failures and flakes are retained and classified; external review closes critical/high findings; no coverage claim exceeds measured evidence.

### N37 - Supply Chain, Release, Signing, Operations, Documentation, and Manifest (`partial`)

Inherited sections: `135-139`, `147`. Added: `ADD-SUPPLY-001`.  
Goal: make every released byte attributable, reproducible, reviewable, revocable, supportable, and recoverable.

Subphases:

- N37.1 Generate complete source/dependency/firmware/data inventories, SPDX 3.0.1 SBOM, vulnerabilities, licenses, patches, and reproducibility metadata.
- N37.2 Generate SLSA 1.2 source/build provenance and in-toto-style signed links across checkout, code review, build, test, image, sign, publish, and independent verification.
- N37.3 Define versions, channels, support lifetimes, compatibility promises, release branches, freeze, candidate, reproducibility, security, performance, accessibility, hardware, and rollback gates.
- N37.4 Separate offline root, online metadata, boot, package, update, receipt, and development keys; document ceremony, quorum, backup, rotation, revocation, expiry, destruction, and incident drills.
- N37.5 Generate the complete section 147 release manifest including exact bootloader/kernel/system/recovery/driver/firmware/ABI/PooleGlyph/PDC/SBOM/provenance/test/benchmark/signature fields.
- N37.6 Publish architecture, boot, kernel, driver, ABI, filesystem, package/update, security, privacy, recovery, admin, SDK, compatibility, hardware, release, and incident documentation.
- N37.7 Establish vulnerability intake, CVE response, telemetry/privacy operation, update revocation, support bundles, disaster recovery, and maintenance ownership.

Exit gate: an independent verifier can reconstruct every release artifact and approval from immutable signed records; key compromise and revocation drills pass; support and recovery documentation is complete.

### N38 - Dependency Milestones, Hardware Qualification, and Readiness Gates (`not_started`)

Inherited sections: `142-145`.  
Goal: turn thousands of leaf requirements into measurable demonstrations without weakening their gates.

Subphases:

- N38.1 Reissue milestone 0 as native constitution/toolchain/QEMU reproducibility.
- N38.2 Demonstrate PooleBoot UEFI proof of life in OVMF and target firmware.
- N38.3 Demonstrate PooleKernel entry, exceptions, memory, panic, interrupts, time, and SMP.
- N38.4 Demonstrate ring 3, capabilities, IPC, root task, driver domains, and service restart.
- N38.5 Demonstrate virtio and exact Tier 1 storage/input/network paths before wider hardware.
- N38.6 Demonstrate PooleFS persistent root, power-loss recovery, userland, service manager, login, shell, package, and update.
- N38.7 Demonstrate software desktop, Liquid Glass fallback, accessibility, audio, and selected connectivity.
- N38.8 Demonstrate observer-only PDC, signed receipts, one bounded actuator, watchdog, and rollback.
- N38.9 Pass first physical boot checklist with exact firmware/device IDs, immutable media hash, serial/graphical logs, shutdown, reboot, and safe mode.
- N38.10 Pass daily-driver gate only after data-loss, boot-loop, privilege, recovery, update, device, accessibility, and soak blockers are closed.
- N38.11 Pass public alpha gate only with installer/recovery safety, signed media, exact limitations, support path, and incident readiness.

Exit gate: every readiness label is generated from leaf evidence and exact hardware profiles; emulator, one boot, or one machine never becomes a general compatibility claim.

### N39 - Reproducible Signed Native ISO and Production Release (`not_started`)

Added requirement: `ADD-REPRO-001`.  
Goal: deliver the exact native PooleOS bytes users boot, install, recover, verify, and reproduce.

Subphases:

- N39.1 Freeze UEFI-only ISO profile, El Torito EFI image, GPT/ESP layout, deterministic volume metadata, boot paths, system/recovery slots, and source archive placement.
- N39.2 Assemble only PooleBoot, PooleKernel, native system bundles, native drivers/services, PooleGlyph/PGB2/PGVM2, PDC, PooleGlass, installer, recovery, manifests, and permitted third-party assets.
- N39.3 Prove architecture conformance: no Linux kernel, Buildroot rootfs, Debian package database, GRUB/Limine, systemd, or undeclared host artifact exists.
- N39.4 Reproduce unsigned artifacts and ISO bytes on two clean independent builders; document signing timestamp/determinism boundaries and bind exact signed outputs.
- N39.5 Sign bootloader, manifest, kernel, system, recovery, packages, update metadata, SBOM, provenance, and final ISO/checksum records through the release ceremony.
- N39.6 Boot the exact signed ISO from clean media across every declared OVMF/QEMU CPU, RAM, firmware, graphics, storage, network, and fault profile.
- N39.7 Boot and operate the exact signed ISO on every Tier 1 physical profile; test live, install, first boot, normal/safe/previous/recovery, shutdown/reboot, update/rollback, damaged media, and unsupported hardware.
- N39.8 Verify distributed bytes equal tested/signed bytes and publish source, checksums, signatures, manifest, SBOM, provenance, limitations, hardware matrix, recovery, and support lifecycle.

Exit gate: all N0-N39 required gates are complete; independent clean builds reproduce declared bytes; exact distributed signed media boots and recovers in every supported profile; external release review accepts the evidence; `production_ready=true` is signed for that exact ISO hash only.

## 10. Added Research Requirements

The coverage ledger records 25 additions with phase, requirement text, and basis. The most consequential additions are:

- an explicit microkernel TCB partition and Linux/Buildroot exclusion;
- formal models and proof-assumption records for capabilities, IPC, VM, scheduler, boot/update, and filesystem state;
- OASIS VIRTIO 1.3 reference-device support;
- capability derivation, attenuation, transfer, revocation, and no ambient authority;
- user-space driver domains with DMA/IRQ/MMIO leases and no v1 loadable kernel modules;
- Secure Boot key/revocation/antirollback state modeling;
- CPU transient-execution/control-flow mitigation matrix tied to exact microcode;
- TUF-style compromise-resilient update roles;
- in-toto links, SLSA 1.2 provenance, and SPDX 3.0.1 SBOM;
- property/model/mutation/symbolic/schedule testing beyond conventional unit and fuzz suites;
- permanent GOP/software/virtio graphics independent from RTX research;
- PGB2/PGVM2 binary/VM freeze after PooleGlyph Phase 66;
- exact-byte independent native ISO reproduction.

Primary research references include:

- UEFI 2.11: `https://uefi.org/specs/UEFI/2.11/`
- ACPI 6.6: `https://uefi.org/specs/ACPI/6.6/`
- OASIS VIRTIO 1.3: `https://docs.oasis-open.org/virtio/virtio/v1.3/virtio-v1.3.html`
- seL4 assurance and proof-boundary references: `https://sel4.systems/Verification/`
- TUF specification: `https://theupdateframework.github.io/specification/`
- in-toto specification: `https://github.com/in-toto/docs/blob/master/in-toto-spec.md`
- SLSA 1.2: `https://slsa.dev/spec/v1.2/`
- SPDX 3.0.1: `https://spdx.github.io/spdx-spec/`
- POSIX.1-2024 Issue 8: `https://pubs.opengroup.org/onlinepubs/9799919799/`
- Unicode 17: `https://www.unicode.org/versions/Unicode17.0.0/`

seL4 is an assurance and architecture reference only. PooleKernel remains an original PooleOS implementation unless a future reuse ADR deliberately changes that decision.

## 11. Critical Stop-Ship Flags

| Flag | Class | State | Closure condition |
|---|---|---|---|
| `FLAG-NATIVE-SCM-001` | STOP_SHIP | Open | Put PooleOS under reviewed source control with immutable release revisions |
| `FLAG-NATIVE-ADR-001` | BLOCKER | Open | Ratify kernel, reuse, language, TCB, ABI, driver, filesystem, and release ADRs |
| `FLAG-NATIVE-BOOT-001` | STOP_SHIP | Open | Reproducible PooleBoot PE32+ boots and transfers through the frozen handoff |
| `FLAG-NATIVE-KERNEL-001` | STOP_SHIP | Open | PooleKernel boots, enforces memory/capabilities/IPC, and runs ring 3 |
| `FLAG-NATIVE-IOMMU-001` | STOP_SHIP | Open | DMA and interrupt remapping confine every bus-mastering driver |
| `FLAG-NATIVE-DRIVER-001` | STOP_SHIP | Open | User-space driver domains survive crash/reset/revoke without stale authority |
| `FLAG-NATIVE-FS-001` | STOP_SHIP | Open | PooleFS durability and repair pass randomized power-cut testing |
| `FLAG-NATIVE-UPDATE-001` | STOP_SHIP | Open | Signed A/B update, rollback, key compromise, and recovery tests pass |
| `FLAG-NATIVE-SEC-001` | STOP_SHIP | Open | Threat model, crypto/RNG, boot trust, isolation, and external review gates pass |
| `FLAG-NATIVE-UI-001` | REQUIRED | Open | Native PooleGlass and accessibility/fallback paths pass supported profiles |
| `FLAG-NATIVE-PGL-001` | BLOCKER | Open | PooleGlyph Phase 66 promotion and PGB2/PGVM2 v1 freeze are accepted |
| `FLAG-NATIVE-PDC-001` | REQUIRED | Open | Signed dynamics and native/backend differentials pass without claim expansion |
| `FLAG-NATIVE-HW-001` | STOP_SHIP | Open | Exact Tier 1 hardware, spare media, firmware, driver, and recovery qualification pass |
| `FLAG-NATIVE-ISO-001` | STOP_SHIP | Open | Two builders reproduce and exact signed ISO passes clean QEMU and physical media |
| `FLAG-NATIVE-REVIEW-001` | STOP_SHIP | Open | Independent security, filesystem, kernel, update, and release review closes critical/high findings |
| `FLAG-BUILDROOT-LEGACY-001` | SUPERSEDED | Closed by architecture reset | Buildroot remains historical reference and cannot promote native status |

## 12. Near-Term Execution Sequence

Cycle 83 completes every non-owner preparation step currently available for `N0-RATIFY-001`. The manifest/signature/tag verifier fails closed, but the move is now blocked on owner disposition, key custody, physical signing, and publication. `N2-HW-001`, `N4-QEMU-001`, and second-host N3 reproduction may proceed in parallel without promoting N0.

| Order | Move | Required output |
|---:|---|---|
| 1 | `N0-RATIFY-001` | Owner disposition of ADR-0003/0004, custody choice, public-key fingerprint, detached signature, signed tag, and exact publication receipt |
| 2 | `N1-SCM-CLOSE-001` | Signed-commit policy, immutable refs, retained CI/review policy, and protected-workflow closure after the pre-signing history is resolved |
| 3 | `N2-HW-001` | Exact Tier 0/Tier 1 hardware and standards manifests plus safe lab approval |
| 4 | `N4-QEMU-001` | Pinned OVMF/QEMU native launch, serial capture, GDB, deterministic debug-exit receipt |
| 5 | `N5-POOLEBOOT-001` | Poole-authored PE32+ UEFI application prints, draws GOP pixels, reads tables/map, exits cleanly |
| 6 | `N5-BOOTPROTO-001` | Canonical boot handoff schema, independent decoder, golden bytes, malformed corpus |
| 7 | `N5-ELF-001` | PooleBoot validates and loads a minimal PooleKernel ELF64 image |
| 8 | `N6-KENTRY-001` | Kernel entry, serial/framebuffer log, panic, build ID, signed manifest continuity |
| 9 | `N7-TRAP-001` | GDT/TSS/IDT and deliberate breakpoint/page-fault evidence |
| 10 | `N9-PMM-001` | Normalized map, bootstrap allocator, physical allocator, guarded mappings |
| 11 | `N8-IRQ-001` | Local APIC, timer, monotonic clock, and first SMP application processor |
| 12 | `N12-SCHED-001` | Neutral scheduler and context switch under SMP stress |
| 13 | `N13-RING3-001` | First user task, syscall, capability object, exception, and clean exit |
| 14 | `N14-IPC-001` | Capability-mediated call/reply, cancellation, quota, and hostile message tests |
| 15 | `N16-VIRTIO-001` | Isolated virtio console/RNG driver domain with revocation and restart |

PDC-SIGNED-001 and PooleGlyph Phase 66 may proceed as parallel component lanes, but neither outranks N0-N5 on the native critical path.

## 13. Production Completion Contract

PooleOS is production-ready only when:

- every required checklist item from all 8,996 implementation items is complete or is excluded by a signed release-profile disposition;
- every applicable `ADD-*` requirement is complete;
- all N0-N39 phase and subphase exit gates pass;
- PooleBoot and PooleKernel are original, source-controlled, reviewed, reproducible native artifacts;
- capabilities, IPC, memory, scheduling, IOMMU, driver isolation, cancellation, cleanup, fault containment, and recovery pass adversarial testing;
- PooleFS, package/update, installer, backup, and recovery survive declared power-loss and compromise scenarios;
- PooleGlyph Phase 66 promotion and PGB2/PGVM2 v1 are accepted;
- canonical PDC execution matches reference and guarded backend evidence within declared scope;
- PooleGlass Liquid Glass UI, animated/static boot identity, accessibility, software rendering, and recovery fallbacks pass;
- the exact signed ISO is independently reproducible, boots from clean media in every supported QEMU and physical profile, and the tested bytes equal the distributed bytes;
- SBOM, provenance, source, licenses, standards, hardware matrix, limitations, signatures, support, incident, update, rollback, and recovery records ship with the release;
- independent reviewers accept the exact release evidence and no stop-ship flag remains open.

Anything less is a research build, developer preview, lab image, alpha, beta, or release candidate with explicit limitations. It is not production-ready PooleOS.
