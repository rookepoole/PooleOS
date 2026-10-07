"""Independent PKERR1 oracle for the Ryzen 7 9800X3D target policy."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from runtime.schema_validation import validate_json


CONTRACT_ID = "PKERR1"
SELECTED_MOVE_ID = "N7-ERRATA-POLICY-001"
ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE = "specs/native-kernel-errata-policy-contract.json"
CONTRACT_SCHEMA_RELATIVE = "specs/native-kernel-errata-policy-contract.schema.json"
READINESS_SCHEMA_RELATIVE = "specs/native-kernel-errata-policy-readiness.schema.json"
READINESS_RELATIVE = "runs/native-kernel-errata-policy-readiness.json"

TARGET_CPUID_SIGNATURE = 0x00B40F40
WINDOWS_REPORTED_MICROCODE_REVISION = 0x0B404023

FEATURE_LONG_MODE = 1 << 0
FEATURE_NX = 1 << 1
FEATURE_SSE2 = 1 << 2
FEATURE_XSAVE = 1 << 3
FEATURE_OSXSAVE = 1 << 4
FEATURE_FSGSBASE = 1 << 5
FEATURE_SMEP = 1 << 6
FEATURE_SMAP = 1 << 7
FEATURE_INVARIANT_TSC = 1 << 8
REQUIRED_FEATURES = (
    FEATURE_LONG_MODE
    | FEATURE_NX
    | FEATURE_SSE2
    | FEATURE_XSAVE
    | FEATURE_OSXSAVE
    | FEATURE_FSGSBASE
    | FEATURE_SMEP
    | FEATURE_SMAP
    | FEATURE_INVARIANT_TSC
)

FAILURE_IDENTITY = 1 << 0
FAILURE_FEATURES = 1 << 1
FAILURE_BOARD_LINEAGE = 1 << 2
FAILURE_BIOS_FLOOR = 1 << 3
FAILURE_AGESA_FLOOR = 1 << 4
FAILURE_MICROCODE_EVIDENCE = 1 << 5
FAILURE_MICROCODE_FLOOR_SOURCE = 1 << 6
FAILURE_ERRATA_GUIDE = 1 << 7
FAILURE_RDSEED_POLICY = 1 << 8
FAILURE_SOURCE_APPLICABILITY = 1 << 9

FAILURE_NAMES = {
    FAILURE_IDENTITY: "identity",
    FAILURE_FEATURES: "features",
    FAILURE_BOARD_LINEAGE: "board_lineage",
    FAILURE_BIOS_FLOOR: "bios_floor",
    FAILURE_AGESA_FLOOR: "agesa_floor",
    FAILURE_MICROCODE_EVIDENCE: "microcode_evidence",
    FAILURE_MICROCODE_FLOOR_SOURCE: "microcode_floor_source",
    FAILURE_ERRATA_GUIDE: "errata_guide",
    FAILURE_RDSEED_POLICY: "rdseed_policy",
    FAILURE_SOURCE_APPLICABILITY: "source_applicability",
}

CURRENT_EXPECTED_FAILURES = (
    FAILURE_BOARD_LINEAGE
    | FAILURE_BIOS_FLOOR
    | FAILURE_AGESA_FLOOR
    | FAILURE_MICROCODE_EVIDENCE
    | FAILURE_MICROCODE_FLOOR_SOURCE
    | FAILURE_ERRATA_GUIDE
)

BOARD_UNKNOWN = 0
BOARD_REV10_TO_12 = 1
BOARD_REV13 = 2
RDSEED_UNKNOWN = 0
RDSEED_MASKED = 1
RDSEED_USE_64_ONLY = 2
RDSEED_PATCHED_FIRMWARE = 3
COMBINED_SECURITY_AGESA_FLOOR = (1, 2, 0, 3, 9)

FEATURE_NAMES = (
    "long_mode",
    "nx",
    "sse2",
    "xsave",
    "osxsave",
    "fsgsbase",
    "smep",
    "smap",
    "invariant_tsc",
)

IMPLEMENTATION_INPUTS = (
    "specs/native-toolchain-lock.json",
    "native/Cargo.toml",
    "native/Cargo.lock",
    "native/cpupolicy/Cargo.toml",
    "native/cpupolicy/src/lib.rs",
    "native/cpupolicy/src/bin/pkerr1_probe.rs",
    "runtime/native_kernel_errata_policy.py",
    "tools/qualify_native_kernel_errata_policy.py",
    "tests/test_native_kernel_errata_policy.py",
    "tests/test_native_errata_admission.py",
    "docs/native-kernel-errata-policy.md",
)

NEGATIVE_CONTROL_IDS = (
    "NEG-N7-PKERR-IDENTITY",
    "NEG-N7-PKERR-FEATURE",
    "NEG-N7-PKERR-BOARD-UNKNOWN",
    "NEG-N7-PKERR-BIOS-BELOW-FLOOR",
    "NEG-N7-PKERR-BIOS-PRERELEASE",
    "NEG-N7-PKERR-AGESA-BELOW-SB7033",
    "NEG-N7-PKERR-AGESA-BELOW-SB7055",
    "NEG-N7-PKERR-MICROCODE-ZERO",
    "NEG-N7-PKERR-MICROCODE-MIXED",
    "NEG-N7-PKERR-MICROCODE-UNTRUSTED",
    "NEG-N7-PKERR-MICROCODE-FLOOR-MISSING",
    "NEG-N7-PKERR-ERRATA-GUIDE-MISSING",
    "NEG-N7-PKERR-ERRATA-GUIDE-WRONG-RANGE",
    "NEG-N7-PKERR-RDSEED-UNKNOWN",
    "NEG-N7-PKERR-RDSEED-PATCH-STALE",
    "NEG-N7-PKERR-CROSS-SEGMENT-SOURCE",
    "NEG-N7-PKERR-SOURCE-HASH",
    "NEG-N7-PKERR-58251-APPLICABILITY",
    "NEG-N7-PKERR-CURRENT-OVERCLAIM",
    "NEG-N7-PKERR-NUMERIC-FLOOR-INVENTED",
    "NEG-N7-PKERR-FIRMWARE-FLOOR-LOWERED",
    "NEG-N7-PKERR-AUTHORITY-OVERCLAIM",
    "NEG-N7-PKERR-ACTION-OVERCLAIM",
    "NEG-N7-PKERR-PRODUCTION-OVERCLAIM",
)

AGESA_PATTERN = re.compile(r"^([0-9]+)\.([0-9]+)\.([0-9]+)\.([0-9]+)([a-z]?)$")

OPEN_ITEMS = (
    "Physically confirm the exact B650M GAMING PLUS WIFI board revision before selecting the F or FA firmware lineage.",
    "Acquire and hash an applicable AMD Family 1Ah Models 40h-4Fh revision guide or retain a reviewed vendor-response gap.",
    "Obtain a direct AMD numeric client microcode floor or ratify a replacement rule that does not invent one.",
    "Hash the exact stable board firmware image selected after board-revision confirmation and complete supersession review.",
    "Perform reviewed native per-processor read-only CPUID and MSR_PATCH_LEVEL observation on a separately safe target path.",
    "Prove all processors are homogeneous and bind the result to the exact firmware, reset state, and target identity.",
    "Integrate PKERR1 into PooleKernel before feature activation and application-processor online transitions.",
    "Implement and test RDSEED masking or the reviewed 64-bit-only fallback until remediated firmware is qualified.",
    "Complete the broader transient-execution, branch, return-stack, store-bypass, SMT, and control-flow matrix.",
    "Obtain a cryptographically retained GIGABYTE support-page or exact firmware metadata snapshot.",
    "Reproduce the policy and target evidence on a second clean builder and target-firmware boot.",
    "Complete N7 and every signed-media, physical-hardware, release, and production gate.",
)


class KernelErrataPolicyError(ValueError):
    """Raised when PKERR1 data violates the frozen target policy."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise KernelErrataPolicyError(f"JSON object required: {path.name}")
    return value


