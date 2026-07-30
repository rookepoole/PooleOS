# PooleOS Native Production Goal Charter

Charter version: 2.0.0-native-reset  
Status date: 2026-07-29
Owner and IP holder: Rooke Poole  
Parent objective: production-ready native PooleOS with a Poole-authored microkernel  
Authoritative Build Plan: `docs/pdc-production-build-plan.md`  
Machine ledger: `runs/pdc_production_roadmap.json`  
Master-checklist coverage: `runs/pooleos_native_checklist_coverage.json`  
Last roadmap reconciliation: PooleOS Cycle 141

Cycle 141 reconciliation (superseding current Cycle 140 implementation and
next-move values): governance and external-key state are unchanged, and no
key, signature, publication, privileged host probe, driver load, firmware
change, physical-media write, tag, release, or production promotion occurred.
The owner-independent `N8-SMP-MULTI-AP-001` move upgrades selector 14 to
PKSMP5 and closes only its bounded flag. On one exact four-vCPU
`SandyBridge,-avx` TCG topology, BSP APIC ID 0 owns three private AP runtimes
for APIC IDs 1, 2, and 3 with dynamic local masks `0x2`, `0x4`, and `0x8`.
One injected APIC-4 timeout after APs 1 and 2 start proves final-INIT parking,
alias revocation, complete scrub/release, and fresh allocation before retry.
The successful retry brings all three APs online simultaneously, records nine
accepted and three forged-capability-denied deliveries, twelve EOIs, three
one-page remote invalidations, and aggregate target/ack mask `0xE`. Reclaim is
rejected twice before all unique acknowledgements arrive; generation 1 then
retires, every AP quiesces and final-INIT parks, and all 96 runtime plus six
frame pages are scrubbed, read-verified, and released. Two exact 40-marker
runs, 30 hostile-control categories covering 243 rejected cases, and 137
kernel host tests pass; each resource lifecycle verifies 417,792 bytes. The
exact kernel is 409,600 canonical bytes in a 458,752-byte, 112-page image with
985 relocations and SHA-256
`8118ED5F7761B9D36A4A65EFF1BC1856C5182D5733CE95A8BEEB24D1C2435F8D`.
General topology/x2APIC, address-space-wide or concurrent-generation
shootdown, scheduler ownership, production capability authority, target
execution, N8/N9 exit, release, and production remain open.
`production_ready=false`; the blocked external move remains
`N0-HW-KEY-ACQUIRE-001`, and the next owner-independent move is
`N12-SCHED-001`.

Cycle 140 reconciliation (superseding current Cycle 139 implementation and
next-move values): governance and external-key state are unchanged, and no
key, signature, publication, privileged host probe, driver load, firmware
change, physical-media write, tag, release, or production promotion occurred.
The owner-independent `N9-SMP-SHOOTDOWN-001` move upgrades selector 14 to
PKSMP4 and closes only its bounded flag. On the frozen two-vCPU
`SandyBridge,-avx` TCG profile, one AP fills a translation for one page from
one AP-owned root, validates a checksum-bound generation-2 request, executes
exactly one linked-image-audited `INVLPG`, observes the replacement frame, and
acknowledges the exact generation, root, page, target mask, sequence, and
attempt. The BSP proves one offline-target timeout with same-attempt retry,
rejects premature reclaim, and releases the retired frame only after exact
acknowledgement. Two exact 40-marker runs, 25 hostile-control categories
covering 169 rejected cases, and 132 kernel host tests pass; all 32 runtime
pages plus both data frames, 139,264 bytes, are scrubbed, read-verified, and
released. The exact kernel is 409,600 canonical bytes in a 458,752-byte,
112-page image with 969 relocations and SHA-256
`95DDA27784DA944A9C0F5B04029255EDE4DE1BB0684A8EA10DCFC07E686B59A2`.
General multi-AP or address-space-wide shootdown, concurrent generations,
scheduler ownership, production capability authority, target execution,
N8/N9 exit, release, and production remain open. `production_ready=false`;
the blocked external move remains `N0-HW-KEY-ACQUIRE-001`, and the next
owner-independent move is `N8-SMP-MULTI-AP-001`.

