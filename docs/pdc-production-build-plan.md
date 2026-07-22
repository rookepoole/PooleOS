# PooleOS Native Architecture Production Build Plan

Status date: 2026-07-22
Plan version: 2.31.0-native-kernel-physical-memory
Roadmap cycle: PooleOS Cycle 125
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

Cycle 80 reset architecture claims without discarding validated component evidence. Cycles 81-96 established the native constitution, source boundary, pinned one-host toolchain, owner-controlled governance state, hardware and Tier 0 profiles, bounded formal models, and the PooleGlyph co-development lane. Cycles 97-107 qualified the bounded native boot path through exact profile retention and the permanent pre-transfer stop. Cycles 108-113 froze PINIT1, PREC1, PSYM1, synthetic-only PMCU1, synthetic-only PFWM1, and qualification-only PPOL1 as six independently validated inner formats. Cycle 114 integrates those parsers into live PooleBoot over the exact retained firmware-page bytes. Cycle 115 freezes PBTRUST1 and live unsigned-policy denial. Cycle 116 adds PBSTATE1 as a pure allocation-free two-copy backend-selection and transition-planning model anchored to an externally authenticated monotonic record. Cycle 117 expands the final PBP1 loaded-artifact profile to exact retained PSM1, six PBART1 files, PBTP1, and PBTS1 locators and implements PKREVAL1 in allocation-free `no_std` PooleKernel code. Cycle 118 adds PKXFER1 as a separately feature-gated QEMU-only one-way development transfer while preserving the ordinary stop-before-transfer path. PooleBoot installs retained CR3 and guarded RSP, clears IF/DF, passes the exact PBP1 ABI once, and never resumes. PooleKernel validates runtime continuity, independently reparses all nine retained files, reconstructs exact `pbtrust_policy_unsigned` denial, emits five terminal markers over serial and debugcon, and halts. Two exact QEMU/OVMF runs reproduce all 30 markers and PBP1 bytes; 58/58 transfer controls pass with zero signatures, authority grants, authorized actions, state writes, or post-exit firmware calls. No cryptographic verifier, authenticated monotonic provider, persistent backend, revocation or Secure Boot evidence, capability creation, policy application, PooleGlyph executable authority, target-firmware result, physical-media write, or production transfer exists.

Cycle 119 adds PKTRAP1 as three mutually exclusive opt-in QEMU-only continuations of PKXFER1. One BSP installs and reads back a five-entry GDT, 104-byte TSS, and 256-entry IDT allocation with five present gates; uses distinct 8,192-byte IST1 and IST2 arrays; normalizes integer traps into a 176-byte frame; returns from deliberate `#BP`, `#UD`, and PKMAP2 guard-page `#PF`; contains a processor-delivered terminal `#DF`; and rejects an explicitly synthetic semantic malformed-frame control. Six fresh-vars QEMU/OVMF runs and 51/51 hostile controls pass with exact per-scenario serial/debugcon markers, screenshots, and PBP1 bytes. N7 remains partial: CPU/errata/control-state policy, x87/SSE/XSAVE ownership, per-CPU tables, guarded IST mappings, complete vectors, user transitions, asynchronous state, NMI/machine check, retained crash recovery, target hardware, and the N7 exit gate remain open.

Cycle 120 adds PKCPU1 as a fourth mutually exclusive opt-in QEMU-only continuation of PKXFER1. Two fresh-vars qemu64 QEMU/OVMF runs capture and independently validate one BSP's required CPUID identity, features, topology, and address widths; CR0, CR4, EFER, and XCR0; and support-gated APIC, PAT, and MTRR MSRs. Rust and Python agree across 35 ordered markers and 41/41 hostile controls. The observed emulator identity is `AuthenticAMD`, family 15, model 107, stepping 1, with 40-bit physical and 48-bit linear addresses. The profile performs five MSR reads, zero MSR writes, zero control-state writes, zero authority grants, and zero actions. N7.1 and N7.3 become partial only for this bounded read-only emulator slice. Exact Ryzen 7 9800X3D family/model/stepping and errata/microcode policy, target-hardware state, AP-local policy, syscall/GS/TSC_AUX/machine-check/performance MSRs, x87/SSE/XSAVE ownership, and the N7 exit gate remain open.

Cycle 121 adds PKERR1 as a pure, non-promoting exact-target policy. Independent allocation-free `no_std` Rust and Python evaluators require CPUID signature `0x00B40F40`, nine mandatory features, an exact B650M GAMING PLUS WIFI board lineage, a stable lineage-specific BIOS floor, the stronger AMD-SB-7033/AMD-SB-7055 AGESA floor, homogeneous trusted microcode evidence, directly applicable errata authority, and a fail-closed RDSEED disposition. Six Rust tests, both native targets, 128 cross-language vectors, and 24/24 hostile controls pass. The current workstation is denied for exactly six reasons: unknown board lineage, BIOS and AGESA below the frozen floor, unqualified microcode evidence, no direct numeric client microcode floor, and no applicable Model 40h-4Fh errata guide. Windows reports homogeneous revision `0x0B404023` across 16 logical processors, but that is unprivileged OS metadata rather than direct MSR evidence or a vendor floor. AMD revision guide 58251 is explicitly rejected because it covers Models 00h-0Fh. No privileged read, firmware download or change, microcode application, driver load, key use, signature, physical-media write, authority grant, release, or promotion occurred. N7.2 and N15.1 become partial only for this fail-closed policy boundary.

Cycle 122 adds PKXSTATE1 as a fifth mutually exclusive, opt-in, QEMU-only continuation of PKXFER1. The frozen policy selects eager standard-format `XSAVE64`/`XRSTOR64` ownership for x87 and SSE only, exact XCR0 `0x3`, XSS zero, 4,096-byte 64-byte-aligned owner images, canonical FCW `0x037F`, canonical MXCSR `0x1F80`, masked exceptions, fail-closed context-switch preconditions, sensitive-image clearing, and a kernel-SIMD prohibition. Thirty-one kernel host tests and two exact fresh-vars EPYC-Rome-v4 QEMU/OVMF runs reproduce 35 markers, two saves, four restores, two isolated owner patterns, 8,192 cleared image bytes, and all 43 hostile controls with independent Rust/Python agreement. The only privileged configuration writes are CR0, CR4, and XCR0; there are zero MSR writes, signatures, authority grants, authorized actions, firmware calls, or physical-media writes. The AMD64 APM Volume 2 revision 3.44 source is hash-bound but not redistributed. N7.4 becomes partial only for this one-BSP development slice. AVX and extended state, deliberate `#MF`/`#XM`/`#NM` delivery, real scheduler/thread ownership, AP state, CPU migration, final machine-code SIMD audit, target hardware, N7 exit, release, and production remain open.

Cycle 123 adds PKXEXC1 as a sixth mutually exclusive opt-in continuation of PKXFER1 after revalidating PKXSTATE1. One expected TCG diagnostic proves QEMU issue 215 remains fail-closed: the unmasked SIMD invalid-operation status bit is set but vector 19 is not injected, so PooleKernel halts with panic `0x100E`. Two fresh-vars WHPX QEMU/OVMF runs then reproduce 41 ordered markers: processor-delivered x87 `#MF` and SIMD `#XM`, exact `FNINIT` and `LDMXCSR 0x1F80` recovery, exact resume sites, and terminal test-only `#NM` delivery rejected by the eager policy without state sampling or recovery. All 43 hostile controls pass. A hash-bound LLVM 22.1.6 linked-image audit finds eight allowlisted XMM instructions, zero YMM/ZMM instructions, the required x87/SIMD/#NM trigger sequences, and only the two reviewed recovery writes. Four privileged configuration writes are limited to CR0, CR4, XCR0, and test-only CR0.TS; there are zero signatures, authority grants, authorized actions, post-exit firmware calls, or physical-media effects. This closes only `FLAG-N7-XSTATE-EXCEPTION-001`; N7.4 remains partial. Scheduler and user-task exception delivery, AP state, CPU migration, AVX/extended components, exact target qualification, N7 exit, release, and production remain open.

Cycle 124 adds PKMSR1 as a seventh mutually exclusive opt-in continuation of PKXFER1. Two fresh-vars TCG qemu64 QEMU/OVMF runs reproduce 35 ordered markers and independently validate `AuthenticAMD` family 15 model 107 stepping 1, support-gated system-linkage and FS/GS reads, absent RDTSCP and therefore no `TSC_AUX` read, ten MCA banks, and an unsupported PMU. The profile performs exactly eleven `RDMSR` operations, no MCA bank read, no `RDPMC`, `WRMSR`, `SYSCALL`, `SYSRET`, or `SWAPGS`, and zero control writes, signatures, authority grants, actions, post-exit firmware calls, or physical-media effects. All 47 hostile controls pass. A hash-bound linked-image audit freezes 17 total `RDMSR` instructions and zero activation/write instructions. QEMU's `MCG_CAP` bit 24 and all-ones `MCG_CTL` values are compatibility observations only, not generalized AMD hardware semantics. This closes only `FLAG-N7-PRIVILEGE-MSR-POLICY-001`; N7.3 remains partial. Syscall activation, GS/TSC_AUX ownership, machine-check handling, PMU ownership, AP state, exact target qualification, and N7 exit remain open.