def file_binding(path: Path, root: Path = ROOT) -> dict[str, Any]:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise KernelErrataPolicyError("binding path escapes the repository") from error
    data = resolved.read_bytes()
    return {"path": relative, "byte_count": len(data), "sha256": sha256_bytes(data)}


def expected_inputs(root: Path = ROOT) -> dict[str, Any]:
    return {
        "contract": file_binding(root / CONTRACT_RELATIVE, root),
        "contract_schema": file_binding(root / CONTRACT_SCHEMA_RELATIVE, root),
        "readiness_schema": file_binding(root / READINESS_SCHEMA_RELATIVE, root),
        "implementation_inputs": [file_binding(root / path, root) for path in IMPLEMENTATION_INPUTS],
    }


def parse_agesa(value: str) -> tuple[int, int, int, int, int]:
    match = AGESA_PATTERN.fullmatch(value)
    if match is None:
        raise KernelErrataPolicyError(f"invalid AGESA version: {value}")
    suffix = match.group(5)
    suffix_rank = 0 if not suffix else ord(suffix) - ord("a") + 1
    return tuple(int(match.group(index)) for index in range(1, 5)) + (suffix_rank,)


def _minimum_bios(board_lineage: int) -> int | None:
    if board_lineage == BOARD_REV10_TO_12:
        return 39
    if board_lineage == BOARD_REV13:
        return 7
    return None