Cycle 139 reconciliation (superseding only Cycle 138 closeout-integrity
metadata): main-integration preflight reproduced all 819 Cycle 138 tests but
found six stale bindings because the PBTRUST1 readiness writer had hashed CRLF
working bytes before Git stored LF. The same platform-default newline defect
was present in the new PKSMP3 writer and would have made its architecture
binding stale after checkout. Both writers now force LF and have byte-level
regression tests. PBTRUST1, PKLOAD6, PKREVAL1, PKXFER1, every affected
CPU/xstate/MSR/memory/SMP receipt, PKSMP3, and PooleBoot were requalified in
dependency order against committed-byte semantics. The exact kernel, bounded
PKSMP3 behavior, phase/subphase status, flags, gaps, and production boundary
do not advance. `production_ready=false`; no key, signature, firmware change,
physical-media write, tag, release, or production promotion occurred. The
blocked external move remains `N0-HW-KEY-ACQUIRE-001`; the next
owner-independent engineering move remains `N9-SMP-SHOOTDOWN-001`.

Cycle 138 reconciliation (superseding the historical Cycle 137 paragraph
below): governance and external-key state are unchanged. The selected
`hardware_fido2_ed25519_sk` device remains physically unavailable;
`N0-HW-KEY-ACQUIRE-001` remains the blocked external move; and no key,
signature, privileged-hardware, firmware, physical-media, publication,
release, or production-promotion action occurred. The owner-independent
`N8-SMP-IPI-001` move closes only its bounded PKSMP3 development transport.
On the frozen two-vCPU `SandyBridge,-avx` TCG profile, APIC ID 1 installs six
fixed vectors and acknowledges six allowlisted operation classes behind a
checksum-bound development capability. Two exact 39-marker runs observe six
accepted and four denied deliveries, ten EOIs, one bounded offline-APIC
timeout, panic latching, stop quiescence, final-INIT parking, post-execution
descriptor/xstate/APIC-table validation, capability and alias revocation, and
exact scrub/release of all 32 pages or 131,072 bytes. Eighteen hostile-control
categories cover 120 independently rejected cases and 130 kernel host tests
pass. The exact kernel is 409,600 canonical bytes in a 458,752-byte, 112-page
image with 959 relocations and SHA-256
`6B8A9C2C3EAC559E1D9CB5965800A1671DB8F487F149861300D4EDCB279B3A11`.
N8.6 is partial only. The capability is a fixed development token; the
shootdown operation records transport but performs zero TLB invalidations,
and call-function exposes no arbitrary callback. Real generation-bound remote
invalidation and deferred reclaim, production capability authority, scheduler
CPU ownership, multi-AP and live partial-start fault injection, target
hardware, N8/N9 exit, release, and production remain open. The next
owner-independent move is `N9-SMP-SHOOTDOWN-001`; PooleGlyph Phase 66 may
proceed in parallel without outranking N0-N9.