Cycle 125 adds PKPMM1 as selector `8`, an opt-in one-BSP qemu64 continuation of PKXFER1. Two exact fresh-vars QEMU/OVMF runs emit 40 ordered markers and consume the live 97-entry PBP1 memory map inside PooleKernel. PKPMM1 independently revalidates every UEFI source-type/kind pair, admits only conventional usable memory, excludes page zero, holds boot-services and ACPI reclaim classes, protects all retained loader ranges, and audits the exact kernel, current page-table root, fourteen-page guarded stack, and handoff ownership. The manager exposes DMA, DMA32, and Normal zones; deterministic first fit; generation-safe handles; a 64-page profile quota; stale/double-free rejection; metadata poisoning; and same-zone coalescing. It manages 117,924 of 117,925 usable pages, holds 11,250 boot-reclaimable pages, protects 819 retained loader pages, and performs four deterministic allocator operations. All 48 hostile controls pass with zero physical-page reads or writes, page-table mutations, reclaim transitions, signatures, authority grants, or actions. The first live selector-8 attempt also exposed an insufficient eight-page bootstrap stack; expanding it to fourteen pages reached the allocator result, and the subsequent trap rerun exposed and fixed a hard-coded old guard offset. `ADD-MEM-001` now requires one derived stack/guard/root/handoff ownership boundary. This closes only `FLAG-N9-PMM-FOUNDATION-001`; N9.1 and N9.2 are partial. Page scrubbing, lifecycle reclaim, virtual memory, heap/object caches, MMIO/cache aliases, concurrency/SMP, pressure/OOM policy, target hardware, and N9 exit remain open.

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
| Native Tier 0 | `POOLEOS-TIER0-Q35-1`; exact 1,180,772,298-byte QEMU runtime closure; two profiles; 4/4 paused q35/QMP probes; 18/18 negative controls | Partial N4.1-N4.4 | No guest CPU execution, native media, PooleBoot boot, current source rebuild, driver execution, Secure Boot, formal model, or N4 exit claim |
| Native formal models | `POOLEOS-N4-MODELS-5`; six safe state spaces drained; twenty-one required hostile invariant violations; 27/27 repeat matches; 31/31 negative controls | Partial N4.5-N4.6 | All seven required domains have bounded safety models; all six implementation-trace comparisons, liveness, refinement, ABI-freeze, kernel/filesystem execution, hardware durability, and promotion remain open |
| Native PooleBoot proof | `POOLEOS-N5-POOLEBOOT-7`; 8/8 host tests; 2/2 exact PE32+ builds; 2/2 exact twelve-file GPT/FAT32 images; 2/2 pinned OVMF runs; twenty-five ordered markers; 2/2 dual-channel and GOP-frame matches; 155/155 hostile controls | Partial N5.1-N5.9 | The ordinary build retains unsigned files, denies authority, exits boot services, and stops before transfer; PKXFER1 separately proves only the opt-in QEMU development transfer. No policy-signature verification, authenticated revocation or monotonic writable backend, Secure Boot-state verification, capability activation, target firmware, physical media, N5 exit, or production claim exists |
| Native PBP1 handoff | Canonical 64-byte header and 32-byte descriptors; twelve typed records; 8/8 Rust tests; 2/2 `no_std` target builds; 3/3 golden vectors; 32/32 controls; 16,384 Rust/Python differential cases with zero mismatches; PKLOAD6 independently reconstructs 2/2 exact 5,008-byte post-exit development messages with ten artifact descriptors and 96 stride-48 memory entries | Partial N5.8 | Live bytes bind retained root, guarded stack, handoff, kernel, six PBART1 files, exact PSM1/PBTP1/PBTS1 files, GOP, and final-map ranges. The authenticated production profile rejects these unsigned bytes; PKXFER1 separately accepts only the exact QEMU development envelope and grants no ABI ratification or production authority |
| Native PBC1 boot configuration | Canonical ASCII/LF grammar; allocation-free `no_std` parser; independent Python oracle; 12/12 Rust tests; 2/2 parser and 2/2 PooleBoot integration target builds; 3/3 vectors; 64/64 controls; 16,384 differential cases with zero mismatches | Partial N5.4 | Standalone PBC1 receipt remains parser-only; PKLOAD6 separately proves a live exact read and final PSM1/PBP1 binding, but not signature trust or persistent rollback |
| Native PSM1 system manifest | Canonical bounded ASCII/LF grammar; allocation-free `no_std` parser; independent Python oracle; exact slot/version/path/file/image/SHA-256/entry binding; 8/8 Rust tests; 2/2 `no_std` targets; one PooleBoot integration build; 3/3 vectors; 64/64 controls; 16,384 differential and 1,027 digest cases with zero mismatches | Partial N5.4-N5.5 | Unsigned digest-bound development selection only; PBDIGEST1 security review, signatures, signer/revocation policy, and persistent rollback remain open |
| Native PKELF1 kernel loader | Bounded ELF64 `ET_DYN` profile; dependency-free `no_std` loader; independent Python oracle; 12/12 Rust tests; 2/2 target and 2/2 PooleBoot integration builds; 3/3 exact loaded images; 129/129 controls; 16,384 differential cases with zero mismatches | Partial N5.5 | Standalone PKELF1 receipt remains caller-buffer evidence; PKLOAD6 separately proves manifest-bound live allocation retained through successful `ExitBootServices`, but not transfer or trust |
| Native PBART1 profile artifacts | Fixed 96-byte envelope; exact roles 2-7; independent Rust/Python validation; six whole-file and payload digest bindings; distinct zero-padded loader pages; final-map and PBP1 retention; live PooleBoot and opt-in live PooleKernel reparse | Partial N5.6 | Envelopes are unsigned and untrusted; parsing and mandatory denial create no authority, and authenticated consumption plus every payload action remain open |
| Native PINIT1 initial-system bundle | Canonical 1,764-byte typed declaration bundle; 3 components, 3 services, 3 dependencies, 4 resources, 11 attenuated routes; 3/3 Rust tests; 2/2 `no_std` targets; 3/3 vectors; 120/120 controls; 16,384 Rust/Python differential cases; exact PooleBoot and host-qualified PooleKernel retained-page parses with zero effects | Partial N5.6/N19/N21 | Declarations confer no authority, unsigned activation is denied, and live PooleKernel execution, authenticated loading, capability creation, process launch, lifecycle execution, and rollback remain open |
| Native PREC1 recovery bundle | Canonical 992-byte immutable policy and 128-byte mutable state; 2 slots, 10 failure routes, 7 authority requirements; decrement-before-handoff, known-good fallback, bounded safe/recovery routing, authenticated receipt binding, and physical-presence gates; 3/3 Rust tests; 2/2 `no_std` targets; 3/3 vectors; 144/144 controls; 16,384 parser/state and 8,192 transition cases with zero mismatches | Partial N5.6/N5.9/N23 | Host/reference validation only; checksum is not authentication, unsigned activation is denied, no persistent state is read or written, no authority is granted, and PooleBoot enforcement and PooleKernel recovery execution remain open |
| Native PSYM1 public symbol bundle | Canonical bounded public-only diagnostic index; exact stripped/loaded/build/debug/source identity; image-relative offsets; bounded KASLR lookup; 4/4 Rust tests; 2/2 `no_std` targets; 3/3 vectors; 158/158 controls; 16,384 parser and 16,384 lookup cases; two exact split-debug builds; three public symbols; zero mismatches | Partial N5.6/N5.9 | Host/reference validation only; unsigned consumption is denied, full debug data is absent from media, pointers default to redacted, no export or diagnostic authority is created, and PooleBoot/PooleKernel consumption remains open |
| Native PMCU1 microcode package | Canonical bounded exact-CPU wrapper around opaque bytes; two canonical patches; 4/4 Rust tests; 2/2 `no_std` targets; 3/3 vectors; 174/174 controls; 16,384 parser, 16,384 selection, and 8,192 post-apply cases; 35 synthetic never-apply payloads; zero mismatches | Partial N5.6/N5.9/N15 | Host/reference policy validation only; no real vendor payload, container validation, license approval, privileged revision observation, kernel authority, CPU update, firmware mutation, or physical-media write |
| Native PFWM1 firmware manifest | Canonical 1,312-byte synthetic qualification manifest; 3 external-payload components; 2 dependency edges; 5/5 Rust tests; 2/2 `no_std` targets; 3/3 vectors; 101/101 controls; 16,384 parser, 8,192 activation, and 8,192 post-reset cases; zero mismatches and zero embedded payloads | Partial N5.6/N5.9/N15/N24 | Host/reference dry-run validation only; no live inventory, vendor payload validation, updater driver, apply authority, capsule submission, reset, firmware mutation, physical-media write, or hardware qualification |
| Native PPOL1 system policy | Canonical 1,984-byte qualification-only policy; 6 exact modes; 11 PINIT1-cross-bound capability rules; 6/6 Rust tests; 2/2 `no_std` targets; 3/3 vectors; 116/116 controls; 8,192 parser, 4,096 cross-binding, 12,288 activation, and 8,192 receipt cases; zero mismatches | Partial N5.6/N5.9/N13/N15 | Host/reference dry-run validation only; no live signature or rollback state, PooleBoot/PooleKernel interpreter, capability allocation, applied decision, durable write, PooleGlyph executable authority, or production promotion |
| Native PBTRUST1/PBSTATE1 boot trust | Separate 320-byte PBTP1 policy and 256-byte PBTS1 acceptance state; pure authenticated-anchor and two-copy backend model; 12/12 Rust tests; 2/2 `no_std` targets; one PooleBoot integration build; 105/105 controls; 32,768 differential cases; nine interrupted-transition cases; fourteen live PooleBoot bindings and host-qualified independent PooleKernel bindings with exact unsigned-policy denial | Partial N5.1/N5.4/N5.5/N5.8/N5.9 | Backend inputs are synthetic external evidence and the model performs no cryptography or I/O; ESP records remain non-authoritative; no trusted signer/revocation store, real monotonic provider, persistent repair/migration, Secure Boot evidence, live kernel execution, authority, or production promotion |
| Native PKLOAD6 / PBLIVE3 / PKMAP2 / PBEXIT1 integration | Exact live PBC1, PSM1, real 192,512-byte canonical PKELF1, six PBART1, PBTP1, and PBTS1 reads; 139/139 Rust host tests; 2/2 exact PooleBoot, kernel, twelve-file media, and QEMU runs; 25 markers; 155/155 controls; exact 97-entry final PBP1, 64-page kernel and nine-file retained mapping, fourteen-page guarded stack, firmware-boundary agreement, live six-format and PBTRUST1 parsing, and independent oracle agreement | Partial N5.1/N5.4-N5.9 | The default path proves retained pages, successful `ExitBootServices`, unsigned denial, and permanent stop. PKXFER1 separately proves the development transfer; signature trust, authenticated state I/O, capability/action enforcement, final framebuffer remap, production transfer, and N5 exit remain open |
| Native PKENTRY1 PooleKernel | Real 192,512-byte canonical PKELF1 product in a 262,144-byte image; fixed 0x8000 entry; 401 relative relocations; 54/54 host tests; 2/2 exact clean builds; 43/43 hostile controls; exact Rust/Python loaded bytes; canonical SHA-256 `F449D0E037571345A40162DC9A943A2FA01F1195F21C239C8D8F1A85D39CA06E` | Partial N6.4-N6.6 | PKXFER1, PKTRAP1, PKCPU1, PKXSTATE1, PKXEXC1, PKMSR1, and PKPMM1 separately prove opt-in virtualized entry and bounded BSP trap/CPU/xstate/MSR/PMM slices, while PKERR1 freezes a pure exact-target policy. Authentication, production PBP1, final framebuffer remap, complete per-CPU exception/xstate runtime, target firmware, and N6 exit remain open |
| Native PKPMM1 physical memory | Exact live 97-entry PBP1 intake; 117,925 conventional usable source pages; 117,924 managed pages; 11,250 reclaimable pages held; 819 loader pages protected; DMA/DMA32/Normal zones; deterministic allocate/free, quota, poison, double-free, and coalescing evidence; 2/2 exact 40-marker QEMU runs; 48/48 hostile controls | Partial N9.1-N9.2 | Zero page-content writes, mappings, reclaim, concurrency, authority, or actions; virtual memory, heaps, MMIO/cache policy, pressure/OOM, target, and N9 exit remain open |
| Native PKREVAL1 PooleKernel revalidation | Allocation-free `no_std` verifier over exact retained PSM1, six PBART1 files, PBTP1, and PBTS1; 54/54 Rust tests; 8/8 Python tests; both target builds; 36/36 hostile controls; 32,768/32,768 role-complete mutation rejects; exact Rust/Python denial receipt; zero authority, actions, and state writes | Partial N5.8/N6.4-N6.6 | The standalone receipt makes no live-entry claim; PKXFER1 separately proves live execution only for the unsigned QEMU development envelope. Cryptographic trust, persistent state selection, capabilities, actions, writes, N5/N6 exit, and production remain open |
| Native PKXFER1 kernel transfer | Default feature disabled and permanent stop preserved; 2/2 exact kernel builds; 2/2 feature-enabled boot builds plus one default isolation build; 2/2 exact media and fresh-vars QEMU/OVMF runs; 30/30 markers; 5/5 kernel markers; exact serial/debugcon/PBP1/guest-host PKREVAL1 agreement; 58/58 hostile controls | Partial N5.8/N5.9/N6.4 | QEMU-only unsigned development transfer terminating in denial and halt; zero signatures, authority, actions, writes, or firmware calls. No authenticated production entry, target firmware, physical media, capability enforcement, N5/N6 exit, or production claim |
| Native PKTRAP1 BSP trap entry | Five-entry GDT, 104-byte TSS, 256-entry IDT allocation with five present gates, distinct 8,192-byte IST arrays, 176-byte integer frame, exact returning `#BP`/`#UD`/guard-page `#PF`, terminal processor-delivered `#DF`, and semantic malformed-frame rejection; 3 scenarios, 6 exact QEMU/OVMF runs, 51/51 controls | Partial N7.5-N7.6 | BSP-only QEMU development evidence. Per-CPU and guarded stacks, complete vectors, asynchronous state, NMI/machine check, user transitions, persistent crash recovery, target hardware, N7 exit, and production remain open |
| Native PKCPU1 read-only CPU policy | Required CPUID identity/features/topology/address-widths plus CR0/CR4/EFER, XCR0, APIC/PAT/MTRR observation; 31/31 kernel tests; 2 exact qemu64 QEMU/OVMF runs; 35 markers; 41/41 controls; exact Rust/Python agreement; 5 MSR reads; zero MSR/control writes, authority, or actions | Partial N7.1/N7.3 | BSP-only qemu64 development evidence. Exact Tier 1 family/stepping, errata/microcode policy, AP-local state, syscall/GS/TSC_AUX/MCE/performance MSRs, target hardware, N7 exit, and production remain open |
| Native PKERR1 exact-target policy | Exact Ryzen 7 9800X3D identity; nine mandatory features; board-lineage BIOS and AMD bulletin AGESA floors; RDSEED, microcode-evidence, and source-applicability rules; 6/6 Rust tests; 2/2 `no_std` targets; 128 vectors; 24/24 controls; current six-reason denial; zero privileged reads, writes, authority, or actions | Partial N7.2/N15.1 | Pure policy and unprivileged OS metadata only. Exact board revision, applicable Model 40h-4Fh errata authority, direct numeric microcode floor or ratified replacement, native per-processor evidence, firmware-image hash, kernel integration, target qualification, N7 exit, and production remain open |
| Native PKXSTATE1 x87/SSE ownership | Eager standard `XSAVE64`/`XRSTOR64`; XCR0 `0x3`; XSS zero; 4,096-byte aligned owner images; canonical FCW/MXCSR; 31/31 kernel tests; 2 exact EPYC-Rome-v4 QEMU/OVMF runs; 35 markers; 43/43 controls; 2 saves; 4 restores; 8,192 cleared image bytes; 3 allowlisted privileged configuration writes | Partial N7.4 | One-BSP emulator evidence only. PKXEXC1 separately adds bounded deliberate exceptions and a linked scope audit. AVX/extended state, user-task delivery, scheduler/thread integration, AP initialization, migration, target hardware, N7 exit, and production remain open |
| Native PKXEXC1 xstate exceptions | 2 exact WHPX QEMU/OVMF runs plus 1 expected TCG limitation probe; 41 markers; 43/43 controls; 3 delivered exceptions; exact `#MF`/`#XM` recovery; terminal test-only `#NM` rejection; linked LLVM machine-code audit; 4 configuration and 2 recovery writes | Partial N7.4 | One virtualized BSP only. No user-task delivery, scheduler/thread integration, AP initialization, migration, AVX/extended state, exact target qualification, N7 exit, or production claim |
| Native PKMSR1 privilege/MSR policy | 2 exact TCG qemu64 QEMU/OVMF runs; 35 markers; 47/47 controls; 11 support-gated MSR reads; 10 MCA banks; 0 MCA bank reads; linked LLVM audit with 17 `RDMSR` and zero activation/write instructions | Partial N7.3 | One virtual BSP compatibility model only. No syscall/GS/TSC_AUX activation, machine-check handler, MCA recovery, PMU owner, AP state, exact target qualification, N7 exit, or production claim |
| Native v1 objectives | 38 measurable owner-directed definitions: 7 reliability, 8 accessibility, 6 compatibility, 7 privacy, and 10 performance; ten negative controls pass | Partial N0.6 | Zero targets measured; cryptographic signature and all implementation evidence remain open |
| Test suite | Cycle 125: 779 tests pass with one Windows symlink-permission skip, including PKPMM1 map/ownership/allocator controls plus all PKMSR1, PKXEXC1, PKXSTATE1, PKERR1, PKCPU1, PKTRAP1, PKXFER1, PKREVAL1, and producer controls | Partial N36 | Predominantly host/reference, bounded-model, emulator, and artifact tests; no authenticated authority, target-firmware, or physical-hardware result exists |
| Release gate | Cycle 125: 92/92 consistency checks over 87 artifacts; 20 native gaps | Partial N37 | `production_ready=false`; not a release acceptance gate |
| Source control | Public `rookepoole/PooleOS`, protected `main`, topic-branch workflow, private vulnerability reporting | Partial N1/N37 | Initial commit unsigned; signed tags, immutable release refs, retained CI, and full review policy remain open |
| ADR ratification | Frozen 16-source owner packet, completed public-safe response receipt, 2/2 ADR dispositions, 38/38 definition dispositions, canonical OpenSSH `SSHSIG` contract, public trust/revocation files, signed-tag/remote verifier, and 38 combined packet/response/ceremony controls | Partial N0/N1/N37 | Packet stays historically unselected; all seven ADRs are owner-directed but unsigned; selected hardware key unavailable; zero trusted keys. Cycle 118 authorizes acquisition, key use, publication, signing, releases, and promotion, but no such operation has occurred and every custody/qualification/release gate remains open |
| Native toolchain | Rust 1.97.0/Cargo 1.97.0/LLD 22.1.6; dedicated empty PE32+/ELF64 fixtures and the PooleBoot product each reproduce exactly on one host | Partial N3 | Second host, source provenance, and remaining tool families are open |
| Tier 1 hardware | Exact target matches 24/24 required identity checks; 16 allowlisted user-mode CPUID records are captured and decoded; 14/14 negative controls pass with zero privacy violations | Partial N2 | Seven required channels remain non-complete, including partial CPU/MSR and SPD/topology; 15 standards hashes, ten lab prerequisites, and native comparison remain open |
| Native bootloader | Reproducible unsigned Poole-authored PE32+ UEFI application with live PBC1/PSM1/PKELF1/PBART1/PBTP1/PBTS1 intake, retained PKMAP2 kernel/nine-file/root/stack/handoff ranges, ten-descriptor final PBLIVE3, bounded PBEXIT1, successful `ExitBootServices`, a default firmware-free stop, and an opt-in QEMU-only one-way transfer | Partial N5.1-N5.8 | No signature-authenticated manifest/artifacts, trusted rollback state, payload authority, initial-system execution, production transfer, final framebuffer remap, target firmware, or N5 exit |
| Native kernel | Real reproducible 64-page PooleKernel PKELF1 source and image with host-qualified PKREVAL1 and an opt-in two-run QEMU live-entry/revalidation trace ending in unsigned denial | Partial N6.4-N6.6 | No authenticated production entry, descriptor/exception runtime, ring 3, IPC, capability, or driver-domain execution |
| Native media | Deterministic 64 MiB protective-MBR/GPT/FAT32 development image with exact fallback EFI, PBC1 config, PSM1 system manifest, and PKELF1 kernel | Partial N5.1/N5.4/N5.5 | Ordinary-file proof media; no El Torito ISO, installer, signature, physical write, or N39 evidence |

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
| N2 | Partial | `005-007,146,169` | 236 | 1 |
| N3 | Partial | `008-011` | 200 | 0 |
| N4 | Partial | `012` | 34 | 3 |
| N5 | Partial | `013-015` | 241 | 10 |
| N6 | Partial | `016-019,148-149` | 291 | 3 |
| N7 | Partial | `020-022` | 192 | 1 |
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
| N34 | Blocked | `124` | 102 | 6 |
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

Cycle 81-91 evidence:

- ADR-0001 through ADR-0007 record the owner-directed unsigned native constitution, reuse/publication boundary, language split, namespace registry, v1 scope, TCB placement, and repository governance.
- `specs/native-architecture-constitution.json` and `runs/native_architecture_baseline.json` bind exact architecture constants, seven ADR byte hashes, source hashes, owner direction, repository identity, 20 version namespaces, and eight TCB domains.
- `specs/native-release-architecture-policy.json` and `tools/check_native_release_architecture.py` reject missing native release objects, prohibited substitute paths/content, symbolic links, case-fold collisions, non-NFC paths, unreadable objects, and unscanned oversized binaries.
- Negative tests execute every prohibited path glob and every prohibited binary marker. A passing extracted-tree report remains non-promoting because it does not parse ISO, GPT, ESP, El Torito, signatures, hidden sectors, or source provenance.
- `specs/adr-ratification-policy.json` freezes canonical sorted UTF-8/LF JSON, the owner principal, a PooleOS-specific SSH signature namespace, allowed key profiles, public trust/revocation paths, immutable tag name, exact remote-publication contract, and six exact decision sources. Those sources include the candidate objectives and schema, PooleKernel charter, native constitution, release-architecture policy, and publication boundary.
- `tools/prepare_adr_ratification.py` requires separate explicit acceptance of all seven ADR bytes and all 38 exact objective definitions. It refuses inferred acceptance, zero/multiple signers, unsupported keys, and unacknowledged provisional software-key risk. `tools/verify_adr_ratification.py` verifies exact manifest bytes, objective/profile/count bindings, owner principal, namespace, revocation, signed annotated tag, tag-contained evidence, remote tag object, peeled commit, and exact remote `main` tip.
- Eleven focused tests exercise a throwaway test-only key and Git repository plus tampered ADRs, objective definitions, objective schema, wrong namespaces, unknown signers, malformed signatures, noncanonical bytes, revocation, missing dispositions, and tag/publication gates. A simulated fully verified architecture ceremony still yields `production_promotion_allowed=false`, `measurements_complete=false`, and `full_n0_exit_evidence_present=false`. No test key is retained.
- `runs/adr_ratification_readiness.json` deterministically records seven owner-directed ADRs, six bound decision sources, 38 accepted definitions, zero measured targets, zero cryptographically ratified records, zero trusted signers, 12 declared ceremony controls, four remaining gated actions, and `production_promotion_allowed=false`.
- `runs/n0_owner_decision_packet.json` and `docs/n0-owner-decision-packet.md` remain a byte-frozen 16-source historical review input with every original packet field `UNSELECTED`; twelve packet controls reject mutation or inferred authority.
- `specs/n0-owner-response.json`, `runs/n0_owner_response_receipt.json`, and `docs/n0-owner-response-receipt.md` record exact acceptance of ADR-0003, ADR-0004, and all 38 definition values; select `hardware_fido2_ed25519_sk`; record hardware availability `do_not_have`, software-key risk `not_applicable`, and public-key publication `not_yet`; and pass 16/16 controls rejecting stale packets, placeholders, inconsistent risk, measurement overclaim, private material, and gated authorizations.
- `specs/native-v1-objectives.json` defines the owner-directed `POOLEOS-WORKSTATION-V1-CANDIDATE` profile, seven required operating modes, exact Tier 0/Tier 1 scope boundaries, threat assumptions, measurement policy, and 38 measurable targets: 7 reliability, 8 accessibility, 6 compatibility, 7 privacy, and 10 performance.
- `runtime/native_v1_objectives.py`, both schemas, and `runs/native_v1_objectives_readiness.json` enforce exact target-family counts, owner-directed definition state, zero measured targets, deterministic byte bindings, and ten negative controls covering missing families, duplicates, invalid samples/percentiles, telemetry defaults, compatibility overclaims, recovery accessibility, evidence overclaims, production promotion, and acceptance regression.
- The candidate contract references WCAG 2.2, ETSI EN 301 549 V3.2.1, NIST Privacy Framework 1.1, and ADR-0005 with explicit applicability and non-claim boundaries. These references inform candidate criteria; they do not assert PooleOS conformance.

Open N0 work:

- No ADR has an owner-controlled cryptographic signature. ADR-0003 and ADR-0004 now carry owner-directed acceptance, while trademark review and full toolchain qualification also remain open.
- Rooke Poole selected `hardware_fido2_ed25519_sk` but reports no FIDO2 hardware key is available. Obtaining and confirming possession of compatible hardware remains the next external step.
- Cycle 118 explicitly authorizes compatible-key acquisition, key generation/use, public-key publication, signing, secrets use, privileged probes, driver loading, firmware changes, physical-media writes, tag/release publication, and production promotion. This current authority does not alter the historical response receipt, prove safe execution, or waive owner presence, custody, backup, recovery, safe-target, qualification, and exact-release gates. Codex generated or used no key and performed no newly authorized cryptographic, privileged, mutating, publication, release, or promotion action in Cycle 118.
- All 38 target definitions are accepted, but every target remains `not_measured`; implementation-bound baselines and passing evidence remain open across N4-N39.
- Cycle 93 preserves the original packet unchanged, records only the explicit source/objective/custody dispositions, and grants no key, signing, merge, tag, publication, measurement, or production authority.
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
- `main` requires pull requests, stale-review dismissal, resolved conversations, and linear history; force-push and deletion are denied. Private vulnerability reporting is enabled. Rooke Poole merged PRs #1 through #5; the Cycle 90 tree is public at merge commit `3f364a4a06e0ce3eb676e98fe6444669c4e2b3d7`.
- PolyForm Noncommercial 1.0.0 terms, owner notice, security policy, trademark notice, CODEOWNERS, ADR template, public/private evidence boundary, and native source-tree ownership skeleton are present.
- `.gitignore` excludes raw internal PDC inputs, private/local run evidence, historical Buildroot sources and lab images, archives, credentials, private signing material, firmware without redistribution clearance, and release-media binaries.
- `tools/check_publication_boundary.py` scans exact indexed bytes for prohibited paths, unapproved run artifacts, release media, credential containers, secret signatures, and workstation-specific paths.
- `security/owner-adr-signers.allowed` and `security/revoked-adr-signers` are public-only trust inputs and intentionally contain no key. Private signing material remains prohibited by path, suffix, and content scans.

Open N1 work: owner custody choice, owner-controlled commit/tag signing, a signed baseline tag, immutable release references, retained CI evidence, reviewer quorum, contributor policy, and legal/patent/export/trademark/component-license review remain open. Required signed commits must not be enabled until the existing unsigned setup history and merge strategy are resolved. Administrator enforcement and approval count must be revisited when another maintainer is configured.

Exit gate: PooleOS is source-controlled; every required decision has an owner and due gate; deletions and deferrals are reviewable; no component lacks licensing/provenance classification.

### N2 - Hardware Target, Laboratory, and Standards (`partial`)

Inherited sections: `005-007`, `146`, `169`. Added: `ADD-HW-PROBE-001`.
Goal: replace generic hardware assumptions with exact devices, lawful specifications, errata, safe test equipment, and support tiers.

Subphases:

