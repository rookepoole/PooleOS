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
    "N5.6": "partial",
    "N5.7": "partial",
    "N5.8": "partial",
    "N5.9": "partial",
    "N6.4": "partial",
    "N6.5": "partial",
    "N6.6": "partial",
    "N7.1": "partial",
    "N7.2": "partial",
    "N7.3": "partial",
    "N7.4": "partial",
    "N7.5": "partial",
    "N7.6": "partial",
    "N9.1": "partial",
    "N9.2": "partial",
    "N9.3": "partial",
    "N9.4": "partial",
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
        "Cycle 118 current owner authorization: compatible FIDO2-key acquisition, key generation/use, public-key publication, signing, secrets use, privileged probes, driver loading, firmware changes, physical-media writes, tag/release publication, and production promotion are approved as operation categories; the selected key remains physically unavailable, no newly authorized operation was performed, and charter qualification, owner-presence, backup, recovery, safe-target, and exact-release gates still control execution",
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
        "specs/native-pooleboot-proof.json: POOLEOS-N5-POOLEBOOT-7 bounded unsigned aggregate contract across N5.1-N5.9",
        "native/boot: Poole-authored no_std PE32+ UEFI application with reviewed firmware bindings, live bounded filesystem/config/kernel/PBART1/PBTP1/PBTS1 intake, exact retained-page inner parsing, GOP identity, retained PKMAP2 kernel/six-artifact/PSM1/trust-policy/trust-state/table/guarded-stack/handoff storage, final PBLIVE3 production, bounded PBEXIT1 retry, successful ExitBootServices, direct post-exit serial/debugcon diagnostics, a default permanent stop, and a separately feature-gated QEMU-only one-way development transfer",
        "native/artifact, runtime/native_boot_artifact.py, and docs/native-initial-system-profile.md: PBART1 fixed envelope, exact PBASET1 seven-role development profile, independent parser/oracle, role/version/payload/whole-file digest boundaries, and explicit no-authentication/no-activation contract",
        "specs/native-initial-system-contract.json and docs/native-initial-system-bundle.md: PINIT1 deterministic component, service, dependency, abstract-resource, attenuated-capability, lifecycle, transaction, rollback, and activation-separation contract",
        "native/initsys and runtime/native_initial_system.py: allocation-free no_std Rust validator plus independent Python encoder/oracle with declarations that cannot confer kernel authority",
        "runs/native_initial_system_readiness.json: 3/3 Rust tests, 2/2 no_std target builds, 3/3 golden vectors, 120/120 parser and activation controls, mandatory unsigned-development activation denial, and 16,384 Rust/Python differential cases with zero mismatches",
        "specs/native-recovery-contract.json and docs/native-recovery-bundle.md: PREC1 immutable recovery policy, separately mutable boot-attempt state, exact A/B eligibility and known-good fallback, failure routing, authority separation, activation preconditions, and recovery-loop bounds",
        "native/recovery and runtime/native_recovery.py: allocation-free no_std Rust validator and transition engine plus independent Python encoder, parser, state machine, receipt validator, and activation oracle",
        "runs/native_recovery_readiness.json: 3/3 Rust tests, 2/2 no_std target builds, 3/3 golden policy/state/transition vectors, 144/144 controls, 16,384 parser/state and 8,192 transition differential cases with zero mismatches, and mandatory development activation denial",
        "specs/native-symbol-contract.json and docs/native-symbol-bundle.md: PSYM1 deterministic public diagnostic index, exact stripped/loaded/build/debug/source identity chain, image-relative address model, KASLR-base input, public-name and pointer-redaction policy, bounded lookup, and target-consumption preconditions",
        "native/symbols and runtime/native_symbols.py: allocation-free no_std Rust parser/lookup implementation plus independent Python encoder, parser, debug-ELF inspector, lookup oracle, and consumption gate",
        "runs/native_symbol_readiness.json: 4/4 Rust tests, 2/2 no_std targets, 3/3 golden vectors, 158/158 controls, 16,384 parser and 16,384 lookup differential cases, two reproducible split-debug builds, exact three-symbol public extraction, zero mismatches, and mandatory development-consumption denial",
        "specs/native-microcode-contract.json and docs/native-microcode-bundle.md: PMCU1 deterministic wrapper around opaque vendor-authenticated bytes, exact AuthenticAMD and CPUID 0x00B40F40 targeting, revision and authenticated-floor selection, reset-based known-good recovery, BSP/AP timing, mixed-revision failure, post-apply verification, and explicit no-authority boundaries",
        "native/microcode and runtime/native_microcode.py: allocation-free no_std Rust parser and selection/apply-plan/post-verify model plus independent Python encoder, parser, policy oracle, activation gate, and host differential harness",
        "runs/native_microcode_readiness.json: 4/4 Rust tests, 2/2 no_std targets, 3/3 golden vectors, 174/174 controls, 16,384 parser, 16,384 selection, and 8,192 post-apply differential cases with zero mismatches, 35 synthetic never-apply payloads, mandatory development activation denial, and zero production vendor payloads",
        "specs/native-firmware-contract.json and docs/native-firmware-manifest.md: PFWM1 synthetic qualification manifest with exact resource, hardware-instance, version-floor, signer, updater-plugin, payload-identity, dependency, recovery, dry-run authority, and post-reset receipt semantics",
        "native/firmware and runtime/native_firmware.py: allocation-free no_std Rust parser and policy model plus independent Python encoder, parser, dry-run authorization, post-reset receipt validator, and differential harness",
        "runs/native_firmware_readiness.json: 5/5 Rust tests, 2/2 no_std targets, 3/3 golden vectors, 101/101 controls, 16,384 parser, 8,192 activation, and 8,192 post-reset differential cases with zero mismatches, zero embedded payloads, mandatory development activation denial, and zero live inventory or apply authority",
        "specs/native-policy-contract.json and docs/native-policy-bundle.md: PPOL1 bounded role-7 policy with six exact boot modes, default deny, authority intersection, PINIT1 capability-route cross-binding, safe/recovery floors, firmware physical-presence separation, and durable decision-receipt semantics",
        "native/policy and runtime/native_policy.py: allocation-free no_std Rust parser and policy model plus independent Python encoder, parser, activation oracle, receipt validator, and differential harness",
        "runs/native_policy_readiness.json: 6/6 Rust tests, 2/2 no_std targets, 3/3 golden vectors, 116/116 controls, 8,192 parser, 4,096 cross-binding, 12,288 activation, and 8,192 receipt differential cases with zero mismatches, mandatory development activation denial, zero live enforcement, and zero authority creation",
        "native/inner, runtime/native_inner_live.py, and tests/test_native_inner_live.py: allocation-free no_std six-format retained-set validator plus independent Python oracle, exact PPOL1 payload-digest and PINIT1 route cross-binding, six mandatory development denials, a domain-separated retained-set digest, and explicit zero authority/action/state/hardware effects",
        "specs/native-boot-trust-contract.json and docs/native-boot-trust.md: PBTRUST1 separates immutable PBTP1 trust policy, mutable PBTS1 acceptance state, and PREC1 boot-attempt state; PBSTATE1 freezes authenticated-anchor, logical-digest, redundant-selection, repair/migration-plan, power-loss, denial-order, and no-authority boundaries",
        "native/trust and runtime/native_boot_trust.py: allocation-free no_std Rust parser/authorization/backend model plus independent Python encoder, parser, authorization, backend-selection, and deterministic recovery oracles",
        "runs/native_boot_trust_readiness.json: 12/12 Rust tests, both no_std targets, one PooleBoot UEFI integration build, 105/105 controls, 32,768 Rust/Python differential cases, nine interrupted-transition recovery cases, fourteen live bindings, mandatory unsigned-policy denial, zero signature verification, authority grants, backend I/O, anchor writes, and state writes, and explicit rejection of the ESP state candidate as persistent authority",
        "runtime/native_kernel_load.py and tools/qualify_native_kernel_load.py: deterministic 64 MiB protective-MBR/GPT/FAT32 ordinary-file media with exact fallback EFI, PBC1 config, PSM1 system manifest, PKELF1 PooleKernel, six PBART1 artifacts, PBTP1/PBTS1 development candidates, exact retained-page inner-set reconstruction, and no physical-media output mode",
        "runs/native_pooleboot_readiness.json: 8/8 host tests, 2/2 exact PooleBoot PE builds, 2/2 exact twelve-file media generations, 2/2 exact QEMU/OVMF runs, twenty-five ordered markers, 2/2 serial/debugcon matches, 2/2 exact GOP frames, and 155/155 integrated hostile controls with exact nine-file retained-set and PBTRUST1 denial binding",
        "docs/native-pooleboot-proof.md: reproduction procedure, observed firmware boundary, hostile corpus, exact evidence, and N5 nonclaims",
        "specs/native-boot-handoff-contract.json and docs/native-boot-handoff.md: canonical PBP1 little-endian header, descriptors, twelve typed records, x86-64 transfer state, ownership/lifetime rules, version negotiation, and explicit nonclaims",
        "native/handoff and runtime/native_boot_handoff.py: dependency-free no_std Rust codec plus independently implemented Python host oracle",
        "runs/native_boot_handoff_readiness.json: 8/8 Rust tests, 2/2 no_std target builds, twelve layout assertions, 3/3 golden vectors, 32/32 hostile controls, and 16,384 Rust/Python differential cases with zero mismatches; PKLOAD6 separately proves a retained post-exit development producer",
        "native/livehandoff, native/boot/src/livehandoff.rs, and runtime/native_live_boot_handoff.py: allocation-free canonical PBP1 assembly from stride-aware UEFI descriptors, final-map kernel/root/guarded-stack/handoff/GOP bindings, retained loader-range validation, and independent transcript reconstruction",
        "specs/native-boot-config-contract.json and docs/native-boot-config.md: canonical bounded PBC1 text grammar, fail-closed version policy, five boot modes, root-confined UEFI paths, artifact-size bounds, and explicit live-I/O nonclaims",
        "native/bootcfg and runtime/native_boot_config.py: allocation-free dependency-free no_std Rust parser plus independently implemented Python host oracle; PooleBoot has a compile-time path dependency but no live file read",
        "runs/native_boot_config_readiness.json: 12/12 Rust tests, 2/2 no_std parser builds, 2/2 PooleBoot integration builds, 3/3 golden vectors, 64/64 hostile controls, and 16,384 Rust/Python differential cases with zero mismatches",
        "specs/native-elf-loader-contract.json and docs/native-elf-loader.md: bounded PKELF1 ELF64 ET_DYN profile, three canonical load segments, relative relocations, transactional mutation rule, W^X map plan, and explicit firmware/paging/transfer nonclaims",
        "native/elf and runtime/native_elf_loader.py: dependency-free no_std Rust inspector/loader plus an independently implemented Python host oracle; PooleBoot has a compile-time dependency but performs no live file read, allocation, mapping, or transfer",
        "runs/native_elf_loader_readiness.json: 12/12 Rust tests, 2/2 no_std target builds, 2/2 PooleBoot integration builds, 3/3 exact loaded-byte vectors, 129/129 hostile controls, and 16,384 Rust/Python differential cases with zero mismatches",
        "specs/native-system-manifest-contract.json and docs/native-system-manifest.md: canonical bounded PSM1 grammar, exact artifact/slot/version/path/size/SHA-256/entry binding, independent parser, and explicit unsigned trust boundary",
        "native/manifest and runtime/native_system_manifest.py: allocation-free no_std Rust parser and SHA-256 provider integration plus an independently implemented Python oracle",
        "runs/native_system_manifest_readiness.json: 8/8 Rust tests, 2/2 no_std target builds, one PooleBoot integration build, 3/3 golden vectors, 64/64 hostile controls, 16,384 differential cases, and 1,027 SHA-256 agreement cases with zero mismatches",
        "specs/native-kernel-load-contract.json and docs/native-kernel-load.md: PKLOAD6 freezes live UEFI intake, PSM1/PBART1 digest binding, exact PBASET1 plus PSM1/PBTP1/PBTS1 loading and retention, six-format retained-page parsing and denial, PBTRUST1 policy/state candidate parsing, fourteen cross-bindings and exact unsigned-policy denial, retained PKMAP2 storage, final ten-role PBLIVE3 production, bounded PBEXIT1 retry, successful ExitBootServices, stop-before-transfer, trust, semantics, and nonclaim boundaries",
        "native/bootload, native/inner, native/trust, native/boot/src/kload.rs, native/boot/src/kmap.rs, native/boot/src/exit.rs, native/bootexit, runtime/native_inner_live.py, runtime/native_boot_trust.py, and runtime/native_kernel_load.py: dependency-free contracts, reviewed raw UEFI adapters, and independent retained-set/trust/media/map/exit oracle implementation",
        "specs/native-kernel-map-contract.json, native/kmap, runtime/native_kernel_map.py, and docs/native-kernel-map.md: PKMAP2 exact 64-page 4 KiB supervisor kernel mapping, guarded stack, read-only handoff, W^X/WP/NX, active-root audit, framebuffer preservation, ten-role retained allocation coverage, and nonclaim contract",
        "specs/native-boot-exit-contract.json, native/bootexit, runtime/native_boot_exit.py, and docs/native-boot-exit.md: PBEXIT1 final-map, current-key, bounded stale-key retry, no-post-attempt-service, no-post-exit-firmware, and permanent pre-transfer-stop contract",
        "runs/native_kernel_load_readiness.json: 151/151 Rust host tests, 2/2 exact PooleBoot builds, 2/2 exact PooleKernel builds, 2/2 exact twelve-file media generations, 2/2 QEMU/OVMF runs, 25 ordered markers, 155/155 integrated hostile controls, exact retained PINIT1, PREC1, PSYM1, PMCU1, PFWM1, and PPOL1 parsing with payload/route cross-binding and mandatory development denial, exact retained PSM1/PBTP1/PBTS1 parsing with fourteen trust cross-bindings and unsigned-policy denial, two exact post-exit ten-role PBP1 reconstructions, exact 64-page kernel plus nine retained files/table/14-page guarded-stack/handoff range agreement, successful ExitBootServices, zero later firmware calls, and exact guest/oracle agreement",
        "specs/native-kernel-revalidation-contract.json and docs/native-kernel-revalidation.md: PKREVAL1 freezes independent allocation-free no_std PooleKernel reparsing of exact retained PSM1, six PBART1 inner files, PBTP1, and PBTS1 bytes before authority, with exact role/order/range/digest/binding/denial requirements and standalone-execution nonclaims",
        "native/kernel/src/revalidation.rs, native/kernel/src/bin/pkreval1_probe.rs, runtime/native_kernel_revalidation.py, and tests/test_native_kernel_revalidation.py: independent kernel-side verifier, host probe, Python oracle, loader-summary substitution controls, post-load mutation controls, and deterministic role-complete differential campaign",
        "runs/native-kernel-revalidation-readiness.json: 66/66 Rust tests, 8/8 Python tests, both no_std target builds, nine exact retained files and parsers, 36/36 hostile controls, 32,768/32,768 deterministic mutation rejects, exact unsigned-policy denial, zero authority grants/actions/state writes, and no standalone live-entry claim",
        "specs/native-kernel-transfer-contract.json, runtime/native_kernel_transfer.py, tools/qualify_native_kernel_transfer.py, tests/test_native_kernel_transfer.py, and docs/native-kernel-transfer.md: PKXFER1 freezes an opt-in QEMU-only one-way transfer while preserving the default stop-before-transfer build",
        "runs/native-kernel-transfer-readiness.json: 2/2 exact PooleKernel builds, 2/2 feature-enabled PooleBoot builds plus one default isolation build, 2/2 exact media generations and fresh-vars QEMU/OVMF runs, 30 ordered markers, exact serial/debugcon and PBP1 agreement, 58/58 hostile controls, live nine-file PKREVAL1 execution, and terminal unsigned denial with zero authority, actions, writes, signatures, or post-exit firmware calls",
    ],
    "N6": [
        "specs/native-kernel-entry-contract.json and docs/native-kernel-entry.md: PKENTRY1 transfer, mapping, diagnostic, panic, build, and explicit nonclaim boundary",
        "native/kernel: real freestanding PooleKernel product with fixed entry assembly, allocation-free PBP1 intake and PKREVAL1 retained-byte verifier, static early ring, bounded COM1 candidate, optional volatile framebuffer sink, and terminal panic path",
        "runtime/native_kernel_image.py: fail-closed pinned-LLD input validation and deterministic PKELF1 canonicalization",
        "runs/native_kernel_entry_readiness.json: 66/66 host tests, 2/2 exact clean linked and canonical builds, 43/43 hostile controls, 221,184 canonical bytes in a 262,144-byte image, entry offset 0x8000, 525 relative relocations, exact independent Rust/Python loaded bytes, and canonical SHA-256 5533347F0DA41B0F08B4E0ADF643379706BE548B5486D49C57960FEFE799FE93",
        "specs/native-boot-digest-provider.json: PBDIGEST1 pins vendored RustCrypto sha2 0.11.0, the soft-compact UEFI backend, locked transitive packages, and reproducible /pooleos/native source-path remapping while retaining independent security review and provider promotion as open",
        "ADD-BOOT-003: boot-time digest-provider pinning, reproducible path remapping, qualification, independent review, and target-backend promotion boundary",
        "ADD-KERNEL-001: explicit temporary framebuffer identity mapping, cache-policy preservation, lifetime, replacement, and revocation dependency",
    ],
    "N7": [
        "specs/native-kernel-trap-contract.json and docs/native-kernel-trap.md: PKTRAP1 freezes a BSP-only QEMU development boundary for GDT/TSS/IDT installation, uniform integer trap frames, three deliberate returning exceptions, terminal double-fault containment, and explicit semantic malformed-frame rejection",
        "native/kernel/src/arch/x86_64.rs and native/kernel/src/main.rs: five-entry BSP GDT, 104-byte TSS, 256-entry IDT allocation with five present gates, distinct 8192-byte IST1/IST2 arrays, 176-byte normalized frame, descriptor/control-state readback, exact deliberate origins, and terminal fail-closed handlers",
        "runs/native-kernel-trap-readiness.json: 3 scenarios, 6 fresh-vars QEMU/OVMF runs, exact per-scenario serial/debugcon markers, screenshots, and PBP1 bytes, 3 returning exceptions, 1 terminal processor-delivered double fault, 1 semantic malformed-frame rejection, and 51/51 hostile controls with zero authority or effects",
        "specs/native-kernel-cpu-policy-contract.json and docs/native-kernel-cpu-policy.md: PKCPU1 freezes a bounded BSP-only, read-only QEMU policy for required CPUID leaves and features, CR0/CR4/EFER state, XCR0, APIC/PAT/MTRR MSRs, topology, address widths, and explicit no-write/no-authority boundaries",
        "native/kernel/src/arch/x86_64.rs, native/kernel/src/lib.rs, and native/kernel/src/main.rs: support-gated CPUID, control-register, XGETBV, and RDMSR observation plus allocation-free policy validation and an opt-in selector-4 terminal development profile",
        "runs/native-kernel-cpu-policy-readiness.json: 31/31 kernel host tests, 2 exact fresh-vars qemu64 QEMU/OVMF runs, 35 ordered markers, 41/41 hostile controls, exact Rust/Python agreement, AuthenticAMD family 15 model 107 stepping 1 observation, 5 MSR reads, zero MSR writes, and zero authority or actions",
        "specs/native-kernel-errata-policy-contract.json and docs/native-kernel-errata-policy.md: PKERR1 freezes exact Ryzen 7 9800X3D identity, mandatory features, board-lineage-specific BIOS floors, AMD-SB-7033 and AMD-SB-7055 AGESA floors, RDSEED policy, source applicability, and explicit no-authority boundaries",
        "native/cpupolicy and runtime/native_kernel_errata_policy.py: independent allocation-free no_std Rust and Python pure-policy evaluators with ten fail-closed reason bits and no privileged or mutating path",
        "runs/native-kernel-errata-policy-readiness.json: 6/6 Rust tests, both no_std targets, 128 cross-language vectors, 24/24 hostile controls, seven exact source records, homogeneous 16-record read-only Windows metadata, and exact six-reason current denial with zero privileged reads, writes, authority, or actions",
        "specs/native-kernel-xstate-policy-contract.json and docs/native-kernel-xstate-policy.md: PKXSTATE1 freezes eager standard-format x87/SSE ownership, XCR0 0x3, XSS zero, 4,096-byte aligned images, canonical FCW/MXCSR state, context-switch preconditions, sensitive-image clearing, and kernel-SIMD prohibition",
        "runs/native-kernel-xstate-policy-readiness.json: 31/31 kernel host tests, two exact fresh-vars EPYC-Rome-v4 x87/SSE QEMU/OVMF runs, 35 markers, 43/43 hostile controls, two context saves, four restores, 8,192 cleared image bytes, three bounded control writes, zero authority, and explicit scheduler/SMP/target nonclaims",
        "specs/native-kernel-xstate-exception-contract.json and docs/native-kernel-xstate-exception.md: PKXEXC1 freezes deliberate #MF/#XM delivery and exact recovery plus terminal test-only #NM eager-policy rejection under a hardware-accelerated one-BSP development boundary",
        "runs/native-kernel-xstate-exception-readiness.json: two exact fresh-vars WHPX QEMU/OVMF runs, one expected TCG limitation probe, 41 markers, 43/43 hostile controls, three processor-delivered exceptions, two exact recoveries, one terminal #NM rejection, linked machine-code scope audit, four bounded configuration writes, two recovery writes, zero authority, and explicit scheduler/SMP/target nonclaims",
        "specs/native-kernel-privilege-msr-policy-contract.json and docs/native-kernel-privilege-msr-policy.md: PKMSR1 freezes a read-only qemu64 BSP policy for system-linkage, FS/GS, support-gated TSC_AUX, global machine-check, and unsupported-PMU state without activation",
        "runs/native-kernel-privilege-msr-policy-readiness.json: two exact fresh-vars TCG QEMU/OVMF runs, 35 markers, 47/47 hostile controls, 11 support-gated MSR reads, ten observed MCA banks, zero bank reads, zero writes, linked no-WRMSR audit, zero authority, and explicit emulator/target/production nonclaims",
    ],
    "N9": [
        "specs/native-kernel-physical-memory-contract.json, specs/native-kernel-physical-memory-contract.schema.json, and docs/native-kernel-physical-memory.md: PKPMM1 freezes exact PBP1 intake, UEFI source-kind validation, usable-only initial ownership, held reclaim classes, page-zero exclusion, DMA/DMA32/Normal zones, generation-safe handles, quotas, poisoning, and coalescing without mapping, reclaim, concurrency, or production claims",
        "native/kernel/src/physical_memory.rs, runtime/native_kernel_physical_memory.py, tools/qualify_native_kernel_physical_memory.py, and tests/test_native_kernel_physical_memory.py: allocation-free no_std kernel allocator, independent transcript/oracle validation, source audit, PBP1 substitution controls, and bounded deterministic allocate/free exercise",
        "runs/native-kernel-physical-memory-readiness.json: 2/2 exact qemu64 QEMU/OVMF runs, 40 ordered markers, 48/48 hostile controls, 97 PBP1 memory entries, 117,925 usable source pages, 117,924 managed pages after page-zero exclusion, 11,250 boot-reclaimable pages held, 819 retained loader pages protected, four allocator operations, and zero physical writes, mappings, reclaim, signatures, authority, or actions",
        "specs/native-kernel-virtual-memory-contract.json and docs/native-kernel-virtual-memory.md: PKVM2 freezes the 48-bit candidate-root layout, exact inherited kernel/entry/guarded-stack/handoff mappings, bounded nine-page direct map, CR3 activation/rollback, architectural Accessed/Dirty handling, local invalidation receipts, and release ordering",
        "native/kernel/src/active_virtual_memory.rs, native/kernel/src/main.rs, runtime/native_kernel_virtual_memory.py, tools/qualify_native_kernel_virtual_memory.py, and tests/test_native_kernel_virtual_memory.py: fixed-capacity no_std active-root core, privileged volatile CR3/INVLPG adapter, independent PBP1 first-fit oracle, source audit, host rollback/fault tests, and bounded selector-10 evidence; the selector-9 PKVM1 inactive foundation remains its predecessor",
        "runs/native-kernel-virtual-memory-readiness.json: 2/2 exact qemu64 QEMU/OVMF runs, 40 ordered markers, 46/46 hostile controls, eight table pages and one data page, 8,720 physical table writes, 5,336 bootstrap temporary-PTE writes and invalidations, two CR3 writes, three active local invalidation receipts, exact original-root restoration and allocation release, zero shootdowns, and zero signatures, authority, or actions",
        "ADD-MEM-001: one cross-stage bootstrap stack, guard, root-table, handoff, kernel-image, and allocator-metadata boundary shared by PooleBoot, PBP1, PKMAP2, PooleKernel entry, trap handling, and PMM ownership",
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
    "N36": ["Cycle 127 host baseline: TEST_COUNT tests with one Windows symlink-permission skip", "native binary parser, reproduction, leakage, malformed, substitution, governance, hardware, Tier 0, bounded-model, deterministic boot-media, PBP1/PBC1/PSM1/PBART1, six inner-format, PBTRUST1/PBSTATE1, PKELF1, PKENTRY1, PKLOAD6/PBLIVE3/PKMAP2/PBEXIT1, PKREVAL1, PKXFER1, PKTRAP1, PKCPU1, PKERR1, PKXSTATE1, PKXEXC1, PKMSR1, PKPMM1, PKVM1, and PKVM2 policy/source/machine-code/zero-authority controls, PooleGlyph roadmap bindings, Doctor external-report nonmutation, and collector-smoke negatives"],
    "N37": ["Cycle 127 consistency release gate: 93/93 checks over 88 artifacts", "content-addressed source, objectives and governance receipts, native toolchain, bounded hardware/Tier 0/model evidence, PBTRUST1/PBSTATE1, bounded PooleBoot, PBP1/PBC1/PSM1/PBART1 and six inner formats, PKELF1, PKENTRY1, PKLOAD6/PKMAP2/PBEXIT1, PKREVAL1, PKXFER1, PKTRAP1, PKCPU1, PKERR1, PKXSTATE1, PKXEXC1, PKMSR1, PKPMM1, PKVM1, PKVM2, PooleGlyph planning artifacts, and retained historical consistency artifacts"],
}