Cycle 137 reconciliation (superseding the historical Cycle 136 paragraph
below): governance and external-key state are unchanged. The selected
`hardware_fido2_ed25519_sk` device remains physically unavailable;
`N0-HW-KEY-ACQUIRE-001` remains the blocked external move; and no key,
signature, privileged-hardware, firmware, physical-media, publication,
release, or production-promotion action occurred. The owner-independent
`N8-SMP-PERCPU-RUNTIME-001` move closes only its bounded PKSMP2 lifecycle. On
the frozen two-vCPU `SandyBridge,-avx` TCG profile, APIC ID 1 loads one
processor-local GDT/TSS/IDT, guarded RSP0/IST1/IST2 stacks, x87/SSE owner
state, eight exception gates, and nineteen owned interrupt gates. The
32-page below-1-MiB transaction has thirteen mapped leaves, fourteen absent
guards, and one absent reserved page. The BSP verifies the hardware-set busy
TSS descriptor, all 27 gates, and one XSAVE/XRSTOR round trip before it
commands quiescence, final-INIT parks the AP, revokes all aliases, zeroes and
read-verifies 131,072 bytes, and releases all 32 pages. Two exact 42-marker
runs, 19 hostile-control categories covering 159 independently rejected
cases, and 122 kernel host tests pass. The exact kernel is 409,600 canonical
bytes in a 458,752-byte, 112-page image with 919 relocations and SHA-256
`214F32214494E632063238337551C355BFED150B9B49846DB8A927584B8E47F0`.
N8.5 remains partial. General SMP, multi-AP startup, capability-gated IPI
delivery and acknowledgement, TLB shootdown, scheduler CPU ownership, live
partial-start fault injection, target hardware, N8 exit, release, and
production remain open. The next owner-independent move is `N8-SMP-IPI-001`;
PooleGlyph Phase 66 may proceed in parallel without outranking N0-N9.

Cycle 136 reconciliation (superseding the historical Cycle 135 paragraph
below): governance and external-key state are unchanged. The selected
`hardware_fido2_ed25519_sk` device remains physically unavailable;
`N0-HW-KEY-ACQUIRE-001` remains the blocked external move; and no key,
signature, privileged-hardware, firmware, physical-media, publication,
release, or production-promotion action occurred. The owner-independent
`N8-SMP-FIRST-AP-001` move closes only its bounded PKSMP1 lifecycle. On a
two-vCPU qemu64 profile, PooleKernel selects APIC ID 1 from the retained MADT,
allocates fourteen pages below 1 MiB, installs four absent guards plus an RX
16-to-32-to-64-bit trampoline and guarded RW/NX stack/mailbox, performs one
INIT-SIPI-SIPI sequence, observes the AP online in long mode, commands stop,
validates quiescence and the dynamic mailbox checksum, issues a final INIT
park, revokes aliases, scrubs and verifies 57,344 bytes, and releases all
fourteen pages. Two exact 38-marker runs, 72 hostile controls, and 111 kernel
host tests pass. Live fault investigation found and fixed an RX-GDT accessed-
bit write that had caused an AP page fault and triple fault; every trampoline
descriptor is now pre-accessed. The exact kernel is 335,872 canonical bytes in
a 376,832-byte, 92-page image with 855 relocations and SHA-256
`6596CB332EB24813089F95A00AC979C892C47235943CB0E73E3979ED9901B725`.
N8.5 is partial only. General SMP, AP-local GDT/TSS/IDT/RSP0/IST/xstate and
interrupt state, multi-AP startup, IPIs, shootdown, live partial-start fault
injection, target hardware, N8 exit, release, and production remain open. The
next owner-independent move is `N8-SMP-PERCPU-RUNTIME-001`; PooleGlyph Phase 66
may proceed in parallel without outranking N0-N9.

Cycle 135 reconciliation (superseding the historical Cycle 134 paragraph
below): governance and external-key state are unchanged. The selected
`hardware_fido2_ed25519_sk` device remains physically unavailable;
`N0-HW-KEY-ACQUIRE-001` remains the blocked external move; and no key,
signature, privileged-hardware, firmware, physical-media, publication,
release, or production-promotion action occurred. The owner-independent
`N8-IRQ-001` move now has a bounded one-BSP implementation but remains open as
an encompassing flag. PKIRQ1 walks the retained validated MADT and HPET
descriptions, validates local-xAPIC identity, reserves 51 vectors, installs
guarded uncacheable LAPIC/HPET mappings, masks and restores the legacy PIC,
calibrates checked one-shot local-APIC time against HPET, and opens exactly
eight interrupt windows. Two exact 36-marker qemu64 runs deliver eight timer
interrupts and eight EOIs with zero APIC-error, spurious, or remaining ISR
bits; normal completion restores APIC, HPET, PIC, IA32_APIC_BASE, and MMIO
state. Ninety-nine kernel host tests and 58 hostile controls pass. The exact
kernel is 323,584 canonical bytes in a 364,544-byte, 89-page image with 812
relocations and SHA-256
`2ACD4A5EF30CA1A4A22711FD31E2A259A5C87D97BCE7FB1BF49A3488B3FC02B2`.
N8.1 and N8.3 are partial only. I/O APIC routing, MSI/MSI-X, complete time
services, panic-path rollback, first-AP startup, per-CPU state, IPIs, SMP
shootdown, target hardware, and N8 exit remain open. The next
owner-independent move is `N8-SMP-FIRST-AP-001`; PooleGlyph Phase 66 may
proceed in parallel without outranking N0-N9.