def evaluate(evidence: dict[str, Any]) -> dict[str, Any]:
    failures = 0
    if evidence["cpuid_signature"] != TARGET_CPUID_SIGNATURE:
        failures |= FAILURE_IDENTITY
    if evidence["feature_mask"] & REQUIRED_FEATURES != REQUIRED_FEATURES:
        failures |= FAILURE_FEATURES
    minimum_bios = _minimum_bios(evidence["board_lineage"])
    if minimum_bios is None:
        failures |= FAILURE_BOARD_LINEAGE
    if (
        not evidence["bios_is_stable"]
        or minimum_bios is None
        or evidence["bios_number"] < minimum_bios
    ):
        failures |= FAILURE_BIOS_FLOOR
    if tuple(evidence["agesa"]) < COMBINED_SECURITY_AGESA_FLOOR:
        failures |= FAILURE_AGESA_FLOOR
    if (
        evidence["microcode_revision"] == 0
        or not evidence["all_processors_same_revision"]
        or not evidence["native_revision_evidence_trusted"]
    ):
        failures |= FAILURE_MICROCODE_EVIDENCE
    if not evidence["vendor_numeric_microcode_floor_available"]:
        failures |= FAILURE_MICROCODE_FLOOR_SOURCE
    if (
        not evidence["model44_revision_guide_available"]
        or not evidence["model44_revision_guide_applicable"]
    ):
        failures |= FAILURE_ERRATA_GUIDE
    if evidence["rdseed_capability_exposed"]:
        rdseed_policy = evidence["rdseed_policy"]
        rdseed_safe = rdseed_policy in (RDSEED_MASKED, RDSEED_USE_64_ONLY) or (
            rdseed_policy == RDSEED_PATCHED_FIRMWARE
            and tuple(evidence["agesa"]) >= COMBINED_SECURITY_AGESA_FLOOR
        )
        if not rdseed_safe:
            failures |= FAILURE_RDSEED_POLICY
    if not evidence["direct_product_sources_only"]:
        failures |= FAILURE_SOURCE_APPLICABILITY
    return {
        "failure_mask": failures,
        "failure_codes": [name for bit, name in FAILURE_NAMES.items() if failures & bit],
        "policy_satisfied": failures == 0,
        "authority_grants": 0,
        "actions_authorized": 0,
        "state_writes": 0,
    }


