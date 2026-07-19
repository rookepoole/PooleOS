from __future__ import annotations

import hashlib
import struct
import unittest

from runtime import native_boot_handoff as pbp1
from runtime import native_live_boot_handoff


KERNEL_PHYSICAL = 0x0200_0000
KERNEL_SIZE = 0x0003_0000
KERNEL_VIRTUAL = 0xFFFF_FFFF_8000_0000
ARTIFACT_PHYSICAL = 0x0210_0000
ROOT_PHYSICAL = 0x0300_0000
STACK_PHYSICAL = 0x0400_0000
STACK_TOP = KERNEL_VIRTUAL + 57 * 4096
HANDOFF_PHYSICAL = 0x0500_0000
HANDOFF_VIRTUAL = KERNEL_VIRTUAL + 64 * 4096


def exited_handoff() -> bytes:
    memory_entries = (
        (KERNEL_PHYSICAL, 48, 0, pbp1.MEMORY_LOADER_RESERVED, 2, 0),
        (ARTIFACT_PHYSICAL, 9, 0, pbp1.MEMORY_LOADER_RESERVED, 2, 0),
        (ROOT_PHYSICAL, 4, 0, pbp1.MEMORY_LOADER_RESERVED, 2, 0),
        (STACK_PHYSICAL, 8, 0, pbp1.MEMORY_LOADER_RESERVED, 2, 0),
        (HANDOFF_PHYSICAL, 256, 0, pbp1.MEMORY_LOADER_RESERVED, 2, 0),
        (0x8000_0000, 1000, 0, pbp1.MEMORY_FRAMEBUFFER, 11, 0),
    )
    memory = b"".join(struct.pack("<QQQIIQ", *entry) for entry in memory_entries)
    framebuffer = struct.pack(
        "<QQIIIIIIII",
        0x8000_0000,
        4_096_000,
        1280,
        800,
        1280,
        2,
        0x00FF_0000,
        0x0000_FF00,
        0x0000_00FF,
        0xFF00_0000,
    )
    digest = hashlib.sha256(b"PKLOAD5 kernel").digest()
    artifacts = [
        struct.pack(
            "<IIQQQQQ32s",
            pbp1.ARTIFACT_KERNEL,
            pbp1.ARTIFACT_HASH_VERIFIED | pbp1.ARTIFACT_EXECUTABLE,
            KERNEL_PHYSICAL,
            KERNEL_SIZE,
            KERNEL_VIRTUAL,
            KERNEL_SIZE,
            KERNEL_VIRTUAL + 0x4000,
            digest,
        )
    ]
    for index, role in enumerate(native_live_boot_handoff.PROFILE_ARTIFACT_ROLES[1:]):
        artifacts.append(
            struct.pack(
                "<IIQQQQQ32s",
                role,
                pbp1.ARTIFACT_HASH_VERIFIED,
                ARTIFACT_PHYSICAL + index * pbp1.PAGE_BYTES,
                257 + index * 31,
                0,
                0,
                0,
                hashlib.sha256(f"PBART1 role {role}".encode("ascii")).digest(),
            )
        )
    artifact = b"".join(artifacts)
    total = pbp1.encoded_size((pbp1.CORE_BYTES, len(memory), len(framebuffer), len(artifact)))
    core_values = (
        pbp1.DEVELOPMENT_MODE | pbp1.BOOT_SERVICES_EXITED,
        KERNEL_PHYSICAL,
        KERNEL_SIZE,
        KERNEL_VIRTUAL,
        KERNEL_SIZE,
        KERNEL_VIRTUAL + 0x4000,
        STACK_TOP,
        ROOT_PHYSICAL,
        HANDOFF_PHYSICAL,
        HANDOFF_VIRTUAL,
        total,
        0,
        0,
    )
    core = struct.pack("<13Q6I", *core_values, 0, 3, 1, 1, 0x0002_0046, 0)
    return pbp1.encode(
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
                "element_count": len(memory_entries),
                "payload": memory,
            },
            {
                "record_type": pbp1.RECORD_FRAMEBUFFER,
                "element_size": pbp1.FRAMEBUFFER_BYTES,
                "element_count": 1,
                "payload": framebuffer,
            },
            {
                "record_type": pbp1.RECORD_LOADED_ARTIFACTS,
                "flags": pbp1.RECORD_REQUIRED | pbp1.RECORD_ARRAY,
                "element_size": pbp1.ARTIFACT_ENTRY_BYTES,
                "element_count": len(artifacts),
                "payload": artifact,
            },
        )
    )


class NativeLiveBootHandoffTests(unittest.TestCase):
    def test_exited_development_profile_is_exact_and_nontransferable(self) -> None:
        data = exited_handoff()
        transcript = native_live_boot_handoff.extract_transcript(
            native_live_boot_handoff.format_transcript(data)
        )
        self.assertEqual("PBLIVE3", transcript.summary["contract_id"])
        self.assertTrue(transcript.summary["boot_services_exited"])
        self.assertTrue(transcript.summary["exit_development_profile_validated"])
        self.assertFalse(transcript.summary["transferable"])
        self.assertEqual(6, transcript.summary["memory_entry_count"])
        self.assertEqual(10, transcript.summary["artifact_count"])

    def test_exited_profile_rejects_transfer_overclaim(self) -> None:
        handoff = pbp1.decode(exited_handoff())
        artifact = handoff.record(pbp1.RECORD_LOADED_ARTIFACTS)
        assert artifact is not None
        hostile = bytearray(artifact.payload)
        struct.pack_into(
            "<I",
            hostile,
            4,
            pbp1.ARTIFACT_HASH_VERIFIED
            | pbp1.ARTIFACT_SIGNATURE_VERIFIED
            | pbp1.ARTIFACT_EXECUTABLE,
        )
        records = []
        for record in handoff.records:
            records.append(
                {
                    "record_type": record.record_type,
                    "flags": record.flags,
                    "element_size": record.element_size,
                    "element_count": record.element_count,
                    "payload": bytes(hostile) if record.record_type == pbp1.RECORD_LOADED_ARTIFACTS else record.payload,
                }
            )
        with self.assertRaises((pbp1.BootHandoffError, native_live_boot_handoff.LiveHandoffError)):
            native_live_boot_handoff.validate_exit_development_profile(
                pbp1.decode(pbp1.encode(records))
            )

    def test_loader_range_coverage_rejects_omission_and_wrong_kind(self) -> None:
        summary = native_live_boot_handoff.extract_transcript(
            native_live_boot_handoff.format_transcript(exited_handoff())
        ).summary
        entries = summary["memory_entries"]
        self.assertTrue(native_live_boot_handoff._loader_range_covered(entries, STACK_PHYSICAL, 8 * 4096))
        hostile = [dict(item) for item in entries]
        hostile[3]["kind"] = pbp1.MEMORY_USABLE
        self.assertFalse(native_live_boot_handoff._loader_range_covered(hostile, STACK_PHYSICAL, 8 * 4096))
        self.assertFalse(native_live_boot_handoff._loader_range_covered(entries, 0x0600_0000, 4096))


if __name__ == "__main__":
    unittest.main()
