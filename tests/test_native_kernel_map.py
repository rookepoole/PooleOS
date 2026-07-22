from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime import native_kernel_map  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def plan() -> dict[str, object]:
    return {
        "physical_base": 0x0200_0000,
        "virtual_base": native_kernel_map.MIN_VIRTUAL_BASE,
        "image_size": 0x40000,
        "entry_virtual": native_kernel_map.MIN_VIRTUAL_BASE + 0x8000,
        "mappings": [
            {"virtual_offset": 0, "memory_size": 0x8000, "permissions": "r"},
            {"virtual_offset": 0x8000, "memory_size": 0x22000, "permissions": "rx"},
            {"virtual_offset": 0x2A000, "memory_size": 0x5000, "permissions": "r"},
            {"virtual_offset": 0x2F000, "memory_size": 0x11000, "permissions": "rw"},
        ],
    }


class NativeKernelMapTests(unittest.TestCase):
    def test_contract_matches_schema_and_control_register(self) -> None:
        contract = json.loads(
            (ROOT / "specs" / "native-kernel-map-contract.json").read_text(encoding="utf-8")
        )
        schema = json.loads(
            (ROOT / "specs" / "native-kernel-map-contract.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual([], list(validate_json(contract, schema)))
        self.assertEqual(native_kernel_map.RETAINED_CONTRACT_ID, contract["contract_id"])
        self.assertEqual(28, len(contract["required_negative_controls"]))

    def test_exact_product_model_matches_frozen_summary(self) -> None:
        model = native_kernel_map.build_model(native_kernel_map.request_from_elf_plan(plan(), 48))
        self.assertEqual(64, model["mapped_page_count"])
        self.assertEqual(13, model["read_only_page_count"])
        self.assertEqual(34, model["read_execute_page_count"])
        self.assertEqual(17, model["read_write_page_count"])
        self.assertEqual(0, model["writable_executable_page_count"])
        self.assertEqual(
            {"pml4": 511, "pdpt": 510, "page_directory": 0, "first_page_table": 0},
            model["indices"],
        )
        self.assertEqual("ECB08F4FB12FEC67", model["leaf_fingerprint"])
        native_kernel_map.validate_model(model)

    def test_cpu_profile_requires_wp_nx_and_four_level_non_pcid_mode(self) -> None:
        profile = {
            "paging": True,
            "pae": True,
            "long_mode": True,
            "write_protect": True,
            "nx_supported": True,
            "nx_enabled": True,
            "five_level_paging": False,
            "pcid_enabled": False,
            "physical_address_bits": 40,
        }
        native_kernel_map.validate_cpu(profile)
        for field in ("write_protect", "nx_supported", "nx_enabled"):
            hostile = dict(profile)
            hostile[field] = False
            with self.assertRaises(native_kernel_map.KernelMapError):
                native_kernel_map.validate_cpu(hostile)
        for field in ("five_level_paging", "pcid_enabled"):
            hostile = dict(profile)
            hostile[field] = True
            with self.assertRaises(native_kernel_map.KernelMapError):
                native_kernel_map.validate_cpu(hostile)

    def test_rejects_occupied_high_half_slot(self) -> None:
        root = [0] * native_kernel_map.TABLE_ENTRIES
        root[511] = 0x4003
        with self.assertRaises(native_kernel_map.KernelMapError):
            native_kernel_map.build_model(
                native_kernel_map.request_from_elf_plan(plan(), 48), original_root=root
            )

    def test_rejects_alignment_gap_overlap_and_window_overflow(self) -> None:
        for mutate in (
            lambda value: value["mappings"][1].__setitem__("virtual_offset", 0x4001),
            lambda value: value["mappings"][1].__setitem__("virtual_offset", 0x5000),
            lambda value: value["mappings"][1].__setitem__("virtual_offset", 0x3000),
            lambda value: value.__setitem__("image_size", native_kernel_map.WINDOW_BYTES + 0x1000),
        ):
            hostile = copy.deepcopy(plan())
            mutate(hostile)
            with self.assertRaises(native_kernel_map.KernelMapError):
                native_kernel_map.build_model(
                    native_kernel_map.request_from_elf_plan(hostile, 48)
                )

    def test_rejects_writable_executable_and_nonexecutable_entry(self) -> None:
        hostile = copy.deepcopy(plan())
        hostile["mappings"][3]["permissions"] = "rwx"
        with self.assertRaises(native_kernel_map.KernelMapError):
            native_kernel_map.build_model(native_kernel_map.request_from_elf_plan(hostile, 48))
        hostile = copy.deepcopy(plan())
        hostile["entry_virtual"] = native_kernel_map.MIN_VIRTUAL_BASE
        with self.assertRaises(native_kernel_map.KernelMapError):
            native_kernel_map.build_model(native_kernel_map.request_from_elf_plan(hostile, 48))

    def test_rejects_wrong_physical_and_table_overlap(self) -> None:
        hostile = copy.deepcopy(plan())
        hostile["physical_base"] += 1
        with self.assertRaises(native_kernel_map.KernelMapError):
            native_kernel_map.build_model(native_kernel_map.request_from_elf_plan(hostile, 48))
        request = native_kernel_map.request_from_elf_plan(plan(), 48)
        with self.assertRaises(native_kernel_map.KernelMapError):
            native_kernel_map.build_model(request, table_base=request.physical_base)

    def test_model_validator_rejects_leaf_physical_flag_and_index_drift(self) -> None:
        model = native_kernel_map.build_model(native_kernel_map.request_from_elf_plan(plan(), 48))
        hostile_values = (
            native_kernel_map.mutated_model(model, ("leaves", 1, "physical_offset"), 0),
            native_kernel_map.mutated_model(model, ("leaves", 1, "normalized_flags"), "8000000000000003"),
            native_kernel_map.mutated_model(model, ("indices", "pdpt"), 509),
        )
        for hostile in hostile_values:
            with self.assertRaises(native_kernel_map.KernelMapError):
                native_kernel_map.validate_model(hostile)

    def test_probe_parser_requires_exact_order_and_fingerprint(self) -> None:
        line = (
            "PKMAP1 PASS mappings=4 pages=64 ro=13 rx=34 rw=17 wx=0 "
            "pml4=511 pdpt=510 pd=0 pt=0 leaf_fnv1a64=ECB08F4FB12FEC67"
        )
        observed = native_kernel_map.parse_probe_output(line)
        expected = native_kernel_map.marker_expectation(plan(), 48)
        self.assertEqual(expected, observed)
        with self.assertRaises(native_kernel_map.KernelMapError):
            native_kernel_map.parse_probe_output(line.replace("wx=0", "wx=1"))

    def test_retained_model_binds_guarded_stack_and_read_only_handoff(self) -> None:
        model = native_kernel_map.build_retained_model(
            native_kernel_map.request_from_elf_plan(plan(), 48),
            native_kernel_map.RetainedRequest(
                stack_physical_base=0x0400_0000,
                stack_page_count=14,
                handoff_physical_base=0x0500_0000,
                handoff_capacity_bytes=1024 * 1024,
            ),
        )
        self.assertEqual([66, 81], model["guard_page_indices"])
        self.assertEqual(334, model["total_mapped_page_count"])
        self.assertEqual("rw", model["retained_leaves"][0]["permissions"])
        self.assertEqual("r", model["retained_leaves"][-1]["permissions"])

    def test_retained_model_rejects_overlap_range_and_kernel_guard_collision(self) -> None:
        request = native_kernel_map.request_from_elf_plan(plan(), 48)
        for retained in (
            native_kernel_map.RetainedRequest(request.physical_base, 14, 0x0500_0000, 1024 * 1024),
            native_kernel_map.RetainedRequest(0x0400_0001, 14, 0x0500_0000, 1024 * 1024),
            native_kernel_map.RetainedRequest(0x0400_0000, 13, 0x0500_0000, 1024 * 1024),
        ):
            with self.assertRaises(native_kernel_map.KernelMapError):
                native_kernel_map.build_retained_model(request, retained)
        hostile = copy.deepcopy(plan())
        hostile["image_size"] = 67 * native_kernel_map.PAGE_SIZE
        hostile["mappings"][-1]["memory_size"] += native_kernel_map.PAGE_SIZE
        with self.assertRaises(native_kernel_map.KernelMapError):
            native_kernel_map.build_retained_model(
                native_kernel_map.request_from_elf_plan(hostile, 48),
                native_kernel_map.RetainedRequest(0x0400_0000, 14, 0x0500_0000, 1024 * 1024),
            )

    def test_retained_probe_and_lifecycle_are_exact(self) -> None:
        expected = native_kernel_map.build_retained_model(
            native_kernel_map.request_from_elf_plan(plan(), 48),
            native_kernel_map.RetainedRequest(0x0400_0000, 14, 0x0500_0000, 1024 * 1024),
        )
        line = (
            "PKMAP2 PASS kernel_pages=64 stack_pages=14 handoff_pages=256 guards=2 "
            f"total_pages=334 stack_pt=67 handoff_pt=82 retained_fnv1a64={expected['retained_leaf_fingerprint']}"
        )
        self.assertEqual(
            expected["retained_leaf_fingerprint"],
            native_kernel_map.parse_retained_probe_output(line)["retained_leaf_fingerprint"],
        )
        events = [
            {"state": "prepared", "original_cr3": 0x1000},
            {"state": "candidate_active", "firmware_call_count": 0},
            {"state": "restored", "observed_cr3": 0x1000},
            {"state": "retained", "table_pages_freed": 0},
        ]
        native_kernel_map.validate_retained_lifecycle(events)
        hostile = copy.deepcopy(events)
        hostile[-1]["table_pages_freed"] = 4
        with self.assertRaises(native_kernel_map.KernelMapError):
            native_kernel_map.validate_retained_lifecycle(hostile)

    def test_lifecycle_rejects_firmware_call_activation_and_rollback_drift(self) -> None:
        events = [
            {"state": "prepared", "original_cr3": 0x1000},
            {"state": "candidate_active", "firmware_call_count": 0},
            {"state": "restored", "observed_cr3": 0x1000},
            {"state": "released", "table_pages_freed": 4},
        ]
        native_kernel_map.validate_lifecycle(events)
        for index, field, value in (
            (1, "firmware_call_count", 1),
            (2, "observed_cr3", 0x2000),
            (3, "table_pages_freed", 3),
        ):
            hostile = copy.deepcopy(events)
            hostile[index][field] = value
            with self.assertRaises(native_kernel_map.KernelMapError):
                native_kernel_map.validate_lifecycle(hostile)

    def test_framebuffer_snapshot_rejects_translation_and_cache_drift(self) -> None:
        snapshot = {
            "first_physical": 0x8000_0000,
            "last_physical": 0x803F_FFFF,
            "first_page_size": 0x20_0000,
            "last_page_size": 0x20_0000,
            "cache_signature": 0,
        }
        native_kernel_map.validate_framebuffer_preserved(snapshot, snapshot)
        for field in snapshot:
            hostile = dict(snapshot)
            hostile[field] += 1
            with self.assertRaises(native_kernel_map.KernelMapError):
                native_kernel_map.validate_framebuffer_preserved(snapshot, hostile)


if __name__ == "__main__":
    unittest.main()