def synthetic_qualification_fixture() -> dict[str, Any]:
    return {
        "cpuid_signature": TARGET_CPUID_SIGNATURE,
        "feature_mask": REQUIRED_FEATURES,
        "board_lineage": BOARD_REV10_TO_12,
        "bios_number": 39,
        "bios_is_stable": True,
        "agesa": parse_agesa("1.2.8.0"),
        "microcode_revision": WINDOWS_REPORTED_MICROCODE_REVISION,
        "all_processors_same_revision": True,
        "native_revision_evidence_trusted": True,
        "vendor_numeric_microcode_floor_available": True,
        "model44_revision_guide_available": True,
        "model44_revision_guide_applicable": True,
        "rdseed_capability_exposed": True,
        "rdseed_policy": RDSEED_PATCHED_FIRMWARE,
        "direct_product_sources_only": True,
    }


def current_observation() -> dict[str, Any]:
    evidence = synthetic_qualification_fixture()
    evidence.update(
        {
            "board_lineage": BOARD_UNKNOWN,
            "bios_number": 32,
            "agesa": parse_agesa("1.2.0.2b"),
            "native_revision_evidence_trusted": False,
            "vendor_numeric_microcode_floor_available": False,
            "model44_revision_guide_available": False,
            "model44_revision_guide_applicable": False,
            "rdseed_policy": RDSEED_MASKED,
        }
    )
    return evidence


def probe_arguments(evidence: dict[str, Any]) -> list[str]:
    agesa = tuple(evidence["agesa"])
    return [
        f"0x{evidence['cpuid_signature']:08X}",
        f"0x{evidence['feature_mask']:016X}",
        str(evidence["board_lineage"]),
        str(evidence["bios_number"]),
        str(int(evidence["bios_is_stable"])),
        *(str(value) for value in agesa),
        f"0x{evidence['microcode_revision']:08X}",
        str(int(evidence["all_processors_same_revision"])),
        str(int(evidence["native_revision_evidence_trusted"])),
        str(int(evidence["vendor_numeric_microcode_floor_available"])),
        str(int(evidence["model44_revision_guide_available"])),
        str(int(evidence["model44_revision_guide_applicable"])),
        str(int(evidence["rdseed_capability_exposed"])),
        str(evidence["rdseed_policy"]),
        str(int(evidence["direct_product_sources_only"])),
    ]


def expected_claims() -> dict[str, bool]:
    return {
        "exact_target_identity_frozen": True,
        "direct_product_firmware_floors_frozen": True,
        "wrong_model_revision_guide_rejected": True,
        "mandatory_feature_rejection_implemented": True,
        "rust_python_policy_agreement": True,
        "current_target_policy_denied": True,
        "windows_registry_microcode_observed": True,
        "numeric_microcode_floor_complete": False,
        "model44_errata_matrix_complete": False,
        "native_privileged_revision_qualified": False,
        "firmware_update_performed": False,
        "microcode_update_performed": False,
        "target_cpu_qualified": False,
        "n7_exit_gate_satisfied": False,
        "production_ready": False,
    }


