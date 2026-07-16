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
    "N15.1": "partial",
    "N31.7": "partial",
    "N32.1": "complete",
    "N33.1": "partial",
    "N33.8": "partial",
    "N34.1": "blocked",
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
        "specs/native-v1-objectives.json and docs/native-v1-objectives.md: 38 measurable candidate targets across five required families",
        "runs/native_v1_objectives_readiness.json: deterministic consistency pass with zero measured targets and owner ratification pending",
        "tools/verify_native_v1_objectives.py with ten fail-closed negative controls",
        "specs/adr-ratification-policy.json and docs/adr-ratification-ceremony.md: scope-hardened contract binding six exact decision sources and all 38 objective definitions without accepting measurements",
        "runs/adr_ratification_readiness.json: deterministic six-source owner-action boundary with zero trusted signers, 12 declared negative controls, and six owner actions",
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
        "ADR-0003 proposed Rust/assembly/C17 split",
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
    ],
    "N15": ["runs/microkernel_isolation.json", "runs/capability_trap_proof.json", "runs/capability_trap_fuzz.json"],
    "N31": ["existing signed receipt and benchmark methodology artifacts"],
    "N32": ["PDC-MATH-0.1", "PDC-REP-0.1", "PDC-GOLDEN-0.2", "PDC-QP-0.1", "PDC-QP-STABILITY-0.1"],
    "N33": ["existing PDC receipt schemas and guarded-route source documents; no native services"],
    "N34": ["PooleGlyph Phase 65 checkpoint", "draft PGB2/PGVM2 trap evidence"],
    "N35": ["bounded static capability and trap simulations; no native containment"],
    "N36": ["Cycle 88 host baseline: 455 tests with one Windows symlink-permission skip", "native binary parser, reproduction, leakage, malformed, substitution, objectives, ADR-signing, ratification-scope, hardware privacy, malformed-CPUID, Tier 0 profile/provenance/path/overclaim controls, and collector-smoke negatives"],
    "N37": ["Cycle 88 consistency release gate: 66/66 checks over 61 artifacts", "content-addressed source, objectives-readiness, scope-hardened ADR-readiness, native-toolchain, bounded hardware-readiness, and native Tier 0 readiness artifacts"],
}


PHASE_GAPS = {
    "N0": [
        "The canonical ceremony now binds all six decision sources, including the exact 38-target objective contract and schema, but none of seven ADRs is cryptographically signed; ADR-0003 and ADR-0004 still require owner disposition",
        "The 38 reliability, accessibility, compatibility, privacy, and performance target definitions remain candidate-only; owner acceptance and all implementation-bound measurements remain open",
        "The extracted-tree scanner does not yet parse ISO/GPT/ESP/El Torito/signature structures",
    ],
    "N1": [
        "Public remote and branch protection exist; owner key choice, signed tags, immutable release refs, retained CI/review evidence, signing custody, and multi-maintainer approval policy remain open",
        "Legal, patent, export, trademark, contributor, signing-custody, and component-specific license review remain open",
    ],
    "N2": ["Exact identity passes 24/24 required checks and 16 allowlisted user-mode CPUID records close the bounded CPUID sub-capability, but MSR access remains pending a reviewed privileged mechanism; seven required evidence channels, 15 exact standards artifact hashes, ten destructive-lab prerequisites, and native-parser comparison remain open"],
    "N3": ["One-host Rust PE32+/ELF64 qualification passes; second-host reproduction, source provenance, C17/assembly/ABI/image tools, complete build graph, and low-level safety gates remain open"],
    "N4": ["A pinned one-host q35/QEMU/OVMF/VIRTIO profile and paused-instantiation evidence exist, but current upstream source rebuilds, actual PooleBoot serial/debug-exit/GDB/reset evidence, remaining VIRTIO profiles, malformed-device campaigns, formal models, model-trace cross-checks, and second-host reproduction remain open"],
    "N5": ["No PooleBoot PE32+ image or frozen boot handoff exists"],
    "N6": ["No native boot trust, kernel image, entry, serial panic, or measured boot exists"],
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
    "N34": ["PooleGlyph Phase 66 is absent", "PGB2 and PGVM2 v1 are not frozen or native"],
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
    ("FLAG-NATIVE-BOOT-001", "STOP_SHIP", "N5", "Boot reproducible PooleBoot PE32+ and transfer through the frozen handoff"),
    ("FLAG-NATIVE-KERNEL-001", "STOP_SHIP", "N13", "Boot PooleKernel and enforce memory, capabilities, IPC, and ring-3 execution"),
    ("FLAG-NATIVE-IOMMU-001", "STOP_SHIP", "N11", "Confine all bus-mastering drivers with DMA and interrupt remapping"),
    ("FLAG-NATIVE-DRIVER-001", "STOP_SHIP", "N16", "Prove driver crash/reset/revocation without stale authority"),
    ("FLAG-NATIVE-FS-001", "STOP_SHIP", "N19", "Pass declared PooleFS durability and randomized power-cut gates"),
    ("FLAG-NATIVE-UPDATE-001", "STOP_SHIP", "N23", "Pass signed A/B update, rollback, compromise, and recovery gates"),
    ("FLAG-NATIVE-SEC-001", "STOP_SHIP", "N15", "Pass boot trust, crypto/RNG, capability, isolation, and external security review"),
    ("FLAG-NATIVE-UI-001", "REQUIRED", "N29", "Pass PooleGlass accessibility, software fallback, and recovery UI gates"),
    ("FLAG-NATIVE-PGL-001", "BLOCKER", "N34", "Accept PooleGlyph Phase 66 and freeze PGB2/PGVM2 v1"),
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
    ("FLAG-NATIVE-ISO-001", "STOP_SHIP", "N39", "Reproduce and boot the exact signed native ISO in clean QEMU and physical profiles"),
    ("FLAG-NATIVE-REVIEW-001", "STOP_SHIP", "N37", "Close critical/high independent kernel, filesystem, update, security, and release findings"),
    ("FLAG-BUILDROOT-LEGACY-001", "SUPERSEDED", "N0", "Keep Buildroot as historical non-promoting reference evidence"),
]


