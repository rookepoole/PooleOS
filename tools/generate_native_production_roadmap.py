#!/usr/bin/env python3
"""Generate the machine-readable PooleOS native production roadmap."""

from __future__ import annotations

import argparse
import copy
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
    "N29.8": "partial",
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
    "N8.1": "partial",
    "N8.3": "partial",
    "N8.5": "partial",
    "N9.1": "partial",
    "N9.2": "partial",
    "N9.3": "partial",
    "N9.4": "partial",
    "N12.1": "complete",
    "N12.2": "complete",
    "N12.3": "partial",
    "N12.4": "partial",
    "N12.5": "partial",
    "N12.6": "partial",
    "N12.7": "partial",
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
        "runs/adr_ratification_readiness.json: all seven ADRs owner-directed, one registered hardware-backed public signer, 12 declared negative controls, and four remaining gated actions; enrollment signature verification and independent recovery custody remain pending",
        "runs/n0_owner_decision_packet.json and docs/n0-owner-decision-packet.md: byte-frozen 16-source historical review packet retaining every original field as UNSELECTED and 12/12 fail-closed controls",
        "specs/n0-owner-response.json, runs/n0_owner_response_receipt.json, and docs/n0-owner-response-receipt.md: exact completed response, 2/2 ADR and 38/38 definition dispositions, unavailable hardware-key state, 16/16 hostile controls, and zero authorization for key generation, signing, merge, tag, or publication",
        "Cycle 118 owner authorization remains subject to charter qualification, owner-presence, backup, recovery, safe-target, and exact-release gates. The later primary-key enrollment and GitHub registration are recorded in security/governance-key-registration.json; recovery custody and architecture signatures remain pending",
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
        "Cycle 169: six current N5 component receipts, six fresh boots, two live kernel entries and 83 passing regressions; inner SHA256 2DC54F8C02425C44DEB80A0F6285CAF4687A90537114902D39BB338C14BD7664. PSYM1 requires current PKENTRY1 evidence. No authenticated boot or N5 exit. Earlier entries are historical.",
       "Cycle 168 requires changed-image N5 replay beginning PSYM1; the unchanged PPOL1 component remains current. No N5 exit or authenticated boot is claimed. Earlier entries below are historical.",
        "Cycle 163: docs/checkpoints/cycle163-boot-chain-replay.md records six current N5 component passes, six final headless boots, two live kernel entries, nine retained files and 70 focused Python tests. Fixed-day loader/PooleBoot schemas are repaired with explicit calendar validation. Current inner SHA256 864A7094E7ED3AFDF282791CC53D97D5D1CD4064E998D1678BD7ED79EBF6B79D agrees across independent host, Rust and guest evidence. N5 remains partial; nineteen downstream checks and full qualification remain pending",
        "Historical Cycle 162: docs/checkpoints/cycle162-active-root-retention.md records the 146-page image and PKMAP2 retained-window repair under N5.5/N5.8. Rust14/Python15 map tests and the independent retained-map fingerprint agree. Other N5 changed-image dependencies require replay; earlier receipts below retain historical scope",
        "Cycle 161 confirms the six Cycle 159 N5 receipts and Cycle 160 N7 receipts still pass current-source checks. All fourteen downstream profiles and the full pre-closeout canonical suite now pass on the unchanged Cycle 158 kernel. Earlier cycle entries retain their historical scopes",
        "Cycle 159 current-kernel replay: PSYM1 and PPOL1 pass independent rebuild/differential qualification; PKLOAD6 passes 304 host tests, two fresh boots and 155 controls; PooleBoot passes two additional fresh boots and 155 controls; PKREVAL1 passes 219 kernel tests, 36 controls and 32768 mutations; PKXFER1 passes two actual entries, nine-file independent revalidation and 58 controls. All six selected gates and 68 focused Python tests pass. Current inner SHA256 7B68DDA305B46690E02CA7597633F16ADBDAAF7607759253F95EB919F2493B9F matches measured source, Rust and guest results. Nineteen downstream checks and the full aggregate replay remain pending. Earlier cycle entries below preserve historical scope; no N5 exit, phase/flag closure, demo rebase or production claim follows",
        "Cycle 154 current-source replay: measured PSYM1 identities and PPOL1 current-reference validation pass; PKLOAD6 and aggregate PooleBoot each pass two exact runs, PKREVAL1 passes 36 controls and 32768 mutations, and PKXFER1 passes two real kernel entries, nine-file revalidation and 58 controls. All six boot-chain gates and 63 focused Python tests pass. Inner SHA256 99DB2125174F65A067F619FD65D61EBC5806D2AFCCCAB3E66411A42A1EFC5342 agrees with independent source reconstruction and Rust/guest evidence. Remaining downstream profiles and the full candidate gate are still pending; no N5 exit or production claim",
        "ADD-BOOT-010 / FLAG-N5-POLICY-BUNDLE-001: Cycle 154 repairs a readiness validation gap that accepted an old policy receipt despite stale current PSYM1-derived vectors. Bind all five payload-reference implementations and validate the current contract and golden vectors; dependency drift, changed contract and unavailable-vector controls reject. Existing ADD-BOOT-011 governs subsequent exact retained-byte replay; no requirement is waived",
        "demos/native_iso/evidence.json: Cycle 151 non-promoting UEFI El Torito optical demo, two fresh four-vCPU PKLOCK1 boots, unchanged canonical kernel and native source, exact static PooleGlass guest pixels; not a signed or production ISO",
        "specs/native-pooleboot-proof.json: POOLEOS-N5-POOLEBOOT-7 bounded unsigned aggregate contract across N5.1-N5.9",
        "native/boot: Poole-authored no_std PE32+ UEFI application with reviewed firmware bindings, live bounded filesystem/config/kernel/PBART1/PBTP1/PBTS1 intake, exact retained-page inner parsing, GOP identity, retained PKMAP2 kernel/six-artifact/PSM1/trust-policy/trust-state/table/guarded-stack/handoff storage, final PBLIVE4 production with a firmware RSDP record, bounded PBEXIT1 retry, successful ExitBootServices, direct post-exit serial/debugcon diagnostics, a default permanent stop, and a separately feature-gated QEMU-only one-way development transfer",
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
        "specs/native-kernel-load-contract.json and docs/native-kernel-load.md: PKLOAD6 freezes live UEFI intake, PSM1/PBART1 digest binding, exact PBASET1 plus PSM1/PBTP1/PBTS1 loading and retention, six-format retained-page parsing and denial, PBTRUST1 policy/state candidate parsing, fourteen cross-bindings and exact unsigned-policy denial, retained PKMAP2 storage, final ten-role PBLIVE4 production with a firmware RSDP record, bounded PBEXIT1 retry, successful ExitBootServices, stop-before-transfer, trust, semantics, and nonclaim boundaries",
        "native/bootload, native/inner, native/trust, native/boot/src/kload.rs, native/boot/src/kmap.rs, native/boot/src/exit.rs, native/bootexit, runtime/native_inner_live.py, runtime/native_boot_trust.py, and runtime/native_kernel_load.py: dependency-free contracts, reviewed raw UEFI adapters, and independent retained-set/trust/media/map/exit oracle implementation",
        "specs/native-kernel-map-contract.json, native/kmap, runtime/native_kernel_map.py, and docs/native-kernel-map.md: current PKMAP2 exact 146-page 4 KiB supervisor kernel mapping, two retained leaf tables, guarded stack starting at page 147, read-only handoff starting at page 184, W^X/WP/NX, active-root audit, framebuffer preservation, ten-role retained allocation coverage, and nonclaim contract",
        "specs/native-boot-exit-contract.json, native/bootexit, runtime/native_boot_exit.py, and docs/native-boot-exit.md: PBEXIT1 final-map, current-key, bounded stale-key retry, no-post-attempt-service, no-post-exit-firmware, and permanent pre-transfer-stop contract",
        "runs/native_kernel_load_readiness.json: Cycle 154 exact 299/299 aggregate Rust host tests, 2/2 exact PooleBoot builds, 2/2 exact PooleKernel builds, 2/2 exact twelve-file media generations, 2/2 QEMU/OVMF runs, 25 ordered markers, 155 integrated hostile controls, exact retained PINIT1, PREC1, PSYM1, PMCU1, PFWM1, and PPOL1 parsing with payload/route cross-binding and mandatory development denial, exact retained PSM1/PBTP1/PBTS1 parsing with fourteen trust cross-bindings and unsigned-policy denial, two exact post-exit PBLIVE4 PBP1 reconstructions, exact 144-page kernel plus nine retained files/five table pages/36-page guarded-stack/handoff/firmware-record agreement, successful ExitBootServices, zero later firmware calls, and exact guest/oracle agreement",
        "specs/native-kernel-revalidation-contract.json and docs/native-kernel-revalidation.md: PKREVAL1 freezes independent allocation-free no_std PooleKernel reparsing of exact retained PSM1, six PBART1 inner files, PBTP1, and PBTS1 bytes before authority, with exact role/order/range/digest/binding/denial requirements and standalone-execution nonclaims",
        "native/kernel/src/revalidation.rs, native/kernel/src/bin/pkreval1_probe.rs, runtime/native_kernel_revalidation.py, and tests/test_native_kernel_revalidation.py: independent kernel-side verifier, host probe, Python oracle, loader-summary substitution controls, post-load mutation controls, and deterministic role-complete differential campaign",
        "runs/native-kernel-revalidation-readiness.json: Cycle 154 214/214 kernel Rust tests, 8/8 Python tests, both no_std target builds, nine exact retained files and parsers, 36/36 hostile controls, 32,768/32,768 deterministic mutation rejects, exact unsigned-policy denial, zero authority grants/actions/state writes, and no standalone live-entry claim",
        "specs/native-kernel-transfer-contract.json, runtime/native_kernel_transfer.py, tools/qualify_native_kernel_transfer.py, tests/test_native_kernel_transfer.py, and docs/native-kernel-transfer.md: PKXFER1 freezes an opt-in QEMU-only one-way transfer while preserving the default stop-before-transfer build",
        "runs/native-kernel-transfer-readiness.json: 2/2 exact PooleKernel builds, 2/2 feature-enabled PooleBoot builds plus one default isolation build, 2/2 exact media generations and fresh-vars QEMU/OVMF runs, 30 ordered markers, exact serial/debugcon and PBP1 agreement, 58/58 hostile controls, live nine-file PKREVAL1 execution, and terminal unsigned denial with zero authority, actions, writes, signatures, or post-exit firmware calls",
    ],
   "N6": [
        "Cycle 169 re-executes the unchanged 243-test Cycle 168 kernel through two PKXFER1 entries and nine-file revalidation before unsigned-policy halt. Kernel bytes are unchanged; production entry and N6 exit remain open.",
       "Cycle 168 qualifies the 147-page, 1321-relocation kernel with 243 host tests, 43 ELF negative controls and two clean same-host builds. Build identity and mapping diagnostics are synchronized. See docs/checkpoints/cycle168-ap-ownership-qualification.md; earlier entries below are historical.",
        "Cycle 162 PKENTRY1: 228 host tests, 43 controls, two clean identical builds, canonical 525976 bytes, memory 598016 bytes, 1319 relocations, SHA256 D0AA3295F66AF02D48476BCEDC44D962A873E98FBA21F48A6753AA7BB9B24EA4. Earlier image identities below are historical, not current proof",
        "specs/native-kernel-entry-contract.json and docs/native-kernel-entry.md: PKENTRY1 transfer, mapping, diagnostic, panic, build, and explicit nonclaim boundary",
        "native/kernel: real freestanding PooleKernel product with fixed entry assembly, allocation-free PBP1 intake and PKREVAL1 retained-byte verifier, static early ring, bounded COM1 candidate, optional volatile framebuffer sink, and terminal panic path",
        "runtime/native_kernel_image.py: fail-closed pinned-LLD input validation and deterministic PKELF1 canonicalization",
        "runs/native_kernel_entry_readiness.json: Cycle 158 candidate with 219/219 host tests, 2/2 exact clean linked and canonical builds, 43/43 hostile controls, 1,305 relative relocations, exact independent Rust/Python loaded bytes, and canonical SHA-256 18EDADA10E141DBADA8C95C1C0B3454696122C5E96C528F45E0AECE6ADD2F07D; independently rebuilt again inside Cycle 159 boot-chain, Cycle 160 N7 and Cycle 161 memory-through-lock qualification",
        "specs/native-boot-digest-provider.json: PBDIGEST1 pins vendored RustCrypto sha2 0.11.0, the soft-compact UEFI backend, locked transitive packages, and reproducible /pooleos/native source-path remapping while retaining independent security review and provider promotion as open",
        "ADD-BOOT-003: boot-time digest-provider pinning, reproducible path remapping, qualification, independent review, and target-backend promotion boundary",
        "ADD-KERNEL-001: explicit temporary framebuffer identity mapping, cache-policy preservation, lifetime, replacement, and revocation dependency",
    ],
    "N7": [
        "Cycle 170: five current trap/CPU/xstate/MSR receipts qualify the unchanged Cycle 168 kernel with fourteen fresh headless boots, 225 marker controls and 42 focused Python tests. One expected TCG diagnostic is separate. The stale trap gate identity pins are repaired and 17 aggregate-gate cases reject stale identity or production/authority claims. Selected projection14/27;13 downstream checks plus prior SMP new-artifact replay remain. Next is N9-PMM-ACPI-CONSUMER-001; no N7 closure or target claim.",
        "Cycle 169 boot-chain replay is complete. Next is N7-TRAP-001 and ordered CPU/xstate/MSR qualification; pure errata evidence remains source-current.",
       "Cycle 168 changes kernel bytes, so CPU/trap/xstate/MSR execution evidence requires dependency replay. The independent pure errata-policy check remains current. Earlier entries below are historical.",
        "Cycle 164: docs/checkpoints/cycle164-cpu-replay.md binds five current-kernel trap/CPU/xstate/MSR profiles, fourteen successful headless boots and 225 marker controls. One expected TCG exception non-delivery diagnostic is separate from the two successful WHPX exception runs. All 41 focused N7 tests pass, including unchanged pure PKERR1 policy tests. Each live qualifier also passes 228 kernel host tests. The selected projection passes 13/27; fourteen memory-through-lock checks and full exact-final qualification remain pending. Native kernel bytes and N7 phase status are unchanged",
        "Historical Cycle 160 current-source replay: five live profiles contain fourteen successful fresh headless boots and 225 marker controls, with one expected TCG exception non-delivery diagnostic separately recorded. All 41 focused N7 Python tests and twelve selected N5/N7 gates pass on unchanged kernel SHA256 18EDADA10E141DBADA8C95C1C0B3454696122C5E96C528F45E0AECE6ADD2F07D. PKCPU1 now rejects 28 recorded-evidence and eight summary/gate mutation cases after a genuine failing precheck, repair and requalification. Fourteen downstream native checks and full qualification remain pending; no N7 exit or production claim",
        "Cycle 155 current-source replay: fourteen fresh QEMU/OVMF boots across PKTRAP1 (six), PKCPU1, PKXSTATE1, PKXEXC1 and PKMSR1 (two each), 225 marker controls and 41 focused Python tests pass on kernel SHA256 BDEECCB27B1B91406911F91169B9BF5F9DF0439BB39FA0E1882C07E1AF3B81EF. The unchanged PKERR1 receipt remains current. PKTRAP1 also rejects 25 recorded-evidence mutations and eight release-boundary controls. No native executable bytes, authority, target or production status change",
        "ADD-N36-RECEIPT-COVERAGE-001 / FLAG-N36-RECEIPT-COVERAGE-001 preserve the cross-profile receipt audit: Cycle 155 repairs PKTRAP1 and Cycle 160 repairs PKCPU1 recorded consistency only. Neither certifies other validators, authenticates observations or replaces fresh execution",
        "specs/native-kernel-trap-contract.json and docs/native-kernel-trap.md: PKTRAP1 freezes a BSP-only QEMU development boundary for GDT/TSS/IDT installation, uniform integer trap frames, three deliberate returning exceptions, terminal double-fault containment, and explicit semantic malformed-frame rejection",
        "native/kernel/src/arch/x86_64.rs and native/kernel/src/main.rs: five-entry BSP GDT, 104-byte TSS, 256-entry IDT allocation with five present gates, distinct 8192-byte IST1/IST2 arrays, 176-byte normalized frame, descriptor/control-state readback, exact deliberate origins, and terminal fail-closed handlers",
        "runs/native-kernel-trap-readiness.json: 3 scenarios, 6 fresh-vars QEMU/OVMF runs, exact per-scenario serial/debugcon markers, screenshots, and PBP1 bytes, 3 returning exceptions, 1 terminal processor-delivered double fault, 1 semantic malformed-frame rejection, and 51/51 hostile controls with zero authority or effects",
        "specs/native-kernel-cpu-policy-contract.json and docs/native-kernel-cpu-policy.md: PKCPU1 freezes a bounded BSP-only, read-only QEMU policy for required CPUID leaves and features, CR0/CR4/EFER state, XCR0, APIC/PAT/MTRR MSRs, topology, address widths, and explicit no-write/no-authority boundaries",
        "native/kernel/src/arch/x86_64.rs, native/kernel/src/lib.rs, and native/kernel/src/main.rs: support-gated CPUID, control-register, XGETBV, and RDMSR observation plus allocation-free policy validation and an opt-in selector-4 terminal development profile",
        "runs/native-kernel-cpu-policy-readiness.json: 228/228 kernel host tests, 2 exact fresh-vars qemu64 QEMU/OVMF runs, 35 ordered markers, 41/41 hostile controls, exact Rust/Python agreement, AuthenticAMD family 15 model 107 stepping 1 observation, 5 MSR reads, zero MSR writes, and zero authority or actions",
        "specs/native-kernel-errata-policy-contract.json and docs/native-kernel-errata-policy.md: PKERR1 freezes exact Ryzen 7 9800X3D identity, mandatory features, board-lineage-specific BIOS floors, AMD-SB-7033 and AMD-SB-7055 AGESA floors, RDSEED policy, source applicability, and explicit no-authority boundaries",
        "native/cpupolicy and runtime/native_kernel_errata_policy.py: independent allocation-free no_std Rust and Python pure-policy evaluators with ten fail-closed reason bits and no privileged or mutating path",
        "runs/native-kernel-errata-policy-readiness.json: 6/6 Rust tests, both no_std targets, 128 cross-language vectors, 24/24 hostile controls, seven exact source records, homogeneous 16-record read-only Windows metadata, and exact six-reason current denial with zero privileged reads, writes, authority, or actions",
        "specs/native-kernel-xstate-policy-contract.json and docs/native-kernel-xstate-policy.md: PKXSTATE1 freezes eager standard-format x87/SSE ownership, XCR0 0x3, XSS zero, 4,096-byte aligned images, canonical FCW/MXCSR state, context-switch preconditions, sensitive-image clearing, and kernel-SIMD prohibition",
        "runs/native-kernel-xstate-policy-readiness.json: 228/228 kernel host tests, two exact fresh-vars EPYC-Rome-v4 x87/SSE QEMU/OVMF runs, 35 markers, 43/43 hostile controls, two context saves, four restores, 8,192 cleared image bytes, three bounded control writes, zero authority, and explicit scheduler/SMP/target nonclaims",
        "specs/native-kernel-xstate-exception-contract.json and docs/native-kernel-xstate-exception.md: PKXEXC1 freezes deliberate #MF/#XM delivery and exact recovery plus terminal test-only #NM eager-policy rejection under a hardware-accelerated one-BSP development boundary",
        "runs/native-kernel-xstate-exception-readiness.json: two exact fresh-vars WHPX QEMU/OVMF runs, one expected TCG limitation probe, 41 markers, 43/43 hostile controls, three processor-delivered exceptions, two exact recoveries, one terminal #NM rejection, linked machine-code scope audit, four bounded configuration writes, two recovery writes, zero authority, and explicit scheduler/SMP/target nonclaims",
        "specs/native-kernel-privilege-msr-policy-contract.json and docs/native-kernel-privilege-msr-policy.md: PKMSR1 freezes a read-only qemu64 BSP policy for system-linkage, FS/GS, support-gated TSC_AUX, global machine-check, and unsupported-PMU state without activation",
        "runs/native-kernel-privilege-msr-policy-readiness.json: two exact fresh-vars TCG QEMU/OVMF runs, 35 markers, 47/47 hostile controls, 11 support-gated MSR reads, ten observed MCA banks, zero bank reads, zero runtime writes, and an exact linked-image audit of 43 RDMSR and three WRMSR sites that isolates PKSMP1, PKSMP2, PKSMP5/PKSCHED4, PKSCHED1, PKSCHED2, PKSCHED3, and PKIRQ1 accesses from the read-only PKMSR1 profile, with zero authority and explicit emulator/target/production nonclaims",
    ],
    "N8": [
        "Cycle 171: docs/checkpoints/cycle171-native-dependency-replay.md records 28 final headless boots across fourteen current-kernel profiles, 660 control groups and 2126 rejected cases. All 27 selected native checks pass; current SMP boot-artifact binding and malformed-dependency rejection are repaired. Full exact-final qualification and broader N8 exit remain open.",
        "Cycle 170 completes N7 replay; IRQ, first-AP and per-CPU runtime still need replay. Prior Cycle 168 SMP evidence remains bounded to declared source inputs and the prior boot artifacts; replay with current artifacts and audit transitive binding coverage before whole-candidate qualification.",
        "Cycle 169 changes the boot artifact set without changing kernel bytes. The prior two AP boots remain bounded Cycle 168 evidence, not fresh Cycle 169 runs. Replay SMP against current boot inputs and audit transitive source coverage during N8 qualification.",
       "Cycle 168 qualifies two exact four-vCPU PKSMP5 runs with mandatory AP runtime/stack/frame retention, partial rollback, full startup, 27/18 release rejections per attempt, 249 negative cases and complete cleanup. No general topology, hardware quiescence or N8 exit follows. Earlier entries below are historical.",
        "Cycle 165 replays the existing IRQ/time, AP startup, per-CPU runtime and PKSMP5 profiles on the unchanged 228-test kernel. All fourteen memory-through-lock profiles pass 28 final boots, 660 control groups and 2120 rejected cases. No N8 exit or general SMP claim follows; earlier-cycle evidence below retains its historical scope",
        "Cycle 161 completes all fourteen downstream profile receipts: 28 final successful headless boots, 658 control groups, 2,118 rejected cases and 219 kernel host tests per qualifier. All 26 selected native checks and the 105-check/708-Doctor/917-test pre-closeout canonical suite pass. Two overlapping scheduler boots are excluded and replaced by a frozen-source rerun. No native Rust or frozen-demo bytes change; N0 custody, N12.3 active-root/execution-stack/CPU-retirement ownership and the broader N36 schema/evidence audit remain open. Exact-final qualification, publication and review checks are required before a main merge; no production promotion is claimed.",
        "specs/native-kernel-interrupt-time-contract.json and docs/native-kernel-interrupt-time.md: PKIRQ1 freezes a bounded one-BSP qemu64 xAPIC/HPET transaction, complete retained MADT/HPET parsing, vector ownership, guarded uncacheable MMIO, exact local timer delivery and EOI accounting, normal-path rollback, and explicit no-AP/no-IPI/no-target/nonproduction boundaries",
        "native/kernel/src/interrupt_time.rs, native/kernel/src/arch/x86_64.rs, and native/kernel/src/main.rs: allocation-free MADT/HPET parsing and checked clock arithmetic, typed APIC/PIC/IDT/MSR operations, selector-11 controller transaction, eight interrupt windows, and exact controller/clock/PIC/MSR/MMIO restoration",
        "runs/native-kernel-interrupt-time-readiness.json: 219/219 kernel host tests, two exact fresh-vars qemu64 QEMU/OVMF runs, 36 ordered markers, 58/58 hostile controls, eight timer deliveries, eight EOIs, zero APIC-error or spurious deliveries, three absent MMIO guards, exact LAPIC/HPET mapping revocation, zero AP starts, and zero signatures, authority, actions, or production claims",
        "specs/native-kernel-smp-first-ap-contract.json and docs/native-kernel-smp-first-ap.md: PKSMP1 freezes one bounded xAPIC first-AP lifecycle with a below-1-MiB RX trampoline, pre-accessed GDT, guarded RW/NX stack and mailbox, INIT-SIPI-SIPI startup, observed long-mode state, stop/quiesce/final-INIT park, exact scrub/release, and explicit no-general-SMP/no-IPI/no-shootdown/no-target/nonproduction boundaries",
        "native/kernel/src/smp.rs, native/kernel/src/arch/x86_64.rs, and native/kernel/src/main.rs: allocation-free first-AP selection and transaction model, 16-to-32-to-64-bit trampoline, two-vCPU selector-12 live path, fail-closed final-park ownership retention, alias revocation, and exact resource cleanup",
        "runs/native-kernel-smp-first-ap-readiness.json: 219/219 kernel host tests, two exact fresh-vars two-vCPU qemu64 QEMU/OVMF runs, 38 ordered markers, 72/72 hostile controls, exactly one AP started/online/quiesced/parked, fourteen pages and 57,344 bytes scrubbed/verified/released, and zero signatures, authority, target, N8-exit, or production claims",
        "specs/native-kernel-smp-percpu-runtime-contract.json, native/kernel/src/smp_runtime.rs, runtime/native_kernel_smp_percpu_runtime.py, and docs/native-kernel-smp-percpu-runtime.md: PKSMP2 freezes one AP-local runtime transaction with processor-local GDT/TSS/IDT, guarded RSP0/IST stacks, x87/SSE xstate ownership, interrupt-vector ownership, final INIT parking, exact scrub/release, and explicit no-IPI/no-shootdown/no-scheduler/no-target/nonproduction boundaries",
        "runs/native-kernel-smp-percpu-runtime-readiness.json: 219/219 kernel host tests, two exact fresh-vars two-vCPU SandyBridge-minus-AVX TCG QEMU/OVMF runs, 42 ordered markers, 19/19 hostile-control categories covering 159 rejected cases, exactly one AP-local descriptor set, three guarded stack classes, 27 gates, one xstate round trip, and 32 pages or 131,072 bytes scrubbed/verified/released with zero signatures, authority, N8-exit, or production claims",
        "specs/native-kernel-smp-ipi-contract.json, native/kernel/src/smp_ipi.rs, runtime/native_kernel_smp_ipi.py, and docs/native-kernel-smp-ipi.md: PKSMP5 freezes one exact four-vCPU/three-AP topology with private AP runtimes, dynamic local masks, aggregate target and acknowledgement mask 0xE, partial-start timeout and complete rollback, fresh retry, six fixed development IPI classes per AP, three generation-bound one-page remote invalidations, deferred-reclaim ordering, exact cleanup, and explicit no-general-topology/no-general-shootdown/no-scheduler/no-target/nonproduction boundaries",
        "runs/native-kernel-smp-ipi-readiness.json: 219/219 kernel host tests, two exact fresh-vars four-vCPU SandyBridge-minus-AVX TCG QEMU/OVMF runs, 40 ordered markers, 30/30 hostile-control categories covering 243 rejected cases, three APs simultaneously online, nine accepted and three denied live deliveries, twelve EOIs, one partial-start timeout and rollback, one fresh retry, three exact AP-side INVLPG operations, aggregate target/ack mask 0xE, one retired generation, two premature-reclaim rejections, and 102 pages or 417,792 bytes scrubbed/verified/released with zero signatures, authority, N8/N9-exit, or production claims",
    ],
    "N9": [
        "Cycle 171: docs/checkpoints/cycle171-native-dependency-replay.md records 28 final headless boots across fourteen current-kernel profiles, 660 control groups and 2126 rejected cases. All 27 selected native checks pass; current SMP boot-artifact binding and malformed-dependency rejection are repaired. Full exact-final qualification and broader N9 exit remain open.",
        "Cycle 170 completes current-kernel boot/CPU dependencies. Next is N9-PMM-ACPI-CONSUMER-001 then VM replay, with no new memory ownership or phase completion claim.",
        "Cycle 169 boot-chain receipts are refreshed. PMM and VM still need current dependency replay; no memory-phase closure or native ownership expansion is claimed.",
       "Cycle 168 retains every AP runtime and both frames through possible execution and fallible scrubbing. The active-root/PMM/direct-map profiles need replay on the new image; general VM and data-frame hygiene remain open. Earlier entries below are historical.",
        "Cycle 165: docs/checkpoints/cycle165-native-dependency-replay.md records four final PKPMM7/PKACPI1 and PKVM3 boots, 239 control groups and 228 kernel tests per qualifier. Source usable/loader protected/final managed pages are 117820/924/129080. VM owns 117819 mapped pages with 12946 holes and 243 tables, six retained-free rejections, three local invalidation receipts and one retirement. Current transfer dependence is requalified. Corrected geometry and data-release documentation do not implement data-frame scrub-before-reuse, concurrency, hardware or N9 exit",
        "Historical Cycle 162 PKVM3: mandatory active table/data retention, six copied-handle free rejections in each of two exact headless boots, 40 markers and 48 controls, three local invalidation receipts and one exact generation retirement. PMM cleanup preserves ownership on failed insertion, metadata or wrong-manager paths. Cycle 163 replaces its transfer dependency, so this VM receipt now requires replay; PMM and SMP evidence below also needs changed-image replay",
        "Cycle 161 completes all fourteen downstream profile receipts: 28 final successful headless boots, 658 control groups, 2,118 rejected cases and 219 kernel host tests per qualifier. All 26 selected native checks and the 105-check/708-Doctor/917-test pre-closeout canonical suite pass. Two overlapping scheduler boots are excluded and replaced by a frozen-source rerun. No native Rust or frozen-demo bytes change; N0 custody, N12.3 active-root/execution-stack/CPU-retirement ownership and the broader N36 schema/evidence audit remain open. Exact-final qualification, publication and review checks are required before a main merge; no production promotion is claimed.",
        "Historical Cycle 156 current-source replay: N9-PMM-ACPI-CONSUMER-001 and N9-VM-DIRECT-MAP-001 pass four final headless QEMU/OVMF boots and 237 negative controls on the unchanged Cycle 153 kernel. The manager contract is 15632 bytes; old-size contract and marker controls reject. Independent PBP1 accounting proves the one-page usable-to-loader shift, current sparse coverage and address-bound checksums. Thirty-two existing allocator host tests pass. Allocation retention does not itself exclude direct-map admission. No N9 exit, general concurrent lifetime, authenticated evidence or production claim follows",
        "specs/native-kernel-physical-memory-contract.json, specs/native-kernel-physical-memory-contract.schema.json, and docs/native-kernel-physical-memory.md: PKPMM7 freezes exact PBLIVE4/PBP1 intake, UEFI source-kind validation, usable-only initial ownership, page-zero exclusion, DMA/DMA32/Normal zones, generation-safe scrubbed transactions, a stable five-page guarded manager, external generation-owned guarded active ledgers, checked pressure-triggered repeated growth, bounded-window fallback/rejection, PKACPI1 required-table validation and retained snapshot copying, and two separately lifecycle-gated reclaim receipts without AML, concurrency, interrupt-context, SMP, target, or production claims",
        "native/kernel/src/acpi.rs, native/kernel/src/physical_memory.rs, native/kernel/src/main.rs, native/boot/src/livehandoff.rs, runtime/native_kernel_physical_memory.py, tools/qualify_native_kernel_physical_memory.py, and tests/test_native_kernel_physical_memory.py: allocation-free no_std ACPI/PMM path; canonical firmware RSDP handoff; RSDP/XSDT checksum, range, signature, uniqueness, length, copy, readback, and rollback validation; retained scrubbed snapshot; opaque evidence-gated AcpiTablesReleased transition; dual streamed reclaim; generation growth/retirement; independent transcript/oracle validation; and host malformed, duplicate, allocation, copy, readback, rollback, early-reclaim, and idempotence controls",
        "runs/native-kernel-physical-memory-readiness.json: Cycle 161 passes 2/2 exact qemu64 QEMU/OVMF runs, 45 ordered markers, 191/191 hostile controls and 219/219 kernel host tests; 98 PBP1 entries, 117,822 usable source pages and 129,082 final managed pages. PKACPI1 validates RSDP/XSDT and APIC/FACP/HPET/MCFG, copies 600 bytes into a retained one-page 616-byte snapshot, and binds source/snapshot checksums 078583AEEFDD6581/4089A5CFEC81CB41. Boot reclaim admits 11,250 pages under receipt 5DEA9A3BC9E10C18; ACPI reclaim admits 11 only after validation/copy/readback under receipt 60DAA52A8A05ABD6. The 15,632-byte manager remains five guarded pages; growth spans 4/8/15/29 pages, retires three predecessors totaling 27 pages (last predecessor 15), records 119 checks, seven triggers, 59 cycles, three soft fallbacks and one hard pre-effect rejection; growth checksum 0xC75C03982EE3474D. The runs protect 922 loader pages, scrub/verify 11,473 pages and 46,993,408 bytes, perform 5,875,277 writes, 5,879,957 reads and 23,172 temporary PTE writes/invalidations with zero signatures, authority, actions, AML, concurrent/SMP allocation, target or production claims",
        "specs/native-kernel-virtual-memory-contract.json and docs/native-kernel-virtual-memory.md: PKVM3 freezes the 48-bit candidate-root layout, exact inherited kernel/entry/guarded-stack/handoff mappings, PMM-derived sparse direct-map ownership and write-back cache policy, dynamic topology, CR3 activation/rollback, architectural Accessed/Dirty handling, local invalidation receipts, exact one-BSP generation-retirement receipts, and future SMP-shootdown rejection",
        "native/kernel/src/active_virtual_memory.rs, native/kernel/src/main.rs, runtime/native_kernel_virtual_memory.py, tools/qualify_native_kernel_virtual_memory.py, and tests/test_native_kernel_virtual_memory.py: fixed-capacity no_std active-root core, privileged volatile CR3/INVLPG adapter, independent PBP1 first-fit oracle, source audit, host rollback/fault tests, and bounded selector-10 evidence; the selector-9 PKVM1 inactive foundation remains its predecessor",
        "runs/native-kernel-virtual-memory-readiness.json: Cycle 161 passes 2/2 exact qemu64 QEMU/OVMF runs, 40 ordered markers, 46/46 hostile controls and 219/219 kernel host tests; 117,821 admitted pages in eleven ranges with 12,944 hole pages, 237 direct leaf tables, one direct directory and 243 table pages, checksum 0x64E09067B6BFDCB3, 367,408 physical table writes, 950,682 temporary-PTE writes and invalidations, two CR3 writes, three local invalidation receipts, one exact generation-retirement receipt, zero remote shootdowns, signatures, authority or actions",
        "runs/native-kernel-smp-ipi-readiness.json: PKSMP5 records two exact 40-marker four-vCPU runs, 30/30 hostile-control categories covering 243 rejects, three private AP-owned roots and one page per root, three executions of one linked-image-audited AP-side INVLPG instruction, aggregate target/ack mask 0xE, generation 1-to-2 retirement, two premature-reclaim rejections, one partial-start timeout and complete rollback, one fresh retry, and exact scrub/release of 102 pages or 417,792 bytes without general topology/shootdown, scheduler, target, authority, N8/N9-exit, or production claims",
        "ADD-MEM-001: one cross-stage bootstrap stack, guard, root-table, handoff, kernel-image, and allocator-metadata boundary shared by PooleBoot, PBP1, PKMAP2, PooleKernel entry, trap handling, and PMM ownership",
        "ADD-MEM-002: replace the bounded nine-page PKVM2 mapping with one complete generation-owned sparse physical direct map that excludes holes and forbidden ranges, prevents incompatible cache aliases, preserves retained bootstrap and ACPI snapshot exclusions, switches transactionally, records local invalidation and future SMP-shootdown dependencies, and defers reclamation until exact generation receipts permit it",
    ],
    "N12": [
        "Cycle 172: docs/checkpoints/cycle172-task-stack-ownership.md qualifies mandatory inactive PKSTACK1 stack ownership with 34 lifecycle tests per host profile, explicit scrub failure/capacity retention and no live context claim. All 27 selected native checks pass; full current canonical qualification remains pending. Guarded mappings, CPU retirement and automatic scrub-receipt growth integration stay open under ADD-N12-CONCURRENCY-RECLAMATION-001.",
        "Cycle 171: docs/checkpoints/cycle171-native-dependency-replay.md records 28 final headless boots across fourteen current-kernel profiles, 660 control groups and 2126 rejected cases. All 27 selected native checks pass; current SMP boot-artifact binding and malformed-dependency rejection are repaired. Full exact-final qualification and broader N12 exit remain open.",
        "Cycle 170 preserves Cycle 168 AP ownership and requalifies traps/CPU state. Scheduler/atomics/locks still require dependency replay after memory/IRQ/SMP. General execution-stack and CPU-retirement ownership remain open.",
        "Cycle 169 preserves Cycle 168 AP ownership and kernel bytes while requalifying N5. General task-stack and CPU-retirement ownership, downstream scheduler replay and the new-boot-artifact AP replay remain open.",
       "Cycle 168 qualifies bounded PKAPOWN1 execution ownership in the real three-AP path: 243 kernel, 20 retention, 11 AP-owner, 24 lifetime, 19 pool and nine compile-fail tests; two final guest runs observe both partial/full attempt controls. General task-stack/CPU retirement and N12.3 remain open. Earlier entries below are historical.",
        "Cycle 165 replays all six scheduler profiles, atomics and locks on the unchanged mandatory active-retention kernel. Three profiles are rerun after test-only expectation corrections; six superseded initial boots are excluded from the final 28 dependency boots. All27 selected native checks pass. Full runtime-inclusive qualification still precedes merge and further N12.3 execution-stack/general CPU-retirement ownership; earlier-cycle evidence below is historical",
        "Cycle 162: 228 kernel tests, 16 PMM retention cases, 24 lifetime and 19 pool tests in both host modes, seven compile-fail checks, plus two real PKVM3 boots qualify active table/data ownership. N12.3 execution stacks, general CPU retirement, independent lifecycle oracle and exact-topology live failure evidence remain open. Prior bounded scheduler/atomic/lock qualifications below need changed-image replay",
        "Cycle 161 completes all fourteen downstream profile receipts: 28 final successful headless boots, 658 control groups, 2,118 rejected cases and 219 kernel host tests per qualifier. All 26 selected native checks and the 105-check/708-Doctor/917-test pre-closeout canonical suite pass. Two overlapping scheduler boots are excluded and replaced by a frozen-source rerun. No native Rust or frozen-demo bytes change; N0 custody, N12.3 active-root/execution-stack/CPU-retirement ownership and the broader N36 schema/evidence audit remain open. Exact-final qualification, publication and review checks are required before a main merge; no production promotion is claimed.",
        "Historical Cycle 157 qualification superseded the historical pending-replay statements below: 24 final boots across all twelve IRQ/SMP/scheduler/atomic/lock profiles, 1881 negative cases, 214 kernel host tests and the 105-gate/708-Doctor/917-test suite pass. The repaired bounded PKLOCK1 milestone closes again; N12.3 ownership and live failure evidence remain open",
        "specs/native-kernel-scheduler-contract.json and docs/native-kernel-scheduler.md: PKSCHED1 freezes a bounded allocation-free four-CPU/eight-task scheduler foundation, neutral fixed-priority round-robin policy, maximum bypass bound, task lifecycle, affinity, migration, cancellation, timeout, accounting, one-mutex direct priority inheritance, reference lifetime, raw spinlock, context-state, stack, cleanup, and strict cooperative-BSP nonclaims",
        "native/kernel/src/scheduler.rs, native/kernel/src/arch/x86_64.rs, native/kernel/src/main.rs, and native/kernel/src/bin/pksched1_probe.rs: generation-safe fixed-capacity scheduler core, host stress probe, and exact 18-instruction live context switch over two isolated 16-KiB kernel stacks",
        "runtime/native_kernel_scheduler.py, tools/qualify_native_kernel_scheduler.py, and tests/test_native_kernel_scheduler.py: independent deterministic scheduler oracle, marker and linked-image audits, source controls, model overlap, hostile mutations, and exact receipt validation",
        "runs/native-kernel-scheduler-readiness.json: 14/14 scheduler Rust tests within 219/219 kernel host tests, four exact Rust/Python host-probe receipts over 4,096 steps, 1,761 dispatches and 2,334 migrations, two exact 17-marker qemu64 BSP runs, eight live dispatches, sixteen context transitions, 32,768 stack bytes cleared, and 28/28 hostile-control categories covering 115 rejected cases with zero live AP dispatch, ring-3/address-space switch, authority, N12-exit, or production claims",
        "ADD-N12-SCHED-FOUNDATION-001: preserve exact task identity, ownership, fairness, lifecycle, synchronization, context, stack, and cleanup boundaries while separating this cooperative BSP foundation from later interrupt-preemptive, SMP, ring-3, address-space, and production promotion",
        "specs/native-kernel-scheduler-preemption-contract.json, native/kernel/src/scheduler_preempt.rs, runtime/native_kernel_scheduler_preempt.py, tools/qualify_native_kernel_scheduler_preempt.py, tests/test_native_kernel_scheduler_preempt.py, and docs/native-kernel-scheduler-preemption.md: PKSCHED2 freezes bounded BSP timer/wakeup preemption, exact interrupt-frame and task-stack ownership, an eight-event deferred-reschedule controller, deterministic quantum/wake/block ordering, balanced EOI and rollback rules, teardown, cleanup, and strict no-live-AP/no-ring-3/no-address-space/no-target/nonproduction boundaries",
        "runs/native-kernel-scheduler-preemption-readiness.json: 7/7 focused preemption tests within 219/219 kernel host tests, three exact Rust/Python host-probe receipts, two exact 35-marker selector-16 qemu64 BSP runs, six timer windows and EOIs, task trace 0,1,2,0,3,3, six saved and four restored interrupt frames, four hardware switches, 65,536 stack bytes cleared, and 25/25 hostile-control categories covering 178 rejected cases with zero live AP dispatch, ring-3/address-space switch, authority, N12-exit, or production claims",
        "ADD-N12-SCHED-PREEMPT-001: preserve exact timer/event/frame/context/stack/EOI/rollback/cleanup ownership while separating bounded BSP preemption from deferred workers, SMP, ring-3, address-space, target, and production promotion",
        "specs/native-kernel-scheduler-deferred-contract.json, native/kernel/src/scheduler_deferred.rs, runtime/native_kernel_scheduler_deferred.py, tools/qualify_native_kernel_scheduler_deferred.py, tests/test_native_kernel_scheduler_deferred.py, and docs/native-kernel-scheduler-deferred.md: PKSCHED3 freezes an allocation-free eight-slot deferred-work controller, generation-safe identity, fixed typed operations, duplicate suppression, EOI-gated dispatch, two retained-memory BSP worker stacks, bounded priority bypass, queued/running cancellation, flush watermarks, five rollback boundaries, exact shutdown, and strict no-callback/no-consumer/no-live-AP/no-ring-3/no-target/nonproduction boundaries",
        "runs/native-kernel-scheduler-deferred-readiness.json: 7/7 focused deferred-work tests within 219/219 kernel host tests, five exact Rust/Python host-probe receipts, two exact 37-marker selector-17 qemu64 BSP runs, eight enqueues, six worker dispatches, twelve context transitions, five completions, three cancellations, five fault rollbacks, 32,768 stack bytes cleared, and 30/30 hostile-control categories covering 208 rejected cases with zero arbitrary callbacks, driver/service consumers, live AP dispatch, authority, N12-exit, or production claims",
        "ADD-N12-SCHED-DEFERRED-001: preserve exact queue/work/receipt/generation/EOI/cancellation/flush/rollback/shutdown/stack-cleanup ownership while separating bounded BSP deferred work from arbitrary callbacks, driver/service consumers, SMP, ring-3, target, and production promotion",
        "specs/native-kernel-scheduler-smp-contract.json, native/kernel/src/scheduler_smp.rs, runtime/native_kernel_scheduler_smp.py, tools/qualify_native_kernel_scheduler_smp.py, tests/test_native_kernel_scheduler_smp.py, and docs/native-kernel-scheduler-smp.md: PKSCHED4 freezes one allocation-free exact-topology four-CPU/eight-task scheduler with acknowledgement-gated ownership, generation-safe wake/migration, six live AP dispatches, bounded fairness, offline timeout rollback, exact cleanup, and strict no-general-SMP/no-ring-3/no-target/nonproduction boundaries",
        "runs/native-kernel-scheduler-smp-readiness.json: 8/8 focused SMP scheduler tests within 219/219 kernel host tests, five exact Rust/Python host-probe receipts, two exact 37-marker four-vCPU selector-18 runs, one cross-CPU wake, two migrations, three transaction acknowledgements, six AP dispatches, one APIC-4 timeout rollback, two stale acknowledgement rejections, eight task retirements, and 32/32 hostile-control categories covering 209 rejected cases; 102 pages or 417,792 bytes are scrubbed, verified, and released",
        "ADD-N12-SCHED-SMP-001: exact-topology AP-local run queues, remote reschedule acknowledgement, generation-safe cross-CPU wake/migration, offline timeout rollback, topology balancing, idle ownership, and exact teardown close only for PKSCHED4's bounded development profile",
        "ADD-N12-SCHED-AP-WORKERS-001: extend PKSCHED3 deferred work to AP-local workers and real driver/service consumers with remote cancellation, flush, reclamation, offline rollback, starvation, and cleanup evidence",
        "specs/native-kernel-scheduler-ap-workers-contract.json, native/kernel/src/scheduler_ap_workers.rs, runtime/native_kernel_scheduler_ap_workers.py, tools/qualify_native_kernel_scheduler_ap_workers.py, tests/test_native_kernel_scheduler_ap_workers.py, and docs/native-kernel-scheduler-ap-workers.md: PKSCHED5 freezes three allocation-free AP-local workers, two fixed typed timer-driver and generation-reclaim consumers, EOI-gated dispatch, remote cancellation, flush/reclamation ordering, offline rollback, bounded starvation, exact cleanup, and strict no-arbitrary-callback/no-general-preemption/no-target/nonproduction boundaries",
        "runs/native-kernel-scheduler-ap-workers-readiness.json: 10/10 focused AP-worker tests within 219/219 kernel host tests, six exact Rust/Python host-probe receipts, two exact 37-marker four-vCPU selector-19 runs, thirteen enqueues, twelve typed AP calls, eleven completions, two cancellations, one offline timeout rollback, thirteen reclaimed slots, and 34/34 hostile-control categories covering 226 rejected cases; three workers retire and all 102 pages or 417,792 bytes are scrubbed, verified, and released",
        "ADD-N12-SCHED-SMP-PREEMPT-001: compose PKSCHED2 timer/wakeup preemption with PKSCHED4/PKSCHED5 exact-topology CPU and worker ownership, including per-CPU timers, remote reschedule acknowledgement, concurrent event ordering, offline rollback, watchdog/latency bounds, and exact teardown without claiming general topology, ring 3, target, N12 exit, or production",
        "specs/native-kernel-scheduler-smp-preempt-contract.json, native/kernel/src/scheduler_smp_preempt.rs, runtime/native_kernel_scheduler_smp_preempt.py, tools/qualify_native_kernel_scheduler_smp_preempt.py, tests/test_native_kernel_scheduler_smp_preempt.py, and docs/native-kernel-scheduler-smp-preempt.md: PKSCHED6 freezes bounded exact-topology per-CPU timer/event/frame/run-queue ownership, acknowledgement-gated live reschedule IPIs, deterministic cancel/wake/migration ordering, offline rollback, watchdog/fairness bounds, exact cleanup, and strict no-AP-timer/no-general-SMP/no-ring-3/no-target/nonproduction boundaries",
        "runs/native-kernel-scheduler-smp-preempt-readiness.json: 5/5 focused SMP-preemption tests within 219/219 kernel host tests, seven exact Rust/Python host receipts, two exact 38-marker four-vCPU selector-20 runs, eight live reschedule IPIs, five modeled acknowledgements, three quantum switches, one offline rollback, eight task retirements, and 34/34 hostile-control categories covering 232 rejected cases; all 102 pages or 417,792 bytes are scrubbed, verified, and released",
        "ADD-N12-CONCURRENCY-ATOMICS-001: qualify typed atomics and compiler/x86 memory-order contracts before broader locks, reclamation, or SMP scheduler promotion",
        "specs/native-kernel-atomics-contract.json, native/kernel/src/atomics.rs, runtime/native_kernel_atomics.py, tools/qualify_native_kernel_atomics.py, tests/test_native_kernel_atomics.py, and docs/native-kernel-atomics.md: PKATOM1 freezes typed load/store/RMW/fence order domains, nine valid and eleven invalid compare-exchange order pairs, fixed-width and pointer atomics, bounded references, interrupt-context publication, linked-code auditing, deterministic host stress, and strict no-lock/no-reclamation/no-general-SMP/no-target/nonproduction boundaries",
        "runs/native-kernel-atomics-readiness.json: 7/7 focused atomics tests within 219/219 kernel host tests, eight exact host-probe receipts, two exact 41-marker qemu64 selector-21 runs, 4,096 publication rounds with zero stale reads, 16,384 contended fetch-adds plus 4,096 CAS increments with zero lost updates, 2,048 sequentially consistent rounds with zero forbidden outcomes, seven linked audit symbols, and 29/29 hostile-control categories covering 78 rejected cases",
        "ADD-N12-CONCURRENCY-LOCKS-001: build the complete bounded lock family over PKATOM1 with interrupt, preemption, ownership, priority-inheritance, lock-order, teardown, fairness, and rollback evidence before reclamation or broader SMP promotion",
        "specs/native-kernel-locks-contract.json, native/kernel/src/locks.rs, runtime/native_kernel_locks.py, tools/qualify_native_kernel_locks.py, tests/test_native_kernel_locks.py, and docs/native-kernel-locks.md: PKLOCK1 freezes an allocation-free FIFO ticket spinlock, IRQ-save lock, sleeping mutex, notification, writer-preferred reader-writer lock, seqlock, five-rank lock-order graph, direct bounded priority donation, exact owner-death and rollback rules, and strict no-reclamation/no-general-SMP/no-target/nonproduction boundaries",
        "runs/native-kernel-locks-readiness.json: 10/10 focused lock tests within 219/219 kernel host tests, nine exact host-probe receipts including 8,192 FIFO ticket acquisitions, two exact 35-marker four-vCPU SandyBridge selector-22 runs, exact tickets 0,1,2,3 across BSP plus three APs, three installed and revoked shared aliases, and 30/30 hostile-control categories covering 103 rejected cases",
        "runs/native-kernel-reclamation-core-readiness.json: Cycle 150 PKRECLAIM1-CORE owns real values in a bounded no_std pool with pool-bound generation handles, RAII pins, retire-before-reclaim, exact-once transfer, nonwrapping limits, pressure retention and shutdown sealing; 19 tests pass in debug and optimized host profiles, one borrow compile-fail test and 206 kernel regressions pass; freestanding Clippy passes and canonical linked bytes remain unchanged; no live integration or CPU grace-period claim",
        "docs/native-kernel-task-lifetimes.md and runs/native-kernel-reclamation-core-readiness.json: Cycle 152 PKLIFE1 owns the actual PKSCHED4 scheduler and moved inactive PKVM1 address spaces, binds checked task/root generations, retains pinned retired resources, and blocks premature task-slot reuse. Nineteen lifecycle and nineteen core tests pass in each of two host profiles; three borrow compile-fail tests and 206 kernel regressions pass. No new guest selector or physical quiescence evidence is claimed",
        "docs/native-kernel-physical-retention.md: Cycle 153 implements allocator-enforced retention for explicit tokens and stop/park-before-old-frame-release in the three-AP path, including uncertain startup targets in final cleanup. Eight allocator tests within 214 kernel tests, 20 task-lifetime tests, 19 pool tests and five borrowing compile-fail tests pass; the new 144-page image requires complete dependency replay. The first aggregate audit failed 25/105 checks before the final startup-mask repair. This candidate is unmerged and has no current aggregate pass. Mandatory all-task/root/data/stack ownership and independent live retention/failure qualification remain open",
        "FLAG-N12-CONCURRENCY-LOCKS-001: reopened in Cycle 153 after stale-counter sampling produced QueueFull with four host participants; raw and writer-ticket admission now retry changed samples. Replay current-source lock and aggregate evidence before extending N12.3",
        "Cycle 158: Resources::new now mandates PKPMM retention of every inactive PKVM1 root and bound/pending frame. Group acquisition/release validates all members before mutation and preserves complete ownership on late failure. 24 lifetime tests, 19 core tests, 219 kernel regressions including 13 retention cases, seven compile-fail tests and host/freestanding Clippy cover this host-executed contract. Changed kernel bytes require fresh dependency replay; the full Cycle 157 pass is historical. Active roots, execution stacks, raw alias isolation and CPU quiescence remain outside this increment",
        "ADD-N12-CONCURRENCY-RECLAMATION-001: Cycle 162 qualifies mandatory active PKVM3 table/data ownership. Replay changed-image N5-through-N12 prerequisites, then implement execution-stack ownership, acknowledged cross-CPU quiescence, live timeout/offline/death/pressure/shutdown rollback, an independent oracle and exact-topology live evidence before closing N12.3",
    ],
    "N15": ["runs/microkernel_isolation.json", "runs/capability_trap_proof.json", "runs/capability_trap_fuzz.json"],
    "N29": [
        "docs/pooleglass-design-system.md and specs/pooleglass-design-tokens.json: OS-wide visual direction and PG-01 through PG-10 implementation register under FLAG-NATIVE-UI-001; performance budgets are unmeasured targets",
        "demos/native_iso/boot: demo-only static glass emblem and licensed fixed wordmark; four Rust renderer tests, two fresh optical boots and exact guest/host pixels; no native compositor or animation claim",
    ],
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
    "N36": [
        "Cycle 172: docs/checkpoints/cycle172-task-stack-ownership.md records exact stack-test evidence validation with 40 rejection cases and separates the 17-stage host core receipt from historical live AP and canonical qualification. ADD-N36-RECEIPT-COVERAGE-001 remains open; no new live scenario or general evidence audit closure is inferred.",
        "Cycle 171: docs/checkpoints/cycle171-native-dependency-replay.md records 28 final headless boots across fourteen current-kernel profiles, 660 control groups and 2126 rejected cases. All 27 selected native checks pass; current SMP boot-artifact binding and malformed-dependency rejection are repaired. Full exact-final qualification and broader N36 exit remain open.",
        "Cycle 170 adds 17 aggregate N7 gate regression cases after repairing measured stale trap identity pins. Five qualifiers, 14 successful boots and 42 focused tests pass; one expected TCG diagnostic stays separate. Broader recorded-evidence and transitive-input coverage audits remain open.", "Cycle 169 adds failing-then-passing PSYM1 kernel-entry dependency controls, corrects stale aggregate trust hashes and passes 83 focused regressions. Audit shared/transitive input coverage in downstream receipts; no full canonical audit or N36 closure is claimed.", "Cycle 168 fixes split-module test accounting, rejection of failed/ignored named records, AP receipt JSON round-trip consistency and malformed-shape handling. Final receipts pass 56 focused tests and four stale-kernel/ownership gate controls. The wider receipt audit remains open; prior failures are preserved. Earlier entries below are historical.", "Cycle 165 corrects measured PMM accounting pins, eleven host-count/linked-image gate pins, three stale test expectations and memory-guide descriptions. Two new gate tests reject 25 stale/off-by-one cases; fourteen independent production-overclaim controls reject. The 142-test profile/map/gate suite passes with two optional local-transcript skips, while fresh qualifiers validate actual transcripts. Six superseded boots and the pre-pin 16/27 failure projection remain recorded. The broader ADD-N36-RECEIPT-COVERAGE-001 audit stays open", "Cycle 164 corrects a WHPX/TCG profile-description contradiction and stale current summary counts without altering executable contracts. A roadmap regression binds all five N7 receipts to exact hashes, current kernel, boot/control totals and the separately counted TCG diagnostic. ADD-N36-RECEIPT-COVERAGE-001 remains open for the broader schema, cross-profile evidence and independent reproduction audit", "Historical Cycle 163 repairs fixed-day constraints in loader/PooleBoot receipts and validates canonical calendar dates in both runtimes. Six valid and twenty invalid date cases pass through components and release checks; 70 focused Python tests pass. The initial schema-rejected loader attempt is preserved separately. Existing ADD-N36-RECEIPT-COVERAGE-001 still requires broader shared-schema, recorded-evidence, independent-builder and target review", "Historical Cycle 162 requires two recorded PKVM3 runs, six measured retained-free rejections per run, and consistency with the independently derived PMM summary. Six new receipt mutations reject; broader schema/evidence review remains open. Historical Cycle 161 removes two fixed-day scheduler readiness constraints and explicitly validates canonical calendar dates in their runtime validators. Six valid and twenty invalid date cases pass, with rejection checked through both component and release paths. The shared small schema engine still does not enforce pattern/format; its wider audit is not closed. Both changed profiles were actually requalified. The pre-closeout canonical suite passes 105 gates, 708 Doctor checks and 917 discovered tests", "Historical Cycle 160 PKCPU1 recorded-evidence repair: four corruptions were incorrectly accepted before repair; 28 recorded-evidence mutations and eight summary/gate cases now reject, and the changed validator passes actual two-boot requalification. All 41 focused N7 tests pass; broader cross-profile audit and full candidate suite remain open", "Cycle 150 host baseline: TEST_COUNT tests with three expected environment skips", "native binary parser, reproduction, leakage, malformed, substitution, governance, hardware, Tier 0, bounded-model, deterministic boot-media, PBP1/PBC1/PSM1/PBART1, six inner-format, PBTRUST1/PBSTATE1, PKELF1, PKENTRY1, PKLOAD6/PBLIVE4/PKMAP2/PBEXIT1, PKREVAL1, PKXFER1, PKTRAP1, PKCPU1, PKERR1, PKXSTATE1, PKXEXC1, PKMSR1, PKPMM7/PKACPI1, PKVM1, PKVM3, PKIRQ1, PKSMP1, PKSMP2, PKSMP5, PKSCHED1 through PKSCHED6, PKATOM1, and PKLOCK1 source/live/zero-authority controls, PKRECLAIM1-CORE host-only evidence and source-freshness controls, canonical-LF readiness regression controls, PooleGlyph roadmap bindings, Doctor external-report nonmutation, and collector-smoke negatives"],
    "N37": ["Cycle 170 is a five-profile trap/CPU-state checkpoint, not full canonical qualification. Current selected projection14/27; thirteen stale downstream checks plus prior SMP new-boot-artifact replay remain. Keep PR76draft until exact-final qualification, publication and review pass.", "Cycle 169 is a six-component boot-chain checkpoint, not a full qualification. The selected projection passes9/27; 18 downstream checks plus prior SMP boot-artifact replay and exact-final qualification still gate PR76. Main stays qualified Cycle165.", "Cycle 168 is a bounded AP-ownership checkpoint with 4/27 selected checks current and 23 dependencies pending. Main is exact-final qualified Cycle 165, not this changed source. Full qualification, publication and review still gate PR76; no release or production promotion follows. Earlier entries below are historical.", "Cycle 165 has fourteen source-current native dependency receipts and all27 selected native checks passing. Main remains qualified Cycle161; runtime-inclusive exact-final qualification, publication and GitHub review still gate draft PR75. This checkpoint is not a full canonical pass, release or production promotion", "Cycle 164 has five passing N7 live profiles and a 13/27 selected-native projection. Fourteen downstream dependencies and runtime-inclusive exact-final qualification still block main merge. Draft PR75 backs up development; publication and review gates are still required, and historical full audits are not current scores", "Historical Cycle 163 is a source-backed draft checkpoint with six passing N5 components and an 8/27 selected-native projection. Nineteen downstream receipts and runtime-inclusive exact-final qualification still block main merge. The failed Cycle 162 audit is historical, not a current aggregate score", "Historical Cycle 162 is an unmerged changed-image development candidate with 23 stale selected native dependencies. Cloud backup does not establish qualification. Historical Cycle 161 pre-closeout canonical development gate passes 105 checks over 62 explicit/default artifact paths; exact-final qualification and publication/review checks remain required for merge, with no release or production promotion", "Historical Cycle 150 consistency release gate: 105 checks over 62 explicit/default artifact paths", "content-addressed source, objectives and governance receipts, native toolchain, bounded hardware/Tier 0/model evidence, PBTRUST1/PBSTATE1, bounded PooleBoot, PBP1/PBC1/PSM1/PBART1 and six inner formats, PKELF1, PKENTRY1, PKLOAD6/PKMAP2/PBEXIT1, PKREVAL1, PKXFER1, PKTRAP1, PKCPU1, PKERR1, PKXSTATE1, PKXEXC1, PKMSR1, PKPMM7/PKACPI1, PKVM1, PKVM3, PKIRQ1, PKSMP1, PKSMP2, PKSMP5, PKSCHED1 through PKSCHED6, PKATOM1, PKLOCK1, PooleGlyph planning artifacts, and retained historical consistency artifacts"],
}


PHASE_GAPS = {
    "N0": [
        "The completed historical response records owner direction for ADR-0003, ADR-0004, and all 38 definitions. The 2026-09-04 registration record confirms primary hardware-key enrollment, owner fingerprint review, and exact GitHub signing-key registration. A verified enrollment signature, separately controlled recovery signer, architecture signature, signed tag, and publication receipt remain pending under the existing owner authorization and qualification gates",
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
    "N6": ["A reproducible real 146-page Cycle 162 PooleKernel PKELF1 candidate with current downstream replay pending against the fully qualified Cycle 161 baseline, PKENTRY1 intake, allocation-free PKREVAL1 verifier, bounded diagnostics, an opt-in QEMU-only live transfer, and bounded descriptor/exception, CPU, xstate, MSR, physical-memory, ACPI-container, virtual-memory, interrupt/time, first-AP, AP-local runtime, fixed-vector IPI, one-page remote-shootdown, cooperative scheduler, BSP timer/wakeup preemption, BSP deferred-work, exact-topology SMP scheduler, typed AP-local worker, and exact-topology SMP-preemption profiles now exist on one host; authenticated boot trust, measured boot, production transfer, final framebuffer remap/revocation, production capability authority, retained crash paths, target execution, and N6 exit remain open"],
    "N7": ["PKTRAP1 proves only one BSP descriptor/fault slice, PKCPU1 proves only a bounded qemu64 BSP read-only CPU snapshot, and PKERR1 freezes an exact-target rejection policy that correctly denies six current gaps. PKXSTATE1 proves bounded eager x87/SSE standard-XSAVE ownership and clearing; PKXEXC1 adds deliberate #MF/#XM delivery and exact bounded recovery, terminal test-only #NM eager-policy rejection, and a linked machine-code scope audit under WHPX on one BSP. PKMSR1 adds a read-only qemu64 BSP system-linkage/FS-GS/global-MCA/unsupported-PMU policy with eleven support-gated reads and zero activation. PKSMP5 adds three AP-local GDT/TSS/IDT, guarded RSP0/IST, x87/SSE-owner, and interrupt-vector state transactions without scheduler ownership or production capability authority. Exact board revision, stable firmware-image hash, an applicable AMD Family 1Ah Models 40h-4Fh errata guide or reviewed vendor-response disposition, a direct numeric client microcode floor or ratified replacement rule, native per-processor privileged revision evidence, target-specific privileged-MSR semantics, syscall and complete per-CPU activation transactions, machine-check delivery and recovery, supported PMU ownership, AVX and extended xstate, user-task exception delivery, scheduler integration, CPU migration, complete descriptor/fault handling, target qualification, and the N7 exit gate remain open"],
    "N8": ["PKIRQ1 proves a bounded one-BSP qemu64 local xAPIC and HPET substrate; PKSMP1 and PKSMP2 prove one-AP startup and one AP-local runtime; PKSMP5 scales that path to an exact four-vCPU topology with three private AP runtimes, dynamic local masks, aggregate target/ack mask 0xE, partial-start rollback, fresh retry, fixed development IPI delivery, final park, and exact cleanup; PKSCHED4 through PKSCHED6 add bounded scheduler, typed AP-worker, and acknowledgement-gated SMP-preemption ownership on that exact topology. I/O APIC routing, MSI/MSI-X, invariant-TSC calibration, AP-local timer interrupt delivery, public time domains, general topology and x2APIC, production capability authority, general SMP shootdown, additional failure interleavings, panic-path transactional recovery, general scheduler CPU ownership, target hardware, and the N8 exit gate remain open"],
    "N9": ["PKPMM7 consumes the live PBLIVE4/PBP1 map and provides bounded generation-safe physical ownership, scrub-before-allocation/reuse, a stable guarded five-page manager, external generation-owned guarded active ledgers, checked automatic growth, verified predecessor retirement, bounded-window fallback/rejection, exact Boot Services reclaim, and PKACPI1-gated ACPI reclaim after required RSDP/XSDT/APIC/FACP/HPET/MCFG validation and retained snapshot copy/readback. PKVM1 supplies inactive page-table transactions. PKVM3 adds a kernel-complete one-BSP candidate root with a PMM-derived complete-profile sparse physical direct map, exact hole and retained-range exclusion, write-back cache-alias rejection, exact CR3 activation/restoration, architectural Accessed/Dirty handling, three active local invalidation receipts, and generation-retirement gating. PKSMP5 proves three AP-side INVLPG operations for three AP-owned roots, one page per root, one generation, aggregate target/ack mask 0xE, stale and duplicate rejection, premature-reclaim denial, retirement, and exact frame release. General topology or address-space-wide shootdown, multiple concurrent generations, production capability authority, incremental concurrent map replacement, huge pages, PCID, COW, user faults, pager IPC, heaps/object caches, MMIO/PAT/MTRR qualification, interrupt-context and concurrent allocation, pressure/OOM policy beyond bounded metadata pressure, target hardware, and the N9 exit gate remain open PKVM3 data-frame release still requires scrub-before-reuse integration; the separate scrubbed PMM diagnostic and table-zeroing path do not close it."],
    "N10": ["PKACPI1 validates and retains only the required RSDP/XSDT/APIC/FACP/HPET/MCFG container set; no AML execution, complete ACPI namespace/resource graph, SMBIOS graph, or PCIe enumeration/configuration graph exists"],
    "N11": ["No AMD IOMMU or interrupt-remapping confinement exists"],
    "N12": ["Cycle 172 retains prepared inactive 16-KiB task stacks and verifies scrubbed owner release, not live contexts. Integrate guarded stack mappings, architectural context ownership, acknowledged CPU retirement and PMM scrub-receipt growth/pressure handling before N12.3 closure. Historical Cycle 171 exact-final qualification and main merge are complete; the new source still needs its own final audit.", "Cycle 168 completes only bounded AP runtime/stack/frame retention. General task stacks, CPU retirement, independent hardware quiescence and the changed-image scheduler/atomic/lock dependency replay remain open. Earlier dated notes below are historical.", "Cycle 165 refreshes all selected native dependency receipts; full runtime-inclusive exact-final qualification remains pending before merge. Execution-stack ownership and general CPU retirement remain open. Historical Cycle 162 qualifies mandatory active-root table/data retention only. N12.3 execution-stack and general CPU retirement ownership remain open; the bounded N12.2 contract was qualified in Cycle 161, but changed-image dependent receipts still need replay. Historical capability descriptions and reopen records below do not override that current status. PKSCHED1 supplies a bounded allocation-free scheduler core, neutral fixed-priority round-robin policy, selected lifecycle primitives, and a live cooperative BSP two-task context switch. PKSCHED2 integrates that core with PKIRQ1 through exact interrupt frames and proves bounded BSP quantum and wakeup preemption. PKSCHED3 adds allocation-free interrupt-deferred work, two fixed BSP workers, generation-safe slot reclamation, cancellation, flush, rollback, shutdown, and complete cleanup. PKSCHED4 adds four AP/BSP-local run queues on one exact topology, acknowledgement-gated ownership, one generation-safe cross-CPU wake, two migrations, six live AP dispatches, topology balancing, per-CPU idle ownership, timeout rollback, stale-ack rejection, and exact teardown. PKSCHED5 adds three AP-local workers and fixed typed timer-driver and generation-reclaim consumers. PKSCHED6 composes those foundations into four bounded timer/event/frame/run-queue lanes, deterministic cancel/wake/migration ordering, eight live acknowledgement-gated reschedule IPIs, three quantum switches, offline rollback, watchdog/fairness bounds, and exact teardown on the frozen topology. PKATOM1 closes N12.1 for typed 32-bit, 64-bit, pointer, reference-count, RMW, CAS, and fence primitives with explicit order domains, deterministic host stress, linked-code auditing, interrupt-context publication, two live QEMU runs, and invalid-order rejection. Cycle 149 historically closed N12.2 for the bounded allocation-free ticket/IRQ-save/mutex/notification/reader-writer/seqlock family, direct priority donation, five-rank order graph, owner death, exact rollback, host contention, and one exact four-vCPU live ticket-lock profile. Cycle 153 reopens N12.2 and its existing lock flag after stale-counter admission produced QueueFull with four participants; current-source repair and aggregate replay are required before further N12.3 promotion. AP-local timer interrupt delivery, arbitrary callbacks and a general driver/service framework, general topology/hotplug/x2APIC scheduling, deferred reclamation and ABA-safe object lifetime, ring-3 and address-space switching, per-task FS/GS and full xstate/debug/PMU ownership, target-hardware evidence, and the N12 exit gate remain open"],
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
    "N29": ["Cycle 151 supplies a demo-only static PooleGlass boot mark and design specification, but no native compositor, desktop, toolkit, accessibility stack, live glass material renderer, preference integration or animated transition; PG-01 through PG-10 remain under FLAG-NATIVE-UI-001"],
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
    "N36": ["Cycle 172's strict named stack-test parser rejects 40 missing/duplicate/failed/ignored evidence cases; source bindings separate current host ownership from prior live AP execution. Full profile/run/scenario coverage and independent live task-stack evidence remain open.", "No native system, power-loss, hardware, accessibility, soak, or external security suite exists. ADD-N36-RECEIPT-COVERAGE-001 requires a per-profile recorded-evidence audit and malformed/missing/duplicate/substitution controls through validators and release gates; Cycle 155 hardens PKTRAP1 and Cycle 160 hardens PKCPU1 internal consistency only. Cycle 162 adds six PKVM3 recorded-run consistency controls but does not close the broader review. Cycle 161 validates calendar dates in two scheduler component validators only; shared schema pattern/format enforcement remains open. Other profiles, authentication, independent builders and target execution remain under review"],
    "N37": ["No native SBOM/provenance/signing ceremony/release manifest or source-controlled release exists"],
    "N38": ["No native milestone, first hardware boot, daily-driver, or public-alpha gate has passed"],
    "N39": ["No reproducible signed native ISO, clean-media boot, or exact-byte release receipt exists"],
}


FLAGS = [
    ("FLAG-NATIVE-SCM-001", "STOP_SHIP", "N1", "Put PooleOS under reviewed source control with immutable release revisions"),
    ("FLAG-NATIVE-ADR-001", "BLOCKER", "N0", "Ratify the native architecture, TCB, reuse, language, ABI, driver, filesystem, and release ADR set"),
    ("FLAG-N0-OBJECTIVES-001", "REQUIRED", "N0", "Owner-ratify the native v1 profile and all 38 target values, then bind passing implementation evidence to every target"),
    ("FLAG-N0-RATIFICATION-SCOPE-001", "REQUIRED", "N0", "Bind the exact objective definitions and schema into the owner ceremony while excluding measurements and all production promotion"),
    ("FLAG-N0-GOVERNANCE-KEY-001", "BLOCKER", "N0", "Primary hardware key is enrolled, fingerprint-confirmed, and registered; verify an enrollment signature and establish separately controlled recovery custody under the existing owner authorization"),
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
    ("FLAG-N9-PMM-SCRUB-001", "REQUIRED", "N9", "Qualify scrub-before-allocation and scrub-before-reuse over generation-owned physical pages with full-page zero/readback, immutable receipts, exact-reuse stale-data rejection, preflighted release, ownership-preserving fault rollback, and temporary-alias revocation through host fault tests, two exact QEMU runs, and hostile controls without claiming predecessor raw APIs, reclaim, concurrency, target hardware, N9 exit, or production readiness"),
    ("FLAG-N9-PMM-METADATA-001", "REQUIRED", "N9", "Move PMM maps, free extents, allocation records, scrub receipts, and ownership metadata from fixed bootstrap storage into explicitly reserved, mapped, guarded, generation-owned pages with bootstrap-to-main handoff, corruption checks, rollback, and exact release exclusions before any held-class reclaim"),
    ("FLAG-N9-PMM-RECLAIM-001", "REQUIRED", "N9", "Implement generation-safe held-class reclaim with exact UEFI lifecycle gates, retained-range exclusion, metadata-capacity preflight, scrub-before-admission, atomic ownership transition, idempotence and rollback, immutable receipts, and exact boot-services versus ACPI timing without claiming concurrent reclaim, SMP, target hardware, N9 exit, or production readiness"),
    ("FLAG-N9-PMM-GROWTH-001", "REQUIRED", "N9", "Replace bounded fixed-capacity PMM source, free-extent, allocation, scrub-receipt, and reclaim-receipt ledgers with generation-owned scalable metadata growth that preserves guards, integrity, failure atomicity, deterministic accounting, retirement safety, and rollback without claiming concurrency, SMP, target hardware, N9 exit, or production readiness"),
    ("FLAG-N9-PMM-GROWTH-AUTOMATION-001", "REQUIRED", "N9", "Integrate checked pressure-triggered multi-generation PMM ledger growth, qualify repeated growth and both guarded-window exhaustion/fallback paths, and preserve deterministic accounting, rollback, retirement retry, and explicit concurrency/SMP/target nonclaims"),
    ("FLAG-N9-PMM-ACPI-CONSUMER-001", "REQUIRED", "N9", "Integrate a bounded native ACPI table consumer that validates and copies every required table before advancing the PMM lifecycle, then qualify exact ACPI-reclaim admission, idempotence, rollback, retained-range exclusion, malformed-table rejection, and explicit no-AML/no-SMP/no-target/no-production boundaries"),
    ("FLAG-N9-VM-DIRECT-MAP-001", "REQUIRED", "N9", "Replace the bounded nine-page PKVM2 mapping with a complete generation-owned sparse physical direct map that covers only admitted memory, excludes holes and forbidden or retained ranges, rejects incompatible cache aliases, commits and rolls back transactionally, binds local invalidation receipts and future SMP-shootdown dependencies, and defers old-generation reclamation without claiming SMP, target hardware, N9 exit, or production readiness"),
    ("FLAG-N8-IRQ-001", "REQUIRED", "N8", "Implement and qualify local APIC discovery and enablement, a bounded interrupt-vector ownership model, one monotonic timer source with calibration and overflow policy, and first-AP startup with per-CPU state, failure rollback, and zero unacknowledged interrupts before SMP TLB shootdown work is promoted"),
    ("FLAG-N8-SMP-FIRST-AP-001", "REQUIRED", "N8", "Start exactly one selected application processor through a below-1-MiB guarded trampoline/mailbox transaction; observe required long-mode state; command stop; prove quiescence and final-INIT parking; revoke aliases; scrub and release every resource; and preserve explicit no-general-SMP, no-IPI, no-shootdown, no-target, and nonproduction boundaries"),
    ("FLAG-N8-SMP-PERCPU-RUNTIME-001", "REQUIRED", "N8", "Qualify one AP-local GDT/TSS/IDT, guarded RSP0/IST stacks, x87/SSE owner state, and interrupt-vector ownership transaction on the proven first-AP lifecycle; verify hardware-loaded state and exact teardown; and preserve explicit no-IPI, no-shootdown, no-scheduler, no-target, and nonproduction boundaries"),
    ("FLAG-N8-SMP-IPI-001", "REQUIRED", "N8", "Qualify one capability-gated fixed-vector IPI request, delivery, acknowledgement, EOI, timeout, replay-control, panic, stop, park, and release transaction on the proven one-AP runtime while preserving explicit no-real-TLB-shootdown, no-arbitrary-callback, no-scheduler, no-target, and nonproduction boundaries"),
    ("FLAG-N9-SMP-SHOOTDOWN-001", "REQUIRED", "N9", "Implement and qualify generation-bound remote TLB invalidation over the capability-gated IPI transport with target masks, per-CPU acknowledgement, timeout and offline handling, stale-generation and duplicate-ack rejection, deferred-reclaim ordering, rollback, and exact no-reuse-before-retirement evidence"),
    ("FLAG-N8-SMP-MULTI-AP-001", "REQUIRED", "N8", "Scale the proven AP-local runtime and IPI path across the complete frozen Tier 0 processor topology with unique APIC ownership, per-CPU resources, multi-target masks, partial-start and timeout rollback, exact park/release accounting, and no scheduler, target-hardware, N8-exit, or production overclaim"),
    ("FLAG-N12-SCHED-FOUNDATION-001", "REQUIRED", "N12", "Freeze and qualify a bounded allocation-free scheduler core with generation-safe tasks, deterministic queues, explicit CPU ownership and affinity, bounded neutral priority policy, wake/block/cancel/timeout/teardown, selected synchronization and lifetime primitives, exact cooperative BSP context switching, stack isolation and clearing, independent oracle agreement, and no preemption, live AP, ring-3, address-space, target, N12-exit, or production overclaim"),
    ("FLAG-N12-SCHED-PREEMPT-001", "REQUIRED", "N12", "Integrate PKIRQ1 timer and wake/cancel paths with PKSCHED1 through a bounded interrupt-frame and deferred-reschedule contract; prove deterministic BSP quantum expiration, wakeup preemption, nesting and interrupt-state rules, exact context/stack ownership, rollback and cleanup, starvation/accounting bounds, and zero live-AP, ring-3, address-space, target, N12-exit, or production overclaim"),
    ("FLAG-N12-SCHED-DEFERRED-001", "REQUIRED", "N12", "Implement and qualify bounded interrupt-deferred queues and kernel workers with generation-safe work identity, duplicate suppression, cancellation and flush semantics, recursion prevention, priority and starvation bounds, rollback, shutdown ordering, reclamation-safe ownership, exact cleanup, independent oracle agreement, and no live-AP, ring-3, address-space, target, N12-exit, or production overclaim"),
    ("FLAG-N12-SCHED-SMP-001", "REQUIRED", "N12", "Integrate and qualify AP-local scheduler queues with explicit CPU ownership transfer, remote reschedule IPI delivery and acknowledgement, generation-safe cross-CPU wake and migration, offline and timeout rollback, topology-aware balancing, per-CPU idle ownership, exact teardown, independent oracle agreement, and no general-SMP, ring-3, address-space, target, N12-exit, or production overclaim"),
    ("FLAG-N12-SCHED-AP-WORKERS-001", "REQUIRED", "N12", "Extend bounded deferred work to AP-local workers and real kernel driver/service consumers with explicit queue and CPU ownership, remote wake/cancellation, flush and reclamation ordering, offline rollback, starvation bounds, exact worker-stack cleanup, independent SMP stress evidence, and no arbitrary-callback, target, N12-exit, or production overclaim"),
    ("FLAG-N12-SCHED-SMP-PREEMPT-001", "REQUIRED", "N12", "Compose bounded timer and wakeup preemption with the exact-topology SMP scheduler and AP-worker path; prove per-CPU timer/event/frame/run-queue ownership, acknowledgement-gated remote reschedule, deterministic tick/wake/cancel/migration ordering, offline rollback, starvation/watchdog latency bounds, exact teardown, and no general-topology, ring-3, address-space, target, N12-exit, or production overclaim"),
    ("FLAG-N12-CONCURRENCY-ATOMICS-001", "REQUIRED", "N12", "Freeze typed kernel atomics and compiler/x86-64 memory-order contracts; qualify supported operations and fences through deterministic litmus tests, generated-instruction review, invalid-order rejection, and explicit interrupt/SMP/progress/portability boundaries before broader locks, reclamation, or scheduler promotion"),
    ("FLAG-N12-CONCURRENCY-LOCKS-001", "REQUIRED", "N12", "Build and qualify raw and interrupt-save spinlocks, ownership-tracked priority-inheritance mutexes, reader-writer locks, seqlocks, try/timed paths, recursion and nesting rules, lock-order ranks, owner-death and teardown behavior, starvation/fairness bounds, rollback, and exact-topology contention over PKATOM1 without reclamation, general-SMP, target, N12-exit, or production overclaim"),
    ("FLAG-N12-CONCURRENCY-RECLAMATION-001", "REQUIRED", "N12", "Define and qualify bounded deferred reclamation and ABA-safe object lifetime over PKATOM1 and PKLOCK1 with scheduler, generation, acknowledged cross-CPU quiescence, timeout, cancellation, offline, owner-death, pressure, shutdown, and rollback evidence without general-SMP, hotplug, target, N12-exit, or production overclaim"),
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
    ("FLAG-N36-RECEIPT-COVERAGE-001", "REQUIRED", "N36", "Close ADD-N36-RECEIPT-COVERAGE-001 with a per-profile exact scenario/run/dependency/observation matrix and negative controls through component validators and release gates; keep consistency, fresh execution, authentication, independent builders and hardware evidence separate"),
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
    "The native repository, protected workflow, scope-hardened ADR ceremony, frozen 16-source packet, and completed response receipt record 2/2 ADR and 38/38 definition dispositions. The primary hardware-backed governance key is enrolled and registered. Enrollment signature verification, independent recovery custody, architecture signatures, signed tags, immutable release refs, retained CI review evidence, and all measurements remain open. No alternate recovery-key profile is accepted or provisioned",
    "Rust PE32+/ELF64 fixtures pass one-host qualification, but second-host reproduction, source provenance, C17/assembly/ABI tools, and image tooling remain open",
    "The native-only q35/QEMU/OVMF/VIRTIO profile passes one-host paused-instantiation controls, bounded checks for all seven required boot-slot/capability/virtual-memory/IPC/scheduler/update/PooleFS domains detect their required hostile violations, and a bounded PooleBoot proof executes under pinned OVMF, but source-rebuilt current QEMU/EDK II, complete reference devices/fault campaigns, six implementation-trace cross-checks, liveness/refinement/conformance work, and second-host reproduction remain open",
    "A reproducible unsigned PooleBoot proof application boots twice with deterministic twelve-file GPT/FAT32 media, exact GOP frames, retained PKMAP2 kernel/PSM1/six-artifact/PBTP1/PBTS1/table/guarded-stack/handoff storage, independently reconstructed PBLIVE4 bytes including a firmware RSDP record, bounded PBEXIT1 retry, successful ExitBootServices, and zero later firmware calls. The ordinary build stops before transfer; a separate opt-in QEMU-only PKXFER1 build installs retained CR3/RSP, transfers once, and live-executes PKREVAL1 over all nine retained files before an exact terminal unsigned-policy denial with zero signatures, authority, actions, writes, or firmware calls. PBSTATE1 still only models authenticated monotonic-anchor validation, deterministic redundant-copy selection, rollback/future rejection, repair/migration planning, and nine interrupted-transition recovery boundaries with no performed effects. Policy signature verification, authenticated revocation, a real cryptographic monotonic writable state provider, persistent backend I/O and executed repair/migration, Secure Boot-state verification, capability creation, activation or update application, policy application, recovery execution or symbol consumption, licensed real vendor payload intake and validation, live FMP/ESRT/PLDM inventory, privileged per-processor revision observation, initial-system execution, final framebuffer remap/revocation, production transfer, target-firmware and physical-media qualification, and N5 exit remain open",
    "Cycle 172 qualifies mandatory PKSTACK1 inactive task-stack ownership in PKLIFE1: 34 lifecycle tests and 243 kernel regressions per host profile, 11 compile-fail tests and a source-bound 17-stage core receipt. All 27 selected native checks pass on the unchanged linked kernel; no new QEMU execution or active stack context is claimed. Scrub failure and the fixed 16-receipt boundary retain ownership. Guarded mappings, architectural context/CPU retirement and automatic receipt-growth integration remain open. Cycle 171 is exact-final qualified and merged through PR76 at main8006c7b. Full runtime-inclusive exact-final qualification and publication/review still gate PR77; no phase, flag or production condition closes. Historical Cycle 171 completes fourteen memory/IRQ/SMP/scheduler/atomic/lock profiles on the unchanged Cycle 168 kernel: 28 final headless boots, 660 control groups, 2126 rejected cases and 243 kernel host tests per qualifier. Four superseded boots are preserved separately. All 27 selected native checks pass. SMP evidence now binds current boot artifacts and rejects stale or malformed transfer dependencies; five new test methods cover nine rejection cases. The final 155-test focused suite passes with two optional local-transcript skips. Measured memory and host/image gate pins are reconciled with 20 memory and 38 stale-identity regression cases. Full runtime-inclusive exact-final qualification, publication and review gates still precede merge and N12.3 task-stack/CPU-retirement integration. Main stays qualified Cycle 165 at this pre-closeout checkpoint. No phase, flag or production gate closes. Historical Cycle 170 requalifies five trap/CPU/xstate/MSR profiles on the unchanged Cycle 168 kernel: fourteen fresh headless boots, 225 marker controls and 42 passing focused tests. One expected TCG exception diagnostic is separate. The trap gate's stale identity pins are repaired and 17 aggregate-gate regression cases reject stale identity or production/authority claims. Fourteen of 27 selected checks pass; thirteen downstream checks plus prior SMP new-boot-artifact replay remain. Next is N9-PMM-ACPI-CONSUMER-001. Full runtime-inclusive canonical qualification is pending; main stays qualified Cycle 165. No phase, flag or production gate closes. Historical Cycle 169 requalifies six N5 components on the unchanged Cycle 168 kernel: six fresh headless boots, two kernel entries, nine-file revalidation and 83 passing focused tests. PSYM1 now binds source-current kernel-entry evidence and measured identities. Nine of 27 selected checks pass; 18 downstream checks and a new-boot-artifact replay of the prior SMP result remain pending. Next is N7-TRAP-001. Full canonical qualification has not run; main stays qualified Cycle 165. No phase, flag or production gate closes. Historical Cycle 168 qualifies mandatory AP runtime/stack and frame retention with two final four-vCPU boots, 27 copied-free and 18 owner-release rejections per partial/full attempt, 249 rejected cases, and 243 kernel host tests. The 147-page kernel has corrected build and mapping diagnostics. All 56 focused tests pass, including serialized receipt and ownership controls. Four of 27 selected native checks pass; 23 changed-image dependencies need replay beginning N5-SYMBOLS-SEMANTICS-001. Main contains exact-final qualified Cycle 165 through PR75. Current full canonical qualification, general task-stack ownership and CPU retirement remain open. No phase, flag or production gate closes. Historical Cycle 165 completes fourteen current-kernel memory/VM/IRQ/SMP/scheduler/atomic/lock profiles with 28 final headless boots, 660 negative-control groups and 2120 rejected cases. Six superseded initial boots are excluded after three test-only corrections. All 27 selected native checks pass, and the 142-test profile/map/gate suite passes with two optional local-transcript skips. Native bytes are unchanged; data-frame scrub-before-reuse, execution-stack ownership, general CPU retirement and full runtime-inclusive exact-final qualification remain open. Main stays qualified Cycle 161, and no phase/flag or production gate closes. Historical Cycle 164 completes five N7 live profiles on the unchanged Cycle 162 kernel with fourteen successful headless boots, 225 marker controls and 41 focused Python tests. One expected TCG exception diagnostic is counted separately. The current selected projection passes 13/27; fourteen memory/VM/IRQ/SMP/scheduler/atomic/lock dependencies still need replay beginning N9-PMM-ACPI-CONSUMER-001. No current full canonical pass, phase closure, target qualification or production promotion is claimed. Historical Cycle 163 completes six N5 component replays with six final headless boots and 70 focused Python tests. Calendar-date validation repairs loader and PooleBoot fixed-day blockers without closing the broader N36 review. The current projection passes 8/27; nineteen downstream receipts, including transfer-dependent VM evidence, require replay beginning N7-TRAP-001. No current full canonical pass, phase closure or production promotion is claimed. Historical Cycle 162 adds mandatory PKVM3 table/data retention and atomic owner-authorized PMM cleanup. The 146-page kernel passes 228 host tests, 16 retention cases, two exact PKVM3 boots with six retained-free rejections each, 48 marker controls and two reproducible PKENTRY1 builds. The selected current-source projection passes 4/27 checks; 23 changed-image dependencies need replay, beginning N5-SYMBOLS-SEMANTICS-001. Main remains the fully qualified Cycle 161 baseline merged through PR74. Execution-stack ownership, general CPU retirement and the broader N36 schema/evidence audit remain open; no phase closure, demo rebase or production promotion follows. Historical Cycle 161 completes current-source replay of the Cycle 158 mandatory inactive table/frame-retention kernel after Cycle 159 boot-chain and Cycle 160 N7 qualification. Fourteen memory/IRQ/SMP/scheduler/atomic/lock profiles pass 28 final headless boots, 658 control groups and 2,118 rejected cases on the unchanged 219-test kernel. All 26 selected native checks and the pre-closeout 105-check/708-Doctor/917-test canonical suite pass; exact-final qualification, publication and review checks still gate a main merge. The failed Cycle 158 audit is preserved separately. PKCPU1 recorded consistency and the two scheduler calendar-date repairs do not close the broader N36 schema/evidence audit. Active roots, execution stacks and CPU-retirement ownership remain open under N12.3. The native foundation includes PKENTRY1 intake, allocation-free PKREVAL1 verifier, bounded early diagnostics, opt-in QEMU-only live entry, BSP-only PKTRAP1 descriptor/exception containment, bounded BSP PKXSTATE1 x87/SSE ownership, PKPMM7 scrubbed lifecycle and checked repeated ledger growth, guarded stable-manager and generation-owned active-ledger transactions, PKACPI1 required-table snapshot/reclaim evidence, PKVM3 sparse PMM-owned direct-map evidence, PKIRQ1 one-BSP timer evidence, PKSMP1 one-AP lifecycle evidence, PKSMP2 one-AP processor-local runtime evidence, PKSMP5 fixed four-vCPU/three-AP startup, rollback, IPI, and one-page-per-root remote-invalidation evidence, PKSCHED1 cooperative scheduler/context-switch evidence, PKSCHED2 bounded BSP timer/wakeup preemption evidence, PKSCHED3 bounded BSP deferred-work evidence, PKSCHED4 exact-topology live AP scheduler ownership/wake/migration evidence, PKSCHED5 exact-topology typed AP-local worker evidence, PKSCHED6 bounded exact-topology SMP-preemption evidence, PKATOM1 typed atomic/memory-order evidence, and PKLOCK1 bounded lock-family/exact-topology contention evidence exist, but authenticated boot trust, measured boot, production transfer, production capability authority, general topology and shootdown, AP-local timer interrupt delivery, deferred reclamation and ABA-safe object lifetime, a general driver/service framework, arbitrary callbacks, general SMP preemption, retained crash evidence, target execution, and N6/N7/N8/N9/N12 exit remain open",
    "PKERR1 freezes a pure exact-target CPU/errata rejection policy, PKXSTATE1 proves bounded x87/SSE standard-XSAVE ownership, PKXEXC1 proves deliberate #MF/#XM recovery plus terminal test-only #NM rejection with a linked scope audit under WHPX, and PKMSR1 proves only a read-only qemu64 BSP system-linkage/global-MCA/unsupported-PMU observation. PKPMM7 supplies bounded physical ownership, scrubbed lifecycle transactions, a stable guarded five-page manager, external generation-owned active ledgers, checked automatic growth with retirement, bounded-window fallback and pre-effect rejection, streamed lifecycle-gated Boot Services reclaim, and PKACPI1-gated ACPI reclaim after required-table validation and retained copy/readback; PKVM1 supplies inactive page-table transactions; PKVM3 proves one-BSP activation/restoration of a complete-profile PMM-owned sparse direct map; PKIRQ1 proves one bounded local timer transaction; PKSMP1 proves one first-AP start/quiesce/park lifecycle; PKSMP2 proves one AP-local GDT/TSS/IDT, guarded-stack, x87/SSE-owner, and interrupt-vector runtime transaction; and PKSMP5 proves three simultaneous AP-local runtimes, partial-start rollback with fresh retry, six fixed IPI classes per AP, three AP-side one-page INVLPG operations, aggregate acknowledgement, and one deferred generation retirement. No target-qualified complete native CPU policy, applicable Model 40h-4Fh errata authority, direct numeric client microcode floor or ratified replacement, target-specific privileged-MSR semantics, syscall/MCE/PMU activation, AVX/extended state, user-task exception delivery, scheduler or migration integration, general interrupt routing/time services, production capability authority, general topology or SMP shootdown, AML or complete ACPI resource-graph execution, complete kernel/user address spaces, heap, MMIO/PAT/MTRR qualification, interrupt-context or concurrent allocator, general pressure, or OOM implementation exists",
    "The exact Tier 1 identity passes 24/24 required checks and 16 allowlisted user-mode CPUID records are captured with zero public raw registers, but seven required channels remain non-complete in total, including partial CPU/MSR and SPD/topology; 15 standards hashes, ten lab-safety prerequisites, native parsing, and physical qualification also remain open",
    "No native DMA/IOMMU/interrupt-remapping confinement",
    "PKPMM7 supplies bounded one-BSP physical-page ownership, scrub-before-allocation and scrub-before-reuse with full readback and fault rollback, a stable guarded five-page manager, external generation-owned guarded ledgers, checked automatic repeated growth, verified retirement, bounded-window fallback and pre-effect rejection, exact post-ExitBootServices Boot Services reclaim, and PKACPI1-gated ACPI reclaim after required-table validation plus retained snapshot copy/readback. PKVM1 supplies inactive four-level 4 KiB transactions, PKVM3 supplies a complete-profile PMM-owned sparse direct map, cache-alias rejection, exact CR3 restoration, three local invalidation receipts, and generation-retirement gating, and PKSMP5 proves exactly three AP-side INVLPG operations and deferred reclaim for three AP-owned roots, one page per root, one generation, and aggregate target/ack mask 0xE. General topology, address-space-wide shootdown, multiple concurrent generations, production capability authority, incremental concurrent map replacement, huge pages, PCID, COW, user faults, pager IPC, cache/MMIO qualification, heaps/object caches, interrupt-context allocation, concurrent allocation, general pressure and OOM policy, scheduler, task, syscall, capability, IPC, isolation, and asynchronous I/O remain open",
    "No native security/crypto/TPM/secrets/MAC/privacy implementation or external review",
    "No isolated native driver domains or virtio reference drivers",
    "No native block/NVMe/USB/input/VFS/PooleFS persistent path",
    "No native user ABI, libc, init, service manager, login, shell, terminal, package, update, installer, or recovery",
    "No native network, graphics, audio, compositor, PooleGlass, accessibility, or application platform",
    "No source-bound signed PDC dynamics or portable/native PDC backends",
    "No native PDC control-plane services or bounded actuator proof",
    "PooleGlyph Phase 66 and the source, semantic, Core IR, PGASM, PGB2, PGVM2, host-ABI, policy, toolchain, compatibility, IP-boundary, private-backend-equivalence, and native-integration gates remain open",
    "No native integrated fuzz/fault/power-loss/security/conformance/soak evidence; ADD-N36-RECEIPT-COVERAGE-001 also requires cross-profile recorded scenario/run/dependency/oracle validation and negative controls before qualification closure",
    "No native SBOM/provenance/signing ceremony/operations/release manifest",
    "No reproducible signed native ISO or exact clean-media QEMU/physical release receipt",
]


PROGRAM_GAPS[4] = (
    "Cycle 173 repairs PKENTRY1 full linked-ELF provenance and replays six N5 components with six fresh boots. "
    "The selected projection passes 22/27, while five stale checks and broader embedded-entry CPU/memory/SMP "
    "replay remain open. The Cycle 172 full audit failed 104/105; no current full qualification or main merge "
    "is claimed. Historical records below are not current-source promotion. " + PROGRAM_GAPS[4]
)


PROGRAM_GAPS[4] = (
    "Cycle 174 requalifies five CPU profiles with fourteen fresh successful virtual boots and 225 controls. "
    "Embedded entry evidence now requires exact JSON-typed identity with the current validated receipt. "
    "The selected projection passes 24/27; PMM, VM, SMP IPI and broader memory-through-lock provenance "
    "replay remain pending before full qualification. No phase or production gate closes. " + PROGRAM_GAPS[4]
)


PROGRAM_GAPS[4] = (
    "Cycle 175 qualifies fourteen final memory-through-lock profiles with 28 fresh virtual boots, "
    "660 groups and 2126 rejected cases; two earlier SMP boots are superseded after a shape-guard repair. "
    "All 27 selected native checks pass. Embedded provenance rejects 224 substitutions and 56 invalid "
    "dependencies; 161 of 163 focused tests pass with two optional skips. Exact full qualification, "
    "publication/review and N12.3 live stack/context and CPU-retirement work remain open. No phase or "
    "production gate closes. " + PROGRAM_GAPS[4]
)


PROGRAM_GAPS[4] = (
    "Cycle 177 adds PKEXEC1 dispatch execution holds and repairs transaction/bypass exhaustion "
    "admission rollback. All 17 core stages pass with 245 kernel, 40 lifecycle and 15 compile-fail "
    "tests; the changed image has only 2/27 current selected checks and needs 25 dependency replays "
    "beginning N6-KENTRY-001. Cycle 176 qualified 105 canonical gates and 708 Doctor checks and "
    "merged PR77 to main; that baseline does not qualify the new image. Live guarded stacks, "
    "context activation, architectural CPU quiescence and full current qualification remain open. "
    "No phase, flag or production gate closes. Historical records follow. " + PROGRAM_GAPS[4]
)


PROGRAM_GAPS[4] = (
    "Cycle 178 requalifies PKENTRY1 for the unchanged Cycle 177 kernel with two clean matching "
    "builds, 245 host tests, 43 rejection controls and 55 bindings covering 39 kernel Rust sources. "
    "Twelve entry-gate controls cover stale identities and exact numeric types. The selected "
    "projection is 3/27; 24 boot/CPU/memory dependencies still need replay beginning "
    "N5-SYMBOLS-SEMANTICS-001. No fresh guest, independent builder, full canonical or production "
    "qualification follows. Prior failures and historical qualification remain preserved. " + PROGRAM_GAPS[4]
)


PROGRAM_GAPS[4] = (
    "Cycle 179 qualifies six N5 components on the unchanged kernel: six final headless boots, "
    "two kernel entries, nine-file revalidation and 71 focused Python tests pass. PKREVAL1 "
    "requires semantic receipt acceptance before output; three admission and thirteen artifact/count "
    "gate controls pass. Two superseded boots and prior failures remain preserved. Selected "
    "readiness is 8/27; nineteen CPU/memory profiles require replay beginning N7-TRAP-001. "
    "Full exact-candidate, independent-builder and production qualification remain pending. " + PROGRAM_GAPS[4]
)


PROGRAM_GAPS[4] = (
    "Cycle 181 resumed closeout fails exact entry-receipt reproduction: the host-only PKELF1 probe is 147968 bytes rather than 148480. A preserved rebuild confirms identical kernel product fields and canonical bytes; host-probe provenance/root cause remains unqualified. Resolve N6-KENTRY-001 before the scheduler control audit; the combined suite has 331 passes, one failure and two skips, not a full pass. "
    "Cycle 181 replays fourteen memory-through-lock profiles with 28 final virtual boots and four superseded boots. All 27 selected consistency checks and 164 of 166 focused tests pass (two optional skips). The 660 groups and 2126 cases are reported counts: at least 65 scheduler source-control entries lack per-control rejection execution. Repair ADD-N36-RECEIPT-COVERAGE-001 beginning PKSCHED3 before exact full qualification, publication/review and PR78 merge, then N12.3 live contexts. No phase, flag, native bytes or production condition closes. "
    "Cycle 180 qualifies five CPU profiles on the unchanged kernel with fourteen fresh virtual "
    "boots, 225 controls and 46 focused tests; one expected TCG diagnostic remains separate. "
    "Positive provenance tests now require untouched generated receipts, and nineteen aggregate "
    "controls reject stale identities or promotion. Selected readiness is 13/27; fourteen "
    "memory-through-lock profiles need replay beginning N9-PMM-ACPI-CONSUMER-001. Full exact "
    "qualification, live task contexts/CPU retirement and production remain open. " + PROGRAM_GAPS[4]
)


PROGRAM_GAPS[4] = (
    "Cycle 182 isolates the host probe size drift to MSVC runtime libraries and pins four host input trees. "
    "Shared environment repair rejects ambient LINK/_LINK_ and Cargo overrides; 39 hostile-environment "
    "regressions, exact entry reproduction and fixture reproduction pass. The earlier 38-test failure "
    "is preserved. Kernel bytes remain unchanged; new entry/fixture provenance leaves 24/27 selected checks "
    "stale. Replay N5-ELF-001 and N5 symbols/boot, CPU and memory dependencies, including actual "
    "execution evidence for at least 65 scheduler controls, before full qualification or PR78 merge. "
    "Complete host attestation, independent builders and production remain open. " + PROGRAM_GAPS[4]
)


PROGRAM_GAPS[4] = (
    "Cycle 183 requalifies the shared ELF loader and kernel entry against declared pinned host inputs. "
    "ELF validates typed host evidence and rejects invalid receipts before creating or replacing output. "
    "Entry inherits all 19 loader inputs in 72 total bindings; its unchanged kernel product reproduces. "
    "All 59 hostile-environment focused tests pass. The separate ELF gate passes, while the selected "
    "projection remains 3/27 with 24 downstream dependencies stale. N5-SYMBOLS-SEMANTICS-001 begins "
    "ordered symbol/policy/boot and CPU/memory replay. At least 65 scheduler controls still require "
    "individual execution evidence before full exact-candidate qualification or PR78 merge. No native "
    "feature, new guest boot, independent builder, ISO or production promotion follows. " + PROGRAM_GAPS[4]
)


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
        phase["current_gaps"] = list(PHASE_GAPS[phase_id])
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
                    "native/boot/src/exit.rs",
                    "native/boot/src/livehandoff.rs",
                    "native/boot/src/main.rs",
                    "native/livehandoff/src/lib.rs",
                    "native/kernel/src/acpi.rs",
                    "native/kernel/src/lib.rs",
                    "native/kernel/src/physical_memory.rs",
                    "native/kernel/src/main.rs",
                    "runtime/native_live_boot_handoff.py",
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
                    "security/governance-key-registration.json",
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
        if flag_id == "FLAG-N8-IRQ-001":
            evidence.extend(
                [
                    "specs/native-kernel-interrupt-time-contract.json",
                    "specs/native-kernel-interrupt-time-contract.schema.json",
                    "specs/native-kernel-interrupt-time-readiness.schema.json",
                    "native/kernel/src/interrupt_time.rs",
                    "native/kernel/src/arch/x86_64.rs",
                    "native/kernel/src/main.rs",
                    "runtime/native_kernel_interrupt_time.py",
                    "tools/qualify_native_kernel_interrupt_time.py",
                    "tests/test_native_kernel_interrupt_time.py",
                    "docs/native-kernel-interrupt-time.md",
                    "runs/native-kernel-interrupt-time-readiness.json",
                ]
            )
        if flag_id == "FLAG-N8-SMP-FIRST-AP-001":
            evidence.extend(
                [
                    "specs/native-kernel-smp-first-ap-contract.json",
                    "specs/native-kernel-smp-first-ap-contract.schema.json",
                    "specs/native-kernel-smp-first-ap-readiness.schema.json",
                    "native/kernel/src/smp.rs",
                    "native/kernel/src/arch/x86_64.rs",
                    "native/kernel/src/main.rs",
                    "runtime/native_kernel_smp_first_ap.py",
                    "tools/qualify_native_kernel_smp_first_ap.py",
                    "tests/test_native_kernel_smp_first_ap.py",
                    "docs/native-kernel-smp-first-ap.md",
                    "runs/native-kernel-smp-first-ap-readiness.json",
                ]
            )
        if flag_id == "FLAG-N8-SMP-PERCPU-RUNTIME-001":
            evidence.extend(
                [
                    "specs/native-kernel-smp-percpu-runtime-contract.json",
                    "specs/native-kernel-smp-percpu-runtime-contract.schema.json",
                    "specs/native-kernel-smp-percpu-runtime-readiness.schema.json",
                    "native/kernel/src/smp_runtime.rs",
                    "native/kernel/src/arch/x86_64.rs",
                    "native/kernel/src/main.rs",
                    "runtime/native_kernel_smp_percpu_runtime.py",
                    "tools/qualify_native_kernel_smp_percpu_runtime.py",
                    "tests/test_native_kernel_smp_percpu_runtime.py",
                    "docs/native-kernel-smp-percpu-runtime.md",
                    "runs/native-kernel-smp-percpu-runtime-readiness.json",
                ]
            )
        if flag_id in {"FLAG-N8-SMP-IPI-001", "FLAG-N8-SMP-MULTI-AP-001"}:
            evidence.extend(
                [
                    "specs/native-kernel-smp-ipi-contract.json",
                    "specs/native-kernel-smp-ipi-contract.schema.json",
                    "specs/native-kernel-smp-ipi-readiness.schema.json",
                    "native/kernel/src/smp_ipi.rs",
                    "native/kernel/src/arch/x86_64.rs",
                    "native/kernel/src/main.rs",
                    "runtime/native_kernel_smp_ipi.py",
                    "tools/qualify_native_kernel_smp_ipi.py",
                    "tests/test_native_kernel_smp_ipi.py",
                    "docs/native-kernel-smp-ipi.md",
                    "runs/native-kernel-smp-ipi-readiness.json",
                ]
            )
        if flag_id in {
            "FLAG-N12-SCHED-FOUNDATION-001",
            "FLAG-N12-SCHED-PREEMPT-001",
            "FLAG-N12-SCHED-DEFERRED-001",
            "FLAG-N12-SCHED-SMP-001",
            "FLAG-N12-SCHED-AP-WORKERS-001",
            "FLAG-N12-SCHED-SMP-PREEMPT-001",
        }:
            evidence.extend(
                [
                    "specs/native-kernel-scheduler-contract.json",
                    "specs/native-kernel-scheduler-contract.schema.json",
                    "specs/native-kernel-scheduler-readiness.schema.json",
                    "native/kernel/src/scheduler.rs",
                    "native/kernel/src/arch/x86_64.rs",
                    "native/kernel/src/main.rs",
                    "native/kernel/src/bin/pksched1_probe.rs",
                    "runtime/native_kernel_scheduler.py",
                    "tools/qualify_native_kernel_scheduler.py",
                    "tests/test_native_kernel_scheduler.py",
                    "docs/native-kernel-scheduler.md",
                    "runs/native-kernel-scheduler-readiness.json",
                ]
            )
        if flag_id in {
            "FLAG-N12-SCHED-PREEMPT-001",
            "FLAG-N12-SCHED-DEFERRED-001",
            "FLAG-N12-SCHED-SMP-001",
            "FLAG-N12-SCHED-AP-WORKERS-001",
            "FLAG-N12-SCHED-SMP-PREEMPT-001",
        }:
            evidence.extend(
                [
                    "specs/native-kernel-scheduler-preemption-contract.json",
                    "specs/native-kernel-scheduler-preemption-contract.schema.json",
                    "specs/native-kernel-scheduler-preemption-readiness.schema.json",
                    "native/kernel/src/scheduler_preempt.rs",
                    "native/kernel/src/bin/pksched2_probe.rs",
                    "runtime/native_kernel_scheduler_preempt.py",
                    "tools/qualify_native_kernel_scheduler_preempt.py",
                    "tests/test_native_kernel_scheduler_preempt.py",
                    "docs/native-kernel-scheduler-preemption.md",
                    "runs/native-kernel-scheduler-preemption-readiness.json",
                ]
            )
        if flag_id in {
            "FLAG-N12-SCHED-DEFERRED-001",
            "FLAG-N12-SCHED-SMP-001",
            "FLAG-N12-SCHED-AP-WORKERS-001",
            "FLAG-N12-SCHED-SMP-PREEMPT-001",
        }:
            evidence.extend(
                [
                    "specs/native-kernel-scheduler-deferred-contract.json",
                    "specs/native-kernel-scheduler-deferred-contract.schema.json",
                    "specs/native-kernel-scheduler-deferred-readiness.schema.json",
                    "native/kernel/src/scheduler_deferred.rs",
                    "native/kernel/src/bin/pksched3_probe.rs",
                    "runtime/native_kernel_scheduler_deferred.py",
                    "tools/qualify_native_kernel_scheduler_deferred.py",
                    "tests/test_native_kernel_scheduler_deferred.py",
                    "docs/native-kernel-scheduler-deferred.md",
                    "runs/native-kernel-scheduler-deferred-readiness.json",
                ]
            )
        if flag_id in {
            "FLAG-N12-SCHED-SMP-001",
            "FLAG-N12-SCHED-AP-WORKERS-001",
            "FLAG-N12-SCHED-SMP-PREEMPT-001",
        }:
            evidence.extend(
                [
                    "specs/native-kernel-scheduler-smp-contract.json",
                    "specs/native-kernel-scheduler-smp-contract.schema.json",
                    "specs/native-kernel-scheduler-smp-readiness.schema.json",
                    "native/kernel/src/scheduler_smp.rs",
                    "native/kernel/src/smp_ipi.rs",
                    "native/kernel/src/bin/pksched4_probe.rs",
                    "runtime/native_kernel_scheduler_smp.py",
                    "tools/qualify_native_kernel_scheduler_smp.py",
                    "tests/test_native_kernel_scheduler_smp.py",
                    "docs/native-kernel-scheduler-smp.md",
                    "runs/native-kernel-scheduler-smp-readiness.json",
                ]
            )
        if flag_id in {
            "FLAG-N12-SCHED-AP-WORKERS-001",
            "FLAG-N12-SCHED-SMP-PREEMPT-001",
        }:
            evidence.extend(
                [
                    "specs/native-kernel-scheduler-ap-workers-contract.json",
                    "specs/native-kernel-scheduler-ap-workers-contract.schema.json",
                    "specs/native-kernel-scheduler-ap-workers-readiness.schema.json",
                    "native/kernel/src/scheduler_ap_workers.rs",
                    "native/kernel/src/bin/pksched5_probe.rs",
                    "runtime/native_kernel_scheduler_ap_workers.py",
                    "tools/qualify_native_kernel_scheduler_ap_workers.py",
                    "tests/test_native_kernel_scheduler_ap_workers.py",
                    "docs/native-kernel-scheduler-ap-workers.md",
                    "runs/native-kernel-scheduler-ap-workers-readiness.json",
                ]
            )
        if flag_id == "FLAG-N12-SCHED-SMP-PREEMPT-001":
            evidence.extend(
                [
                    "specs/native-kernel-scheduler-smp-preempt-contract.json",
                    "specs/native-kernel-scheduler-smp-preempt-contract.schema.json",
                    "specs/native-kernel-scheduler-smp-preempt-readiness.schema.json",
                    "native/kernel/src/scheduler_smp_preempt.rs",
                    "native/kernel/src/bin/pksched6_probe.rs",
                    "runtime/native_kernel_scheduler_smp_preempt.py",
                    "tools/qualify_native_kernel_scheduler_smp_preempt.py",
                    "tests/test_native_kernel_scheduler_smp_preempt.py",
                    "docs/native-kernel-scheduler-smp-preempt.md",
                    "runs/native-kernel-scheduler-smp-preempt-readiness.json",
                ]
            )
        if flag_id == "FLAG-N12-CONCURRENCY-ATOMICS-001":
            evidence.extend(
                [
                    "specs/native-kernel-atomics-contract.json",
                    "specs/native-kernel-atomics-contract.schema.json",
                    "specs/native-kernel-atomics-readiness.schema.json",
                    "native/kernel/src/atomics.rs",
                    "native/kernel/src/bin/pkatom1_probe.rs",
                    "runtime/native_kernel_atomics.py",
                    "tools/qualify_native_kernel_atomics.py",
                    "tests/test_native_kernel_atomics.py",
                    "docs/native-kernel-atomics.md",
                    "runs/native-kernel-atomics-readiness.json",
                ]
            )
        if flag_id == "FLAG-N12-CONCURRENCY-LOCKS-001":
            evidence.extend(
                [
                    "specs/native-kernel-locks-contract.json",
                    "specs/native-kernel-locks-contract.schema.json",
                    "specs/native-kernel-locks-readiness.schema.json",
                    "native/kernel/src/locks.rs",
                    "native/kernel/src/bin/pklock1_probe.rs",
                    "runtime/native_kernel_locks.py",
                    "tools/qualify_native_kernel_locks.py",
                    "tests/test_native_kernel_locks.py",
                    "docs/native-kernel-locks.md",
                    "runs/native-kernel-locks-readiness.json",
                ]
            )
        if flag_id == "FLAG-N12-CONCURRENCY-RECLAMATION-001":
            evidence.extend([
                "docs/checkpoints/cycle172-task-stack-ownership.md",
                "docs/checkpoints/cycle168-ap-ownership-qualification.md",
                "native/kernel/src/reclamation/ap_resources.rs",
                "native/kernel/src/physical_memory/tests/ap_resources.rs",
                "runs/native-kernel-smp-ipi-readiness.json",
                "docs/checkpoints/cycle162-active-root-retention.md",
                "native/kernel/src/active_virtual_memory.rs",
                "runs/native-kernel-virtual-memory-readiness.json",
                "native/kernel/src/reclamation.rs",
                "native/kernel/src/reclamation/task_lifetimes.rs",
                "native/kernel/tests/task_lifetimes.rs",
                "docs/native-kernel-task-lifetimes.md",
                "native/kernel/src/physical_memory/retention.rs",
                "native/kernel/src/physical_memory/tests/retention.rs",
                "docs/native-kernel-physical-retention.md",
                "native/kernel/tests/reclamation_core.rs",
                "tools/qualify_native_reclamation_core.py",
                "tests/test_native_reclamation_core.py",
                "docs/native-kernel-reclamation-core.md",
                "runs/native-kernel-reclamation-core-readiness.json",
            ])
        if flag_id == "FLAG-N9-SMP-SHOOTDOWN-001":
            evidence.extend(
                [
                    "specs/native-kernel-smp-ipi-contract.json",
                    "specs/native-kernel-smp-ipi-contract.schema.json",
                    "specs/native-kernel-smp-ipi-readiness.schema.json",
                    "native/kernel/src/smp_ipi.rs",
                    "native/kernel/src/arch/x86_64.rs",
                    "native/kernel/src/main.rs",
                    "runtime/native_kernel_smp_ipi.py",
                    "tools/qualify_native_kernel_smp_ipi.py",
                    "tests/test_native_kernel_smp_ipi.py",
                    "docs/native-kernel-smp-ipi.md",
                    "runs/native-kernel-smp-ipi-readiness.json",
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
        if flag_id == "FLAG-N36-RECEIPT-COVERAGE-001":
            evidence.extend([
                "docs/checkpoints/cycle172-task-stack-ownership.md",
                "docs/checkpoints/cycle171-native-dependency-replay.md",
                "docs/checkpoints/cycle170-cpu-state-replay.md",
                "docs/checkpoints/cycle169-boot-chain-replay.md",
                "runtime/native_symbols.py",
                "tests/test_native_symbols.py",
                "docs/checkpoints/cycle168-ap-ownership-qualification.md",
                "runtime/native_kernel_smp_ipi.py",
                "tests/test_native_kernel_smp_ipi.py",
                "tests/test_native_reclamation_core.py",
                "docs/checkpoints/cycle165-native-dependency-replay.md",
                "tests/test_native_memory_release_gate.py",
                "tests/test_native_dependency_release_gate.py",
                "docs/native-kernel-physical-memory.md",
                "docs/native-kernel-virtual-memory.md",
                "docs/checkpoints/cycle164-cpu-replay.md",
                "docs/native-kernel-xstate-exception.md",
                "tests/test_pdc_production_roadmap.py",
                "docs/checkpoints/cycle163-boot-chain-replay.md",
                "runtime/native_kernel_load.py",
                "runtime/native_pooleboot.py",
                "specs/native-kernel-load-readiness.schema.json",
                "specs/native-pooleboot-readiness.schema.json",
                "tests/test_native_kernel_load.py",
                "tests/test_native_pooleboot.py",
                "docs/checkpoints/cycle162-active-root-retention.md",
                "runtime/native_kernel_virtual_memory.py",
                "tests/test_native_kernel_virtual_memory.py",
                "tests/test_native_dependency_release_boundaries.py",
                "runtime/native_kernel_trap.py",
                "tests/test_native_kernel_trap.py",
                "docs/native-kernel-trap.md",
                "runs/native-kernel-trap-readiness.json",
                "runtime/native_kernel_cpu_policy.py",
                "tests/test_native_kernel_cpu_policy.py",
                "docs/native-kernel-cpu-policy.md",
                "runs/native-kernel-cpu-policy-readiness.json",
                "docs/checkpoints/cycle160-cpu-evidence.md",
                "runtime/native_kernel_scheduler.py",
                "runtime/native_kernel_scheduler_preempt.py",
                "specs/native-kernel-scheduler-readiness.schema.json",
                "specs/native-kernel-scheduler-preemption-readiness.schema.json",
                "tests/test_native_kernel_scheduler.py",
                "tests/test_native_kernel_scheduler_preempt.py",
                "docs/native-kernel-scheduler.md",
                "docs/native-kernel-scheduler-preemption.md",
                "docs/checkpoints/cycle161-qualified-checkpoints.md",
                "tools/pooleos_release_gate.py",
            ])
        implementation_flags.append(
            {
                "id": flag_id,
                "class": flag_class,
                # Cycle 157 requalifies the repaired bounded PKLOCK1 contract.
                "status": "closed"
                if flag_class == "SUPERSEDED"
                or flag_id == "FLAG-N12-CONCURRENCY-LOCKS-001"
                or flag_id in {"FLAG-N0-RATIFICATION-SCOPE-001", "FLAG-N2-CPUID-001", "FLAG-N4-PROFILE-001", "FLAG-N4-IPC-MODEL-001", "FLAG-N4-SCHEDULER-MODEL-001", "FLAG-N4-POOLEFS-MODEL-001", "FLAG-N5-POOLEBOOT-PROOF-001", "FLAG-N5-BOOTPROTO-001", "FLAG-N5-BOOTCFG-001", "FLAG-N5-ELF-001", "FLAG-N5-KLOAD-001", "FLAG-N5-MANIFEST-001", "FLAG-N5-PBP1-LIVE-001", "FLAG-N5-KMAP-001", "FLAG-N5-HANDOFF-EXIT-001", "FLAG-N5-INIT-SYSTEM-001", "FLAG-N5-INIT-BUNDLE-001", "FLAG-N5-RECOVERY-BUNDLE-001", "FLAG-N5-SYMBOL-BUNDLE-001", "FLAG-N5-MICROCODE-BUNDLE-001", "FLAG-N5-FIRMWARE-BUNDLE-001", "FLAG-N5-POLICY-BUNDLE-001", "FLAG-N5-INIT-SEMANTICS-001", "FLAG-N5-INNER-PARSE-001", "FLAG-N5-INNER-TRUST-CONTRACT-001", "FLAG-N5-INNER-TRUST-BACKEND-MODEL-001", "FLAG-N5-INNER-KERNEL-REVALIDATE-001", "FLAG-N5-KERNEL-TRANSFER-001", "FLAG-N6-KENTRY-001", "FLAG-N7-TRAP-001", "FLAG-N7-CPU-POLICY-001", "FLAG-N7-ERRATA-POLICY-001", "FLAG-N7-XSTATE-POLICY-001", "FLAG-N7-XSTATE-EXCEPTION-001", "FLAG-N7-PRIVILEGE-MSR-POLICY-001", "FLAG-N8-SMP-FIRST-AP-001", "FLAG-N8-SMP-PERCPU-RUNTIME-001", "FLAG-N8-SMP-IPI-001", "FLAG-N8-SMP-MULTI-AP-001", "FLAG-N9-PMM-FOUNDATION-001", "FLAG-N9-VM-FOUNDATION-001", "FLAG-N9-VM-ACTIVE-001", "FLAG-N9-PMM-SCRUB-001", "FLAG-N9-PMM-METADATA-001", "FLAG-N9-PMM-RECLAIM-001", "FLAG-N9-PMM-GROWTH-001", "FLAG-N9-PMM-GROWTH-AUTOMATION-001", "FLAG-N9-PMM-ACPI-CONSUMER-001", "FLAG-N9-VM-DIRECT-MAP-001", "FLAG-N9-SMP-SHOOTDOWN-001", "FLAG-N12-SCHED-FOUNDATION-001", "FLAG-N12-SCHED-PREEMPT-001", "FLAG-N12-SCHED-DEFERRED-001", "FLAG-N12-SCHED-SMP-001", "FLAG-N12-SCHED-AP-WORKERS-001", "FLAG-N12-SCHED-SMP-PREEMPT-001", "FLAG-N12-CONCURRENCY-ATOMICS-001"}
                else "open",
                "phase_id": phase_id,
                "closure_condition": closure,
                "evidence": evidence,
            }
        )

    roadmap = {
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
            "last_updated_cycle": 172,
            "selected_move_id": "N12-CONCURRENCY-RECLAMATION-001",
            "immediate_next_move_id": "N0-GOVERNANCE-CUSTODY-001",
            "owner_independent_next_move_id": "N12-CONCURRENCY-RECLAMATION-001",
            "required_records": [
                "docs/checkpoints/cycle172-task-stack-ownership.md",
                "docs/checkpoints/cycle171-native-dependency-replay.md",
                "docs/checkpoints/cycle170-cpu-state-replay.md",
                "docs/checkpoints/cycle169-boot-chain-replay.md",
                "docs/checkpoints/cycle168-ap-ownership-qualification.md",
                "docs/production-goal-charter.md",
                "docs/pdc-production-build-plan.md",
                "runs/pdc_production_roadmap.json",
                "runs/pooleos_native_checklist_coverage.json",
                "runs/native_toolchain_qualification.json",
                "runs/adr_ratification_readiness.json",
                "security/governance-key-registration.json",
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
                "runs/native-kernel-interrupt-time-readiness.json",
                "runs/native-kernel-smp-first-ap-readiness.json",
                "runs/native-kernel-smp-percpu-runtime-readiness.json",
                "runs/native-kernel-smp-ipi-readiness.json",
                "runs/native-kernel-scheduler-readiness.json",
                "runs/native-kernel-scheduler-preemption-readiness.json",
                "runs/native-kernel-scheduler-deferred-readiness.json",
                "runs/native-kernel-scheduler-smp-readiness.json",
                "runs/native-kernel-scheduler-ap-workers-readiness.json",
                "runs/native-kernel-scheduler-smp-preempt-readiness.json",
                "runs/native-kernel-atomics-readiness.json",
                "runs/native-kernel-locks-readiness.json",
                "runs/native-kernel-reclamation-core-readiness.json",
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
            "pooleos_cycle": 172,
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
                "passed_checks": 105,
                "total_checks": 105,
                "artifact_count": 62,
                "explicit_gap_count": len(PROGRAM_GAPS),
                "production_ready": False,
                "native_promotion_role": "partially_qualified_development_candidate_non_promoting",
                "qualification_status": "selected_native_and_host_stack_checks_pass_full_qualification_pending",
                "passed_check_count_scope": "historical_cycle171_exact_final_canonical_audit",
                "current_cycle_full_canonical_audit_performed": False,
                "last_fully_qualified_cycle": 171,
                "last_fully_qualified_passed_checks": 105,
                "current_candidate_audit": {
                    "cycle": 172,
                    "status": "not_run",
                    "applies_to_current_source": False,
                    "aggregate_suite_passed": False,
                    "merge_requires_runtime_inclusive_exact_final_qualification": True,
                    "production_ready": False,
                },
                "historical_cycle171_canonical_replay": {
                    "cycle": 171,
                    "passed_checks": 105,
                    "doctor_passed_checks": 708,
                    "doctor_total_checks": 708,
                    "pooleos_test_count": 943,
                    "tracked_file_count": 1527,
                    "tracked_source_unchanged": True,
                    "both_bundle_and_replay_inputs_supplied": True,
                    "include_runtime": True,
                    "final_receipt_sha256": "4F140A6AFD8EB92B65C6F3A2083D77C023E94B1FAB10BDDE7E4B27CC69F9F077",
                    "initial_failed_receipt_sha256": "DCF4E94EB215A07E22A1AC0D5F2179C28C30B54596C5A1FA5DEA8EF77388C792",
                    "initial_failure": "TLC_evidence_directory_permission_denied_no_source_change_on_repair",
                    "publication_receipt_sha256": "0DEB220325E6D999CC5717338F742998B9D93019BF2DFEA9B0418D3CB84F537E",
                    "qualified_source_commit": "c3551e43f76c4f5aca2f50191e8f12b18e11d02f",
                    "merged_main_commit": "8006c7be3a8fdbe314fa049f7161285f4def03cb",
                    "merged_tree": "1499017b20234037b55663b413cb9469a696260d",
                    "pull_request_number": 76,
                    "applies_to_current_source": False,
                    "production_ready": False,
                },
                "historical_cycle165_canonical_replay": {
                    "cycle": 165,
                    "passed_checks": 105,
                    "doctor_passed_checks": 708,
                    "doctor_total_checks": 708,
                    "pooleos_test_count": 924,
                    "tracked_file_count": 1519,
                    "tracked_source_unchanged": True,
                    "both_bundle_and_replay_inputs_supplied": True,
                    "include_runtime": True,
                    "final_receipt_sha256": "621EFC831F7FB4F29990D2E27CD26FC6BB78B6AE11453FAB856BF7615B7DED34",
                    "merged_main_commit": "6f9399c3cd70ebef2f7610f8b6fdb40ae262e27f",
                    "merged_tree": "c20156f18d2727f7e3c1df73ac05ad8126b9f470",
                    "applies_to_current_source": False,
                    "production_ready": False,
                },
                "historical_cycle162_candidate_audit": {
                    "cycle": 162,
                    "applies_to_current_source": False,
                    "status": "fail",
                    "passed_checks": 81,
                    "failed_checks": 24,
                    "doctor_passed_checks": 683,
                    "doctor_total_checks": 706,
                    "stale_native_receipt_checks": 23,
                    "aggregate_suite_passed": False,
                    "both_bundle_and_replay_inputs_supplied": True,
                    "include_runtime": False,
                    "separate_pooleglyph_runtime_checks_passed": 2,
                    "separate_runtime_checks_do_not_change_audit_counts": True,
                    "audited_source_base_commit": "a4c3c27fdfb5447e2a458066f97c62e5634962d4",
                    "audited_tree": "uncommitted_pre_closeout_candidate",
                    "receipt_sha256": "09AB1890FF3095F9D332B139BFCE352B977C266F13D98A6CCC1CE2600B877407",
                    "scope": "pre_closeout_failed_audit_not_exact_final_qualification",
                    "merge_requires_runtime_inclusive_exact_final_qualification": True,
                    "production_ready": False,
                },
                "historical_cycle161_candidate_audit": {
                    "cycle": 161,
                    "status": "pass",
                    "passed_checks": 105,
                    "failed_checks": 0,
                    "doctor_passed_checks": 708,
                    "doctor_total_checks": 708,
                    "stale_native_receipt_checks": 0,
                    "aggregate_suite_passed": True,
                    "both_bundle_and_replay_inputs_supplied": True,
                    "audited_source_base_commit": "0fa2738ae6f4d369d0dcba7fa53ce545e2b5c2dd",
                    "audited_tree": "uncommitted_pre_closeout_candidate",
                    "receipt_sha256": "5F7F3DEBE21ADA7974016D2EB112E141BBE664E5A18F95F96CCB248102027A46",
                    "scope": "actual_pre_closeout_audit_final_replay_still_required",
                    "production_ready": False,
                },
                "historical_cycle161_canonical_replay": {
                    "cycle": 161,
                    "passed_checks": 105,
                    "doctor_passed_checks": 708,
                    "doctor_total_checks": 708,
                    "pooleos_test_count": 917,
                    "both_bundle_and_replay_inputs_supplied": True,
                    "pre_closeout_receipt_sha256": "5F7F3DEBE21ADA7974016D2EB112E141BBE664E5A18F95F96CCB248102027A46",
                    "final_receipt_sha256": "B41996D9D9725C767B232C1E191A5C364B958E1DD1A516C070A071AB0BDEAD39",
                    "merged_main_commit": "a4c3c27fdfb5447e2a458066f97c62e5634962d4",
                    "merged_tree": "110d78ecce5287388b81ff85924458470ee1bb3e",
                    "merge_requires_exact_final_replay_publication_and_review_checks": True,
                    "production_ready": False,
                },
                "current_focused_source_projection": {
                    "cycle": 172,
                    "scope": "27_selected_native_checks_not_full_canonical_audit",
                    "passed_checks": 27,
                    "total_checks": 27,
                    "pending_downstream_native_checks": 0,
                    "prior_smp_new_boot_artifact_set_replay_pending": False,
                    "final_receipt_fresh_qemu_runs": 0,
                    "fresh_qemu_run_count_scope": "no_new_cycle172_live_execution_existing_exact_image_receipts_revalidated",
                    "revalidated_dependency_execution_cycle": 171,
                    "separate_reclamation_source_check": "pass",
                    "core_qualification_stage_count": 17,
                    "lifetime_tests_per_host_profile": 34,
                    "pool_tests_per_host_profile": 19,
                    "kernel_host_tests_per_profile": 243,
                    "compile_fail_tests": 11,
                    "stack_test_methods": 10,
                    "stack_evidence_parser_rejection_cases": 40,
                    "canonical_full_replay_performed": False,
                    "next_dependency_move_id": "N12-CONCURRENCY-RECLAMATION-001",
                    "required_next_gate": "runtime_inclusive_exact_final_qualification_then_publication_and_review_before_merge",
                    "production_ready": False,
                },
                "historical_cycle171_source_projection": {
                    "cycle": 171,
                    "scope": "27_selected_native_checks_not_full_canonical_audit",
                    "passed_checks": 27,
                    "total_checks": 27,
                    "pending_downstream_native_checks": 0,
                    "prior_smp_new_boot_artifact_set_replay_pending": False,
                    "final_receipt_fresh_qemu_runs": 28,
                    "fresh_qemu_run_count_scope": "fourteen_final_cycle171_dependency_profiles_only",
                    "expected_tcg_limitation_probes": 0,
                    "superseded_initial_runs": 4,
                    "failed_guest_validation_runs": 0,
                    "negative_control_groups": 660,
                    "negative_control_cases": 2126,
                    "aggregate_gate_regression_cases": 58,
                    "replayed_cpu_gate_regression_cases": 17,
                    "boot_dependency_rejection_cases": 9,
                    "production_overclaim_rejections": 14,
                    "kernel_host_tests": 243,
                    "focused_python_tests": 155,
                    "focused_python_passed": 153,
                    "focused_python_skipped": 2,
                    "separate_reclamation_source_check": "pass",
                    "canonical_full_replay_performed": False,
                    "next_dependency_move_id": "N12-CONCURRENCY-RECLAMATION-001",
                    "required_next_gate": "runtime_inclusive_exact_final_qualification_then_publication_and_review_before_merge",
                    "production_ready": False
                },
                "historical_cycle170_source_projection": {
                    "cycle": 170,
                    "scope": "27_selected_native_checks_not_full_canonical_audit",
                    "passed_checks": 14,
                    "total_checks": 27,
                    "pending_downstream_native_checks": 13,
                    "prior_smp_new_boot_artifact_set_replay_pending": True,
                    "final_receipt_fresh_qemu_runs": 14,
                    "fresh_qemu_run_count_scope": "five_N7_profiles_final_cycle170_runs_only",
                    "expected_tcg_limitation_probes": 1,
                    "superseded_initial_runs": 0,
                    "failed_guest_validation_runs": 0,
                    "cpu_component_gates_passed": 5,
                    "negative_control_groups": 225,
                    "aggregate_gate_regression_cases": 17,
                    "kernel_host_tests": 243,
                    "focused_python_tests": 42,
                    "focused_python_passed": 42,
                    "focused_python_skipped": 0,
                    "separate_reclamation_source_check": "pass",
                    "canonical_full_replay_performed": False,
                    "next_dependency_move_id": "N9-PMM-ACPI-CONSUMER-001",
                    "required_next_gate": "memory_through_lock_replay_then_runtime_inclusive_exact_final_qualification",
                    "production_ready": False,
                },
                "historical_cycle169_source_projection": {
                    "cycle": 169,
                    "scope": "27_selected_native_checks_not_full_canonical_audit",
                    "passed_checks": 9,
                    "total_checks": 27,
                    "pending_downstream_native_checks": 18,
                    "prior_smp_new_boot_artifact_set_replay_pending": True,
                    "final_receipt_fresh_qemu_runs": 6,
                    "fresh_qemu_run_count_scope": "PKLOAD6_PooleBoot_PKXFER1_final_cycle169_runs_only",
                    "kernel_entry_runs": 2,
                    "superseded_initial_runs": 0,
                    "failed_guest_validation_runs": 0,
                    "boot_chain_component_gates_passed": 6,
                    "negative_controls_total": 678,
                    "differential_cases_total": 98304,
                    "kernel_host_tests": 243,
                    "focused_python_tests": 83,
                    "focused_python_passed": 83,
                    "focused_python_skipped": 0,
                    "separate_reclamation_source_check": "pass",
                    "canonical_full_replay_performed": False,
                    "next_dependency_move_id": "N7-TRAP-001",
                    "required_next_gate": "downstream_replay_then_runtime_inclusive_exact_final_qualification",
                    "production_ready": False,
                },
                "historical_cycle168_source_projection": {
                    "cycle": 168,
                    "scope": "27_selected_native_checks_not_full_canonical_audit",
                    "passed_checks": 4,
                    "total_checks": 27,
                    "pending_downstream_native_checks": 23,
                    "final_receipt_fresh_qemu_runs": 2,
                    "fresh_qemu_run_count_scope": "two_final_PKAPOWN1_PKSMP5_four_vcpu_runs",
                    "superseded_initial_runs": 4,
                    "failed_guest_validation_runs": 1,
                    "negative_control_groups": 30,
                    "negative_control_cases": 249,
                    "kernel_host_tests": 243,
                    "focused_python_tests": 56,
                    "focused_python_passed": 56,
                    "focused_python_skipped": 0,
                    "separate_reclamation_source_check": "pass",
                    "canonical_full_replay_performed": False,
                    "next_dependency_move_id": "N5-SYMBOLS-SEMANTICS-001",
                    "required_next_gate": "changed_image_dependency_replay_then_runtime_inclusive_exact_final_qualification",
                    "production_ready": False,
                },
                "historical_cycle165_source_projection": {
                    "cycle": 165,
                    "scope": "27_selected_native_checks_not_full_canonical_audit",
                    "passed_checks": 27,
                    "total_checks": 27,
                    "pending_downstream_native_checks": 0,
                    "final_receipt_fresh_qemu_runs": 28,
                    "fresh_qemu_run_count_scope": "fourteen_final_memory_through_lock_profiles_in_cycle165",
                    "superseded_initial_runs": 6,
                    "negative_control_groups": 660,
                    "negative_control_cases": 2120,
                    "kernel_host_tests": 228,
                    "native_dependency_component_gates_passed": 14,
                    "focused_python_tests": 142,
                    "focused_python_passed": 140,
                    "focused_python_skipped": 2,
                    "release_boundary_controls": 14,
                    "stale_acceptance_pin_controls": 25,
                    "canonical_full_replay_performed": False,
                    "required_next_gate": "runtime_inclusive_exact_final_qualification_publication_and_merge_review",
                    "next_dependency_move_id": "N12-CONCURRENCY-RECLAMATION-001",
                    "production_ready": False,
                },
                "historical_cycle164_source_projection": {
                    "cycle": 164,
                    "scope": "27_selected_native_checks_not_full_canonical_audit",
                    "passed_checks": 13,
                    "total_checks": 27,
                    "pending_downstream_native_checks": 14,
                    "final_receipt_fresh_qemu_runs": 14,
                    "fresh_qemu_run_count_scope": "five_N7_profiles_across_cycle164_including_six_pre_backup_trap_runs",
                    "expected_tcg_limitation_probes": 1,
                    "negative_control_groups": 225,
                    "kernel_host_tests": 228,
                    "n7_live_component_gates_passed": 5,
                    "focused_python_tests": 41,
                    "focused_python_scope": "five_live_profiles_plus_unchanged_pure_errata_policy",
                    "canonical_full_replay_performed": False,
                    "next_dependency_move_id": "N9-PMM-ACPI-CONSUMER-001",
                    "production_ready": False,
                },
                "historical_cycle163_source_projection": {
                    "cycle": 163,
                    "scope": "27_selected_native_checks_not_full_canonical_audit",
                    "passed_checks": 8,
                    "total_checks": 27,
                    "pending_downstream_native_checks": 19,
                    "final_receipt_fresh_qemu_runs": 6,
                    "fresh_qemu_run_count_scope": "PKLOAD6_PooleBoot_PKXFER1_final_runs_only",
                    "kernel_entry_runs": 2,
                    "kernel_host_tests": 228,
                    "boot_chain_component_gates_passed": 6,
                    "focused_python_tests": 70,
                    "valid_calendar_date_cases": 6,
                    "invalid_calendar_date_cases": 20,
                    "canonical_full_replay_performed": False,
                    "next_dependency_move_id": "N7-TRAP-001",
                    "production_ready": False,
                },
                "historical_cycle162_source_projection": {
                    "cycle": 162,
                    "scope": "27_selected_native_checks_not_full_canonical_audit",
                    "passed_checks": 4,
                    "total_checks": 27,
                    "pending_downstream_native_checks": 23,
                    "final_receipt_fresh_qemu_runs": 2,
                    "fresh_qemu_run_count_scope": "PKVM3_only_final_exact_kernel_and_source",
                    "negative_control_groups": 48,
                    "kernel_host_tests": 228,
                    "retained_free_rejections_per_run": 6,
                    "canonical_full_replay_performed": False,
                    "next_dependency_move_id": "N5-SYMBOLS-SEMANTICS-001",
                    "production_ready": False,
                },
                "historical_cycle161_source_projection": {
                    "cycle": 161,
                    "scope": "all_26_selected_native_dependency_checks_not_full_canonical",
                    "passed_checks": 26,
                    "total_checks": 26,
                    "pending_downstream_native_checks": 0,
                    "final_receipt_fresh_qemu_runs": 28,
                    "fresh_qemu_run_count_scope": "fourteen_requalified_memory_through_lock_profiles_in_cycle161",
                    "excluded_overlapping_scheduler_runs": 2,
                    "negative_control_groups": 658,
                    "negative_control_cases": 2118,
                    "kernel_host_tests": 219,
                    "production_overclaim_controls": 14,
                    "valid_calendar_date_cases": 6,
                    "invalid_calendar_date_cases": 20,
                    "canonical_full_replay_performed": False,
                    "projection_sha256": "1C353A94A929736E47B9AAABD627415DF27CB4AC182127E394A2E5E5BDB657E1",
                    "next_dependency_move_id": "N12-CONCURRENCY-RECLAMATION-001",
                    "production_ready": False,
                },
                "historical_focused_source_projection": {
                    "cycle": 157,
                    "scope": "all_26_selected_native_dependency_checks",
                    "passed_checks": 26,
                    "total_checks": 26,
                    "pending_downstream_native_checks": 0,
                    "final_receipt_fresh_qemu_runs": 24,
                    "negative_control_groups": 421,
                    "negative_control_cases": 1881,
                    "kernel_host_tests": 214,
                    "production_overclaim_controls": 12,
                    "schema_error_reporting_controls": 3,
                    "canonical_full_replay_performed": False,
                    "projection_sha256": "097E8880ECDD525A4ED1C1CB6E2F5C55B9C1A98869DCE278FE2A8047939C18EE",
                    "next_dependency_move_id": "N12-CONCURRENCY-RECLAMATION-001",
                },
                "current_ownership_qualification": {
                    "cycle": 172,
                    "scope": "host_inactive_task_stack_retention_and_separate_cycle171_live_AP_evidence",
                    "host_qualification_cycle": 172,
                    "live_receipt_scope": "two_final_cycle171_exact_four_vcpu_PKSMP5_runs",
                    "live_receipt_source_current": True,
                    "source_current_scope": "declared_inputs_current_boot_artifact_set_and_transfer_dependency",
                    "current_boot_artifact_set_replay_pending": False,
                    "live_replay_cycle": 171,
                    "fresh_current_cycle_qemu_runs": 0,
                    "lifetime_tests_per_host_profile": 34,
                    "pool_tests_per_host_profile": 19,
                    "kernel_tests_per_host_profile": 243,
                    "retention_test_count": 20,
                    "ap_resource_test_count": 11,
                    "compile_fail_tests": 11,
                    "kernel_sha256": "8A2DA65C86B09F7BCF2D5ACDB90029A5B7B7361581BA841ADC3B62AEE168B625",
                    "qemu_run_count": 2,
                    "attempts_per_run": 2,
                    "retained_free_rejections_per_attempt": 27,
                    "owner_release_rejections_per_attempt": 18,
                    "ap_runtime_live_integration_verified": True,
                    "task_stack_live_integration_verified": False,
                    "current_candidate_full_gate_passed": False,
                    "active_root_current_image_replay_complete": True,
                    "general_task_CPU_retirement_integration_verified": False,
                    "reclamation_receipt_sha256": "AFD1ABBE7EB217A132C0D9596004EC20AB2910CC23AEBD64D52E55EE645EF1D5",
                    "entry_receipt_sha256": "0BC2368946D26877B0214211EBA0EC62958C62AADE0A1C31965EE7C5D2F6F42B",
                    "smp_receipt_sha256": "6B5323FB9C85844FF66D532B2CF96EF10F9C870F561686E1320BBF488298EC71",
                    "production_ready": False,
                },
                "current_task_stack_qualification": {
                    "cycle": 172,
                    "contract_id": "PKSTACK1",
                    "scope": "prepared_inactive_task_stack_retention_and_scrubbed_release",
                    "receipt_path": "runs/native-kernel-reclamation-core-readiness.json",
                    "receipt_sha256": "AFD1ABBE7EB217A132C0D9596004EC20AB2910CC23AEBD64D52E55EE645EF1D5",
                    "receipt_schema_version": "1.5",
                    "page_count": 4,
                    "byte_count": 16384,
                    "stack_test_methods": 10,
                    "lifetime_tests_per_host_profile": 34,
                    "pool_tests_per_host_profile": 19,
                    "kernel_tests_per_host_profile": 243,
                    "compile_fail_tests": 11,
                    "host_profile_count": 2,
                    "scrub_fault_cases": 7,
                    "evidence_parser_rejection_cases": 40,
                    "single_manager_scrub_receipt_capacity_tested": 16,
                    "rejected_receipt_ordinal": 17,
                    "scheduler_generations_tested": 128,
                    "fresh_manager_every_task_batch": 8,
                    "linked_kernel_byte_identical": True,
                    "fresh_qemu_runs": 0,
                    "task_stack_live_verified": False,
                    "guarded_stack_mappings_verified": False,
                    "architectural_context_activation_verified": False,
                    "cross_cpu_quiescence_verified": False,
                    "automatic_scrub_receipt_growth_integrated": False,
                    "n12_3_complete": False,
                    "production_ready": False,
                },
                "historical_cycle171_ownership_qualification": {
                    "cycle": 168,
                    "scope": "mandatory_three_AP_runtime_stack_and_two_frame_retention",
                    "live_receipt_scope": "two_final_cycle171_exact_four_vcpu_PKSMP5_runs",
                    "live_receipt_source_current": True,
                    "source_current_scope": "declared_inputs_current_boot_artifact_set_and_transfer_dependency",
                    "current_boot_artifact_set_replay_pending": False,
                    "live_replay_cycle": 171,
                    "lifetime_tests_per_host_profile": 24,
                    "pool_tests_per_host_profile": 19,
                    "kernel_tests_per_host_profile": 243,
                    "retention_test_count": 20,
                    "ap_resource_test_count": 11,
                    "compile_fail_tests": 9,
                    "kernel_sha256": "8A2DA65C86B09F7BCF2D5ACDB90029A5B7B7361581BA841ADC3B62AEE168B625",
                    "qemu_run_count": 2,
                    "attempts_per_run": 2,
                    "retained_free_rejections_per_attempt": 27,
                    "owner_release_rejections_per_attempt": 18,
                    "ap_runtime_live_integration_verified": True,
                    "current_candidate_full_gate_passed": False,
                    "active_root_current_image_replay_complete": True,
                    "general_task_CPU_retirement_integration_verified": False,
                    "reclamation_receipt_sha256": "98646A6726A0925B58B2D1F554E9E3EDD03A582B02D83D2D30D3C83959D52CCB",
                    "entry_receipt_sha256": "0BC2368946D26877B0214211EBA0EC62958C62AADE0A1C31965EE7C5D2F6F42B",
                    "smp_receipt_sha256": "6B5323FB9C85844FF66D532B2CF96EF10F9C870F561686E1320BBF488298EC71",
                    "production_ready": False
                },
                "current_dependency_qualification": {
                    "cycle": 171,
                    "scope": "fourteen_native_memory_through_lock_profiles_on_cycle168_kernel",
                    "qualified_profiles": [
                        "physical_memory",
                        "virtual_memory",
                        "interrupt_time",
                        "smp_first_ap",
                        "smp_percpu_runtime",
                        "smp_ipi",
                        "scheduler",
                        "scheduler_preempt",
                        "scheduler_deferred",
                        "scheduler_smp",
                        "scheduler_ap_workers",
                        "scheduler_smp_preempt",
                        "atomics",
                        "locks"
                    ],
                    "kernel_sha256": "8A2DA65C86B09F7BCF2D5ACDB90029A5B7B7361581BA841ADC3B62AEE168B625",
                    "boot_chain_replay_pending": False,
                    "fresh_qemu_runs": 28,
                    "superseded_initial_runs": 4,
                    "superseded_profiles": [
                        "smp_ipi",
                        "scheduler_preempt"
                    ],
                    "negative_control_groups": 660,
                    "negative_control_cases": 2126,
                    "kernel_host_tests_per_qualifier": 243,
                    "focused_python_tests": 155,
                    "focused_python_passed": 153,
                    "focused_python_skipped": 2,
                    "memory_gate_rejection_cases": 20,
                    "host_identity_gate_rejection_cases": 38,
                    "boot_dependency_rejection_cases": 9,
                    "production_overclaim_rejection_cases": 14,
                    "receipt_bindings": [
                        {
                            "path": "runs/native-kernel-physical-memory-readiness.json",
                            "sha256": "3C6FBC663CB8110529789AC1A0EC90577223F92648E81DBD8422E6E00ECA071F",
                            "fresh_runs": 2,
                            "kernel_host_tests": 243,
                            "negative_groups": 191,
                            "negative_cases": 191,
                            "marker_count": 45
                        },
                        {
                            "path": "runs/native-kernel-virtual-memory-readiness.json",
                            "sha256": "64056FA11745713B8323245D551953CA2A7D8F2C1E52773D20A9709BE12F193D",
                            "fresh_runs": 2,
                            "kernel_host_tests": 243,
                            "negative_groups": 48,
                            "negative_cases": 48,
                            "marker_count": 40
                        },
                        {
                            "path": "runs/native-kernel-interrupt-time-readiness.json",
                            "sha256": "E74A03EAA6AAD28BF2B337F84FA21F01E9B174F8A5EDBB53A629C7055AE8013E",
                            "fresh_runs": 2,
                            "kernel_host_tests": 243,
                            "negative_groups": 58,
                            "negative_cases": 58,
                            "marker_count": 36
                        },
                        {
                            "path": "runs/native-kernel-smp-first-ap-readiness.json",
                            "sha256": "7BC1746699B5F44015B8480D5697F9389BC7D19DB5C35A234EC1337CEC5891A5",
                            "fresh_runs": 2,
                            "kernel_host_tests": 243,
                            "negative_groups": 72,
                            "negative_cases": 72,
                            "marker_count": 38
                        },
                        {
                            "path": "runs/native-kernel-smp-percpu-runtime-readiness.json",
                            "sha256": "77F0CF73C7EDD9B8B0DD1FAAE6BF0B8F36C87A94DE43736181C6976C8AE9D2F2",
                            "fresh_runs": 2,
                            "kernel_host_tests": 243,
                            "negative_groups": 19,
                            "negative_cases": 159,
                            "marker_count": 42
                        },
                        {
                            "path": "runs/native-kernel-smp-ipi-readiness.json",
                            "sha256": "6B5323FB9C85844FF66D532B2CF96EF10F9C870F561686E1320BBF488298EC71",
                            "fresh_runs": 2,
                            "kernel_host_tests": 243,
                            "negative_groups": 30,
                            "negative_cases": 249,
                            "marker_count": 40
                        },
                        {
                            "path": "runs/native-kernel-scheduler-readiness.json",
                            "sha256": "F2EBFF22B1D19E5938E4D479594094B254AB103B1E75B3C8B07893D1FA50C7C4",
                            "fresh_runs": 2,
                            "kernel_host_tests": 243,
                            "negative_groups": 28,
                            "negative_cases": 115,
                            "marker_count": 34
                        },
                        {
                            "path": "runs/native-kernel-scheduler-preemption-readiness.json",
                            "sha256": "00B746FC153EDE7A482A49EB7B11A49D90BE193B7FBED727FBA44A5FBAC4C5AE",
                            "fresh_runs": 2,
                            "kernel_host_tests": 243,
                            "negative_groups": 25,
                            "negative_cases": 178,
                            "marker_count": 35
                        },
                        {
                            "path": "runs/native-kernel-scheduler-deferred-readiness.json",
                            "sha256": "335849119664C13FC37A3C05CF9BA73F55E2AA7DBB61346410C39E1E631C813D",
                            "fresh_runs": 2,
                            "kernel_host_tests": 243,
                            "negative_groups": 30,
                            "negative_cases": 208,
                            "marker_count": 37
                        },
                        {
                            "path": "runs/native-kernel-scheduler-smp-readiness.json",
                            "sha256": "D06439B0C6C2D9F7C4DFE7D43D1CCDB38C6C319D7B9152319BC1C7CF9904F759",
                            "fresh_runs": 2,
                            "kernel_host_tests": 243,
                            "negative_groups": 32,
                            "negative_cases": 209,
                            "marker_count": 37
                        },
                        {
                            "path": "runs/native-kernel-scheduler-ap-workers-readiness.json",
                            "sha256": "30F85FC6E4CEB12865CA339DA774688409D17B3FBABAA16165C647FA55DC6186",
                            "fresh_runs": 2,
                            "kernel_host_tests": 243,
                            "negative_groups": 34,
                            "negative_cases": 226,
                            "marker_count": 37
                        },
                        {
                            "path": "runs/native-kernel-scheduler-smp-preempt-readiness.json",
                            "sha256": "5648ADC72109B6B7BFE26108053BAD51C553C9FF21839BE1A68883756FCA4BFF",
                            "fresh_runs": 2,
                            "kernel_host_tests": 243,
                            "negative_groups": 34,
                            "negative_cases": 232,
                            "marker_count": 38
                        },
                        {
                            "path": "runs/native-kernel-atomics-readiness.json",
                            "sha256": "A304D90154A61036B8FCD4C4C5DAB4FD26F46824420240FEBDD49A4C761586F2",
                            "fresh_runs": 2,
                            "kernel_host_tests": 243,
                            "negative_groups": 29,
                            "negative_cases": 78,
                            "marker_count": 41
                        },
                        {
                            "path": "runs/native-kernel-locks-readiness.json",
                            "sha256": "7676C54A75A30733891FB3A841FA2988D985AD44E97091614A56DE52F90BB66C",
                            "fresh_runs": 2,
                            "kernel_host_tests": 243,
                            "negative_groups": 30,
                            "negative_cases": 103,
                            "marker_count": 35
                        }
                    ],
                    "current_candidate_full_gate_passed": False,
                    "production_ready": False
                },
                "historical_cycle170_ownership_qualification": {
                    "cycle": 168,
                    "scope": "mandatory_three_AP_runtime_stack_and_two_frame_retention",
                    "live_receipt_scope": "two_final_exact_four_vcpu_PKSMP5_runs",
                    "live_receipt_source_current": True,
                    "source_current_scope": "declared_inputs_only_prior_boot_artifact_set",
                    "current_boot_artifact_set_replay_pending": True,
                    "live_replay_cycle": 168,
                    "lifetime_tests_per_host_profile": 24,
                    "pool_tests_per_host_profile": 19,
                    "kernel_tests_per_host_profile": 243,
                    "retention_test_count": 20,
                    "ap_resource_test_count": 11,
                    "compile_fail_tests": 9,
                    "kernel_sha256": "8A2DA65C86B09F7BCF2D5ACDB90029A5B7B7361581BA841ADC3B62AEE168B625",
                    "qemu_run_count": 2,
                    "attempts_per_run": 2,
                    "retained_free_rejections_per_attempt": 27,
                    "owner_release_rejections_per_attempt": 18,
                    "ap_runtime_live_integration_verified": True,
                    "current_candidate_full_gate_passed": False,
                    "active_root_current_image_replay_complete": False,
                    "general_task_CPU_retirement_integration_verified": False,
                    "reclamation_receipt_sha256": "98646A6726A0925B58B2D1F554E9E3EDD03A582B02D83D2D30D3C83959D52CCB",
                    "entry_receipt_sha256": "0BC2368946D26877B0214211EBA0EC62958C62AADE0A1C31965EE7C5D2F6F42B",
                    "smp_receipt_sha256": "E9C8A4A81AFF9C5BD9266C481C60012249228CA56E26399A6B99B5A8AF42FE24",
                    "production_ready": False,
                },
                "historical_cycle165_ownership_qualification": {
                    "cycle": 162,
                    "scope": "mandatory_active_PKVM3_table_and_data_retention",
                    "live_receipt_scope": "historical_cycle165_VM_replay",
                    "live_receipt_source_current": False,
                    "lifetime_tests_per_host_profile": 24,
                    "pool_tests_per_host_profile": 19,
                    "kernel_tests_per_host_profile": 228,
                    "retention_test_count": 16,
                    "compile_fail_tests": 7,
                    "kernel_sha256": "D0AA3295F66AF02D48476BCEDC44D962A873E98FBA21F48A6753AA7BB9B24EA4",
                    "qemu_run_count": 2,
                    "retained_free_rejections_per_run": 6,
                    "current_candidate_full_gate_passed": False,
                    "active_root_live_integration_verified": True,
                    "general_task_CPU_retirement_integration_verified": False,
                    "reclamation_receipt_sha256": "81FB5AA16D11CDF180433A6A11E97F357F418D6471A353A0D89348F8B485FACD",
                    "entry_receipt_sha256": "2A1F81312A64FF28CD7CDB4888BCBB5500FD6BCB6941248C60FFAFF390DC4A86",
                    "virtual_memory_receipt_sha256": "C14722C1C88F853915391A9AAA648DB3CD8A9DF58C70BE7B71D94C953AC05908",
                    "production_ready": False,
                    "live_replay_cycle": 165,
                },
                "historical_cycle162_ownership_qualification": {
                    "cycle": 162,
                    "scope": "mandatory_active_PKVM3_table_and_data_retention",
                    "live_receipt_scope": "historical_cycle162_VM_transfer_dependency_replay_pending",
                    "live_receipt_source_current": False,
                    "lifetime_tests_per_host_profile": 24,
                    "pool_tests_per_host_profile": 19,
                    "kernel_tests_per_host_profile": 228,
                    "retention_test_count": 16,
                    "compile_fail_tests": 7,
                    "kernel_sha256": "D0AA3295F66AF02D48476BCEDC44D962A873E98FBA21F48A6753AA7BB9B24EA4",
                    "qemu_run_count": 2,
                    "retained_free_rejections_per_run": 6,
                    "current_candidate_full_gate_passed": False,
                    "active_root_live_integration_verified": True,
                    "general_task_CPU_retirement_integration_verified": False,
                    "reclamation_receipt_sha256": "81FB5AA16D11CDF180433A6A11E97F357F418D6471A353A0D89348F8B485FACD",
                    "entry_receipt_sha256": "2A1F81312A64FF28CD7CDB4888BCBB5500FD6BCB6941248C60FFAFF390DC4A86",
                    "virtual_memory_receipt_sha256": "14E2328B646909AD982B83E972201B24991B7039FBE9CF417EF08BCD218B988F",
                    "production_ready": False,
                },
                "current_boot_chain_qualification": {
                    "cycle": 169,
                    "scope": "six_N5_components_on_unchanged_cycle168_kernel",
                    "kernel_sha256": "8A2DA65C86B09F7BCF2D5ACDB90029A5B7B7361581BA841ADC3B62AEE168B625",
                    "fresh_qemu_runs": 6,
                    "kernel_entry_runs": 2,
                    "kernel_host_tests": 243,
                    "loader_host_tests": 328,
                    "retained_file_count": 9,
                    "inner_artifact_bytes": 8761,
                    "retained_bytes": 11952,
                    "inner_set_sha256": "2DC54F8C02425C44DEB80A0F6285CAF4687A90537114902D39BB338C14BD7664",
                    "focused_python_tests": 83,
                    "symbol_entry_dependency_controls_added": True,
                    "receipt_bindings": [
                        {"path": "runs/native_symbol_readiness.json", "sha256": "9CA16D389EAC641FADC7DF310476F872C80255E1AFCA5566718C397A944B4170"},
                        {"path": "runs/native_policy_readiness.json", "sha256": "DFC63C64BF2550F45894D5193339BED011E54D33EC6555020BE5B32FE3AA4AE1"},
                        {"path": "runs/native_kernel_load_readiness.json", "sha256": "290EE8726EA27444DFFF1582E2AD412E21AAE38684DD4A2104A1244E0F57104B"},
                        {"path": "runs/native_pooleboot_readiness.json", "sha256": "C3840B0DCAA092FF0B8B283D087AA1908DDB1D39E53437C4FD1BDA2BDDE3CAA5"},
                        {"path": "runs/native-kernel-revalidation-readiness.json", "sha256": "973791A9F07E62B373C19B45AF03A3574AF038EA977C711B65ED44013891C810"},
                        {"path": "runs/native-kernel-transfer-readiness.json", "sha256": "296E089DAAE4EF5F2E908D8ECB4E4883F16EC93DDA33FFA68EECE04A966FA75F"},
                    ],
                    "current_candidate_full_gate_passed": False,
                    "production_ready": False,
                },
                "historical_cycle163_boot_chain_qualification": {
                    "cycle": 163,
                    "scope": "six_N5_components_same_kernel_no_production_promotion",
                    "kernel_sha256": "D0AA3295F66AF02D48476BCEDC44D962A873E98FBA21F48A6753AA7BB9B24EA4",
                    "inner_set_sha256": "864A7094E7ED3AFDF282791CC53D97D5D1CD4064E998D1678BD7ED79EBF6B79D",
                    "fresh_qemu_runs": 6,
                    "kernel_entry_runs": 2,
                    "retained_file_count": 9,
                    "focused_python_tests": 70,
                    "receipt_bindings": [
                        {"path": "runs/native_symbol_readiness.json", "sha256": "38CA1F7D1C3FB7A2C69A9185AFA73717509724E6F56B382CF2D897CC0CFEC8EA"},
                        {"path": "runs/native_policy_readiness.json", "sha256": "5D10ED417B85088BB37D936BD11097CBD8887943754E3A65021DB9E8EDC3E605"},
                        {"path": "runs/native_kernel_load_readiness.json", "sha256": "C3995D72501990BEA2F962762D487582E2E995228E69034B704F9C7E9290E041"},
                        {"path": "runs/native_pooleboot_readiness.json", "sha256": "FF0D8154527AEB8EA66FE30F826688652FE9CF48BE85D97B4CBADEBC15C47877"},
                        {"path": "runs/native-kernel-revalidation-readiness.json", "sha256": "BE2192F3D8FEEC60C7510161DADC54ED920EB58EAA9DF348C8E51CE2DEC0F038"},
                        {"path": "runs/native-kernel-transfer-readiness.json", "sha256": "7D07BDA3F3D967D570E22470C4B6890AA058BA5D617290CBDAA9EDFAFAEEEE75"},
                    ],
                    "production_ready": False,
                },
                "historical_cycle168_dependency_qualification": {
                    "cycle": 168,
                    "scope": "one_refreshed_SMP_profile_other_changed_image_dependencies_pending",
                    "kernel_sha256": "8A2DA65C86B09F7BCF2D5ACDB90029A5B7B7361581BA841ADC3B62AEE168B625",
                    "qualified_profiles": ["smp_ipi"],
                    "boot_chain_replay_pending": True,
                    "fresh_qemu_runs": 2,
                    "negative_control_groups": 30,
                    "negative_control_cases": 249,
                    "kernel_host_tests_per_qualifier": 243,
                    "receipt_bindings": [{
                        "profile": "smp_ipi",
                        "path": "runs/native-kernel-smp-ipi-readiness.json",
                        "sha256": "E9C8A4A81AFF9C5BD9266C481C60012249228CA56E26399A6B99B5A8AF42FE24",
                        "fresh_runs": 2, "kernel_host_tests": 243,
                        "negative_groups": 30, "negative_cases": 249, "marker_count": 40,
                    }],
                    "production_ready": False,
                },
                "historical_cycle165_dependency_qualification": {
                    "cycle": 165,
                    "scope": "fourteen_current_native_dependency_profiles_no_full_candidate_or_production_claim",
                    "kernel_sha256": "D0AA3295F66AF02D48476BCEDC44D962A873E98FBA21F48A6753AA7BB9B24EA4",
                    "fresh_qemu_runs": 28,
                    "superseded_initial_runs": 6,
                    "negative_control_groups": 660,
                    "negative_control_cases": 2120,
                    "kernel_host_tests_per_qualifier": 228,
                    "receipt_bindings": [
                        {
                            "profile": "physical_memory",
                            "path": "runs/native-kernel-physical-memory-readiness.json",
                            "sha256": "827F8AA1FB21FB40970A79F8804618EB0C94D114AC3897C9C195E0C5E10BC35E",
                            "fresh_runs": 2,
                            "kernel_host_tests": 228,
                            "negative_groups": 191,
                            "negative_cases": 191,
                            "marker_count": 45,
                        },
                        {
                            "profile": "virtual_memory",
                            "path": "runs/native-kernel-virtual-memory-readiness.json",
                            "sha256": "C14722C1C88F853915391A9AAA648DB3CD8A9DF58C70BE7B71D94C953AC05908",
                            "fresh_runs": 2,
                            "kernel_host_tests": 228,
                            "negative_groups": 48,
                            "negative_cases": 48,
                            "marker_count": 40,
                        },
                        {
                            "profile": "interrupt_time",
                            "path": "runs/native-kernel-interrupt-time-readiness.json",
                            "sha256": "5A009143E9145C7B1B37AA456E0963471EC40AA99E884162EE27B9CC12A49B54",
                            "fresh_runs": 2,
                            "kernel_host_tests": 228,
                            "negative_groups": 58,
                            "negative_cases": 58,
                            "marker_count": 36,
                        },
                        {
                            "profile": "smp_first_ap",
                            "path": "runs/native-kernel-smp-first-ap-readiness.json",
                            "sha256": "235AA56932A49B263CADC6300080015E8BCB5EAA8359A6C8D745489C29034F82",
                            "fresh_runs": 2,
                            "kernel_host_tests": 228,
                            "negative_groups": 72,
                            "negative_cases": 72,
                            "marker_count": 38,
                        },
                        {
                            "profile": "smp_percpu_runtime",
                            "path": "runs/native-kernel-smp-percpu-runtime-readiness.json",
                            "sha256": "0A0F26D034B602CCA37DF6E94AF4413BDD8DF09D9C3F45AF4A1102659E6561AE",
                            "fresh_runs": 2,
                            "kernel_host_tests": 228,
                            "negative_groups": 19,
                            "negative_cases": 159,
                            "marker_count": 42,
                        },
                        {
                            "profile": "smp_ipi",
                            "path": "runs/native-kernel-smp-ipi-readiness.json",
                            "sha256": "23B295573B47AF4EBED41013BA737B5F66D55C85EBAD852C1158A591DD014224",
                            "fresh_runs": 2,
                            "kernel_host_tests": 228,
                            "negative_groups": 30,
                            "negative_cases": 243,
                            "marker_count": 40,
                        },
                        {
                            "profile": "scheduler",
                            "path": "runs/native-kernel-scheduler-readiness.json",
                            "sha256": "B2115DB31AC2CE82E3DE21BF7F4F02FD5BE9B52BB1EEE965CAF28915DF89FBCC",
                            "fresh_runs": 2,
                            "kernel_host_tests": 228,
                            "negative_groups": 28,
                            "negative_cases": 115,
                            "marker_count": 34,
                        },
                        {
                            "profile": "scheduler_preempt",
                            "path": "runs/native-kernel-scheduler-preemption-readiness.json",
                            "sha256": "ADDAF44D3194B1C99195DF4F4AE0060D3184A52F623E86862D701D4999D262DA",
                            "fresh_runs": 2,
                            "kernel_host_tests": 228,
                            "negative_groups": 25,
                            "negative_cases": 178,
                            "marker_count": 35,
                        },
                        {
                            "profile": "scheduler_deferred",
                            "path": "runs/native-kernel-scheduler-deferred-readiness.json",
                            "sha256": "69A8F65545E244B90EF9AA502093A6F7E88242C3A98ADA8AE9BB525D6943D1E8",
                            "fresh_runs": 2,
                            "kernel_host_tests": 228,
                            "negative_groups": 30,
                            "negative_cases": 208,
                            "marker_count": 37,
                        },
                        {
                            "profile": "scheduler_smp",
                            "path": "runs/native-kernel-scheduler-smp-readiness.json",
                            "sha256": "9E69068D74514F195DE022BB5D3D3928C27A7A1A802344273F562A71AC3AA7D6",
                            "fresh_runs": 2,
                            "kernel_host_tests": 228,
                            "negative_groups": 32,
                            "negative_cases": 209,
                            "marker_count": 37,
                        },
                        {
                            "profile": "scheduler_ap_workers",
                            "path": "runs/native-kernel-scheduler-ap-workers-readiness.json",
                            "sha256": "B6A61B49B65EC1242E0C04C35D67C43ACC2D0BDA13E772C73BC06426C26ACB2A",
                            "fresh_runs": 2,
                            "kernel_host_tests": 228,
                            "negative_groups": 34,
                            "negative_cases": 226,
                            "marker_count": 37,
                        },
                        {
                            "profile": "scheduler_smp_preempt",
                            "path": "runs/native-kernel-scheduler-smp-preempt-readiness.json",
                            "sha256": "79695934C7CD68CEB12E1126668EEB2B60B46F9A01D96D18C75DDC6EDA8F150D",
                            "fresh_runs": 2,
                            "kernel_host_tests": 228,
                            "negative_groups": 34,
                            "negative_cases": 232,
                            "marker_count": 38,
                        },
                        {
                            "profile": "atomics",
                            "path": "runs/native-kernel-atomics-readiness.json",
                            "sha256": "721924F1653A399C56BAE3E16777C76870684D5F009A4C26173A3C4A5C6CE0BA",
                            "fresh_runs": 2,
                            "kernel_host_tests": 228,
                            "negative_groups": 29,
                            "negative_cases": 78,
                            "marker_count": 41,
                        },
                        {
                            "profile": "locks",
                            "path": "runs/native-kernel-locks-readiness.json",
                            "sha256": "A6A4A6399F87FAD16381189C90AF70A37B1C83264FA4D87DE80975B0FFD0E623",
                            "fresh_runs": 2,
                            "kernel_host_tests": 228,
                            "negative_groups": 30,
                            "negative_cases": 103,
                            "marker_count": 35,
                        },
                    ],
                    "production_ready": False,
                },
                "current_cpu_qualification": {
                    "cycle": 170,
                    "scope": "five_N7_live_profiles_same_kernel_no_production_promotion",
                    "kernel_sha256": "8A2DA65C86B09F7BCF2D5ACDB90029A5B7B7361581BA841ADC3B62AEE168B625",
                    "fresh_qemu_runs": 14,
                    "expected_tcg_limitation_probes": 1,
                    "negative_control_groups": 225,
                    "aggregate_gate_regression_cases": 17,
                    "focused_python_tests": 42,
                    "kernel_host_tests_per_qualifier": 243,
                    "whpx_exception_runs": 2,
                    "exception_deliveries_per_run": 3,
                    "exception_recoveries_per_run": 2,
                    "linked_exception_audit_passed": True,
                    "linked_msr_audit_passed": True,
                    "receipt_bindings": [
                        {"path": "runs/native-kernel-trap-readiness.json", "sha256": "EAA883E69CCD3384EC26CACCA40D02429FA1E6864DFDCE25379ED10495421ED6"},
                        {"path": "runs/native-kernel-cpu-policy-readiness.json", "sha256": "B59DF075082E5E10D83DF145C19FC78B47672C3CAAC836C3F685077BFACC9F5A"},
                        {"path": "runs/native-kernel-xstate-policy-readiness.json", "sha256": "AE8C489B41BCF65DA2A961102B4EB0CB6E08D7D85668B01BB463BD7B965AC729"},
                        {"path": "runs/native-kernel-xstate-exception-readiness.json", "sha256": "62D0CF78976709B736D23BE912EB0974F1B55DF6BBCA0D14E4D42DB54BD7C7F6"},
                        {"path": "runs/native-kernel-privilege-msr-policy-readiness.json", "sha256": "995F9ECBF6FDCE1D3D28DA17C86544DA73F97992CE9A34CB1B18C1F143F0A4F5"},
                    ],
                    "current_candidate_full_gate_passed": False,
                    "production_ready": False,
                },
                "historical_cycle164_cpu_qualification": {
                    "cycle": 164,
                    "scope": "five_N7_live_profiles_same_kernel_no_production_promotion",
                    "kernel_sha256": "D0AA3295F66AF02D48476BCEDC44D962A873E98FBA21F48A6753AA7BB9B24EA4",
                    "fresh_qemu_runs": 14,
                    "pre_backup_trap_runs_included": 6,
                    "expected_tcg_limitation_probes": 1,
                    "negative_control_groups": 225,
                    "focused_python_tests": 41,
                    "kernel_host_tests_per_qualifier": 228,
                    "whpx_exception_runs": 2,
                    "exception_deliveries_per_run": 3,
                    "exception_recoveries_per_run": 2,
                    "linked_exception_audit_passed": True,
                    "linked_msr_audit_passed": True,
                    "receipt_bindings": [
                        {"path": "runs/native-kernel-trap-readiness.json", "sha256": "B68232FF7FC5C121D8D16423D61BD54E4D1E0E03388C1EBF9DBA21246CD86234"},
                        {"path": "runs/native-kernel-cpu-policy-readiness.json", "sha256": "C6332B796B5B812B5751E3A33E4910CCE122C39AEF80DD92AAB63C5051891F3A"},
                        {"path": "runs/native-kernel-xstate-policy-readiness.json", "sha256": "BBA6B1312C832DA9C0BFE1669A4F65E83844F3666BDA4F79A205D8E8EEF0BA81"},
                        {"path": "runs/native-kernel-xstate-exception-readiness.json", "sha256": "F679F40FDD7E3E06D18784BAA1947EE5B4B22176A97B3177D048BDD268381E18"},
                        {"path": "runs/native-kernel-privilege-msr-policy-readiness.json", "sha256": "9573D12F8C939A22FD29BDF06D4CFBC3134EB9141785B8A72000E73BC16C3173"},
                    ],
                    "production_ready": False,
                },
                "historical_cycle158_ownership_qualification": {
                    "cycle": 158,
                    "scope": "mandatory_inactive_table_and_bound_frame_retention",
                    "lifetime_tests_per_host_profile": 24,
                    "pool_tests_per_host_profile": 19,
                    "kernel_tests_per_host_profile": 219,
                    "retention_test_count": 13,
                    "compile_fail_tests": 7,
                    "current_candidate_full_gate_passed": True,
                    "live_integration_verified": False,
                    "production_ready": False,
                },
                "candidate_replay_diagnostic": {
                    "cycle": 154,
                    "status": "failed_noncanonical_invocation",
                    "passed_checks": 83,
                    "total_checks": 105,
                    "artifact_count": 60,
                    "stale_downstream_native_checks": 19,
                    "doctor_passed_checks": 689,
                    "doctor_total_checks": 708,
                    "omitted_input_flags": ["--bundle", "--replay-proof"],
                    "corrected_input_checks_passed_separately": 2,
                    "canonical_full_replay_passed": False,
                    "diagnostic_sha256": "7FAFEF81C698C2BCABFE216E7FA9C04D39FE92ECC71B623BCCDDEAB01D538A45",
                    "input_correction_sha256": "B35EE5B3657A3B523F71A249589845A09C8E2CA82EEEBC441808101F71B0C713",
                },
                "historical_failed_candidate_audit": {
                    "cycle": 158,
                    "status": "fail",
                    "passed_checks": 80,
                    "failed_checks": 25,
                    "doctor_passed_checks": 684,
                    "doctor_total_checks": 708,
                    "stale_native_receipt_checks": 24,
                    "aggregate_suite_passed": False,
                    "both_bundle_and_replay_inputs_supplied": True,
                    "audited_source_commit": "bc5a1e4bed966507de7731d2e2184c6db8543255",
                    "receipt_sha256": "BB43C8A08A390893B48CDB8259752AC431D9A9AADBDDA63A2227EA347697DE4B",
                    "scope": "pre_closeout_audit_not_a_final_candidate_pass",
                    "production_ready": False,
                },
                "historical_canonical_replay": {
                    "cycle": 157,
                    "passed_checks": 105,
                    "doctor_passed_checks": 708,
                    "doctor_total_checks": 708,
                    "pooleos_test_count": 917,
                    "both_bundle_and_replay_inputs_supplied": True,
                    "pre_closeout_receipt_sha256": "09E28D0CB455D9D370102263D5F9B4FA0B02F5EE6A6F53401D6EC4A99C4040E6",
                    "merge_requires_exact_final_replay_publication_and_review_checks": True,
                    "production_ready": False,
                },
                "historical_cycle160_source_projection": {
                    "cycle": 160,
                    "scope": "twelve_current_source_N5_N7_checks_not_full_canonical_replay",
                    "passed_checks": 12,
                    "total_checks": 12,
                    "pending_downstream_native_checks": 14,
                    "final_receipt_fresh_qemu_runs": 14,
                    "fresh_qemu_run_count_scope": "five_requalified_N7_profiles_in_cycle160",
                    "expected_tcg_limitation_probes": 1,
                    "negative_control_groups": 225,
                    "kernel_host_tests": 219,
                    "loader_host_tests": 304,
                    "cpu_recorded_evidence_controls": 28,
                    "cpu_summary_gate_controls": 8,
                    "focused_python_test_count": 41,
                    "canonical_full_replay_performed": False,
                    "projection_sha256": "1AE89AD2A61EA0D7C3AD0CD76C857C9023B962525A6D7F619BAF5FAF6FA130BA",
                    "next_dependency_move_id": "N9-PMM-ACPI-CONSUMER-001",
                    "production_ready": False,
                },
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
            "id": "N0-GOVERNANCE-CUSTODY-001",
            "phase_ids": ["N0", "N1"],
            "title": "Verify the enrolled primary governance key and establish separately controlled recovery custody",
            "entry_evidence": ["security/governance-key-registration.json", "security/owner-adr-signers.allowed", "runs/adr_ratification_readiness.json", "docs/adr-ratification-ceremony.md"],
            "exit_evidence": ["owner-present namespaced enrollment signature verifies with the registered public key", "separately controlled recovery signer and hardware-handle custody verified", "exact architecture manifest prepared for the already authorized signing ceremony"],
            "blocked": True,
        },
        "claim_boundaries": [
            "Cycle 172 qualifies only prepared inactive PKSTACK1 task-stack retention and explicit scrubbed release. Its 34 lifecycle tests per host profile and exact source-bound receipt do not establish guarded stack mappings, live CPU context activation, hardware quiescence or automatic scrub-receipt growth. All 27 selected native checks pass by revalidation on an unchanged linked image; zero new QEMU boots are claimed. Historical Cycle 171 full qualification is separate. PR77 requires current exact-final runtime-inclusive qualification, publication and review gates; no phase, flag or production condition closes.",
            "Cycle 171 completes fourteen memory/IRQ/SMP/scheduler/atomic/lock profiles on the unchanged Cycle 168 kernel: 28 final headless boots, 660 control groups, 2126 rejected cases and 243 kernel host tests per qualifier. Four superseded boots are preserved separately. All 27 selected native checks pass. SMP evidence now binds current boot artifacts and rejects stale or malformed transfer dependencies; five new test methods cover nine rejection cases. The final 155-test focused suite passes with two optional local-transcript skips. Measured memory and host/image gate pins are reconciled with 20 memory and 38 stale-identity regression cases. Full runtime-inclusive exact-final qualification, publication and review gates still precede merge and N12.3 task-stack/CPU-retirement integration. Main stays qualified Cycle 165 at this pre-closeout checkpoint. No phase, flag or production gate closes.",
            "Cycle 170 requalifies five trap/CPU/xstate/MSR profiles on the unchanged Cycle 168 kernel: fourteen fresh headless boots, 225 marker controls and 42 passing focused tests. One expected TCG exception diagnostic is separate. The trap gate's stale identity pins are repaired and 17 aggregate-gate regression cases reject stale identity or production/authority claims. Fourteen of 27 selected checks pass; thirteen downstream checks plus prior SMP new-boot-artifact replay remain. Next is N9-PMM-ACPI-CONSUMER-001. Full runtime-inclusive canonical qualification is pending; main stays qualified Cycle 165. No phase, flag or production gate closes. Historical Cycle 169 requalifies six N5 components on the unchanged Cycle 168 kernel: six fresh headless boots, two kernel entries, nine-file revalidation and 83 passing focused tests. PSYM1 now binds source-current kernel-entry evidence and measured identities. Nine of 27 selected checks pass; 18 downstream checks and a new-boot-artifact replay of the prior SMP result remain pending. Next is N7-TRAP-001. Full canonical qualification has not run; main stays qualified Cycle 165. No phase, flag or production gate closes. Historical Cycle 168 qualifies mandatory AP runtime/stack and frame retention with two final four-vCPU boots, 27 copied-free and 18 owner-release rejections per partial/full attempt, 249 rejected cases, and 243 kernel host tests. The 147-page kernel has corrected build and mapping diagnostics. All 56 focused tests pass, including serialized receipt and ownership controls. Four of 27 selected native checks pass; 23 changed-image dependencies need replay beginning N5-SYMBOLS-SEMANTICS-001. Main contains exact-final qualified Cycle 165 through PR75. Current full canonical qualification, general task-stack ownership and CPU retirement remain open. No phase, flag or production gate closes.",
            "Cycle 165 completes fourteen current-kernel memory/VM/IRQ/SMP/scheduler/atomic/lock profiles with 28 final headless boots, 660 negative-control groups and 2120 rejected cases. Six superseded initial boots are excluded after three test-only corrections. All 27 selected native checks pass, and the 142-test profile/map/gate suite passes with two optional local-transcript skips. Native bytes are unchanged; data-frame scrub-before-reuse, execution-stack ownership, general CPU retirement and full runtime-inclusive exact-final qualification remain open. Main stays qualified Cycle 161, and no phase/flag or production gate closes. Historical Cycle 164 completes five N7 live profiles on the unchanged Cycle 162 kernel with fourteen successful headless boots, 225 marker controls and 41 focused Python tests. One expected TCG exception diagnostic is counted separately. The current selected projection passes 13/27; fourteen memory/VM/IRQ/SMP/scheduler/atomic/lock dependencies still need replay beginning N9-PMM-ACPI-CONSUMER-001. No current full canonical pass, phase closure, target qualification or production promotion is claimed. Main remains qualified Cycle 161. PooleGlyph, the frozen demo and all phase/flag statuses are unchanged. Historical Cycle 163 qualifies only the current-kernel N5 boot chain: six final headless boots, two kernel entries, independent nine-file agreement and 70 focused tests. The selected source projection passes 8/27; nineteen downstream receipts and full exact-final qualification remain pending. Calendar repairs cover two component validators, not the broader N36 schema engine. Main stays Cycle 161; PooleGlyph and demo bytes are unchanged. Historical Cycle 162 qualifies mandatory active PKVM3 table/data ownership and owner-authorized PMM cleanup on the exact 146-page D0AA3295 kernel: 228 kernel tests, 16 retention cases, two fresh headless boots, six retained-free rejections per run and 48 marker controls. The selected projection passes 4/27 checks; 23 changed-image dependencies still require replay beginning at N5-SYMBOLS-SEMANTICS-001. Main remains the fully qualified Cycle 161 tree merged by PR74. All earlier cycle claims below are historical. No execution-stack/general CPU-retirement completion, phase/flag closure, target qualification, demo rebase, release or production promotion follows",
            "Cycle 161 completes all fourteen downstream profile receipts: 28 final successful headless boots, 658 control groups, 2,118 rejected cases and 219 kernel host tests per qualifier. All 26 selected native checks and the 105-check/708-Doctor/917-test pre-closeout canonical suite pass. Two overlapping scheduler boots are excluded and replaced by a frozen-source rerun. No native Rust or frozen-demo bytes change; N0 custody, N12.3 active-root/execution-stack/CPU-retirement ownership and the broader N36 schema/evidence audit remain open. Exact-final qualification, publication and review checks are required before a main merge; no production promotion is claimed.",
            "Cycle 160 completes five current-kernel N7 live profiles with fourteen successful fresh headless boots, 225 marker controls and 41 focused Python tests; an expected TCG exception diagnostic is separate evidence. All twelve selected N5/N7 checks pass and fourteen downstream native checks remain stale. PKCPU1 recorded consistency is repaired with 28 receipt and eight summary/gate mutations after four genuine pre-fix acceptance failures; N36 broader review remains open. The preserved full Cycle 158 audit stays failed at80/105, not a current aggregate score. Next N9-PMM-ACPI-CONSUMER-001, then VM, IRQ/SMP, scheduler, atomics and locks before full qualification and merge. No native Rust or frozen-demo change, active-root/execution-stack completion, phase/flag closure, target qualification, key use, physical-media operation, release or production promotion follows. All counts and PooleGlyph Phase65/report hashes are preserved; draft PR74 holds the development checkpoint.",
            "Cycle 159 requalifies the unchanged Cycle 158 kernel's six selected N5 dependencies with six fresh headless boots, two actual entries, independently checked nine-file retained bytes and 68 focused Python tests. PKLOAD6 host coverage is304 and PKREVAL1 is219; previous build-ID substitution rejects. Nineteen N7-through-N12 native checks and the full aggregate remain pending, starting at N7-TRAP-001. The preserved failed Cycle158 audit remains80/105, not an invented current aggregate score. No kernel Rust changes, active-root/execution-stack ownership completion, physical boot, phase/flag closure, N5 exit, governance key use, firmware/media mutation, demo rebase, main merge or production promotion follows. Counts, PooleGlyph Phase65/user report and all locked checklist requirements are preserved. Draft PR74 backs up the current development branch.",
            "Cycle 158 adds mandatory allocator-backed ownership to inactive PKLIFE1 task roots and bound frames, including aliases and pending unmaps. Group operations validate all members before mutation and preserve full ownership on failure. Host proof is not active-root, execution-stack, raw-alias or CPU-quiescence proof. The changed linked image requires fresh dependency replay before a main merge; the complete Cycle 157 gate is historical only. N12.3, N36 and N0 remain open. No new guest/physical boot, phase/flag closure, key use, firmware/media mutation, demo rebase or production promotion follows.",
            "Historical Cycle 157 completes all twelve IRQ/SMP/scheduler/atomic/lock profiles with 24 final headless boots, 421 control groups and 1881 rejected cases. Its 26 selected dependency checks and complete 105-gate/708-Doctor/917-test suite passed; PR #73 merged the exact qualified tree as main 4ad5b11. Only bounded N12.2 closed again; the original checkpoint branch remains remotely preserved. This evidence is not inherited by changed Cycle 158 kernel bytes.",
            "Cycle 155 replays five N7 live profiles through fourteen fresh boots and 225 marker controls; the unchanged pure PKERR1 receipt remains current. Twelve selected N5/N7 gates pass, fourteen downstream native checks remain stale, and no full candidate aggregate or Doctor pass is claimed. PKTRAP1 recorded-run validation is repaired with 25 mutation cases and eight release-boundary controls; ADD-N36-RECEIPT-COVERAGE-001 and its open flag require the broader audit. No executable kernel bytes, main, demo, signing trust, firmware, physical media or production status change. Next re-derive PMM manager/layout/ownership accounting under N9-PMM-ACPI-CONSUMER-001, then replay VM, interrupts, SMP, scheduler, atomics and locks before full qualification and any merge. N12.2 and N12.3 remain open; N0 custody is separately blocked without requiring new owner action for this replay.",
            "Cycle 154 completes six current-source N5 boot-chain checks for the unmerged Cycle 153 image, not the overall N5 exit or candidate release gate. PSYM1 and PPOL1 dependency drift is repaired; two-run PKLOAD6/PooleBoot and PKXFER1 plus host PKREVAL1 agree on exact retained bytes and unsigned denial. 63 focused regressions pass. Replay N7-TRAP-001 then CPU, memory, SMP, scheduler, atomics and locks before N12.2 closure or merge; mandatory N12.3 ownership and independent lifetime oracle remain later work. N0 custody remains externally blocked; no owner action is needed for this development step. No governance/release key use, firmware mutation, physical-media write, demo rebase or production operation occurred. Isolated disposable signing fixtures in the full host suite confer no production trust.",
            "Cycle 153 is an unmerged native allocator/teardown candidate. Explicit retention protects pages from copied handles; tokens survive migration and ledger growth and fail closed when lost. The three-AP implementation now parks all APs before ending old-frame retention. The changed 144-page kernel and shifted retained layout invalidate prior current-candidate bindings; complete replay remains pending. The last fully qualified main baseline is Cycle 152. Mandatory ownership for all task resources, an independent lifecycle oracle and explicit live retention/failure evidence remain open. The separate demo is unchanged; N12.3 and production remain open.",
            "Cycle 152 PKLIFE1 composes the actual scheduler, object pool and inactive address spaces with generation-safe task-slot retention, exact-once resource return, cancellation, pending/running dispatch retention, timeout, shutdown and owner-loss handling. Nineteen new lifecycle tests pass in both host profiles and no unsafe code is added. Copyable PMM handles, active-root ownership, hardware quiescence, an independent lifecycle oracle and a new live selector remain open. Canonical linked kernel and the separate demo remain unchanged; N12.3 and production remain open.",
            "Cycle 151 provides the owner-requested unsigned QEMU-only optical demo with a demo-only PooleGlass static renderer. Two fresh four-vCPU optical boots pass PKLOCK1 and exact boot-frame comparison while canonical native source and kernel bytes stay unchanged. The OS-wide design system records PG-01 through PG-10 under FLAG-NATIVE-UI-001; N29.8 is partial only. No compositor, animation, installer, physical target, N5/N29/N39 exit or production claim follows; N12-CONCURRENCY-RECLAMATION-001 remains the next chronological kernel move.",
            "Cycle 150 implements and host-qualifies PKRECLAIM1-CORE only. The fixed-capacity no_std object pool uses PKLOCK1 admission and PKATOM1 pins, pool-bound nonwrapping generation handles, actual payload ownership, retirement, exact-once reclamation and shutdown retention. N12.3 and FLAG-N12-CONCURRENCY-RECLAMATION-001 remain open for scheduler/address-space lifecycle binding, acknowledged cross-CPU quiescence, failure rollback and two-run live evidence. Existing canonical linked kernel bytes are unchanged; no new guest execution, target, N12-exit or production claim follows.",
            "Post-Cycle 149 registration evidence supersedes historical unavailable-key statements for the primary signer only. Enrollment signature verification, recovery custody, architecture ratification, and production remain pending.",
            "Buildroot and Linux artifacts are historical reference evidence and cannot satisfy native PooleOS gates.",
            "Checklist mapping is not implementation completion.",
            "Host simulations and schemas are not native kernel enforcement.",
            "The Cycle 148 N12-CONCURRENCY-ATOMICS-001 receipt adds selector 21 PKATOM1 and closes only FLAG-N12-CONCURRENCY-ATOMICS-001 and N12.1. Typed load, store, exchange, compare-exchange, weak compare-exchange, integer and pointer read-modify-write operations, four typed order domains, nine valid and eleven rejected compare-exchange order pairs, fences, and a bounded reference count are allocation-free and compile only where 32-bit, 64-bit, and pointer atomics exist. Eight host-probe receipts cover 4,096 release/acquire publication rounds with zero stale reads, four-thread contention with 16,384 fetch-adds plus 4,096 CAS increments and zero lost updates, and 2,048 sequentially consistent rounds with zero forbidden outcomes. Two exact 41-marker qemu64 runs exercise process-to-interrupt release/acquire publication and interrupt-context acq_rel RMW before EOI; seven stable linked symbols are audited inside the pinned toolchain; 29 hostile-control categories cover 78 rejected cases. The canonical kernel is 513,672 bytes in a 585,728-byte, 143-page image with entry 0xA000, 1,289 relocations, and SHA-256 3CBDF56E90D957E62FC35EAEFF376580BEBDA3623FE4591AB6718984AB258EB7. This proves no general lock family, reclamation protocol, general SMP/topology, ring-3 or address-space switch, target hardware, N12 exit, release, or production readiness. ADD-N12-CONCURRENCY-LOCKS-001 and FLAG-N12-CONCURRENCY-LOCKS-001 preserve the next bounded dependency.",
            "The Cycle 149 N12-CONCURRENCY-LOCKS-001 receipt adds selector 22 PKLOCK1 and closes only FLAG-N12-CONCURRENCY-LOCKS-001 and N12.2. The allocation-free PKATOM1-based family implements FIFO ticket and IRQ-save spinlocks, a fixed-capacity sleeping mutex with direct bounded priority donation and seven-bypass fairness, FIFO notification, writer-preferred reader-writer locking, seqlocks, try and timed paths, five rank classes with cycle rejection, ownership and recursion checks, owner-death teardown, and exact failure rollback. Nine host receipts include 8,192 exact FIFO ticket acquisitions plus mutex, notification, reader-writer, and seqlock contention. Two exact 35-marker four-vCPU SandyBridge QEMU/OVMF runs exercise one shared live ticket lock across the BSP and three APs, yielding tickets 0,1,2,3, CPU mask 0xF, four acquisitions, a drained queue, cleared owner, and three installed then revoked aliases before the existing shootdown/park/release path. Ten focused lock tests within 206 kernel tests and 30 hostile-control categories covering 103 rejected cases pass. The canonical kernel is 513,680 bytes in a 585,728-byte, 143-page image with entry 0xA000, 1,295 relocations, and SHA-256 9029AEE51A4D557EF5B29945985E4A1F07C67DDE9C8C367C80BD1B9EDD9D409E. This proves no deferred reclamation or ABA-safe lifetime, general SMP/topology, ring-3 or address-space switch, target hardware, N12 exit, release, or production readiness. ADD-N12-CONCURRENCY-RECLAMATION-001 and FLAG-N12-CONCURRENCY-RECLAMATION-001 preserve the next bounded dependency.",
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
            "The Cycle 127 N9-VM-ACTIVE-001 receipt adds opt-in selector-10 PKVM2 after the PKVM1 foundation. A fixed-capacity no_std core allocates eight generation-bound DMA32 table pages plus one data frame, copies and audits exact inherited kernel, entry, guarded-stack, and handoff mappings, constructs a bounded supervisor RW/NX direct map over exactly those nine owned pages, and installs the candidate root on BSP 0 with interrupts disabled. It handles architectural Accessed/Dirty drift, host-tests CR3 and leaf-write rollback, binds protect/user-unmap/direct-unmap to three local invalidation receipts, rejects premature reuse, restores the exact original CR3, scrubs and releases both allocations, and revokes the bootstrap alias. The Cycle 128 image geometry rebind changes only its bootstrap adapter count: two exact fresh-vars qemu64 runs emit 40 markers and pass 46 hostile controls with 8,720 physical table writes, 5,368 bootstrap temporary-PTE writes and invalidations, two CR3 writes, three active local invalidations, zero shootdowns, and zero signatures, authority, or actions. This does not prove held-class reclaim, a complete direct map, SMP shootdown/deferred reclaim, ring 3, huge pages, PCID, COW, user faults, pager, heap, target hardware, N9 exit, release, or production readiness.",
            "The Cycle 128 N9-PMM-SCRUB-001 receipt upgrades selector-8 to PKPMM2. Allocation is planned before ownership commit, then every 64-bit word is zeroed and read back through one temporary supervisor RW/NX alias; release preflights extent reinsertion and retains ownership until the same full scrub verifies. Immutable receipts bind sequence, operation, range, generation, owner, and byte counts. Host faults prove partial allocation scrub and release-verification failures preserve ownership; the live exact-reuse path proves a nonzero stale pattern is absent. Two exact fresh-vars qemu64 runs emit 40 markers and pass 63 hostile controls plus 70 kernel host tests. They scrub and verify eight pages and 32,768 bytes, emit four receipts, perform 5,120 physical word writes, 6,144 reads, 28 temporary PTE writes and invalidations, revoke the alias, and restore zero allocated pages with zero reclaim, signatures, authority, actions, or production claims. The kernel geometry is rebound to 66 pages with 542 relocations, and all dependent PKENTRY1 through PKVM2 evidence is regenerated. This does not promote predecessor raw allocate/free APIs, a durable mapped metadata arena, held-class reclaim, concurrent or SMP allocation, target hardware, N9 exit, release, or production readiness.",
            "The Cycle 129 N9-PMM-METADATA-001 receipt upgrades selector-8 to PKPMM3 and moves the complete 14,616-byte physical-memory manager out of bootstrap stack storage. The manager reserves and scrubs five contiguous DMA32 pages, installs five persistent supervisor RW/NX mappings between absent low/high guards, copies all source, extent, allocation, and receipt ledgers, binds generation 1 and owner 19781, seals and validates the handoff, and retires the stack bootstrap only after exact verification. Mapping and handoff faults roll back reservations and mappings; deliberate mapped corruption is detected before the next public mutation; and every release path rejects metadata pages. Two exact fresh-vars qemu64 runs emit 41 markers and pass 87 hostile controls plus 74 kernel host tests. They manage 117,918 of 117,919 source-usable pages, protect 825 loader pages, retain five metadata pages and two guards, scrub and verify 13 pages and 53,248 bytes, perform 7,680 physical word writes, 8,704 reads, and 43 temporary-PTE writes and invalidations, and finish with exact handoff/final integrity and zero reclaim, signatures, authority, actions, or production claims. The kernel is rebound to 245,760 canonical bytes, 286,720 image bytes, 70 pages, 569 relocations, and SHA-256 F81F4B21F67A4A490AAE049C92B0E890A1D5B286DC708E41557DFCEBB37282DC; PKVM2 correspondingly records 5,432 bootstrap writes and invalidations. This does not prove held-class reclaim, scalable metadata growth, concurrent or SMP allocation, a complete direct map, target hardware, N9 exit, release, or production readiness.",
            "The Cycle 130 N9-PMM-RECLAIM-001 receipt upgrades selector-8 to PKPMM4. After explicit transition to PostExitBootServices, it streams the immutable PBP1 source ledger three times: complete capacity/arithmetic/retained-overlap preflight, full zero/readback, then infallible ownership/free-ledger commit. Seventy boot-services records coalesce into twelve ranges and admit 11,250 pages across DMA/DMA32 while eleven ACPI reclaimable pages remain held until AcpiTablesReleased. Exact repeat calls return the immutable receipt without physical access; early ACPI admission is rejected; and injected content faults preserve ownership, managed/free accounting, receipt state, and sequence while reporting partial scrub audit counters. A scalar ReclaimCursor replaces an initial dual-extent-array plan that exhausted the live bootstrap stack after PKREVAL1. Two exact fresh-vars qemu64 runs emit 42 markers and pass 109 hostile controls plus 79 kernel host tests. They finish with 129,168 managed pages, five retained metadata pages and two guards, 11,263 scrubbed and verified pages, 46,133,248 scrubbed and verified bytes, 5,767,680 physical word writes, 5,768,704 reads, and 22,543 temporary-PTE writes and invalidations. Range checksum 0x5A485D4A5725EED8 and receipt checksum 0x4D3EBF743B7F2CCC bind the admission. The kernel remains 245,760 canonical bytes in a 286,720-byte, 70-page image, now with 593 relocations and SHA-256 20BCE1C7501BC2344A6D7505BCDA749D9B2738A8435255D0EC2EF5A3E177CC4. This does not prove scalable metadata growth, ACPI table-consumer integration, concurrent or SMP allocation, a complete direct map, target hardware, N9 exit, release, or production readiness.",
            "The Cycle 131 N9-PMM-GROWTH-001 receipt upgrades selector-8 to PKPMM5. The five-page guarded manager becomes stable control state while source, free-extent, allocation, scrub-receipt, and reclaim-receipt storage moves into an external guarded generation. Two alternate 32-page virtual windows permit transactional preflight, reserve/map, copy, seal, active-generation switch, old-leaf revocation, full zero/readback, and physical retirement. Generation 2 starts in four pages with capacities 256/32/256/16/2 and explicitly grows to generation 3 in eight pages with capacities 512/64/512/32/4. Host faults prove precommit rollback and postcommit retirement retry; the independent Python oracle models the stable manager, retired initial hole, and active grown generation. Two exact fresh-vars qemu64 runs emit 43 markers and pass 137 hostile controls plus 82 kernel host tests. They manage 117,913 source-usable pages and 129,162 final pages, protect 831 loader pages, retire four old-generation pages, admit 11,250 Boot Services pages while holding eleven ACPI pages, scrub and verify 11,279 pages and 46,198,784 bytes, and perform 5,775,872 physical writes, 5,776,896 reads, and 22,591 temporary-PTE writes and invalidations. Growth checksum 0xFA339A347E3A3CAF binds the transaction. A shared bootstrap finalizer assumption exposed by the larger retained layout was corrected so VM-only profiles require zero active PMM ledgers; PKVM2 was rebound to 5,528 temporary writes and invalidations. The kernel is 270,336 canonical bytes in a 311,296-byte, 76-page image with 662 relocations and SHA-256 30E414826D7DF588C07A66032423DCD6AA8C47B0E6CCFC3D6686BC9224AFB947. This does not prove automatic pressure-triggered or repeated growth, ledger-window exhaustion/fallback, concurrency, SMP, target hardware, N9 exit, release, or production readiness.",
            "The Cycle 132 N9-PMM-GROWTH-AUTOMATION-001 receipt upgrades selector-8 to PKPMM6. Every automatic scrubbed allocate/free computes exact post-operation demand and reserves one allocation plus four scrub-receipt slots for complete failed-growth rollback and retry. The profile grows through 4/8/15/29-page generations with capacities ending at 2048/256/2048/128/16, revokes and scrub-retires three predecessors totaling 27 pages, records 121 pressure checks, eight triggers, three automatic growths, sixty successful cycles, and four soft fallbacks, then host-proves one hard pre-effect rejection because the 58-page next layout exceeds each bounded 32-page window. Two exact fresh-vars qemu64 runs retain 43 markers while 147 hostile controls and 84 kernel host tests pass. They manage 117,911 source-usable and 129,160 final pages, protect 833 loader pages, admit 11,250 Boot Services pages while holding eleven ACPI pages, scrub and verify 11,462 pages and 46,948,352 bytes, and perform 5,869,568 physical writes, 5,870,592 reads, and 22,798 temporary-PTE writes and invalidations. Growth checksum 0xF7AD111CA266071D binds the sequence. The retained-layout shift rebinds PKVM2 to 5,560 temporary writes and invalidations. A build-ID split discovered during closeout is fixed and guarded: PKMID1 and the live kernel diagnostic now both carry PKBUILD1-CYCLE132-N9-PMM-GROWTH-AUTOMATION-001. The kernel is 278,528 canonical bytes in a 319,488-byte, 78-page image with 667 relocations and SHA-256 CDF33067B2421550BB03A4796FF9A92AE54D40B2575188632BF2C208449B882E. This does not prove complete ACPI consumer integration, interrupt-context or concurrent allocation, SMP, general pressure/OOM policy, target hardware, N9 exit, release, or production readiness.",
            "The Cycle 133 N9-PMM-ACPI-CONSUMER-001 receipt upgrades selector-8 to PKPMM7 and the live handoff to PBLIVE4. PooleBoot records the UEFI ACPI 2.0 RSDP address; PKACPI1 validates RSDP and XSDT checksums, range and length bounds, then requires exactly one APIC, FACP, HPET, and MCFG table. It allocates and scrubs one retained page, copies 600 table bytes into a 616-byte snapshot, verifies readback, and advances to AcpiTablesReleased only with an opaque evidence token. Boot reclaim admits 11,250 pages under receipt 5DEA9A3BC9E10C18; the later ACPI transaction admits eleven pages under independent receipt 60DAA52A8A05ABD6. Missing, duplicate, malformed, checksum, range, allocation, copy, readback, rollback, early-reclaim, and repeat-call controls fail closed. Two exact qemu64 runs emit 45 markers and pass 191 hostile controls plus 88 kernel host tests. They manage 117,888 source-usable and 129,148 final pages, protect 856 loader pages, retain the ACPI snapshot, scrub and verify 11,473 pages and 46,993,408 bytes, and perform 5,875,277 physical writes, 5,879,957 reads, and 23,172 temporary-PTE writes and invalidations. The dependent PKVM2 count is 5,640. The kernel is 299,008 canonical bytes in a 339,968-byte, 83-page image with 693 relocations and SHA-256 D9EF9B10B56BF779B155BD18DE55853874CCC032D2A3E5E7841B918F08CDE1F2. This proves no AML execution, complete ACPI namespace/resource graph, SMP, target hardware, N9 exit, release, or production readiness.",
            "The Cycle 134 N9-VM-DIRECT-MAP-001 receipt upgrades selector-10 to PKVM3. PKPMM7 reconstructs an exact generation-bound direct-map manifest from free extents plus active non-release-excluded allocations, omits retained ownership, coalesces sparse ranges, and binds counts, gaps, write-back cache policy, and checksum before and after allocation. PKVM3 derives 237 occupied 2 MiB leaf regions and one 1 GiB directory, allocates 243 contiguous DMA32 table pages, maps all 117,887 admitted pages across eleven ranges, leaves 12,878 gap pages unmapped, rejects cache drift and forged manifests, and audits inherited kernel, guarded-stack, handoff, range-edge, and sparse-hole translations before activation. Three local leaf receipts protect and revoke the data aliases; any active-processor count other than one returns ShootdownRequired; exact CR3 restoration mints one root/generation/BSP/local-context-flush retirement receipt; and table reclamation rejects absent or stale receipts. Ninety-one kernel host tests and two exact 40-marker qemu64 runs pass 46 hostile controls with coverage checksum 0x341CF729ADB26B52, 367,474 physical table writes, and 950,234 temporary-PTE writes and invalidations. The exact Cycle 134 kernel remains 299,008 canonical bytes in a 339,968-byte, 83-page image with 729 relocations and SHA-256 5B581CC1D1ABEB163D0984D12144CA5016C44B46A28B190A6DFCBDCDA689A255. AP startup, inter-processor shootdown execution, generation-safe remote deferred reclaim, incremental concurrent map replacement, target hardware, N9 exit, release, and production readiness remain open.",
            "The Cycle 135 N8-IRQ-001 receipt adds selector-11 PKIRQ1 as a bounded one-BSP xAPIC/HPET substrate. It walks the retained validated MADT and HPET descriptions, validates BSP/APIC identity, reserves 51 vectors, installs guarded uncacheable LAPIC and HPET mappings, masks and restores the legacy PIC, calibrates a one-shot local APIC timer over a checked ten-millisecond HPET interval, and opens exactly eight interrupt windows. Two exact 36-marker qemu64 runs deliver and acknowledge eight timer interrupts with zero APIC-error, spurious, or remaining ISR bits; revoke both MMIO leaves; restore controller, clock, PIC, and IA32_APIC_BASE state; and pass 58 hostile controls plus 99 kernel host tests. The exact kernel is 323,584 canonical bytes in a 364,544-byte, 89-page image with 812 relocations and SHA-256 2ACD4A5EF30CA1A4A22711FD31E2A259A5C87D97BCE7FB1BF49A3488B3FC02B2. PKIRQ1 starts zero APs and implements no I/O APIC route, MSI/MSI-X, public time API, IPI, shootdown, target-hardware path, N8 exit, release, or production readiness. FLAG-N8-IRQ-001 remains open; N8-SMP-FIRST-AP-001 is next.",
            "The Cycle 136 N8-SMP-FIRST-AP-001 receipt adds selector-12 PKSMP1 after PKIRQ1. PooleKernel selects APIC ID 1 from the retained validated MADT, allocates fourteen contiguous pages below 1 MiB, builds a W^X identity hierarchy with four absent guard pages, and uses an RX 16-to-32-to-64-bit trampoline whose four GDT descriptors have their hardware-accessed bits pre-set. Two exact fresh-vars, two-vCPU qemu64 QEMU/OVMF runs each perform one INIT-SIPI-SIPI sequence, observe APIC ID 1 online in long mode with the required CR0/CR3/CR4/EFER and CPUID state, command stop, validate the dynamic mailbox checksum, observe quiescence, issue a final INIT park, revoke aliases, scrub and verify 57,344 bytes, and release all fourteen pages. Thirty-eight ordered markers, 72 hostile controls, and 111 kernel host tests pass. The exact kernel is 335,872 canonical bytes in a 376,832-byte, 92-page image with 855 relocations and SHA-256 6596CB332EB24813089F95A00AC979C892C47235943CB0E73E3979ED9901B725. A live triple-fault investigation found and fixed the RX-GDT accessed-bit write hazard. FLAG-N8-SMP-FIRST-AP-001 closes only this bounded lifecycle; general SMP, AP-local GDT/TSS/IDT/RSP0/IST/xstate/interrupt state, IPIs, shootdown, multi-AP and partial-start fault handling, target hardware, N8 exit, release, and production readiness remain open. N8-SMP-PERCPU-RUNTIME-001 is next.",
            "The Cycle 137 N8-SMP-PERCPU-RUNTIME-001 receipt adds selector-13 PKSMP2 after PKSMP1. In a frozen two-vCPU SandyBridge-minus-AVX TCG profile, one AP starts through the 16-to-32-to-64-bit trampoline, loads a processor-local GDT/TSS/IDT, guarded four-page RSP0 plus two-page IST1/IST2 stacks, x87/SSE owner state, and eight exception plus nineteen owned interrupt gates. The BSP verifies the hardware-busy TSS descriptor, all 27 gates, exact stack and xstate geometry, both FNV mailbox checksums, final INIT parking, and zero/readback release of all 32 pages or 131,072 bytes. Two exact 42-marker runs, 19 hostile-control categories covering 159 independently rejected cases, and 122 kernel host tests pass. The exact kernel is 409,600 canonical bytes in a 458,752-byte, 112-page image with 919 relocations and SHA-256 214F32214494E632063238337551C355BFED150B9B49846DB8A927584B8E47F0. FLAG-N8-SMP-PERCPU-RUNTIME-001 closes only this bounded one-AP runtime. General SMP, capability-gated IPI delivery, TLB shootdown, scheduler ownership, multi-AP and live partial-start fault injection, target hardware, N8 exit, release, and production readiness remain open. N8-SMP-IPI-001 is next.",
            "The Cycle 138 N8-SMP-IPI-001 receipt adds selector-14 PKSMP3 after PKSMP2. In the frozen two-vCPU SandyBridge-minus-AVX TCG profile, APIC ID 1 installs six fixed vectors and acknowledges six allowlisted operation classes behind a checksum-bound development capability. Two exact 39-marker runs observe six accepted and four denied deliveries, ten EOIs, one bounded offline-APIC timeout, panic latching, stop quiescence, final INIT parking, post-execution descriptor/xstate/APIC-table validation, capability and alias revocation, and exact scrub/release of all 32 pages or 131,072 bytes. Eighteen hostile-control categories cover 120 independently rejected cases and 130 kernel host tests pass. The exact kernel is 409,600 canonical bytes in a 458,752-byte, 112-page image with 959 relocations and SHA-256 6B8A9C2C3EAC559E1D9CB5965800A1671DB8F487F149861300D4EDCB279B3A11. FLAG-N8-SMP-IPI-001 closes only this bounded transport. The capability is a fixed development token; shootdown records transport only and performs zero TLB invalidations; call-function is one no-op token and exposes no arbitrary callback. Real generation-bound remote invalidation and deferred reclaim, scheduler ownership, multi-AP and live partial-start fault injection, I/O APIC/MSI, target hardware, N8/N9 exit, release, and production readiness remain open. N9-SMP-SHOOTDOWN-001 is next.",
            "Cycle 139 repairs one cross-platform release-integrity defect without advancing a kernel claim: PBTRUST1 and PKSMP3 readiness writers now force canonical LF before dependent hashes are captured, focused byte-level tests reject CRLF, and the affected trust-to-PooleBoot chain is requalified in dependency order. Cycle 138 kernel identity and behavior remain exact; phase status, flags, gaps, and production_ready=false are unchanged. N9-SMP-SHOOTDOWN-001 remains next.",
            "The Cycle 145 N12-SCHED-SMP-001 receipt adds selector 18 PKSCHED4 and closes only FLAG-N12-SCHED-SMP-001 for one exact BSP-0/AP-1,2,3 SandyBridge-minus-AVX development topology. Four fixed run queues and eight generation-tagged task slots commit one cross-CPU wake and two migrations only after exact AP acknowledgements; each AP dispatches two local tasks and the BSP dispatches two. One deliberate APIC-4 timeout preserves the source queue and owner epoch, withholds target ownership, and rejects a late acknowledgement; a stale task generation is also rejected. All eight tasks retire, four idle owners are observed, all three APs quiesce and park, and 102 pages or 417,792 bytes are scrubbed, verified, and released. Eight focused tests within 173 kernel host tests, five exact Rust/Python host receipts, two exact 37-marker four-vCPU boots, and 32 hostile-control categories covering 209 rejected cases pass. A necessary PKENTRY1 layout expansion preserves entry 0xA000 and the 557,056-byte, 136-page memory image while moving text end to 0x66000 and RELRO end to 0x74000. Downstream PKVM3 replay then exposed a bootstrap-stack low-guard write at RSP/CR2 FFFFFFFF80088BC8; the shared retained stack is now 36 pages, the active-VM consumer derives the common constant, and leaf 511 remains spare. The repaired canonical kernel is 476,808 bytes with 1,181 relocations and SHA-256 9C23236E85A6D2C7AEEFDA12F3CEC202DC3BF34B89D9CEAEEBB7037A079DA168. This proves no general topology/hotplug/x2APIC scheduling, general SMP timer preemption, AP-local deferred workers or driver/service consumers, arbitrary callbacks, ring-3 or address-space switch, full per-task architectural ownership, target hardware, N12 exit, release, or production readiness. ADD-N12-SCHED-AP-WORKERS-001 and FLAG-N12-SCHED-AP-WORKERS-001 preserve the next bounded dependency.",
            "The Cycle 144 N12-SCHED-DEFERRED-001 receipt adds selector 17 PKSCHED3 and closes only FLAG-N12-SCHED-DEFERRED-001. An allocation-free eight-slot controller uses generation-safe IDs, typed Add/Xor/Fence tokens, duplicate suppression, EOI-bound dispatch permits, a maximum three-item high-priority bypass, queued and running cancellation, flush watermarks, exact retirement, and five fault rollback boundaries. One real local-APIC timer top half enqueues eight items and issues EOI before six worker dispatches. Two fixed BSP workers run on private 16-KiB stacks inside the retained bootstrap partition, alternate across slots 0,2,4,1,5,6, enter three times each, and perform twelve hardware context transitions. Five items complete, three cancel, all eight retire, all 32,768 stack bytes clear, and LAPIC/HPET/PIC/MMIO state is restored. Seven focused tests within 165 kernel host tests, five independent Rust/Python host-probe receipts, two exact 37-marker qemu64 BSP runs, and 30 hostile-control categories covering 208 rejected cases pass. The kernel is 460,424 canonical bytes in a 557,056-byte, 136-page image with 1,125 relocations and SHA-256 FC13CF79E94318FAE10AFF9E7198036B30C587CF2BFD10457A045ACC6EB7665E. This proves no arbitrary callbacks, driver/service consumers, live AP dispatch, cross-CPU migration, ring-3 or address-space switch, production capability authority, target hardware, N12 exit, release, or production readiness. ADD-N12-SCHED-SMP-001 and FLAG-N12-SCHED-SMP-001 record N12-SCHED-SMP-001 as the next owner-independent move.",
            "The Cycle 143 N12-SCHED-PREEMPT-001 receipt adds selector 16 PKSCHED2 and closes only FLAG-N12-SCHED-PREEMPT-001. It composes PKSCHED1 with the PKIRQ1 local-APIC one-shot path through an exact 176-byte interrupt frame and a fixed eight-event controller. Two exact 35-marker qemu64 BSP runs open six timer windows, acknowledge six EOIs, and produce task trace 0,1,2,0,3,3 with causes none,quantum,wake,block,wake,none. They save six and restore four frames, perform four hardware context switches, enter each of four 16-KiB task stacks once, retire all contexts, and clear all 65,536 stack bytes. Seven focused tests within 158 kernel host tests, three independent Rust/Python host-probe receipts, and 25 hostile-control categories covering 178 rejected cases pass. The kernel is 443,504 canonical bytes in a 557,056-byte, 136-page image with 1,086 relocations and SHA-256 A5DE1DBD2ECA9243D90C2EAA2BEDCAC4B0FCC5E4A4779073E398C6722F30B943. This proves no deferred workers, live AP dispatch, cross-CPU migration, ring-3 or address-space switch, production capability authority, target hardware, N12 exit, release, or production readiness. N12-SCHED-DEFERRED-001 is next.",
            "The Cycle 142 N12-SCHED-001 receipt adds selector 15 PKSCHED1 as a bounded scheduler and context-switch foundation. The allocation-free four-CPU/eight-task core freezes generation-safe task identity, four fixed-capacity run queues, priorities 1-31, maximum bypass 7, affinity, modeled migration, accounting, yield, block, exact wake/cancel/timeout delivery, teardown, one-mutex direct priority inheritance, bounded reference lifetime, and a raw spinlock. A deterministic Rust/Python host campaign agrees over 4,096 steps, 1,761 dispatches, 2,334 migrations, and checksum 0x23B76E2F80E2B747. Two exact 17-marker qemu64 BSP runs execute eight cooperative dispatches and sixteen transitions across two distinct 16-KiB stacks through an exact linked-image-audited 18-instruction, 36-byte switch, preserve one CR3 and excluded extended state, then retire both contexts and clear 32,768 stack bytes. Fourteen scheduler tests within 151 kernel host tests and 28 hostile-control categories covering 115 rejected cases pass. The kernel is 425,984 canonical bytes in a 507,904-byte, 124-page image with 1,042 relocations and SHA-256 AFED4AF858404D83CD77215C118F8478C88E91BDDC0F0B1ABAC3C9324B6ED602. FLAG-N12-SCHED-FOUNDATION-001 closes only this bounded cooperative-BSP foundation. Interrupt timer/wakeup preemption, deferred work, live AP dispatch, cross-CPU migration, ring-3/address-space switching, full per-task FS/GS/xstate/debug/PMU ownership, general locks, target hardware, N12 exit, release, and production readiness remain open. N12-SCHED-PREEMPT-001 is next.",
            "The Cycle 141 N8-SMP-MULTI-AP-001 receipt upgrades selector 14 to PKSMP5 on one exact four-vCPU SandyBridge-minus-AVX TCG topology. BSP APIC ID 0 starts three private AP runtimes for APIC IDs 1, 2, and 3 with dynamic local masks 0x2/0x4/0x8. A deliberate APIC-4 timeout after APs 1 and 2 start proves final-INIT parking, alias revocation, complete scrub/release, and fresh allocation before retry. The successful retry brings all three APs online simultaneously, accepts one diagnostic, one shootdown, and one stop per AP, denies one forged capability per AP, validates three private acknowledgements into aggregate mask 0xE, rejects reclaim twice before all unique acknowledgements arrive, retires generation 1, final-INIT parks every AP, and releases 96 runtime plus six frame pages. Two exact 40-marker runs, 30 hostile-control categories covering 243 rejected cases, and 137 kernel host tests pass; each attempt verifies 417,792 bytes. The kernel is 409,600 canonical bytes in a 458,752-byte, 112-page image with 985 relocations and SHA-256 8118ED5F7761B9D36A4A65EFF1BC1856C5182D5733CE95A8BEEB24D1C2435F8D. FLAG-N8-SMP-MULTI-AP-001 closes only this frozen topology and bounded one-page-per-root generation transition. General topology/x2APIC, general or address-space-wide shootdown, concurrent generations, scheduler ownership, production capability authority, target hardware, N8/N9 exit, release, and production readiness remain open. N12-SCHED-001 is next.",
            "The Cycle 140 N9-SMP-SHOOTDOWN-001 receipt upgrades selector 14 to PKSMP4. One AP fills a TLB entry for virtual page 0x001FF000 from an AP-owned root, then a checksum-bound generation-2 request targets CPU mask 0x2. The AP validates the request, executes exactly one linked-image-audited INVLPG through RAX, reads the new frame value, and returns an exact generation/root/page/mask/sequence/attempt acknowledgement. A deliberate offline target-mask 0x4 timeout and same-attempt retry pass; stale generation, duplicate acknowledgement, forged mask, pre-ack reclaim, checksum, and state faults fail closed. The BSP rejects premature release, commits retirement only after exact acknowledgement, then scrubs and releases the retired and active frames plus all 32 runtime pages. Two exact 40-marker SandyBridge-minus-AVX TCG runs, 25 hostile-control categories covering 169 rejected cases, and 132 kernel host tests pass. The kernel remains 409,600 canonical bytes in a 458,752-byte, 112-page image with 969 relocations and SHA-256 95DDA27784DA944A9C0F5B04029255EDE4DE1BB0684A8EA10DCFC07E686B59A2. FLAG-N9-SMP-SHOOTDOWN-001 closes only this one-AP, one-root, one-page, one-generation slice. General multi-AP SMP, address-space-wide invalidation, concurrent generations, scheduler ownership, production capability authority, target hardware, N8/N9 exit, release, and production readiness remain open. N8-SMP-MULTI-AP-001 is next.",
            "Sixteen allowlisted user-mode CPUID records prove only a bounded host observation; they do not prove MSR access, privileged probes, native parsing, driver safety, or Tier 1 qualification.",
            "Owner-directed acceptance of thirty-eight objective definitions while binding zero measurements is not a cryptographic signature or implementation evidence.",
            "PooleGlyph Phase 65 proves a metadata, parser, AST, and diagnostic foundation only; no source form, Core IR, PGASM, PGB2, PGVM2, host call, policy, optimization, or version label is promoted without its own frozen contract and evidence gate.",
            "Private PooleGlyph or PooleMath optimization evidence cannot replace the public-safe reference path, independent semantic/effect/authority differentials, or PooleOS capability enforcement.",
            "Finite PDC/QP evidence remains bounded to its declared classical models and protocols.",
            "A file named ISO is not reproducible signed clean-media boot evidence.",
        ],
    }

    # Preserve the prior checkpoint before applying this measured replay.
    checkpoint = "docs/checkpoints/cycle173-entry-provenance-replay.md"
    protocol = roadmap["execution_protocol"]
    protocol.update(last_updated_cycle=173, selected_move_id="N5-SYMBOLS-SEMANTICS-001",
                    owner_independent_next_move_id="N7-TRAP-001")
    protocol["required_records"].insert(0, checkpoint)
    roadmap["baseline"]["pooleos_cycle"] = 173
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for historical, current in (
        ("historical_cycle172_source_projection", "current_focused_source_projection"),
        ("historical_cycle172_ownership_qualification", "current_ownership_qualification"),
        ("historical_cycle169_boot_chain_qualification", "current_boot_chain_qualification"),
        ("historical_cycle170_cpu_qualification", "current_cpu_qualification"),
        ("historical_cycle171_dependency_qualification", "current_dependency_qualification"),
    ):
        gate[historical] = gate[current]
    gate["qualification_status"] = "entry_and_boot_replay_pass_downstream_provenance_replay_pending"
    gate["historical_cycle172_n36_host_summary"] = {
        "text": "Cycle 150 host baseline: 945 tests with three expected environment skips",
        "status": "superseded_mislabeled_dynamic_test_inventory_not_execution_evidence",
    }
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=173)
    gate["historical_cycle172_candidate_audit"] = {
        "cycle": 172, "status": "fail", "applies_to_current_source": False,
        "aggregate_suite_passed": False, "passed_checks": 104, "total_checks": 105,
        "doctor_passed_checks": 707, "doctor_total_checks": 708,
        "include_runtime": True, "both_bundle_and_replay_inputs_supplied": True,
        "audited_source_commit": "9c111e282372290d93a853240d4ef361b6666584",
        "audited_tree": "bae7e532e48a1a3ba9a912f9452824c3a18a764c",
        "receipt_sha256": "D5AF0E1BCA6C6278ED9E506DB2EBBA1E464AED74177DDC73C8EF30B977D52DD4",
        "failure": "kernel_entry_linked_ELF_reproduction_drift_and_incomplete_source_bindings",
        "production_ready": False,
    }
    gate["current_focused_source_projection"] = dict(
        gate["current_focused_source_projection"], cycle=173, passed_checks=22,
        pending_downstream_native_checks=5, prior_smp_new_boot_artifact_set_replay_pending=True,
        final_receipt_fresh_qemu_runs=6,
        fresh_qemu_run_count_scope="two_each_PKLOAD6_PooleBoot_PKXFER1_cycle173_runs",
        next_dependency_move_id="N7-TRAP-001",
        required_next_gate="CPU_memory_and_SMP_dependency_replay_then_exact_full_qualification",
        passing_selected_checks_do_not_requalify_old_embedded_entry_evidence=True,
    )
    gate["current_entry_provenance_qualification"] = {
        "cycle": 173, "source_binding_count": 54, "kernel_crate_rust_source_count": 38,
        "previously_omitted_kernel_source_count": 24,
        "linked_byte_count": 7025584,
        "linked_sha256": "87B12B0278881804BDDA57132657950CF8CD8F515B7A0CC4BC9E2B6326FA1C0A",
        "canonical_byte_count": 530072,
        "canonical_sha256": "8A2DA65C86B09F7BCF2D5ACDB90029A5B7B7361581BA841ADC3B62AEE168B625",
        "entry_receipt_sha256": "9998F12E922201BA60C46521444BD1AD6CB641A0172B36F4A3552DCF66434A0B",
        "clean_matching_builds": 2, "kernel_host_tests": 243, "negative_controls": 43,
        "entry_python_tests": 11, "crate_digest_mutation_cases": 38,
        "exact_receipt_and_product_reproduction_passed": True,
        "single_host_only": True, "transitive_workspace_provenance_complete": False,
        "production_ready": False,
    }
    gate["current_ownership_qualification"] = dict(
        gate["current_ownership_qualification"], cycle=173,
        scope="cycle172_host_stack_receipt_with_cycle171_AP_execution_awaiting_provenance_replay",
        live_receipt_source_current=False, current_boot_artifact_set_replay_pending=True,
        active_root_current_image_replay_complete=False,
        entry_receipt_sha256="9998F12E922201BA60C46521444BD1AD6CB641A0172B36F4A3552DCF66434A0B",
    )
    gate["current_boot_chain_qualification"] = dict(
        gate["current_boot_chain_qualification"], cycle=173,
        scope="six_N5_components_after_linked_debug_and_source_binding_repair",
        inner_set_sha256="E4B88EAF9B322531292D03EBA9FDCFA6ECABF6EEF7A5210C29D130C8AE321D3A",
        focused_python_tests=71, boot_identity_rejection_cases=5,
        receipt_bindings=[
            {"path": "runs/native_symbol_readiness.json", "sha256": "A116A0BBB288A6005BDEB4DFE8FF793D8A330C3DB2AA02581D89F9BEFEC8E409"},
            {"path": "runs/native_policy_readiness.json", "sha256": "9262886C425628FF2732379B5D63683DEF98FF50310F17D8AE9D5FCFF9DC212D"},
            {"path": "runs/native_kernel_load_readiness.json", "sha256": "02AAC204A50A5157228DE5FDA11B0819128BA64431E8A959255A8B99B0236EAA"},
            {"path": "runs/native_pooleboot_readiness.json", "sha256": "DA8B44DA10144843E0DDF8AD6D6F8DD8490BE68967454E032ADC539ADEB2CDD8"},
            {"path": "runs/native-kernel-revalidation-readiness.json", "sha256": "4F595F788E07D811D5D2CEC16CD944E50E2804B3A8BF22ED8F7A6671BA1D1BC0"},
            {"path": "runs/native-kernel-transfer-readiness.json", "sha256": "295A8C43E1CE81325E09F7C72A3D419207AC98A05CF0D28D2EFAF3B52290E1B4"},
        ],
    )
    gate["current_cpu_qualification"] = dict(
        gate["current_cpu_qualification"], source_validation_cycle=173,
        embedded_entry_provenance_replay_pending=True,
        readiness_replay_required_profiles=["cpu_policy", "privilege_msr_policy"],
    )
    gate["current_dependency_qualification"] = dict(
        gate["current_dependency_qualification"], source_validation_cycle=173,
        embedded_entry_provenance_replay_pending=True,
        readiness_replay_required_profiles=["physical_memory", "virtual_memory", "smp_ipi"],
    )
    evidence = (
        "Cycle 173: " + checkpoint + " requalifies PKENTRY1 and six N5 components after full linked-ELF drift. "
        "All 38 kernel Rust sources are bound among 54 inputs; 11 entry tests, 71 boot-chain tests and six fresh "
        "QEMU runs pass. The selected projection is 22/27; five stale checks and broader embedded-entry "
        "CPU/memory/SMP provenance replay remain open. No phase, flag or production gate closes."
    )
    gap = (
        "Cycle 173 repairs kernel-entry and symbol provenance; replay CPU, memory and SMP dependencies from "
        "N7-TRAP-001 before exact full qualification. Passing selected checks is not new execution evidence. "
        "Full transitive-workspace input coverage and independent-builder qualification remain open."
    )
    for phase in roadmap["phases"]:
        if phase["id"] == "N36":
            mislabeled = f"Cycle 150 host baseline: {test_count} tests with three expected environment skips"
            phase["current_evidence"] = [
                "Cycle 173 source inventory: 950 Python tests discovered; full qualification pending"
                if item == mislabeled else item for item in phase["current_evidence"]
            ]
        if phase["id"] in {"N5", "N6", "N7", "N9", "N12", "N36"}:
            phase["current_evidence"] = [evidence, *phase["current_evidence"]]
            phase["current_gaps"] = [gap, *phase["current_gaps"]]
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N12-CONCURRENCY-RECLAMATION-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"] = [checkpoint, *flag["evidence"]]
        if flag["id"] == "FLAG-N36-RECEIPT-COVERAGE-001":
            flag["evidence"].extend(["runtime/native_kernel_entry.py", "tests/test_native_kernel_entry.py",
                                     "tests/test_native_boot_chain_release_gate.py"])
    roadmap["claim_boundaries"].insert(0, evidence)
    checkpoint = "docs/checkpoints/cycle174-cpu-entry-provenance.md"
    protocol.update(last_updated_cycle=174, selected_move_id="N7-TRAP-001",
                    owner_independent_next_move_id="N9-PMM-ACPI-CONSUMER-001")
    protocol["required_records"].insert(0, checkpoint)
    roadmap["baseline"]["pooleos_cycle"] = 174
    for historical, current in (
        ("historical_cycle173_source_projection", "current_focused_source_projection"),
        ("historical_cycle173_ownership_qualification", "current_ownership_qualification"),
        ("historical_cycle173_cpu_qualification", "current_cpu_qualification"),
        ("historical_cycle173_dependency_qualification", "current_dependency_qualification"),
    ):
        gate[historical] = gate[current]
    gate["qualification_status"] = "cpu_entry_provenance_replay_pass_memory_replay_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=174)
    gate["current_focused_source_projection"] = dict(
        gate["current_focused_source_projection"], cycle=174, passed_checks=24,
        pending_downstream_native_checks=3, final_receipt_fresh_qemu_runs=14,
        fresh_qemu_run_count_scope="six_trap_and_two_each_CPU_XSTATE_XEXC_MSR_cycle174_runs",
        next_dependency_move_id="N9-PMM-ACPI-CONSUMER-001",
        required_next_gate="memory_IRQ_SMP_scheduler_dependency_replay_then_exact_full_qualification",
    )
    gate["current_ownership_qualification"] = dict(gate["current_ownership_qualification"], cycle=174)
    gate["current_cpu_qualification"] = dict(
        gate["current_cpu_qualification"], cycle=174, source_validation_cycle=174,
        scope="five_N7_profiles_with_exact_current_embedded_entry_provenance",
        embedded_entry_provenance_replay_pending=False, readiness_replay_required_profiles=[],
        focused_python_tests=47, embedded_entry_rejection_cases=80,
        invalid_current_entry_dependency_cases=20, entry_identity_comparison="canonical_JSON_typed_equality",
        provenance_coverage_scope="five_N7_profiles_only_not_all_transitive_inputs",
        receipt_bindings=[
            {"path": "runs/native-kernel-trap-readiness.json", "sha256": "8C14786643F1423656AD20D733A1F339CC7036BEB0957CF2945C605DCD40648F"},
            {"path": "runs/native-kernel-cpu-policy-readiness.json", "sha256": "F3A67A26D0E749921A1F3AAC6B924C6B74BF71564DBDA2B292B8B844718C0285"},
            {"path": "runs/native-kernel-xstate-policy-readiness.json", "sha256": "9D66DD4EC4AC145A6639D6A0C50179D112D9221CE8B5224851DB5645CFD3BFE0"},
            {"path": "runs/native-kernel-xstate-exception-readiness.json", "sha256": "CE34466E452D16847F6773764BF55733F0F0C25601E4F37C36B7F13101B916C7"},
            {"path": "runs/native-kernel-privilege-msr-policy-readiness.json", "sha256": "AE0AC3771B7C8C749CF2F0AA1700FF35753973F2494A1B34342CB60A96B18632"},
        ],
    )
    gate["current_dependency_qualification"] = dict(
        gate["current_dependency_qualification"], source_validation_cycle=174,
    )
    evidence = (
        "Cycle 174: " + checkpoint + " qualifies five CPU profiles with fourteen fresh successful virtual "
        "boots, 225 controls and 47 focused tests. Exact JSON-typed embedded entry identity rejects 80 "
        "malformed/stale/type cases and 20 invalid current dependencies. The projection is 24/27; memory "
        "and SMP provenance replay and full qualification remain open. No phase or flag closes."
    )
    gap = (
        "Cycle 174 leaves PMM, VM and SMP IPI selected gates stale; all fourteen older memory-through-lock "
        "profiles need embedded-entry provenance replay from N9-PMM-ACPI-CONSUMER-001. Complete transitive "
        "coverage, independent builders, physical targets and the exact full audit remain open."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N7", "N8", "N9", "N12", "N36"}:
            phase["current_evidence"] = [evidence, *phase["current_evidence"]]
            phase["current_gaps"] = [gap, *phase["current_gaps"]]
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 174 source inventory: 954 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] == "FLAG-N36-RECEIPT-COVERAGE-001":
            flag["evidence"] = [checkpoint, "runtime/native_kernel_profile_evidence.py",
                                "tests/test_native_cpu_entry_provenance.py", *flag["evidence"]]
    roadmap["claim_boundaries"].insert(0, evidence)
    checkpoint = "docs/checkpoints/cycle175-memory-entry-provenance.md"
    protocol.update(last_updated_cycle=175, selected_move_id="N9-PMM-ACPI-CONSUMER-001",
                    owner_independent_next_move_id="N12-CONCURRENCY-RECLAMATION-001")
    protocol["required_records"].insert(0, checkpoint)
    roadmap["baseline"]["pooleos_cycle"] = 175
    for historical, current in (
        ("historical_cycle174_source_projection", "current_focused_source_projection"),
        ("historical_cycle174_ownership_qualification", "current_ownership_qualification"),
        ("historical_cycle174_dependency_qualification", "current_dependency_qualification"),
        ("historical_cycle174_candidate_audit", "current_candidate_audit"),
    ):
        gate[historical] = gate[current]
    gate["qualification_status"] = "memory_entry_provenance_and_dependency_replay_pass_full_audit_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=175)
    gate["current_focused_source_projection"] = dict(
        gate["current_focused_source_projection"], cycle=175, passed_checks=27,
        pending_downstream_native_checks=0, prior_smp_new_boot_artifact_set_replay_pending=False,
        final_receipt_fresh_qemu_runs=28, superseded_initial_runs=2,
        fresh_qemu_run_count_scope="two_each_fourteen_final_cycle175_profiles_excludes_two_superseded_SMP_boots",
        revalidated_dependency_execution_cycle=175,
        negative_control_groups=660, negative_control_cases=2126,
        focused_python_tests=163, focused_python_passed=161, focused_python_skipped=2,
        next_dependency_move_id="N12-CONCURRENCY-RECLAMATION-001",
        required_next_gate="exact_full_canonical_qualification_then_publication_review_before_N12_3_implementation",
    )
    gate["current_ownership_qualification"] = dict(
        gate["current_ownership_qualification"], cycle=175,
        scope="cycle172_host_stack_receipt_with_cycle175_exact_AP_execution",
        live_receipt_scope="two_final_cycle175_exact_four_vcpu_PKSMP5_runs",
        live_replay_cycle=175, fresh_current_cycle_qemu_runs=2,
        live_receipt_source_current=True, current_boot_artifact_set_replay_pending=False,
        active_root_current_image_replay_complete=True,
        smp_receipt_sha256="33AC859F22E4D973B44B69C33C1F135FDC281DDDC7AB14833157BCC0616AC93F",
    )
    gate["current_dependency_qualification"] = dict(
        gate["current_dependency_qualification"], cycle=175, source_validation_cycle=175,
        scope="fourteen_native_profiles_with_exact_current_embedded_entry_provenance",
        embedded_entry_provenance_replay_pending=False, readiness_replay_required_profiles=[],
        fresh_qemu_runs=28, superseded_initial_runs=2, superseded_profiles=["smp_ipi"],
        negative_control_groups=660, negative_control_cases=2126,
        focused_python_tests=163, focused_python_passed=161, focused_python_skipped=2,
        embedded_entry_rejection_cases=224, invalid_current_entry_dependency_cases=56,
        smp_non_object_regression_cases=4,
        entry_identity_comparison="canonical_JSON_typed_equality",
        provenance_coverage_scope="fourteen_profiles_only_not_all_transitive_inputs",
        receipt_bindings=[
            {"path":"runs/native-kernel-physical-memory-readiness.json","sha256":"1E0BFE165847F44D378BCE34E8CBB80381B5D55461BE184926A18098DC2A428A","fresh_runs":2,"kernel_host_tests":243,"negative_groups":191,"negative_cases":191,"marker_count":45},
            {"path":"runs/native-kernel-virtual-memory-readiness.json","sha256":"70BFA62FA783F8D86192C9A4B2D09B25E6C95651091B696BF0DEF55781B1FD22","fresh_runs":2,"kernel_host_tests":243,"negative_groups":48,"negative_cases":48,"marker_count":40},
            {"path":"runs/native-kernel-interrupt-time-readiness.json","sha256":"9B8701771419F236BBCB2EFDD113252FC7AB475F9627BCC3EDE193ED0A06C23F","fresh_runs":2,"kernel_host_tests":243,"negative_groups":58,"negative_cases":58,"marker_count":36},
            {"path":"runs/native-kernel-smp-first-ap-readiness.json","sha256":"8091CE3463ED7B176694453A2BAC3CDE12A4A99B62A0C0556B631A484BAE9A55","fresh_runs":2,"kernel_host_tests":243,"negative_groups":72,"negative_cases":72,"marker_count":38},
            {"path":"runs/native-kernel-smp-percpu-runtime-readiness.json","sha256":"CB5F40B6A9126277E63683C6445143ED4743AA5A1B4C27D41B35A27732D82012","fresh_runs":2,"kernel_host_tests":243,"negative_groups":19,"negative_cases":159,"marker_count":42},
            {"path":"runs/native-kernel-smp-ipi-readiness.json","sha256":"33AC859F22E4D973B44B69C33C1F135FDC281DDDC7AB14833157BCC0616AC93F","fresh_runs":2,"kernel_host_tests":243,"negative_groups":30,"negative_cases":249,"marker_count":40},
            {"path":"runs/native-kernel-scheduler-readiness.json","sha256":"7B88A628040CF2D56EF20C82597F28EEEF4BBA8EF7E54530DB18504E87C59784","fresh_runs":2,"kernel_host_tests":243,"negative_groups":28,"negative_cases":115,"marker_count":34},
            {"path":"runs/native-kernel-scheduler-preemption-readiness.json","sha256":"DD7D25E4519AD547C83F455E8F07D68D460AFDBF7008497399773FBF621A7F85","fresh_runs":2,"kernel_host_tests":243,"negative_groups":25,"negative_cases":178,"marker_count":35},
            {"path":"runs/native-kernel-scheduler-deferred-readiness.json","sha256":"5DD7943E2BA0DF888ABD5BB0B07CA7E9A993667AE9F0BCFEF934153E2AD1BA8C","fresh_runs":2,"kernel_host_tests":243,"negative_groups":30,"negative_cases":208,"marker_count":37},
            {"path":"runs/native-kernel-scheduler-smp-readiness.json","sha256":"C1CDB80614A014295892BE0830EE53AF69302517F28B0F06BDC148A4BBD59FBE","fresh_runs":2,"kernel_host_tests":243,"negative_groups":32,"negative_cases":209,"marker_count":37},
            {"path":"runs/native-kernel-scheduler-ap-workers-readiness.json","sha256":"A1E4BBF2533C5CBD6A7606AF1668033203947244243B1E15511453E2FE2E5A71","fresh_runs":2,"kernel_host_tests":243,"negative_groups":34,"negative_cases":226,"marker_count":37},
            {"path":"runs/native-kernel-scheduler-smp-preempt-readiness.json","sha256":"BA92D612301355611C744B2E80B04D7F18DE864A680BC8B7DBAADD4B29FE043F","fresh_runs":2,"kernel_host_tests":243,"negative_groups":34,"negative_cases":232,"marker_count":38},
            {"path":"runs/native-kernel-atomics-readiness.json","sha256":"AA89BA7799FFCA130B87B36CA30347128C717F6F60184CCAFC09EE02C72CAD1C","fresh_runs":2,"kernel_host_tests":243,"negative_groups":29,"negative_cases":78,"marker_count":41},
            {"path":"runs/native-kernel-locks-readiness.json","sha256":"F9E8B7754343DD02CF44D0FD7394294C3A2B43F4B4D308D5AF2606C083283496","fresh_runs":2,"kernel_host_tests":243,"negative_groups":30,"negative_cases":103,"marker_count":35},
        ],
    )
    evidence = (
        "Cycle 175: " + checkpoint + " qualifies fourteen final memory-through-lock profiles with 28 fresh "
        "virtual boots, 660 control groups and 2126 rejected cases. Two earlier SMP boots are superseded "
        "after a four-case malformed-input regression repair. All 27 selected gates pass; 161 of 163 "
        "focused tests pass with two optional transcript skips. Exact entry provenance rejects 224 "
        "embedded substitutions and 56 invalid dependencies. No phase or flag closes."
    )
    gap = (
        "Cycle 175 completes the declared memory-through-lock provenance replay; exact full canonical "
        "qualification and publication/review still precede PR77 merge and N12.3 live guarded stacks, "
        "context activation and general CPU retirement. Complete transitive coverage, independent "
        "builders, physical targets, automatic receipt-growth integration and production remain open."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N8", "N9", "N12", "N36"}:
            phase["current_evidence"] = [evidence, *phase["current_evidence"]]
            phase["current_gaps"] = [gap, *phase["current_gaps"]]
        if phase["id"] == "N6":
            phase["current_gaps"] = [gap, *phase["current_gaps"]]
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 175 source inventory: 958 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N12-CONCURRENCY-RECLAMATION-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"] = [checkpoint, *flag["evidence"]]
        if flag["id"] == "FLAG-N36-RECEIPT-COVERAGE-001":
            flag["evidence"].append("tests/test_native_memory_entry_provenance.py")
    roadmap["claim_boundaries"].insert(0, evidence)
    checkpoint = "docs/checkpoints/cycle177-dispatch-execution-holds.md"
    protocol.update(last_updated_cycle=177, selected_move_id="N12-CONCURRENCY-RECLAMATION-001",
                    owner_independent_next_move_id="N6-KENTRY-001")
    protocol["required_records"].insert(0, checkpoint)
    roadmap["baseline"]["pooleos_cycle"] = 177
    for name in (
        "focused_source_projection", "ownership_qualification", "task_stack_qualification",
        "entry_provenance_qualification", "boot_chain_qualification", "cpu_qualification",
        "dependency_qualification", "candidate_audit",
    ):
        historical_name = "source_projection" if name == "focused_source_projection" else name
        gate["historical_cycle175_" + historical_name] = gate["current_" + name]
    gate["historical_cycle176_canonical_replay"] = {
        "cycle": 176, "status": "pass", "passed_checks": 105, "total_checks": 105,
        "doctor_passed_checks": 708, "doctor_total_checks": 708, "pooleos_test_count": 958,
        "tracked_file_count": 1535, "tracked_source_unchanged": True,
        "include_runtime": True, "both_bundle_and_replay_inputs_supplied": True,
        "source_commit": "ac95c38840e07be725d6f3e85c536668f4142ea6",
        "merged_main_commit": "ac15d1da5304eab19ae3ed098d26cdcadfa78156",
        "merged_tree": "1bce3ce5317a9202e80f4df482ce0b4766093d44",
        "merge_pr": 77, "merged_at": "2026-09-12T12:35:05Z",
        "final_receipt_sha256": "57C7C95D0EA982FB16763C8440A24103E5C6E0F21C133C56E6EEDC9AA7A4AA0A",
        "execution_receipt_sha256": "1368149CCC695ACDEE91AD662430C497B929BAA66CBE414DCCE43A5AEF70CD6F",
        "publication_report_sha256": "4EBDA0081406FB44AC414FBCCFB17038968FF0212D13A823F2DBB14DECC3AE65",
        "applies_to_current_source": False, "production_ready": False,
    }
    gate.update(
        qualification_status="dispatch_execution_holds_host_verified_entry_and_dependency_replay_pending",
        passed_check_count_scope="historical_cycle176_exact_final_canonical_audit",
        last_fully_qualified_cycle=176, current_cycle_full_canonical_audit_performed=False,
    )
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=177)
    core_sha = "7E289FE30319EA9577C66716FE31EB02600E779D8F0E380172D3C3C708900A71"
    kernel_sha = "563ED1976CAB4DA773BAE9BCE49F370242C893760E7C221239C1B31F44D969CA"
    gate["current_focused_source_projection"] = {
        "cycle": 177, "scope": "27_selected_native_checks_not_full_canonical_audit",
        "passed_checks": 2, "total_checks": 27, "pending_downstream_native_checks": 25,
        "passing_profiles": ["native_policy_readiness", "native_kernel_errata_policy_readiness"],
        "final_receipt_fresh_qemu_runs": 0, "revalidated_dependency_execution_cycle": None,
        "core_qualification_stage_count": 17, "lifetime_tests_per_host_profile": 40,
        "compile_fail_tests": 15, "core_receipt_sha256": core_sha,
        "reconciliation_python_tests_passed": 37,
        "expanded_python_test_methods": 60, "expanded_python_passed_methods": 55,
        "expanded_python_failed_methods": 5, "expanded_python_failure_reports": 9,
        "expanded_python_suite_passed": False,
        "expanded_failure_scope": "stale_boot_cpu_memory_positive_baselines_block_dependent_tests",
        "expanded_test_log_sha256": "8BED42149F82D07C4EAA48C7AABF6A35E23E69351F774AC4D5A56AAD11F85176",
        "canonical_full_replay_performed": False, "production_ready": False,
        "next_dependency_move_id": "N6-KENTRY-001",
        "required_next_gate": "entry_then_ordered_dependency_replay_then_exact_full_qualification",
    }
    gate["current_ownership_qualification"] = {
        "cycle": 177, "scope": "host_dispatch_hold_and_inactive_stack_retention",
        "host_qualification_cycle": 177, "fresh_current_cycle_qemu_runs": 0,
        "lifetime_tests_per_host_profile": 40, "pool_tests_per_host_profile": 19,
        "kernel_tests_per_host_profile": 245, "retention_test_count": 20,
        "ap_resource_test_count": 11, "compile_fail_tests": 15,
        "kernel_sha256": kernel_sha, "reclamation_receipt_sha256": core_sha,
        "live_receipt_source_current": False, "live_replay_cycle": None,
        "current_boot_artifact_set_replay_pending": True,
        "active_root_current_image_replay_complete": False,
        "ap_runtime_live_integration_verified": False, "task_stack_live_integration_verified": False,
        "general_task_CPU_retirement_integration_verified": False,
        "current_candidate_full_gate_passed": False, "production_ready": False,
    }
    gate["current_task_stack_qualification"] = dict(
        gate["current_task_stack_qualification"], cycle=177, receipt_sha256=core_sha,
        receipt_schema_version="1.6", lifetime_tests_per_host_profile=40,
        kernel_tests_per_host_profile=245, compile_fail_tests=15,
        linked_kernel_byte_identical=False,
    )
    gate["current_execution_qualification"] = {
        "cycle": 177, "contract_id": "PKEXEC1",
        "scope": "mandatory_dispatch_hold_architecture_quiescence_boundary",
        "receipt_path": "runs/native-kernel-reclamation-core-readiness.json",
        "receipt_sha256": core_sha, "kernel_sha256": kernel_sha,
        "execution_test_methods": 6, "evidence_parser_rejection_cases": 30,
        "loss_modes": ["drop", "forget", "unwind"], "scheduler_exhaustion_regressions": 2,
        "host_profile_count": 2, "fresh_qemu_runs": 0,
        "task_execution_live_verified": False, "storage_address_stability_guaranteed": False,
        "cross_cpu_quiescence_verified": False, "n12_3_complete": False, "production_ready": False,
    }
    replay_profiles = {
        "entry_provenance": ["kernel_entry"],
        "boot_chain": ["symbol", "kernel_load", "pooleboot", "kernel_revalidation", "kernel_transfer"],
        "cpu": ["trap", "cpu_policy", "xstate_policy", "xstate_exception", "privilege_msr_policy"],
        "dependency": list(gate["historical_cycle175_dependency_qualification"]["qualified_profiles"]),
    }
    for name, profiles in replay_profiles.items():
        gate["current_" + name + "_qualification"] = {
            "cycle": 177, "source_validation_cycle": 177,
            "status": "source_requalification_required", "applies_to_current_source": False,
            "historical_record": "historical_cycle175_" + name + "_qualification",
            "readiness_replay_required_profiles": profiles, "qualified_profiles": [],
            "fresh_qemu_runs": 0, "current_candidate_full_gate_passed": False,
            "kernel_sha256": kernel_sha, "production_ready": False,
        }
    evidence = (
        "Cycle 177: " + checkpoint + " records PKEXEC1 mandatory dispatch execution holds and two "
        "reproduced transaction/bypass exhaustion admission rollback repairs. All 17 core stages pass "
        "with 245 kernel, 40 lifecycle, 19 pool and 15 compile-fail tests. Six execution cases and "
        "30 parser controls are host evidence only. Cycle 176 qualified 105/708 and merged PR77 to "
        "main ac15d1d. The 37-test reconciliation suite passes; an expanded 60-test suite fails "
        "with nine reports across five stale-dependent acceptance tests (55 methods pass). "
        "No new live dispatch, phase closure or production claim follows."
    )
    gap = (
        "Cycle 177 changes the kernel and has only 2/27 current selected readiness checks; 25 "
        "dependencies require replay beginning N6-KENTRY-001. Guarded live task mappings, active "
        "contexts, architecture-confirmed CPU quiescence, automatic scrub receipt growth, complete "
        "transitive evidence, independent builders and full exact-candidate qualification remain open."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N6", "N8", "N9", "N12", "N36"}:
            phase["current_evidence"] = [evidence, *phase["current_evidence"]]
            phase["current_gaps"] = [gap, *phase["current_gaps"]]
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 177 source inventory: 960 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N12-CONCURRENCY-RECLAMATION-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"] = [checkpoint, "native/kernel/src/reclamation/execution.rs", *flag["evidence"]]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    checkpoint = "docs/checkpoints/cycle178-kernel-entry-requalification.md"
    protocol.update(last_updated_cycle=178, selected_move_id="N6-KENTRY-001",
                    owner_independent_next_move_id="N5-SYMBOLS-SEMANTICS-001")
    protocol["required_records"].insert(0, checkpoint)
    roadmap["baseline"]["pooleos_cycle"] = 178
    for name in (
        "focused_source_projection", "ownership_qualification", "task_stack_qualification",
        "execution_qualification", "entry_provenance_qualification", "boot_chain_qualification",
        "cpu_qualification", "dependency_qualification", "candidate_audit",
    ):
        historical_name = "source_projection" if name == "focused_source_projection" else name
        gate["historical_cycle177_" + historical_name] = gate["current_" + name]
    gate["qualification_status"] = "kernel_entry_requalified_boot_and_downstream_replay_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=178)
    entry_sha = "B9E79FE7CABA4931C3654134A68934B732DD77A6F1555179C2E09EF93D6212D6"
    gate["current_focused_source_projection"] = {
        "cycle": 178, "scope": "27_selected_native_checks_not_full_canonical_audit",
        "passed_checks": 3, "total_checks": 27, "pending_downstream_native_checks": 24,
        "passing_profiles": ["native_kernel_entry_readiness", "native_policy_readiness", "native_kernel_errata_policy_readiness"],
        "final_receipt_fresh_qemu_runs": 0, "revalidated_dependency_execution_cycle": None,
        "entry_clean_builds_per_qualifier": 2, "entry_kernel_host_tests": 245,
        "entry_negative_controls": 43, "entry_source_binding_count": 55,
        "entry_receipt_sha256": entry_sha, "entry_release_gate_controls": 12,
        "focused_python_tests_passed": 57,
        "focused_test_scope": "entry_roadmap_architecture_core_coverage_and_entry_gate_not_full_audit",
        "focused_test_log_sha256": "4AC7C41FDFE2CF79F96A1BB6E25C6313D84A65DC620BA62BF4B737256142D009",
        "core_receipt_sha256": core_sha, "core_live_execution_cycle": None,
        "canonical_full_replay_performed": False, "production_ready": False,
        "next_dependency_move_id": "N5-SYMBOLS-SEMANTICS-001",
        "required_next_gate": "ordered_boot_CPU_memory_replay_then_exact_full_qualification",
    }
    gate["current_entry_provenance_qualification"] = {
        "cycle": 178, "source_validation_cycle": 178,
        "status": "single_host_entry_reproduction_pass", "applies_to_current_source": True,
        "source_binding_count": 55, "kernel_crate_rust_source_count": 39,
        "linked_byte_count": 7032744,
        "linked_sha256": "50084E1DFDD64A7EBDC884EB041533B50F0F354997E3D9C9BC0CF5B6277C1E11",
        "canonical_byte_count": 530072, "canonical_sha256": kernel_sha,
        "entry_receipt_sha256": entry_sha, "clean_matching_builds": 2,
        "kernel_host_tests": 245, "negative_controls": 43,
        "entry_python_tests": 11, "crate_digest_mutation_cases": 39,
        "release_gate_rejection_cases": 12,
        "exact_receipt_and_product_reproduction_passed": True,
        "single_host_only": True, "transitive_workspace_provenance_complete": False,
        "fresh_qemu_runs": 0, "n6_exit_gate_satisfied": False, "production_ready": False,
    }
    for name in ("boot_chain", "cpu", "dependency"):
        gate["current_" + name + "_qualification"] = dict(
            gate["current_" + name + "_qualification"], cycle=178, source_validation_cycle=178,
        )
    evidence = (
        "Cycle 178: " + checkpoint + " requalifies the unchanged Cycle 177 kernel through two "
        "clean matching linked/canonical builds, 245 host tests, 43 ELF controls and 55 source "
        "bindings covering 39 kernel Rust files. Entry image pins and release-gate type checks "
        "are repaired; twelve isolated gate controls reject. The combined 57-test entry, roadmap, "
        "architecture, core and checklist suite passes. Core ownership remains host-only."
    )
    gap = (
        "Cycle 178 passes only 3/27 selected native checks. Twenty-four dependent profiles remain "
        "stale, beginning N5-SYMBOLS-SEMANTICS-001. No new QEMU execution, architecture quiescence, "
        "independent builder, full canonical qualification, phase closure or production claim follows."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N5", "N6", "N12", "N36"}:
            phase["current_evidence"] = [evidence, *phase["current_evidence"]]
            phase["current_gaps"] = [gap, *phase["current_gaps"]]
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 178 source inventory: 961 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N12-CONCURRENCY-RECLAMATION-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"] = [checkpoint, *flag["evidence"]]
        if flag["id"] == "FLAG-N36-RECEIPT-COVERAGE-001":
            flag["evidence"] = ["tests/test_native_dependency_release_gate.py", *flag["evidence"]]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    checkpoint = "docs/checkpoints/cycle179-boot-chain-requalification.md"
    protocol.update(last_updated_cycle=179, selected_move_id="N5-SYMBOLS-SEMANTICS-001",
                    owner_independent_next_move_id="N7-TRAP-001")
    protocol["required_records"].insert(0, checkpoint)
    roadmap["baseline"]["pooleos_cycle"] = 179
    for name in (
        "focused_source_projection", "ownership_qualification", "task_stack_qualification",
        "execution_qualification", "entry_provenance_qualification", "boot_chain_qualification",
        "cpu_qualification", "dependency_qualification", "candidate_audit",
    ):
        historical_name = "source_projection" if name == "focused_source_projection" else name
        gate["historical_cycle178_" + historical_name] = gate["current_" + name]
    gate["qualification_status"] = "boot_chain_requalified_cpu_and_memory_replay_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=179)
    gate["current_focused_source_projection"] = {
        "cycle": 179, "scope": "27_selected_native_checks_not_full_canonical_audit",
        "passed_checks": 8, "total_checks": 27, "pending_downstream_native_checks": 19,
        "passing_profiles": [
            "native_kernel_entry_readiness", "native_symbol_readiness", "native_policy_readiness",
            "native_kernel_load_readiness", "native_pooleboot_readiness",
            "native_kernel_revalidation_readiness", "native_kernel_transfer_readiness",
            "native_kernel_errata_policy_readiness",
        ],
        "final_receipt_fresh_qemu_runs": 6, "superseded_initial_qemu_runs": 2,
        "kernel_entry_runs": 2, "revalidated_dependency_execution_cycle": 179,
        "entry_receipt_sha256": entry_sha, "entry_kernel_host_tests": 245,
        "entry_source_binding_count": 55, "entry_release_gate_controls": 12,
        "focused_python_tests_passed": 71, "focused_test_scope": "six_N5_components_not_full_audit",
        "focused_test_log_sha256": "BF2D89D92750BF5192042F8719DAD48F9DE94C28864269E6441A5F4C685212EE",
        "boot_identity_rejection_cases": 13, "qualifier_admission_rejection_cases": 3,
        "core_receipt_sha256": core_sha, "core_live_execution_cycle": None,
        "canonical_full_replay_performed": False, "production_ready": False,
        "next_dependency_move_id": "N7-TRAP-001",
        "required_next_gate": "ordered_CPU_memory_replay_then_exact_full_qualification",
    }
    gate["current_entry_provenance_qualification"] = dict(
        gate["current_entry_provenance_qualification"], source_validation_cycle=179,
    )
    gate["current_boot_chain_qualification"] = {
        "cycle": 179, "source_validation_cycle": 179, "status": "single_host_replay_pass",
        "scope": "six_N5_components_for_current_dispatch_execution_hold_kernel",
        "applies_to_current_source": True, "kernel_sha256": kernel_sha,
        "qualified_profiles": ["symbol", "policy", "kernel_load", "pooleboot", "kernel_revalidation", "kernel_transfer"],
        "readiness_replay_required_profiles": [], "fresh_qemu_runs": 6,
        "superseded_initial_runs": 2, "superseded_profiles": ["kernel_transfer"],
        "superseded_reason": "revalidation_semantic_admission_and_source_binding_repair",
        "kernel_entry_runs": 2, "kernel_host_tests": 245, "loader_host_tests": 330,
        "retained_file_count": 9, "inner_artifact_bytes": 8761, "retained_bytes": 11952,
        "inner_set_sha256": "A3078488088B2BF11B8D88F48862FA8D80957D610EB1F3FF4411AD5E4729FEAF",
        "focused_python_tests": 71, "boot_identity_rejection_cases": 13,
        "qualifier_admission_rejection_cases": 3, "prior_kernel_identity_cases_added": 4,
        "receipt_generation_semantically_validated": True,
        "receipt_write_semantically_validated": True,
        "current_candidate_full_gate_passed": False, "production_ready": False,
    }
    gate["current_boot_chain_qualification"]["receipt_bindings"] = [
        {
            "profile": "symbol",
            "path": "runs/native_symbol_readiness.json",
            "sha256": "6E251E2863ABC20B4F1302805F092C382BE7D9CF7CA0AA70CB4E20270E33F96F",
            "fresh_runs": 0,
            "execution_log_sha256": "39D622078702BC250B96EFD6CACB9EC04214EB6EEF0062BCFD4BF83419DC0038"
        },
        {
            "profile": "policy",
            "path": "runs/native_policy_readiness.json",
            "sha256": "40DFF7B628EAC8DB946BA9535740053A5F6B044E5882D3C527D20C1A273AE39E",
            "fresh_runs": 0,
            "execution_log_sha256": "4E0AA1F9DB24DE8D841452D60CA70EBAD0B1883FF79739D7A96CB02A1045ECA7"
        },
        {
            "profile": "kernel_load",
            "path": "runs/native_kernel_load_readiness.json",
            "sha256": "E9BB7A7CE5C709A02ED02CB53A47FF66A55C949ED85BFEEF1FEC277BA667F611",
            "fresh_runs": 2,
            "execution_log_sha256": "417C7B59688B1D98ACDF8391A970DF09430B126C4345FE53A04840D1C461B330"
        },
        {
            "profile": "pooleboot",
            "path": "runs/native_pooleboot_readiness.json",
            "sha256": "7D748DB12AB52F126DF5FF007F257CF7CD625C972DA748C35D3DA1DC325CD2E5",
            "fresh_runs": 2,
            "execution_log_sha256": "56338F6E2175B97E50BB1E2377476252F07B88CAAEAF64E220040A84FE086C65"
        },
        {
            "profile": "kernel_revalidation",
            "path": "runs/native-kernel-revalidation-readiness.json",
            "sha256": "8577B6060FB35C3D0C16629E7CCB2CEB676ABECDB6410B9FC34E3C48755A9454",
            "fresh_runs": 0,
            "execution_log_sha256": "A241574365E43C16D05D7D059E5D2DF662F24D5D5A58A65536FB8528DE34177D"
        },
        {
            "profile": "kernel_transfer",
            "path": "runs/native-kernel-transfer-readiness.json",
            "sha256": "C41EC5F4709169B84C3F3C96B9B17ACF26CC128624D9481378BCB313B3DA1A9C",
            "fresh_runs": 2,
            "execution_log_sha256": "CFA47E76AB3375E41C02258ADFBB2C49320C3D8F2D0956B0CDC404ECD5A5D402"
        }
    ]
    for name in ("cpu", "dependency"):
        gate["current_" + name + "_qualification"] = dict(
            gate["current_" + name + "_qualification"], cycle=179, source_validation_cycle=179,
        )
    evidence = (
        "Cycle 179: " + checkpoint + " qualifies six N5 components with six final headless boots, "
        "two kernel entries, nine-file independent revalidation and 71 passing focused Python tests. "
        "The revalidation qualifier now semantically validates before returning and writing a receipt; "
        "three specific invalid candidates reject without output. Thirteen gate controls reject "
        "old artifact/trust identities and host counts. Two superseded transfer boots and all failures "
        "remain separate. Kernel and native Rust bytes are unchanged."
    )
    gap = (
        "Cycle 179 passes 8/27 selected native checks. Nineteen CPU and memory-through-lock profiles "
        "require replay beginning N7-TRAP-001. Independent builders, complete transitive evidence, "
        "live task contexts/CPU retirement and full exact-candidate qualification remain open. "
        "No phase, flag, authenticated boot, new demo ISO or production claim follows."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N5", "N6", "N12", "N36"}:
            phase["current_evidence"] = [evidence, *phase["current_evidence"]]
            phase["current_gaps"] = [gap, *phase["current_gaps"]]
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 179 source inventory: 962 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N5-SYMBOL-BUNDLE-001", "FLAG-N12-CONCURRENCY-RECLAMATION-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"] = [checkpoint, *flag["evidence"]]
        if flag["id"] == "FLAG-N36-RECEIPT-COVERAGE-001":
            flag["evidence"] = ["tests/test_native_kernel_revalidation.py", "tools/qualify_native_kernel_revalidation.py", *flag["evidence"]]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    checkpoint = "docs/checkpoints/cycle180-cpu-qualification.md"
    protocol.update(last_updated_cycle=180, selected_move_id="N7-TRAP-001",
                    owner_independent_next_move_id="N9-PMM-ACPI-CONSUMER-001")
    protocol["required_records"].insert(0, checkpoint)
    roadmap["baseline"]["pooleos_cycle"] = 180
    for name in (
        "focused_source_projection", "ownership_qualification", "task_stack_qualification",
        "execution_qualification", "entry_provenance_qualification", "boot_chain_qualification",
        "cpu_qualification", "dependency_qualification", "candidate_audit",
    ):
        historical_name = "source_projection" if name == "focused_source_projection" else name
        gate["historical_cycle179_" + historical_name] = gate["current_" + name]
    gate["qualification_status"] = "cpu_requalified_memory_replay_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=180)
    gate["current_focused_source_projection"] = {
        "cycle": 180, "scope": "27_selected_native_checks_not_full_canonical_audit",
        "passed_checks": 13, "total_checks": 27, "pending_downstream_native_checks": 14,
        "passing_profiles": [
            "native_kernel_entry_readiness", "native_symbol_readiness", "native_policy_readiness",
            "native_kernel_load_readiness", "native_pooleboot_readiness",
            "native_kernel_revalidation_readiness", "native_kernel_transfer_readiness",
            "native_kernel_trap_readiness", "native_kernel_cpu_policy_readiness",
            "native_kernel_errata_policy_readiness", "native_kernel_xstate_policy_readiness",
            "native_kernel_xstate_exception_readiness", "native_kernel_privilege_msr_policy_readiness",
        ],
        "final_receipt_fresh_qemu_runs": 14, "expected_tcg_limitation_probes": 1,
        "whpx_exception_runs": 2, "superseded_initial_runs": 0,
        "negative_control_groups": 225, "aggregate_gate_regression_cases": 19,
        "entry_receipt_sha256": entry_sha, "entry_kernel_host_tests": 245,
        "entry_source_binding_count": 55, "entry_release_gate_controls": 12,
        "focused_python_tests_passed": 46,
        "focused_test_scope": "five_CPU_profiles_pure_errata_provenance_and_CPU_gate_not_full_audit",
        "focused_test_log_sha256": "5F0968C7EA5288C3E189D04E06EEB246951C6AF40EB59C89307EC3301B92754D",
        "core_receipt_sha256": core_sha, "core_live_execution_cycle": None,
        "canonical_full_replay_performed": False, "production_ready": False,
        "next_dependency_move_id": "N9-PMM-ACPI-CONSUMER-001",
        "required_next_gate": "ordered_memory_replay_then_exact_full_qualification",
    }
    for name in ("entry_provenance", "boot_chain"):
        gate["current_" + name + "_qualification"] = dict(
            gate["current_" + name + "_qualification"], source_validation_cycle=180,
        )
    gate["current_cpu_qualification"] = dict(
        gate["historical_cycle175_cpu_qualification"], cycle=180, source_validation_cycle=180,
        status="single_host_cpu_replay_pass", applies_to_current_source=True,
        scope="five_N7_profiles_with_untouched_generated_positive_receipts",
        kernel_sha256=kernel_sha, kernel_host_tests_per_qualifier=245,
        focused_python_tests=46, aggregate_gate_regression_cases=19,
        qualified_profiles=["trap", "cpu_policy", "xstate_policy", "xstate_exception", "privilege_msr_policy"],
        positive_receipts_rebound_in_tests=False, recorded_marker_replay_verified=True,
        superseded_initial_runs=0,
    )
    gate["current_cpu_qualification"]["receipt_bindings"] = [
        {
            "profile": "trap", "path": "runs/native-kernel-trap-readiness.json",
            "sha256": "2A997942A2AD844814BF4FE5A6C14D51A1C7A24044796D82FCEC73C3A403BD2C",
            "fresh_runs": 6, "negative_controls": 51, "kernel_host_tests": 245,
            "execution_log_sha256": "7E2F449373D9AC8C54B86D0CCC94BB7962EFED183681CAEBD68BF0C6D3DFB4AC",
            "elapsed_seconds": 102.437,
        },
        {
            "profile": "cpu_policy", "path": "runs/native-kernel-cpu-policy-readiness.json",
            "sha256": "9BD6F02A53B34281CB60A13C86CEC26AC99C06F02958FFA23ABAB26A0A54A136",
            "fresh_runs": 2, "negative_controls": 41, "kernel_host_tests": 245,
            "execution_log_sha256": "CFA41675A79CE67949D1FDB8D08F791EB2FD1115237010D33465135306D1CE23",
            "elapsed_seconds": 63.609,
        },
        {
            "profile": "xstate_policy", "path": "runs/native-kernel-xstate-policy-readiness.json",
            "sha256": "669B861DBA9E62A2BCD532BB37A87207DE9D2CC389CA92B2A0B1FF86B2C996C3",
            "fresh_runs": 2, "negative_controls": 43, "kernel_host_tests": 245,
            "execution_log_sha256": "4260145CE808D54618100843E5797A22DAFA156F94093C1D222D6D99730A162A",
            "elapsed_seconds": 73.657,
        },
        {
            "profile": "xstate_exception", "path": "runs/native-kernel-xstate-exception-readiness.json",
            "sha256": "1BFC2D346562896621E72EBAABF05B224ECF517B1050E172DBF426AEF247BFB8",
            "fresh_runs": 2, "negative_controls": 43, "kernel_host_tests": 245,
            "execution_log_sha256": "F3ED8801D7E59F458EBE9E20B63EED505D5DEF7034E3E58654DA297E074BF60D",
            "elapsed_seconds": 73.609,
        },
        {
            "profile": "privilege_msr_policy", "path": "runs/native-kernel-privilege-msr-policy-readiness.json",
            "sha256": "D6198669F7CE065B48D64EEEF3774C213E94B8DD0C1FA537B66B1BCDAE6ECFE0",
            "fresh_runs": 2, "negative_controls": 47, "kernel_host_tests": 245,
            "execution_log_sha256": "9B9A31059D4151F9B9A62622272025F3EDB8EEF33A8C29EEA6267DBE5A72AE32",
            "elapsed_seconds": 69.609,
        },
    ]
    gate["current_dependency_qualification"] = dict(
        gate["current_dependency_qualification"], cycle=180, source_validation_cycle=180,
    )
    evidence = (
        "Cycle 180: " + checkpoint + " qualifies five CPU profiles on the unchanged kernel with "
        "fourteen fresh virtual boots, 225 controls and 46 focused tests. One expected TCG "
        "diagnostic is separate from two WHPX exception boots. Positive provenance tests require "
        "untouched generated receipts; eighty entry substitutions, twenty invalid dependencies "
        "and nineteen aggregate controls reject. Exact current marker/channel/entry evidence and "
        "linked exception/MSR audits pass; old failures and receipts remain preserved."
    )
    gap = (
        "Cycle 180 passes 13/27 selected native checks. Fourteen memory-through-lock profiles "
        "require replay beginning N9-PMM-ACPI-CONSUMER-001 before full exact-candidate qualification. "
        "All-vector/user-context/guarded-IST coverage, target errata, physical hardware, independent "
        "builders and N12.3 live task contexts/architectural CPU retirement remain open. "
        "No phase, flag, new ISO or production claim follows."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N7", "N12", "N36"}:
            phase["current_evidence"] = [evidence, *phase["current_evidence"]]
            phase["current_gaps"] = [gap, *phase["current_gaps"]]
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 180 source inventory: 962 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {
            "FLAG-N7-TRAP-001", "FLAG-N7-CPU-POLICY-001", "FLAG-N7-XSTATE-POLICY-001",
            "FLAG-N7-XSTATE-EXCEPTION-001", "FLAG-N7-PRIVILEGE-MSR-POLICY-001",
            "FLAG-N12-CONCURRENCY-RECLAMATION-001", "FLAG-N36-RECEIPT-COVERAGE-001",
        }:
            flag["evidence"] = [checkpoint, *flag["evidence"]]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)

    checkpoint = "docs/checkpoints/cycle181-memory-qualification.md"
    protocol.update(last_updated_cycle=181, selected_move_id="N9-PMM-ACPI-CONSUMER-001",
                    owner_independent_next_move_id="N6-KENTRY-001")
    protocol["required_records"].insert(0, checkpoint)
    roadmap["baseline"]["pooleos_cycle"] = 181
    for name in (
        "focused_source_projection", "ownership_qualification", "task_stack_qualification",
        "execution_qualification", "entry_provenance_qualification", "boot_chain_qualification",
        "cpu_qualification", "dependency_qualification", "candidate_audit",
    ):
        historical_name = "source_projection" if name == "focused_source_projection" else name
        gate["historical_cycle180_" + historical_name] = gate["current_" + name]
    gate["qualification_status"] = "native_replay_pass_entry_reproduction_and_control_audit_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=181)
    gate["current_focused_source_projection"] = {
        "cycle": 181, "scope": "27_selected_native_checks_not_full_canonical_audit",
        "passed_checks": 27, "total_checks": 27, "pending_downstream_native_checks": 0,
        "final_receipt_fresh_qemu_runs": 28, "superseded_initial_runs": 4,
        "failed_pre_guest_attempts": 1, "revalidated_dependency_execution_cycle": 181,
        "negative_control_groups": 660, "negative_control_cases": 2126,
        "reported_case_count_is_not_executed_rejection_count": True,
        "unproven_per_control_rejection_groups_at_least": 65,
        "aggregate_gate_regression_cases": 79, "source_audit_rejection_cases": 4,
        "focused_python_tests": 166, "focused_python_passed": 164, "focused_python_skipped": 2,
        "focused_test_log_sha256": "F3433D8B55D3FDF95A7B3C75633657CFDB1A4C9FD7E2748A9CC153860FFCE915",
        "entry_receipt_sha256": entry_sha, "core_receipt_sha256": core_sha,
        "core_qualification_stage_count": 17, "core_live_execution_cycle": None,
        "canonical_full_replay_performed": False, "production_ready": False,
        "next_dependency_move_id": "N6-KENTRY-001",
        "required_next_gate": "entry_receipt_reproduction_then_control_execution_and_exact_full_qualification",
    }
    for name in ("entry_provenance", "boot_chain", "cpu"):
        gate["current_" + name + "_qualification"] = dict(
            gate["current_" + name + "_qualification"], source_validation_cycle=181,
        )
    gate["current_entry_provenance_qualification"].update(
        exact_receipt_and_product_reproduction_passed=False,
        latest_reproduction_cycle=181,
        latest_reproduction_status="receipt_mismatch_kernel_product_identical",
    )
    gate["current_closeout_regression"] = {
        "cycle": 181, "status_date": "2026-09-26", "status": "fail",
        "tests_run": 334, "tests_passed": 331, "tests_failed": 1, "tests_skipped": 2,
        "log_sha256": "B9AA16FF5BE22A4EDCFE29F93EA36065612476EEC7605890D5472F06B8C52477",
        "failed_test": "tests.test_native_kernel_entry.NativeKernelEntryTests.test_qualifier_reproduces_receipt_and_product_exactly",
        "canonical_full_replay_performed": False, "merge_qualified": False,
        "production_ready": False,
        "preserved_entry_diagnostic": {
            "status": "receipt_mismatch_kernel_product_identical",
            "differing_path": "$.toolchain.pkelf1_probe_qualification.host_probe_byte_count",
            "recorded_value": 148480, "observed_value": 147968,
            "recorded_receipt_sha256": entry_sha,
            "diagnostic_receipt_sha256": "0E4876E1E8A67E91791FB2C16DB658667AD671122B66EF6E88032ED7FC03F1C5",
            "execution_log_sha256": "A8D5A5CCC1B43EF0D4BECA8AD7DE2A0887D24BFA6F531C24AA587FD09893971C",
            "all_kernel_product_fields_equal": True, "canonical_kernel_sha256": kernel_sha,
            "host_probe_root_cause_established": False, "public_receipt_replaced": False,
        },
    }
    gate["current_ownership_qualification"] = dict(
        gate["current_ownership_qualification"], cycle=181,
        scope="host177_dispatch_and_inactive_stack_receipt_with_cycle181_VM_and_AP_replay",
        live_receipt_scope="two_current_VM_and_two_current_four_vcpu_AP_runs",
        live_replay_cycle=181, fresh_current_cycle_qemu_runs=4,
        live_receipt_source_current=True, current_boot_artifact_set_replay_pending=False,
        active_root_current_image_replay_complete=True, ap_runtime_live_integration_verified=True,
        entry_receipt_sha256=entry_sha,
        virtual_memory_receipt_sha256="4AFEA30E25DB4DCD0D9038E01D3FE1CC6EE5D82DBAB4595A4631D34902460BB7",
        smp_receipt_sha256="2B1F8D623D31476F2C8886DFD583BE9514C68A2B3D0DA36BC75DDD13D6823CCA",
    )
    gate["current_dependency_qualification"] = dict(
        gate["historical_cycle175_dependency_qualification"], cycle=181, source_validation_cycle=181,
        status="live_replay_pass_control_execution_incomplete", applies_to_current_source=True,
        scope="fourteen_current_guest_receipts_not_complete_per_control_execution_evidence",
        kernel_sha256=kernel_sha, fresh_qemu_runs=28, superseded_initial_runs=4,
        superseded_profiles=["atomics", "locks"], failed_pre_guest_attempts=1,
        focused_python_tests=166, focused_python_passed=164, focused_python_skipped=2,
        memory_gate_rejection_cases=20, host_identity_gate_rejection_cases=59,
        source_audit_rejection_cases=4, positive_receipts_rebound_in_tests=False,
        recorded_marker_replay_verified=True, independent_memory_oracle_replay_verified=True,
        reported_case_count_is_not_executed_rejection_count=True,
        control_execution_complete=False, unproven_per_control_rejection_groups_at_least=65,
    )
    gate["current_dependency_qualification"]["receipt_bindings"] = [
        {
            "profile": "physical_memory",
            "path": "runs/native-kernel-physical-memory-readiness.json",
            "sha256": "EEFD0E8592CB98E8D0EDBCB480FFD6DDEF761C5432AE0ED4FB3C95C73E10D008",
            "fresh_runs": 2,
            "kernel_host_tests": 245,
            "negative_groups": 191,
            "negative_cases": 191,
            "marker_count": 45,
            "execution_log_sha256": "73D78CC992A80B448CB62D488AC4EFA73BF8EED5DBCA5B8F76C37B5AF855061A",
            "elapsed_seconds": 115.297
        },
        {
            "profile": "virtual_memory",
            "path": "runs/native-kernel-virtual-memory-readiness.json",
            "sha256": "4AFEA30E25DB4DCD0D9038E01D3FE1CC6EE5D82DBAB4595A4631D34902460BB7",
            "fresh_runs": 2,
            "kernel_host_tests": 245,
            "negative_groups": 48,
            "negative_cases": 48,
            "marker_count": 40,
            "execution_log_sha256": "3F150DB57A3859B6474CCAE0679F8D501C0B6264436950A77C7EDC5EE719DE52",
            "elapsed_seconds": 63.813
        },
        {
            "profile": "interrupt_time",
            "path": "runs/native-kernel-interrupt-time-readiness.json",
            "sha256": "19FB9DA0B525064D56126E9EEE159C887A46B4FD1EB6B6DA3646C5F88182E7B2",
            "fresh_runs": 2,
            "kernel_host_tests": 245,
            "negative_groups": 58,
            "negative_cases": 58,
            "marker_count": 36,
            "execution_log_sha256": "98DE2D5B7B345ED29CFDA5E1BBE0160126A332F0E4319B4AF91FCE66567C4606",
            "elapsed_seconds": 65.797
        },
        {
            "profile": "smp_first_ap",
            "path": "runs/native-kernel-smp-first-ap-readiness.json",
            "sha256": "58F0EBEEA6C844714D4E57568C56987C0A9E03D92A9D29421974A6D7C91FD5AC",
            "fresh_runs": 2,
            "kernel_host_tests": 245,
            "negative_groups": 72,
            "negative_cases": 72,
            "marker_count": 38,
            "execution_log_sha256": "D2823B8479F27386573962DB57FA0DC7211F656CDEC4BDF03C890911B24C5242",
            "elapsed_seconds": 71.594
        },
        {
            "profile": "smp_percpu_runtime",
            "path": "runs/native-kernel-smp-percpu-runtime-readiness.json",
            "sha256": "03B2E751984D8FADBB64302748E3D4CBB025F5DF285D665AAD8399CDA9DC07C2",
            "fresh_runs": 2,
            "kernel_host_tests": 245,
            "negative_groups": 19,
            "negative_cases": 159,
            "marker_count": 42,
            "execution_log_sha256": "6AA6B171C06F825AB34FD35B6DC0F0C4AE1B3C3BDBEA115B9A29D1DDD4812575",
            "elapsed_seconds": 55.906
        },
        {
            "profile": "smp_ipi",
            "path": "runs/native-kernel-smp-ipi-readiness.json",
            "sha256": "2B1F8D623D31476F2C8886DFD583BE9514C68A2B3D0DA36BC75DDD13D6823CCA",
            "fresh_runs": 2,
            "kernel_host_tests": 245,
            "negative_groups": 30,
            "negative_cases": 249,
            "marker_count": 40,
            "execution_log_sha256": "B52F64CD5C85DB0561172F386D850EE8876DE82BDE1CD3453EF45FD17EE63EE9",
            "elapsed_seconds": 65.609
        },
        {
            "profile": "scheduler",
            "path": "runs/native-kernel-scheduler-readiness.json",
            "sha256": "CC340D6AFAD07D3A17A3E63AC296A228E8366EC48D623B277DAAFEF588B4E6D2",
            "fresh_runs": 2,
            "kernel_host_tests": 245,
            "negative_groups": 28,
            "negative_cases": 115,
            "marker_count": 34,
            "execution_log_sha256": "399BEE5F394C0AAB2849ABCE27436416C874B83E860D63D92D413338C2E8878D",
            "elapsed_seconds": 75.437
        },
        {
            "profile": "scheduler_preempt",
            "path": "runs/native-kernel-scheduler-preemption-readiness.json",
            "sha256": "D1F027454CDE978D504FFA232A427ABC7992D92193B593DBF9261EF2C9E190BE",
            "fresh_runs": 2,
            "kernel_host_tests": 245,
            "negative_groups": 25,
            "negative_cases": 178,
            "marker_count": 35,
            "execution_log_sha256": "3102C866D1525AAE7C4AB92053387BFE6AFE3C814F048166A939B0B59ED990A8",
            "elapsed_seconds": 86.078
        },
        {
            "profile": "scheduler_deferred",
            "path": "runs/native-kernel-scheduler-deferred-readiness.json",
            "sha256": "05F5250DD497E0803959AA67939362DBA19023A97089C06AA1B66837AF6C64AC",
            "fresh_runs": 2,
            "kernel_host_tests": 245,
            "negative_groups": 30,
            "negative_cases": 208,
            "marker_count": 37,
            "execution_log_sha256": "4EBE89807DC249C40962D3E7447C0C9F29E74969E1379DC547ECA0E970986D14",
            "elapsed_seconds": 77.125
        },
        {
            "profile": "scheduler_smp",
            "path": "runs/native-kernel-scheduler-smp-readiness.json",
            "sha256": "47382C39021EB7BF6580844B6E4B1F2BAC53C05FD56ECB2313E036C81A1A391C",
            "fresh_runs": 2,
            "kernel_host_tests": 245,
            "negative_groups": 32,
            "negative_cases": 209,
            "marker_count": 37,
            "execution_log_sha256": "A5FEC8483EF1E11FC817A0D5BC72936936C71B95AF19DC428C50CC70F7197FAE",
            "elapsed_seconds": 77.031
        },
        {
            "profile": "scheduler_ap_workers",
            "path": "runs/native-kernel-scheduler-ap-workers-readiness.json",
            "sha256": "828E48B8EBBFF8472A9BD27B7EA7BCD2DA64E418B58E38F9FD375B640CA365C0",
            "fresh_runs": 2,
            "kernel_host_tests": 245,
            "negative_groups": 34,
            "negative_cases": 226,
            "marker_count": 37,
            "execution_log_sha256": "21900BB29BF0D4A76CAF00CA05051C739A38319DA0A37D143DA90AAA6A15CED7",
            "elapsed_seconds": 68.438
        },
        {
            "profile": "scheduler_smp_preempt",
            "path": "runs/native-kernel-scheduler-smp-preempt-readiness.json",
            "sha256": "269B22A60B6E5B7D512EC18BF1EC30396C6E0AB41B2182303BF4E89A3AF18076",
            "fresh_runs": 2,
            "kernel_host_tests": 245,
            "negative_groups": 34,
            "negative_cases": 232,
            "marker_count": 38,
            "execution_log_sha256": "658B2791846126535D9385743AD633421B22FF64E22437D38E3F4EAF6561C867",
            "elapsed_seconds": 68.313
        },
        {
            "profile": "atomics",
            "path": "runs/native-kernel-atomics-readiness.json",
            "sha256": "7DB057751A677EE46115146E84FCE19EDD3F49B5E7B699948B13307DA1ACA986",
            "fresh_runs": 2,
            "kernel_host_tests": 245,
            "negative_groups": 29,
            "negative_cases": 78,
            "marker_count": 41,
            "execution_log_sha256": "588C498E72D9B75AF3C7F38B31973A207CC4E90C8ECD6AAD53ED893E8B670857",
            "elapsed_seconds": 90.156
        },
        {
            "profile": "locks",
            "path": "runs/native-kernel-locks-readiness.json",
            "sha256": "837AF50A257AA54316E72014E4B63BB6B18E33161E42FD854A849F2D7AE96F79",
            "fresh_runs": 2,
            "kernel_host_tests": 245,
            "negative_groups": 30,
            "negative_cases": 103,
            "marker_count": 35,
            "execution_log_sha256": "F3D19104BFF87F4D07C6D36EBECE56413E7410894E64B393FEB255C8DF8FAADF",
            "elapsed_seconds": 60.953
        }
    ]
    gate["current_control_execution_audit"] = {
        "cycle": 181, "status": "open", "requirement_id": "ADD-N36-RECEIPT-COVERAGE-001",
        "flag_id": "FLAG-N36-RECEIPT-COVERAGE-001", "blocks_merge_qualification": True,
        "scope": "four_scheduler_qualifier_loops_not_an_exhaustive_all_profile_audit",
        "unproven_per_control_rejection_groups_at_least": 65,
        "reported_case_count_is_not_executed_rejection_count": True,
        "next_profile": "scheduler_deferred", "production_ready": False,
        "source_control_gaps": [
            {
                "profile": "scheduler_deferred",
                "source_path": "tools/qualify_native_kernel_scheduler_deferred.py",
                "source_sha256": "0A5157E0AF2BB4B886FEE5C97F53CB3417F94EAF59212C3F30B583239C57C42C",
                "control_ids": [
                    "NEG-N12-PKSCHED3-FIXED-CAPACITY",
                    "NEG-N12-PKSCHED3-DUPLICATE-SUPPRESSION",
                    "NEG-N12-PKSCHED3-TOP-HALF-CONTEXT",
                    "NEG-N12-PKSCHED3-RECURSION",
                    "NEG-N12-PKSCHED3-EOI-PERMIT",
                    "NEG-N12-PKSCHED3-PRIORITY-BYPASS",
                    "NEG-N12-PKSCHED3-QUEUED-CANCEL",
                    "NEG-N12-PKSCHED3-RUNNING-CANCEL",
                    "NEG-N12-PKSCHED3-FLUSH-WATERMARK",
                    "NEG-N12-PKSCHED3-STALE-GENERATION",
                    "NEG-N12-PKSCHED3-FAULT-ROLLBACK",
                    "NEG-N12-PKSCHED3-SHUTDOWN-ORDER",
                    "NEG-N12-PKSCHED3-NO-HEAP-OR-CALLBACK",
                    "NEG-N12-PKSCHED3-WORKER-STACK-OWNERSHIP"
                ],
                "reported_case_count": 14,
                "slice_start": 15,
                "slice_end": 29,
                "classification": "source_audit_attestation_without_per_control_rejection_execution"
            },
            {
                "profile": "scheduler_smp",
                "source_path": "tools/qualify_native_kernel_scheduler_smp.py",
                "source_sha256": "6D6175C9FAA2C1B4235A0249FC6C9B886182D3EBE9F4FC17BEFE938B1369CA39",
                "control_ids": [
                    "NEG-N12-PKSCHED4-EXACT-TOPOLOGY",
                    "NEG-N12-PKSCHED4-DUPLICATE-RUNNABLE",
                    "NEG-N12-PKSCHED4-STALE-GENERATION",
                    "NEG-N12-PKSCHED4-OWNER-EPOCH",
                    "NEG-N12-PKSCHED4-WAKE-ACK-BINDING",
                    "NEG-N12-PKSCHED4-MIGRATION-ACK-BINDING",
                    "NEG-N12-PKSCHED4-DISPATCH-ACK-BINDING",
                    "NEG-N12-PKSCHED4-OFFLINE-TIMEOUT",
                    "NEG-N12-PKSCHED4-LATE-ACK",
                    "NEG-N12-PKSCHED4-SOURCE-QUEUE-ROLLBACK",
                    "NEG-N12-PKSCHED4-TOPOLOGY-BALANCING",
                    "NEG-N12-PKSCHED4-FAIRNESS-BOUND",
                    "NEG-N12-PKSCHED4-IDLE-OWNERSHIP",
                    "NEG-N12-PKSCHED4-AP-REGISTER-RESTORE",
                    "NEG-N12-PKSCHED4-PARK-SCRUB-RELEASE",
                    "NEG-N12-PKSCHED4-NO-HEAP-OR-CALLBACK"
                ],
                "reported_case_count": 16,
                "slice_start": 15,
                "slice_end": 31,
                "classification": "source_audit_attestation_without_per_control_rejection_execution"
            },
            {
                "profile": "scheduler_ap_workers",
                "source_path": "tools/qualify_native_kernel_scheduler_ap_workers.py",
                "source_sha256": "21C8A734AC8100BCF8EB82FE1B201E0012F843D9EA39773C74B120B8ECE7882D",
                "control_ids": [
                    "NEG-N12-PKSCHED5-TYPED-CALL-ALLOWLIST",
                    "NEG-N12-PKSCHED5-ARBITRARY-CALLBACK",
                    "NEG-N12-PKSCHED5-TOP-HALF-CONTEXT",
                    "NEG-N12-PKSCHED5-DISPATCH-BEFORE-EOI",
                    "NEG-N12-PKSCHED5-DUPLICATE-WORK",
                    "NEG-N12-PKSCHED5-QUEUED-CANCEL",
                    "NEG-N12-PKSCHED5-REMOTE-CANCEL",
                    "NEG-N12-PKSCHED5-ACK-BINDING",
                    "NEG-N12-PKSCHED5-OFFLINE-TIMEOUT",
                    "NEG-N12-PKSCHED5-SOURCE-QUEUE-ROLLBACK",
                    "NEG-N12-PKSCHED5-LATE-ACK",
                    "NEG-N12-PKSCHED5-FAIRNESS-BOUND",
                    "NEG-N12-PKSCHED5-FLUSH-WATERMARK",
                    "NEG-N12-PKSCHED5-RECLAIM-GENERATION",
                    "NEG-N12-PKSCHED5-STALE-ID",
                    "NEG-N12-PKSCHED5-IST1-STACK-GATE",
                    "NEG-N12-PKSCHED5-AP-REGISTER-RESTORE",
                    "NEG-N12-PKSCHED5-PARK-SCRUB-RELEASE"
                ],
                "reported_case_count": 18,
                "slice_start": 15,
                "slice_end": 33,
                "classification": "source_audit_attestation_without_per_control_rejection_execution"
            },
            {
                "profile": "scheduler_smp_preempt",
                "source_path": "tools/qualify_native_kernel_scheduler_smp_preempt.py",
                "source_sha256": "C075F0FAEB9AC177508ACC25201F8A78C8A03136F3511DFE67C6BDB6EB71DB6B",
                "control_ids": [
                    "NEG-N12-PKSCHED6-FRAME-CPU",
                    "NEG-N12-PKSCHED6-FRAME-APIC",
                    "NEG-N12-PKSCHED6-FRAME-EPOCH",
                    "NEG-N12-PKSCHED6-FRAME-STACK",
                    "NEG-N12-PKSCHED6-TIMER-EPOCH",
                    "NEG-N12-PKSCHED6-EVENT-DEADLINE",
                    "NEG-N12-PKSCHED6-EVENT-ORDER",
                    "NEG-N12-PKSCHED6-ACK-BINDING",
                    "NEG-N12-PKSCHED6-ACK-GATED-OWNER",
                    "NEG-N12-PKSCHED6-OFFLINE-TIMEOUT",
                    "NEG-N12-PKSCHED6-SOURCE-QUEUE-ROLLBACK",
                    "NEG-N12-PKSCHED6-LATE-ACK",
                    "NEG-N12-PKSCHED6-WATCHDOG-BOUND",
                    "NEG-N12-PKSCHED6-STARVATION-BOUND",
                    "NEG-N12-PKSCHED6-DUPLICATE-RUNNABLE",
                    "NEG-N12-PKSCHED6-AP-REGISTER-RESTORE",
                    "NEG-N12-PKSCHED6-PARK-SCRUB-RELEASE"
                ],
                "reported_case_count": 17,
                "slice_start": 16,
                "slice_end": 33,
                "classification": "source_audit_attestation_without_per_control_rejection_execution"
            }
        ],
    }
    evidence = (
        "Cycle 181: " + checkpoint + " replays fourteen current-kernel memory-through-lock profiles "
        "with 28 final boots, four superseded atomics/locks boots and one pre-guest source-audit "
        "failure. All 27 selected consistency checks pass; 164 of 166 focused tests pass with two "
        "optional local-transcript skips. Untouched positive receipts guard 224 entry substitutions "
        "and 56 invalid dependencies. Source audit requires all ten SMP scheduler tests and both "
        "rollback regressions; four source-audit and 79 aggregate identity/accounting cases pass. "
        "The 660 groups and 2126 cases are reported qualifier counts, not all executed rejections."
    )
    gap = (
        "Cycle 181 resumed closeout fails exact entry-receipt reproduction at the host-only "
        "probe byte count (148480 recorded, 147968 observed); all kernel product fields and "
        "canonical bytes reproduce. Resolve N6-KENTRY-001 before the control audit. "
        "Cycle 181 identifies at least 65 PKSCHED3/4/5/6 source-control entries (14/16/18/17) "
        "labeled passed/rejected without per-control rejection execution. Repair this existing "
        "ADD-N36-RECEIPT-COVERAGE-001 requirement beginning scheduler_deferred before exact full "
        "canonical qualification, publication/review and PR78 merge, then N12.3 live task contexts "
        "and architectural CPU retirement. Other profiles also need coverage audit; complete "
        "transitive provenance, independent builders, hardware and production remain open."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N8", "N9", "N12", "N36"}:
            phase["current_evidence"] = [evidence, *phase["current_evidence"]]
            phase["current_gaps"] = [gap, *phase["current_gaps"]]
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 181 source inventory: 962 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {
            "FLAG-N9-PMM-ACPI-CONSUMER-001", "FLAG-N9-VM-DIRECT-MAP-001",
            "FLAG-N12-CONCURRENCY-RECLAMATION-001", "FLAG-N36-RECEIPT-COVERAGE-001",
            "FLAG-N6-KENTRY-001",
        }:
            flag["evidence"] = [checkpoint, *flag["evidence"]]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle182(roadmap, test_count)


def apply_cycle182(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle182-host-toolchain-repair.md"
    protocol = roadmap["execution_protocol"]
    protocol.update(last_updated_cycle=182, selected_move_id="N6-KENTRY-001",
                    owner_independent_next_move_id="N5-ELF-001")
    protocol["required_records"].insert(0, checkpoint)
    roadmap["baseline"]["pooleos_cycle"] = 182
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for name in (
        "focused_source_projection", "ownership_qualification", "entry_provenance_qualification",
        "boot_chain_qualification", "cpu_qualification", "dependency_qualification",
        "closeout_regression", "candidate_audit",
    ):
        historical = "source_projection" if name == "focused_source_projection" else name
        gate["historical_cycle181_" + historical] = copy.deepcopy(gate["current_" + name])
    entry_sha = "5B3A8DAD63C21416A43074664F9C52B9BE8FB6E906824AF30F805F5FFC65CED5"
    gate["qualification_status"] = "host_toolchain_repaired_entry_reproduced_dependency_and_control_replay_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=182)
    gate["current_focused_source_projection"] = {
        "cycle": 182, "scope": "27_selected_native_checks_not_full_canonical_audit",
        "passed_checks": 3, "total_checks": 27, "pending_downstream_native_checks": 24,
        "final_receipt_fresh_qemu_runs": 0, "canonical_full_replay_performed": False,
        "passing_profiles": ["kernel_entry", "kernel_revalidation", "kernel_errata_policy"],
        "entry_receipt_sha256": entry_sha, "production_ready": False,
        "next_dependency_move_id": "N5-ELF-001",
        "required_next_gate": "shared_loader_and_ordered_dependencies_then_control_audit_and_exact_full_qualification",
        "unproven_per_control_rejection_groups_at_least": 65,
        "reported_case_count_is_not_executed_rejection_count": True,
    }
    gate["current_entry_provenance_qualification"] = dict(
        gate["current_entry_provenance_qualification"], cycle=182, source_validation_cycle=182,
        entry_receipt_sha256=entry_sha, source_binding_count=61,
        exact_receipt_and_product_reproduction_passed=True, latest_reproduction_cycle=182,
        latest_reproduction_status="exact_receipt_and_product_reproduced_under_hostile_environment",
    )
    gate["current_host_toolchain_qualification"] = {
        "cycle": 182, "status": "scoped_repair_verified", "profile_path": "specs/native-host-msvc-profile.json",
        "profile_sha256": "4BD6B069392E11215EE1942425B3A12CE2CAEC6746A9450EAC20B037FC538182",
        "msvc_version": "14.44.35207", "windows_sdk_version": "10.0.18362.0",
        "pinned_trees": 4, "pinned_files": 720, "pinned_bytes": 889212229,
        "matrix_variants": 7, "observed_size_change_cause": "MSVC_CRT_library_tree_selection",
        "old_crt_probe_bytes": 148480, "new_crt_probe_bytes": 147968,
        "matrix_sha256": "25748BD729DC814C1C9532A198DECBA12AFBB64523CA32FC129F846907A6FAB9",
        "cross_matrix_sha256": "75795B2ACB21C8A36D71CEF44FB66A152479EEAB641B9616B501C69E709CB409",
        "kernel_product_unchanged": True, "environment_changed_globally": False,
        "toolchain_fixture_receipt_sha256": "87668ADC571427244CD490D172CD01BAA3871709A0D76F7319D665526B68CFB5",
        "initial_hostile_regression": {"tests_run": 38, "tests_passed": 37, "tests_failed": 1,
            "failure": "fixture_UEFI_linker_inherited__LINK__option",
            "log_sha256": "E76BA9D6444174F1401C7265DC880B7A8F35588CADB9393494A86044640BDF7D"},
        "complete_host_attestation": False, "second_builder_reproduced": False,
        "production_ready": False,
    }
    gate["current_closeout_regression"] = {
        "cycle": 182, "status": "pass", "scope": "host_toolchain_entry_and_fixture_tests_only",
        "tests_run": 39, "tests_passed": 39, "tests_failed": 0, "tests_skipped": 0,
        "hostile_environment": True,
        "log_sha256": "F3056EA5AD8415E934307A9947D0E186DB83E3209155DF393D58B34E0F45E2AF",
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    for name in ("boot_chain", "cpu", "dependency"):
        previous = gate["historical_cycle181_" + name + "_qualification"]
        gate["current_" + name + "_qualification"] = dict(
            previous, cycle=182, source_validation_cycle=182, applies_to_current_source=False,
            status="replay_required_after_host_toolchain_provenance_repair", fresh_qemu_runs=0,
            qualified_profiles=[], readiness_replay_required_profiles=previous["qualified_profiles"],
            retained_execution_cycle=previous["cycle"], current_candidate_full_gate_passed=False,
        )
    gate["current_ownership_qualification"] = dict(
        gate["current_ownership_qualification"], cycle=182,
        scope="retained_host177_evidence_live_provenance_replay_required",
        fresh_current_cycle_qemu_runs=0, live_receipt_source_current=False,
        current_boot_artifact_set_replay_pending=True, active_root_current_image_replay_complete=False,
        ap_runtime_live_integration_verified=False,
    )
    evidence = (
        "Cycle 182: " + checkpoint + " isolates probe-size drift to the MSVC CRT library tree through "
        "seven controlled builds. Four pinned host trees (720 files) and shared environment sanitation "
        "restore exact entry and fixture reproduction under hostile overrides; 39 focused tests pass. "
        "The first 38-test hostile run failed in the fixture UEFI linker and remains preserved. "
        "Kernel product bytes are unchanged; six new entry input bindings expose host provenance."
    )
    gap = (
        "The selected projection is 3/27; 24 dependent checks reject stale entry/fixture provenance. "
        "N5-ELF-001 shared-loader qualification precedes N5 symbols/boot, CPU and memory replay. "
        "The existing N36 audit still requires at least 65 scheduler rejection executions and broader "
        "coverage review before exact canonical/Doctor/publication/review qualification and PR78 merge. "
        "Core host evidence remains Cycle 177 with incomplete transitive tool provenance. No new guest, "
        "native feature, ISO, phase closure, independent builder or production readiness is claimed."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N3", "N5", "N6", "N12", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 182 source inventory: 981 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N36-RECEIPT-COVERAGE-001", "FLAG-N6-KENTRY-001", "FLAG-N5-ELF-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle183(roadmap, test_count)


def apply_cycle183(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle183-elf-loader-provenance.md"
    protocol = roadmap["execution_protocol"]
    protocol.update(last_updated_cycle=183, selected_move_id="N5-ELF-001",
                    owner_independent_next_move_id="N5-SYMBOLS-SEMANTICS-001")
    protocol["required_records"][0:0] = [checkpoint, "docs/checkpoints/cycle183-unfinished-cloud-backup.md"]
    roadmap["baseline"]["pooleos_cycle"] = 183
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for name in (
        "focused_source_projection", "ownership_qualification", "entry_provenance_qualification",
        "boot_chain_qualification", "cpu_qualification", "dependency_qualification",
        "closeout_regression", "candidate_audit", "host_toolchain_qualification",
    ):
        historical = "source_projection" if name == "focused_source_projection" else name
        gate["historical_cycle182_" + historical] = copy.deepcopy(gate["current_" + name])
    entry_sha = "ACAEC303FA750DD75CA8B721B0BD359E4291CF1C4218B3DDFBFE09AF17390B65"
    gate["qualification_status"] = "shared_loader_and_entry_reproduced_downstream_and_control_replay_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=183)
    gate["current_focused_source_projection"] = dict(
        gate["current_focused_source_projection"], cycle=183, entry_receipt_sha256=entry_sha,
        next_dependency_move_id="N5-SYMBOLS-SEMANTICS-001",
        required_next_gate="ordered_dependencies_then_control_audit_and_exact_full_qualification",
    )
    gate["current_entry_provenance_qualification"] = dict(
        gate["current_entry_provenance_qualification"], cycle=183, source_validation_cycle=183,
        entry_receipt_sha256=entry_sha, source_binding_count=72, latest_reproduction_cycle=183,
        inherited_shared_loader_input_count=19,
        latest_reproduction_status="exact_receipt_and_product_reproduced_with_shared_loader_input_bindings",
    )
    gate["current_shared_loader_qualification"] = {
        "cycle": 183, "contract_id": "PKELF1", "status": "single_host_replay_pass",
        "receipt_path": "runs/native_elf_loader_readiness.json",
        "receipt_sha256": "70399A505005A60E04CB801E3B49E5A149B854E3CE9A4F952ECA458761E45E91",
        "implementation_input_count": 19, "new_input_bindings": 8,
        "host_profile_sha256": "4BD6B069392E11215EE1942425B3A12CE2CAEC6746A9450EAC20B037FC538182",
        "rust_host_tests_passed": 12, "clippy_runs_passed": 3,
        "no_std_target_builds_passed": 2, "pooleboot_integration_builds_passed": 2,
        "exact_loaded_byte_vectors_matched": 3, "maximum_relocations_exercised": 4096,
        "negative_controls_passed": 129, "differential_fuzz_cases": 16384, "differential_mismatches": 0,
        "host_profile_rejection_cases": 10, "build_input_mutation_cases": 8,
        "entry_shared_input_mutation_cases": 19, "invalid_output_admission_cases": 2,
        "invalid_output_created_or_replaced": False, "exact_receipt_reproduction_passed": True,
        "execution_log_sha256": "A9C743905D74D9DFC26B724F9D42068DCC36817F084A56EDC85D2DB7AC420F64",
        "complete_host_attestation": False, "second_builder_reproduced": False,
        "fresh_qemu_runs": 0, "n5_exit_gate_satisfied": False, "production_ready": False,
    }
    gate["current_closeout_regression"] = {
        "cycle": 183, "status": "pass", "scope": "shared_loader_entry_host_profile_and_fixture_tests_only",
        "tests_run": 59, "tests_passed": 59, "tests_failed": 0, "tests_skipped": 0,
        "hostile_environment": True,
        "log_sha256": "2CAE0B436D748B7658D39BD81457CDD283E9244AA4962E2B86A0812CED3D6559",
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    for name in ("boot_chain", "cpu", "dependency"):
        gate["current_" + name + "_qualification"] = dict(
            gate["current_" + name + "_qualification"], cycle=183, source_validation_cycle=183,
            status="replay_required_after_shared_loader_and_entry_provenance_repair",
        )
    gate["current_ownership_qualification"] = dict(gate["current_ownership_qualification"], cycle=183)
    evidence = (
        "Cycle 183: " + checkpoint + " qualifies the shared ELF loader with 12 Rust tests, 129 "
        "negative controls and 16384 differential cases. Typed host-profile evidence is validated "
        "before receipt output, and entry inherits all 19 loader inputs in 72 total bindings. "
        "All 59 focused hostile-environment Python tests pass, including exact ELF, entry and fixture "
        "reproduction. Entry passes 245 host tests and 43 controls with unchanged product bytes. "
        "Five new test methods bring the discovered inventory to 986; discovery is not execution."
    )
    gap = (
        "The separate ELF readiness check passes; the 27-check projection remains 3/27. "
        "N5-SYMBOLS-SEMANTICS-001 and ordered N5/CPU/memory replay precede final scheduler evidence, "
        "the existing 65 per-control execution gaps, exact canonical/Doctor/publication/review and "
        "PR78 merge. Historical failures remain. No guest boot, new native feature, complete host "
        "attestation, independent builder, phase/flag closure, ISO or production readiness is claimed."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N3", "N5", "N6", "N12", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 183 source inventory: 986 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N36-RECEIPT-COVERAGE-001", "FLAG-N6-KENTRY-001", "FLAG-N5-ELF-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle184(roadmap, test_count)


def apply_cycle184(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle184-boot-host-provenance.md"
    protocol = roadmap["execution_protocol"]
    protocol.update(last_updated_cycle=184, selected_move_id="N5-SYMBOLS-SEMANTICS-001",
                    owner_independent_next_move_id="N7-TRAP-001")
    protocol["required_records"][0:0] = [checkpoint,
        "docs/checkpoints/cycle184-unfinished-cloud-backup.md",
        "docs/checkpoints/cycle184-validated-boot-cloud-backup.md"]
    roadmap["baseline"]["pooleos_cycle"] = 184
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for name in (
        "focused_source_projection", "ownership_qualification", "entry_provenance_qualification",
        "boot_chain_qualification", "cpu_qualification", "dependency_qualification",
        "closeout_regression", "candidate_audit", "host_toolchain_qualification", "shared_loader_qualification",
    ):
        suffix = "source_projection" if name == "focused_source_projection" else name
        gate["historical_cycle183_" + suffix] = copy.deepcopy(gate["current_" + name])
    gate["qualification_status"] = "boot_chain_host_provenance_replayed_cpu_memory_and_control_replay_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=184)
    gate["current_focused_source_projection"] = dict(
        gate["current_focused_source_projection"], cycle=184, passed_checks=8,
        pending_downstream_native_checks=19, final_receipt_fresh_qemu_runs=6,
        kernel_entry_runs=2, superseded_initial_qemu_runs=8,
        passing_profiles=["kernel_entry", "symbol", "policy", "kernel_load", "pooleboot",
                          "kernel_revalidation", "kernel_transfer", "kernel_errata_policy"],
        next_dependency_move_id="N7-TRAP-001",
        required_next_gate="CPU_memory_replay_then_control_execution_audit_and_exact_full_qualification",
        focused_python_tests_passed=109, focused_python_tests_skipped=0,
        focused_test_log_sha256="A2F46811D85AC57D35BDE1641F295116046CF3BA1AABAF039EEE1899793149FE",
    )
    gate["current_entry_provenance_qualification"] = dict(
        gate["current_entry_provenance_qualification"], source_validation_cycle=184,
    )
    gate["current_shared_loader_qualification"] = dict(
        gate["current_shared_loader_qualification"], source_validation_cycle=184,
    )
    gate["current_ownership_qualification"] = dict(gate["current_ownership_qualification"], cycle=184)
    for name in ("cpu", "dependency"):
        gate["current_" + name + "_qualification"] = {
            "cycle": 184, "source_validation_cycle": 184,
            "status": "replay_required_after_entry_and_boot_host_provenance_repair",
            "applies_to_current_source": False, "qualified_profiles": [], "fresh_qemu_runs": 0,
            "historical_record": "historical_cycle183_" + name + "_qualification",
            "current_candidate_full_gate_passed": False, "production_ready": False,
        }
    bindings = [
        {"profile": profile, "path": path, "sha256": digest, "fresh_runs": runs,
         "execution_log_sha256": log}
        for profile, path, digest, runs, log in (
            ("symbol", "runs/native_symbol_readiness.json", "F2AD36EBD03B14BF9C1BE17CA9AABFFA146703D507B5DB70E7EEB9AC8147BCE0", 0, "39D622078702BC250B96EFD6CACB9EC04214EB6EEF0062BCFD4BF83419DC0038"),
            ("policy", "runs/native_policy_readiness.json", "4B3C4CFBEB27119D7D84317F718AB472B0F5F48B6CB89B110E3272767AE2EC8B", 0, "4E0AA1F9DB24DE8D841452D60CA70EBAD0B1883FF79739D7A96CB02A1045ECA7"),
            ("kernel_load", "runs/native_kernel_load_readiness.json", "998D67B4B8ABB92534163E9C311938335E0AEBEF013382AD1C1F6A6C7F7EFE65", 2, "417C7B59688B1D98ACDF8391A970DF09430B126C4345FE53A04840D1C461B330"),
            ("pooleboot", "runs/native_pooleboot_readiness.json", "C94B4FC184FB2F7A76AF3C9AFA577C4C1B27DF5D50A961720558A1B1E6B6583E", 2, "56338F6E2175B97E50BB1E2377476252F07B88CAAEAF64E220040A84FE086C65"),
            ("kernel_revalidation", "runs/native-kernel-revalidation-readiness.json", "0BF1A4E6EC9097738E6BC57BA68A43B4BFE2417AA617BBD8879149AA174F89CB", 0, "A241574365E43C16D05D7D059E5D2DF662F24D5D5A58A65536FB8528DE34177D"),
            ("kernel_transfer", "runs/native-kernel-transfer-readiness.json", "1FA247B02A1B8DB0D54E4AEB20DA2E911B8C1840A765B36AB299A7A96164ABD1", 2, "CFA47E76AB3375E41C02258ADFBB2C49320C3D8F2D0956B0CDC404ECD5A5D402"),
            ("firmware", "runs/native_firmware_readiness.json", "BEDA71BC705EDF813259778E1B40CAB425DF7AAFDD70A4D0B85460E0FB4610A0", 0, "AADE70D894175EDA671F0E8A35E4F908346E57AD18A962EBB3D699970A085289"),
            ("boot_trust", "runs/native_boot_trust_readiness.json", "85E7EEF84704C436213904C0C2D67F9A76EE9090923A822D98EBF34880A20D47", 0, "E86826A26679C8FCABA1858EA95FC621D3E4D8F00B5CD0AA68C272F09A7C581D"),
        )
    ]
    gate["current_boot_chain_qualification"] = {
        "cycle": 184, "source_validation_cycle": 184, "status": "single_host_replay_pass",
        "scope": "six_N5_profiles_plus_firmware_and_boot_trust_prerequisites",
        "applies_to_current_source": True, "qualified_profiles": [b["profile"] for b in bindings[:6]],
        "receipt_bindings": bindings[:6], "prerequisite_receipt_bindings": bindings[6:],
        "fresh_qemu_runs": 6, "superseded_initial_runs": 8, "kernel_entry_runs": 2,
        "superseded_run_reason": "admission_error_formatter_and_PooleBoot_count_schema_repairs",
        "failed_unadmitted_guest_attempts_excluded_from_success_count": True,
        "preserved_failed_runner_attempts": 13,
        "kernel_sha256": "563ED1976CAB4DA773BAE9BCE49F370242C893760E7C221239C1B31F44D969CA",
        "kernel_host_tests": 245, "loader_host_tests": 330, "pooleboot_host_tests": 8,
        "focused_python_tests": 109, "focused_python_passed": 109, "focused_python_skipped": 0,
        "retained_file_count": 9, "inner_artifact_bytes": 8761, "retained_bytes": 11952,
        "inner_set_sha256": "A3078488088B2BF11B8D88F48862FA8D80957D610EB1F3FF4411AD5E4729FEAF",
        "host_pinned_qualifier_count": 6,
        "host_profile_sha256": "4BD6B069392E11215EE1942425B3A12CE2CAEC6746A9450EAC20B037FC538182",
        "host_profile_rejection_cases": 66, "host_input_binding_mutation_cases": 36,
        "symbol_policy_invalid_output_cases": 8, "forged_PooleBoot_host_test_count_rejections": 12,
        "boot_identity_rejection_cases": 13,
        "receipt_generation_semantically_validated": True, "receipt_write_semantically_validated": True,
        "readiness_replay_required_profiles": [], "complete_host_attestation": False,
        "second_builder_reproduced": False, "n5_exit_gate_satisfied": False,
        "current_candidate_full_gate_passed": False, "production_ready": False,
    }
    gate["current_closeout_regression"] = {
        "cycle": 184, "status": "pass", "scope": "boot_chain_host_profile_and_aggregate_gate_tests_only",
        "tests_run": 109, "tests_passed": 109, "tests_failed": 0, "tests_skipped": 0,
        "hostile_environment": True,
        "log_sha256": "A2F46811D85AC57D35BDE1641F295116046CF3BA1AABAF039EEE1899793149FE",
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
        "initial_metadata_closeout": {
            "status": "fail", "tests_run": 46, "tests_passed": 43, "tests_failed": 3,
            "reason": "roadmap_cycle_move_and_architecture_binding_count_schema_pins_not_yet_updated",
            "log_sha256": "34C875F50562F0A2D1ADB89420BC9056DD859091AFD40FD5FDE455ADB26B4C68",
        },
        "repaired_metadata_closeout": {
            "status": "pass", "tests_run": 46, "tests_passed": 46, "tests_failed": 0,
            "log_sha256": "C2C7DD3732334E8CF83DC0B8FE11F00950490C8A02B56F0705E02D657E2195F5",
        },
        "combined_regression": {
            "scope": "boot_host_profile_progress_checklist_and_core_not_full_canonical",
            "status": "pass", "tests_run": 171, "tests_passed": 171, "tests_skipped": 0,
            "log_sha256": "D4A090A04863193E760C720A550B11564AEB54DC75B034EEFC8087BA43926BE5",
        },
    }
    evidence = (
        "Cycle 184: " + checkpoint + " pins six host qualifiers and admits eight actual generated "
        "boot-chain/prerequisite receipts. Six final headless boots include two kernel entries; "
        "109 focused Python tests pass. Typed host evidence, source bindings, invalid-output preservation, "
        "exact schema counts and twelve forged PooleBoot host-test-count rejections are verified. "
        "Repeated roadmap generation no longer mutates earlier results. Kernel bytes are unchanged."
    )
    gap = (
        "Selected readiness is 8/27, with nineteen CPU/memory checks pending from N7-TRAP-001. "
        "At least 65 scheduler controls still need individually bound rejection execution before "
        "full exact-candidate canonical/Doctor/publication/review qualification and PR78 merge. "
        "Thirteen failed runner attempts, including the first metadata closeout, and eight "
        "superseded successful boots remain preserved. "
        "No complete host attestation, independent builder, phase/flag closure, new native feature, "
        "new ISO or production readiness is claimed."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N3", "N5", "N6", "N12", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 184 source inventory: 994 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N36-RECEIPT-COVERAGE-001", "FLAG-N5-SYMBOL-BUNDLE-001",
                          "FLAG-N5-FIRMWARE-BUNDLE-001", "FLAG-N5-POLICY-BUNDLE-001",
                          "FLAG-N5-INNER-KERNEL-REVALIDATE-001", "FLAG-N5-KERNEL-TRANSFER-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"] = list(roadmap["gap_summary"]["native_program_gaps"])
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle185(roadmap, test_count)

def apply_cycle185(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle185-cpu-recorded-evidence.md"
    protocol = roadmap["execution_protocol"]
    protocol.update(last_updated_cycle=185, selected_move_id="N7-TRAP-001",
                    owner_independent_next_move_id="N9-PMM-ACPI-CONSUMER-001")
    protocol["required_records"][0:0] = [checkpoint, "docs/checkpoints/cycle185-unfinished-cloud-backup.md"]
    roadmap["baseline"]["pooleos_cycle"] = 185
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for name in (
        "focused_source_projection", "ownership_qualification", "entry_provenance_qualification",
        "boot_chain_qualification", "cpu_qualification", "dependency_qualification",
        "closeout_regression", "candidate_audit", "host_toolchain_qualification", "shared_loader_qualification",
    ):
        suffix = "source_projection" if name == "focused_source_projection" else name
        gate["historical_cycle184_" + suffix] = copy.deepcopy(gate["current_" + name])
    gate["qualification_status"] = "cpu_recorded_evidence_repaired_memory_and_control_replay_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=185)
    gate["current_focused_source_projection"] = dict(
        gate["current_focused_source_projection"], cycle=185, passed_checks=13,
        pending_downstream_native_checks=14, final_receipt_fresh_qemu_runs=14,
        kernel_entry_runs=14, superseded_initial_qemu_runs=6,
        run_count_scope="current_cycle_CPU_profiles_only_prior_boot_qualification_retained_separately",
        passing_profiles=["native_kernel_entry_readiness","native_symbol_readiness","native_policy_readiness","native_kernel_load_readiness","native_pooleboot_readiness","native_kernel_revalidation_readiness","native_kernel_transfer_readiness","native_kernel_trap_readiness","native_kernel_cpu_policy_readiness","native_kernel_errata_policy_readiness","native_kernel_xstate_policy_readiness","native_kernel_xstate_exception_readiness","native_kernel_privilege_msr_policy_readiness"],
        next_dependency_move_id="N9-PMM-ACPI-CONSUMER-001",
        required_next_gate="ordered_memory_replay_then_control_execution_audit_and_exact_full_qualification",
        focused_python_tests_passed=50, focused_python_tests_skipped=0,
        focused_test_log_sha256="491896009188DD96F1986886CD1D8BCE9DA9BC1874F42F3A22DAD69F6A0056E1",
        recorded_exit_rejections=98, recorded_coverage_rejections=112, recorded_evidence_rejections=161,
        expected_tcg_limitation_probes=1, whpx_exception_runs=2,
    )
    for name in ("entry_provenance", "shared_loader", "boot_chain"):
        gate["current_" + name + "_qualification"] = dict(
            gate["current_" + name + "_qualification"], source_validation_cycle=185,
        )
    gate["current_ownership_qualification"] = dict(gate["current_ownership_qualification"], cycle=185)
    gate["current_dependency_qualification"] = {
        "cycle": 185, "source_validation_cycle": 185,
        "status": "replay_required_after_entry_boot_and_CPU_recorded_evidence_repair",
        "applies_to_current_source": False, "qualified_profiles": [], "fresh_qemu_runs": 0,
        "historical_record": "historical_cycle184_dependency_qualification",
        "current_candidate_full_gate_passed": False, "production_ready": False,
    }
    bindings = [
            {
                    "profile": "trap",
                    "path": "runs/native-kernel-trap-readiness.json",
                    "sha256": "3FE6CEDF9A96978A22C5B422D57E584BE05D0EA948B787EB80DABA7F5F7B7391",
                    "fresh_runs": 6,
                    "negative_controls": 51,
                    "kernel_host_tests": 245,
                    "execution_log_sha256": "7E2F449373D9AC8C54B86D0CCC94BB7962EFED183681CAEBD68BF0C6D3DFB4AC",
                    "elapsed_seconds": 168.078
            },
            {
                    "profile": "cpu_policy",
                    "path": "runs/native-kernel-cpu-policy-readiness.json",
                    "sha256": "7AE0D57D223A1C01A389303767F255B5FF45A77EFDB22A19A32EDE7A52BB1ECE",
                    "fresh_runs": 2,
                    "negative_controls": 41,
                    "kernel_host_tests": 245,
                    "execution_log_sha256": "CFA41675A79CE67949D1FDB8D08F791EB2FD1115237010D33465135306D1CE23",
                    "elapsed_seconds": 66.984
            },
            {
                    "profile": "xstate_policy",
                    "path": "runs/native-kernel-xstate-policy-readiness.json",
                    "sha256": "B6C8EA6AFE80F11A98597CBA5EF47837E29E5B48B0CAAA97C8A05C8E8535F06B",
                    "fresh_runs": 2,
                    "negative_controls": 43,
                    "kernel_host_tests": 245,
                    "execution_log_sha256": "4260145CE808D54618100843E5797A22DAFA156F94093C1D222D6D99730A162A",
                    "elapsed_seconds": 89.672
            },
            {
                    "profile": "xstate_exception",
                    "path": "runs/native-kernel-xstate-exception-readiness.json",
                    "sha256": "C0A4808E2D6150CEC87FBCD4DF1F4C66CC0F112D1B332269739C742B54211B7A",
                    "fresh_runs": 2,
                    "negative_controls": 43,
                    "kernel_host_tests": 245,
                    "execution_log_sha256": "F3ED8801D7E59F458EBE9E20B63EED505D5DEF7034E3E58654DA297E074BF60D",
                    "elapsed_seconds": 81.375
            },
            {
                    "profile": "privilege_msr_policy",
                    "path": "runs/native-kernel-privilege-msr-policy-readiness.json",
                    "sha256": "CE291CC5C0679FEA1F88A85F10E913EF10F2C9A0820AFC98B82E0D543C648261",
                    "fresh_runs": 2,
                    "negative_controls": 47,
                    "kernel_host_tests": 245,
                    "execution_log_sha256": "9B9A31059D4151F9B9A62622272025F3EDB8EEF33A8C29EEA6267DBE5A72AE32",
                    "elapsed_seconds": 76.953
            }
    ]
    gate["current_cpu_qualification"] = dict(
        gate["historical_cycle181_cpu_qualification"], cycle=185, source_validation_cycle=185,
        status="single_host_cpu_replay_pass", applies_to_current_source=True,
        scope="five_N7_profiles_with_typed_recorded_pairs_and_genuine_positive_receipts",
        qualified_profiles=[b["profile"] for b in bindings], receipt_bindings=bindings,
        fresh_qemu_runs=14, superseded_initial_runs=6, negative_control_groups=225,
        focused_python_tests=50, aggregate_gate_regression_cases=19,
        recorded_exit_rejection_cases=98, recorded_coverage_rejection_cases=112,
        recorded_evidence_rejection_cases=161, recorded_evidence_total_rejection_cases=371,
        recorded_pair_count=7, malformed_gate_exception_repairs=2,
        recorded_evidence_rejections_exercised_through_runtime_and_gate=True,
        positive_receipts_rebound_in_tests=False,
        pre_repair_exit_counterexample={
            "cases": 42, "runtime_accepted": 42, "aggregate_gate_accepted": 42,
            "record_sha256": "D91F76C6BFEF4DE91C08487438C1359974E2E367E8F2EA20B814F0FC642FE62C",
        },
        pair_validation_is_freshness_or_authentication=False,
    )
    gate["current_closeout_regression"] = {
        "cycle": 185, "status": "pass", "scope": "five_CPU_profiles_errata_provenance_and_actual_CPU_gate_only",
        "tests_run": 50, "tests_passed": 50, "tests_failed": 0, "tests_skipped": 0,
        "hostile_environment": True,
        "log_sha256": "491896009188DD96F1986886CD1D8BCE9DA9BC1874F42F3A22DAD69F6A0056E1",
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
        "initial_pair_test": {
            "status": "fail", "tests_run": 1, "tests_failed": 1,
            "reason": "test_assumed_a_top_level_marker_count_in_every_profile_summary",
            "log_sha256": "D26EE94F9838852AD488BC3DA409B2014249464E8D2DAF739FD684104A86B41F",
        },
        "repaired_pair_test": {
            "status": "pass", "tests_run": 1, "tests_passed": 1,
            "log_sha256": "B598DA5C0C4F540771E1E8C92E7FA1D333CFF33B0361E344CF93AB7338692210",
        },
        "malformed_preflight": {
            "scope": "exception_detection_on_stale_receipts_not_rejection_proof",
            "initial_gate_exceptions": 2, "repaired_gate_exceptions": 0, "cases": 371,
        },
        "initial_combined_closeout": {
            "status": "fail", "tests_run": 221, "tests_passed": 219, "tests_failed": 2,
            "reason": "two_current_projection_assertions_still_expected_historical_8_passes_and_19_pending",
            "log_sha256": "220F9D3CF13F69C7B75B3AECA4CCAD645DDD32D217C2B06628ABADEF22C762B2",
        },
        "combined_regression": {
            "scope": "CPU_boot_host_progress_checklist_and_core_not_full_canonical",
            "status": "pass", "tests_run": 221, "tests_passed": 221, "tests_skipped": 0,
            "log_sha256": "E9EDE7E18D007ED2E2FEA18A0396CD4EBA3FD91DA3927D07285071E609E2C488",
        },
    }
    evidence = (
        "Cycle 185: " + checkpoint + " repairs typed recorded execution across five CPU profiles. "
        "Fourteen final virtual boots and 225 marker controls pass on unchanged kernel bytes. "
        "All 50 focused tests pass, including 98 exit, 112 run-coverage and 161 record-evidence "
        "mutations through both the runtime validators and actual release gates. Two malformed "
        "CPU gate exceptions are repaired. Genuine generated positive receipts are never rebound."
    )
    gap = (
        "Selected readiness is 13/27; fourteen memory-through-lock profiles need replay beginning "
        "N9-PMM-ACPI-CONSUMER-001. At least 65 scheduler controls still lack individually bound "
        "rejection execution before full exact-candidate canonical/Doctor/publication/review and "
        "PR78 merge. The 42 accepted pre-repair exit counterexamples, initial test error, two "
        "gate exceptions and six superseded initial trap boots remain preserved. Recorded "
        "consistency is not freshness or authentication. No phase/flag closure, independent "
        "builder, target hardware, new kernel feature, new ISO or production readiness is claimed."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N3", "N7", "N12", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 185 source inventory: 998 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {
            "FLAG-N7-TRAP-001", "FLAG-N7-CPU-POLICY-001", "FLAG-N7-XSTATE-POLICY-001",
            "FLAG-N7-XSTATE-EXCEPTION-001", "FLAG-N7-PRIVILEGE-MSR-POLICY-001",
            "FLAG-N12-CONCURRENCY-RECLAMATION-001", "FLAG-N36-RECEIPT-COVERAGE-001",
        }:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"] = list(roadmap["gap_summary"]["native_program_gaps"])
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle186(roadmap, test_count)


def apply_cycle186(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle186-pmm-recorded-evidence.md"
    roadmap["baseline"]["pooleos_cycle"] = 186
    protocol = roadmap["execution_protocol"]
    protocol.update(last_updated_cycle=186, selected_move_id="N9-PMM-ACPI-CONSUMER-001",
                    owner_independent_next_move_id="N9-VM-DIRECT-MAP-001")
    protocol["required_records"].insert(0, checkpoint)
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for name in ("focused_source_projection", "dependency_qualification", "closeout_regression", "candidate_audit"):
        suffix = "source_projection" if name == "focused_source_projection" else name
        gate["historical_cycle185_" + suffix] = copy.deepcopy(gate["current_" + name])
    gate["qualification_status"] = "pmm_recorded_evidence_repaired_thirteen_dependencies_and_control_audit_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=186)
    gate["current_focused_source_projection"] = {
        "cycle": 186, "scope": "27_selected_native_checks_not_full_canonical_audit",
        "passed_checks": 14, "total_checks": 27, "pending_downstream_native_checks": 13,
        "passing_profiles": [*gate["historical_cycle185_source_projection"]["passing_profiles"],
                             "native_kernel_physical_memory_readiness"],
        "final_receipt_fresh_qemu_runs": 2, "kernel_entry_runs": 2, "superseded_initial_qemu_runs": 2,
        "run_count_scope": "current_cycle_PMM_only_prior_boot_and_CPU_qualification_retained_separately",
        "next_dependency_move_id": "N9-VM-DIRECT-MAP-001",
        "required_next_gate": "ordered_remaining_dependency_replay_then_control_audit_and_exact_full_qualification",
        "focused_python_tests_passed": 12, "focused_python_tests_skipped": 0,
        "focused_test_log_sha256": "C1FE871A6BD5AD1BA4A1EE34485EEAF4BAEB42FBB234B081560BAB2E7B43314C",
        "recorded_evidence_rejection_cases": 234,
        "canonical_full_replay_performed": False, "production_ready": False,
    }
    gate["current_dependency_qualification"] = {
        "cycle": 186, "source_validation_cycle": 186, "status": "PMM_pass_thirteen_profiles_pending",
        "scope": "physical_memory_only", "applies_to_current_source": True,
        "all_fourteen_profiles_current": False, "qualified_profiles": ["physical_memory"],
        "readiness_replay_required_profiles": ["virtual_memory", "interrupt_time", "smp_first_ap",
            "smp_percpu_runtime", "smp_ipi", "scheduler", "scheduler_preempt", "scheduler_deferred",
            "scheduler_smp", "scheduler_ap_workers", "scheduler_smp_preempt", "atomics", "locks"],
        "fresh_qemu_runs": 2, "superseded_initial_runs": 2, "negative_control_groups": 191,
        "kernel_sha256": "563ED1976CAB4DA773BAE9BCE49F370242C893760E7C221239C1B31F44D969CA",
        "receipt_bindings": [{"profile": "physical_memory", "path": "runs/native-kernel-physical-memory-readiness.json",
            "sha256": "3FD215CB703F8DF55A8EAB4D5716EF9466F33384A89F805FCF704DE395BF8F16",
            "fresh_runs": 2, "negative_controls": 191, "kernel_host_tests": 245,
            "execution_log_sha256": "73D78CC992A80B448CB62D488AC4EFA73BF8EED5DBCA5B8F76C37B5AF855061A",
            "elapsed_seconds": 86.641}],
        "recorded_evidence_cases": {"exit": 14, "coverage": 16, "evidence": 29, "accounting": 7, "summary": 168},
        "recorded_evidence_case_total": 234,
        "recorded_evidence_rejections_exercised_through_runtime_and_gate": True,
        "pre_repair_counterexample": {"cases": 65, "runtime_accepted": 62, "aggregate_gate_accepted": 61,
            "record_sha256": "93AA3A4D8930107C92E32F16938C56222831EF5BD8F800F888A323A5F5F56651"},
        "initial_receipt_sha256": "42F0575EC9893B58A5586EC4839D8A52C887E1022DA6C1EC963AF4F015906D51",
        "historical_PMM_receipt_sha256": "EEFD0E8592CB98E8D0EDBCB480FFD6DDEF761C5432AE0ED4FB3C95C73E10D008",
        "positive_receipts_rebound_in_tests": False, "pair_validation_is_freshness_or_authentication": False,
        "control_execution_complete": False, "unproven_per_control_rejection_groups_at_least": 65,
        "current_candidate_full_gate_passed": False, "production_ready": False,
    }
    gate["current_closeout_regression"] = {
        "cycle": 186, "status": "pass", "scope": "physical_memory_accounting_and_recorded_evidence_only",
        "tests_run": 12, "tests_passed": 12, "tests_failed": 0, "tests_skipped": 0,
        "hostile_environment": True,
        "log_sha256": "C1FE871A6BD5AD1BA4A1EE34485EEAF4BAEB42FBB234B081560BAB2E7B43314C",
        "qualifier_output_preservation_cases": 2,
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
        "initial_combined_closeout": {
            "status": "fail", "tests_run": 234, "tests_passed": 233, "tests_failed": 1,
            "reason": "historical_CPU_closeout_assertion_selected_current_PMM_closeout",
            "log_sha256": "67427264FF6C15911AE0174A1542CA9CD3E5E617D1F3FDB1371E9EE9C58E139F",
        },
        "initial_conservation_audit": {
            "status": "fail", "reason": "private_audit_empty_historical_list_suffix_bug",
            "history_removed": False,
        },
        "combined_regression": {
            "status": "pass", "scope": "PMM_CPU_boot_host_progress_checklist_and_core_not_full_canonical",
            "tests_run": 234, "tests_passed": 234, "tests_skipped": 0,
            "log_sha256": "C6517C55F2D73B6B03D6EA8BE688F17F8966AEA05568853164B8E787EC322B87",
        },
        "original_counterexample_replay": {
            "cases": 65, "runtime_accepted": 0, "aggregate_gate_accepted": 0,
            "genuine_positive_runtime_and_gate_pass": True,
        },
    }
    evidence = (
        "Cycle 186: " + checkpoint + " repairs PMM recorded execution and independently rederives "
        "ACPI/PMM accounting from both PBP1 handoffs. Two fresh virtual boots and 191 marker controls "
        "pass on unchanged kernel bytes; 12 focused tests pass, including 234 malformed records "
        "through runtime and actual gate plus two rejected-output preservation cases. "
        "Positive source-qualified receipts are genuinely generated, never rebound."
    )
    gap = (
        "Selected readiness is 14/27; thirteen memory-through-lock profiles need replay from "
        "N9-VM-DIRECT-MAP-001. At least 65 scheduler controls still require individually bound "
        "rejection execution and full exact-candidate canonical/Doctor/publication/review before "
        "PR78 merge. The original 65 mutation cases, 62 runtime and 61 gate admissions, and two "
        "superseded initial boots remain preserved. Recorded consistency is not authentication "
        "or freshness. No phase/flag, target hardware, independent builder, kernel feature, ISO "
        "or production gate closes."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N9", "N10", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 186 source inventory: 1002 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N9-PMM-ACPI-CONSUMER-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"] = list(roadmap["gap_summary"]["native_program_gaps"])
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle187(roadmap, test_count)


def apply_cycle187(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle187-vm-recorded-evidence.md"
    roadmap["baseline"]["pooleos_cycle"] = 187
    protocol = roadmap["execution_protocol"]
    protocol.update(last_updated_cycle=187, selected_move_id="N9-VM-DIRECT-MAP-001",
                    owner_independent_next_move_id="N8-IRQ-001")
    protocol["required_records"].insert(0, checkpoint)
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for name in ("focused_source_projection", "dependency_qualification", "closeout_regression", "candidate_audit"):
        suffix = "source_projection" if name == "focused_source_projection" else name
        gate["historical_cycle186_" + suffix] = copy.deepcopy(gate["current_" + name])
    gate["qualification_status"] = "VM_recorded_evidence_repaired_twelve_dependencies_and_control_audit_pending"
    gate["historical_cycle186_ownership_qualification"] = copy.deepcopy(gate["current_ownership_qualification"])
    gate["current_ownership_qualification"] = dict(
        gate["current_ownership_qualification"], cycle=187,
        scope="retained_host177_VM187_pass_AP_replay_pending", fresh_current_cycle_qemu_runs=2,
        virtual_memory_live_replay_cycle=187, virtual_memory_live_receipt_source_current=True,
        active_root_current_image_replay_complete=True,
        live_receipt_source_current=False, current_boot_artifact_set_replay_pending=True,
        ap_runtime_live_integration_verified=False,
        live_receipt_scope="two_current_VM_runs_AP_profile_replay_pending",
        source_current_scope="VM187_declared_inputs_only_AP_receipt181_stale",
        entry_receipt_sha256="ACAEC303FA750DD75CA8B721B0BD359E4291CF1C4218B3DDFBFE09AF17390B65",
        virtual_memory_receipt_sha256="F2CC0C55F09600DE728D2BDAB1F26855EF7BE624AF9F6B1D00B4F16D9418A1FC",
    )
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=187)
    gate["current_focused_source_projection"] = {
        "cycle": 187, "scope": "27_selected_native_checks_not_full_canonical_audit",
        "passed_checks": 15, "total_checks": 27, "pending_downstream_native_checks": 12,
        "passing_profiles": [*gate["historical_cycle186_source_projection"]["passing_profiles"],
                             "native_kernel_virtual_memory_readiness"],
        "final_receipt_fresh_qemu_runs": 2, "kernel_entry_runs": 2, "superseded_initial_qemu_runs": 2,
        "run_count_scope": "current_cycle_VM_only_prior_PMM_CPU_and_boot_qualification_retained_separately",
        "next_dependency_move_id": "N8-IRQ-001",
        "required_next_gate": "ordered_remaining_dependency_replay_then_control_audit_and_exact_full_qualification",
        "focused_python_tests_passed": 10, "focused_python_tests_skipped": 0,
        "focused_test_log_sha256": "03B75B553C37E1B8F472D2F700A16775DBA8CF512CB80835F2C83896876FC32A",
        "recorded_evidence_rejection_cases": 115,
        "canonical_full_replay_performed": False, "production_ready": False,
    }
    prior = gate["historical_cycle186_dependency_qualification"]
    gate["current_dependency_qualification"] = {
        "cycle": 187, "source_validation_cycle": 187, "status": "PMM_and_VM_pass_twelve_profiles_pending",
        "scope": "physical_memory_and_virtual_memory_only", "applies_to_current_source": True,
        "all_fourteen_profiles_current": False, "qualified_profiles": ["physical_memory", "virtual_memory"],
        "newly_qualified_profiles": ["virtual_memory"],
        "readiness_replay_required_profiles": prior["readiness_replay_required_profiles"][1:],
        "fresh_qemu_runs": 2, "run_count_scope": "current_cycle_VM_only",
        "superseded_initial_runs": 2, "negative_control_groups": 48,
        "kernel_sha256": prior["kernel_sha256"],
        "receipt_bindings": [*copy.deepcopy(prior["receipt_bindings"]), {
            "profile": "virtual_memory", "path": "runs/native-kernel-virtual-memory-readiness.json",
            "sha256": "F2CC0C55F09600DE728D2BDAB1F26855EF7BE624AF9F6B1D00B4F16D9418A1FC",
            "fresh_runs": 2, "negative_controls": 48, "kernel_host_tests": 245,
            "execution_log_sha256": "3F150DB57A3859B6474CCAE0679F8D501C0B6264436950A77C7EDC5EE719DE52",
            "elapsed_seconds": 72.359}],
        "prior_PMM_qualification_record": "historical_cycle186_dependency_qualification",
        "recorded_evidence_cases": {"exit": 14, "coverage": 16, "evidence": 28, "accounting": 7, "summary": 50},
        "recorded_evidence_case_total": 115,
        "recorded_evidence_rejections_exercised_through_runtime_and_gate": True,
        "pre_repair_counterexample": {"cases": 65, "runtime_accepted": 46, "aggregate_gate_accepted": 45,
            "record_sha256": "EFF8C3152C0878F32B6E9A37F10563F9442E717A85C5518E9346C29C1FC17579"},
        "initial_receipt_sha256": "5CEEE0A862C985CC314ECA7AA229A1C2669B5460E8D90FF6B704AF5934623FB1",
        "historical_VM_receipt_sha256": "4AFEA30E25DB4DCD0D9038E01D3FE1CC6EE5D82DBAB4595A4631D34902460BB7",
        "positive_receipts_rebound_in_tests": False, "pair_validation_is_freshness_or_authentication": False,
        "control_execution_complete": False, "unproven_per_control_rejection_groups_at_least": 65,
        "current_candidate_full_gate_passed": False, "production_ready": False,
    }
    gate["current_closeout_regression"] = {
        "cycle": 187, "status": "pass", "scope": "virtual_memory_accounting_and_recorded_evidence_only",
        "tests_run": 10, "tests_passed": 10, "tests_failed": 0, "tests_skipped": 0,
        "hostile_environment": True,
        "log_sha256": "03B75B553C37E1B8F472D2F700A16775DBA8CF512CB80835F2C83896876FC32A",
        "qualifier_output_preservation_cases": 2,
        "original_counterexample_replay": {"cases": 65, "runtime_accepted": 0, "aggregate_gate_accepted": 0,
            "genuine_positive_runtime_and_gate_pass": True},
        "initial_combined_closeout": {
            "status": "fail", "tests_run": 245, "tests_passed": 244, "tests_failed": 1,
            "reason": "historical_VM181_hash_compared_with_current_VM187_receipt",
            "log_sha256": "0DAD750AFEF0A44C901ED6033E80194D75F052F7ACE078E3DB12FD91DD8202F4",
        },
        "combined_regression": {
            "status": "pass", "scope": "VM_PMM_CPU_boot_host_progress_checklist_and_core_not_full_canonical",
            "tests_run": 261, "tests_passed": 261, "tests_skipped": 0,
            "distinct_test_methods": 245, "repeated_test_executions": 16,
            "repeated_module": "tests.test_native_host_toolchain",
            "log_sha256": "8E01E333BBBEECF3C3FC578DE0D149BCDA4C0B8516A43E383924C2C9D8646FE1",
        },
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 187: " + checkpoint + " repairs strict VM recorded execution, independently "
        "rederived direct-map accounting and typed summaries. Two final virtual boots and 48 "
        "marker controls pass on unchanged kernel bytes. All 10 focused tests pass, including "
        "115 corruptions through runtime and actual gate and two output-preservation cases. "
        "The original 65 counterexamples now reject; genuine positive receipts are never rebound."
    )
    gap = (
        "Selected readiness is 15/27; twelve interrupt/time-through-lock profiles remain from "
        "N8-IRQ-001. At least 65 scheduler controls still require individually bound rejection "
        "execution and full exact-candidate canonical/Doctor/publication/review before PR78 "
        "merge. The original 46 runtime and 45 gate admissions and two superseded initial boots "
        "remain preserved. Recorded consistency is not freshness or authentication. No phase, "
        "flag, native kernel feature, target hardware, independent builder, ISO or production "
        "gate closes."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N9", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 187 source inventory: 1006 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N9-VM-DIRECT-MAP-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"] = list(roadmap["gap_summary"]["native_program_gaps"])
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle188(roadmap, test_count)


def apply_cycle188(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle188-irq-recorded-evidence.md"
    roadmap["baseline"]["pooleos_cycle"] = 188
    protocol = roadmap["execution_protocol"]
    protocol.update(last_updated_cycle=188, selected_move_id="N8-IRQ-001",
                    owner_independent_next_move_id="N8-SMP-FIRST-AP-001")
    protocol["required_records"].insert(0, checkpoint)
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for name in ("focused_source_projection", "dependency_qualification", "closeout_regression", "candidate_audit"):
        suffix = "source_projection" if name == "focused_source_projection" else name
        gate["historical_cycle187_" + suffix] = copy.deepcopy(gate["current_" + name])
    gate["qualification_status"] = "IRQ_recorded_evidence_repaired_eleven_dependencies_and_control_audit_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=188)
    gate["current_focused_source_projection"] = {
        "cycle": 188, "scope": "27_selected_native_checks_not_full_canonical_audit",
        "passed_checks": 16, "total_checks": 27, "pending_downstream_native_checks": 11,
        "passing_profiles": [*gate["historical_cycle187_source_projection"]["passing_profiles"],
                             "native_kernel_interrupt_time_readiness"],
        "final_receipt_fresh_qemu_runs": 2, "kernel_entry_runs": 2, "superseded_initial_qemu_runs": 2,
        "run_count_scope": "current_cycle_IRQ_only_prior_VM_PMM_CPU_and_boot_qualification_retained_separately",
        "next_dependency_move_id": "N8-SMP-FIRST-AP-001",
        "required_next_gate": "ordered_remaining_dependency_replay_then_control_audit_and_exact_full_qualification",
        "focused_python_tests_passed": 12, "focused_python_tests_skipped": 0,
        "focused_test_log_sha256": "8477E89A8F5030CE86DB3659E0C22E57E74AC1E7BDDBEB48D48F86C3F0D3F3A7",
        "recorded_evidence_rejection_cases": 229, "malformed_root_and_control_cases": 6,
        "canonical_full_replay_performed": False, "production_ready": False,
    }
    prior = gate["historical_cycle187_dependency_qualification"]
    gate["current_dependency_qualification"] = {
        "cycle": 188, "source_validation_cycle": 188, "status": "PMM_VM_IRQ_pass_eleven_profiles_pending",
        "scope": "physical_memory_virtual_memory_and_interrupt_time_only", "applies_to_current_source": True,
        "all_fourteen_profiles_current": False,
        "qualified_profiles": [*prior["qualified_profiles"], "interrupt_time"],
        "newly_qualified_profiles": ["interrupt_time"],
        "readiness_replay_required_profiles": prior["readiness_replay_required_profiles"][1:],
        "fresh_qemu_runs": 2, "run_count_scope": "current_cycle_IRQ_only",
        "superseded_initial_runs": 2, "negative_control_groups": 58,
        "kernel_sha256": prior["kernel_sha256"],
        "receipt_bindings": [*copy.deepcopy(prior["receipt_bindings"]), {
            "profile": "interrupt_time", "path": "runs/native-kernel-interrupt-time-readiness.json",
            "sha256": "A8812EE8F48CBA157554EB3264EA945082641014D9E2FE1C7A3982D648FF046B",
            "fresh_runs": 2, "negative_controls": 58, "kernel_host_tests": 245,
            "execution_log_sha256": "98DE2D5B7B345ED29CFDA5E1BBE0160126A332F0E4319B4AF91FCE66567C4606",
            "elapsed_seconds": 78.312}],
        "prior_memory_qualification_record": "historical_cycle187_dependency_qualification",
        "recorded_evidence_cases": {"exit": 14, "coverage": 16, "evidence": 23, "shape": 3,
                                    "observation": 145, "summary": 22, "clock": 6},
        "recorded_evidence_case_total": 229, "malformed_root_and_control_cases": 6,
        "recorded_evidence_rejections_exercised_through_runtime_and_gate": True,
        "pre_repair_counterexample": {"cases": 64, "runtime_accepted": 52, "aggregate_gate_accepted": 44,
            "runtime_exceptions": 1, "aggregate_gate_exceptions": 4,
            "zero_sample_direct_parser": "ZeroDivisionError",
            "record_sha256": "011B519EB45330A2E04E3C7CCCBF237127A0AEA1D74E895E5209223203515329"},
        "initial_receipt_sha256": "6AD05F1D92CB328088D56DD064F4D011D818D85FDD15153DF1314F2B7B939076",
        "historical_IRQ_receipt_sha256": "19FB9DA0B525064D56126E9EEE159C887A46B4FD1EB6B6DA3646C5F88182E7B2",
        "positive_receipts_rebound_in_tests": False, "pair_validation_is_freshness_or_authentication": False,
        "control_execution_complete": False, "unproven_per_control_rejection_groups_at_least": 65,
        "current_candidate_full_gate_passed": False, "production_ready": False,
    }
    gate["current_closeout_regression"] = {
        "cycle": 188, "status": "pass", "scope": "IRQ_recorded_evidence_and_clock_calibration_only",
        "tests_run": 12, "tests_passed": 12, "tests_failed": 0, "tests_skipped": 0,
        "hostile_environment": True,
        "log_sha256": "8477E89A8F5030CE86DB3659E0C22E57E74AC1E7BDDBEB48D48F86C3F0D3F3A7",
        "qualifier_output_preservation_cases": 2, "direct_clock_boundary_rejections": 6,
        "original_counterexample_replay": {"cases": 64, "runtime_accepted": 0, "aggregate_gate_accepted": 0,
            "runtime_exceptions": 0, "aggregate_gate_exceptions": 0,
            "genuine_positive_runtime_and_gate_pass": True,
            "record_sha256": "D06DA52166453BD9E72604ABFF7A6C860D530A64AEB1A7C1CB155817E13350AD"},
        "combined_regression": {
            "status": "pass", "scope": "IRQ_VM_PMM_CPU_boot_host_progress_checklist_and_core_not_full_canonical",
            "tests_run": 258, "tests_passed": 258, "tests_skipped": 0,
            "log_sha256": "E7C1BEF95B382EE94A18126281845A2750A43521B8BCFCB17190A1CF68F21810",
        },
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 188: " + checkpoint + " repairs IRQ recorded execution, typed aggregate observations "
        "and summaries, fail-closed malformed input and checked calibration before frequency arithmetic. "
        "Two final boots, 58 executed controls and 12 focused tests pass on unchanged kernel bytes, "
        "including 229 recorded mutations, six malformed root/control cases and two output-preservation "
        "cases. All 64 original audit cases now reject without validator exceptions."
    )
    gap = (
        "Selected readiness is 16/27; eleven SMP-through-lock profiles remain from N8-SMP-FIRST-AP-001. "
        "At least 65 scheduler controls still need individually bound rejection execution before exact "
        "full canonical/Doctor/publication/configured-check/review qualification and PR78 merge. "
        "The prior 52 runtime and 44 gate admissions, one runtime and four gate exceptions, direct "
        "zero-sample division failure and two superseded initial boots remain preserved. Recorded "
        "consistency is not freshness or authentication; no phase, flag, kernel feature, hardware, "
        "independent builder, ISO or production gate closes."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N8", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 188 source inventory: 1011 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N8-IRQ-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"] = list(roadmap["gap_summary"]["native_program_gaps"])
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle189(roadmap, test_count)


def apply_cycle189(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle189-first-ap-recorded-evidence.md"
    roadmap["baseline"]["pooleos_cycle"] = 189
    protocol = roadmap["execution_protocol"]
    protocol.update(last_updated_cycle=189, selected_move_id="N8-SMP-FIRST-AP-001",
                    owner_independent_next_move_id="N8-SMP-PERCPU-RUNTIME-001")
    protocol["required_records"].insert(0, checkpoint)
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for name in ("focused_source_projection", "dependency_qualification", "closeout_regression", "candidate_audit"):
        suffix = "source_projection" if name == "focused_source_projection" else name
        gate["historical_cycle188_" + suffix] = copy.deepcopy(gate["current_" + name])
    gate["qualification_status"] = "first_AP_recorded_evidence_repaired_ten_dependencies_and_control_audit_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=189)
    gate["current_focused_source_projection"] = dict(
        copy.deepcopy(gate["historical_cycle188_source_projection"]),
        cycle=189, passed_checks=17, pending_downstream_native_checks=10,
        passing_profiles=[*gate["historical_cycle188_source_projection"]["passing_profiles"],
                          "native_kernel_smp_first_ap_readiness"],
        run_count_scope="current_cycle_first_AP_only_prior_qualification_retained_separately",
        next_dependency_move_id="N8-SMP-PERCPU-RUNTIME-001",
        focused_test_log_sha256="9D496774589156953AB92E2112CC5D1D73620B1A7F4DCAD3E007CA89F507B999",
        recorded_evidence_rejection_cases=159,
    )
    prior = gate["historical_cycle188_dependency_qualification"]
    gate["current_dependency_qualification"] = {
        "cycle": 189, "source_validation_cycle": 189, "status": "PMM_VM_IRQ_first_AP_pass_ten_profiles_pending",
        "scope": "physical_memory_virtual_memory_interrupt_time_first_AP_only", "applies_to_current_source": True,
        "all_fourteen_profiles_current": False,
        "qualified_profiles": [*prior["qualified_profiles"], "smp_first_ap"],
        "newly_qualified_profiles": ["smp_first_ap"],
        "readiness_replay_required_profiles": prior["readiness_replay_required_profiles"][1:],
        "fresh_qemu_runs": 2, "run_count_scope": "current_cycle_first_AP_only",
        "superseded_initial_runs": 2, "negative_control_groups": 72, "kernel_sha256": prior["kernel_sha256"],
        "receipt_bindings": [*copy.deepcopy(prior["receipt_bindings"]), {
            "profile": "smp_first_ap", "path": "runs/native-kernel-smp-first-ap-readiness.json",
            "sha256": "5777FF2F8C1FC296FF4C4C1CB2233B4674DF5B1BBA15C9A7F06300DD25946841",
            "fresh_runs": 2, "negative_controls": 72, "kernel_host_tests": 245,
            "execution_log_sha256": "D2823B8479F27386573962DB57FA0DC7211F656CDEC4BDF03C890911B24C5242",
            "elapsed_seconds": 72.75}],
        "prior_qualification_record": "historical_cycle188_dependency_qualification",
        "recorded_evidence_cases": {"exit": 14, "coverage": 16, "evidence": 23, "shape": 3,
            "dynamic-policy": 2, "observation": 69, "summary": 30, "raw-stop": 2},
        "recorded_evidence_case_total": 159, "malformed_root_and_control_cases": 6,
        "recorded_evidence_rejections_exercised_through_runtime_and_gate": True,
        "pre_repair_counterexample": {"cases": 67, "runtime_accepted": 55, "aggregate_gate_accepted": 46,
            "runtime_exceptions": 1, "aggregate_gate_exceptions": 4,
            "record_sha256": "5E3DD35914AB8A5B32DB6EB1D62898948F5C7FAAC7651EA97AFB5FBB935A3C90"},
        "initial_receipt_sha256": "358AB331BA34A0F207AFE93CEFFA45A355AE2DD6332EF0F9C9FBA0A9FD92C42C",
        "historical_first_AP_receipt_sha256": "58F0EBEEA6C844714D4E57568C56987C0A9E03D92A9D29421974A6D7C91FD5AC",
        "positive_receipts_rebound_in_tests": False, "pair_validation_is_freshness_or_authentication": False,
        "dynamic_comparison_scope": "validated_TSC_online_TSC_stop_and_dependent_checksum_only",
        "control_execution_complete": False, "unproven_per_control_rejection_groups_at_least": 65,
        "current_candidate_full_gate_passed": False, "production_ready": False,
    }
    gate["current_closeout_regression"] = {
        "cycle": 189, "status": "pass", "scope": "first_AP_recorded_evidence_and_validated_dynamic_comparison_only",
        "tests_run": 12, "tests_passed": 12, "tests_failed": 0, "tests_skipped": 0,
        "hostile_environment": True,
        "log_sha256": "9D496774589156953AB92E2112CC5D1D73620B1A7F4DCAD3E007CA89F507B999",
        "qualifier_output_preservation_cases": 2,
        "synthetic_dynamic_consistency_positive_cases": 1,
        "synthetic_dynamic_consistency_rejection_cases": 3,
        "synthetic_consistency_is_fresh_execution": False,
        "preserved_intake_helper_failures": ["cycle198_pin_instead_of188", "prerequisite18_pin_instead_of19"],
        "repaired_intake_prerequisites_passed": 19,
        "original_counterexample_replay": {"cases": 67, "runtime_accepted": 0, "aggregate_gate_accepted": 0,
            "runtime_exceptions": 0, "aggregate_gate_exceptions": 0,
            "genuine_positive_runtime_and_gate_pass": True,
            "record_sha256": "FF815E0DA6C952176E0430FBBC574BEC28FB5AE0DFA3355ED03BB98B0958D730"},
        "combined_regression": {
            "status": "pass", "scope": "first_AP_IRQ_VM_PMM_CPU_boot_host_progress_checklist_and_core_not_full_canonical",
            "tests_run": 271, "tests_passed": 271, "tests_skipped": 0,
            "log_sha256": "2F82DB7E7017340835E7FC84456145C49805EA3054A93BC59F2DCDFCA87B7CDD",
        },
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 189: " + checkpoint + " repairs first-AP recorded execution, typed lifecycle/cleanup "
        "accounting and fail-closed malformed admission. Raw runs validate before allowing only TSC "
        "and dependent-checksum differences. Two final boots, 72 executed controls and 12 focused "
        "tests pass, including 159 corrupt records, six malformed root/control cases and two "
        "output-preservation cases. All 67 original counterexamples reject without exceptions."
    )
    gap = (
        "Selected readiness is 17/27; ten per-CPU-runtime-through-lock profiles remain from "
        "N8-SMP-PERCPU-RUNTIME-001. At least 65 scheduler controls still require individually bound "
        "rejection execution before full exact canonical/Doctor/publication/configured-check/review "
        "qualification and PR78 merge. The prior 55 runtime and 46 gate admissions, one runtime "
        "and four gate exceptions, two superseded initial boots and two intake-helper pin failures "
        "remain preserved. No general AP runtime, CPU retirement, hardware, independent builder, "
        "phase, flag, native kernel feature, ISO or production gate closes."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N8", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 189 source inventory: 1016 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N8-SMP-FIRST-AP-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"] = list(roadmap["gap_summary"]["native_program_gaps"])
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle190(roadmap, test_count)


def apply_cycle190(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle190-percpu-recorded-evidence.md"
    roadmap["baseline"]["pooleos_cycle"] = 190
    protocol = roadmap["execution_protocol"]
    protocol.update(last_updated_cycle=190, selected_move_id="N8-SMP-PERCPU-RUNTIME-001",
                    owner_independent_next_move_id="N8-SMP-IPI-001")
    protocol["required_records"].insert(0, checkpoint)
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for name in ("focused_source_projection", "dependency_qualification", "closeout_regression", "candidate_audit"):
        suffix = "source_projection" if name == "focused_source_projection" else name
        gate["historical_cycle189_" + suffix] = copy.deepcopy(gate["current_" + name])
    gate["qualification_status"] = "per_CPU_recorded_evidence_repaired_nine_dependencies_and_control_audit_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=190)
    gate["current_focused_source_projection"] = dict(
        copy.deepcopy(gate["historical_cycle189_source_projection"]),
        cycle=190, passed_checks=18, pending_downstream_native_checks=9,
        passing_profiles=[*gate["historical_cycle189_source_projection"]["passing_profiles"],
                          "native_kernel_smp_percpu_runtime_readiness"],
        run_count_scope="current_cycle_per_CPU_runtime_only_prior_qualification_retained_separately",
        next_dependency_move_id="N8-SMP-IPI-001", focused_python_tests_passed=10,
        focused_test_log_sha256="61B27EBF0AA15CC269E4C45EDD3DAEA30E3BEA454E63863603BAA0ACCD32FDC0",
        recorded_evidence_rejection_cases=253,
    )
    prior = gate["historical_cycle189_dependency_qualification"]
    gate["current_dependency_qualification"] = {
        "cycle": 190, "source_validation_cycle": 190, "status": "PMM_VM_IRQ_first_AP_per_CPU_pass_nine_profiles_pending",
        "scope": "physical_memory_virtual_memory_interrupt_time_first_AP_per_CPU_runtime_only",
        "applies_to_current_source": True, "all_fourteen_profiles_current": False,
        "qualified_profiles": [*prior["qualified_profiles"], "smp_percpu_runtime"],
        "newly_qualified_profiles": ["smp_percpu_runtime"],
        "readiness_replay_required_profiles": prior["readiness_replay_required_profiles"][1:],
        "fresh_qemu_runs": 2, "run_count_scope": "current_cycle_per_CPU_runtime_only",
        "superseded_initial_runs": 2, "negative_control_groups": 19, "negative_control_cases": 159,
        "kernel_sha256": prior["kernel_sha256"],
        "receipt_bindings": [*copy.deepcopy(prior["receipt_bindings"]), {
            "profile": "smp_percpu_runtime", "path": "runs/native-kernel-smp-percpu-runtime-readiness.json",
            "sha256": "1E1778C2E204F40D8D12C992BFF7DCEFC20067D16F9DFE1BC83CCCECFE8BD9B7",
            "fresh_runs": 2, "negative_controls": 19, "hostile_cases": 159, "kernel_host_tests": 245,
            "execution_log_sha256": "6AA6B171C06F825AB34FD35B6DC0F0C4AE1B3C3BDBEA115B9A29D1DDD4812575",
            "elapsed_seconds": 71.797}],
        "prior_qualification_record": "historical_cycle189_dependency_qualification",
        "recorded_evidence_cases": {"exit": 14, "coverage": 16, "evidence": 23, "shape": 3,
            "dynamic-policy": 7, "observation": 108, "summary": 40, "raw-stop": 3, "controls": 39},
        "recorded_evidence_case_total": 253, "malformed_root_and_control_cases": 6,
        "recorded_evidence_rejections_exercised_through_runtime_and_gate": True,
        "per_control_case_counts_bound": True,
        "pre_repair_counterexample": {"cases": 69, "runtime_accepted": 57, "aggregate_gate_accepted": 48,
            "runtime_exceptions": 1, "aggregate_gate_exceptions": 4,
            "record_sha256": "1E6B18B306586F79AF8B345A14202075390D3423883CD38256180629F3513358"},
        "initial_receipt_sha256": "A15F3A44972D7A5472D62EE5D62CABCE61872CBD44C1FA15B5022DA356CB450A",
        "historical_per_CPU_receipt_sha256": "03B2E751984D8FADBB64302748E3D4CBB025F5DF285D665AAD8399CDA9DC07C2",
        "positive_receipts_rebound_in_tests": False, "pair_validation_is_freshness_or_authentication": False,
        "dynamic_comparison_scope": "validated_TSC_online_TSC_stop_and_both_dependent_checksums_only",
        "control_execution_complete": False, "unproven_per_control_rejection_groups_at_least": 65,
        "current_candidate_full_gate_passed": False, "production_ready": False,
    }
    gate["current_closeout_regression"] = {
        "cycle": 190, "status": "pass", "scope": "per_CPU_recorded_evidence_dynamic_comparison_and_control_counts_only",
        "tests_run": 10, "tests_passed": 10, "tests_failed": 0, "tests_skipped": 0,
        "hostile_environment": True,
        "log_sha256": "61B27EBF0AA15CC269E4C45EDD3DAEA30E3BEA454E63863603BAA0ACCD32FDC0",
        "qualifier_output_preservation_cases": 2, "raw_dynamic_normalization_rejections": 4,
        "original_counterexample_replay": {"cases": 69, "runtime_accepted": 0, "aggregate_gate_accepted": 0,
            "runtime_exceptions": 0, "aggregate_gate_exceptions": 0,
            "genuine_positive_runtime_and_gate_pass": True,
            "record_sha256": "94F7EE3D5D95AFA8DD59647DD918E7FDA47876E0EFBA176E77B5CE955E690D30"},
        "combined_regression": {
            "status": "pass", "scope": "per_CPU_first_AP_IRQ_VM_PMM_CPU_boot_host_progress_checklist_and_core_not_full_canonical",
            "tests_run": 282, "tests_passed": 282, "tests_skipped": 0,
            "log_sha256": "30B8009003B608F0DC78D7B837BF65750E7263551C4DB69577B0E933085BD262",
        },
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 190: " + checkpoint + " repairs per-CPU recorded execution, exact typed accounting, "
        "dynamic timestamp and dual-checksum validation, malformed-input rejection and per-control "
        "case-count binding. Two final boots, 159 executed cases in 19 categories and 10 focused "
        "tests pass, including 253 corrupt records, six root/control shapes and two output-preservation "
        "cases. All 69 original counterexamples reject without validator exceptions."
    )
    gap = (
        "Selected readiness is 18/27; nine IPI-through-lock profiles remain from N8-SMP-IPI-001. "
        "At least 65 scheduler controls still require individually bound rejection execution before "
        "full exact canonical/Doctor/publication/configured-check/review qualification and PR78 merge. "
        "The prior 57 runtime and 48 gate admissions, one runtime and four gate exceptions, and two "
        "superseded initial boots remain preserved. General CPU retirement, AP resource ownership "
        "integration, hardware, independent builders and production remain unproved. No phase, flag, "
        "native kernel feature, ISO or production gate closes."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N8", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 190 source inventory: 1021 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N8-SMP-PERCPU-RUNTIME-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"] = list(roadmap["gap_summary"]["native_program_gaps"])
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle191(roadmap, test_count)


def apply_cycle191(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle191-ipi-recorded-evidence.md"
    next_move = "N8-SMP-MAILBOX-ORACLE-001"
    roadmap["baseline"]["pooleos_cycle"] = 191
    protocol = roadmap["execution_protocol"]
    protocol.update(last_updated_cycle=191, selected_move_id="N8-SMP-IPI-001",
                    owner_independent_next_move_id=next_move)
    protocol["required_records"].insert(0, checkpoint)
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for name in ("focused_source_projection", "dependency_qualification", "closeout_regression", "candidate_audit", "ownership_qualification"):
        suffix = "source_projection" if name == "focused_source_projection" else name
        gate["historical_cycle190_" + suffix] = copy.deepcopy(gate["current_" + name])
    gate["qualification_status"] = "IPI_recorded_evidence_repaired_mailbox_oracle_eight_dependencies_and_control_audit_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=191)
    gate["current_focused_source_projection"] = dict(
        copy.deepcopy(gate["historical_cycle190_source_projection"]),
        cycle=191, passed_checks=19, pending_downstream_native_checks=8,
        passing_profiles=[*gate["historical_cycle190_source_projection"]["passing_profiles"],
                          "native_kernel_smp_ipi_readiness"],
        run_count_scope="current_cycle_IPI_only_prior_qualification_retained_separately",
        next_dependency_move_id=next_move, focused_python_tests_passed=31,
        required_next_gate="export_and_independently_validate_AP_mailboxes_then_requalify_affected_dependencies_and_full_candidate",
        focused_test_log_sha256="7D708D7E007B0EF1C94E78E7906A061938A1ECB059A26A6A09571D8EDD9125DF",
        recorded_evidence_rejection_cases=528,
    )
    prior = gate["historical_cycle190_dependency_qualification"]
    binding = {
        "profile": "smp_ipi", "path": "runs/native-kernel-smp-ipi-readiness.json",
        "sha256": "7ADC371664FB3778A02688DBB521211237A4788CA01EF61B48C410CEF5898B44",
        "fresh_runs": 2, "negative_controls": 30, "hostile_cases": 249, "kernel_host_tests": 245,
        "execution_log_sha256": "3A54459FA80BF16849BAE25B15FD7D59B3D30E403057A683A053E7D568C3A23F",
        "elapsed_seconds": 100.594,
    }
    gate["current_dependency_qualification"] = {
        "cycle": 191, "source_validation_cycle": 191, "status": "PMM_VM_IRQ_first_AP_per_CPU_IPI_pass_eight_profiles_pending",
        "scope": "six_current_memory_interrupt_and_AP_profiles_only",
        "applies_to_current_source": True, "all_fourteen_profiles_current": False,
        "qualified_profiles": [*prior["qualified_profiles"], "smp_ipi"],
        "newly_qualified_profiles": ["smp_ipi"],
        "readiness_replay_required_profiles": prior["readiness_replay_required_profiles"][1:],
        "fresh_qemu_runs": 2, "run_count_scope": "current_cycle_IPI_only",
        "superseded_initial_runs": 2, "negative_control_groups": 30, "negative_control_cases": 249,
        "kernel_sha256": prior["kernel_sha256"],
        "receipt_bindings": [*copy.deepcopy(prior["receipt_bindings"]), binding],
        "prior_qualification_record": "historical_cycle190_dependency_qualification",
        "recorded_evidence_cases": {"exit": 14, "coverage": 16, "evidence": 23, "shape": 3,
            "dynamic-policy": 8, "observation": 367, "summary": 34, "raw-frame": 2, "controls": 61},
        "recorded_evidence_case_total": 528, "malformed_root_and_control_cases": 6,
        "recorded_evidence_rejections_exercised_through_runtime_and_gate": True,
        "per_control_case_counts_bound": True,
        "pre_repair_counterexample": {"cases": 66, "runtime_accepted": 48, "aggregate_gate_accepted": 40,
            "runtime_exceptions": 0, "aggregate_gate_exceptions": 3,
            "record_sha256": "1FE9D8F3E79463176F3FB84ACAED13A0BFE3BD9E88155CA55098C4D7F0C9FD2B"},
        "initial_receipt_sha256": "2AA019A85D2C5DC032E5BB7A0F1B714FF27FD6F1772701687594F40B2D3430B6",
        "historical_IPI_receipt_sha256": "2B1F8D623D31476F2C8886DFD583BE9514C68A2B3D0DA36BC75DDD13D6823CCA",
        "positive_receipts_rebound_in_tests": False, "pair_validation_is_freshness_or_authentication": False,
        "dynamic_comparison_scope": "guest_checked_AP_mailbox_checksums_not_independently_host_recomputed",
        "host_recomputed_frame_checksums": True,
        "frame_checksum_scope": "frozen_contiguous_private_resource_and_frame_layout_only",
        "constant_only_release_controls_replaced": 3,
        "prior_claimed_249_cases_included_constant_only_controls": True,
        "control_execution_complete": False, "unproven_per_control_rejection_groups_at_least": 65,
        "current_candidate_full_gate_passed": False, "production_ready": False,
    }
    gate["current_ownership_qualification"] = dict(
        gate["current_ownership_qualification"], cycle=191,
        scope="retained_host177_VM187_and_bounded_PKAPOWN1_IPI191",
        fresh_current_cycle_qemu_runs=2, live_replay_cycle=191,
        live_receipt_source_current=True, current_boot_artifact_set_replay_pending=False,
        ap_runtime_live_integration_verified=True,
        live_receipt_scope="two_current_IPI_runs_prior_VM187_retained_separately",
        source_current_scope="declared_inputs_current_boot_artifacts_and_transfer_dependency",
        smp_receipt_sha256=binding["sha256"], attempts_per_run=2,
        retained_free_rejections_per_attempt=27, owner_release_rejections_per_attempt=18,
        independent_AP_mailbox_checksum_oracle_complete=False,
    )
    gate["current_ipi_mailbox_oracle_gap"] = {
        "cycle": 191, "status": "open", "move_id": next_move,
        "requirement_id": "ADD-N36-RECEIPT-COVERAGE-001", "flag_id": "FLAG-N36-RECEIPT-COVERAGE-001",
        "phases": ["N8.5", "N8.6", "N36"], "blocks_merge_qualification": True,
        "scope": "two_mailbox_checksum_words_for_each_of_three_APs_per_run",
        "guest_recomputes_checksums": True, "host_independently_recomputes_checksums": False,
        "export_complete": False, "production_ready": False,
        "implementation_tasks": [
            "Export the complete baseline/runtime mailbox checksum inputs from native PooleKernel on both channels",
            "Bind each snapshot to its AP identity, phase, and checksum algorithm without normalizing first",
            "Independently derive both checksums and reject missing, duplicate, reordered, malformed and coherently altered inputs",
            "Preserve the opaque prior receipts as limited history; qualify new native bytes and every affected boot/dependency receipt",
            "Resume the eight scheduler-through-lock profiles and individually execute the 65 scheduler controls before full qualification",
        ],
    }
    gate["current_closeout_regression"] = {
        "cycle": 191, "status": "pass", "scope": "IPI_recorded_evidence_frame_oracle_and_actual_release_controls_only",
        "tests_run": 31, "tests_passed": 31, "tests_failed": 0, "tests_skipped": 0,
        "hostile_environment": True,
        "log_sha256": "7D708D7E007B0EF1C94E78E7906A061938A1ECB059A26A6A09571D8EDD9125DF",
        "qualifier_output_preservation_cases": 2, "raw_dynamic_normalization_rejections": 6,
        "independent_frame_address_mutations": 4, "release_accounting_direct_rejections": 6,
        "disabled_real_accounting_validator_detected": True,
        "synthetic_opaque_checksum_limitation_documented": True,
        "initial_combined_regression": {"tests_run": 314, "tests_passed": 312, "tests_failed": 2,
            "tests_skipped": 0, "classification": "historical_IPI_receipt_and_embedded_entry_expectations_not_updated",
            "log_sha256": "9F94FF8807A23394981C5D659B8AE30F74AF54509C816E67B02D5E55F042477E"},
        "synthetic_consistency_is_fresh_execution": False,
        "original_counterexample_replay": {"cases": 66, "runtime_accepted": 0, "aggregate_gate_accepted": 0,
            "runtime_exceptions": 0, "aggregate_gate_exceptions": 0,
            "genuine_positive_runtime_and_gate_pass": True,
            "record_sha256": "8D871AC61941C027378508F6538B7078275213082F2C263C5533F577EB39364F"},
        "combined_regression": {
            "status": "pass", "scope": "IPI_per_CPU_first_AP_IRQ_VM_PMM_CPU_boot_host_progress_checklist_and_core_not_full_canonical",
            "tests_run": 314, "tests_passed": 314, "tests_skipped": 0,
            "log_sha256": "40361D70294E071A558B56D685628287D99225A4AB938293B35FC320474481FA",
        },
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 191: " + checkpoint + " repairs strict IPI recorded execution, typed observations and summaries, "
        "per-control counts and pre-write admission. The host now recomputes frozen frame-address checksums; "
        "three constant-only controls now execute the real release-accounting validator. Two final four-vCPU "
        "boots, 249 executed cases in 30 categories and 31 focused tests pass, including 528 corrupted records "
        "through runtime and gate. All 66 original cases reject without exceptions. Bounded PKAPOWN1 "
        "ownership is current on these two runs; general task-stack/CPU retirement is not proved."
    )
    gap = (
        "Selected readiness is 19/27, not independent complete mailbox validation. Next " + next_move +
        " must export complete native AP mailbox inputs and independently recompute both checksums before "
        "normalization under ADD-N36-RECEIPT-COVERAGE-001 / FLAG-N36-RECEIPT-COVERAGE-001. "
        "This blocks merge qualification, followed by affected-image replay, eight scheduler-through-lock "
        "profiles, at least 65 scheduler control-execution gaps and exact full qualification. The prior "
        "48 runtime/40 gate admissions, three gate exceptions, three constant-only controls and two "
        "superseded boots remain preserved. No phase, flag, kernel feature, ISO or production gate closes."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N8", "N9", "N12", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 191 source inventory: 1028 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N8-SMP-IPI-001", "FLAG-N8-SMP-MULTI-AP-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"] = list(roadmap["gap_summary"]["native_program_gaps"])
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle192(roadmap, test_count)


def apply_cycle192(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle192-native-mailbox-oracle.md"
    kernel_sha = "B9AF7DFB13472C0A0D3CBE70036EFAD7C3B792F13FC9944ACEC935B362F0FBA8"
    core_sha = "B9B486A01F540E93B1178B887E17BBA9FA43B90C5F3956D630AA4A6BA9A6F818"
    entry_sha = "C73306B5D5D6CF48C5FB6BBF00155CBD08283920A353C78B5AFF20039119BAB5"
    ipi_sha = "D302E39890B500E1D8B732EDE823A62893A0C6453E5E78FC0747FE91DF7CF2F7"
    test_log = "10F42ABFF988C39A72B1AF910A01825D4D1AFCFB1AAD267FC3DAC225B8A80FE6"
    cpu_pending = ["trap", "cpu_policy", "xstate_policy", "xstate_exception", "privilege_msr_policy"]
    memory_pending = ["physical_memory", "virtual_memory", "interrupt_time", "smp_first_ap", "smp_percpu_runtime",
                      "scheduler", "scheduler_preempt", "scheduler_deferred", "scheduler_smp",
                      "scheduler_ap_workers", "scheduler_smp_preempt", "atomics", "locks"]
    passing = ["kernel_entry", "symbol", "policy", "kernel_load", "pooleboot", "kernel_revalidation",
               "kernel_transfer", "kernel_errata_policy", "kernel_smp_ipi"]
    roadmap["baseline"]["pooleos_cycle"] = 192
    protocol = roadmap["execution_protocol"]
    protocol.update(last_updated_cycle=192, selected_move_id="N8-SMP-MAILBOX-ORACLE-001",
                    owner_independent_next_move_id="N7-TRAP-001")
    protocol["required_records"][:0] = [checkpoint,
        "docs/checkpoints/cycle192-unfinished-cloud-backup.md",
        "docs/checkpoints/cycle192-mailbox-qualified-backup.md"]
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for name in ("focused_source_projection", "dependency_qualification", "closeout_regression", "candidate_audit",
                 "ownership_qualification", "ipi_mailbox_oracle_gap", "boot_chain_qualification", "cpu_qualification",
                 "entry_provenance_qualification", "task_stack_qualification", "execution_qualification"):
        suffix = "source_projection" if name == "focused_source_projection" else name
        gate["historical_cycle191_" + suffix] = copy.deepcopy(gate["current_" + name])
    gate["qualification_status"] = "native_mailbox_oracle_verified_eighteen_dependencies_and_control_audit_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=192)
    gate["current_focused_source_projection"] = {
        "cycle": 192, "scope": "27_selected_native_checks_not_full_canonical_audit",
        "passed_checks": 9, "total_checks": 27, "pending_downstream_native_checks": 18,
        "passing_profiles": ["native_" + name + "_readiness" for name in passing],
        "final_receipt_fresh_qemu_runs": 8, "kernel_entry_runs": 4, "superseded_initial_qemu_runs": 2,
        "run_count_scope": "current_cycle_boot_chain_and_IPI_only",
        "next_dependency_move_id": "N7-TRAP-001",
        "required_next_gate": "requalify_eighteen_changed_kernel_dependencies_then_controls_and_full_candidate",
        "focused_python_tests_passed": 57, "focused_python_tests_skipped": 0,
        "focused_test_log_sha256": test_log, "recorded_evidence_rejection_cases": 906,
        "raw_mailbox_rejection_cases": 360, "malformed_root_and_control_cases": 6,
        "canonical_full_replay_performed": False, "production_ready": False,
    }
    boot_bindings = [
        {"profile": profile, "path": path, "sha256": digest, "fresh_runs": runs,
         "execution_log_sha256": log, "elapsed_seconds": seconds}
        for profile, path, digest, runs, log, seconds in (
            ("symbol", "runs/native_symbol_readiness.json", "546A2D3075FE4FD1F956AD77FF00BBCF2C8642EF386A40FAB1A8CD150EDE009A", 0,
             "39D622078702BC250B96EFD6CACB9EC04214EB6EEF0062BCFD4BF83419DC0038", 67.719),
            ("policy", "runs/native_policy_readiness.json", "67522CD25A64FA6DA6CEA98A7BACB8DF61BB04AF49C50A570C94F8326096D838", 0,
             "4E0AA1F9DB24DE8D841452D60CA70EBAD0B1883FF79739D7A96CB02A1045ECA7", 26.469),
            ("kernel_load", "runs/native_kernel_load_readiness.json", "F51E811F7DA5C771BAEFA6437E27D6B48B96035D85AFC9757F2B55AC90C3C0FD", 2,
             "24233E8F7FB37FC573D7D9F836F53C273844B1D9F79D391608D605F316876C4B", 242.578),
            ("pooleboot", "runs/native_pooleboot_readiness.json", "25959CA635B90E27AC3AABCB03300DD1EB1C3F6B3B0664B1B3EDEB29BFE8C248", 2,
             "56338F6E2175B97E50BB1E2377476252F07B88CAAEAF64E220040A84FE086C65", 108.437),
            ("kernel_revalidation", "runs/native-kernel-revalidation-readiness.json", "DF72365F4583614401500AEC332725DC7B63558EA2C63C0E1F55764EF7B1EF6A", 0,
             "A241574365E43C16D05D7D059E5D2DF662F24D5D5A58A65536FB8528DE34177D", 25.516),
            ("kernel_transfer", "runs/native-kernel-transfer-readiness.json", "132A97CD727B3A135501B5932B75D7ED33CAEA7204B5F0E8F762CA167B65983A", 2,
             "6D262F6F7B5DC4C455CCFC552F207D2F267C44047D41E43A0312C1FA6DDD12F6", 69.813),
        )
    ]
    gate["current_boot_chain_qualification"] = {
        "cycle": 192, "source_validation_cycle": 192, "status": "single_host_replay_pass",
        "scope": "six_N5_profiles_with_prior_current_firmware_and_trust_prerequisites",
        "applies_to_current_source": True, "qualified_profiles": [b["profile"] for b in boot_bindings],
        "receipt_bindings": boot_bindings,
        "prerequisite_receipt_bindings": copy.deepcopy(gate["historical_cycle191_boot_chain_qualification"]["prerequisite_receipt_bindings"]),
        "prerequisite_run_count_scope": "retained_prior_receipts_revalidated_not_fresh_executions",
        "fresh_qemu_runs": 6, "kernel_entry_runs": 2, "kernel_sha256": kernel_sha,
        "kernel_host_tests": 246, "loader_host_tests": 331, "pooleboot_host_tests": 8,
        "retained_file_count": 9, "retained_bytes": 11952, "manifest_bytes": 2615,
        "inner_set_sha256": "FE35AE51B905BDFE7CB59F32CB2AF69A56910DA24DA83A74A9D92BB1BE5C7F0B",
        "trust_policy_sha256": "7FD68927AECC739F8459ED6C6B2AB154318B357929F478A2D5B4B6D8C306C6B3",
        "trust_state_sha256": "5F8AE1BE86EE3DC024C332D5CA3BA5D5B8ED09B60BAB17855A410A16A64634AD",
        "real_image_trust_independently_reconstructed": True,
        "golden_fixture_is_actual_kernel": False, "unsigned_policy_denied": True,
        "authority_grants": 0, "actions_authorized": 0, "state_writes": 0,
        "boot_identity_rejection_cases": 23, "forged_PooleBoot_host_test_count_rejections": 12,
        "readiness_replay_required_profiles": [], "complete_host_attestation": False,
        "second_builder_reproduced": False, "n5_exit_gate_satisfied": False,
        "current_candidate_full_gate_passed": False, "production_ready": False,
    }
    gate["current_entry_provenance_qualification"] = dict(
        gate["current_entry_provenance_qualification"], cycle=192, source_validation_cycle=192,
        linked_byte_count=7036160, linked_sha256="6FFC3709DDBFD66328B734AD735153FCCEE192B5E68AC5D1EF42D1F6E5DFC980",
        canonical_sha256=kernel_sha, entry_receipt_sha256=entry_sha,
        kernel_host_tests=246, entry_python_tests=14, latest_reproduction_cycle=192,
    )
    gate["current_task_stack_qualification"] = dict(
        gate["current_task_stack_qualification"], cycle=192, receipt_sha256=core_sha, kernel_tests_per_host_profile=246)
    gate["current_execution_qualification"] = dict(
        gate["current_execution_qualification"], cycle=192, receipt_sha256=core_sha, kernel_sha256=kernel_sha)
    gate["current_cpu_qualification"] = {
        "cycle": 192, "source_validation_cycle": 192, "status": "source_requalification_required",
        "applies_to_current_source": False, "kernel_sha256": kernel_sha,
        "historical_record": "historical_cycle191_cpu_qualification", "qualified_profiles": [],
        "readiness_replay_required_profiles": cpu_pending, "fresh_qemu_runs": 0,
        "embedded_entry_provenance_replay_pending": True,
        "current_candidate_full_gate_passed": False, "production_ready": False,
    }
    binding = {
        "profile": "smp_ipi", "path": "runs/native-kernel-smp-ipi-readiness.json", "sha256": ipi_sha,
        "fresh_runs": 2, "negative_controls": 33, "hostile_cases": 609, "kernel_host_tests": 246,
        "execution_log_sha256": "4B314EC1800F8184E16D843D507E35981A96115FE26798BD1E83E590C3FE2EF3",
        "elapsed_seconds": 319.219,
    }
    gate["current_dependency_qualification"] = {
        "cycle": 192, "source_validation_cycle": 192, "status": "IPI_pass_thirteen_memory_dependencies_pending",
        "scope": "current_PKMBX1_IPI_only_not_prior_memory_or_scheduler_profiles",
        "applies_to_current_source": True, "all_fourteen_profiles_current": False,
        "qualified_profiles": ["smp_ipi"], "newly_qualified_profiles": ["smp_ipi"],
        "readiness_replay_required_profiles": memory_pending, "fresh_qemu_runs": 2,
        "run_count_scope": "current_cycle_final_IPI_only", "superseded_initial_runs": 2,
        "negative_control_groups": 33, "negative_control_cases": 609, "kernel_sha256": kernel_sha,
        "receipt_bindings": [binding], "prior_qualification_record": "historical_cycle191_dependency_qualification",
        "recorded_evidence_cases": {"exit": 14, "coverage": 16, "evidence": 23, "shape": 3,
            "dynamic-policy": 8, "observation": 739, "summary": 34, "raw-frame": 2, "controls": 67},
        "recorded_evidence_case_total": 906, "raw_mailbox_rejection_cases": 360,
        "malformed_root_and_control_cases": 6, "recorded_evidence_rejections_exercised_through_runtime_and_gate": True,
        "per_control_case_counts_bound": True, "positive_receipts_rebound_in_tests": False,
        "pair_validation_is_freshness_or_authentication": False,
        "dynamic_comparison_scope": "independently_validated_PKMBX1_TSC_and_dependent_checksums_only",
        "host_recomputed_frame_checksums": True, "host_recomputed_mailbox_checksums": True,
        "control_execution_complete": False, "unproven_per_control_rejection_groups_at_least": 65,
        "current_candidate_full_gate_passed": False, "production_ready": False,
    }
    gate["current_ownership_qualification"] = dict(
        gate["current_ownership_qualification"], cycle=192, host_qualification_cycle=192,
        scope="host192_and_bounded_PKAPOWN1_IPI192_prior_VM187_historical_only",
        kernel_sha256=kernel_sha, kernel_tests_per_host_profile=246,
        reclamation_receipt_sha256=core_sha, entry_receipt_sha256=entry_sha, smp_receipt_sha256=ipi_sha,
        live_replay_cycle=192, live_receipt_source_current=True,
        active_root_current_image_replay_complete=False, virtual_memory_live_receipt_source_current=False,
        live_receipt_scope="two_current_IPI_runs_not_historical_VM187",
        independent_AP_mailbox_checksum_oracle_complete=True,
    )
    gate["current_ipi_mailbox_oracle_gap"] = {
        "cycle": 192, "status": "bounded_oracle_verified_affected_dependency_replay_pending",
        "move_id": "N8-SMP-MAILBOX-ORACLE-001", "requirement_id": "ADD-N36-RECEIPT-COVERAGE-001",
        "flag_id": "FLAG-N36-RECEIPT-COVERAGE-001", "phases": ["N8.5", "N8.6", "N36"],
        "blocks_merge_qualification": True, "scope": "PKMBX1_saved_quiesced_snapshots_for_three_APs",
        "guest_recomputes_checksums": True, "host_independently_recomputes_checksums": True,
        "export_complete": True, "context_word_count": 5, "baseline_word_count": 15, "runtime_word_count": 38,
        "raw_mailbox_rejection_cases": 360, "disabled_oracle_detected": True,
        "authentication_proved": False, "all_coherent_forgeries_excluded": False,
        "remaining_affected_profiles": 18, "production_ready": False,
    }
    gate["current_closeout_regression"] = {
        "cycle": 192, "status": "pass", "scope": "mailbox_IPI_boot_gate_entry_gate_and_publication_only",
        "tests_run": 57, "tests_passed": 57, "tests_failed": 0, "tests_skipped": 0,
        "log_sha256": test_log, "elapsed_seconds": 189.518,
        "disabled_real_accounting_validator_detected": True, "disabled_mailbox_oracle_detected": True,
        "initial_gate_pin_regression": {"tests_run": 6, "tests_passed": 4, "tests_failed": 2,
            "classification": "fixture_only_trust_pins_used_for_actual_boot_image",
            "log_sha256": "42798D1A736D0B090A22791FFCE18458AD18C48C5AE4F7EB28F1CC3439CBFDFA"},
        "corrected_gate_pin_regression": {"tests_run": 6, "tests_passed": 6, "tests_failed": 0,
            "log_sha256": "8C9320236108D50787849349CAF55991AC792582F6E72663D1A21BEA8CFE2E04"},
        "initial_metadata_regression": {"tests_run": 33, "tests_passed": 30, "tests_failed": 3,
            "classification": "two_prior_schema_constants_and_one_historical_ownership_assertion",
            "log_sha256": "F563058F91B4F389F1670EDB0D3F63CB239535B04F612DB687D2096AD7B9B698"},
        "corrected_metadata_regression": {"tests_run": 33, "tests_passed": 33, "tests_failed": 0,
            "log_sha256": "252690F857336D44B6F3901DD52BF0DE0E8B1094B57429AB064E81DA9F642F80"},
        "combined_regression": {
            "status": "pass", "scope": "mailbox_IPI_entry_boot_host_core_progress_and_checklist_not_full_canonical",
            "tests_run": 189, "tests_passed": 189, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 135.414,
            "log_sha256": "A006B6EE240A27783BA4D24B6E5FAF8B357081C1F2145835AF2AAC7EB2643BFA",
        },
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 192: " + checkpoint + " implements native PKMBX1 saved AP mailbox export and independent host "
        "checksum/state validation before normalization. Two final four-vCPU IPI boots pass 609 rejection "
        "cases in 33 groups and 246 native kernel tests. Six final boot-chain runs and 57 scoped regression "
        "tests pass, including 906 recorded-evidence and 360 raw-mailbox corruptions through runtime and "
        "actual gate. The changed kernel has nine admitted bounded receipts; independent builders, general "
        "CPU/task retirement, hardware and production remain unproved."
    )
    gap = (
        "Selected readiness is 9/27 after the kernel change; historical 19/27 is not current-image evidence. "
        "Eighteen CPU, memory, IRQ, AP, scheduler, atomic and lock profiles require replay from N7-TRAP-001. "
        "Prior VM/CPU receipts are explicitly historical. At least 65 scheduler control-execution gaps and "
        "full exact-candidate canonical/Doctor/publication/configured-check/review qualification still "
        "block merge. PKMBX1 consistency is not authentication or exclusion of all coherent forgeries. "
        "Initial failures and two superseded IPI boots are retained. No phase, flag or production gate closes."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N5", "N6", "N7", "N8", "N9", "N12", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 192 source inventory: 1041 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N8-SMP-IPI-001", "FLAG-N8-SMP-MULTI-AP-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle193(roadmap, test_count)


def apply_cycle193(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle193-current-kernel-cpu-replay.md"
    next_move = "N9-PMM-ACPI-CONSUMER-001"
    roadmap["baseline"]["pooleos_cycle"] = 193
    protocol = roadmap["execution_protocol"]
    protocol.update(last_updated_cycle=193, selected_move_id="N7-TRAP-001",
                    owner_independent_next_move_id=next_move)
    protocol["required_records"].insert(0, checkpoint)
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for name in ("focused_source_projection", "cpu_qualification", "closeout_regression",
                 "candidate_audit", "ipi_mailbox_oracle_gap"):
        suffix = "source_projection" if name == "focused_source_projection" else name
        gate["historical_cycle192_" + suffix] = copy.deepcopy(gate["current_" + name])
    gate["qualification_status"] = "N7_current_image_replay_pass_thirteen_dependencies_and_control_audit_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=193)
    test_log = "A8AEED4944BD3E510B4AAB2FDEF166FE1BE1CA2622874FC384113216B2677B2E"
    bindings = [
        {"profile": profile, "path": "runs/native-kernel-" + profile.replace("_", "-") + "-readiness.json",
         "sha256": digest, "fresh_runs": runs, "negative_controls": controls, "kernel_host_tests": 246,
         "execution_log_sha256": log, "elapsed_seconds": seconds}
        for profile, digest, runs, controls, log, seconds in (
            ("trap", "D85B45BE21B4BEF1380D8A3DCB6F8E84D7F211B828A8B26BFABAEE26BDF79116", 6, 51,
             "E8368031D10457C37DBBFBCD0B8EA83A5D18B3A22C74930B6EDCA9FF548D0310", 172.015),
            ("cpu_policy", "167A164D7DF161CC4DB41964D16F88A6A3D54200BB91C78BA57C5FB7CD316E5D", 2, 41,
             "CFA41675A79CE67949D1FDB8D08F791EB2FD1115237010D33465135306D1CE23", 68.625),
            ("xstate_policy", "22B5BAC22729C90A04650AB380AA6C79B56E9E65821C1B43EE03332F2B577253", 2, 43,
             "4260145CE808D54618100843E5797A22DAFA156F94093C1D222D6D99730A162A", 75.016),
            ("xstate_exception", "7F25AE4A722855B4E24B5359E0074B0DC39DB2727C443817363A800C78D697C0", 2, 43,
             "F3ED8801D7E59F458EBE9E20B63EED505D5DEF7034E3E58654DA297E074BF60D", 76.734),
            ("privilege_msr_policy", "00DD6ADC8CBF3289DE7D16B831E145C8171C401B65BE9E9D6873BD2FAC31BCF7", 2, 47,
             "9B9A31059D4151F9B9A62622272025F3EDB8EEF33A8C29EEA6267DBE5A72AE32", 105.469),
        )
    ]
    gate["current_cpu_qualification"] = {
        "cycle": 193, "source_validation_cycle": 193, "status": "single_host_cpu_replay_pass",
        "scope": "five_N7_profiles_freshly_executed_against_Cycle192_mailbox_kernel",
        "applies_to_current_source": True, "kernel_sha256": gate["current_boot_chain_qualification"]["kernel_sha256"],
        "qualified_profiles": [b["profile"] for b in bindings], "receipt_bindings": bindings,
        "historical_record": "historical_cycle191_cpu_qualification",
        "readiness_replay_required_profiles": [], "embedded_entry_provenance_replay_pending": False,
        "fresh_qemu_runs": 14, "negative_control_groups": 225, "kernel_host_tests_per_qualifier": 246,
        "whpx_exception_runs": 2, "expected_tcg_limitation_probes": 1,
        "exception_deliveries_per_run": 3, "exception_recoveries_per_run": 2,
        "focused_python_tests": 51, "aggregate_gate_regression_cases": 19,
        "embedded_entry_rejection_cases": 80, "invalid_current_entry_dependency_cases": 20,
        "recorded_pair_count": 7, "recorded_exit_rejection_cases": 98,
        "recorded_coverage_rejection_cases": 112, "recorded_evidence_rejection_cases": 161,
        "recorded_evidence_total_rejection_cases": 371,
        "recorded_evidence_rejections_exercised_through_runtime_and_gate": True,
        "positive_receipts_rebound_in_tests": False, "pair_validation_is_freshness_or_authentication": False,
        "trap_control_validator_calls": 51, "disabled_trap_validator_detected": True,
        "entry_identity_comparison": "canonical_JSON_typed_equality",
        "canonical_kernel_changed_this_cycle": False, "superseded_initial_runs": 0,
        "current_candidate_full_gate_passed": False, "production_ready": False,
    }
    passing = ["kernel_entry", "symbol", "policy", "kernel_load", "pooleboot", "kernel_revalidation",
               "kernel_transfer", "kernel_trap", "kernel_cpu_policy", "kernel_errata_policy",
               "kernel_xstate_policy", "kernel_xstate_exception", "kernel_privilege_msr_policy", "kernel_smp_ipi"]
    gate["current_focused_source_projection"] = {
        "cycle": 193, "scope": "27_selected_native_checks_not_full_canonical_audit",
        "passed_checks": 14, "total_checks": 27, "pending_downstream_native_checks": 13,
        "passing_profiles": ["native_" + p + "_readiness" for p in passing],
        "final_receipt_fresh_qemu_runs": 14, "kernel_entry_runs": 14, "superseded_initial_qemu_runs": 0,
        "run_count_scope": "Cycle193_five_N7_profiles_only_not_retained_Cycle192_boot_and_IPI",
        "expected_tcg_limitation_probes": 1, "next_dependency_move_id": next_move,
        "required_next_gate": "thirteen_memory_IRQ_AP_scheduler_atomic_lock_profiles_then_controls_and_full_candidate",
        "focused_python_tests_passed": 51, "focused_python_tests_skipped": 0,
        "focused_test_log_sha256": test_log, "recorded_evidence_rejection_cases": 371,
        "canonical_full_replay_performed": False, "production_ready": False,
    }
    gate["current_ipi_mailbox_oracle_gap"] = dict(
        gate["current_ipi_mailbox_oracle_gap"], cycle=193, remaining_affected_profiles=13,
        newly_requalified_profiles=[b["profile"] for b in bindings])
    gate["current_closeout_regression"] = {
        "cycle": 193, "status": "pass", "scope": "five_N7_profiles_errata_entry_provenance_and_actual_CPU_release_gate",
        "tests_run": 51, "tests_passed": 51, "tests_failed": 0, "tests_skipped": 0,
        "elapsed_seconds": 21.014, "log_sha256": test_log, "disabled_trap_validator_detected": True,
        "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        "initial_metadata_regression": {
            "tests_run": 41, "tests_passed": 40, "tests_failed": 1, "tests_skipped": 0,
            "classification": "one_current_projection_assertion_retained_Cycle192_count_nine",
            "log_sha256": "AF449C3A0B9CFF99B5FCFC0AC6E0EA07849B48B3B547AC0DBF96547DFEBC21A7",
        },
        "corrected_metadata_regression": {
            "tests_run": 41, "tests_passed": 41, "tests_failed": 0, "tests_skipped": 0,
            "log_sha256": "03867A9D85A9C7DA88F5342501C2FC7F6F8038920E8BFAA39C02D91FB74037E5",
        },
        "combined_regression": {
            "status": "pass", "scope": "N7_entry_boot_mailbox_IPI_core_progress_checklist_publication_not_full_canonical",
            "tests_run": 249, "tests_passed": 249, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 249.924,
            "log_sha256": "19B76FD7488D7D89AA1877B71BFC5D5D7822427CF84F84920EBDFB1BFB75067A",
        },
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 193: " + checkpoint + " admits five fresh N7 receipts against the unchanged Cycle192 kernel: "
        "fourteen guest boots, 225 executed rejection controls, linked exception/MSR audits and 246 kernel "
        "host tests per qualifier. One expected TCG limitation probe remains diagnostic only. Fifty-one "
        "focused tests pass, including 371 recorded-evidence corruptions through runtime and actual gate, "
        "80 embedded-entry and 20 invalid-dependency cases, and disabled trap-validator detection."
    )
    gap = (
        "Selected readiness is 14/27; thirteen memory/IRQ/AP/scheduler/atomic/lock profiles remain from "
        + next_move + ". The current N7 records replace stale image evidence without rebinding it. "
        "The 65 scheduler control-execution gaps and full exact-candidate canonical/Doctor/publication/"
        "configured-check/review qualification still block main merge. User exceptions, general task/CPU "
        "retirement, independent builders, hardware and production are not proved. No phase or flag closes."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N7", "N8", "N9", "N12", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 193 source inventory: 1042 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N7-CPU-POLICY-001", "FLAG-N7-XSTATE-POLICY-001",
                          "FLAG-N7-XSTATE-EXCEPTION-001", "FLAG-N7-PRIVILEGE-MSR-POLICY-001",
                          "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle194(roadmap, test_count)


def apply_cycle194(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle194-memory-runtime-replay.md"
    next_move = "N12-SCHED-001"
    roadmap["baseline"]["pooleos_cycle"] = 194
    protocol = roadmap["execution_protocol"]
    protocol.update(last_updated_cycle=194, selected_move_id="N9-PMM-ACPI-CONSUMER-001",
                    owner_independent_next_move_id=next_move)
    protocol["required_records"].insert(0, checkpoint)
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for name in ("focused_source_projection", "dependency_qualification", "ownership_qualification",
                 "closeout_regression", "candidate_audit", "ipi_mailbox_oracle_gap"):
        suffix = "source_projection" if name == "focused_source_projection" else name
        gate["historical_cycle193_" + suffix] = copy.deepcopy(gate["current_" + name])
    gate["qualification_status"] = "memory_runtime_replay_pass_eight_dependencies_and_control_audit_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=194)
    bindings = [
        {"profile": profile, "path": "runs/native-kernel-" + profile.replace("_", "-") + "-readiness.json",
         "sha256": digest, "fresh_runs": 2, "negative_controls": controls, "hostile_cases": cases,
         "kernel_host_tests": 246, "execution_log_sha256": log, "elapsed_seconds": seconds,
         "recorded_evidence_cases": copy.deepcopy(gate[f"historical_cycle{cycle}_dependency_qualification"]["recorded_evidence_cases"])}
        for profile, digest, controls, cases, log, seconds, cycle in (
            ("physical_memory", "BB5C864CF76128B9D144D360B12792E70C0E2ED6A5986019328967A5B15CF0A8", 191, 191,
             "73D78CC992A80B448CB62D488AC4EFA73BF8EED5DBCA5B8F76C37B5AF855061A", 68.844, 186),
            ("virtual_memory", "2D2FC54F7AC8DB642E5F628CCF381F33C05100D9FE1D1245FE73374A114B2CAF", 48, 48,
             "3F150DB57A3859B6474CCAE0679F8D501C0B6264436950A77C7EDC5EE719DE52", 65.828, 187),
            ("interrupt_time", "9FED29AEE36D11165C2F800376DE4EC9BE0E558AB5225170908C6A176F19DE81", 58, 58,
             "047FF2DF6EB68D3816503F9E81C83FA820E6D47828691C1D6F48D6B95C2F54B1", 68.422, 188),
            ("smp_first_ap", "7B20241B707FBC077AA2DD937354E4347AD7952673491C9CA9A77EDD40C43401", 72, 72,
             "6A25DBB4AE5AC7A23E7328961F320F5551C3A189A91211F1B4C970530B8614E1", 71.031, 189),
            ("smp_percpu_runtime", "4C218EAAEB01673F7F0C45ED9DA92895E6EC564AA6A5EEAA57BFB09162F1B99B", 19, 159,
             "BEDC73DE58B81C522F0C0F23D34D0E0573C50C2BA8A22ADF37436DC4F4E4C890", 59.219, 190),
        )
    ]
    retained = copy.deepcopy(gate["current_dependency_qualification"])
    pending = [p for p in retained["readiness_replay_required_profiles"] if p not in {b["profile"] for b in bindings}]
    gate["current_dependency_qualification"] = {
        "cycle": 194, "source_validation_cycle": 194, "status": "six_current_profiles_eight_pending",
        "scope": "five_fresh_memory_IRQ_AP_profiles_plus_retained_Cycle192_IPI",
        "applies_to_current_source": True, "all_fourteen_profiles_current": False,
        "qualified_profiles": [b["profile"] for b in bindings] + ["smp_ipi"],
        "newly_qualified_profiles": [b["profile"] for b in bindings],
        "readiness_replay_required_profiles": pending,
        "fresh_qemu_runs": 10, "run_count_scope": "Cycle194_five_profiles_only_not_retained_IPI",
        "superseded_initial_runs": 0, "negative_control_groups": 388, "negative_control_cases": 528,
        "kernel_sha256": retained["kernel_sha256"],
        "receipt_bindings": bindings + retained["receipt_bindings"],
        "retained_IPI_qualification_record": "historical_cycle193_dependency_qualification",
        "recorded_evidence_case_total": 990, "recorded_evidence_scope": "five_fresh_profiles_only",
        "recorded_evidence_rejections_exercised_through_runtime_and_gate": True,
        "positive_receipts_rebound_in_tests": False, "pair_validation_is_freshness_or_authentication": False,
        "disabled_PMM_parser_and_memory_oracle_detected": True, "PMM_marker_validator_calls": 189,
        "control_execution_complete": False, "unproven_per_control_rejection_groups_at_least": 65,
        "current_candidate_full_gate_passed": False, "production_ready": False,
    }
    gate["current_ownership_qualification"] = dict(
        gate["current_ownership_qualification"], cycle=194,
        scope="host_and_IPI192_retained_with_fresh_active_root_VM194",
        fresh_current_cycle_qemu_runs=2, live_receipt_scope="two_VM194_runs_plus_retained_IPI192_not_fresh_IPI",
        active_root_current_image_replay_complete=True, virtual_memory_live_receipt_source_current=True,
        virtual_memory_live_replay_cycle=194, virtual_memory_receipt_sha256=bindings[1]["sha256"])
    test_log = "3D9CF2291DCB897F2ED2443A43C8819640BA3513C62A2EDF228B7601B907CE96"
    passing = gate["current_focused_source_projection"]["passing_profiles"]
    gate["current_focused_source_projection"] = {
        "cycle": 194, "scope": "27_selected_native_checks_not_full_canonical_audit",
        "passed_checks": 19, "total_checks": 27, "pending_downstream_native_checks": 8,
        "passing_profiles": passing[:-1] + ["native_kernel_" + b["profile"] + "_readiness" for b in bindings] + passing[-1:],
        "final_receipt_fresh_qemu_runs": 10, "kernel_entry_runs": 10, "superseded_initial_qemu_runs": 0,
        "run_count_scope": "Cycle194_five_memory_IRQ_AP_profiles_only_not_retained_CPU_boot_IPI",
        "next_dependency_move_id": next_move,
        "required_next_gate": "eight_scheduler_atomic_lock_profiles_control_execution_repair_then_full_candidate",
        "focused_python_tests_passed": 57, "focused_python_tests_skipped": 0,
        "focused_test_log_sha256": test_log, "recorded_evidence_rejection_cases": 990,
        "canonical_full_replay_performed": False, "production_ready": False,
    }
    gate["current_ipi_mailbox_oracle_gap"] = dict(
        gate["current_ipi_mailbox_oracle_gap"], cycle=194, remaining_affected_profiles=8,
        newly_requalified_profiles=[b["profile"] for b in bindings])
    gate["current_closeout_regression"] = {
        "cycle": 194, "status": "pass", "scope": "five_memory_IRQ_AP_profiles_not_full_canonical",
        "tests_run": 57, "tests_passed": 57, "tests_failed": 0, "tests_skipped": 0,
        "elapsed_seconds": 43.642, "log_sha256": test_log,
        "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        "disabled_PMM_parser_and_memory_oracle_detected": True,
        "preserved_measurement_helper_failure": "KeyError_qemu_run_count_IRQ_schema_uses_qemu_runs_total_corrected_by_counting_validated_runs",
        "initial_metadata_regression": {
            "tests_run": 42, "tests_passed": 42, "tests_failed": 0, "tests_skipped": 0,
            "log_sha256": "3715D1F869CCC7FCC802E760E20CAE4EDC95CBE66A92D349F2BE36AEDE2EB7C3",
        },
        "initial_combined_invocation": {
            "return_code": 2, "tests_run": 0,
            "classification": "unittest_rejected_test_names_after_interleaved_verbose_option_before_test_execution",
            "log_sha256": "E5BD949E09F100EBA3AF6986500A528EFC66CE300495179FC4558DC29BD5BE74",
        },
        "combined_regression": {
            "status": "pass", "scope": "memory_IRQ_AP_N7_entry_boot_mailbox_IPI_core_progress_checklist_publication_not_full_canonical",
            "tests_run": 307, "tests_passed": 307, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 289.696,
            "log_sha256": "2C98C22223D5F67165F3499344B0D0898A6913E609955666CDFDD389641D9FBA",
        },
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 194: " + checkpoint + " admits five fresh PMM/VM/IRQ/first-AP/per-CPU receipts on the "
        "unchanged Cycle192 kernel: ten guest boots, 388 control groups, 528 executed rejection cases "
        "and 246 kernel host tests per qualifier. All 57 focused tests pass, including 990 corrupted "
        "records through runtime and actual gates and disabled PMM parser/oracle detection."
    )
    gap = (
        "Selected readiness is 19/27, with eight scheduler-through-lock profiles pending from " + next_move +
        ". The 65 scheduler control-execution gaps and full exact-candidate qualification still block "
        "main merge. Retained IPI192 and CPU193 evidence is not fresh Cycle194 execution. No phase or "
        "flag closes; general task/CPU retirement, independent builders, hardware and production remain open."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N8", "N9", "N10", "N12", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 194 source inventory: 1044 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N9-PMM-ACPI-CONSUMER-001", "FLAG-N9-VM-DIRECT-MAP-001", "FLAG-N8-IRQ-001",
                          "FLAG-N8-SMP-FIRST-AP-001", "FLAG-N8-SMP-PERCPU-RUNTIME-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle195(roadmap, test_count)


def apply_cycle195(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle195-scheduler-recorded-evidence.md"
    next_move = "N12-SCHED-PREEMPT-001"
    roadmap["baseline"]["pooleos_cycle"] = 195
    protocol = roadmap["execution_protocol"]
    protocol.update(last_updated_cycle=195, selected_move_id="N12-SCHED-001",
                    owner_independent_next_move_id=next_move)
    protocol["required_records"][:0] = [checkpoint, "docs/checkpoints/cycle195-scheduler-cloud-backup.md"]
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for name in ("focused_source_projection", "dependency_qualification", "closeout_regression",
                 "candidate_audit", "ipi_mailbox_oracle_gap"):
        suffix = "source_projection" if name == "focused_source_projection" else name
        gate["historical_cycle194_" + suffix] = copy.deepcopy(gate["current_" + name])
    gate["qualification_status"] = "scheduler_evidence_pass_seven_dependencies_and_control_audit_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=195)
    gate["current_preemption_control_execution_audit"] = {
        "cycle": 195, "status": "open", "move_id": "N12-SCHED-PREEMPT-001",
        "requirement_id": "ADD-N36-RECEIPT-COVERAGE-001", "flag_id": "FLAG-N36-RECEIPT-COVERAGE-001",
        "blocks_merge_qualification": True, "profile": "scheduler_preempt",
        "scope": "one_additional_PKSCHED2_loop_without_per_control_rejection_calls",
        "source_path": "tools/qualify_native_kernel_scheduler_preempt.py",
        "source_sha256": "9461C3A0DE65CDEA1C9F1E31FAF7518225293E5B1DAFE2238C85D33DB6783473",
        "slice_start": 15, "slice_end": 24, "reported_case_count": 9,
        "control_ids": [
            "NEG-N12-PKSCHED2-INTERRUPT-FRAME-CONTRACT", "NEG-N12-PKSCHED2-CONTEXT-OWNERSHIP",
            "NEG-N12-PKSCHED2-EVENT-CAPACITY", "NEG-N12-PKSCHED2-EVENT-DEADLINE",
            "NEG-N12-PKSCHED2-EVENT-DUPLICATE", "NEG-N12-PKSCHED2-QUANTUM-BOUNDARY",
            "NEG-N12-PKSCHED2-TRANSACTIONAL-ROLLBACK", "NEG-N12-PKSCHED2-LINKED-SWITCH-SCOPE",
            "NEG-N12-PKSCHED2-RETAINED-STACK-PARTITION",
        ],
        "classification": "source_audit_attestation_without_per_control_rejection_execution",
        "loop_calls": ["controls.append"], "prior_audit_record": "current_control_execution_audit",
        "prior_audit_groups": 65, "aggregate_unproven_groups_at_least": 74,
        "native_preemption_defect_proved": False, "all_profile_control_execution_audited": False,
        "production_ready": False,
    }
    retained = gate["historical_cycle194_dependency_qualification"]
    binding = {
        "profile": "scheduler", "path": "runs/native-kernel-scheduler-readiness.json",
        "sha256": "0CA89C0F579FB5BA086ED61FF7D56B0F68E6C82A974B4698CFEA84F621B83363",
        "fresh_runs": 2, "negative_controls": 28, "hostile_cases": 115, "kernel_host_tests": 246,
        "execution_log_sha256": "8F867ACC242340662A5873DD9035F537409D16A81AF05268BEABE7274F48A33F",
        "elapsed_seconds": 87.578,
    }
    cases = {"exit": 14, "coverage": 16, "evidence": 23, "shape": 4, "profile": 8,
             "observation": 37, "summary": 26, "host-probe": 30, "controls": 57,
             "root-shape": 3, "control-shape": 3}
    before = {"cases": 219, "runtime_accepted": 172, "aggregate_gate_accepted": 100,
              "runtime_exceptions": 4, "aggregate_gate_exceptions": 9,
              "log_sha256": "04155A4918C88EC0251F4012000D8653DD16325996CE57451E74DCA25798F7A4"}
    after = {"cases": 219, "runtime_accepted": 0, "aggregate_gate_accepted": 0,
             "runtime_exceptions": 0, "aggregate_gate_exceptions": 0,
             "log_sha256": "2BA5A86349B0ADEB8E02B971473CDE3A036B6C34B18EA86CF32738B3FDBC9762"}
    test_log = "E58C5B0675259CBFDA13624156F7C6C24DDC46152986DEDF36E7AE0372F4C5DE"
    gate["current_dependency_qualification"] = {
        "cycle": 195, "source_validation_cycle": 195, "status": "seven_current_profiles_seven_pending",
        "scope": "fresh_scheduler_with_six_retained_memory_IRQ_AP_IPI_profiles",
        "applies_to_current_source": True, "all_fourteen_profiles_current": False,
        "qualified_profiles": retained["qualified_profiles"] + ["scheduler"],
        "newly_qualified_profiles": ["scheduler"],
        "readiness_replay_required_profiles": [p for p in retained["readiness_replay_required_profiles"] if p != "scheduler"],
        "fresh_qemu_runs": 2, "run_count_scope": "Cycle195_final_scheduler_only_not_retained_profiles",
        "superseded_initial_runs": 2, "negative_control_groups": 28, "negative_control_cases": 115,
        "kernel_sha256": retained["kernel_sha256"],
        "receipt_bindings": copy.deepcopy(retained["receipt_bindings"]) + [binding],
        "retained_qualification_record": "historical_cycle194_dependency_qualification",
        "recorded_evidence_cases": cases, "recorded_evidence_case_total": 221,
        "recorded_evidence_scope": "scheduler_only_including_six_malformed_root_control_cases",
        "recorded_evidence_rejections_exercised_through_runtime_and_gate": True,
        "pre_repair_counterexample": before, "post_repair_counterexample_replay": after,
        "per_control_case_counts_bound": True, "raw_host_probe_independently_reparsed": True,
        "typed_observation_and_summary_rederived": True, "disabled_validator_checks": 3,
        "rejected_output_preservation_cases": 2, "positive_receipts_rebound_in_tests": False,
        "pair_validation_is_freshness_or_authentication": False,
        "control_execution_complete": False, "unproven_per_control_rejection_groups_at_least": 74,
        "current_candidate_full_gate_passed": False, "production_ready": False,
    }
    gate["current_focused_source_projection"] = {
        "cycle": 195, "scope": "27_selected_native_checks_not_full_canonical_audit",
        "passed_checks": 20, "total_checks": 27, "pending_downstream_native_checks": 7,
        "passing_profiles": gate["historical_cycle194_source_projection"]["passing_profiles"] + ["native_kernel_scheduler_readiness"],
        "final_receipt_fresh_qemu_runs": 2, "kernel_entry_runs": 2, "superseded_initial_qemu_runs": 2,
        "run_count_scope": "Cycle195_final_scheduler_only_not_retained_profiles",
        "next_dependency_move_id": next_move,
        "required_next_gate": "seven_preemption_through_lock_profiles_control_execution_repair_then_full_candidate",
        "focused_python_tests_passed": 14, "focused_python_tests_skipped": 0,
        "focused_test_log_sha256": test_log, "recorded_evidence_rejection_cases": 221,
        "canonical_full_replay_performed": False, "production_ready": False,
    }
    gate["current_ipi_mailbox_oracle_gap"] = dict(
        gate["current_ipi_mailbox_oracle_gap"], cycle=195, remaining_affected_profiles=7,
        newly_requalified_profiles=["scheduler"])
    gate["current_closeout_regression"] = {
        "cycle": 195, "status": "pass", "scope": "scheduler_recorded_evidence_and_executed_controls_only",
        "tests_run": 14, "tests_passed": 14, "tests_failed": 0, "tests_skipped": 0,
        "elapsed_seconds": 16.423, "log_sha256": test_log,
        "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        "disabled_validator_checks": 3, "rejected_output_preservation_cases": 2,
        "pre_repair_counterexample": copy.deepcopy(before),
        "post_repair_counterexample_replay": copy.deepcopy(after),
        "initial_payload_regression": {
            "tests_run": 4, "tests_passed": 2, "tests_failed": 1, "tests_errored": 1,
            "classification": "old_public_scheduler_fixture_had_stale_kernel_entry_identity",
            "log_sha256": "75F703268BC6B22151A302382B24B24DD65EEFE58B0AF2D76F2981AD8F8AD4FB",
        },
        "cloud_backup_regression": {
            "tests_run": 23, "tests_passed": 23, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 105.171,
            "log_sha256": "9AC6DE2CD459085794B28E5DF9B85614C456BEC207ED44B40CC7328FF151BD1F",
        },
        "combined_regression": {
            "status": "pass", "scope": "scheduler_memory_IRQ_AP_N7_entry_boot_mailbox_IPI_core_progress_publication_not_full_canonical",
            "tests_run": 322, "tests_passed": 322, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 303.618,
            "log_sha256": "C8B15D4B8BF19675781D0C5C2F7B22DF7111E01F41065D1F2CED90292831C40A",
            "final_metadata_replay_required_after_supplemental_preemption_audit": True,
        },
        "initial_metadata_regression": {
            "tests_run": 43, "tests_passed": 42, "tests_failed": 1, "tests_skipped": 0,
            "classification": "historical_entry_test_still_expected_current_scheduler_receipt_to_be_stale",
            "log_sha256": "F518887F1351092BC2AADC32A1388191921DF9122AC03513BBB58CCD53336A20",
        },
        "corrected_metadata_regression": {
            "tests_run": 43, "tests_passed": 43, "tests_failed": 0, "tests_skipped": 0,
            "log_sha256": "FA5B3191D619D6AF939D0C57572B85BB0E64A40294FE2FA6BC99CB6506CF0C0B",
        },
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 195: " + checkpoint + " qualifies strict scheduler recorded-evidence admission on the "
        "unchanged Cycle192 kernel. Two final boots, 115 executed rejection cases in 28 groups and "
        "246 kernel host tests pass. Fourteen focused tests reject 221 corruptions through runtime "
        "and actual gate, detect three disabled validators and preserve rejected output. The original "
        "219 counterexamples all reject without exceptions; initial acceptance and failures remain history."
    )
    gap = (
        "Selected readiness is 20/27; seven profiles remain from " + next_move +
        ". Nine newly verified constant-only preemption control records add to the prior 65, "
        "leaving at least 74 scheduler control-execution gaps. These and full exact-candidate qualification still "
        "block main merge. Retained memory/AP/IPI/CPU evidence is not fresh scheduler execution. "
        "Recorded consistency is not authentication or freshness. No phase or flag closes; native "
        "general task/CPU retirement, independent builders, hardware and production remain open."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N12", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 195 source inventory: 1050 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N12-SCHED-FOUNDATION-001", "FLAG-N12-SCHED-PREEMPT-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle196(roadmap, test_count)


def apply_cycle196(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle196-preemption-executed-controls.md"
    next_move = "N12-SCHED-DEFERRED-001"
    roadmap["baseline"]["pooleos_cycle"] = 196
    protocol = roadmap["execution_protocol"]
    protocol.update(last_updated_cycle=196, selected_move_id="N12-SCHED-PREEMPT-001",
                    owner_independent_next_move_id=next_move)
    protocol["required_records"].insert(0, checkpoint)
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for name in ("focused_source_projection", "dependency_qualification", "closeout_regression",
                 "candidate_audit", "ipi_mailbox_oracle_gap", "preemption_control_execution_audit"):
        suffix = "source_projection" if name == "focused_source_projection" else name
        gate["historical_cycle195_" + suffix] = copy.deepcopy(gate["current_" + name])
    gate["qualification_status"] = "preemption_controls_pass_six_dependencies_and_full_candidate_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=196)
    binding = {
        "profile": "scheduler_preempt", "path": "runs/native-kernel-scheduler-preemption-readiness.json",
        "sha256": "2DFF24BCF02069ADB74E78F53F63A1F3EBF2C1EB478F2DBFF7D27D31E9FD757B",
        "fresh_runs": 2, "negative_controls": 25, "hostile_cases": 226, "kernel_host_tests": 246,
        "execution_log_sha256": "C4CA732801FB906F7442652BE154022EA0C59C4E633C31145D785E2F4E5A52F5",
        "elapsed_seconds": 119.953,
    }
    test_log = "3691DE7B42E0F1DE99AFB5C59FE41C7AD4B87F741445B8F78404CCD260C9396F"
    cases = {"exit": 14, "coverage": 16, "evidence": 23, "shape": 4, "profile": 8,
             "observation": 48, "summary": 22, "host-probe": 14, "controls": 51,
             "root-shape": 3, "control-shape": 3}
    retained = gate["historical_cycle195_dependency_qualification"]
    gate["current_dependency_qualification"] = {
        "cycle": 196, "source_validation_cycle": 196, "status": "eight_current_profiles_six_pending",
        "scope": "fresh_preemption_with_seven_retained_memory_IRQ_AP_IPI_scheduler_profiles",
        "applies_to_current_source": True, "all_fourteen_profiles_current": False,
        "qualified_profiles": retained["qualified_profiles"] + ["scheduler_preempt"],
        "newly_qualified_profiles": ["scheduler_preempt"],
        "readiness_replay_required_profiles": [p for p in retained["readiness_replay_required_profiles"] if p != "scheduler_preempt"],
        "fresh_qemu_runs": 2, "run_count_scope": "Cycle196_final_preemption_only_not_retained_profiles",
        "superseded_initial_runs": 4, "negative_control_groups": 25, "negative_control_cases": 226,
        "kernel_sha256": retained["kernel_sha256"],
        "receipt_bindings": copy.deepcopy(retained["receipt_bindings"]) + [binding],
        "retained_qualification_record": "historical_cycle195_dependency_qualification",
        "recorded_evidence_cases": cases, "additional_control_receipt_corruptions": 26,
        "recorded_evidence_case_total": 232, "recorded_evidence_scope": "206_generic_and26_executed_control_receipt_cases",
        "recorded_evidence_rejections_exercised_through_runtime_and_gate": True,
        "native_control_groups": 7, "native_control_cases": 50,
        "linked_scope_control_cases": 3, "stack_source_guard_control_cases": 4,
        "disabled_native_validator_variants_detected": 7, "disabled_auditors_detected": 2,
        "disabled_marker_validator_detected": True, "rejected_output_preservation_cases": 2,
        "per_control_case_counts_bound": True, "raw_host_probe_independently_reparsed": True,
        "typed_observation_and_summary_rederived": True, "positive_receipts_rebound_in_tests": False,
        "pair_validation_is_freshness_or_authentication": False,
        "control_execution_complete": False, "unproven_per_control_rejection_groups_at_least": 65,
        "current_candidate_full_gate_passed": False, "production_ready": False,
    }
    gate["current_preemption_control_execution_audit"] = {
        "cycle": 196, "status": "repaired_with_bounded_executed_controls", "profile": "scheduler_preempt",
        "move_id": "N12-SCHED-PREEMPT-001", "requirement_id": "ADD-N36-RECEIPT-COVERAGE-001",
        "flag_id": "FLAG-N36-RECEIPT-COVERAGE-001", "historical_finding": "historical_cycle195_preemption_control_execution_audit",
        "repaired_groups": 9, "native_host_cases": 50, "linked_scope_cases": 3, "stack_source_guard_cases": 4,
        "disabled_native_variants_detected": 7, "disabled_auditors_detected": 2,
        "receipt_path": binding["path"], "receipt_sha256": binding["sha256"],
        "aggregate_unproven_groups_at_least": 65, "all_profile_control_execution_audited": False,
        "privileged_hardware_fault_injection": False, "native_kernel_bytes_changed": False,
        "production_ready": False,
    }
    gate["current_focused_source_projection"] = {
        "cycle": 196, "scope": "27_selected_native_checks_not_full_canonical_audit",
        "passed_checks": 21, "total_checks": 27, "pending_downstream_native_checks": 6,
        "passing_profiles": gate["historical_cycle195_source_projection"]["passing_profiles"] + ["native_kernel_scheduler_preemption_readiness"],
        "final_receipt_fresh_qemu_runs": 2, "kernel_entry_runs": 2, "superseded_initial_qemu_runs": 4,
        "run_count_scope": "Cycle196_final_preemption_only_not_retained_profiles",
        "next_dependency_move_id": next_move,
        "required_next_gate": "six_deferred_through_lock_profiles_remaining_control_execution_then_full_candidate",
        "focused_python_tests_passed": 17, "focused_python_tests_skipped": 0,
        "focused_test_log_sha256": test_log, "recorded_evidence_rejection_cases": 232,
        "canonical_full_replay_performed": False, "production_ready": False,
    }
    gate["current_ipi_mailbox_oracle_gap"] = dict(gate["current_ipi_mailbox_oracle_gap"], cycle=196,
        remaining_affected_profiles=6, newly_requalified_profiles=["scheduler_preempt"])
    gate["current_closeout_regression"] = {
        "cycle": 196, "status": "pass", "scope": "preemption_recorded_evidence_and_executed_controls_only",
        "tests_run": 17, "tests_passed": 17, "tests_failed": 0, "tests_skipped": 0,
        "elapsed_seconds": 18.887, "log_sha256": test_log,
        "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        "initial_diagnostic_baseline": {"genuine_runs": 2, "constant_only_groups": 9, "admitted_as_final": False,
            "log_sha256": "F27418BA8A30BC7A9D927DC2294764FE85E00991A54F2E600DE91D841DF6EA1D"},
        "superseded_repaired_receipt": {"genuine_runs": 2, "reason": "added_shared_validator_source_bindings_before_final_requalification",
            "sha256": "164474EBF4F39568FB862ED1CAEB091D67286C83ED9D1D4D6842564F78B75925",
            "focused_tests_passed": 17, "test_log_sha256": "87E27BB3D7BF81C7DA72F8DA92612D5A12CF179CE9D33B2F6D8842A3F04B9880"},
        "initial_runner_invocation": {"return_code": 2, "tests_run": 0, "classification": "mistaken_nonexistent_script_argument_before_test_execution",
            "log_sha256": "453A2C314D2DE1B07BF0BA1C1264761D5302666CAFFDC24C83F1C0E9A26B7E63"},
        "pre_repair_corruption_acceptance_audit_performed": False,
        "combined_regression": {"status": "pass", "scope": "preemption_scheduler_memory_IRQ_AP_CPU_entry_boot_mailbox_core_progress_publication_not_full_canonical",
            "tests_run": 339, "tests_passed": 339, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 305.449,
            "log_sha256": "A4D0AA0BCE12B72DF1E456052D10EB8D54132371E2391CA524E121492CD9A800"},
        "corrected_metadata_regression": {"tests_run": 43, "tests_passed": 43, "tests_failed": 0, "tests_skipped": 0,
            "log_sha256": "5C8B473007606E357FF95139D1EA1DB9FD5C87638C5184DDCB341475758E2687"},
        "second_metadata_regression": {"tests_run": 43, "tests_passed": 41, "tests_failed": 2, "tests_skipped": 0,
            "classification": "two_remaining_old_selected_and_pending_count_assertions",
            "log_sha256": "FDD9E51069EC121555660AE685A86169F2B1B9480C1D151D86FC6FB6038D9523"},
        "initial_metadata_regression": {"tests_run": 43, "tests_passed": 38, "tests_failed": 5, "tests_skipped": 0,
            "classification": "old_pending_counts_historical_preemption_receipt_and_architecture_count_assertions",
            "log_sha256": "AA017E30138D78D74C1EC897A00BE2A2754C2AEC752709A427CED9620761188B"},
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 196: " + checkpoint + " qualifies strict preemption recorded evidence and replaces nine "
        "constant-only control groups. Two final boots, 246 kernel host tests, 226 executed rejection "
        "cases and 17 focused tests pass, including 232 corrupt receipts and seven native disabled-check variants."
    )
    gap = (
        "Selected readiness is 21/27; six profiles remain from " + next_move + ". At least 65 control-execution "
        "gaps remain in four later qualifiers, alongside full exact-candidate qualification before main merge. "
        "Native controller tests run on the host; linked and stack-source audits are not hardware faults. "
        "Native kernel bytes are unchanged. No phase or flag closes; N12/N36, independent builders, hardware "
        "and production remain open. Historical runs and retained profiles are not fresh Cycle196 final evidence."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N12", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 196 source inventory: 1060 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N12-SCHED-PREEMPT-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle197(roadmap, test_count)


def apply_cycle197(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle197-native-deferred-transactions.md"
    kernel_sha = "B19D4F7E854ECED3495D88C00F7379061B913EF00477FBD3701929B2F77D80F1"
    core_sha = "23E8AEC41CEDD9804EBD24023B4DFC68318AC13BD6DF9DCFD531B1A21A0F5BFE"
    entry_sha = "70814DA7358BEE6FA6E5D2341D251ACE57A906BA4FB2E9E12BD8D53677C7E38D"
    next_move = "N5-SYMBOLS-SEMANTICS-001"
    roadmap["baseline"]["pooleos_cycle"] = 197
    protocol = roadmap["execution_protocol"]
    protocol.update(last_updated_cycle=197, selected_move_id="N12-SCHED-DEFERRED-001",
                    owner_independent_next_move_id=next_move)
    protocol["required_records"].insert(0, checkpoint)
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for key, value in list(gate.items()):
        if key.startswith("current_") and isinstance(value, dict):
            suffix = "source_projection" if key == "current_focused_source_projection" else key.removeprefix("current_")
            gate["historical_cycle196_" + suffix] = copy.deepcopy(value)
    gate["qualification_status"] = "native_deferred_transactions_repaired_changed_image_replay_and_receipt_controls_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=197)
    gate["current_focused_source_projection"] = {
        "cycle": 197, "scope": "27_selected_native_checks_not_full_canonical_audit",
        "passed_checks": 3, "total_checks": 27, "pending_downstream_native_checks": 24,
        "passing_profiles": ["native_kernel_entry_readiness", "native_policy_readiness", "native_kernel_errata_policy_readiness"],
        "final_receipt_fresh_qemu_runs": 0, "kernel_entry_runs": 0,
        "prior_kernel_diagnostic_qemu_runs": 2, "diagnostic_is_final_qualification": False,
        "next_dependency_move_id": next_move,
        "required_next_gate": "ordered_changed_image_replay_then_deferred_admission_and_executed_controls_then_full_candidate",
        "focused_python_tests_passed": 54, "focused_python_tests_skipped": 0,
        "native_transaction_tests_per_profile": 21, "native_transaction_host_profiles": 2,
        "canonical_full_replay_performed": False, "production_ready": False,
    }
    pending_profiles = {
        "boot_chain": ["symbol", "kernel_load", "pooleboot", "kernel_revalidation", "kernel_transfer"],
        "cpu": ["trap", "cpu_policy", "xstate_policy", "xstate_exception", "privilege_msr_policy"],
        "dependency": ["physical_memory", "virtual_memory", "interrupt_time", "smp_first_ap", "smp_percpu_runtime",
                       "smp_ipi", "scheduler", "scheduler_preempt", "scheduler_deferred", "scheduler_smp",
                       "scheduler_ap_workers", "scheduler_smp_preempt", "atomics", "locks"],
    }
    for group, profiles in pending_profiles.items():
        gate["current_" + group + "_qualification"] = {
            "cycle": 197, "source_validation_cycle": 197, "status": "source_requalification_required",
            "applies_to_current_source": False, "kernel_sha256": kernel_sha,
            "historical_record": "historical_cycle196_" + group + "_qualification",
            "qualified_profiles": [], "readiness_replay_required_profiles": profiles,
            "fresh_qemu_runs": 0, "receipt_bindings": [], "embedded_entry_provenance_replay_pending": True,
            "all_fourteen_profiles_current": False, "control_execution_complete": False,
            "unproven_per_control_rejection_groups_at_least": 65,
            "current_candidate_full_gate_passed": False, "production_ready": False,
        }
    gate["current_entry_provenance_qualification"] = dict(
        gate["current_entry_provenance_qualification"], cycle=197, source_validation_cycle=197,
        linked_byte_count=7042768, linked_sha256="907EACFD6BC6D5669CA88489BC4A3E1121ED52F648FE434D3C05A4CB606C345A",
        canonical_sha256=kernel_sha, entry_receipt_sha256=entry_sha,
        latest_reproduction_cycle=197,
    )
    gate["current_task_stack_qualification"] = dict(
        gate["current_task_stack_qualification"], cycle=197, receipt_sha256=core_sha)
    gate["current_execution_qualification"] = dict(
        gate["current_execution_qualification"], cycle=197, receipt_sha256=core_sha, kernel_sha256=kernel_sha)
    gate["current_ownership_qualification"] = dict(
        gate["current_ownership_qualification"], cycle=197, host_qualification_cycle=197,
        scope="host197_only_prior_IPI_and_VM_receipts_historical", kernel_sha256=kernel_sha,
        reclamation_receipt_sha256=core_sha, entry_receipt_sha256=entry_sha,
        fresh_current_cycle_qemu_runs=0, live_receipt_source_current=False,
        current_boot_artifact_set_replay_pending=True, active_root_current_image_replay_complete=False,
        ap_runtime_live_integration_verified=False, virtual_memory_live_receipt_source_current=False,
        live_receipt_scope="historical_IPI192_and_VM194_not_current_kernel_execution",
        source_current_scope="host_core_and_entry_only", historical_record="historical_cycle196_ownership_qualification",
    )
    gate["current_ipi_mailbox_oracle_gap"] = dict(
        gate["current_ipi_mailbox_oracle_gap"], cycle=197, remaining_affected_profiles=24,
        newly_requalified_profiles=[], current_kernel_live_replay_pending=True)
    gate["current_preemption_control_execution_audit"] = dict(
        gate["current_preemption_control_execution_audit"], current_kernel_live_replay_pending=True,
        current_receipt_admitted=False)
    gate["current_deferred_transaction_qualification"] = {
        "cycle": 197, "move_id": "N12-SCHED-DEFERRED-001",
        "requirements": ["ADD-N12-SCHED-DEFERRED-001", "ADD-N36-RECEIPT-COVERAGE-001"],
        "status": "native_host_repairs_verified_live_and_recorded_admission_pending",
        "scope": "single_controller_state_transactions_not_cross_CPU_atomicity",
        "initial_native_tests": 19, "initial_native_passed": 8, "initial_native_failed": 11,
        "initial_log_sha256": "91AF75227D825FE8F7DF3AC9E9AAB18C9C50901C0BFBCE3A4C7CE9D9E8215220",
        "same_tests_after_repair_passed": 19,
        "same_tests_after_log_sha256": "DEA2DEEFCAB48E4BCBE8ACF5D913236DA3B6BC926D97EC2CF447718EED8B18A1",
        "final_native_tests_per_profile": 21, "host_optimization_levels": [0, 3],
        "disabled_native_variants_detected": 4, "focused_python_test_methods": 2,
        "final_test_log_sha256": "26DE0DFB7FEFB5C368F2B76CF84142F6AC86B8C42DAE872EA03B7396270FC45D",
        "sources": {
            "native/kernel/src/scheduler_deferred.rs": "1F8AE8F0521C08DDAE73BBADB16E91B33235129FCC695191AF83A98ABDD8786E",
            "tests/fixtures/pksched3_transaction_probe.rs": "C500335DAA70341FF5709770EECB8C77ABB01FC8E1DEAFFCFDF12AA06D324B8D",
            "tests/test_native_deferred_transactions.py": "FF86678E2ECE734813E67AAD89D5AA3E6B1384C29AB5FD6A2C46FFB2E89AB654",
        },
        "kernel_sha256": kernel_sha, "kernel_bytes_changed": True,
        "core_receipt_sha256": core_sha, "entry_receipt_sha256": entry_sha,
        "genuine_before_audit": {
            "baseline_sha256": "CFAE9962A392540B7DFED0C94E174FC48E51DAEFC423B70DCDFD182EAFC22709",
            "audit_sha256": "FE54D3F330EF99C6367F01336AD7D0DD909F3CAC07B91B1E603763F39BED5D5F",
            "positive_runtime_and_gate": True, "cases": 121,
            "runtime_accepted": 114, "runtime_rejected": 3, "runtime_exceptions": 4,
            "gate_accepted": 47, "gate_rejected": 73, "gate_exceptions": 1,
            "prior_kernel_runs": 2, "reported_control_groups": 30, "reported_cases": 208,
            "constant_only_groups": 14, "admitted_as_final": False,
        },
        "recorded_evidence_admission_repaired": False, "constant_only_control_groups_replaced": 0,
        "new_kernel_qemu_runs": 0, "cross_cpu_atomicity_proved": False,
        "production_ready": False,
    }
    gate["current_closeout_regression"] = {
        "cycle": 197, "status": "pass", "scope": "native_deferred_core_entry_host_provenance_publication_and_entry_gate_not_full_canonical",
        "tests_run": 54, "tests_passed": 54, "tests_failed": 0, "tests_skipped": 0,
        "focused_suite": {"tests_run": 53, "elapsed_seconds": 115.797,
            "log_sha256": "42D04FDE2D8E64FEF457773D430D874258DA593C14A74DE1A4DC9CC104838DF7"},
        "entry_gate": {"tests_run": 1, "rejection_cases": 12,
            "log_sha256": "208927165B913AA833216B549755DC2F394BBC064E44FCF4AABEA2281672AE34"},
        "initial_metadata_regression": {
            "tests_run": 36, "tests_passed": 31, "tests_failed": 5, "tests_skipped": 0,
            "elapsed_seconds": 6.844,
            "log_sha256": "83202FF14EDE1F534879D537ED10B5B2C0D9B563441AF3AF352B773AD690DB00",
            "cause": "five_historical_profile_tests_incorrectly_expected_old_image_receipts_to_remain_current",
            "repair": "require_stale_embedded_entry_rejection_and_false_current_gate_without_rebinding_old_receipts",
        },
        "corrected_metadata_regression": {
            "tests_run": 44, "tests_passed": 44, "tests_failed": 0, "tests_skipped": 0,
            "scope": "roadmap_architecture_and_locked_checklist_not_full_canonical",
            "elapsed_seconds": 8.297,
            "log_sha256": "474C2C4792E4322663DB560DDD56279DD7E5DE1806ABC0D2489D16B7F08DE9AF",
        },
        "core": {"stages_passed": 17, "elapsed_seconds": 37.578,
            "log_sha256": "2AB8D226E34E1EC1FD773B540A39E2E660DA56CAD8E6063453F24A14CBE3DD9D"},
        "entry": {"clean_builds": 2, "rejection_cases": 43, "elapsed_seconds": 38.609,
            "log_sha256": "5B006AC3BCB5E5F7BF1AB0368F017F13585D71B9400A5817324AEFEACAC5F53A"},
        "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 197: " + checkpoint + " repairs native deferred state transactions, fault fairness and shutdown order. "
        "Eleven original native failures now pass; expanded 21-case debug/optimized runs and four disabled variants pass. "
        "All 17 core stages, two matching kernel builds, 43 entry controls and 54 scoped Python tests pass."
    )
    gap = (
        "Kernel bytes changed; selected readiness is 3/27 and 24 dependencies need ordered replay from " + next_move + ". "
        "The genuine 121-case deferred admission audit accepted 114 corruptions in runtime and 47 at the gate, with "
        "four runtime exceptions and one gate exception. These admission defects and 14 constant-only deferred "
        "groups remain open within the existing 65-group lower bound. Repair admission and execute controls before "
        "new deferred qualification, then full exact-candidate qualification before main merge. No new-kernel guest "
        "boot, independent builder, ISO, phase closure or production promotion is claimed."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N5", "N6", "N12", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 197 source inventory: 1063 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N12-SCHED-DEFERRED-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
            flag["status"] = "open"
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle198(roadmap, test_count)


def apply_cycle198(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle198-symbol-admission-and-boot-replay.md"
    kernel_sha = "B19D4F7E854ECED3495D88C00F7379061B913EF00477FBD3701929B2F77D80F1"
    roadmap["baseline"]["pooleos_cycle"] = 198
    protocol = roadmap["execution_protocol"]
    protocol.update(last_updated_cycle=198, selected_move_id="N5-SYMBOLS-SEMANTICS-001",
                    owner_independent_next_move_id="N7-TRAP-001")
    protocol["required_records"].insert(0, checkpoint)
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for key, value in list(gate.items()):
        if key.startswith("current_") and isinstance(value, dict):
            suffix = "source_projection" if key == "current_focused_source_projection" else key.removeprefix("current_")
            gate["historical_cycle197_" + suffix] = copy.deepcopy(value)
    gate["qualification_status"] = "symbol_admission_repaired_boot_chain_current_CPU_and_downstream_replay_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=198)
    gate["current_focused_source_projection"] = {
        "cycle": 198, "scope": "27_selected_native_checks_not_full_canonical_audit",
        "passed_checks": 8, "total_checks": 27, "pending_downstream_native_checks": 19,
        "passing_profiles": ["native_kernel_entry_readiness", "native_symbol_readiness", "native_policy_readiness",
            "native_kernel_load_readiness", "native_pooleboot_readiness", "native_kernel_revalidation_readiness",
            "native_kernel_transfer_readiness", "native_kernel_errata_policy_readiness"],
        "final_receipt_fresh_qemu_runs": 6, "kernel_entry_runs": 2,
        "failed_transfer_qualification_attempts": 1, "failed_attempts_counted_as_final": False,
        "next_dependency_move_id": "N7-TRAP-001", "required_next_gate": "ordered_CPU_then_memory_SMP_scheduler_and_full_candidate",
        "focused_python_tests_passed": 80, "focused_python_tests_skipped": 0,
        "canonical_full_replay_performed": False, "production_ready": False,
    }
    rows = (
        ("symbol", "runs/native_symbol_readiness.json", "BDCFD2F4D6BA8E7AAAF4AB2BFAB31DE9F7C93D1D8D40B73BCDE02D83E4A6745F", 0, 158),
        ("policy", "runs/native_policy_readiness.json", "03DE511F444A52AD00102BBA6603D6A2C90A05CCB228B149700077FE78C8ACEF", 0, 116),
        ("kernel_load", "runs/native_kernel_load_readiness.json", "B93A612535CE764C22FD632B0C7DA6F5D119B4CB51D6DB3CAB3FC4B077A554F4", 2, 155),
        ("pooleboot", "runs/native_pooleboot_readiness.json", "BC7DBB6A019207226E3F8F777285FD18E9C6F34F60CA65DAABFED7E118DBC8FE", 2, 155),
        ("kernel_revalidation", "runs/native-kernel-revalidation-readiness.json", "0A08098BE8E6106CDE8A88F1CF3A14C0565262444C57B9F5B9882B0578977726", 0, 36),
        ("kernel_transfer", "runs/native-kernel-transfer-readiness.json", "ED27A60D7CE19CE22BC174E326F736B22A4282315948AF435740247BD652E943", 2, 58),
    )
    gate["current_boot_chain_qualification"] = {
        "cycle": 198, "source_validation_cycle": 198, "status": "single_host_replay_pass",
        "applies_to_current_source": True, "kernel_sha256": kernel_sha,
        "qualified_profiles": [row[0] for row in rows], "readiness_replay_required_profiles": [],
        "receipt_bindings": [dict(profile=p, path=path, sha256=sha, fresh_runs=runs, negative_controls=controls)
                             for p, path, sha, runs, controls in rows],
        "prerequisite_receipt_bindings": copy.deepcopy(gate["historical_cycle196_boot_chain_qualification"]["prerequisite_receipt_bindings"]),
        "fresh_qemu_runs": 6, "kernel_entry_runs": 2, "failed_transfer_qualification_attempts": 1,
        "kernel_host_tests": 246, "loader_host_tests": 331, "pooleboot_host_tests": 8,
        "focused_python_tests": 80, "focused_python_passed": 80, "focused_python_skipped": 0,
        "retained_file_count": 9, "inner_artifact_bytes": 8761, "retained_bytes": 11952, "manifest_bytes": 2615,
        "inner_set_sha256": "A50F908DB5C6C4119FDECD0D267E4D06BEE3626F9AE209B94B5A99DC3453F5EE",
        "trust_policy_sha256": "B8B49BBD847C28832458B9B375067191AA204620411D9ADBDAD653F757EFB7AD",
        "trust_state_sha256": "6D5A23B7DAD78CF9659AD4F839BCA96CF0D6A5E74FEFC4C364542BF98E2D4B30",
        "real_image_trust_independently_reconstructed": True, "golden_fixture_is_actual_kernel": False,
        "additional_superseded_identity_rejection_cases": 5, "rejected_symbol_output_preservation_cases": 2,
        "receipt_generation_semantically_validated": True, "receipt_write_semantically_validated": True,
        "complete_host_attestation": False, "second_builder_reproduced": False,
        "n5_exit_gate_satisfied": False, "current_candidate_full_gate_passed": False, "production_ready": False,
    }
    gate["current_symbol_admission_qualification"] = {
        "cycle": 198, "move_id": "N5-SYMBOLS-SEMANTICS-001", "phases": ["N5.6", "N5.9", "N36"],
        "requirement_id": "ADD-N36-RECEIPT-COVERAGE-001", "status": "bounded_recorded_consistency_repaired",
        "pre_repair_counterexample": {
            "cases": 646, "runtime_accepted": 494, "runtime_rejected": 146, "runtime_exceptions": 6,
            "aggregate_gate_accepted": 467, "aggregate_gate_rejected": 168, "aggregate_gate_exceptions": 11,
            "genuine_source_current_positive": True,
            "baseline_sha256": "AD6E3CE46B0DD427FD05F7C883F21D457A6E33114468B5A349E413E01F635BC3",
            "audit_sha256": "9579C1F23835AA04213EAA5FBACFFFB3D91FB47AD9BBD26C7D71A064F981ADAC",
        },
        "post_repair_counterexample_replay": {
            "cases": 650, "additional_bound_test_source_cases": 4, "runtime_accepted": 0,
            "aggregate_gate_accepted": 0, "runtime_exceptions": 0, "aggregate_gate_exceptions": 0,
            "runtime_rejected": 650, "aggregate_gate_rejected": 650, "genuine_source_current_positive": True,
            "audit_sha256": "36FB7996B5900AA5309D4D36BED173E3170B10D33752B4EB2F676CF4C8B44DFF",
        },
        "symbol_receipt_sha256": rows[0][2], "debug_builds_byte_identical": 2,
        "native_parser_tests": 4, "native_control_cases": 158,
        "parser_differential_cases": 16384, "lookup_differential_cases": 16384,
        "parser_and_activation_results_reconstructed": True, "typed_counts_and_schema_bindings_required": True,
        "rejected_output_preservation_cases": 2, "coherent_forgery_excluded": False,
        "recorded_consistency_is_freshness_or_authentication": False, "production_ready": False,
    }
    gate["current_entry_provenance_qualification"] = dict(
        gate["current_entry_provenance_qualification"], latest_reproduction_cycle=198)
    gate["current_ownership_qualification"] = dict(
        gate["current_ownership_qualification"], current_boot_artifact_set_replay_pending=False,
        boot_artifact_replay_cycle=198, source_current_scope="host197_and_boot198_not_AP_or_VM_execution")
    gate["current_ipi_mailbox_oracle_gap"] = dict(
        gate["current_ipi_mailbox_oracle_gap"], cycle=198, remaining_affected_profiles=19,
        newly_requalified_profiles=[row[0] for row in rows])
    gate["current_closeout_regression"] = {
        "cycle": 198, "status": "pass", "scope": "symbols_policy_boot_chain_and_host_provenance_not_full_canonical",
        "tests_run": 80, "tests_passed": 80, "tests_failed": 0, "tests_skipped": 0,
        "elapsed_seconds": 41.922, "log_sha256": "91BBF055CB2621D81187217AF33EE20D5AAFA11B9AA523F2110B5C3EE1F2D110",
        "failed_initial_transfer": {"attempts": 1, "elapsed_seconds": 65.265,
            "cause": "transfer_validator_still_expected_Cycle192_build_ID", "counted_as_final": False,
            "log_sha256": "DAF6047EE00735EFABF4488868E00CDE18E893A981B43DCED4805A8D9AD84001"},
        "failed_identity_regression": {"tests_run": 1, "tests_failed": 1,
            "log_sha256": "93BAABAC162111DB1EFD91A9B2AE3F264C57E541611AEFCBFD0649F020C9477F"},
        "corrected_identity_regression": {"tests_run": 3, "tests_passed": 3,
            "log_sha256": "23B0697B19316561BA774F5AB43575EA4108F2584824F0F3774A0DC040AB37E7"},
        "corrected_transfer": {"runs_passed": 2, "rejection_cases": 58, "elapsed_seconds": 70.047,
            "log_sha256": "8B0DC768FA17D4F061480465E17227A21EF363B5E3DA3FA0B47215DC26AF6421"},
        "metadata_regression": {"tests_run": 45, "tests_passed": 45, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 8.828,
            "log_sha256": "5C0B1A973FEF8E15E88040442B792382F65A8D68F8CC2A40C2CB204BB4EB2DBE"},
        "combined_regression": {"tests_run": 178, "tests_passed": 178, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 160.688,
            "log_sha256": "5165D872B28A0BA9A770450DF9FCA3690AAF6775B129301A2EE98321A6B42617",
            "scope": "scoped_regression_including_kernel_reproduction_not_full_canonical_suite"},
        "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 198: " + checkpoint + " repairs symbol recorded-evidence admission and stale transfer build identity. "
        "A genuine 646-case before audit admitted 494 corruptions in runtime and 467 at the gate, with six/eleven exceptions; "
        "all 650 final corruptions reject with zero exceptions. Two matching symbol builds, 158 controls, two 16384-case "
        "symbol campaigns, six fresh final boot runs and 80 scoped Python tests pass. Kernel bytes are unchanged."
    )
    gap = (
        "Selected current readiness is 8/27; 19 CPU and downstream dependencies need replay from N7-TRAP-001. "
        "Deferred recorded admission and at least 65 scheduler control-execution groups remain open. "
        "Preserve the failed initial transfer and one failing identity test; neither counts as final evidence. "
        "Recorded consistency is not authentication, independent reproduction or production readiness. "
        "Full exact-candidate canonical/Doctor/publication/configured-check/review qualification precedes main merge."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N5", "N6", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 198 source inventory: 1066 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N5-SYMBOL-BUNDLE-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle199(roadmap, test_count)


def apply_cycle199(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle199-cpu-control-admission-and-replay.md"
    next_move = "N9-PMM-ACPI-CONSUMER-001"
    roadmap["baseline"]["pooleos_cycle"] = 199
    protocol = roadmap["execution_protocol"]
    protocol.update(last_updated_cycle=199, selected_move_id="N7-TRAP-001",
                    owner_independent_next_move_id=next_move)
    protocol["required_records"].insert(0, checkpoint)
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for key, value in list(gate.items()):
        if key.startswith("current_") and isinstance(value, dict):
            suffix = "source_projection" if key == "current_focused_source_projection" else key.removeprefix("current_")
            gate["historical_cycle198_" + suffix] = copy.deepcopy(value)
    gate["qualification_status"] = "CPU_control_admission_repaired_five_current_profiles_fourteen_dependencies_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=199)
    rows = (
        ("trap", "50D9C781FBC7CF7ED15EE3295028B09DD713BEC0AE53DC909F13F832BD7006B6", 6, 51,
         "67789E03FB49A6D11DE6132978D80CEFC5269C87DBE992EB2A626BD242C956C1", 119.656),
        ("cpu_policy", "98CFFDC8BADF7681B519D8936D5491DE27EBD32B5BE51196AC8EC26C37D39C07", 2, 41,
         "CFA41675A79CE67949D1FDB8D08F791EB2FD1115237010D33465135306D1CE23", 90.671),
        ("xstate_policy", "8B683AC3B32FBB3576771F6D8742B12C412394D98AC9C9A947DF98AC8A876621", 2, 43,
         "4260145CE808D54618100843E5797A22DAFA156F94093C1D222D6D99730A162A", 66.453),
        ("xstate_exception", "33F94DD2D6D37256D74E7D29411BF0DCB8ADEB6C09EC738F9E62CC73DEBD0AD7", 2, 43,
         "F3ED8801D7E59F458EBE9E20B63EED505D5DEF7034E3E58654DA297E074BF60D", 78.172),
        ("privilege_msr_policy", "D5027EF6F51ADCCA9A6B33308CA91D8FF617BC08483F91B47F321A88776452FC", 2, 47,
         "9B9A31059D4151F9B9A62622272025F3EDB8EEF33A8C29EEA6267DBE5A72AE32", 76.078),
    )
    bindings = [dict(profile=profile, path="runs/native-kernel-" + profile.replace("_", "-") + "-readiness.json",
                     sha256=digest, fresh_runs=runs, negative_controls=controls, kernel_host_tests=246,
                     execution_log_sha256=log, elapsed_seconds=seconds)
                for profile, digest, runs, controls, log, seconds in rows]
    gate["current_cpu_qualification"] = {
        "cycle": 199, "source_validation_cycle": 199, "status": "single_host_cpu_replay_pass",
        "scope": "five_N7_profiles_and_strict_control_admission_on_Cycle197_kernel",
        "applies_to_current_source": True, "kernel_sha256": gate["current_boot_chain_qualification"]["kernel_sha256"],
        "qualified_profiles": [b["profile"] for b in bindings], "receipt_bindings": bindings,
        "readiness_replay_required_profiles": [], "embedded_entry_provenance_replay_pending": False,
        "fresh_qemu_runs": 14, "superseded_initial_runs": 6, "negative_control_groups": 225,
        "kernel_host_tests_per_qualifier": 246, "whpx_exception_runs": 2, "expected_tcg_limitation_probes": 1,
        "exception_deliveries_per_run": 3, "exception_recoveries_per_run": 2,
        "focused_python_tests": 54, "aggregate_gate_regression_cases": 21,
        "embedded_entry_rejection_cases": 80, "invalid_current_entry_dependency_cases": 20,
        "recorded_pair_count": 7, "recorded_exit_rejection_cases": 98,
        "recorded_coverage_rejection_cases": 112, "recorded_evidence_rejection_cases": 161,
        "recorded_evidence_total_rejection_cases": 371,
        "recorded_control_rejection_cases": {"trap": 1084, "cpu_policy": 546, "xstate_policy": 572,
                                           "xstate_exception": 572, "privilege_msr_policy": 624},
        "recorded_control_total_rejection_cases": 3398,
        "control_corpus_matches_before_generator": True,
        "recorded_evidence_rejections_exercised_through_runtime_and_gate": True,
        "positive_receipts_rebound_in_tests": False, "pair_validation_is_freshness_or_authentication": False,
        "trap_control_validator_calls": 51, "disabled_trap_validator_detected": True,
        "entry_identity_comparison": "canonical_JSON_typed_equality",
        "canonical_kernel_changed_this_cycle": False, "current_candidate_full_gate_passed": False,
        "pre_repair_control_counterexample": {
            "cases": 1084, "genuine_source_current_positive": True,
            "runtime_accepted": 663, "runtime_rejected": 416, "runtime_exceptions": 5,
            "aggregate_gate_accepted": 663, "aggregate_gate_rejected": 421, "aggregate_gate_exceptions": 0,
            "receipt_sha256": "8B46672DFA24980C4D3728D9A9CAFBFAD9548AB73D58D2581C277CF96C213C97",
            "audit_sha256": "1260297B4F4D703D17667851E571291AC57DF9264380389F68F8D0FF00B53972",
        },
        "post_repair_control_counterexample_replay": {
            "cases": 1084, "genuine_source_current_positive": True, "runtime_accepted": 0,
            "aggregate_gate_accepted": 0, "runtime_rejected": 1084, "aggregate_gate_rejected": 1084,
            "runtime_exceptions": 0, "aggregate_gate_exceptions": 0,
            "audit_sha256": "9D10D6F8357739B92F195896FFDA1907347F97172388F3EEA7F8781B8F49786E",
        },
        "coherent_forgery_excluded": False, "production_ready": False,
    }
    passing = ["native_" + name + "_readiness" for name in (
        "kernel_entry", "symbol", "policy", "kernel_load", "pooleboot", "kernel_revalidation",
        "kernel_transfer", "kernel_trap", "kernel_cpu_policy", "kernel_errata_policy",
        "kernel_xstate_policy", "kernel_xstate_exception", "kernel_privilege_msr_policy")]
    gate["current_focused_source_projection"] = {
        "cycle": 199, "scope": "27_selected_native_checks_not_full_canonical_audit",
        "passed_checks": 13, "total_checks": 27, "pending_downstream_native_checks": 14,
        "passing_profiles": passing, "final_receipt_fresh_qemu_runs": 14, "kernel_entry_runs": 14,
        "superseded_initial_qemu_runs": 6, "expected_tcg_limitation_probes": 1,
        "run_count_scope": "Cycle199_five_CPU_profiles_not_retained_Cycle198_boot_chain",
        "next_dependency_move_id": next_move,
        "required_next_gate": "fourteen_memory_IRQ_SMP_scheduler_atomic_lock_profiles_then_controls_and_full_candidate",
        "focused_python_tests_passed": 54, "focused_python_tests_skipped": 0,
        "canonical_full_replay_performed": False, "production_ready": False,
    }
    gate["current_entry_provenance_qualification"] = dict(
        gate["current_entry_provenance_qualification"], latest_reproduction_cycle=199)
    gate["current_ipi_mailbox_oracle_gap"] = dict(
        gate["current_ipi_mailbox_oracle_gap"], cycle=199, remaining_affected_profiles=14,
        newly_requalified_profiles=[b["profile"] for b in bindings])
    gate["current_closeout_regression"] = {
        "cycle": 199, "status": "pass", "scope": "CPU_profiles_errata_recorded_admission_and_two_selected_aggregate_gate_tests",
        "tests_run": 54, "tests_passed": 54, "tests_failed": 0, "tests_skipped": 0,
        "elapsed_seconds": 176.656, "log_sha256": "D3599A8C5F5C9ECCFE3030674165E0B1D0A60F51C357909883AC5C85B944630B",
        "initial_gate_pin_regression": {"tests_run": 1, "tests_failed": 1, "elapsed_seconds": 0.797,
            "cause": "aggregate_trap_gate_retained_Cycle192_hash_and_relocation_count",
            "log_sha256": "D18042EB201DF92A159C8B0B027247C05F63FDB90D5913C99ACB999F40579402"},
        "corrected_gate_pin_verified_in_focused_regression": True,
        "control_audit_before_log_sha256": "27AF30A3BA175B093796D7754DD7E829CD895A8DD34935B65007EC158F0F54ED",
        "control_audit_after_log_sha256": "1A34878B0ECA4777EB791678250085E3785F8BDA9CFC8B7549EAECC18A42A044",
        "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        "initial_metadata_regression": {
            "status": "pass", "tests_run": 46, "tests_passed": 46, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 14.657,
            "log_sha256": "E6CCFFEB776508E6218383DF5C0D9B7164609A8C056C8F0D42180D614EAF019B",
        },
        "combined_regression": {
            "status": "pass", "scope": "boot_kernel_CPU_admission_native_deferred_metadata_publication_not_full_canonical",
            "tests_run": 233, "tests_passed": 233, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 343.453,
            "log_sha256": "D1BF6DC903758E38583778E0C507F1BC8E8DAF2568DC3F0973B91D6E678EDEA4",
            "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        },
        "initial_conservation": {
            "status": "pass", "archived_records": 17, "architecture_bindings": 325,
            "test_inventory": 1069, "selected_checks": "13/27", "flag_statuses_unchanged": True,
            "normative_charter_checklist_owner_ISO_preserved": True,
        },
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 199: " + checkpoint + " repairs complete CPU control-record admission and malformed root rejection. "
        "The genuine 1084-case trap audit admitted 663 corruptions through runtime and gate, with five runtime "
        "exceptions; all original cases now reject without exceptions. Five final CPU profiles pass fourteen "
        "guest boots, 225 executed controls and 54 focused tests, including 3398 control-record and 371 paired "
        "execution corruptions. Six initial boots and the stale aggregate-pin failure remain historical."
    )
    gap = (
        "Selected readiness is 13/27; fourteen memory/IRQ/SMP/scheduler/atomic/lock profiles remain from "
        + next_move + ". Deferred admission and at least 65 scheduler control-execution groups remain open. "
        "Recorded consistency is not authentication or exclusion of coherent forgery. Full all-vector, guarded "
        "IST, user-context, target-hardware and N7-exit qualification remain open. Full exact-candidate "
        "canonical/Doctor/publication/configured-check/review qualification still precedes main merge."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N7", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 199 source inventory: 1069 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N7-TRAP-001", "FLAG-N7-CPU-POLICY-001", "FLAG-N7-XSTATE-POLICY-001",
                          "FLAG-N7-XSTATE-EXCEPTION-001", "FLAG-N7-PRIVILEGE-MSR-POLICY-001",
                          "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle200(roadmap, test_count)


def apply_cycle200(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle200-memory-and-multiprocessor-replay.md"
    next_move = "N12-SCHED-001"
    roadmap["baseline"]["pooleos_cycle"] = 200
    protocol = roadmap["execution_protocol"]
    protocol.update(last_updated_cycle=200, selected_move_id="N9-PMM-ACPI-CONSUMER-001",
                    owner_independent_next_move_id=next_move)
    protocol["required_records"].insert(0, checkpoint)
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for key, value in list(gate.items()):
        if key.startswith("current_") and isinstance(value, dict):
            suffix = "source_projection" if key == "current_focused_source_projection" else key.removeprefix("current_")
            gate["historical_cycle199_" + suffix] = copy.deepcopy(value)
    gate["qualification_status"] = "six_current_memory_IRQ_SMP_profiles_eight_scheduler_dependencies_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=200)
    bindings = [
        {
            "profile": "physical_memory",
            "path": "runs/native-kernel-physical-memory-readiness.json",
            "sha256": "C4AD82F6B52D987F303DB02E5FBFEF7B782277168ACD921A0B27510AFB6E328B",
            "fresh_runs": 2,
            "negative_controls": 191,
            "hostile_cases": 191,
            "recorded_evidence_cases": {
                "exit": 14,
                "coverage": 16,
                "evidence": 29,
                "accounting": 7,
                "summary": 168
            },
            "kernel_host_tests": 246,
            "execution_log_sha256": "73D78CC992A80B448CB62D488AC4EFA73BF8EED5DBCA5B8F76C37B5AF855061A",
            "elapsed_seconds": 67.562
        },
        {
            "profile": "virtual_memory",
            "path": "runs/native-kernel-virtual-memory-readiness.json",
            "sha256": "52526BF1B46D4739B636032D6BAFDA774E31495EF1F381863B0785BFF6E2FF13",
            "fresh_runs": 2,
            "negative_controls": 48,
            "hostile_cases": 48,
            "recorded_evidence_cases": {
                "exit": 14,
                "coverage": 16,
                "evidence": 28,
                "accounting": 7,
                "summary": 50
            },
            "kernel_host_tests": 246,
            "execution_log_sha256": "3F150DB57A3859B6474CCAE0679F8D501C0B6264436950A77C7EDC5EE719DE52",
            "elapsed_seconds": 65.25
        },
        {
            "profile": "interrupt_time",
            "path": "runs/native-kernel-interrupt-time-readiness.json",
            "sha256": "558819215BF1EE636FEFBE496BD5F06612B1362DF92D29AD4A8E771CE9A7F2BA",
            "fresh_runs": 2,
            "negative_controls": 58,
            "hostile_cases": 58,
            "recorded_evidence_cases": {
                "exit": 14,
                "coverage": 16,
                "evidence": 23,
                "shape": 3,
                "observation": 145,
                "summary": 22,
                "clock": 6
            },
            "kernel_host_tests": 246,
            "execution_log_sha256": "047FF2DF6EB68D3816503F9E81C83FA820E6D47828691C1D6F48D6B95C2F54B1",
            "elapsed_seconds": 68.344
        },
        {
            "profile": "smp_first_ap",
            "path": "runs/native-kernel-smp-first-ap-readiness.json",
            "sha256": "6293B3B799ED48F4F923AD6483C218D68D4EBA885EE2A02C04825929B7845B31",
            "fresh_runs": 2,
            "negative_controls": 72,
            "hostile_cases": 72,
            "recorded_evidence_cases": {
                "exit": 14,
                "coverage": 16,
                "evidence": 23,
                "shape": 3,
                "dynamic-policy": 2,
                "observation": 69,
                "summary": 30,
                "raw-stop": 2
            },
            "kernel_host_tests": 246,
            "execution_log_sha256": "6A25DBB4AE5AC7A23E7328961F320F5551C3A189A91211F1B4C970530B8614E1",
            "elapsed_seconds": 71.5
        },
        {
            "profile": "smp_percpu_runtime",
            "path": "runs/native-kernel-smp-percpu-runtime-readiness.json",
            "sha256": "31C04EFD10CD2BE8E1DBCDF3E08655AB525909987E61F83E52D1CAD907543888",
            "fresh_runs": 2,
            "negative_controls": 19,
            "hostile_cases": 159,
            "recorded_evidence_cases": {
                "exit": 14,
                "coverage": 16,
                "evidence": 23,
                "shape": 3,
                "dynamic-policy": 7,
                "observation": 108,
                "summary": 40,
                "raw-stop": 3,
                "controls": 39
            },
            "kernel_host_tests": 246,
            "execution_log_sha256": "BEDC73DE58B81C522F0C0F23D34D0E0573C50C2BA8A22ADF37436DC4F4E4C890",
            "elapsed_seconds": 59.609
        },
        {
            "profile": "smp_ipi",
            "path": "runs/native-kernel-smp-ipi-readiness.json",
            "sha256": "1CECF18AF71AA97276AF28BC6AFA1815649A110B50084ACDFEFAA6A2D2468619",
            "fresh_runs": 2,
            "negative_controls": 33,
            "hostile_cases": 609,
            "recorded_evidence_cases": {
                "exit": 14,
                "coverage": 16,
                "evidence": 23,
                "shape": 3,
                "dynamic-policy": 8,
                "observation": 739,
                "summary": 34,
                "raw-frame": 2,
                "controls": 67
            },
            "kernel_host_tests": 246,
            "execution_log_sha256": "E0B087D9E37F4C38338846C92713C05222236A8EBA791CE7729263229D4EF138",
            "elapsed_seconds": 70.906
        }
    ]
    retained = gate["current_dependency_qualification"]
    pending = [p for p in retained["readiness_replay_required_profiles"] if p not in {b["profile"] for b in bindings}]
    gate["current_dependency_qualification"] = {
        "cycle": 200, "source_validation_cycle": 200, "status": "six_current_profiles_eight_pending",
        "scope": "six_fresh_memory_IRQ_AP_IPI_profiles_on_Cycle197_kernel",
        "applies_to_current_source": True, "all_fourteen_profiles_current": False,
        "qualified_profiles": [b["profile"] for b in bindings],
        "newly_qualified_profiles": [b["profile"] for b in bindings],
        "readiness_replay_required_profiles": pending, "embedded_entry_provenance_replay_pending": True,
        "fresh_qemu_runs": 12, "superseded_initial_runs": 0,
        "run_count_scope": "Cycle200_six_profiles_only_not_retained_CPU_or_boot_runs",
        "negative_control_groups": 421, "negative_control_cases": 1137,
        "kernel_sha256": retained["kernel_sha256"], "receipt_bindings": bindings,
        "kernel_host_tests_per_qualifier": 246, "focused_python_tests": 93,
        "recorded_evidence_case_total": 1896, "recorded_evidence_scope": "six_fresh_profiles",
        "recorded_evidence_rejections_exercised_through_runtime_and_gate": True,
        "positive_receipts_rebound_in_tests": False, "pair_validation_is_freshness_or_authentication": False,
        "disabled_PMM_parser_and_memory_oracle_detected": True, "PMM_marker_validator_calls": 189,
        "raw_mailbox_rejection_cases": 360, "independent_IPI_pin_rejection_cases": 4,
        "memory_gate_rejection_cases": 20, "canonical_kernel_changed_this_cycle": False,
        "control_execution_complete": False, "unproven_per_control_rejection_groups_at_least": 65,
        "current_candidate_full_gate_passed": False, "production_ready": False,
    }
    gate["current_ownership_qualification"] = dict(
        gate["current_ownership_qualification"], cycle=200,
        scope="retained_host_core197_and_fresh_bounded_VM_IPI200",
        fresh_current_cycle_qemu_runs=4, live_replay_cycle=200,
        live_receipt_scope="two_VM200_and_two_IPI200_runs",
        live_receipt_source_current=True, active_root_current_image_replay_complete=True,
        virtual_memory_live_receipt_source_current=True, ap_runtime_live_integration_verified=True,
        virtual_memory_live_replay_cycle=200, virtual_memory_receipt_sha256=bindings[1]["sha256"],
        smp_receipt_sha256=bindings[5]["sha256"],
        source_current_scope="host_core197_boot198_and_bounded_VM_IPI200")
    passing = gate["current_focused_source_projection"]["passing_profiles"]
    gate["current_focused_source_projection"] = {
        "cycle": 200, "scope": "27_selected_native_checks_not_full_canonical_audit",
        "passed_checks": 19, "total_checks": 27, "pending_downstream_native_checks": 8,
        "passing_profiles": passing + ["native_kernel_" + b["profile"] + "_readiness" for b in bindings],
        "final_receipt_fresh_qemu_runs": 12, "kernel_entry_runs": 12, "superseded_initial_qemu_runs": 0,
        "run_count_scope": "Cycle200_six_memory_IRQ_SMP_profiles_not_retained_CPU_or_boot_runs",
        "next_dependency_move_id": next_move,
        "required_next_gate": "eight_scheduler_atomic_lock_profiles_deferred_admission_controls_then_full_candidate",
        "focused_python_tests_passed": 93, "focused_python_tests_skipped": 0,
        "recorded_evidence_rejection_cases": 1896,
        "canonical_full_replay_performed": False, "production_ready": False,
    }
    gate["current_entry_provenance_qualification"] = dict(
        gate["current_entry_provenance_qualification"], latest_reproduction_cycle=200)
    gate["current_ipi_mailbox_oracle_gap"] = dict(
        gate["current_ipi_mailbox_oracle_gap"], cycle=200, remaining_affected_profiles=8,
        newly_requalified_profiles=[b["profile"] for b in bindings], current_kernel_live_replay_pending=False)
    gate["current_closeout_regression"] = {
        "cycle": 200, "status": "pass", "scope": "six_memory_IRQ_SMP_profiles_and_independent_memory_IPI_gates",
        "tests_run": 93, "tests_passed": 93, "tests_failed": 0, "tests_skipped": 0,
        "elapsed_seconds": 121.922,
        "log_sha256": "0492DA3723BE1ED1565D43A4674EF948EF0862969D5E31F64B73C51BD8CD7B5A",
        "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        "initial_IPI_admission": {
            "status": "rejected", "attempts": 1, "runtime_validated": True, "guest_qualifier_passed": True,
            "actual_gate_detail": "PKSMP5 embedded kernel identity changed",
            "cause": "aggregate_gate_retained_Cycle192_kernel_hash",
            "candidate_sha256": bindings[5]["sha256"], "chain_return_code": 1,
            "failed_guest_runs": 0, "guest_evidence_rewritten_or_rerun": False,
        },
        "corrected_IPI_admission": {"status": "pass", "same_candidate_sha256": bindings[5]["sha256"],
                                    "runtime_and_actual_gate_passed": True, "independent_pin_rejection_cases": 4},
        "initial_metadata_regression": {
            "status": "fail", "tests_run": 47, "tests_passed": 41, "tests_failed": 6, "tests_skipped": 0,
            "elapsed_seconds": 16.063,
            "cause": "six_historical_tests_still_expected_current_memory_IPI_receipts_to_be_stale",
            "log_sha256": "FD309DC9C6C222B6415AA193577477CA14E9E72E1441DBD5551401B2B7D058F6",
        },
        "corrected_metadata_regression": {
            "status": "pass", "tests_run": 47, "tests_passed": 47, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 17.609,
            "log_sha256": "8F6A7844FD179AF3170B9E97166E49AD873834299261BC572D5ADBF5BFEB2A16",
            "historical_hashes_and_records_preserved": True,
        },
        "combined_scoped_regression": {
            "status": "pass", "tests_run": 327, "tests_passed": 327, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 472.891,
            "log_sha256": "F568E4C6D77BEF54DEACFAA2181B0E81C6B3F5A2DBBF4A8261C28B3D825211AA",
            "scope": "boot_entry_core_CPU_memory_IRQ_SMP_metadata_and_publication_not_full_canonical",
            "source_unchanged_during_execution": True, "owner_report_unchanged": True,
            "executed_before_result_recording": True,
        },
        "initial_conservation": {
            "status": "pass", "archived_parent_current_records": 17, "architecture_bindings": 326,
            "test_inventory": 1071, "selected_checks": "19/27",
            "native_other_receipts_owner_ISO_checklist_normative_charter_preserved": True,
        },
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 200: " + checkpoint + " qualifies six current PMM/VM/IRQ/first-AP/per-CPU/IPI profiles on the "
        "unchanged Cycle197 kernel: twelve final virtual boots, 421 control groups, 1137 executed rejection cases "
        "and 246 kernel host tests per qualifier. All 93 focused tests pass, including 1896 recorded corruptions, "
        "360 mailbox mutations, 20 memory gate cases and four independent IPI pin cases. The initial IPI "
        "admission rejection from the old kernel pin is preserved; the same guest receipt passes after correction. "
        "Combined scoped regression passes 327 tests with zero skips; corrected metadata passes 47/47 and "
        "conservation preserves 17 parent records and verifies 326 architecture bindings."
    )
    gap = (
        "Selected readiness is 19/27; eight scheduler/atomic/lock profiles remain from " + next_move +
        ". Deferred receipt admission, at least 65 control-execution groups and full exact-candidate "
        "canonical/Doctor/publication/configured-check/review qualification still precede main merge. "
        "Current bounded AP and VM ownership is not general task-stack or CPU-retirement integration. "
        "Recorded consistency is not authentication. No phase, flag, native kernel byte, ISO or production claim changes."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N8", "N9", "N10", "N12", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 200 source inventory: 1071 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N9-PMM-ACPI-CONSUMER-001", "FLAG-N9-VM-DIRECT-MAP-001", "FLAG-N8-IRQ-001",
                          "FLAG-N8-SMP-FIRST-AP-001", "FLAG-N8-SMP-PERCPU-RUNTIME-001", "FLAG-N8-SMP-IPI-001",
                          "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle201(roadmap, test_count)


def apply_cycle201(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle201-scheduler-and-preemption-replay.md"
    next_move = "N12-SCHED-DEFERRED-001"
    roadmap["baseline"]["pooleos_cycle"] = 201
    protocol = roadmap["execution_protocol"]
    protocol.update(last_updated_cycle=201, selected_move_id="N12-SCHED-001",
                    owner_independent_next_move_id=next_move)
    protocol["required_records"].insert(0, checkpoint)
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for key, value in list(gate.items()):
        if key.startswith("current_") and isinstance(value, dict):
            suffix = "source_projection" if key == "current_focused_source_projection" else key.removeprefix("current_")
            gate["historical_cycle200_" + suffix] = copy.deepcopy(value)
    gate["qualification_status"] = "current_scheduler_and_preemption_six_dependencies_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=201)
    bindings = [
        {
            "profile": "scheduler",
            "path": "runs/native-kernel-scheduler-readiness.json",
            "sha256": "FF5A23F5D19B5D009BC5D9823CBB29D0B74343684D5AE4D051345D3AF0A5D7E8",
            "fresh_runs": 2,
            "negative_controls": 28,
            "hostile_cases": 115,
            "recorded_evidence_cases": {
                "exit": 14,
                "coverage": 16,
                "evidence": 23,
                "shape": 4,
                "profile": 8,
                "observation": 37,
                "summary": 26,
                "host-probe": 30,
                "controls": 57,
                "root-shape": 3,
                "control-shape": 3
            },
            "kernel_host_tests": 246,
            "execution_log_sha256": "A05D356DCFD64DA45E0725945AEE1EEB96E15E160E1589353424DC46CA535D20",
            "elapsed_seconds": 135.797
        },
        {
            "profile": "scheduler_preempt",
            "path": "runs/native-kernel-scheduler-preemption-readiness.json",
            "sha256": "00F89E715A57EB75F734C8C4E26E5867614E061EF1BD4DF3575FDA439F4D0750",
            "fresh_runs": 2,
            "negative_controls": 25,
            "hostile_cases": 226,
            "recorded_evidence_cases": {
                "exit": 14,
                "coverage": 16,
                "evidence": 23,
                "shape": 4,
                "profile": 8,
                "observation": 48,
                "summary": 22,
                "host-probe": 14,
                "controls": 51,
                "root-shape": 3,
                "control-shape": 3
            },
            "kernel_host_tests": 246,
            "execution_log_sha256": "C4CA732801FB906F7442652BE154022EA0C59C4E633C31145D785E2F4E5A52F5",
            "elapsed_seconds": 123.453
        }
    ]
    retained = gate["current_dependency_qualification"]
    pending = [p for p in retained["readiness_replay_required_profiles"] if p not in {b["profile"] for b in bindings}]
    gate["current_dependency_qualification"] = {
        "cycle": 201, "source_validation_cycle": 201, "status": "eight_current_profiles_six_pending",
        "scope": "six_retained_memory_IRQ_SMP200_and_two_fresh_scheduler201_profiles",
        "applies_to_current_source": True, "all_fourteen_profiles_current": False,
        "qualified_profiles": retained["qualified_profiles"] + [b["profile"] for b in bindings],
        "newly_qualified_profiles": [b["profile"] for b in bindings],
        "readiness_replay_required_profiles": pending, "embedded_entry_provenance_replay_pending": True,
        "fresh_qemu_runs": 4, "superseded_initial_runs": 0,
        "run_count_scope": "Cycle201_two_profiles_only_not_retained_memory_CPU_or_boot_runs",
        "negative_control_groups": 53, "negative_control_cases": 341,
        "kernel_sha256": retained["kernel_sha256"],
        "receipt_bindings": copy.deepcopy(retained["receipt_bindings"]) + bindings,
        "retained_qualification_record": "historical_cycle200_dependency_qualification",
        "kernel_host_tests_per_qualifier": 246, "focused_python_tests": 31,
        "recorded_evidence_case_total": 453, "generic_recorded_evidence_cases": 427,
        "additional_preemption_control_receipt_corruptions": 26,
        "recorded_evidence_scope": "221_scheduler_206_preemption_26_additional_preemption_controls",
        "recorded_evidence_rejections_exercised_through_runtime_and_gate": True,
        "positive_receipts_rebound_in_tests": False, "pair_validation_is_freshness_or_authentication": False,
        "native_preemption_control_cases": 50, "linked_scope_control_cases": 3, "stack_source_guard_cases": 4,
        "disabled_native_variants_detected": 7, "disabled_auditors_detected": 2,
        "canonical_kernel_changed_this_cycle": False, "control_execution_complete": False,
        "unproven_per_control_rejection_groups_at_least": 65,
        "current_candidate_full_gate_passed": False, "production_ready": False,
    }
    passing = gate["current_focused_source_projection"]["passing_profiles"]
    gate["current_focused_source_projection"] = {
        "cycle": 201, "scope": "27_selected_native_checks_not_full_canonical_audit",
        "passed_checks": 21, "total_checks": 27, "pending_downstream_native_checks": 6,
        "passing_profiles": passing + ["native_kernel_scheduler_readiness", "native_kernel_scheduler_preemption_readiness"],
        "final_receipt_fresh_qemu_runs": 4, "kernel_entry_runs": 4, "superseded_initial_qemu_runs": 0,
        "run_count_scope": "Cycle201_scheduler_and_preemption_only",
        "next_dependency_move_id": next_move,
        "required_next_gate": "deferred_admission_and_controls_six_profiles_then_full_exact_candidate",
        "focused_python_tests_passed": 31, "focused_python_tests_skipped": 0,
        "recorded_evidence_rejection_cases": 453,
        "canonical_full_replay_performed": False, "production_ready": False,
    }
    gate["current_entry_provenance_qualification"] = dict(
        gate["current_entry_provenance_qualification"], latest_reproduction_cycle=201)
    gate["current_preemption_control_execution_audit"] = dict(
        gate["current_preemption_control_execution_audit"], cycle=201, original_repair_cycle=196,
        source_validation_cycle=201, receipt_sha256=bindings[1]["sha256"],
        current_kernel_live_replay_pending=False, current_receipt_admitted=True)
    gate["current_ipi_mailbox_oracle_gap"] = dict(
        gate["current_ipi_mailbox_oracle_gap"], cycle=201, remaining_affected_profiles=6,
        newly_requalified_profiles=[b["profile"] for b in bindings])
    gate["current_closeout_regression"] = {
        "cycle": 201, "status": "pass", "scope": "scheduler_preemption_and_native_preemption_controls",
        "tests_run": 31, "tests_passed": 31, "tests_failed": 0, "tests_skipped": 0,
        "elapsed_seconds": 35.797,
        "log_sha256": "34BE546EFB85C71B4DE8BF7E0642F771333FB650B4F982B7193A17D0191A3985",
        "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        "initial_metadata_regression": {
            "status": "fail", "tests_run": 48, "tests_passed": 45, "tests_failed": 3, "tests_skipped": 0,
            "elapsed_seconds": 18.297,
            "cause": "obsolete_current_scheduler_entry_dependency_count_and_next_move_assertions",
            "log_sha256": "4E6A21C3CFD6738F996D004E6EF6D20DBA28EEC4E68995A4BD95E03F15AD1428",
            "guest_or_native_runtime_failure": False,
        },
        "intermediate_metadata_regression": {
            "status": "fail", "tests_run": 48, "tests_passed": 47, "tests_failed": 1, "tests_skipped": 0,
            "elapsed_seconds": 18.375,
            "cause": "later_assertion_in_entry_test_still_expected_19_instead_of_21_current_checks",
            "log_sha256": "F84FEF323F093C515FA73D17D1E3538094EB3186A439A563A5CBE19E7AAC06ED",
            "guest_or_native_runtime_failure": False,
        },
        "repaired_metadata_regression": {
            "status": "pass", "tests_run": 48, "tests_passed": 48, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 18.328,
            "log_sha256": "9DC0D60BA092B1F648F84F6CDDFB653349B17436AE6087717141488191CA0350",
        },
        "combined_scoped_regression": {
            "status": "pass", "tests_run": 128, "tests_passed": 128, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 171.172,
            "log_sha256": "AFBC14EF6CB5715473F8ED9739AD8A5A3B5B08721B3272B7712922CC4CDC417D",
            "scope": "entry_core_deferred_transactions_IRQ_scheduler_preemption_publication_metadata_not_full_canonical",
            "source_unchanged_during_execution": True, "owner_report_unchanged": True,
            "executed_before_result_recording": True,
        },
        "initial_conservation": {
            "status": "pass", "archived_parent_current_records": 17, "architecture_bindings": 327,
            "test_inventory": 1072, "selected_checks": "21/27",
            "native_other_receipts_owner_ISO_checklist_normative_charter_preserved": True,
        },
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 201: " + checkpoint + " requalifies scheduler and BSP preemption on the unchanged Cycle197 "
        "kernel. Four fresh virtual boots, 53 control groups, 341 executed rejection cases and all 31 focused "
        "tests pass, including 453 recorded corruptions and seven disabled native preemption variants. "
        "Six memory/IRQ/SMP profiles remain current Cycle200 evidence, not new Cycle201 boots. "
        "Combined scoped regression passes 128 tests with zero skips; repaired metadata passes 48/48 "
        "and conservation verifies 17 archived parent records and 327 architecture bindings."
    )
    gap = (
        "Selected readiness is 21/27. Six profiles remain from " + next_move +
        "; repair deferred recorded admission and execute its 14 constant-only groups before qualification. "
        "At least 65 control-execution groups remain across deferred/SMP/AP-worker/SMP-preemption profiles. "
        "Full exact-candidate canonical/Doctor/release/publication/configured-check/review qualification "
        "still precedes main merge. N0 custody, N5 authenticated boot, general task/CPU retirement, independent "
        "builders, hardware and production remain open. No phase, flag, kernel byte or ISO changes."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N5", "N12", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 201 source inventory: 1072 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N12-SCHED-001", "FLAG-N12-SCHED-PREEMPT-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle202(roadmap, test_count)


def apply_cycle202(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle202-deferred-admission-and-controls.md"
    next_move = "N12-SCHED-SMP-001"
    roadmap["baseline"]["pooleos_cycle"] = 202
    protocol = roadmap["execution_protocol"]
    protocol.update(last_updated_cycle=202, selected_move_id="N12-SCHED-DEFERRED-001",
                    owner_independent_next_move_id=next_move)
    protocol["required_records"].insert(0, checkpoint)
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for key, value in list(gate.items()):
        if key.startswith("current_") and isinstance(value, dict):
            suffix = "source_projection" if key == "current_focused_source_projection" else key.removeprefix("current_")
            gate["historical_cycle201_" + suffix] = copy.deepcopy(value)
    gate["qualification_status"] = "deferred_admission_and_controls_repaired_five_dependencies_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=202)
    binding = {
        "profile": "scheduler_deferred", "path": "runs/native-kernel-scheduler-deferred-readiness.json",
        "sha256": "5DEB81D744D08EC14895631699B64A9573F57587F6D3520476A7A57E01262F3A",
        "fresh_runs": 2, "negative_controls": 30, "control_cases": 254,
        "rejection_cases": 204, "native_boundary_cases": 50,
        "kernel_host_tests": 246, "elapsed_seconds": 92.812,
        "execution_log_sha256": "E12A45434566B849DD8DC27938DC5EE50E8BFA45D9F58DD3867479C1C06D291E",
    }
    retained = gate["current_dependency_qualification"]
    gate["current_dependency_qualification"] = {
        "cycle": 202, "source_validation_cycle": 202, "status": "nine_current_profiles_five_pending",
        "scope": "eight_retained_memory_IRQ_SMP_scheduler_profiles_and_fresh_deferred202",
        "applies_to_current_source": True, "all_fourteen_profiles_current": False,
        "qualified_profiles": retained["qualified_profiles"] + ["scheduler_deferred"],
        "newly_qualified_profiles": ["scheduler_deferred"],
        "readiness_replay_required_profiles": [p for p in retained["readiness_replay_required_profiles"] if p != "scheduler_deferred"],
        "embedded_entry_provenance_replay_pending": True,
        "fresh_qemu_runs": 2, "diagnostic_pre_repair_runs_not_admitted": 2,
        "superseded_initial_runs": 0, "run_count_scope": "two_final_deferred202_runs_only",
        "negative_control_groups": 30, "negative_control_cases": 254,
        "case_semantics": "204_rejections_and_50_native_boundary_scenarios_not_254_API_rejections",
        "kernel_sha256": retained["kernel_sha256"],
        "receipt_bindings": copy.deepcopy(retained["receipt_bindings"]) + [binding],
        "retained_qualification_record": "historical_cycle201_dependency_qualification",
        "kernel_host_tests_per_qualifier": 246, "focused_python_tests": 17,
        "recorded_evidence_case_total": 315, "original_corruption_corpus": 273,
        "additional_control_receipt_corruptions": 42,
        "recorded_evidence_rejections_exercised_through_runtime_and_gate": True,
        "positive_receipts_rebound_in_tests": False, "pair_validation_is_freshness_or_authentication": False,
        "native_deferred_boundary_cases": 50, "source_audit_rejections": 10,
        "disabled_native_variants_detected": 12, "disabled_auditors_detected": 1,
        "canonical_kernel_changed_this_cycle": False, "control_execution_complete": False,
        "unproven_per_control_rejection_groups_at_least": 51,
        "current_candidate_full_gate_passed": False, "production_ready": False,
    }
    passing = gate["current_focused_source_projection"]["passing_profiles"]
    gate["current_focused_source_projection"] = {
        "cycle": 202, "scope": "27_selected_native_checks_not_full_canonical_audit",
        "passed_checks": 22, "total_checks": 27, "pending_downstream_native_checks": 5,
        "passing_profiles": passing + ["native_kernel_scheduler_deferred_readiness"],
        "final_receipt_fresh_qemu_runs": 2, "kernel_entry_runs": 2,
        "diagnostic_pre_repair_runs_not_admitted": 2, "superseded_initial_qemu_runs": 0,
        "run_count_scope": "two_final_deferred202_runs_only", "next_dependency_move_id": next_move,
        "required_next_gate": "SMP_scheduler_admission_and_executed_controls_then_five_profile_qualification_and_full_exact_candidate",
        "focused_python_tests_passed": 17, "focused_python_tests_skipped": 0,
        "recorded_evidence_rejection_cases": 315, "canonical_full_replay_performed": False, "production_ready": False,
    }
    gate["current_entry_provenance_qualification"] = dict(
        gate["current_entry_provenance_qualification"], latest_reproduction_cycle=202)
    gate["current_ipi_mailbox_oracle_gap"] = dict(
        gate["current_ipi_mailbox_oracle_gap"], cycle=202, remaining_affected_profiles=5,
        newly_requalified_profiles=["scheduler_deferred"])
    audit = copy.deepcopy(gate["current_control_execution_audit"])
    audit.update(cycle=202, original_finding_cycle=181, next_profile="scheduler_smp",
                 unproven_per_control_rejection_groups_at_least=51,
                 scope="three_remaining_scheduler_qualifier_loops_not_exhaustive_all_profile_audit")
    audit["source_control_gaps"] = [gap for gap in audit["source_control_gaps"] if gap["profile"] != "scheduler_deferred"]
    audit["deferred_groups_repaired"] = 14
    gate["current_control_execution_audit"] = audit
    gate["current_deferred_control_qualification"] = {
        "cycle": 202, "move_id": "N12-SCHED-DEFERRED-001", "requirement_id": "ADD-N36-RECEIPT-COVERAGE-001",
        "status": "pass_bounded_recorded_admission_and_host_controls_non_promoting",
        "receipt_path": binding["path"], "receipt_sha256": binding["sha256"],
        "repaired_groups": 14, "native_boundary_cases": 50, "source_audit_rejection_cases": 10,
        "disabled_native_variants_detected": 12, "disabled_auditors_detected": 1,
        "genuine_before_audit": {
            "receipt_sha256": "929191330266F7C0D5BD51963F5EE39539177F3D227E1512618FB8C68AC87BFF",
            "original_audit_sha256": "346485F2D4C2C136D20033B1576C6768B04A2015737916FB3213DBA2DBD004C2",
            "pin_corrected_audit_sha256": "982DC9897D7B87DC11A9643CDE5A31090B73C85D25A1B767AAF00DCEF6A04EB1",
            "original_gate_failed_stale_product_pin": True, "positive_runtime_and_pin_corrected_gate": True,
            "cases": 273, "runtime_accepted": 258, "runtime_rejected": 11, "runtime_exceptions": 4,
            "gate_accepted": 164, "gate_rejected": 90, "gate_exceptions": 19,
            "diagnostic_boots": 2, "admitted_as_final": False,
        },
        "after_audit": {
            "sha256": "A73B80AEE5A2D653628911AEEAACF9A503118BEB98A844B71DE8EC4C6DFAD798",
            "same_corpus_cases": 273, "runtime_rejected": 273, "gate_rejected": 273,
            "runtime_accepted": 0, "gate_accepted": 0, "runtime_exceptions": 0, "gate_exceptions": 0,
            "additional_control_receipt_cases_rejected_by_both": 42,
        },
        "initial_control_test": {
            "status": "fail", "tests_run": 5, "tests_passed": 4, "tests_failed": 1,
            "cause": "flush_mutation_target_not_unique_before_native_variant_execution",
            "log_sha256": "7E5C9727611260390C0512899E8C8F97CA6516229AB6A6BB549BC3162534F95F",
            "native_runtime_failure": False,
        },
        "repaired_control_test": {
            "status": "pass", "tests_run": 5, "tests_passed": 5, "tests_skipped": 0,
            "log_sha256": "876088AAD3E5632AB972DDF46DB3DBDE00C5707C45D456EE591323BCCDFBD09E",
        },
        "aggregate_unproven_groups_at_least": 51, "native_kernel_bytes_changed": False,
        "all_profile_control_execution_audited": False, "privileged_hardware_fault_injection": False,
        "recorded_consistency_is_authentication_or_freshness": False, "production_ready": False,
    }
    gate["current_closeout_regression"] = {
        "cycle": 202, "status": "pass", "scope": "deferred_admission_controls_and_native_transactions",
        "tests_run": 17, "tests_passed": 17, "tests_failed": 0, "tests_skipped": 0,
        "elapsed_seconds": 33.296,
        "log_sha256": "9F919ACB3EFD449692172D20810F95AB2E672944358E3479F17506C1244A2731",
        "initial_metadata": {
            "status": "fail", "tests_run": 49, "tests_passed": 42, "tests_failed": 7,
            "elapsed_seconds": 17.375,
            "cause": "stale_cycle_schema_binding_counts_and_historical_deferred_expectations",
            "log_sha256": "53C42EAD791C3EE3CF6188AD5C5E53E1920287E57FEBB7DF49CF7495DC918658",
        },
        "second_metadata": {
            "status": "fail", "tests_run": 49, "tests_passed": 47, "tests_failed": 1, "tests_errored": 1,
            "elapsed_seconds": 18.359,
            "cause": "remaining_old_pending_count_and_nonexistent_historical_audit_key",
            "log_sha256": "E3644F0F78B7D92746557FF35EAB75F429E80124D17413165FAB293A2413D648",
        },
        "repaired_metadata": {
            "status": "pass", "tests_run": 49, "tests_passed": 49, "tests_skipped": 0,
            "elapsed_seconds": 18.828,
            "log_sha256": "958559B270220C750D101074C77D004F4BA9415934C096937BABD5C05249F008",
        },
        "combined_regression": {
            "status": "pass", "tests_run": 144, "tests_passed": 144, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 196.625,
            "scope": "entry_core_IRQ_scheduler_preemption_deferred_controls_publication_metadata_not_full_canonical",
            "includes_focused_and_metadata_tests": True,
            "log_sha256": "2CF0A1DF614AEAF90FB41206E59D002F73A88AE6BCF1DE0EC6BC7323E6F503D1",
        },
        "conservation": {
            "status": "pass", "parent_current_records_archived_unchanged": 17,
            "architecture_bindings": 338, "test_inventory": 1081,
            "locked_checklist_and_prior_receipts_preserved": True,
            "native_sources_and_normative_charter_preserved": True,
        },
        "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 202: " + checkpoint + " repairs deferred recorded admission and replaces 14 constant-only groups. "
        "Two final virtual boots, 254 executed cases (204 rejections and 50 native boundary scenarios), "
        "17 focused tests and 315 recorded corruption rejections pass. Twelve disabled native variants "
        "and a disabled source auditor are detected. Eight prior dependency receipts remain retained evidence."
    )
    gap = (
        "Selected readiness is 22/27. Next " + next_move + " requires recorded-admission inspection and 16 "
        "executed control groups before fresh qualification. At least 51 groups remain in three scheduler "
        "profiles. SMP scheduling, AP workers, SMP preemption, atomics and locks, then full exact-candidate "
        "canonical/Doctor/release/publication/configured-check/review qualification still precede main merge. "
        "N0 custody, N5 authentication, general task/CPU retirement, independent builders and production remain "
        "open. No phase, flag, native kernel byte or demo ISO changes."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N5", "N12", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 202 source inventory: 1081 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N12-SCHED-DEFERRED-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle203(roadmap, test_count)


def apply_cycle203(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle203-native-smp-transactions.md"
    kernel_sha = "A943DCB6E41A27F952868F05ED2B3523B47D9D7A7B5DB909EE385205F7CA3B31"
    entry_sha = "E90F11157F3416CE2C78650C4605ADF92BF5D7AC19A293E0C105499EF17276A5"
    core_sha = "33EE501601ACB8109FA867C2634FAC1C04F43505B4DD6C6D75821545B120BDD8"
    next_move = "N5-SYMBOLS-SEMANTICS-001"
    roadmap["baseline"]["pooleos_cycle"] = 203
    protocol = roadmap["execution_protocol"]
    protocol.update(last_updated_cycle=203, selected_move_id="N12-SCHED-SMP-001",
                    owner_independent_next_move_id=next_move)
    protocol["required_records"].insert(0, checkpoint)
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for key, value in list(gate.items()):
        if key.startswith("current_") and isinstance(value, dict):
            suffix = "source_projection" if key == "current_focused_source_projection" else key.removeprefix("current_")
            gate["historical_cycle202_" + suffix] = copy.deepcopy(value)
    gate["qualification_status"] = "native_SMP_transactions_repaired_changed_image_replay_and_controls_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=203)
    gate["current_focused_source_projection"] = {
        "cycle": 203, "scope": "27_selected_native_checks_not_full_canonical_audit",
        "passed_checks": 2, "total_checks": 27, "pending_downstream_native_checks": 25,
        "passing_profiles": ["native_kernel_entry_readiness", "native_kernel_errata_policy_readiness"],
        "final_receipt_fresh_qemu_runs": 0, "kernel_entry_runs": 0,
        "next_dependency_move_id": next_move,
        "required_next_gate": "changed_image_symbols_policy_boot_CPU_memory_scheduler_replay_and_executed_SMP_controls",
        "native_transaction_tests_per_profile": 19, "native_transaction_host_profiles": 2,
        "canonical_full_replay_performed": False, "production_ready": False,
    }
    pending_profiles = {
        "boot_chain": ["symbol", "policy", "kernel_load", "pooleboot", "kernel_revalidation", "kernel_transfer"],
        "cpu": ["trap", "cpu_policy", "xstate_policy", "xstate_exception", "privilege_msr_policy"],
        "dependency": ["physical_memory", "virtual_memory", "interrupt_time", "smp_first_ap", "smp_percpu_runtime",
                       "smp_ipi", "scheduler", "scheduler_preempt", "scheduler_deferred", "scheduler_smp",
                       "scheduler_ap_workers", "scheduler_smp_preempt", "atomics", "locks"],
    }
    for group, profiles in pending_profiles.items():
        gate["current_" + group + "_qualification"] = {
            "cycle": 203, "source_validation_cycle": 203, "status": "source_requalification_required",
            "applies_to_current_source": False, "kernel_sha256": kernel_sha,
            "historical_record": "historical_cycle202_" + group + "_qualification",
            "qualified_profiles": [], "readiness_replay_required_profiles": profiles,
            "fresh_qemu_runs": 0, "receipt_bindings": [], "embedded_entry_provenance_replay_pending": True,
            "all_fourteen_profiles_current": False, "control_execution_complete": False,
            "unproven_per_control_rejection_groups_at_least": 51,
            "current_candidate_full_gate_passed": False, "production_ready": False,
        }
    gate["current_entry_provenance_qualification"] = dict(
        gate["current_entry_provenance_qualification"], cycle=203, source_validation_cycle=203,
        linked_byte_count=7046784, linked_sha256="557687A9F39EEECFFD839A8619D696CEBB4E391B229778162725752C72B4D9AA",
        canonical_byte_count=530072, canonical_sha256=kernel_sha, entry_receipt_sha256=entry_sha,
        source_binding_count=74, latest_reproduction_cycle=203,
    )
    gate["current_task_stack_qualification"] = dict(
        gate["current_task_stack_qualification"], cycle=203, receipt_sha256=core_sha)
    gate["current_execution_qualification"] = dict(
        gate["current_execution_qualification"], cycle=203, receipt_sha256=core_sha, kernel_sha256=kernel_sha)
    gate["current_ownership_qualification"] = dict(
        gate["current_ownership_qualification"], cycle=203, host_qualification_cycle=203,
        scope="host203_only_prior_IPI_and_VM_receipts_historical", kernel_sha256=kernel_sha,
        reclamation_receipt_sha256=core_sha, entry_receipt_sha256=entry_sha,
        fresh_current_cycle_qemu_runs=0, live_receipt_source_current=False,
        current_boot_artifact_set_replay_pending=True, active_root_current_image_replay_complete=False,
        ap_runtime_live_integration_verified=False, virtual_memory_live_receipt_source_current=False,
        live_receipt_scope="historical_IPI_and_VM200_not_current_kernel_execution",
        source_current_scope="host_core_and_entry_only", historical_record="historical_cycle202_ownership_qualification",
    )
    gate["current_ipi_mailbox_oracle_gap"] = dict(
        gate["current_ipi_mailbox_oracle_gap"], cycle=203, remaining_affected_profiles=25,
        newly_requalified_profiles=[], current_kernel_live_replay_pending=True)
    gate["current_control_execution_audit"] = dict(gate["current_control_execution_audit"], cycle=203)
    for name in ("preemption_control_execution_audit", "deferred_transaction_qualification",
                 "symbol_admission_qualification", "deferred_control_qualification"):
        gate["current_" + name] = dict(
            gate["current_" + name], applies_to_current_source=False,
            current_kernel_live_replay_pending=True, current_receipt_admitted=False,
            historical_record="historical_cycle202_" + name)
    gate["current_smp_transaction_qualification"] = {
        "cycle": 203, "move_id": "N12-SCHED-SMP-001",
        "requirements": ["ADD-N12-SCHED-SMP-001", "ADD-N36-RECEIPT-COVERAGE-001"],
        "status": "native_host_transactions_verified_current_boot_and_controls_pending",
        "scope": "exclusive_controller_state_transactions_not_cross_CPU_atomicity",
        "initial_native_tests": 18, "initial_native_passed": 11, "initial_native_failed": 7,
        "initial_injector_error": "owner_epoch_fault_also_staled_ticket_before_counter_path",
        "initial_log_sha256": "FAA4FE09FFA2DF5F6D4D00C016E9E0786A60B9679378892E71C4804038B95863",
        "corrected_before_log_sha256": "6DFDFCC04DF604EDFF86DA114FE0076CC3C071DF774B8D9527F487CE29635324",
        "same_tests_after_repair_passed": 18,
        "same_tests_after_log_sha256": "4E836D15EA93E1FBC3C75A95B7063501EA4F71CF78B611B53731976B59C51629",
        "final_native_tests_per_profile": 19, "host_optimization_levels": [0, 3],
        "disabled_native_variants_detected": 9, "focused_python_test_methods": 2,
        "combined_transaction_methods_passed": 4,
        "control_log_sha256": "E2DB3A21CB7B7971FBEC84ADC982780C4CF9BBEAD0C805E994C2ECA7AF14A6F9",
        "sources": {
            "native/kernel/src/scheduler_smp.rs": "392A986CFEC545BB56A54A669005011096FAE243FB863036C6FC3F06909461D4",
            "tests/fixtures/pksched4_transaction_probe.rs": "13C3D0934B6FE435404DABAA0D2B22F913B556AE4D0A25BD809972D435DC8F56",
            "tests/test_native_smp_transactions.py": "321374D12C8C113A4F6887E8255F9241FF005D0171A199419F4E2DB71667947F",
        },
        "kernel_sha256": kernel_sha, "kernel_bytes_changed": True,
        "entry_receipt_sha256": entry_sha, "core_receipt_sha256": core_sha,
        "entry_attempts_rejected": [
            {"cause": "stale_manifest_contract_digest", "elapsed_seconds": 0.406,
             "log_sha256": "8B7A2FD1407928AFC246EC5F5DC7F60F934DCBAB0DBC2237D990731ED7A4687E"},
            {"cause": "stale_live_build_ID_literal", "elapsed_seconds": 29.734,
             "log_sha256": "39F8B3AADF65970D5CE6486B3B47CE6DF27B0BDC340C665E0CE1E054090ED223"},
        ],
        "superseded_preliminary_core_sha256": "60D1BACCF77B282D71B5B97170A68F302191774CD3B01F714CB6C8B986C5C908",
        "superseded_entry3_receipt_sha256": "CDD7102D91D5B24A61E9BF5930A087CF8DBEA6561B7FBF0F6537BA637F5D3BE9",
        "superseded_reason": "final_manifest_and_frozen_test_binding_reconciliation_not_native_semantic_change",
        "remote_ack_synthesized_or_accepted_by_preflight": False,
        "recorded_evidence_admission_repaired": False, "constant_only_control_groups_replaced": 0,
        "remaining_SMP_control_groups": 16, "remaining_global_control_groups_at_least": 51,
        "new_kernel_qemu_runs": 0, "cross_cpu_atomicity_proved": False, "production_ready": False,
    }
    gate["current_closeout_regression"] = {
        "cycle": 203, "status": "pass", "scope": "native_SMP_host_core_entry_not_full_canonical",
        "tests_run": 109, "tests_passed": 109, "tests_failed": 0, "tests_skipped": 0,
        "elapsed_seconds": 149.640,
        "log_sha256": "8685E792EBA51FF228060100FFF386884F22B5B0C45179DB8A9255D44640FF70",
        "includes_corrected_focused_and_metadata_tests": True,
        "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        "initial_conservation": {"status": "pass", "archived_parent_current_records": 18,
            "architecture_bindings": 344, "test_inventory": 1084, "selected_checks": "2/27",
            "all_prior_boot_receipts_and_normative_charter_preserved": True,
            "only_SMP_flag_reopened_and_no_phase_status_changed": True},
        "initial_metadata": {"tests_run": 50, "tests_passed": 40, "tests_failed": 10,
            "elapsed_seconds": 12.407, "cause": "historical_tests_still_accepted_previous_image_evidence",
            "log_sha256": "C75A773AE4F83FF4FE89C3C4B359CDBC17CB68967CD8E86B3B356A97E7BDF54C"},
        "second_metadata": {"tests_run": 50, "tests_passed": 49, "tests_failed": 1,
            "elapsed_seconds": 18.219, "cause": "remaining_old_dependency_pending_count",
            "log_sha256": "2AD90AEC5035CF84B82EB8A7F4E4C2E9A9B92CD3C7B1F8AD753A72157BB57C67"},
        "initial_focused": {"tests_run": 58, "tests_passed": 57, "tests_failed": 1, "tests_skipped": 0,
            "elapsed_seconds": 126.906, "cause": "frozen_entry_test_still_pinned_prior_kernel_hash",
            "log_sha256": "B223BC17EFCA7F3880A00CEABF689D576526198F76BF066A6C2DBE8681D06F27"},
        "core": {"stages_passed": 17, "elapsed_seconds": 37.797,
            "log_sha256": "2AB8D226E34E1EC1FD773B540A39E2E660DA56CAD8E6063453F24A14CBE3DD9D"},
        "entry": {"clean_builds": 2, "kernel_tests": 246, "rejection_cases": 43, "elapsed_seconds": 38.625,
            "log_sha256": "412A13BDE4C2505F96C32DD727C7BF678B58582F0CFC97FD19344E6B6C3D36F5"},
        "entry_gate": {"tests_passed": 1, "rejection_cases": 12,
            "log_sha256": "208927165B913AA833216B549755DC2F394BBC064E44FCF4AABEA2281672AE34"},
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 203: " + checkpoint + " repairs native SMP acknowledgement, dispatch, cancellation, timeout "
        "and retirement transactions. Seven reproduced failures now pass; expanded 19-case debug/optimized "
        "runs and nine disabled variants verify the repair. All 17 core stages, two matching kernel builds, "
        "246 kernel tests, 43 image controls and 12 entry-gate rejections pass."
    )
    gap = (
        "Kernel bytes changed. Selected readiness is 2/27: 25 source-dependent profiles require replay from "
        + next_move + ", including policy. SMP recorded admission and 16 constant-only groups remain open "
        "within the existing 51-group lower bound. FLAG-N12-SCHED-SMP-001 is reopened for current-source "
        "qualification. Full exact-candidate canonical/Doctor/release/publication/check/review gates precede "
        "main merge. No new-kernel guest boot, cross-CPU atomicity, ISO, phase closure or production promotion."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N5", "N6", "N12", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 203 source inventory: 1084 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N12-SCHED-SMP-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
        if flag["id"] == "FLAG-N12-SCHED-SMP-001":
            flag["status"] = "open"
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle204(roadmap, test_count)


def apply_cycle204(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle204-current-kernel-boot-replay.md"
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for key, value in list(gate.items()):
        if key.startswith("current_") and isinstance(value, dict):
            suffix = "source_projection" if key == "current_focused_source_projection" else key.removeprefix("current_")
            gate["historical_cycle203_" + suffix] = copy.deepcopy(value)
    roadmap["baseline"]["pooleos_cycle"] = 204
    roadmap["execution_protocol"].update(last_updated_cycle=204, selected_move_id="N5-SYMBOLS-SEMANTICS-001",
                                         owner_independent_next_move_id="N7-TRAP-001")
    roadmap["execution_protocol"]["required_records"].insert(0, checkpoint)
    gate["qualification_status"] = "current_kernel_boot_chain_qualified_CPU_and_downstream_replay_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=204)
    gate["current_focused_source_projection"] = {
        "cycle": 204, "scope": "27_selected_native_checks_not_full_canonical_audit",
        "passed_checks": 8, "total_checks": 27, "pending_downstream_native_checks": 19,
        "passing_profiles": ["native_kernel_entry_readiness", "native_symbol_readiness", "native_policy_readiness",
            "native_kernel_load_readiness", "native_pooleboot_readiness", "native_kernel_revalidation_readiness",
            "native_kernel_transfer_readiness", "native_kernel_errata_policy_readiness"],
        "final_receipt_fresh_qemu_runs": 6, "kernel_entry_runs": 2,
        "next_dependency_move_id": "N7-TRAP-001",
        "required_next_gate": "current_image_CPU_memory_scheduler_replay_and_executed_SMP_controls",
        "canonical_full_replay_performed": False, "production_ready": False,
    }
    bindings = [
        {"profile": "symbol", "path": "runs/native_symbol_readiness.json", "sha256": "C9FF1E5347A831045E46BCF8DCF2CD77D25497D68BD48B177B80162026901C99", "fresh_runs": 0, "negative_controls": 158},
        {"profile": "policy", "path": "runs/native_policy_readiness.json", "sha256": "56E724804B70A4B530D7410D651DF1E88773273C501EE65A7E7DF8D4A659B8B5", "fresh_runs": 0, "negative_controls": 116},
        {"profile": "kernel_load", "path": "runs/native_kernel_load_readiness.json", "sha256": "AC8B3954741AB689BD07B5875949B2437B63664CD47E09E055C04A65E99701B7", "fresh_runs": 2, "negative_controls": 155},
        {"profile": "pooleboot", "path": "runs/native_pooleboot_readiness.json", "sha256": "48A507A2059BC400EA5A2A9F37626874A267870BF946A34E3B0069213787CCDE", "fresh_runs": 2, "negative_controls": 155},
        {"profile": "kernel_revalidation", "path": "runs/native-kernel-revalidation-readiness.json", "sha256": "2A1230B151E1494B3C6C9EFF712A7529194B5F27180A1CE5D882D1B98733450E", "fresh_runs": 0, "negative_controls": 36},
        {"profile": "kernel_transfer", "path": "runs/native-kernel-transfer-readiness.json", "sha256": "95AEEF7FF80A960096D8FC236017C9789ACD7B96DF085E73F857EEADB047AB85", "fresh_runs": 2, "negative_controls": 58},
    ]
    gate["current_boot_chain_qualification"] = {
        "cycle": 204, "source_validation_cycle": 204, "status": "single_host_boot_replay_pass",
        "applies_to_current_source": True, "kernel_sha256": gate["current_entry_provenance_qualification"]["canonical_sha256"],
        "qualified_profiles": [b["profile"] for b in bindings], "readiness_replay_required_profiles": [],
        "receipt_bindings": bindings, "embedded_entry_provenance_replay_pending": False,
        "fresh_qemu_runs": 6, "kernel_entry_runs": 2, "focused_python_tests": 81,
        "kernel_host_tests": 246, "loader_rust_tests": 331, "pooleboot_host_tests": 8,
        "retained_files": 9, "retained_bytes": 11952, "manifest_bytes": 2615,
        "inner_artifacts": 6, "inner_bytes": 8761, "inner_payload_bytes": 8185,
        "inner_set_sha256": "C48B7C41E73F79F0326B9E0146BF9DC001B902E5A95F5560400FE854530C9B58",
        "trust_policy_sha256": "DF9BD076267061F731263B86BDE62EBE161B8666605EDC3AA32606870EEE2049",
        "trust_state_sha256": "073CEB317F1B6314274452846AC1959F988EFE9537A72456AEFB493F1DEB69CE",
        "manifest_sha256": "EF6A00FE89683E8C44AC8FEF1C1F2F626F82654A5721C18AD44B2307835BD85B",
        "real_image_trust_independently_reconstructed": True, "golden_fixture_is_actual_kernel": False,
        "independent_previous_identity_rejection_cases": 20, "component_validators_bypassed_only_in_negative_test": True,
        "terminal": "unsigned-denial-halt", "authority_created": 0, "state_writes": 0, "firmware_calls_after_exit": 0,
        "kernel_bytes_changed_this_cycle": False, "entry_and_core_receipts_unchanged": True,
        "complete_host_attestation": False, "second_builder_reproduced": False, "n5_exit_gate_satisfied": False,
        "current_candidate_full_gate_passed": False, "production_ready": False,
    }
    gate["current_symbol_admission_qualification"] = {
        "cycle": 204, "original_repair_cycle": 198, "applies_to_current_source": True,
        "historical_repair_record": "historical_cycle202_symbol_admission_qualification",
        "symbol_receipt_sha256": bindings[0]["sha256"], "current_receipt_admitted": True,
        "recorded_corruption_cases": 650, "runtime_rejected": 650, "aggregate_gate_rejected": 650,
        "native_parser_tests": 4, "native_control_cases": 158, "debug_builds_byte_identical": 2,
        "parser_differential_cases": 16384, "lookup_differential_cases": 16384,
        "rejected_output_preservation_cases": 2, "pre_repair_audit_reexecuted_this_cycle": False,
        "coherent_forgery_excluded": False, "recorded_consistency_is_freshness_or_authentication": False,
        "production_ready": False,
    }
    gate["current_ownership_qualification"] = dict(
        gate["current_ownership_qualification"], current_boot_artifact_set_replay_pending=False,
        boot_artifact_replay_cycle=204, source_current_scope="host_core_and_entry203_boot204_not_AP_or_VM")
    gate["current_entry_provenance_qualification"] = dict(
        gate["current_entry_provenance_qualification"], latest_reproduction_cycle=204)
    gate["current_ipi_mailbox_oracle_gap"] = dict(gate["current_ipi_mailbox_oracle_gap"], cycle=204,
        remaining_affected_profiles=19, newly_requalified_profiles=[b["profile"] for b in bindings])
    gate["current_control_execution_audit"] = dict(gate["current_control_execution_audit"], cycle=204)
    gate["current_closeout_regression"] = {
        "cycle": 204, "status": "pass", "scope": "boot_chain_and_admission_not_full_canonical",
        "tests_run": 81, "tests_passed": 81, "tests_failed": 0, "tests_skipped": 0,
        "elapsed_seconds": 41.688, "log_sha256": "141727F1A0BFA8B4DB577BB43FB30FACFF5A12D0FD6238D607F464585EA6400B",
        "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        "failed_symbol_attempts": [
            {"cause": "previous_split_debug_identity", "elapsed_seconds": 27.218,
             "log_sha256": "828D527347D619BA596BDF3D39A0D7C913AD51327434A83A276AB7E823699074"},
            {"cause": "previous_PSYM1_golden_identity", "elapsed_seconds": 0.438,
             "log_sha256": "3D1F214FC6B947A144168C40794CD12D35AE025C5E8282AE886A1AD7BCA93F56"},
        ],
        "failed_receipts_admitted": False, "canonical_full_replay_performed": False,
        "merge_qualified": False, "production_ready": False,
        "combined_scoped_regression": {
            "status": "pass", "tests_run": 188, "tests_passed": 188, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 188.969, "log_sha256": "4441B394B1762FA1D45558FB3A9F764F6D4B9951B8B111FF192AA493E380B5C7",
            "includes_focused_native_transactions_entry_reproduction_publication_and_metadata": True,
            "executed_before_result_recording": True, "source_unchanged": True, "owner_report_unchanged": True,
        },
        "initial_metadata": {
            "tests_run": 43, "tests_passed": 43, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 18.953, "log_sha256": "E0AF2B0FE42DA70E69212534DAA81B61D1DD564E0EB22027911774C25A0C44C5",
        },
        "initial_conservation": {
            "status": "pass", "archived_parent_current_records": 19, "architecture_bindings": 345,
            "test_inventory": 1086, "selected_checks": "8/27", "all_phase_and_flag_statuses_preserved": True,
            "all_prior_checkpoints_native_source_entry_core_and_normative_charter_preserved": True,
        },
    }
    evidence = (
        "Cycle 204: " + checkpoint + " qualifies symbols, policy, load, PooleBoot, kernel revalidation and "
        "transfer on unchanged kernel203. Six fresh virtual boots include two kernel entries ending in "
        "unsigned-development denial. All 81 focused tests pass, including 650 corrupt symbol records "
        "and 20 independent previous-image pin rejections."
    )
    gap = (
        "Selected current readiness is 8/27; 19 CPU/memory/SMP/scheduler profiles remain pending from "
        "N7-TRAP-001. At least 51 later control groups and SMP recorded admission remain open. "
        "No phase or flag closure, signed authority, second-builder reproduction, new ISO or production "
        "promotion. Full exact-candidate qualification still precedes main merge; branch backup is separate."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N5", "N6", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 204 source inventory: 1086 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N5-SYMBOL-BUNDLE-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle205(roadmap, test_count)


def apply_cycle205(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle205-current-kernel-cpu-replay.md"
    next_move = "N9-PMM-ACPI-CONSUMER-001"
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for key, value in list(gate.items()):
        if key.startswith("current_") and isinstance(value, dict):
            suffix = "source_projection" if key == "current_focused_source_projection" else key.removeprefix("current_")
            gate["historical_cycle204_" + suffix] = copy.deepcopy(value)
    roadmap["baseline"]["pooleos_cycle"] = 205
    roadmap["execution_protocol"].update(last_updated_cycle=205, selected_move_id="N7-TRAP-001",
                                         owner_independent_next_move_id=next_move)
    roadmap["execution_protocol"]["required_records"].insert(0, checkpoint)
    gate["qualification_status"] = "current_kernel_CPU_qualified_fourteen_dependencies_and_scheduler_controls_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=205)
    rows = (
        ("trap", "6CCBE079A996F2257D9605047331DD7FFCF51130F97B4F173E50A68911208674", 6, 51,
         "24BA6A9C62976CF70FF9481440D1E1864DF6B69B772E3B9800C46F45AF0DA8FF", 100.407),
        ("cpu_policy", "9EA8402056FB8A83F37AA8A541043B79F55A9AE656AA4B442D6E94AA7FEE8014", 2, 41,
         "CFA41675A79CE67949D1FDB8D08F791EB2FD1115237010D33465135306D1CE23", 64.016),
        ("xstate_policy", "48095CE52295F2C8512DD2CBAA7581FE4C1F3DA2EEA5194843299901D35CC551", 2, 43,
         "4260145CE808D54618100843E5797A22DAFA156F94093C1D222D6D99730A162A", 66.750),
        ("xstate_exception", "5EEA8DA366205957DF6C735D54A46A6B80EC7264D700F80A5F7D775B02EEAAE0", 2, 43,
         "F3ED8801D7E59F458EBE9E20B63EED505D5DEF7034E3E58654DA297E074BF60D", 78.516),
        ("privilege_msr_policy", "2C4F4AD1A98C3626182DCFEDB1D9C2664BD34E9090905E5C4D96A054CCD11CD7", 2, 47,
         "9B9A31059D4151F9B9A62622272025F3EDB8EEF33A8C29EEA6267DBE5A72AE32", 76.563),
    )
    bindings = [dict(profile=profile, path="runs/native-kernel-" + profile.replace("_", "-") + "-readiness.json",
                     sha256=digest, fresh_runs=runs, negative_controls=controls, kernel_host_tests=246,
                     execution_log_sha256=log, elapsed_seconds=seconds)
                for profile, digest, runs, controls, log, seconds in rows]
    gate["current_cpu_qualification"] = {
        "cycle": 205, "source_validation_cycle": 205, "status": "single_host_cpu_replay_pass",
        "scope": "five_N7_profiles_on_unchanged_Cycle203_kernel", "applies_to_current_source": True,
        "kernel_sha256": gate["current_entry_provenance_qualification"]["canonical_sha256"],
        "qualified_profiles": [b["profile"] for b in bindings], "receipt_bindings": bindings,
        "readiness_replay_required_profiles": [], "embedded_entry_provenance_replay_pending": False,
        "fresh_qemu_runs": 14, "superseded_initial_runs": 0, "negative_control_groups": 225,
        "kernel_host_tests_per_qualifier": 246, "whpx_exception_runs": 2, "expected_tcg_limitation_probes": 1,
        "exception_deliveries_per_run": 3, "exception_recoveries_per_run": 2,
        "focused_python_tests": 54, "aggregate_gate_regression_cases": 26,
        "new_previous_image_and_wrong_typed_pin_rejection_cases": 5,
        "embedded_entry_rejection_cases": 80, "invalid_current_entry_dependency_cases": 20,
        "recorded_pair_count": 7, "recorded_exit_rejection_cases": 98,
        "recorded_coverage_rejection_cases": 112, "recorded_evidence_rejection_cases": 161,
        "recorded_evidence_total_rejection_cases": 371,
        "recorded_control_rejection_cases": {"trap": 1084, "cpu_policy": 546, "xstate_policy": 572,
                                           "xstate_exception": 572, "privilege_msr_policy": 624},
        "recorded_control_total_rejection_cases": 3398,
        "recorded_evidence_rejections_exercised_through_runtime_and_gate": True,
        "historical_admission_repair_record": "historical_cycle202_cpu_qualification",
        "pre_repair_audit_reexecuted_this_cycle": False, "positive_receipts_rebound_in_tests": False,
        "pair_validation_is_freshness_or_authentication": False, "coherent_forgery_excluded": False,
        "trap_control_validator_calls": 51, "disabled_trap_validator_detected": True,
        "entry_identity_comparison": "canonical_JSON_typed_equality",
        "canonical_kernel_changed_this_cycle": False, "entry_and_core_receipts_unchanged": True,
        "second_builder_reproduced": False, "target_hardware_qualified": False,
        "n7_exit_gate_satisfied": False, "current_candidate_full_gate_passed": False, "production_ready": False,
    }
    passing = ["native_" + name + "_readiness" for name in (
        "kernel_entry", "symbol", "policy", "kernel_load", "pooleboot", "kernel_revalidation",
        "kernel_transfer", "kernel_trap", "kernel_cpu_policy", "kernel_errata_policy",
        "kernel_xstate_policy", "kernel_xstate_exception", "kernel_privilege_msr_policy")]
    gate["current_focused_source_projection"] = {
        "cycle": 205, "scope": "27_selected_native_checks_not_full_canonical_audit",
        "passed_checks": 13, "total_checks": 27, "pending_downstream_native_checks": 14,
        "passing_profiles": passing, "final_receipt_fresh_qemu_runs": 14, "kernel_entry_runs": 14,
        "expected_tcg_limitation_probes": 1, "run_count_scope": "CPU205_not_retained_boot204",
        "next_dependency_move_id": next_move,
        "required_next_gate": "fourteen_memory_IRQ_SMP_scheduler_atomic_lock_profiles_then_controls_and_full_candidate",
        "focused_python_tests_passed": 54, "focused_python_tests_skipped": 0,
        "canonical_full_replay_performed": False, "production_ready": False,
    }
    gate["current_entry_provenance_qualification"] = dict(
        gate["current_entry_provenance_qualification"], latest_reproduction_cycle=205)
    gate["current_ipi_mailbox_oracle_gap"] = dict(gate["current_ipi_mailbox_oracle_gap"], cycle=205,
        remaining_affected_profiles=14, newly_requalified_profiles=[b["profile"] for b in bindings])
    gate["current_control_execution_audit"] = dict(gate["current_control_execution_audit"], cycle=205)
    gate["current_closeout_regression"] = {
        "cycle": 205, "status": "pass", "scope": "five_CPU_profiles_not_full_canonical",
        "tests_run": 54, "tests_passed": 54, "tests_failed": 0, "tests_skipped": 0,
        "elapsed_seconds": 179.343, "log_sha256": "D2E79D016939E8D878FEDABCF471825C8DEEF0742CF8DB7700042639061E1A29",
        "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        "obsolete_trap_aggregate_pin_observed_rejecting_current_receipt": True,
        "obsolete_pin_reconciled_from_measured_kernel_not_claim_bypass": True,
        "initial_metadata_regression": {
            "tests_run": 52, "tests_passed": 52, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 24.907,
            "log_sha256": "B31841C8F7022131396AA3E7E67378B4F128B8EA05E3589BC187D576424F2053",
        },
        "combined_scoped_regression": {
            "tests_run": 242, "tests_passed": 242, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 364.890,
            "log_sha256": "FB57C8B9D99427CD73CB2F594E8AE0BC58C950796F5F7E5A8D01AB2F66DEB5B0",
            "scope": "boot_CPU_native_transactions_entry_core_host_publication_metadata_not_full_canonical",
            "includes_focused_and_metadata_tests": True,
            "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        },
        "initial_conservation": {
            "status": "pass", "archived_parent_current_records": 19,
            "architecture_source_bindings": 346, "discovered_test_inventory": 1087,
            "prior_checkpoints_native_entry_core_owner_checklist_ISO_normative_charter_preserved": True,
            "all_phase_and_flag_statuses_preserved": True,
        },
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 205: " + checkpoint + " qualifies five CPU profiles on unchanged kernel203: fourteen fresh "
        "virtual boots, 225 controls, two WHPX exception runs and a separate expected TCG limitation probe. "
        "All 54 focused tests pass, including 3398 corrupt control records, 371 run-evidence corruptions "
        "and 26 aggregate identity/promotion rejections. The obsolete trap image pin is reconciled. "
        "Combined scoped regression passes 242/242 with zero skips; metadata passes 52/52 and "
        "conservation verifies 346 bindings and 19 unchanged archived records. Counts overlap."
    )
    gap = (
        "Selected readiness is 13/27; fourteen memory/IRQ/SMP/scheduler/atomic/lock profiles remain from "
        + next_move + ". SMP recorded admission and at least 51 later executed-control groups remain open. "
        "No phase, flag, kernel byte, ISO or production status changes; full exact-candidate qualification "
        "still precedes main merge. This is not all-vector, user-context, physical-target or N7-exit proof."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N7", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 205 source inventory: 1087 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N7-TRAP-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle206(roadmap, test_count)


def apply_cycle206(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle206-memory-and-multiprocessor-replay.md"
    next_move = "N12-SCHED-001"
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for key, value in list(gate.items()):
        if key.startswith("current_") and isinstance(value, dict):
            suffix = "source_projection" if key == "current_focused_source_projection" else key.removeprefix("current_")
            gate["historical_cycle205_" + suffix] = copy.deepcopy(value)
    roadmap["baseline"]["pooleos_cycle"] = 206
    roadmap["execution_protocol"].update(last_updated_cycle=206,
        selected_move_id="N9-PMM-ACPI-CONSUMER-001", owner_independent_next_move_id=next_move)
    roadmap["execution_protocol"]["required_records"].insert(0, checkpoint)
    gate["qualification_status"] = "six_current_memory_IRQ_SMP_profiles_eight_scheduler_dependencies_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=206)
    rows = (
        ("physical_memory", "83129AB1A6AC4CBACD2C55DC45B8564BC7C21D9571508405A931978C4E0E8A40", 191, 191,
         "73D78CC992A80B448CB62D488AC4EFA73BF8EED5DBCA5B8F76C37B5AF855061A", 74.390,
         {"exit": 14, "coverage": 16, "evidence": 29, "accounting": 7, "summary": 168}),
        ("virtual_memory", "23EFB1654F8EF006C19DE1E0AA635E7FDD3FA7EE6BE57FE5A7F4F5BC65BDB801", 48, 48,
         "3F150DB57A3859B6474CCAE0679F8D501C0B6264436950A77C7EDC5EE719DE52", 65.609,
         {"exit": 14, "coverage": 16, "evidence": 28, "accounting": 7, "summary": 50}),
        ("interrupt_time", "8A84236C3725A6CB8C40655BC4171228481535B5BD081BA66F4AF16B0ED118CC", 58, 58,
         "047FF2DF6EB68D3816503F9E81C83FA820E6D47828691C1D6F48D6B95C2F54B1", 68.328,
         {"exit": 14, "coverage": 16, "evidence": 23, "shape": 3, "observation": 145, "summary": 22, "clock": 6}),
        ("smp_first_ap", "D4B2ED8AD2463C2EFD1923352DF34A359FF09E41C688354039EB897AD8C770FC", 72, 72,
         "6A25DBB4AE5AC7A23E7328961F320F5551C3A189A91211F1B4C970530B8614E1", 72.735,
         {"exit": 14, "coverage": 16, "evidence": 23, "shape": 3, "dynamic-policy": 2, "observation": 69, "summary": 30, "raw-stop": 2}),
        ("smp_percpu_runtime", "9543CAC00F85386C15DC788210FA1613BC34840A65FC7BAE6E1C292C0E205314", 19, 159,
         "BEDC73DE58B81C522F0C0F23D34D0E0573C50C2BA8A22ADF37436DC4F4E4C890", 60.063,
         {"exit": 14, "coverage": 16, "evidence": 23, "shape": 3, "dynamic-policy": 7, "observation": 108, "summary": 40, "raw-stop": 3, "controls": 39}),
        ("smp_ipi", "FFBD31E6CD151CBD6D1E483F5FBD6D4CFA8D5D394E06481BE3F7989AF3FE4A52", 33, 609,
         "D6CBBA9E84715032D9F38CC00341288DDD16A40EBC7371B872D74677860066A6", 71.406,
         {"exit": 14, "coverage": 16, "evidence": 23, "shape": 3, "dynamic-policy": 8, "observation": 739, "summary": 34, "raw-frame": 2, "controls": 67}),
    )
    bindings = [dict(profile=profile, path="runs/native-kernel-" + profile.replace("_", "-") + "-readiness.json",
                     sha256=digest, fresh_runs=2, negative_controls=controls, hostile_cases=cases,
                     kernel_host_tests=246, execution_log_sha256=log, elapsed_seconds=seconds,
                     recorded_evidence_cases=mutations)
                for profile, digest, controls, cases, log, seconds, mutations in rows]
    qualified = [b["profile"] for b in bindings]
    retained = gate["current_dependency_qualification"]
    pending = [p for p in retained["readiness_replay_required_profiles"] if p not in qualified]
    gate["current_dependency_qualification"] = {
        "cycle": 206, "source_validation_cycle": 206, "status": "six_current_profiles_eight_pending",
        "scope": "six_fresh_memory_IRQ_AP_IPI_profiles_on_unchanged_Cycle203_kernel",
        "applies_to_current_source": True, "all_fourteen_profiles_current": False,
        "qualified_profiles": qualified, "newly_qualified_profiles": qualified,
        "readiness_replay_required_profiles": pending, "embedded_entry_provenance_replay_pending": True,
        "fresh_qemu_runs": 12, "superseded_initial_runs": 0,
        "run_count_scope": "Cycle206_six_profiles_only_not_retained_CPU_or_boot_runs",
        "negative_control_groups": 421, "negative_control_cases": 1137,
        "kernel_sha256": retained["kernel_sha256"], "receipt_bindings": bindings,
        "kernel_host_tests_per_qualifier": 246, "focused_python_tests": 93,
        "recorded_evidence_case_total": 1896, "recorded_evidence_scope": "six_fresh_profiles",
        "recorded_evidence_rejections_exercised_through_runtime_and_gate": True,
        "positive_receipts_rebound_in_tests": False, "pair_validation_is_freshness_or_authentication": False,
        "disabled_PMM_parser_and_memory_oracle_detected": True, "PMM_marker_validator_calls": 189,
        "raw_mailbox_rejection_cases": 360, "independent_IPI_pin_rejection_cases": 7,
        "memory_gate_rejection_cases": 20, "canonical_kernel_changed_this_cycle": False,
        "control_execution_complete": False, "unproven_per_control_rejection_groups_at_least": 51,
        "current_candidate_full_gate_passed": False, "production_ready": False,
    }
    gate["current_ownership_qualification"] = dict(gate["current_ownership_qualification"], cycle=206,
        scope="retained_host_core203_and_fresh_bounded_VM_IPI206", fresh_current_cycle_qemu_runs=4,
        live_replay_cycle=206, live_receipt_scope="two_VM206_and_two_IPI206_runs",
        live_receipt_source_current=True, active_root_current_image_replay_complete=True,
        virtual_memory_live_receipt_source_current=True, ap_runtime_live_integration_verified=True,
        virtual_memory_live_replay_cycle=206, virtual_memory_receipt_sha256=bindings[1]["sha256"],
        smp_receipt_sha256=bindings[5]["sha256"], source_current_scope="host_core203_boot204_and_bounded_VM_IPI206")
    passing = gate["current_focused_source_projection"]["passing_profiles"]
    gate["current_focused_source_projection"] = {
        "cycle": 206, "scope": "27_selected_native_checks_not_full_canonical_audit",
        "passed_checks": 19, "total_checks": 27, "pending_downstream_native_checks": 8,
        "passing_profiles": passing + ["native_kernel_" + p + "_readiness" for p in qualified],
        "final_receipt_fresh_qemu_runs": 12, "kernel_entry_runs": 12, "superseded_initial_qemu_runs": 0,
        "run_count_scope": "Cycle206_six_memory_IRQ_SMP_profiles_not_retained_CPU_or_boot_runs",
        "next_dependency_move_id": next_move,
        "required_next_gate": "eight_scheduler_atomic_lock_profiles_SMP_admission_controls_then_full_candidate",
        "focused_python_tests_passed": 93, "focused_python_tests_skipped": 0,
        "recorded_evidence_rejection_cases": 1896, "canonical_full_replay_performed": False, "production_ready": False,
    }
    gate["current_entry_provenance_qualification"] = dict(gate["current_entry_provenance_qualification"], latest_reproduction_cycle=206)
    gate["current_ipi_mailbox_oracle_gap"] = dict(gate["current_ipi_mailbox_oracle_gap"], cycle=206,
        remaining_affected_profiles=8, newly_requalified_profiles=qualified, current_kernel_live_replay_pending=False)
    gate["current_control_execution_audit"] = dict(gate["current_control_execution_audit"], cycle=206)
    gate["current_closeout_regression"] = {
        "cycle": 206, "status": "pass", "scope": "six_memory_IRQ_SMP_profiles_and_independent_memory_IPI_gates",
        "tests_run": 93, "tests_passed": 93, "tests_failed": 0, "tests_skipped": 0,
        "elapsed_seconds": 124.203, "log_sha256": "56A861856A52EACFEBB95935FB0C1954A13089477F1663D5FF1A7130B0D55FE0",
        "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        "initial_IPI_admission": {
            "status": "rejected", "attempts": 1, "runtime_validated": True, "guest_qualifier_passed": True,
            "actual_gate_detail": "PKSMP5 embedded kernel identity changed",
            "cause": "aggregate_gate_retained_Cycle197_kernel_hash", "candidate_sha256": bindings[5]["sha256"],
            "chain_return_code": 1, "failed_guest_runs": 0, "guest_evidence_rewritten_or_rerun": False,
        },
        "corrected_IPI_admission": {"status": "pass", "same_candidate_sha256": bindings[5]["sha256"],
            "runtime_and_actual_gate_passed": True, "independent_pin_rejection_cases": 7},
        "initial_metadata_regression": {
            "status": "fail", "tests_run": 53, "tests_passed": 50, "tests_failed": 3, "tests_skipped": 0,
            "elapsed_seconds": 27.656,
            "log_sha256": "99AC81E9227F00608F528A5FE1ADA10F6C0516C52BCD2735C6848F76ED2DD1BA",
            "cause": "three_current_progress_assertions_retained_previous_13_of_27_state",
        },
        "corrected_metadata_regression": {
            "status": "pass", "tests_run": 53, "tests_passed": 53, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 27.844,
            "log_sha256": "B6410FA2EB9047D5E2765ACAA7B7E59ED5DAE53FF8B0220EA47CB36CB5145492",
            "historical_hashes_and_records_preserved": True,
        },
        "combined_scoped_regression": {
            "status": "pass", "tests_run": 283, "tests_passed": 283, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 324.219,
            "log_sha256": "07BF462CF9D3769C3B98B69ABE16B9E7443E4733025A911CFB2BDAC940D3008F",
            "scope": "boot_native_transactions_entry_core_host_memory_IRQ_SMP_publication_metadata_not_full_canonical",
            "includes_focused_and_metadata_tests": True, "executed_before_result_recording": True,
            "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        },
        "initial_conservation": {
            "status": "pass", "archived_parent_current_records": 19, "architecture_bindings": 347,
            "test_inventory": 1088, "selected_checks": "19/27",
            "native_other_receipts_owner_ISO_checklist_normative_charter_preserved": True,
            "all_phase_and_flag_statuses_preserved": True,
        },
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 206: " + checkpoint + " qualifies six memory/IRQ/SMP profiles on unchanged kernel203. "
        "Twelve virtual boots, 421 control groups covering 1137 cases and 93 focused tests pass, including "
        "1896 corrupted records and 360 raw-mailbox cases. The stale IPI aggregate pin rejection is "
        "preserved; its measured correction admits identical guest evidence with seven pin rejections. "
        "Combined scoped regression passes 283/283 with zero skips; corrected metadata passes 53/53 "
        "and conservation verifies 347 bindings and 19 unchanged archived records. Counts overlap."
    )
    gap = (
        "Selected readiness is 19/27; eight scheduler/atomic/lock profiles remain from " + next_move + ". "
        "SMP recorded admission and at least 51 later control groups remain open. No native byte, phase, "
        "flag, ISO or production status changes. General task/CPU retirement, physical hardware and N8/N9 "
        "exit remain unqualified; full exact-candidate qualification precedes main merge."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N8", "N9", "N10", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 206 source inventory: 1088 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N9-PMM-ACPI-CONSUMER-001", "FLAG-N9-VM-DIRECT-MAP-001",
                          "FLAG-N8-IRQ-001", "FLAG-N8-SMP-IPI-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle207(roadmap, test_count)


def apply_cycle207(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle207-current-kernel-scheduler-replay.md"
    next_move = "N12-SCHED-SMP-001"
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for key, value in list(gate.items()):
        if key.startswith("current_") and isinstance(value, dict):
            suffix = "source_projection" if key == "current_focused_source_projection" else key.removeprefix("current_")
            gate["historical_cycle206_" + suffix] = copy.deepcopy(value)
    roadmap["baseline"]["pooleos_cycle"] = 207
    roadmap["execution_protocol"].update(last_updated_cycle=207,
        selected_move_id="N12-SCHED-001", owner_independent_next_move_id=next_move)
    roadmap["execution_protocol"]["required_records"].insert(0, checkpoint)
    gate["qualification_status"] = "three_current_scheduler_profiles_five_SMP_atomic_lock_dependencies_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=207)
    rows = (
        ("scheduler", "scheduler", "57048B311D72A5F86677FF6D81B81584A7DECE90AD316DFA4775B5EA9A3149E7", 28, 115,
         "EA2DA7C2C1EAD263356F358D905FC279A492DDCB118A2CE6EC39B74A7A8874E0", 91.094,
         {"exit": 14, "coverage": 16, "evidence": 23, "shape": 4, "profile": 8, "observation": 37,
          "summary": 26, "host-probe": 30, "controls": 57, "root-shape": 3, "control-shape": 3}),
        ("scheduler_preempt", "scheduler-preemption", "8E3EEDDB9C0DFA7270CED165084289E1CE4D96C880BE797D6E0EE2B7EAB3AA14", 25, 226,
         "C4CA732801FB906F7442652BE154022EA0C59C4E633C31145D785E2F4E5A52F5", 100.000,
         {"exit": 14, "coverage": 16, "evidence": 23, "shape": 4, "profile": 8, "observation": 48,
          "summary": 22, "host-probe": 14, "controls": 51, "root-shape": 3, "control-shape": 3}),
        ("scheduler_deferred", "scheduler-deferred", "FAC1F18E866A871BFEF1F3569CB2667F5FDA36656FC9B0F4384F474C80AB0507", 30, 254,
         "E12A45434566B849DD8DC27938DC5EE50E8BFA45D9F58DD3867479C1C06D291E", 82.375,
         {"exit": 14, "coverage": 16, "evidence": 23, "shape": 12, "profile": 8, "observation": 54,
          "host-probe": 12, "controls": 121, "root": 3, "date": 10}),
    )
    bindings = [dict(profile=profile, path="runs/native-kernel-" + filename + "-readiness.json",
                     sha256=digest, fresh_runs=2, negative_controls=controls, hostile_cases=cases,
                     kernel_host_tests=246, execution_log_sha256=log, elapsed_seconds=seconds,
                     recorded_evidence_cases=mutations)
                for profile, filename, digest, controls, cases, log, seconds, mutations in rows]
    qualified = [b["profile"] for b in bindings]
    retained = gate["current_dependency_qualification"]
    gate["current_dependency_qualification"] = {
        "cycle": 207, "source_validation_cycle": 207, "status": "nine_current_profiles_five_pending",
        "scope": "retained_six_memory206_and_three_fresh_scheduler207_profiles_on_unchanged_kernel203",
        "applies_to_current_source": True, "all_fourteen_profiles_current": False,
        "qualified_profiles": retained["qualified_profiles"] + qualified, "newly_qualified_profiles": qualified,
        "readiness_replay_required_profiles": [p for p in retained["readiness_replay_required_profiles"] if p not in qualified],
        "embedded_entry_provenance_replay_pending": True,
        "fresh_qemu_runs": 6, "superseded_initial_runs": 0, "failed_guest_runs": 0,
        "run_count_scope": "Cycle207_three_scheduler_profiles_only_not_retained_memory_CPU_boot_runs",
        "negative_control_groups": 83, "negative_control_cases": 595,
        "executed_rejection_cases": 545, "native_boundary_cases": 50,
        "kernel_sha256": retained["kernel_sha256"], "receipt_bindings": retained["receipt_bindings"] + bindings,
        "kernel_host_tests_per_qualifier": 246, "focused_python_tests": 47,
        "generic_recorded_evidence_cases": 700, "additional_preemption_control_receipt_cases": 26,
        "additional_deferred_control_receipt_cases": 42, "recorded_evidence_case_total": 768,
        "recorded_evidence_scope": "three_fresh_scheduler_profiles",
        "recorded_evidence_rejections_exercised_through_runtime_and_gate": True,
        "independent_deferred_linked_identity_cases": 11,
        "disabled_preemption_native_variants_detected": 7, "disabled_deferred_native_variants_detected": 12,
        "positive_receipts_rebound_in_tests": False, "pair_validation_is_freshness_or_authentication": False,
        "canonical_kernel_changed_this_cycle": False, "control_execution_complete": False,
        "unproven_per_control_rejection_groups_at_least": 51,
        "current_candidate_full_gate_passed": False, "production_ready": False,
    }
    projection = gate["current_focused_source_projection"]
    gate["current_focused_source_projection"] = dict(projection, cycle=207,
        passed_checks=22, pending_downstream_native_checks=5,
        passing_profiles=projection["passing_profiles"] + ["native_kernel_scheduler_readiness",
            "native_kernel_scheduler_preemption_readiness", "native_kernel_scheduler_deferred_readiness"],
        final_receipt_fresh_qemu_runs=6, kernel_entry_runs=6,
        run_count_scope="Cycle207_three_scheduler_profiles_only", next_dependency_move_id=next_move,
        required_next_gate="SMP_recorded_admission_and_controls_five_profiles_then_full_candidate",
        focused_python_tests_passed=47, recorded_evidence_rejection_cases=768)
    gate["current_entry_provenance_qualification"] = dict(gate["current_entry_provenance_qualification"], latest_reproduction_cycle=207)
    gate["current_ipi_mailbox_oracle_gap"] = dict(gate["current_ipi_mailbox_oracle_gap"], cycle=207,
        remaining_affected_profiles=5, newly_requalified_profiles=qualified)
    gate["current_control_execution_audit"] = dict(gate["current_control_execution_audit"], cycle=207)
    for key, binding, original in (("current_preemption_control_execution_audit", bindings[1], 196),
                                   ("current_deferred_control_qualification", bindings[2], 202)):
        gate[key] = dict(gate[key], cycle=207, source_validation_cycle=207, original_repair_cycle=original,
            receipt_sha256=binding["sha256"], applies_to_current_source=True,
            current_kernel_live_replay_pending=False, current_receipt_admitted=True,
            aggregate_unproven_groups_at_least=51, original_failure_audits_reexecuted_this_cycle=False)
    gate["current_deferred_transaction_qualification"] = dict(gate["current_deferred_transaction_qualification"],
        status="historical_native_transaction_repair_current_live_replay_tracked_separately",
        historical_artifact_identity_retained=True,
        applies_to_current_source_scope="original_Cycle197_entry_and_core_artifacts_not_current_kernel",
        current_kernel_live_replay_pending=False, current_receipt_admitted=True,
        latest_live_replay_cycle=207, latest_live_receipt_sha256=bindings[2]["sha256"],
        latest_live_kernel_sha256=retained["kernel_sha256"])
    gate["current_closeout_regression"] = {
        "cycle": 207, "status": "pass", "scope": "scheduler_preemption_deferred_controls_and_independent_linked_identity",
        "tests_run": 47, "tests_passed": 47, "tests_failed": 0, "tests_skipped": 0,
        "elapsed_seconds": 60.817, "runner_elapsed_seconds": 61.703,
        "log_sha256": "8DF6223B8326D98D78E51DE13ABFE1C82BB06B32DF9EB5BD9583DB0561DDD272",
        "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        "initial_deferred_admission": {
            "status": "rejected", "runtime_validated": True, "guest_qualifier_passed": True,
            "actual_gate_detail": "PKSCHED3 host oracle, source, or linked switch audit changed",
            "cause": "aggregate_gate_retained_Cycle197_kernel_hash", "candidate_sha256": bindings[2]["sha256"],
            "chain_return_code": 1, "failed_guest_runs": 0, "guest_evidence_rewritten_or_rerun": False,
        },
        "corrected_deferred_admission": {"status": "pass", "same_candidate_sha256": bindings[2]["sha256"],
            "runtime_and_actual_gate_passed": True, "independent_linked_identity_rejection_cases": 11},
        "initial_metadata_regression": {
            "status": "fail", "tests_run": 54, "tests_passed": 50, "tests_failed": 4, "tests_skipped": 0,
            "elapsed_seconds": 27.094, "runner_elapsed_seconds": 27.860,
            "log_sha256": "E983C8747B345AA880FEDCE28FAB581D7FC0EAFCB60CCFE9971A4DA4268AA4B4",
            "cause": "current_projection_and_scheduler_entry_assertions_retained_previous_19_of_27_state",
            "native_runtime_failure": False,
        },
        "intermediate_metadata_regression": {
            "status": "fail", "tests_run": 54, "tests_passed": 52, "tests_failed": 2, "tests_skipped": 0,
            "elapsed_seconds": 28.398, "runner_elapsed_seconds": 29.187,
            "log_sha256": "BA5BB5C047FA0AA1EDEDEEA6FB2AEEF1E062A38FB949298E4C549793F5FC3B81",
            "cause": "two_later_assertions_in_same_tests_retained_previous_current_counts",
            "native_runtime_failure": False,
        },
        "repaired_metadata_regression": {
            "status": "pass", "tests_run": 54, "tests_passed": 54, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 29.067, "runner_elapsed_seconds": 29.844,
            "log_sha256": "DF2EE4A647ACDF119B15D1449DA9C3A5F0E078BD6D8A4CA49EEBE0D102A0CD57",
            "historical_hashes_and_records_preserved": True,
        },
        "combined_scoped_regression": {
            "status": "pass", "tests_run": 166, "tests_passed": 166, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 218.638, "runner_elapsed_seconds": 219.563,
            "log_sha256": "21FAA36012EBC2A7B1E1FA7C4099C98AFC921C5C06B84BAA62696244C70CAF3E",
            "scope": "scheduler_controls_native_transactions_entry_core_host_boot_memory_CPU_gates_publication_metadata",
            "includes_focused_and_metadata_tests": True, "executed_before_result_recording": True,
            "source_unchanged_during_execution": True, "owner_report_unchanged": True,
            "all_CPU_memory_corruption_suites_or_five_downstream_profiles_reexecuted": False,
        },
        "initial_conservation": {
            "status": "pass", "archived_parent_current_records": 19, "architecture_bindings": 348,
            "test_inventory": 1090, "selected_checks": "22/27",
            "native_other_receipts_owner_ISO_checklist_normative_charter_preserved": True,
            "all_phase_and_flag_statuses_preserved": True,
        },
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 207: " + checkpoint + " qualifies three scheduler profiles on unchanged kernel203. "
        "Six virtual boots, 83 control groups and 595 executed cases (545 rejections and 50 native boundary "
        "cases) pass. All 47 focused tests pass, rejecting 768 recorded corruptions and eleven independent "
        "linked-identity mutations; 19 disabled native variants are detected. The stale deferred aggregate "
        "pin failure is preserved and corrected without rewriting or rerunning guest evidence. "
        "Combined scoped regression passes 166/166 with zero skips; repaired metadata passes 54/54. "
        "Conservation verifies 348 bindings and 19 unchanged archived records. Counts overlap."
    )
    gap = (
        "Selected readiness is 22/27; five SMP-scheduler/AP-worker/SMP-preemption/atomic/lock profiles "
        "remain from " + next_move + ". SMP recorded admission and at least 51 later control groups "
        "remain open. No native byte, phase, flag, ISO, N12 exit or production claim changes. General "
        "task/CPU retirement and physical qualification remain open; full exact-candidate qualification "
        "precedes main merge. Cloud checkpoint backup is separate."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N12", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 207 source inventory: 1090 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N12-SCHED-FOUNDATION-001", "FLAG-N12-SCHED-PREEMPT-001",
                          "FLAG-N12-SCHED-DEFERRED-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle208(roadmap, test_count)


def apply_cycle208(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle208-smp-admission-and-controls.md"
    next_move = "N12-SCHED-AP-WORKERS-001"
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for key, value in list(gate.items()):
        if key.startswith("current_") and isinstance(value, dict):
            suffix = "source_projection" if key == "current_focused_source_projection" else key.removeprefix("current_")
            gate["historical_cycle207_" + suffix] = copy.deepcopy(value)
    roadmap["baseline"]["pooleos_cycle"] = 208
    roadmap["execution_protocol"].update(last_updated_cycle=208,
        selected_move_id="N12-SCHED-SMP-001", owner_independent_next_move_id=next_move)
    roadmap["execution_protocol"]["required_records"].insert(0, checkpoint)
    gate["qualification_status"] = "SMP_admission_controls_verified_four_downstream_dependencies_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=208)
    digest = "31C084B5C7AEA66051FD8E36785C4CE8E2C8FF5FEA2701023CCBDE41BC2540F0"
    binding = {
        "profile": "scheduler_smp", "path": "runs/native-kernel-scheduler-smp-readiness.json",
        "sha256": digest, "fresh_runs": 2, "negative_controls": 32, "hostile_cases": 303,
        "kernel_host_tests": 246, "execution_log_sha256": "B4AFCEDC4E0B5203EA8C7434E85C6ABD1BFF4D8CFEFFE76250C1A9A84BB46958",
        "elapsed_seconds": 82.5, "recorded_evidence_cases": 279,
    }
    retained = gate["current_dependency_qualification"]
    gate["current_dependency_qualification"] = {
        "cycle": 208, "source_validation_cycle": 208, "status": "ten_current_profiles_four_pending",
        "scope": "retained_memory206_scheduler207_and_fresh_SMP208_on_unchanged_kernel203",
        "applies_to_current_source": True, "all_fourteen_profiles_current": False,
        "qualified_profiles": retained["qualified_profiles"] + ["scheduler_smp"],
        "newly_qualified_profiles": ["scheduler_smp"],
        "readiness_replay_required_profiles": ["scheduler_ap_workers", "scheduler_smp_preempt", "atomics", "locks"],
        "embedded_entry_provenance_replay_pending": True,
        "fresh_qemu_runs": 2, "superseded_initial_runs": 4, "failed_guest_runs": 0,
        "run_count_scope": "Cycle208_two_final_boots_two_diagnostic_and_two_superseded_label_boots_separate",
        "negative_control_groups": 32, "negative_control_cases": 303,
        "executed_rejection_cases": 244, "native_boundary_cases": 59,
        "kernel_sha256": retained["kernel_sha256"], "receipt_bindings": retained["receipt_bindings"] + [binding],
        "kernel_host_tests_per_qualifier": 246, "focused_python_tests": 18,
        "generic_recorded_evidence_cases": 279, "additional_control_profile_receipt_cases": 47,
        "recorded_evidence_case_total": 326, "independent_aggregate_cases": 8,
        "recorded_evidence_rejections_exercised_through_runtime_and_gate": True,
        "disabled_SMP_native_variants_detected": 13, "disabled_transaction_variants_detected": 9,
        "positive_receipts_rebound_in_tests": False, "pair_validation_is_freshness_or_authentication": False,
        "canonical_kernel_changed_this_cycle": False, "control_execution_complete": False,
        "unproven_per_control_rejection_groups_at_least": 35,
        "current_candidate_full_gate_passed": False, "production_ready": False,
    }
    projection = gate["current_focused_source_projection"]
    gate["current_focused_source_projection"] = dict(projection, cycle=208,
        passed_checks=23, pending_downstream_native_checks=4,
        passing_profiles=projection["passing_profiles"] + ["native_kernel_scheduler_smp_readiness"],
        final_receipt_fresh_qemu_runs=2, kernel_entry_runs=2, superseded_initial_qemu_runs=4,
        run_count_scope="Cycle208_two_final_boots_two_diagnostic_and_two_superseded_label_boots_separate", next_dependency_move_id=next_move,
        required_next_gate="AP_worker_admission_and_18_controls_four_profiles_then_full_candidate",
        focused_python_tests_passed=18, recorded_evidence_rejection_cases=326)
    gate["current_entry_provenance_qualification"] = dict(gate["current_entry_provenance_qualification"], latest_reproduction_cycle=208)
    gate["current_ipi_mailbox_oracle_gap"] = dict(gate["current_ipi_mailbox_oracle_gap"], cycle=208,
        remaining_affected_profiles=4, newly_requalified_profiles=["scheduler_smp"])
    audit = gate["current_control_execution_audit"]
    gate["current_control_execution_audit"] = dict(audit, cycle=208,
        scope="two_remaining_scheduler_qualifier_loops_not_exhaustive_all_profile_audit",
        unproven_per_control_rejection_groups_at_least=35, next_profile="scheduler_ap_workers",
        source_control_gaps=[g for g in audit["source_control_gaps"] if g["profile"] != "scheduler_smp"],
        SMP_groups_repaired=16)
    gate["current_smp_transaction_qualification"] = dict(gate["current_smp_transaction_qualification"],
        status="historical_Cycle203_native_repair_current_admission_tracked_separately",
        original_failure_and_repair_record_preserved=True, latest_live_replay_cycle=208,
        latest_live_receipt_sha256=digest, current_kernel_live_replay_pending=False)
    gate["current_smp_control_qualification"] = {
        "cycle": 208, "move_id": "N12-SCHED-SMP-001", "source_validation_cycle": 208,
        "requirements": ["ADD-N12-SCHED-SMP-001", "ADD-N36-RECEIPT-COVERAGE-001"],
        "status": "bounded_recorded_admission_and_executed_controls_pass",
        "applies_to_current_source": True, "receipt_sha256": digest,
        "repaired_groups": 16, "native_groups": 13, "native_boundary_cases": 59,
        "source_audit_groups": 3, "source_rejection_cases": 51,
        "disabled_native_variants_detected": 13, "disabled_source_auditor_detected": True,
        "empty_rejection_list_denied": True, "current_receipt_admitted": True,
        "genuine_before_audit": {
            "positive_runtime_and_gate": True, "receipt_sha256": "9C4B82AAFA5162900F1C3FEEB2E9E8AAD96B01D601DFBE75C9E5DF7F7329A128",
            "fresh_runs": 2, "cases": 279, "runtime_accepted": 264, "gate_accepted": 168,
            "runtime_rejected": 11, "gate_rejected": 93, "runtime_exceptions": 4, "gate_exceptions": 18,
            "admitted_as_final": False, "execution_log_sha256": "13585A2EF1DF0382F00F0D754972A92396003A1D0F963BE63FAE3E23BF9E34F1",
            "elapsed_seconds": 78.141,
        },
        "after_audit": {
            "positive_runtime_and_gate": True, "cases": 279, "runtime_rejected": 279, "gate_rejected": 279,
            "runtime_accepted": 0, "gate_accepted": 0, "runtime_exceptions": 0, "gate_exceptions": 0,
            "additional_control_profile_cases": 47, "independent_aggregate_cases": 8,
            "final_receipt_replay_log_sha256": "6CFB867BF66A5649ED611A9419F0F595377E1D98AD1FFFFABCEEFD478E49ACC0",
        },
        "superseded_label_receipt": {
            "receipt_sha256": "F41F52E82975EBF8BAEB0F1BA34E5CCA8EC91BD307F7E456D2CC8953BBA334DA",
            "fresh_runs": 2, "elapsed_seconds": 80.172,
            "execution_log_sha256": "B4AFCEDC4E0B5203EA8C7434E85C6ABD1BFF4D8CFEFFE76250C1A9A84BB46958",
            "reason": "rename_saved_register_count_to_preserved_count_14_stack_saved_plus_untouched_RBP",
            "admitted_as_final": False,
        },
        "initial_aggregate_pin_rejection_preserved": True,
        "measured_canonical_sha256": retained["kernel_sha256"], "measured_relocation_count": 1326,
        "source_mutations_are_hardware_fault_injection": False,
        "recorded_consistency_is_authentication": False, "native_kernel_bytes_changed": False,
        "aggregate_unproven_groups_at_least": 35, "full_candidate_merge_qualified": False,
        "production_ready": False,
    }
    gate["current_closeout_regression"] = {
        "cycle": 208, "status": "pass", "scope": "SMP_profile_controls_admission_and_native_transactions",
        "tests_run": 18, "tests_passed": 18, "tests_failed": 0, "tests_skipped": 0,
        "elapsed_seconds": 43.037, "runner_elapsed_seconds": 43.891,
        "log_sha256": "6CFB867BF66A5649ED611A9419F0F595377E1D98AD1FFFFABCEEFD478E49ACC0",
        "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        "superseded_label_receipt_regression": {
            "tests_run": 18, "tests_passed": 18, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 44.078, "runner_elapsed_seconds": 45.0,
            "log_sha256": "B5F300419FC4528161C70E57806BA7DABFA8FFA0ED4865608D7D5AFF29101D80",
        },
        "initial_control_test_failures": [
            {"tests_run": 5, "failures": 1, "errors": 1, "elapsed_seconds": 15.615,
             "cause": "ambiguous_source_scope_and_unwrap_diagnostic_not_assertion",
             "log_sha256": "41B9E766EF036436851707DF7151724C2DE8E11EFAF79D0CC94FDD23E93A5DD9"},
            {"tests_run": 5, "failures": 1, "errors": 0, "elapsed_seconds": 15.945,
             "cause": "custom_Rust_assertion_message_omitted_expected_diagnostic_word",
             "log_sha256": "00B32EFC644F183B4FD01437E0797AEEFEE0984F808ED5F0FD0416CD1A02ABE5"},
        ],
        "repaired_controls": {"tests_passed": 5, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 15.817, "runner_elapsed_seconds": 16.687,
            "log_sha256": "4CB234E0203A98948C61090D90A06D1D62A2D3F5095AE73B5407779454A94255"},
        "native_transaction_tests_per_optimization": 19, "optimization_levels": [0, 3],
        "initial_metadata_regression": {
            "status": "fail", "tests_run": 47, "tests_passed": 44, "tests_failed": 3, "tests_skipped": 0,
            "elapsed_seconds": 28.261, "runner_elapsed_seconds": 29.047,
            "log_sha256": "ED544BB52B327FBE15CB5C48322F20F674D8D66E4D5D639D3D165B14D5A4EFFD",
            "cause": "two_old_five_pending_assertions_and_current_SMP_entry_still_expected_stale",
            "native_runtime_failure": False,
        },
        "second_metadata_regression": {
            "status": "fail", "tests_run": 55, "tests_passed": 53, "tests_failed": 2, "tests_skipped": 0,
            "elapsed_seconds": 29.021, "runner_elapsed_seconds": 29.797,
            "log_sha256": "D3035C52EEE4D1E97C16BBA6DB0A738F161657DC243D64F36BD1DA2E2530F6CC",
            "cause": "later_assertions_still_expected_five_pending_and_22_passed",
            "native_runtime_failure": False,
        },
        "repaired_metadata_regression": {
            "status": "pass", "tests_run": 55, "tests_passed": 55, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 29.237, "runner_elapsed_seconds": 30.0,
            "log_sha256": "B230C6D837A92A60C31FCDF74006D714957F58C21E16B68165EA7B2CC8CAC864",
            "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        },
        "combined_scoped_regression": {
            "status": "pass", "tests_run": 183, "tests_passed": 183, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 246.093, "runner_elapsed_seconds": 247.031,
            "log_sha256": "C6ED9CEC90D55F7EF6DD2B176AA4621E25ECD5BC596616AD0ED20592977AE4BE",
            "scope": "scheduler_controls_transactions_entry_core_host_boot_memory_selected_dependency_gates_publication_metadata",
            "source_unchanged_during_execution": True, "owner_report_unchanged": True,
            "native_smp_tests_per_optimization": 19, "native_deferred_tests_per_optimization": 21,
            "counts_overlap_prior_focused_tests": True, "canonical_full_replay_performed": False,
        },
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 208: " + checkpoint + " repairs SMP recorded admission and replaces sixteen constant-only "
        "groups with thirteen compiled-native groups (59 boundary scenarios) and three source-audit groups "
        "(51 rejected mutations). Two fresh final boots pass 32 groups/303 cases. All 18 focused tests pass, "
        "rejecting 326 corrupted records and eight independent gate cases; thirteen disabled native safeguards "
        "and nine transaction-repair variants are detected. The 279-case before audit admitted 264 runtime/168 "
        "gate corruptions and raised 4/18 exceptions; the fresh after audit rejects all 279 without exceptions. "
        "Both test-harness failures, metadata assertion failures, the old aggregate pin failure, two diagnostic "
        "boots and two superseded register-label boots are preserved. Combined scoped regression passes "
        "183/183 and repaired metadata 55/55, with zero skips; counts overlap, not full canonical qualification."
    )
    gap = (
        "Selected readiness is 23/27; AP workers, SMP preemption, atomics and locks remain from " + next_move +
        ". At least 35 control groups remain. Native kernel/entry/core and prior qualified boot/CPU/memory/"
        "scheduler receipts are unchanged. SMP flag remains open pending downstream integration/closure review; "
        "source-audit mutations are not live hardware faults. No phase, general task/CPU retirement, N12 exit, "
        "ISO or production promotion. N0 custody and N5 authentication remain open. Full exact-candidate "
        "qualification still precedes main merge; branch cloud backup is separate."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N12", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 208 source inventory: 1100 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N12-SCHED-SMP-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle209(roadmap, test_count)


def apply_cycle209(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle209-native-ap-worker-transactions.md"
    kernel_sha = "72C37783A5729229E6A259E38DC8DF55034FD467B77839FFFC4AA62B66E33EBF"
    entry_sha = "81D4EF8ABBF735A1A39B3E8D40966A9C299377BC36E77C469CCAA61BCB8788E8"
    core_sha = "DD0436EFBAD686C4AB352EB1B4FF97F20158BB53DA7B44E3A7AC7F8143EA814F"
    next_move = "N5-SYMBOLS-SEMANTICS-001"
    roadmap["baseline"]["pooleos_cycle"] = 209
    protocol = roadmap["execution_protocol"]
    protocol.update(last_updated_cycle=209, selected_move_id="N12-SCHED-AP-WORKERS-001",
                    owner_independent_next_move_id=next_move)
    protocol["required_records"].insert(0, checkpoint)
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for key, value in list(gate.items()):
        if key.startswith("current_") and isinstance(value, dict):
            suffix = "source_projection" if key == "current_focused_source_projection" else key.removeprefix("current_")
            gate["historical_cycle208_" + suffix] = copy.deepcopy(value)
    gate["qualification_status"] = "native_AP_worker_transactions_repaired_changed_image_replay_and_controls_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=209)
    gate["current_focused_source_projection"] = {
        "cycle": 209, "scope": "27_selected_native_checks_not_full_canonical_audit",
        "passed_checks": 3, "total_checks": 27, "pending_downstream_native_checks": 24,
        "passing_profiles": ["native_kernel_entry_readiness", "native_policy_readiness", "native_kernel_errata_policy_readiness"],
        "final_receipt_fresh_qemu_runs": 0, "kernel_entry_runs": 0,
        "next_dependency_move_id": next_move,
        "required_next_gate": "changed_image_symbols_boot_CPU_memory_scheduler_replay_and_executed_AP_controls",
        "native_transaction_tests_per_profile": 30, "native_transaction_host_profiles": 2,
        "canonical_full_replay_performed": False, "production_ready": False,
    }
    pending_profiles = {
        "boot_chain": ["symbol", "kernel_load", "pooleboot", "kernel_revalidation", "kernel_transfer"],
        "cpu": ["trap", "cpu_policy", "xstate_policy", "xstate_exception", "privilege_msr_policy"],
        "dependency": ["physical_memory", "virtual_memory", "interrupt_time", "smp_first_ap", "smp_percpu_runtime",
                       "smp_ipi", "scheduler", "scheduler_preempt", "scheduler_deferred", "scheduler_smp",
                       "scheduler_ap_workers", "scheduler_smp_preempt", "atomics", "locks"],
    }
    for group, profiles in pending_profiles.items():
        gate["current_" + group + "_qualification"] = {
            "cycle": 209, "source_validation_cycle": 209, "status": "source_requalification_required",
            "applies_to_current_source": False, "kernel_sha256": kernel_sha,
            "historical_record": "historical_cycle208_" + group + "_qualification",
            "qualified_profiles": ["policy"] if group == "boot_chain" else [],
            "readiness_replay_required_profiles": profiles,
            "fresh_qemu_runs": 0, "receipt_bindings": [], "embedded_entry_provenance_replay_pending": True,
            "all_fourteen_profiles_current": False, "control_execution_complete": False,
            "unproven_per_control_rejection_groups_at_least": 35,
            "current_candidate_full_gate_passed": False, "production_ready": False,
        }
    gate["current_entry_provenance_qualification"] = dict(
        gate["current_entry_provenance_qualification"], cycle=209, source_validation_cycle=209,
        linked_byte_count=7091272, linked_sha256="B29916B90D42010CCDBDCC8927E10F8FCEEF14020CA037051367CCB4CC29F841",
        canonical_byte_count=534168, canonical_sha256=kernel_sha, entry_receipt_sha256=entry_sha,
        source_binding_count=76, latest_reproduction_cycle=209,
    )
    gate["current_task_stack_qualification"] = dict(gate["current_task_stack_qualification"], cycle=209, receipt_sha256=core_sha)
    gate["current_execution_qualification"] = dict(gate["current_execution_qualification"], cycle=209,
        receipt_sha256=core_sha, kernel_sha256=kernel_sha)
    gate["current_ownership_qualification"] = dict(
        gate["current_ownership_qualification"], cycle=209, host_qualification_cycle=209,
        scope="host209_only_prior_IPI_and_VM_receipts_historical", kernel_sha256=kernel_sha,
        reclamation_receipt_sha256=core_sha, entry_receipt_sha256=entry_sha,
        fresh_current_cycle_qemu_runs=0, live_receipt_source_current=False,
        current_boot_artifact_set_replay_pending=True, active_root_current_image_replay_complete=False,
        ap_runtime_live_integration_verified=False, virtual_memory_live_receipt_source_current=False,
        live_receipt_scope="historical_IPI_and_VM206_not_current_kernel_execution",
        source_current_scope="host_core_and_entry_only", historical_record="historical_cycle208_ownership_qualification",
    )
    gate["current_ipi_mailbox_oracle_gap"] = dict(gate["current_ipi_mailbox_oracle_gap"], cycle=209,
        remaining_affected_profiles=24, newly_requalified_profiles=[], current_kernel_live_replay_pending=True)
    gate["current_control_execution_audit"] = dict(gate["current_control_execution_audit"], cycle=209)
    for name in ("preemption_control_execution_audit", "deferred_transaction_qualification",
                 "symbol_admission_qualification", "deferred_control_qualification",
                 "smp_transaction_qualification", "smp_control_qualification"):
        gate["current_" + name] = dict(gate["current_" + name], applies_to_current_source=False,
            current_kernel_live_replay_pending=True, current_receipt_admitted=False,
            historical_record="historical_cycle208_" + name)
    gate["current_ap_worker_transaction_qualification"] = {
        "cycle": 209, "move_id": "N12-SCHED-AP-WORKERS-001",
        "requirements": ["ADD-N12-SCHED-AP-WORKERS-001", "ADD-N36-RECEIPT-COVERAGE-001"],
        "status": "native_host_transactions_verified_current_boot_and_controls_pending",
        "scope": "exclusive_controller_state_transactions_not_cross_CPU_atomicity",
        "initial_native_tests_per_profile": 28, "initial_native_passed": 12, "initial_native_failed": 16,
        "initial_log_sha256": "C02F786B0630E8D7C6EF1F12FA3E5F6F8A0F75DBE4EA78999AB4A234E7CC13A4",
        "final_native_tests_per_profile": 30, "new_private_state_tests": 20, "host_optimization_levels": [0, 3],
        "disabled_native_variants_detected": 15, "focused_python_test_methods": 2,
        "combined_transaction_methods_passed": 6,
        "control_log_sha256": "401921DBF877082D913FDB223D23DFF814CF04D269351C09E85A9626801209AE",
        "sources": {
            "native/kernel/src/scheduler_ap_workers.rs": "AD365CC34066F7D26921B4F9D264D5C7FDE7797086B07AD67C8C34DCCD1452A7",
            "tests/fixtures/pksched5_transaction_probe.rs": "8E5F5EFA7587BE6491CEDC3AFCC650B24A8932DDC4ACB8B2A476C54C48B52126",
            "tests/test_native_ap_worker_transactions.py": "6774DFA9A106BDABE1C348D3CE0DBCA833D54DF90D102563B47E515325CCA850",
        },
        "kernel_sha256": kernel_sha, "kernel_bytes_changed": True,
        "entry_receipt_sha256": entry_sha, "core_receipt_sha256": core_sha,
        "preserved_rejected_attempts": [
            {"tag": "repaired", "cause": "Option_comparison_not_const_stable", "log_sha256": "74ECE56963B6689C14523713F27CD62884A527BA12E9CE42D82C771FBA3AFFAF"},
            {"tag": "repaired2", "cause": "existing_order_test_expected_late_ack_not_early_dispatch_rejection", "log_sha256": "8D31C21C74CE59D378AD2ED1CD8319B6ED5854E90B9EF62729F7888A673C8F9F"},
            {"tag": "controls", "cause": "mutation_anchor_changed_by_rustfmt", "log_sha256": "EF07FB07EF4639002B3E9A41C0B45BE27325A8F624A910C51CE5E80F89BD7FD3"},
            {"tag": "measure", "cause": "text_boundary_short_by_1150_bytes", "log_sha256": "6838C356CCE2C342F62F83A8E83911103EDD7E12ADF73E7C7B9FA613F960B2C2"},
            {"tag": "measure2", "cause": "RELRO_boundary_short_by_144_bytes", "log_sha256": "F7E1E22320A8239F2951EC52CEAE5CA5B5F279355A20B50344ABC89D00E755D7"},
            {"tag": "measure3", "cause": "image_boundary_short_by_3572_bytes", "log_sha256": "CF5826CE9C77B09C012C9B0FEEA692C9607B654555BDFEA55B6600FFAC281A6C"},
        ],
        "remote_ack_synthesized_or_accepted_by_preflight": False,
        "recorded_evidence_admission_repaired": False, "constant_only_control_groups_replaced": 0,
        "remaining_AP_worker_control_groups": 18, "remaining_global_control_groups_at_least": 35,
        "controller_size_upper_bound_bytes": 2048, "new_kernel_qemu_runs": 0,
        "cross_cpu_atomicity_proved": False, "production_ready": False,
    }
    gate["current_closeout_regression"] = {
        "cycle": 209, "status": "pass",
        "scope": "native_AP_worker_host_core_entry_not_full_canonical",
        "tests_run": 117, "tests_passed": 117, "tests_failed": 0, "tests_skipped": 0,
        "elapsed_seconds": 163.739, "runner_elapsed_seconds": 164.703,
        "log_sha256": "6A2F2869405F2693416AFF31CF008539BBDF7EDEBD651D2C5D608D134D094EEC",
        "includes_native_transactions_entry_core_host_transfer_publication_and_metadata": True,
        "repaired_metadata_tests_passed": 56, "counts_overlap_prior_tests": True,
        "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        "core": {"stages_passed": 17, "elapsed_seconds": 39.547,
            "log_sha256": "2AB8D226E34E1EC1FD773B540A39E2E660DA56CAD8E6063453F24A14CBE3DD9D"},
        "entry": {"clean_builds": 2, "kernel_tests": 246, "rejection_cases": 43, "elapsed_seconds": 38.390,
            "log_sha256": "812247C631861F134E36E05396EF5D5167953BCFF34A0322E7CA7A343FF45D3E"},
        "initial_metadata": {"tests_run": 56, "failure_records": 23, "tests_skipped": 0,
            "elapsed_seconds": 12.532, "runner_elapsed_seconds": 13.328,
            "cause": "old_cycle_schema_and_historical_receipts_still_expected_current",
            "log_sha256": "10DB2FC9AACC7A4B4577F8D9F1FF2BD5E55B3EE816785E3DA16458563498DCD9"},
        "second_metadata": {"tests_run": 56, "tests_passed": 53, "tests_failed": 3, "tests_skipped": 0,
            "elapsed_seconds": 21.885, "runner_elapsed_seconds": 22.687,
            "cause": "remaining_old_pending_count_current_CPU_acceptance_and_old_marker_identity",
            "log_sha256": "E5147F725F88B41A121AA2C63DC35714CCB7F53BECF24DC82790BBBEC083FF4B"},
        "initial_conservation_diagnostics": [
            "helper_numeric_substitution_changed_locked_coverage_hash_literal_not_the_coverage_file",
            "metadata_test_indentation_error_temporarily_prevented_full_test_discovery",
        ],
        "initial_conservation": {"status": "pass", "archived_parent_current_records": 20,
            "architecture_bindings": 354, "test_inventory": 1103, "selected_checks": "3/27",
            "all_prior_boot_receipts_and_normative_charter_preserved": True,
            "only_AP_worker_flag_reopened_and_no_phase_status_changed": True},
        "initial_combined_regression": {"tests_run": 117, "tests_passed": 116, "tests_failed": 1,
            "tests_skipped": 0, "elapsed_seconds": 163.711, "runner_elapsed_seconds": 164.625,
            "cause": "transfer_validator_still_pinned_Cycle203_build_ID",
            "log_sha256": "3E7D107D74277F38D93E71AD48473FE6DCDCE3D55D375E45BA6CCBB972A4783E",
            "source_unchanged_during_execution": True, "owner_report_unchanged": True,
            "metadata_tests_passed": 56},
        "second_combined_regression": {"tests_run": 117, "tests_passed": 116, "tests_failed": 0,
            "tests_errored": 1, "tests_skipped": 0, "elapsed_seconds": 172.417, "runner_elapsed_seconds": 173.343,
            "cause": "synthetic_transfer_fixture_still_carried_Cycle203_build_ID",
            "log_sha256": "1AB00AB6C637EF2DBF33D9B7AE607D13D79721679AD793C7E6ED9D1C0074E8F6",
            "source_unchanged_during_execution": True, "owner_report_unchanged": True,
            "recorded_guest_transcripts_rebound": False},
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 209: " + checkpoint + " repairs native AP-worker queue, dispatch, acknowledgement, cancellation, "
        "timeout, reclaim, retirement, offlining and shutdown transactions, generation wrap and wide-counter validation. "
        "Sixteen pre-repair native failures per host profile are preserved. Thirty final native cases per debug/optimized "
        "profile and fifteen disabled variants pass; six combined transaction methods, 17 core stages, two matching "
        "kernel builds, 246 kernel tests and 43 hostile image controls pass. Failed compiler, order/anchor tests and "
        "three measured linker-boundary attempts remain separate. Final combined scoped regression passes "
        "117/117 with zero skips, including 56 repaired metadata tests and the corrected transfer identity "
        "and synthetic fixture. Both initial combined failures are preserved; counts overlap prior tests."
    )
    gap = (
        "Kernel bytes changed. Selected readiness is 3/27; entry, policy and errata pass while 24 profiles require "
        "replay from " + next_move + ". The AP-worker flag is reopened; recorded admission and eighteen constant-only "
        "groups remain within at least 35 unproven groups. No phase closes. N0 custody, N5 authentication, general "
        "task/CPU retirement, independent builders and production remain open. No new-kernel guest boot, cross-CPU "
        "atomicity, ISO change or main merge is claimed. Full exact-candidate qualification still precedes merge."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N5", "N6", "N12", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 209 source inventory: 1103 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N12-SCHED-AP-WORKERS-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
        if flag["id"] == "FLAG-N12-SCHED-AP-WORKERS-001":
            flag["status"] = "open"
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle210(roadmap, test_count)


def apply_cycle210(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle210-retained-map-growth-and-boot-replay.md"
    kernel = "AE3422B2D44E6EC87AB1D5B51414C023E46F2EE3461A0D0895B9D1242E10D25A"
    entry = "080A019D50DBBA7CCA32FAD792D70949A4E0A21DC43E9F52031B371227B56E53"
    core = "E752211396320793A4EE7C28FADF9A4DE51A503D17B6D9FF264DDD5F49D43650"
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for key, value in list(gate.items()):
        if key.startswith("current_") and isinstance(value, dict):
            suffix = "source_projection" if key == "current_focused_source_projection" else key.removeprefix("current_")
            gate["historical_cycle209_" + suffix] = copy.deepcopy(value)
    roadmap["baseline"]["pooleos_cycle"] = 210
    protocol = roadmap["execution_protocol"]
    protocol.update(last_updated_cycle=210, selected_move_id="N5-KMAP-001",
                    owner_independent_next_move_id="N7-TRAP-001")
    protocol["required_records"].insert(0, checkpoint)
    gate["qualification_status"] = "native_retained_map_repaired_boot_replayed_downstream_and_controls_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=210)
    profiles = ["symbol", "policy", "kernel_load", "pooleboot", "kernel_revalidation", "kernel_transfer"]
    bindings = []
    for profile, path, digest, runs, controls in (
        ("symbol", "native_symbol_readiness.json", "D727F88200ED95CED5AC99C1FB0781209A50022668F3935FA8C6969013B6EC4A", 0, 158),
        ("policy", "native_policy_readiness.json", "CE31D5D02151A45731EF0E72E516F5DEF977811B48A527D648F5BB3256F715D1", 0, 116),
        ("kernel_load", "native_kernel_load_readiness.json", "03832C810CAFE4594AD213ACF134172C58350EBE6F9626F500E72F2B4D2BC701", 2, 155),
        ("pooleboot", "native_pooleboot_readiness.json", "681D870EB05CE21E2631A8768559FE7963C7A0929D89737F401F4237B0B73728", 2, 155),
        ("kernel_revalidation", "native-kernel-revalidation-readiness.json", "0FE9DEE9CD343895BA46BE1F8DD6405E422ED5773A2405679E1559DD18D5EACD", 0, 36),
        ("kernel_transfer", "native-kernel-transfer-readiness.json", "4521507E4A8055C411809CB7CA4AC77D3507F1A04CF386BA68713BDFD2F5E001", 2, 58),
    ):
        bindings.append(dict(profile=profile, path="runs/" + path, sha256=digest, fresh_runs=runs, negative_controls=controls))
    gate["current_focused_source_projection"] = {
        "cycle": 210, "scope": "27_selected_native_checks_not_full_canonical_audit",
        "passed_checks": 8, "total_checks": 27, "pending_downstream_native_checks": 19,
        "passing_profiles": ["native_kernel_entry_readiness"] + ["native_" + p + "_readiness" for p in profiles] + ["native_kernel_errata_policy_readiness"],
        "final_receipt_fresh_qemu_runs": 6, "kernel_entry_runs": 2,
        "next_dependency_move_id": "N7-TRAP-001",
        "required_next_gate": "current_image_CPU_memory_scheduler_replay_and_executed_AP_controls",
        "canonical_full_replay_performed": False, "production_ready": False,
    }
    boot = copy.deepcopy(gate["historical_cycle208_boot_chain_qualification"])
    boot.update(cycle=210, source_validation_cycle=210, kernel_sha256=kernel, receipt_bindings=bindings,
        focused_python_tests=97, loader_rust_tests=332, kernel_bytes_changed_this_cycle=True,
        entry_and_core_receipts_unchanged=False, entry_and_core_freshly_qualified=True,
        inner_set_sha256="163EDAC3648C52267DAD983A6283D0860668B04B2E9B077A40F1855046A81DB1",
        trust_policy_sha256="957F07706B7B7CA495B9745CB50721B0698AAE79EBFE87A4BDB8B10F6892CEDC",
        trust_state_sha256="CC015F3A79444B1BB91B1F7BEB985BEC9024759CAC2A688BA62339CCD48CAEF2",
        manifest_sha256="8A73B6E1382F4F241D59676B977CA466CD8A98A2987FE2A49CC4A2397DDC8AD3",
        independent_previous_identity_rejection_cases=25)
    gate["current_boot_chain_qualification"] = boot
    for group in ("cpu", "dependency"):
        gate["current_" + group + "_qualification"] = dict(gate["current_" + group + "_qualification"],
            cycle=210, source_validation_cycle=210, kernel_sha256=kernel,
            historical_record="historical_cycle209_" + group + "_qualification")
    gate["current_entry_provenance_qualification"] = dict(gate["current_entry_provenance_qualification"],
        cycle=210, source_validation_cycle=210, latest_reproduction_cycle=210,
        canonical_sha256=kernel, linked_sha256="6B168F59888CE36050918908E9D7DDB4EEA87F4B8A13FF90EB80E26E0C248BD5",
        entry_receipt_sha256=entry)
    gate["current_task_stack_qualification"] = dict(gate["current_task_stack_qualification"], cycle=210, receipt_sha256=core)
    gate["current_execution_qualification"] = dict(gate["current_execution_qualification"], cycle=210, receipt_sha256=core, kernel_sha256=kernel)
    gate["current_ownership_qualification"] = dict(gate["current_ownership_qualification"], cycle=210,
        host_qualification_cycle=210, scope="host210_only_prior_IPI_and_VM_receipts_historical", kernel_sha256=kernel,
        reclamation_receipt_sha256=core, entry_receipt_sha256=entry,
        historical_record="historical_cycle209_ownership_qualification")
    gate["current_ipi_mailbox_oracle_gap"] = dict(gate["current_ipi_mailbox_oracle_gap"], cycle=210,
        remaining_affected_profiles=19, newly_requalified_profiles=profiles)
    gate["current_control_execution_audit"] = dict(gate["current_control_execution_audit"], cycle=210)
    gate["current_ap_worker_transaction_qualification"] = dict(gate["current_ap_worker_transaction_qualification"],
        applies_to_current_source=False, current_receipt_admitted=False, current_kernel_live_replay_pending=True,
        historical_record="historical_cycle209_ap_worker_transaction_qualification")
    gate["current_symbol_admission_qualification"] = dict(gate["current_symbol_admission_qualification"], cycle=210,
        applies_to_current_source=True, current_receipt_admitted=True, current_kernel_live_replay_pending=False,
        symbol_receipt_sha256=bindings[0]["sha256"], historical_record="historical_cycle209_symbol_admission_qualification")
    gate["current_retained_map_qualification"] = {
        "cycle": 210, "move_id": "N5-KMAP-001", "reconstructed_from_move_id": "N5-SYMBOLS-SEMANTICS-001",
        "requirements": ["ADD-MEM-001", "ADD-BOOT-007", "ADD-N36-RECEIPT-COVERAGE-001"],
        "status": "native_guard_repair_and_boot_replay_pass",
        "kernel_pages": 148, "previous_guard_page": 147, "kernel_capacity_pages": 192,
        "stack_first_page": 193, "handoff_first_page": 230, "handoff_pages": 256,
        "handoff_populated_table_entries": 512, "accepted_boundary_pages": [148, 192], "rejected_pages": 193,
        "rejected_before_table_writes": True, "unused_kernel_pages_unmapped": True,
        "stack_RW_NX": True, "handoff_R_NX": True, "guards_unmapped": True,
        "native_tests_per_profile": 15, "host_optimization_levels": [0, 3],
        "before_native_passed": 14, "before_native_failed": 1,
        "before_log_sha256": "DCB5B9910CEF4D72DB145149DB6238A1B940761E68EF551B01BC0174B1C6927D",
        "after_log_sha256": "A085E7857F9C9C3416F03E2C7F139A9E7107C5696841A739ED7C9310A8503144",
        "final_native_log_sha256": "51CA1E8C2A7488F50E0472DE17907CFBFC2930D1B2B1B97D8071EE42ACAD3FB3",
        "initial_loader_failure_log_sha256": "9DDE37AEA9DAE0CEC429EE7537E3F3D1E1AD01722698A564B53CCA8578B76B89",
        "stale_guard_control_failure_log_sha256": "06753CB44EA4BF1205EBE4096ED7A07C27F7F499EA9DFAE55FF9174229F0C3E0",
        "kernel_sha256": kernel, "entry_receipt_sha256": entry, "core_receipt_sha256": core,
        "production_ready": False,
    }
    gate["current_closeout_regression"] = {
        "cycle": 210, "status": "pass", "scope": "guard_symbols_boot_chain_not_full_canonical",
        "tests_run": 97, "tests_passed": 97, "tests_failed": 0, "tests_skipped": 0,
        "elapsed_seconds": 41.579, "runner_elapsed_seconds": 42.468,
        "log_sha256": "EF94D4166CE644A2D557B33092F9930365E45BFB356741C05C94B07AD217CD9F",
        "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        "failed_attempts_preserved_in_checkpoint": True, "failed_receipts_admitted": False,
        "core_stages_passed": 17, "matching_clean_builds": 2, "kernel_tests": 246, "image_rejection_cases": 43,
        "initial_metadata": {"tests_run": 57, "tests_passed": 52, "tests_failed": 5, "tests_skipped": 0,
            "elapsed_seconds": 27.316, "runner_elapsed_seconds": 28.281,
            "cause": "stale_pending_counts_symbol_expectation_and_architecture_binding_count",
            "log_sha256": "5BB36D5B27F9CDD02D97E078BCD49D996EB4544868ED8983E460D135AA1CFF73"},
        "combined_scoped_regression": {"tests_run": 212, "tests_passed": 212, "tests_failed": 0,
            "tests_skipped": 0, "elapsed_seconds": 275.617, "runner_elapsed_seconds": 276.625,
            "log_sha256": "41A610A52599C58359FECB18DB666E6E14F953E496EBCD08594A5FAFBCD1D3AF",
            "includes_native_transactions_core_entry_boot_and_57_metadata_tests": True,
            "source_unchanged_during_execution": True, "owner_report_unchanged": True,
            "executed_before_result_recording": True, "counts_overlap_focused_tests": True},
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 210: " + checkpoint + " repairs the retained stack guard collision exposed by the 148-page kernel. "
        "A fixed 192-page reservation preserves unmapped gaps/guards and NX stack/handoff permissions; 193 pages reject "
        "before table writes and handoff population is constrained to its first table. Fifteen native cases per host "
        "profile, 17 core stages, two matching kernel builds, 246 kernel tests, 43 image controls, six final virtual "
        "boots with two kernel entries and 97 scoped Python tests pass. Combined regression passes 212/212 with "
        "zero skips, including 57 repaired metadata tests; counts overlap. Failed and provisional attempts remain separate."
    )
    gap = (
        "Selected readiness is 8/27; nineteen current-image CPU/memory/scheduler profiles require replay from N7-TRAP-001. "
        "At least 35 executed-control groups remain unproven, including eighteen AP-worker groups. Full exact-candidate "
        "canonical qualification, publication and review still gate main merge. N0 custody, N5 authentication, general "
        "retirement and independent builders remain open. No phase/flag closes, demo ISO changes or production promotion."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N5", "N6", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 210 source inventory: 1105 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N5-KMAP-001", "FLAG-N6-KENTRY-001", "FLAG-N5-SYMBOL-BUNDLE-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle211(roadmap, test_count)


def apply_cycle211(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle211-current-kernel-cpu-admission-and-replay.md"
    next_move = "N9-PMM-ACPI-CONSUMER-001"
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for key, value in list(gate.items()):
        if key.startswith("current_") and isinstance(value, dict):
            suffix = "source_projection" if key == "current_focused_source_projection" else key.removeprefix("current_")
            gate["historical_cycle210_" + suffix] = copy.deepcopy(value)
    roadmap["baseline"]["pooleos_cycle"] = 211
    roadmap["execution_protocol"].update(last_updated_cycle=211, selected_move_id="N7-TRAP-001",
        owner_independent_next_move_id=next_move)
    roadmap["execution_protocol"]["required_records"].insert(0, checkpoint)
    gate["qualification_status"] = "current_kernel_CPU_admission_repaired_fourteen_dependencies_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=211)
    rows = (
        ("trap", "F2D74BF5725E695206ED378E169DE9694800DFB74EC2B5EF7AC9F6B10C5E2E5E", 6, 51,
         "E11DA9317E145FC30364A9927DC273C1159991B3A0CD287E11D5B7DC65869F68", 398.188),
        ("cpu_policy", "667877ADB4100D7C972C4E1897A00936C6F51A4DB95B33C3155CDBC188531D5F", 2, 41,
         "CFA41675A79CE67949D1FDB8D08F791EB2FD1115237010D33465135306D1CE23", 121.500),
        ("xstate_policy", "6577398A5EC288D3D82B0335B216564E35C169FAE657C82DE5EB945FF8C8B518", 2, 43,
         "4260145CE808D54618100843E5797A22DAFA156F94093C1D222D6D99730A162A", 96.656),
        ("xstate_exception", "95B614172F92F68D8EAEDA87EAA1A3673058DBA43DCC02E46CFD3034277F3108", 2, 43,
         "F3ED8801D7E59F458EBE9E20B63EED505D5DEF7034E3E58654DA297E074BF60D", 81.718),
        ("privilege_msr_policy", "E3F549D9BD679B38060B636555EEB17061A7FD278EA0867B744DB66190C8E418", 2, 47,
         "9B9A31059D4151F9B9A62622272025F3EDB8EEF33A8C29EEA6267DBE5A72AE32", 77.906),
    )
    bindings = [dict(profile=profile, path="runs/native-kernel-" + profile.replace("_", "-") + "-readiness.json",
        sha256=digest, fresh_runs=runs, negative_controls=controls, kernel_host_tests=246,
        execution_log_sha256=log, elapsed_seconds=seconds)
        for profile, digest, runs, controls, log, seconds in rows]
    cpu = copy.deepcopy(gate["historical_cycle208_cpu_qualification"])
    cpu.update(cycle=211, source_validation_cycle=211, scope="five_N7_profiles_on_unchanged_Cycle210_kernel",
        kernel_sha256=gate["current_entry_provenance_qualification"]["canonical_sha256"], receipt_bindings=bindings,
        focused_python_tests=55, aggregate_gate_regression_cases=32,
        new_previous_image_and_wrong_typed_pin_rejection_cases=6)
    cpu["nested_build_admission_audit"] = {
        "genuine_current_positives": 5, "full_gate_cases": 80,
        "before_rejected": 68, "before_exceptions": 12, "before_accepted": 0,
        "after_rejected": 80, "after_exceptions": 0, "after_accepted": 0,
        "isolated_float_relocation_accepted_before": True, "isolated_float_relocation_accepted_after": False,
        "schema_and_component_bypassed_only_for_isolated_pin_case": True,
        "malformed_shapes": ["null", "array", "boolean", "string", "empty_object"],
        "before_gate_source_sha256": "46AB564FD3788D44CDB33F9D97323D411CC42014A1A020C8BA074A9694A40757",
        "after_gate_source_sha256": "E0B370DB0D132A3F33E1385BB22B4E3D164F491EB26CEDACA84AFC7DE433EC0F",
        "source_hash_scope": "at_audit_execution_before_later_gap_text_update",
        "receipt_rewriting_or_validator_bypass_in_real_admission": False,
    }
    gate["current_cpu_qualification"] = cpu
    projection = copy.deepcopy(gate["historical_cycle205_source_projection"])
    projection.update(cycle=211, run_count_scope="CPU211_not_retained_boot210", focused_python_tests_passed=55)
    gate["current_focused_source_projection"] = projection
    gate["current_entry_provenance_qualification"] = dict(gate["current_entry_provenance_qualification"], latest_reproduction_cycle=211)
    gate["current_ipi_mailbox_oracle_gap"] = dict(gate["current_ipi_mailbox_oracle_gap"], cycle=211,
        remaining_affected_profiles=14, newly_requalified_profiles=[b["profile"] for b in bindings])
    gate["current_control_execution_audit"] = dict(gate["current_control_execution_audit"], cycle=211)
    gate["current_closeout_regression"] = {
        "cycle": 211, "status": "pass", "scope": "five_CPU_profiles_and_aggregate_admission_not_full_canonical",
        "tests_run": 55, "tests_passed": 55, "tests_failed": 0, "tests_skipped": 0,
        "elapsed_seconds": 177.854, "runner_elapsed_seconds": 178.766,
        "log_sha256": "4049032FB36A9882BABCD61442E0CCC28F70B7623D6869E3BC4F81502AE486DA",
        "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        "initial_metadata": {"tests_run": 58, "tests_passed": 56, "tests_failed": 2, "tests_skipped": 0,
            "elapsed_seconds": 23.101, "runner_elapsed_seconds": 23.891,
            "cause": "historical_CPU_tests_still_expected_current_receipts_to_be_stale",
            "log_sha256": "D54FA418AACF096D9E3DD4BE911B59577D9FF1A5DFFDAC86969038198837D062"},
        "initial_combined_scoped_regression": {
            "tests_run": 249, "tests_passed": 248, "tests_failed": 1, "tests_skipped": 0,
            "elapsed_seconds": 396.655, "runner_elapsed_seconds": 398.094,
            "log_sha256": "47805465466321560B97E2219754924EABD42C7CDC732747B0EA64F29358E68C",
            "scope": "boot_CPU_entry_host_publication_metadata_not_full_canonical",
            "cause": "one_remaining_stale_current_CPU_assertion_in_historical_metadata_test",
            "source_unchanged_during_execution": True, "owner_report_unchanged": True,
            "counts_overlap_focused_tests": True, "admitted_as_passing_suite": False,
        },
        "corrected_metadata_regression": {
            "tests_run": 58, "tests_passed": 58, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 29.005, "runner_elapsed_seconds": 29.844,
            "log_sha256": "4003E25622DE08D904FCD891E0A1B59B373349AF06FBA36E1F8F1DEB6EDAC4DE",
            "source_unchanged_during_execution": True, "owner_report_unchanged": True,
            "full_combined_suite_rerun_after_metadata_only_fix": False,
        },
        "obsolete_trap_aggregate_pin_observed_rejecting_current_receipt": True,
        "obsolete_pin_reconciled_from_measured_kernel_not_claim_bypass": True,
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 211: " + checkpoint + " qualifies five CPU profiles on unchanged kernel210: fourteen fresh "
        "virtual boots, 225 controls, two WHPX exception runs and one separate expected TCG limitation probe. "
        "All 55 focused tests pass, including 3398 control-record corruptions, 371 run-evidence corruptions, "
        "32 independent identity/promotion cases and 80 malformed nested-build cases. The before audit raised "
        "12 exceptions and rejected 68 cases; all 80 now reject without exceptions. An isolated float relocation "
        "pin counterexample is repaired; the full gate had accepted none. The stale trap image pin is reconciled."
        " Initial metadata passes 56/58; combined regression passes 248/249 with one remaining stale current-CPU "
        "expectation. Corrected metadata passes 58/58 with no skips; the failed combined run is not promoted."
    )
    gap = (
        "Selected readiness is 13/27; fourteen memory/IRQ/SMP/scheduler/atomic/lock profiles remain from "
        + next_move + ". At least 35 control groups and AP-worker recorded admission remain open. "
        "No phase, flag, kernel byte, ISO or production status changes; full exact-candidate canonical, Doctor, "
        "release, publication and configured GitHub/review gates still precede main merge. Branch cloud backup "
        "does not require main merge. N0 custody, N5 authentication and general retirement remain open."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N7", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 211 source inventory: 1107 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N7-TRAP-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle212(roadmap, test_count)


def apply_cycle212(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle212-current-kernel-memory-and-multiprocessor-replay.md"
    next_move = "N12-SCHED-001"
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for key, value in list(gate.items()):
        if key.startswith("current_") and isinstance(value, dict):
            suffix = "source_projection" if key == "current_focused_source_projection" else key.removeprefix("current_")
            gate["historical_cycle211_" + suffix] = copy.deepcopy(value)
    roadmap["baseline"]["pooleos_cycle"] = 212
    roadmap["execution_protocol"].update(last_updated_cycle=212,
        selected_move_id="N9-PMM-ACPI-CONSUMER-001", owner_independent_next_move_id=next_move)
    roadmap["execution_protocol"]["required_records"].insert(0, checkpoint)
    gate["qualification_status"] = "current_kernel_memory_IRQ_SMP_admitted_eight_dependencies_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=212)
    rows = (
        ("physical_memory", "96491F3210FEE8FC40241FE73C8417F701D6DEE57E7B2AC0BF775A9C78A3515A",
         "DABF6931746E7B05FAB06DB2C225FF2B45090B588DCD37C95117C017E54AFADE", 122.343),
        ("virtual_memory", "200FA4B7705FB46F09EA7ABF71EF54FA4E414F639C4FCC95BC09D1D284B6F427",
         "84D7AB0B656C88F720F700F9A86E640C473DA2C250A0D008220F2CF8F5390D24", 78.625),
        ("interrupt_time", "234C79DE91BFC748EA495AD4D3A71C3DBFE4527904825A412FC2A2AF18EB4D2D",
         "047FF2DF6EB68D3816503F9E81C83FA820E6D47828691C1D6F48D6B95C2F54B1", 85.063),
        ("smp_first_ap", "1EBF68B263C36D40558977FA7A646CE0776D5DC777040AF7960F3D01EA3DE159",
         "6A25DBB4AE5AC7A23E7328961F320F5551C3A189A91211F1B4C970530B8614E1", 110.797),
        ("smp_percpu_runtime", "95BEDA0D2769D71245B561F093BE2F725808A0275C62E5BB28CD24824473F82A",
         "BEDC73DE58B81C522F0C0F23D34D0E0573C50C2BA8A22ADF37436DC4F4E4C890", 71.421),
        ("smp_ipi", "42F9C658BC14E0F666AAFEB527A82B392A41E87B6C5085E798FB024AFB26E491",
         "388DF5EF603F6509E38EF8251F7C6ADEEBA7A459AF2A01F948466E3A93302F41", 76.844),
    )
    record = copy.deepcopy(gate["historical_cycle206_dependency_qualification"])
    bindings = record["receipt_bindings"]
    for binding, (profile, digest, log, seconds) in zip(bindings, rows, strict=True):
        assert binding["profile"] == profile
        binding.update(sha256=digest, execution_log_sha256=log, elapsed_seconds=seconds)
    record.update(cycle=212, source_validation_cycle=212,
        scope="six_fresh_memory_IRQ_AP_IPI_profiles_on_unchanged_Cycle210_kernel",
        run_count_scope="Cycle212_six_profiles_only_not_retained_CPU_or_boot_runs",
        kernel_sha256=gate["current_entry_provenance_qualification"]["canonical_sha256"],
        independent_IPI_pin_rejection_cases=8, memory_gate_rejection_cases=23,
        unproven_per_control_rejection_groups_at_least=35)
    gate["current_dependency_qualification"] = record
    gate["current_ownership_qualification"] = dict(gate["current_ownership_qualification"], cycle=212,
        scope="retained_host_core210_and_fresh_bounded_VM_IPI212", fresh_current_cycle_qemu_runs=4,
        live_replay_cycle=212, live_receipt_scope="two_VM212_and_two_IPI212_runs",
        live_receipt_source_current=True, active_root_current_image_replay_complete=True,
        virtual_memory_live_receipt_source_current=True, ap_runtime_live_integration_verified=True,
        virtual_memory_live_replay_cycle=212, virtual_memory_receipt_sha256=bindings[1]["sha256"],
        smp_receipt_sha256=bindings[5]["sha256"], source_current_scope="host_core210_boot210_bounded_VM_IPI212",
        current_boot_artifact_set_replay_pending=False, boot_artifact_replay_cycle=210,
        live_boot_dependency_replay_cycle=212, historical_record="historical_cycle211_ownership_qualification")
    projection = copy.deepcopy(gate["historical_cycle206_source_projection"])
    projection.update(cycle=212, run_count_scope="Cycle212_six_memory_IRQ_SMP_profiles_not_retained_CPU_or_boot_runs")
    gate["current_focused_source_projection"] = projection
    gate["current_entry_provenance_qualification"] = dict(gate["current_entry_provenance_qualification"], latest_reproduction_cycle=212)
    gate["current_ipi_mailbox_oracle_gap"] = dict(gate["current_ipi_mailbox_oracle_gap"], cycle=212,
        remaining_affected_profiles=8, newly_requalified_profiles=record["qualified_profiles"], current_kernel_live_replay_pending=False)
    gate["current_control_execution_audit"] = dict(gate["current_control_execution_audit"], cycle=212)
    gate["current_closeout_regression"] = {
        "cycle": 212, "status": "pass", "scope": "six_memory_IRQ_SMP_profiles_and_memory_IPI_gates_not_full_canonical",
        "tests_run": 93, "tests_passed": 93, "tests_failed": 0, "tests_skipped": 0,
        "elapsed_seconds": 123.625, "runner_elapsed_seconds": 124.562,
        "log_sha256": "C9D35A333321A2E10241EAB5CD7FA70635B5747036E1303769B1AE1150E9B01C",
        "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        "initial_admission_failures": [
            {"profile": "physical_memory", "detail": "PKPMM7 readiness summary changed", "reconciled_pins": 3},
            {"profile": "virtual_memory", "detail": "PKVM3 readiness summary changed", "reconciled_pins": 6},
            {"profile": "smp_ipi", "detail": "PKSMP5 embedded kernel identity changed", "reconciled_pins": 1},
        ],
        "same_candidates_admitted_after_independent_measurement": True,
        "failed_guest_runs": 0, "guest_evidence_rewritten_or_rerun_for_pin_repair": False,
        "IPI_patch_context_typo_prevented_initial_edit": True,
        "IPI_after_audit_and_admission_rejected_once_more_before_successful_patch": True,
        "corrected_metadata_regression": {
            "tests_run": 59, "tests_passed": 59, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 33.250, "runner_elapsed_seconds": 34.063,
            "log_sha256": "4A232B2C89221286AA400A6DC3CA1B641101E049D4C8235CEEEEF991A2D672ED",
            "source_unchanged_during_execution": True, "owner_report_unchanged": True,
            "scope": "roadmap_architecture_and_locked_checklist_not_full_canonical",
        },
        "initial_metadata_regression": {
            "tests_run": 59, "tests_passed": 58, "tests_failed": 1, "tests_skipped": 0,
            "elapsed_seconds": 32.403, "runner_elapsed_seconds": 33.188,
            "log_sha256": "4D8A3A1B3F5B760FCF13DE3972579CC5C9C2658E24D8EFD973DDF208240CFBFC",
            "cause": "entry_provenance_progress_test_still_expected_current_IPI_entry_to_be_stale",
            "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        },
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 212: " + checkpoint + " qualifies six memory/IRQ/SMP profiles on unchanged kernel210. "
        "Twelve virtual boots, 421 control groups covering 1137 cases and 93 focused tests pass, including "
        "1896 corrupted records, 360 raw-mailbox cases, eight isolated IPI identity cases and 23 memory "
        "summary cases. Three PMM, six VM and one IPI obsolete pins are reconciled only after independent "
        "current-image evidence. Failed admissions are preserved; identical candidates then pass."
    )
    gap = (
        "Selected readiness is 19/27; eight scheduler/atomic/lock profiles remain from " + next_move + ". "
        "At least 35 control groups and AP-worker recorded admission remain open. No native byte, phase, "
        "flag, ISO or production status changes. Exact-candidate canonical, Doctor, release, publication "
        "and configured GitHub/review gates still precede main merge; development branches provide cloud backup. "
        "N0 custody, N5 authentication, general retirement and physical hardware remain open."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N8", "N9", "N10", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 212 source inventory: 1108 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N9-PMM-ACPI-CONSUMER-001", "FLAG-N9-VM-DIRECT-MAP-001",
                          "FLAG-N8-IRQ-001", "FLAG-N8-SMP-IPI-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle213(roadmap, test_count)


def apply_cycle213(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle213-current-kernel-scheduler-replay.md"
    next_move = "N12-SCHED-SMP-001"
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for key, value in list(gate.items()):
        if key.startswith("current_") and isinstance(value, dict):
            suffix = "source_projection" if key == "current_focused_source_projection" else key.removeprefix("current_")
            gate["historical_cycle212_" + suffix] = copy.deepcopy(value)
    roadmap["baseline"]["pooleos_cycle"] = 213
    roadmap["execution_protocol"].update(last_updated_cycle=213,
        selected_move_id="N12-SCHED-001", owner_independent_next_move_id=next_move)
    roadmap["execution_protocol"]["required_records"].insert(0, checkpoint)
    gate["qualification_status"] = "current_kernel_scheduler_admitted_five_dependencies_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=213)
    record = copy.deepcopy(gate["historical_cycle207_dependency_qualification"])
    record["receipt_bindings"][:6] = copy.deepcopy(gate["historical_cycle212_dependency_qualification"]["receipt_bindings"])
    rows = (
        ("scheduler", "687FC1818AB0E00E533AFAD88D4C905807543F9F78676233CC332B9A25F9BE69",
         "05FDDA173940B525A595C1426BC1D07FB610D321F79F5CF33C3A58364A100696", 121.297),
        ("scheduler_preempt", "CAFD7C7140E8912246E1CFA52EA3BEC2382FD519DE824DFE9B41E1CA2CA44DD2",
         "C4CA732801FB906F7442652BE154022EA0C59C4E633C31145D785E2F4E5A52F5", 94.375),
        ("scheduler_deferred", "E956D15D43CEA3B0E5E14821115123DE69DAEFB9E75AC46C2F89A159CD93219F",
         "E12A45434566B849DD8DC27938DC5EE50E8BFA45D9F58DD3867479C1C06D291E", 93.063),
    )
    for binding, (profile, digest, log, seconds) in zip(record["receipt_bindings"][6:], rows, strict=True):
        assert binding["profile"] == profile
        binding.update(sha256=digest, execution_log_sha256=log, elapsed_seconds=seconds)
    record.update(cycle=213, source_validation_cycle=213,
        scope="retained_six_memory212_and_three_fresh_scheduler213_profiles_on_unchanged_kernel210",
        run_count_scope="Cycle213_three_scheduler_profiles_only_not_retained_memory_CPU_boot_runs",
        kernel_sha256=gate["current_entry_provenance_qualification"]["canonical_sha256"],
        independent_deferred_linked_identity_cases=14,
        unproven_per_control_rejection_groups_at_least=35)
    gate["current_dependency_qualification"] = record
    projection = copy.deepcopy(gate["historical_cycle207_source_projection"])
    projection.update(cycle=213, run_count_scope="Cycle213_three_scheduler_profiles_only",
        required_next_gate="current_SMP_replay_then_AP_worker_admission_controls_and_remaining_profiles_then_full_candidate")
    gate["current_focused_source_projection"] = projection
    gate["current_entry_provenance_qualification"] = dict(gate["current_entry_provenance_qualification"], latest_reproduction_cycle=213)
    gate["current_ipi_mailbox_oracle_gap"] = dict(gate["current_ipi_mailbox_oracle_gap"], cycle=213,
        remaining_affected_profiles=5, newly_requalified_profiles=record["newly_qualified_profiles"])
    gate["current_control_execution_audit"] = dict(gate["current_control_execution_audit"], cycle=213)
    for key, binding in (("current_preemption_control_execution_audit", record["receipt_bindings"][-2]),
                         ("current_deferred_control_qualification", record["receipt_bindings"][-1])):
        gate[key] = dict(gate[key], cycle=213, source_validation_cycle=213,
            receipt_sha256=binding["sha256"], current_kernel_live_replay_pending=False,
            current_receipt_admitted=True, applies_to_current_source=True,
            aggregate_unproven_groups_at_least=35,
            historical_record="historical_cycle212_" + key.removeprefix("current_"))
    gate["current_deferred_transaction_qualification"] = dict(gate["current_deferred_transaction_qualification"],
        current_kernel_live_replay_pending=False, current_receipt_admitted=True,
        latest_live_replay_cycle=213, latest_live_receipt_sha256=rows[-1][1],
        latest_live_kernel_sha256=record["kernel_sha256"],
        historical_record="historical_cycle212_deferred_transaction_qualification")
    gate["current_closeout_regression"] = {
        "cycle": 213, "status": "pass", "scope": "three_scheduler_profiles_and_deferred_identity_gate_not_full_canonical",
        "tests_run": 47, "tests_passed": 47, "tests_failed": 0, "tests_skipped": 0,
        "elapsed_seconds": 61.783, "runner_elapsed_seconds": 62.704,
        "log_sha256": "3941A59CEFFBF5D290FF9D3CF2095AD3B0D6AC0970DCF865A1219E2508B5E385",
        "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        "initial_deferred_admission": {
            "status": "fail", "detail": "PKSCHED3 host oracle, source, or linked switch audit changed",
            "candidate_sha256": rows[-1][1], "failed_guest_runs": 0,
            "guest_evidence_rewritten_or_rerun": False,
        },
        "corrected_deferred_admission": {
            "status": "pass", "same_candidate_sha256": rows[-1][1],
            "independently_measured_relocation_count": 1323,
            "independently_measured_kernel_sha256": record["kernel_sha256"],
            "schema_or_component_validation_bypassed": False,
        },
        "isolated_relocation_type_audit": {
            "wrong_value": 1323.0, "full_gate_accepted_before": False,
            "full_gate_accepted_after": False, "isolated_pin_accepted_before": True,
            "isolated_pin_accepted_after": False,
            "component_bypassed_only_for_isolated_diagnostic": True,
            "genuine_current_positive_passed_before_and_after": True,
        },
        "corrected_metadata_regression": {
            "tests_run": 60, "tests_passed": 60, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 34.041, "runner_elapsed_seconds": 34.828,
            "log_sha256": "4ED07E0803CF5E14C092475A750AC8A5362ED2F25E3898D5871C76B88119B953",
            "source_unchanged_during_execution": True, "owner_report_unchanged": True,
            "scope": "roadmap_architecture_and_locked_checklist_not_full_canonical",
        },
        "initial_metadata_regression": {
            "tests_run": 60, "tests_passed": 57, "tests_failed": 3, "tests_skipped": 0,
            "elapsed_seconds": 32.354, "runner_elapsed_seconds": 33.172,
            "log_sha256": "ADF15E460BCB8CD21E92EB6E06D9246E8B1A33E53B6805C67B688696F4709D33",
            "cause": "three_progress_assertions_still_expected_eight_pending_profiles_and_stale_deferred_evidence",
            "source_unchanged_during_execution": True, "owner_report_unchanged": True,
            "admitted_as_passing_suite": False,
        },
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 213: " + checkpoint + " qualifies scheduler, preemption and deferred work on unchanged kernel210. "
        "Six virtual boots, 83 control groups covering 595 cases and 47 focused tests pass, including "
        "768 corrupted records, 14 isolated linked-identity cases and 19 disabled native variants. "
        "Two measured deferred image pins are reconciled; the identical candidate passes. An isolated "
        "float-relocation pin inconsistency is repaired; full admission already rejected that float."
    )
    gap = (
        "Selected readiness is 22/27; five SMP scheduler/atomic/lock profiles remain from " + next_move + ". "
        "At least 35 control groups and AP-worker recorded admission remain open. No native byte, phase, "
        "flag, ISO or production status changes. Exact-candidate canonical, Doctor, release, publication "
        "and configured GitHub/review gates still precede main merge; development branches provide cloud backup. "
        "N0 custody, N5 authentication, general retirement and physical hardware remain open."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N12", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 213 source inventory: 1109 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N12-SCHED-FOUNDATION-001", "FLAG-N12-SCHED-PREEMPT-001",
                          "FLAG-N12-SCHED-DEFERRED-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle214(roadmap, test_count)


def apply_cycle214(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle214-current-kernel-smp-scheduler-replay.md"
    next_move = "N12-SCHED-AP-WORKERS-001"
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for key, value in list(gate.items()):
        if key.startswith("current_") and isinstance(value, dict):
            suffix = "source_projection" if key == "current_focused_source_projection" else key.removeprefix("current_")
            gate["historical_cycle213_" + suffix] = copy.deepcopy(value)
    roadmap["baseline"]["pooleos_cycle"] = 214
    roadmap["execution_protocol"].update(last_updated_cycle=214,
        selected_move_id="N12-SCHED-SMP-001", owner_independent_next_move_id=next_move)
    roadmap["execution_protocol"]["required_records"].insert(0, checkpoint)
    gate["qualification_status"] = "current_kernel_SMP_scheduler_admitted_four_dependencies_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=214)
    digest = "6A7EDCA3DCC42389D55170584C975D9DEAEBA8DBE790A21E13A7E243298FE527"
    binding = dict(profile="scheduler_smp", path="runs/native-kernel-scheduler-smp-readiness.json",
        sha256=digest, fresh_runs=2, negative_controls=32, hostile_cases=303, kernel_host_tests=246,
        execution_log_sha256="B4AFCEDC4E0B5203EA8C7434E85C6ABD1BFF4D8CFEFFE76250C1A9A84BB46958",
        elapsed_seconds=82.594, recorded_evidence_cases=279)
    retained = gate["historical_cycle213_dependency_qualification"]
    record = copy.deepcopy(gate["historical_cycle208_dependency_qualification"])
    record.update(cycle=214, source_validation_cycle=214,
        scope="retained_memory212_scheduler213_and_fresh_SMP214_on_unchanged_kernel210",
        qualified_profiles=retained["qualified_profiles"] + ["scheduler_smp"],
        receipt_bindings=copy.deepcopy(retained["receipt_bindings"]) + [binding],
        kernel_sha256=retained["kernel_sha256"], superseded_initial_runs=0,
        run_count_scope="Cycle214_two_fresh_SMP_boots_only_not_retained_memory_scheduler_CPU_boot_runs",
        focused_python_tests=19, independent_aggregate_cases=11)
    gate["current_dependency_qualification"] = record
    projection = gate["current_focused_source_projection"]
    gate["current_focused_source_projection"] = dict(projection, cycle=214,
        passed_checks=23, pending_downstream_native_checks=4,
        passing_profiles=projection["passing_profiles"] + ["native_kernel_scheduler_smp_readiness"],
        final_receipt_fresh_qemu_runs=2, kernel_entry_runs=2, superseded_initial_qemu_runs=0,
        run_count_scope="Cycle214_two_fresh_SMP_boots_only", next_dependency_move_id=next_move,
        required_next_gate="AP_worker_admission_and_18_controls_four_profiles_then_full_candidate",
        focused_python_tests_passed=19, recorded_evidence_rejection_cases=326)
    gate["current_entry_provenance_qualification"] = dict(gate["current_entry_provenance_qualification"], latest_reproduction_cycle=214)
    gate["current_ipi_mailbox_oracle_gap"] = dict(gate["current_ipi_mailbox_oracle_gap"], cycle=214,
        remaining_affected_profiles=4, newly_requalified_profiles=["scheduler_smp"])
    gate["current_control_execution_audit"] = dict(gate["current_control_execution_audit"], cycle=214)
    gate["current_smp_control_qualification"] = dict(gate["current_smp_control_qualification"],
        cycle=214, source_validation_cycle=214, original_repair_cycle=208,
        applies_to_current_source=True, receipt_sha256=digest, current_receipt_admitted=True,
        current_kernel_live_replay_pending=False, measured_canonical_sha256=record["kernel_sha256"],
        measured_relocation_count=1323, historical_record="historical_cycle213_smp_control_qualification",
        original_failure_audits_reexecuted_this_cycle=False,
        after_audit_scope="historical_Cycle208_admission_repair_latest_replay_recorded_in_current_closeout")
    gate["current_smp_transaction_qualification"] = dict(gate["current_smp_transaction_qualification"],
        latest_live_replay_cycle=214, latest_live_receipt_sha256=digest,
        latest_live_kernel_sha256=record["kernel_sha256"], current_kernel_live_replay_pending=False,
        current_receipt_admitted=True, historical_artifact_identity_retained=True,
        applies_to_current_source_scope="original_Cycle203_entry_and_core_artifacts_not_current_kernel",
        historical_record="historical_cycle213_smp_transaction_qualification")
    gate["current_closeout_regression"] = {
        "cycle": 214, "status": "pass", "scope": "SMP_scheduler_controls_transactions_and_identity_gate_not_full_canonical",
        "tests_run": 19, "tests_passed": 19, "tests_failed": 0, "tests_skipped": 0,
        "elapsed_seconds": 43.153, "runner_elapsed_seconds": 44.047,
        "log_sha256": "AFACEB291245818E00FFF30CF69D48EBE6BA167285B51B3AF8B15282ED4BCEBC",
        "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        "initial_SMP_admission": {"status": "fail", "detail": "PKSCHED4 host oracle, source, or linked INVLPG audit changed",
            "candidate_sha256": digest, "failed_guest_runs": 0},
        "corrected_SMP_admission": {"status": "pass", "same_candidate_sha256": digest,
            "guest_evidence_rewritten_or_rerun": False, "schema_or_component_validation_bypassed": False},
        "isolated_relocation_type_audit": {"wrong_value": 1323.0,
            "full_gate_accepted_before": False, "full_gate_accepted_after": False,
            "isolated_pin_accepted_before": True, "isolated_pin_accepted_after": False,
            "component_bypassed_only_for_isolated_diagnostic": True},
        "source_binding_workflow_failure": {
            "temporary_test_edit_invalidated_candidate": True,
            "after_audit_and_admission_stopped_before_copy": True,
            "regression_launched_despite_failed_admission": True,
            "old_public_receipt_used_in_failed_regression": True,
            "aggregate_regression_moved_to_unbound_gate_test_module": True,
            "original_bound_test_restored_byte_exactly": True,
            "positive_receipt_rebound_or_validation_bypassed": False,
        },
        "initial_focused_regression": {"tests_run": 18, "tests_passed": 13, "tests_failed": 5, "tests_skipped": 0,
            "elapsed_seconds": 29.212, "runner_elapsed_seconds": 30.109,
            "log_sha256": "88669854A9DED7DBFC07E703B95959F5F92FB516C2E27F9D4490467E87C9D912",
            "cause": "tests_launched_after_rejected_admission_still_read_previous_kernel_receipt",
            "admitted_as_passing_suite": False},
        "metadata_regression": {"tests_run": 61, "tests_passed": 61, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 34.397, "runner_elapsed_seconds": 35.234,
            "log_sha256": "99561256817568CF85572EF0270D9F5AA8701DF4431A7A665BCF2E9D2105928A",
            "source_unchanged_during_execution": True, "owner_report_unchanged": True,
            "scope": "roadmap_architecture_and_locked_checklist_not_full_canonical"},
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 214: " + checkpoint + " admits the SMP scheduler on unchanged kernel210. Two four-vCPU "
        "boots, 32 control groups covering 303 cases and 19 focused tests pass, including 326 corrupted "
        "records, 11 independent aggregate cases and 22 disabled native variants. Two measured image "
        "pins and an isolated integer-type guard are repaired. The same guest candidate is admitted. "
        "An initial bound-test edit and premature regression caused five failures; all are preserved."
    )
    gap = (
        "Selected readiness is 23/27; four AP-worker/SMP-preemption/atomic/lock profiles remain from " + next_move + ". "
        "At least 35 control groups and AP-worker recorded admission remain open. No native byte, phase, "
        "flag, ISO or production status changes. Full exact-candidate canonical, Doctor, release, publication "
        "and configured GitHub/review gates still precede main merge; branch backup is separate. "
        "N0 custody, N5 authentication, general retirement and physical hardware remain open."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N12", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 214 source inventory: 1111 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N12-SCHED-SMP-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle215(roadmap, test_count)


def apply_cycle215(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle215-ap-worker-admission-and-controls.md"
    next_move = "N12-SCHED-SMP-PREEMPT-001"
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for key, value in list(gate.items()):
        if key.startswith("current_") and isinstance(value, dict):
            suffix = "source_projection" if key == "current_focused_source_projection" else key.removeprefix("current_")
            gate["historical_cycle214_" + suffix] = copy.deepcopy(value)
    roadmap["baseline"]["pooleos_cycle"] = 215
    roadmap["execution_protocol"].update(last_updated_cycle=215,
        selected_move_id="N12-SCHED-AP-WORKERS-001", owner_independent_next_move_id=next_move)
    roadmap["execution_protocol"]["required_records"].insert(0, checkpoint)
    gate["qualification_status"] = "AP_worker_admission_and_controls_repaired_three_dependencies_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=215)
    digest = "30B59312AF639F6E0B55391FCB33474A9B999E351BCC414E5A8B0384B53A82B4"
    binding = dict(profile="scheduler_ap_workers", path="runs/native-kernel-scheduler-ap-workers-readiness.json",
        sha256=digest, fresh_runs=2, negative_controls=34, hostile_cases=325, kernel_host_tests=246,
        execution_log_sha256="B06620B801239E6381B91722D9B146A38F8E0EDC3B2CA346918A635BF2F030DA",
        elapsed_seconds=82.687, recorded_evidence_cases=294)
    previous = gate["historical_cycle214_dependency_qualification"]
    record = copy.deepcopy(previous)
    record.update(cycle=215, source_validation_cycle=215, status="eleven_current_profiles_three_pending",
        scope="retained_memory212_scheduler213_SMP214_and_fresh_AP_workers215_on_unchanged_kernel210",
        qualified_profiles=previous["qualified_profiles"] + ["scheduler_ap_workers"],
        newly_qualified_profiles=["scheduler_ap_workers"],
        readiness_replay_required_profiles=["scheduler_smp_preempt", "atomics", "locks"],
        receipt_bindings=copy.deepcopy(previous["receipt_bindings"]) + [binding],
        fresh_qemu_runs=2, superseded_initial_runs=2, failed_guest_runs=0,
        run_count_scope="Cycle215_two_final_boots_only_two_diagnostic_baseline_boots_excluded",
        negative_control_groups=34, negative_control_cases=325, executed_rejection_cases=266,
        native_boundary_cases=59, focused_python_tests=19, generic_recorded_evidence_cases=294,
        additional_control_profile_receipt_cases=49, recorded_evidence_case_total=343,
        independent_aggregate_cases=10, disabled_AP_worker_native_variants_detected=14,
        disabled_transaction_variants_detected=15, unproven_per_control_rejection_groups_at_least=17)
    record.pop("disabled_SMP_native_variants_detected")
    gate["current_dependency_qualification"] = record
    projection = gate["current_focused_source_projection"]
    gate["current_focused_source_projection"] = dict(projection, cycle=215,
        passed_checks=24, pending_downstream_native_checks=3,
        passing_profiles=projection["passing_profiles"] + ["native_kernel_scheduler_ap_workers_readiness"],
        final_receipt_fresh_qemu_runs=2, kernel_entry_runs=2, superseded_initial_qemu_runs=2,
        run_count_scope="Cycle215_two_final_AP_worker_boots_only", next_dependency_move_id=next_move,
        required_next_gate="SMP_preemption_admission_and_17_controls_three_profiles_then_full_candidate",
        focused_python_tests_passed=19, recorded_evidence_rejection_cases=343)
    gate["current_entry_provenance_qualification"] = dict(gate["current_entry_provenance_qualification"], latest_reproduction_cycle=215)
    gate["current_ipi_mailbox_oracle_gap"] = dict(gate["current_ipi_mailbox_oracle_gap"], cycle=215,
        remaining_affected_profiles=3, newly_requalified_profiles=["scheduler_ap_workers"])
    audit = gate["current_control_execution_audit"]
    gate["current_control_execution_audit"] = dict(audit, cycle=215,
        scope="one_remaining_SMP_preemption_loop_not_exhaustive_all_profile_audit",
        unproven_per_control_rejection_groups_at_least=17, next_profile="scheduler_smp_preempt",
        AP_worker_groups_repaired=18,
        source_control_gaps=[copy.deepcopy(g) for g in audit["source_control_gaps"] if g["profile"] != "scheduler_ap_workers"])
    gate["current_ap_worker_control_qualification"] = {
        "cycle": 215, "source_validation_cycle": 215, "move_id": "N12-SCHED-AP-WORKERS-001",
        "status": "pass", "applies_to_current_source": True, "current_receipt_admitted": True,
        "current_kernel_live_replay_pending": False, "receipt_sha256": digest,
        "kernel_sha256": record["kernel_sha256"], "measured_relocation_count": 1323,
        "constant_only_groups_replaced": 18, "native_groups": 14, "native_cases": 59,
        "source_groups": 4, "source_rejections": 58, "generic_record_cases": 294,
        "additional_record_cases": 49, "independent_gate_cases": 10,
        "disabled_native_variants_detected": 14, "disabled_transaction_variants_detected": 15,
        "diagnostic_baseline": {
            "receipt_sha256": "D896E4406E85D11B7CE7756C9F66CC5C5ACD9BEC693D6AA309F2E9DCB040D942",
            "boots": 2, "elapsed_seconds": 84.125,
            "log_sha256": "02E0E81B096AB0EDEEFF1DD25C6F54431329A048B7E29574BB3DCCD44B88245A",
            "current_runtime_accepted": True, "original_gate_accepted": False,
            "original_gate_detail": "PKSCHED5 host oracle, source, or linked INVLPG audit changed",
            "pin_corrected_genuine_gate_accepted": True,
            "runtime_corruptions_accepted": 279, "gate_corruptions_accepted_after_pin_repair": 178,
            "runtime_exceptions": 4, "gate_exceptions": 19,
            "qualified_after_repair": False,
        },
        "after_audit": {"genuine_runtime_accepted": True, "genuine_gate_accepted": True,
            "case_count": 294, "runtime_corruptions_accepted": 0, "gate_corruptions_accepted": 0,
            "runtime_exceptions": 0, "gate_exceptions": 0},
        "pair_validation_is_freshness_or_authentication": False,
        "positive_receipt_rebound_in_tests": False, "native_kernel_changed": False,
        "full_hardware_fault_injection": False, "production_ready": False,
    }
    gate["current_ap_worker_transaction_qualification"] = dict(gate["current_ap_worker_transaction_qualification"],
        latest_live_replay_cycle=215, latest_live_receipt_sha256=digest,
        latest_live_kernel_sha256=record["kernel_sha256"], current_kernel_live_replay_pending=False,
        current_receipt_admitted=True, recorded_evidence_admission_repaired=True,
        constant_only_control_groups_replaced=18, remaining_AP_worker_control_groups=0,
        remaining_global_control_groups_at_least=17, historical_artifact_identity_retained=True,
        applies_to_current_source_scope="original_Cycle209_entry_and_core_artifacts_not_current_kernel",
        historical_record="historical_cycle214_ap_worker_transaction_qualification")
    gate["current_closeout_regression"] = {
        "cycle": 215, "status": "pass", "scope": "AP_worker_admission_controls_transactions_not_full_canonical",
        "tests_run": 19, "tests_passed": 19, "tests_failed": 0, "tests_skipped": 0,
        "elapsed_seconds": 37.801, "runner_elapsed_seconds": 38.687,
        "log_sha256": "EED2A9C54843FB2CA73BFE1D83BD498E436F16D905CC44337DA93D20AB348499",
        "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        "initial_control_harness": {"tests_run": 5, "failure_records": 4,
            "elapsed_seconds": 12.695, "runner_elapsed_seconds": 13.625,
            "log_sha256": "A922A8463B9CDD95172CEBE792AE3D85A7E497C5D97EF944A6D8D8C96DDBEC6C",
            "causes": ["declared_total61_instead_of_executed59", "redundant_timeout_guard_mutation_masked_by_preflight",
                       "two_native_variants_detected_by_invariant_instead_of_assertion_text"], "admitted_as_pass": False},
        "corrected_control_harness": {"tests_run": 5, "tests_passed": 5, "tests_skipped": 0,
            "elapsed_seconds": 12.394, "runner_elapsed_seconds": 13.281,
            "log_sha256": "8B72F7FD7F645C54D47DB1DBA4BFD68255CB349B4EAFA14096C744811B1F239C"},
        "initial_metadata_regression": {"tests_run": 62, "tests_passed": 59, "tests_failed": 3, "tests_skipped": 0,
            "elapsed_seconds": 34.309, "runner_elapsed_seconds": 35.093,
            "log_sha256": "06C938D9778EBD6E231730AFCA4EB988AD69767B1306D310BA326C73A7931AAC",
            "cause": "three_stale_progress_assertions_not_native_or_receipt_failures", "admitted_as_pass": False},
        "second_metadata_regression": {"tests_run": 62, "tests_passed": 61, "tests_failed": 1, "tests_skipped": 0,
            "elapsed_seconds": 34.339, "runner_elapsed_seconds": 35.125,
            "log_sha256": "154FF5409A9A80890B01D9681083C8B592FA33A4DC8FB15B9E824450051EBE6D",
            "cause": "remaining_stale_pending_profile_count_now_asserts_exact_three_profiles", "admitted_as_pass": False},
        "metadata_regression": {"tests_run": 62, "tests_passed": 62, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 34.281, "runner_elapsed_seconds": 35.063,
            "log_sha256": "AD3EC6118AD143DA62371EBC2566FC728DB01C6F39D14B499D57DFB6964FFEA1",
            "source_unchanged_during_execution": True, "owner_report_unchanged": True,
            "scope": "roadmap_architecture_and_locked_checklist_not_full_canonical"},
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 215: " + checkpoint + " repairs AP-worker recorded admission and eighteen constant-only "
        "groups. Two final four-vCPU boots pass 34 groups/325 cases, including 59 native boundaries and "
        "58 source mutations. Nineteen focused tests pass, rejecting 343 corrupt records and ten independent "
        "gate cases and detecting 29 disabled safeguard/transaction variants. Two diagnostic boots, initial "
        "279/178 bad admissions, 4/19 exceptions and four harness failures remain preserved."
    )
    gap = (
        "Selected readiness is 24/27. SMP preemption, atomics and locks remain from " + next_move + ". "
        "At least seventeen SMP-preemption control groups remain; full exact-candidate canonical, Doctor, "
        "release, publication and GitHub/review gates precede main merge. Native bytes, broader phase/flag "
        "statuses and the demo ISO are unchanged. N0 custody, N5 authentication, general retirement, "
        "independent builders and physical hardware remain open; branch backup is not production."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N12", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 215 source inventory: 1121 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N12-SCHED-AP-WORKERS-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle216(roadmap, test_count)


def apply_cycle216(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle216-native-smp-preempt-transactions.md"
    kernel = "FD6C2A0C709957B9EDFFC0647D534E060ED68215C075F07D70AB2AEBCA6C81D1"
    entry = "1B5A40C248B02809CFEA397D058973DFD43DE5B85468BA31BD368EE3D8ED7CC7"
    core = "8AA5643002A3FBE416C1B40ECA0BD3D1DFAE7785E500ACBD06292FFAFFAB9DCB"
    next_move = "N5-SYMBOLS-SEMANTICS-001"
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for key, value in list(gate.items()):
        if key.startswith("current_") and isinstance(value, dict):
            suffix = "source_projection" if key == "current_focused_source_projection" else key.removeprefix("current_")
            gate["historical_cycle215_" + suffix] = copy.deepcopy(value)
    roadmap["baseline"]["pooleos_cycle"] = 216
    protocol = roadmap["execution_protocol"]
    protocol.update(last_updated_cycle=216, selected_move_id="N12-SCHED-SMP-PREEMPT-001",
                    owner_independent_next_move_id=next_move)
    protocol["required_records"].insert(0, checkpoint)
    gate["qualification_status"] = "native_SMP_preemption_transactions_repaired_changed_image_replay_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=216)
    gate["current_focused_source_projection"] = {
        "cycle": 216, "scope": "27_selected_native_checks_not_full_canonical_audit",
        "passed_checks": 3, "total_checks": 27, "pending_downstream_native_checks": 24,
        "passing_profiles": ["native_kernel_entry_readiness", "native_policy_readiness", "native_kernel_errata_policy_readiness"],
        "final_receipt_fresh_qemu_runs": 0, "kernel_entry_runs": 0,
        "next_dependency_move_id": next_move,
        "required_next_gate": "changed_image_symbols_boot_CPU_memory_scheduler_replay_and_executed_SMP_preemption_controls",
        "canonical_full_replay_performed": False, "production_ready": False,
    }
    pending_profiles = {
        "boot_chain": ["symbol", "kernel_load", "pooleboot", "kernel_revalidation", "kernel_transfer"],
        "cpu": ["trap", "cpu_policy", "xstate_policy", "xstate_exception", "privilege_msr_policy"],
        "dependency": ["physical_memory", "virtual_memory", "interrupt_time", "smp_first_ap", "smp_percpu_runtime",
                       "smp_ipi", "scheduler", "scheduler_preempt", "scheduler_deferred", "scheduler_smp",
                       "scheduler_ap_workers", "scheduler_smp_preempt", "atomics", "locks"],
    }
    for group, profiles in pending_profiles.items():
        gate["current_" + group + "_qualification"] = {
            "cycle": 216, "source_validation_cycle": 216, "status": "source_requalification_required",
            "applies_to_current_source": False, "kernel_sha256": kernel,
            "historical_record": "historical_cycle215_" + group + "_qualification",
            "qualified_profiles": ["policy"] if group == "boot_chain" else [],
            "readiness_replay_required_profiles": profiles, "fresh_qemu_runs": 0, "receipt_bindings": [],
            "embedded_entry_provenance_replay_pending": True, "all_fourteen_profiles_current": False,
            "control_execution_complete": False, "unproven_per_control_rejection_groups_at_least": 17,
            "current_candidate_full_gate_passed": False, "production_ready": False,
        }
    gate["current_entry_provenance_qualification"] = dict(
        gate["current_entry_provenance_qualification"], cycle=216, source_validation_cycle=216,
        linked_byte_count=7158864, linked_sha256="5E40AB31AFB4BCE79BEDB32D7B66D64D957B42CA915B2B70D2F15049F90B7D91",
        canonical_byte_count=538264, canonical_sha256=kernel, entry_receipt_sha256=entry,
        source_binding_count=79, latest_reproduction_cycle=216,
    )
    gate["current_task_stack_qualification"] = dict(gate["current_task_stack_qualification"], cycle=216, receipt_sha256=core)
    gate["current_execution_qualification"] = dict(gate["current_execution_qualification"], cycle=216,
        receipt_sha256=core, kernel_sha256=kernel)
    gate["current_ownership_qualification"] = dict(
        gate["current_ownership_qualification"], cycle=216, host_qualification_cycle=216,
        scope="host216_only_prior_IPI_and_VM_receipts_historical", kernel_sha256=kernel,
        reclamation_receipt_sha256=core, entry_receipt_sha256=entry, fresh_current_cycle_qemu_runs=0,
        live_receipt_source_current=False, current_boot_artifact_set_replay_pending=True,
        active_root_current_image_replay_complete=False, ap_runtime_live_integration_verified=False,
        virtual_memory_live_receipt_source_current=False,
        live_receipt_scope="historical_IPI_and_VM212_not_current_kernel_execution",
        source_current_scope="host_core_and_entry_only", historical_record="historical_cycle215_ownership_qualification",
    )
    gate["current_ipi_mailbox_oracle_gap"] = dict(gate["current_ipi_mailbox_oracle_gap"], cycle=216,
        remaining_affected_profiles=24, newly_requalified_profiles=[], current_kernel_live_replay_pending=True)
    gate["current_control_execution_audit"] = dict(gate["current_control_execution_audit"], cycle=216)
    for name in ("preemption_control_execution_audit", "deferred_transaction_qualification",
                 "symbol_admission_qualification", "deferred_control_qualification", "smp_transaction_qualification",
                 "smp_control_qualification", "ap_worker_transaction_qualification", "ap_worker_control_qualification",
                 "retained_map_qualification"):
        gate["current_" + name] = dict(gate["current_" + name], applies_to_current_source=False,
            current_kernel_live_replay_pending=True, current_receipt_admitted=False,
            historical_record="historical_cycle215_" + name)
    gate["current_smp_preempt_transaction_qualification"] = {
        "cycle": 216, "move_id": "N12-SCHED-SMP-PREEMPT-001",
        "requirements": ["ADD-N12-SCHED-SMP-PREEMPT-001", "ADD-N36-RECEIPT-COVERAGE-001"],
        "status": "native_host_transactions_and_tick_continuation_verified_live_replay_pending",
        "scope": "exclusive_controller_state_transactions_not_cross_CPU_atomicity",
        "initial_tests_per_profile": 14, "initial_failures_by_optimization": {"0": 8, "3": 7},
        "initial_log_sha256": "67E5333E3899EE9B67A071288DD521C8C3D8DE73398B0E3E48E79A3D35332B8A",
        "event_progress_counterexamples_per_profile": 2,
        "event_diagnostic_log_sha256": "29239C23D02ADC6DFFA6473F53BC06AA02B7EBA4CEBE1F6BD6580427F5F2F981",
        "final_native_tests_per_profile": 27, "new_private_state_tests": 22, "host_optimization_levels": [0, 3],
        "disabled_native_variants_detected": 14, "redundant_guard_positive_controls": 1,
        "maximum_remote_operations_per_tick": 5, "timer_epoch_increments_per_tick": 1,
        "completion_preview_uses_discarded_copy": True, "hypothetical_ack_confers_live_authority": False,
        "live_ack_still_required": True, "cross_cpu_atomicity_proved": False,
        "sources": {
            "native/kernel/src/scheduler_smp_preempt.rs": "C4A8A1AD77524FB37BA68AA01E73198F9171C4A990EBC97751E91EA2B2328A1E",
            "tests/fixtures/pksched6_transaction_probe.rs": "7F1D594259AD6A365AD88ACD7C3EA33F1D66D89386F921C0A46FF63928F1AE21",
            "tests/fixtures/pksched6_event_progress_probe.rs": "597169419FE73DDABF98A815209B40E86B7C2C31653706C3D4F05DB259C9F807",
            "tests/test_native_smp_preempt_transactions.py": "77C18ADF244C55148029DCA9A1982F70E2D18C1B5BC44EEC0EAD4F19E2DEA9A5",
        },
        "kernel_sha256": kernel, "kernel_bytes_changed": True, "kernel_image_pages": 149,
        "entry_receipt_sha256": entry, "core_receipt_sha256": core,
        "recorded_evidence_admission_repaired": False, "constant_only_control_groups_replaced": 0,
        "remaining_global_control_groups_at_least": 17, "new_kernel_qemu_runs": 0,
        "production_ready": False,
    }
    gate["current_closeout_regression"] = {
        "cycle": 216, "status": "pass", "scope": "selected_native_host_core_entry_not_full_canonical",
        "tests_run": 43, "tests_passed": 43, "tests_failed": 0, "tests_skipped": 0,
        "elapsed_seconds": 84.635, "runner_elapsed_seconds": 85.531,
        "log_sha256": "CA39E66FDE99F24FB48146EB10B031FA6DA5DFE34F8DEF9CB53E45F6A0E619CB",
        "excluded_known_failing_live_test": "tests.test_native_kernel_transfer.NativeKernelTransferTests.test_contract_and_generated_readiness_are_current",
        "excluded_live_test_remains_a_merge_blocker": True,
        "metadata_regression": {"tests_run": 63, "tests_passed": 63, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 33.788, "runner_elapsed_seconds": 34.625,
            "log_sha256": "513FE08E46FD552224821AEB512C8DFD8BD754CF0A22FB82897847397C2F7949",
            "scope": "roadmap_architecture_and_locked_checklist_not_full_canonical"},
        "preserved_metadata_attempts": [
            {"tag": "metadata", "tests_run": 63, "failure_records": 38,
             "log_sha256": "2E4FAA97903ED30ABC7D762EE4FF7737C9E53D886D3AF94EDE1E1A44E340CEE9"},
            {"tag": "metadata2", "tests_run": 63, "failure_records": 37,
             "log_sha256": "2E6B7A6B3F96E49FF5837BE1A84E7EF8A2D5A911327B6BE8176EB625E733EB17"},
            {"tag": "metadata3", "tests_run": 63, "failure_records": 6, "error_records": 7,
             "log_sha256": "923EFF1A1E9704F02C39AA4017F779DF21966365C830320F5915E1FB598F78A5"},
        ],
        "metadata_failure_causes": ["stale_current_image_assertions_and_architecture_count",
            "mechanical_migration_anchor_absent_no_source_write", "archive_dictionary_names_applied_to_inner_fields",
            "unrelated_prerequisite_gates_outside_selected_projection", "historical_count_and_marker_expectations"],
        "initial_conservation_failure": "dynamic_test_inventory_was_applied_to_Cycle215_history_then_frozen_at_1121",
        "core_stages_passed": 17, "clean_entry_builds": 2, "kernel_tests_per_host_profile": 246,
        "entry_rejection_cases": 43, "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        "preserved_failures": [
            {"tag": "nativeextended", "cause": "two_mutation_anchors_ambiguous", "log_sha256": "45EEC1B2A4EB02311BC378648F7988045DDA0E018533CD5F3046020812F12009"},
            {"tag": "continuation", "cause": "capacity_guard_redundancy_misclassified", "log_sha256": "8E04F0CD27E692F70BBDAA07EC9824FF2D0C44DE90750123CCE11BEFB39C8663"},
            {"tag": "measure", "cause": "text_boundary_exceeded_by_814_bytes", "log_sha256": "41CD21B73397DF1D22B1CE7F7788CA5984AC19733FFDFD2196E44B16A6D06FA0"},
            {"tag": "entry", "cause": "old_size_contract_not_yet_reconciled", "log_sha256": "9AD692B18A469B3DF215CCD4169C319A5F34270676303CB2B82D34CCB8AEBAF4"},
            {"tag": "focused", "cause": "regression_started_after_receipt_admission_failed_stale_test_binding",
             "tests_run": 44, "tests_passed": 34, "tests_failed": 9, "tests_errored": 1,
             "log_sha256": "6B4FE0EA3B57B6F5F80E1EAE9B13819497F42CA1AF93C907E1D10DD86DBAF537"},
        ],
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 216: " + checkpoint + " repairs native SMP-preemption state transactions, epoch overflow, "
        "read-only query side effects, and same-tick remote-event/quantum continuation. Twenty-seven native "
        "tests in both host profiles, fourteen disabled variants, one redundant-check positive control, "
        "17 core stages, two matching builds, 246 kernel tests and 43 image controls pass. Selected host "
        "regression passes 43/43; the old live-transfer positive remains an explicit failing merge blocker. "
        "Initial native, harness, linker, size-contract and receipt-ordering failures are preserved."
    )
    gap = (
        "Kernel bytes changed; selected readiness is 3/27. Twenty-four profiles require replay from "
        + next_move + ". The SMP-preemption flag is reopened, and at least seventeen executed-control groups "
        "and recorded admission remain. No phase closes. N0 custody, N5 authentication, general SMP, "
        "independent builders, physical hardware, full canonical/Doctor/release qualification and main merge "
        "remain open. No current-image guest boot or ISO change is claimed. Branch backup is separate."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N5", "N6", "N12", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 216 source inventory: 1124 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N12-SCHED-SMP-PREEMPT-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
        if flag["id"] == "FLAG-N12-SCHED-SMP-PREEMPT-001":
            flag["status"] = "open"
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle217(roadmap, test_count)


def apply_cycle217(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle217-current-kernel-boot-replay.md"
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for key, value in list(gate.items()):
        if key.startswith("current_") and isinstance(value, dict):
            suffix = "source_projection" if key == "current_focused_source_projection" else key.removeprefix("current_")
            gate["historical_cycle216_" + suffix] = copy.deepcopy(value)
    roadmap["baseline"]["pooleos_cycle"] = 217
    roadmap["execution_protocol"].update(last_updated_cycle=217, selected_move_id="N5-SYMBOLS-SEMANTICS-001",
                                         owner_independent_next_move_id="N7-TRAP-001")
    roadmap["execution_protocol"]["required_records"].insert(0, checkpoint)
    gate["qualification_status"] = "current_kernel_boot_chain_qualified_CPU_and_downstream_replay_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=217)
    gate["current_focused_source_projection"] = {
        "cycle": 217, "scope": "27_selected_native_checks_not_full_canonical_audit",
        "passed_checks": 8, "total_checks": 27, "pending_downstream_native_checks": 19,
        "passing_profiles": ["native_kernel_entry_readiness", "native_symbol_readiness", "native_policy_readiness",
            "native_kernel_load_readiness", "native_pooleboot_readiness", "native_kernel_revalidation_readiness",
            "native_kernel_transfer_readiness", "native_kernel_errata_policy_readiness"],
        "final_receipt_fresh_qemu_runs": 6, "kernel_entry_runs": 2,
        "next_dependency_move_id": "N7-TRAP-001",
        "required_next_gate": "current_image_CPU_memory_scheduler_replay_and_executed_SMP_preemption_controls",
        "canonical_full_replay_performed": False, "production_ready": False,
    }
    rows = (
        ("symbol", "native_symbol", "E14EFC2D988192967FA21737519A310A6D987AA198E584672CF292B3B50A7311", 0, 158),
        ("policy", "native_policy", "EA3A12B78EB5A9B4A5BC7863DF962E97070213983224F670F9D1B3CE215057A4", 0, 116),
        ("kernel_load", "native_kernel_load", "A1A03D71AADF381FFE34217F74C3BFF583DBFF9EF9EF4FA41CED21EDC9BB0021", 2, 155),
        ("pooleboot", "native_pooleboot", "84417647DFCFD04765EE8F0C11BA66538E8DF7A8E58535E2EED9C010317EB0D4", 2, 155),
        ("kernel_revalidation", "native-kernel-revalidation", "8D35EAC9C8B39857ADC6A2B9596F698D628219996FF4C531176252930A8EC88E", 0, 36),
        ("kernel_transfer", "native-kernel-transfer", "B564B4459C810A558DCC55939C674947D771DFB519202D93BE8451D68B749302", 2, 58),
    )
    bindings = [dict(profile=profile, path="runs/" + filename + "_readiness.json" if "_" in filename else
                     "runs/" + filename + "-readiness.json", sha256=digest, fresh_runs=runs, negative_controls=controls)
                for profile, filename, digest, runs, controls in rows]
    gate["current_boot_chain_qualification"] = {
        "cycle": 217, "source_validation_cycle": 217, "status": "single_host_boot_replay_pass",
        "applies_to_current_source": True, "kernel_sha256": gate["current_entry_provenance_qualification"]["canonical_sha256"],
        "qualified_profiles": [b["profile"] for b in bindings], "readiness_replay_required_profiles": [],
        "receipt_bindings": bindings, "embedded_entry_provenance_replay_pending": False,
        "fresh_qemu_runs": 6, "kernel_entry_runs": 2, "focused_python_tests": 97,
        "kernel_host_tests": 246, "loader_rust_tests": 332, "pooleboot_host_tests": 8,
        "retained_files": 9, "retained_bytes": 11952, "manifest_bytes": 2615,
        "inner_artifacts": 6, "inner_bytes": 8761, "inner_payload_bytes": 8185,
        "inner_set_sha256": "AE7180A6C8126B2C2AAA119C24C8B53451E41EB2BF8DD0E259EB0DB947264C84",
        "trust_policy_sha256": "6691BF1BE2B76D48EB8D934CB11F113FBDC450038FDDC8A252F982A5BE5306AF",
        "trust_state_sha256": "8B93EDE9F95AE1F9AF8379B386982B8ECB81F124A38B10171717EBEF84FA0EA0",
        "manifest_sha256": "4AE6C6A9AEAF6EE9A27951BCC236756B441C03A82E2B9C1DA595A08BA6A3E76A",
        "real_image_trust_independently_reconstructed": True, "golden_fixture_is_actual_kernel": False,
        "independent_previous_identity_rejection_cases": 30, "component_validators_bypassed_only_in_negative_test": True,
        "terminal": "unsigned-denial-halt", "authority_created": 0, "state_writes": 0, "firmware_calls_after_exit": 0,
        "kernel_bytes_changed_this_cycle": False, "entry_and_core_receipts_unchanged": True,
        "map_probe_kernel_pages": 149, "map_reserved_kernel_pages": 192, "map_boundary_tests": 16,
        "symbol_unit_test_only_native_change": True, "map_probe_only_native_change": True,
        "complete_host_attestation": False, "second_builder_reproduced": False, "n5_exit_gate_satisfied": False,
        "current_candidate_full_gate_passed": False, "production_ready": False,
    }
    gate["current_symbol_admission_qualification"] = {
        "cycle": 217, "original_repair_cycle": 198, "applies_to_current_source": True,
        "historical_repair_record": "historical_cycle202_symbol_admission_qualification",
        "symbol_receipt_sha256": bindings[0]["sha256"], "current_receipt_admitted": True,
        "recorded_corruption_cases": 650, "runtime_rejected": 650, "aggregate_gate_rejected": 650,
        "native_parser_tests": 4, "native_control_cases": 158, "debug_builds_byte_identical": 2,
        "parser_differential_cases": 16384, "lookup_differential_cases": 16384,
        "rejected_output_preservation_cases": 2, "pre_repair_audit_reexecuted_this_cycle": False,
        "coherent_forgery_excluded": False, "recorded_consistency_is_freshness_or_authentication": False,
        "production_ready": False,
    }
    gate["current_ownership_qualification"] = dict(gate["current_ownership_qualification"],
        current_boot_artifact_set_replay_pending=False, boot_artifact_replay_cycle=217,
        source_current_scope="host_core_and_entry216_boot217_not_AP_or_VM")
    gate["current_entry_provenance_qualification"] = dict(
        gate["current_entry_provenance_qualification"], latest_reproduction_cycle=217)
    gate["current_ipi_mailbox_oracle_gap"] = dict(gate["current_ipi_mailbox_oracle_gap"], cycle=217,
        remaining_affected_profiles=19, newly_requalified_profiles=[b["profile"] for b in bindings])
    gate["current_closeout_regression"] = {
        "cycle": 217, "status": "pass", "scope": "boot_chain_admission_and_geometry_not_full_canonical",
        "tests_run": 97, "tests_passed": 97, "tests_failed": 0, "tests_skipped": 0,
        "elapsed_seconds": 40.816, "runner_elapsed_seconds": 41.734,
        "log_sha256": "2E2A8BCEAD885B6EE40E0E473D8A2F068830796DCADADA2F30C1A9BF8778014A",
        "metadata_regression": {
            "tests_run": 64, "tests_passed": 64, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 33.634, "runner_elapsed_seconds": 34.469,
            "log_sha256": "04E55F077CB6E2AF9C5DD08979A128FC326764EE74BA05AD9C927656D578A751",
            "initial_tests_run": 64, "initial_tests_failed": 2,
            "initial_log_sha256": "B1893D84AF98B11CCFA7E19154CB3D03C36A3DFE1D1F3D3F4DD15B0B738E4055",
            "initial_failure_causes": ["old_pending_profile_count", "historical_receipt_compared_with_current_file"],
        },
        "initial_conservation": {"status": "pass", "archived_parent_current_records": 24,
            "architecture_bindings": 369, "test_inventory": 1125, "selected_checks": "8/27",
            "all_phase_and_flag_statuses_preserved": True},
        "previously_failing_live_transfer_test_now_passes": True, "known_failure_exclusions": [],
        "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        "preserved_failures": [
            {"tag": "symbols", "cause": "native_test_lookup_used_previous_image_address", "seconds": 7.25,
             "log_sha256": "2F320C2718DF0920FA81936E219A136D2862CDCB967FE6F304261E75CF19CAD2"},
            {"tag": "load", "cause": "native_host_probe_used_previous_image_geometry", "seconds": 113.969,
             "log_sha256": "D7F82960B1721F0C33B80D25454E22F93B5C6898FDAAC8CCB566B3DE25865FEF"},
        ],
        "failed_receipts_admitted": False, "canonical_full_replay_performed": False,
        "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 217: " + checkpoint + " qualifies six boot-chain profiles on unchanged kernel216. Six fresh "
        "virtual boots include two kernel entries ending in unsigned-development denial. All 97 focused "
        "tests pass, including the previously stale live-transfer positive, 650 corrupt symbol records, "
        "30 independent artifact/trust pin rejections and 16 map tests. Two initial symbol/map-probe "
        "failures are preserved and repaired without changing the kernel implementation."
    )
    gap = (
        "Selected current readiness is 8/27; nineteen CPU/memory/SMP/scheduler profiles remain from "
        "N7-TRAP-001. Seventeen SMP-preemption control groups and recorded admission remain open. "
        "No phase or flag closes; N0 custody, N5 authentication, independent builders and physical "
        "hardware remain open. Full exact-candidate qualification still precedes main merge; "
        "branch cloud backup is separate. No signed activation, ISO change or production promotion."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N5", "N6", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 217 source inventory: 1125 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N5-SYMBOL-BUNDLE-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle218(roadmap, test_count)


def apply_cycle218(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle218-terminal-capture-and-cpu-replay.md"
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for key, value in list(gate.items()):
        if key.startswith("current_") and isinstance(value, dict):
            suffix = "source_projection" if key == "current_focused_source_projection" else key.removeprefix("current_")
            gate["historical_cycle217_" + suffix] = copy.deepcopy(value)
    roadmap["baseline"]["pooleos_cycle"] = 218
    roadmap["execution_protocol"].update(last_updated_cycle=218, selected_move_id="N7-TRAP-001",
        owner_independent_next_move_id="N9-PMM-ACPI-CONSUMER-001")
    roadmap["execution_protocol"]["required_records"].insert(0, checkpoint)
    gate["qualification_status"] = "terminal_capture_repaired_current_CPU_qualified_fourteen_dependencies_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=218)
    rows = (
        ("trap", "0437D9C2185674D5A5A7F084F14EFE662489969EA7AB77078B701E2FFD371A4C", 6, 51,
         "A7D909C2B3CCFF4B54B6D332F6507A8FAC16CD007F7A832C3C16D328A4486BB4", 106.75),
        ("cpu_policy", "588DD2BCA4C19D48C1E564FD075830F2D8A8DE67C764CB26080CD458A9BCB1E0", 2, 41,
         "CFA41675A79CE67949D1FDB8D08F791EB2FD1115237010D33465135306D1CE23", 69.047),
        ("xstate_policy", "DAEC34625644276E711EBAE5854F303FAC2770651AD5681D2A59A302D9ACFF75", 2, 43,
         "4260145CE808D54618100843E5797A22DAFA156F94093C1D222D6D99730A162A", 66.859),
        ("xstate_exception", "616936D78BA36C437C4E20BDE5FE8E7D45C059E90F915D2F2520D934AB058FD6", 2, 43,
         "F3ED8801D7E59F458EBE9E20B63EED505D5DEF7034E3E58654DA297E074BF60D", 77.672),
        ("privilege_msr_policy", "634265F8626719A9707355132EE4D72E9BD01979DDFB17533139E932CDE01C93", 2, 47,
         "9B9A31059D4151F9B9A62622272025F3EDB8EEF33A8C29EEA6267DBE5A72AE32", 75.61),
    )
    bindings = [dict(profile=profile, path="runs/native-kernel-" + profile.replace("_", "-") + "-readiness.json",
        sha256=digest, fresh_runs=runs, negative_controls=controls, kernel_host_tests=246,
        execution_log_sha256=log, elapsed_seconds=seconds)
        for profile, digest, runs, controls, log, seconds in rows]
    cpu = copy.deepcopy(gate["historical_cycle215_cpu_qualification"])
    cpu.pop("nested_build_admission_audit")
    cpu.update(cycle=218, source_validation_cycle=218, scope="five_N7_profiles_on_unchanged_Cycle216_kernel",
        kernel_sha256=gate["current_entry_provenance_qualification"]["canonical_sha256"], receipt_bindings=bindings,
        focused_python_tests=64, aggregate_gate_regression_cases=33, superseded_initial_runs=8,
        new_previous_image_and_wrong_typed_pin_rejection_cases=1, nested_build_regression_cases=80,
        historical_nested_build_repair_record="historical_cycle215_cpu_qualification")
    gate["current_cpu_qualification"] = cpu
    boot_rows = (
        ("kernel_load", "runs/native_kernel_load_readiness.json", "CD0F9CFBA4472AE5F6BB98EE20D244447A4E50C276C39E9D81581132989C4B68", 155,
         "CC1FBEAB3FC5A0A5A76A3484B496A2DE75EABE264CBA137E4D02C21421E34E9B", 108.672),
        ("pooleboot", "runs/native_pooleboot_readiness.json", "AE2223ED615B076835A28BCD003618B2E89213B4A4E2DB8BA10D0D4394F4EBB9", 155,
         "56338F6E2175B97E50BB1E2377476252F07B88CAAEAF64E220040A84FE086C65", 110.219),
        ("kernel_transfer", "runs/native-kernel-transfer-readiness.json", "B0B3AE877F3EE222FB19E50CD2891A955B8C9B1E3A3E42267FE0A15092D9D1B2", 58,
         "2768BD9CAC9B6A51E7707A696EFA9CA5EF53E4E9E04033EABF9EBA626E7DC6DC", 75.875),
    )
    boot_bindings = [dict(profile=profile, path=path, sha256=digest, fresh_runs=2,
        negative_controls=controls, execution_log_sha256=log, elapsed_seconds=seconds)
        for profile, path, digest, controls, log, seconds in boot_rows]
    boot = copy.deepcopy(gate["current_boot_chain_qualification"])
    refreshed = {b["profile"]: b for b in boot_bindings}
    boot.update(cycle=218, source_validation_cycle=218, fresh_profiles=list(refreshed),
        retained_component_profiles=["symbol", "policy", "kernel_revalidation"],
        retained_component_execution_cycle=217, source_validation_includes_retained_components=True,
        symbol_unit_test_only_native_change=False, map_probe_only_native_change=False,
        previous_focused_regression_record="historical_cycle217_closeout_regression")
    boot.pop("focused_python_tests")
    boot["receipt_bindings"] = [refreshed.get(b["profile"], b) for b in boot["receipt_bindings"]]
    gate["current_boot_chain_qualification"] = boot
    gate["current_capture_qualification"] = {
        "cycle": 218, "requirement_id": "ADD-N36-RECEIPT-COVERAGE-001", "status": "terminal_capture_repaired",
        "capture_after_validated_terminal": True, "delays_added": False, "frame_equality_relaxed": False,
        "native_bytes_changed": False, "unit_tests": 9, "before_failed_tests": 4, "after_failed_tests": 0,
        "before_log_sha256": "72E043DE76FBEE53F42B70EE3481FA38904E1E8EA768A047D1AEAC2098350983",
        "after_log_sha256": "5FAA431992507D7A26725EE9425F7A31F9FC82D585A4E78F0FF5672DA043278A",
        "initial_trap_failure": {"runs": 2, "elapsed_seconds": 98.141,
            "log_sha256": "FF72BC4F0ECA5B1149FAA1E2BCD625A9ACA0B3DB6EC3BFF78748A2C4CA2C3390",
            "cause": "paired_screenshots_differed", "original_differing_frames_retained": False,
            "exact_original_pixel_cause_proved": False},
        "diagnostic_pre_repair_replay": {"runs": 6, "elapsed_seconds": 107.141,
            "log_sha256": "A7D909C2B3CCFF4B54B6D332F6507A8FAC16CD007F7A832C3C16D328A4486BB4",
            "all_raw_frames_retained_locally": True, "admitted_after_repair": False},
        "early_frame_sha256": "E9D4CFD48C23DBA760AED5B2049B39DCA49A0D172F680D570082EB0680FDFDBD",
        "terminal_frame_sha256": "6AA5C90B92B580D07C11397FB89D44E2EBD090C04D526AC3E9F5D37A7B355B58",
        "early_vs_terminal_changed_pixel_bounds": [0, 0, 299, 23], "boot_receipt_bindings": boot_bindings,
        "final_boot_runs": 6, "final_CPU_runs": 14, "final_successful_runs": 20,
        "expected_TCG_limitation_probes": 1, "shared_helper_transitive_binding_audit_complete": False,
        "full_canonical_replay_performed": False, "production_ready": False,
    }
    projection = copy.deepcopy(gate["historical_cycle211_source_projection"])
    projection.update(cycle=218, run_count_scope="CPU218_fourteen_plus_boot218_six_not_initial_diagnostic_runs",
        focused_python_tests_passed=64, final_receipt_fresh_qemu_runs=20, kernel_entry_runs=16,
        required_next_gate="current_image_memory_SMP_scheduler_replay_and_remaining_preemption_controls")
    gate["current_focused_source_projection"] = projection
    gate["current_entry_provenance_qualification"] = dict(gate["current_entry_provenance_qualification"], latest_reproduction_cycle=218)
    gate["current_ownership_qualification"] = dict(gate["current_ownership_qualification"], boot_artifact_replay_cycle=218,
        source_current_scope="host_core_entry216_boot218_CPU218_not_AP_or_VM")
    gate["current_ipi_mailbox_oracle_gap"] = dict(gate["current_ipi_mailbox_oracle_gap"], cycle=218,
        remaining_affected_profiles=14, newly_requalified_profiles=[b["profile"] for b in bindings])
    gate["current_control_execution_audit"] = dict(gate["current_control_execution_audit"], cycle=218)
    gate["current_closeout_regression"] = {
        "cycle": 218, "status": "pass", "scope": "CPU_capture_and_aggregate_admission_not_full_canonical",
        "tests_run": 64, "tests_passed": 64, "tests_failed": 0, "tests_skipped": 0,
        "elapsed_seconds": 182.617, "runner_elapsed_seconds": 183.5,
        "log_sha256": "D0F982CB117B90DD22986C1F97A68A7652DFFEF1357C7278852CD1C06AB9C546",
        "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        "obsolete_trap_aggregate_pin_reconciled_from_measured_kernel": True,
        "before_pin_repair_selected_checks": 12, "after_pin_repair_selected_checks": 13,
        "initial_metadata_regression": {
            "tests_run": 65, "tests_passed": 60, "tests_failed": 5, "tests_skipped": 0,
            "elapsed_seconds": 28.123, "runner_elapsed_seconds": 28.922,
            "log_sha256": "068A764B7EB518E08C2501B009E844ABDDB26A12E54710EC1055D972BCCA56FA",
            "cause": "stale_current_CPU_receipt_and_projection_expectations",
        },
        "corrected_metadata_regression": {
            "tests_run": 65, "tests_passed": 65, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 34.444, "runner_elapsed_seconds": 35.234,
            "log_sha256": "D0387F4AFA5C258580A31CC91F56550A53875B1CBBB30A7F82F1359EE5412E83",
            "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        },
        "initial_conservation": {
            "status": "pass", "archived_records": 24, "architecture_bindings": 371,
            "test_inventory": 1135, "all_phase_and_flag_statuses_preserved": True,
            "receipt_sha256": "1242B163B215B70567057B00DFF53EF9AF9124E3D4FB3BA4C30C71A85DBEDA5C",
        },
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 218: " + checkpoint + " repairs an early QMP screenshot race without changing native bytes. "
        "Nine capture tests expose four old failures and all pass after terminal-stage capture. Twenty final "
        "virtual boots pass: six boot and fourteen CPU runs with 225 CPU controls and one separate TCG "
        "limitation probe. All 64 focused tests pass, including 3398 control-record corruptions, 371 paired "
        "run-evidence corruptions, 33 independent identity/promotion cases and 80 malformed nested-build cases. "
        "Two failed initial trap runs and six diagnostic pre-repair runs remain separate. Original differing "
        "frames were not retained; their exact pixel cause is unproven. Current trap pins are measured."
    )
    gap = (
        "Readiness is 13/27; fourteen memory/IRQ/SMP/scheduler/atomic/lock profiles remain from "
        "N9-PMM-ACPI-CONSUMER-001, plus seventeen SMP-preemption control groups and recorded admission. "
        "The broader shared-helper transitive-binding audit remains within ADD-N36-RECEIPT-COVERAGE-001. "
        "No phase or flag closes. Full canonical/Doctor/release/GitHub/review gates precede main merge; "
        "cloud branch backup is separate. N0 custody, N5 authentication, independent builders, physical "
        "hardware and production remain open. No ISO, signing, firmware or media change."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N5", "N7", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 218 source inventory: 1135 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N7-TRAP-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle219(roadmap, test_count)


def apply_cycle219(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle219-current-kernel-memory-replay.md"
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for key, value in list(gate.items()):
        if key.startswith("current_") and isinstance(value, dict):
            suffix = "source_projection" if key == "current_focused_source_projection" else key.removeprefix("current_")
            gate["historical_cycle218_" + suffix] = copy.deepcopy(value)
    roadmap["baseline"]["pooleos_cycle"] = 219
    roadmap["execution_protocol"].update(last_updated_cycle=219, selected_move_id="N9-PMM-ACPI-CONSUMER-001",
        owner_independent_next_move_id="N12-SCHED-001")
    roadmap["execution_protocol"]["required_records"].insert(0, checkpoint)
    gate["qualification_status"] = "current_kernel_memory_IRQ_SMP_admitted_eight_dependencies_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=219)
    rows = (
        ("physical_memory", "E98BC4D2AAF7DF9E748E99EC6AA701867DACC78DEB948DEA5725DEDAF9B4B26F",
         "EA410E61CD615D15E6DB74C485B0DAF07CF2AED81BE8A07B46E2A9A628163FD0", 76.937),
        ("virtual_memory", "3E9B0A808CC67FB3E418502F33D940CEC2F226D0CE6F553EFF5B6FDBE71643C5",
         "7F53E79717F800849474CC2A625F03F7BB7C5A2356813C050DEE8D8C62D4ECF1", 149.422),
        ("interrupt_time", "826D2CB6D18BE8BC7B1E6ADFEAB6D737DBE57375684B19F4DAAB96096304D7E1",
         "047FF2DF6EB68D3816503F9E81C83FA820E6D47828691C1D6F48D6B95C2F54B1", 71.422),
        ("smp_first_ap", "8B866AA7606A8E1A586F6BF4C1D6EF7B24D615FC6DB4400ECFDFED93267576FC",
         "6A25DBB4AE5AC7A23E7328961F320F5551C3A189A91211F1B4C970530B8614E1", 72.984),
        ("smp_percpu_runtime", "E9D4D23D90C4D1BE969F05C8D39D76BC9B380214339980E9FB6CEEC374BD1E1C",
         "BEDC73DE58B81C522F0C0F23D34D0E0573C50C2BA8A22ADF37436DC4F4E4C890", 64.063),
        ("smp_ipi", "91FEDCDF0435D8B0F4BC823E870AC8C4C33FAC4BCF3D48842269F76195FB014D",
         "E46A29F6E4A8FB43FA259C668D5724BB902F195D05533526E8765E26830A54C1", 77.593),
    )
    record = copy.deepcopy(gate["historical_cycle212_dependency_qualification"])
    bindings = record["receipt_bindings"]
    for binding, (profile, digest, log, seconds) in zip(bindings, rows, strict=True):
        assert binding["profile"] == profile
        binding.update(sha256=digest, execution_log_sha256=log, elapsed_seconds=seconds)
    record.update(cycle=219, source_validation_cycle=219,
        scope="six_fresh_memory_IRQ_AP_IPI_profiles_on_unchanged_Cycle216_kernel",
        run_count_scope="Cycle219_twelve_runs_only_not_retained_boot_or_CPU218",
        kernel_sha256=gate["current_entry_provenance_qualification"]["canonical_sha256"],
        independent_IPI_pin_rejection_cases=9, memory_gate_rejection_cases=29,
        embedded_entry_provenance_pending_scope="eight_remaining_scheduler_atomic_lock_profiles",
        unproven_per_control_rejection_groups_at_least=17)
    gate["current_dependency_qualification"] = record
    gate["current_ownership_qualification"] = dict(gate["current_ownership_qualification"], cycle=219,
        scope="retained_host_core216_and_fresh_bounded_VM_IPI219", fresh_current_cycle_qemu_runs=4,
        live_replay_cycle=219, live_receipt_scope="two_VM219_and_two_IPI219_runs",
        live_receipt_source_current=True, active_root_current_image_replay_complete=True,
        virtual_memory_live_receipt_source_current=True, ap_runtime_live_integration_verified=True,
        virtual_memory_live_replay_cycle=219, virtual_memory_receipt_sha256=bindings[1]["sha256"],
        smp_receipt_sha256=bindings[5]["sha256"], source_current_scope="host_core216_boot_CPU218_bounded_VM_IPI219",
        live_boot_dependency_replay_cycle=219, historical_record="historical_cycle218_ownership_qualification")
    projection = copy.deepcopy(gate["historical_cycle212_source_projection"])
    projection.update(cycle=219, run_count_scope="Cycle219_six_memory_IRQ_SMP_profiles_not_retained_CPU_or_boot_runs")
    gate["current_focused_source_projection"] = projection
    gate["current_entry_provenance_qualification"] = dict(gate["current_entry_provenance_qualification"], latest_reproduction_cycle=219)
    gate["current_ipi_mailbox_oracle_gap"] = dict(gate["current_ipi_mailbox_oracle_gap"], cycle=219,
        remaining_affected_profiles=8, newly_requalified_profiles=record["qualified_profiles"], current_kernel_live_replay_pending=False)
    gate["current_control_execution_audit"] = dict(gate["current_control_execution_audit"], cycle=219)
    gate["current_closeout_regression"] = {
        "cycle": 219, "status": "pass", "scope": "six_memory_IRQ_SMP_profiles_and_memory_IPI_gates_not_full_canonical",
        "tests_run": 93, "tests_passed": 93, "tests_failed": 0, "tests_skipped": 0,
        "elapsed_seconds": 128.027, "runner_elapsed_seconds": 128.938,
        "log_sha256": "7A091F71778BBA375CFAD1A91BBAB6B5E0CD91707CC179861CABA84AF2C57B3B",
        "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        "initial_admission_failures": [
            {"profile": "physical_memory", "detail": "PKPMM7 readiness summary changed", "reconciled_pins": 3},
            {"profile": "virtual_memory", "detail": "PKVM3 readiness summary changed", "reconciled_pins": 6},
            {"profile": "smp_ipi", "detail": "PKSMP5 embedded kernel identity changed", "reconciled_pins": 1},
        ],
        "same_candidates_admitted_after_independent_measurement": True,
        "failed_guest_runs": 0, "guest_evidence_rewritten_or_rerun_for_pin_repair": False,
        "initial_metadata_regression": {
            "tests_run": 66, "tests_passed": 56, "tests_failed": 10, "tests_skipped": 0,
            "elapsed_seconds": 20.634, "runner_elapsed_seconds": 21.437,
            "log_sha256": "8F1A8A735362A3E3EA29267E40C93F97846FC41C102A2B98E0DC3095B98F7D23",
            "cause": "stale_current_memory_IRQ_AP_IPI_receipt_expectations_in_historical_record_tests",
        },
        "corrected_metadata_regression": {
            "tests_run": 66, "tests_passed": 66, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 35.696, "runner_elapsed_seconds": 36.547,
            "log_sha256": "516AD3E9D45AE2E72D340599688D0AD5FEED00045BF2A2BF8D3C5B4CBE6CCD4E",
            "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        },
        "initial_conservation": {
            "status": "pass", "archived_records": 25, "architecture_bindings": 372,
            "test_inventory": 1136, "all_phase_and_flag_statuses_preserved": True,
            "receipt_sha256": "20BB99F6DF1D35088999880383FE290B28934348428ADF0A6C79766DE430D697",
        },
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 219: " + checkpoint + " qualifies six memory/IRQ/SMP profiles on unchanged kernel216. "
        "Twelve virtual boots, 421 control groups covering 1137 cases and 93 focused tests pass, including "
        "1896 corrupted receipts, 360 raw-mailbox cases, nine isolated IPI identity cases and 29 memory "
        "summary cases. Three PMM, six VM and one IPI obsolete pins are reconciled after independent "
        "current-image validation. Initial failed admissions remain recorded; identical candidates then pass."
    )
    gap = (
        "Readiness is 19/27; eight scheduler/atomic/lock profiles remain from N12-SCHED-001, plus "
        "seventeen SMP-preemption control groups and recorded admission. Shared-helper transitive-binding "
        "review remains within N36. No phase, flag, native byte, ISO or production status changes. "
        "Full exact-candidate canonical/Doctor/release/publication and configured GitHub/review gates "
        "precede main merge; cloud branch backup is separate. N0 custody, N5 authentication, general "
        "retirement, independent builders and physical hardware remain open."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N8", "N9", "N10", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 219 source inventory: 1136 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N9-PMM-ACPI-CONSUMER-001", "FLAG-N9-VM-DIRECT-MAP-001",
                          "FLAG-N8-IRQ-001", "FLAG-N8-SMP-IPI-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle220(roadmap, test_count)


def apply_cycle220(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle220-current-kernel-scheduler-replay.md"
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for key, value in list(gate.items()):
        if key.startswith("current_") and isinstance(value, dict):
            suffix = "source_projection" if key == "current_focused_source_projection" else key.removeprefix("current_")
            gate["historical_cycle219_" + suffix] = copy.deepcopy(value)
    roadmap["baseline"]["pooleos_cycle"] = 220
    roadmap["execution_protocol"].update(last_updated_cycle=220, selected_move_id="N12-SCHED-001",
        owner_independent_next_move_id="N12-SCHED-SMP-001")
    roadmap["execution_protocol"]["required_records"].insert(0, checkpoint)
    gate["qualification_status"] = "current_kernel_scheduler_admitted_five_dependencies_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=220)
    record = copy.deepcopy(gate["historical_cycle213_dependency_qualification"])
    record["receipt_bindings"][:6] = copy.deepcopy(gate["historical_cycle219_dependency_qualification"]["receipt_bindings"])
    rows = (
        ("scheduler", "887A1EC3277DF219F990CF51FFEC4B394C358C08EA012C907B3713A92D5240DD",
         "B9D6770526A3B9FC67708492C692995ADBBB35F18916E6E3303D37263BA66A1F", 90.765),
        ("scheduler_preempt", "60C1F4D6A5BCAF5FCB46BF7AEDAE8C838F93F6030ADE23F276AA89064E33B7BB",
         "C4CA732801FB906F7442652BE154022EA0C59C4E633C31145D785E2F4E5A52F5", 99.172),
        ("scheduler_deferred", "3F878D6690A507D4782E863840B811FB38E26F9726F30926CAF545DA2CF922CC",
         "E12A45434566B849DD8DC27938DC5EE50E8BFA45D9F58DD3867479C1C06D291E", 85.688),
    )
    for binding, (profile, digest, log, seconds) in zip(record["receipt_bindings"][6:], rows, strict=True):
        assert binding["profile"] == profile
        binding.update(sha256=digest, execution_log_sha256=log, elapsed_seconds=seconds)
    record.update(cycle=220, source_validation_cycle=220,
        scope="retained_six_memory219_and_three_fresh_scheduler220_profiles_on_unchanged_kernel216",
        run_count_scope="Cycle220_three_scheduler_profiles_only_not_retained_memory_CPU_boot_runs",
        kernel_sha256=gate["current_entry_provenance_qualification"]["canonical_sha256"],
        independent_deferred_linked_identity_cases=16,
        embedded_entry_provenance_pending_scope="five_remaining_SMP_atomic_lock_profiles",
        unproven_per_control_rejection_groups_at_least=17)
    gate["current_dependency_qualification"] = record
    projection = copy.deepcopy(gate["historical_cycle213_source_projection"])
    projection.update(cycle=220, run_count_scope="Cycle220_three_scheduler_profiles_only",
        required_next_gate="current_SMP_AP_worker_replay_then_SMP_preemption_controls_admission_atomics_locks_and_full_candidate")
    gate["current_focused_source_projection"] = projection
    gate["current_entry_provenance_qualification"] = dict(gate["current_entry_provenance_qualification"], latest_reproduction_cycle=220)
    gate["current_ipi_mailbox_oracle_gap"] = dict(gate["current_ipi_mailbox_oracle_gap"], cycle=220,
        remaining_affected_profiles=5, newly_requalified_profiles=record["newly_qualified_profiles"])
    gate["current_control_execution_audit"] = dict(gate["current_control_execution_audit"], cycle=220)
    for key, binding in (("current_preemption_control_execution_audit", record["receipt_bindings"][-2]),
                         ("current_deferred_control_qualification", record["receipt_bindings"][-1])):
        gate[key] = dict(gate[key], cycle=220, source_validation_cycle=220,
            receipt_sha256=binding["sha256"], current_kernel_live_replay_pending=False,
            current_receipt_admitted=True, applies_to_current_source=True,
            aggregate_unproven_groups_at_least=17,
            historical_record="historical_cycle219_" + key.removeprefix("current_"))
    gate["current_deferred_transaction_qualification"] = dict(gate["current_deferred_transaction_qualification"],
        current_kernel_live_replay_pending=False, current_receipt_admitted=True,
        latest_live_replay_cycle=220, latest_live_receipt_sha256=rows[-1][1],
        latest_live_kernel_sha256=record["kernel_sha256"],
        historical_record="historical_cycle219_deferred_transaction_qualification")
    gate["current_closeout_regression"] = {
        "cycle": 220, "status": "pass", "scope": "three_scheduler_profiles_and_deferred_identity_gate_not_full_canonical",
        "tests_run": 47, "tests_passed": 47, "tests_failed": 0, "tests_skipped": 0,
        "elapsed_seconds": 60.880, "runner_elapsed_seconds": 61.781,
        "log_sha256": "D7AA57E9B99806B55F5DC8A56990B0439193ED63183D318BB230678A8287B1C3",
        "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        "initial_deferred_admission": {
            "status": "fail", "detail": "PKSCHED3 host oracle, source, or linked switch audit changed",
            "candidate_sha256": rows[-1][1], "failed_guest_runs": 0,
            "guest_evidence_rewritten_or_rerun": False,
        },
        "corrected_deferred_admission": {
            "status": "pass", "same_candidate_sha256": rows[-1][1],
            "independently_measured_relocation_count": 1326,
            "independently_measured_kernel_sha256": record["kernel_sha256"],
            "schema_or_component_validation_bypassed": False,
        },
        "metadata_regression": {
            "tests_run": 67, "tests_passed": 67, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 36.581, "runner_elapsed_seconds": 37.438,
            "log_sha256": "53316225DF772B62D07BB6388CD029BBDDD084340C8097595CC3EC78B597509C",
            "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        },
        "initial_conservation": {
            "status": "pass", "archived_records": 25, "architecture_bindings": 373,
            "test_inventory": 1137, "all_phase_and_flag_statuses_preserved": True,
            "receipt_sha256": "4EDAF9A3FB8D847F25C2165ED9BF565C1A77DD6D625DF0321BDCBBCD66A89038",
        },
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 220: " + checkpoint + " qualifies scheduler, BSP preemption and deferred work on unchanged kernel216. "
        "Six virtual boots, 83 control groups/595 cases and 47 focused tests pass, including 768 corrupt records, "
        "16 independent deferred identity cases and 19 disabled native safeguards. Two measured deferred image "
        "pins replace obsolete expectations; the initial failed admission is retained and the identical candidate passes."
    )
    gap = (
        "Readiness is 22/27; five SMP scheduler/AP-worker/preemption/atomic/lock profiles remain from N12-SCHED-SMP-001, "
        "plus seventeen SMP-preemption control groups and recorded admission. Shared-helper transitive bindings "
        "remain N36. No phase, flag, native byte, ISO or production change. Full exact-candidate canonical/Doctor/"
        "release/publication and configured GitHub/review gates precede main merge; cloud branch backup is separate. "
        "N0 custody, N5 authentication, general retirement, independent builders and physical hardware remain open."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N12", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 220 source inventory: 1137 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N12-SCHED-FOUNDATION-001", "FLAG-N12-SCHED-PREEMPT-001",
                          "FLAG-N12-SCHED-DEFERRED-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle221(roadmap, test_count)


def apply_cycle221(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle221-current-kernel-smp-and-ap-worker-replay.md"
    next_move = "N12-SCHED-SMP-PREEMPT-001"
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for key, value in list(gate.items()):
        if key.startswith("current_") and isinstance(value, dict):
            suffix = "source_projection" if key == "current_focused_source_projection" else key.removeprefix("current_")
            gate["historical_cycle220_" + suffix] = copy.deepcopy(value)
    roadmap["baseline"]["pooleos_cycle"] = 221
    roadmap["execution_protocol"].update(last_updated_cycle=221, selected_move_id="N12-SCHED-SMP-001",
        owner_independent_next_move_id=next_move)
    roadmap["execution_protocol"]["required_records"].insert(0, checkpoint)
    gate["qualification_status"] = "current_kernel_SMP_and_AP_workers_admitted_three_dependencies_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=221)
    previous = gate["historical_cycle220_dependency_qualification"]
    rows = (
        ("scheduler_smp", "runs/native-kernel-scheduler-smp-readiness.json",
         "EF7E7BA350D5B0853F4528C61CD2DA9436FA800AA194B1C2AA933D5188CF5D4E", 32, 303, 279,
         "B4AFCEDC4E0B5203EA8C7434E85C6ABD1BFF4D8CFEFFE76250C1A9A84BB46958", 107.281),
        ("scheduler_ap_workers", "runs/native-kernel-scheduler-ap-workers-readiness.json",
         "BF96F20CEF9D51E75E836B9780A902EF90D8C39D64CC7C881E0694E3884E1A16", 34, 325, 294,
         "B06620B801239E6381B91722D9B146A38F8E0EDC3B2CA346918A635BF2F030DA", 87.078),
    )
    bindings = [dict(profile=p, path=path, sha256=digest, fresh_runs=2, negative_controls=groups,
        hostile_cases=cases, kernel_host_tests=246, recorded_evidence_cases=corruptions,
        execution_log_sha256=log, elapsed_seconds=seconds)
        for p, path, digest, groups, cases, corruptions, log, seconds in rows]
    record = {
        "cycle": 221, "source_validation_cycle": 221, "status": "eleven_current_profiles_three_pending",
        "scope": "retained_memory219_scheduler220_and_fresh_SMP_AP_workers221_on_unchanged_kernel216",
        "applies_to_current_source": True, "all_fourteen_profiles_current": False,
        "qualified_profiles": previous["qualified_profiles"] + [b["profile"] for b in bindings],
        "newly_qualified_profiles": [b["profile"] for b in bindings],
        "readiness_replay_required_profiles": ["scheduler_smp_preempt", "atomics", "locks"],
        "embedded_entry_provenance_replay_pending": True,
        "embedded_entry_provenance_pending_scope": "three_remaining_SMP_preemption_atomic_lock_profiles",
        "fresh_qemu_runs": 4, "superseded_initial_runs": 0, "failed_guest_runs": 0,
        "run_count_scope": "Cycle221_four_fresh_SMP_AP_worker_boots_only_not_retained_runs",
        "negative_control_groups": 66, "negative_control_cases": 628,
        "executed_rejection_cases": 510, "native_boundary_cases": 118,
        "kernel_sha256": previous["kernel_sha256"],
        "receipt_bindings": copy.deepcopy(previous["receipt_bindings"]) + bindings,
        "kernel_host_tests_per_qualifier": 246, "focused_python_tests": 39,
        "generic_recorded_evidence_cases": 573, "additional_control_profile_receipt_cases": 96,
        "recorded_evidence_case_total": 669, "recorded_evidence_scope": "two_fresh_SMP_AP_worker_profiles",
        "recorded_evidence_rejections_exercised_through_runtime_and_gate": True,
        "independent_aggregate_cases": 30, "independent_current_image_pin_cases": 12,
        "disabled_native_safeguard_variants_detected": 27, "disabled_transaction_variants_detected": 24,
        "positive_receipts_rebound_in_tests": False, "pair_validation_is_freshness_or_authentication": False,
        "canonical_kernel_changed_this_cycle": False, "control_execution_complete": False,
        "unproven_per_control_rejection_groups_at_least": 17,
        "current_candidate_full_gate_passed": False, "production_ready": False,
    }
    gate["current_dependency_qualification"] = record
    projection = gate["current_focused_source_projection"]
    gate["current_focused_source_projection"] = dict(projection, cycle=221, passed_checks=24,
        pending_downstream_native_checks=3,
        passing_profiles=projection["passing_profiles"] + ["native_kernel_" + b["profile"] + "_readiness" for b in bindings],
        final_receipt_fresh_qemu_runs=4, kernel_entry_runs=4, superseded_initial_qemu_runs=0,
        run_count_scope="Cycle221_four_fresh_SMP_AP_worker_boots_only", next_dependency_move_id=next_move,
        required_next_gate="SMP_preemption_admission_and_17_controls_atomics_locks_then_full_candidate",
        focused_python_tests_passed=39, recorded_evidence_rejection_cases=669)
    gate["current_entry_provenance_qualification"] = dict(gate["current_entry_provenance_qualification"], latest_reproduction_cycle=221)
    gate["current_ipi_mailbox_oracle_gap"] = dict(gate["current_ipi_mailbox_oracle_gap"], cycle=221,
        remaining_affected_profiles=3, newly_requalified_profiles=record["newly_qualified_profiles"])
    gate["current_control_execution_audit"] = dict(gate["current_control_execution_audit"], cycle=221)
    for name, binding in zip(("smp", "ap_worker"), bindings, strict=True):
        key = "current_" + name + "_control_qualification"
        gate[key] = dict(gate[key], cycle=221, source_validation_cycle=221,
            applies_to_current_source=True, receipt_sha256=binding["sha256"],
            current_receipt_admitted=True, current_kernel_live_replay_pending=False,
            measured_canonical_sha256=record["kernel_sha256"], measured_relocation_count=1326,
            historical_record="historical_cycle220_" + name + "_control_qualification",
            original_failure_audits_reexecuted_this_cycle=False,
            latest_replay_scope="Cycle221_live_replay_and_regression_original_failures_preserved_as_history")
        if name == "ap_worker":
            gate[key]["kernel_sha256"] = record["kernel_sha256"]
        key = "current_" + name + "_transaction_qualification"
        gate[key] = dict(gate[key], current_receipt_admitted=True, current_kernel_live_replay_pending=False,
            latest_live_replay_cycle=221, latest_live_receipt_sha256=binding["sha256"],
            latest_live_kernel_sha256=record["kernel_sha256"], historical_artifact_identity_retained=True,
            historical_record="historical_cycle220_" + name + "_transaction_qualification")
    gate["current_closeout_regression"] = {
        "cycle": 221, "status": "pass", "scope": "SMP_AP_worker_controls_transactions_and_identity_gates_not_full_canonical",
        "tests_run": 39, "tests_passed": 39, "tests_failed": 0, "tests_skipped": 0,
        "elapsed_seconds": 81.264, "runner_elapsed_seconds": 82.172,
        "log_sha256": "05D2FC34B99F390064E6EBD07EFA3A7621F9E9FD334B01B8516B819413E9F8B6",
        "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        "initial_metadata_regression": {
            "tests_run": 68, "tests_passed": 63, "tests_failed": 5, "tests_skipped": 0,
            "elapsed_seconds": 36.058, "runner_elapsed_seconds": 36.875,
            "log_sha256": "9BE00A685CE89F4FE7E0392685C7CF8D118A67655AF0F9046660A35027ACE9AB",
            "cause": "stale_current_profile_count_next_move_and_embedded_entry_assertions",
            "source_unchanged_during_execution": True, "owner_report_unchanged": True,
            "admitted_as_pass": False,
        },
        "second_metadata_regression": {
            "tests_run": 68, "tests_passed": 67, "tests_failed": 1, "tests_skipped": 0,
            "elapsed_seconds": 36.708, "runner_elapsed_seconds": 37.516,
            "log_sha256": "6AFA635A478E15677B455DEF1AED12EB2313BA3A821099AE4A4EDBB31B4D7A36",
            "cause": "remaining_stale_current_readiness_total_after_prior_assertion_repair",
            "source_unchanged_during_execution": True, "owner_report_unchanged": True,
            "admitted_as_pass": False,
        },
        "corrected_metadata_regression": {
            "tests_run": 68, "tests_passed": 68, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 36.638, "runner_elapsed_seconds": 37.422,
            "log_sha256": "E7A4E0912CB45535AC6B98BA6672896F7B9277AEDC25008337FC09D710AA67BF",
            "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        },
        "initial_admission_failures": [dict(profile=b["profile"], candidate_sha256=b["sha256"],
            status="fail", detail=contract + " host oracle, source, or linked INVLPG audit changed",
            measured_relocation_count=1326, reconciled_pins=2, same_candidate_admitted_after_repair=True)
            for b, contract in zip(bindings, ("PKSCHED4", "PKSCHED5"), strict=True)],
        "failed_guest_runs": 0, "guest_evidence_rewritten_or_rerun_for_pin_repair": False,
        "schema_or_component_validation_bypassed": False,
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 221: " + checkpoint + " qualifies SMP scheduling and AP workers on unchanged kernel216. "
        "Four four-vCPU boots, 66 control groups/628 cases and 39 focused tests pass, including 669 corrupt "
        "records, 30 independent aggregate cases and 51 disabled native variants. Four measured aggregate "
        "image pins replace obsolete expectations; both initial rejected admissions and identical candidates are retained."
    )
    gap = (
        "Readiness is 24/27. SMP preemption, atomics and locks remain from " + next_move + ", plus seventeen "
        "SMP-preemption control groups and recorded admission. N36 shared-helper transitive bindings stay open. "
        "No native byte, phase, flag, ISO or production change. Full exact-candidate canonical/Doctor/release/"
        "publication and configured GitHub/review gates precede main merge; branch backup is separate. "
        "N0 custody, N5 authentication, full task state, general retirement, hardware and independent builders remain open."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N12", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 221 source inventory: 1139 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N12-SCHED-SMP-001", "FLAG-N12-SCHED-AP-WORKERS-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle222(roadmap, test_count)


def apply_cycle222(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle222-smp-preemption-admission-and-controls.md"
    next_move = "N12-CONCURRENCY-ATOMICS-001"
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for key, value in list(gate.items()):
        if key.startswith("current_") and isinstance(value, dict):
            suffix = "source_projection" if key == "current_focused_source_projection" else key.removeprefix("current_")
            gate["historical_cycle221_" + suffix] = copy.deepcopy(value)
    roadmap["baseline"]["pooleos_cycle"] = 222
    roadmap["execution_protocol"].update(last_updated_cycle=222,
        selected_move_id="N12-SCHED-SMP-PREEMPT-001", owner_independent_next_move_id=next_move)
    roadmap["execution_protocol"]["required_records"].insert(0, checkpoint)
    gate["qualification_status"] = "SMP_preemption_admission_and_controls_repaired_two_dependencies_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=222)
    digest = "6BA9A37CF1C6E067085858399302364376B07F5918D12D88439EB3E060E6E4D3"
    binding = dict(profile="scheduler_smp_preempt", path="runs/native-kernel-scheduler-smp-preempt-readiness.json",
        sha256=digest, fresh_runs=2, negative_controls=34, hostile_cases=322, kernel_host_tests=246,
        execution_log_sha256="32DC2A4F71B6B64BD879B86B7BF320B6707E712CE2B501643C06AF9AFB08F0EA",
        elapsed_seconds=182.562, recorded_evidence_cases=288)
    previous = gate["historical_cycle221_dependency_qualification"]
    record = copy.deepcopy(previous)
    record.update(cycle=222, source_validation_cycle=222, status="twelve_current_profiles_two_pending",
        scope="retained_memory219_scheduler220_SMP_workers221_and_fresh_SMP_preempt222_on_kernel216",
        qualified_profiles=previous["qualified_profiles"] + ["scheduler_smp_preempt"],
        newly_qualified_profiles=["scheduler_smp_preempt"], readiness_replay_required_profiles=["atomics", "locks"],
        receipt_bindings=copy.deepcopy(previous["receipt_bindings"]) + [binding],
        embedded_entry_provenance_pending_scope="two_remaining_atomic_lock_profiles",
        fresh_qemu_runs=2, superseded_initial_runs=6, failed_guest_runs=0,
        run_count_scope="Cycle222_two_final_boots_only_two_diagnostic_and_four_superseded_boots_excluded",
        negative_control_groups=34, negative_control_cases=322, executed_rejection_cases=261,
        native_boundary_cases=61, focused_python_tests=19, generic_recorded_evidence_cases=288,
        additional_control_profile_receipt_cases=51, recorded_evidence_case_total=339,
        recorded_evidence_scope="fresh_SMP_preemption_profile", independent_aggregate_cases=11,
        independent_current_image_pin_cases=5, disabled_native_safeguard_variants_detected=15,
        disabled_transaction_variants_detected=14, unproven_per_control_rejection_groups_at_least=0)
    gate["current_dependency_qualification"] = record
    projection = gate["current_focused_source_projection"]
    gate["current_focused_source_projection"] = dict(projection, cycle=222, passed_checks=25,
        pending_downstream_native_checks=2,
        passing_profiles=projection["passing_profiles"] + ["native_kernel_scheduler_smp_preempt_readiness"],
        final_receipt_fresh_qemu_runs=2, kernel_entry_runs=2, superseded_initial_qemu_runs=6,
        run_count_scope=record["run_count_scope"], next_dependency_move_id=next_move,
        required_next_gate="atomics_locks_shared_helper_binding_review_then_full_exact_candidate",
        focused_python_tests_passed=19, recorded_evidence_rejection_cases=339)
    gate["current_entry_provenance_qualification"] = dict(gate["current_entry_provenance_qualification"], latest_reproduction_cycle=222)
    gate["current_ipi_mailbox_oracle_gap"] = dict(gate["current_ipi_mailbox_oracle_gap"], cycle=222,
        remaining_affected_profiles=2, newly_requalified_profiles=["scheduler_smp_preempt"])
    gate["current_control_execution_audit"] = dict(gate["current_control_execution_audit"], cycle=222,
        scope="known_constant_only_scheduler_groups_repaired_broader_N36_review_open",
        unproven_per_control_rejection_groups_at_least=0, next_profile="atomics",
        SMP_preemption_groups_repaired=17, source_control_gaps=[])
    gate["current_smp_preempt_control_qualification"] = {
        "cycle": 222, "source_validation_cycle": 222, "move_id": "N12-SCHED-SMP-PREEMPT-001",
        "status": "pass", "applies_to_current_source": True, "current_receipt_admitted": True,
        "current_kernel_live_replay_pending": False, "receipt_sha256": digest,
        "kernel_sha256": record["kernel_sha256"], "measured_relocation_count": 1326,
        "constant_only_groups_replaced": 17, "native_groups": 15, "native_cases": 61,
        "source_groups": 2, "source_rejections": 46, "generic_record_cases": 288,
        "additional_record_cases": 51, "independent_gate_cases": 11,
        "disabled_native_variants_detected": 15, "disabled_transaction_variants_detected": 14,
        "diagnostic_baseline": {
            "receipt_sha256": "5DEFF9E6E8E9DDB28B9970E9359260EAAB5D73875FC33FE03A997D9F1391A273",
            "boots": 2, "elapsed_seconds": 83.375,
            "log_sha256": "5A56B9FF83DB43A371DE1BE3FA26672B7FE0C31E1D20FE8E0B73A4E56A15BF21",
            "runtime_accepted": True, "aggregate_gate_accepted": False,
            "mutation_cases": 288, "runtime_corruptions_accepted": 273,
            "runtime_corruptions_rejected": 11, "runtime_exceptions": 4, "admitted_as_final": False,
        },
        "after_audit": {"genuine_runtime_accepted": True, "genuine_gate_accepted": True,
            "generic_case_count": 288, "additional_case_count": 51,
            "runtime_corruptions_accepted": 0, "gate_corruptions_accepted": 0,
            "runtime_exceptions": 0, "gate_exceptions": 0},
        "pair_validation_is_freshness_or_authentication": False,
        "positive_receipt_rebound_in_tests": False, "native_kernel_changed": False,
        "full_hardware_fault_injection": False, "production_ready": False,
    }
    gate["current_smp_preempt_transaction_qualification"] = dict(gate["current_smp_preempt_transaction_qualification"],
        status="native_transactions_retained_current_live_profile_and_admission_verified",
        latest_live_replay_cycle=222, latest_live_receipt_sha256=digest,
        current_kernel_live_replay_pending=False, current_receipt_admitted=True,
        recorded_evidence_admission_repaired=True, constant_only_control_groups_replaced=17,
        remaining_global_control_groups_at_least=0, historical_record="historical_cycle221_smp_preempt_transaction_qualification")
    gate["current_closeout_regression"] = {
        "cycle": 222, "status": "pass", "scope": "SMP_preemption_controls_transactions_and_admission_not_full_canonical",
        "tests_run": 19, "tests_passed": 19, "tests_failed": 0, "tests_skipped": 0,
        "elapsed_seconds": 48.173, "runner_elapsed_seconds": 49.094,
        "log_sha256": "02FD21CDA360173C162EAFDD2170A9A7BC626A593919F0ABC04655FE5CC56723",
        "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        "initial_native_controls": {"tests_run": 5, "tests_failed": 1,
            "log_sha256": "73A5E6FC6BF3D4B07844D46D82C6702B0060947917F5357E1D80842E6D6F5A17",
            "cause": "redundant_watchdog_guard_masked_the_selected_disabled_guard", "admitted_as_pass": False},
        "initial_focused": {"tests_run": 19, "tests_passed": 18, "tests_skipped": 1,
            "log_sha256": "68D5F65E7B557A92DCDC383893B90C422D023A29A264DACFC9C34F669E82A084",
            "cause": "optional_temporary_transcript_missing_replaced_with_retained_two_run_test", "admitted_as_pass": False},
        "initial_metadata": {"tests_run": 69, "failure_records": 17, "tests_skipped": 0,
            "log_sha256": "4D209E8E02E6C2A16B4C9727BBBC47B8A6B57A501637DE3423D58D9331277920",
            "cause": "stale_current_progress_assertions_and_cycle_schema", "admitted_as_pass": False},
        "second_metadata": {"tests_run": 69, "tests_passed": 67, "tests_failed": 2, "tests_skipped": 0,
            "log_sha256": "CD5C09A733464EEF374BAC32507ECB152E5FEEE666C44E352BE747030FD901CA",
            "cause": "two_remaining_current_profile_assertions", "admitted_as_pass": False},
        "metadata_regression": {"tests_run": 69, "tests_passed": 69, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 36.550, "runner_elapsed_seconds": 37.359,
            "log_sha256": "3BFFDFB4AA86B875CC9F675F58B97967D69B439B6D58FEDFDA7821E00A395486",
            "source_unchanged_during_execution": True, "owner_report_unchanged": True},
        "initial_conservation_failure": {
            "cause": "regeneration_substituted_current_test_inventory_into_Cycle221_historical_evidence",
            "repair": "freeze_Cycle221_inventory_at_1139", "admitted_as_pass": False},
        "combined_regression": {"tests_run": 167, "tests_passed": 167, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 241.386, "runner_elapsed_seconds": 242.375,
            "log_sha256": "6696145C03D306EDC61DA3AE3E622CE53BB7481F6A218384971D74661F116751",
            "scope": "preemption_SMP_AP_workers_IPI_capture_and_metadata_not_full_canonical",
            "source_unchanged_during_execution": True, "owner_report_unchanged": True,
            "counts_overlap_focused_and_metadata": True},
        "conservation": {"status": "pass", "architecture_bindings": 377, "test_inventory": 1149,
            "unchanged_parent_current_records_archived": 25, "selected_checks": "25/27",
            "phase_flag_and_normative_charter_preserved": True, "native_and_demo_bytes_preserved": True},
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 222: " + checkpoint + " replaces seventeen constant-only SMP-preemption groups and repairs "
        "recorded admission on unchanged kernel216. Two final four-vCPU boots pass 34 groups/322 cases; "
        "19 focused tests pass, rejecting 339 corrupt records and 11 independent gate cases and detecting "
        "29 disabled native variants. Diagnostic 273 invalid admissions/four exceptions, a masked watchdog "
        "mutation, an optional transcript skip and six non-final boots remain separate historical evidence."
    )
    gap = (
        "Readiness is 25/27. Next " + next_move + ", then locks, shared-helper transitive binding review and "
        "full exact-candidate canonical/Doctor/release/publication/GitHub/review gates before main merge. "
        "Known seventeen control groups are repaired; broader N36 verification remains open. No native "
        "byte, phase, flag, ISO or production change. N0 custody, N5 authentication, full architectural "
        "task state, general retirement, hardware and independent builders remain open."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N12", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 222 source inventory: 1149 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N12-SCHED-SMP-PREEMPT-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle223(roadmap, test_count)


def apply_cycle223(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle223-atomics-admission-and-instruction-audit.md"
    next_move = "N12-CONCURRENCY-LOCKS-001"
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for key, value in list(gate.items()):
        if key.startswith("current_") and isinstance(value, dict):
            suffix = "source_projection" if key == "current_focused_source_projection" else key.removeprefix("current_")
            gate["historical_cycle222_" + suffix] = copy.deepcopy(value)
    roadmap["baseline"]["pooleos_cycle"] = 223
    roadmap["execution_protocol"].update(last_updated_cycle=223,
        selected_move_id="N12-CONCURRENCY-ATOMICS-001", owner_independent_next_move_id=next_move)
    roadmap["execution_protocol"]["required_records"].insert(0, checkpoint)
    gate["qualification_status"] = "atomics_admission_and_instruction_audit_repaired_locks_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=223)
    digest = "1E684D59C800F1C08BD05C1BEAB940654FD1CC8550779217FFE5AA4162DAB3CC"
    binding = dict(profile="atomics", path="runs/native-kernel-atomics-readiness.json", sha256=digest,
        fresh_runs=2, negative_controls=29, hostile_cases=78, kernel_host_tests=246,
        execution_log_sha256="0BF036FC79C939C9EB6CDB0C580AB2D279EE05C4D7B64A29D07B34995FCC76BD",
        elapsed_seconds=93.828, recorded_evidence_cases=356)
    previous = gate["historical_cycle222_dependency_qualification"]
    record = copy.deepcopy(previous)
    record.update(cycle=223, source_validation_cycle=223, status="thirteen_current_profiles_locks_pending",
        scope="retained_twelve_profiles_and_fresh_atomics223_on_unchanged_kernel216",
        qualified_profiles=previous["qualified_profiles"] + ["atomics"], newly_qualified_profiles=["atomics"],
        readiness_replay_required_profiles=["locks"],
        receipt_bindings=copy.deepcopy(previous["receipt_bindings"]) + [binding],
        embedded_entry_provenance_pending_scope="remaining_lock_profile",
        fresh_qemu_runs=2, superseded_initial_runs=6, failed_guest_runs=0,
        run_count_scope="Cycle223_two_final_boots_only_two_diagnostic_and_four_superseded_boots_excluded",
        negative_control_groups=29, negative_control_cases=78, executed_rejection_cases=78,
        native_boundary_cases=0, focused_python_tests=22, generic_recorded_evidence_cases=356,
        additional_control_profile_receipt_cases=0, recorded_evidence_case_total=356,
        recorded_evidence_scope="fresh_atomics_profile_plus_separate_instruction_mutants",
        independent_aggregate_cases=8, independent_current_image_pin_cases=8,
        disabled_native_safeguard_variants_detected=8, disabled_transaction_variants_detected=0)
    gate["current_dependency_qualification"] = record
    projection = gate["current_focused_source_projection"]
    gate["current_focused_source_projection"] = dict(projection, cycle=223, passed_checks=26,
        pending_downstream_native_checks=1,
        passing_profiles=projection["passing_profiles"] + ["native_kernel_atomics_readiness"],
        final_receipt_fresh_qemu_runs=2, kernel_entry_runs=2, superseded_initial_qemu_runs=6,
        run_count_scope=record["run_count_scope"], next_dependency_move_id=next_move,
        required_next_gate="locks_shared_helper_binding_review_then_full_exact_candidate",
        focused_python_tests_passed=22, recorded_evidence_rejection_cases=356)
    gate["current_entry_provenance_qualification"] = dict(gate["current_entry_provenance_qualification"], latest_reproduction_cycle=223)
    gate["current_ipi_mailbox_oracle_gap"] = dict(gate["current_ipi_mailbox_oracle_gap"], cycle=223,
        remaining_affected_profiles=1, newly_requalified_profiles=["atomics"])
    gate["current_control_execution_audit"] = dict(gate["current_control_execution_audit"], cycle=223, next_profile="locks")
    gate["current_atomics_admission_qualification"] = {
        "cycle": 223, "source_validation_cycle": 223, "move_id": "N12-CONCURRENCY-ATOMICS-001",
        "status": "pass", "applies_to_current_source": True, "current_receipt_admitted": True,
        "receipt_sha256": digest, "kernel_sha256": record["kernel_sha256"],
        "recorded_corruption_cases": 356, "independent_gate_cases": 8,
        "rehashed_instruction_receipt_cases": 7, "comment_only_symbol_cases": 7,
        "opcode_operand_branch_instruction_cases": 7, "disabled_auditor_variants": 2,
        "disabled_native_guard_variants": 8, "native_guard_optimization_levels": [0, 3],
        "native_guard_mutant_executions": 16, "native_unit_tests_per_baseline": 7,
        "direct_loader_and_transfer_sources_bound": True,
        "diagnostic_baseline": {
            "receipt_sha256": "61AC116FD675948E45F9BCE626F338B5B03C3496A146608A114FE15511FC568F",
            "runtime_accepted": True, "aggregate_gate_accepted": True, "mutation_cases": 277,
            "runtime_corruptions_accepted": 168, "gate_corruptions_accepted": 91,
            "runtime_exceptions": 4, "gate_exceptions": 19, "comment_only_assembly_accepted": True,
            "admitted_as_final": False,
        },
        "after_audit": {"genuine_runtime_accepted": True, "genuine_gate_accepted": True,
            "runtime_corruptions_accepted": 0, "gate_corruptions_accepted": 0,
            "runtime_exceptions": 0, "gate_exceptions": 0},
        "pair_validation_is_freshness_or_authentication": False, "positive_receipt_rebound_in_tests": False,
        "native_kernel_changed": False, "live_AP_litmus_verified": False, "production_ready": False,
    }
    gate["current_closeout_regression"] = {
        "cycle": 223, "status": "pass", "scope": "atomics_admission_instructions_and_native_guards_not_full_canonical",
        "tests_run": 22, "tests_passed": 22, "tests_failed": 0, "tests_skipped": 0,
        "elapsed_seconds": 26.831, "runner_elapsed_seconds": 27.703,
        "log_sha256": "8097A531343C60DA999DC5708F91F2C42F44BA26BDB763E41102922C2A52544C",
        "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        "initial_admission": {"status": "fail", "case_count": 356, "invalid_mutation_cases": 1,
            "cause": "test_replaced_null_selected_default_feature_with_identical_null",
            "unchanged_valid_receipt_correctly_accepted": True, "admitted_as_pass": False,
            "repair": "use_a_distinct_invalid_value_then_fresh_qualification_no_receipt_rebinding"},
        "initial_metadata": {"tests_run": 70, "tests_passed": 69, "tests_failed": 1, "tests_skipped": 0,
            "log_sha256": "4E79A2DF7D88E2962630ACD07EE1A7A861F8783F619DD359C0AA922334125FF2",
            "cause": "obsolete_two_pending_profiles_assertion_after_atomics_admission", "admitted_as_pass": False},
        "superseded_focused_receipt_sha256": "FFCA7FD621C9E12C91C3FE7C52B2606402642895B720AFDF7BDF37C940043004",
        "final_source_change_after_focused": "bind_existing_direct_loader_and_transfer_helpers_then_fresh_qualification",
        "combined_regression": {"tests_run": 146, "tests_passed": 146, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 160.360, "runner_elapsed_seconds": 161.297,
            "log_sha256": "93361F4A4C29D8A740FDAFD174986E04AA4652C20DCB97EC16884074F2C1F2AD",
            "scope": "final_bound_atomics_entry_IRQ_preemption_capture_and_70_metadata_tests_not_full_canonical",
            "source_unchanged_during_execution": True, "owner_report_unchanged": True,
            "counts_overlap_focused_and_metadata": True},
        "conservation": {"status": "pass", "architecture_bindings": 379, "test_inventory": 1157,
            "unchanged_parent_current_records_archived": 26, "selected_checks": "26/27",
            "phase_flag_and_normative_charter_preserved": True, "native_and_demo_bytes_preserved": True},
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 223: " + checkpoint + " repairs atomics recorded admission and comment-spoofable instruction checks. "
        "Two final one-BSP boots pass 29 groups/78 cases; 22 focused tests pass. Both gates reject 356 corruptions; "
        "eight independent image/count cases, seven rehashed bodies, fourteen disassembly attacks and eight "
        "disabled native guards at two optimization levels are detected. Diagnostic defects and one invalid "
        "test mutation remain recorded; no native kernel bytes changed."
    )
    gap = (
        "Readiness is 26/27. Next " + next_move + ", then N36 shared-helper transitive binding review and full "
        "exact-candidate canonical/Doctor/release/publication/GitHub/review gates before main merge. All prior "
        "checkpoint records remain historical. No phase/flag/ISO/production change. N0 custody, N5 authentication, "
        "full architectural task state, general retirement, hardware and independent builders remain open."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N12", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, "Cycle 223 source inventory: 1157 Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N12-CONCURRENCY-ATOMICS-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return apply_cycle224(roadmap, test_count)


def apply_cycle224(roadmap: dict, test_count: int) -> dict:
    checkpoint = "docs/checkpoints/cycle224-locks-admission-and-current-kernel-replay.md"
    next_move = "N36-RECEIPT-COVERAGE-001"
    gate = roadmap["baseline"]["native_consistency_release_gate"]
    for key, value in list(gate.items()):
        if key.startswith("current_") and isinstance(value, dict):
            suffix = "source_projection" if key == "current_focused_source_projection" else key.removeprefix("current_")
            gate["historical_cycle223_" + suffix] = copy.deepcopy(value)
    roadmap["baseline"]["pooleos_cycle"] = 224
    roadmap["execution_protocol"].update(last_updated_cycle=224,
        selected_move_id="N12-CONCURRENCY-LOCKS-001", owner_independent_next_move_id=next_move)
    roadmap["execution_protocol"]["required_records"].insert(0, checkpoint)
    gate["qualification_status"] = "all_selected_profiles_current_shared_binding_review_and_full_gate_pending"
    gate["current_candidate_audit"] = dict(gate["current_candidate_audit"], cycle=224)
    digest = "40EC2B1A2A79A6EE2388CBF695CDF95752C672529B5803D979AE994382641BA0"
    binding = dict(profile="locks", path="runs/native-kernel-locks-readiness.json", sha256=digest,
        fresh_runs=2, negative_controls=30, hostile_cases=103, kernel_host_tests=246,
        execution_log_sha256="F544F181B3FA3E96D07A5941BB9A85282A9B1F8B2F870BAEF946585B3154046B",
        elapsed_seconds=67.797, recorded_evidence_cases=631)
    previous = gate["historical_cycle223_dependency_qualification"]
    record = copy.deepcopy(previous)
    record.update(cycle=224, source_validation_cycle=224, status="fourteen_current_profiles_full_gate_pending",
        scope="retained_thirteen_profiles_and_fresh_locks224_on_unchanged_kernel216",
        all_fourteen_profiles_current=True,
        qualified_profiles=previous["qualified_profiles"] + ["locks"], newly_qualified_profiles=["locks"],
        readiness_replay_required_profiles=[],
        receipt_bindings=copy.deepcopy(previous["receipt_bindings"]) + [binding],
        embedded_entry_provenance_replay_pending=False, embedded_entry_provenance_pending_scope="none",
        fresh_qemu_runs=2, superseded_initial_runs=4, failed_guest_runs=0,
        run_count_scope="Cycle224_two_final_boots_only_two_diagnostic_and_two_superseded_boots_excluded",
        negative_control_groups=30, negative_control_cases=103, executed_rejection_cases=103,
        native_boundary_cases=0, focused_python_tests=21, generic_recorded_evidence_cases=576,
        additional_control_profile_receipt_cases=55, recorded_evidence_case_total=631,
        recorded_evidence_scope="locks_recorded_admission_not_authentication_or_hardware",
        independent_aggregate_cases=0, independent_current_image_pin_cases=0,
        disabled_native_safeguard_variants_detected=0, disabled_transaction_variants_detected=0)
    gate["current_dependency_qualification"] = record
    projection = gate["current_focused_source_projection"]
    gate["current_focused_source_projection"] = dict(projection, cycle=224, passed_checks=27,
        pending_downstream_native_checks=0,
        passing_profiles=projection["passing_profiles"] + ["native_kernel_locks_readiness"],
        final_receipt_fresh_qemu_runs=2, kernel_entry_runs=2, superseded_initial_qemu_runs=4,
        run_count_scope=record["run_count_scope"], next_dependency_move_id=next_move,
        required_next_gate="shared_helper_binding_review_then_full_exact_candidate",
        focused_python_tests_passed=21, recorded_evidence_rejection_cases=631)
    gate["current_entry_provenance_qualification"] = dict(gate["current_entry_provenance_qualification"], latest_reproduction_cycle=224)
    gate["current_ipi_mailbox_oracle_gap"] = dict(gate["current_ipi_mailbox_oracle_gap"], cycle=224,
        status="bounded_oracle_verified_affected_dependency_replay_complete", remaining_affected_profiles=0,
        newly_requalified_profiles=["locks"], blocks_merge_qualification=False)
    gate["current_control_execution_audit"] = dict(gate["current_control_execution_audit"], cycle=224,
        next_profile="shared_helper_transitive_bindings", locks_recorded_admission_repaired=True,
        shared_helper_static_inventory={
            "status": "preliminary_not_complete_dependency_proof", "profiles_examined": 14,
            "local_import_closure_range": [35, 38], "missing_explicit_path_hash_binding_range": [20, 27],
            "common_missing_paths": 17, "stale_explicit_bindings": 0,
            "report_sha256": "D09C9DA173797D63FFFCFA7C0E9E01F1D986DF929372C2E69D9F725DD55FA499",
            "script_sha256": "BF4024B9D592F3797AB7A1D91B183A3BD0481132A36F5B2B94789C3C36DC0E0A",
            "limitations": "conservative_static_imports_not_dynamic_imports_data_or_tool_closure",
            "wrong_execution_source_proved": False,
            "snapshot_reconciliation": {
                "profiles_accounted": 14, "missing_snapshot_paths": 0, "changed_snapshot_paths": 0,
                "exact_successful_producer_output_matches": 14,
                "report_sha256": "890AC3472499E07097F845625BCF7386096DE668600C752D089944D7269D090A",
                "script_sha256": "3A355CA00D569F0DFE35D7F6F997CB0A0541D0CBB43898FDD66FAF50128260AE",
                "runtime_dependency_guard_integrated": False,
                "authentication_or_independent_builder_proved": False,
            },
            "next_action": "enforce_retained_execution_source_closure_and_review_upstream_dynamic_data_and_tool_dependencies_before_full_exact_candidate_gate",
        })
    gate["current_locks_admission_qualification"] = {
        "cycle": 224, "source_validation_cycle": 224, "move_id": "N12-CONCURRENCY-LOCKS-001",
        "status": "pass", "applies_to_current_source": True, "current_receipt_admitted": True,
        "receipt_sha256": digest, "kernel_sha256": record["kernel_sha256"],
        "recorded_corruption_cases": 631, "disabled_validator_variants_detected": 3,
        "empty_control_groups_rejected": True, "host_probe_timeout_seconds": 180,
        "windows_timeout_cleanup": "launched_Cargo_tree_killed_before_wait_with_file_capture_no_inherited_pipe_wait",
        "timeout_cleanup_success_and_failure_paths_mock_tested": True,
        "real_host_probe_timeout_observed": False,
        "superseded_pre_cleanup_receipt_sha256": "2754EAC48AFEAB0C251DBC448BC531EC76069C38A842D4BE502649AC068A13A8",
        "diagnostic_baseline": {"receipt_sha256": "16BB7B563380C8AA92BCF73D9A06F5425559E116F865C7DE744D15C349B00889",
            "runtime_accepted": True, "aggregate_gate_accepted": True, "mutation_cases": 576,
            "runtime_corruptions_accepted": 53, "gate_corruptions_accepted": 32,
            "runtime_exceptions": 6, "gate_exceptions": 64, "boots": 2, "admitted_as_final": False},
        "after_audit": {"runtime_corruptions_accepted": 0, "gate_corruptions_accepted": 0,
            "runtime_exceptions": 0, "gate_exceptions": 0},
        "historical_fixture_path": "tests/fixtures/cycle181-locks-readiness.json",
        "historical_fixture_sha256": "837AF50A257AA54316E72014E4B63BB6B18E33161E42FD854A849F2D7AE96F79",
        "pair_validation_is_freshness_or_authentication": False, "positive_receipt_rebound_in_tests": False,
        "native_kernel_changed": False, "production_ready": False,
    }
    gate["current_closeout_regression"] = {
        "cycle": 224, "status": "pass", "scope": "locks_and_all_profile_entry_provenance_not_full_canonical",
        "tests_run": 21, "tests_passed": 21, "tests_failed": 0, "tests_skipped": 0,
        "elapsed_seconds": 25.475, "runner_elapsed_seconds": 26.359,
        "log_sha256": "E4AC6246B4E4CA55F26B2873A841A94B100C9ACFD40CD0CF2535F5F26830F0AC",
        "source_unchanged_during_execution": True, "owner_report_unchanged": True,
        "focused_and_initial_combined_precede_timeout_cleanup_repair": True,
        "initial_metadata": {"tests_run": 71, "tests_passed": 68, "tests_failed": 3, "tests_skipped": 0,
            "cause": "three_stale_current_profile_count_assertions", "admitted_as_pass": False,
            "log_sha256": "0EA5DF94F654CB88C9570FB2A7997F823317AE259B63F00A8530540139E366A7"},
        "combined_regression": {"tests_run": 137, "tests_passed": 137, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 135.301, "runner_elapsed_seconds": 136.250,
            "log_sha256": "0D96AE0CA14C364056D7E14BF175144EC399CB214C2AF0BEBD8AA09C48706FB7",
            "scope": "locks_all_profile_entry_atomics_capture_and_71_metadata_tests_not_full_canonical",
            "source_unchanged_during_execution": True, "owner_report_unchanged": True,
            "counts_overlap_focused_and_metadata": True},
        "final_combined_regression": {"tests_run": 137, "tests_passed": 137, "tests_failed": 0, "tests_skipped": 0,
            "elapsed_seconds": 135.545, "runner_elapsed_seconds": 136.485,
            "log_sha256": "5077FC39F2E8CBD50C02945D1FFC5415577EA97FA5859C6448AE1B0EBCC24588",
            "scope": "final_timeout_cleanup_source_locks_entry_atomics_capture_and_71_metadata_not_full_canonical",
            "source_unchanged_during_execution": True, "owner_report_unchanged": True,
            "counts_overlap_initial_combined": True},
        "conservation": {"status": "pass", "architecture_bindings": 382, "test_inventory": 1163,
            "unchanged_parent_current_records_archived": 27, "selected_checks": "27/27",
            "phase_flag_and_normative_charter_preserved": True, "native_and_demo_bytes_preserved": True},
        "canonical_full_replay_performed": False, "merge_qualified": False, "production_ready": False,
    }
    evidence = (
        "Cycle 224: " + checkpoint + " repairs lock recorded admission and replays two final four-vCPU boots "
        "on unchanged kernel216. 246 kernel tests, 30 groups/103 cases and 21 focused tests pass, including "
        "all-profile entry provenance. Both gates reject 631 corrupted records; three disabled validators "
        "are detected. Final combined regression passes 137/137 without skips; all 14 static helper closures "
        "match preserved successful producer snapshots. Diagnostic invalid admissions and exceptions remain "
        "preserved, not accepted as final."
    )
    gap = (
        "All 27 selected native checks pass. Next " + next_move + ": audit shared-helper transitive source "
        "bindings, then full exact-candidate canonical/Doctor/release/publication/GitHub/review gates before "
        "main merge. This is not N36 closure. No phase/flag/native-byte/ISO/production change. N0 custody, "
        "N5 authentication, complete task state, general retirement, hardware and independent builders remain open."
    )
    for phase in roadmap["phases"]:
        if phase["id"] in {"N12", "N36"}:
            phase["current_evidence"].insert(0, evidence)
            phase["current_gaps"].insert(0, gap)
        if phase["id"] == "N36":
            phase["current_evidence"].insert(0, f"Cycle 224 source inventory: {test_count} Python tests discovered; full qualification pending")
    for flag in roadmap["implementation_flags"]:
        if flag["id"] in {"FLAG-N12-CONCURRENCY-LOCKS-001", "FLAG-N36-RECEIPT-COVERAGE-001"}:
            flag["evidence"].insert(0, checkpoint)
    roadmap["gap_summary"]["native_program_gaps"][4] = evidence + " " + gap + " " + roadmap["gap_summary"]["native_program_gaps"][4]
    roadmap["claim_boundaries"].insert(0, evidence + " " + gap)
    return roadmap


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "runs/pdc_production_roadmap.json")
    parser.add_argument("--test-count", type=int, default=1163)
    parser.add_argument("--status-date", default="2026-10-07")
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