Cycle 134 reconciliation (superseding the historical Cycle 133 paragraph
below): governance and external-key state are unchanged. The selected
`hardware_fido2_ed25519_sk` device is still physically unavailable; no key or
signature exists; and `N0-HW-KEY-ACQUIRE-001` remains the blocked external
move. No cryptographic, privileged-hardware, firmware, physical-media,
publication, release, or production-promotion action occurred. The
owner-independent `N9-VM-DIRECT-MAP-001` move is complete only within its
bounded one-BSP scope. PKPMM7 reconstructs a generation-bound ownership
manifest from every free extent and active non-release-excluded allocation,
coalesces eleven exact write-back ranges, and excludes retained ownership.
PKVM3 derives and audits a 243-table topology before activation, maps 117,887
supervisor RW/NX pages, leaves 12,878 gap pages absent, and binds checksum
`0x341CF729ADB26B52`. Forged manifests, retained-hole admission, PWT/PCD drift,
partial writes, CR3 rollback, premature reuse, and absent or stale retirement
receipts fail closed. Three local invalidation receipts gate the data frame;
one exact root/generation/BSP/local-context-flush receipt gates table scrub and
release. Ninety-one kernel host tests and two exact 40-marker qemu64 runs pass
46 hostile controls with 367,474 physical table writes and 950,234 temporary-
PTE writes and invalidations. The exact kernel is 299,008 canonical bytes in a
339,968-byte, 83-page image with 729 relocations and SHA-256
`5B581CC1D1ABEB163D0984D12144CA5016C44B46A28B190A6DFCBDCDA689A255`.
N9 remains partial: PKVM3 deliberately rejects more than one active processor
until AP startup, interrupt delivery, and real inter-processor shootdown exist;
remote deferred reclaim, concurrent replacement, huge pages, PCID, COW, user
faults, pager IPC, heaps, broad MMIO/cache policy, pressure/OOM, target
hardware, and N9 exit remain open. `N8-IRQ-001` is the next owner-independent
move; PooleGlyph Phase 66 may proceed in parallel without outranking N0-N9.

Cycle 133 reconciliation (superseding the historical Cycle 132 paragraph
below): the governance and external-key state is unchanged. The selected
`hardware_fido2_ed25519_sk` device is still physically unavailable, no key or
signature exists, and `N0-HW-KEY-ACQUIRE-001` remains the blocked external
move. No cryptographic, privileged-hardware, firmware, physical-media,
publication, release, or production-promotion action occurred. The
owner-independent `N9-PMM-ACPI-CONSUMER-001` move is complete within its
bounded one-BSP scope. PBLIVE4 adds one canonical ACPI2 RSDP record; PKACPI1
validates RSDP/XSDT and exactly one APIC/FACP/HPET/MCFG table, copies and
read-verifies 600 source bytes into a 616-byte release-excluded scrubbed
snapshot, and supplies opaque evidence for the lifecycle transition.
PKPMM7 then admits eleven ACPI reclaimable pages under a second immutable
receipt while retaining the snapshot. Eighty-eight kernel host tests, two
exact 45-marker qemu64 runs, and 191 hostile controls pass. Closeout found and
fixed two real cross-stage contract defects: PKTRAP1 and PKVM2 still used a
retired 14-page stack constant after PooleBoot had moved to 32 pages. Both now
consume the shared 32-page geometry and their live profiles pass. The exact
kernel is 299,008 canonical bytes in a 339,968-byte, 83-page image with 693
relocations and SHA-256
`D9EF9B10B56BF779B155BD18DE55853874CCC032D2A3E5E7841B918F08CDE1F2`.
PKVM2 records 5,640 bootstrap writes and invalidations after the ACPI consumer
is included. N9 remains partial: AML, full platform discovery, a complete
generation-owned physical direct map, SMP shootdown/deferred reclaim,
interrupt-context and concurrent allocation, heaps, pager, pressure/OOM,
target hardware, and N9 exit remain open. The next owner-independent move is
`N9-VM-DIRECT-MAP-001`; PooleGlyph Phase 66 may proceed in parallel without
outranking N0-N9.

