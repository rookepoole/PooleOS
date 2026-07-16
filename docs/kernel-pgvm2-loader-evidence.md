# Kernel PGVM2 Loader Evidence

Status: draft v0.1

Kernel PGVM2 loader evidence consumes `kernel_boot_handoff.json` and turns the handoff into an explicit kernel-owned checklist. It does not execute a kernel loader by itself.

Emit the non-claiming output fixture, then the evidence stub:

```powershell
python .\tools\emit_kernel_pgvm2_loader_output.py --kernel-boot-handoff .\runs\kernel_boot_handoff.json --pooleglyph-source-anchor .\runs\pooleglyph_source_anchor.json --parser-kernel-promotion-receipt .\runs\pooleglyph_parser_kernel_promotion_receipt.json --kernel-build-id pending-kernel-loader --out .\runs\kernel_pgvm2_loader_output.json
python .\tools\emit_kernel_pgvm2_loader_evidence.py --kernel-boot-handoff .\runs\kernel_boot_handoff.json --kernel-loader-output .\runs\kernel_pgvm2_loader_output.json --pooleglyph-source-anchor .\runs\pooleglyph_source_anchor.json --parser-kernel-promotion-receipt .\runs\pooleglyph_parser_kernel_promotion_receipt.json --out .\runs\kernel_pgvm2_loader_evidence.json
```

When a booted-kernel transcript exists, replace the fixture command with:

```powershell
python .\tools\verify_kernel_pgvm2_loader_transcript.py --kernel-boot-handoff .\runs\kernel_boot_handoff.json --transcript .\runs\kernel_pgvm2_loader.transcript.txt --pooleglyph-source-anchor .\runs\pooleglyph_source_anchor.json --parser-kernel-promotion-receipt .\runs\pooleglyph_parser_kernel_promotion_receipt.json --out .\runs\kernel_pgvm2_loader_output.json
python .\tools\emit_lab_kernel_transcript_export_receipt.py --out .\runs\lab_kernel_transcript_export_receipt.json
```

`status=blocked` means the handoff is not ready or required source evidence is missing.

`status=ready_for_kernel_loader` means the handoff is ready and the planned kernel checks are recorded, but no booted kernel loader output has satisfied them yet. In this state `kernel_enforcement_claimed=false`, `pgvm2_execution_claimed=false`, and `booted_kernel_path_claimed=false`.

`status=kernel_enforced` is reserved for a future booted kernel output with artifact kind `pooleos.kernel_pgvm2_loader_output`. That output must bind to `source_handoff_sha256`, `pooleglyph_source_anchor_sha256`, and `pooleglyph_parser_kernel_promotion_receipt_sha256`, claim a booted kernel path, match the expected trap execution count, satisfy every planned kernel check, and be paired with `pooleglyph_parser_kernel_promotion_receipt.json` at `status=parser_to_kernel_ready`.

`status=invalid` means a present source artifact has the wrong kind, a loader output digest does not match the handoff/source-anchor/promotion receipt, or a loader output tries to claim enforcement without satisfying the booted-kernel requirements.

## Planned Kernel Checks

- `handoff_digest_lock`: verify the loader input bytes match `source_handoff_sha256`.
- `trap_bundle_signature_verify`: verify the PGB2 bundle, replay proof, signed metrics, and trap sections.
- `pgvm2_bytecode_decode`: decode the trap byte stream with the frozen PGVM2 kernel ABI decoder.
- `capability_table_install`: install a closed-by-default capability table before PGVM2 execution.
- `memory_isolation_map`: map PGVM2 regions into isolated kernel-owned ranges.
- `trap_instruction_execution`: execute exactly the handoff's expected trap instruction count.
- `serial_evidence_bind`: bind serial evidence, handoff digest, and kernel build id in the booted output.
- `pooleglyph_source_anchor_digest_bind`: bind the booted transcript to the PooleGlyph source anchor used by the release gate.
- `parser_promotion_receipt_digest_bind`: bind the booted transcript to the PooleGlyph parser promotion receipt used by the release gate.
- `parser_promotion_receipt_bind`: require a parser-to-kernel promotion receipt before parser-backed PGVM2 enforcement.
- `negative_claim_guard`: keep enforcement claims false if any required kernel check fails.

## Boundary

This artifact is a kernel loader contract and release-gate input, not production security proof. Enforcement claims remain false until a booted kernel path emits `kernel_pgvm2_loader_output.json` and all planned checks pass.

The lab transcript export receipt is a separate release-gate input. It records transcript export continuity, hash-binds the exact verifier output, and requires the guest contract's source-anchor/parser-promotion environment digest pair to match the host verifier before a recorded run is accepted.