def expected_contract() -> dict[str, Any]:
    current = current_observation()
    current_decision = evaluate(current)
    return {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_kernel_errata_policy_contract",
        "contract_id": CONTRACT_ID,
        "selected_move_id": SELECTED_MOVE_ID,
        "status_date": "2026-07-21",
        "status": "candidate_fail_closed_target_errata_policy_non_promoting",
        "production_ready": False,
        "production_promotion_allowed": False,
        "phase_mapping": ["N7.2", "N15.1"],
        "source_requirement_ids": ["020.1", "020.2", "ADD-CPU-001", "ADD-N7-ERRATA-SOURCE-001"],
        "target": {
            "product": "AMD Ryzen 7 9800X3D",
            "former_codename": "Granite Ridge",
            "architecture": "Zen 5",
            "vendor_id": "AuthenticAMD",
            "cpuid_signature": "0x00B40F40",
            "decoded_family": 26,
            "decoded_model": 68,
            "decoded_stepping": 0,
            "product_id_boxed": "100-100001084WOF",
            "product_id_tray": "100-000001084",
            "hardware_profile": "TIER1-B650M-9800X3D-RTX5070-001",
        },
        "mandatory_features": {
            "mask": f"0x{REQUIRED_FEATURES:016X}",
            "names": list(FEATURE_NAMES),
            "basis": "sanitized user-mode target CPUID evidence; native per-processor confirmation remains required",
            "missing_feature_policy": "deny",
        },
        "firmware_policy": {
            "amd_sb_7033_minimum": "ComboAM5PI 1.2.0.3c",
            "amd_sb_7055_remediated_versions": ["ComboAM5PI 1.2.0.3i", "ComboAM5PI 1.2.8.0"],
            "combined_comparison_floor": "1.2.0.3i",
            "prerelease_bios_allowed": False,
            "unknown_board_revision_policy": "deny",
            "lineages": [
                {
                    "board_revisions": ["1.0", "1.1", "1.2"],
                    "bios_prefix": "F",
                    "minimum_stable_bios": "F39",
                    "minimum_stable_agesa": "1.2.8.0",
                    "vendor_checksum_noncryptographic": "B86C",
                },
                {
                    "board_revisions": ["1.3"],
                    "bios_prefix": "FA",
                    "minimum_stable_bios": "FA7",
                    "minimum_stable_agesa": "1.2.8.0",
                    "vendor_checksum_noncryptographic": "7349",
                },
            ],
            "current_observation": {
                "board_revision": "unknown",
                "bios": "F32",
                "agesa": "1.2.0.2b",
                "decision": "deny",
            },
        },
        "microcode_policy": {
            "windows_registry_revision_bytes_little_endian": "2340400B",
            "windows_reported_revision": "0x0B404023",
            "logical_processor_record_count": 16,
            "all_windows_records_same_after_normalization": True,
            "windows_observation_is_native_msr_evidence": False,
            "amd_published_client_numeric_floor": None,
            "numeric_floor_status": "not_published_in_applicable_direct_product_sources",
            "observed_revision_is_security_floor": False,
            "production_rule": "deny numeric-revision qualification until a direct AMD floor or reviewed replacement ADR is bound",
            "native_rule": "read every processor revision through a separately qualified read-only mechanism and reject mixed state",
        },
        "rdseed_policy": {
            "bulletin": "AMD-SB-7055",
            "cve": "CVE-2025-62626",
            "severity": "High",
            "affected_forms": [16, 32],
            "unaffected_form": 64,
            "pre_patch_allowed_modes": ["mask_cpuid_rdseed", "use_64_bit_only_with_zero_retry"],
            "unknown_mode_policy": "deny",
            "post_patch_policy": "require an applicable remediated AGESA version before ordinary exposure",
        },
        "errata_policy": {
            "required_target_range": "AMD Family 1Ah Models 40h-4Fh",
            "public_target_revision_guide_status": "not_located",
            "document_58251_range": "AMD Family 1Ah Models 00h-0Fh",
            "document_58251_target_applicable": False,
            "cross_model_or_cross_segment_inference_allowed": False,
            "production_rule": "deny target errata completion until an applicable AMD guide or reviewed vendor response is bound",
        },
        "source_register": [
            {
                "id": "AMD-CPUID-25481",
                "authority": "AMD",
                "source_class": "architecture_identity",
                "url": "https://www.amd.com/content/dam/amd/en/documents/archived-tech-docs/design-guides/25481.pdf",
                "captured_byte_count": 184465,
                "captured_sha256": "05A19B3619628EB050EB05383913BE9E55859755CC192E67F840591F3EE449C0",
                "target_applicable": True,
            },
            {
                "id": "AMD-PRODUCT-9800X3D",
                "authority": "AMD",
                "source_class": "direct_product_identity",
                "url": "https://www.amd.com/en/products/processors/desktops/ryzen/9000-series/amd-ryzen-7-9800x3d.html",
                "captured_byte_count": 200021,
                "captured_sha256": "3EEED6552FE7F56B4DB31B16EC33ADB856765A00866E4824B03147BB707D0077",
                "target_applicable": True,
            },
            {
                "id": "AMD-SB-7033",
                "authority": "AMD",
                "source_class": "direct_product_security_bulletin",
                "url": "https://www.amd.com/en/resources/product-security/bulletin/amd-sb-7033.html",
                "captured_byte_count": 174264,
                "captured_sha256": "540FF884CB2BC69FF495AD1272A85AA44105737153FD1CBD300FA206D6C1DD61",
                "target_applicable": True,
            },
            {
                "id": "AMD-SB-7055",
                "authority": "AMD",
                "source_class": "direct_product_security_bulletin",
                "url": "https://www.amd.com/en/resources/product-security/bulletin/amd-sb-7055.html",
                "captured_byte_count": 160179,
                "captured_sha256": "2BE2FA4E39E2BDD2362AD49323EF1DCAA866DE8A298DC4BB851ACD44442CB7C7",
                "target_applicable": True,
            },
            {
                "id": "AMD-REV-58251",
                "authority": "AMD",
                "source_class": "nonapplicable_revision_guide_control",
                "url": "https://www.amd.com/content/dam/amd/en/documents/processor-tech-docs/revision-guides/58251.pdf",
                "captured_byte_count": 1002117,
                "captured_sha256": "541BE14A5B2A6A4E9A0B1383492D09A28C061EE57EB969D5CFD5C8ED75A5C231",
                "target_applicable": False,
            },
            {
                "id": "GIGABYTE-B650M-GAMING-PLUS-WIFI-BIOS",
                "authority": "GIGABYTE",
                "source_class": "direct_board_firmware_metadata",
                "url": "https://www.gigabyte.com/eu/Motherboard/B650M-GAMING-PLUS-WIFI-rev-10-11-12/support",
                "captured_byte_count": None,
                "captured_sha256": None,
                "capture_status": "primary_page_verified_raw_download_denied",
                "target_applicable": True,
            },
            {
                "id": "AMD-F1A-M40-4F-REVISION-GUIDE-GAP",
                "authority": "AMD",
                "source_class": "required_missing_target_errata_source",
                "url": None,
                "captured_byte_count": None,
                "captured_sha256": None,
                "capture_status": "not_located_in_public_amd_catalog",
                "target_applicable": False,
            },
        ],
        "current_observation": {
            "cpuid_signature": f"0x{current['cpuid_signature']:08X}",
            "feature_mask": f"0x{current['feature_mask']:016X}",
            "board_lineage": "unknown",
            "bios": "F32",
            "agesa": "1.2.0.2b",
            "windows_reported_microcode_revision": "0x0B404023",
            "rdseed_mode": "masked_until_qualified",
            "expected_failure_mask": f"0x{current_decision['failure_mask']:08X}",
            "expected_failure_codes": current_decision["failure_codes"],
            "decision": "deny",
        },
        "authority_gate": {
            "signature_verifications": 0,
            "authority_grants": 0,
            "actions_authorized": 0,
            "state_writes": 0,
            "privileged_reads": 0,
            "cpu_or_firmware_writes": 0,
        },
        "claims": expected_claims(),
        "required_negative_controls": list(NEGATIVE_CONTROL_IDS),
        "non_claims": [
            "PKERR1 freezes a policy and rejects the current evidence; it does not qualify the physical target.",
            "The Windows registry revision is an unprivileged OS report, not direct per-processor MSR evidence and not an AMD-published security floor.",
            "AMD document 58251 covers Family 1Ah Models 00h-0Fh and is prohibited as target errata evidence for Model 44h.",
            "The public-source audit did not locate an applicable Family 1Ah Models 40h-4Fh revision guide or a client numeric microcode floor.",
            "F32 and AGESA 1.2.0.2b are recorded observations only; no firmware download, flash, setting change, or reboot was performed.",
            "Synthetic all-true vectors demonstrate evaluator reachability only and create no trust, authority, or hardware evidence.",
            "No microcode payload is acquired, parsed, staged, authenticated, applied, or redistributed.",
            "No key, signature, capability, privileged probe, driver, firmware mutation, physical-media write, release, or production promotion is claimed.",
        ],
    }