- N2.1 Capture full PCIe, USB, ACPI, SMBIOS, UEFI, CPU feature, IOMMU, EDID, storage, firmware, topology, sensor, and power inventories for Tier 1.
- N2.2 Assign Tier 0 emulator, Tier 1 exact machine, Tier 2 controller-family, Tier 3 community-tested, Tier 4 best-effort, unsupported, and quarantined states.
- N2.3 Acquire a confirmed sacrificial SSD, two labeled USB devices, immutable recovery media, serial path, second-machine recovery, backups, UPS/power-cut apparatus, packet capture, and thermal/power measurement.
- N2.4 Build the standards register with revision, publication date, hash, license/access terms, errata, assumptions, supersession, and implementation owner.
- N2.5 Lock UEFI 2.11, ACPI 6.6, exact AMD64/AMD IOMMU manuals, SMBIOS 3.9, NVMe 2.2, xHCI 1.2, applicable USB/HID, TPM, network RFC, Unicode 17, POSIX Issue 8, VIRTIO 1.3, and exact device documents unless superseded through review.
- N2.6 Turn every undocumented register or observed firmware behavior into an explicit blocker or hardware-specific tested assumption.

Cycle 84 and Cycle 87 evidence:

- `specs/hardware-support-policy.json` defines Tier 0 through Tier 4, unsupported, and quarantined states; 14 required evidence channels; privacy prohibitions; ten destructive-lab prerequisites; and fail-closed promotion rules.
- `specs/tier1-hardware-target.json` identifies `TIER1-B650M-9800X3D-RTX5070-001`. The sanitized host observation matches all 24 required identity checks plus the optional display-resolution check.
- `tools/collect_tier1_hardware.ps1` 1.1 is read-only and writes only an ignored `.private.json` capture. Its x86-64 thunk queries a frozen CPUID leaf/subleaf allowlist from user mode, pins each query to the lowest process-allowed logical processor, restores the previous thread affinity immediately afterward, never queries processor-serial leaf `0x00000003`, allocates writable memory before changing it to execute/read, flushes the instruction cache, and never creates an RWX mapping. It loads no driver and attempts no MSR, PCI, SPD, UEFI-variable, physical-memory, I/O-port, TPM-write, firmware-write, disk-write, boot-state, or device-state operation.
- `tools/sanitize_tier1_hardware_capture.py` and `runtime/hardware_target.py` validate the exact private CPUID transcript before reconstructing a fixed public whitelist. They reject forbidden leaves, duplicate/missing records, malformed register encodings, false transcript hashes, serial-leaf collection, MSR overclaim, privileged-driver overclaim, or any mutation guard.
- `runs/tier1_hardware_observation.json` publishes only allowlisted facts and hashes: 25 enumerated ACPI signatures, first-table hashes including `IVRS` and `TPM2`, a 2,492-byte SMBIOS blob hash `F04EFC0E99D7CAC1A528D529E2D9B7E807D4B05DDF657FF4A013545F6DF096AB`, and an affinity-pinned 16-record CPUID transcript hash `1C4EB05B165ABA43F3DED644B0ADFB29A96D8919D0A15948028C1BEA03CC2848`. It publishes decoded vendor/family/model/stepping, address widths, and bounded feature booleans, not raw CPUID registers or a processor serial.
- `specs/native-standards-register.json` records 15 official primary-source entries. Ten metadata locks are verified, five supersession/profile reviews remain open, and zero exact artifacts are hash-verified; metadata and URLs do not satisfy the standards exit gate.
- `runs/hardware_target_readiness.json` passes schema and binding checks, all 24 required identity checks, two partial evidence channels, 16 CPUID records, zero privacy violations, and 14/14 adversarial controls. Seven required evidence channels and all ten lab-safety prerequisites remain pending, so `n2_exit_gate_satisfied=false` and `production_promotion_allowed=false`.
- `FLAG-N2-CPUID-001` closes only the direct user-mode CPUID sub-capability. `FLAG-N2-PRIVILEGED-PROBE-001` blocks driver-backed or privileged acquisition until its exact source, read-only mechanism, possible side effects, access scope, failure path, hostile tests, and operator authorization have been reviewed.
- Secure Boot and TPM inventory are permission-limited. MSR, PCI configuration space, SPD, UEFI variables, sensor/power evidence, duplicate ACPI retrieval, exact standards hashes, and native PooleOS parser comparison remain open. The separate N4 Tier 0 profile is now partially qualified, but it does not close any missing Tier 1 evidence channel. The firmware release-date representation also requires reconciliation.
- No firmware, TPM, disk, boot, power, device, or configuration mutation was authorized or performed. N2.3 remains `not_started`; destructive testing requires separate owner approval after every prerequisite is accepted.

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

Open N3 work: a second clean host, detached-signature and source-rebuild provenance, freestanding C17, bounded assembly, ABI probes/headers, archive and image tools, QEMU/OVMF source-build integration, generated ABI tables, complete build graph, static analysis, unsafe inventory, and the remaining section 008-011 requirements.

Cycle 117 control-plane validation passes 724 tests with one Windows symlink-permission skip. Live Doctor passes its complete generated check set, and the 84/84 release gate passes over 79 artifacts while retaining 20 explicit gaps and `production_ready=false`. Standalone PooleGlyph conformance output is redirected to temporary storage and the full upstream stack runs from a temporary source mirror, preserving the tandem repository's generated reports and run log. Exact authority and gate hashes are recorded only after their final deterministic generation.

Exit gate: two clean host environments reproduce bootstrap tools and empty native images; host headers/libraries cannot leak; ABI fixtures pass independently; all generated inputs are declared.

### N4 - Emulation, Reference Devices, and Formal Models (`partial`)

Inherited section: `012`. Added: `ADD-ASSURE-001`, `ADD-VIRTIO-001`, `ADD-TIER0-SUPPLY-001`.
Goal: create the disposable, observable environment in which native mechanisms can fail safely and repeatably.

Subphases:

- N4.1 Freeze QEMU machine, CPU, RAM, OVMF code/variables, q35 PCIe topology, serial, debug exit, and deterministic launch profiles.
- N4.2 Add OASIS VIRTIO 1.3 PCI transport and staged console, block, net, input, GPU, RNG, balloon, and IOMMU profiles.
- N4.3 Provide GDB/LLDB remote debugging, symbols, disassembly, QEMU tracing, serial capture, monitor control, deterministic seeds, snapshots, and packet/disk capture.
- N4.4 Provide malformed ACPI/SMBIOS/PCI/virtio/USB/storage/network fixtures and hardware-fault injection profiles.
- N4.5 Model capability derivation/revocation, IPC, scheduler, page mapping, boot slots, update rollback, and PooleFS transaction state before ABI freeze.
- N4.6 Record model assumptions and cross-check model traces against implementation traces; no proof claim extends beyond its configuration and assumptions.

Cycle 88 bounded foundation evidence:

- `specs/native-tier0-lock.json` separates the QEMU `11.0.2` upstream source target from the exact one-host QEMU `11.0.0` Windows runner, binds the publisher SHA-512, installer SHA-256, executable, all 3,368 extracted runtime files, five OVMF/descriptor inputs, provider commit, bundled EDK II commit, target EDK II commit, and two rejected substitute binaries;
- `specs/native-tier0-profile.json` freezes `pc-q35-11.0`, TCG single-thread execution, `qemu64`, one vCPU, 512 MiB, fixed virtual time, immutable code flash, a fresh variables copy, no default devices/network/host share/passthrough, non-transitional VIRTIO PCI block, serial, debugcon, ISA debug exit, tracing, and opt-in loopback GDB;
- `tools/qualify_native_tier0.py` verifies the complete workspace-local runtime closure and runs both profiles twice with guest CPUs paused, a private placeholder medium, temporary loopback QMP, and clean quit; 4/4 machine probes and both deterministic command/QMP comparisons pass;
- `tools/run_native_tier0.py` is dry-run-first, accepts no unknown QEMU argument, requires read-only non-Buildroot/non-Linux media and a new confined run directory, copies OVMF variables per launch, and leaves every boot and promotion claim false;
- 18/18 controls reject Android QEMU, a QEMU `11.0.50` development build, hash/version/machine/firmware drift, writable code, variables-template reuse, legacy/transitional VIRTIO, networking, host sharing, host acceleration, extra arguments, Buildroot/Linux media, path escape, and boot overclaim;
- the Windows candidate cannot disable guest memory dumping through the q35 property; its Authenticode certificate is expired; its bundled OVMF is older than `edk2-stable202605`; current source rebuilds, SBOM/license/vulnerability/redistribution review, and second-host reproduction remain mandatory.

Cycle 89-90 and Cycle 94-96 bounded model evidence:

- `specs/native-model-toolchain-lock.json` freezes TLA+ `v1.7.4`, `tla2tools.jar`, Eclipse Temurin JRE `jdk-21.0.11+10`, the complete 315-file JRE closure, TLC arguments, and two repeats while recording unsigned-input and unverified-detached-signature limits;
- `PooleBootSlots` checks a two-slot, two-attempt atomic rollback abstraction: the safe configuration drains 20 distinct states at depth 7, while `UnsafeRollback=TRUE` violates `Recoverable` through `Init -> Stage -> StartTrial -> TrialFailure`;
- `PooleCapabilities` checks three capability IDs, attenuation, ancestry, and transitive revocation: the safe configuration drains 1,316 distinct states at depth 6, while `UnsafeLocalRevoke=TRUE` violates `NoLiveDescendantOfRevoked` through `Init -> Derive -> Revoke`;
- `PooleVirtualMemory` checks two domains, two CPUs, two pages, one virtual address, and one generation-changing ownership reuse: the safe configuration drains 1,422 distinct states at depth 13; the independent stale-mapping mutant violates `PageTableSafety` through `Init -> Map -> BeginTransfer -> CompleteTransfer`; the independent early-reuse mutant violates `TlbSafety` through `Init -> Map -> TlbFill -> BeginTransfer -> Unmap -> CompleteTransfer`;
- `PooleIPC` checks two principals, one endpoint, two calls, two reply tokens, a one-call queue, and endpoint epochs 0 through 1: the safe configuration drains 621 distinct states at depth 9; independent mutants violate `QueuedCallAuthorized`, `LiveTokenConsistent`, `AcceptedRepliesFresh`, and `ClosedEndpointQuiescent` through exact 2-, 4-, 5-, and 3-state traces;
- `PooleScheduler` checks three fixed-priority tasks, one CPU context, one lock, cancellation and timeout wake results, immediate one-level inheritance, audited dispatch, two-bypass accounting, lock handoff, and teardown: the safe configuration drains 2,391 distinct states at depth 19; seven independent mutants violate `WakeDeliverySound`, `NoDuplicateRunnable`, `PriorityInheritanceSound`, `DispatchPrioritySound`, `BypassBound`, and `TerminalQuiescent` through exact 3- to 8-state traces;
- `PooleFS` checks one two-block copy-on-write update, durable data/checksum/allocation/journal state, crash and restart before or during recovery, ordered commit publication, old-or-new visibility, checksum rejection, replay idempotence, and teardown: the safe configuration drains 74 distinct states at depth 13; six independent mutants violate `ChecksummedDataValid`, `PublicationOrderSound`, `AllocationOwnershipSound`, `ReplayIdempotent`, `ChecksumRejectionSound`, and `MountedQuiescent` through exact 2- to 12-state traces;
- all twenty-seven model cases reproduce exactly over two runs, and 31/31 controls reject prerelease/toolchain substitution, stale runtime/model bindings, path escape, arbitrary TLC modes, unexpected safe violations, all twenty-one missing hostile violations, and implementation-trace overclaim;
- `runs/native_model_readiness.json` publishes normalized, path-free traces and keeps `formal_proof_claimed`, `liveness_checked`, `implementation_trace_cross_checked`, `abi_freeze_authorized`, `poolekernel_executed`, and `production_promotion_allowed` false;
- all seven required bounded domains are modeled; all six current model families have zero native implementation-trace cross-checks, and temporal liveness, refinement, implementation conformance, source-built toolchain provenance, and second-host reproduction remain open.

N4.1-N4.6 are partial. The N4 qualification itself remains a paused non-boot proof, while Cycle 97 consumes its exact runtime and profile for two separately bounded N5 PooleBoot runs. No debug-exit/reset/GDB path, VIRTIO driver, Secure Boot state, malformed-device campaign, native model implementation trace, liveness/refinement proof, or ABI-freeze authority was executed or claimed.

Exit gate: one command launches each pinned native test profile; logs and artifacts are deterministic where declared; formal models have executable counterexample checks; no Buildroot guest is required.

### N5 - Boot Media, Boot Protocol, and PooleBoot UEFI Loader (`partial`)

Inherited sections: `013-015`. Added: `ADD-BOOT-001`, `ADD-BOOT-004`, `ADD-BOOT-005`, `ADD-BOOT-006`, `ADD-BOOT-007`, `ADD-BOOT-008`, `ADD-BOOT-009`, `ADD-BOOT-010`, `ADD-BOOT-011`, `ADD-BOOT-012`.
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

Cycle 97 bounded proof evidence:

- `native/fixtures/pooleboot` preserves the empty N3 compiler fixture, while `native/boot` is now a distinct PooleBoot product crate;
- `PooleBoot.efi` is a 13,312-byte PE32+ x86-64 UEFI application at SHA-256 `B4EF888C588807CBF715E33831A0B52B07CEF5F8BEAFA4FD74D65BD9AA4919B8`; two clean builds are byte-identical, the timestamp is zero, the UEFI application subsystem is exact, and imports, debug directory, and host-leakage hits are absent;
- the proof validates bounded UEFI System Table and Boot Services signatures, headers, and CRCs; emits independent polling COM1 and debugcon diagnostics; handles watchdog and console paths; bounds configuration-table enumeration; accepts only bounded direct RGB/BGR GOP framebuffers; follows the two-call memory-map pattern with descriptor-stride validation; renders a deterministic static Poole identity; and returns `EFI_SUCCESS`;
- `runtime/native_pooleboot.py` emits and independently inspects a 67,108,864-byte ordinary-file medium at SHA-256 `E8175F70270D6E0A9D4BD1FB16A8814D9B30DD460CE1E6219CCF7AC528600FCA`, with protective MBR, mirrored GPT and CRCs, fixed disk/ESP GUIDs, FAT32, identical FATs, and exactly `EFI/BOOT/BOOTX64.EFI`; the CLI enforces workspace-regular-file input and output roots and rejects device namespaces, alternate streams, reserved names, symlinks, and physical targets;
- two pinned Q35/TCG/OVMF runs use read-only media, fresh variable stores, no guest network, no host acceleration, and loopback-only QMP; both produce the same eleven ordered markers over serial and debugcon and the same 1280x800 GOP frame at SHA-256 `E9D4CFD48C23DBA760AED5B2049B39DCA49A0D172F680D570082EB0680FDFDBD`;
- fifteen controls reject PE machine/subsystem/debug drift, all primary/backup/entry GPT CRC mutations, ESP-type substitution with recomputed CRCs, FAT-copy mismatch, FAT loops, fallback-path mutation, unsafe media output paths, marker omission/order drift, blank frames, and claim overreach;
- `runs/native_pooleboot_readiness.json`, schemas, release-gate integration, Doctor integration, and `docs/native-pooleboot-proof.md` bind the exact evidence and nonclaims.

Cycle 98 PBP1 evidence:

- `specs/native-boot-handoff-contract.json` defines the 64-byte header, 32-byte descriptors, twelve typed records, physical/virtual address semantics, ownership/lifetime, x86-64 transfer registers, strict canonicalization, compatibility rules, and kernel-entry profile;
- `native/handoff` provides a dependency-free `no_std` caller-buffer encoder and zero-allocation decoder that build for both `x86_64-unknown-uefi` and `x86_64-unknown-none`; no current PooleBoot or PooleKernel path calls it;
- `runtime/native_boot_handoff.py` independently implements the same byte and semantic rules as a prohibited-from-production host oracle;
- three exact vectors cover a full synthetic kernel-entry profile, a valid minimal handoff, and a minor-1 optional extension accepted by the minor-0 reader;
- 32 semantic controls reject version downgrade, unknown required data, malformed canonical layout, range/overflow, UTF-8, geometry, digest, entropy, timing, TCG, cross-record, and pre-`ExitBootServices` profile cases;
- 16,384 deterministic differential mutations produce 1,947 shared accepts, 14,437 shared rejects, and zero Rust/Python mismatches; the finite corpus is not a proof;
- `runs/native_boot_handoff_readiness.json`, release gate, Doctor, architecture baseline, roadmap, and public-boundary controls bind the exact candidate contract and nonclaims.

Cycle 99 PBC1 evidence:

- `specs/native-boot-config-contract.json` defines printable ASCII/LF encoding, strict key and entry order, exact version failure, canonical decimal numbers, five entry modes, caller-capacity handling, and complete file/line/entry/path/artifact bounds;
- `native/bootcfg` provides a dependency-free allocation-free `no_std` parser over caller-owned entry storage, and PooleBoot has a compile-time path dependency plus re-export without claiming live file I/O;
- `runtime/native_boot_config.py` independently encodes, parses, summarizes, and validates observed artifact sizes as prohibited-from-production host evidence;
- three exact vectors cover the minimum configuration, all five boot modes, and all maximum entry, timeout, attempt, slot, path, and artifact-limit bounds;
- 64 named controls reject malformed encoding, files, lines, syntax, duplicates, unknown keys, order, truncation, versions, identifiers, numeric non-canonicality/overflow/range, traversal/root/case/suffix paths, output capacity, count mismatches, and observed artifact sizes;
- 16,384 deterministic generated and mutated inputs compare complete Rust/Python semantic or error summaries with zero mismatches;
- `runs/native_boot_config_readiness.json`, release gate, Doctor, architecture baseline, roadmap, and public-boundary controls bind the candidate contract and nonclaims.

Cycle 100 PKELF1 evidence:

- `specs/native-elf-loader-contract.json` defines the strict ELF64 little-endian System V x86-64 `ET_DYN` profile, exact seven-program-header layout, three contiguous `r`/`rx`/`rw` loads, bounded high-half and physical bases, relative relocations, transactional mutation, and post-relocation W^X map plan;
- `native/elf` provides a dependency-free allocation-free `no_std` inspector/loader, and PooleBoot has a compile-time dependency plus re-export without claiming live file I/O, firmware allocation, mappings, or transfer;
- `runtime/native_elf_loader.py` independently validates and loads the same synthetic images as prohibited-from-production host evidence;
- three exact vectors cover two, 32, and the maximum 4,096 relative relocations with exact file, image, semantic, and post-load SHA-256 bindings;
- 129 named controls reject malformed headers, segments, dynamic state, relocations, permissions, ranges, bases, capacities, transactional mutation, and claim overreach;
- 16,384 deterministic generated and mutated inputs produce 8,071 shared accepts, 8,313 shared rejects, and zero Rust/Python mismatches;
- `runs/native_elf_loader_readiness.json`, release gate, Doctor, architecture baseline, roadmap, and public-boundary controls bind the candidate contract and nonclaims.

Cycle 102 PKLOAD1 evidence:

