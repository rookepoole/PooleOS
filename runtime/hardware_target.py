"""Privacy-preserving Tier-1 hardware target evidence for PooleOS."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POLICY_RELATIVE = "specs/hardware-support-policy.json"
POLICY_SCHEMA_RELATIVE = "specs/hardware-support-policy.schema.json"
STANDARDS_RELATIVE = "specs/native-standards-register.json"
STANDARDS_SCHEMA_RELATIVE = "specs/native-standards-register.schema.json"
TARGET_RELATIVE = "specs/tier1-hardware-target.json"
TARGET_SCHEMA_RELATIVE = "specs/tier1-hardware-target.schema.json"
CAPTURE_SCHEMA_RELATIVE = "specs/tier1-hardware-capture.schema.json"
OBSERVATION_RELATIVE = "runs/tier1_hardware_observation.json"
OBSERVATION_SCHEMA_RELATIVE = "specs/tier1-hardware-observation.schema.json"
READINESS_RELATIVE = "runs/hardware_target_readiness.json"
READINESS_SCHEMA_RELATIVE = "specs/hardware-target-readiness.schema.json"
COLLECTOR_RELATIVE = "tools/collect_tier1_hardware.ps1"

SHA256_PATTERN = re.compile(r"^[0-9A-F]{64}$")
ABSOLUTE_USER_PATH = re.compile(
    r"(?:[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/][^\\/\s]+|/(?:Users|home)/[^/\s]+)",
    flags=re.IGNORECASE,
)
MAC_ADDRESS = re.compile(r"(?<![0-9A-Fa-f])(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}(?![0-9A-Fa-f])")
FULL_PNP_INSTANCE = re.compile(r"^(?:PCI|USB|HDAUDIO|BTH|ACPI)\\[^\\\r\n]+\\[^\\\r\n]+", re.IGNORECASE)
PROHIBITED_KEY_PARTS = (
    "serial",
    "uuid",
    "mac_address",
    "physical_address",
    "ip_address",
    "hostname",
    "host_name",
    "computer_name",
    "username",
    "user_name",
    "user_profile",
    "instance_id",
    "device_instance",
    "pnp_device_id",
    "tpm_ek",
    "endorsement_key",
)


class HardwareEvidenceError(RuntimeError):
    """Raised when hardware evidence is malformed, unsafe, or inconsistent."""


def canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise HardwareEvidenceError(f"JSON root must be an object: {path.name}")
    return value


def _safe_relative(root: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute():
        raise HardwareEvidenceError(f"repository path must be relative: {relative!r}")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as error:
        raise HardwareEvidenceError(f"repository path escapes root: {relative!r}") from error
    return candidate


def file_binding(root: Path, relative: str) -> dict[str, Any]:
    path = _safe_relative(root, relative)
    data = path.read_bytes()
    return {"path": relative.replace("\\", "/"), "sha256": sha256_bytes(data), "byte_count": len(data)}


def schema_errors(value: dict[str, Any], root: Path, schema_relative: str) -> list[str]:
    from runtime.schema_validation import validate_json

    schema = read_json(root / schema_relative)
    return [f"{error.path}: {error.message}" for error in validate_json(value, schema)]


def _trim(value: Any) -> str:
    return str(value or "").strip()


def _records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def _first(value: Any) -> dict[str, Any]:
    records = _records(value)
    return records[0] if records else {}


def scan_public_privacy(value: Any, *, path: str = "$") -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            folded = key.casefold()
            negative_attestation = child is False and folded.endswith(("_published", "_present", "_collected", "_requested"))
            if any(part in folded for part in PROHIBITED_KEY_PARTS) and not negative_attestation:
                violations.append({"path": f"{path}.{key}", "type": "prohibited_field", "detail": key})
            violations.extend(scan_public_privacy(child, path=f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            violations.extend(scan_public_privacy(child, path=f"{path}[{index}]"))
    elif isinstance(value, str):
        if ABSOLUTE_USER_PATH.search(value):
            violations.append({"path": path, "type": "absolute_user_path", "detail": "workstation user path"})
        if MAC_ADDRESS.search(value):
            violations.append({"path": path, "type": "mac_address", "detail": "link-layer address"})
        if FULL_PNP_INSTANCE.search(value):
            violations.append({"path": path, "type": "full_pnp_instance", "detail": "device instance suffix"})
    return sorted(violations, key=lambda item: (item["path"], item["type"], item["detail"]))


def _capture_status(raw: dict[str, Any], *keys: str, fallback: str = "unavailable") -> str:
    value: Any = raw
    for key in keys:
        if not isinstance(value, dict):
            return fallback
        value = value.get(key)
    if isinstance(value, dict):
        return _trim(value.get("status")) or fallback
    return fallback


def _build_evidence_channels(raw: dict[str, Any], facts: dict[str, Any]) -> list[dict[str, str]]:
    acpi_status = _capture_status(raw, "firmware_tables", "acpi")
    smbios_status = _capture_status(raw, "firmware_tables", "smbios")
    secure_boot_status = _capture_status(raw, "security", "secure_boot")
    tpm_status = _capture_status(raw, "security", "tpm")
    monitor_status = _capture_status(raw, "monitor")
    sensor_status = _capture_status(raw, "sensors_power")
    acpi = raw.get("firmware_tables", {}).get("acpi", {})
    signatures = {item.get("signature") for item in _records(acpi.get("tables"))}
    return [
        {"id": "CIM_CORE_INVENTORY", "status": "observed", "detail": "allowlisted board, firmware, CPU, memory, storage, display, and network properties"},
        {"id": "PNP_HARDWARE_PREFIXES", "status": "observed" if facts["pnp.hardware_prefixes"] else "unavailable", "detail": "bus and hardware identifiers only; instance suffixes removed"},
        {"id": "UEFI_FIRMWARE_TYPE", "status": "observed" if facts["host.firmware_type"] == "UEFI" else "unavailable", "detail": facts["host.firmware_type"] or "not reported"},
        {"id": "ACPI_TABLE_HASHES", "status": acpi_status, "detail": "table signatures, byte counts, and SHA-256 only"},
        {"id": "SMBIOS_RAW_HASH", "status": smbios_status, "detail": "raw table bytes are not published"},
        {"id": "AMD_IOMMU_IVRS", "status": "observed" if "IVRS" in signatures else "unavailable", "detail": "derived only from ACPI IVRS presence"},
        {"id": "SECURE_BOOT_STATE", "status": secure_boot_status, "detail": "read-only Confirm-SecureBootUEFI query"},
        {"id": "TPM_INVENTORY", "status": tpm_status, "detail": "no EK, certificate, owner state, or key material requested"},
        {"id": "EDID_IDENTITY", "status": monitor_status, "detail": "serial field excluded; full EDID acquisition remains separate"},
        {"id": "CPU_CPUID_MSR", "status": "pending_tool", "detail": "CIM values do not replace leaf/subleaf CPUID and MSR capture"},
        {"id": "PCI_CONFIG_SPACE", "status": "pending_tool", "detail": "PnP identifiers do not replace ECAM/configuration-space capture"},
        {"id": "SPD_MEMORY_TOPOLOGY", "status": "partial", "detail": "CIM part/capacity/channel facts only; raw SPD not acquired"},
        {"id": "SENSORS_AND_POWER", "status": sensor_status, "detail": "no firmware writes, fan changes, stress load, or power action performed"},
        {"id": "UEFI_VARIABLE_SNAPSHOT", "status": "pending_tool", "detail": "no NVRAM variable values acquired in this cycle"},
    ]


def sanitize_capture(capture: dict[str, Any], capture_bytes: bytes, root: Path = ROOT, *, status_date: str = "2026-07-16") -> dict[str, Any]:
    capture_schema_failures = schema_errors(capture, root, CAPTURE_SCHEMA_RELATIVE)
    if capture_schema_failures:
        raise HardwareEvidenceError("private capture schema invalid: " + "; ".join(capture_schema_failures))
    if capture.get("collection_mode") != "read_only":
        raise HardwareEvidenceError("private capture is not marked read-only")
    guards = capture.get("mutation_guard", {})
    if not guards or any(value is not False for value in guards.values()):
        raise HardwareEvidenceError("private capture mutation guard is not fail-closed")

    collector = file_binding(root, COLLECTOR_RELATIVE)
    if capture["collector"]["script_sha256"] != collector["sha256"]:
        raise HardwareEvidenceError("private capture was not emitted by the current collector bytes")

    system = capture["system"]
    board = _first(system["baseboard"])
    bios = _first(system["bios"])
    cpu = _first(capture["processor"])
    memory = _records(capture["memory"])
    disks = _records(capture["storage"])
    display = _first(capture["display"])
    pnp = _records(capture["pnp_devices"])
    prefixes = sorted({_trim(item.get("hardware_prefix")) for item in pnp if _trim(item.get("hardware_prefix"))})
    memory_parts = sorted(_trim(item.get("part_number")) for item in memory)
    memory_capacities = sorted(int(item.get("capacity_bytes") or 0) for item in memory)
    memory_speeds = sorted(int(item.get("configured_speed_mt_s") or 0) for item in memory)
    disk_records = sorted(
        f"{_trim(item.get('model'))}|{_trim(item.get('firmware_revision'))}|{int(item.get('size_bytes') or 0)}"
        for item in disks
    )
    host_context = capture["host_context"]
    firmware_type = _trim(host_context["firmware_type"].get("value"))
    facts: dict[str, Any] = {
        "baseboard.manufacturer": _trim(board.get("manufacturer")),
        "baseboard.product": _trim(board.get("product")),
        "baseboard.version": _trim(board.get("version")),
        "bios.manufacturer": _trim(bios.get("manufacturer")),
        "bios.version": _trim(bios.get("version")),
        "bios.smbios_version": _trim(bios.get("smbios_version")),
        "bios.cim_release_date_utc": _trim(bios.get("release_date_utc")),
        "cpu.name": _trim(cpu.get("name")),
        "cpu.manufacturer": _trim(cpu.get("manufacturer")),
        "cpu.cim_family_code": int(cpu.get("cim_family_code") or 0),
        "cpu.cim_stepping": _trim(cpu.get("cim_stepping")),
        "cpu.cim_revision": int(cpu.get("cim_revision") or 0),
        "cpu.core_count": int(cpu.get("core_count") or 0),
        "cpu.logical_processor_count": int(cpu.get("logical_processor_count") or 0),
        "cpu.socket": _trim(cpu.get("socket")),
        "memory.module_count": len(memory),
        "memory.total_capacity_bytes": sum(memory_capacities),
        "memory.part_numbers": memory_parts,
        "memory.module_capacities_bytes": memory_capacities,
        "memory.configured_speeds_mt_s": memory_speeds,
        "storage.records": disk_records,
        "display.name": _trim(display.get("name")),
        "display.current_resolution": f"{int(display.get('horizontal_resolution') or 0)}x{int(display.get('vertical_resolution') or 0)}",
        "pnp.hardware_prefixes": prefixes,
        "host.firmware_type": firmware_type,
        "host.hypervisor_present": bool(host_context.get("hypervisor_present")),
    }

    acpi = capture["firmware_tables"]["acpi"]
    smbios = capture["firmware_tables"]["smbios"]
    acpi_tables = [
        {
            "signature": _trim(item.get("signature")),
            "byte_count": int(item.get("byte_count") or 0),
            "sha256": _trim(item.get("sha256")),
        }
        for item in _records(acpi.get("tables"))
        if _trim(item.get("signature")) and SHA256_PATTERN.fullmatch(_trim(item.get("sha256")))
    ]
    acpi_tables.sort(key=lambda item: (item["signature"], item["sha256"]))
    evidence_channels = _build_evidence_channels(capture, facts)
    observation = {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_tier1_hardware_observation",
        "status_date": status_date,
        "status": "captured_partial_non_promoting",
        "selected_move_id": "N2-HW-001",
        "target_id": "TIER1-B650M-9800X3D-RTX5070-001",
        "production_ready": False,
        "production_promotion_allowed": False,
        "bindings": {
            "collector": collector,
            "private_capture": {
                "artifact_kind": capture["artifact_kind"],
                "sha256": sha256_bytes(capture_bytes),
                "byte_count": len(capture_bytes),
                "path_recorded": False,
                "content_publication_allowed": False,
            },
        },
        "collection": {
            "mode": "read_only",
            "collector_version": capture["collector"]["version"],
            "raw_values_published": False,
            "host_identity_published": False,
        },
        "facts": facts,
        "firmware_table_evidence": {
            "acpi_status": _trim(acpi.get("status")),
            "acpi_enumerated_signature_count": int(acpi.get("enumerated_signature_count") or 0),
            "acpi_tables": acpi_tables,
            "acpi_duplicate_retrieval_limitation": True,
            "smbios_status": _trim(smbios.get("status")),
            "smbios_byte_count": int(smbios.get("byte_count") or 0),
            "smbios_sha256": _trim(smbios.get("sha256")),
            "raw_table_bytes_published": False,
        },
        "security_observation": {
            "secure_boot_status": _capture_status(capture, "security", "secure_boot"),
            "secure_boot_enabled": capture["security"]["secure_boot"].get("value"),
            "tpm_status": _capture_status(capture, "security", "tpm"),
            "tpm_key_or_certificate_material_requested": False,
        },
        "evidence_channels": evidence_channels,
        "privacy": {
            "sanitization_mode": "fixed_whitelist_reconstruction",
            "serials_published": False,
            "mac_addresses_published": False,
            "uuids_published": False,
            "full_pnp_instance_paths_published": False,
            "user_or_host_names_published": False,
            "absolute_local_paths_published": False,
            "tpm_ek_material_published": False,
            "privacy_violation_count": 0,
        },
        "limitations": [
            "This observation is a sanitized Windows-host view, not PooleKernel enumeration evidence.",
            "CIM and PnP values do not replace raw PCI configuration space, CPUID/MSR, complete EDID, SPD, or native ACPI parser evidence.",
            "Windows firmware-table APIs return only the first ACPI table for a duplicated signature.",
            "The private capture hash permits owner-side correlation but does not make private evidence independently reproducible from the public checkout.",
            "No destructive, privileged configuration, firmware, TPM, disk, boot, power, or device action was performed.",
        ],
    }
    violations = scan_public_privacy(observation)
    if violations:
        raise HardwareEvidenceError(f"sanitized observation violates public privacy boundary: {violations}")
    return observation


def compare_target(target: dict[str, Any], observation: dict[str, Any]) -> list[dict[str, Any]]:
    facts = observation.get("facts", {})
    checks: list[dict[str, Any]] = []
    for rule in target["verification_contract"]:
        fact = rule["fact"]
        expected = rule["expected"]
        present = fact in facts
        actual = facts.get(fact)
        operator = rule["operator"]
        matched = False
        if present and operator == "equals":
            matched = actual == expected
        elif present and operator == "contains_all" and isinstance(actual, list) and isinstance(expected, list):
            matched = not (Counter(json.dumps(item, sort_keys=True) for item in expected) - Counter(json.dumps(item, sort_keys=True) for item in actual))
        elif present and operator == "multiset_equals" and isinstance(actual, list) and isinstance(expected, list):
            matched = Counter(json.dumps(item, sort_keys=True) for item in actual) == Counter(json.dumps(item, sort_keys=True) for item in expected)
        status = "match" if matched else ("missing" if not present else "mismatch")
        checks.append(
            {
                "id": rule["id"],
                "fact": fact,
                "operator": operator,
                "required": rule["required"],
                "status": status,
                "expected": expected,
                "observed": actual if present else "not_observed",
            }
        )
    return checks


def _negative_controls(policy: dict[str, Any], target: dict[str, Any], observation: dict[str, Any]) -> list[dict[str, str]]:
    controls: list[tuple[str, bool]] = []
    controls.append(("reject_serial_field", bool(scan_public_privacy({"serial_number": "SAMPLE"}))))
    controls.append(("reject_mac_address", bool(scan_public_privacy({"value": "00:11:22:33:44:55"}))))
    controls.append(("reject_absolute_user_path", bool(scan_public_privacy({"value": r"C:\Users\sample\capture.json"}))))
    controls.append(("reject_full_pnp_instance", bool(scan_public_privacy({"value": r"PCI\VEN_1234&DEV_5678\INSTANCE"}))))

    wrong_board = copy.deepcopy(observation)
    wrong_board["facts"]["baseboard.product"] = "SUBSTITUTED"
    controls.append(("reject_substituted_baseboard", any(item["status"] == "mismatch" for item in compare_target(target, wrong_board))))
    missing_cpu = copy.deepcopy(observation)
    missing_cpu["facts"].pop("cpu.name", None)
    controls.append(("reject_missing_required_fact", any(item["status"] == "missing" for item in compare_target(target, missing_cpu))))
    wrong_target = copy.deepcopy(observation)
    wrong_target["target_id"] = "TIER1-SUBSTITUTED"
    controls.append(("reject_target_identity_substitution", wrong_target["target_id"] != target["target_id"]))
    controls.append(("deny_destructive_testing_without_acceptance", policy["destructive_safety"]["current_approval"] is False))
    controls.append(("deny_unlisted_hardware_promotion", policy["default_disposition"]["unlisted_hardware"] == "unsupported"))
    controls.append(("deny_private_capture_publication", policy["privacy_boundary"]["raw_capture_publication_allowed"] is False))
    return [
        {"id": control_id, "expected": "reject", "observed": "reject" if passed else "accept", "status": "pass" if passed else "fail"}
        for control_id, passed in controls
    ]


def build_readiness(root: Path = ROOT) -> dict[str, Any]:
    policy = read_json(root / POLICY_RELATIVE)
    standards = read_json(root / STANDARDS_RELATIVE)
    target = read_json(root / TARGET_RELATIVE)
    observation = read_json(root / OBSERVATION_RELATIVE)
    schema_results = {
        "policy": schema_errors(policy, root, POLICY_SCHEMA_RELATIVE),
        "standards_register": schema_errors(standards, root, STANDARDS_SCHEMA_RELATIVE),
        "target": schema_errors(target, root, TARGET_SCHEMA_RELATIVE),
        "observation": schema_errors(observation, root, OBSERVATION_SCHEMA_RELATIVE),
    }
    privacy_violations = scan_public_privacy(observation)
    target_checks = compare_target(target, observation)
    required_failures = [item for item in target_checks if item["required"] and item["status"] != "match"]
    negative_controls = _negative_controls(policy, target, observation)
    binding_errors: list[str] = []
    collector_binding = observation.get("bindings", {}).get("collector", {})
    expected_collector = file_binding(root, COLLECTOR_RELATIVE)
    if collector_binding != expected_collector:
        binding_errors.append("observation collector binding does not match current collector bytes")
    if observation.get("target_id") != target.get("target_id"):
        binding_errors.append("observation target_id does not match exact Tier-1 target")

    standards_entries = standards["entries"]
    locked_standards = [item for item in standards_entries if item["lock_status"] == "locked_metadata_verified"]
    hashed_standards = [item for item in standards_entries if item["artifact_hash_status"] == "verified"]
    unresolved_standards = [item["id"] for item in standards_entries if item["lock_status"] != "locked_metadata_verified" or item["artifact_hash_status"] != "verified"]
    channels = observation["evidence_channels"]
    required_channel_ids = set(policy["evidence_requirements"]["n2_exit_required_channel_ids"])
    satisfied_channel_ids = {item["id"] for item in channels if item["status"] == "observed"}
    pending_channels = sorted(required_channel_ids - satisfied_channel_ids)
    safety_items = policy["destructive_safety"]["prerequisites"]
    pending_safety = [item["id"] for item in safety_items if item["status"] != "accepted"]
    schema_failure_count = sum(len(errors) for errors in schema_results.values())
    consistency_ok = (
        schema_failure_count == 0
        and not privacy_violations
        and not required_failures
        and not binding_errors
        and all(item["status"] == "pass" for item in negative_controls)
    )
    n2_exit_ready = (
        consistency_ok
        and not unresolved_standards
        and not pending_channels
        and not pending_safety
        and policy["destructive_safety"]["current_approval"] is True
    )
    status = "n2_exit_ready_non_production" if n2_exit_ready else ("consistent_partial_non_promoting" if consistency_ok else "invalid")
    open_items = [
        "Reconcile the vendor BIOS release date with the CIM UTC date representation.",
        "Acquire full CPUID/MSR, PCI configuration-space, EDID, SPD, ACPI duplicate-table, UEFI-variable, sensor, and power evidence with reviewed read-only tools.",
        "Resolve TPM inventory permission without requesting EK, certificate, owner, or secret material.",
        "Acquire and hash every lawfully accessible locked standard and complete supersession/errata review.",
        "Owner must separately identify sacrificial media, backups, immutable recovery, a second recovery machine, serial path, power-cut apparatus, and explicit destructive-test approval.",
        "Define and qualify the Tier-0 QEMU/OVMF target under N4 before N2 can close.",
    ]
    return {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_hardware_target_readiness",
        "status_date": observation["status_date"],
        "status": status,
        "selected_move_id": "N2-HW-001",
        "target_id": target["target_id"],
        "production_ready": False,
        "production_promotion_allowed": False,
        "n2_exit_gate_satisfied": n2_exit_ready,
        "bindings": {
            "support_policy": file_binding(root, POLICY_RELATIVE),
            "standards_register": file_binding(root, STANDARDS_RELATIVE),
            "tier1_target": file_binding(root, TARGET_RELATIVE),
            "sanitized_observation": file_binding(root, OBSERVATION_RELATIVE),
            "collector": expected_collector,
            "runtime": file_binding(root, "runtime/hardware_target.py"),
        },
        "schema_validation": {"failure_count": schema_failure_count, "results": schema_results},
        "privacy_validation": {
            "mode": "fixed_whitelist_reconstruction_plus_recursive_scan",
            "violation_count": len(privacy_violations),
            "violations": privacy_violations,
            "private_capture_content_present": False,
        },
        "target_verification": {
            "required_check_count": sum(item["required"] for item in target_checks),
            "matched_required_check_count": sum(item["required"] and item["status"] == "match" for item in target_checks),
            "required_failure_count": len(required_failures),
            "checks": target_checks,
            "known_discrepancies": target["known_discrepancies"],
        },
        "evidence_coverage": {
            "required_channel_count": len(required_channel_ids),
            "observed_required_channel_count": len(required_channel_ids & satisfied_channel_ids),
            "pending_required_channel_ids": pending_channels,
            "channels": channels,
        },
        "standards_coverage": {
            "entry_count": len(standards_entries),
            "metadata_locked_count": len(locked_standards),
            "artifact_hash_verified_count": len(hashed_standards),
            "unresolved_entry_ids": unresolved_standards,
            "supersession_review_ids": [item["id"] for item in standards_entries if item["supersession_review"] != "none_required"],
        },
        "lab_safety": {
            "destructive_testing_approved": policy["destructive_safety"]["current_approval"],
            "prerequisite_count": len(safety_items),
            "accepted_prerequisite_count": len(safety_items) - len(pending_safety),
            "pending_prerequisite_ids": pending_safety,
            "mutation_performed": False,
        },
        "negative_controls": negative_controls,
        "summary": {
            "consistency_pass": consistency_ok,
            "schema_failure_count": schema_failure_count,
            "privacy_violation_count": len(privacy_violations),
            "required_target_check_count": sum(item["required"] for item in target_checks),
            "matched_required_target_check_count": sum(item["required"] and item["status"] == "match" for item in target_checks),
            "pending_evidence_channel_count": len(pending_channels),
            "unresolved_standard_count": len(unresolved_standards),
            "pending_lab_safety_count": len(pending_safety),
            "negative_control_count": len(negative_controls),
            "negative_control_pass_count": sum(item["status"] == "pass" for item in negative_controls),
        },
        "binding_errors": binding_errors,
        "open_items": open_items,
        "claim_boundary": [
            "This ledger proves that a sanitized Windows-host observation consistently matches the declared Tier-1 identity checks; it is not PooleBoot or PooleKernel hardware enumeration evidence.",
            "A matching model, firmware, or hardware-ID prefix does not qualify a native driver, DMA confinement, reset, power, recovery, update, or daily-driver claim.",
            "Private capture bytes remain local and are represented publicly only by SHA-256 and byte count.",
            "Unresolved standards, evidence channels, and destructive-test prerequisites keep N2 open and production promotion prohibited.",
            "No firmware, TPM, disk, boot, power, device, or configuration mutation was authorized or performed.",
        ],
    }


def write_json(value: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))
