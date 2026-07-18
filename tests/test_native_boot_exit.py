from __future__ import annotations

import unittest

from runtime import native_boot_exit


def final_map(key: int = 0) -> dict[str, int]:
    return {
        "map_key": key,
        "map_bytes": 48 * 96,
        "descriptor_size": 48,
        "descriptor_version": 1,
    }


def handoff() -> dict[str, object]:
    return {
        "byte_count": 4248,
        "boot_services_exited": True,
        "development_mode": True,
        "stack_top_virtual": 0xFFFF_FFFF_8003_9000,
        "page_table_root_physical": 0x0300_0000,
        "kernel_signature_verified": False,
        "kernel_entry_profile_valid": False,
    }


def attempt(key: int, result: str) -> list[dict[str, object]]:
    return [
        {"operation": "get_memory_map", "map": final_map(key)},
        {"operation": "finalize_handoff", "handoff": handoff()},
        {"operation": "exit_boot_services", "result": result},
    ]


class NativeBootExitTests(unittest.TestCase):
    def test_accepts_one_exact_success_attempt_and_zero_map_key(self) -> None:
        summary = native_boot_exit.validate_trace(attempt(0, "success"))
        self.assertEqual(summary["attempt_count"], 1)
        self.assertFalse(summary["transfer_allowed"])

    def test_accepts_bounded_stale_key_retries_with_fresh_maps(self) -> None:
        trace = attempt(1, "invalid_parameter") + attempt(2, "success")
        self.assertEqual(native_boot_exit.validate_trace(trace)["attempt_count"], 2)

    def test_rejects_retry_exhaustion_and_non_retryable_status(self) -> None:
        with self.assertRaises(native_boot_exit.BootExitError):
            native_boot_exit.validate_trace(
                sum((attempt(index, "invalid_parameter") for index in range(4)), [])
            )
        invalid = attempt(1, "success")
        invalid[-1]["result"] = "device_error"
        with self.assertRaises(native_boot_exit.BootExitError):
            native_boot_exit.validate_trace(invalid)

    def test_rejects_post_exit_firmware_or_transfer_activity(self) -> None:
        trace = attempt(1, "success") + [{"operation": "get_memory_map", "map": final_map(2)}]
        with self.assertRaises(native_boot_exit.BootExitError):
            native_boot_exit.validate_trace(trace)

    def test_rejects_map_handoff_and_order_faults(self) -> None:
        invalid_map = attempt(1, "success")
        invalid_map[0]["map"]["descriptor_size"] = 41
        with self.assertRaises(native_boot_exit.BootExitError):
            native_boot_exit.validate_trace(invalid_map)
        invalid_handoff = attempt(1, "success")
        invalid_handoff[1]["handoff"]["stack_top_virtual"] = 0
        with self.assertRaises(native_boot_exit.BootExitError):
            native_boot_exit.validate_trace(invalid_handoff)
        with self.assertRaises(native_boot_exit.BootExitError):
            native_boot_exit.validate_trace(list(reversed(attempt(1, "success"))))

    def test_validates_exact_live_boundary_markers(self) -> None:
        summary = native_boot_exit.validate_live_markers(
            "POOLEBOOT/0.1 EXIT_BOOT_SERVICES PASS contract=PBEXIT1 attempts=1 map_bytes=4608 descriptor_bytes=48 descriptors=96",
            "POOLEBOOT/0.1 FIRMWARE_BOUNDARY PASS calls_after_exit=0 kernel_pages=48 table_pages=4 stack_pages=8 handoff_pages=256",
            native_boot_exit.DEVELOPMENT_BOUNDARY,
            native_boot_exit.STOP_MARKER,
        )
        self.assertTrue(summary["stopped_before_transfer"])
        with self.assertRaises(native_boot_exit.BootExitError):
            native_boot_exit.validate_live_markers(
                "POOLEBOOT/0.1 EXIT_BOOT_SERVICES PASS contract=PBEXIT1 attempts=1 map_bytes=4608 descriptor_bytes=48 descriptors=96",
                "POOLEBOOT/0.1 FIRMWARE_BOUNDARY PASS calls_after_exit=1 kernel_pages=48 table_pages=4 stack_pages=8 handoff_pages=256",
                native_boot_exit.DEVELOPMENT_BOUNDARY,
                native_boot_exit.STOP_MARKER,
            )


if __name__ == "__main__":
    unittest.main()