- `specs/native-kernel-load-contract.json` freezes the exact `LoadedImage -> DeviceHandle -> SimpleFileSystem -> OpenVolume` call chain, PBC1 and PKELF1 paths, file bounds, page arithmetic, mapping-plan validation, resource stack, 17 markers, 30 controls, and nonclaims;
- `native/bootload` implements the dependency-free `no_std` pure contract, while `native/boot/src/kload.rs` provides the raw UEFI adapter and fails closed on malformed file metadata, partial reads, arithmetic overflow, allocation/load errors, writable-executable plans, and cleanup failures;
- PooleBoot opens and parses the 231-byte live PBC1 file, reads the real 139,264-byte Cycle 101 PooleKernel PKELF1 image, allocates 48 `EfiLoaderData` pages, materializes 196,608 bytes with 40 relative relocations, validates four `r`/`rx`/`r`/`rw` ranges and zero W+X mappings, then closes three handles and frees two pools plus all 48 pages;
- the fixed `\EFI\POOLEOS\KERNEL.ELF` path is explicitly `fixed_untrusted`: PBC1 names a manifest, no manifest is opened, and no hash, signature, revocation, Secure Boot, TCG2, or TPM state authenticates selection;
- `runtime/native_kernel_load.py` independently builds and inspects exact three-file GPT/FAT32 media, parses PBC1 and PKELF1, reconstructs loaded bytes, and binds the guest FNV-1a result without entering the production boot chain;
- `runs/native_kernel_load_readiness.json` records 33/33 Rust host tests, two exact 45,056-byte PooleBoot builds, two exact canonical kernel builds, two exact 67,108,864-byte media generations, two fresh-vars QEMU/OVMF runs, 17/17 ordered markers, 30/30 hostile controls, exact guest/oracle agreement, zero production claims, and `n5_exit_gate_satisfied=false`.

Cycle 103 PSM1 and PKLOAD2 evidence:

- `specs/native-system-manifest-contract.json` freezes strict printable-ASCII/LF PSM1, 65,536-byte/192-line/16-artifact bounds, exact canonical field order, root-confined uppercase paths, one PKELF1/PKENTRY1 kernel, and slot/version/file/image/SHA-256 binding;
- `native/manifest` is the allocation-free `no_std` Rust parser and digest adapter; `runtime/native_system_manifest.py` is the independent host oracle; 8/8 Rust tests, two `no_std` targets, one PooleBoot integration build, 3/3 vectors, 64/64 controls, 16,384 differential cases, and 1,027 independent SHA-256 cases pass with zero mismatch;
- PBDIGEST1 pins vendored RustCrypto `sha2` 0.11.0, default features off, the `soft-compact` UEFI backend, locked checksums, and `/pooleos/native` path remapping; independent cryptographic/supply-chain review and target-backend promotion remain open under `ADD-BOOT-003` and `FLAG-N6-BOOT-DIGEST-001`;
- PooleBoot opens live PBC1, then its selected 462-byte `SYSTEM_A.PBM`, binds slot/version/path/file/image/digest/entry fields, hashes the 139,264-byte kernel before allocation and again before loading, materializes 196,608 bytes with 40 relocations, validates four W^X-safe mapping ranges, then closes four handles, frees three pools, and frees all 48 pages;
- two exact 61,440-byte PooleBoot builds, two exact kernel builds, two exact four-file 64 MiB media images, two fresh-vars QEMU/OVMF runs, 19 ordered markers, 40/40 integration controls, and exact guest/oracle agreement pass with `selection=manifest_digest_untrusted`, `entry=not_called`, and `n5_exit_gate_satisfied=false`.

Cycle 104 live PBP1 and PKLOAD3 evidence:

- `native/livehandoff` provides a dependency-free allocation-free `no_std` builder that accepts UEFI descriptor strides from 40 through 256 bytes, normalizes known source types while preserving attributes, sorts by physical address, and rejects malformed strides, versions, ranges, overlaps, types, and capacity failures before emitting canonical records;
- PooleBoot allocates all snapshot buffers before its provisional map, performs a bounded four-attempt map acquisition, binds required core, normalized memory map, and loaded-kernel artifact records plus optional GOP framebuffer, then requires the pre-exit profile to pass and the kernel-entry profile to reject because stack and CR3 remain zero;
- the live 4,248-byte snapshot contains four records and 95 stride-48 memory descriptors, binds the exact 139,264-byte kernel file and 196,608-byte live image, PSM1 SHA-256, entry, virtual bounds, PBC1 attempt/slot policy, and GOP; both serial and debugcon `PBP1HEX/0.1` transcripts reconstruct the exact bytes under the independent Python oracle;
- PooleBoot rechecks the snapshot after transcript emission, frees all three PBP1 pools, then frees all 48 kernel pages; a later diagnostic map observation is not the final `ExitBootServices` map and makes no hardware read-only, retained-handoff, or transfer claim;
- 49/49 Rust host tests, two exact 81,408-byte PooleBoot builds, two exact kernel builds, two exact four-file 64 MiB media images, two fresh-vars QEMU/OVMF runs, 21 ordered markers, 52/52 integration controls, and two exact PBP1 oracle matches pass with `state=pre_exit`, `entry=not_called`, and `n5_exit_gate_satisfied=false`.

Cycle 105 PKMAP1 and PKLOAD4 evidence:

- `specs/native-kernel-map-contract.json`, `native/kmap`, `runtime/native_kernel_map.py`, and `docs/native-kernel-map.md` freeze an exact 48-page supervisor mapping at `0xFFFFFFFF80000000`: 6 read-only pages, 28 read-execute pages, 14 read-write pages, and zero writable-executable pages under PML4/PDPT/PD/PT indices `511/510/0/0`;
- PKMAP1 requires CR0.WP, processor NX support, and EFER.NXE; this bounded profile fails closed on LA57, PCID, an occupied PML4 slot, malformed alignment/coverage/ranges, table overlap, writable-executable leaves, physical or permission drift, large leaves, framebuffer drift, activation/rollback failure, firmware use while active, cleanup failure, marker drift, and oracle divergence;
- PooleBoot allocates four private page-table pages, clones the active PML4, verifies the candidate hierarchy before activation, disables interrupts, installs the candidate CR3, walks every leaf, hashes all 196,608 higher-half bytes to `80F8CD80B30B2EBA`, and matches the normalized leaf fingerprint `A671D0D8901064A5`;
- framebuffer first/last translations, effective permissions, two 2 MiB source leaf sizes, and PAT/PCD/PWT signature `00` remain equal; zero firmware calls occur while the candidate root is active; the exact original CR3 is restored and read-verified before interrupts or firmware resume; all four table pages and all 48 kernel pages are then released;
- 10/10 PKMAP1 Rust tests and 11 focused Python contract/oracle tests pass; aggregate PKLOAD4 records 59/59 Rust host tests, two exact 94,720-byte PooleBoot builds, two exact kernel and media generations, two fresh-vars QEMU/OVMF runs, 23 ordered markers, 77/77 hostile controls, two exact PBP1 matches, and exact guest/oracle mapping agreement with `entry=not_called`, `n5_exit_gate_satisfied=false`, and `production_ready=false`.

Cycle 106 PKMAP2, PBLIVE2, PBEXIT1, and PKLOAD5 evidence:

- PKMAP2 now covers the exact 64-page kernel plan and adds four retained page-table pages, fourteen RW/NX stack pages bracketed by absent guards, and 256 RO/NX handoff pages; the independent Rust/Python retained-layout model is bound by the current contract and generated readiness artifacts;
- PooleBoot activates the candidate root only for complete kernel-alias and framebuffer verification, restores the exact original CR3 before the final firmware sequence, and retains the private root instead of releasing it;
- PBLIVE2 serializes the successful final map directly into the retained one-MiB allocation, binds nonzero root/stack/handoff state, requires loader-reserved coverage for every retained physical range, and deliberately rejects the unsigned kernel-entry profile;
- PBEXIT1 preallocates all storage, obtains the map immediately before exit, retries only `EFI_INVALID_PARAMETER` with a fresh key for at most four attempts, forbids unrelated firmware after the first attempt, and proves zero firmware calls after success;
- after successful `ExitBootServices`, PooleBoot disables interrupts, verifies unchanged PBP1 bytes, emits direct COM1/debugcon diagnostics, and halts permanently at `STOP BEFORE TRANSFER` without changing CR3/RSP or calling PooleKernel;
- 14/14 PKMAP2 tests, 5/5 PBEXIT1 tests, 8/8 PBLIVE2 tests, and focused independent Python tests pass; aggregate PKLOAD5 records 70/70 Rust host tests, two exact 104,960-byte PooleBoot builds, two exact kernel and media generations, two fresh-vars QEMU/OVMF runs, 22 ordered markers, 95/95 hostile controls, and two exact 4,208-byte PBP1 reconstructions with 94 memory entries;
- `FLAG-N5-HANDOFF-EXIT-001` closes only this retained exit-and-stop boundary. The observed OVMF path exits on attempt one; stale-key retry is state-machine and negative-control evidence, not a naturally observed stale-key event.

Cycle 107 PBART1, PBLIVE3, and PKLOAD6 evidence:

- `native/artifact` freezes the dependency-free `no_std` PBART1 envelope at 96 header bytes with exact magic/version/role/artifact-version/payload-length/payload-SHA-256/reserved-zero validation; the independent Python oracle and Rust probe agree for all six canonical artifacts plus a hostile digest case;
- PSM1 now requires exactly seven ordered IDs and roles: PKELF1 kernel plus initial-system, recovery, symbols, microcode, firmware manifest, and policy PBART1 files; each path, version, byte count, and whole-file digest is bound before loading;
- PooleBoot opens ten media files, closes ten handles, frees nine intake pools, allocates six distinct `EfiLoaderData` ranges, copies exact file bytes, zeroes page padding, and releases every loaded range on pre-exit failure while retaining all seven artifact ranges on success;
- PBLIVE3 requires roles 1 through 7, exact digests, non-overlapping physical ranges, physical-only non-kernel entries, no executable auxiliary flags, and final-map loader coverage for all seven artifacts plus PKMAP2 tables, stack, and handoff;
- PKLOAD6 passes 76/76 Rust checks, two exact 113,664-byte PooleBoot builds, two exact kernel and ten-file media generations, two fresh-vars QEMU/OVMF runs, 23 ordered markers, 112/112 hostile controls, and two exact 4,728-byte PBP1 reconstructions with seven artifacts and 95 memory entries;
- `FLAG-N5-INIT-SYSTEM-001` closes only the unsigned envelope/load/retain/PBP1-bind boundary. `FLAG-N5-INIT-SEMANTICS-001` remains open for each inner format, capability/resource declaration, dependency graph, lifecycle, and apply/execute precondition.

Cycle 108 PINIT1 and integrated host-oracle evidence:

- `specs/native-initial-system-contract.json` freezes a 192-byte header and five canonical tables for components, services, dependencies, resources, and attenuated capability routes, with exact bounds, ordering, UTF-8, zero padding, reserved fields, identifiers, digests, table geometry, and body hash;
- `native/initsys` provides the dependency-free allocation-free `no_std` parser for both native targets, while `runtime/native_initial_system.py` independently constructs, parses, validates, summarizes, and applies activation preconditions as prohibited-from-production host evidence;
- the canonical 1,764-byte bundle at SHA-256 `FFE7243CEE75963D84905E6C9BF9F0D04310EEDBF097757C32E0EBE30FA0C3ED` contains three components, three services, three dependencies, four abstract resources, and eleven attenuated routes with deterministic start order `1,2,3`;
- strong dependencies form a complete deterministic DAG; weak dependencies may not conceal a strong cycle; executable services target only executable PXABI1 components; route sources and destinations are type-checked; every grant is bounded by its source rights and destination quota; declarations are inert IDs, not kernel handles or addresses;
- transactional start, reverse rollback, default deny, bootstrap-authority drop, outer and inner signature requirements, rollback state, and component ABI validation are mandatory. Unsigned development media parses for analysis but fails activation before authority creation or execution;
- 3/3 Rust tests, 2/2 `no_std` targets, 3/3 golden vectors, 120/120 parser and activation controls, and 16,384 deterministic Rust/Python cases pass with zero mismatches. The campaign found and fixed a data-component service-target acceptance defect and an independent diagnostic-precedence mismatch;
- PKLOAD6 and the aggregate PooleBoot receipt bind the exact PINIT1 payload and add three hostile integration controls for inner semantics, inner version, and activation overreach, reaching 115/115 controls while retaining explicit false claims for PooleBoot semantic enforcement and PooleKernel activation;
- `FLAG-N5-INIT-BUNDLE-001` closes only this declaration-format, parser, independent-oracle, and activation-denial boundary. `FLAG-N5-INIT-SEMANTICS-001` remains open for recovery, symbols, microcode, firmware, policy, live capability construction, process launch, lifecycle execution, and rollback.

Cycle 109 PREC1 recovery policy, state, and transition evidence:

- `specs/native-recovery-contract.json` freezes an exact 992-byte immutable policy with a 256-byte header, two 96-byte slot records, ten 32-byte failure rules, and seven 32-byte authority requirements; a separate exact 128-byte mutable record carries authenticated-generation inputs, slot masks, attempts, safe-mode history, failure, and in-flight receipt binding;
- `native/recovery` provides dependency-free allocation-free `no_std` policy/state parsing and transition functions for both native targets, while `runtime/native_recovery.py` independently constructs, parses, validates, transitions, validates success/failure receipts, and evaluates activation as prohibited-from-production host evidence;
- the canonical policy is 992 bytes at SHA-256 `BA63DF2A44AD51EBEEDBE3F05D2D4D13FAF68CF6A2024A7DE355A86A4D0D666C`; its canonical mutable state is 128 bytes at SHA-256 `23EC98523CABC73C77A9A655355398618C620FE1A982CA4F78AA05C4BEF9D505`;
- candidate attempts decrement and require persistence before handoff; exhausted candidates retire to previous-known-good, safe mode is attempted at most once per eligible slot, invalid or unwritable state routes to recovery, and firmware/destructive authority requires physical presence plus explicit declared prerequisites;
- the state checksum is a 16-byte truncated SHA-256 corruption detector, not authentication. Activation separately requires outer, inner, and manifest signatures; authenticated monotonic writable state; version floor; verified components and ABI; offline independence from PDC and PooleGlyph; serial or GOP/software recovery; transaction capacity; retained evidence; and rollback readiness;
- 3/3 Rust tests, 2/2 `no_std` targets, 3/3 exact policy/state/transition vectors, 144/144 parser/state/transition/receipt/activation controls, 16,384 parser/state cases, and 8,192 generated transitions pass with zero Rust/Python mismatches;
- the canonical role-3 PBART1 payload now carries exact PREC1 bytes. PKLOAD6 and aggregate PooleBoot add recovery-inner-semantics, recovery-inner-version, and recovery-activation-overreach controls, reaching 118/118 while retaining false claims for PooleBoot PREC1 enforcement, PooleKernel recovery execution, persistent state I/O, recovery authority, disk writes, and production readiness;
- `ADD-BOOT-006` records the immutable-policy/mutable-state separation and authenticated transition requirements. `FLAG-N5-RECOVERY-BUNDLE-001` closes only this policy/state/parser/transition/receipt/activation-denial boundary; broad `FLAG-N5-INIT-SEMANTICS-001` remains open for live PINIT1/PREC1 enforcement and the symbol, microcode, firmware, and policy formats.

Cycle 110 PSYM1 public symbol and split-debug evidence:

- `specs/native-symbol-contract.json` freezes a bounded 384-byte header, dense 32-byte segment records, 48-byte public symbol records, and a compact ASCII string region with exact size, count, name, lookup-step, reserved-zero, ordering, non-overlap, and body-digest rules;
- the bundle binds the exact stripped PKELF1 file, preferred loaded image, build ID, private split-debug ELF, and source manifest. Addresses are image-relative offsets; the aligned KASLR runtime base is an explicit lookup input and no absolute runtime address is stored;
- `native/symbols` provides dependency-free allocation-free `no_std` parsing and bounded binary-search lookup for both native targets, while `runtime/native_symbols.py` independently constructs, parses, inspects debug ELF, checks split-debug correspondence, performs lookup, and evaluates consumption preconditions as prohibited-from-production host evidence;
- the canonical bundle contains three explicitly public default-visible PooleKernel functions. Source paths, local/private symbols, line/type/local metadata, and the full debug ELF are excluded from boot media; runtime diagnostics default to pointer redaction;
- two full-debug builds are byte-identical, both canonicalize to the exact stripped PKELF1 image, and the separately stripped release build has no `.symtab` or `.debug*` sections. The three PooleOS compilation units are DWARF 5 while pinned prebuilt sysroot units remain DWARF 4, an explicit provenance limit rather than a whole-program DWARF 5 claim;
- 4/4 Rust tests, 2/2 `no_std` targets, 3/3 exact vectors, 158/158 parser/lookup/debug/consumption controls, 16,384 parser cases, and 16,384 lookup cases pass with zero Rust/Python mismatches. Unsigned development consumption fails closed;
- the canonical role-4 PBART1 payload now carries exact PSYM1 bytes. PKLOAD6 and aggregate PooleBoot add symbol-inner-semantics, symbol-inner-version, and symbol-consumption-overreach controls, reaching 121/121 while retaining false claims for PooleBoot/PooleKernel consumption, kernel exports, diagnostic authority, default runtime-address disclosure, full debug data on media, and production readiness;
- `ADD-BOOT-007` records the identity/address/privacy/consumption boundary. `FLAG-N5-SYMBOL-BUNDLE-001` closes only this format/parser/lookup/correspondence/privacy/consumption-denial slice; broad `FLAG-N5-INIT-SEMANTICS-001` remains open for live PINIT1/PREC1/PSYM1 enforcement and the microcode, firmware, and policy formats.

Cycle 111 PMCU1 microcode-package and apply-policy evidence:

- `specs/native-microcode-contract.json` freezes a 512-byte header, bounded 128-byte patch records, aligned opaque payloads, complete package/body/header/payload/metadata SHA-256 bindings, exact `AuthenticAMD` and CPUID `0x00B40F40` identity, package trust/license/revocation/hardware-profile identities, and a one-MiB PBART1-compatible envelope bound;
- normal selection chooses the highest eligible non-revoked revision at or above package and authenticated rollback floors. Previous-known-good mode selects only the exact known-good record; a newer in-session revision requires reset rather than downgrade. Mixed per-processor state fails closed or requires quarantine before user scheduling;
- apply planning requires authenticated outer, inner, manifest, vendor, revocation, license, hardware, CPUID, and revision evidence; complete quiesced processor inventory; early PooleKernel timing before affected features and user work; BSP then every AP application; bounded capacities; explicit apply authority; post-apply revision and CPUID re-evaluation; mitigation-policy revalidation; and durable receipts;
- `native/microcode` provides dependency-free allocation-free `no_std` parsing, selection, apply-plan gating, and post-apply validation for both native targets. `runtime/native_microcode.py` independently encodes, parses, selects, gates, and verifies as prohibited-from-production host evidence;
- 4/4 Rust tests, 2/2 `no_std` targets, 3/3 exact vectors, 174/174 controls, 16,384 parser cases, 16,384 selection cases, and 8,192 post-apply cases pass with zero mismatches. A differential campaign exposed and fixed one parser validation-order mismatch;
- all 35 checked-in payloads and all `0xF1A440xx` revisions are visibly synthetic qualification data marked never-apply. No real vendor container, production payload, redistribution approval, privileged microcode-revision observation, WRMSR, firmware call, driver load, CPU rendezvous, update, firmware mutation, or physical-media write exists;
- the canonical role-5 PBART1 payload now carries exact PMCU1 bytes. PKLOAD6 and aggregate PooleBoot add microcode-inner-semantics, microcode-inner-version, and activation-overreach controls, reaching 124/124 while retaining false claims for PooleBoot/PooleKernel enforcement, privileged observation, vendor validation, application, firmware mutation, physical-media write, N5 exit, and production readiness;
- `ADD-BOOT-008` records the production microcode obligations. `FLAG-N5-MICROCODE-BUNDLE-001` closes only this wrapper/parser/selection/apply-plan/post-verify/development-denial slice; broad `FLAG-N5-INIT-SEMANTICS-001` remains open for live PINIT1/PREC1/PSYM1/PMCU1 enforcement and the firmware-manifest and policy formats.