def _typed_equal(actual: Any, expected: Any, label: str) -> None:
    if json.dumps(actual, sort_keys=True, allow_nan=False) != json.dumps(expected, sort_keys=True, allow_nan=False):
        raise KernelErrataPolicyError(f"PKERR1 {label} differs from the recorded contract")


def contract_errors(value: Any, root: Path = ROOT) -> list[str]:
    try:
        issues = validate_json(value, read_json(root / CONTRACT_SCHEMA_RELATIVE))
        if issues:
            return [f"schema {issue.path}: {issue.message}" for issue in issues]
        _typed_equal(value, expected_contract(), "contract")
    except (KeyError, TypeError, ValueError, OSError, RecursionError) as error:
        return [f"PKERR1 contract invalid: {error}"]
    return []


def expected_controls() -> list[dict[str, Any]]:
    # Independent expected outcomes for the qualifier's sixteen evaluator mutations.
    masks = (1, 2, 12, 8, 8, 16, 272, 32, 32, 32, 64, 128, 128, 256, 272, 512)
    controls = [
        {"id": name, "status": "pass", "expected": "deny", "failure_mask": f"0x{mask:08X}",
         "failure_codes": [code for bit, code in FAILURE_NAMES.items() if mask & bit]}
        for name, mask in zip(NEGATIVE_CONTROL_IDS[:16], masks, strict=True)
    ]
    return controls + [{"id": name, "status": "pass", "expected": "contract_rejected"}
                       for name in NEGATIVE_CONTROL_IDS[16:]]


