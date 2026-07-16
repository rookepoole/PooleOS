# Kernel PGVM2 Loader Transcript Verifier

Status: draft v0.1

The transcript verifier consumes a booted-kernel transcript or serial-export file and emits `kernel_pgvm2_loader_output.json`. It promotes to `status=pass` only when the transcript proves the handoff digest, PooleGlyph source anchor digest, parser promotion receipt digest, kernel build id, booted path, PGVM2 execution claim, instruction counts, and every kernel check.

Verify a transcript:

```powershell
python .\tools\verify_kernel_pgvm2_loader_transcript.py --kernel-boot-handoff .\runs\kernel_boot_handoff.json --transcript .\runs\kernel_pgvm2_loader.transcript.txt --pooleglyph-source-anchor .\runs\pooleglyph_source_anchor.json --parser-kernel-promotion-receipt .\runs\pooleglyph_parser_kernel_promotion_receipt.json --out .\runs\kernel_pgvm2_loader_output.json
```

Required transcript markers:

```text
POOLEOS_KERNEL_BUILD_ID <build-id>
POOLEOS_KERNEL_HANDOFF_SHA256 <sha256>
POOLEOS_POOLEGLYPH_SOURCE_ANCHOR_SHA256 <sha256>
POOLEOS_POOLEGLYPH_PARSER_PROMOTION_RECEIPT_SHA256 <sha256>
POOLEOS_KERNEL_BOOTED_PATH true
POOLEOS_KERNEL_ENFORCEMENT_CLAIM true
POOLEOS_PGVM2_EXECUTION_CLAIM true
POOLEOS_KERNEL_EXPECTED_INSTRUCTIONS <count>
POOLEOS_KERNEL_ACTUAL_INSTRUCTIONS <count>
POOLEOS_KERNEL_CHECK handoff_digest_lock PASS
POOLEOS_KERNEL_CHECK trap_bundle_signature_verify PASS
POOLEOS_KERNEL_CHECK pgvm2_bytecode_decode PASS
POOLEOS_KERNEL_CHECK capability_table_install PASS
POOLEOS_KERNEL_CHECK memory_isolation_map PASS
POOLEOS_KERNEL_CHECK trap_instruction_execution PASS
POOLEOS_KERNEL_CHECK serial_evidence_bind PASS
POOLEOS_KERNEL_CHECK pooleglyph_source_anchor_digest_bind PASS
POOLEOS_KERNEL_CHECK parser_promotion_receipt_digest_bind PASS
POOLEOS_KERNEL_CHECK parser_promotion_receipt_bind PASS
POOLEOS_KERNEL_CHECK negative_claim_guard PASS
```

The lab shell contract also emits two receipt-only audit markers. The loader verifier ignores these lines, while `lab_kernel_transcript_export_receipt.json` requires each exactly once for a recorded run:

```text
POOLEOS_KERNEL_GUEST_ENV POOLEOS_POOLEGLYPH_SOURCE_ANCHOR_SHA256 <sha256>
POOLEOS_KERNEL_GUEST_ENV POOLEOS_POOLEGLYPH_PARSER_PROMOTION_RECEIPT_SHA256 <sha256>
```

If the transcript is incomplete and does not claim enforcement, the output remains `status=blocked` with `kernel_enforcement_claimed=false`.

If the transcript claims enforcement before all required evidence is present, the output becomes `status=invalid` and still keeps `kernel_enforcement_claimed=false`.

After producing `kernel_pgvm2_loader_output.json`, emit the lab transcript export receipt:

```powershell
python .\tools\emit_lab_kernel_transcript_export_receipt.py --out .\runs\lab_kernel_transcript_export_receipt.json
```

Use `--contract-run-recorded --contract-mode disabled` only after a real operator/lab path ran the contract in disabled mode. Use `--contract-run-recorded --contract-mode enabled` only after a booted kernel path produced a complete passing transcript. Both recorded modes require the exact guest digest pair, transcript digest, and verifier-output digest to remain mutually bound.

## Boundary

This verifier does not boot the kernel. It only converts a transcript into a loader-output artifact when the transcript is complete and self-consistent.
