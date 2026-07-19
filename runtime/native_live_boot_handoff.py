"""Independent oracle for live pre-exit and exited-development PBP1 transcripts."""

from __future__ import annotations

import dataclasses
import re
import struct
from typing import Any

from runtime import native_boot_handoff as pbp1


CONTRACT_ID = "PBLIVE3"
PROFILE_ARTIFACT_ROLES = (
    pbp1.ARTIFACT_KERNEL,
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
PROFILE_PBART1_COUNT = 6
TRANSCRIPT_PREFIX = "PBP1HEX/0.1 "
MAX_CHUNK_BYTES = 64
BEGIN = re.compile(r"^PBP1HEX/0\.1 BEGIN bytes=([0-9]+)$")
DATA = re.compile(r"^PBP1HEX/0\.1 DATA offset=([0-9]+) hex=([0-9A-F]+)$")
END = re.compile(
    r"^PBP1HEX/0\.1 END bytes=([0-9]+) message_crc32=([0-9A-F]{8}) fnv1a64=([0-9A-F]{16})$"
)


class LiveHandoffError(ValueError):
    """Raised when a live PBP1 transcript or cross-binding fails closed."""


@dataclasses.dataclass(frozen=True)
class Transcript:
    data: bytes
    summary: dict[str, Any]


def fnv1a64(data: bytes) -> int:
    value = 0xCBF29CE484222325
    for byte in data:
        value ^= byte
        value = (value * 0x00000100000001B3) & 0xFFFF_FFFF_FFFF_FFFF
    return value


def format_transcript(data: bytes, *, message_crc32: int | None = None, fnv: int | None = None) -> bytes:
    if not data:
        raise LiveHandoffError("PBP1 transcript payload is empty")
    message_crc32 = pbp1._u32(data, 48) if message_crc32 is None else message_crc32
    fnv = fnv1a64(data) if fnv is None else fnv
    lines = [f"{TRANSCRIPT_PREFIX}BEGIN bytes={len(data)}"]
    for offset in range(0, len(data), MAX_CHUNK_BYTES):
        lines.append(f"{TRANSCRIPT_PREFIX}DATA offset={offset} hex={data[offset:offset + MAX_CHUNK_BYTES].hex().upper()}")
    lines.append(
        f"{TRANSCRIPT_PREFIX}END bytes={len(data)} message_crc32={message_crc32:08X} fnv1a64={fnv:016X}"
    )
    return ("\n".join(lines) + "\n").encode("ascii")


def _hex64(value: int) -> str:
    return f"{value:016X}"


def _record_types(handoff: pbp1.Handoff) -> list[int]:
    return [item.record_type for item in handoff.records]


def _memory_entries(record: pbp1.Record) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for index in range(record.element_count):
        base = index * pbp1.MEMORY_ENTRY_BYTES
        start, pages, attributes = struct.unpack_from("<QQQ", record.payload, base)
        values.append(
            {
                "physical_start": _hex64(start),
                "page_count": pages,
                "attributes": _hex64(attributes),
                "kind": pbp1._u32(record.payload, base + 24),
                "source_type": pbp1._u32(record.payload, base + 28),
            }
        )
    return values


def _artifact_entries(record: pbp1.Record) -> list[dict[str, Any]]:
    if record.element_count != len(PROFILE_ARTIFACT_ROLES):
        raise LiveHandoffError("live PBP1 must bind exactly ten profile artifacts")
    values = []
    ranges = []
    for index, expected_role in enumerate(PROFILE_ARTIFACT_ROLES):
        base = index * pbp1.ARTIFACT_ENTRY_BYTES
        role, flags = struct.unpack_from("<II", record.payload, base)
        physical_base, physical_size, virtual_base, virtual_size, entry_virtual = (
            struct.unpack_from("<QQQQQ", record.payload, base + 8)
        )
        expected_flags = (
            pbp1.ARTIFACT_HASH_VERIFIED | pbp1.ARTIFACT_EXECUTABLE
            if index == 0
            else pbp1.ARTIFACT_HASH_VERIFIED
        )
        digest = record.payload[base + 48 : base + 80]
        if (
            role != expected_role
            or flags != expected_flags
            or physical_base == 0
            or physical_base % pbp1.PAGE_BYTES
            or physical_size == 0
            or (index == 0 and physical_size % pbp1.PAGE_BYTES)
            or not any(digest)
            or (
                index != 0
                and (virtual_base != 0 or virtual_size != 0 or entry_virtual != 0)
            )
        ):
            raise LiveHandoffError("live PBP1 artifact role, flags, or range changed")
        allocation_size = (
            (physical_size + pbp1.PAGE_BYTES - 1) // pbp1.PAGE_BYTES
        ) * pbp1.PAGE_BYTES
        ranges.append((physical_base, allocation_size))
        values.append(
            {
                "role": role,
                "flags": flags,
                "physical_base": _hex64(physical_base),
                "physical_size": physical_size,
                "virtual_base": _hex64(virtual_base),
                "virtual_size": virtual_size,
                "entry_virtual": _hex64(entry_virtual),
                "sha256": digest.hex().upper(),
            }
        )
    for index, (start, size) in enumerate(ranges):
        for other_start, other_size in ranges[index + 1 :]:
            if start < other_start + other_size and other_start < start + size:
                raise LiveHandoffError("live PBP1 artifact ranges overlap")
    return values


def _framebuffer_summary(record: pbp1.Record | None) -> dict[str, Any] | None:
    if record is None:
        return None
    values = struct.unpack("<QQIIIIIIII", record.payload)
    return {
        "physical_base": _hex64(values[0]),
        "byte_count": values[1],
        "width": values[2],
        "height": values[3],
        "stride": values[4],
        "pixel_format": values[5],
        "red_mask": f"{values[6]:08X}",
        "green_mask": f"{values[7]:08X}",
        "blue_mask": f"{values[8]:08X}",
        "reserved_mask": f"{values[9]:08X}",
    }


def _profile_records(
    handoff: pbp1.Handoff,
) -> tuple[dict[str, Any], pbp1.Record, list[dict[str, Any]], dict[str, Any] | None]:
    framebuffer = handoff.record(pbp1.RECORD_FRAMEBUFFER)
    expected_types = [pbp1.RECORD_CORE, pbp1.RECORD_MEMORY_MAP]
    if framebuffer is not None:
        expected_types.append(pbp1.RECORD_FRAMEBUFFER)
    expected_types.append(pbp1.RECORD_LOADED_ARTIFACTS)
    expected_features = (
        pbp1.FEATURE_CORE
        | pbp1.FEATURE_MEMORY_MAP
        | pbp1.FEATURE_LOADED_ARTIFACTS
        | (pbp1.FEATURE_FRAMEBUFFER if framebuffer is not None else 0)
    )
    expected_required = pbp1.FEATURE_CORE | pbp1.FEATURE_MEMORY_MAP | pbp1.FEATURE_LOADED_ARTIFACTS
    if (
        _record_types(handoff) != expected_types
        or handoff.features != expected_features
        or handoff.required_features != expected_required
    ):
        raise LiveHandoffError("live PBP1 record or feature profile changed")
    core_record = handoff.record(pbp1.RECORD_CORE)
    memory = handoff.record(pbp1.RECORD_MEMORY_MAP)
    artifacts = handoff.record(pbp1.RECORD_LOADED_ARTIFACTS)
    if core_record is None or memory is None or artifacts is None:
        raise LiveHandoffError("live PBP1 required record missing")
    core = pbp1._validate_core(core_record.payload, handoff.total_size)
    return core, memory, _artifact_entries(artifacts), _framebuffer_summary(framebuffer)


def _profile_summary(
    handoff: pbp1.Handoff,
    core: dict[str, Any],
    memory: pbp1.Record,
    artifacts: list[dict[str, Any]],
    framebuffer: dict[str, Any] | None,
    *,
    exited: bool,
) -> dict[str, Any]:
    return {
        "record_count": len(handoff.records),
        "features": f"{handoff.features:016X}",
        "required_features": f"{handoff.required_features:016X}",
        "memory_entry_count": memory.element_count,
        "memory_entries": _memory_entries(memory),
        "core": {
            "boot_flags": f"{core['boot_flags']:016X}",
            "kernel_physical_base": _hex64(core["kernel_physical_base"]),
            "kernel_physical_size": core["kernel_physical_size"],
            "kernel_virtual_base": _hex64(core["kernel_virtual_base"]),
            "kernel_virtual_size": core["kernel_virtual_size"],
            "kernel_entry_virtual": _hex64(core["kernel_entry_virtual"]),
            "initial_stack_top_virtual": _hex64(core["initial_stack_top_virtual"]),
            "page_table_root_physical": _hex64(core["page_table_root_physical"]),
            "handoff_physical_base": _hex64(core["handoff_physical_base"]),
            "handoff_virtual_base": _hex64(core["handoff_virtual_base"]),
            "handoff_byte_count": core["handoff_byte_count"],
            "boot_attempt": core["boot_attempt"],
            "boot_attempt_limit": core["boot_attempt_limit"],
            "boot_slot": core["boot_slot"],
            "selected_entry": core["selected_entry"],
            "uefi_revision": f"{core['uefi_revision']:08X}",
        },
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "kernel_artifact": artifacts[0],
        "framebuffer": framebuffer,
        "development_mode_only": True,
        "boot_services_exited": exited,
        "transferable": False,
        "secret_bearing_records_present": False,
        "exit_development_profile_validated": exited,
        "pre_exit_profile_validated": not exited,
        "kernel_entry_profile_rejected": True,
    }


def validate_pre_exit_profile(handoff: pbp1.Handoff) -> dict[str, Any]:
    core, memory, artifacts, framebuffer = _profile_records(handoff)
    if (
        core["boot_flags"] != pbp1.DEVELOPMENT_MODE
        or core["initial_stack_top_virtual"] != 0
        or core["page_table_root_physical"] != 0
        or core["uefi_system_table_physical"] != 0
        or core["uefi_runtime_services_physical"] != 0
    ):
        raise LiveHandoffError("live PBP1 is not an honest pre-exit snapshot")
    try:
        pbp1.validate_kernel_entry_profile(handoff)
    except pbp1.BootHandoffError:
        pass
    else:
        raise LiveHandoffError("pre-exit PBP1 unexpectedly satisfies the transfer profile")
    return _profile_summary(
        handoff, core, memory, artifacts, framebuffer, exited=False
    )


def validate_exit_development_profile(handoff: pbp1.Handoff) -> dict[str, Any]:
    core, memory, artifacts, framebuffer = _profile_records(handoff)
    if (
        core["boot_flags"] != pbp1.DEVELOPMENT_MODE | pbp1.BOOT_SERVICES_EXITED
        or core["initial_stack_top_virtual"] == 0
        or core["initial_stack_top_virtual"] % 16
        or core["page_table_root_physical"] == 0
        or core["page_table_root_physical"] % pbp1.PAGE_BYTES
        or core["uefi_system_table_physical"] != 0
        or core["uefi_runtime_services_physical"] != 0
    ):
        raise LiveHandoffError("exited-development PBP1 transfer state is malformed")
    try:
        pbp1.validate_kernel_entry_profile(handoff)
    except pbp1.BootHandoffError:
        pass
    else:
        raise LiveHandoffError("exited-development PBP1 unexpectedly satisfies kernel entry")
    return _profile_summary(
        handoff, core, memory, artifacts, framebuffer, exited=True
    )


def extract_transcript(raw: bytes) -> Transcript:
    text = raw.decode("ascii", errors="strict").replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith(TRANSCRIPT_PREFIX)]
    if len(lines) < 3:
        raise LiveHandoffError("complete PBP1 transcript is missing")
    begin = BEGIN.fullmatch(lines[0])
    end = END.fullmatch(lines[-1])
    if begin is None or end is None:
        raise LiveHandoffError("PBP1 transcript framing is malformed")
    declared = int(begin.group(1))
    if not 1 <= declared <= pbp1.MAX_TOTAL_BYTES or int(end.group(1)) != declared:
        raise LiveHandoffError("PBP1 transcript byte count is invalid")
    chunks: list[bytes] = []
    cursor = 0
    for line in lines[1:-1]:
        match = DATA.fullmatch(line)
        if match is None:
            raise LiveHandoffError("PBP1 transcript data line is malformed")
        if int(match.group(1)) != cursor:
            raise LiveHandoffError("PBP1 transcript offset is not contiguous")
        encoded = match.group(2)
        if len(encoded) % 2:
            raise LiveHandoffError("PBP1 transcript has odd-length hex")
        chunk = bytes.fromhex(encoded)
        if not 1 <= len(chunk) <= MAX_CHUNK_BYTES:
            raise LiveHandoffError("PBP1 transcript chunk exceeds its bound")
        chunks.append(chunk)
        cursor += len(chunk)
    data = b"".join(chunks)
    if len(data) != declared:
        raise LiveHandoffError("PBP1 transcript reconstruction length differs")
    declared_crc = int(end.group(2), 16)
    declared_fnv = int(end.group(3), 16)
    if pbp1._u32(data, 48) != declared_crc:
        raise LiveHandoffError("PBP1 transcript message CRC declaration differs")
    if fnv1a64(data) != declared_fnv:
        raise LiveHandoffError("PBP1 transcript FNV declaration differs")
    try:
        handoff = pbp1.decode(data)
    except pbp1.BootHandoffError as error:
        raise LiveHandoffError(f"PBP1 transcript payload rejects: {error}") from error
    core_record = handoff.record(pbp1.RECORD_CORE)
    if core_record is None:
        raise LiveHandoffError("PBP1 core record is missing")
    boot_flags = pbp1._validate_core(core_record.payload, handoff.total_size)["boot_flags"]
    if boot_flags == pbp1.DEVELOPMENT_MODE:
        profile = validate_pre_exit_profile(handoff)
    elif boot_flags == pbp1.DEVELOPMENT_MODE | pbp1.BOOT_SERVICES_EXITED:
        profile = validate_exit_development_profile(handoff)
    else:
        raise LiveHandoffError("live PBP1 boot-state profile is unsupported")
    summary = {
        "contract_id": CONTRACT_ID,
        "byte_count": len(data),
        "sha256": pbp1.sha256_bytes(data),
        "message_crc32": f"{declared_crc:08X}",
        "fnv1a64": f"{declared_fnv:016X}",
        **profile,
    }
    return Transcript(data=data, summary=summary)


