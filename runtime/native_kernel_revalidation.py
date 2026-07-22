"""Independent host oracle for PooleKernel retained-byte revalidation (PKREVAL1)."""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from runtime import (
    native_boot_artifact,
    native_boot_handoff as pbp1,
    native_boot_trust,
    native_elf_loader,
    native_inner_live,
    native_kernel_load,
    native_system_manifest,
)
from runtime.schema_validation import validate_json


CONTRACT_ID = "PKREVAL1"
SELECTED_MOVE_ID = "N5-INNER-KERNEL-REVALIDATE-001"
ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE = "specs/native-kernel-revalidation-contract.json"
SCHEMA_RELATIVE = "specs/native-kernel-revalidation-readiness.schema.json"
READINESS_RELATIVE = "runs/native-kernel-revalidation-readiness.json"
IMPLEMENTATION_INPUTS = (
    "native/handoff/src/lib.rs",
    "native/livehandoff/src/lib.rs",
    "native/boot/src/kload.rs",
    "native/boot/src/livehandoff.rs",
    "native/boot/src/kmap.rs",
    "native/kernel/Cargo.toml",
    "native/kernel/src/lib.rs",
    "native/kernel/src/main.rs",
    "native/kernel/src/revalidation.rs",
    "native/kernel/src/bin/pkreval1_probe.rs",
    "runtime/native_kernel_revalidation.py",
    "tools/qualify_native_kernel_revalidation.py",
    "tests/test_native_kernel_revalidation.py",
    "docs/native-kernel-revalidation.md",
    "runs/native_initial_system_readiness.json",
    "runs/native_recovery_readiness.json",
    "runs/native_symbol_readiness.json",
    "runs/native_microcode_readiness.json",
    "runs/native_firmware_readiness.json",
    "runs/native_policy_readiness.json",
    "runs/native_boot_trust_readiness.json",
    "runs/native_system_manifest_readiness.json",
)
RETAINED_ROLES = (
    pbp1.ARTIFACT_INITIAL_SYSTEM,
    pbp1.ARTIFACT_RECOVERY,
    pbp1.ARTIFACT_SYMBOLS,
    pbp1.ARTIFACT_MICROCODE,
    pbp1.ARTIFACT_FIRMWARE_MANIFEST,
    pbp1.ARTIFACT_POLICY_BUNDLE,
    pbp1.ARTIFACT_SYSTEM_MANIFEST,
    pbp1.ARTIFACT_TRUST_POLICY,
    pbp1.ARTIFACT_TRUST_STATE,
)
PROFILE_ROLES = (pbp1.ARTIFACT_KERNEL, *RETAINED_ROLES)
RETAINED_FILE_COUNT = len(RETAINED_ROLES)
MANIFEST_FILE_INDEX = 6
TRUST_POLICY_FILE_INDEX = 7
TRUST_STATE_FILE_INDEX = 8
ARTIFACT_PATHS = tuple(item[4] for item in native_kernel_load.ARTIFACT_DEFINITIONS)


class KernelRevalidationError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Descriptor:
    role: int
    flags: int
    physical_base: int
    byte_count: int
    sha256: str


@dataclass(frozen=True)
class CanonicalBundle:
    handoff: bytes
    files: tuple[bytes, ...]
    physical_bases: tuple[int, ...]
    kernel: bytes


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise KernelRevalidationError("pkreval_json_object")
    return value


def file_binding(path: Path, root: Path = ROOT) -> dict[str, object]:
    resolved = path.resolve()
    relative = resolved.relative_to(root.resolve()).as_posix()
    data = resolved.read_bytes()
    return {"path": relative, "sha256": sha256_bytes(data), "byte_count": len(data)}


def expected_claims() -> dict[str, bool]:
    return {
        "allocation_free_no_std_kernel_verifier": True,
        "exact_final_page_bytes_reparsed": True,
        "psm1_reparsed_in_kernel": True,
        "six_pbart1_files_reparsed_in_kernel": True,
        "six_inner_contracts_reparsed_in_kernel": True,
        "pbtp1_and_pbts1_reparsed_in_kernel": True,
        "loader_summary_substitution_rejected": True,
        "post_loader_byte_mutation_rejected": True,
        "development_authority_denied": True,
        "live_kernel_entry_executed": False,
        "authenticated_persistent_state_selected": False,
        "production_ready": False,
    }