Historical Cycle 132 reconciliation: the seven-record native constitution, public/private boundary, architecture baseline, and conformance policy remain partial evidence. The historical completed owner response directs ADR-0003, ADR-0004, and all 38 Workstation v1 definitions while accepting zero measurements. Rooke Poole selected `hardware_fido2_ed25519_sk`, reported no available key, accepted no software-key substitution, and deferred public-key publication at that time; that receipt remains immutable. The selected physical key is still unavailable, the trust store remains empty, and no key was generated or used. Standing Authority Amendment V2 permits ordinary repository and fully gated clean-merge work. Later owner authorization approves compatible-key acquisition, key generation/use, public-key publication, signing, secrets use, privileged probes, driver loading, firmware changes, physical-media writes, tags/releases, and production promotion as operation categories, but it does not supply the key, owner presence, custody/recovery procedure, backups, recovery media, a separately identified safe target, qualified mechanisms, passing release evidence, or permission to bypass this charter. None of those operation categories were exercised in Cycle 132. `N0-HW-KEY-ACQUIRE-001` remains the blocked external move. PooleGlyph remains at the Phase 65/66 boundary with its existing generated-report change preserved and no policy authority inferred from metadata. Cycles 97-131 qualify bounded unsigned boot through PKPMM5 explicit ledger growth and one PKVM2 active-root transaction without production promotion. Cycle 132 closes only the bounded serial scope of `FLAG-N9-PMM-GROWTH-AUTOMATION-001`: selector-8 PKPMM6 checks exact post-operation demand before every automatic scrubbed allocate/free, reserves one allocation and four scrub-receipt slots for complete failed-growth rollback and retry, and grows all active ledgers through 4/8/15/29-page generations with final capacities 2048/256/2048/128/16. Three predecessors totaling 27 pages are revoked, zeroed, read-verified, and retired. The measured sequence records 121 pressure checks, eight triggers, three automatic growths, sixty successful cycles, and four soft fallbacks; a host test proves one hard rejection before physical reads/writes, ownership changes, or receipt commitment because the required 58-page next layout exceeds a bounded 32-page window. An independent Python oracle reconstructs all first-fit generations, alternating windows, retired holes, ownership, pressure counters, reclaim coalescing, and physical access counts. Two exact fresh-vars qemu64 runs emit 43 markers and pass 147 hostile controls plus 84 kernel host tests. They manage 117,911 source-usable and 129,160 final pages, keep eleven ACPI pages held, protect 833 loader pages, scrub and verify 11,462 pages and 46,948,352 bytes, and perform 5,869,568 physical writes, 5,870,592 reads, and 22,798 temporary-PTE writes and invalidations. Growth checksum `0xF7AD111CA266071D` binds the sequence. The retained-layout shift rebinds PKVM2 to 5,560 temporary writes and invalidations. Closeout also fixes and directly guards an identity split so PKMID1 and the live diagnostic both carry `PKBUILD1-CYCLE132-N9-PMM-GROWTH-AUTOMATION-001`. The dependent kernel identity is 278,528 canonical bytes, 319,488 image bytes, and 78 pages with 667 relocations and SHA-256 `CDF33067B2421550BB03A4796FF9A92AE54D40B2575188632BF2C208449B882E`. N9.1-N9.4 remain partial. Complete ACPI consumer integration, complete direct-map and SMP TLB policy, deferred reclaim, huge pages, PCID, COW, user faults, pager IPC, heaps/object caches, MMIO/cache qualification, interrupt-context/concurrent allocation, general pressure/OOM policy, target hardware, N9 exit, trust, persistent state, framebuffer, N4-N8, userspace, drivers, filesystems, PooleGlass, installer, signed ISO, and production gates remain open. `N9-PMM-ACPI-CONSUMER-001` is the next owner-independent move, while PooleGlyph Phase 66 may advance in parallel without outranking N0-N9.

