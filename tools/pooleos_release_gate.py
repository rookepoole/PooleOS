#!/usr/bin/env python3
"""Emit a machine-readable PooleOS release-gate report."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import pgb2_bundle as pgb2  # noqa: E402
from runtime import adr_ratification  # noqa: E402
from runtime import hardware_target  # noqa: E402
from runtime import lab_readiness  # noqa: E402
from runtime import native_boot_config  # noqa: E402
from runtime import native_boot_handoff  # noqa: E402
from runtime import native_boot_trust  # noqa: E402
from runtime import native_elf_loader  # noqa: E402
from runtime import native_firmware  # noqa: E402
from runtime import native_kernel_entry  # noqa: E402
from runtime import native_kernel_load  # noqa: E402
from runtime import native_kernel_revalidation  # noqa: E402
from runtime import native_kernel_transfer  # noqa: E402
from runtime import native_kernel_trap  # noqa: E402
from runtime import native_kernel_cpu_policy  # noqa: E402
from runtime import native_initial_system  # noqa: E402
from runtime import native_microcode  # noqa: E402
from runtime import native_models  # noqa: E402
from runtime import native_policy  # noqa: E402
from runtime import native_pooleboot  # noqa: E402
from runtime import native_recovery  # noqa: E402
from runtime import native_symbols  # noqa: E402
from runtime import native_system_manifest  # noqa: E402
from runtime import n0_owner_decision_packet  # noqa: E402
from runtime import n0_owner_response  # noqa: E402
from runtime import native_tier0  # noqa: E402
from runtime import native_v1_objectives  # noqa: E402
from runtime import readiness  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


MASTER_CHECKLIST_SHA256 = "A8C94719FAF9428C1F133010BA2603C0270C4E1EFD7327AF8EAB9C8C362ABB3D"
NATIVE_ROADMAP = ROOT / "runs" / "pdc_production_roadmap.json"
NATIVE_COVERAGE = ROOT / "runs" / "pooleos_native_checklist_coverage.json"
NATIVE_ARCHITECTURE_BASELINE = ROOT / "runs" / "native_architecture_baseline.json"
NATIVE_V1_OBJECTIVES_READINESS = ROOT / "runs" / "native_v1_objectives_readiness.json"
ADR_RATIFICATION_READINESS = ROOT / "runs" / "adr_ratification_readiness.json"
N0_OWNER_DECISION_PACKET = ROOT / "runs" / "n0_owner_decision_packet.json"
N0_OWNER_RESPONSE_RECEIPT = ROOT / "runs" / "n0_owner_response_receipt.json"
NATIVE_TOOLCHAIN_QUALIFICATION = ROOT / "runs" / "native_toolchain_qualification.json"
HARDWARE_TARGET_READINESS = ROOT / "runs" / "hardware_target_readiness.json"
NATIVE_MODEL_READINESS = ROOT / "runs" / "native_model_readiness.json"
NATIVE_BOOT_CONFIG_READINESS = ROOT / "runs" / "native_boot_config_readiness.json"
NATIVE_BOOT_HANDOFF_READINESS = ROOT / "runs" / "native_boot_handoff_readiness.json"
NATIVE_BOOT_TRUST_READINESS = ROOT / "runs" / "native_boot_trust_readiness.json"
NATIVE_ELF_LOADER_READINESS = ROOT / "runs" / "native_elf_loader_readiness.json"
NATIVE_KERNEL_ENTRY_READINESS = ROOT / "runs" / "native_kernel_entry_readiness.json"
NATIVE_KERNEL_LOAD_READINESS = ROOT / "runs" / "native_kernel_load_readiness.json"
NATIVE_KERNEL_REVALIDATION_READINESS = ROOT / "runs" / "native-kernel-revalidation-readiness.json"
NATIVE_KERNEL_TRANSFER_READINESS = ROOT / "runs" / "native-kernel-transfer-readiness.json"
NATIVE_KERNEL_TRAP_READINESS = ROOT / "runs" / "native-kernel-trap-readiness.json"
NATIVE_KERNEL_CPU_POLICY_READINESS = ROOT / "runs" / "native-kernel-cpu-policy-readiness.json"
NATIVE_INITIAL_SYSTEM_READINESS = ROOT / "runs" / "native_initial_system_readiness.json"
NATIVE_FIRMWARE_READINESS = ROOT / "runs" / "native_firmware_readiness.json"
NATIVE_MICROCODE_READINESS = ROOT / "runs" / "native_microcode_readiness.json"
NATIVE_POLICY_READINESS = ROOT / "runs" / "native_policy_readiness.json"
NATIVE_POOLEBOOT_READINESS = ROOT / "runs" / "native_pooleboot_readiness.json"
NATIVE_RECOVERY_READINESS = ROOT / "runs" / "native_recovery_readiness.json"
NATIVE_SYMBOL_READINESS = ROOT / "runs" / "native_symbol_readiness.json"
NATIVE_SYSTEM_MANIFEST_READINESS = ROOT / "runs" / "native_system_manifest_readiness.json"
NATIVE_TIER0_READINESS = ROOT / "runs" / "native_tier0_readiness.json"


DEFAULT_GAPS = [
    "The completed owner response records both ADR dispositions and all 38 objective definitions while accepting zero measurements, but the selected FIDO2 hardware key is unavailable; trusted public-key custody, detached signatures, the signed baseline tag, immutable release refs, and retained CI review evidence remain open.",
    "Rust 1.97.0 PE32+/ELF64 fixtures pass one-host qualification, but the second clean host, source-rebuilt compiler provenance, C17/assembly/ABI tools, and image toolchain remain open.",
    "The native-only q35/QEMU/OVMF/VIRTIO profile passes one-host paused-instantiation controls, six bounded TLC models cover all seven required domains and detect twenty-one required counterexamples, and a bounded PooleBoot proof executes under the pinned profile; current source rebuilds, complete reference devices/fault campaigns, six implementation-trace cross-checks, liveness/refinement/conformance work, and second-host reproduction remain open.",
    "A reproducible unsigned PooleBoot proof application boots twice under pinned non-promoting OVMF with deterministic twelve-file GPT/FAT32 media and twenty-five ordered serial/debugcon markers; PBP1, PBC1, PSM1, PKELF1, PBART1, PINIT1, PREC1, PSYM1, synthetic-only PMCU1, synthetic-only PFWM1, qualification-only PPOL1, PBTRUST1/PBSTATE1, PKMAP2, PBEXIT1, PKREVAL1, PKXFER1, PKTRAP1, PKCPU1, and a separately qualified real PooleKernel image pass their bounded gates. PKLOAD6 proves exact retained storage and successful ExitBootServices with zero later firmware calls while the default path stops permanently. PKXFER1 separately proves one opt-in QEMU-only transfer and live nine-file PKREVAL1 denial. PKTRAP1 adds only three opt-in BSP scenarios with five present IDT gates, distinct unguarded IST arrays, three returning deliberate faults, terminal double-fault containment, and semantic malformed-frame rejection. PKCPU1 adds only one opt-in BSP qemu64 read-only CPUID/control/XCR0/APIC/PAT/MTRR profile with five MSR reads and zero writes or authority. Policy signatures, authenticated revocation, a real cryptographic monotonic writable provider, persistent backend I/O and executed repair/migration, Secure Boot-state verification, activation, recovery execution, symbol consumption, capability creation and enforcement, live firmware inventory, privileged microcode-revision observation, real vendor-container or payload validation, digest-provider promotion, initial-system execution, microcode or firmware application, final framebuffer cache policy, production transfer, second host, target firmware, and physical-media qualification remain open.",
    "A real reproducible PooleKernel image, PKENTRY1 intake, bounded early diagnostics, panic classes, PKXFER1 live entry, BSP-only PKTRAP1 descriptor/exception entry, and BSP-only qemu64 PKCPU1 read-only CPU-policy observation exist, but boot trust, measured boot, production transfer, exact target-family/errata/xstate and AP-local CPU policy, per-CPU descriptor state, guarded IST stacks, complete exception/NMI/machine-check handling, asynchronous context preservation, retained crash evidence, kernel runtime, target execution, and N6/N7 exit remain open.",
    "No target-qualified complete native CPU policy, errata/microcode policy, xstate ownership, AP-local CPU state, interrupt, time, SMP, physical-memory, virtual-memory, or reclaim implementation; PKCPU1 is a bounded read-only qemu64 BSP observation only.",
    "The sanitized Tier 1 identity and bounded user-mode CPUID transcript match, but MSR, PCI configuration-space, Secure Boot, TPM, SPD, sensor/power, standards-hash, lab-safety, native enumeration, and physical qualification evidence remain open.",
    "No native DMA/IOMMU/interrupt-remapping confinement.",
    "No native scheduler, task, syscall, capability, IPC, isolation, asynchronous-I/O, or quota implementation.",
    "No native security, cryptography, TPM, secrets, MAC, privacy implementation, or external review.",
    "No isolated native driver domains or VIRTIO reference drivers.",
    "No native block, NVMe, USB, input, VFS, PooleFS, or persistent-data path.",
    "No native user ABI, libc, init, service manager, login, shell, terminal, package, update, installer, or recovery path.",
    "No native network, graphics, audio, compositor, PooleGlass, accessibility, or application platform.",
    "No source-bound signed PDC dynamics or portable and native PDC backends.",
    "No native PDC control-plane services or bounded actuator proof.",
    "PooleGlyph Phase 66 and the source, semantic, Core IR, PGASM, PGB2, PGVM2, host-ABI, policy, toolchain, compatibility, IP-boundary, private-backend-equivalence, and native-integration gates remain open.",
    "No native integrated fuzz, fault, power-loss, security, conformance, or soak evidence.",
    "No native SBOM, provenance, signing ceremony, operations evidence, or release manifest.",
    "No reproducible signed native ISO or exact clean-media QEMU and physical release receipt.",
]


def run_doctor(*, include_runtime: bool) -> dict:
    cmd = [sys.executable, str(ROOT / "tools" / "pooleos_doctor.py")]
    if not include_runtime:
        cmd.append("--no-runtime")
    completed = subprocess.run(
        cmd,
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    output_lines = completed.stdout.splitlines()
    if completed.returncode == 0:
        detail = "\n".join(output_lines[-8:])
    else:
        failure_lines = [line for line in output_lines if line.startswith("FAIL ")]
        detail = "\n".join([*failure_lines[-12:], "--- doctor tail ---", *output_lines[-8:]])
    return readiness.make_check("pooleos_doctor", completed.returncode == 0, detail)


def check_bundle(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("pgb2_bundle", False, "no bundle path provided")
    if not path.exists():
        return readiness.make_check("pgb2_bundle", False, f"missing {path}")
    bundle = pgb2.read_bundle(path)
    result = pgb2.validate_bundle(bundle, specs_dir=ROOT / "specs")
    section_names = [section.get("name") for section in bundle.get("sections", [])]
    trap_evidence = "TRAP_ENCODING" in section_names and "TRAP_EXECUTION" in section_names
    detail = f"valid; sections={len(section_names)}; trap_evidence={trap_evidence}"
    return readiness.make_check("pgb2_bundle", result.ok, detail if result.ok else "; ".join(result.errors[:5]))


def check_replay_proof(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("replay_proof", False, "no replay proof path provided")
    if not path.exists():
        return readiness.make_check("replay_proof", False, f"missing {path}")
    import json

    proof = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "specs" / "replay-proof.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(proof, schema)
    if proof.get("channel_summary_match") is not True:
        errors.append(type("Error", (), {"path": "$.channel_summary_match", "message": "expected true"})())
    return readiness.make_check(
        "replay_proof",
        not errors,
        "valid" if not errors else "; ".join(f"{e.path}: {e.message}" for e in errors[:5]),
    )


def _load_schema_artifact(path: Path, schema_name: str) -> tuple[dict | None, list]:
    if not path.exists():
        return None, [type("Error", (), {"path": "$", "message": f"missing {path}"})()]
    artifact = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "specs" / schema_name).read_text(encoding="utf-8"))
    return artifact, validate_json(artifact, schema)


def check_native_architecture_plan(
    roadmap_path: Path = NATIVE_ROADMAP,
    coverage_path: Path = NATIVE_COVERAGE,
) -> dict:
    errors: list[str] = []
    roadmap, roadmap_schema_errors = _load_schema_artifact(roadmap_path, "pdc-production-roadmap.schema.json")
    coverage, coverage_schema_errors = _load_schema_artifact(
        coverage_path,
        "pooleos-native-checklist-coverage.schema.json",
    )
    errors.extend(f"roadmap {error.path}: {error.message}" for error in roadmap_schema_errors[:5])
    errors.extend(f"coverage {error.path}: {error.message}" for error in coverage_schema_errors[:5])

    if not isinstance(roadmap, dict) or not isinstance(coverage, dict):
        return readiness.make_check(
            "native_architecture_plan",
            False,
            "; ".join(errors[:8]) or "roadmap or coverage artifact is not an object",
        )

    source = coverage.get("source", {})
    source_relative = source.get("path")
    source_path = ROOT / str(source_relative)
    try:
        source_path.resolve().relative_to(ROOT.resolve())
    except ValueError:
        errors.append("coverage source path escapes the PooleOS workspace")

    if not source_path.is_file():
        errors.append(f"locked checklist is missing: {source_path}")
        source_hash = None
    else:
        source_bytes = source_path.read_bytes()
        source_hash = hashlib.sha256(source_bytes).hexdigest().upper()
        if source_hash != MASTER_CHECKLIST_SHA256:
            errors.append(f"locked checklist hash mismatch: {source_hash}")
        if len(source_bytes) != source.get("byte_count"):
            errors.append("locked checklist byte count does not match coverage")
        if len(source_bytes.decode("utf-8").splitlines()) != source.get("line_count"):
            errors.append("locked checklist line count does not match coverage")

    if coverage.get("status") != "pass" or coverage.get("unmapped_source_lines") != []:
        errors.append("checklist coverage is not a zero-unmapped pass")
    if source.get("sha256") != MASTER_CHECKLIST_SHA256:
        errors.append("coverage is not bound to the canonical checklist digest")
    if source.get("declared_generated_implementation_item_count") != 8996:
        errors.append("coverage implementation-item count is not 8,996")
    if len(coverage.get("phase_coverage", [])) != 40:
        errors.append("coverage does not define all 40 native phases")
    if len(coverage.get("section_coverage", [])) != 171:
        errors.append("coverage does not map all 171 source sections")

    master = roadmap.get("master_checklist", {})
    coverage_hash = hashlib.sha256(coverage_path.read_bytes()).hexdigest().upper() if coverage_path.is_file() else None
    if master.get("source_sha256") != source_hash or master.get("source_sha256") != MASTER_CHECKLIST_SHA256:
        errors.append("roadmap checklist binding does not match the locked source")
    if master.get("coverage_sha256") != coverage_hash:
        errors.append("roadmap coverage digest does not match the coverage artifact")
    architecture = roadmap.get("architecture", {})
    if architecture.get("mode") != "native_capability_microkernel":
        errors.append("roadmap architecture is not native_capability_microkernel")
    if architecture.get("bootloader") != "PooleBoot" or architecture.get("kernel") != "PooleKernel":
        errors.append("roadmap does not name PooleBoot and PooleKernel as production components")
    expected_phase_ids = [f"N{index}" for index in range(40)]
    if [phase.get("id") for phase in roadmap.get("phases", [])] != expected_phase_ids:
        errors.append("roadmap phase sequence is not exactly N0-N39")
    if roadmap.get("production_ready") is not False:
        errors.append("roadmap overclaims native production readiness")

    plan_text = (ROOT / "docs" / "pdc-production-build-plan.md").read_text(encoding="utf-8")
    charter_text = (ROOT / "docs" / "production-goal-charter.md").read_text(encoding="utf-8")
    for marker in ("### N0 -", "### N39 -", "PooleBoot", "PooleKernel", "8,996"):
        if marker not in plan_text:
            errors.append(f"build plan is missing marker {marker!r}")
    for marker in ("2.0.0-native-reset", "PooleBoot", "PooleKernel", "N0-N39"):
        if marker not in charter_text:
            errors.append(f"goal charter is missing marker {marker!r}")

    detail = (
        f"native N0-N39; checklist_sha256={MASTER_CHECKLIST_SHA256}; "
        "implementation_items=8996; sections=171; unmapped=0; production_ready=false"
    )
    return readiness.make_check(
        "native_architecture_plan",
        not errors,
        detail if not errors else "; ".join(errors[:8]),
    )


def check_native_architecture_baseline(path: Path = NATIVE_ARCHITECTURE_BASELINE) -> dict:
    artifact, schema_errors = _load_schema_artifact(path, "native-architecture-baseline.schema.json")
    errors = [f"baseline {error.path}: {error.message}" for error in schema_errors[:8]]
    if not isinstance(artifact, dict):
        return readiness.make_check(
            "native_architecture_baseline",
            False,
            "; ".join(errors) or "architecture baseline is not an object",
        )

    repository = artifact.get("repository", {})
    if repository.get("initialized") is not True:
        errors.append("repository is not initialized")
    if repository.get("current_branch") != "main":
        errors.append("repository branch is not main")
    expected_remote = "https://github.com/rookepoole/PooleOS.git"
    if repository.get("configured_remote") != expected_remote or repository.get("expected_remote") != expected_remote:
        errors.append("repository remote does not match the owner PooleOS remote")

    summary = artifact.get("adr_summary", {})
    if summary.get("required_count") != 7 or summary.get("present_count") != 7:
        errors.append("required seven-record ADR constitution is incomplete")
    if summary.get("accepted_owner_directed_count") != 7 or summary.get("proposed_count") != 0:
        errors.append("ADR status inventory does not match the current baseline")
    if summary.get("accepted_signed_count") != 0 or summary.get("all_required_cryptographically_ratified") is not False:
        errors.append("ADR baseline overclaims cryptographic ratification")
    if artifact.get("production_ready") is not False or artifact.get("production_promotion_allowed") is not False:
        errors.append("architecture baseline overclaims production promotion")

    for binding in [*artifact.get("adrs", []), *artifact.get("bound_sources", [])]:
        relative = binding.get("path")
        if not isinstance(relative, str):
            errors.append("baseline contains a source binding without a path")
            continue
        bound_path = ROOT / relative
        try:
            bound_path.resolve().relative_to(ROOT.resolve())
        except ValueError:
            errors.append(f"baseline path escapes repository: {relative}")
            continue
        if not bound_path.is_file():
            errors.append(f"baseline-bound file is missing: {relative}")
            continue
        data = bound_path.read_bytes()
        if hashlib.sha256(data).hexdigest().upper() != binding.get("sha256"):
            errors.append(f"baseline digest mismatch: {relative}")
        if len(data) != binding.get("byte_count"):
            errors.append(f"baseline byte-count mismatch: {relative}")

    architecture = artifact.get("architecture", {})
    if architecture.get("bootloader") != "PooleBoot" or architecture.get("kernel") != "PooleKernel":
        errors.append("baseline does not freeze PooleBoot and PooleKernel")
    if architecture.get("production_base") != "original_native_pooleos":
        errors.append("baseline production base is not original native PooleOS")

    detail = (
        "7 ADRs byte-bound; accepted_owner_directed=7; proposed=0; signed=0; "
        "repository=main@owner-remote; production_promotion_allowed=false"
    )
    return readiness.make_check(
        "native_architecture_baseline",
        not errors,
        detail if not errors else "; ".join(errors[:8]),
    )


def check_native_v1_objectives_readiness(path: Path = NATIVE_V1_OBJECTIVES_READINESS) -> dict:
    artifact, schema_errors = _load_schema_artifact(path, "native-v1-objectives-readiness.schema.json")
    errors = [f"objectives readiness {error.path}: {error.message}" for error in schema_errors[:8]]
    if not isinstance(artifact, dict):
        return readiness.make_check(
            "native_v1_objectives_readiness",
            False,
            "; ".join(errors) or "native v1 objectives readiness is not an object",
        )

    try:
        regenerated = native_v1_objectives.build_readiness(ROOT)
        if path.read_bytes() != native_v1_objectives.canonical_json_bytes(regenerated):
            errors.append("objectives readiness is not the exact deterministic regeneration")
    except (OSError, ValueError, KeyError, json.JSONDecodeError, native_v1_objectives.ObjectivesError) as error:
        errors.append(f"objectives verifier failed closed: {type(error).__name__}: {error}")

    summary = artifact.get("summary", {})
    owner = artifact.get("owner_boundary", {})
    if artifact.get("status") != "owner_direction_accepted_signature_pending":
        errors.append("objectives do not record owner direction with signature still pending")
    if artifact.get("selected_move_id") != "N0-OBJECTIVES-001":
        errors.append("objectives readiness does not bind N0-OBJECTIVES-001")
    if summary.get("consistency_pass") is not True:
        errors.append("objectives consistency check did not pass")
    if summary.get("target_count") != 38 or summary.get("measured_target_count") != 0:
        errors.append("objectives readiness must bind 38 candidate and zero measured targets")
    if summary.get("negative_control_count") != 10 or summary.get("negative_control_pass_count") != 10:
        errors.append("objectives negative-control inventory is incomplete")
    if owner.get("ratification_required") is not True or owner.get("ready_for_owner_review") is not False:
        errors.append("objectives owner-direction boundary is inconsistent")
    if owner.get("profile_accepted") is not True or owner.get("target_values_accepted") is not True:
        errors.append("objectives readiness omits the recorded owner direction")
    if owner.get("cryptographic_signature_present") is not False or owner.get("ready_for_signature") is not False:
        errors.append("objectives readiness overclaims signature readiness")
    if artifact.get("n0_6_exit_gate_satisfied") is not False:
        errors.append("objectives readiness overclaims the N0.6 exit gate")
    if artifact.get("production_ready") is not False or artifact.get("production_promotion_allowed") is not False:
        errors.append("objectives readiness overclaims production promotion")

    detail = (
        f"profile={artifact.get('profile_id')}; targets={summary.get('target_count')}; "
        f"measured={summary.get('measured_target_count')}; "
        f"negatives={summary.get('negative_control_pass_count')}/{summary.get('negative_control_count')}; "
        "owner_direction=true; signature=false; n0_6_exit=false; production_promotion_allowed=false"
    )
    return readiness.make_check(
        "native_v1_objectives_readiness",
        not errors,
        detail if not errors else "; ".join(errors[:8]),
    )


def check_adr_ratification_readiness(path: Path = ADR_RATIFICATION_READINESS) -> dict:
    artifact, schema_errors = _load_schema_artifact(path, "adr-ratification-readiness.schema.json")
    errors = [f"ratification readiness {error.path}: {error.message}" for error in schema_errors[:8]]
    if not isinstance(artifact, dict):
        return readiness.make_check(
            "adr_ratification_readiness",
            False,
            "; ".join(errors) or "ADR ratification readiness is not an object",
        )

    try:
        regenerated = adr_ratification.build_readiness(ROOT)
        if path.read_bytes() != adr_ratification.canonical_json_bytes(regenerated):
            errors.append("readiness ledger is not the exact deterministic regeneration")
        receipt = adr_ratification.build_receipt(ROOT, observed_at_utc="1970-01-01T00:00:00Z")
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        errors.append(f"ratification verifier failed closed: {type(error).__name__}: {error}")
        receipt = {"status": "invalid", "production_promotion_allowed": False}

    if artifact.get("status") != "owner_direction_recorded_hardware_key_pending":
        errors.append("current readiness status does not preserve the owner-direction and unavailable-key boundary")
    if artifact.get("selected_move_id") != "N0-RATIFY-001":
        errors.append("readiness does not bind N0-RATIFY-001")
    if artifact.get("production_ready") is not False or artifact.get("production_promotion_allowed") is not False:
        errors.append("readiness overclaims production or architecture promotion")
    adr_set = artifact.get("adr_set", {})
    if adr_set.get("required_count") != 7 or adr_set.get("present_count") != 7:
        errors.append("readiness does not bind all seven ADRs")
    if adr_set.get("pending_owner_disposition") != []:
        errors.append("readiness still reports an owner ADR disposition as pending")
    if adr_set.get("accepted_owner_directed_count") != 7 or adr_set.get("proposed_count") != 0:
        errors.append("readiness does not record all seven owner-directed ADR statuses")
    if adr_set.get("cryptographically_ratified_count") != 0:
        errors.append("readiness overclaims cryptographic ADR ratification")
    trust = artifact.get("trust_bootstrap", {})
    if trust.get("trusted_signer_count") != 0 or trust.get("signer_file_errors") != []:
        errors.append("current public trust bootstrap does not match the deliberate zero-signer state")
    if (
        trust.get("selected_key_profile") != "hardware_fido2_ed25519_sk"
        or trust.get("hardware_key_availability") != "do_not_have"
        or trust.get("hardware_key_available") is not False
        or trust.get("key_generation_authorized") is not False
    ):
        errors.append("ratification readiness does not preserve the selected unavailable hardware-key boundary")
    summary = artifact.get("summary", {})
    if summary.get("ready_for_owner_action") is not True or summary.get("ready_for_signature") is not False:
        errors.append("readiness owner/signature boundary is inconsistent")
    if summary.get("defined_negative_control_count") != 12:
        errors.append("ratification negative-control inventory is incomplete")
    if summary.get("blocking_owner_action_count") != 4:
        errors.append("ratification owner-action inventory is incomplete")
    if summary.get("owner_direction_recorded") is not True:
        errors.append("ratification readiness omits the completed owner direction")
    decision_inputs = artifact.get("decision_inputs", {})
    objectives = decision_inputs.get("objectives", {})
    if decision_inputs.get("required_bound_source_count") != 6 or len(decision_inputs.get("bound_sources", [])) != 6:
        errors.append("ratification readiness does not bind the exact six-source decision set")
    if objectives.get("profile_id") != "POOLEOS-WORKSTATION-V1-CANDIDATE":
        errors.append("ratification readiness does not bind the candidate Workstation v1 profile")
    if objectives.get("target_count") != 38 or objectives.get("measured_target_count") != 0:
        errors.append("ratification readiness must retain 38 candidate and zero measured targets")
    if objectives.get("owner_ratification_pending") is not False:
        errors.append("ratification readiness still reports objectives owner direction as pending")
    if receipt.get("status") == "invalid":
        errors.append("live ratification verifier reports an invalid partial ceremony")
    if (
        receipt.get("status") != "pending_owner_action"
        or receipt.get("production_promotion_allowed") is not False
        or receipt.get("architecture_ratification_verified") is not False
    ):
        errors.append("current live ratification state is not a bounded non-promoting owner-action wait")

    for binding in [
        artifact.get("policy", {}),
        *adr_set.get("adrs", []),
        *decision_inputs.get("bound_sources", []),
    ]:
        relative = binding.get("path")
        if not isinstance(relative, str):
            errors.append("ratification binding is missing a relative path")
            continue
        try:
            bound = (ROOT / relative).resolve()
            bound.relative_to(ROOT.resolve())
        except ValueError:
            errors.append(f"ratification binding escapes repository: {relative}")
            continue
        if not bound.is_file():
            errors.append(f"ratification-bound file is missing: {relative}")
            continue
        data = bound.read_bytes()
        if hashlib.sha256(data).hexdigest().upper() != binding.get("sha256") or len(data) != binding.get("byte_count"):
            errors.append(f"ratification binding mismatch: {relative}")

    detail = (
        "policy=scope_hardened; adrs=7; proposed=0; owner_directed=7; bound_sources=6; objectives=38; measured=0; "
        "trusted_signers=0; negative_controls=12; owner_actions=4; status=owner_direction_recorded_hardware_key_pending; "
        "production_promotion_allowed=false"
    )
    return readiness.make_check(
        "adr_ratification_readiness",
        not errors,
        detail if not errors else "; ".join(errors[:8]),
    )


def check_n0_owner_decision_packet(path: Path = N0_OWNER_DECISION_PACKET) -> dict:
    artifact, schema_errors = _load_schema_artifact(path, "n0-owner-decision-packet.schema.json")
    errors = [f"N0 owner packet {error.path}: {error.message}" for error in schema_errors[:8]]
    if not isinstance(artifact, dict):
        return readiness.make_check(
            "n0_owner_decision_packet",
            False,
            "; ".join(errors) or "N0 owner decision packet is not an object",
        )

    try:
        regenerated = n0_owner_decision_packet.build_packet(ROOT)
        if path.read_bytes() != n0_owner_decision_packet.canonical_json_bytes(regenerated):
            errors.append("packet is not the exact deterministic regeneration")
        errors.extend(n0_owner_decision_packet.packet_rejection_reasons(artifact, ROOT))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        errors.append(f"packet verifier failed closed: {type(error).__name__}: {error}")

    current = artifact.get("current_state", {})
    decisions = artifact.get("decisions", {})
    objectives = decisions.get("objectives", {})
    custody = decisions.get("custody", {})
    validation = artifact.get("validation", {})
    if artifact.get("status") != "awaiting_owner_response":
        errors.append("packet must remain awaiting_owner_response")
    if current.get("pending_owner_action_count") != 6:
        errors.append("packet must retain all six pending owner actions")
    if current.get("objective_target_count") != 38 or current.get("measured_target_count") != 0:
        errors.append("packet must bind 38 targets and zero measurements")
    if objectives.get("selection") != n0_owner_decision_packet.UNSELECTED:
        errors.append("packet inferred an objectives disposition")
    if custody.get("selection") != n0_owner_decision_packet.UNSELECTED:
        errors.append("packet inferred a custody profile")
    if validation.get("negative_control_pass_count") != 12:
        errors.append("packet negative controls are incomplete")
    for field in ("owner_acceptance_recorded", "signature_authorized", "publication_authorized", "production_promotion_allowed"):
        if artifact.get(field) is not False:
            errors.append(f"packet overclaims {field}")

    detail = (
        f"sources={artifact.get('source_set', {}).get('binding_count')}; "
        f"targets={current.get('objective_target_count')}; measured={current.get('measured_target_count')}; "
        f"owner_actions={current.get('pending_owner_action_count')}; "
        f"negatives={validation.get('negative_control_pass_count')}/{validation.get('negative_control_count')}; "
        "acceptance=false; signing=false; publication=false; promotion=false"
    )
    return readiness.make_check(
        "n0_owner_decision_packet",
        not errors,
        detail if not errors else "; ".join(dict.fromkeys(errors))[:2000],
    )


def check_n0_owner_response_receipt(path: Path = N0_OWNER_RESPONSE_RECEIPT) -> dict:
    artifact, schema_errors = _load_schema_artifact(path, "n0-owner-response-receipt.schema.json")
    errors = [f"N0 owner response receipt {error.path}: {error.message}" for error in schema_errors[:8]]
    if not isinstance(artifact, dict):
        return readiness.make_check(
            "n0_owner_response_receipt",
            False,
            "; ".join(errors) or "N0 owner response receipt is not an object",
        )

    try:
        response = json.loads((ROOT / n0_owner_response.RESPONSE_RELATIVE).read_text(encoding="utf-8"))
        errors.extend(n0_owner_response.response_rejection_reasons(response, ROOT))
        regenerated = n0_owner_response.build_receipt(ROOT)
        if path.read_bytes() != n0_owner_response.canonical_json_bytes(regenerated):
            errors.append("owner response receipt is not the exact deterministic regeneration")
        errors.extend(n0_owner_response.receipt_rejection_reasons(artifact, ROOT))
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        errors.append(f"owner response verifier failed closed: {type(error).__name__}: {error}")

    decisions = artifact.get("accepted_decisions", {})
    objectives = decisions.get("objectives", {})
    custody = decisions.get("custody", {})
    state = artifact.get("effective_source_state", {})
    trust = artifact.get("trust_state", {})
    execution = artifact.get("execution_boundary", {})
    validation = artifact.get("validation", {})
    if artifact.get("status") != "owner_direction_recorded_hardware_key_unavailable":
        errors.append("owner response receipt has the wrong bounded status")
    if artifact.get("selected_move_id") != "N0-OWNER-RESPONSE-001":
        errors.append("owner response receipt does not bind N0-OWNER-RESPONSE-001")
    if objectives.get("target_count") != 38 or objectives.get("measured_target_count") != 0:
        errors.append("owner response must accept 38 definitions and zero measurements")
    if objectives.get("definition_acceptance_recorded") is not True or objectives.get("measurement_evidence_accepted") is not False:
        errors.append("owner response confuses definition acceptance with measurement acceptance")
    if custody.get("selected_profile") != "hardware_fido2_ed25519_sk":
        errors.append("owner response does not preserve the selected governance-key profile")
    if custody.get("hardware_key_availability") != "do_not_have" or custody.get("provisional_software_key_risk") != "not_applicable":
        errors.append("owner response custody selections are inconsistent")
    if state.get("all_selected_source_dispositions_recorded") is not True:
        errors.append("selected ADR or objectives source disposition is not recorded")
    if trust.get("hardware_key_available") is not False or trust.get("trusted_signer_count") != 0:
        errors.append("owner response receipt overclaims hardware-key or signer availability")
    if any(value is not False for value in execution.values()):
        errors.append("owner response receipt authorizes a separately gated action")
    if validation.get("negative_control_count") != 16 or validation.get("negative_control_pass_count") != 16:
        errors.append("owner response receipt does not retain all 16 fail-closed controls")
    if artifact.get("production_ready") is not False or artifact.get("production_promotion_allowed") is not False:
        errors.append("owner response receipt overclaims production promotion")

    detail = (
        "response=complete_unsigned; adrs=2/2 owner-directed; objective_definitions=38; measured=0; "
        "profile=hardware_fido2_ed25519_sk; hardware_available=false; signers=0; negatives=16/16; "
        "key_generation=false; signing=false; merge=false; tagging=false; publication=false; promotion=false"
    )
    return readiness.make_check(
        "n0_owner_response_receipt",
        not errors,
        detail if not errors else "; ".join(dict.fromkeys(errors))[:2000],
    )


def check_native_toolchain_qualification(path: Path = NATIVE_TOOLCHAIN_QUALIFICATION) -> dict:
    artifact, schema_errors = _load_schema_artifact(path, "native-toolchain-qualification.schema.json")
    errors = [f"qualification {error.path}: {error.message}" for error in schema_errors[:8]]
    if not isinstance(artifact, dict):
        return readiness.make_check(
            "native_toolchain_qualification",
            False,
            "; ".join(errors) or "native toolchain qualification is not an object",
        )

    if artifact.get("status") != "pass_single_windows_host_non_promoting":
        errors.append("qualification status is not the bounded one-host pass state")
    if artifact.get("production_ready") is not False or artifact.get("production_promotion_allowed") is not False:
        errors.append("qualification overclaims production promotion")
    scope = artifact.get("scope", {})
    if scope.get("host_environment_count") != 1 or scope.get("two_host_reproduction_complete") is not False:
        errors.append("qualification does not preserve the one-host/two-host-open boundary")
    if scope.get("functional_boot_tested") is not False or scope.get("kernel_execution_tested") is not False:
        errors.append("qualification overclaims boot or kernel execution")

    for key in ("toolchain_lock", "target_contract"):
        binding = artifact.get("bindings", {}).get(key, {})
        relative = binding.get("path")
        if not isinstance(relative, str):
            errors.append(f"{key} binding has no relative path")
            continue
        bound = ROOT / relative
        try:
            bound.resolve().relative_to(ROOT.resolve())
        except ValueError:
            errors.append(f"{key} binding escapes the repository")
            continue
        if not bound.is_file():
            errors.append(f"{key} binding is missing")
            continue
        data = bound.read_bytes()
        if hashlib.sha256(data).hexdigest().upper() != binding.get("sha256") or len(data) != binding.get("byte_count"):
            errors.append(f"{key} binding does not match the current file")

    expected_targets = {"x86_64-unknown-uefi": "PE32+", "x86_64-unknown-none": "ELF64"}
    builds = artifact.get("builds", [])
    if {item.get("target_triple") for item in builds if isinstance(item, dict)} != set(expected_targets):
        errors.append("qualification target set is not exactly UEFI and freestanding x86-64")
    for build in builds:
        if not isinstance(build, dict):
            errors.append("qualification build entry is not an object")
            continue
        inspection = build.get("inspection", {})
        expected_format = expected_targets.get(build.get("target_triple"))
        if inspection.get("format") != expected_format:
            errors.append(f"{build.get('target_triple')} inspection format mismatch")
        if len(set(build.get("run_sha256", []))) != 1 or len(set(build.get("run_byte_count", []))) != 1:
            errors.append(f"{build.get('target_triple')} clean runs are not identical")
        if build.get("exact_byte_match") is not True or build.get("binary_contract_pass") is not True:
            errors.append(f"{build.get('target_triple')} build evidence does not pass")
        if build.get("host_leakage_hit_count") != 0:
            errors.append(f"{build.get('target_triple')} contains host leakage")
    controls = artifact.get("negative_controls", [])
    if len(controls) != 3 or any(item.get("status") != "pass" for item in controls if isinstance(item, dict)):
        errors.append("qualification negative controls are incomplete")
    summary = artifact.get("summary", {})
    if summary.get("fixture_count") != 2 or summary.get("byte_identical_fixture_count") != 2:
        errors.append("qualification fixture summary is incomplete")
    if summary.get("binary_contract_pass_count") != 2 or summary.get("host_leakage_hit_count") != 0:
        errors.append("qualification contract/leakage summary does not pass")

    detail = (
        "Rust 1.97.0; UEFI PE32+ and freestanding ELF64; clean_runs=2+2; "
        "byte_identical=2/2; host_leaks=0; negatives=3/3; two_host=false; non_promoting=true"
    )
    return readiness.make_check(
        "native_toolchain_qualification",
        not errors,
        detail if not errors else "; ".join(errors[:8]),
    )


def check_hardware_target_readiness(path: Path = HARDWARE_TARGET_READINESS) -> dict:
    artifact, artifact_schema_errors = _load_schema_artifact(path, "hardware-target-readiness.schema.json")
    errors = [f"hardware readiness {error.path}: {error.message}" for error in artifact_schema_errors[:8]]
    if not isinstance(artifact, dict):
        return readiness.make_check(
            "hardware_target_readiness",
            False,
            "; ".join(errors) or "hardware target readiness is not an object",
        )
    try:
        regenerated = hardware_target.build_readiness(ROOT)
        if path.read_bytes() != hardware_target.canonical_json_bytes(regenerated):
            errors.append("hardware readiness is not the exact deterministic regeneration")
    except (OSError, ValueError, KeyError, json.JSONDecodeError, hardware_target.HardwareEvidenceError) as error:
        errors.append(f"hardware readiness verifier failed closed: {type(error).__name__}: {error}")

    summary = artifact.get("summary", {})
    verification = artifact.get("target_verification", {})
    if artifact.get("status") != "consistent_partial_non_promoting":
        errors.append("current hardware readiness status is not consistent_partial_non_promoting")
    if artifact.get("selected_move_id") != "N2-HW-002":
        errors.append("hardware readiness does not bind N2-HW-002")
    if artifact.get("production_ready") is not False or artifact.get("production_promotion_allowed") is not False:
        errors.append("hardware readiness overclaims production promotion")
    if artifact.get("n2_exit_gate_satisfied") is not False:
        errors.append("hardware readiness overclaims the N2 exit gate")
    if summary.get("consistency_pass") is not True:
        errors.append("hardware readiness consistency does not pass")
    if summary.get("schema_failure_count") != 0 or summary.get("privacy_violation_count") != 0:
        errors.append("hardware readiness schema or privacy validation failed")
    if summary.get("required_target_check_count") != 24 or summary.get("matched_required_target_check_count") != 24:
        errors.append("exact Tier 1 required identity checks do not all match")
    if verification.get("required_failure_count") != 0:
        errors.append("exact Tier 1 verification records a required failure")
    if summary.get("pending_evidence_channel_count") != 7:
        errors.append("hardware evidence-channel gap count changed without gate review")
    if summary.get("partial_evidence_channel_count") != 2 or summary.get("cpuid_record_count") != 16:
        errors.append("hardware readiness does not bind the bounded partial CPUID evidence")
    if summary.get("pending_lab_safety_count") != 10:
        errors.append("hardware lab-safety gap count changed without owner review")
    if summary.get("unresolved_standard_count", 0) < 1:
        errors.append("standards register unexpectedly claims complete exact-document locks")
    if summary.get("negative_control_count") != 14 or summary.get("negative_control_pass_count") != 14:
        errors.append("hardware readiness negative controls are incomplete")
    cpu_components = artifact.get("evidence_coverage", {}).get("cpu_architecture_components", {})
    if (
        cpu_components.get("cpuid_status") != "observed"
        or cpu_components.get("cpuid_record_count") != 16
        or cpu_components.get("cpuid_affinity_policy") != "lowest_process_allowed_logical_processor_restored_per_query"
        or cpu_components.get("msr_status") != "pending_reviewed_privileged_mechanism"
        or cpu_components.get("combined_channel_complete") is not False
    ):
        errors.append("hardware CPU architecture component boundary is inconsistent")

    detail = (
        "target=TIER1-B650M-9800X3D-RTX5070-001; identity=24/24; privacy=0; "
        "cpuid=16; msr=pending; pending_channels=7; partial_channels=2; negatives=14/14; "
        "pending_safety=10; n2_exit=false; production_promotion_allowed=false"
    )
    return readiness.make_check(
        "hardware_target_readiness",
        not errors,
        detail if not errors else "; ".join(errors[:8]),
    )


def check_native_tier0_readiness(path: Path = NATIVE_TIER0_READINESS) -> dict:
    artifact, artifact_schema_errors = _load_schema_artifact(path, "native-tier0-readiness.schema.json")
    errors = [f"Tier 0 readiness {error.path}: {error.message}" for error in artifact_schema_errors[:8]]
    if not isinstance(artifact, dict):
        return readiness.make_check(
            "native_tier0_readiness",
            False,
            "; ".join(errors) or "native Tier 0 readiness is not an object",
        )
    errors.extend(native_tier0.readiness_contract_errors(artifact, ROOT))
    candidate = artifact.get("candidate", {})
    tree = candidate.get("runtime_tree", {})
    capabilities = candidate.get("capabilities", {})
    if tree.get("file_count") != 3368 or tree.get("byte_count") != 1180772298:
        errors.append("qualified QEMU runtime closure count or size changed")
    if tree.get("tree_sha256") != "A4CAF423F71E629B839298B35CAE17995865298CF7B29B16C0DD75437B6C0971":
        errors.append("qualified QEMU runtime closure hash changed")
    if not all(capabilities.get(key) is True for key in ("pc_q35_11_0", "q35_alias", "virtio_blk_non_transitional", "isa_debug_exit")):
        errors.append("required q35/VIRTIO/debug-exit capability probe is incomplete")
    profile_checks = artifact.get("profile_checks", [])
    if [item.get("profile_id") for item in profile_checks if isinstance(item, dict)] != list(native_tier0.PROFILE_IDS):
        errors.append("Tier 0 profile set changed")
    if any(
        item.get("command_generation_exact_match") is not True
        or item.get("qmp_summary_exact_match") is not True
        or item.get("machine_instantiation_pass") is not True
        or item.get("guest_cpu_execution_started") is not False
        or item.get("boot_claimed") is not False
        for item in profile_checks
        if isinstance(item, dict)
    ):
        errors.append("Tier 0 profile evidence does not preserve the paused non-boot boundary")
    detail = (
        "profile=POOLEOS-TIER0-Q35-1; qemu=11.0.0-candidate; q35=pc-q35-11.0; "
        "profiles=2/2; paused_qmp=4/4; negatives=18/18; paths=0; boot_claims=0; "
        "formal_models=0; n4_exit=false; production_promotion_allowed=false"
    )
    return readiness.make_check(
        "native_tier0_readiness",
        not errors,
        detail if not errors else "; ".join(errors[:8]),
    )


def check_native_model_readiness(path: Path = NATIVE_MODEL_READINESS) -> dict:
    artifact, artifact_schema_errors = _load_schema_artifact(path, "native-model-readiness.schema.json")
    errors = [f"native model readiness {error.path}: {error.message}" for error in artifact_schema_errors[:8]]
    if not isinstance(artifact, dict):
        return readiness.make_check(
            "native_model_readiness",
            False,
            "; ".join(errors) or "native model readiness is not an object",
        )
    errors.extend(native_models.readiness_contract_errors(artifact, ROOT))
    summary = artifact.get("summary", {})
    coverage = artifact.get("domain_coverage", {})
    runs = artifact.get("runs", [])
    if [item.get("id") for item in runs if isinstance(item, dict)] != list(native_models.RUN_IDS):
        errors.append("bounded model run set changed")
    if summary.get("safe_run_pass_count") != 6 or summary.get("hostile_counterexample_count") != 21:
        errors.append("safe or hostile model evidence is incomplete")
    if summary.get("repeat_match_count") != 27 or summary.get("negative_control_pass_count") != 31:
        errors.append("model determinism or negative controls are incomplete")
    if coverage.get("modeled_count") != 7 or coverage.get("open_count") != 0:
        errors.append("bounded model domain coverage changed")
    if summary.get("implementation_trace_cross_check_count") != 0:
        errors.append("implementation trace cross-check is overclaimed")
    if artifact.get("n4_model_slice_satisfied") is not True or artifact.get("n4_exit_gate_satisfied") is not False:
        errors.append("N4 model-slice or exit boundary changed")
    detail = (
        "contract=POOLEOS-N4-MODELS-5; models=6; safe=6/6; counterexamples=21/21; "
        "repeats=27/27; negatives=31/31; domains=7/7; trace_cross_checks=0/6; "
        "formal_proof=false; n4_exit=false; production_promotion_allowed=false"
    )
    return readiness.make_check(
        "native_model_readiness",
        not errors,
        detail if not errors else "; ".join(errors[:8]),
    )


def check_native_boot_trust_readiness(path: Path = NATIVE_BOOT_TRUST_READINESS) -> dict:
    artifact, artifact_schema_errors = _load_schema_artifact(
        path, "native-boot-trust-readiness.schema.json"
    )
    errors = [
        f"native boot trust readiness {error.path}: {error.message}"
        for error in artifact_schema_errors[:8]
    ]
    if not isinstance(artifact, dict):
        return readiness.make_check(
            "native_boot_trust_readiness",
            False,
            "; ".join(errors) or "native boot trust readiness is not an object",
        )
    errors.extend(native_boot_trust.readiness_errors(artifact, ROOT))
    build = artifact.get("build", {})
    differential = artifact.get("differential", {})
    development = artifact.get("development_integration", {})
    controls = artifact.get("negative_controls", [])
    if (
        build.get("rust_host_tests_passed") != 12
        or build.get("rust_host_tests_total") != 12
        or build.get("pooleboot_uefi_integration_builds_passed") != 1
        or build.get("pooleboot_uefi_integration_builds_total") != 1
    ):
        errors.append("PBTRUST1 build evidence is incomplete")
    if any(
        differential.get(name, {}).get("cases") != 8192
        or differential.get(name, {}).get("mismatches") != 0
        for name in (
            "policy_parser",
            "state_parser",
            "authorization",
            "backend_selection",
        )
    ):
        errors.append("PBTRUST1 differential evidence is incomplete")
    if len(controls) != 105 or any(item.get("status") != "pass" for item in controls):
        errors.append("PBTRUST1 hostile-control evidence is incomplete")
    expected_development = {
        "policy_bytes": 320,
        "state_bytes": 256,
        "binding_count": 14,
        "denial_count": 1,
        "denial": "pbtrust_policy_unsigned",
        "state_source": "esp_candidate_not_persistent_authority",
        "state_authenticated": False,
        "state_monotonic": False,
        "state_backend_writable": False,
        "signature_verifications": 0,
        "authority_grants": 0,
        "state_writes": 0,
    }
    if development != expected_development:
        errors.append("PBTRUST1 development-denial boundary changed")
    backend = artifact.get("backend_model", {})
    power_loss = backend.get("power_loss", {})
    if (
        backend.get("contract_id") != "PBSTATE1"
        or backend.get("selected_copy") != 0
        or backend.get("anchored_copy_mask") != 3
        or backend.get("repair_copy_mask") != 0
        or backend.get("migration_required") is not True
        or backend.get("next_generation") != 2
        or backend.get("target_copy") != 1
        or backend.get("authority_grants") != 0
        or backend.get("state_writes_performed") != 0
        or backend.get("anchor_writes_performed") != 0
        or power_loss.get("case_count") != 9
        or power_loss.get("all_cases_passed") is not True
        or power_loss.get("storage_io_performed") is not False
        or power_loss.get("anchor_writes_performed") != 0
        or power_loss.get("state_writes_performed") != 0
    ):
        errors.append("PBSTATE1 backend-model evidence is incomplete")
    if artifact.get("claims") != native_boot_trust.expected_claims():
        errors.append("PBTRUST1 claim boundary changed")
    if artifact.get("production_ready") is not False:
        errors.append("PBTRUST1 overclaims production readiness")
    detail = (
        "contract=PBTRUST1/PBSTATE1; rust_tests=12/12; uefi_integration=1/1; "
        "controls=105/105; differential=32768; power_loss=9/9; bindings=14; "
        "denial=pbtrust_policy_unsigned; backend_crypto=false; backend_io=false; "
        "policy_signature=false; state_authenticated=false; state_monotonic=false; "
        "state_backend_writable=false; authority=0; state_writes=0; production_ready=false"
    )
    return readiness.make_check(
        "native_boot_trust_readiness",
        not errors,
        detail if not errors else "; ".join(errors[:8]),
    )


def check_native_pooleboot_readiness(path: Path = NATIVE_POOLEBOOT_READINESS) -> dict:
    artifact, artifact_schema_errors = _load_schema_artifact(path, "native-pooleboot-readiness.schema.json")
    errors = [f"native PooleBoot readiness {error.path}: {error.message}" for error in artifact_schema_errors[:8]]
    if not isinstance(artifact, dict):
        return readiness.make_check(
            "native_pooleboot_readiness",
            False,
            "; ".join(errors) or "native PooleBoot readiness is not an object",
        )
    errors.extend(native_pooleboot.readiness_contract_errors(artifact, ROOT))
    expected_summary = {
        "host_contract_tests_total": 8,
        "host_contract_tests_passed": 8,
        "clean_builds_exact": 2,
        "clean_media_generations_exact": 2,
        "guest_runs_total": 2,
        "guest_runs_passed": 2,
        "ordered_marker_count": 25,
        "serial_debugcon_match_count": 2,
        "gop_frame_match_count": 2,
        "negative_controls_total": 155,
        "negative_controls_passed": 155,
        "inner_set_artifact_count": 6,
        "inner_set_parser_count": 6,
        "inner_set_cross_binding_count": 6,
        "inner_set_development_denial_count": 6,
        "inner_set_retained_set_sha256": "C46B9030922FB095F5321CD62CD4930B812B2D8D8EA58B93B7C51956B6EEC8B8",
        "inner_set_authority_grants": 0,
        "inner_set_actions_authorized": 0,
        "inner_set_state_writes": 0,
        "inner_set_hardware_observations": 0,
        "microcode_patch_count": 2,
        "microcode_payload_profile": "synthetic_test_only_never_apply",
        "firmware_component_count": 3,
        "firmware_dependency_count": 2,
        "firmware_manifest_profile": "synthetic_qualification_never_apply",
        "policy_capability_rule_count": 11,
        "policy_mode_count": 6,
        "policy_profile": "synthetic_qualification_only",
        "trust_binding_count": 14,
        "trust_denial": "pbtrust_policy_unsigned",
        "trust_policy_sha256": "0A464E3019C064D04062EAB179C903BCE5DF7C2321E75ABAA6C3A8F3A8DA1884",
        "trust_state_sha256": "924D5DA41A5743FB68A42164839031FF9927732E4D2690B3DE092813B84608D8",
        "trust_authority_grants": 0,
        "trust_state_writes": 0,
        "production_claim_count": 0,
    }
    if artifact.get("summary") != expected_summary:
        errors.append("PooleBoot proof summary changed")
    if artifact.get("claims") != native_pooleboot.expected_claims():
        errors.append("PooleBoot proof claim boundary changed")
    if artifact.get("n5_exit_gate_satisfied") is not False or artifact.get("production_ready") is not False:
        errors.append("PooleBoot proof overclaims N5 exit or production readiness")
    detail = (
        "contract=POOLEOS-N5-POOLEBOOT-7; host_tests=8/8; builds=2/2; media=2/2; "
        "guest_runs=2/2; markers=25; serial_debugcon=2/2; gop_frames=2/2; "
        "retained_files=9; inner=6/6; inner_sha256=C46B9030922FB095; authority=0; actions=0; state=0; hardware=0; "
        "trust=unsigned-deny; trust_bindings=14; trust_authority=0; trust_writes=0; "
        "pbp1=2/2; kmap=2/2; exit=2/2; negatives=155/155; pmcu1=synthetic-never-apply; pfwm1=synthetic-never-apply; ppol1=qualification-only; production_claims=0; n5_exit=false; production_ready=false"
    )
    return readiness.make_check(
        "native_pooleboot_readiness",
        not errors,
        detail if not errors else "; ".join(errors[:8]),
    )


def check_native_kernel_load_readiness(path: Path = NATIVE_KERNEL_LOAD_READINESS) -> dict:
    artifact, artifact_schema_errors = _load_schema_artifact(
        path, "native-kernel-load-readiness.schema.json"
    )
    errors = [
        f"native kernel load readiness {error.path}: {error.message}"
        for error in artifact_schema_errors[:8]
    ]
    if not isinstance(artifact, dict):
        return readiness.make_check(
            "native_kernel_load_readiness",
            False,
            "; ".join(errors) or "native kernel load readiness is not an object",
        )
    errors.extend(native_kernel_load.readiness_errors(artifact, ROOT))
    summary = artifact.get("summary", {})
    if summary.get("guest_runs_passed") != 2 or summary.get("guest_runs_total") != 2:
        errors.append("PKLOAD6 guest-run evidence is incomplete")
    if summary.get("rust_host_tests_passed") != 109 or summary.get("rust_host_tests_total") != 109:
        errors.append("PKLOAD6 Rust host-test evidence is incomplete")
    if summary.get("ordered_marker_count") != 25:
        errors.append("PKLOAD6 marker evidence is incomplete")
    if summary.get("exact_pbp1_match_count") != 2:
        errors.append("PKLOAD6 PBP1 evidence is incomplete")
    if summary.get("oracle_match_count") != 2:
        errors.append("PKLOAD6 PKMAP2/PBEXIT1 oracle evidence is incomplete")
    if summary.get("negative_controls_passed") != 155 or summary.get(
        "negative_controls_total"
    ) != 155:
        errors.append("PKLOAD6 negative controls are incomplete")
    if summary.get("inner_retained_set_sha256") != (
        "C46B9030922FB095F5321CD62CD4930B812B2D8D8EA58B93B7C51956B6EEC8B8"
    ):
        errors.append("PKLOAD6 retained inner-set identity changed")
    if artifact.get("claims") != native_kernel_load.expected_claims():
        errors.append("PKLOAD6 claim boundary changed")
    if artifact.get("n5_exit_gate_satisfied") is not False or artifact.get(
        "production_ready"
    ) is not False:
        errors.append("PKLOAD6 overclaims N5 exit or production readiness")
    detail = (
        "contract=PKLOAD6; rust_tests=109/109; boot_builds=2/2; kernel_builds=2/2; "
        "media=2/2; guest_runs=2/2; markers=25; retained_files=9; inner=6/6; "
        "inner_sha256=C46B9030922FB095; "
        "trust=unsigned-deny; trust_bindings=14; trust_authority=0; trust_writes=0; "
        "oracle=2/2; pbp1=2/2; kmap=2/2; exit=2/2; firmware_after_exit=0; "
        "negatives=155/155; pmcu1=synthetic-never-apply; pfwm1=synthetic-never-apply; "
        "ppol1=qualification-only; transfer=false; n5_exit=false; production_ready=false"
    )
    return readiness.make_check(
        "native_kernel_load_readiness",
        not errors,
        detail if not errors else "; ".join(errors[:8]),
    )


def check_native_kernel_revalidation_readiness(
    path: Path = NATIVE_KERNEL_REVALIDATION_READINESS,
) -> dict:
    artifact, artifact_schema_errors = _load_schema_artifact(
        path, "native-kernel-revalidation-readiness.schema.json"
    )
    errors = [
        f"native kernel revalidation readiness {error.path}: {error.message}"
        for error in artifact_schema_errors[:8]
    ]
    if not isinstance(artifact, dict):
        return readiness.make_check(
            "native_kernel_revalidation_readiness",
            False,
            "; ".join(errors) or "native kernel revalidation readiness is not an object",
        )
    errors.extend(native_kernel_revalidation.readiness_errors(artifact, ROOT))
    build = artifact.get("build", {})
    if not isinstance(build, dict) or build.get("host_test_count") != 24:
        errors.append("PKREVAL1 host-test evidence is incomplete")
    controls = artifact.get("negative_controls", [])
    if (
        not isinstance(controls, list)
        or len(controls) != 36
        or any(not isinstance(item, dict) or item.get("status") != "pass" for item in controls)
    ):
        errors.append("PKREVAL1 hostile controls are incomplete")
    differential = artifact.get("differential", {})
    if not isinstance(differential, dict) or (
        differential.get("case_count"),
        differential.get("reject_count"),
        differential.get("role_coverage"),
    ) != (32_768, 32_768, 9):
        errors.append("PKREVAL1 differential evidence is incomplete")
    golden = artifact.get("golden", {})
    if not isinstance(golden, dict) or (
        golden.get("retained_file_count"),
        golden.get("parser_count"),
        golden.get("retained_set_sha256"),
        golden.get("denial"),
        golden.get("authority_grants"),
        golden.get("actions_authorized"),
        golden.get("state_writes"),
        golden.get("rust_python_match"),
    ) != (
        9,
        9,
        "C46B9030922FB095F5321CD62CD4930B812B2D8D8EA58B93B7C51956B6EEC8B8",
        "pbtrust_policy_unsigned",
        0,
        0,
        0,
        True,
    ):
        errors.append("PKREVAL1 golden evidence changed")
    if artifact.get("claims") != native_kernel_revalidation.expected_claims():
        errors.append("PKREVAL1 claim boundary changed")
    if artifact.get("production_ready") is not False or artifact.get(
        "production_promotion_allowed"
    ) is not False:
        errors.append("PKREVAL1 overclaims production readiness")
    detail = (
        "contract=PKREVAL1; kernel_tests=24/24; python_tests=8/8; targets=2/2; "
        "retained_files=9; parsers=9; controls=36/36; differential=32768/32768; "
        "denial=pbtrust_policy_unsigned; authority=0; actions=0; state_writes=0; "
        "live_kernel_entry=false; production_ready=false"
    )
    return readiness.make_check(
        "native_kernel_revalidation_readiness",
        not errors,
        detail if not errors else "; ".join(errors[:8]),
    )


def check_native_kernel_transfer_readiness(
    path: Path = NATIVE_KERNEL_TRANSFER_READINESS,
) -> dict:
    artifact, artifact_schema_errors = _load_schema_artifact(
        path, "native-kernel-transfer-readiness.schema.json"
    )
    errors = [
        f"native kernel transfer readiness {error.path}: {error.message}"
        for error in artifact_schema_errors[:8]
    ]
    if not isinstance(artifact, dict):
        return readiness.make_check(
            "native_kernel_transfer_readiness",
            False,
            "; ".join(errors) or "native kernel transfer readiness is not an object",
        )
    errors.extend(native_kernel_transfer.readiness_errors(artifact, ROOT))
    summary = artifact.get("summary", {})
    if not isinstance(summary, dict) or (
        summary.get("marker_count"),
        summary.get("kernel_marker_count"),
        summary.get("retained_file_count"),
        summary.get("negative_controls_passed"),
        summary.get("signature_verifications"),
        summary.get("authority_grants"),
        summary.get("actions_authorized"),
        summary.get("state_writes"),
        summary.get("firmware_calls_after_exit"),
    ) != (30, 5, 9, 58, 0, 0, 0, 0, 0):
        errors.append("PKXFER1 summary changed")
    execution = artifact.get("execution", {})
    runs = execution.get("runs", []) if isinstance(execution, dict) else []
    if (
        len(runs) != 2
        or any(
            not isinstance(run, dict)
            or run.get("serial_debugcon_exact_match") is not True
            or run.get("pbp1_serial_debugcon_exact_match") is not True
            or run.get("marker_summary", {}).get("kernel_terminal", {}).get("terminal") != "halt"
            or run.get("independent_kernel_revalidation", {}).get("guest_host_exact_match") is not True
            for run in runs
        )
    ):
        errors.append("PKXFER1 live run evidence is incomplete")
    build = artifact.get("build", {})
    if (
        not isinstance(build, dict)
        or build.get("development_transfer_feature") is not True
        or build.get("default_feature_enabled") is not False
        or build.get("default_stop_marker_present") is not True
        or build.get("default_transfer_marker_absent") is not True
    ):
        errors.append("PKXFER1 feature isolation changed")
    if artifact.get("claims") != native_kernel_transfer.expected_claims():
        errors.append("PKXFER1 claim boundary changed")
    detail = (
        "contract=PKXFER1; feature=development-transfer; default_transfer=false; "
        "qemu_runs=2/2; markers=30/30; kernel_markers=5/5; channels=2/2; "
        "pbp1=2/2; pkreval_files=9; controls=58/58; terminal=unsigned-denial-halt; "
        "signatures=0; authority=0; actions=0; writes=0; firmware_after_exit=0; "
        "target_firmware=false; physical_media=false; n5_exit=false; production_ready=false"
    )
    return readiness.make_check(
        "native_kernel_transfer_readiness",
        not errors,
        detail if not errors else "; ".join(errors[:8]),
    )


def check_native_kernel_trap_readiness(
    path: Path = NATIVE_KERNEL_TRAP_READINESS,
) -> dict:
    artifact, artifact_schema_errors = _load_schema_artifact(
        path, "native-kernel-trap-readiness.schema.json"
    )
    errors = [
        f"native kernel trap readiness {error.path}: {error.message}"
        for error in artifact_schema_errors[:8]
    ]
    if not isinstance(artifact, dict):
        return readiness.make_check(
            "native_kernel_trap_readiness",
            False,
            "; ".join(errors) or "native kernel trap readiness is not an object",
        )
    errors.extend(native_kernel_trap.readiness_errors(artifact, ROOT))
    summary = artifact.get("summary", {})
    if not isinstance(summary, dict) or tuple(
        summary.get(key)
        for key in (
            "scenario_count",
            "qemu_run_count",
            "returning_exception_count",
            "terminal_double_fault_count",
            "malformed_frame_rejection_count",
            "negative_controls_passed",
        )
    ) != (3, 6, 3, 1, 1, 51):
        errors.append("PKTRAP1 summary changed")
    execution = artifact.get("execution", {})
    scenarios = execution.get("scenarios", []) if isinstance(execution, dict) else []
    if (
        len(scenarios) != 3
        or sum(item.get("run_count", 0) for item in scenarios if isinstance(item, dict)) != 6
        or any(
            not isinstance(item, dict)
            or item.get("exact_marker_match") is not True
            or item.get("exact_screenshot_match") is not True
            or item.get("exact_pbp1_match") is not True
            or any(
                run.get("serial_debugcon_exact_match") is not True
                or run.get("pbp1_serial_debugcon_exact_match") is not True
                or run.get("independent_kernel_revalidation", {}).get("guest_host_exact_match")
                is not True
                for run in item.get("runs", [])
                if isinstance(run, dict)
            )
            for item in scenarios
        )
    ):
        errors.append("PKTRAP1 live scenario evidence is incomplete")
    build = artifact.get("build", {})
    kernel_product = build.get("kernel_entry", {}).get("product", {}) if isinstance(build, dict) else {}
    if (
        not isinstance(build, dict)
        or build.get("profile_count") != 4
        or build.get("all_profile_binaries_distinct") is not True
        or build.get("default_stop_marker_present") is not True
        or build.get("default_transfer_marker_absent") is not True
        or kernel_product.get("canonical_sha256")
        != "21DCC577077DEC8CF26764CE83BAAB89DFD43B750DA75F19E12E8F3A58E13B40"
        or kernel_product.get("relocation_count") != 333
    ):
        errors.append("PKTRAP1 build or feature isolation changed")
    if artifact.get("claims") != native_kernel_trap.expected_claims():
        errors.append("PKTRAP1 claim boundary changed")
    detail = (
        "contract=PKTRAP1; bsp=1; profiles=4/4; qemu_scenarios=3/3; qemu_runs=6/6; "
        "returning_vectors=3,6,14; double_fault=1/1; malformed_semantic=1/1; "
        "gdt=loaded; tss=loaded; idt_gates=5; ist=2; controls=51/51; channels=2/2; "
        "interrupts=false; authority=0; all_vectors=false; guarded_ist=false; "
        "per_cpu=false; n7_exit=false; production_ready=false"
    )
    return readiness.make_check(
        "native_kernel_trap_readiness",
        not errors,
        detail if not errors else "; ".join(errors[:8]),
    )


def check_native_kernel_cpu_policy_readiness(
    path: Path = NATIVE_KERNEL_CPU_POLICY_READINESS,
) -> dict:
    artifact, artifact_schema_errors = _load_schema_artifact(
        path, "native-kernel-cpu-policy-readiness.schema.json"
    )
    errors = [
        f"native kernel CPU policy readiness {error.path}: {error.message}"
        for error in artifact_schema_errors[:8]
    ]
    if not isinstance(artifact, dict):
        return readiness.make_check(
            "native_kernel_cpu_policy_readiness",
            False,
            "; ".join(errors) or "native kernel CPU policy readiness is not an object",
        )
    errors.extend(native_kernel_cpu_policy.readiness_errors(artifact, ROOT))
    summary = artifact.get("summary", {})
    if not isinstance(summary, dict) or tuple(
        summary.get(key)
        for key in (
            "qemu_run_count",
            "marker_count",
            "negative_controls_passed",
            "msr_read_count",
            "state_writes",
            "authority_grants",
        )
    ) != (2, 35, 41, 5, 0, 0):
        errors.append("PKCPU1 summary changed")
    execution = artifact.get("execution", {})
    runs = execution.get("runs", []) if isinstance(execution, dict) else []
    if (
        len(runs) != 2
        or execution.get("cpu_model") != "qemu64"
        or execution.get("acceleration") != "tcg_single_thread"
        or any(
            not isinstance(run, dict)
            or run.get("serial_debugcon_exact_match") is not True
            or run.get("pbp1_serial_debugcon_exact_match") is not True
            or run.get("independent_kernel_revalidation", {}).get("guest_host_exact_match")
            is not True
            for run in runs
        )
    ):
        errors.append("PKCPU1 live observation evidence is incomplete")
    build = artifact.get("build", {})
    source_audit = build.get("source_audit", {}) if isinstance(build, dict) else {}
    if (
        not isinstance(build, dict)
        or build.get("profile_count") != 2
        or build.get("all_profile_binaries_distinct") is not True
        or build.get("default_stop_marker_present") is not True
        or build.get("default_transfer_marker_absent") is not True
        or source_audit.get("forbidden_instruction_hits") != []
        or source_audit.get("result") != "pass_no_cpu_state_write_instruction"
    ):
        errors.append("PKCPU1 build, isolation, or no-write audit changed")
    if artifact.get("claims") != native_kernel_cpu_policy.expected_claims():
        errors.append("PKCPU1 claim boundary changed")
    detail = (
        "contract=PKCPU1; profile=qemu64; bsp=1; runs=2/2; markers=35/35; "
        "controls=41/41; cpuid=observed; cr0_cr4_efer=read_only; msrs=5/5; "
        "writes=0; authority=0; target_cpu=false; errata=false; xsave_ownership=false; "
        "n7_exit=false; production_ready=false"
    )
    return readiness.make_check(
        "native_kernel_cpu_policy_readiness",
        not errors,
        detail if not errors else "; ".join(errors[:8]),
    )


def check_native_initial_system_readiness(
    path: Path = NATIVE_INITIAL_SYSTEM_READINESS,
) -> dict:
    artifact, artifact_schema_errors = _load_schema_artifact(
        path, "native-initial-system-readiness.schema.json"
    )
    errors = [
        f"native initial system readiness {error.path}: {error.message}"
        for error in artifact_schema_errors[:8]
    ]
    if not isinstance(artifact, dict):
        return readiness.make_check(
            "native_initial_system_readiness",
            False,
            "; ".join(errors) or "native initial system readiness is not an object",
        )
    errors.extend(native_initial_system.readiness_errors(artifact))
    expected_summary = {
        "development_activation_denied": True,
        "differential_fuzz_cases": 16_384,
        "differential_mismatches": 0,
        "golden_vectors_matched": 3,
        "golden_vectors_total": 3,
        "negative_controls_passed": 120,
        "negative_controls_total": 120,
        "no_std_target_builds_passed": 2,
        "no_std_target_builds_total": 2,
        "production_claim_count": 0,
        "rust_host_tests_passed": 3,
        "rust_host_tests_total": 3,
        "synthetic_activation_passed": True,
    }
    if artifact.get("summary") != expected_summary:
        errors.append("PINIT1 readiness summary changed")
    if artifact.get("claims") != native_initial_system.expected_claims():
        errors.append("PINIT1 claim boundary changed")
    if artifact.get("n5_exit_gate_satisfied") is not False or artifact.get(
        "production_ready"
    ) is not False:
        errors.append("PINIT1 overclaims N5 exit or production readiness")
    detail = (
        "contract=PINIT1; rust_tests=3/3; no_std_targets=2/2; golden=3/3; "
        "negatives=120/120; differential=16384; mismatches=0; development_activation=false; "
        "pooleboot_enforcement=false; poolekernel_activation=false; n5_exit=false; production_ready=false"
    )
    return readiness.make_check(
        "native_initial_system_readiness",
        not errors,
        detail if not errors else "; ".join(errors[:8]),
    )


def check_native_recovery_readiness(
    path: Path = NATIVE_RECOVERY_READINESS,
) -> dict:
    artifact, artifact_schema_errors = _load_schema_artifact(
        path, "native-recovery-readiness.schema.json"
    )
    errors = [
        f"native recovery readiness {error.path}: {error.message}"
        for error in artifact_schema_errors[:8]
    ]
    if not isinstance(artifact, dict):
        return readiness.make_check(
            "native_recovery_readiness",
            False,
            "; ".join(errors) or "native recovery readiness is not an object",
        )
    errors.extend(native_recovery.readiness_errors(artifact, ROOT))
    expected_summary = {
        "development_activation_denied": True,
        "differential_mismatches": 0,
        "golden_vectors_matched": 3,
        "golden_vectors_total": 3,
        "negative_controls_passed": 144,
        "negative_controls_total": 144,
        "no_std_target_builds_passed": 2,
        "no_std_target_builds_total": 2,
        "parser_differential_cases": 16_384,
        "production_claim_count": 0,
        "rust_host_tests_passed": 3,
        "rust_host_tests_total": 3,
        "transition_differential_cases": 8_192,
    }
    if artifact.get("summary") != expected_summary:
        errors.append("PREC1 readiness summary changed")
    if artifact.get("claims") != native_recovery.expected_claims():
        errors.append("PREC1 claim boundary changed")
    if artifact.get("n5_exit_gate_satisfied") is not False or artifact.get(
        "production_ready"
    ) is not False:
        errors.append("PREC1 overclaims N5 exit or production readiness")
    detail = (
        "contract=PREC1; rust_tests=3/3; no_std_targets=2/2; golden=3/3; "
        "negatives=144/144; parser_state_differential=16384; transition_differential=8192; "
        "mismatches=0; development_activation=false; state_checksum_auth=false; "
        "pooleboot_enforcement=false; poolekernel_execution=false; n5_exit=false; production_ready=false"
    )
    return readiness.make_check(
        "native_recovery_readiness",
        not errors,
        detail if not errors else "; ".join(errors[:8]),
    )


def check_native_symbol_readiness(
    path: Path = NATIVE_SYMBOL_READINESS,
) -> dict:
    artifact, artifact_schema_errors = _load_schema_artifact(
        path, "native-symbol-readiness.schema.json"
    )
    errors = [
        f"native symbol readiness {error.path}: {error.message}"
        for error in artifact_schema_errors[:8]
    ]
    if not isinstance(artifact, dict):
        return readiness.make_check(
            "native_symbol_readiness",
            False,
            "; ".join(errors) or "native symbol readiness is not an object",
        )
    errors.extend(native_symbols.readiness_errors(artifact, ROOT))
    expected_summary = {
        "debug_reproducible_builds": 2,
        "differential_mismatches": 0,
        "golden_vectors_matched": 3,
        "golden_vectors_total": 3,
        "lookup_differential_cases": 16_384,
        "negative_controls_passed": 158,
        "negative_controls_total": 158,
        "no_std_target_builds_passed": 2,
        "no_std_target_builds_total": 2,
        "parser_differential_cases": 16_384,
        "production_claim_count": 0,
        "public_symbols": 3,
        "rust_host_tests_passed": 4,
        "rust_host_tests_total": 4,
    }
    if artifact.get("summary") != expected_summary:
        errors.append("PSYM1 readiness summary changed")
    expected_claims = {
        "format_frozen": True,
        "python_oracle_implemented": True,
        "no_std_parser_implemented": True,
        "bounded_lookup_implemented": True,
        "split_debug_correspondence_qualified": True,
        "development_activation_denied": True,
        "symbol_consumption_enabled": False,
        "pooleboot_enforced": False,
        "poolekernel_enforced": False,
        "kernel_export_authority_created": False,
        "full_debug_file_on_boot_media": False,
        "runtime_addresses_disclosed_by_default": False,
        "n5_exit_gate_satisfied": False,
        "production_ready": False,
    }
    if artifact.get("claims") != expected_claims:
        errors.append("PSYM1 claim boundary changed")
    detail = (
        "contract=PSYM1; rust_tests=4/4; no_std_targets=2/2; golden=3/3; "
        "negatives=158/158; parser_differential=16384; lookup_differential=16384; "
        "debug_builds=2; public_symbols=3; mismatches=0; consumption=false; "
        "n5_exit=false; production_ready=false"
    )
    return readiness.make_check(
        "native_symbol_readiness",
        not errors,
        detail if not errors else "; ".join(errors[:8]),
    )


def check_native_microcode_readiness(
    path: Path = NATIVE_MICROCODE_READINESS,
) -> dict:
    artifact, artifact_schema_errors = _load_schema_artifact(
        path, "native-microcode-readiness.schema.json"
    )
    errors = [
        f"native microcode readiness {error.path}: {error.message}"
        for error in artifact_schema_errors[:8]
    ]
    if not isinstance(artifact, dict):
        return readiness.make_check(
            "native_microcode_readiness",
            False,
            "; ".join(errors) or "native microcode readiness is not an object",
        )
    errors.extend(native_microcode.readiness_errors(artifact, ROOT))
    expected_summary = {
        "differential_mismatches": 0,
        "golden_vectors_matched": 3,
        "golden_vectors_total": 3,
        "negative_controls_passed": 174,
        "negative_controls_total": 174,
        "no_std_target_builds_passed": 2,
        "no_std_target_builds_total": 2,
        "parser_differential_cases": 16_384,
        "post_apply_differential_cases": 8_192,
        "production_claim_count": 0,
        "production_vendor_payload_count": 0,
        "rust_host_tests_passed": 4,
        "rust_host_tests_total": 4,
        "selection_differential_cases": 16_384,
        "synthetic_payload_count": 35,
    }
    if artifact.get("summary") != expected_summary:
        errors.append("PMCU1 readiness summary changed")
    expected_claims = {
        "bounded_selection_implemented": True,
        "development_activation_denied": True,
        "format_frozen": True,
        "microcode_applied": False,
        "n5_exit_gate_satisfied": False,
        "no_std_parser_implemented": True,
        "pooleboot_enforced": False,
        "poolekernel_enforced": False,
        "post_apply_verification_model_implemented": True,
        "privileged_revision_observed": False,
        "production_ready": False,
        "python_oracle_implemented": True,
        "vendor_container_parser_implemented": False,
        "vendor_payload_included": False,
    }
    if artifact.get("claims") != expected_claims:
        errors.append("PMCU1 claim boundary changed")
    detail = (
        "contract=PMCU1; rust_tests=4/4; no_std_targets=2/2; golden=3/3; "
        "negatives=174/174; parser_differential=16384; selection_differential=16384; "
        "post_apply_differential=8192; mismatches=0; payloads=synthetic_only; "
        "revision_probe=false; apply=false; n5_exit=false; production_ready=false"
    )
    return readiness.make_check(
        "native_microcode_readiness",
        not errors,
        detail if not errors else "; ".join(errors[:8]),
    )


def check_native_firmware_readiness(
    path: Path = NATIVE_FIRMWARE_READINESS,
) -> dict:
    artifact, artifact_schema_errors = _load_schema_artifact(
        path, "native-firmware-readiness.schema.json"
    )
    errors = [
        f"native firmware readiness {error.path}: {error.message}"
        for error in artifact_schema_errors[:8]
    ]
    if not isinstance(artifact, dict):
        return readiness.make_check(
            "native_firmware_readiness",
            False,
            "; ".join(errors) or "native firmware readiness is not an object",
        )
    errors.extend(native_firmware.readiness_errors(artifact, ROOT))
    if len(artifact.get("negative_controls", [])) != 101:
        errors.append("PFWM1 negative-control count changed")
    differential = artifact.get("differential", {})
    if sum(item.get("cases", 0) for item in differential.values()) != 32_768:
        errors.append("PFWM1 differential case count changed")
    if artifact.get("payloads", {}).get("embedded_payload_count") != 0:
        errors.append("PFWM1 unexpectedly embeds firmware payload bytes")
    detail = (
        "contract=PFWM1; rust_tests=5/5; no_std_targets=2/2; golden=3/3; "
        "negatives=101/101; parser_differential=16384; activation_differential=8192; "
        "post_reset_differential=8192; mismatches=0; embedded_payloads=0; "
        "live_inventory=false; apply=false; production_ready=false"
    )
    return readiness.make_check(
        "native_firmware_readiness",
        not errors,
        detail if not errors else "; ".join(errors[:8]),
    )


def check_native_policy_readiness(
    path: Path = NATIVE_POLICY_READINESS,
) -> dict:
    artifact, artifact_schema_errors = _load_schema_artifact(
        path, "native-policy-readiness.schema.json"
    )
    errors = [
        f"native policy readiness {error.path}: {error.message}"
        for error in artifact_schema_errors[:8]
    ]
    if not isinstance(artifact, dict):
        return readiness.make_check(
            "native_policy_readiness",
            False,
            "; ".join(errors) or "native policy readiness is not an object",
        )
    errors.extend(native_policy.readiness_errors(artifact, ROOT))
    if len(artifact.get("negative_controls", [])) != 116:
        errors.append("PPOL1 negative-control count changed")
    differential = artifact.get("differential", {})
    if sum(item.get("cases", 0) for item in differential.values()) != 32_768:
        errors.append("PPOL1 differential case count changed")
    activation = artifact.get("activation", {})
    if activation.get("development_allowed") is not False:
        errors.append("PPOL1 development activation boundary changed")
    detail = (
        "contract=PPOL1; rust_tests=6/6; no_std_targets=2/2; golden=3/3; "
        "negatives=116/116; parser_differential=8192; cross_binding=4096; "
        "activation_differential=12288; receipt_differential=8192; mismatches=0; "
        "live_enforcement=false; authority_created=false; production_ready=false"
    )
    return readiness.make_check(
        "native_policy_readiness",
        not errors,
        detail if not errors else "; ".join(errors[:8]),
    )


def check_native_system_manifest_readiness(
    path: Path = NATIVE_SYSTEM_MANIFEST_READINESS,
) -> dict:
    artifact, artifact_schema_errors = _load_schema_artifact(
        path, "native-system-manifest-readiness.schema.json"
    )
    errors = [
        f"native system manifest readiness {error.path}: {error.message}"
        for error in artifact_schema_errors[:8]
    ]
    if not isinstance(artifact, dict):
        return readiness.make_check(
            "native_system_manifest_readiness",
            False,
            "; ".join(errors) or "native system manifest readiness is not an object",
        )
    errors.extend(native_system_manifest.readiness_errors(artifact, ROOT))
    expected_summary = {
        "differential_cases": 16384,
        "digest_cases": 1027,
        "golden_vectors_passed": 3,
        "golden_vectors_total": 3,
        "mismatch_count": 0,
        "negative_controls_passed": 64,
        "negative_controls_total": 64,
        "no_std_target_builds_passed": 2,
        "no_std_target_builds_total": 2,
        "pooleboot_uefi_integration_builds_passed": 1,
        "pooleboot_uefi_integration_builds_total": 1,
        "production_claim_count": 0,
        "rust_host_tests_passed": 8,
        "rust_host_tests_total": 8,
    }
    if artifact.get("summary") != expected_summary:
        errors.append("PSM1 readiness summary changed")
    digest = artifact.get("digest_qualification", {})
    if digest.get("security_review_complete") is not False or digest.get(
        "provider_promotion_allowed"
    ) is not False:
        errors.append("PBDIGEST1 security-review boundary changed")
    if artifact.get("n5_exit_gate_satisfied") is not False or artifact.get(
        "production_ready"
    ) is not False:
        errors.append("PSM1 overclaims N5 exit or production readiness")
    detail = (
        "contract=PSM1; rust_tests=8/8; targets=2/2; pooleboot_integration=1/1; "
        "vectors=3/3; negatives=64/64; differential=16384; digest_cases=1027; "
        "mismatches=0; security_review=false; n5_exit=false; production_ready=false"
    )
    return readiness.make_check(
        "native_system_manifest_readiness",
        not errors,
        detail if not errors else "; ".join(errors[:8]),
    )


def check_native_boot_handoff_readiness(path: Path = NATIVE_BOOT_HANDOFF_READINESS) -> dict:
    artifact, artifact_schema_errors = _load_schema_artifact(path, "native-boot-handoff-readiness.schema.json")
    errors = [f"native boot handoff readiness {error.path}: {error.message}" for error in artifact_schema_errors[:8]]
    if not isinstance(artifact, dict):
        return readiness.make_check(
            "native_boot_handoff_readiness",
            False,
            "; ".join(errors) or "native boot handoff readiness is not an object",
        )
    errors.extend(native_boot_handoff.readiness_errors(artifact, ROOT))
    if artifact.get("summary") != {
        "rust_host_tests_passed": 8,
        "rust_host_tests_total": 8,
        "no_std_target_builds_passed": 2,
        "no_std_target_builds_total": 2,
        "layout_assertions_passed": 12,
        "golden_vectors_matched": 3,
        "golden_vectors_total": 3,
        "negative_controls_passed": 32,
        "negative_controls_total": 32,
        "differential_fuzz_cases": 16_384,
        "differential_mismatches": 0,
        "production_claim_count": 0,
    }:
        errors.append("PBP1 qualification summary changed")
    if artifact.get("claims") != native_boot_handoff.expected_claims():
        errors.append("PBP1 claim boundary changed")
    detail = (
        "contract=PBP1; rust_tests=8/8; no_std_targets=2/2; layouts=12; golden=3/3; "
        "negatives=32/32; fuzz=16384; mismatches=0; producer=false; consumer=false; "
        "n5_exit=false; production_ready=false"
    )
    return readiness.make_check(
        "native_boot_handoff_readiness",
        not errors,
        detail if not errors else "; ".join(errors[:8]),
    )


def check_native_boot_config_readiness(path: Path = NATIVE_BOOT_CONFIG_READINESS) -> dict:
    artifact, artifact_schema_errors = _load_schema_artifact(path, "native-boot-config-readiness.schema.json")
    errors = [f"native boot config readiness {error.path}: {error.message}" for error in artifact_schema_errors[:8]]
    if not isinstance(artifact, dict):
        return readiness.make_check(
            "native_boot_config_readiness",
            False,
            "; ".join(errors) or "native boot config readiness is not an object",
        )
    errors.extend(native_boot_config.readiness_errors(artifact, ROOT))
    if artifact.get("summary") != {
        "rust_host_tests_passed": 12,
        "rust_host_tests_total": 12,
        "no_std_target_builds_passed": 2,
        "no_std_target_builds_total": 2,
        "golden_vectors_matched": 3,
        "golden_vectors_total": 3,
        "negative_controls_passed": 64,
        "negative_controls_total": 64,
        "differential_fuzz_cases": 16_384,
        "differential_mismatches": 0,
        "production_claim_count": 0,
    }:
        errors.append("PBC1 qualification summary changed")
    if artifact.get("claims") != native_boot_config.expected_claims():
        errors.append("PBC1 claim boundary changed")
    detail = (
        "contract=PBC1; rust_tests=12/12; no_std_targets=2/2; golden=3/3; "
        "negative=64/64; fuzz=16384; mismatches=0; live_file=false; live_parse=false; "
        "n5_exit=false; production_ready=false"
    )
    return readiness.make_check(
        "native_boot_config_readiness",
        not errors,
        detail if not errors else "; ".join(errors[:8]),
    )


def check_native_elf_loader_readiness(path: Path = NATIVE_ELF_LOADER_READINESS) -> dict:
    artifact, artifact_schema_errors = _load_schema_artifact(path, "native-elf-loader-readiness.schema.json")
    errors = [f"native ELF loader readiness {error.path}: {error.message}" for error in artifact_schema_errors[:8]]
    if not isinstance(artifact, dict):
        return readiness.make_check(
            "native_elf_loader_readiness",
            False,
            "; ".join(errors) or "native ELF loader readiness is not an object",
        )
    errors.extend(native_elf_loader.readiness_errors(artifact))
    expected = {
        "rust_host_tests_passed": 12,
        "rust_host_tests_total": 12,
        "rustfmt_passed": 1,
        "clippy_runs_passed": 3,
        "clippy_runs_total": 3,
        "no_std_target_builds_passed": 2,
        "no_std_target_builds_total": 2,
        "pooleboot_integration_builds_passed": 2,
        "pooleboot_integration_builds_total": 2,
        "golden_vectors_matched": 3,
        "golden_vectors_total": 3,
        "exact_loaded_byte_vectors_matched": 3,
        "maximum_relocations_exercised": 4096,
        "negative_controls_passed": 129,
        "negative_controls_total": 129,
        "differential_fuzz_cases": 16_384,
        "differential_mismatches": 0,
        "production_claim_count": 0,
    }
    if artifact.get("summary") != expected:
        errors.append("PKELF1 qualification summary changed")
    if artifact.get("claims") != native_elf_loader.expected_claims():
        errors.append("PKELF1 claim boundary changed")
    detail = (
        "contract=PKELF1; rust_tests=12/12; no_std_targets=2/2; pooleboot_builds=2/2; "
        "golden=3/3; exact_loaded=3/3; maximum_relocations=4096; negative=129/129; "
        "fuzz=16384; mismatches=0; firmware_allocation=false; page_mapping=false; "
        "kernel_transfer=false; n5_exit=false; production_ready=false"
    )
    return readiness.make_check(
        "native_elf_loader_readiness",
        not errors,
        detail if not errors else "; ".join(errors[:8]),
    )


def check_native_kernel_entry_readiness(path: Path = NATIVE_KERNEL_ENTRY_READINESS) -> dict:
    artifact, artifact_schema_errors = _load_schema_artifact(path, "native-kernel-entry-readiness.schema.json")
    errors = [f"native kernel entry readiness {error.path}: {error.message}" for error in artifact_schema_errors[:8]]
    if not isinstance(artifact, dict):
        return readiness.make_check(
            "native_kernel_entry_readiness",
            False,
            "; ".join(errors) or "native kernel entry readiness is not an object",
        )
    errors.extend(native_kernel_entry.readiness_errors(artifact))
    expected_summary = {
        "rust_host_tests_passed": 24,
        "rust_host_tests_total": 24,
        "rustfmt_packages_passed": 2,
        "clippy_runs_passed": 2,
        "clippy_runs_total": 2,
        "clean_builds_matched": 2,
        "clean_builds_total": 2,
        "negative_controls_passed": 43,
        "negative_controls_total": 43,
        "exact_loaded_byte_implementations_matched": 2,
        "exact_loaded_byte_implementations_total": 2,
        "production_claim_count": 0,
    }
    if artifact.get("summary") != expected_summary:
        errors.append("PKENTRY1 qualification summary changed")
    product = artifact.get("product", {})
    if (
        product.get("canonical_byte_count") != 180_224
        or product.get("image_byte_count") != 262_144
        or product.get("entry_offset") != 0x8000
        or product.get("relocation_count") != 333
        or product.get("canonical_sha256")
        != "21DCC577077DEC8CF26764CE83BAAB89DFD43B750DA75F19E12E8F3A58E13B40"
    ):
        errors.append("PKENTRY1 product identity changed")
    if artifact.get("claims") != native_kernel_entry.expected_claims():
        errors.append("PKENTRY1 claim boundary changed")
    detail = (
        "contract=PKENTRY1; kernel_tests=24/24; clean_builds=2/2; negative=43/43; "
        "exact_loaded=2/2; bytes=180224; image_bytes=262144; entry=0x8000; "
        "relocations=333; live_transfer=false; "
        "target_execution=false; n6_exit=false; production_ready=false"
    )
    return readiness.make_check(
        "native_kernel_entry_readiness",
        not errors,
        detail if not errors else "; ".join(errors[:8]),
    )


def check_publication_boundary() -> dict:
    from tools import check_publication_boundary as publication

    try:
        report = publication.audit_git_index()
    except (OSError, RuntimeError, UnicodeError) as error:
        return readiness.make_check("publication_boundary", False, f"{type(error).__name__}: {error}")
    summary = report["summary"]
    return readiness.make_check(
        "publication_boundary",
        report["publication_allowed"],
        (
            f"status={report['status']}; indexed_paths={summary['indexed_path_count']}; "
            f"indexed_bytes={summary['indexed_byte_count']}; violations={summary['violation_count']}"
        ),
    )


def check_pdc_source_intake(path: Path) -> dict:
    from runtime import pdc_source_intake

    artifact, errors = _load_schema_artifact(path, "pdc-source-intake.schema.json")
    if artifact is None or errors:
        return readiness.make_check(
            "pdc_source_intake",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    copy_failures = []
    for source in artifact["designated_sources"]:
        stored = ROOT / source["stored_path"]
        if not stored.is_file() or pdc_source_intake.sha256_file(stored) != source["sha256"]:
            copy_failures.append(source["id"])
    summary = artifact["summary"]
    ok = (
        artifact.get("status") == "pass"
        and summary.get("locked_source_count") == 7
        and summary.get("verified_copy_count") == 7
        and summary.get("failed_count") == 0
        and artifact["scope"].get("raw_candidates_are_authoritative") is False
        and not copy_failures
    )
    return readiness.make_check(
        "pdc_source_intake",
        ok,
        (
            f"locked={summary.get('locked_source_count')}; verified={summary.get('verified_copy_count')}; "
            f"raw_indexed={summary.get('raw_candidate_count')}; raw_imported={summary.get('raw_imported_count')}; "
            f"bad_copies={len(copy_failures)}"
        ),
    )


def check_pdc_math_contract(path: Path, source_intake_path: Path) -> dict:
    from runtime import pdc_source_intake

    artifact, errors = _load_schema_artifact(path, "pdc-math-contract.schema.json")
    if artifact is None or errors:
        return readiness.make_check(
            "pdc_math_contract",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    intake, intake_errors = _load_schema_artifact(source_intake_path, "pdc-source-intake.schema.json")
    if intake is None or intake_errors:
        return readiness.make_check("pdc_math_contract", False, "source intake is missing or invalid")
    binding = artifact["source_binding"]
    source_bound = binding["artifact_sha256"] == pdc_source_intake.sha256_file(source_intake_path)
    source_set_bound = binding["designated_source_set_sha256"] == intake["digests"]["designated_source_set_sha256"]
    ok = (
        artifact.get("status") == "pass"
        and source_bound
        and source_set_bound
        and artifact["binary_model"].get("strain_is_not_acceptance_predicate") is True
        and artifact["variant_policy"].get("pmphi_is_distinct_model") is True
        and artifact["reference_oracles"].get("optimized_routes_must_match_both") is True
    )
    return readiness.make_check(
        "pdc_math_contract",
        ok,
        f"version={artifact.get('contract_version')}; intake_bound={source_bound}; source_set_bound={source_set_bound}",
    )


def check_pdc_golden_vectors(path: Path, math_contract_path: Path) -> dict:
    from runtime import pdc_source_intake

    artifact, errors = _load_schema_artifact(path, "pdc-golden-vectors.schema.json")
    if artifact is None or errors:
        return readiness.make_check(
            "pdc_golden_vectors",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    binding = artifact["math_contract_binding"]
    contract_bound = binding["artifact_sha256"] == pdc_source_intake.sha256_file(math_contract_path)
    summary = artifact["summary"]
    ok = (
        artifact.get("status") == "pass"
        and contract_bound
        and summary.get("failed_count") == 0
        and summary.get("case_count") == summary.get("passed_count")
        and summary.get("matrix_scalar_agreement_case_count", 0) > 0
    )
    return readiness.make_check(
        "pdc_golden_vectors",
        ok,
        (
            f"version={artifact.get('vector_set_version')}; contract_bound={contract_bound}; "
            f"cases={summary.get('passed_count')}/{summary.get('case_count')}; "
            f"matrix_scalar={summary.get('matrix_scalar_agreement_case_count')}"
        ),
    )


def check_pdc_verifier_intake(path: Path, source_intake_path: Path, math_contract_path: Path) -> dict:
    from runtime import pdc_verifier_intake

    artifact, errors = _load_schema_artifact(path, "pdc-verifier-intake.schema.json")
    if artifact is None or errors:
        return readiness.make_check(
            "pdc_verifier_intake",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )

    bindings = artifact["bindings"]
    source_bound = bindings["source_intake_sha256"] == pdc_verifier_intake.sha256_file(source_intake_path)
    contract_bound = bindings["math_contract_sha256"] == pdc_verifier_intake.sha256_file(math_contract_path)
    copy_failures = []
    for source in artifact["selected_sources"]:
        stored = ROOT / source["stored_path"]
        if not stored.is_file() or pdc_verifier_intake.sha256_file(stored) != source["sha256"]:
            copy_failures.append(source["id"])

    archives_ok = all(item.get("status") == "pass" for item in artifact["archive_security"])
    manifests_ok = all(item.get("failed_entry_count") == 0 for item in artifact["embedded_manifests"])
    lineage_ok = all(item.get("ok") is True for item in artifact["lineage_checks"])
    summary = artifact["summary"]
    ok = (
        artifact.get("status") == "pass_with_documented_erratum"
        and source_bound
        and contract_bound
        and archives_ok
        and manifests_ok
        and lineage_ok
        and not copy_failures
        and summary.get("selected_source_count") == 4
        and summary.get("verified_copy_count") == 4
        and summary.get("manifest_entry_count") == 46
        and summary.get("verified_manifest_entry_count") == 46
        and summary.get("failed_check_count") == 0
    )
    return readiness.make_check(
        "pdc_verifier_intake",
        ok,
        (
            f"source_bound={source_bound}; contract_bound={contract_bound}; "
            f"sources={summary.get('verified_copy_count')}/{summary.get('selected_source_count')}; "
            f"manifest_entries={summary.get('verified_manifest_entry_count')}/{summary.get('manifest_entry_count')}; "
            f"errata={summary.get('documented_erratum_count')}; bad_copies={len(copy_failures)}"
        ),
    )


def check_pdc_verifier_reproduction(path: Path, verifier_intake_path: Path, math_contract_path: Path) -> dict:
    from runtime import pdc_verifier_intake

    artifact, errors = _load_schema_artifact(path, "pdc-verifier-reproduction.schema.json")
    if artifact is None or errors:
        return readiness.make_check(
            "pdc_verifier_reproduction",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )

    intake, intake_errors = _load_schema_artifact(verifier_intake_path, "pdc-verifier-intake.schema.json")
    if intake is None or intake_errors:
        return readiness.make_check("pdc_verifier_reproduction", False, "verifier intake is missing or invalid")

    bindings = artifact["bindings"]
    intake_bound = bindings["verifier_intake_sha256"] == pdc_verifier_intake.sha256_file(verifier_intake_path)
    contract_bound = bindings["math_contract_sha256"] == pdc_verifier_intake.sha256_file(math_contract_path)
    source_set_bound = bindings["selected_source_set_sha256"] == intake["digests"]["selected_source_set_sha256"]
    output_failures = []
    execution_failures = []
    for execution in artifact["source_executions"]:
        if execution.get("return_code") != 0:
            execution_failures.append(execution["id"])
        for output in execution["required_outputs"]:
            preserved = ROOT / output["preserved_path"]
            if not preserved.is_file() or pdc_verifier_intake.sha256_file(preserved) != output["sha256"]:
                output_failures.append(output["id"])

    expected_families = {
        "rectangle": 841,
        "line_hole": 80,
        "arbitrary_mask": 720,
        "inversion": 1225,
        "solid_cuboid": 729,
        "surface_shell": 729,
    }
    actual_families = {item["id"]: item for item in artifact["family_results"]}
    families_ok = set(actual_families) == set(expected_families)
    for family_id, expected_count in expected_families.items():
        family = actual_families.get(family_id, {})
        families_ok = families_ok and all(
            family.get(field) == expected_count
            for field in (
                "declared_case_count",
                "published_case_count",
                "source_execution_case_count",
                "independent_case_count",
            )
        )
        families_ok = families_ok and family.get("status") == "pass"
        families_ok = families_ok and family.get("source_execution_canonical_lf_match") is True
        families_ok = families_ok and family.get("source_execution_raw_byte_match") is False
        families_ok = families_ok and all(
            family.get(field) == 0
            for field in (
                "source_execution_semantic_mismatch_count",
                "published_failed_case_count",
                "independent_source_mismatch_count",
                "formula_mismatch_count",
                "secondary_oracle_mismatch_count",
            )
        )

    summary = artifact["summary"]
    summary_ok = (
        summary.get("family_count") == 6
        and summary.get("declared_case_count") == 4324
        and summary.get("published_case_count") == 4324
        and summary.get("source_execution_case_count") == 4324
        and summary.get("independent_case_count") == 4324
        and summary.get("source_output_file_count") == 6
        and summary.get("exact_byte_match_file_count") == 0
        and summary.get("canonical_lf_match_file_count") == 6
        and summary.get("serialization_drift_file_count") == 6
        and summary.get("mismatch_count") == 0
        and summary.get("failed_family_count") == 0
        and summary.get("failed_check_count") == 0
    )
    ok = (
        artifact.get("status") == "pass_with_documented_serialization_drift"
        and intake_bound
        and contract_bound
        and source_set_bound
        and not execution_failures
        and not output_failures
        and families_ok
        and summary_ok
    )
    return readiness.make_check(
        "pdc_verifier_reproduction",
        ok,
        (
            f"intake_bound={intake_bound}; contract_bound={contract_bound}; source_set_bound={source_set_bound}; "
            f"families={summary.get('family_count')}; cases={summary.get('independent_case_count')}; "
            f"canonical_lf={summary.get('canonical_lf_match_file_count')}/{summary.get('source_output_file_count')}; "
            f"mismatches={summary.get('mismatch_count')}; bad_outputs={len(output_failures)}"
        ),
    )


def check_pdc_representation_contract(
    path: Path,
    math_contract_path: Path,
    golden_vectors_path: Path,
    verifier_reproduction_path: Path,
) -> dict:
    from runtime import pdc_verifier_intake

    artifact, errors = _load_schema_artifact(path, "pdc-representation-contract.schema.json")
    if artifact is None or errors:
        return readiness.make_check(
            "pdc_representation_contract",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    bindings = artifact["bindings"]
    implementation_bound = bindings["reference_implementation_sha256"] == pdc_verifier_intake.sha256_file(
        ROOT / bindings["reference_implementation_path"]
    )
    math_bound = bindings["math_contract_sha256"] == pdc_verifier_intake.sha256_file(math_contract_path)
    golden_bound = bindings["golden_vectors_sha256"] == pdc_verifier_intake.sha256_file(golden_vectors_path)
    verifier_bound = bindings["verifier_reproduction_sha256"] == pdc_verifier_intake.sha256_file(
        verifier_reproduction_path
    )
    representation_ids = {item["id"] for item in artifact["representations"]}
    conversion_ids = {item["id"] for item in artifact["conversion_paths"]}
    summary = artifact["summary"]
    ok = (
        artifact.get("status") == "pass"
        and artifact.get("abi_version") == "PDC-REP-0.1"
        and implementation_bound
        and math_bound
        and golden_bound
        and verifier_bound
        and representation_ids
        == {"dense_binary", "sparse_binary", "bitpacked_binary", "probability_field", "native_buffer_snapshot"}
        and len(conversion_ids) == summary.get("conversion_path_count") == 10
        and summary.get("representation_count") == 5
        and summary.get("native_dtype_count") == 2
        and summary.get("failure_mode_count") == 16
        and artifact["canonical_hash_contract"].get("native_padding_bytes_hashed") is False
    )
    return readiness.make_check(
        "pdc_representation_contract",
        ok,
        (
            f"version={artifact.get('abi_version')}; implementation_bound={implementation_bound}; "
            f"math_bound={math_bound}; golden_bound={golden_bound}; "
            f"verifier_bound={verifier_bound}; representations={summary.get('representation_count')}; "
            f"conversions={summary.get('conversion_path_count')}; failures={summary.get('failure_mode_count')}"
        ),
    )


def check_pdc_representation_receipt(
    path: Path,
    representation_contract_path: Path,
    math_contract_path: Path,
    golden_vectors_path: Path,
    verifier_reproduction_path: Path,
) -> dict:
    from runtime import pdc_verifier_intake

    artifact, errors = _load_schema_artifact(path, "pdc-representation-receipt.schema.json")
    if artifact is None or errors:
        return readiness.make_check(
            "pdc_representation_receipt",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    bindings = artifact["bindings"]
    implementation_bound = bindings["reference_implementation_sha256"] == pdc_verifier_intake.sha256_file(
        ROOT / bindings["reference_implementation_path"]
    )
    contract_bound = bindings["representation_contract_sha256"] == pdc_verifier_intake.sha256_file(
        representation_contract_path
    )
    math_bound = bindings["math_contract_sha256"] == pdc_verifier_intake.sha256_file(math_contract_path)
    golden_bound = bindings["golden_vectors_sha256"] == pdc_verifier_intake.sha256_file(golden_vectors_path)
    verifier_bound = bindings["verifier_reproduction_sha256"] == pdc_verifier_intake.sha256_file(
        verifier_reproduction_path
    )
    expected = {
        "rectangle": (841, 841, 0, "pass"),
        "line_hole": (80, 80, 0, "pass"),
        "arbitrary_mask": (720, 720, 0, "pass"),
        "inversion": (1225, 0, 1225, "excluded_non_field_formula_family"),
        "solid_cuboid": (729, 729, 0, "pass"),
        "surface_shell": (729, 729, 0, "pass"),
    }
    actual = {item["id"]: item for item in artifact["exact_family_results"]}
    families_ok = set(actual) == set(expected)
    for family_id, (declared, tested, excluded, status) in expected.items():
        item = actual.get(family_id, {})
        families_ok = families_ok and (
            item.get("declared_case_count") == declared
            and item.get("tested_case_count") == tested
            and item.get("excluded_case_count") == excluded
            and item.get("round_trip_count") == tested * 4
            and item.get("pdc_result_match_count") == tested
            and item.get("source_result_match_count") == declared
            and item.get("mismatch_count") == 0
            and item.get("status") == status
        )
    summary = artifact["summary"]
    negative_ok = len(artifact["negative_checks"]) == 13 and all(
        item.get("passed") is True for item in artifact["negative_checks"]
    )
    summary_ok = (
        summary.get("representation_count") == 5
        and summary.get("conversion_path_count") == 10
        and summary.get("golden_declared_case_count") == 13
        and summary.get("golden_applicable_case_count") == 10
        and summary.get("golden_excluded_formula_case_count") == 3
        and summary.get("exact_declared_case_count") == 4324
        and summary.get("exact_applicable_case_count") == 3099
        and summary.get("exact_excluded_formula_case_count") == 1225
        and summary.get("differential_case_count") == 3109
        and summary.get("round_trip_count") == 12436
        and summary.get("pdc_result_match_count") == 3109
        and summary.get("negative_check_count") == 13
        and summary.get("failed_negative_check_count") == 0
        and summary.get("mismatch_count") == 0
    )
    ok = (
        artifact.get("status") == "pass_with_explicit_formula_exclusions"
        and artifact.get("abi_version") == "PDC-REP-0.1"
        and implementation_bound
        and contract_bound
        and math_bound
        and golden_bound
        and verifier_bound
        and families_ok
        and negative_ok
        and summary_ok
        and artifact["probability_native_probe"].get("status") == "pass"
    )
    return readiness.make_check(
        "pdc_representation_receipt",
        ok,
        (
            f"implementation_bound={implementation_bound}; contract_bound={contract_bound}; "
            f"math_bound={math_bound}; golden_bound={golden_bound}; "
            f"verifier_bound={verifier_bound}; cases={summary.get('differential_case_count')}; "
            f"round_trips={summary.get('round_trip_count')}; pdc_matches={summary.get('pdc_result_match_count')}; "
            f"negative={summary.get('negative_check_count')}; mismatches={summary.get('mismatch_count')}"
        ),
    )


def check_pdc_golden_metamorphic_corpus(
    path: Path,
    math_contract_path: Path,
    predecessor_golden_path: Path,
    representation_contract_path: Path,
    representation_receipt_path: Path,
) -> dict:
    from runtime import pdc_verifier_intake

    artifact, errors = _load_schema_artifact(path, "pdc-golden-metamorphic-corpus.schema.json")
    if artifact is None or errors:
        return readiness.make_check(
            "pdc_golden_metamorphic_corpus",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    bindings = artifact["bindings"]
    implementation_path = ROOT / bindings["reference_implementation_path"]
    implementation_bound = (
        implementation_path.is_file()
        and bindings["reference_implementation_sha256"] == pdc_verifier_intake.sha256_file(implementation_path)
    )
    math_bound = bindings["math_contract_sha256"] == pdc_verifier_intake.sha256_file(math_contract_path)
    predecessor_bound = bindings["predecessor_golden_sha256"] == pdc_verifier_intake.sha256_file(
        predecessor_golden_path
    )
    representation_bound = bindings["representation_contract_sha256"] == pdc_verifier_intake.sha256_file(
        representation_contract_path
    )
    receipt_bound = bindings["representation_receipt_sha256"] == pdc_verifier_intake.sha256_file(
        representation_receipt_path
    )
    record_set = {
        "threshold_records": artifact["threshold_records"],
        "adversarial_records": artifact["adversarial_records"],
        "metamorphic_records": artifact["metamorphic_records"],
        "non_relations": artifact["non_relations"],
    }
    digest_bound = artifact["digests"]["record_set_sha256"] == pdc_verifier_intake.sha256_json(record_set)
    summary = artifact["summary"]
    summary_ok = (
        summary.get("threshold_pair_count") == 54
        and summary.get("adversarial_case_count") == 8
        and summary.get("translation_relation_count") == 32
        and summary.get("axis_permutation_relation_count") == 40
        and summary.get("metamorphic_relation_count") == 72
        and summary.get("non_relation_count") == 6
        and summary.get("published_record_count") == 140
    )
    ok = (
        artifact.get("status") == "published_expected"
        and implementation_bound
        and math_bound
        and predecessor_bound
        and representation_bound
        and receipt_bound
        and digest_bound
        and summary_ok
        and artifact["scope"].get("finite_verifier_not_all_size_theorem") is True
    )
    return readiness.make_check(
        "pdc_golden_metamorphic_corpus",
        ok,
        (
            f"implementation_bound={implementation_bound}; math_bound={math_bound}; "
            f"predecessor_bound={predecessor_bound}; representation_bound={representation_bound}; "
            f"receipt_bound={receipt_bound}; digest_bound={digest_bound}; "
            f"thresholds={summary.get('threshold_pair_count')}; relations={summary.get('metamorphic_relation_count')}; "
            f"non_relations={summary.get('non_relation_count')}"
        ),
    )


def check_pdc_golden_metamorphic_receipt(
    path: Path,
    corpus_path: Path,
    math_contract_path: Path,
    predecessor_golden_path: Path,
    representation_contract_path: Path,
    representation_receipt_path: Path,
) -> dict:
    from runtime import pdc_verifier_intake

    artifact, errors = _load_schema_artifact(path, "pdc-golden-metamorphic-receipt.schema.json")
    if artifact is None or errors:
        return readiness.make_check(
            "pdc_golden_metamorphic_receipt",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    bindings = artifact["bindings"]
    implementation_path = ROOT / bindings["verifier_implementation_path"]
    binding_checks = {
        "implementation": implementation_path.is_file()
        and bindings["verifier_implementation_sha256"] == pdc_verifier_intake.sha256_file(implementation_path),
        "corpus": bindings["corpus_sha256"] == pdc_verifier_intake.sha256_file(corpus_path),
        "math": bindings["math_contract_sha256"] == pdc_verifier_intake.sha256_file(math_contract_path),
        "predecessor": bindings["predecessor_golden_sha256"] == pdc_verifier_intake.sha256_file(
            predecessor_golden_path
        ),
        "representation": bindings["representation_contract_sha256"] == pdc_verifier_intake.sha256_file(
            representation_contract_path
        ),
        "representation_receipt": bindings["representation_receipt_sha256"] == pdc_verifier_intake.sha256_file(
            representation_receipt_path
        ),
    }
    summary = artifact["summary"]
    results = artifact["results"]
    summary_ok = (
        summary.get("threshold_pair_count") == 54
        and summary.get("adversarial_case_count") == 8
        and summary.get("metamorphic_relation_count") == 72
        and summary.get("non_relation_count") == 6
        and summary.get("oracle_field_evaluation_count") == 206
        and summary.get("representation_round_trip_count") == 824
        and summary.get("negative_check_count") == 10
        and summary.get("failed_negative_check_count") == summary.get("mismatch_count") == 0
    )
    results_ok = (
        results["threshold"].get("passed_count") == 54
        and results["adversarial"].get("passed_count") == 8
        and results["metamorphic"].get("passed_count") == 72
        and results["non_relations"].get("passed_count") == 6
        and all(result.get("mismatch_count") == 0 for result in results.values())
    )
    ok = artifact.get("status") == "pass" and all(binding_checks.values()) and summary_ok and results_ok
    return readiness.make_check(
        "pdc_golden_metamorphic_receipt",
        ok,
        (
            f"implementation_bound={binding_checks['implementation']}; corpus_bound={binding_checks['corpus']}; "
            f"math_bound={binding_checks['math']}; representation_bound={binding_checks['representation']}; "
            f"thresholds={summary.get('threshold_pair_count')}; relations={summary.get('metamorphic_relation_count')}; "
            f"round_trips={summary.get('representation_round_trip_count')}; negative={summary.get('negative_check_count')}; "
            f"mismatches={summary.get('mismatch_count')}"
        ),
    )


def check_pdc_qp_contract(
    path: Path,
    source_intake_path: Path,
    verifier_intake_path: Path,
    math_contract_path: Path,
) -> dict:
    from zipfile import ZipFile

    from runtime import pdc_verifier_intake

    artifact, errors = _load_schema_artifact(path, "pdc-qp-contract.schema.json")
    if artifact is None or errors:
        return readiness.make_check(
            "pdc_qp_contract",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    bindings = artifact["bindings"]
    implementation_path = ROOT / bindings["reference_implementation_path"]
    archive_binding = bindings["typed_case_archive"]
    archive_path = ROOT / archive_binding["stored_path"]
    binding_checks = {
        "implementation": implementation_path.is_file()
        and bindings["reference_implementation_sha256"] == pdc_verifier_intake.sha256_file(implementation_path),
        "source_intake": bindings["source_intake_sha256"] == pdc_verifier_intake.sha256_file(source_intake_path),
        "verifier_intake": bindings["verifier_intake_sha256"]
        == pdc_verifier_intake.sha256_file(verifier_intake_path),
        "math_contract": bindings["math_contract_sha256"] == pdc_verifier_intake.sha256_file(math_contract_path),
        "archive": archive_path.is_file()
        and archive_binding["sha256"] == pdc_verifier_intake.sha256_file(archive_path),
    }
    formula_source_checks = []
    for source in bindings["formula_sources"]:
        source_path = ROOT / source["stored_path"]
        formula_source_checks.append(
            source_path.is_file() and source["sha256"] == pdc_verifier_intake.sha256_file(source_path)
        )
    member_checks = []
    if binding_checks["archive"]:
        try:
            with ZipFile(archive_path) as archive:
                for member in bindings["typed_case_members"]:
                    payload = archive.read(member["member_path"])
                    member_checks.append(
                        pdc_verifier_intake.sha256_bytes(payload) == member["sha256"]
                        and len(payload) == member["size_bytes"]
                    )
        except Exception:
            member_checks.append(False)
    formula_digest_bound = artifact["digests"]["formula_source_set_sha256"] == pdc_verifier_intake.sha256_json(
        bindings["formula_sources"]
    )
    member_digest_bound = artifact["digests"]["typed_case_member_set_sha256"] == pdc_verifier_intake.sha256_json(
        bindings["typed_case_members"]
    )
    summary = artifact["summary"]
    summary_ok = (
        summary.get("feature_channel_count") == 10
        and summary.get("residue_channel_count") == 5
        and summary.get("probability_neighbor_count") == 26
        and summary.get("typed_case_family_count") == 5
        and summary.get("imported_typed_case_count") == 42
        and summary.get("formula_source_count") == 2
    )
    boundary_ok = (
        artifact["feature_contract"].get("collapsed_state_preserves_channel_identity") is False
        and artifact["feature_contract"].get("typed_and_collapsed_outputs_are_interchangeable") is False
        and artifact["cardinality_contract"].get(
            "routing_fanout_timing_reset_isolation_and_demultiplexing_proved"
        )
        is False
    )
    ok = (
        artifact.get("status") == "frozen_reference_contract"
        and all(binding_checks.values())
        and all(formula_source_checks)
        and len(member_checks) == 5
        and all(member_checks)
        and formula_digest_bound
        and member_digest_bound
        and summary_ok
        and boundary_ok
    )
    return readiness.make_check(
        "pdc_qp_contract",
        ok,
        (
            f"bindings={sum(binding_checks.values())}/{len(binding_checks)}; "
            f"formula_sources={sum(formula_source_checks)}/2; members={sum(member_checks)}/5; "
            f"formula_digest={formula_digest_bound}; member_digest={member_digest_bound}; "
            f"features={summary.get('feature_channel_count')}; typed_cases={summary.get('imported_typed_case_count')}; "
            f"collapsed_boundary={boundary_ok}"
        ),
    )


def check_pdc_qp_receipt(
    path: Path,
    contract_path: Path,
    source_intake_path: Path,
    verifier_intake_path: Path,
    math_contract_path: Path,
) -> dict:
    from runtime import pdc_qp
    from runtime import pdc_verifier_intake

    artifact, errors = _load_schema_artifact(path, "pdc-qp-receipt.schema.json")
    if artifact is None or errors:
        return readiness.make_check(
            "pdc_qp_receipt",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    bindings = artifact["bindings"]
    implementation_path = ROOT / bindings["reference_implementation_path"]
    evidence_path = ROOT / bindings["evidence_implementation_path"]
    archive_path = ROOT / bindings["typed_case_archive_path"]
    binding_checks = {
        "implementation": implementation_path.is_file()
        and bindings["reference_implementation_sha256"] == pdc_verifier_intake.sha256_file(implementation_path),
        "evidence": evidence_path.is_file()
        and bindings["evidence_implementation_sha256"] == pdc_verifier_intake.sha256_file(evidence_path),
        "contract": bindings["contract_sha256"] == pdc_verifier_intake.sha256_file(contract_path),
        "source_intake": bindings["source_intake_sha256"] == pdc_verifier_intake.sha256_file(source_intake_path),
        "verifier_intake": bindings["verifier_intake_sha256"]
        == pdc_verifier_intake.sha256_file(verifier_intake_path),
        "math_contract": bindings["math_contract_sha256"] == pdc_verifier_intake.sha256_file(math_contract_path),
        "archive": archive_path.is_file()
        and bindings["typed_case_archive_sha256"] == pdc_verifier_intake.sha256_file(archive_path),
    }
    digest_checks = {
        "feature": artifact["digests"]["feature_result_sha256"]
        == pdc_verifier_intake.sha256_json(artifact["feature_thresholds"]),
        "probability": artifact["digests"]["probability_result_sha256"]
        == pdc_verifier_intake.sha256_json(artifact["probability"]),
        "typed_cases": artifact["digests"]["typed_case_result_sha256"]
        == pdc_verifier_intake.sha256_json(artifact["typed_cases"]),
        "correlation": artifact["digests"]["correlation_result_sha256"]
        == pdc_verifier_intake.sha256_json(artifact["correlation_and_spectrometry"]),
        "negative": artifact["digests"]["negative_check_set_sha256"]
        == pdc_verifier_intake.sha256_json(artifact["negative_checks"]),
    }
    summary = artifact["summary"]
    probability_summary = artifact["probability"]["summary"]
    summary_ok = (
        summary.get("feature_threshold_case_count") == 54
        and summary.get("full_probability_case_count") == 10
        and summary.get("small_brute_force_case_count") == 12
        and summary.get("dp_polynomial_coefficient_check_count") == 270
        and summary.get("brute_force_coefficient_check_count") == 79
        and summary.get("derivative_oracle_check_count") == 260
        and summary.get("center_derivative_check_count") == 10
        and summary.get("finite_difference_check_count") == 104
        and summary.get("normalization_check_count") == 56
        and summary.get("typed_case_family_count") == 5
        and summary.get("imported_typed_case_count") == 42
        and summary.get("negative_check_count") == 16
        and summary.get("failed_negative_check_count") == summary.get("mismatch_count") == 0
    )
    numerical_ok = (
        probability_summary.get("max_dp_polynomial_abs_error", float("inf")) <= pdc_qp.FLOAT_ABS_TOLERANCE
        and probability_summary.get("max_brute_force_abs_error", float("inf")) <= 2e-12
        and probability_summary.get("max_derivative_oracle_abs_error", float("inf")) <= 2e-12
        and probability_summary.get("max_finite_difference_abs_error", float("inf")) <= 2e-8
    )
    typed_ok = (
        artifact["typed_cases"]["summary"].get("passed_count") == 42
        and artifact["typed_cases"]["summary"].get("mismatch_count") == 0
        and all(family.get("mismatch_count") == 0 for family in artifact["typed_cases"]["families"])
    )
    feature_ok = (
        artifact["feature_thresholds"].get("passed_count") == 54
        and artifact["feature_thresholds"].get("mismatch_count") == 0
    )
    negative_ok = len(artifact["negative_checks"]) == 16 and all(
        check.get("passed") is True for check in artifact["negative_checks"]
    )
    ok = (
        artifact.get("status") == "pass"
        and all(binding_checks.values())
        and all(digest_checks.values())
        and summary_ok
        and numerical_ok
        and typed_ok
        and feature_ok
        and negative_ok
        and len(artifact.get("remaining_scope", [])) >= 3
    )
    return readiness.make_check(
        "pdc_qp_receipt",
        ok,
        (
            f"bindings={sum(binding_checks.values())}/{len(binding_checks)}; "
            f"digests={sum(digest_checks.values())}/{len(digest_checks)}; features={summary.get('feature_threshold_case_count')}; "
            f"typed={summary.get('imported_typed_case_count')}; derivatives={summary.get('derivative_oracle_check_count')}; "
            f"finite_difference={summary.get('finite_difference_check_count')}; negative={summary.get('negative_check_count')}; "
            f"mismatches={summary.get('mismatch_count')}"
        ),
    )


def check_pdc_qp_stability_contract(path: Path, qp_contract_path: Path, qp_receipt_path: Path) -> dict:
    from zipfile import ZipFile

    from runtime import pdc_verifier_intake

    artifact, errors = _load_schema_artifact(path, "pdc-qp-stability-contract.schema.json")
    if artifact is None or errors:
        return readiness.make_check(
            "pdc_qp_stability_contract",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    bindings = artifact["bindings"]
    implementation_path = ROOT / bindings["reference_implementation_path"]
    binding_checks = {
        "implementation": implementation_path.is_file()
        and bindings["reference_implementation_sha256"] == pdc_verifier_intake.sha256_file(implementation_path),
        "qp_contract": bindings["qp_contract_sha256"] == pdc_verifier_intake.sha256_file(qp_contract_path),
        "qp_receipt": bindings["qp_receipt_sha256"] == pdc_verifier_intake.sha256_file(qp_receipt_path),
    }
    package_checks = []
    member_checks = []
    for package in bindings["source_packages"]:
        package_path = ROOT / package["stored_path"]
        package_ok = package_path.is_file() and package["sha256"] == pdc_verifier_intake.sha256_file(package_path)
        package_checks.append(package_ok)
        if not package_ok:
            member_checks.extend(False for _ in package["members"])
            continue
        try:
            with ZipFile(package_path) as archive:
                for member in package["members"]:
                    payload = archive.read(member["path"])
                    member_checks.append(
                        pdc_verifier_intake.sha256_bytes(payload) == member["sha256"]
                        and len(payload) == member["size_bytes"]
                    )
        except Exception:
            member_checks.append(False)
    benchmark = artifact["benchmark_protocol"]
    perturbation = artifact["perturbation_protocol"]
    protocol_ok = (
        benchmark.get("lattice_shape") == [28, 28, 28]
        and benchmark.get("target_active_count") == 1317
        and benchmark.get("sample_count_per_raw_class") == 50
        and benchmark.get("seed") == 23
        and len(benchmark.get("combined_channels", [])) == 7
        and benchmark.get("poole_active_excluded_from_combined_score") is True
        and perturbation.get("swap_levels") == [1, 4, 16, 64]
        and perturbation.get("dominant_label_retention_is_diagnostic_not_gate") is True
    )
    ok = (
        artifact.get("status") == "frozen_benchmark_protocol"
        and all(binding_checks.values())
        and len(package_checks) == 2
        and all(package_checks)
        and len(member_checks) == 13
        and all(member_checks)
        and protocol_ok
        and len(artifact.get("claim_boundary", [])) >= 5
    )
    return readiness.make_check(
        "pdc_qp_stability_contract",
        ok,
        (
            f"bindings={sum(binding_checks.values())}/{len(binding_checks)}; "
            f"packages={sum(package_checks)}/2; members={sum(member_checks)}/13; "
            f"fields={benchmark.get('sample_count_per_raw_class', 0) * 11}; swaps={perturbation.get('swap_levels')}; "
            f"protocol={protocol_ok}"
        ),
    )


def check_pdc_qp_stability_receipt(
    path: Path,
    contract_path: Path,
    qp_contract_path: Path,
    qp_receipt_path: Path,
) -> dict:
    from runtime import pdc_verifier_intake

    artifact, errors = _load_schema_artifact(path, "pdc-qp-stability-receipt.schema.json")
    if artifact is None or errors:
        return readiness.make_check(
            "pdc_qp_stability_receipt",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    bindings = artifact["bindings"]
    implementation_path = ROOT / bindings["reference_implementation_path"]
    evidence_path = ROOT / bindings["evidence_implementation_path"]
    runner_path = ROOT / bindings["runner_package_path"]
    result_path = ROOT / bindings["result_package_path"]
    binding_checks = {
        "implementation": implementation_path.is_file()
        and bindings["reference_implementation_sha256"] == pdc_verifier_intake.sha256_file(implementation_path),
        "evidence": evidence_path.is_file()
        and bindings["evidence_implementation_sha256"] == pdc_verifier_intake.sha256_file(evidence_path),
        "contract": bindings["contract_sha256"] == pdc_verifier_intake.sha256_file(contract_path),
        "qp_contract": bindings["qp_contract_sha256"] == pdc_verifier_intake.sha256_file(qp_contract_path),
        "qp_receipt": bindings["qp_receipt_sha256"] == pdc_verifier_intake.sha256_file(qp_receipt_path),
        "runner": runner_path.is_file()
        and bindings["runner_package_sha256"] == pdc_verifier_intake.sha256_file(runner_path),
        "result": result_path.is_file()
        and bindings["result_package_sha256"] == pdc_verifier_intake.sha256_file(result_path),
    }
    digests = artifact["digests"]
    digest_checks = {
        "reproduction": digests["benchmark_reproduction_sha256"]
        == pdc_verifier_intake.sha256_json(artifact["benchmark_reproduction"]),
        "perturbation": digests["controlled_perturbation_sha256"]
        == pdc_verifier_intake.sha256_json(artifact["controlled_perturbations"]),
        "negative": digests["negative_check_set_sha256"]
        == pdc_verifier_intake.sha256_json(artifact["negative_checks"]),
        "field_records": artifact["benchmark_reproduction"]["field_record_set_sha256"]
        == pdc_verifier_intake.sha256_json(artifact["benchmark_reproduction"]["field_records"]),
        "perturbation_records": artifact["controlled_perturbations"]["record_set_sha256"]
        == pdc_verifier_intake.sha256_json(artifact["controlled_perturbations"]["records"]),
        "level_summaries": artifact["controlled_perturbations"]["summary_sha256"]
        == pdc_verifier_intake.sha256_json(artifact["controlled_perturbations"]["level_summaries"]),
    }
    summary = artifact["summary"]
    reproduction = artifact["benchmark_reproduction"]
    perturbation = artifact["controlled_perturbations"]["summary"]
    summary_ok = (
        summary.get("source_package_count") == 2
        and summary.get("verified_source_member_count") == 13
        and summary.get("fresh_field_count") == 550
        and summary.get("published_channel_rate_check_count") == 7150
        and summary.get("independent_channel_rate_check_count") == 7150
        and summary.get("score_check_count") == 4400
        and summary.get("summary_check_count") == 517
        and summary.get("perturbation_case_count") == 2200
        and summary.get("structured_perturbation_case_count") == 1000
        and summary.get("control_perturbation_case_count") == 1200
        and summary.get("negative_check_count") == 14
        and summary.get("failed_negative_check_count") == summary.get("mismatch_count") == 0
    )
    reproduction_ok = (
        reproduction.get("max_published_rate_abs_error") == 0.0
        and reproduction.get("max_oracle_rate_abs_error") == 0.0
        and reproduction.get("max_score_abs_error", float("inf")) <= 2e-12
        and reproduction.get("neighbor_mismatch_voxel_count") == reproduction.get("mismatch_count") == 0
        and reproduction["verification"].get("overall_pass") is True
    )
    perturbation_ok = (
        perturbation.get("case_count") == perturbation.get("passed_count") == 2200
        and perturbation.get("structured_case_count") == 1000
        and perturbation.get("control_case_count") == 1200
        and perturbation.get("mismatch_count") == 0
        and all(record.get("passed") is True for record in artifact["controlled_perturbations"]["records"])
    )
    negative_ok = len(artifact["negative_checks"]) == 14 and all(
        check.get("passed") is True for check in artifact["negative_checks"]
    )
    ok = (
        artifact.get("status") == "pass"
        and all(binding_checks.values())
        and all(digest_checks.values())
        and summary_ok
        and reproduction_ok
        and perturbation_ok
        and negative_ok
        and len(artifact.get("remaining_scope", [])) >= 3
    )
    return readiness.make_check(
        "pdc_qp_stability_receipt",
        ok,
        (
            f"bindings={sum(binding_checks.values())}/{len(binding_checks)}; "
            f"digests={sum(digest_checks.values())}/{len(digest_checks)}; fields={summary.get('fresh_field_count')}; "
            f"channel_checks={summary.get('published_channel_rate_check_count')}; scores={summary.get('score_check_count')}; "
            f"perturbations={summary.get('perturbation_case_count')}; negative={summary.get('negative_check_count')}; "
            f"mismatches={summary.get('mismatch_count')}"
        ),
    )


def check_lab_scaffold() -> dict:
    status = lab_readiness.lab_scaffold_status(ROOT)
    if status["ok"]:
        detail = "Buildroot/QEMU scaffold present; boot image not built"
    else:
        parts = []
        if status["missing"]:
            parts.append(f"missing={status['missing']}")
        if status["semantic_failures"]:
            parts.append(f"semantic_failures={status['semantic_failures']}")
        detail = "; ".join(parts)
    return readiness.make_check("lab_scaffold", status["ok"], detail)


def check_lab_manifest(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("lab_manifest", True, "no lab manifest provided")
    if not path.exists():
        return readiness.make_check("lab_manifest", False, f"missing {path}")
    import json

    manifest = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "specs" / "lab-image-manifest.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(manifest, schema)
    if errors:
        return readiness.make_check(
            "lab_manifest",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    validations = manifest.get("validations", {}) if isinstance(manifest.get("validations"), dict) else {}
    return readiness.make_check(
        "lab_manifest",
        True,
        (
            f"status={manifest.get('status')}; "
            f"probe={validations.get('buildroot_probe_status', '')}; "
            f"configure={validations.get('buildroot_configure_status', '')}; "
            f"build={validations.get('buildroot_build_status', '')}; "
            f"wsl={validations.get('wsl_prerequisites_status', '')}; "
            f"missing_packages={validations.get('wsl_missing_package_count', '')}"
        ),
    )


def check_boot_trap_bundle_manifest(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("boot_trap_bundle_manifest", True, "no boot trap bundle manifest provided")
    if not path.exists():
        return readiness.make_check("boot_trap_bundle_manifest", False, f"missing {path}")
    import json

    manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "boot-trap-bundle-manifest.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(manifest, schema)
    if errors:
        return readiness.make_check(
            "boot_trap_bundle_manifest",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = manifest.get("status")
    summary = manifest.get("summary", {})
    bundle = manifest.get("bundle", {})
    replay = manifest.get("replay_proof", {})
    lab_mount = manifest.get("lab_mount", {})
    trap = manifest.get("trap_execution", {}).get("expected_summary", {})
    ok = (
        status == "pass"
        and summary.get("failed_check_count") == 0
        and summary.get("trap_evidence_present") is True
        and summary.get("expected_executed_instruction_count", 0) > 0
        and Path(bundle.get("target_path", "")).name == "input.pgb2.json"
        and Path(replay.get("target_path", "")).name == "input.replay.json"
        and Path(lab_mount.get("manifest_target_path", "")).name == "pooleos_boot_trap_bundle_manifest.json"
        and replay.get("channel_summary_match") is True
        and trap.get("status") == "pass"
        and trap.get("failed_check_count") == 0
        and trap.get("outcome_mismatch_count") == 0
        and trap.get("security_boundary_claimed") is False
    )
    return readiness.make_check(
        "boot_trap_bundle_manifest",
        ok,
        f"status={status}; sections={summary.get('bundle_section_count')}; executed={summary.get('expected_executed_instruction_count')}; target={bundle.get('target_path')}",
    )


def check_qemu_shared_folder_contract(path: Path | None, *, require_abi_boundary_receipt: bool = False) -> dict:
    if path is None:
        return readiness.make_check("qemu_shared_folder_contract", True, "no QEMU shared-folder contract provided")
    if not path.exists():
        return readiness.make_check("qemu_shared_folder_contract", False, f"missing {path}")
    import json

    contract = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "qemu-shared-folder-contract.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(contract, schema)
    if errors:
        return readiness.make_check(
            "qemu_shared_folder_contract",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = contract.get("status")
    summary = contract.get("summary", {})
    expected_guest = contract.get("expected_guest_verification", {})
    shared = contract.get("shared_folder", {})
    files = contract.get("staged_files", [])
    roles = {file.get("role") for file in files}
    abi_staged = "pgb2_trap_abi_boundary_receipt" in roles
    abi_requirement_satisfied = (not require_abi_boundary_receipt) or abi_staged
    ok = (
        status == "pass"
        and summary.get("failed_check_count") == 0
        and summary.get("staged_file_count") in {3, 4}
        and summary.get("perform_copy") is True
        and summary.get("expected_executed_instruction_count", 0) > 0
        and {"trap_bundle", "replay_proof", "boot_trap_bundle_manifest"}.issubset(roles)
        and abi_requirement_satisfied
        and (
            not abi_staged
            or (
                summary.get("abi_boundary_receipt_staged") is True
                and summary.get("expected_abi_boundary_status") == "draft_verified"
                and expected_guest.get("expected_abi_frozen") is False
                and expected_guest.get("expected_kernel_abi_promotion_allowed") is False
                and expected_guest.get("expected_kernel_enforcement_claimed") is False
            )
        )
        and shared.get("mount_tag") == "pooleos_output"
        and "-virtfs" in shared.get("qemu_args", [])
    )
    return readiness.make_check(
        "qemu_shared_folder_contract",
        ok,
        f"status={status}; staged={summary.get('staged_file_count')}; abi_staged={abi_staged}; abi_required={require_abi_boundary_receipt}; mount_tag={shared.get('mount_tag')}; expected_executed={summary.get('expected_executed_instruction_count')}",
    )


def check_lab_guest_autostart(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("lab_guest_autostart", True, "no Lab guest autostart evidence provided")
    if not path.exists():
        return readiness.make_check("lab_guest_autostart", False, f"missing {path}")
    import json

    manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "lab-guest-autostart.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(manifest, schema)
    if errors:
        return readiness.make_check(
            "lab_guest_autostart",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = manifest.get("status")
    summary = manifest.get("summary", {})
    guest = manifest.get("guest_autostart", {})
    profile = manifest.get("boot_log_profile", {})
    markers = profile.get("required_markers", [])
    ok = (
        status == "pass"
        and manifest.get("boot_evidence_claimed") is False
        and summary.get("failed_check_count") == 0
        and summary.get("qemu_contract_bound") is True
        and guest.get("mount_tag") == "pooleos_output"
        and guest.get("mount_type") == "9p"
        and profile.get("profile") == "trap-input"
        and "POOLEOS_LAB_INPUT_VERIFY_PASS" in markers
        and "POOLEOS_LAB_TRAP_ABI_BOUNDARY_PASS" in markers
        and "POOLEOS_LAB_SHARED_MOUNT_PASS" in markers
    )
    return readiness.make_check(
        "lab_guest_autostart",
        ok,
        f"status={status}; mount_tag={guest.get('mount_tag')}; profile={profile.get('profile')}; markers={summary.get('required_marker_count')}",
    )


def check_qemu_boot_evidence(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("qemu_boot_evidence", True, "no QEMU boot evidence provided")
    if not path.exists():
        return readiness.make_check("qemu_boot_evidence", False, f"missing {path}")
    import json

    evidence = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "qemu-boot-evidence.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(evidence, schema)
    if errors:
        return readiness.make_check(
            "qemu_boot_evidence",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = evidence.get("status")
    source = evidence.get("evidence_source")
    claimed = evidence.get("boot_evidence_claimed")
    validation = evidence.get("boot_log_validation", {})
    summary = evidence.get("summary", {})
    required = validation.get("required_markers", []) if isinstance(validation, dict) else []
    ok = (
        status == "pass"
        and source == "fixture"
        and claimed is False
        and summary.get("failed_check_count") == 0
        and summary.get("profile") == "trap-input"
        and summary.get("missing_marker_count") == 0
        and isinstance(validation, dict)
        and validation.get("ok") is True
        and validation.get("profile") == "trap-input"
        and "POOLEOS_LAB_INPUT_VERIFY_PASS" in required
        and "POOLEOS_LAB_TRAP_ABI_BOUNDARY_PASS" in required
        and "POOLEOS_LAB_SHARED_MOUNT_PASS" in required
        and "POOLEOS_LAB_AUTOSTART_DONE" in required
    )
    return readiness.make_check(
        "qemu_boot_evidence",
        ok,
        f"status={status}; source={source}; boot_evidence_claimed={claimed}; profile={summary.get('profile')}; missing={summary.get('missing_marker_count')}",
    )


def check_qemu_captured_boot_evidence(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("qemu_captured_boot_evidence", True, "no captured QEMU boot evidence provided")
    if not path.exists():
        return readiness.make_check("qemu_captured_boot_evidence", False, f"missing {path}")
    import json

    evidence = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "qemu-boot-evidence.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(evidence, schema)
    if errors:
        return readiness.make_check(
            "qemu_captured_boot_evidence",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = evidence.get("status")
    source = evidence.get("evidence_source")
    claimed = evidence.get("boot_evidence_claimed")
    validation = evidence.get("boot_log_validation", {})
    summary = evidence.get("summary", {})
    ok = (
        status == "pass"
        and source == "captured_qemu_serial"
        and claimed is True
        and summary.get("failed_check_count") == 0
        and summary.get("profile") == "trap-input"
        and summary.get("missing_marker_count") == 0
        and isinstance(validation, dict)
        and validation.get("ok") is True
        and validation.get("profile") == "trap-input"
        and "POOLEOS_LAB_TRAP_ABI_BOUNDARY_PASS" in validation.get("required_markers", [])
    )
    return readiness.make_check(
        "qemu_captured_boot_evidence",
        ok,
        f"status={status}; source={source}; boot_evidence_claimed={claimed}; profile={summary.get('profile')}; missing={summary.get('missing_marker_count')}",
    )


def check_qemu_captured_boot_receipt(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("qemu_captured_boot_receipt", True, "no QEMU captured boot receipt provided")
    if not path.exists():
        return readiness.make_check("qemu_captured_boot_receipt", False, f"missing {path}")
    import json

    receipt = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "qemu-captured-boot-receipt.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(receipt, schema)
    if errors:
        return readiness.make_check(
            "qemu_captured_boot_receipt",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = receipt.get("status")
    summary = receipt.get("summary", {})
    fixture = receipt.get("fixture_boot_evidence", {})
    captured = receipt.get("captured_boot_evidence", {})
    ok = (
        status in {"pending_capture", "captured"}
        and summary.get("failed_check_count") == 0
        and summary.get("fixture_preserved") is True
        and fixture.get("evidence_source") == "fixture"
        and fixture.get("boot_evidence_claimed") is False
        and (
            status == "pending_capture"
            or (
                status == "captured"
                and summary.get("boot_evidence_ingested") is True
                and captured.get("evidence_source") == "captured_qemu_serial"
                and captured.get("boot_evidence_claimed") is True
            )
        )
    )
    return readiness.make_check(
        "qemu_captured_boot_receipt",
        ok,
        f"status={status}; fixture_preserved={summary.get('fixture_preserved')}; captured_exists={summary.get('captured_evidence_exists')}; ingested={summary.get('boot_evidence_ingested')}",
    )


def check_qemu_captured_boot_readiness(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("qemu_captured_boot_readiness", True, "no QEMU captured boot readiness provided")
    if not path.exists():
        return readiness.make_check("qemu_captured_boot_readiness", False, f"missing {path}")
    import json

    report = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "qemu-captured-boot-readiness.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(report, schema)
    if errors:
        return readiness.make_check(
            "qemu_captured_boot_readiness",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = report.get("status")
    summary = report.get("summary", {})
    sources = report.get("sources", {})
    rootfs = sources.get("rootfs_extraction_receipt", {})
    receipt = sources.get("qemu_captured_boot_receipt", {})
    captured = sources.get("qemu_captured_boot_evidence", {})
    ok = (
        status in {"blocked", "ready_for_promotion"}
        and summary.get("failed_check_count") == 0
        and report.get("promotion_language_allowed") is (status == "ready_for_promotion")
        and (
            status == "blocked"
            or (
                summary.get("unmet_requirement_count") == 0
                and rootfs.get("status") == "verified"
                and receipt.get("status") == "captured"
                and captured.get("exists") is True
                and captured.get("status") == "pass"
            )
        )
        and (
            status != "blocked"
            or (
                summary.get("unmet_requirement_count", 0) > 0
                and report.get("promotion_language_allowed") is False
            )
        )
    )
    return readiness.make_check(
        "qemu_captured_boot_readiness",
        ok,
        f"status={status}; promotion_language_allowed={report.get('promotion_language_allowed')}; unmet={summary.get('unmet_requirement_count')}; rootfs={rootfs.get('status')}; receipt={receipt.get('status')}; captured_exists={captured.get('exists')}",
    )


def check_kernel_boot_handoff(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("kernel_boot_handoff", True, "no kernel boot handoff provided")
    if not path.exists():
        return readiness.make_check("kernel_boot_handoff", False, f"missing {path}")
    import json

    handoff = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "kernel-boot-handoff.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(handoff, schema)
    if errors:
        return readiness.make_check(
            "kernel_boot_handoff",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = handoff.get("status")
    summary = handoff.get("summary", {})
    sources = handoff.get("sources", {})
    captured_readiness = sources.get("qemu_captured_boot_readiness", {})
    marker_contract = sources.get("qemu_boot_marker_contract", {})
    boot_manifest = sources.get("boot_trap_bundle_manifest", {})
    loader = sources.get("guest_loader_verification", {})
    ok = (
        status in {"blocked", "ready_for_kernel_handoff"}
        and summary.get("failed_check_count") == 0
        and handoff.get("kernel_boundary_claimed") is False
        and handoff.get("pgvm2_execution_claimed") is False
        and handoff.get("kernel_handoff_allowed") is (status == "ready_for_kernel_handoff")
        and (
            status == "blocked"
            or (
                summary.get("unmet_requirement_count") == 0
                and captured_readiness.get("status") == "ready_for_promotion"
                and marker_contract.get("status") == "pass"
                and boot_manifest.get("status") == "pass"
                and loader.get("exists") is True
                and loader.get("status") == "pass"
            )
        )
        and (
            status != "blocked"
            or (
                summary.get("unmet_requirement_count", 0) > 0
                and handoff.get("kernel_handoff_allowed") is False
            )
        )
    )
    return readiness.make_check(
        "kernel_boot_handoff",
        ok,
        f"status={status}; handoff_allowed={handoff.get('kernel_handoff_allowed')}; unmet={summary.get('unmet_requirement_count')}; captured={captured_readiness.get('status')}; marker={marker_contract.get('status')}; loader_exists={loader.get('exists')}",
    )


def check_kernel_pgvm2_loader_output(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("kernel_pgvm2_loader_output", True, "no kernel PGVM2 loader output provided")
    if not path.exists():
        return readiness.make_check("kernel_pgvm2_loader_output", False, f"missing {path}")
    import json

    output = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "kernel-pgvm2-loader-output.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(output, schema)
    if errors:
        return readiness.make_check(
            "kernel_pgvm2_loader_output",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = output.get("status")
    summary = output.get("summary", {})
    claims = output.get("kernel_enforcement_claimed") is True or output.get("pgvm2_execution_claimed") is True
    hash_present = bool(output.get("source_handoff_sha256"))
    source_anchor_hash_present = bool(output.get("pooleglyph_source_anchor_sha256"))
    promotion_receipt_hash_present = bool(output.get("pooleglyph_parser_kernel_promotion_receipt_sha256"))
    blocked_ok = (
        status == "blocked"
        and output.get("booted_kernel_path") is False
        and output.get("kernel_enforcement_claimed") is False
        and output.get("pgvm2_execution_claimed") is False
        and summary.get("failed_check_count") == 0
        and summary.get("blocking_check_count", 0) > 0
        and summary.get("enforcement_claim_allowed") is False
        and summary.get("negative_claim_guard_held") is True
        and hash_present
        and source_anchor_hash_present
        and promotion_receipt_hash_present
    )
    pass_ok = (
        status == "pass"
        and output.get("booted_kernel_path") is True
        and output.get("kernel_enforcement_claimed") is True
        and output.get("pgvm2_execution_claimed") is True
        and summary.get("failed_check_count") == 0
        and summary.get("blocking_check_count") == 0
        and summary.get("kernel_check_count", 0) >= 11
        and summary.get("satisfied_kernel_check_count", 0) >= 11
        and summary.get("expected_executed_instruction_count", 0) > 0
        and summary.get("actual_executed_instruction_count") == summary.get("expected_executed_instruction_count")
        and summary.get("enforcement_claim_allowed") is True
        and summary.get("negative_claim_guard_held") is True
        and hash_present
        and source_anchor_hash_present
        and promotion_receipt_hash_present
    )
    ok = status in {"blocked", "pass"} and (blocked_ok or pass_ok) and claims is (status == "pass")
    return readiness.make_check(
        "kernel_pgvm2_loader_output",
        ok,
        f"status={status}; booted={output.get('booted_kernel_path')}; enforcement={output.get('kernel_enforcement_claimed')}; checks={summary.get('satisfied_kernel_check_count')}/{summary.get('kernel_check_count')}; blocking={summary.get('blocking_check_count')}; source_anchor_hash={source_anchor_hash_present}; promotion_hash={promotion_receipt_hash_present}",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_lab_kernel_transcript_export_receipt(
    path: Path | None,
    kernel_loader_output_path: Path | None = None,
) -> dict:
    if path is None:
        return readiness.make_check("lab_kernel_transcript_export_receipt", True, "no lab kernel transcript export receipt provided")
    if not path.exists():
        return readiness.make_check("lab_kernel_transcript_export_receipt", False, f"missing {path}")
    import json

    receipt = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "lab-kernel-transcript-export-receipt.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(receipt, schema)
    if errors:
        return readiness.make_check(
            "lab_kernel_transcript_export_receipt",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = receipt.get("status")
    summary = receipt.get("summary", {})
    output = receipt.get("verifier_output", {})
    transcript_export = receipt.get("transcript_export", {})
    guest_environment = receipt.get("guest_environment", {})
    source_anchor_env = guest_environment.get("source_anchor", {})
    parser_promotion_env = guest_environment.get("parser_promotion_receipt", {})
    embedded_verifier_path = Path(str(output.get("path", ""))) if output.get("path") else None
    verifier_path = kernel_loader_output_path or embedded_verifier_path
    verifier_artifact_bound = bool(
        verifier_path
        and verifier_path.exists()
        and output.get("sha256") == _sha256(verifier_path)
    )
    digest_pair_attested = receipt.get("guest_environment_digest_pair_attested") is True
    digest_attestation_consistent = (
        guest_environment.get("digest_pair_attested") is digest_pair_attested
        and summary.get("guest_environment_digest_pair_attested") is digest_pair_attested
    )
    recorded_digest_pair_bound = (
        digest_pair_attested
        and source_anchor_env.get("occurrence_count") == 1
        and source_anchor_env.get("valid_sha256") is True
        and source_anchor_env.get("matches_verifier") is True
        and source_anchor_env.get("observed_value") == output.get("pooleglyph_source_anchor_sha256")
        and parser_promotion_env.get("occurrence_count") == 1
        and parser_promotion_env.get("valid_sha256") is True
        and parser_promotion_env.get("matches_verifier") is True
        and parser_promotion_env.get("observed_value")
        == output.get("pooleglyph_parser_kernel_promotion_receipt_sha256")
    )
    transcript_digest_matches = receipt.get("transcript_digest_matches_verifier") is True
    transcript_binding_consistent = (
        summary.get("transcript_digest_matches_verifier") is transcript_digest_matches
        and bool(transcript_export.get("sha256"))
        and output.get("transcript_source_sha256") == transcript_export.get("sha256")
    )
    recorded_export_attested = recorded_digest_pair_bound and transcript_digest_matches and transcript_binding_consistent
    pending_ok = (
        status == "pending_contract_run"
        and receipt.get("contract_run_recorded") is False
        and receipt.get("verifier_accepted_export") is False
        and receipt.get("kernel_enforcement_promotion_allowed") is False
        and verifier_artifact_bound
    )
    disabled_ok = (
        status == "disabled_verified"
        and receipt.get("contract_run_recorded") is True
        and receipt.get("verifier_accepted_export") is True
        and receipt.get("kernel_enforcement_promotion_allowed") is False
        and output.get("status") == "blocked"
        and output.get("kernel_enforcement_claimed") is False
        and output.get("pgvm2_execution_claimed") is False
        and recorded_export_attested
        and verifier_artifact_bound
    )
    enabled_ok = (
        status == "enabled_verified"
        and receipt.get("contract_run_recorded") is True
        and receipt.get("verifier_accepted_export") is True
        and receipt.get("kernel_enforcement_promotion_allowed") is True
        and output.get("status") == "pass"
        and output.get("kernel_enforcement_claimed") is True
        and output.get("pgvm2_execution_claimed") is True
        and recorded_export_attested
        and verifier_artifact_bound
    )
    ok = (
        status in {"pending_contract_run", "disabled_verified", "enabled_verified"}
        and receipt.get("codex_execution_performed") is False
        and summary.get("failed_check_count") == 0
        and summary.get("overclaim_detected") is False
        and digest_attestation_consistent
        and (pending_ok or disabled_ok or enabled_ok)
    )
    return readiness.make_check(
        "lab_kernel_transcript_export_receipt",
        ok,
        f"status={status}; contract_run={receipt.get('contract_run_recorded')}; mode={receipt.get('inferred_contract_mode')}; verifier_artifact_bound={verifier_artifact_bound}; accepted={receipt.get('verifier_accepted_export')}; guest_digest_pair={digest_pair_attested}; transcript_bound={transcript_digest_matches}; promotion={receipt.get('kernel_enforcement_promotion_allowed')}",
    )


def check_kernel_pgvm2_loader_evidence(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("kernel_pgvm2_loader_evidence", True, "no kernel PGVM2 loader evidence provided")
    if not path.exists():
        return readiness.make_check("kernel_pgvm2_loader_evidence", False, f"missing {path}")
    import json

    evidence = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "kernel-pgvm2-loader-evidence.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(evidence, schema)
    if errors:
        return readiness.make_check(
            "kernel_pgvm2_loader_evidence",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = evidence.get("status")
    summary = evidence.get("summary", {})
    sources = evidence.get("sources", {})
    handoff = sources.get("kernel_boot_handoff", {})
    loader = sources.get("kernel_loader_output", {})
    source_anchor = sources.get("pooleglyph_source_anchor", {})
    promotion = sources.get("pooleglyph_parser_kernel_promotion_receipt", {})
    source_anchor_bound = (
        source_anchor.get("exists") is True
        and summary.get("pooleglyph_source_anchor_bound") is True
    )
    parser_promotion_bound = (
        promotion.get("exists") is True
        and summary.get("parser_promotion_receipt_bound") is True
        and summary.get("parser_promotion_receipt_status") in {"blocked_until_phase66", "parser_to_kernel_ready"}
    )
    parser_promotion_ready = summary.get("parser_promotion_ready_for_enforcement") is True
    source_anchor_digest_ok = (
        loader.get("exists") is not True
        or summary.get("pooleglyph_source_anchor_digest_matches") is True
    )
    promotion_digest_ok = (
        loader.get("exists") is not True
        or summary.get("parser_promotion_receipt_digest_matches") is True
    )
    enforced = status == "kernel_enforced"
    ready = status == "ready_for_kernel_loader"
    blocked = status == "blocked"
    claims_match_status = (
        evidence.get("kernel_enforcement_claimed") is enforced
        and evidence.get("pgvm2_execution_claimed") is enforced
        and evidence.get("booted_kernel_path_claimed") is enforced
    )
    ok = (
        status in {"blocked", "ready_for_kernel_loader", "kernel_enforced"}
        and summary.get("failed_check_count") == 0
        and source_anchor_bound
        and parser_promotion_bound
        and source_anchor_digest_ok
        and promotion_digest_ok
        and claims_match_status
        and evidence.get("kernel_loader_ready") is (ready or enforced)
        and (
            not enforced
            or (
                summary.get("unmet_requirement_count") == 0
                and handoff.get("status") == "ready_for_kernel_handoff"
                and loader.get("exists") is True
                and loader.get("status") == "pass"
                and source_anchor_digest_ok
                and parser_promotion_ready
                and promotion_digest_ok
                and summary.get("output_handoff_hash_matches") is True
                and summary.get("all_kernel_checks_satisfied") is True
            )
        )
        and (
            not ready
            or (
                summary.get("unmet_requirement_count", 0) > 0
                and handoff.get("status") == "ready_for_kernel_handoff"
                and evidence.get("kernel_enforcement_claimed") is False
            )
        )
        and (
            not blocked
            or (
                summary.get("unmet_requirement_count", 0) > 0
                and evidence.get("kernel_loader_ready") is False
                and evidence.get("kernel_enforcement_claimed") is False
            )
        )
    )
    return readiness.make_check(
        "kernel_pgvm2_loader_evidence",
        ok,
        f"status={status}; loader_ready={evidence.get('kernel_loader_ready')}; enforcement={evidence.get('kernel_enforcement_claimed')}; handoff={handoff.get('status')}; loader_exists={loader.get('exists')}; source_anchor={summary.get('pooleglyph_source_anchor_bound')}; parser_promotion={summary.get('parser_promotion_receipt_status')}; source_digest={summary.get('pooleglyph_source_anchor_digest_matches')}; promotion_digest={summary.get('parser_promotion_receipt_digest_matches')}; checks={summary.get('satisfied_kernel_check_count')}/{summary.get('planned_kernel_check_count')}",
    )


def check_qemu_captured_boot_preflight(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("qemu_captured_boot_preflight", True, "no QEMU captured boot preflight provided")
    if not path.exists():
        return readiness.make_check("qemu_captured_boot_preflight", False, f"missing {path}")
    import json

    report = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "qemu-captured-boot-preflight.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(report, schema)
    if errors:
        return readiness.make_check(
            "qemu_captured_boot_preflight",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = report.get("status")
    summary = report.get("summary", {})
    paths = report.get("paths", {})
    ok = (
        status in {"pass", "blocked"}
        and report.get("execution_performed") is False
        and summary.get("safety_failure_count") == 0
        and summary.get("captured_outputs_separate") is True
        and bool(paths.get("image_path"))
        and bool(paths.get("serial_log_path"))
        and bool(paths.get("shared_output_path"))
        and bool(paths.get("boot_validation_output"))
        and bool(paths.get("qemu_boot_evidence_output"))
        and bool(paths.get("qemu_captured_boot_receipt_output"))
        and (status == "pass" or summary.get("blocking_check_count", 0) > 0)
    )
    return readiness.make_check(
        "qemu_captured_boot_preflight",
        ok,
        f"status={status}; launch_ready={report.get('launch_ready')}; blocking={summary.get('blocking_check_count')}; safety={summary.get('safety_failure_count')}",
    )


def check_qemu_captured_boot_launch_bundle(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("qemu_captured_boot_launch_bundle", True, "no QEMU captured boot launch bundle provided")
    if not path.exists():
        return readiness.make_check("qemu_captured_boot_launch_bundle", False, f"missing {path}")
    import json

    bundle = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "qemu-captured-boot-launch-bundle.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(bundle, schema)
    if errors:
        return readiness.make_check(
            "qemu_captured_boot_launch_bundle",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = bundle.get("status")
    summary = bundle.get("summary", {})
    command_roles = {command.get("role") for command in bundle.get("command_plan", [])}
    expected_roles = {
        "prepare_shared_folder",
        "captured_preflight",
        "qemu_launch",
        "emit_captured_evidence_only",
        "captured_receipt",
    }
    expected_outputs = bundle.get("expected_outputs", {})
    release_args = bundle.get("release_gate_arguments", [])
    ok = (
        status in {"pass", "blocked"}
        and bundle.get("execution_performed") is False
        and summary.get("failed_check_count") == 0
        and summary.get("command_count", 0) >= len(expected_roles)
        and expected_roles.issubset(command_roles)
        and summary.get("captured_outputs_separate") is True
        and bool(expected_outputs.get("serial_log_path"))
        and bool(expected_outputs.get("boot_validation_output"))
        and bool(expected_outputs.get("qemu_boot_evidence_output"))
        and bool(expected_outputs.get("qemu_captured_boot_receipt_output"))
        and "--qemu-captured-boot-launch-bundle" in release_args
        and (status == "pass" or summary.get("blocking_check_count", 0) > 0)
    )
    return readiness.make_check(
        "qemu_captured_boot_launch_bundle",
        ok,
        f"status={status}; launch_ready={bundle.get('launch_ready')}; commands={summary.get('command_count')}; blocking={summary.get('blocking_check_count')}; failed={summary.get('failed_check_count')}",
    )


def check_qemu_captured_boot_dry_run_checklist(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("qemu_captured_boot_dry_run_checklist", True, "no QEMU captured boot dry-run checklist provided")
    if not path.exists():
        return readiness.make_check("qemu_captured_boot_dry_run_checklist", False, f"missing {path}")
    import json

    checklist = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "qemu-captured-boot-dry-run-checklist.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(checklist, schema)
    if errors:
        return readiness.make_check(
            "qemu_captured_boot_dry_run_checklist",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = checklist.get("status")
    summary = checklist.get("summary", {})
    markers = set(checklist.get("expected_serial_markers", []))
    receipt = checklist.get("operator_receipt_template", {})
    reconciliation = checklist.get("release_gate_reconciliation", {})
    checklist_args = reconciliation.get("checklist_arguments", [])
    ok = (
        status in {"pass", "blocked"}
        and checklist.get("execution_performed") is False
        and summary.get("failed_check_count") == 0
        and summary.get("checklist_step_count", 0) >= 8
        and summary.get("command_count", 0) >= 5
        and summary.get("expected_marker_count", 0) >= 10
        and summary.get("post_capture_file_count", 0) >= 5
        and {
            "POOLEOS_LAB_INPUT_VERIFY_PASS",
            "POOLEOS_LAB_TRAP_ABI_BOUNDARY_PASS",
            "POOLEOS_LAB_SHARED_MOUNT_PASS",
            "POOLEOS_LAB_AUTOSTART_DONE",
        }.issubset(markers)
        and receipt.get("operator_executed") is False
        and receipt.get("codex_execution_performed") is False
        and "--qemu-captured-boot-launch-bundle" in checklist_args
        and "--qemu-captured-boot-dry-run-checklist" in checklist_args
        and (status == "pass" or summary.get("blocking_check_count", 0) > 0)
    )
    return readiness.make_check(
        "qemu_captured_boot_dry_run_checklist",
        ok,
        f"status={status}; launch_ready={checklist.get('launch_ready')}; steps={summary.get('checklist_step_count')}; blockers={summary.get('preflight_blocker_count')}; failed={summary.get('failed_check_count')}",
    )


def check_qemu_boot_marker_contract(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("qemu_boot_marker_contract", True, "no QEMU boot marker contract provided")
    if not path.exists():
        return readiness.make_check("qemu_boot_marker_contract", False, f"missing {path}")
    import json

    contract = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "qemu-boot-marker-contract.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(contract, schema)
    if errors:
        return readiness.make_check(
            "qemu_boot_marker_contract",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = contract.get("status")
    summary = contract.get("summary", {})
    marker_contract = contract.get("marker_contract", {})
    boundary = contract.get("kernel_pgvm2_boundary", {})
    markers = set(marker_contract.get("required_markers", [])) if isinstance(marker_contract, dict) else set()
    mappings = contract.get("marker_mappings", [])
    ok = (
        status in {"pass", "blocked"}
        and contract.get("execution_performed") is False
        and contract.get("boot_evidence_claimed") is False
        and contract.get("security_boundary_claimed") is False
        and boundary.get("kernel_boundary_claimed") is False
        and boundary.get("pgvm2_execution_claimed") is False
        and summary.get("failed_check_count") == 0
        and summary.get("marker_count", 0) >= 10
        and summary.get("expected_marker_count", 0) >= 10
        and summary.get("boundary_count", 0) >= 10
        and summary.get("post_capture_file_count", 0) >= 4
        and isinstance(mappings, list)
        and len(mappings) >= 10
        and {
            "POOLEOS_LAB_INPUT_VERIFY_PASS",
            "POOLEOS_LAB_TRAP_ABI_BOUNDARY_PASS",
            "POOLEOS_LAB_SHARED_MOUNT_PASS",
            "POOLEOS_LAB_AUTOSTART_DONE",
        }.issubset(markers)
        and (status == "pass" or summary.get("blocking_check_count", 0) > 0)
    )
    return readiness.make_check(
        "qemu_boot_marker_contract",
        ok,
        f"status={status}; markers={summary.get('marker_count')}; boundaries={summary.get('boundary_count')}; dry_run={summary.get('dry_run_status')}; failed={summary.get('failed_check_count')}",
    )


def check_qemu_boot_marker_image_binding(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("qemu_boot_marker_image_binding", True, "no QEMU boot marker image binding provided")
    if not path.exists():
        return readiness.make_check("qemu_boot_marker_image_binding", False, f"missing {path}")
    import json

    binding = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "qemu-boot-marker-image-binding.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(binding, schema)
    if errors:
        return readiness.make_check(
            "qemu_boot_marker_image_binding",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = binding.get("status")
    summary = binding.get("summary", {})
    manifest_binding = binding.get("lab_image_manifest_binding", {})
    marker_files = binding.get("marker_file_bindings", [])
    support_files = binding.get("support_file_bindings", [])
    buildroot_files = binding.get("buildroot_manifest_files", [])
    file_sets = [item for group in (marker_files, support_files, buildroot_files) for item in group]
    all_files_bound = all(item.get("exists") is True and bool(item.get("sha256")) for item in file_sets if isinstance(item, dict))
    ok = (
        status in {"pass", "blocked"}
        and binding.get("execution_performed") is False
        and binding.get("boot_evidence_claimed") is False
        and binding.get("security_boundary_claimed") is False
        and summary.get("failed_check_count") == 0
        and summary.get("marker_count", 0) >= 10
        and summary.get("marker_source_file_count", 0) >= 2
        and summary.get("support_file_count", 0) >= 3
        and summary.get("buildroot_manifest_file_count", 0) >= 5
        and summary.get("hashed_file_count", 0) >= 10
        and summary.get("marker_contract_status") in {"pass", "blocked"}
        and manifest_binding.get("defconfig_sha256") == manifest_binding.get("current_defconfig_sha256")
        and all_files_bound
        and (status == "pass" or summary.get("blocking_check_count", 0) > 0)
    )
    return readiness.make_check(
        "qemu_boot_marker_image_binding",
        ok,
        f"status={status}; marker_sources={summary.get('marker_source_file_count')}; hashed={summary.get('hashed_file_count')}; contract={summary.get('marker_contract_status')}; failed={summary.get('failed_check_count')}",
    )


def check_rootfs_content_manifest(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("rootfs_content_manifest", True, "no rootfs content manifest provided")
    if not path.exists():
        return readiness.make_check("rootfs_content_manifest", False, f"missing {path}")
    import json

    manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "rootfs-content-manifest.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(manifest, schema)
    if errors:
        return readiness.make_check(
            "rootfs_content_manifest",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = manifest.get("status")
    summary = manifest.get("summary", {})
    rootfs_image = manifest.get("rootfs_image", {})
    extracted = manifest.get("extracted_rootfs", {})
    ok = (
        status in {"pass", "blocked"}
        and manifest.get("execution_performed") is False
        and manifest.get("rootfs_extraction_performed") is False
        and manifest.get("boot_evidence_claimed") is False
        and manifest.get("security_boundary_claimed") is False
        and summary.get("failed_check_count") == 0
        and summary.get("source_file_count", 0) >= 5
        and summary.get("source_hashed_file_count") == summary.get("source_file_count")
        and summary.get("image_binding_status") in {"pass", "blocked"}
        and bool(rootfs_image.get("path"))
        and (status == "blocked" or rootfs_image.get("exists") is True)
        and (status == "blocked" or bool(rootfs_image.get("sha256")))
        and (status == "blocked" or extracted.get("exists") is True)
        and (status == "blocked" or summary.get("matched_source_file_count") == summary.get("source_file_count"))
        and (status == "pass" or summary.get("blocking_check_count", 0) > 0)
    )
    return readiness.make_check(
        "rootfs_content_manifest",
        ok,
        f"status={status}; image_exists={summary.get('image_exists')}; extracted={summary.get('extracted_rootfs_exists')}; matched={summary.get('matched_source_file_count')}/{summary.get('source_file_count')}; failed={summary.get('failed_check_count')}",
    )


def check_rootfs_extraction_handoff(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("rootfs_extraction_handoff", True, "no rootfs extraction handoff provided")
    if not path.exists():
        return readiness.make_check("rootfs_extraction_handoff", False, f"missing {path}")
    import json

    handoff = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "rootfs-extraction-handoff.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(handoff, schema)
    if errors:
        return readiness.make_check(
            "rootfs_extraction_handoff",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = handoff.get("status")
    summary = handoff.get("summary", {})
    script = str(handoff.get("bash_script", ""))
    receipt = handoff.get("operator_receipt_template", {})
    ok = (
        status in {"pass", "blocked"}
        and handoff.get("execution_performed") is False
        and handoff.get("codex_execution_allowed") is False
        and handoff.get("rootfs_extraction_performed") is False
        and summary.get("failed_check_count") == 0
        and summary.get("command_count", 0) >= 7
        and summary.get("source_manifest_status") in {"pass", "blocked"}
        and summary.get("source_manifest_failed_check_count") == 0
        and summary.get("source_file_count", 0) >= 5
        and isinstance(handoff.get("bash_script_sha256"), str)
        and len(handoff.get("bash_script_sha256", "")) == 64
        and "mount -o ro,loop" in script
        and "emit_rootfs_content_manifest.py" in script
        and "rm -rf" not in script
        and "--delete" not in script
        and receipt.get("operator_executed") is False
        and receipt.get("codex_execution_performed") is False
        and (status == "pass" or summary.get("blocking_check_count", 0) > 0)
    )
    return readiness.make_check(
        "rootfs_extraction_handoff",
        ok,
        f"status={status}; image_exists={summary.get('rootfs_image_exists')}; commands={summary.get('command_count')}; source={summary.get('source_manifest_status')}; failed={summary.get('failed_check_count')}",
    )


def check_rootfs_extraction_receipt(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("rootfs_extraction_receipt", True, "no rootfs extraction receipt provided")
    if not path.exists():
        return readiness.make_check("rootfs_extraction_receipt", False, f"missing {path}")
    import json

    receipt = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "rootfs-extraction-receipt.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(receipt, schema)
    if errors:
        return readiness.make_check(
            "rootfs_extraction_receipt",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = receipt.get("status")
    summary = receipt.get("summary", {})
    manifest = receipt.get("rootfs_content_manifest", {})
    ok = (
        status in {"pending_operator_action", "verified"}
        and receipt.get("codex_execution_performed") is False
        and summary.get("failed_check_count") == 0
        and summary.get("source_file_count", 0) >= 5
        and (
            status == "pending_operator_action"
            or (
                receipt.get("operator_executed") is True
                and receipt.get("rootfs_extraction_performed") is True
                and receipt.get("captured_qemu_promotion_allowed") is True
                and manifest.get("status") == "pass"
                and manifest.get("matched_source_file_count") == manifest.get("source_file_count")
                and manifest.get("extracted_rootfs_exists") is True
            )
        )
        and (
            status != "pending_operator_action"
            or (
                receipt.get("operator_executed") is False
                and receipt.get("captured_qemu_promotion_allowed") is False
            )
        )
    )
    return readiness.make_check(
        "rootfs_extraction_receipt",
        ok,
        f"status={status}; operator_executed={receipt.get('operator_executed')}; promotion_allowed={receipt.get('captured_qemu_promotion_allowed')}; matched={manifest.get('matched_source_file_count')}/{manifest.get('source_file_count')}; failed={summary.get('failed_check_count')}",
    )


def check_captured_qemu_rootfs_promotion(captured_evidence_path: Path | None, rootfs_receipt_path: Path | None) -> dict:
    if captured_evidence_path is None:
        return readiness.make_check("captured_qemu_rootfs_promotion", True, "no captured QEMU boot evidence provided")
    if not captured_evidence_path.exists():
        return readiness.make_check("captured_qemu_rootfs_promotion", True, f"captured evidence path not present yet: {captured_evidence_path}")
    if rootfs_receipt_path is None or not rootfs_receipt_path.exists():
        return readiness.make_check("captured_qemu_rootfs_promotion", False, "captured QEMU evidence requires a verified rootfs extraction receipt")
    import json

    receipt = json.loads(rootfs_receipt_path.read_text(encoding="utf-8-sig"))
    status = receipt.get("status")
    promotion_allowed = receipt.get("captured_qemu_promotion_allowed") is True
    ok = status == "verified" and promotion_allowed
    return readiness.make_check(
        "captured_qemu_rootfs_promotion",
        ok,
        f"captured={captured_evidence_path}; receipt_status={status}; promotion_allowed={promotion_allowed}",
    )


def check_host_preflight(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("host_preflight", True, "no host preflight provided")
    if not path.exists():
        return readiness.make_check("host_preflight", False, f"missing {path}")
    import json

    report = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "specs" / "host-preflight.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(report, schema)
    if errors:
        return readiness.make_check(
            "host_preflight",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    return readiness.make_check("host_preflight", report.get("status") in {"pass", "warn"}, f"status={report.get('status')}")


def check_buildroot_probe(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("buildroot_probe", True, "no Buildroot probe provided")
    if not path.exists():
        return readiness.make_check("buildroot_probe", False, f"missing {path}")
    import json

    report = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "buildroot-probe.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(report, schema)
    if errors:
        return readiness.make_check(
            "buildroot_probe",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    return readiness.make_check("buildroot_probe", report.get("status") == "pass", f"status={report.get('status')}")


def check_buildroot_configure(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("buildroot_configure", True, "no Buildroot configure report provided")
    if not path.exists():
        return readiness.make_check("buildroot_configure", False, f"missing {path}")
    import json

    report = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "buildroot-configure.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(report, schema)
    if errors:
        return readiness.make_check(
            "buildroot_configure",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = report.get("status")
    return readiness.make_check(
        "buildroot_configure",
        status in {"pass", "blocked"},
        f"status={status}; exit_code={report.get('exit_code')}",
    )


def check_buildroot_build(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("buildroot_build", True, "no Buildroot build report provided")
    if not path.exists():
        return readiness.make_check("buildroot_build", False, f"missing {path}")
    import json

    report = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "buildroot-build.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(report, schema)
    if errors:
        return readiness.make_check(
            "buildroot_build",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = report.get("status")
    summary = report.get("summary", {}) if isinstance(report.get("summary"), dict) else {}
    rootfs = report.get("rootfs_image", {}) if isinstance(report.get("rootfs_image"), dict) else {}
    ok = (
        status == "blocked"
        or (
            status == "pass"
            and report.get("execution_performed") is True
            and summary.get("failed_check_count") == 0
            and rootfs.get("exists") is True
            and bool(rootfs.get("sha256"))
        )
    )
    return readiness.make_check(
        "buildroot_build",
        ok,
        f"status={status}; rootfs_exists={rootfs.get('exists')}; execution_performed={report.get('execution_performed')}; failed={summary.get('failed_check_count')}",
    )


def check_wsl_prerequisites(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("wsl_prerequisites", True, "no WSL prerequisite report provided")
    if not path.exists():
        return readiness.make_check("wsl_prerequisites", False, f"missing {path}")
    import json

    report = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "wsl-prerequisites.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(report, schema)
    if errors:
        return readiness.make_check(
            "wsl_prerequisites",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = report.get("status")
    missing_count = len(report.get("missing_packages", []))
    return readiness.make_check(
        "wsl_prerequisites",
        status in {"pass", "blocked"},
        f"status={status}; missing_packages={missing_count}; execution_performed={report.get('execution_performed')}",
    )


def check_operator_action(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("operator_action", True, "no operator action request provided")
    if not path.exists():
        return readiness.make_check("operator_action", False, f"missing {path}")
    import json

    request = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "operator-action-request.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(request, schema)
    if errors:
        return readiness.make_check(
            "operator_action",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = request.get("status")
    return readiness.make_check(
        "operator_action",
        status in {"pending_approval", "no_action_needed"},
        f"status={status}; execution_performed={request.get('execution_performed')}; approval_required={request.get('requires_operator_approval')}",
    )


def check_operator_receipt(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("operator_receipt", True, "no operator action receipt provided")
    if not path.exists():
        return readiness.make_check("operator_receipt", False, f"missing {path}")
    import json

    receipt = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "operator-action-receipt.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(receipt, schema)
    if errors:
        return readiness.make_check(
            "operator_receipt",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = receipt.get("status")
    return readiness.make_check(
        "operator_receipt",
        status in {"pending_operator_action", "verified"},
        f"status={status}; operator_executed={receipt.get('operator_executed')}; codex_execution_performed={receipt.get('codex_execution_performed')}",
    )


def check_host_prep_note(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("host_prep_note", True, "no host prep note manifest provided")
    if not path.exists():
        return readiness.make_check("host_prep_note", False, f"missing {path}")
    import json

    note = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "host-prep-note.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(note, schema)
    if errors:
        return readiness.make_check(
            "host_prep_note",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = note.get("status")
    return readiness.make_check(
        "host_prep_note",
        status in {"ready_for_operator", "no_action_needed"},
        f"status={status}; note_path={note.get('note_path')}",
    )


def check_isolation_proof(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("isolation_proof", True, "no microkernel isolation proof provided")
    if not path.exists():
        return readiness.make_check("isolation_proof", False, f"missing {path}")
    import json

    proof = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "isolation-proof.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(proof, schema)
    if errors:
        return readiness.make_check(
            "isolation_proof",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = proof.get("status")
    failed_count = proof.get("summary", {}).get("failed_check_count")
    security_boundary_claimed = proof.get("security_boundary_claimed")
    ok = status == "pass" and failed_count == 0 and security_boundary_claimed is False
    return readiness.make_check(
        "isolation_proof",
        ok,
        f"status={status}; failed_checks={failed_count}; security_boundary_claimed={security_boundary_claimed}",
    )


def check_capability_trap_proof(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("capability_trap_proof", True, "no capability trap proof provided")
    if not path.exists():
        return readiness.make_check("capability_trap_proof", False, f"missing {path}")
    import json

    proof = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "capability-trap-proof.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(proof, schema)
    if errors:
        return readiness.make_check(
            "capability_trap_proof",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = proof.get("status")
    summary = proof.get("summary", {})
    failed_count = summary.get("failed_check_count")
    trapped_count = summary.get("trapped_count")
    allowed_count = summary.get("allowed_count")
    security_boundary_claimed = proof.get("security_boundary_claimed")
    matrix_summary = proof.get("matrix_summary", {})
    fuzz_summary = proof.get("fuzz_summary", {})
    ok = (
        status == "pass"
        and failed_count == 0
        and trapped_count > 0
        and allowed_count > 0
        and security_boundary_claimed is False
        and matrix_summary.get("core_ir_executable_audit_bound") is True
        and matrix_summary.get("core_ir_executable_audit_status") in {"audited_non_promoting", "parser_to_kernel_ready"}
        and matrix_summary.get("core_ir_kernel_handoff_allowed") in {False, True}
        and matrix_summary.get("parser_kernel_promotion_receipt_bound") is True
        and matrix_summary.get("parser_kernel_promotion_receipt_status") in {"blocked_until_phase66", "parser_to_kernel_ready"}
        and matrix_summary.get("parser_kernel_promotion_kernel_handoff_allowed") in {False, True}
    )
    return readiness.make_check(
        "capability_trap_proof",
        ok,
        f"status={status}; failed_checks={failed_count}; trapped={trapped_count}; allowed={allowed_count}; matrix_bound={matrix_summary.get('matrix_bound', False)}; audit={matrix_summary.get('core_ir_executable_audit_status')}; promotion={matrix_summary.get('parser_kernel_promotion_receipt_status')}; fuzz_bound={fuzz_summary.get('fuzz_bound', False)}; security_boundary_claimed={security_boundary_claimed}",
    )


def check_capability_trap_fuzz(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("capability_trap_fuzz", True, "no capability trap fuzz proof provided")
    if not path.exists():
        return readiness.make_check("capability_trap_fuzz", False, f"missing {path}")
    import json

    fuzz = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "capability-trap-fuzz.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(fuzz, schema)
    if errors:
        return readiness.make_check(
            "capability_trap_fuzz",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = fuzz.get("status")
    summary = fuzz.get("summary", {})
    ok = (
        status == "pass"
        and summary.get("failed_check_count") == 0
        and summary.get("unknown_capability_count", 0) > 0
        and summary.get("unknown_permission_count", 0) > 0
        and summary.get("trapped_count") == summary.get("operation_count")
    )
    return readiness.make_check(
        "capability_trap_fuzz",
        ok,
        f"status={status}; operations={summary.get('operation_count')}; unknown_caps={summary.get('unknown_capability_count')}; unknown_permissions={summary.get('unknown_permission_count')}; trapped={summary.get('trapped_count')}",
    )


def check_pgb2_trap_encoding(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("pgb2_trap_encoding", True, "no PGB2 trap encoding provided")
    if not path.exists():
        return readiness.make_check("pgb2_trap_encoding", False, f"missing {path}")
    import json

    encoding = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "pgb2-trap-encoding.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(encoding, schema)
    if errors:
        return readiness.make_check(
            "pgb2_trap_encoding",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = encoding.get("status")
    summary = encoding.get("summary", {})
    source = encoding.get("source_trap_proof", {})
    ok = (
        status == "pass"
        and summary.get("failed_check_count") == 0
        and summary.get("instruction_count") == summary.get("source_operation_count")
        and summary.get("byte_length", 0) > 0
        and source.get("matrix_bound") is True
        and source.get("fuzz_bound") is True
        and source.get("core_ir_binding_mode") in {"metadata_only_non_promoting", "phase66_parser_to_kernel_promotable"}
        and source.get("core_ir_executable_audit_bound") is True
        and source.get("core_ir_executable_audit_status") in {"audited_non_promoting", "parser_to_kernel_ready"}
        and source.get("core_ir_kernel_handoff_allowed") in {False, True}
        and source.get("parser_kernel_promotion_receipt_bound") is True
        and source.get("parser_kernel_promotion_receipt_status") in {"blocked_until_phase66", "parser_to_kernel_ready"}
        and source.get("parser_kernel_promotion_kernel_handoff_allowed") in {False, True}
        and source.get("kernel_enforcement_claimed") is False
    )
    return readiness.make_check(
        "pgb2_trap_encoding",
        ok,
        f"status={status}; instructions={summary.get('instruction_count')}; bytes={summary.get('byte_length')}; matrix={source.get('matrix_bound')}; fuzz={source.get('fuzz_bound')}; core_ir={source.get('core_ir_binding_mode')}; audit={source.get('core_ir_executable_audit_status')}; promotion={source.get('parser_kernel_promotion_receipt_status')}",
    )


def check_pgb2_trap_execution(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("pgb2_trap_execution", True, "no PGB2 trap execution provided")
    if not path.exists():
        return readiness.make_check("pgb2_trap_execution", False, f"missing {path}")
    import json

    execution = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "pgb2-trap-execution.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(execution, schema)
    if errors:
        return readiness.make_check(
            "pgb2_trap_execution",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = execution.get("status")
    summary = execution.get("summary", {})
    encoding = execution.get("encoding_artifact", {})
    program = execution.get("program", {})
    ok = (
        status == "pass"
        and summary.get("failed_check_count") == 0
        and summary.get("encoded_instruction_count") == summary.get("executed_instruction_count")
        and summary.get("byte_length", 0) > 0
        and summary.get("outcome_mismatch_count") == 0
        and summary.get("decode_error_count") == 0
        and program.get("all_bytes_consumed") is True
        and execution.get("security_boundary_claimed") is False
        and encoding.get("matrix_bound") is True
        and encoding.get("fuzz_bound") is True
        and encoding.get("core_ir_binding_mode") in {"metadata_only_non_promoting", "phase66_parser_to_kernel_promotable"}
        and encoding.get("parser_kernel_promotion_receipt_bound") is True
        and encoding.get("parser_kernel_promotion_receipt_status") in {"blocked_until_phase66", "parser_to_kernel_ready"}
        and encoding.get("parser_kernel_promotion_kernel_handoff_allowed") in {False, True}
        and encoding.get("kernel_enforcement_claimed") is False
    )
    return readiness.make_check(
        "pgb2_trap_execution",
        ok,
        f"status={status}; executed={summary.get('executed_instruction_count')}; bytes={summary.get('byte_length')}; outcomes={summary.get('outcome_mismatch_count')}; matrix={encoding.get('matrix_bound')}; fuzz={encoding.get('fuzz_bound')}; core_ir={encoding.get('core_ir_binding_mode')}; promotion={encoding.get('parser_kernel_promotion_receipt_status')}",
    )


def check_pgb2_trap_abi_boundary_receipt(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("pgb2_trap_abi_boundary_receipt", True, "no PGB2 trap ABI boundary receipt provided")
    if not path.exists():
        return readiness.make_check("pgb2_trap_abi_boundary_receipt", False, f"missing {path}")
    import json

    receipt = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "pgb2-trap-abi-boundary-receipt.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(receipt, schema)
    if errors:
        return readiness.make_check(
            "pgb2_trap_abi_boundary_receipt",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = receipt.get("status")
    boundary = receipt.get("abi_boundary", {})
    claims = receipt.get("claim_boundaries", {})
    summary = receipt.get("summary", {})
    ok = (
        status == "draft_verified"
        and summary.get("failed_check_count") == 0
        and summary.get("source_overclaim_count") == 0
        and boundary.get("byte_format_classification") == "draft_trap_bytes"
        and boundary.get("abi_frozen") is False
        and boundary.get("kernel_abi_promotion_allowed") is False
        and boundary.get("kernel_enforcement_claimed") is False
        and boundary.get("security_boundary_claimed") is False
        and claims.get("draft_bytes_release_gate_usable") is True
        and claims.get("abi_freeze_evidence_present") is False
        and claims.get("kernel_abi_promotion_allowed") is False
        and claims.get("kernel_enforcement_claimed") is False
        and summary.get("bundle_trap_sections_present") is True
        and summary.get("boot_manifest_bound") is True
        and summary.get("qemu_contract_bound") is True
    )
    return readiness.make_check(
        "pgb2_trap_abi_boundary_receipt",
        ok,
        (
            f"status={status}; encoding={boundary.get('encoding_version')}; "
            f"execution={boundary.get('execution_version')}; abi_frozen={boundary.get('abi_frozen')}; "
            f"promotion={boundary.get('kernel_abi_promotion_allowed')}; overclaims={summary.get('source_overclaim_count')}"
        ),
    )


def check_pooleglyph_source_anchor(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("pooleglyph_source_anchor", True, "no PooleGlyph source anchor provided")
    if not path.exists():
        return readiness.make_check("pooleglyph_source_anchor", False, f"missing {path}")
    import json

    anchor = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "pooleglyph-source-anchor.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(anchor, schema)
    if errors:
        return readiness.make_check(
            "pooleglyph_source_anchor",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = anchor.get("status")
    latest = anchor.get("latest_checkpoint", {})
    summary = anchor.get("summary", {})
    return readiness.make_check(
        "pooleglyph_source_anchor",
        status in {"pass", "warn"},
        f"status={status}; commit={anchor.get('git', {}).get('commit')}; latest={latest.get('checkpoint')}; checkpoints={summary.get('checkpoint_manifest_count')}",
    )


def check_pooleglyph_bridge_manifest(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("pooleglyph_bridge_manifest", True, "no PooleGlyph bridge manifest provided")
    if not path.exists():
        return readiness.make_check("pooleglyph_bridge_manifest", False, f"missing {path}")
    import json

    manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "pooleglyph-bridge-manifest.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(manifest, schema)
    if errors:
        return readiness.make_check(
            "pooleglyph_bridge_manifest",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = manifest.get("status")
    summary = manifest.get("summary", {})
    source_anchor = manifest.get("source_anchor", {})
    diagnostic_summary = manifest.get("diagnostic_summary", {})
    ok = (
        status in {"pass", "warn"}
        and summary.get("failed_check_count") == 0
        and source_anchor.get("latest_phase", 0) >= 65
        and diagnostic_summary.get("diagnostic_case_count", 0) > 0
    )
    return readiness.make_check(
        "pooleglyph_bridge_manifest",
        ok,
        f"status={status}; latest_phase={source_anchor.get('latest_phase')}; bridge_maps={summary.get('bridge_map_count')}; diagnostics={diagnostic_summary.get('diagnostic_case_count')}",
    )


def check_pooleglyph_core_ir_boundary_receipt(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("pooleglyph_core_ir_boundary_receipt", True, "no PooleGlyph Core IR boundary receipt provided")
    if not path.exists():
        return readiness.make_check("pooleglyph_core_ir_boundary_receipt", False, f"missing {path}")
    import json

    receipt = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "pooleglyph-core-ir-boundary-receipt.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(receipt, schema)
    if errors:
        return readiness.make_check(
            "pooleglyph_core_ir_boundary_receipt",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = receipt.get("status")
    summary = receipt.get("summary", {})
    validation_summary = receipt.get("core_ir_validation_summary", {})
    ok = (
        status in {"phase66_pending", "validated_non_promoting", "parser_to_kernel_ready"}
        and summary.get("failed_check_count") == 0
        and summary.get("unexpected_invalid_count") == 0
        and receipt.get("kernel_enforcement_claimed") is False
        and validation_summary.get("validation_file_count", 0) > 0
        and validation_summary.get("validated_executable_candidate_count", 0) > 0
        and validation_summary.get("validated_metadata_zero_program_count", 0) > 0
    )
    return readiness.make_check(
        "pooleglyph_core_ir_boundary_receipt",
        ok,
        (
            f"status={status}; phase66={summary.get('phase66_audit_present')}; "
            f"promotion={summary.get('parser_to_kernel_promotion_allowed')}; "
            f"exec_candidates={validation_summary.get('validated_executable_candidate_count')}; "
            f"metadata_zero={validation_summary.get('validated_metadata_zero_program_count')}; "
            f"unexpected_invalid={validation_summary.get('unexpected_invalid_count')}"
        ),
    )


def check_pooleglyph_core_ir_executable_audit(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("pooleglyph_core_ir_executable_audit", True, "no PooleGlyph executable Core IR audit provided")
    if not path.exists():
        return readiness.make_check("pooleglyph_core_ir_executable_audit", False, f"missing {path}")
    import json

    audit = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "pooleglyph-core-ir-executable-audit.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(audit, schema)
    if errors:
        return readiness.make_check(
            "pooleglyph_core_ir_executable_audit",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = audit.get("status")
    summary = audit.get("summary", {})
    decisions = audit.get("boundary_decisions", {})
    ok = (
        status in {"audited_non_promoting", "parser_to_kernel_ready"}
        and summary.get("failed_check_count") == 0
        and summary.get("executable_candidate_count", 0) > 0
        and summary.get("metadata_zero_count", 0) > 0
        and summary.get("unexpected_invalid_count") == 0
        and summary.get("kernel_enforcement_claimed") is False
        and decisions.get("kernel_handoff_allowed") is summary.get("kernel_handoff_allowed")
        and (
            status == "parser_to_kernel_ready"
            or summary.get("parser_to_kernel_promotion_allowed") is False
        )
    )
    return readiness.make_check(
        "pooleglyph_core_ir_executable_audit",
        ok,
        (
            f"status={status}; phase66={summary.get('phase66_audit_present')}; "
            f"promotion={summary.get('parser_to_kernel_promotion_allowed')}; "
            f"exec_candidates={summary.get('executable_candidate_count')}; "
            f"metadata_zero={summary.get('metadata_zero_count')}; "
            f"kernel_handoff={summary.get('kernel_handoff_allowed')}"
        ),
    )


def check_pooleglyph_parser_kernel_promotion_receipt(path: Path | None) -> dict:
    if path is None:
        return readiness.make_check("pooleglyph_parser_kernel_promotion_receipt", True, "no PooleGlyph parser-to-kernel promotion receipt provided")
    if not path.exists():
        return readiness.make_check("pooleglyph_parser_kernel_promotion_receipt", False, f"missing {path}")
    import json

    receipt = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "pooleglyph-parser-kernel-promotion-receipt.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(receipt, schema)
    if errors:
        return readiness.make_check(
            "pooleglyph_parser_kernel_promotion_receipt",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = receipt.get("status")
    summary = receipt.get("summary", {})
    ok = (
        status in {"blocked_until_phase66", "parser_to_kernel_ready"}
        and summary.get("failed_check_count") == 0
        and summary.get("kernel_enforcement_claimed") is False
        and (
            status != "parser_to_kernel_ready"
            or (
                summary.get("phase66_audit_present") is True
                and summary.get("parser_to_kernel_promotion_allowed") is True
                and summary.get("kernel_handoff_allowed") is True
            )
        )
        and (
            status != "blocked_until_phase66"
            or (
                summary.get("parser_to_kernel_promotion_allowed") is False
                and summary.get("kernel_handoff_allowed") is False
            )
        )
    )
    return readiness.make_check(
        "pooleglyph_parser_kernel_promotion_receipt",
        ok,
        (
            f"status={status}; phase66={summary.get('phase66_audit_present')}; "
            f"promotion={summary.get('parser_to_kernel_promotion_allowed')}; "
            f"kernel_handoff={summary.get('kernel_handoff_allowed')}; "
            f"exec_candidates={summary.get('executable_candidate_count')}"
        ),
    )


def check_permission_capability_matrix(
    path: Path | None,
    *,
    require_core_ir_executable_audit: bool = False,
    require_parser_kernel_promotion_receipt: bool = False,
) -> dict:
    if path is None:
        return readiness.make_check("permission_capability_matrix", True, "no permission/capability matrix provided")
    if not path.exists():
        return readiness.make_check("permission_capability_matrix", False, f"missing {path}")
    import json

    matrix = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((ROOT / "specs" / "permission-capability-matrix.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(matrix, schema)
    if errors:
        return readiness.make_check(
            "permission_capability_matrix",
            False,
            "; ".join(f"{error.path}: {error.message}" for error in errors[:5]),
        )
    status = matrix.get("status")
    summary = matrix.get("summary", {})
    core = matrix.get("core_ir_boundary_receipt", {})
    audit = matrix.get("core_ir_executable_audit", {})
    promotion = matrix.get("parser_kernel_promotion_receipt", {})
    audit_bound = audit.get("exists") is True and summary.get("core_ir_executable_audit_bound") is True
    promotion_bound = promotion.get("exists") is True and summary.get("parser_kernel_promotion_receipt_bound") is True
    ok = (
        status in {"pass", "warn"}
        and summary.get("failed_check_count") == 0
        and summary.get("allowed_resource_permission_count", 0) > 0
        and summary.get("denied_resource_permission_count", 0) > 0
        and summary.get("trap_operation_count", 0) > 0
        and summary.get("core_ir_binding_mode") in {"metadata_only_non_promoting", "phase66_parser_to_kernel_promotable"}
        and summary.get("kernel_enforcement_claimed") is False
        and core.get("unexpected_invalid_count") == 0
        and (not require_core_ir_executable_audit or audit_bound)
        and (
            not audit_bound
            or (
                audit.get("status") in {"audited_non_promoting", "parser_to_kernel_ready"}
                and audit.get("failed_check_count") == 0
                and audit.get("kernel_enforcement_claimed") is False
            )
        )
        and (not require_parser_kernel_promotion_receipt or promotion_bound)
        and (
            not promotion_bound
            or (
                promotion.get("status") in {"blocked_until_phase66", "parser_to_kernel_ready"}
                and promotion.get("failed_check_count") == 0
                and promotion.get("kernel_enforcement_claimed") is False
            )
        )
    )
    return readiness.make_check(
        "permission_capability_matrix",
        ok,
        f"status={status}; resources={summary.get('resource_count')}; permissions={summary.get('permission_count')}; allowed={summary.get('allowed_resource_permission_count')}; denied={summary.get('denied_resource_permission_count')}; trap_ops={summary.get('trap_operation_count')}; core_ir={summary.get('core_ir_binding_mode')}; audit_bound={audit_bound}; audit={audit.get('status')}; promotion_bound={promotion_bound}; promotion={promotion.get('status')}",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit a PooleOS release-gate JSON report.")
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--replay-proof", type=Path)
    parser.add_argument("--pdc-source-intake", type=Path, default=ROOT / "runs" / "pdc_source_intake.json")
    parser.add_argument("--pdc-math-contract", type=Path, default=ROOT / "runs" / "pdc_math_contract.json")
    parser.add_argument("--pdc-golden-vectors", type=Path, default=ROOT / "runs" / "pdc_golden_vectors.json")
    parser.add_argument("--pdc-verifier-intake", type=Path, default=ROOT / "runs" / "pdc_verifier_intake.json")
    parser.add_argument(
        "--pdc-verifier-reproduction",
        type=Path,
        default=ROOT / "runs" / "pdc_verifier_reproduction.json",
    )
    parser.add_argument(
        "--pdc-representation-contract",
        type=Path,
        default=ROOT / "runs" / "pdc_representation_contract.json",
    )
    parser.add_argument(
        "--pdc-representation-receipt",
        type=Path,
        default=ROOT / "runs" / "pdc_representation_receipt.json",
    )
    parser.add_argument(
        "--pdc-golden-metamorphic-corpus",
        type=Path,
        default=ROOT / "runs" / "pdc_golden_metamorphic_corpus.json",
    )
    parser.add_argument(
        "--pdc-golden-metamorphic-receipt",
        type=Path,
        default=ROOT / "runs" / "pdc_golden_metamorphic_receipt.json",
    )
    parser.add_argument("--pdc-qp-contract", type=Path, default=ROOT / "runs" / "pdc_qp_contract.json")
    parser.add_argument("--pdc-qp-receipt", type=Path, default=ROOT / "runs" / "pdc_qp_receipt.json")
    parser.add_argument(
        "--pdc-qp-stability-contract",
        type=Path,
        default=ROOT / "runs" / "pdc_qp_stability_contract.json",
    )
    parser.add_argument(
        "--pdc-qp-stability-receipt",
        type=Path,
        default=ROOT / "runs" / "pdc_qp_stability_receipt.json",
    )
    parser.add_argument("--lab-manifest", type=Path)
    parser.add_argument("--boot-trap-bundle-manifest", type=Path)
    parser.add_argument("--qemu-shared-folder-contract", type=Path)
    parser.add_argument("--lab-guest-autostart", type=Path)
    parser.add_argument("--qemu-boot-evidence", type=Path)
    parser.add_argument("--qemu-captured-boot-preflight", type=Path)
    parser.add_argument("--qemu-captured-boot-launch-bundle", type=Path)
    parser.add_argument("--qemu-captured-boot-dry-run-checklist", type=Path)
    parser.add_argument("--qemu-boot-marker-contract", type=Path)
    parser.add_argument("--qemu-boot-marker-image-binding", type=Path)
    parser.add_argument("--rootfs-content-manifest", type=Path)
    parser.add_argument("--rootfs-extraction-handoff", type=Path)
    parser.add_argument("--rootfs-extraction-receipt", type=Path)
    parser.add_argument("--qemu-captured-boot-evidence", type=Path)
    parser.add_argument("--qemu-captured-boot-receipt", type=Path)
    parser.add_argument("--qemu-captured-boot-readiness", type=Path)
    parser.add_argument("--kernel-boot-handoff", type=Path)
    parser.add_argument("--kernel-pgvm2-loader-output", type=Path)
    parser.add_argument("--lab-kernel-transcript-export-receipt", type=Path)
    parser.add_argument("--kernel-pgvm2-loader-evidence", type=Path)
    parser.add_argument("--host-preflight", type=Path)
    parser.add_argument("--buildroot-probe", type=Path)
    parser.add_argument("--buildroot-configure", type=Path)
    parser.add_argument("--buildroot-build", type=Path)
    parser.add_argument("--wsl-prerequisites", type=Path)
    parser.add_argument("--operator-action", type=Path)
    parser.add_argument("--operator-receipt", type=Path)
    parser.add_argument("--host-prep-note", type=Path)
    parser.add_argument("--isolation-proof", type=Path)
    parser.add_argument("--capability-trap-proof", type=Path)
    parser.add_argument("--capability-trap-fuzz", type=Path)
    parser.add_argument("--pgb2-trap-encoding", type=Path)
    parser.add_argument("--pgb2-trap-execution", type=Path)
    parser.add_argument("--pgb2-trap-abi-boundary-receipt", type=Path)
    parser.add_argument("--pooleglyph-source-anchor", type=Path)
    parser.add_argument("--pooleglyph-bridge-manifest", type=Path)
    parser.add_argument("--pooleglyph-core-ir-boundary-receipt", type=Path)
    parser.add_argument("--pooleglyph-core-ir-executable-audit", type=Path)
    parser.add_argument("--pooleglyph-parser-kernel-promotion-receipt", type=Path)
    parser.add_argument("--permission-capability-matrix", type=Path)
    parser.add_argument("--native-roadmap", type=Path, default=NATIVE_ROADMAP)
    parser.add_argument("--native-checklist-coverage", type=Path, default=NATIVE_COVERAGE)
    parser.add_argument("--native-architecture-baseline", type=Path, default=NATIVE_ARCHITECTURE_BASELINE)
    parser.add_argument("--native-v1-objectives-readiness", type=Path, default=NATIVE_V1_OBJECTIVES_READINESS)
    parser.add_argument("--adr-ratification-readiness", type=Path, default=ADR_RATIFICATION_READINESS)
    parser.add_argument("--n0-owner-decision-packet", type=Path, default=N0_OWNER_DECISION_PACKET)
    parser.add_argument("--n0-owner-response-receipt", type=Path, default=N0_OWNER_RESPONSE_RECEIPT)
    parser.add_argument("--native-toolchain-qualification", type=Path, default=NATIVE_TOOLCHAIN_QUALIFICATION)
    parser.add_argument("--hardware-target-readiness", type=Path, default=HARDWARE_TARGET_READINESS)
    parser.add_argument("--native-tier0-readiness", type=Path, default=NATIVE_TIER0_READINESS)
    parser.add_argument("--native-model-readiness", type=Path, default=NATIVE_MODEL_READINESS)
    parser.add_argument("--native-boot-trust-readiness", type=Path, default=NATIVE_BOOT_TRUST_READINESS)
    parser.add_argument("--native-pooleboot-readiness", type=Path, default=NATIVE_POOLEBOOT_READINESS)
    parser.add_argument("--native-kernel-load-readiness", type=Path, default=NATIVE_KERNEL_LOAD_READINESS)
    parser.add_argument(
        "--native-kernel-revalidation-readiness",
        type=Path,
        default=NATIVE_KERNEL_REVALIDATION_READINESS,
    )
    parser.add_argument(
        "--native-kernel-transfer-readiness",
        type=Path,
        default=NATIVE_KERNEL_TRANSFER_READINESS,
    )
    parser.add_argument(
        "--native-kernel-trap-readiness",
        type=Path,
        default=NATIVE_KERNEL_TRAP_READINESS,
    )
    parser.add_argument(
        "--native-kernel-cpu-policy-readiness",
        type=Path,
        default=NATIVE_KERNEL_CPU_POLICY_READINESS,
    )
    parser.add_argument(
        "--native-initial-system-readiness",
        type=Path,
        default=NATIVE_INITIAL_SYSTEM_READINESS,
    )
    parser.add_argument(
        "--native-recovery-readiness",
        type=Path,
        default=NATIVE_RECOVERY_READINESS,
    )
    parser.add_argument(
        "--native-symbol-readiness",
        type=Path,
        default=NATIVE_SYMBOL_READINESS,
    )
    parser.add_argument(
        "--native-microcode-readiness",
        type=Path,
        default=NATIVE_MICROCODE_READINESS,
    )
    parser.add_argument(
        "--native-firmware-readiness",
        type=Path,
        default=NATIVE_FIRMWARE_READINESS,
    )
    parser.add_argument(
        "--native-policy-readiness",
        type=Path,
        default=NATIVE_POLICY_READINESS,
    )
    parser.add_argument(
        "--native-system-manifest-readiness",
        type=Path,
        default=NATIVE_SYSTEM_MANIFEST_READINESS,
    )
    parser.add_argument("--native-boot-handoff-readiness", type=Path, default=NATIVE_BOOT_HANDOFF_READINESS)
    parser.add_argument("--native-boot-config-readiness", type=Path, default=NATIVE_BOOT_CONFIG_READINESS)
    parser.add_argument("--native-elf-loader-readiness", type=Path, default=NATIVE_ELF_LOADER_READINESS)
    parser.add_argument("--native-kernel-entry-readiness", type=Path, default=NATIVE_KERNEL_ENTRY_READINESS)
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "release_gate.json")
    parser.add_argument("--include-runtime", action="store_true", help="Include PooleGlyph runtime checks in doctor.")
    args = parser.parse_args(argv)

    checks = [
        run_doctor(include_runtime=args.include_runtime),
        check_native_architecture_plan(args.native_roadmap, args.native_checklist_coverage),
        check_native_architecture_baseline(args.native_architecture_baseline),
        check_native_v1_objectives_readiness(args.native_v1_objectives_readiness),
        check_adr_ratification_readiness(args.adr_ratification_readiness),
        check_n0_owner_decision_packet(args.n0_owner_decision_packet),
        check_n0_owner_response_receipt(args.n0_owner_response_receipt),
        check_native_toolchain_qualification(args.native_toolchain_qualification),
        check_hardware_target_readiness(args.hardware_target_readiness),
        check_native_tier0_readiness(args.native_tier0_readiness),
        check_native_model_readiness(args.native_model_readiness),
        check_native_boot_trust_readiness(args.native_boot_trust_readiness),
        check_native_pooleboot_readiness(args.native_pooleboot_readiness),
        check_native_kernel_load_readiness(args.native_kernel_load_readiness),
        check_native_kernel_revalidation_readiness(args.native_kernel_revalidation_readiness),
        check_native_kernel_transfer_readiness(args.native_kernel_transfer_readiness),
        check_native_kernel_trap_readiness(args.native_kernel_trap_readiness),
        check_native_kernel_cpu_policy_readiness(args.native_kernel_cpu_policy_readiness),
        check_native_initial_system_readiness(args.native_initial_system_readiness),
        check_native_recovery_readiness(args.native_recovery_readiness),
        check_native_symbol_readiness(args.native_symbol_readiness),
        check_native_microcode_readiness(args.native_microcode_readiness),
        check_native_firmware_readiness(args.native_firmware_readiness),
        check_native_policy_readiness(args.native_policy_readiness),
        check_native_system_manifest_readiness(args.native_system_manifest_readiness),
        check_native_boot_handoff_readiness(args.native_boot_handoff_readiness),
        check_native_boot_config_readiness(args.native_boot_config_readiness),
        check_native_elf_loader_readiness(args.native_elf_loader_readiness),
        check_native_kernel_entry_readiness(args.native_kernel_entry_readiness),
        check_publication_boundary(),
        check_bundle(args.bundle),
        check_replay_proof(args.replay_proof),
        check_pdc_source_intake(args.pdc_source_intake),
        check_pdc_math_contract(args.pdc_math_contract, args.pdc_source_intake),
        check_pdc_golden_vectors(args.pdc_golden_vectors, args.pdc_math_contract),
        check_pdc_verifier_intake(args.pdc_verifier_intake, args.pdc_source_intake, args.pdc_math_contract),
        check_pdc_verifier_reproduction(
            args.pdc_verifier_reproduction,
            args.pdc_verifier_intake,
            args.pdc_math_contract,
        ),
        check_pdc_representation_contract(
            args.pdc_representation_contract,
            args.pdc_math_contract,
            args.pdc_golden_vectors,
            args.pdc_verifier_reproduction,
        ),
        check_pdc_representation_receipt(
            args.pdc_representation_receipt,
            args.pdc_representation_contract,
            args.pdc_math_contract,
            args.pdc_golden_vectors,
            args.pdc_verifier_reproduction,
        ),
        check_pdc_golden_metamorphic_corpus(
            args.pdc_golden_metamorphic_corpus,
            args.pdc_math_contract,
            args.pdc_golden_vectors,
            args.pdc_representation_contract,
            args.pdc_representation_receipt,
        ),
        check_pdc_golden_metamorphic_receipt(
            args.pdc_golden_metamorphic_receipt,
            args.pdc_golden_metamorphic_corpus,
            args.pdc_math_contract,
            args.pdc_golden_vectors,
            args.pdc_representation_contract,
            args.pdc_representation_receipt,
        ),
        check_pdc_qp_contract(
            args.pdc_qp_contract,
            args.pdc_source_intake,
            args.pdc_verifier_intake,
            args.pdc_math_contract,
        ),
        check_pdc_qp_receipt(
            args.pdc_qp_receipt,
            args.pdc_qp_contract,
            args.pdc_source_intake,
            args.pdc_verifier_intake,
            args.pdc_math_contract,
        ),
        check_pdc_qp_stability_contract(
            args.pdc_qp_stability_contract,
            args.pdc_qp_contract,
            args.pdc_qp_receipt,
        ),
        check_pdc_qp_stability_receipt(
            args.pdc_qp_stability_receipt,
            args.pdc_qp_stability_contract,
            args.pdc_qp_contract,
            args.pdc_qp_receipt,
        ),
        check_lab_scaffold(),
        check_lab_manifest(args.lab_manifest),
        check_boot_trap_bundle_manifest(args.boot_trap_bundle_manifest),
        check_qemu_shared_folder_contract(
            args.qemu_shared_folder_contract,
            require_abi_boundary_receipt=args.pgb2_trap_abi_boundary_receipt is not None,
        ),
        check_lab_guest_autostart(args.lab_guest_autostart),
        check_qemu_boot_evidence(args.qemu_boot_evidence),
        check_qemu_captured_boot_preflight(args.qemu_captured_boot_preflight),
        check_qemu_captured_boot_launch_bundle(args.qemu_captured_boot_launch_bundle),
        check_qemu_captured_boot_dry_run_checklist(args.qemu_captured_boot_dry_run_checklist),
        check_qemu_boot_marker_contract(args.qemu_boot_marker_contract),
        check_qemu_boot_marker_image_binding(args.qemu_boot_marker_image_binding),
        check_rootfs_content_manifest(args.rootfs_content_manifest),
        check_rootfs_extraction_handoff(args.rootfs_extraction_handoff),
        check_rootfs_extraction_receipt(args.rootfs_extraction_receipt),
        check_qemu_captured_boot_evidence(args.qemu_captured_boot_evidence),
        check_captured_qemu_rootfs_promotion(args.qemu_captured_boot_evidence, args.rootfs_extraction_receipt),
        check_qemu_captured_boot_receipt(args.qemu_captured_boot_receipt),
        check_qemu_captured_boot_readiness(args.qemu_captured_boot_readiness),
        check_kernel_boot_handoff(args.kernel_boot_handoff),
        check_kernel_pgvm2_loader_output(args.kernel_pgvm2_loader_output),
        check_lab_kernel_transcript_export_receipt(
            args.lab_kernel_transcript_export_receipt,
            args.kernel_pgvm2_loader_output,
        ),
        check_kernel_pgvm2_loader_evidence(args.kernel_pgvm2_loader_evidence),
        check_host_preflight(args.host_preflight),
        check_buildroot_probe(args.buildroot_probe),
        check_buildroot_configure(args.buildroot_configure),
        check_buildroot_build(args.buildroot_build),
        check_wsl_prerequisites(args.wsl_prerequisites),
        check_operator_action(args.operator_action),
        check_operator_receipt(args.operator_receipt),
        check_host_prep_note(args.host_prep_note),
        check_isolation_proof(args.isolation_proof),
        check_capability_trap_proof(args.capability_trap_proof),
        check_capability_trap_fuzz(args.capability_trap_fuzz),
        check_pgb2_trap_encoding(args.pgb2_trap_encoding),
        check_pgb2_trap_execution(args.pgb2_trap_execution),
        check_pgb2_trap_abi_boundary_receipt(args.pgb2_trap_abi_boundary_receipt),
        check_pooleglyph_source_anchor(args.pooleglyph_source_anchor),
        check_pooleglyph_bridge_manifest(args.pooleglyph_bridge_manifest),
        check_pooleglyph_core_ir_boundary_receipt(args.pooleglyph_core_ir_boundary_receipt),
        check_pooleglyph_core_ir_executable_audit(args.pooleglyph_core_ir_executable_audit),
        check_pooleglyph_parser_kernel_promotion_receipt(args.pooleglyph_parser_kernel_promotion_receipt),
        check_permission_capability_matrix(
            args.permission_capability_matrix,
            require_core_ir_executable_audit=args.pooleglyph_core_ir_executable_audit is not None,
            require_parser_kernel_promotion_receipt=args.pooleglyph_parser_kernel_promotion_receipt is not None,
        ),
    ]
    artifacts = [
        str(path)
        for path in (
            args.bundle,
            args.replay_proof,
            args.pdc_source_intake,
            args.pdc_math_contract,
            args.pdc_golden_vectors,
            args.pdc_verifier_intake,
            args.pdc_verifier_reproduction,
            args.pdc_representation_contract,
            args.pdc_representation_receipt,
            args.pdc_golden_metamorphic_corpus,
            args.pdc_golden_metamorphic_receipt,
            args.pdc_qp_contract,
            args.pdc_qp_receipt,
            args.pdc_qp_stability_contract,
            args.pdc_qp_stability_receipt,
            args.lab_manifest,
            args.boot_trap_bundle_manifest,
            args.qemu_shared_folder_contract,
            args.lab_guest_autostart,
            args.qemu_boot_evidence,
            args.qemu_captured_boot_preflight,
            args.qemu_captured_boot_launch_bundle,
            args.qemu_captured_boot_dry_run_checklist,
            args.qemu_boot_marker_contract,
            args.qemu_boot_marker_image_binding,
            args.rootfs_content_manifest,
            args.rootfs_extraction_handoff,
            args.rootfs_extraction_receipt,
            args.qemu_captured_boot_evidence,
            args.qemu_captured_boot_receipt,
            args.qemu_captured_boot_readiness,
            args.kernel_boot_handoff,
            args.kernel_pgvm2_loader_output,
            args.lab_kernel_transcript_export_receipt,
            args.kernel_pgvm2_loader_evidence,
            args.host_preflight,
            args.buildroot_probe,
            args.buildroot_configure,
            args.buildroot_build,
            args.wsl_prerequisites,
            args.operator_action,
            args.operator_receipt,
            args.host_prep_note,
            args.isolation_proof,
            args.capability_trap_proof,
            args.capability_trap_fuzz,
            args.pgb2_trap_encoding,
            args.pgb2_trap_execution,
            args.pgb2_trap_abi_boundary_receipt,
            args.pooleglyph_source_anchor,
            args.pooleglyph_bridge_manifest,
            args.pooleglyph_core_ir_boundary_receipt,
            args.pooleglyph_core_ir_executable_audit,
            args.pooleglyph_parser_kernel_promotion_receipt,
            args.permission_capability_matrix,
            args.native_roadmap,
            args.native_checklist_coverage,
            args.native_architecture_baseline,
            args.native_v1_objectives_readiness,
            args.adr_ratification_readiness,
            args.n0_owner_decision_packet,
            args.n0_owner_response_receipt,
            args.native_toolchain_qualification,
            args.hardware_target_readiness,
            args.native_tier0_readiness,
            args.native_model_readiness,
            args.native_boot_trust_readiness,
            args.native_pooleboot_readiness,
            args.native_kernel_load_readiness,
            args.native_kernel_revalidation_readiness,
            args.native_kernel_transfer_readiness,
            args.native_kernel_trap_readiness,
            args.native_kernel_cpu_policy_readiness,
            args.native_initial_system_readiness,
            args.native_recovery_readiness,
            args.native_symbol_readiness,
            args.native_microcode_readiness,
            args.native_firmware_readiness,
            args.native_policy_readiness,
            args.native_system_manifest_readiness,
            args.native_boot_handoff_readiness,
            args.native_boot_config_readiness,
            args.native_elf_loader_readiness,
            args.native_kernel_entry_readiness,
        )
        if path is not None
    ]
    report = readiness.make_readiness_report(checks=checks, artifacts=artifacts, remaining_gaps=DEFAULT_GAPS)
    readiness.write_readiness_report(report, args.out)
    print(args.out)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
