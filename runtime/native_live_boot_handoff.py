"""Independent oracle for live pre-exit PBP1 transcripts emitted by PooleBoot."""

from __future__ import annotations

import dataclasses
import re
import struct
from typing import Any

from runtime import native_boot_handoff as pbp1


CONTRACT_ID = "PBLIVE1"
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


def validate_pre_exit_profile(handoff: pbp1.Handoff) -> dict[str, Any]:
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
    if (
        core["boot_flags"] != pbp1.DEVELOPMENT_MODE
        or core["initial_stack_top_virtual"] != 0
        or core["page_table_root_physical"] != 0
        or core["uefi_system_table_physical"] != 0
        or core["uefi_runtime_services_physical"] != 0
    ):
        raise LiveHandoffError("live PBP1 is not an honest pre-exit snapshot")
    if artifacts.element_count != 1:
        raise LiveHandoffError("live PBP1 must bind exactly one kernel artifact")
    role, artifact_flags = struct.unpack_from("<II", artifacts.payload)
    if role != pbp1.ARTIFACT_KERNEL or artifact_flags != (
        pbp1.ARTIFACT_HASH_VERIFIED | pbp1.ARTIFACT_EXECUTABLE
    ):
        raise LiveHandoffError("live PBP1 artifact flags overclaim or omit digest verification")
    try:
        pbp1.validate_kernel_entry_profile(handoff)
    except pbp1.BootHandoffError:
        pass
    else:
        raise LiveHandoffError("pre-exit PBP1 unexpectedly satisfies the transfer profile")

    artifact = {
        "role": role,
        "flags": artifact_flags,
        "physical_base": _hex64(pbp1._u64(artifacts.payload, 8)),
        "physical_size": pbp1._u64(artifacts.payload, 16),
        "virtual_base": _hex64(pbp1._u64(artifacts.payload, 24)),
        "virtual_size": pbp1._u64(artifacts.payload, 32),
        "entry_virtual": _hex64(pbp1._u64(artifacts.payload, 40)),
        "sha256": artifacts.payload[48:80].hex().upper(),
    }
    framebuffer_summary = None
    if framebuffer is not None:
        values = struct.unpack("<QQIIIIIIII", framebuffer.payload)
        framebuffer_summary = {
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
    return {
        "record_count": len(handoff.records),
        "features": f"{handoff.features:016X}",
        "required_features": f"{handoff.required_features:016X}",
        "memory_entry_count": memory.element_count,
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
        "kernel_artifact": artifact,
        "framebuffer": framebuffer_summary,
        "development_mode_only": True,
        "boot_services_exited": False,
        "transferable": False,
        "secret_bearing_records_present": False,
        "pre_exit_profile_validated": True,
        "kernel_entry_profile_rejected": True,
    }


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
    profile = validate_pre_exit_profile(handoff)
    summary = {
        "contract_id": CONTRACT_ID,
        "byte_count": len(data),
        "sha256": pbp1.sha256_bytes(data),
        "message_crc32": f"{declared_crc:08X}",
        "fnv1a64": f"{declared_fnv:016X}",
        **profile,
    }
    return Transcript(data=data, summary=summary)


def validate_oracle_binding(
    transcript: dict[str, Any],
    marker_summary: dict[str, Any],
    media_inspection: dict[str, Any],
) -> None:
    marker = marker_summary["pbp1"]
    if (
        transcript["byte_count"] != marker["byte_count"]
        or transcript["record_count"] != marker["record_count"]
        or transcript["memory_entry_count"] != marker["memory_entry_count"]
        or int(transcript["framebuffer"] is not None) != marker["framebuffer_present"]
        or marker["artifact_count"] != 1
        or transcript["message_crc32"] != marker["message_crc32"]
        or transcript["fnv1a64"] != marker["fnv1a64"]
    ):
        raise LiveHandoffError("PBP1 marker and reconstructed transcript diverge")
    core = transcript["core"]
    artifact = transcript["kernel_artifact"]
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
        or artifact["physical_base"] != core["kernel_physical_base"]
        or artifact["physical_size"] != core["kernel_physical_size"]
        or artifact["virtual_base"] != core["kernel_virtual_base"]
        or artifact["virtual_size"] != core["kernel_virtual_size"]
        or artifact["entry_virtual"] != core["kernel_entry_virtual"]
        or artifact["sha256"] != kernel_manifest["sha256"]
        or artifact["sha256"][:16] != manifest["kernel_sha256_prefix"]
    ):
        raise LiveHandoffError("PBP1 kernel/config/manifest/entry cross-binding differs")
    framebuffer = transcript["framebuffer"]
    gop = marker_summary["gop"]
    if framebuffer is None or (
        framebuffer["width"] != gop["width"]
        or framebuffer["height"] != gop["height"]
        or framebuffer["stride"] != gop["stride"]
        or framebuffer["pixel_format"] != (1 if gop["format"] == "RGB" else 2)
    ):
        raise LiveHandoffError("PBP1 framebuffer and live GOP marker diverge")