The preceding Cycle 132-136 reconciliations are retained as historical
evidence; the Cycle 137 reconciliation at the head of this charter is
authoritative.

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

Develop PooleGlyph machine language itself and PooleOS in tandem. PooleGlyph is not merely a dependency to import after it is finished: language design, frontend, semantic model, Core IR, assembly, package format, virtual machine, standard library, tools, conformance, optimization, security, release, and PooleOS integration are all governed production work.

At the start of each active cycle:

1. inspect the newest checkpoint, manifest, hashes, release notes, conformance evidence, and repository status;
2. preserve user changes and never rewrite the dirty generated conformance report merely to obtain a clean tree;
3. update the PooleGlyph source anchor and boundary records only from observed evidence;
4. keep parser-to-kernel/system promotion blocked until Phase 66 executable Core IR evidence is accepted;
5. never promote metadata-only declarations into executable or privileged authority.

Every tandem cycle must also:

- classify changes across source syntax, diagnostics, AST, semantics, Core IR, PGASM, PGB2, PGVM2, host ABI, policy, standard library, tools, conformance, performance, release, and IP boundaries;
- update a cross-repository compatibility matrix and identify required migrations before either repository consumes changed bytes;
- retain a public-safe deterministic reference path and independent validators for every canonical representation;
- keep experimental language features behind explicit version/profile gates and preserve stable compatibility windows;
- reject semantic, effect, resource, determinism, or authority drift introduced by optimization or private acceleration;
- advance Phase 66 first, followed by evidence-gated v0.5 stabilization, v0.6 AST-parser replacement, v0.7 modules/standard-library expansion, v0.8 process/runtime prototype, v0.9 replay/debug polish, and v1.0 stable public language.

Rooke Poole owns the PooleGlyph and PooleOS IP. Their source-available path does not make every implementation detail public: canonical specifications, formats, reference toolchain/runtime, and conformance evidence must remain sufficient for independent review, while private PooleMath methods and optimization strategy remain segregated and cannot substitute for public-safe reference behavior or PooleOS security enforcement.

PGB2 must become a canonical signed binary package format. PGVM2 must become a bounded deterministic virtual machine with independent verification, typed effects, explicit capabilities, quotas, deadlines, cancellation, cleanup, traps, replay, and version negotiation. PooleGlyph policy may narrow existing authority but cannot create kernel/device authority. Private or optimized compilers and backends must reproduce the declared reference semantics, effects, authority, and bounded outputs before promotion.

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

## 11. Standing Execution Authority

Standing Authority Amendment V2 authorizes Codex to:

- read, edit, build, test, document, commit, branch, push, and manage pull requests, issues, labels, milestones, project metadata, and draft release material needed by this charter;
- install hash-pinned non-administrative tools under a dedicated PooleOS tools directory without changing global `PATH` or system-wide configuration, while recording source, version, hash, license, and provenance;
- run read-only unprivileged hardware and operating-system inventory commands;
- create or strengthen GitHub Actions, rulesets, required checks, branch protections, vulnerability reporting, and repository security controls;
- mark a Codex-authored draft PR ready and merge it, including into `main`, only when the exact candidate passes the canonical qualification suite, publication-boundary scan, release gate, all configured required GitHub checks, clean-merge check, and review gates, with no blocking review request or unresolved thread;
- merge into non-default `agent/*` integration branches and delete only Codex-created remote `agent/*` branches after merge.