PHASE_GAPS = {
    "N0": [
        "The completed response records exact owner direction for ADR-0003, ADR-0004, and all 38 objective definitions. Cycle 118 separately authorizes compatible-key acquisition, key generation/use, public-key publication, signing, secrets, privileged probes, drivers, firmware changes, physical-media writes, tags/releases, and production promotion, but the selected hardware-backed governance key is still physically unavailable; no key, signature, publication, privileged/mutating operation, release, or promotion has occurred, and all charter qualification and operation-safety gates remain mandatory",
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
    "N5": ["A reproducible unsigned PooleBoot, PBP1, PBC1, PSM1, PKELF1, PBART1, PINIT1, PREC1, PSYM1, PMCU1, PFWM1, PPOL1, PBTRUST1/PBSTATE1, PKMAP2, PBEXIT1, PKREVAL1, PKXFER1, and real PooleKernel path now loads and retains the exact six-artifact development profile plus exact PSM1/PBTP1/PBTS1 files and table/guarded-stack/handoff storage; reparses all six exact retained inner files in PooleBoot; cross-binds policy, routes, and trust candidates; binds final post-exit PBP1 bytes to the successful memory map; calls ExitBootServices; and proves zero later firmware calls. The ordinary build stops before transfer. A separate opt-in QEMU-only build installs retained CR3 and guarded RSP, clears IF/DF, transfers once into PooleKernel, independently reparses all nine retained files, reconstructs exact unsigned-policy denial, and halts with zero signatures, authority, actions, state writes, or firmware calls. Artifact authentication and authenticated rollback state, a real cryptographic monotonic writable provider, capability creation or activation, recovery execution, symbol consumption, policy application, real vendor-container validation and licensed payload intake, live FMP/ESRT/PLDM inventory, privileged per-processor revision observation, signature-backed trusted selection, initial-system execution, final framebuffer remap/revocation, live menu/rollback policy, a production transfer profile, second host, target firmware, physical media, and N5 exit remain open"],
    "N6": ["A reproducible real 64-page PooleKernel PKELF1 image, PKENTRY1 intake, allocation-free PKREVAL1 verifier, bounded diagnostics, an opt-in QEMU-only live transfer, and a BSP-only descriptor/exception development profile now exist on one host; authenticated boot trust, measured boot, production transfer, final framebuffer remap/revocation, complete per-CPU GDT/IDT/TSS state, retained crash paths, kernel runtime, target execution, and N6 exit remain open"],
    "N7": ["PKTRAP1 proves only one BSP descriptor/fault slice, PKCPU1 proves only a bounded qemu64 BSP read-only CPU snapshot, and PKERR1 freezes an exact-target rejection policy that correctly denies six current gaps. PKXSTATE1 proves bounded eager x87/SSE standard-XSAVE ownership and clearing; PKXEXC1 adds deliberate #MF/#XM delivery and exact bounded recovery, terminal test-only #NM eager-policy rejection, and a linked machine-code scope audit under WHPX on one BSP. PKMSR1 adds a read-only qemu64 BSP system-linkage/FS-GS/global-MCA/unsupported-PMU policy with eleven support-gated reads and zero activation. Exact board revision, stable firmware-image hash, an applicable AMD Family 1Ah Models 40h-4Fh errata guide or reviewed vendor-response disposition, a direct numeric client microcode floor or ratified replacement rule, native per-processor privileged revision evidence, target-specific privileged-MSR semantics, syscall and per-CPU activation transactions, machine-check delivery and recovery, supported PMU ownership, AVX and extended xstate, user-task exception delivery, scheduler integration, AP-local CPU state, CPU migration, complete descriptor/fault handling, target qualification, and the N7 exit gate remain open"],
    "N8": ["No native APIC/timer/SMP implementation exists"],
    "N9": ["PKPMM1 consumes the live PBP1 map and provides bounded generation-safe physical ownership. PKVM1 supplies inactive page-table transactions. PKVM2 adds a kernel-complete one-BSP candidate root, a bounded nine-page direct map, exact CR3 activation/restoration, architectural Accessed/Dirty handling, and three active local invalidation receipts. Page scrubbing, held-class reclaim, a complete generation-owned direct map, SMP TLB shootdown and deferred reclaim, huge pages, PCID, COW, user faults, pager IPC, heaps/object caches, MMIO/PAT/MTRR qualification, concurrent allocation, pressure/OOM policy, target hardware, and the N9 exit gate remain open"],
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
    ("FLAG-N0-GOVERNANCE-KEY-001", "BLOCKER", "N0", "Obtain a compatible FIDO2 hardware key, then execute the already authorized governance-key generation/use, public fingerprint review and publication, signer registration, and recovery custody under owner presence without exposing private material"),
    ("FLAG-NATIVE-BOOT-001", "STOP_SHIP", "N5", "Boot reproducible PooleBoot PE32+ and transfer through the frozen handoff"),
    ("FLAG-N5-POOLEBOOT-PROOF-001", "REQUIRED", "N5", "Reproduce the bounded unsigned PooleBoot PE32+ proof, deterministic GPT/FAT32 media, ordered dual-channel diagnostics, GOP frame, and hostile corpus without claiming the complete loader or N5 exit"),
    ("FLAG-N5-BOOTPROTO-001", "REQUIRED", "N5", "Qualify the canonical PBP1 byte schema with no_std codec, independent decoder, layout assertions, golden bytes, downgrade controls, malformed corpus, and deterministic differential fuzzing before loader or kernel entry code depends on it"),
    ("FLAG-N5-BOOTCFG-001", "REQUIRED", "N5", "Qualify the bounded PBC1 grammar with an allocation-free no_std parser, independent oracle, golden semantics, duplicate/unknown-key, traversal, range, truncation, version, capacity, artifact-size, and deterministic differential controls before live filesystem integration"),
    ("FLAG-N5-ELF-001", "REQUIRED", "N5", "Qualify the bounded PKELF1 ELF64 ET_DYN profile with allocation-free no_std inspection/loading, independent oracle, exact loaded bytes, transactional rejection, relocation, W^X planning, hostile controls, and deterministic differential evidence before live firmware integration"),
    ("FLAG-N5-KLOAD-001", "REQUIRED", "N5", "Qualify bounded live UEFI PBC1 and PKELF1 reads, exact firmware-page allocation, relocation, W^X mapping-plan validation, deterministic cleanup, guest/oracle agreement, and hostile controls without claiming authentication, installed mappings, transfer, or N5 exit"),
    ("FLAG-N5-MANIFEST-001", "REQUIRED", "N5", "Qualify canonical bounded PSM1 parsing, exact slot/version/path/size/digest/entry binding, manifest-driven live selection, artifact hashing, deterministic cleanup, independent agreement, and hostile controls without claiming signature trust, rollback persistence, transfer, or N5 exit"),
    ("FLAG-N5-PBP1-LIVE-001", "REQUIRED", "N5", "Qualify temporary pre-ExitBootServices PBP1 production from stride-aware firmware descriptors and exact config, manifest, kernel, and GOP bindings with bounded storage lifetime, cleanup, independent transcript reconstruction, hostile controls, and no retained-handoff or transfer claim"),
    ("FLAG-N5-KMAP-001", "REQUIRED", "N5", "Qualify exact supervisor 4 KiB higher-half kernel mappings through an active-root clone, W^X/WP/NX enforcement, framebuffer translation and cache preservation, candidate CR3 activation, complete alias audit, exact rollback, zero active-root firmware calls, and cleanup without retained-address-space, transfer, or N5-exit claims"),
    ("FLAG-N5-HANDOFF-EXIT-001", "REQUIRED", "N5", "Qualify retained kernel, page-table, guarded-stack, and immutable development-handoff ranges; final-map normalization and current-key binding; bounded ExitBootServices retry; zero post-exit firmware calls; and permanent stop before transfer without signature, entry, or N5-exit claims"),
    ("FLAG-N5-INIT-SYSTEM-001", "REQUIRED", "N5", "Qualify the exact seven-artifact PSM1 development profile, PBART1 role/version/payload envelope, whole-file digest binding, transactional page loading and cleanup, zero padding, retention, final-map coverage, and PBP1 cross-binding without signature, measurement, payload-semantics, execution, microcode, transfer, or N5-exit claims"),
    ("FLAG-N5-INIT-BUNDLE-001", "REQUIRED", "N5", "Qualify a deterministic initial-system declaration bundle with independent no_std Rust and Python validators, exact dependency and lifecycle ordering, abstract resources, attenuated capability routes, parser and activation hostile controls, declaration-versus-authority separation, and mandatory unsigned-development activation denial without claiming PooleBoot enforcement, PooleKernel activation, execution, or N5 exit"),
    ("FLAG-N5-RECOVERY-BUNDLE-001", "REQUIRED", "N5", "Qualify deterministic PREC1 immutable policy and mutable state formats with independent no_std Rust and Python validators, exact A/B selection and attempt persistence, known-good fallback, bounded safe and recovery transitions, authenticated success-receipt binding, authority and physical-presence separation, activation denial, hostile controls, and parser/transition differential evidence without claiming PooleBoot enforcement, PooleKernel recovery execution, persistent-state I/O, disk writes, or N5 exit"),
    ("FLAG-N5-SYMBOL-BUNDLE-001", "REQUIRED", "N5", "Qualify deterministic PSYM1 public symbol bytes with exact stripped/loaded/build/debug/source identity, image-relative addresses, bounded KASLR lookup, public-name and pointer-redaction policy, split-debug correspondence, independent no_std Rust and Python validators, hostile and differential evidence, and unsigned-development consumption denial without claiming PooleBoot or PooleKernel enforcement, authority, disclosure, kernel exports, N5 exit, or production readiness"),
    ("FLAG-N5-MICROCODE-BUNDLE-001", "REQUIRED", "N5", "Qualify deterministic PMCU1 microcode package semantics around synthetic-only opaque vendor bytes with exact CPU identity, digests, revision and rollback floors, highest-eligible and reset-based known-good selection, BSP/AP timing, mixed-revision failure, post-apply verification, independent no_std Rust and Python validators, hostile and differential evidence, and mandatory development activation denial without claiming vendor-container validation, privileged revision observation, PooleBoot or PooleKernel enforcement, CPU update, firmware mutation, physical-media writes, N5 exit, or production readiness"),
    ("FLAG-N5-FIRMWARE-BUNDLE-001", "REQUIRED", "N5", "Qualify deterministic PFWM1 firmware-manifest semantics with exact component, hardware-instance, version-floor, external-payload, signer, updater-plugin, dependency, recovery, dry-run authority, and post-reset receipt rules; independent no_std Rust and Python validators; hostile and differential evidence; zero embedded payloads; and mandatory development activation denial without claiming live inventory, vendor-payload validation, driver loading, firmware mutation, physical-media writes, N5 exit, or production readiness"),
    ("FLAG-N5-POLICY-BUNDLE-001", "REQUIRED", "N5", "Qualify deterministic PPOL1 role-7 policy semantics with six exact modes, default deny, built-in/signed/mode/capability/request intersection, PINIT1 route cross-binding, monotonic attenuation, safe/recovery floors, firmware physical-presence separation, durable decision receipts, independent no_std Rust and Python validators, hostile and differential evidence, and mandatory development activation denial without claiming live enforcement, authority creation, state mutation, PooleGlyph executable authority, N5 exit, or production readiness"),
    ("FLAG-N5-INIT-SEMANTICS-001", "REQUIRED", "N5", "Freeze and independently validate the inner initial-system, recovery, symbols, microcode, firmware-manifest, and policy formats, capability/resource declarations, dependency graph, lifecycle, rollback behavior, and apply/execute preconditions before PooleBoot or PooleKernel interprets any payload"),
    ("FLAG-N5-INNER-PARSE-001", "REQUIRED", "N5", "Reparse all six exact retained PBART1 files inside live PooleBoot, cross-bind PPOL1 payload digests and PINIT1 capability routes, require every development action gate to deny at the absent outer signature, bind a domain-separated retained-set digest, and prove zero authority, action, state-write, and hardware-observation effects through dual-channel QEMU and hostile evidence"),
    ("FLAG-N5-INNER-TRUST-CONTRACT-001", "REQUIRED", "N5", "Freeze separate PBTRUST1 immutable policy and mutable acceptance-state records, exact artifact/revocation/rollback/copy/previous-state/external-evidence bindings, deterministic failure precedence, and live PooleBoot unsigned-policy denial while explicitly rejecting ESP candidates as persistent authority and creating no signature, authority, or state-write claim"),
    ("FLAG-N5-INNER-TRUST-BACKEND-MODEL-001", "REQUIRED", "N5", "Freeze and independently qualify PBSTATE1 authenticated monotonic-anchor validation, two-copy logical-state selection, rollback and future-state rejection, deterministic repair and migration planning, and interrupted-transition recovery while performing no cryptography, storage I/O, anchor update, state write, or authority grant"),
    ("FLAG-N5-INNER-KERNEL-REVALIDATE-001", "REQUIRED", "N5", "Independently reparse exact retained PSM1, six PBART1 inner files, PBTP1, and PBTS1 bytes in allocation-free no_std PooleKernel code; reject locator, role, size, digest, binding, loader-summary substitution, and post-load mutation faults; reconstruct exact unsigned-policy denial; and grant zero authority before live kernel execution is separately proven"),
    ("FLAG-N5-KERNEL-TRANSFER-001", "REQUIRED", "N5", "Install the final retained CR3 and guarded RSP after ExitBootServices, preserve the required framebuffer mapping and ABI state, transfer exactly once into PooleKernel, execute PKREVAL1 over final retained bytes, emit an independently reconstructed terminal denial receipt, and preserve zero authority, actions, writes, and firmware calls"),
    ("FLAG-N5-INNER-TRUST-STATE-001", "BLOCKER", "N5", "Implement and enforce a real cryptographic monotonic writable provider, authenticated redundant PBTS1 persistence, repair and migration execution, rollback floors, revocation, and Secure Boot evidence before any PooleBoot authority decision, while preserving owner-presence, custody, safe-target, recovery, qualification, and zero-authority-before-verification boundaries"),
    ("FLAG-N5-INNER-ENFORCEMENT-001", "REQUIRED", "N5", "Authenticate and persist the six frozen inner formats and exact trust state, then make live PooleKernel revalidation gate only attenuated capability creation and authorized lifecycle, recovery, diagnostic, microcode, firmware, and policy actions with durable audit and rollback evidence"),
    ("FLAG-N6-KENTRY-001", "REQUIRED", "N6", "Qualify a real reproducible PooleKernel PKELF1 product with PKENTRY1 intake, bounded early diagnostics, panic taxonomy, hostile controls, manifest continuity, and explicit live-transfer nonclaims"),
    ("FLAG-N6-BOOT-DIGEST-001", "REQUIRED", "N6", "Complete independent cryptographic and supply-chain review of the pinned PBDIGEST1 provider, qualify its exact target backend, and prohibit trust promotion until the review and provider-promotion gates pass"),
    ("FLAG-N6-FRAMEBUFFER-MAP-001", "REQUIRED", "N6", "Install and record the exact temporary framebuffer identity mapping, preserve effective cache policy, and replace and revoke that mapping before graphics capability delegation"),
    ("FLAG-N7-TRAP-001", "REQUIRED", "N7", "Qualify a bounded BSP-only GDT/TSS/IDT and uniform integer trap-entry slice with exact deliberate breakpoint, invalid-opcode, guard-page-fault, double-fault, and malformed-frame evidence while preserving all per-CPU, all-vector, asynchronous, guarded-stack, target-hardware, and production nonclaims"),
    ("FLAG-N7-CPU-POLICY-001", "REQUIRED", "N7", "Qualify a bounded BSP-only qemu64 read-only CPUID, required-feature, control-register, XCR0, and support-gated MSR observation policy with independent Rust/Python agreement, exact dual-channel QEMU evidence, zero writes, zero authority, and explicit target-family, errata, xstate-ownership, AP-local, target-hardware, and production nonclaims"),
    ("FLAG-N7-ERRATA-POLICY-001", "REQUIRED", "N7", "Freeze and independently qualify a fail-closed exact-target CPU identity, mandatory-feature, board-lineage, BIOS, AGESA, microcode-evidence, errata-source-applicability, and RDSEED mitigation policy with zero privileged reads, writes, authority, or current-target promotion"),
    ("FLAG-N7-XSTATE-POLICY-001", "REQUIRED", "N7", "Qualify bounded eager x87/SSE standard-XSAVE ownership with exact XCR0/XSS policy, aligned per-owner images, canonical initialization, round-trip isolation, sensitive-image clearing, context-switch preconditions, kernel-SIMD prohibition, independent Rust/Python agreement, and explicit scheduler/SMP/target nonclaims"),
    ("FLAG-N7-XSTATE-EXCEPTION-001", "REQUIRED", "N7", "Qualify deliberate x87 #MF and SIMD #XM delivery with exact bounded recovery, terminal test-only #NM eager-policy rejection, independent marker validation, expected TCG limitation evidence, linked-machine-code scope audit, and explicit scheduler/SMP/target nonclaims"),
    ("FLAG-N7-PRIVILEGE-MSR-POLICY-001", "REQUIRED", "N7", "Freeze and independently qualify a read-only qemu64 BSP system-linkage, FS/GS, support-gated TSC_AUX, global machine-check, and unsupported-PMU policy with reserved-bit and canonical-address rejection, linked no-write audit, exact emulator boundaries, and zero authority"),
    ("FLAG-N9-PMM-FOUNDATION-001", "REQUIRED", "N9", "Consume and independently validate the exact live PBP1 memory map in PooleKernel; enforce UEFI source-kind, usable-only ownership, held reclaim classes, page-zero exclusion, retained loader ownership, DMA/DMA32/Normal zones, generation-safe handles, quotas, metadata poisoning, double-free rejection, and coalescing through two exact QEMU runs and hostile controls without claiming page scrubbing, mapping, reclaim, concurrency, N9 exit, or production readiness"),
    ("FLAG-N9-VM-FOUNDATION-001", "REQUIRED", "N9", "Freeze the initial 48-bit kernel/user layout and qualify generation-bound inactive four-level 4 KiB tables, bounded map/protect/unmap transactions, W^X and mixed-cache-alias rejection, exact rollback, inactive-root reuse receipts, and a single revoked PKMAP2 bootstrap temporary leaf through host fault tests, two exact QEMU runs, and hostile controls without claiming an active PKVM1 root, SMP shootdown, heap, pager, N9 exit, or production readiness"),
    ("FLAG-N9-VM-ACTIVE-001", "REQUIRED", "N9", "Qualify a kernel-complete one-BSP candidate root with exact inherited kernel, entry, guarded-stack, and handoff mappings; a bounded generation-owned direct map; transactional CR3 activation and exact restoration; architectural Accessed/Dirty handling; three local invalidation receipts; and release ordering through host fault tests, two exact QEMU runs, and hostile controls without claiming SMP shootdown, ring 3, heap, pager, target, N9 exit, or production readiness"),
    ("FLAG-N7-ERRATA-SOURCE-001", "STOP_SHIP", "N7", "Acquire and cryptographically bind an AMD source directly applicable to Family 1Ah Models 40h-4Fh, or retain an explicit reviewed vendor-response disposition; never substitute revision guide 58251 or another model range"),
    ("FLAG-N7-MICROCODE-FLOOR-001", "STOP_SHIP", "N7", "Obtain a direct AMD numeric client microcode security floor for the exact target or owner-ratify a reviewed replacement rule that does not infer a floor from OS metadata, unrelated products, firmware labels, or synthetic PMCU1 revisions"),
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
    ("FLAG-N2-PRIVILEGED-PROBE-001", "BLOCKER", "N2", "Qualify source-bound read-only MSR, PCI, SPD, UEFI-variable, memory, and I/O mechanisms through driver and side-effect review, then execute only against an identified safe target with backups, recovery, bounded scope, and retained evidence under the Cycle 118 owner authorization"),
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
    "The native repository, protected workflow, scope-hardened ADR ceremony, frozen 16-source packet, and completed response receipt record 2/2 ADR and 38/38 definition dispositions. Cycle 118 authorizes the remaining key/signing/publication and privileged operation categories, but all measurements, compatible hardware-key possession, trusted public-key custody, signatures, signed tags, immutable release refs, and retained CI review evidence remain open and no newly authorized operation has yet been performed",
    "Rust PE32+/ELF64 fixtures pass one-host qualification, but second-host reproduction, source provenance, C17/assembly/ABI tools, and image tooling remain open",
    "The native-only q35/QEMU/OVMF/VIRTIO profile passes one-host paused-instantiation controls, bounded checks for all seven required boot-slot/capability/virtual-memory/IPC/scheduler/update/PooleFS domains detect their required hostile violations, and a bounded PooleBoot proof executes under pinned OVMF, but source-rebuilt current QEMU/EDK II, complete reference devices/fault campaigns, six implementation-trace cross-checks, liveness/refinement/conformance work, and second-host reproduction remain open",
    "A reproducible unsigned PooleBoot proof application boots twice with deterministic twelve-file GPT/FAT32 media, exact GOP frames, retained PKMAP2 kernel/PSM1/six-artifact/PBTP1/PBTS1/table/guarded-stack/handoff storage, independently reconstructed ten-descriptor final PBLIVE3 bytes, bounded PBEXIT1 retry, successful ExitBootServices, and zero later firmware calls. The ordinary build stops before transfer; a separate opt-in QEMU-only PKXFER1 build installs retained CR3/RSP, transfers once, and live-executes PKREVAL1 over all nine retained files before an exact terminal unsigned-policy denial with zero signatures, authority, actions, writes, or firmware calls. PBSTATE1 still only models authenticated monotonic-anchor validation, deterministic redundant-copy selection, rollback/future rejection, repair/migration planning, and nine interrupted-transition recovery boundaries with no performed effects. Policy signature verification, authenticated revocation, a real cryptographic monotonic writable state provider, persistent backend I/O and executed repair/migration, Secure Boot-state verification, capability creation, activation or update application, policy application, recovery execution or symbol consumption, licensed real vendor payload intake and validation, live FMP/ESRT/PLDM inventory, privileged per-processor revision observation, initial-system execution, final framebuffer remap/revocation, production transfer, target-firmware and physical-media qualification, and N5 exit remain open",
    "A real reproducible 64-page PooleKernel image, PKENTRY1 intake, allocation-free PKREVAL1 verifier, bounded early diagnostics, opt-in QEMU-only live entry, BSP-only PKTRAP1 descriptor/exception containment, and bounded BSP PKXSTATE1 x87/SSE ownership exist, but authenticated boot trust, measured boot, production transfer, complete per-CPU descriptor/exception/xstate state, retained crash evidence, kernel runtime, target execution, and N6/N7 exit remain open",
    "PKERR1 freezes a pure exact-target CPU/errata rejection policy, PKXSTATE1 proves bounded x87/SSE standard-XSAVE ownership, PKXEXC1 proves deliberate #MF/#XM recovery plus terminal test-only #NM rejection with a linked scope audit under WHPX, and PKMSR1 proves only a read-only qemu64 BSP system-linkage/global-MCA/unsupported-PMU observation. PKPMM1 supplies bounded physical ownership, PKVM1 supplies inactive page-table transactions, and PKVM2 proves one-BSP candidate-root activation/restoration with a nine-page direct map and three local invalidation receipts; no target-qualified complete native CPU policy, applicable Model 40h-4Fh errata authority, direct numeric client microcode floor or ratified replacement, target-specific privileged-MSR semantics, syscall/per-CPU/MCE/PMU activation, AVX/extended state, user-task exception delivery, scheduler/AP/migration integration, interrupts, time, SMP, page-content scrubbing, reclaim transition, complete kernel/user address spaces, SMP TLB shootdown, heap, MMIO/cache-alias qualification, concurrent allocator, pressure, or OOM implementation exists",
    "The exact Tier 1 identity passes 24/24 required checks and 16 allowlisted user-mode CPUID records are captured with zero public raw registers, but seven required channels remain non-complete in total, including partial CPU/MSR and SPD/topology; 15 standards hashes, ten lab-safety prerequisites, native parsing, and physical qualification also remain open",
    "No native DMA/IOMMU/interrupt-remapping confinement",
    "PKPMM1 supplies bounded one-BSP physical-page ownership, PKVM1 supplies inactive four-level 4 KiB transactions, and PKVM2 supplies one bounded active root, nine-page direct map, exact CR3 restoration, and three local invalidation receipts; page-content scrubbing, reclaim transitions, a complete generation-owned direct map, SMP TLB shootdown and deferred reclaim, huge pages, PCID, COW, user faults, pager IPC, cache/MMIO qualification, heaps/object caches, concurrency/SMP, pressure and OOM policy, scheduler, task, syscall, capability, IPC, isolation, and asynchronous I/O remain open",
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
        phase["current_evidence"] = [
            item.replace("TEST_COUNT", str(test_count))
            for item in PHASE_EVIDENCE.get(phase_id, [])
        ]
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
                    "specs/native-initial-system-contract.json",
                    "specs/native-initial-system-golden-vectors.json",
                    "runs/native_initial_system_readiness.json",
                    "docs/native-initial-system-bundle.md",
                    "native/initsys/src/lib.rs",
                    "specs/native-recovery-contract.json",
                    "specs/native-recovery-golden-vectors.json",
                    "runs/native_recovery_readiness.json",
                    "docs/native-recovery-bundle.md",
                    "native/recovery/src/lib.rs",
                    "specs/native-symbol-contract.json",
                    "specs/native-symbol-golden-vectors.json",
                    "runs/native_symbol_readiness.json",
                    "docs/native-symbol-bundle.md",
                    "native/symbols/src/lib.rs",
                    "specs/native-microcode-contract.json",
                    "specs/native-microcode-golden-vectors.json",
                    "runs/native_microcode_readiness.json",
                    "docs/native-microcode-bundle.md",
                    "native/microcode/src/lib.rs",
                    "specs/native-firmware-contract.json",
                    "specs/native-firmware-golden-vectors.json",
                    "runs/native_firmware_readiness.json",
                    "docs/native-firmware-manifest.md",
                    "native/firmware/src/lib.rs",
                    "specs/native-policy-contract.json",
                    "specs/native-policy-golden-vectors.json",
                    "runs/native_policy_readiness.json",
                    "docs/native-policy-bundle.md",
                    "native/policy/src/lib.rs",
                    "native/inner/src/lib.rs",
                    "native/inner/src/bin/pinner1_probe.rs",
                    "runtime/native_inner_live.py",
                    "tests/test_native_inner_live.py",
                    "specs/native-boot-trust-contract.json",
                    "specs/native-boot-trust-contract.schema.json",
                    "specs/native-boot-trust-readiness.schema.json",
                    "runs/native_boot_trust_readiness.json",
                    "docs/native-boot-trust.md",
                    "native/trust/src/lib.rs",
                    "native/trust/src/bin/pbtrust1_probe.rs",
                    "runtime/native_boot_trust.py",
                    "tools/qualify_native_boot_trust.py",
                    "tests/test_native_boot_trust.py",
                ]
            )
        if phase_id == "N9":
            evidence.extend(
                [
                    "specs/native-kernel-physical-memory-contract.json",
                    "specs/native-kernel-physical-memory-contract.schema.json",
                    "specs/native-kernel-physical-memory-readiness.schema.json",
                    "native/kernel/src/physical_memory.rs",
                    "runtime/native_kernel_physical_memory.py",
                    "tools/qualify_native_kernel_physical_memory.py",
                    "tests/test_native_kernel_physical_memory.py",
                    "docs/native-kernel-physical-memory.md",
                    "runs/native-kernel-physical-memory-readiness.json",
                    "specs/native-kernel-virtual-memory-contract.json",
                    "specs/native-kernel-virtual-memory-contract.schema.json",
                    "specs/native-kernel-virtual-memory-readiness.schema.json",
                    "native/kernel/src/virtual_memory.rs",
                    "native/kernel/src/active_virtual_memory.rs",
                    "runtime/native_kernel_virtual_memory.py",
                    "tools/qualify_native_kernel_virtual_memory.py",
                    "tests/test_native_kernel_virtual_memory.py",
                    "docs/native-kernel-virtual-memory.md",
                    "runs/native-kernel-virtual-memory-readiness.json",
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
        if flag_id == "FLAG-N5-HANDOFF-EXIT-001":
            evidence.extend(
                [
                    "specs/native-boot-exit-contract.json",
                    "native/bootexit/src/lib.rs",
                    "native/boot/src/exit.rs",
                    "runtime/native_boot_exit.py",
                    "runtime/native_live_boot_handoff.py",
                    "docs/native-boot-exit.md",
                    "tests/test_native_boot_exit.py",
                    "tests/test_native_live_boot_handoff.py",
                    "runs/native_kernel_load_readiness.json",
                    "runs/native_pooleboot_readiness.json",
                ]
            )
        if flag_id == "FLAG-N5-INIT-SYSTEM-001":
            evidence.extend(
                [
                    "docs/native-initial-system-profile.md",
                    "native/artifact/src/lib.rs",
                    "native/bootload/src/lib.rs",
                    "native/boot/src/kload.rs",
                    "native/boot/src/livehandoff.rs",
                    "runtime/native_boot_artifact.py",
                    "runtime/native_kernel_load.py",
                    "tests/test_native_boot_artifact.py",
                    "tests/test_native_kernel_load.py",
                    "runs/native_kernel_load_readiness.json",
                    "runs/native_pooleboot_readiness.json",
                ]
            )
        if flag_id == "FLAG-N5-INIT-BUNDLE-001":
            evidence.extend(
                [
                    "specs/native-initial-system-contract.json",
                    "specs/native-initial-system-golden-vectors.json",
                    "native/initsys/src/lib.rs",
                    "runtime/native_initial_system.py",
                    "tools/qualify_native_initial_system.py",
                    "tests/test_native_initial_system.py",
                    "docs/native-initial-system-bundle.md",
                    "runs/native_initial_system_readiness.json",
                    "runs/native_kernel_load_readiness.json",
                    "runs/native_pooleboot_readiness.json",
                ]
            )
        if flag_id == "FLAG-N5-RECOVERY-BUNDLE-001":
            evidence.extend(
                [
                    "specs/native-recovery-contract.json",
                    "specs/native-recovery-golden-vectors.json",
                    "native/recovery/src/lib.rs",
                    "native/recovery/src/bin/prec1_probe.rs",
                    "runtime/native_recovery.py",
                    "tools/qualify_native_recovery.py",
                    "tests/test_native_recovery.py",
                    "docs/native-recovery-bundle.md",
                    "runs/native_recovery_readiness.json",
                    "runs/native_kernel_load_readiness.json",
                    "runs/native_pooleboot_readiness.json",
                ]
            )
        if flag_id == "FLAG-N5-SYMBOL-BUNDLE-001":
            evidence.extend(
                [
                    "specs/native-symbol-contract.json",
                    "specs/native-symbol-golden-vectors.json",
                    "native/symbols/src/lib.rs",
                    "native/symbols/src/bin/psym1_probe.rs",
                    "runtime/native_symbols.py",
                    "tools/qualify_native_symbols.py",
                    "tests/test_native_symbols.py",
                    "docs/native-symbol-bundle.md",
                    "runs/native_symbol_readiness.json",
                    "runs/native_kernel_load_readiness.json",
                    "runs/native_pooleboot_readiness.json",
                ]
            )
        if flag_id == "FLAG-N5-MICROCODE-BUNDLE-001":
            evidence.extend(
                [
                    "specs/native-microcode-contract.json",
                    "specs/native-microcode-golden-vectors.json",
                    "native/microcode/src/lib.rs",
                    "native/microcode/src/bin/pmcu1_probe.rs",
                    "runtime/native_microcode.py",
                    "tools/qualify_native_microcode.py",
                    "tests/test_native_microcode.py",
                    "docs/native-microcode-bundle.md",
                    "runs/native_microcode_readiness.json",
                    "runs/native_kernel_load_readiness.json",
                    "runs/native_pooleboot_readiness.json",
                ]
            )
        if flag_id == "FLAG-N5-FIRMWARE-BUNDLE-001":
            evidence.extend(
                [
                    "specs/native-firmware-contract.json",
                    "specs/native-firmware-golden-vectors.json",
                    "native/firmware/src/lib.rs",
                    "native/firmware/src/bin/pfwm1_probe.rs",
                    "runtime/native_firmware.py",
                    "tools/qualify_native_firmware.py",
                    "tests/test_native_firmware.py",
                    "docs/native-firmware-manifest.md",
                    "runs/native_firmware_readiness.json",
                    "runs/native_kernel_load_readiness.json",
                    "runs/native_pooleboot_readiness.json",
                ]
            )
        if flag_id == "FLAG-N5-POLICY-BUNDLE-001":
            evidence.extend(
                [
                    "specs/native-policy-contract.json",
                    "specs/native-policy-golden-vectors.json",
                    "native/policy/src/lib.rs",
                    "native/policy/src/bin/ppol1_probe.rs",
                    "runtime/native_policy.py",
                    "tools/qualify_native_policy.py",
                    "tests/test_native_policy.py",
                    "docs/native-policy-bundle.md",
                    "runs/native_policy_readiness.json",
                    "runs/native_kernel_load_readiness.json",
                    "runs/native_pooleboot_readiness.json",
                ]
            )
        if flag_id in {
            "FLAG-N5-INNER-PARSE-001",
            "FLAG-N5-INNER-TRUST-CONTRACT-001",
            "FLAG-N5-INNER-TRUST-BACKEND-MODEL-001",
            "FLAG-N5-INNER-TRUST-STATE-001",
        }:
            evidence.extend(
                [
                    "native/inner/src/lib.rs",
                    "native/inner/src/bin/pinner1_probe.rs",
                    "runtime/native_inner_live.py",
                    "tests/test_native_inner_live.py",
                    "native/trust/src/lib.rs",
                    "native/trust/src/backend.rs",
                    "native/trust/src/bin/pbtrust1_probe.rs",
                    "runtime/native_boot_trust.py",
                    "tests/test_native_boot_trust.py",
                    "specs/native-boot-trust-contract.json",
                    "runs/native_boot_trust_readiness.json",
                    "docs/native-boot-trust.md",
                    "native/boot/src/kload.rs",
                    "native/boot/src/main.rs",
                    "runs/native_kernel_load_readiness.json",
                    "runs/native_pooleboot_readiness.json",
                ]
            )
        if flag_id == "FLAG-N7-XSTATE-POLICY-001":
            evidence.extend(
                [
                    "specs/native-kernel-xstate-policy-contract.json",
                    "specs/native-kernel-xstate-policy-contract.schema.json",
                    "specs/native-kernel-xstate-policy-readiness.schema.json",
                    "native/boot/src/exit.rs",
                    "native/bootexit/src/lib.rs",
                    "native/kernel/src/arch/x86_64.rs",
                    "native/kernel/src/lib.rs",
                    "native/kernel/src/main.rs",
                    "native/kernel/src/xstate.rs",
                    "runtime/native_kernel_xstate_policy.py",
                    "tools/qualify_native_kernel_xstate_policy.py",
                    "tests/test_native_kernel_xstate_policy.py",
                    "docs/native-kernel-xstate-policy.md",
                    "runs/native-kernel-xstate-policy-readiness.json",
                ]
            )
        if flag_id == "FLAG-N7-XSTATE-EXCEPTION-001":
            evidence.extend(
                [
                    "specs/native-kernel-xstate-exception-contract.json",
                    "specs/native-kernel-xstate-exception-contract.schema.json",
                    "specs/native-kernel-xstate-exception-readiness.schema.json",
                    "native/kernel/src/arch/x86_64.rs",
                    "native/kernel/src/main.rs",
                    "native/kernel/src/xstate_exception.rs",
                    "runtime/native_kernel_xstate_exception.py",
                    "tools/qualify_native_kernel_xstate_exception.py",
                    "tests/test_native_kernel_xstate_exception.py",
                    "docs/native-kernel-xstate-exception.md",
                    "runs/native-kernel-xstate-exception-readiness.json",
                ]
            )
        if flag_id == "FLAG-N7-PRIVILEGE-MSR-POLICY-001":
            evidence.extend(
                [
                    "specs/native-kernel-privilege-msr-policy-contract.json",
                    "specs/native-kernel-privilege-msr-policy-contract.schema.json",
                    "specs/native-kernel-privilege-msr-policy-readiness.schema.json",
                    "native/boot/src/exit.rs",
                    "native/bootexit/src/lib.rs",
                    "native/kernel/src/arch/x86_64.rs",
                    "native/kernel/src/lib.rs",
                    "native/kernel/src/main.rs",
                    "native/kernel/src/privilege_msr.rs",
                    "runtime/native_kernel_privilege_msr_policy.py",
                    "tools/qualify_native_kernel_privilege_msr_policy.py",
                    "tests/test_native_kernel_privilege_msr_policy.py",
                    "docs/native-kernel-privilege-msr-policy.md",
                    "runs/native-kernel-privilege-msr-policy-readiness.json",
                ]
            )
        if flag_id == "FLAG-N5-INNER-KERNEL-REVALIDATE-001":
            evidence.extend(
                [
                    "specs/native-kernel-revalidation-contract.json",
                    "native/kernel/src/revalidation.rs",
                    "native/kernel/src/bin/pkreval1_probe.rs",
                    "runtime/native_kernel_revalidation.py",
                    "tools/qualify_native_kernel_revalidation.py",
                    "tests/test_native_kernel_revalidation.py",
                    "runs/native-kernel-revalidation-readiness.json",
                    "docs/native-kernel-revalidation.md",
                    "runs/native_kernel_load_readiness.json",
                ]
            )
        if flag_id == "FLAG-N5-KERNEL-TRANSFER-001":
            evidence.extend(
                [
                    "specs/native-kernel-transfer-contract.json",
                    "specs/native-kernel-transfer-readiness.schema.json",
                    "specs/native-kernel-entry-contract.json",
                    "specs/native-kernel-revalidation-contract.json",
                    "specs/native-kernel-map-contract.json",
                    "specs/native-boot-exit-contract.json",
                    "native/boot/src/exit.rs",
                    "native/bootexit/src/lib.rs",
                    "native/kernel/src/main.rs",
                    "runtime/native_kernel_transfer.py",
                    "tools/qualify_native_kernel_transfer.py",
                    "tests/test_native_kernel_transfer.py",
                    "docs/native-kernel-transfer.md",
                    "runs/native_kernel_entry_readiness.json",
                    "runs/native-kernel-revalidation-readiness.json",
                    "runs/native_kernel_load_readiness.json",
                    "runs/native-kernel-transfer-readiness.json",
                ]
            )
        if flag_id == "FLAG-N7-TRAP-001":
            evidence.extend(
                [
                    "specs/native-kernel-trap-contract.json",
                    "specs/native-kernel-trap-readiness.schema.json",
                    "native/boot/src/exit.rs",
                    "native/bootexit/src/lib.rs",
                    "native/kernel/src/arch/x86_64.rs",
                    "native/kernel/src/lib.rs",
                    "native/kernel/src/main.rs",
                    "runtime/native_kernel_trap.py",
                    "tools/qualify_native_kernel_trap.py",
                    "tests/test_native_kernel_trap.py",
                    "docs/native-kernel-trap.md",
                    "runs/native-kernel-trap-readiness.json",
                    "runs/native-kernel-trap-frame.ppm",
                ]
            )
        if flag_id == "FLAG-N7-CPU-POLICY-001":
            evidence.extend(
                [
                    "specs/native-kernel-cpu-policy-contract.json",
                    "specs/native-kernel-cpu-policy-readiness.schema.json",
                    "native/boot/src/exit.rs",
                    "native/bootexit/src/lib.rs",
                    "native/kernel/src/arch/x86_64.rs",
                    "native/kernel/src/lib.rs",
                    "native/kernel/src/main.rs",
                    "runtime/native_kernel_cpu_policy.py",
                    "tools/qualify_native_kernel_cpu_policy.py",
                    "tests/test_native_kernel_cpu_policy.py",
                    "docs/native-kernel-cpu-policy.md",
                    "runs/native-kernel-cpu-policy-readiness.json",
                ]
            )
        if flag_id in {
            "FLAG-N7-ERRATA-POLICY-001",
            "FLAG-N7-ERRATA-SOURCE-001",
            "FLAG-N7-MICROCODE-FLOOR-001",
        }:
            evidence.extend(
                [
                    "specs/native-kernel-errata-policy-contract.json",
                    "specs/native-kernel-errata-policy-contract.schema.json",
                    "specs/native-kernel-errata-policy-readiness.schema.json",
                    "native/cpupolicy/src/lib.rs",
                    "native/cpupolicy/src/bin/pkerr1_probe.rs",
                    "runtime/native_kernel_errata_policy.py",
                    "tools/qualify_native_kernel_errata_policy.py",
                    "tests/test_native_kernel_errata_policy.py",
                    "docs/native-kernel-errata-policy.md",
                    "runs/native-kernel-errata-policy-readiness.json",
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
                or flag_id in {"FLAG-N0-RATIFICATION-SCOPE-001", "FLAG-N2-CPUID-001", "FLAG-N4-PROFILE-001", "FLAG-N4-IPC-MODEL-001", "FLAG-N4-SCHEDULER-MODEL-001", "FLAG-N4-POOLEFS-MODEL-001", "FLAG-N5-POOLEBOOT-PROOF-001", "FLAG-N5-BOOTPROTO-001", "FLAG-N5-BOOTCFG-001", "FLAG-N5-ELF-001", "FLAG-N5-KLOAD-001", "FLAG-N5-MANIFEST-001", "FLAG-N5-PBP1-LIVE-001", "FLAG-N5-KMAP-001", "FLAG-N5-HANDOFF-EXIT-001", "FLAG-N5-INIT-SYSTEM-001", "FLAG-N5-INIT-BUNDLE-001", "FLAG-N5-RECOVERY-BUNDLE-001", "FLAG-N5-SYMBOL-BUNDLE-001", "FLAG-N5-MICROCODE-BUNDLE-001", "FLAG-N5-FIRMWARE-BUNDLE-001", "FLAG-N5-POLICY-BUNDLE-001", "FLAG-N5-INIT-SEMANTICS-001", "FLAG-N5-INNER-PARSE-001", "FLAG-N5-INNER-TRUST-CONTRACT-001", "FLAG-N5-INNER-TRUST-BACKEND-MODEL-001", "FLAG-N5-INNER-KERNEL-REVALIDATE-001", "FLAG-N5-KERNEL-TRANSFER-001", "FLAG-N6-KENTRY-001", "FLAG-N7-TRAP-001", "FLAG-N7-CPU-POLICY-001", "FLAG-N7-ERRATA-POLICY-001", "FLAG-N7-XSTATE-POLICY-001", "FLAG-N7-XSTATE-EXCEPTION-001", "FLAG-N7-PRIVILEGE-MSR-POLICY-001", "FLAG-N9-PMM-FOUNDATION-001", "FLAG-N9-VM-FOUNDATION-001", "FLAG-N9-VM-ACTIVE-001"}
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
            "last_updated_cycle": 127,
            "selected_move_id": "N9-VM-ACTIVE-001",
            "immediate_next_move_id": "N0-HW-KEY-ACQUIRE-001",
            "owner_independent_next_move_id": "N9-PMM-SCRUB-001",
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
                "runs/native_boot_trust_readiness.json",
                "runs/native_pooleboot_readiness.json",
                "runs/native_boot_handoff_readiness.json",
                "runs/native_boot_config_readiness.json",
                "runs/native_elf_loader_readiness.json",
                "runs/native_kernel_entry_readiness.json",
                "runs/native_kernel_load_readiness.json",
                "runs/native-kernel-revalidation-readiness.json",
                "runs/native-kernel-transfer-readiness.json",
                "runs/native-kernel-trap-readiness.json",
                "runs/native-kernel-cpu-policy-readiness.json",
                "runs/native-kernel-errata-policy-readiness.json",
                "runs/native-kernel-xstate-policy-readiness.json",
                "runs/native-kernel-xstate-exception-readiness.json",
                "runs/native-kernel-privilege-msr-policy-readiness.json",
                "runs/native-kernel-physical-memory-readiness.json",
                "runs/native-kernel-virtual-memory-readiness.json",
                "runs/native_initial_system_readiness.json",
                "runs/native_recovery_readiness.json",
                "runs/native_symbol_readiness.json",
                "runs/native_microcode_readiness.json",
                "runs/native_firmware_readiness.json",
                "runs/native_policy_readiness.json",
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
            "pooleos_cycle": 127,
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
                "passed_checks": 93,
                "total_checks": 93,
                "artifact_count": 50,
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
            "title": "Obtain and confirm possession of the selected compatible FIDO2 hardware key before the already authorized governance-key ceremony",
            "entry_evidence": ["specs/n0-owner-response.json", "runs/n0_owner_response_receipt.json", "runs/adr_ratification_readiness.json", "docs/adr-ratification-ceremony.md"],
            "exit_evidence": ["owner confirms possession of a compatible FIDO2 hardware key", "owner-presence and recovery-custody procedure reviewed before execution", "exact public fingerprint and signer-registration procedure prepared without exposing private material"],
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
            "The Cycle 106 PKLOAD5/PooleBoot6 receipts prove retained kernel, four-table-page, guarded eight-page stack, and one-MiB read-only handoff storage; exact final-map-bound post-exit development PBP1 bytes; bounded stale-key retry semantics; successful ExitBootServices; zero later firmware calls; and a permanent stop before transfer. They do not prove signatures or trust, profile artifact loading, the kernel-entry PBP1 profile, final CR3/RSP installation, kernel consumption or execution, final framebuffer cache policy, target firmware, N5 exit, or production readiness.",
            "The Cycle 107 PKLOAD6/PooleBoot7 receipts prove an exact seven-artifact PSM1 development profile, independent PBART1 role/version/payload and whole-file digest checks, distinct zero-padded loader ranges, final-map retention, seven-role PBP1 cross-binding, two exact OVMF runs, and fail-closed artifact controls. They do not prove signatures, authentication, payload semantics, initial-system execution, microcode application, kernel transfer, target firmware, N5 exit, or production readiness.",
            "The Cycle 108 PINIT1 receipt proves a deterministic initial-system declaration format, exact component/service/dependency/resource/capability graph validation, canonical start ordering, lifecycle and rollback policy checks, 120 fail-closed parser and activation controls, mandatory unsigned-development activation denial, and 16,384-case Rust/Python agreement. The PKLOAD6 and PooleBoot7 aggregate receipts bind those bytes and host-oracle results into two exact development-media boots, but PooleBoot does not enforce PINIT1 semantics, PooleKernel does not allocate or activate the declarations, no component executes, and no signature, rollback-state, target-firmware, N5-exit, or production claim follows.",
            "The Cycle 109 PREC1 receipt proves a deterministic 992-byte immutable recovery policy, a separately mutable 128-byte state record, exact A/B eligibility and decrement-before-handoff transitions, known-good fallback, bounded safe and recovery loops, authenticated success-receipt binding, failure routing, physical-presence authority separation, 144 fail-closed controls, 16,384 parser/state and 8,192 transition differential cases, and mandatory unsigned-development activation denial. PKLOAD6 and PooleBoot7 bind those policy bytes and host-oracle results into two exact development-media boots, but PooleBoot does not enforce PREC1, PooleKernel does not execute recovery, the checksum is not authentication, no persistent UEFI/disk state is read or written, and no signature, target-firmware, N5-exit, or production claim follows.",
            "The Cycle 110 PSYM1 receipt proves a deterministic public-only symbol bundle with exact stripped/loaded/build/debug/source identity, image-relative offsets, bounded KASLR-base lookup, three explicitly public symbols, source-path exclusion, pointer redaction, split-debug correspondence, 158 fail-closed controls, two 16,384-case Rust/Python differential campaigns, and mandatory unsigned-development consumption denial. PKLOAD6 and PooleBoot7 bind those bytes and host-oracle results into two exact development-media boots, but PooleBoot and PooleKernel do not consume PSYM1, no kernel export or diagnostic authority is created, the full debug file is absent from media, runtime pointers remain redacted by default, and no signature, target-firmware, N5-exit, or production claim follows.",
            "The Cycle 111 PMCU1 receipt proves a deterministic exact-CPU wrapper around 35 synthetic never-apply payloads, per-package and per-patch digests, revision and authenticated-floor selection, normal and reset-based known-good policy, no in-session downgrade, BSP/AP timing prerequisites, mixed-revision failure, post-apply revision and CPUID checks, 174 fail-closed controls, and 40,960 Rust/Python differential cases with zero mismatches and mandatory unsigned-development activation denial. PKLOAD6 and PooleBoot7 bind those bytes and host-oracle results into two exact development-media boots, but no real vendor container or production payload is present or validated, no privileged per-processor revision is observed, PooleBoot and PooleKernel do not enforce PMCU1, no CPU update, firmware mutation, driver load, or physical-media write occurs, and no signature, target-firmware, N5-exit, or production claim follows.",
            "The Cycle 112 PFWM1 receipt proves a deterministic synthetic-only firmware manifest with three exact components, two dependency edges, normalized UEFI capsule/ESRT and PLDM transports, exact resource and hardware-instance identity, external payload digests, version and rollback floors, signer and updater-plugin bindings, a single-transaction topological plan, 47 ordered activation prerequisites, recovery identities, post-reset receipt and driver-rebind checks, 101 fail-closed controls, and 32,768 Rust/Python differential cases with zero mismatches and mandatory development activation denial. PKLOAD6 and PooleBoot7 bind those bytes and host-oracle results into two exact development-media boots, but PFWM1 contains no payload bytes, no live FMP/ESRT/PLDM inventory is observed, no vendor payload or updater is validated or loaded, PooleBoot and PooleKernel do not enforce PFWM1, no capsule is submitted, no firmware is mutated, no physical media is written, and no signature, target-firmware, N5-exit, or production claim follows.",
            "The Cycle 113 PPOL1 receipt proves a deterministic 1,984-byte qualification-only policy with six exact modes, eleven PINIT1-cross-bound capability rules, default-deny authority intersection, parent-monotonic attenuation, immutable safe/recovery floors, firmware physical-presence and separate-authority requirements, durable decision receipts, 116 fail-closed controls, and 32,768 Rust/Python differential cases with zero mismatches and mandatory development activation denial. PKLOAD6 and PooleBoot7 bind those exact bytes and host-oracle results into two development-media boots and raise the integrated corpus to 130 controls, but neither target interprets PPOL1, no signature or persistent state is verified, no authority or PooleGlyph executable role is created, no decision is applied, and no state mutation, physical-media, target-firmware, N5-exit, or production claim follows.",
            "The Cycle 114 N5-INNER-LIVE-PARSE-001 receipt proves that live PooleBoot reparses all six exact retained PBART1 files from their allocated firmware pages before ExitBootServices, binds PPOL1's five payload digests and eleven PINIT1 capability routes, requires each development gate to fail first at its missing outer signature, and emits the domain-separated retained-set SHA-256 F3154B354C77D0567207994EFDDA4FE2D203611CA21D60B63872BC9FFC73C675 with zero authority grants, authorized actions, state writes, and hardware observations. Two exact QEMU/OVMF runs emit 24 ordered markers and pass 139 hostile controls, but the files remain unsigned and untrusted, PooleKernel does not independently reparse them, no persistent state is read or written, no capability or executable authority is created, no action is applied, and no kernel transfer, target-firmware, physical-media, N5-exit, or production claim follows.",
            "The Cycle 115 N5-INNER-TRUST-CONTRACT-001 receipt freezes PBTRUST1 as separate 320-byte immutable-policy and 256-byte mutable acceptance-state records, distinct from PREC1 boot-attempt state; models signer thresholds, revocation identity, fourteen artifact/state/rollback bindings, redundant-copy and previous-state-chain shapes, and eight external evidence gates; and integrates both exact development candidates into live PooleBoot. Four Rust tests, 88 hostile controls, 24,576 Rust/Python differential cases, and two exact QEMU/OVMF runs with 25 markers and 148 integrated controls pass. The live path denies exactly at unsigned policy with zero signature verification, authority grants, or state writes. The ESP candidate is not authenticated, monotonic, writable, or accepted as persistent authority; no cryptographic verifier, revocation store, Secure Boot-state evidence, redundant transactional backend, power-loss recovery, PooleKernel revalidation, key use, signing, kernel transfer, target-firmware, physical-media, N5-exit, or production claim follows.",
            "The Cycle 116 N5-INNER-TRUST-BACKEND-001 receipt extends PBTRUST1 with a pure allocation-free PBSTATE1 model over exactly two physical copies and an externally authenticated monotonic anchor. Twelve Rust tests, 105 hostile controls, four independent 8,192-case Rust/Python differential campaigns, and nine interrupted-transition recovery cases pass. Selection rejects unauthenticated, malformed, stale, future, previous-chain-mismatched, digest-mismatched, non-writable, or capacity-insufficient inputs; the transition planner freezes alternate-copy, generation-overflow, migration, anchor-commit, and repair ordering. The model performs no cryptography, persistent backend I/O, anchor update, repair, migration, authority grant, or state write; it is not wired into live PooleBoot, and PooleKernel does not independently revalidate the retained files or selected state. No trust promotion, key use, signing, kernel transfer, target-firmware, physical-media, N5-exit, or production claim follows.",
            "The Cycle 117 N5-INNER-KERNEL-REVALIDATE-001 receipt expands the final PBP1 profile to exact retained PSM1, six PBART1 files, PBTP1, and PBTS1 byte locators and adds allocation-free no_std PKREVAL1 PooleKernel code that independently validates role order, exact file sizes and SHA-256 identities, disjoint retained ranges, all nine parsers, PSM1 artifact bindings, six inner-format bindings, PBTRUST1 policy/state bindings, and exact unsigned-policy denial. Thirteen Rust tests, eight Python tests, 36 hostile controls, and 32,768 role-complete deterministic mutation rejects pass with zero authority grants, authorized actions, or state writes. PKLOAD6 separately reproduces two 25-marker QEMU/OVMF producer runs and 155 integrated controls over the ten-role PBP1 profile. PooleBoot still stops permanently before transfer, so the kernel verifier is host-executed and target-built but not live-executed after ExitBootServices; no authenticated persistent state, capability creation, key use, signing, target-firmware, physical-media, N5-exit, or production claim follows.",
            "The Cycle 118 N5-KERNEL-TRANSFER-001 receipt preserves the ordinary PooleBoot stop-before-transfer path and adds only an opt-in QEMU-only development-transfer feature. Two exact PooleKernel builds, two exact feature-enabled PooleBoot builds, one default isolation build, two exact media generations, and two fresh-vars QEMU/OVMF runs agree on 30 ordered markers and exact serial/debugcon/PBP1 bytes. PooleBoot installs retained CR3 and guarded RSP, clears IF/DF, and transfers once; PooleKernel validates runtime state and independently executes PKREVAL1 over all nine retained files before an exact terminal unsigned denial. Fifty-eight hostile controls pass, and signatures, authority grants, actions, state writes, and post-exit firmware calls remain zero. This does not prove an authenticated production entry, persistent trust state, capabilities, target firmware, physical media, N5/N6 exit, or production readiness.",
            "The Cycle 119 N7-TRAP-001 receipt adds three mutually exclusive opt-in QEMU-only PKTRAP1 profiles after PKXFER1. Six fresh-vars runs prove one BSP GDT/TSS/IDT setup with five present gates, distinct bounded IST1/IST2 arrays, a normalized 176-byte integer frame, returning #BP/#UD/guard-page #PF handling, terminal processor-delivered #DF containment, and explicit semantic malformed-frame rejection across 51 hostile controls. It does not prove per-CPU tables, guarded IST mappings, all-vector or asynchronous context coverage, NMI, machine check, user transitions, persistent crash recovery, target firmware, physical hardware, N7 exit, or production readiness.",
            "The Cycle 120 N7-CPU-POLICY-001 receipt adds one mutually exclusive opt-in QEMU-only PKCPU1 profile after PKXFER1. Two fresh-vars qemu64 runs prove a support-gated BSP read-only snapshot and validation of CPUID identity/features/topology/address widths, CR0/CR4/EFER, XCR0, and APIC/PAT/MTRR MSRs across 35 markers and 41 hostile controls with exact Rust/Python agreement, five MSR reads, zero MSR writes, zero authority, and zero actions. It does not prove the Tier 1 target family, errata or microcode-revision policy, x87/SSE/XSAVE ownership, AP-local policy, syscall/GS/TSC_AUX/MCE/performance MSRs, target firmware, physical hardware, N7 exit, or production readiness.",
            "The Cycle 121 N7-ERRATA-POLICY-001 receipt freezes PKERR1 as a pure exact-target policy for CPUID signature 0x00B40F40, nine mandatory features, board-lineage-specific stable BIOS floors, AMD-SB-7033 and AMD-SB-7055 AGESA floors, RDSEED handling, homogeneous microcode evidence, and direct-source applicability. Independent no_std Rust and Python evaluators agree across 128 vectors and 24 hostile controls. The current evidence is denied for six exact reasons with zero privileged reads, writes, authority, or actions. AMD revision guide 58251 is explicitly rejected because it covers Models 00h-0Fh, while the required Model 40h-4Fh guide and a direct numeric client microcode floor remain stop-ship gaps. Windows registry revision 0x0B404023 is OS-reported metadata only. No firmware was downloaded or changed, no microcode was applied, and no target, N7-exit, release, or production claim follows.",
            "The Cycle 122 N7-XSTATE-POLICY-001 receipt adds one mutually exclusive opt-in QEMU-only PKXSTATE1 profile after PKXFER1. Thirty-one kernel host tests and two exact fresh-vars EPYC-Rome-v4 x87/SSE runs prove support-gated CR0/CR4/XCR0 initialization, XCR0 0x3, XSS zero, 576-byte enabled state inside 4,096-byte aligned owner images, canonical FCW 0x037F and MXCSR 0x1F80, two context saves, four restores, exact cross-owner isolation, 8,192 cleared image bytes, and 43 hostile controls with exact Rust/Python agreement. The three writes are restricted to CR0, CR4, and XCR0; signatures, authority, and actions remain zero. AVX and extended components, deliberate #MF/#XM/#NM handling, scheduler integration, AP state, CPU migration, final machine-code SIMD audit, target hardware, N7 exit, release, and production remain open.",
            "The Cycle 123 N7-XSTATE-EXCEPTION-001 receipt adds one mutually exclusive opt-in PKXEXC1 profile after PKXSTATE1. One expected TCG limitation probe records missing #XM injection, while two exact fresh-vars WHPX QEMU/OVMF runs deliver #MF and #XM, perform exact bounded FNINIT and LDMXCSR recovery, resume at exact sites, and then deliver a terminal test-only #NM that the eager policy rejects without state sampling or recovery. Forty-one markers, 43 hostile controls, a source instruction audit, and a hash-bound linked llvm-objdump audit pass. The four configuration writes are restricted to CR0, CR4, XCR0, and test-only CR0.TS; the two recovery writes are FNINIT and LDMXCSR. Signatures, authority, actions, firmware calls, and physical-media effects remain zero. Scheduler and user-task delivery, AP state, CPU migration, AVX and extended components, exact-target qualification, N7 exit, release, and production remain open.",
            "The Cycle 124 N7-PRIVILEGE-MSR-POLICY-001 receipt adds one mutually exclusive opt-in PKMSR1 profile after PKXEXC1. Two exact fresh-vars TCG qemu64 QEMU/OVMF runs emit 35 ordered markers and perform eleven support-gated RDMSR observations over inactive system linkage, zero FS/GS bases, global machine-check state, and an unsupported PMU path. Forty-seven hostile controls, independent Rust/Python validation, a source allowlist audit, and a hash-bound linked audit with exactly seventeen total RDMSR instructions and zero WRMSR/RDPMC/SYSCALL/SYSRET/SWAPGS instructions pass. The measured emulator lacks RDTSCP, reports ten MCA banks, MCG_CAP 0x000000000100010A, and all-ones MCG_CTL; those are qemu64 compatibility facts and not AMD target semantics. No MSR/control write, syscall entry, SWAPGS, TSC_AUX read, bank read, machine-check handler, PMU owner, signature, authority, action, firmware call, or physical-media effect occurs. AP-local state, target-specific privileged-MSR policy, activation transactions, target qualification, N7 exit, release, and production remain open.",
            "The Cycle 125 N9-PMM-001 receipt adds opt-in selector-8 PKPMM1 after PKXFER1 and fixes the shared bootstrap stack from eight to fourteen pages while preserving low/high guards and handoff placement. Two exact fresh-vars qemu64 QEMU/OVMF runs emit 40 ordered markers and consume the live 97-entry PBP1 map inside PooleKernel. The allocator revalidates UEFI source kinds, manages 117,924 of 117,925 conventional usable pages after page-zero exclusion, holds 11,250 boot-reclaimable pages, protects 819 retained loader pages, audits kernel/root/stack/handoff ownership, and exercises four deterministic zoned allocate/free operations with quota, stale/double-free, poison, and coalescing checks. Forty-eight hostile controls pass with zero physical-page writes, page-table mappings, reclaim transitions, signatures, authority, or actions. Page-content scrubbing, virtual memory, heaps, MMIO/cache aliases, concurrent/SMP allocation, pressure/OOM policy, target hardware, N9 exit, release, and production remain open.",
            "The Cycle 126 N9-VM-001 receipt adds opt-in selector-9 PKVM1 after PKPMM1. A fixed-capacity no_std core allocates four generation-bound DMA32 table pages plus one data frame, materializes one inactive x86_64 hierarchy, and proves bounded map/protect/unmap, exact rollback, W^X and mixed-cache-alias rejection, inactive-root receipts, and deferred frame reuse. Because new conventional pages are not inherited identity mappings, the live adapter validates BSP CPUID address width and uses exactly one previously absent PKMAP2 leaf as a supervisor RW/NX bootstrap alias, revoking it before table free. Two exact fresh-vars qemu64 runs emit 40 markers and pass 39 hostile controls with 4,104 inactive-table writes, 40 bootstrap PTE writes, 40 local INVLPG operations, zero PKVM1 CR3 writes, zero shootdowns, exact allocation release, and zero signatures, authority, or actions. This does not prove a kernel-complete active root, direct map, active-address-space TLB protocol, SMP shootdown, huge pages, PCID, COW, user faults, pager, heap, target hardware, N9 exit, release, or production readiness.",
            "The Cycle 127 N9-VM-ACTIVE-001 receipt adds opt-in selector-10 PKVM2 after the PKVM1 foundation. A fixed-capacity no_std core allocates eight generation-bound DMA32 table pages plus one data frame, copies and audits exact inherited kernel, entry, guarded-stack, and handoff mappings, constructs a bounded supervisor RW/NX direct map over exactly those nine owned pages, and installs the candidate root on BSP 0 with interrupts disabled. It handles architectural Accessed/Dirty drift, host-tests CR3 and leaf-write rollback, binds protect/user-unmap/direct-unmap to three local invalidation receipts, rejects premature reuse, restores the exact original CR3, scrubs and releases both allocations, and revokes the bootstrap alias. Two exact fresh-vars qemu64 runs emit 40 markers and pass 46 hostile controls with 8,720 physical table writes, 5,336 bootstrap temporary-PTE writes and invalidations, two CR3 writes, three active local invalidations, zero shootdowns, and zero signatures, authority, or actions. This does not prove page-content scrubbing policy, held-class reclaim, a complete direct map, SMP shootdown/deferred reclaim, ring 3, huge pages, PCID, COW, user faults, pager, heap, target hardware, N9 exit, release, or production readiness.",
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
    parser.add_argument("--test-count", type=int, default=785)
    parser.add_argument("--status-date", default="2026-07-22")
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