Cycle 112 PFWM1 firmware-manifest and dry-run-policy evidence:

- `specs/native-firmware-contract.json` freezes a 512-byte header, bounded 256-byte component records, 16-byte dependency records, 64 KiB manifest and 64 MiB declared external-payload limits, exact resource GUID and nonzero hardware-instance identity, current/target/lowest/floor/known-good versions, and payload/device/vendor-signer/updater-plugin/recovery bindings;
- three canonical synthetic-only components normalize UEFI capsule/ESRT, exact device-plugin, and PLDM routes without treating any transport as generic flashing. Two edges form an acyclic topological order, and a plan permits one active component per durable transaction;
- dry-run authorization checks 47 ordered prerequisites covering outer and inner signatures, exact target inventory and versions, transport/plugin authority, external payload and license/revocation evidence, antirollback, recovery and backup, protected staging and capacity, AC/battery/power, durable journal, device and storage quiescence, suspend/shutdown guards, reset/reboot authority, user and physical confirmation, post-reset verification, receipt storage, explicit firmware-change authority, and qualification-only non-overreach;
- post-reset validation binds every component's resource identity, hardware instance, target and last-attempt versions/status, re-enumeration, self-test, recovery, durable receipt, boot-loop guard, and state commit; driver rebinding is permitted only after all checks pass;
- `native/firmware` provides dependency-free allocation-free `no_std` parsing, dry-run planning, and post-reset validation for both native targets. `runtime/native_firmware.py` independently encodes, parses, authorizes, and validates as prohibited-from-production host evidence;
- 5/5 Rust tests, 2/2 `no_std` targets, 3/3 exact vectors, 101/101 controls, 16,384 parser cases, 8,192 activation cases, and 8,192 post-reset cases pass with zero Rust/Python mismatches. Differential testing exposed and fixed an unbounded Python phase-range allocation before qualification;
- the canonical 1,312-byte role-6 PBART1 payload embeds zero firmware bytes and is marked synthetic qualification never-apply. PKLOAD6 and aggregate PooleBoot add firmware-inner-semantics, firmware-inner-version, and activation-overreach controls, reaching 127/127 while retaining false claims for live inventory, vendor payload validation, updater load, PooleBoot/PooleKernel enforcement, capsule submission, reset, mutation, physical-media write, N5 exit, and production readiness;
- `ADD-BOOT-009` records production firmware obligations. `FLAG-N5-FIRMWARE-BUNDLE-001` closes only this manifest/parser/dependency/dry-run/post-reset/development-denial slice; broad `FLAG-N5-INIT-SEMANTICS-001` remains open for live PINIT1/PREC1/PSYM1/PMCU1/PFWM1 enforcement and the role-7 policy format.

Cycle 113 PPOL1 default-deny system-policy evidence:

- `specs/native-policy-contract.json` freezes a 512-byte header, six exact 128-byte mode records, bounded 64-byte capability rules, a 64 KiB policy limit, exact body and PINIT1 identities, policy and generation floors, and fail-closed unknown-bit, reserved-field, table-geometry, ordering, and digest rules;
- effective authority is modeled only as `built-in ceiling & authenticated policy & selected mode & issued capability & request`; child rules remain parent-monotonic, no rule may amplify PINIT1 rights/effects, and the exact eleven-route PINIT1 set must cross-bind without omission, substitution, or surplus;
- normal, safe, previous, recovery, diagnostic, and firmware modes have explicit default-deny ceilings. Safe and recovery retain compiled-in floors that policy cannot widen; firmware requires physical presence and a separately authenticated authority even in the synthetic qualified context;
- activation is ordered and separately requires outer, inner, and manifest signatures; authenticated generation, revocation, and rollback state; exact mode and PINIT1 binding; issued capability state; audit durability; and no requested live effects. The checked-in development context fails first at `ppol_activation_outer_signature`;
- decision receipts bind policy digest, mode, capability, generation, revocation epoch, rights, effects, request, result, and durability. Receipt validation writes nothing and grants no authority;
- `native/policy` provides allocation-free `no_std` parsing, cross-binding, dry-run authorization, and receipt validation for both native targets. `runtime/native_policy.py` independently encodes, parses, authorizes, and verifies as prohibited-from-production host evidence;
- 6/6 Rust tests, 2/2 `no_std` targets, 3/3 exact vectors, 116/116 controls, 8,192 parser cases, 4,096 cross-binding cases, 12,288 activation cases, and 8,192 receipt cases pass with zero Rust/Python mismatches;
- the canonical role-7 PBART1 payload now carries exact 1,984-byte PPOL1 bytes. PKLOAD6 and aggregate PooleBoot add policy-inner-semantics, policy-inner-version, and activation-overreach controls, reaching 130/130 while retaining false claims for live PooleBoot/PooleKernel enforcement, authority creation, state mutation, applied decisions, PooleGlyph executable authority, physical-media write, N5 exit, and production readiness;
- `ADD-BOOT-010` records production policy obligations. `FLAG-N5-POLICY-BUNDLE-001` and `FLAG-N5-INIT-SEMANTICS-001` close only the independent six-format semantics boundary. `FLAG-N5-INNER-ENFORCEMENT-001` remains open for live target parsing, authentication, state persistence, capability creation, lifecycle execution, audit, and rollback.

Cycle 114 retained-page inner parsing evidence:

- `native/inner` is an allocation-free `no_std` crate that accepts exactly six ordered PBART1 files, invokes the PINIT1, PREC1, PSYM1, PMCU1, PFWM1, and PPOL1 parsers, binds each outer role/version to the inner contract, and fails closed on any parser, ordering, or version error;
- after all firmware-page copies complete, `native/boot/src/kload.rs` reconstructs slices from the retained physical page ranges rather than trusting pre-copy input or a parser summary. It validates PPOL1's exact five payload digests and eleven PINIT1 capability routes, then calls each development action or consumption gate and requires the first failure to be the absent outer signature;
- the retained-set identity is `SHA256("POOLEOS/INNER-LIVE-SET/V1\0" || role_le32 || file_len_le64 || exact_file_bytes)` for roles 2 through 7. The canonical result is `F3154B354C77D0567207994EFDDA4FE2D203611CA21D60B63872BC9FFC73C675` over 8,761 file bytes and 8,185 payload bytes;
- the live `INNER_SET` marker records six parsers, six cross-bindings, six mandatory denials, exact retention, and zero authority grants, authorized actions, state writes, and hardware observations. Both serial and debugcon emit identical receipts across two clean QEMU/OVMF runs;
- `runtime/native_inner_live.py` independently reconstructs the same bytes and policy. Five Rust unit tests, five Rust/Python canonical/hostile differential cases, both native target checks, 81/81 aggregate Rust host tests, 24 ordered markers, and 139/139 integrated controls pass;
- `ADD-BOOT-011` requires independent PooleBoot and PooleKernel reparsing of exact retained bytes before authority. Cycle 114 closes the live PooleBoot half through `FLAG-N5-INNER-PARSE-001`; Cycle 117 closes the allocation-free standalone PooleKernel verifier through `FLAG-N5-INNER-KERNEL-REVALIDATE-001`; and Cycle 118 closes the opt-in QEMU live-execution boundary through `FLAG-N5-KERNEL-TRANSFER-001`. Authenticated state and authority enforcement remain open.

Cycles 115-116 boot trust policy/state and backend-model evidence:

- `specs/native-boot-trust-contract.json` freezes PBTRUST1 as a 320-byte PBTP1 immutable-policy record and a separate 256-byte PBTS1 mutable acceptance-state record. PREC1 mutable boot-attempt state remains a third contract with no overloaded authority;
- PBTP1 binds exact PSM1, PooleKernel, retained-set, and revocation-set digests; seven artifact roles; policy, secure-version, state-generation, and trust-epoch floors; bounded signer threshold and signature shape; and deterministic body identity. PBTS1 binds the accepted policy, manifest, kernel, and retained set plus copy index/count, commit state, generation, previous-state identity, and authentication-profile shape;
- authorization applies fourteen exact binding and rollback checks before eight external evidence gates for policy signature, signer threshold, revocation authentication/non-revocation, state authentication, monotonicity, backend writability, and Secure Boot state. The checked-in development policy then denies exactly at `pbtrust_policy_unsigned`;
- `native/trust` provides allocation-free `no_std` parsing, authorization-order modeling, and PBSTATE1 two-copy backend selection and transition planning. `runtime/native_boot_trust.py` independently encodes, parses, authorizes, selects, and models recovery. Twelve Rust tests, both native target builds, one PooleBoot UEFI integration build, 105/105 hostile controls, and four independent 8,192-case policy-parser, state-parser, authorization, and backend-selection campaigns pass with zero mismatch;
- live PooleBoot reads exact `TRUST.PBT` and `TRUSTST.PBS` development candidates from the twelve-file medium, cross-binds fourteen facts, emits one `TRUST_STATE DENY` marker, grants zero authority, and writes zero state. The Cycle 125-refreshed PKLOAD6 passes 139/139 Rust tests, 25 markers, and the current integrated hostile corpus across two exact QEMU/OVMF runs;
- PBSTATE1 requires an externally authenticated monotonic anchor and per-copy authentication evidence; selects only an exact logical generation/epoch/profile/previous-chain/digest match; requires writable repair capacity; rejects stale, future, rollback, malformed, mismatched, overflow, and migration-rollback states; and emits a deterministic alternate-copy transition plan with zero performed effects;
- nine power-loss cases cover pre-write, torn target body, target flush, target commit/authentication, commit flush, anchor advance, anchor verification, torn repair, and final verification. Before anchor advancement the old generation wins; afterward the new generation wins and the other copy is repaired. Rust and Python agree for every case;
- the ESP state candidate is explicitly not persistent authority: it is unauthenticated, non-monotonic, non-writable, and neither selected, repaired, migrated, nor committed. The PBSTATE1 model performs no cryptography, backend I/O, anchor update, repair, migration, state write, or authority grant. No key, cryptographic signature verification, revocation store, Secure Boot variable observation, TPM state, firmware mutation, or physical-media write exists;
- `ADD-BOOT-012` requires separate trust-policy, acceptance-state, and recovery-attempt contracts plus a redundant authenticated transactional backend, deterministic copy selection, previous-state chaining, rollback floors, torn-write/power-loss recovery, and independent PooleKernel revalidation. Cycle 115 closes `FLAG-N5-INNER-TRUST-CONTRACT-001`; Cycle 116 closes the pure PBSTATE1 backend model; Cycle 117 closes exact standalone PooleKernel PBTP1/PBTS1 reparsing; and Cycle 118 proves the same denial live only in QEMU development mode. A real cryptographic monotonic writable provider, persistent backend I/O, and broad enforcement remain open.

Cycle 117 independent PooleKernel revalidation evidence:

- PBP1 1.0 retains its wire layout but the loaded-artifact role profile is now exact and positional: kernel; six PBART1 roles; reserved crash-kernel slot; PSM1; PBTP1; and PBTS1. The live development message carries ten descriptors because the reserved crash-kernel slot remains absent;
- PooleBoot copies PSM1, PBTP1, and PBTS1 into final page allocations, reparses the final destination bytes, frees their source pools, and requires PKMAP2 identity coverage for every retained allocation. Non-kernel descriptor sizes are exact file-byte counts; allocation-page rounding is never accepted as file identity;
- `native/kernel/src/revalidation.rs` accepts only the frozen role order, disjoint retained ranges, exact file sizes and SHA-256 values, canonical PSM1, six PBART1 envelopes and inner contracts, PBTP1, and PBTS1. It reconstructs PSM1 artifact bindings, PPOL1 payload bindings, PINIT1 routes, and PBTRUST1 policy/state bindings before requiring exact unsigned-policy denial;
- the safe verifier is allocation-free and `no_std`. Its narrow unsafe entry bridge forms slices only after fixed-count profile, nonzero locator, exact-size, overflow, range, and overlap validation. Loader summaries cannot substitute for final retained bytes;
- 54/54 Rust tests, 8/8 Python tests, both `x86_64-unknown-none` and `x86_64-unknown-uefi` builds, 36/36 hostile controls, and 32,768/32,768 deterministic mutation rejects pass. The current live six-PBART1 retained-set SHA-256 is `2A80BA31090B247D7CE28FFCCCB1BBD936B4544E8052888EA8D992C51F4F91AE`, with PSM1/PBTP1/PBTS1 bound separately;
- the expanded verifier requires a 262,144-byte PooleKernel image with a 192,512-byte canonical file, entry offset `0x8000`, and 401 relative relocations. PKMAP2 covers 64 kernel pages with 13 read-only, 34 executable, and 17 read-write leaves, then places low guard/stack/high guard at pages 64/65-78/79 and the handoff allocation at page 80;
- PKLOAD6 passes 139/139 Rust tests, two exact PooleBoot and PooleKernel builds, two exact media generations, two QEMU/OVMF producer runs, 25 markers, 155/155 hostile controls, and two independent 5,048-byte PBP1 reconstructions with 97 memory descriptors and ten artifact descriptors;
- `FLAG-N5-INNER-KERNEL-REVALIDATE-001` closes only the exact host-executed verifier boundary. PooleBoot still stops permanently before transfer, so `FLAG-N5-KERNEL-TRANSFER-001` is open for final CR3/RSP installation, one-way entry, live PKREVAL1 execution, and a terminal zero-authority denial receipt.

Cycle 118 one-way development transfer evidence:

- Cargo feature `development-transfer` is opt-in and disabled by default. A separate default build contains `STOP BEFORE TRANSFER` and no `TRANSFER_ARM`, preserving the established fail-closed aggregate proof;
- after successful `ExitBootServices`, PooleBoot validates a terminal emulator-only transfer envelope, allows only CR3 PWT/PCD low bits, emits `TRANSFER_ARM` and a one-way boundary, executes `cli` and `cld`, installs retained CR3 and guarded RSP, places the exact PBP1 address/length/magic in `RDI`/`RSI`/`RDX`, and jumps once to the manifest-bound entry;
- the PooleKernel assembly wrapper validates the incoming stack before a language call, captures CR3 and RFLAGS, and enters Rust once. Rust verifies exact handoff, stack, root, low CR3 flags, IF/DF state, ten-descriptor development profile, and null post-exit UEFI pointers;
- live PKREVAL1 independently reparses all nine retained files and emits exact `ENTRY`, `STATE`, `PBP1`, `PKREVAL`, and `TRANSFER-DENIED` markers over COM1 and debugcon before a permanent halt;
- two exact kernel builds, two feature-enabled PooleBoot builds, one default isolation build, two byte-identical media generations, and two fresh-vars QEMU/OVMF runs reproduce all 30 markers, exact PBP1 bytes, and exact guest/host denial. The Cycle 125-refreshed 192,512-byte PooleKernel has SHA-256 `F449D0E037571345A40162DC9A943A2FA01F1195F21C239C8D8F1A85D39CA06E`; all 58 hostile controls still pass;
- `FLAG-N5-KERNEL-TRANSFER-001` closes only this unsigned QEMU development boundary. Signature verifications, authority grants, actions, state writes, and post-exit firmware calls remain zero; the ordinary boot build remains stopped.

N5.1-N5.9 remain partial. PooleBoot now performs bounded live intake, exact retention, parsing and cross-binding, final PBLIVE3 production, successful `ExitBootServices`, and either the ordinary firmware-free stop or the explicit QEMU-only PKXFER1 transfer. PBSTATE1 still models but does not perform authenticated persistent state selection or recovery. PooleBoot does not authenticate files, verify a policy signature or revocation store, use a real monotonic provider, perform persistent trust-state I/O, consume symbols, apply policy, observe Secure Boot state, privileged revisions, or live firmware inventory, or apply microcode or firmware. PooleKernel live-executes PKREVAL1 only to deny and halt; it creates no capability and executes no lifecycle, recovery, or policy action. The path still lacks authenticated rollback, a licensed real vendor payload, TCG2/TPM evidence, final framebuffer remap/revocation, production transfer, second-host reproduction, target firmware, physical media, ISO construction, and the N5 exit gate. The static identity is not the final animated PooleGlass boot experience or an accessibility result.

Exit gate: PooleBoot reproducibly boots under pinned OVMF and target firmware, validates all artifacts, exits boot services, transfers through a versioned golden-tested handoff, and rejects the complete hostile loader corpus.

### N6 - Boot Trust, Kernel Image, Early Runtime, and Emergency Diagnostics (`partial`)

Inherited sections: `016-019`, `148-149`. Added: `ADD-BOOT-002`, `ADD-BOOT-003`, `ADD-KERNEL-001`.
Goal: make the earliest native path authenticated, measurable, diagnosable, and recoverable before higher services exist.

Subphases:

- N6.1 Define offline root, release intermediates, development keys, PK/KEK/db/dbx interaction, key rotation, revocation, compromised-key response, and development-mode visibility.
- N6.2 Verify boot manifest, kernel, initial system, recovery, modules if ever allowed, firmware, PDC, and PooleGlyph policy by artifact type and minimum secure version.
- N6.3 Measure configuration and artifacts through TCG2 with documented PCR/event semantics and preserve the event log for local verification.
- N6.4 Freeze kernel ELF layout, relocation, KASLR policy, section permissions, debug symbols, map files, build ID, unwind strategy, and read-only-after-init behavior.
- N6.5 Enter on a known stack with interrupts disabled; validate handoff, reserve every range, establish canonical mappings, initialize bootstrap GDT/IDT/TSS, and run early self-tests.
- N6.6 Implement allocation-independent serial, framebuffer, and ring-buffer logs; bounded formatting; panic codes; register/control-state/page-fault dumps; nested panic; double-fault/NMI paths; and next-boot panic summary.
- N6.7 Implement 16550-compatible emergency serial discovery plus RTC/CMOS and UEFI-variable access with locking, validation, write limits, rollback state, and wake-alarm boundaries.