def contract_errors(contract: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if contract.get("contract_id") != CONTRACT_ID or contract.get("selected_move_id") != SELECTED_MOVE_ID:
        errors.append("PKREVAL1 contract identity changed")
    if contract.get("production_ready") is not False or contract.get("production_promotion_allowed") is not False:
        errors.append("PKREVAL1 contract overclaims production")
    profile = contract.get("handoff_profile", {})
    roles = profile.get("roles", []) if isinstance(profile, dict) else []
    if (
        not isinstance(profile, dict)
        or profile.get("profile_role_count") != len(PROFILE_ROLES)
        or profile.get("retained_file_count") != RETAINED_FILE_COUNT
        or [item.get("code") for item in roles if isinstance(item, dict)] != list(PROFILE_ROLES)
    ):
        errors.append("PKREVAL1 retained-role profile changed")
    qualification = contract.get("qualification", {})
    if not isinstance(qualification, dict) or (
        qualification.get("rust_host_test_count"),
        qualification.get("python_unit_test_count"),
        qualification.get("negative_control_count"),
        qualification.get("differential_mutation_cases"),
        qualification.get("retained_role_coverage"),
    ) != (60, 8, 36, 32_768, RETAINED_FILE_COUNT):
        errors.append("PKREVAL1 qualification profile changed")
    authority = contract.get("authority_gate", {})
    if not isinstance(authority, dict) or (
        authority.get("development_result"),
        authority.get("authority_grants"),
        authority.get("actions_authorized"),
        authority.get("state_writes"),
    ) != ("deny_pbtrust_policy_unsigned", 0, 0, 0):
        errors.append("PKREVAL1 zero-authority gate changed")
    if contract.get("claims") != expected_claims():
        errors.append("PKREVAL1 claim boundary changed")
    return errors


def readiness_errors(readiness: dict[str, object], root: Path = ROOT) -> list[str]:
    schema = read_json(root / SCHEMA_RELATIVE)
    errors = [
        f"schema {item.path}: {item.message}"
        for item in validate_json(readiness, schema)
    ]
    contract = read_json(root / CONTRACT_RELATIVE)
    errors.extend(contract_errors(contract))
    expected_inputs = {
        "contract": file_binding(root / CONTRACT_RELATIVE, root),
        "toolchain_lock": file_binding(root / "specs/native-toolchain-lock.json", root),
        "implementation_inputs": [file_binding(root / path, root) for path in IMPLEMENTATION_INPUTS],
    }
    if readiness.get("inputs") != expected_inputs:
        errors.append("PKREVAL1 readiness input bindings are stale")
    build = readiness.get("build", {})
    if not isinstance(build, dict) or build.get("host_test_count") != 70 or set(
        build.get("targets", {}) if isinstance(build.get("targets"), dict) else {}
    ) != {"x86_64-unknown-none", "x86_64-unknown-uefi"}:
        errors.append("PKREVAL1 build evidence changed")
    golden = readiness.get("golden", {})
    if not isinstance(golden, dict) or (
        golden.get("retained_file_count"),
        golden.get("artifact_count"),
        golden.get("parser_count"),
        golden.get("denial"),
        golden.get("authority_grants"),
        golden.get("actions_authorized"),
        golden.get("state_writes"),
        golden.get("rust_python_match"),
    ) != (9, 6, 9, "pbtrust_policy_unsigned", 0, 0, 0, True):
        errors.append("PKREVAL1 golden evidence changed")
    controls = readiness.get("negative_controls", [])
    if (
        not isinstance(controls, list)
        or len(controls) != 36
        or len({item.get("id") for item in controls if isinstance(item, dict)}) != 36
        or any(not isinstance(item, dict) or item.get("status") != "pass" for item in controls)
    ):
        errors.append("PKREVAL1 hostile-control evidence changed")
    differential = readiness.get("differential", {})
    if not isinstance(differential, dict) or (
        differential.get("case_count"),
        differential.get("reject_count"),
        differential.get("expected_file_digest_count"),
        differential.get("role_coverage"),
    ) != (32_768, 32_768, 32_768, RETAINED_FILE_COUNT):
        errors.append("PKREVAL1 differential evidence changed")
    if readiness.get("claims") != expected_claims():
        errors.append("PKREVAL1 readiness claim boundary changed")
    if readiness.get("non_claims") != contract.get("non_claims"):
        errors.append("PKREVAL1 non-claim boundary changed")
    if readiness.get("production_ready") is not False or readiness.get("production_promotion_allowed") is not False:
        errors.append("PKREVAL1 readiness overclaims production")
    return errors


def _fail(code: str) -> None:
    raise KernelRevalidationError(code)


def _file_size_allowed(role: int, byte_count: int) -> bool:
    if role in RETAINED_ROLES[:6]:
        return native_boot_artifact.HEADER_BYTES <= byte_count <= native_boot_artifact.MAX_FILE_BYTES
    if role == pbp1.ARTIFACT_SYSTEM_MANIFEST:
        return 1 <= byte_count <= native_system_manifest.MAX_MANIFEST_BYTES
    if role == pbp1.ARTIFACT_TRUST_POLICY:
        return byte_count == native_boot_trust.POLICY_BYTES
    if role == pbp1.ARTIFACT_TRUST_STATE:
        return byte_count == native_boot_trust.STATE_BYTES
    return False


def _core(payload: bytes) -> tuple[int, ...]:
    if len(payload) != pbp1.CORE_BYTES:
        _fail("pkreval_handoff")
    return struct.unpack("<13Q6I", payload)


def _profile(data: bytes) -> tuple[pbp1.Handoff, tuple[int, ...], tuple[Descriptor, ...]]:
    try:
        handoff = pbp1.decode(data)
    except pbp1.BootHandoffError:
        _fail("pkreval_handoff")
    core_record = handoff.record(pbp1.RECORD_CORE)
    artifact_record = handoff.record(pbp1.RECORD_LOADED_ARTIFACTS)
    if core_record is None or artifact_record is None:
        _fail("pkreval_artifact_profile")
    core = _core(core_record.payload)
    if not core[0] & pbp1.BOOT_SERVICES_EXITED:
        _fail("pkreval_exit_state")
    if (
        artifact_record.element_size != pbp1.ARTIFACT_ENTRY_BYTES
        or artifact_record.element_count != len(PROFILE_ROLES)
        or len(artifact_record.payload) != len(PROFILE_ROLES) * pbp1.ARTIFACT_ENTRY_BYTES
    ):
        _fail("pkreval_artifact_profile")
    descriptors: list[Descriptor] = []
    for index, expected_role in enumerate(PROFILE_ROLES):
        offset = index * pbp1.ARTIFACT_ENTRY_BYTES
        role, flags, physical_base, byte_count, virtual_base, virtual_size, entry = struct.unpack_from(
            "<IIQQQQQ", artifact_record.payload, offset
        )
        digest = artifact_record.payload[offset + 48 : offset + 80].hex().upper()
        if role != expected_role:
            _fail("pkreval_artifact_profile")
        permitted = (
            pbp1.ARTIFACT_HASH_VERIFIED
            | pbp1.ARTIFACT_SIGNATURE_VERIFIED
            | pbp1.ARTIFACT_MEASURED
            | pbp1.ARTIFACT_EXECUTABLE
        )
        if (
            not flags & pbp1.ARTIFACT_HASH_VERIFIED
            or flags & pbp1.ARTIFACT_WRITABLE
            or flags & ~permitted
            or bool(flags & pbp1.ARTIFACT_EXECUTABLE) != (index == 0)
        ):
            _fail("pkreval_artifact_flags")
        if (
            physical_base <= 0
            or physical_base % pbp1.PAGE_BYTES
            or byte_count <= 0
            or physical_base + byte_count > (1 << 64) - 1
        ):
            _fail("pkreval_artifact_range")
        if index == 0:
            if (physical_base, byte_count, virtual_base, virtual_size, entry) != core[1:6]:
                _fail("pkreval_artifact_profile")
        elif virtual_base or virtual_size or entry or not _file_size_allowed(role, byte_count):
            _fail("pkreval_artifact_profile")
        descriptors.append(Descriptor(role, flags, physical_base, byte_count, digest))
    for index, first in enumerate(descriptors):
        for second in descriptors[index + 1 :]:
            if (
                first.physical_base < second.physical_base + second.byte_count
                and second.physical_base < first.physical_base + first.byte_count
            ):
                _fail("pkreval_artifact_overlap")
    return handoff, core, tuple(descriptors)


def revalidate_development(
    handoff_data: bytes,
    files: Sequence[bytes],
    physical_bases: Sequence[int] | None = None,
) -> dict[str, object]:
    _, core, descriptors = _profile(handoff_data)
    if len(files) != RETAINED_FILE_COUNT:
        _fail("pkreval_file_order")
    bases = (
        tuple(item.physical_base for item in descriptors[1:])
        if physical_bases is None
        else tuple(physical_bases)
    )
    if len(bases) != RETAINED_FILE_COUNT:
        _fail("pkreval_file_order")
    for index, (data, base) in enumerate(zip(files, bases, strict=True)):
        descriptor = descriptors[index + 1]
        if descriptor.role != RETAINED_ROLES[index]:
            _fail("pkreval_file_order")
        if base != descriptor.physical_base:
            _fail("pkreval_file_locator")
        if len(data) != descriptor.byte_count:
            _fail("pkreval_file_size")
        if hashlib.sha256(data).hexdigest().upper() != descriptor.sha256:
            _fail("pkreval_file_digest")

    manifest_data = files[MANIFEST_FILE_INDEX]
    try:
        manifest = native_system_manifest.parse(manifest_data)
        profile = native_kernel_load._profile_artifacts(manifest)
    except (native_system_manifest.ManifestError, native_kernel_load.KernelLoadError) as error:
        _fail(getattr(error, "code", "manifest_binding"))
    kernel_descriptor = descriptors[0]
    if (
        manifest.slot != core[15]
        or native_system_manifest.sha256_bytes(manifest_data)
        != descriptors[MANIFEST_FILE_INDEX + 1].sha256
        or profile[0].sha256 != kernel_descriptor.sha256
        or profile[0].image_bytes != core[4]
    ):
        _fail("pkreval_manifest_binding")
    for index, artifact in enumerate(profile[1:]):
        descriptor = descriptors[index + 1]
        if (
            RETAINED_ROLES[index] != descriptor.role
            or artifact.file_bytes != descriptor.byte_count
            or artifact.sha256 != descriptor.sha256
        ):
            _fail("pkreval_manifest_binding")

    try:
        inner = native_inner_live.validate_development_set(files[:6])
    except native_inner_live.InnerLiveError as error:
        _fail(str(error))
    if any(
        inner[field]
        for field in ("authority_grants", "actions_authorized", "state_writes", "hardware_observations")
    ):
        _fail("pkreval_unexpected_authority")
    observed = native_boot_trust.ObservedBoot(
        manifest_sha256=native_system_manifest.sha256_bytes(manifest_data),
        kernel_sha256=profile[0].sha256,
        retained_set_sha256=str(inner["retained_set_sha256"]),
        revocation_set_sha256=native_boot_trust.sha256_bytes(b""),
        manifest_version=manifest.manifest_version,
        minimum_secure_version=manifest.minimum_secure_version,
    )
    try:
        trust = native_boot_trust.validate_development(
            files[TRUST_POLICY_FILE_INDEX], files[TRUST_STATE_FILE_INDEX], observed
        )
    except native_boot_trust.BootTrustError as error:
        _fail(error.code)
    if (
        trust["denial"] != "pbtrust_policy_unsigned"
        or trust["authority_grants"]
        or trust["state_writes"]
    ):
        _fail("pkreval_unexpected_authority")
    return {
        "contract_id": CONTRACT_ID,
        "retained_file_count": RETAINED_FILE_COUNT,
        "artifact_count": inner["artifact_count"],
        "parser_count": inner["parser_count"] + 3,
        "manifest_bytes": len(manifest_data),
        "retained_file_bytes": sum(len(data) for data in files),
        "retained_set_sha256": inner["retained_set_sha256"],
        "policy_sha256": trust["policy_sha256"],
        "state_sha256": trust["state_sha256"],
        "denial": trust["denial"],
        "authority_grants": 0,
        "actions_authorized": 0,
        "state_writes": 0,
    }


def canonical_bundle() -> CanonicalBundle:
    kernel = native_elf_loader.build_fixture("minimal_relative_v1")
    plan = native_elf_loader.inspect(
        kernel, native_kernel_load.PHYSICAL_ORACLE_BASE, native_elf_loader.MIN_VIRTUAL_BASE
    )
    artifact_files = native_kernel_load.canonical_artifact_files()
    manifest = native_kernel_load.canonical_manifest_bytes(kernel, artifact_files)
    trust_files, _ = native_kernel_load.canonical_trust_files(manifest, kernel, artifact_files)
    files = (
        *(artifact_files[path] for path in ARTIFACT_PATHS),
        manifest,
        trust_files[native_kernel_load.TRUST_POLICY_PATH],
        trust_files[native_kernel_load.TRUST_STATE_PATH],
    )
    physical_bases: list[int] = []
    cursor = 0x0030_0000
    for data in files:
        physical_bases.append(cursor)
        cursor += ((len(data) + pbp1.PAGE_BYTES - 1) // pbp1.PAGE_BYTES) * pbp1.PAGE_BYTES
    entries = [
        struct.pack(
            "<IIQQQQQ32s",
            pbp1.ARTIFACT_KERNEL,
            pbp1.ARTIFACT_HASH_VERIFIED | pbp1.ARTIFACT_EXECUTABLE,
            plan.physical_base,
            plan.image_size,
            plan.virtual_base,
            plan.image_size,
            plan.entry_virtual,
            hashlib.sha256(kernel).digest(),
        )
    ]
    for role, base, data in zip(RETAINED_ROLES, physical_bases, files, strict=True):
        entries.append(
            struct.pack(
                "<IIQQQQQ32s",
                role,
                pbp1.ARTIFACT_HASH_VERIFIED,
                base,
                len(data),
                0,
                0,
                0,
                hashlib.sha256(data).digest(),
            )
        )
    artifacts = b"".join(entries)
    memory = struct.pack(
        "<QQQIIQ",
        0x0020_0000,
        1024,
        0,
        pbp1.MEMORY_LOADER_RESERVED,
        2,
        0,
    )
    payload_lengths = (pbp1.CORE_BYTES, len(memory), len(artifacts))
    total = pbp1.encoded_size(payload_lengths)
    core = struct.pack(
        "<13Q6I",
        pbp1.BOOT_SERVICES_EXITED | pbp1.DEVELOPMENT_MODE,
        plan.physical_base,
        plan.image_size,
        plan.virtual_base,
        plan.image_size,
        plan.entry_virtual,
        0xFFFF_FFFF_8003_9000,
        0x0050_0000,
        0x0060_0000,
        0xFFFF_FFFF_8004_0000,
        total,
        0,
        0,
        0,
        3,
        1,
        1,
        0x0002_0064,
        0,
    )
    handoff = pbp1.encode(
        (
            {
                "record_type": pbp1.RECORD_CORE,
                "flags": pbp1.RECORD_REQUIRED,
                "element_size": pbp1.CORE_BYTES,
                "element_count": 1,
                "payload": core,
            },
            {
                "record_type": pbp1.RECORD_MEMORY_MAP,
                "flags": pbp1.RECORD_REQUIRED | pbp1.RECORD_ARRAY,
                "element_size": pbp1.MEMORY_ENTRY_BYTES,
                "element_count": 1,
                "payload": memory,
            },
            {
                "record_type": pbp1.RECORD_LOADED_ARTIFACTS,
                "flags": pbp1.RECORD_REQUIRED | pbp1.RECORD_ARRAY,
                "element_size": pbp1.ARTIFACT_ENTRY_BYTES,
                "element_count": len(entries),
                "payload": artifacts,
            },
        )
    )
    bundle = CanonicalBundle(handoff, tuple(files), tuple(physical_bases), kernel)
    revalidate_development(bundle.handoff, bundle.files, bundle.physical_bases)
    return bundle


def _xorshift64(value: int) -> int:
    mask = (1 << 64) - 1
    value ^= (value << 13) & mask
    value ^= value >> 7
    value ^= (value << 17) & mask
    return value & mask


def _fnv_extend(value: int, data: bytes) -> int:
    for byte in data:
        value ^= byte
        value = (value * 0x00000100000001B3) & ((1 << 64) - 1)
    return value


def mutation_campaign(bundle: CanonicalBundle, case_count: int) -> dict[str, object]:
    if not 1 <= case_count <= 65_536:
        raise ValueError("case_count must be between 1 and 65,536")
    storage = [bytearray(data) for data in bundle.files]
    state = 0x504B_5245_5641_4C31
    outcome = 0xCBF29CE484222325
    rejects = 0
    expected = 0
    coverage = 0
    for case_index in range(case_count):
        state = _xorshift64(state)
        target = state % RETAINED_FILE_COUNT
        state = _xorshift64(state)
        offset = state % len(storage[target])
        state = _xorshift64(state)
        xor_mask = ((state >> 56) & 0xFF) | 1
        storage[target][offset] ^= xor_mask
        try:
            revalidate_development(
                bundle.handoff,
                tuple(bytes(value) for value in storage),
                bundle.physical_bases,
            )
        except KernelRevalidationError as error:
            code = error.code
            rejects += 1
            if code == "pkreval_file_digest":
                expected += 1
        else:
            code = "pass"
        storage[target][offset] ^= xor_mask
        coverage |= 1 << target
        outcome = _fnv_extend(outcome, case_index.to_bytes(8, "little"))
        outcome = _fnv_extend(outcome, target.to_bytes(8, "little"))
        outcome = _fnv_extend(outcome, offset.to_bytes(8, "little"))
        outcome = _fnv_extend(outcome, bytes((xor_mask,)))
        outcome = _fnv_extend(outcome, code.encode("ascii"))
    return {
        "case_count": case_count,
        "reject_count": rejects,
        "expected_file_digest_count": expected,
        "role_coverage": coverage.bit_count(),
        "outcome_fnv1a64": f"{outcome:016X}",
    }


def rewrite_profile_descriptor(
    handoff_data: bytes,
    profile_index: int,
    *,
    role: int | None = None,
    flags: int | None = None,
    physical_base: int | None = None,
    byte_count: int | None = None,
    sha256: bytes | None = None,
) -> bytes:
    if not 0 <= profile_index < len(PROFILE_ROLES):
        raise ValueError("profile_index outside PKREVAL1 profile")
    output = bytearray(handoff_data)
    record_count = struct.unpack_from("<H", output, 20)[0]
    descriptor_offset = None
    payload_offset = None
    payload_length = None
    for index in range(record_count):
        candidate = pbp1.HEADER_BYTES + index * pbp1.DESCRIPTOR_BYTES
        if struct.unpack_from("<H", output, candidate)[0] == pbp1.RECORD_LOADED_ARTIFACTS:
            descriptor_offset = candidate
            payload_offset, payload_length = struct.unpack_from("<II", output, candidate + 8)
            break
    if descriptor_offset is None or payload_offset is None or payload_length is None:
        raise ValueError("PBP1 loaded-artifact record missing")
    entry = payload_offset + profile_index * pbp1.ARTIFACT_ENTRY_BYTES
    if role is not None:
        struct.pack_into("<I", output, entry, role)
    if flags is not None:
        struct.pack_into("<I", output, entry + 4, flags)
    if physical_base is not None:
        struct.pack_into("<Q", output, entry + 8, physical_base)
    if byte_count is not None:
        struct.pack_into("<Q", output, entry + 16, byte_count)
    if sha256 is not None:
        if len(sha256) != 32:
            raise ValueError("SHA-256 must contain 32 bytes")
        output[entry + 48 : entry + 80] = sha256
    payload = bytes(output[payload_offset : payload_offset + payload_length])
    struct.pack_into("<I", output, descriptor_offset + 20, pbp1._crc32(payload))
    struct.pack_into("<I", output, 48, 0)
    struct.pack_into("<I", output, 48, pbp1._crc32(bytes(output)))
    return bytes(output)


def rewrite_file_digest(handoff_data: bytes, file_index: int, file_data: bytes) -> bytes:
    if not 0 <= file_index < RETAINED_FILE_COUNT:
        raise ValueError("file_index outside retained-file profile")
    return rewrite_profile_descriptor(
        handoff_data,
        file_index + 1,
        sha256=hashlib.sha256(file_data).digest(),
    )


def rewrite_core_boot_flags(handoff_data: bytes, boot_flags: int) -> bytes:
    output = bytearray(handoff_data)
    record_count = struct.unpack_from("<H", output, 20)[0]
    for index in range(record_count):
        descriptor = pbp1.HEADER_BYTES + index * pbp1.DESCRIPTOR_BYTES
        if struct.unpack_from("<H", output, descriptor)[0] != pbp1.RECORD_CORE:
            continue
        payload_offset, payload_length = struct.unpack_from("<II", output, descriptor + 8)
        struct.pack_into("<Q", output, payload_offset, boot_flags)
        payload = bytes(output[payload_offset : payload_offset + payload_length])
        struct.pack_into("<I", output, descriptor + 20, pbp1._crc32(payload))
        struct.pack_into("<I", output, 48, 0)
        struct.pack_into("<I", output, 48, pbp1._crc32(bytes(output)))
        return bytes(output)
    raise ValueError("PBP1 core record missing")
