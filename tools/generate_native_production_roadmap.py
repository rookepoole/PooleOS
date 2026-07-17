#!/usr/bin/env python3
"""Generate the machine-readable PooleOS native production roadmap."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "docs/pdc-production-build-plan.md"
COVERAGE_PATH = ROOT / "runs/pooleos_native_checklist_coverage.json"
ARCHIVED_ROADMAP_PATH = ROOT / "runs/archive/cycle79-linux-buildroot-baseline/pdc_production_roadmap.json"


DEPENDENCIES = {
    "N0": [],
    "N1": ["N0"],
    "N2": ["N0", "N1"],
    "N3": ["N0", "N1"],
    "N4": ["N2", "N3"],
    "N5": ["N4"],
    "N6": ["N5"],
    "N7": ["N6"],
    "N8": ["N7"],
    "N9": ["N7"],
    "N10": ["N8", "N9"],
    "N11": ["N10"],
    "N12": ["N8", "N9"],
    "N13": ["N12"],
    "N14": ["N13"],
    "N15": ["N6", "N11", "N14"],
    "N16": ["N10", "N11", "N14", "N15"],
    "N17": ["N16"],
    "N18": ["N16"],
    "N19": ["N14", "N17"],
    "N20": ["N13", "N14"],
    "N21": ["N16", "N19", "N20"],
    "N22": ["N20", "N21"],
    "N23": ["N15", "N19", "N21", "N22"],
    "N24": ["N10", "N17", "N21"],
    "N25": ["N16"],
    "N26": ["N15", "N20", "N25"],
    "N27": ["N16", "N18", "N20"],
    "N28": ["N16", "N20"],
    "N29": ["N18", "N20", "N21", "N27"],
    "N30": ["N20", "N21", "N23", "N29"],
    "N31": ["N6", "N14", "N20"],
    "N32": ["N3", "N20", "N31"],
    "N33": ["N15", "N21", "N31", "N32", "N34"],
    "N34": ["N13", "N14", "N20"],
    "N35": ["N16", "N21", "N24", "N31", "N33"],
    "N36": ["N4", "N31", "N35"],
    "N37": ["N1", "N3", "N23", "N36"],
    "N38": ["N23", "N24", "N26", "N29", "N30", "N33", "N34", "N36", "N37"],
    "N39": ["N37", "N38"],
}


SUBPHASE_OVERRIDES = {
    "N0.1": "partial",
    "N0.2": "partial",
    "N0.3": "partial",
    "N0.4": "partial",
    "N0.5": "partial",
    "N0.6": "partial",
    "N0.7": "partial",
    "N0.8": "partial",
    "N1.1": "partial",
    "N1.2": "partial",
    "N1.3": "partial",
    "N1.4": "partial",
    "N1.5": "partial",
    "N1.6": "partial",
    "N1.7": "partial",
    "N2.1": "partial",
    "N2.2": "partial",
    "N2.4": "partial",
    "N2.5": "partial",
    "N2.6": "partial",
    "N3.1": "partial",
    "N3.2": "partial",
    "N3.3": "partial",
    "N3.6": "partial",
    "N4.1": "partial",
    "N4.2": "partial",
    "N4.3": "partial",
    "N4.4": "partial",
    "N4.5": "partial",
    "N4.6": "partial",
    "N5.1": "partial",
    "N5.2": "partial",
    "N5.3": "partial",
    "N5.4": "partial",
    "N5.5": "partial",
    "N5.7": "partial",
    "N5.8": "partial",
    "N6.4": "partial",
    "N6.5": "partial",
    "N6.6": "partial",
    "N15.1": "partial",
    "N31.7": "partial",
    "N32.1": "complete",
    "N33.1": "partial",
    "N33.8": "partial",
    "N34.1": "partial",
    "N34.3": "blocked",
    "N34.4": "partial",
    "N34.6": "partial",
    "N35.1": "partial",
    "N36.1": "partial",
    "N36.4": "partial",
    "N37.1": "partial",
}


PHASE_EVIDENCE = {
    "N0": [
        "docs/adr/0001-native-pooleos-constitution.md through ADR-0007",
        "specs/native-architecture-constitution.json",
        "runs/native_architecture_baseline.json",
        "specs/native-v1-objectives.json and docs/native-v1-objectives.md: 38 measurable owner-directed target definitions across five required families with zero measurements",
        "runs/native_v1_objectives_readiness.json: deterministic consistency pass with definition acceptance recorded, zero measured targets, and cryptographic signature pending",
        "tools/verify_native_v1_objectives.py with ten fail-closed negative controls",
        "specs/adr-ratification-policy.json and docs/adr-ratification-ceremony.md: scope-hardened contract binding six exact decision sources and all 38 objective definitions without accepting measurements",
        "runs/adr_ratification_readiness.json: all seven ADRs owner-directed, zero trusted signers, selected unavailable hardware-key profile, 12 declared negative controls, and four remaining gated actions",
        "runs/n0_owner_decision_packet.json and docs/n0-owner-decision-packet.md: byte-frozen 16-source historical review packet retaining every original field as UNSELECTED and 12/12 fail-closed controls",
        "specs/n0-owner-response.json, runs/n0_owner_response_receipt.json, and docs/n0-owner-response-receipt.md: exact completed response, 2/2 ADR and 38/38 definition dispositions, unavailable hardware-key state, 16/16 hostile controls, and zero authorization for key generation, signing, merge, tag, or publication",
        "tools/prepare_adr_ratification.py and tools/verify_adr_ratification.py with eleven focused adversarial and signature-path tests",
        "specs/native-release-architecture-policy.json",
        "tools/check_native_release_architecture.py",
        "tests/test_native_release_architecture.py",
    ],
    "N1": [
        "public rookepoole/PooleOS repository with protected main and topic-branch workflow",
        "private vulnerability reporting enabled",
        "LICENSE, NOTICE.md, SECURITY.md, TRADEMARKS.md, and CODEOWNERS",
        "docs/publication-boundary.md",
        "tools/check_publication_boundary.py",
        "public ADR trust and revocation stores are present but intentionally contain zero owner keys",
    ],
    "N2": [
        "specs/hardware-support-policy.json: support tiers, evidence channels, privacy boundary, destructive-test prerequisites, and a source-bound user-mode CPUID versus privileged-probe boundary",
        "specs/tier1-hardware-target.json: exact Tier 1 target and 24 required identity checks",
        "specs/native-standards-register.json: 15 primary-source standards records with revision and supersession state",
        "tools/collect_tier1_hardware.ps1 1.1: bounded W-to-X user-mode CPUID thunk with an exact leaf/subleaf allowlist, lowest allowed logical-processor affinity restored after every query, no processor-serial leaf, no driver, and no privileged access attempt",
        "runs/tier1_hardware_observation.json: sanitized whitelist reconstruction bound to the ignored private capture, with 16 canonical CPUID records represented by a public transcript hash and decoded facts rather than raw registers",
        "runs/hardware_target_readiness.json: 24/24 required identity checks, two partial evidence channels, 16 CPUID records, 14/14 negative controls, zero privacy violations, and explicit non-promotion",
        "docs/hardware-target-and-lab-safety.md: reproducible capture procedure and owner safety boundary",
    ],
    "N3": [
        "ADR-0003 owner-directed Rust/assembly/C17 split with cryptographic signature and full qualification still pending",
        "official Rust UEFI and x86_64-unknown-none target documentation",
        "specs/native-toolchain-lock.json and specs/native-target-contract.json",
        "dependency-free no_std PE32+/ELF64 qualification fixtures",
        "runs/native_toolchain_qualification.json: two byte-identical clean builds per fixture on one host",
        "format-aware inspection, zero host-leakage hits, and three passing negative controls",
    ],
    "N4": [
        "specs/native-tier0-lock.json: exact upstream target, Windows runner, complete runtime, OVMF, VIRTIO, and rejected-candidate locks",
        "specs/native-tier0-profile.json: versioned q35, TCG, immutable pflash, fresh vars, modern-only VIRTIO block, serial/debugcon/debug-exit, tracing, and opt-in GDB contract",
        "runs/native_tier0_readiness.json: 2/2 deterministic profiles, 4/4 paused QMP machine probes, 18/18 fail-closed controls, zero path leaks, and zero boot claims",
        "tools/qualify_native_tier0.py and tools/run_native_tier0.py: workspace-local qualification and dry-run-first launcher with no arbitrary QEMU arguments",
        "docs/native-tier0-qemu.md: acquisition, reproduction, launch, provenance gaps, and non-claim boundary",
        "specs/native-model-toolchain-lock.json and specs/native-model-contract.json: exact workspace-local TLC/Java inputs, six finite-state model contracts, twenty-seven named cases, safe expectations, and required hostile violations",
        "runs/native_model_readiness.json: 6/6 safe state spaces drained, 21/21 required counterexamples detected, 27/27 repeat matches, 31/31 negative controls, and twenty-one normalized traces",
        "models/tla/PooleBootSlots.tla, models/tla/PooleCapabilities.tla, models/tla/PooleVirtualMemory.tla, models/tla/PooleIPC.tla, models/tla/PooleScheduler.tla, and models/tla/PooleFS.tla: bounded boot rollback, capability derivation/revocation, page-ownership/map/unmap/shootdown, capability-mediated IPC, scheduler, and PooleFS transaction/recovery state machines",
        "docs/native-formal-models.md: frozen assumptions, reproduction, trace normalization, open domains, and explicit non-proof boundary",
    ],
    "N5": [
        "specs/native-pooleboot-proof.json: POOLEOS-N5-POOLEBOOT-5 bounded unsigned aggregate contract across N5.1-N5.5, N5.7, and N5.8",
        "native/boot: Poole-authored no_std PE32+ UEFI application with reviewed firmware bindings, independent serial/debugcon diagnostics, live bounded filesystem/config/kernel intake, GOP identity, stride-aware memory-map observation, temporary pre-exit PBP1 production, temporary PKMAP1 candidate-root activation and exact rollback, and EFI_SUCCESS return",
        "runtime/native_kernel_load.py and tools/qualify_native_kernel_load.py: deterministic 64 MiB protective-MBR/GPT/FAT32 ordinary-file media with exact fallback EFI, PBC1 config, PSM1 system manifest, and PKELF1 PooleKernel inspection and no physical-media output mode",
        "runs/native_pooleboot_readiness.json: 8/8 host tests, 2/2 exact 94,720-byte PE builds, 2/2 exact four-file media generations, 2/2 exact QEMU/OVMF runs, twenty-three ordered markers, 2/2 serial/debugcon matches, 2/2 exact GOP frames, and 77/77 hostile controls",
        "docs/native-pooleboot-proof.md: reproduction procedure, observed firmware boundary, hostile corpus, exact evidence, and N5 nonclaims",
        "specs/native-boot-handoff-contract.json and docs/native-boot-handoff.md: canonical PBP1 little-endian header, descriptors, twelve typed records, x86-64 transfer state, ownership/lifetime rules, version negotiation, and explicit nonclaims",
        "native/handoff and runtime/native_boot_handoff.py: dependency-free no_std Rust codec plus independently implemented Python host oracle",
        "runs/native_boot_handoff_readiness.json: 8/8 Rust tests, 2/2 no_std target builds, twelve layout assertions, 3/3 golden vectors, 32/32 hostile controls, and 16,384 Rust/Python differential cases with zero mismatches; PKLOAD4 separately proves a temporary pre-exit producer",
        "native/livehandoff, native/boot/src/livehandoff.rs, and runtime/native_live_boot_handoff.py: allocation-free canonical PBP1 assembly from stride-aware UEFI descriptors, live kernel/manifest/config/GOP bindings, bounded snapshot lifetime, and independent transcript reconstruction",
        "specs/native-boot-config-contract.json and docs/native-boot-config.md: canonical bounded PBC1 text grammar, fail-closed version policy, five boot modes, root-confined UEFI paths, artifact-size bounds, and explicit live-I/O nonclaims",
        "native/bootcfg and runtime/native_boot_config.py: allocation-free dependency-free no_std Rust parser plus independently implemented Python host oracle; PooleBoot has a compile-time path dependency but no live file read",
        "runs/native_boot_config_readiness.json: 12/12 Rust tests, 2/2 no_std parser builds, 2/2 PooleBoot integration builds, 3/3 golden vectors, 64/64 hostile controls, and 16,384 Rust/Python differential cases with zero mismatches",
        "specs/native-elf-loader-contract.json and docs/native-elf-loader.md: bounded PKELF1 ELF64 ET_DYN profile, three canonical load segments, relative relocations, transactional mutation rule, W^X map plan, and explicit firmware/paging/transfer nonclaims",
        "native/elf and runtime/native_elf_loader.py: dependency-free no_std Rust inspector/loader plus an independently implemented Python host oracle; PooleBoot has a compile-time dependency but performs no live file read, allocation, mapping, or transfer",
        "runs/native_elf_loader_readiness.json: 12/12 Rust tests, 2/2 no_std target builds, 2/2 PooleBoot integration builds, 3/3 exact loaded-byte vectors, 129/129 hostile controls, and 16,384 Rust/Python differential cases with zero mismatches",
        "specs/native-system-manifest-contract.json and docs/native-system-manifest.md: canonical bounded PSM1 grammar, exact artifact/slot/version/path/size/SHA-256/entry binding, independent parser, and explicit unsigned trust boundary",
        "native/manifest and runtime/native_system_manifest.py: allocation-free no_std Rust parser and SHA-256 provider integration plus an independently implemented Python oracle",
        "runs/native_system_manifest_readiness.json: 8/8 Rust tests, 2/2 no_std target builds, one PooleBoot integration build, 3/3 golden vectors, 64/64 hostile controls, 16,384 differential cases, and 1,027 SHA-256 agreement cases with zero mismatches",
        "specs/native-kernel-load-contract.json and docs/native-kernel-load.md: PKLOAD4 freezes live UEFI file intake, manifest/digest binding, retained-through-snapshot allocation, pre-exit PBP1 production, temporary PKMAP1 activation and rollback, cleanup, marker, trust, and nonclaim boundaries",
        "native/bootload, native/boot/src/kload.rs, native/boot/src/kmap.rs, and runtime/native_kernel_load.py: dependency-free load contract, reviewed raw UEFI adapters, and independent media/oracle implementation",
        "specs/native-kernel-map-contract.json, native/kmap, runtime/native_kernel_map.py, and docs/native-kernel-map.md: PKMAP1 exact 4 KiB supervisor mapping, W^X/WP/NX, active-root clone, framebuffer-preservation, activation, rollback, cleanup, and nonclaim contract",
        "runs/native_kernel_load_readiness.json: 59/59 Rust host tests, 2/2 exact PooleBoot builds, 2/2 exact PooleKernel builds, 2/2 exact media generations, 2/2 QEMU/OVMF runs, 23 ordered markers, 77/77 hostile controls, two exact 4,248-byte PBP1 reconstructions, exact 48-page higher-half map and full-image hash agreement, exact CR3 rollback, and exact guest/oracle agreement",
    ],
    "N6": [
        "specs/native-kernel-entry-contract.json and docs/native-kernel-entry.md: PKENTRY1 transfer, mapping, diagnostic, panic, build, and explicit nonclaim boundary",
        "native/kernel: real freestanding PooleKernel product with fixed entry assembly, allocation-free PBP1 intake, static early ring, bounded COM1 candidate, optional volatile framebuffer sink, and terminal panic path",
        "runtime/native_kernel_image.py: fail-closed pinned-LLD input validation and deterministic PKELF1 canonicalization",
        "runs/native_kernel_entry_readiness.json: 13/13 host tests, 2/2 exact clean linked and canonical builds, 43/43 hostile controls, exact independent Rust/Python loaded bytes, and canonical SHA-256 BF1176019E9E4AF1C588898F565A6B1F66737517C2D3CA804510C4B0AC1B2E9D",
        "specs/native-boot-digest-provider.json: PBDIGEST1 pins vendored RustCrypto sha2 0.11.0, the soft-compact UEFI backend, locked transitive packages, and reproducible /pooleos/native source-path remapping while retaining independent security review and provider promotion as open",
        "ADD-BOOT-003: boot-time digest-provider pinning, reproducible path remapping, qualification, independent review, and target-backend promotion boundary",
        "ADD-KERNEL-001: explicit temporary framebuffer identity mapping, cache-policy preservation, lifetime, replacement, and revocation dependency",
    ],
    "N15": ["runs/microkernel_isolation.json", "runs/capability_trap_proof.json", "runs/capability_trap_fuzz.json"],
    "N31": ["existing signed receipt and benchmark methodology artifacts"],
    "N32": ["PDC-MATH-0.1", "PDC-REP-0.1", "PDC-GOLDEN-0.2", "PDC-QP-0.1", "PDC-QP-STABILITY-0.1"],
    "N33": ["existing PDC receipt schemas and guarded-route source documents; no native services"],
    "N34": [
        "PooleGlyph Phase 65 checkpoint and manifest with verified ZIP SHA-256 F3CCEB701CF76274D9464A0958BF6106888FB34F3C0BFBD55DE4ACE03C427ABC",
        "PooleGlyph v0.5-dev parser, source-spanned AST, semantic diagnostics, Core IR candidate, source-map, module, and conformance foundations",
        "runs/pooleglyph_source_anchor.json, runs/pooleglyph_bridge_manifest.json, runs/pooleglyph_core_ir_boundary_receipt.json, runs/pooleglyph_core_ir_executable_audit.json, and runs/pooleglyph_parser_kernel_promotion_receipt.json",
        "draft PGB2/PGVM2 trap evidence and capability/resource bridge artifacts",
        "Cycle 92 N34 machine-language co-development plan with six ADD-PGL requirements and explicit drift, Core IR, and IP flags",
    ],
    "N35": ["bounded static capability and trap simulations; no native containment"],
    "N36": ["Cycle 105 host baseline: 592 tests with one Windows symlink-permission skip", "native binary parser, reproduction, leakage, malformed, substitution, objectives, ADR-signing, ratification-scope, frozen owner-packet and completed owner-response omission/staleness/placeholder/custody/private-material/authorization controls, hardware privacy, malformed-CPUID, Tier 0 profile/provenance/path/overclaim, bounded-model multi-case mutation/trace/claim controls including six independent PooleFS mutants, deterministic GPT/FAT32 inspection, media path-policy rejection, PE mutation, marker/frame, PBP1, PBC1, PSM1, PKELF1, PKENTRY1, and PKLOAD4 live-file/manifest/digest/allocation/PBP1/PKMAP1 activation/rollback/lifetime/cleanup/oracle/claim controls, PooleGlyph roadmap bindings, and collector-smoke negatives"],
    "N37": ["Cycle 105 consistency release gate: 76/76 checks over 71 artifacts", "content-addressed source, objectives-readiness, scope-hardened ADR-readiness, frozen N0 owner packet, deterministic owner-response receipt, native-toolchain, bounded hardware-readiness, native Tier 0 readiness, native model-readiness, bounded PooleBoot readiness, PBP1 readiness, PBC1 readiness, PSM1 readiness, PKELF1 readiness, PKENTRY1 readiness, PKLOAD4/PKMAP1 readiness, and PooleGlyph planning artifacts"],
}


PHASE_GAPS = {
    "N0": [
        "The completed response records exact owner direction for ADR-0003, ADR-0004, and all 38 objective definitions, but the selected hardware-backed governance key is unavailable and no public key, signature, tag, merge, or publication is authorized",
        "The 38 reliability, accessibility, compatibility, privacy, and performance definitions are owner-directed but cryptographically unsigned; every implementation-bound measurement remains open",
        "The extracted-tree scanner does not yet parse ISO/GPT/ESP/El Torito/signature structures",
    ],
    "N1": [
        "Public remote and branch protection exist; owner key choice, signed tags, immutable release refs, retained CI/review evidence, signing custody, and multi-maintainer approval policy remain open",
        "Legal, patent, export, trademark, contributor, signing-custody, and component-specific license review remain open",
    ],
    "N2": ["Exact identity passes 24/24 required checks and 16 allowlisted user-mode CPUID records close the bounded CPUID sub-capability, but MSR access remains pending a reviewed privileged mechanism; seven required evidence channels, 15 exact standards artifact hashes, ten destructive-lab prerequisites, and native-parser comparison remain open"],
    "N3": ["One-host Rust PE32+/ELF64 qualification passes; second-host reproduction, source provenance, C17/assembly/ABI/image tools, complete build graph, and low-level safety gates remain open"],
    "N4": ["A pinned one-host q35/QEMU/OVMF/VIRTIO profile, paused-instantiation evidence, bounded checks for all seven required boot-slot/capability/virtual-memory/IPC/scheduler/update/PooleFS domains, and two bounded PooleBoot guest runs exist, but current upstream source rebuilds, debug-exit/GDB/reset/fault evidence, remaining VIRTIO profiles, malformed-device campaigns, six implementation-trace cross-checks, liveness/refinement/conformance work, and second-host reproduction remain open"],
    "N5": ["A reproducible unsigned PooleBoot, PBP1, PBC1, PSM1, PKELF1, PKMAP1, real PooleKernel image, and bounded live config/manifest/kernel digest-bound path now produce an exact temporary pre-exit PBP1 snapshot and temporarily activate, audit, and roll back an exact higher-half W^X mapping; however, signature-backed trusted manifest selection, persistent rollback enforcement, retained handoff, kernel, and page-table allocations, final framebuffer cache policy, menu/rollback policy, kernel consumption, final memory-map retry, ExitBootServices transfer, second host, target firmware, physical media, and N5 exit remain open"],
    "N6": ["A reproducible real PooleKernel PKELF1 image, candidate PKENTRY1 intake, bounded ring/COM1/framebuffer diagnostics, and panic classes exist only as single-host product/static evidence; boot trust, measured boot, live mappings and transfer, framebuffer mapping proof, GDT/IDT/TSS, exception and retained-crash paths, kernel runtime, target execution, and N6 exit remain open"],
    "N7": ["No native CPU/descriptor/exception implementation exists"],
    "N8": ["No native APIC/timer/SMP implementation exists"],
    "N9": ["No native allocator, paging, address-space, or reclaim implementation exists"],
    "N10": ["No native ACPI/AML/SMBIOS/PCIe resource graph exists"],
    "N11": ["No AMD IOMMU or interrupt-remapping confinement exists"],
    "N12": ["No native concurrency primitives, scheduler, or context switch exists"],
    "N13": ["No ring-3 task, syscall, or capability object implementation exists"],
    "N14": ["No native IPC, isolation, async completion, or quota implementation exists"],
    "N15": ["Current security artifacts are simulations; native crypto, TPM, MAC, and mitigations are absent"],
    "N16": ["No isolated native driver domain or virtio transport exists"],
    "N17": ["No native block, NVMe, partition, or volume path exists"],
    "N18": ["No native virtio input, xHCI, USB, HID, or removable-media path exists"],
    "N19": ["No native VFS, PooleFS, page cache, encryption, or power-loss evidence exists"],
    "N20": ["No native executable loader, user ABI, libc, threads, or language runtime exists"],
    "N21": ["No native init, service graph, utilities, logging, device policy, or health service exists"],
    "N22": ["No native authentication, session, shell, PTY, terminal, account, or user-data model exists"],
    "N23": ["No native packages, TUF-style updates, installer, recovery, backup, or migration exists"],
    "N24": ["No native shutdown/power/firmware/sensor/health implementation exists"],
    "N25": ["No native virtio-net, RTL8125, Wi-Fi, or Bluetooth driver exists"],
    "N26": ["No native network stack, services, firewall, or TLS integration exists"],
    "N27": ["No native software renderer or virtio-gpu path exists; RTX support remains research"],
    "N28": ["No native audio path or media/peripheral service exists"],
    "N29": ["No native compositor, PooleGlass desktop, toolkit, accessibility, or boot identity exists"],
    "N30": ["No native application ABI, SDK, sandbox, or portal model exists"],
    "N31": ["No native debugger, crash dump, trace, PMU, or system metrics implementation exists"],
    "N32": ["Signed dynamics and portable/native C/CPU/RAM/GPU execution remain open"],
    "N33": ["No native PDC observer/planner/gate/actuator/watchdog/rollback service exists"],
    "N34": [
        "PooleGlyph Phase 66 Core IR classification and promotion evidence are absent",
        "Source, semantic, Core IR, PGASM, PGB2, PGVM2, host-ABI, policy, compatibility, release, and IP contracts are not frozen for a PooleOS profile",
        "No independent end-to-end toolchain, native PGVM2 runtime, capability-broker integration, private-backend equivalence, or cross-repository compatibility release evidence exists",
    ],
    "N35": ["No native watchdog, driver restart, RAS, or fault-containment evidence exists"],
    "N36": ["No native system, power-loss, hardware, accessibility, soak, or external security suite exists"],
    "N37": ["No native SBOM/provenance/signing ceremony/release manifest or source-controlled release exists"],
    "N38": ["No native milestone, first hardware boot, daily-driver, or public-alpha gate has passed"],
    "N39": ["No reproducible signed native ISO, clean-media boot, or exact-byte release receipt exists"],
}


FLAGS = [
    ("FLAG-NATIVE-SCM-001", "STOP_SHIP", "N1", "Put PooleOS under reviewed source control with immutable release revisions"),
    ("FLAG-NATIVE-ADR-001", "BLOCKER", "N0", "Ratify the native architecture, TCB, reuse, language, ABI, driver, filesystem, and release ADR set"),
    ("FLAG-N0-OBJECTIVES-001", "REQUIRED", "N0", "Owner-ratify the native v1 profile and all 38 target values, then bind passing implementation evidence to every target"),
    ("FLAG-N0-RATIFICATION-SCOPE-001", "REQUIRED", "N0", "Bind the exact objective definitions and schema into the owner ceremony while excluding measurements and all production promotion"),
    ("FLAG-N0-GOVERNANCE-KEY-001", "BLOCKER", "N0", "Obtain a compatible FIDO2 hardware key, then separately authorize and verify governance-key generation, public fingerprint review, signer registration, and recovery custody without exposing private material"),
    ("FLAG-NATIVE-BOOT-001", "STOP_SHIP", "N5", "Boot reproducible PooleBoot PE32+ and transfer through the frozen handoff"),
    ("FLAG-N5-POOLEBOOT-PROOF-001", "REQUIRED", "N5", "Reproduce the bounded unsigned PooleBoot PE32+ proof, deterministic GPT/FAT32 media, ordered dual-channel diagnostics, GOP frame, and hostile corpus without claiming the complete loader or N5 exit"),
    ("FLAG-N5-BOOTPROTO-001", "REQUIRED", "N5", "Qualify the canonical PBP1 byte schema with no_std codec, independent decoder, layout assertions, golden bytes, downgrade controls, malformed corpus, and deterministic differential fuzzing before loader or kernel entry code depends on it"),
    ("FLAG-N5-BOOTCFG-001", "REQUIRED", "N5", "Qualify the bounded PBC1 grammar with an allocation-free no_std parser, independent oracle, golden semantics, duplicate/unknown-key, traversal, range, truncation, version, capacity, artifact-size, and deterministic differential controls before live filesystem integration"),
    ("FLAG-N5-ELF-001", "REQUIRED", "N5", "Qualify the bounded PKELF1 ELF64 ET_DYN profile with allocation-free no_std inspection/loading, independent oracle, exact loaded bytes, transactional rejection, relocation, W^X planning, hostile controls, and deterministic differential evidence before live firmware integration"),
    ("FLAG-N5-KLOAD-001", "REQUIRED", "N5", "Qualify bounded live UEFI PBC1 and PKELF1 reads, exact firmware-page allocation, relocation, W^X mapping-plan validation, deterministic cleanup, guest/oracle agreement, and hostile controls without claiming authentication, installed mappings, transfer, or N5 exit"),
    ("FLAG-N5-MANIFEST-001", "REQUIRED", "N5", "Qualify canonical bounded PSM1 parsing, exact slot/version/path/size/digest/entry binding, manifest-driven live selection, artifact hashing, deterministic cleanup, independent agreement, and hostile controls without claiming signature trust, rollback persistence, transfer, or N5 exit"),
    ("FLAG-N5-PBP1-LIVE-001", "REQUIRED", "N5", "Qualify temporary pre-ExitBootServices PBP1 production from stride-aware firmware descriptors and exact config, manifest, kernel, and GOP bindings with bounded storage lifetime, cleanup, independent transcript reconstruction, hostile controls, and no retained-handoff or transfer claim"),
    ("FLAG-N5-KMAP-001", "REQUIRED", "N5", "Qualify exact supervisor 4 KiB higher-half kernel mappings through an active-root clone, W^X/WP/NX enforcement, framebuffer translation and cache preservation, candidate CR3 activation, complete alias audit, exact rollback, zero active-root firmware calls, and cleanup without retained-address-space, transfer, or N5-exit claims"),
    ("FLAG-N6-KENTRY-001", "REQUIRED", "N6", "Qualify a real reproducible PooleKernel PKELF1 product with PKENTRY1 intake, bounded early diagnostics, panic taxonomy, hostile controls, manifest continuity, and explicit live-transfer nonclaims"),
    ("FLAG-N6-BOOT-DIGEST-001", "REQUIRED", "N6", "Complete independent cryptographic and supply-chain review of the pinned PBDIGEST1 provider, qualify its exact target backend, and prohibit trust promotion until the review and provider-promotion gates pass"),
    ("FLAG-N6-FRAMEBUFFER-MAP-001", "REQUIRED", "N6", "Install and record the exact temporary framebuffer identity mapping, preserve effective cache policy, and replace and revoke that mapping before graphics capability delegation"),
    ("FLAG-NATIVE-KERNEL-001", "STOP_SHIP", "N13", "Boot PooleKernel and enforce memory, capabilities, IPC, and ring-3 execution"),
    ("FLAG-NATIVE-IOMMU-001", "STOP_SHIP", "N11", "Confine all bus-mastering drivers with DMA and interrupt remapping"),
    ("FLAG-NATIVE-DRIVER-001", "STOP_SHIP", "N16", "Prove driver crash/reset/revocation without stale authority"),
    ("FLAG-NATIVE-FS-001", "STOP_SHIP", "N19", "Pass declared PooleFS durability and randomized power-cut gates"),
    ("FLAG-NATIVE-UPDATE-001", "STOP_SHIP", "N23", "Pass signed A/B update, rollback, compromise, and recovery gates"),
    ("FLAG-NATIVE-SEC-001", "STOP_SHIP", "N15", "Pass boot trust, crypto/RNG, capability, isolation, and external security review"),
    ("FLAG-NATIVE-UI-001", "REQUIRED", "N29", "Pass PooleGlass accessibility, software fallback, and recovery UI gates"),
    ("FLAG-NATIVE-PGL-001", "BLOCKER", "N34", "Close the promoted PooleGlyph language, Phase 66, PGB2/PGVM2 v1, host-ABI, compatibility, native-integration, and recovery gates"),
    ("FLAG-PGL-CODEV-001", "REQUIRED", "N34", "Bind exact PooleGlyph and PooleOS revisions, checkpoint evidence, change impacts, and compatibility profiles so neither repository drifts silently"),
    ("FLAG-PGL-CORE-IR-001", "BLOCKER", "N34", "Accept Phase 66 classification and independent validation proving metadata cannot become executable or privileged Core IR"),
    ("FLAG-PGL-IP-001", "REQUIRED", "N34", "Review and enforce the source-available/public/private component boundary while keeping private backends reference-equivalent and non-authority-amplifying"),
    ("FLAG-NATIVE-PDC-001", "REQUIRED", "N32", "Reproduce signed dynamics and pass native/backend differential gates"),
    ("FLAG-NATIVE-HW-001", "STOP_SHIP", "N38", "Qualify exact Tier 1 hardware, firmware, media, drivers, and recovery"),
    ("FLAG-N2-CPUID-001", "REQUIRED", "N2", "Capture and sanitize a bounded direct user-mode CPUID transcript with an exact allowlist, no processor-serial leaf, no raw-register publication, and passing malformed/overclaim negative controls"),
    ("FLAG-N2-PRIVILEGED-PROBE-001", "BLOCKER", "N2", "Qualify source-bound read-only MSR, PCI, SPD, UEFI-variable, memory, and I/O mechanisms through driver and side-effect review, then require explicit operator authorization before any driver load or privileged probe"),
    ("FLAG-N2-EVIDENCE-001", "REQUIRED", "N2", "Complete read-only CPUID/MSR, PCI configuration, ACPI duplicate, EDID/SPD, UEFI-variable, sensor/power, and native-parser comparison evidence"),
    ("FLAG-N2-STANDARDS-001", "REQUIRED", "N2", "Acquire and hash lawfully accessible exact standards artifacts and close supersession, errata, profile, and access review"),
    ("FLAG-N2-LAB-SAFETY-001", "BLOCKER", "N2", "Obtain owner acceptance for sacrificial media, backups, recovery, diagnostics, power, and network controls plus separate destructive-test approval"),
    ("FLAG-N4-PROFILE-001", "REQUIRED", "N4", "Freeze and adversarially qualify the exact native-only q35/QEMU/OVMF/VIRTIO launch profile without a boot claim"),
    ("FLAG-N4-PROVENANCE-001", "BLOCKER", "N4", "Source-build the pinned current QEMU and EDK II targets, verify signatures and patch deltas, complete license/SBOM/vulnerability review, and reproduce on a second host"),
    ("FLAG-N4-MODELS-001", "BLOCKER", "N4", "Execute bounded counterexample models and cross-check their traces before dependent ABI freezes"),
    ("FLAG-N4-IPC-MODEL-001", "REQUIRED", "N4", "Exhaust the frozen capability-mediated IPC state space, detect unauthorized enqueue, reply-token reuse, stale reply, and teardown-leak mutants, and retain the finite non-proof boundary"),
    ("FLAG-N4-SCHEDULER-MODEL-001", "REQUIRED", "N4", "Exhaust the frozen scheduler state space, detect lost cancel and timeout wakeups, duplicate runnable entries, missing priority inheritance, priority and bounded-bypass violations, and teardown leakage while retaining the no-liveness boundary"),
    ("FLAG-N4-POOLEFS-MODEL-001", "REQUIRED", "N4", "Exhaust the frozen PooleFS transaction/recovery state space, detect torn-write, premature-publication, double-allocation, non-idempotent-replay, checksum-acceptance, and recovery-leak mutants, and retain the finite non-implementation boundary"),
    ("FLAG-NATIVE-ISO-001", "STOP_SHIP", "N39", "Reproduce and boot the exact signed native ISO in clean QEMU and physical profiles"),
    ("FLAG-NATIVE-REVIEW-001", "STOP_SHIP", "N37", "Close critical/high independent kernel, filesystem, update, security, and release findings"),
    ("FLAG-BUILDROOT-LEGACY-001", "SUPERSEDED", "N0", "Keep Buildroot as historical non-promoting reference evidence"),
]


PROGRAM_GAPS = [
    "The native repository, protected workflow, scope-hardened ADR ceremony, frozen 16-source packet, and completed response receipt record 2/2 ADR and 38/38 definition dispositions, but all measurements, compatible hardware-key acquisition, trusted public key custody, signatures, signed tags, immutable release refs, and retained CI review evidence remain open",
    "Rust PE32+/ELF64 fixtures pass one-host qualification, but second-host reproduction, source provenance, C17/assembly/ABI tools, and image tooling remain open",
    "The native-only q35/QEMU/OVMF/VIRTIO profile passes one-host paused-instantiation controls, bounded checks for all seven required boot-slot/capability/virtual-memory/IPC/scheduler/update/PooleFS domains detect their required hostile violations, and a bounded PooleBoot proof executes under pinned OVMF, but source-rebuilt current QEMU/EDK II, complete reference devices/fault campaigns, six implementation-trace cross-checks, liveness/refinement/conformance work, and second-host reproduction remain open",
    "A reproducible unsigned PooleBoot proof application boots twice with deterministic GPT/FAT32 media, ordered dual-channel markers, exact GOP frames, independently reconstructed temporary pre-exit PBP1 bytes, and temporary PKMAP1 higher-half activation with exact rollback, while canonical PBP1, PBC1, PSM1, bounded PKELF1, and a separately qualified real PooleKernel product pass their declared gates; live manifest-driven file I/O, SHA-256 artifact equality, firmware allocation, pre-exit handoff production, exact W^X leaves, and framebuffer translation/cache preservation are bounded evidence, but trusted signature selection, rollback persistence, retained page-table and handoff storage, final framebuffer cache policy, kernel consumption, final-map retry, ExitBootServices transfer, target firmware, physical-media qualification, and N5 exit remain open",
    "A real reproducible PooleKernel image, PKENTRY1 intake, bounded early ring/COM1/framebuffer paths, and panic classes exist, but boot trust, measured boot, live mappings and transfer, descriptor/exception setup, retained crash evidence, kernel runtime, target execution, and N6 exit remain open",
    "No native CPU, interrupts, time, SMP, physical memory, virtual memory, or reclaim implementation",
    "The exact Tier 1 identity passes 24/24 required checks and 16 allowlisted user-mode CPUID records are captured with zero public raw registers, but seven required channels remain non-complete in total, including partial CPU/MSR and SPD/topology; 15 standards hashes, ten lab-safety prerequisites, native parsing, and physical qualification also remain open",
    "No native DMA/IOMMU/interrupt-remapping confinement",
    "No native scheduler, task, syscall, capability, IPC, isolation, async I/O, or quota implementation",
    "No native security/crypto/TPM/secrets/MAC/privacy implementation or external review",
    "No isolated native driver domains or virtio reference drivers",
    "No native block/NVMe/USB/input/VFS/PooleFS persistent path",
    "No native user ABI, libc, init, service manager, login, shell, terminal, package, update, installer, or recovery",
    "No native network, graphics, audio, compositor, PooleGlass, accessibility, or application platform",
    "No source-bound signed PDC dynamics or portable/native PDC backends",
    "No native PDC control-plane services or bounded actuator proof",
    "PooleGlyph Phase 66 and the source, semantic, Core IR, PGASM, PGB2, PGVM2, host-ABI, policy, toolchain, compatibility, IP-boundary, private-backend-equivalence, and native-integration gates remain open",
    "No native integrated fuzz/fault/power-loss/security/conformance/soak evidence",
    "No native SBOM/provenance/signing ceremony/operations/release manifest",
    "No reproducible signed native ISO or exact clean-media QEMU/physical release receipt",
]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def parse_plan() -> tuple[list[dict], dict[str, str]]:
    text = PLAN_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()
    phase_indices: list[tuple[int, str, str, str]] = []
    for index, line in enumerate(lines):
        match = re.match(r"^### (N\d+) - (.+) \(`([^`]+)`\)$", line)
        if match:
            phase_indices.append((index, match.group(1), match.group(2), match.group(3)))
    if len(phase_indices) != 40:
        raise ValueError(f"expected 40 native phases in Build Plan, found {len(phase_indices)}")

    phases = []
    exit_gates: dict[str, str] = {}
    for position, (start, phase_id, title, status) in enumerate(phase_indices):
        end = phase_indices[position + 1][0] if position + 1 < len(phase_indices) else len(lines)
        block = lines[start:end]
        subphases = []
        for line in block:
            match = re.match(r"^- (N\d+\.\d+) (.+)$", line)
            if match:
                subphase_id = match.group(1)
                subphases.append(
                    {
                        "id": subphase_id,
                        "status": SUBPHASE_OVERRIDES.get(subphase_id, "not_started"),
                        "description": match.group(2),
                    }
                )
            if line.startswith("Exit gate: "):
                exit_gates[phase_id] = line[len("Exit gate: ") :]
        phases.append({"id": phase_id, "title": title, "status": status, "subphases": subphases})
    return phases, exit_gates


def make_roadmap(test_count: int, status_date: str) -> dict:
    coverage = json.loads(COVERAGE_PATH.read_text(encoding="utf-8"))
    archived = json.loads(ARCHIVED_ROADMAP_PATH.read_text(encoding="utf-8"))
    phases, exit_gates = parse_plan()
    coverage_by_phase = {item["phase_id"]: item for item in coverage["phase_coverage"]}

    for phase in phases:
        phase_id = phase["id"]
        cover = coverage_by_phase[phase_id]
        phase["depends_on"] = DEPENDENCIES[phase_id]
        phase["source_section_ids"] = cover["source_section_ids"]
        phase["source_checkbox_count"] = cover["source_checkbox_count"]
        phase["added_requirement_ids"] = cover["added_requirement_ids"]
        phase["current_evidence"] = PHASE_EVIDENCE.get(phase_id, [])
        phase["current_gaps"] = PHASE_GAPS[phase_id]
        phase["exit_gate"] = exit_gates[phase_id]

    status_counts = Counter(phase["status"] for phase in phases)
    source_set = list(archived["source_set"])
    source_set.append(
        {
            "id": "SRC-NATIVE-CHECKLIST-1",
            "path": coverage["source"]["path"],
            "kind": "markdown",
            "sha256": coverage["source"]["sha256"],
            "claim_role": "Normative from-scratch native OS leaf-requirement register.",
            "intake_status": "imported_locked",
        }
    )

    pdc_baseline_keys = [
        "pdc_math",
        "pdc_verifiers",
        "pdc_representation",
        "pdc_golden_metamorphic",
        "pdc_qp",
        "pdc_qp_stability",
    ]
    pdc_baseline = {key: archived["baseline"][key] for key in pdc_baseline_keys}

    implementation_flags = []
    for flag_id, flag_class, phase_id, closure in FLAGS:
        evidence = ["docs/pdc-production-build-plan.md", "runs/pooleos_native_checklist_coverage.json"]
        if phase_id == "N2":
            evidence.extend(["runs/hardware_target_readiness.json", "specs/hardware-support-policy.json"])
        if phase_id == "N4":
            evidence.extend(["runs/native_tier0_readiness.json", "specs/native-tier0-lock.json", "specs/native-tier0-profile.json"])
        if phase_id == "N5":
            evidence.extend(
                [
                    "specs/native-pooleboot-proof.json",
                    "runs/native_pooleboot_readiness.json",
                    "docs/native-pooleboot-proof.md",
                    "native/boot/src/main.rs",
                    "specs/native-boot-handoff-contract.json",
                    "specs/native-boot-handoff-golden-vectors.json",
                    "runs/native_boot_handoff_readiness.json",
                    "docs/native-boot-handoff.md",
                    "native/handoff/src/lib.rs",
                    "specs/native-boot-config-contract.json",
                    "specs/native-boot-config-golden-vectors.json",
                    "runs/native_boot_config_readiness.json",
                    "docs/native-boot-config.md",
                    "native/bootcfg/src/lib.rs",
                    "specs/native-elf-loader-contract.json",
                    "specs/native-elf-loader-golden-vectors.json",
                    "runs/native_elf_loader_readiness.json",
                    "docs/native-elf-loader.md",
                    "native/elf/src/lib.rs",
                    "specs/native-kernel-load-contract.json",
                    "specs/native-kernel-load-contract.schema.json",
                    "specs/native-kernel-load-readiness.schema.json",
                    "runs/native_kernel_load_readiness.json",
                    "docs/native-kernel-load.md",
                    "native/bootload/src/lib.rs",
                    "native/boot/src/kload.rs",
                    "specs/native-system-manifest-contract.json",
                    "specs/native-system-manifest-golden-vectors.json",
                    "specs/native-boot-digest-provider.json",
                    "runs/native_system_manifest_readiness.json",
                    "docs/native-system-manifest.md",
                    "native/manifest/src/lib.rs",
                ]
            )
        if phase_id == "N6":
            evidence.extend(
                [
                    "specs/native-kernel-entry-contract.json",
                    "runs/native_kernel_entry_readiness.json",
                    "docs/native-kernel-entry.md",
                    "native/kernel/src/main.rs",
                    "native/kernel/src/lib.rs",
                    "runtime/native_kernel_image.py",
                    "runtime/native_kernel_entry.py",
                    "tools/qualify_native_kernel_entry.py",
                    "tests/test_native_kernel_entry.py",
                ]
            )
        if phase_id == "N34":
            evidence.extend(
                [
                    "docs/pooleglyph-checkpoint-deep-inspection.md",
                    "runs/pooleglyph_source_anchor.json",
                    "runs/pooleglyph_core_ir_boundary_receipt.json",
                    "runs/pooleglyph_parser_kernel_promotion_receipt.json",
                ]
            )
        if flag_id in {"FLAG-N4-MODELS-001", "FLAG-N4-IPC-MODEL-001", "FLAG-N4-SCHEDULER-MODEL-001", "FLAG-N4-POOLEFS-MODEL-001"}:
            evidence.extend(
                [
                    "runs/native_model_readiness.json",
                    "specs/native-model-toolchain-lock.json",
                    "specs/native-model-contract.json",
                    "models/tla/PooleIPC.tla",
                    "models/tla/PooleScheduler.tla",
                    "models/tla/PooleFS.tla",
                    "docs/native-formal-models.md",
                ]
            )
        if flag_id == "FLAG-N2-CPUID-001":
            evidence.extend(
                [
                    "tools/collect_tier1_hardware.ps1",
                    "runs/tier1_hardware_observation.json",
                    "specs/tier1-hardware-observation.schema.json",
                ]
            )
        if flag_id == "FLAG-N2-PRIVILEGED-PROBE-001":
            evidence.extend(
                [
                    "specs/tier1-hardware-capture.schema.json",
                    "docs/hardware-target-and-lab-safety.md",
                ]
            )
        if flag_id == "FLAG-N0-OBJECTIVES-001":
            evidence.extend(["specs/native-v1-objectives.json", "runs/native_v1_objectives_readiness.json", "runs/n0_owner_decision_packet.json"])
        if flag_id == "FLAG-NATIVE-ADR-001":
            evidence.extend(["runs/adr_ratification_readiness.json", "runs/n0_owner_decision_packet.json", "docs/n0-owner-decision-packet.md"])
        if flag_id == "FLAG-N0-RATIFICATION-SCOPE-001":
            evidence.extend(
                [
                    "specs/adr-ratification-policy.json",
                    "specs/native-v1-objectives.json",
                    "specs/native-v1-objectives.schema.json",
                    "runs/adr_ratification_readiness.json",
                ]
            )
        if flag_id == "FLAG-N0-GOVERNANCE-KEY-001":
            evidence.extend(
                [
                    "specs/n0-owner-response.json",
                    "runs/n0_owner_response_receipt.json",
                    "runs/adr_ratification_readiness.json",
                    "security/owner-adr-signers.allowed",
                ]
            )
        if flag_id == "FLAG-N5-BOOTPROTO-001":
            evidence.extend(
                [
                    "runtime/native_boot_handoff.py",
                    "tools/qualify_native_boot_handoff.py",
                    "tests/test_native_boot_handoff.py",
                ]
            )
        if flag_id == "FLAG-N5-BOOTCFG-001":
            evidence.extend(
                [
                    "runtime/native_boot_config.py",
                    "tools/qualify_native_boot_config.py",
                    "tests/test_native_boot_config.py",
                ]
            )
        if flag_id == "FLAG-N5-ELF-001":
            evidence.extend(
                [
                    "runtime/native_elf_loader.py",
                    "tools/qualify_native_elf_loader.py",
                    "tests/test_native_elf_loader.py",
                ]
            )
        if flag_id == "FLAG-N5-KLOAD-001":
            evidence.extend(
                [
                    "runtime/native_kernel_load.py",
                    "tools/qualify_native_kernel_load.py",
                    "tests/test_native_kernel_load.py",
                ]
            )
        if flag_id == "FLAG-N5-MANIFEST-001":
            evidence.extend(
                [
                    "runtime/native_system_manifest.py",
                    "tools/qualify_native_system_manifest.py",
                    "tests/test_native_system_manifest.py",
                ]
            )
        if flag_id == "FLAG-N5-PBP1-LIVE-001":
            evidence.extend(
                [
                    "native/livehandoff/src/lib.rs",
                    "native/boot/src/livehandoff.rs",
                    "runtime/native_live_boot_handoff.py",
                    "tools/qualify_native_kernel_load.py",
                    "runs/native_kernel_load_readiness.json",
                ]
            )
        if flag_id == "FLAG-N5-KMAP-001":
            evidence.extend(
                [
                    "specs/native-kernel-map-contract.json",
                    "native/kmap/src/lib.rs",
                    "native/boot/src/kmap.rs",
                    "runtime/native_kernel_map.py",
                    "docs/native-kernel-map.md",
                    "tests/test_native_kernel_map.py",
                    "runs/native_kernel_load_readiness.json",
                ]
            )
        if flag_id == "FLAG-N6-BOOT-DIGEST-001":
            evidence.extend(
                [
                    "specs/native-boot-digest-provider.json",
                    "native/third_party/rustcrypto-sha2-0.11.0.md",
                    "native/Cargo.lock",
                    "native/vendor/sha2/Cargo.toml",
                    "runs/native_system_manifest_readiness.json",
                ]
            )
        implementation_flags.append(
            {
                "id": flag_id,
                "class": flag_class,
                "status": "closed"
                if flag_class == "SUPERSEDED"
                or flag_id in {"FLAG-N0-RATIFICATION-SCOPE-001", "FLAG-N2-CPUID-001", "FLAG-N4-PROFILE-001", "FLAG-N4-IPC-MODEL-001", "FLAG-N4-SCHEDULER-MODEL-001", "FLAG-N4-POOLEFS-MODEL-001", "FLAG-N5-POOLEBOOT-PROOF-001", "FLAG-N5-BOOTPROTO-001", "FLAG-N5-BOOTCFG-001", "FLAG-N5-ELF-001", "FLAG-N5-KLOAD-001", "FLAG-N5-MANIFEST-001", "FLAG-N5-PBP1-LIVE-001", "FLAG-N5-KMAP-001", "FLAG-N6-KENTRY-001"}
                else "open",
                "phase_id": phase_id,
                "closure_condition": closure,
                "evidence": evidence,
            }
        )

    return {
        "schema_version": "1.0",
        "artifact_kind": "pdc_production_roadmap",
        "status_date": status_date,
        "objective": "Deliver production-ready native PooleOS as an original PooleBoot plus PooleKernel microkernel system and reproducible signed UEFI bootable ISO while developing PooleGlyph machine language in tandem through independently verified source, Core IR, PGB2, PGVM2, host-ABI, policy, compatibility, and IP-boundary gates, alongside canonical PDC, isolated drivers, guarded backends, and accessible PooleGlass Liquid Glass UI.",
        "production_ready": False,
        "architecture": {
            "mode": "native_capability_microkernel",
            "bootloader": "PooleBoot",
            "kernel": "PooleKernel",
            "production_base": "original_pooleos",
            "forbidden_production_substitutes": ["Linux", "Debian", "Buildroot", "GRUB", "Limine", "systemd"],
            "development_only_inputs": ["Windows", "WSL", "Linux", "Buildroot", "QEMU", "OVMF", "EDK II"],
            "target_architecture": "x86_64",
            "firmware_interface": "UEFI",
            "legacy_bios_required": False,
            "production_kernel_modules_v1": False,
            "completion_phase_range": "N0-N39",
        },
        "goal_charter": {
            "version": "2.0.0-native-reset",
            "path": "docs/production-goal-charter.md",
            "status": "adopted",
            "completion_phase_range": "N0-N39",
        },
        "execution_protocol": {
            "updates_required_each_goal_turn": True,
            "inspect_live_pooleglyph_each_turn": True,
            "verify_master_checklist_coverage_each_turn": True,
            "new_work_must_be_flagged": True,
            "last_updated_cycle": 105,
            "selected_move_id": "N5-KMAP-001",
            "immediate_next_move_id": "N0-HW-KEY-ACQUIRE-001",
            "owner_independent_next_move_id": "N5-HANDOFF-001",
            "required_records": [
                "docs/production-goal-charter.md",
                "docs/pdc-production-build-plan.md",
                "runs/pdc_production_roadmap.json",
                "runs/pooleos_native_checklist_coverage.json",
                "runs/native_toolchain_qualification.json",
                "runs/adr_ratification_readiness.json",
                "runs/n0_owner_decision_packet.json",
                "runs/n0_owner_response_receipt.json",
                "runs/hardware_target_readiness.json",
                "runs/native_tier0_readiness.json",
                "runs/native_model_readiness.json",
                "runs/native_pooleboot_readiness.json",
                "runs/native_boot_handoff_readiness.json",
                "runs/native_boot_config_readiness.json",
                "runs/native_elf_loader_readiness.json",
                "runs/native_kernel_entry_readiness.json",
                "runs/native_kernel_load_readiness.json",
                "runs/native_system_manifest_readiness.json",
                "runs/native_v1_objectives_readiness.json",
                "runs/release_gate.json",
                "docs/cycle_log.md",
                "README.md",
            ],
            "flag_classes": ["STOP_SHIP", "BLOCKER", "REQUIRED", "RISK", "RESEARCH", "OPTIONAL", "DEFERRED", "SUPERSEDED"],
        },
        "master_checklist": {
            "source_path": coverage["source"]["path"],
            "source_sha256": coverage["source"]["sha256"],
            "source_byte_count": coverage["source"]["byte_count"],
            "source_line_count": coverage["source"]["line_count"],
            "checkbox_line_count": coverage["source"]["checkbox_line_count"],
            "implementation_item_count": coverage["source"]["declared_generated_implementation_item_count"],
            "section_count": coverage["source"]["top_level_section_count"],
            "coverage_path": "runs/pooleos_native_checklist_coverage.json",
            "coverage_sha256": sha256_file(COVERAGE_PATH),
            "coverage_status": coverage["status"],
            "added_requirement_count": len(coverage["added_requirements"]),
        },
        "baseline": {
            "pooleos_cycle": 105,
            "entry_cycle": 79,
            "pooleos_test_count": test_count,
            "historical_consistency_release_gate": {
                "passed_checks": archived["baseline"]["release_gate"]["passed_checks"],
                "total_checks": archived["baseline"]["release_gate"]["total_checks"],
                "artifact_count": archived["baseline"]["release_gate"]["artifact_count"],
                "explicit_gap_count": archived["baseline"]["release_gate"]["explicit_gap_count"],
                "production_ready": False,
                "native_promotion_role": "historical_non_promoting",
            },
            "native_consistency_release_gate": {
                "passed_checks": 76,
                "total_checks": 76,
                "artifact_count": 71,
                "explicit_gap_count": len(PROGRAM_GAPS),
                "production_ready": False,
                "native_promotion_role": "planning_and_evidence_consistency_non_promoting",
            },
            "native": {
                "source_controlled": True,
                "pooleboot_exists": True,
                "poolekernel_exists": True,
                "native_qemu_boot": False,
                "native_physical_boot": False,
                "ring3_execution": False,
                "capability_enforcement": False,
                "iommu_driver_confinement": False,
                "native_filesystem": False,
                "native_desktop": False,
                "reproducible_signed_iso": False,
            },
            "pooleglyph": archived["baseline"]["pooleglyph"],
            "pdc": pdc_baseline,
        },
        "source_set": source_set,
        "phase_summary": {
            "total": len(phases),
            "complete": status_counts["complete"],
            "partial": status_counts["partial"],
            "blocked": status_counts["blocked"],
            "not_started": status_counts["not_started"],
            "subphase_total": sum(len(phase["subphases"]) for phase in phases),
        },
        "phases": phases,
        "implementation_flags": implementation_flags,
        "gap_summary": {
            "native_program_gap_count": len(PROGRAM_GAPS),
            "native_program_gaps": PROGRAM_GAPS,
            "historical_release_gate_gap_count": archived["baseline"]["release_gate"]["explicit_gap_count"],
            "historical_release_gaps_are_non_promoting": True,
        },
        "immediate_next_move": {
            "id": "N0-HW-KEY-ACQUIRE-001",
            "phase_ids": ["N0", "N1"],
            "title": "Obtain the selected compatible FIDO2 hardware key before any separately approved governance-key generation or registration",
            "entry_evidence": ["specs/n0-owner-response.json", "runs/n0_owner_response_receipt.json", "runs/adr_ratification_readiness.json", "docs/adr-ratification-ceremony.md"],
            "exit_evidence": ["owner confirms possession of a compatible FIDO2 hardware key", "separate explicit approval for governance-key generation or use", "owner-presence and recovery-custody procedure reviewed before execution"],
            "blocked": True,
        },
        "claim_boundaries": [
            "Buildroot and Linux artifacts are historical reference evidence and cannot satisfy native PooleOS gates.",
            "Checklist mapping is not implementation completion.",
            "Host simulations and schemas are not native kernel enforcement.",
            "Four paused q35/QMP instantiations prove host-side profile construction only; no guest CPU instruction, native media, boot, driver, Secure Boot, or formal-model claim follows.",
            "The six TLC state models cover all seven required domains only for their frozen finite constants: they are not theorem proofs, liveness checks, refinement proofs, fingerprint-collision guarantees, implementation-trace comparisons, ABI-freeze authority, hardware-durability evidence, or PooleKernel/PooleFS execution evidence.",
            "The Cycle 97 PooleBoot receipt proves one unsigned bounded UEFI application, deterministic development media, two pinned OVMF executions, ordered diagnostics, and exact static GOP frames; it does not prove the complete loader, a frozen handoff, PooleKernel loading or execution, ExitBootServices, Secure Boot, measured boot, signatures, target firmware, physical media, N5 exit, or production readiness.",
            "The Cycle 98 PBP1 receipt proves canonical synthetic bytes, no_std Rust and independent Python decoding, bounded downgrade and malformed controls, and finite differential agreement; it does not prove live PooleBoot population, ExitBootServices, PooleKernel consumption or execution, ABI ratification, target firmware, or N5 exit.",
            "The Cycle 99 PBC1 receipt proves a bounded candidate grammar, allocation-free no_std Rust parsing, an independent Python oracle, root-confined synthetic paths, named hostile controls, and finite differential agreement; it does not prove live firmware file I/O, trusted entry selection, artifact verification/loading, ABI ratification, target firmware, or N5 exit.",
            "The Cycle 100 PKELF1 receipt proves bounded synthetic ELF64 validation/loading, exact segment/BSS/relative-relocation bytes, a post-relocation W^X plan, named hostile controls, and finite Rust/Python differential agreement; it does not prove live firmware file I/O, signed-manifest authentication, firmware allocation, installed page tables, a functional PooleKernel image, ExitBootServices, kernel transfer or execution, ABI ratification, target firmware, physical media, or N5 exit.",
            "The Cycle 101 PKENTRY1 receipt proves a real reproducible PooleKernel product image, allocation-free candidate PBP1 intake helpers, bounded static diagnostics, deterministic panic classes, hostile linked/canonical rejection, and exact Rust/Python loaded bytes; it does not prove a live PooleBoot caller, ExitBootServices, installed mappings or W^X, privileged diagnostics execution, descriptor/exception setup, kernel runtime, target firmware, N6 exit, or production readiness.",
            "The Cycle 102 PKLOAD1 receipt proves exact live UEFI PBC1 and PKELF1 reads, firmware-page allocation, segment/BSS/relative-relocation materialization, a W^X mapping plan, complete load-then-release cleanup, and two-run guest/oracle agreement; it does not prove manifest-driven authentication, retained pages, installed page tables, PBP1 production, ExitBootServices, kernel entry, target firmware, N5 exit, or production readiness.",
            "The Cycle 103 PSM1/PKLOAD2 receipts prove canonical bounded unsigned manifest parsing, manifest-selected slot/version/path/file/image/entry binding, SHA-256 agreement against the selected kernel bytes, firmware-page load then release, nineteen ordered markers, and finite independent/hostile agreement; they do not prove manifest signature trust, provider security review, persistent rollback state, retained mappings, live PBP1 production, ExitBootServices, kernel entry, target firmware, N5 exit, or production readiness.",
            "The Cycle 104 PKLOAD3/PooleBoot4 receipts prove stride-aware normalization of a live UEFI memory map, exact temporary pre-exit PBP1 production and dual-channel reconstruction, cross-binding to PBC1, PSM1, the live kernel allocation and digest, GOP, bounded lifetime recheck, and complete release; they do not prove retained handoff storage or kernel pages, installed or activated page tables, final ExitBootServices map capture, successful ExitBootServices, kernel consumption or transfer, target firmware, N5 exit, or production readiness.",
            "The Cycle 105 PKLOAD4/PooleBoot5 receipts prove exact supervisor 4 KiB higher-half leaves for the complete 48-page PooleKernel image, CR0.WP and NX prerequisites, W^X, temporary candidate CR3 activation, full alias hashing, framebuffer translation and cache-bit preservation, zero firmware calls while active, exact original-CR3 restoration, and four-table-page cleanup; they do not prove retained page tables, retained kernel or handoff pages, final framebuffer cache policy, final ExitBootServices map capture, successful ExitBootServices, kernel consumption or transfer, target firmware, N5 exit, or production readiness.",
            "Sixteen allowlisted user-mode CPUID records prove only a bounded host observation; they do not prove MSR access, privileged probes, native parsing, driver safety, or Tier 1 qualification.",
            "Owner-directed acceptance of thirty-eight objective definitions while binding zero measurements is not a cryptographic signature or implementation evidence.",
            "PooleGlyph Phase 65 proves a metadata, parser, AST, and diagnostic foundation only; no source form, Core IR, PGASM, PGB2, PGVM2, host call, policy, optimization, or version label is promoted without its own frozen contract and evidence gate.",
            "Private PooleGlyph or PooleMath optimization evidence cannot replace the public-safe reference path, independent semantic/effect/authority differentials, or PooleOS capability enforcement.",
            "Finite PDC/QP evidence remains bounded to its declared classical models and protocols.",
            "A file named ISO is not reproducible signed clean-media boot evidence.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "runs/pdc_production_roadmap.json")
    parser.add_argument("--test-count", type=int, default=581)
    parser.add_argument("--status-date", default="2026-07-17")
    args = parser.parse_args()
    roadmap = make_roadmap(args.test_count, args.status_date)
    args.out.write_text(json.dumps(roadmap, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")
    print(
        f"wrote {args.out}: phases={roadmap['phase_summary']['total']} "
        f"subphases={roadmap['phase_summary']['subphase_total']} "
        f"gaps={roadmap['gap_summary']['native_program_gap_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