Cycle 101 PKENTRY1 evidence:

- `specs/native-kernel-entry-contract.json` freezes the direct-jump register, stack, mapping, image, diagnostic, panic, and nonclaim boundary and binds Rust, LLD, and x86-64 ABI authorities;
- `native/kernel` builds the real `PooleKernelLinked` freestanding image, while the prior empty image is isolated as `poolekernel-fixture` under `native/fixtures/poolekernel`;
- `runtime/native_kernel_image.py` fail-closes over pinned-LLD output and canonicalizes it into the existing PKELF1 profile without imports, section headers, host paths, writable-executable pages, or unbound manifest bytes;
- the Cycle 125-refreshed `runs/native_kernel_entry_readiness.json` records 54/54 host tests, two byte-identical clean linked and canonical builds, 43/43 hostile controls, 401 relative relocations, exact independent Rust/Python loaded bytes, and canonical SHA-256 `F449D0E037571345A40162DC9A943A2FA01F1195F21C239C8D8F1A85D39CA06E`;
- `ADD-KERNEL-001` and the refined PBP1/PKENTRY1 contracts expose the previously implicit framebuffer mapping dependency: the complete aperture needs a temporary writable, non-executable identity mapping with preserved cache policy and a defined revocation transition before graphics delegation;
- N6.4-N6.6 are only partial. PKXFER1 proves opt-in QEMU CR3/RSP installation, live COM1/debugcon/framebuffer diagnostics, and terminal unsigned denial; PKTRAP1, PKCPU1, and PKXSTATE1 separately prove only bounded BSP descriptor/exception, read-only CPU-policy, and x87/SSE ownership slices; and PKERR1 freezes only a pure exact-target rejection policy. KASLR, final debug/unwind policy, framebuffer remap/revocation, direct target errata and microcode-floor authority, complete per-CPU GDT/IDT/TSS/xstate state, early self-tests, all exception/NMI/machine-check paths, retained next-boot panic state, authenticated production transfer, target firmware, and boot trust remain open.

Exit gate: every accepted boot is signature/digest/version bound; revocation and malformed signatures fail closed into recovery; deliberate failures at every early stage yield retained serial evidence without silent reset loops.

### N7 - x86-64 CPU, Privilege, Descriptor, and Fault Foundation (`partial`)

Inherited sections: `020-022`. Added: `ADD-N7-ERRATA-SOURCE-001`, `ADD-N7-XSTATE-001`.
Goal: establish a correct processor contract before concurrency or user execution.

Subphases:

- N7.1 Enumerate CPUID leaves, topology, address widths, caches, APIC, NX, PCID, SMEP/SMAP/UMIP, FSGSBASE, XSAVE, entropy, virtualization, encryption, RAS, PMU, and thermal features.
- N7.2 Validate exact Ryzen 7 9800X3D family/model/stepping and microcode against errata; reject missing mandatory features precisely.
- N7.3 Define CR0/CR4/EFER, PAT/MTRR, syscall, GS, TSC_AUX, APIC, machine-check, and performance MSR policy with reserved-bit discipline.
- N7.4 Initialize x87/SSE/XSAVE state, per-thread vector areas, exception behavior, sensitive-state clearing, and kernel SIMD restrictions.
- N7.5 Build per-CPU GDT, TSS, RSP0, IST stacks, IDT stubs, uniform trap frames, and entry/exit assembly with generated offset validation.
- N7.6 Handle every architectural exception with user delivery or kernel panic policy, recursion limits, stack guards, and adversarial tests.

Cycle 119 PKTRAP1 evidence:

- the three opt-in features `development-trap-returning`, `development-trap-double-fault`, and `development-trap-malformed-frame` imply PKXFER1 but remain mutually exclusive and disabled from the default PooleBoot path;
- one BSP installs and reads back a five-entry GDT, a 104-byte TSS with retained `RSP0`, distinct 8,192-byte IST1/IST2 arrays, and a 256-entry IDT allocation whose only present gates are vectors 3, 6, 8, 13, and 14;
- assembly normalizes all fifteen general-purpose registers plus vector, error code, RIP, CS, RFLAGS, RSP, and SS into a 176-byte integer frame. Pure validation requires exact selectors, canonical addresses, clear IF/DF, depth one, expected origins, IST range, error code, and page-fault CR2 before any resume;
- two runs each return from exact deliberate `#BP`, `#UD`, and low-stack-guard `#PF`; contain a processor-delivered terminal `#DF` on IST2; and reject a code-selector mutation in an explicitly synthetic semantic copy;
- six fresh-vars QEMU/OVMF runs reproduce exact per-scenario markers, screenshots, and PBP1 bytes; all 51 hostile controls pass with zero signatures, authority, actions, state writes, post-exit firmware calls, or enabled interrupts;
- At the end of Cycle 119, only subphases N7.5 and N7.6 were partial. The IST arrays are unguarded kernel-data allocations, only five gates are present, and no AP-local state, user transition, asynchronous interrupt preservation, NMI, machine check, recursion recovery, persistent crash record, target-hardware evidence, or N7-exit claim follows.

Cycle 120 PKCPU1 evidence:

- Cargo feature `development-cpu-policy` implies PKXFER1, is disabled by default, is mutually exclusive with all PKTRAP1 features, and uses selector `4`; selector `0` and the ordinary stop-before-transfer profile remain unchanged;
- `native/kernel/src/arch/x86_64.rs` performs support-gated read-only CPUID, CR0/CR4, EFER/APIC/PAT/MTRR, and XGETBV observation. The validator requires long mode, NX, paging, write protection, protected mode, PAE, OSFXSR, OSXMMEXCPT, and a policy-consistent optional feature/control relationship while rejecting reserved bits and incoherent topology/address-width state;
- two fresh-vars qemu64 QEMU/OVMF runs reproduce 35 exact serial/debugcon markers and independently reconstructed observations: `AuthenticAMD`, family 15, model 107, stepping 1, 40-bit physical and 48-bit linear widths, CR0 `0x80010033`, CR4 `0x668`, EFER `0xD00`, APIC base `0xFEE00900`, PAT `0x0007040600070406`, MTRR capability `0x508`, and MTRR default type `0xC06`;
- 31/31 kernel host tests and 41/41 contract, parser, marker, feature, control-state, MSR, topology, address-width, no-write, no-authority, stale-binding, and profile-isolation controls pass with exact Rust/Python agreement;
- the profile performs five MSR reads and zero MSR or control-register writes; it verifies no signatures, grants no authority, authorizes no actions, writes no state, and makes no post-exit firmware calls;
- `FLAG-N7-CPU-POLICY-001` is closed only for this bounded BSP qemu64 read-only observation. N7.1 and N7.3 become partial; N7.2 exact Ryzen target-family/errata/microcode policy and N7.4 xstate ownership remain unstarted. Target hardware, AP-local state, syscall/GS/TSC_AUX/machine-check/performance MSRs, N7 exit, and production remain open.

Cycle 121 PKERR1 evidence:

- `native/cpupolicy` implements an allocation-free `no_std` policy evaluator for both native targets, while `runtime/native_kernel_errata_policy.py` independently implements the same ten fail-closed reason bits without sharing code or runtime dependencies;
- the contract requires CPUID signature `0x00B40F40`, long mode, NX, SSE2, XSAVE, OSXSAVE, FSGSBASE, SMEP, SMAP, and invariant TSC; exact board-lineage selection; stable BIOS `F39` for revisions 1.0-1.2 or `FA7` for revision 1.3; and the stronger AMD-SB-7055 comparison floor AGESA `1.2.0.3i`;
- AMD revision guide 58251 is cryptographically bound but marked nonapplicable because it covers Family 1Ah Models 00h-0Fh. The required Model 40h-4Fh guide and direct numeric client microcode floor remain explicit stop-ship gaps rather than inferred values;
- a read-only, unprivileged Windows registry observation reports identical revision `0x0B404023` for 16 logical processors. PKERR1 treats it as OS metadata only, never as direct `MSR_PATCH_LEVEL` evidence or an AMD security floor;
- six Rust tests, two `no_std` builds, formatting and clippy, 128 Rust/Python vectors covering all ten reason bits, and 24 hostile controls pass. The current target decision is exactly `deny` with failure mask `0x000000FC`, six reasons, and zero privileged reads, CPU/firmware writes, authority grants, authorized actions, or state writes;
- `FLAG-N7-ERRATA-POLICY-001` closes only the pure policy boundary. `FLAG-N7-ERRATA-SOURCE-001` and `FLAG-N7-MICROCODE-FLOOR-001` remain open stop-ship flags. N7.2 and N15.1 are partial; target qualification, firmware selection or update, direct per-processor evidence, kernel/AP integration, N7 exit, and production remain open.

Cycle 122 PKXSTATE1 evidence:

- Cargo feature `development-xstate-policy` implies PKXFER1, is disabled by default, is mutually exclusive with every other continuation, and uses selector `5`; selector `0`, the frozen qemu64 Tier 0 profile, and the ordinary stop-before-transfer build remain unchanged;
- `native/kernel/src/xstate.rs` freezes a pure, allocation-free eager standard-XSAVE policy for x87/SSE only. It requires XCR0 `0x3`, XSS zero, exact 4,096-byte 64-byte-aligned owner images, canonical FCW `0x037F`, canonical MXCSR `0x1F80`, masked exceptions, distinct owners and images, initialized incoming state, scheduler-lock ownership, disabled interrupts, same-CPU execution, and no kernel SIMD;
- one dedicated x86-64 path performs exactly one CR0 write, one CR4 write, and one XSETBV, followed by `XSAVE64`/`XRSTOR64` ownership exercises for contexts 10 and 11. Two saves and four restores preserve distinct XMM0 patterns, restore an explicit canonical image, and volatile-zero both 4,096-byte images. No MSR, firmware, authority, signature, action, or media write occurs;
- two exact fresh-vars `EPYC-Rome-v4,-avx,-avx2,-fma,-f16c,-pku` QEMU/OVMF runs reproduce 35 ordered markers and exact screenshots/PBP1 bytes. The enabled area is 576 bytes, observed MXCSR mask is `0xFFFF`, 31/31 kernel host tests and all 43 hostile controls pass, and independent Rust/Python validation agrees;
- the source audit finds exactly one source occurrence each of the CR0 write, CR4 write, XSETBV, `XSAVE64`, and `XRSTOR64` path, rejects XSAVES/XRSTORS/YMM/ZMM use, and bounds dedicated XMM0 use. This is not a final linked-machine-code proof;
- `FLAG-N7-XSTATE-POLICY-001` closes only this one-BSP development boundary. N7.4 is partial. PKXEXC1 separately qualifies bounded deliberate exception delivery and the linked-image scope; AVX and all other extended components, user-task delivery, scheduler/thread integration, AP-local state, SMP/migration, target hardware, N7 exit, release, and production remain open.

Cycle 123 PKXEXC1 evidence:

- `specs/native-kernel-xstate-exception-contract.json`, `native/kernel/src/xstate_exception.rs`, `runtime/native_kernel_xstate_exception.py`, and `tools/qualify_native_kernel_xstate_exception.py` freeze and independently validate deliberate x87 `#MF`, SIMD `#XM`, and terminal test-only `#NM` behavior;
- one TCG probe reproduces QEMU issue 215 by observing MXCSR `0x1F01` with the invalid mask clear and `CR4.OSXMMEXCPT=1` but no vector 19, followed by fail-closed panic `0x100E`; this expected limitation is diagnostic evidence, not a successful exception run;
- two fresh-vars WHPX runs reproduce 41 exact markers, processor vectors 16, 19, and 7, two exact recoveries, one terminal eager-policy rejection, four allowlisted configuration writes, two allowlisted recovery writes, and zero signatures, authority, actions, or post-exit firmware calls;
- the workspace-local pinned LLVM 22.1.6 `llvm-objdump` is hash-bound to SHA-256 `84DE1EDCEFED12FEB797F8B1C41DEBA99B6116A6BB3B80A1832FFF2CC06F2F94`; its audit of the exact 3,600,160-byte linked ELF finds eight allowlisted XMM instructions, zero extended-vector instructions, and the required x87/SIMD/#NM and recovery sequences;
- all 43 source, marker, state, authority, machine-code, synthetic-disassembly, and tool-binding controls pass. `FLAG-N7-XSTATE-EXCEPTION-001` closes only this virtualized one-BSP boundary. N7.4 remains partial; scheduler/user-task semantics, AP and migration state, AVX/extended components, exact target execution, N7 exit, release, and production remain open.

Cycle 124 PKMSR1 evidence:

- Cargo feature `development-privilege-msr-policy` implies PKXFER1, is disabled by default, is mutually exclusive with every other continuation, and uses selector `7`; selector `0` and the ordinary stop-before-transfer build remain unchanged;
- `native/kernel/src/privilege_msr.rs` and `native/kernel/src/arch/x86_64.rs` freeze an allocation-free read-only snapshot and policy for EFER/system-linkage, FS/GS/KERNEL_GS bases, support-gated TSC_AUX, global machine-check capability/status/control, PMU feature gates, and `CR4.PCE`. The validator rejects reserved bits, unsupported reads, active linkage, MCA bank access, PMU access, writes, activation, and authority claims;
- two fresh-vars TCG qemu64 QEMU/OVMF runs reproduce 35 exact markers and independently reconstruct `AuthenticAMD`, family 15, model 107, stepping 1, no RDTSCP, EFER `0xD00`, inactive linkage and FS/GS state, ten MCA banks, `MCG_CAP=0x000000000100010A`, `MCG_STATUS=0`, `MCG_CTL=0xFFFFFFFFFFFFFFFF`, and no architectural or AMD PerfMonV2 PMU;
- the profile performs eleven support-gated `RDMSR` operations, no `TSC_AUX` or MCA-bank read, and zero `WRMSR`, `RDPMC`, control writes, signatures, authority grants, actions, or post-exit firmware calls. QEMU's MCG_CAP bit 24 and all-ones MCG_CTL are compatibility observations only and are not assigned AMD hardware semantics;
- the workspace-local LLVM 22.1.6 audit parses the exact 3,633,704-byte linked ELF and freezes 17 total `RDMSR` instructions with zero `WRMSR`, `RDPMC`, `SYSCALL`, `SYSRET`, or `SWAPGS`. All 47 contract, parser, support-gate, reserved-bit, source, machine-code, zero-effect, and stale-binding controls pass;
- `FLAG-N7-PRIVILEGE-MSR-POLICY-001` closes only this one-BSP qemu64 compatibility boundary. N7.3 remains partial; syscall entry/return, GS/TSC_AUX ownership, machine-check handling/recovery, MCA bank semantics, PMU ownership, AP-local state, exact target execution, N7 exit, release, and production remain open.

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

### N9 - Physical and Virtual Memory, MMIO, Allocation, and Reclaim (`partial`)

Inherited sections: `026-029`, `151`. Added: `ADD-MEM-001`.
Goal: make ownership, mapping, cacheability, allocation, reclaim, and OOM behavior explicit and testable.

Cycle 125 PKPMM1 evidence:

- `specs/native-kernel-physical-memory-contract.json` freezes exact PBP1 parsing, UEFI source-kind validation, usable-only initial ownership, held reclaim classes, page-zero exclusion, retained core/loader ownership, DMA/DMA32/Normal zone boundaries, fixed capacities, generation-safe handles, quota, poison, double-free, and coalescing semantics;
- `native/kernel/src/physical_memory.rs` is allocation-free `no_std` PooleKernel code with fixed capacity for 256 map records, 256 free extents, 32 active allocations, and a 64-page profile quota; the independent Python oracle reconstructs all totals, zones, deterministic addresses, and ownership directly from the live PBP1 bytes;
- two exact selector-8 qemu64 QEMU/OVMF runs emit 40 ordered markers and agree on 97 memory entries, 117,925 conventional usable source pages, 117,924 managed pages, 11,250 held boot-reclaimable pages, 819 protected loader pages, four allocator operations, and a restored free-extent topology;
- all 48 hostile controls reject marker omission/order/duplication, wrong selector or contract, count/zone/largest-extent drift, PBP1 overlap/source-kind/core-ownership faults, allocator address drift, quota escape, unavailable-zone success, stale/double free, poison/coalescing drift, residue, physical-write/mapping/reclaim/concurrency/signature/authority/action overclaim, and nonterminal completion;
- the shared PKMAP2 stack grew from eight to fourteen pages after the first live selector-8 run exhausted the old bound. A PKTRAP1 rerun then caught the stale hard-coded low-guard calculation; `BOOTSTRAP_STACK_PAGE_COUNT` now derives that probe, all three trap scenarios pass, and `ADD-MEM-001` binds stack/guard/root/handoff/kernel/metadata boundaries across boot, handoff, entry, trap, and PMM consumers;
- PKPMM1 performs no physical-page content access, page-table mutation, reclaim transition, signature verification, authority grant, or action. N9.1 and N9.2 are partial only; the next move is `N9-VM-001`.

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

### N34 - PooleGlyph Machine Language, PGB2, PGVM2, and System Policy (`blocked`)

Inherited section: `124`. Added: `ADD-PGL-001` through `ADD-PGL-006`.
Goal: develop PooleGlyph machine language and PooleOS as coordinated but independently versioned products, then integrate only verified language, package, VM, and policy surfaces into native PooleOS.

Subphases:

- N34.1 Operate a tandem-development intake loop that inspects the live PooleGlyph repository and newest checkpoint first, binds exact commits/manifests/hashes, preserves dirty user-generated evidence, records ownership direction, and classifies every observed change by PooleGlyph and PooleOS impact.
- N34.2 Establish language governance with semantic versioning, experimental and stable feature tiers, compatibility profiles, deprecation and migration rules, reserved namespaces, release branches, checkpoint promotion, and an explicit source-available/public/private IP classification for every language component.
- N34.3 Complete and accept Phase 66 by auditing every declaration and Core IR form as source syntax, compile-time metadata, non-executable descriptor, executable operation, privileged policy request, or invalid form; default unknown and metadata-only forms to non-executable and non-promotable.
- N34.4 Freeze the source-language lexical and syntactic contract: UTF-8/Unicode policy, normalization, tokens, comments, literals, operators, precedence, declarations, patterns, predicates, macros, modules, imports/exports, visibility, attributes, feature gates, and bounded parser recovery.
- N34.5 Freeze the semantic contract: scopes, symbols, identity, type and value domains, generic and aggregate forms where adopted, constant evaluation, effects, capabilities, permissions, resources, lifecycle, service/package/deployment forms, determinism, initialization, errors, and compatibility behavior.
- N34.6 Harden the complete frontend pipeline from source loader through lexer, parser, source-spanned AST, diagnostics and recovery, module/name resolution, macro expansion, semantic/type/effect/capability checking, cycle detection, constant evaluation, linting, and a stable diagnostic-code catalog.
- N34.7 Freeze canonical Core IR with explicit operation semantics, typed operands/results, control flow, effects, capability/resource requirements, source maps, canonical serialization, hashes, version/feature negotiation, validators, and independent encoder/decoder/lowering implementations.
- N34.8 Freeze PGASM as the reviewable textual assembly boundary with a canonical grammar, assembler, disassembler, verifier, source/debug maps, lossless supported round trips, stable diagnostics, and differential agreement with direct Core IR-to-PGB2 lowering.
- N34.9 Define reference and optimized compiler passes with preconditions, postconditions, invariants, deterministic modes, pass receipts, translation validation, differential tests, and a mandatory no-optimization path; no pass may change observable semantics, effects, resource bounds, or authority.
- N34.10 Freeze PGB2 as a canonical signed binary package with framing, section table, byte order, widths, alignment, canonical bytes, digests, signatures, dependency and feature metadata, capability/resource declarations, debug/source sections, unknown-section rules, size limits, and downgrade-safe version negotiation.
- N34.11 Freeze the PGVM2 instruction-set and verifier contract covering typed instructions, control flow, calls, stack/register state, linear and bounded memory, object/handle lifetimes, effects, capability use, resource accounting, traps, malformed bytecode, verifier termination, and proof-carrying receipts where practical.
- N34.12 Implement the bounded deterministic PGVM2 runtime with quotas, fuel, deadlines, cancellation, cleanup, replay, trace, deterministic scheduling modes, memory safety, generation-safe handles, structured traps, watchdog integration, and no ambient kernel, filesystem, network, device, clock, entropy, or secret access.
- N34.13 Freeze the PooleOS host ABI and capability-broker boundary with canonical host-call schemas, rights attenuation, argument/result validation, copy and shared-memory rules, async completion, cancellation races, version negotiation, audit receipts, revocation, process death, and stale-handle rejection.
- N34.14 Compile PooleGlyph policy only into declarative boot, service, package, deployment, resource, permission, and topology manifests; validate and simulate before transactional application, require signatures for privileged policy, retain rollback and explanation records, and keep static recovery policy independent.
- N34.15 Build a versioned standard library, module/package system, local-first resolver, lockfile, offline cache, reproducible dependency graph, core/geometry/PDC/system APIs, capability-safe wrappers, documentation, licensing metadata, vulnerability handling, and compatibility support windows.
- N34.16 Deliver compiler, package manager, formatter, linter, language server, documentation generator, REPL/simulator where safe, debugger, trace/replay viewer, profiler, diff, migration, conformance, publisher, and IDE/editor integrations without requiring private optimization code.
- N34.17 Maintain a language and runtime threat model plus parser, semantic, Core IR, PGASM, PGB2, verifier, VM, host-call, package, dependency, signature, resource-exhaustion, cancellation, concurrency, and supply-chain fuzz/fault/adversarial campaigns with minimized retained cases.
- N34.18 Maintain cross-repository golden and negative corpora spanning source bytes, tokens, AST, diagnostics, semantic model, Core IR, PGASM, PGB2, verifier results, runtime traces, host calls, and policy output; require independent implementations and an explicit compatibility matrix before promotion.
- N34.19 Provide a portable public-safe reference backend first, then separately gated CPU, SIMD, RAM-data-lane, GPU, and PDC-assisted optimization lanes with workload budgets, deterministic fallback, output/effect/authority equivalence, invalidation, and no expansion of bounded performance claims.
- N34.20 Enforce the PooleGlyph IP and publication boundary: public source-available specifications, canonical formats, reference toolchain/runtime, and conformance evidence remain independently reviewable while private PooleMath methods and optimization strategy stay segregated, inventoried, access-controlled, and legally reviewed.
- N34.21 Integrate promoted PooleGlyph releases into PooleOS userspace, service startup, package/update, SDK, policy, observability, crash, and application lanes through pinned compatibility profiles; prevent bootstrapping cycles and ensure normal boot, safe mode, and recovery remain available when PooleGlyph is absent or rejected.
- N34.22 Advance the upstream language roadmap through evidence-gated milestones: v0.5 frontend/Core IR stabilization, v0.6 AST-parser replacement, v0.7 modules and standard-library expansion, v0.8 process/runtime prototype, v0.9 replay/debug polish, and v1.0 stable public language, without treating version labels or checkpoints as PooleOS production evidence.

Exit gate: the exact promoted PooleGlyph revision and Phase 66 boundary are accepted; source, semantic, Core IR, PGASM, PGB2, PGVM2, host-ABI, policy, compatibility, IP, and recovery contracts are frozen for the release profile; independent toolchains reproduce canonical artifacts; verifier and native runtime pass malformed, over-authorized, resource, replay, cancellation, teardown, hostile-host-call, and cross-version tests; private backends remain reference-equivalent; and recovery does not require PooleGlyph.

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

The coverage ledger records 35 additions with phase, requirement text, and basis. The most consequential additions are:

- an explicit microkernel TCB partition and Linux/Buildroot exclusion;
- formal models and proof-assumption records for capabilities, IPC, VM, scheduler, boot/update, and filesystem state;
- OASIS VIRTIO 1.3 reference-device support;
- capability derivation, attenuation, transfer, revocation, and no ambient authority;
- user-space driver domains with DMA/IRQ/MMIO leases and no v1 loadable kernel modules;
- Secure Boot key/revocation/antirollback state modeling;
- pinned, vendored, reproducibly path-remapped boot digest providers with independent review and no authentication claim from unsigned digest equality;
- typed non-kernel boot artifact envelopes with exact profile, digest, transactional loading, retained ownership, PBP1 cross-binding, and separately gated payload semantics;
- CPU transient-execution/control-flow mitigation matrix tied to exact microcode;
- TUF-style compromise-resilient update roles;
- in-toto links, SLSA 1.2 provenance, and SPDX 3.0.1 SBOM;
- property/model/mutation/symbolic/schedule testing beyond conventional unit and fuzz suites;
- permanent GOP/software/virtio graphics independent from RTX research;
- tandem PooleGlyph/PooleOS checkpoint intake, change-impact records, and cross-repository compatibility control;
- a complete deterministic PooleGlyph source-to-Core-IR-to-PGASM-to-PGB2-to-PGVM2 contract with metadata remaining non-executable;
- independent PooleGlyph toolchains, golden/hostile/migration/replay corpora, capability confinement, and recovery independence;
- a public-safe reference language/runtime plus separately gated private PooleMath optimization lanes with semantic and authority equivalence;
- PGB2/PGVM2 binary/VM freeze after PooleGlyph Phase 66;
- exact-byte independent native ISO reproduction.

Primary research references include:

- UEFI 2.11: `https://uefi.org/specs/UEFI/2.11/`
- ELF symbol tables: `https://gabi.xinuos.com/elf/05-symtab.html`
- DWARF 5: `https://dwarfstd.org/doc/DWARF5.pdf`
- GDB separate debug files: `https://sourceware.org/gdb/current/onlinedocs/gdb.html/Separate-Debug-Files.html`
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
| `FLAG-N0-OBJECTIVES-001` | REQUIRED | Open | Owner-ratify the v1 profile and 38 target values, then bind passing native evidence to every target |
| `FLAG-N0-RATIFICATION-SCOPE-001` | REQUIRED | Closed in Cycle 86 | Bind exact objective definitions and schema into the owner ceremony while excluding measurements and production promotion |
| `FLAG-N0-GOVERNANCE-KEY-001` | BLOCKER | Open in Cycle 93 | Obtain compatible FIDO2 hardware, then separately authorize and verify governance-key generation, public fingerprint review, signer registration, and recovery custody without exposing private material |
| `FLAG-NATIVE-BOOT-001` | STOP_SHIP | Open | Reproducible PooleBoot PE32+ boots and transfers through the frozen handoff |
| `FLAG-N5-POOLEBOOT-PROOF-001` | REQUIRED | Closed in Cycle 97 | Bounded unsigned PooleBoot PE32+ proof, deterministic GPT/FAT32 media, dual-channel markers, GOP frame, hostile controls, and nonclaims reproduce exactly |
| `FLAG-N5-BOOTPROTO-001` | REQUIRED | Closed in Cycle 98 | Canonical PBP1 schema, `no_std` codec, independent decoder, layouts, golden bytes, downgrade/malformed controls, and differential fuzz receipt reproduce exactly |
| `FLAG-N5-BOOTCFG-001` | REQUIRED | Closed in Cycle 99 | Canonical bounded PBC1 grammar, allocation-free `no_std` parser, independent oracle, full semantic vectors, 64 hostile controls, and 16,384-case differential receipt reproduce exactly without a live-file claim |
| `FLAG-N5-ELF-001` | REQUIRED | Closed in Cycle 100 | Bounded PKELF1 profile, allocation-free `no_std` loader, independent oracle, three exact loaded images, 129 hostile controls, 16,384-case differential receipt, and transactional non-mutation reproduce without live firmware, paging, or transfer claims |
| `FLAG-N5-KLOAD-001` | REQUIRED | Closed in Cycle 102 | Live bounded PBC1/PKELF1 reads, exact page allocation, relocation, W^X plan validation, deterministic cleanup, 17 markers, 30 hostile controls, and guest/oracle agreement reproduce without authentication, retained mappings, transfer, or N5-exit claims |
| `FLAG-N5-MANIFEST-001` | REQUIRED | Closed in Cycle 103 | Canonical PSM1 parsing, exact slot/version/path/size/digest/entry binding, live manifest-driven selection, kernel hashing, 19 aggregate markers, 40 integration controls, and independent agreement reproduce without signature trust, persistent rollback, retained mappings, transfer, or N5-exit claims |
| `FLAG-N5-PBP1-LIVE-001` | REQUIRED | Closed in Cycle 104 | Stride-aware live UEFI map normalization, exact config/manifest/kernel/GOP-bound temporary PBP1 bytes, dual-channel independent reconstruction, profile rejection, lifetime recheck, cleanup, 21 aggregate markers, and 52 integration controls reproduce without retained storage, final-map, `ExitBootServices`, transfer, or N5-exit claims |
| `FLAG-N5-KMAP-001` | REQUIRED | Closed in Cycle 105 | Exact supervisor 4 KiB higher-half leaves, CR0.WP/NX/W^X prerequisites, active-root cloning, candidate CR3 activation, full alias audit, framebuffer translation/cache preservation, exact rollback, zero active firmware calls, and complete table/kernel cleanup reproduce without retained-address-space, final-cache-policy, transfer, or N5-exit claims |
| `FLAG-N5-HANDOFF-EXIT-001` | REQUIRED | Closed in Cycle 106 | Retained kernel/table/guarded-stack/handoff ranges, final-map-bound immutable development PBP1, bounded stale-key retry, successful `ExitBootServices`, zero later firmware calls, and permanent stop before transfer reproduce without signature, kernel-entry, target-firmware, or N5-exit claims |
| `FLAG-N5-INIT-SYSTEM-001` | REQUIRED | Closed in Cycle 107 | Exact seven-artifact PSM1 profile, PBART1 role/version/payload and whole-file digest validation, transactional zero-padded page loading/cleanup, retained final-map coverage, and seven-role PBP1 binding reproduce without signature, semantics, execution, microcode, transfer, or N5-exit claims |
| `FLAG-N5-INIT-BUNDLE-001` | REQUIRED | Closed in Cycle 108 | Freeze and independently validate PINIT1 declarations, dependency/capability/resource semantics, lifecycle policy, activation preconditions, hostile corpus, and deterministic Rust/Python agreement without claiming authority creation or execution |
| `FLAG-N5-RECOVERY-BUNDLE-001` | REQUIRED | Closed in Cycle 109 | Freeze and independently validate PREC1 immutable policy and mutable state, A/B eligibility and decrement-before-handoff transitions, known-good fallback, bounded safe/recovery routing, authenticated receipts, authority and physical-presence rules, activation denial, hostile corpus, and deterministic Rust/Python agreement without claiming state I/O, authority creation, or recovery execution |
| `FLAG-N5-SYMBOL-BUNDLE-001` | REQUIRED | Closed in Cycle 110 | Freeze and independently validate PSYM1 identity, image-relative address and KASLR-base model, bounded lookup, public-name/privacy policy, stripped/split-debug correspondence, hostile corpus, deterministic Rust/Python agreement, and unsigned consumption denial without claiming target consumption, exports, diagnostic authority, or address disclosure |
| `FLAG-N5-MICROCODE-BUNDLE-001` | REQUIRED | Closed in Cycle 111 | Freeze and independently validate synthetic-only PMCU1 package identity, opaque-payload binding, revision/floor selection, reset-only downgrade policy, BSP/AP sequencing, apply-plan prerequisites, mixed-revision failure, post-apply checks, hostile corpus, deterministic Rust/Python agreement, and development activation denial without claiming vendor-container validation, privileged observation, CPU update, firmware mutation, or physical-media writes |
| `FLAG-N5-FIRMWARE-BUNDLE-001` | REQUIRED | Closed in Cycle 112 | Freeze and independently validate synthetic-only PFWM1 component/hardware/version/payload identity, dependency ordering, dry-run authority prerequisites, recovery, post-reset receipt, and driver-rebind rules without claiming live inventory, payload validation, updater load, capsule submission, reset, firmware mutation, or physical-media writes |
| `FLAG-N5-POLICY-BUNDLE-001` | REQUIRED | Closed in Cycle 113 | Freeze and independently validate qualification-only PPOL1 six-mode default-deny policy, authority intersection, exact PINIT1 route binding, attenuation, safe/recovery floors, firmware physical-presence separation, durable receipts, hostile corpus, and deterministic Rust/Python agreement without claiming target enforcement, authority creation, state mutation, PooleGlyph executable authority, or production promotion |
| `FLAG-N5-INIT-SEMANTICS-001` | REQUIRED | Closed in Cycle 113 | All six inner formats now have frozen independent semantics, exact byte identities, hostile controls, differential evidence, and mandatory development activation or consumption denial |
| `FLAG-N5-INNER-PARSE-001` | REQUIRED | Closed in Cycle 114 | Live PooleBoot reparses all six exact retained PBART1 files, binds PPOL1 payload digests and PINIT1 routes, requires all six development gates to deny, and proves zero authority, action, state-write, and hardware-observation effects through independent and dual-channel evidence |
| `FLAG-N5-INNER-TRUST-CONTRACT-001` | REQUIRED | Closed in Cycle 115 | PBTRUST1 freezes separate immutable policy and mutable acceptance-state records, exact artifact/revocation/rollback/copy/previous-state/external-evidence bindings, deterministic failure precedence, and live unsigned-policy denial while rejecting ESP candidates as authority and producing zero signature, authority, or write effects |
| `FLAG-N5-INNER-TRUST-BACKEND-MODEL-001` | REQUIRED | Closed in Cycle 116 | PBSTATE1 freezes pure authenticated-anchor validation, two-copy logical selection, stale/future/rollback/chain/digest rejection, deterministic repair/migration planning, nine interrupted-transition cases, and zero-effect boundaries without cryptography or persistent I/O |
| `FLAG-N5-INNER-KERNEL-REVALIDATE-001` | REQUIRED | Closed in Cycle 117 | Allocation-free `no_std` PooleKernel code independently reparses exact retained PSM1, six PBART1 inner files, PBTP1, and PBTS1; rejects locator/role/size/digest/binding/substitution/mutation faults; reconstructs exact unsigned-policy denial; and grants zero authority in host execution |
| `FLAG-N5-KERNEL-TRANSFER-001` | REQUIRED | Closed in Cycle 118 | Default transfer remains disabled; an opt-in QEMU-only path installs retained CR3 and guarded RSP after `ExitBootServices`, preserves the inherited framebuffer mapping and ABI state, enters PooleKernel exactly once, live-executes PKREVAL1, and emits an independently reconstructed terminal denial receipt with zero signatures, authority, actions, writes, or firmware calls |
| `FLAG-N5-INNER-TRUST-STATE-001` | BLOCKER | Open in Cycle 119 | Implement and authenticate a real cryptographic monotonic writable acceptance-state provider, revocation and Secure Boot evidence, and executed persistent selection/repair/migration under storage faults and power loss |
| `FLAG-N5-INNER-ENFORCEMENT-001` | REQUIRED | Open in Cycle 119 | Complete authenticated state, production-profile PooleKernel revalidation, attenuated capability creation, authorized lifecycle/recovery/diagnostic/policy/update actions, durable audit, and rollback evidence |
| `FLAG-N6-KENTRY-001` | REQUIRED | Closed in Cycle 101; live development entry added in Cycle 118 | Real PooleKernel PKELF1 product, PKENTRY1 contract, exact two-build reproduction, PBP1 intake, bounded early diagnostics, deterministic panic taxonomy, 43 hostile controls, and independent loaded-byte comparison; PKXFER1 separately proves QEMU-only unsigned entry without expanding the standalone receipt |
| `FLAG-N6-BOOT-DIGEST-001` | REQUIRED | Open in Cycle 104 | Independent cryptographic/supply-chain review and exact target-backend qualification accept PBDIGEST1 before any boot-trust promotion |
| `FLAG-N6-FRAMEBUFFER-MAP-001` | REQUIRED | Open in Cycle 101 | PooleBoot installs and records the exact temporary framebuffer identity mapping, preserves cache policy, and PooleKernel replaces and revokes it before graphics capability delegation |
| `FLAG-N7-TRAP-001` | REQUIRED | Closed in Cycle 119 | BSP-only PKTRAP1 GDT/TSS/IDT readback, five present exception gates, distinct bounded IST arrays, uniform integer frames, three deliberate returning faults, terminal double-fault containment, semantic malformed-frame rejection, six exact QEMU/OVMF runs, and 51 hostile controls reproduce without expanding the production claim |
| `FLAG-N7-CPU-POLICY-001` | REQUIRED | Closed in Cycle 120 | BSP-only qemu64 PKCPU1 read-only CPUID/control/XCR0/APIC/PAT/MTRR observation, independent Rust/Python agreement, two exact QEMU/OVMF runs, 35 markers, 41 hostile controls, five MSR reads, and zero writes, authority, or actions reproduce without target or production promotion |
| `FLAG-N7-ERRATA-POLICY-001` | REQUIRED | Closed in Cycle 121 | PKERR1 freezes exact target identity, mandatory features, board/BIOS/AGESA floors, microcode-evidence, source-applicability, and RDSEED rules through independent Rust/Python evaluators, 128 vectors, 24 hostile controls, exact current denial, and zero privileged reads, writes, authority, or actions |
| `FLAG-N7-ERRATA-SOURCE-001` | STOP_SHIP | Open in Cycle 121 | Acquire and bind a directly applicable AMD Family 1Ah Models 40h-4Fh errata source or retain a reviewed vendor-response disposition; revision guide 58251 and cross-model evidence are prohibited substitutes |
| `FLAG-N7-MICROCODE-FLOOR-001` | STOP_SHIP | Open in Cycle 121 | Obtain a direct AMD numeric client microcode floor or ratify a reviewed replacement rule without treating OS metadata, unrelated products, firmware labels, or synthetic PMCU1 revisions as the floor |
| `FLAG-N7-XSTATE-POLICY-001` | REQUIRED | Closed in Cycle 122 | PKXSTATE1 freezes bounded eager standard-format x87/SSE ownership, exact XCR0/XSS and image rules, canonical initialization, isolated round trips, sensitive-image clearing, context-switch preconditions, kernel-SIMD prohibition, two exact QEMU runs, 43 hostile controls, and three allowlisted privileged configuration writes without scheduler, SMP, target, or production promotion |
| `FLAG-N7-XSTATE-EXCEPTION-001` | REQUIRED | Closed in Cycle 123 | PKXEXC1 proves deliberate processor-delivered x87 `#MF` and SIMD `#XM` with exact bounded recovery, terminal test-only `#NM` eager-policy rejection, one expected TCG non-delivery diagnostic, two exact WHPX runs, 43 hostile controls, and a hash-bound linked machine-code scope audit without scheduler, user-task, SMP, target, or production promotion |
| `FLAG-N7-PRIVILEGE-MSR-POLICY-001` | REQUIRED | Closed in Cycle 124 | PKMSR1 freezes support-gated read-only system-linkage, FS/GS, TSC_AUX, global MCA, and PMU policy through two exact TCG qemu64 runs, 35 markers, 47 hostile controls, 11 live MSR reads, and a linked audit with 17 `RDMSR` and zero activation/write instructions, without syscall, MCE, PMU, AP, target, or production promotion |
| `FLAG-N9-PMM-FOUNDATION-001` | REQUIRED | Closed in Cycle 125 | PKPMM1 consumes and independently validates the exact live PBP1 map, enforces usable-only ownership and retained-range protection, holds reclaim classes, excludes page zero, and proves deterministic zoned allocation, generation-safe free, quota, poison, double-free rejection, and coalescing through two exact 40-marker qemu64 runs and 48 controls without page scrubbing, mapping, reclaim, concurrency, N9-exit, or production promotion |
| `FLAG-NATIVE-KERNEL-001` | STOP_SHIP | Open | PooleKernel boots, enforces memory/capabilities/IPC, and runs ring 3 |
| `FLAG-NATIVE-IOMMU-001` | STOP_SHIP | Open | DMA and interrupt remapping confine every bus-mastering driver |
| `FLAG-NATIVE-DRIVER-001` | STOP_SHIP | Open | User-space driver domains survive crash/reset/revoke without stale authority |
| `FLAG-NATIVE-FS-001` | STOP_SHIP | Open | PooleFS durability and repair pass randomized power-cut testing |
| `FLAG-NATIVE-UPDATE-001` | STOP_SHIP | Open | Signed A/B update, rollback, key compromise, and recovery tests pass |
| `FLAG-NATIVE-SEC-001` | STOP_SHIP | Open | Threat model, crypto/RNG, boot trust, isolation, and external review gates pass |
| `FLAG-NATIVE-UI-001` | REQUIRED | Open | Native PooleGlass and accessibility/fallback paths pass supported profiles |
| `FLAG-NATIVE-PGL-001` | BLOCKER | Open | Close the promoted PooleGlyph language, Phase 66, PGB2/PGVM2 v1, host-ABI, compatibility, native-integration, and recovery gates |
| `FLAG-PGL-CODEV-001` | REQUIRED | Open | Bind exact PooleGlyph and PooleOS revisions, checkpoint evidence, change impacts, and compatibility profiles so neither repository drifts silently |
| `FLAG-PGL-CORE-IR-001` | BLOCKER | Open | Accept Phase 66 classification and independent validation proving metadata cannot become executable or privileged Core IR |
| `FLAG-PGL-IP-001` | REQUIRED | Open | Review and enforce the source-available/public/private component boundary while keeping private backends reference-equivalent and non-authority-amplifying |
| `FLAG-NATIVE-PDC-001` | REQUIRED | Open | Signed dynamics and native/backend differentials pass without claim expansion |
| `FLAG-NATIVE-HW-001` | STOP_SHIP | Open | Exact Tier 1 hardware, spare media, firmware, driver, and recovery qualification pass |
| `FLAG-N2-CPUID-001` | REQUIRED | Closed in Cycle 87 | Bounded direct user-mode CPUID transcript is captured, sanitized, privacy-safe, and adversarially tested |
| `FLAG-N2-PRIVILEGED-PROBE-001` | BLOCKER | Open; operation category authorized in Cycle 118 | Review and qualify source-bound read-only privileged mechanisms, bind an identified safe target, backups, recovery, and bounded side effects, then retain exact probe evidence |
| `FLAG-N2-EVIDENCE-001` | REQUIRED | Open | Complete low-level read-only hardware capture and native-parser comparison evidence |
| `FLAG-N2-STANDARDS-001` | REQUIRED | Open | Hash lawful exact standards and close supersession, errata, profile, and access review |
| `FLAG-N2-LAB-SAFETY-001` | BLOCKER | Open; physical-write category authorized in Cycle 118 | Identify sacrificial media and target, verify backups and recovery media, freeze rollback/stop conditions, and retain per-operation evidence before any destructive test |
| `FLAG-N4-PROFILE-001` | REQUIRED | Closed in Cycle 88 | Exact native-only q35/QEMU/OVMF/VIRTIO profile passes deterministic paused-instantiation and hostile substitution controls without a boot claim |
| `FLAG-N4-PROVENANCE-001` | BLOCKER | Open | Source-build current pinned QEMU/EDK II, verify signatures/patches, close runtime security/license/SBOM/redistribution review, and reproduce on a second host |
| `FLAG-N4-MODELS-001` | BLOCKER | Open; all seven required bounded domains landed by Cycle 96 | All six model families need native implementation-trace cross-checks before dependent ABI freezes; temporal liveness, refinement, implementation conformance, and toolchain assurance remain separate open work |
| `FLAG-N4-IPC-MODEL-001` | REQUIRED | Closed in Cycle 94 | Frozen IPC safe search drains and all four independent authorization/token/stale-reply/teardown mutants produce their exact counterexamples without expanding the proof boundary |
| `FLAG-N4-SCHEDULER-MODEL-001` | REQUIRED | Closed in Cycle 95 | Frozen scheduler safe search drains and seven independent wake, duplicate-runnable, inheritance, priority, bypass, and teardown mutants produce exact counterexamples without a liveness claim |
| `FLAG-N4-POOLEFS-MODEL-001` | REQUIRED | Closed in Cycle 96 | Frozen PooleFS safe search drains and six independent torn-write, publication, allocation, replay, checksum, and recovery-leak mutants produce exact counterexamples without implementation or hardware-durability claims |
| `FLAG-NATIVE-ISO-001` | STOP_SHIP | Open | Two builders reproduce and exact signed ISO passes clean QEMU and physical media |
| `FLAG-NATIVE-REVIEW-001` | STOP_SHIP | Open | Independent security, filesystem, kernel, update, and release review closes critical/high findings |
| `FLAG-BUILDROOT-LEGACY-001` | SUPERSEDED | Closed by architecture reset | Buildroot remains historical reference and cannot promote native status |