Codex may not force-push, bypass protections, rewrite shared history, delete `main` or a user-created branch, weaken governance, alter repository visibility/ownership/billing, expose secrets, or treat an ordinary permitted merge as production promotion. A later Cycle 118 owner statement, reaffirmed before Cycle 124 closeout, supplies explicit categorical authorization to acquire a compatible FIDO2 key; generate/use the selected key; publish its public key; sign; use secrets without exposing them; run privileged probes; load drivers; change firmware; write physical media; publish tags/releases; and promote production. These are permissions, not evidence or instructions to act immediately. Key work still requires the selected physical device, owner presence, reviewed custody and recovery, exact fingerprint review, and no private-material disclosure. Privileged, driver, firmware, disk, media, boot, TPM, device, and installation work still requires a bounded reviewed mechanism, verified backups and recovery media where applicable, a separately identified safe target, stop conditions, and retained evidence. Tag/release publication or production promotion still requires every charter release gate to pass for the exact bytes. No newly authorized cryptographic, privileged-hardware, mutating, publication, release, or promotion action occurred through Cycle 137; Cycles 132-137 used only host builds and non-promoting virtual-machine execution. Historical owner packets and receipts remain immutable records of the authority that existed when they were created.

## 12. Per-Turn Next-Best-Move Loop

Every active goal turn must:

1. Read this charter, the Build Plan, machine roadmap, checklist coverage ledger, current flags, release gaps, latest cycle log, and previous handoff.
2. Reinspect the live PooleGlyph checkpoint folder and repository state, then decide whether the selected move belongs in PooleOS, PooleGlyph, or a coordinated cross-repository change.
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

Architecture work N0-N5 outranks downstream optimization while those foundations remain unclosed. PDC signed dynamics and the PooleGlyph machine-language lane beginning with Phase 66 may proceed in parallel but cannot substitute for native boot progress.

## 13. Phase Contract

The authoritative completion range is `N0-N39`.

- N0-N4 establish constitution, governance, hardware, toolchain, emulation, reference devices, and formal models.
- N5-N11 establish PooleBoot, boot trust, CPU, interrupts/time/SMP, memory, platform discovery, and IOMMU.
- N12-N16 establish scheduling, capability objects, IPC/isolation, security, and user-space driver domains.
- N17-N24 establish storage, input, PooleFS, user ABI, services, sessions, update/recovery, and power/firmware health.
- N25-N30 establish networking, graphics, audio, desktop/accessibility, and application platform.
- N31-N35 establish observability, PDC, PooleGlyph, reliability, watchdogs, and fault containment.
- N36-N39 establish full verification, supply chain, qualification, and exact signed native ISO release.

A phase may be marked complete only when every mapped required item and applicable research addition passes its Build Plan exit gate with immutable evidence.

## 14. Bootable ISO Contract

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

## 15. Completion Gate

Do not mark this goal complete until all of the following are true for the exact supported release profile:

- all 8,996 implementation requirements are complete or explicitly excluded by signed scope disposition;
- all applicable `ADD-*` requirements are complete;
- all required N0-N39 phases and subphases are complete;
- PooleOS is source-controlled and every release byte has provenance and licensing records;
- PooleBoot and PooleKernel are original, reviewed, reproducible, signed native components;
- capability, IPC, memory, scheduler, IOMMU, driver isolation, storage, PooleFS, network, security, update, recovery, and fault-containment gates pass;
- the promoted PooleGlyph revision, Phase 66 boundary, source/semantic/Core IR/PGASM/PGB2/PGVM2/host-ABI contracts, compatibility profile, public/private IP boundary, independent conformance, and native capability enforcement are accepted for the release profile;
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
