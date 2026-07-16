import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


OVERLAY = ROOT / "lab-os" / "buildroot" / "external" / "board" / "pooleos_lab" / "rootfs_overlay"
CONTRACT = OVERLAY / "usr" / "bin" / "pooleos-kernel-pgvm2-transcript-contract"
SMOKE = OVERLAY / "usr" / "bin" / "pooleos-lab-smoke"
INIT = OVERLAY / "etc" / "init.d" / "S99pooleos-lab"


class KernelPgvm2TranscriptContractOverlayTests(unittest.TestCase):
    def test_contract_script_exists_and_contains_required_verifier_markers(self) -> None:
        text = CONTRACT.read_text(encoding="utf-8")
        required = [
            "POOLEOS_KERNEL_BUILD_ID",
            "POOLEOS_KERNEL_HANDOFF_SHA256",
            "POOLEOS_KERNEL_GUEST_ENV POOLEOS_POOLEGLYPH_SOURCE_ANCHOR_SHA256",
            "POOLEOS_KERNEL_GUEST_ENV POOLEOS_POOLEGLYPH_PARSER_PROMOTION_RECEIPT_SHA256",
            "POOLEOS_POOLEGLYPH_SOURCE_ANCHOR_SHA256",
            "POOLEOS_POOLEGLYPH_PARSER_PROMOTION_RECEIPT_SHA256",
            "POOLEOS_KERNEL_BOOTED_PATH",
            "POOLEOS_KERNEL_ENFORCEMENT_CLAIM",
            "POOLEOS_PGVM2_EXECUTION_CLAIM",
            "POOLEOS_KERNEL_EXPECTED_INSTRUCTIONS",
            "POOLEOS_KERNEL_ACTUAL_INSTRUCTIONS",
            "POOLEOS_KERNEL_CHECK handoff_digest_lock",
            "POOLEOS_KERNEL_CHECK trap_bundle_signature_verify",
            "POOLEOS_KERNEL_CHECK pgvm2_bytecode_decode",
            "POOLEOS_KERNEL_CHECK capability_table_install",
            "POOLEOS_KERNEL_CHECK memory_isolation_map",
            "POOLEOS_KERNEL_CHECK trap_instruction_execution",
            "POOLEOS_KERNEL_CHECK serial_evidence_bind",
            "POOLEOS_KERNEL_CHECK pooleglyph_source_anchor_digest_bind",
            "POOLEOS_KERNEL_CHECK parser_promotion_receipt_digest_bind",
            "POOLEOS_KERNEL_CHECK parser_promotion_receipt_bind",
            "POOLEOS_KERNEL_CHECK negative_claim_guard",
        ]
        self.assertTrue(CONTRACT.exists())
        for marker in required:
            self.assertIn(marker, text)

    def test_contract_defaults_to_disabled_non_claiming_output(self) -> None:
        text = CONTRACT.read_text(encoding="utf-8")
        disabled_block = text.split('if [ "$ENABLE" != "1" ]; then', 1)[1].split("exit 0", 1)[0]
        self.assertIn("POOLEOS_KERNEL_TRANSCRIPT_DISABLED", disabled_block)
        self.assertIn("POOLEOS_KERNEL_BOOTED_PATH false", disabled_block)
        self.assertIn("POOLEOS_KERNEL_ENFORCEMENT_CLAIM false", disabled_block)
        self.assertIn("POOLEOS_PGVM2_EXECUTION_CLAIM false", disabled_block)
        self.assertIn("POOLEOS_KERNEL_CHECK pooleglyph_source_anchor_digest_bind FAIL", disabled_block)
        self.assertIn("POOLEOS_KERNEL_CHECK parser_promotion_receipt_digest_bind FAIL", disabled_block)
        self.assertIn("POOLEOS_KERNEL_CHECK negative_claim_guard PASS", disabled_block)

    def test_contract_not_called_by_autostart_or_smoke_until_real_loader_exists(self) -> None:
        contract_name = "pooleos-kernel-pgvm2-transcript-contract"
        self.assertNotIn(contract_name, SMOKE.read_text(encoding="utf-8"))
        self.assertNotIn(contract_name, INIT.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