def _loader_range_covered(entries: list[dict[str, Any]], start: int, byte_count: int) -> bool:
    end = start + byte_count
    cursor = start
    for entry in entries:
        entry_start = int(entry["physical_start"], 16)
        entry_end = entry_start + entry["page_count"] * pbp1.PAGE_BYTES
        if cursor < entry_start:
            return False
        if cursor >= entry_end:
            continue
        if entry["kind"] != pbp1.MEMORY_LOADER_RESERVED:
            return False
        cursor = min(entry_end, end)
        if cursor == end:
            return True
    return False


def validate_oracle_binding(
    transcript: dict[str, Any],
    marker_summary: dict[str, Any],
    media_inspection: dict[str, Any],
) -> None:
    marker = marker_summary["pbp1"]
    if (
        transcript.get("boot_services_exited") is not True
        or transcript.get("exit_development_profile_validated") is not True
        or transcript.get("transferable") is not False
        or transcript["byte_count"] != marker["byte_count"]
        or transcript["record_count"] != marker["record_count"]
        or transcript["memory_entry_count"] != marker["memory_entry_count"]
        or int(transcript["framebuffer"] is not None) != marker["framebuffer_present"]
        or transcript["artifact_count"] != len(PROFILE_ARTIFACT_ROLES)
        or marker["artifact_count"] != len(PROFILE_ARTIFACT_ROLES)
        or transcript["message_crc32"] != marker["message_crc32"]
        or transcript["fnv1a64"] != marker["fnv1a64"]
    ):
        raise LiveHandoffError("PBP1 marker and reconstructed transcript diverge")
    core = transcript["core"]
    artifact = transcript["kernel_artifact"]
    artifacts = transcript["artifacts"]
    retained = marker_summary["kernel_map"]["retained"]
    plan = media_inspection["kernel"]["plan"]
    config = marker_summary["boot_config"]
    manifest = marker_summary["manifest"]
    media_manifest = media_inspection["manifest"]
    kernel_manifest = next(item for item in media_manifest["artifacts"] if item["type"] == "kernel")
    if (
        int(core["kernel_virtual_base"], 16) != plan["virtual_base"]
        or core["kernel_virtual_size"] != plan["image_size"]
        or int(core["kernel_entry_virtual"], 16) != plan["entry_virtual"]
        or core["kernel_physical_size"] != plan["image_size"]
        or core["handoff_byte_count"] != transcript["byte_count"]
        or core["boot_attempt"] != 0
        or core["boot_attempt_limit"] != config["boot_attempt_limit"]
        or core["boot_slot"] != config["selected_slot"]
        or core["selected_entry"] != 1
        or int(core["uefi_revision"], 16) != marker_summary["uefi_revision"]
        or int(core["kernel_physical_base"], 16) != retained["kernel_physical_base"]
        or int(core["initial_stack_top_virtual"], 16) != retained["stack_top_virtual"]
        or int(core["page_table_root_physical"], 16)
        != retained["page_table_root_physical"]
        or int(core["handoff_physical_base"], 16) != retained["handoff_physical_base"]
        or int(core["handoff_virtual_base"], 16) != retained["handoff_virtual_base"]
        or artifact["physical_base"] != core["kernel_physical_base"]
        or artifact["physical_size"] != core["kernel_physical_size"]
        or artifact["virtual_base"] != core["kernel_virtual_base"]
        or artifact["virtual_size"] != core["kernel_virtual_size"]
        or artifact["entry_virtual"] != core["kernel_entry_virtual"]
        or artifact["sha256"] != kernel_manifest["sha256"]
        or artifact["sha256"][:16] != manifest["kernel_sha256_prefix"]
    ):
        raise LiveHandoffError("PBP1 kernel/config/manifest/entry cross-binding differs")
    media_artifacts = media_inspection["artifact_set"]["artifacts"]
    if len(media_artifacts) != PROFILE_PBART1_COUNT:
        raise LiveHandoffError("PBP1 PBART1 media profile count diverges")
    manifest_file = media_inspection["files"][2]
    trust_policy_file = media_inspection["files"][-2]
    trust_state_file = media_inspection["files"][-1]
    expected_inputs = [
        {
            "role": PROFILE_ARTIFACT_ROLES[index],
            "file_bytes": media_artifact["file_bytes"],
            "sha256": media_artifact["file_sha256"],
        }
        for index, media_artifact in enumerate(media_artifacts, start=1)
    ]
    expected_inputs.extend(
        (
            {
                "role": pbp1.ARTIFACT_SYSTEM_MANIFEST,
                "file_bytes": manifest_file["byte_count"],
                "sha256": manifest_file["sha256"],
            },
            {
                "role": pbp1.ARTIFACT_TRUST_POLICY,
                "file_bytes": trust_policy_file["byte_count"],
                "sha256": trust_policy_file["sha256"],
            },
            {
                "role": pbp1.ARTIFACT_TRUST_STATE,
                "file_bytes": trust_state_file["byte_count"],
                "sha256": trust_state_file["sha256"],
            },
        )
    )
    if len(expected_inputs) != len(artifacts) - 1:
        raise LiveHandoffError("PBP1 and retained-input counts diverge")
    for entry, expected in zip(artifacts[1:], expected_inputs, strict=True):
        if (
            entry["role"] != expected["role"]
            or entry["flags"] != pbp1.ARTIFACT_HASH_VERIFIED
            or entry["physical_size"] != expected["file_bytes"]
            or entry["virtual_base"] != "0000000000000000"
            or entry["virtual_size"] != 0
            or entry["entry_virtual"] != "0000000000000000"
            or entry["sha256"] != expected["sha256"]
        ):
            raise LiveHandoffError("PBP1 retained-input role, digest, or exact size diverges")
    retained_input_pages = sum(
        (item["physical_size"] + pbp1.PAGE_BYTES - 1) // pbp1.PAGE_BYTES
        for item in artifacts[1:]
    )
    expected_input_pages = marker_summary["artifact_set"]["page_count"] + sum(
        (item["byte_count"] + pbp1.PAGE_BYTES - 1) // pbp1.PAGE_BYTES
        for item in (manifest_file, trust_policy_file, trust_state_file)
    )
    if (
        retained_input_pages != expected_input_pages
        or marker_summary["boot_exit"]["artifact_page_count"] != expected_input_pages
        or manifest_file["byte_count"] != marker_summary["manifest"]["byte_count"]
        or trust_policy_file["byte_count"]
        != marker_summary["trust_state"]["policy_bytes"]
        or trust_state_file["byte_count"]
        != marker_summary["trust_state"]["state_bytes"]
        or trust_policy_file["sha256"]
        != marker_summary["trust_state"]["policy_sha256"]
        or trust_state_file["sha256"]
        != marker_summary["trust_state"]["state_sha256"]
    ):
        raise LiveHandoffError("PBP1 retained-input page or trust accounting diverges")
    retained_ranges = (
        *((int(item["physical_base"], 16), item["physical_size"]) for item in artifacts),
        (
            retained["page_table_root_physical"],
            retained["table_page_count"] * pbp1.PAGE_BYTES,
        ),
        (
            retained["stack_physical_base"],
            retained["stack_page_count"] * pbp1.PAGE_BYTES,
        ),
        (
            retained["handoff_physical_base"],
            retained["handoff_page_count"] * pbp1.PAGE_BYTES,
        ),
    )
    if not all(
        _loader_range_covered(transcript["memory_entries"], start, size)
        for start, size in retained_ranges
    ):
        raise LiveHandoffError("PBP1 final map omits a retained loader range")
    framebuffer = transcript["framebuffer"]
    gop = marker_summary["gop"]
    if framebuffer is None or (
        framebuffer["width"] != gop["width"]
        or framebuffer["height"] != gop["height"]
        or framebuffer["stride"] != gop["stride"]
        or framebuffer["pixel_format"] != (1 if gop["format"] == "RGB" else 2)
    ):
        raise LiveHandoffError("PBP1 framebuffer and live GOP marker diverge")