PROGRAM_GAPS = [
    "The native repository, protected workflow, and scope-hardened ADR ceremony bind the 38-target candidate objectives contract exactly, but target acceptance, all measurements, owner disposition, trusted key custody, signatures, signed tags, immutable release refs, and retained CI review evidence remain open",
    "Rust PE32+/ELF64 fixtures pass one-host qualification, but second-host reproduction, source provenance, C17/assembly/ABI tools, and image tooling remain open",
    "The native-only q35/QEMU/OVMF/VIRTIO profile passes one-host paused-instantiation controls, but source-rebuilt current QEMU/EDK II, real PooleBoot launch evidence, complete reference devices/fault campaigns, formal state models, trace cross-checks, and second-host reproduction remain open",
    "No PooleBoot PE32+ UEFI loader or frozen boot protocol",
    "No native boot trust, measured boot, kernel image, early runtime, serial panic, or crash path",
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
    "PooleGlyph Phase 66, PGB2 v1, and PGVM2 v1 remain open",
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
            evidence.extend(["specs/native-v1-objectives.json", "runs/native_v1_objectives_readiness.json"])
        if flag_id == "FLAG-N0-RATIFICATION-SCOPE-001":
            evidence.extend(
                [
                    "specs/adr-ratification-policy.json",
                    "specs/native-v1-objectives.json",
                    "specs/native-v1-objectives.schema.json",
                    "runs/adr_ratification_readiness.json",
                ]
            )
        implementation_flags.append(
            {
                "id": flag_id,
                "class": flag_class,
                "status": "closed"
                if flag_class == "SUPERSEDED"
                or flag_id in {"FLAG-N0-RATIFICATION-SCOPE-001", "FLAG-N2-CPUID-001", "FLAG-N4-PROFILE-001"}
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
        "objective": "Deliver production-ready native PooleOS as an original PooleBoot plus PooleKernel microkernel system and reproducible signed UEFI bootable ISO with PooleGlyph, canonical PDC, isolated drivers, guarded backends, and accessible PooleGlass Liquid Glass UI.",
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
            "last_updated_cycle": 88,
            "selected_move_id": "N4-QEMU-001",
            "immediate_next_move_id": "N0-RATIFY-001",
            "required_records": [
                "docs/production-goal-charter.md",
                "docs/pdc-production-build-plan.md",
                "runs/pdc_production_roadmap.json",
                "runs/pooleos_native_checklist_coverage.json",
                "runs/native_toolchain_qualification.json",
                "runs/adr_ratification_readiness.json",
                "runs/hardware_target_readiness.json",
                "runs/native_tier0_readiness.json",
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
            "pooleos_cycle": 88,
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
                "passed_checks": 66,
                "total_checks": 66,
                "artifact_count": 61,
                "explicit_gap_count": len(PROGRAM_GAPS),
                "production_ready": False,
                "native_promotion_role": "planning_and_evidence_consistency_non_promoting",
            },
            "native": {
                "source_controlled": True,
                "pooleboot_exists": False,
                "poolekernel_exists": False,
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
            "id": "N0-RATIFY-001",
            "phase_ids": ["N0", "N1"],
            "title": "Complete owner objective acceptance, ADR disposition, key custody, signatures, signed tag, and publication receipt for the exact six-source architecture set",
            "entry_evidence": ["docs/adr/0001-native-pooleos-constitution.md through ADR-0007", "runs/native_architecture_baseline.json", "runs/native_v1_objectives_readiness.json", "runs/adr_ratification_readiness.json", "docs/adr-ratification-ceremony.md", "runs/native_toolchain_qualification.json"],
            "exit_evidence": ["owner acceptance or amendment of the native v1 profile and all 38 target values", "owner disposition of ADR-0003 and ADR-0004", "owner-controlled signatures for the accepted ADR set", "documented signing custody and verification procedure", "signed baseline tag and publication receipt"],
            "blocked": True,
        },
        "claim_boundaries": [
            "Buildroot and Linux artifacts are historical reference evidence and cannot satisfy native PooleOS gates.",
            "Checklist mapping is not implementation completion.",
            "Host simulations and schemas are not native kernel enforcement.",
            "Four paused q35/QMP instantiations prove host-side profile construction only; no guest CPU instruction, native media, boot, driver, Secure Boot, or formal-model claim follows.",
            "Sixteen allowlisted user-mode CPUID records prove only a bounded host observation; they do not prove MSR access, privileged probes, native parsing, driver safety, or Tier 1 qualification.",
            "Binding thirty-eight consistent candidate objective definitions into a future signature while binding zero measurements is not owner ratification or implementation evidence.",
            "PooleGlyph Phase 65 metadata cannot be promoted before Phase 66 executable evidence.",
            "Finite PDC/QP evidence remains bounded to its declared classical models and protocols.",
            "A file named ISO is not reproducible signed clean-media boot evidence.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "runs/pdc_production_roadmap.json")
    parser.add_argument("--test-count", type=int, default=455)
    parser.add_argument("--status-date", default="2026-07-16")
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