def expected_vectors() -> dict[str, Any]:
    """Reconstruct the frozen selector outcomes independently of the live Rust probe."""
    masks = (1, 2, 12, 8, 8, 272, 32, 32, 32, 64, 128, 128, 256, 512, 0)
    state, union, satisfied = 0x504B_4552_5231_0121, 0, 0
    digest = hashlib.sha256()
    for index in range(128):
        state ^= (state << 13) & ((1 << 64) - 1)
        state ^= state >> 7
        state = (state ^ (state << 17)) & ((1 << 64) - 1)
        failure = masks[state % len(masks)]
        union |= failure
        satisfied += int(failure == 0)
        digest.update(index.to_bytes(4, "little") + failure.to_bytes(4, "little"))
    if union != sum(FAILURE_NAMES):
        raise KernelErrataPolicyError("PKERR1 frozen vectors no longer cover all failure bits")
    return {"status": "pass", "case_count": 128, "mismatch_count": 0,
            "satisfied_case_count": satisfied, "failure_bit_coverage": union.bit_count(),
            "outcome_sha256": digest.hexdigest().upper()}


def _recorded_fields(root: Path) -> dict[str, Any]:
    contract = read_json(root / CONTRACT_RELATIVE)
    errors = contract_errors(contract, root)
    if errors:
        raise KernelErrataPolicyError("; ".join(errors))
    lock = read_json(root / "specs/native-toolchain-lock.json")
    current = evaluate(current_observation())
    synthetic = evaluate(synthetic_qualification_fixture())
    forbidden = ("unsafe", "asm!", "wrmsr", "xsetbv", "write_volatile", "std::")
    source = (root / "native/cpupolicy/src/lib.rs").read_text(encoding="utf-8").lower()
    if any(token in source for token in forbidden):
        raise KernelErrataPolicyError("PKERR1 policy source violates the recorded no-I/O audit")
    revision = f"0x{WINDOWS_REPORTED_MICROCODE_REVISION:08X}"
    identifier = "AMD64 Family 26 Model 68 Stepping 0"
    return {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_kernel_errata_policy_readiness",
        "status": "pass_policy_denies_current_target", "contract_id": CONTRACT_ID,
        "selected_move_id": SELECTED_MOVE_ID, "production_ready": False,
        "production_promotion_allowed": False, "n7_exit_gate_satisfied": False,
        "phase_status": {"N7": "partial", "N7.2": "partial", "N15.1": "partial"},
        "inputs": expected_inputs(root),
        "build_qualification": {
            "status": "pass", "rustc": "rustc " + lock["channel_manifest"]["rust_version"],
            "host_tests_passed": 6, "host_tests_total": 6, "rustfmt_packages": 1,
            "clippy_targets": 1, "no_std_targets": ["x86_64-unknown-none", "x86_64-unknown-uefi"],
        },
        "source_audit": {"status": "pass_pure_policy_no_cpu_or_firmware_io",
            "forbidden_tokens": list(forbidden), "forbidden_hits": [],
            "privileged_reads": 0, "cpu_or_firmware_writes": 0},
        "windows_registry_observation": {
            "status": "pass_read_only_unprivileged_os_report", "read_only": True,
            "record_count": 16, "unique_revision_count": 1, "normalized_revision": revision,
            "identifier": identifier, "raw_registers_read": False, "msr_reads": 0,
            "privileged_reads": 0, "driver_loaded": False, "writes": 0,
            "records": [{"processor": processor, "identifier": identifier,
                "revision_bytes_little_endian": WINDOWS_REPORTED_MICROCODE_REVISION.to_bytes(4, "little").hex().upper(),
                "normalized_revision": revision} for processor in range(16)],
        },
        "current_policy_decision": {**current, "failure_mask": f"0x{current['failure_mask']:08X}",
                                    "decision": "deny"},
        "synthetic_policy_decision": {**synthetic, "failure_mask": f"0x{synthetic['failure_mask']:08X}",
            "decision": "policy_satisfied_without_authority", "is_hardware_or_trust_evidence": False},
        "cross_language_vectors": expected_vectors(), "negative_controls": expected_controls(),
        "claims": expected_claims(),
        "summary": {
            "rust_host_tests_passed": 6, "rust_host_tests_total": 6,
            "no_std_target_builds_passed": 2, "no_std_target_builds_total": 2,
            "cross_language_vector_count": 128, "cross_language_mismatch_count": 0,
            "negative_controls_passed": len(NEGATIVE_CONTROL_IDS), "negative_controls_total": len(NEGATIVE_CONTROL_IDS),
            "current_failure_count": len(current["failure_codes"]),
            "source_register_count": len(contract["source_register"]),
            "applicable_source_count": sum(s["target_applicable"] for s in contract["source_register"]),
            "privileged_read_count": 0, "cpu_or_firmware_write_count": 0,
            "authority_grant_count": 0, "actions_authorized_count": 0, "production_claim_count": 0,
        },
        "open_items": list(OPEN_ITEMS), "non_claims": contract["non_claims"],
    }


def readiness_errors(value: Any, root: Path = ROOT) -> list[str]:
    """Admit exact recorded consistency, not authentication or fresh execution."""
    try:
        issues = validate_json(value, read_json(root / READINESS_SCHEMA_RELATIVE))
        if issues:
            return [f"schema {issue.path}: {issue.message}" for issue in issues]
        status_date = value["status_date"]
        if len(status_date) != 10 or date.fromisoformat(status_date).isoformat() != status_date:
            raise KernelErrataPolicyError("PKERR1 date is not canonical")
        expected = _recorded_fields(root)
        if set(value) != set(expected) | {"status_date"}:
            raise KernelErrataPolicyError("PKERR1 readiness fields changed")
        for field, required in expected.items():
            _typed_equal(value[field], required, field)
    except (KeyError, TypeError, ValueError, OSError, RecursionError) as error:
        return [f"PKERR1 recorded evidence invalid: {error}"]
    return []