## 12. Near-Term Execution Sequence

Cycle 125 closes only `FLAG-N9-PMM-FOUNDATION-001`. PKPMM1 proves a bounded one-BSP physical-page ownership and allocator foundation over the exact live PBP1 map through two exact 40-marker qemu64 runs and 48 hostile controls. It manages only conventional usable pages, holds reclaim classes, excludes page zero, protects retained loader ownership, and exercises zoned deterministic allocation/free, generation checks, quota, poisoning, double-free rejection, and coalescing with zero page-content writes, mappings, reclaim, signatures, authority, or actions. The same cycle expands the bootstrap stack to fourteen pages and fixes the derived trap guard. N9.1/N9.2 are partial, not complete. `FLAG-N7-ERRATA-SOURCE-001` and `FLAG-N7-MICROCODE-FLOOR-001` remain open stop-ship flags; page scrubbing, lifecycle reclaim, virtual memory, heap/object caches, MMIO/cache aliases, concurrency/SMP, pressure/OOM policy, exact target qualification, and N9 exit remain open. The selected `hardware_fido2_ed25519_sk` device remains physically unavailable, so `N0-HW-KEY-ACQUIRE-001` is still the immediate blocked external move. No key, signature, public-key publication, secret use, privileged host probe, driver load, firmware change, physical-media write, tag/release publication, or production promotion occurred in Cycle 125. The next owner-independent engineering move is `N9-VM-001`: freeze the virtual layout and implement bounded page-table allocation and map/unmap/protect primitives before heaps or SMP. PooleGlyph Phase 66 may advance in parallel without outranking N0-N9.

| Order | Move | Required output |
|---:|---|---|
| 1 | `N0-HW-KEY-ACQUIRE-001` | Acquire and confirm possession of a compatible FIDO2 hardware security key; generation/use/publication/signing are already authorized but still require owner presence, reviewed custody/recovery steps, exact fingerprint review, and no private-material disclosure |
| 2 | `N1-SCM-CLOSE-001` | Signed-commit policy, immutable refs, retained CI/review policy, and protected-workflow closure after the pre-signing history is resolved |
| 3 | `N2-HW-002` | Complete reviewed read-only MSR, PCI configuration, duplicate ACPI, EDID/SPD, UEFI-variable, sensor/power, and native-comparison evidence; direct CPUID is complete but grants no privileged authorization |
| 4 | `N5-BOOTCFG-001` | Cycle 99 complete boundary: bounded boot configuration grammar with duplicate, unknown-key, traversal, range, truncation, incompatible-version, and oversized-artifact rejection |
| 5 | `N5-ELF-001` | Cycle 100 complete boundary: bounded PKELF1 validation/loading with exact bytes, hostile corpus, and explicit live-integration nonclaims |
| 6 | `N6-KENTRY-001` | Cycle 101 complete boundary: real reproducible PKELF1 PooleKernel product, PKENTRY1 intake, bounded early diagnostics, panic taxonomy, and explicit transfer nonclaims |
| 7 | `N5-KLOAD-001` | Cycle 102 complete boundary: bounded live PBC1/PKELF1 reads, exact page allocation/load, W^X plan validation, cleanup, and explicit authentication/transfer nonclaims |
| 8 | `N5-MANIFEST-001` | Cycle 103 complete boundary: canonical bounded PSM1, independent parser, digest/version/size/slot/path/entry binding, hostile corpus, and manifest-driven development selection without a signature or trust claim |
| 9 | `N5-PBP1-LIVE-001` | Cycle 104 complete boundary: stride-aware live memory-map normalization, exact config/manifest/kernel/GOP-bound temporary PBP1 bytes, independent transcript reconstruction, hostile lifetime/cleanup controls, and explicit pre-`ExitBootServices`/no-transfer boundary |
| 10 | `N5-KMAP-001` | Cycle 105 complete boundary: exact 48-page supervisor higher-half map, W^X/WP/NX enforcement, candidate CR3 activation, full alias and framebuffer audit, exact rollback, and complete cleanup without entry or retention claims |
| 11 | `N5-HANDOFF-001` | Cycle 106 complete boundary: retained kernel/table/guarded-stack/handoff storage, final-map PBP1, bounded `ExitBootServices`, zero later firmware calls, and permanent stop before transfer |
| 12 | `N5-INIT-SYSTEM-001` | Cycle 107 complete boundary: exact seven-artifact PSM1/PBART1 development profile, digest/envelope checks, transactional load/cleanup, retained final-map coverage, and PBP1 binding without signature, semantics, or execution claims |
| 13 | `N5-INIT-BUNDLE-001` | Cycle 108 complete boundary: deterministic PINIT1 declaration format, independent allocation-free parsers, dependency/capability/resource/lifecycle validation, hostile corpus, and unsigned activation denial without authority creation or execution claims |
| 14 | `N5-RECOVERY-SEMANTICS-001` | Cycle 109 complete boundary: deterministic PREC1 policy/state formats, independent allocation-free validators and transitions, bounded A/B/safe/recovery routing, receipt and authority controls, hostile corpus, and unsigned activation denial without state-I/O, authority, or execution claims |
| 15 | `N5-SYMBOLS-SEMANTICS-001` | Cycle 110 complete boundary: deterministic PSYM1 public index, exact image/debug/source identity, image-relative address and KASLR model, bounded lookup, public/privacy policy, stripped/split-debug correspondence, hostile and differential evidence, and unsigned consumption denial without target-consumption or authority claims |
| 16 | `N5-MICROCODE-SEMANTICS-001` | Cycle 111 complete boundary: deterministic synthetic-only PMCU1 package, exact CPU and payload identity, revision/floor and reset-known-good selection, BSP/AP apply prerequisites, mixed-revision failure, post-apply checks, hostile and differential evidence, and unsigned activation denial without vendor validation, privileged observation, or update claims |
| 17 | `N5-FIRMWARE-SEMANTICS-001` | Cycle 112 complete boundary: deterministic synthetic-only PFWM1 manifest, exact external-payload and hardware/version identity, dependency order, dry-run prerequisites, recovery and post-reset checks, hostile and differential evidence, and unsigned activation denial without live inventory, payload validation, updater load, or firmware mutation claims |
| 18 | `N5-POLICY-SEMANTICS-001` | Cycle 113 complete boundary: deterministic qualification-only PPOL1 policy, six exact modes, default-deny authority intersection, PINIT1 route cross-binding, attenuation, safe/recovery floors, firmware authority separation, durable receipts, hostile and differential evidence, and unsigned activation denial without target enforcement or authority claims |
| 19 | `N5-INNER-LIVE-PARSE-001` | Cycle 114 complete boundary: all six exact retained PBART1 files reparsed by live PooleBoot, PPOL1 payload and PINIT1 route cross-binding, six mandatory missing-signature denials, exact retained-set digest, zero-effect receipt, 24 markers, and 139/139 controls without trust, state, authority, action, or transfer claims |
| 20 | `N5-INNER-TRUST-CONTRACT-001` | Cycle 115 complete boundary: separate PBTP1/PBTS1 formats, fourteen binding/rollback checks, eight external evidence gates, 88/88 standalone controls, 24,576 differential cases, exact live unsigned-policy denial, 25 markers, and 148/148 integrated controls without authentication, persistent authority, writes, or transfer claims |
| 21 | `N5-INNER-TRUST-BACKEND-001` | Cycle 116 complete model boundary: PBSTATE1 authenticated monotonic-anchor validation, deterministic two-copy logical selection, rollback/future/chain/digest rejection, repair/migration planning, 105/105 controls, 32,768 differential cases, and nine interruption points with zero cryptography, I/O, writes, or authority |
| 22 | `N5-INNER-KERNEL-REVALIDATE-001` | Cycle 117 complete boundary: exact retained PSM1/six-PBART1/PBTP1/PBTS1 PBP1 locators, allocation-free independent PooleKernel reparsing, binding reconstruction, 36/36 hostile controls, 32,768/32,768 mutation rejects, and exact unsigned-policy denial with zero authority, actions, or writes; live kernel entry remains explicitly unclaimed |
| 23 | `N5-KERNEL-TRANSFER-001` | Cycle 118 complete development boundary: default stop preserved; exact QEMU-only feature installs retained CR3/RSP, clears IF/DF, transfers once, live-executes PKREVAL1, and emits a terminal zero-authority denial across two exact runs and 58 hostile controls |
| 24 | `N7-TRAP-001` | Cycle 119 complete bounded boundary: BSP GDT/TSS/IDT readback, uniform integer frames, exact returning breakpoint/invalid-opcode/guard-page faults, terminal double-fault containment, semantic malformed-frame rejection, six QEMU/OVMF runs, and 51 hostile controls |
| 25 | `N7-CPU-POLICY-001` | Cycle 120 complete bounded boundary: BSP-only qemu64 CPUID/control/XCR0/APIC/PAT/MTRR observation, exact Rust/Python agreement, two QEMU/OVMF runs, 35 markers, 41 hostile controls, five MSR reads, and zero writes or authority |
| 26 | `N7-ERRATA-POLICY-001` | Cycle 121 complete pure-policy boundary: exact Ryzen identity and mandatory features, lineage-specific stable firmware floors, source applicability, RDSEED handling, exact six-reason current denial, 128 cross-language vectors, 24 hostile controls, and zero privileged reads or effects; applicable errata and numeric microcode-floor sources remain stop-ship gaps |
| 27 | `N7-XSTATE-POLICY-001` | Cycle 122 complete bounded boundary: eager standard-format x87/SSE ownership, exact XCR0/XSS policy, canonical owner images, isolated round trips, clearing, fail-closed switch preconditions, kernel-SIMD prohibition, two exact QEMU runs, and 43 hostile controls without scheduler/SMP/target promotion |
| 28 | `N7-XSTATE-EXCEPTION-001` | Cycle 123 complete bounded boundary: deliberate `#MF`/`#XM` delivery and exact recovery, terminal test-only `#NM` rejection, expected TCG limitation evidence, two exact WHPX runs, and linked machine-code scope audit without scheduler/user-task/SMP/target promotion |
| 29 | `N7-PRIVILEGE-MSR-POLICY-001` | Cycle 124 complete bounded boundary: support-gated read-only syscall-linkage, FS/GS, TSC_AUX, global MCA, and PMU policy; two exact TCG qemu64 runs; 47 controls; linked no-activation/no-write audit; no syscall, MCE, PMU, AP, target, or production promotion |
| 30 | `N9-PMM-001` | Cycle 125 complete bounded foundation: exact live PBP1 source-kind/ownership validation, held reclaim classes, page-zero exclusion, retained loader protection, DMA/DMA32/Normal zones, deterministic allocation/free, generation, quota, poison, double-free and coalescing controls; two exact runs; no page scrub, mapping, reclaim, concurrency, target, or production promotion |
| 31 | `N9-VM-001` | Next owner-independent move: freeze kernel/user virtual layouts and implement bounded page-table allocation, map/unmap/protect, alias/cache checks, rollback, TLB contract, and exact hostile evidence without heap, SMP, or user-pager overclaim |
| 32 | `N8-IRQ-001` | Local APIC, timer, monotonic clock, and first SMP application processor |
| 33 | `N12-SCHED-001` | Neutral scheduler and context switch under SMP stress |
| 34 | `N13-RING3-001` | First user task, syscall, capability object, exception, and clean exit |
| 35 | `N14-IPC-001` | Capability-mediated call/reply, cancellation, quota, and hostile message tests |
| 36 | `N16-VIRTIO-001` | Isolated virtio console/RNG driver domain with revocation and restart |

PDC-SIGNED-001 and the PooleGlyph machine-language lane beginning with Phase 66 may proceed as parallel component lanes, but neither outranks the current N0-N7 native critical path. Every PooleGlyph cycle must update the exact checkpoint anchor, representation compatibility matrix, N34 status, relevant `ADD-PGL-*` requirements, and open PooleGlyph flags before PooleOS consumes changed outputs.

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
