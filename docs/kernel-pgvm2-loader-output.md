# Kernel PGVM2 Loader Output

Status: draft v0.1

Kernel PGVM2 loader output is the file shape that a future booted PooleOS kernel loader must emit before any PGVM2 enforcement claim is allowed. The current tool emits a non-claiming negative fixture so release packages can carry the output slot without pretending a kernel has run.

Emit the negative fixture:

```powershell
python .\tools\emit_kernel_pgvm2_loader_output.py --kernel-boot-handoff .\runs\kernel_boot_handoff.json --pooleglyph-source-anchor .\runs\pooleglyph_source_anchor.json --parser-kernel-promotion-receipt .\runs\pooleglyph_parser_kernel_promotion_receipt.json --kernel-build-id pending-kernel-loader --out .\runs\kernel_pgvm2_loader_output.json
```

When a booted-kernel transcript exists, verify it instead:

```powershell
python .\tools\verify_kernel_pgvm2_loader_transcript.py --kernel-boot-handoff .\runs\kernel_boot_handoff.json --transcript .\runs\kernel_pgvm2_loader.transcript.txt --pooleglyph-source-anchor .\runs\pooleglyph_source_anchor.json --parser-kernel-promotion-receipt .\runs\pooleglyph_parser_kernel_promotion_receipt.json --out .\runs\kernel_pgvm2_loader_output.json
python .\tools\emit_lab_kernel_transcript_export_receipt.py --out .\runs\lab_kernel_transcript_export_receipt.json
```

`status=blocked` means the output is present only as a claim guard. It binds to `source_handoff_sha256`, `pooleglyph_source_anchor_sha256`, and `pooleglyph_parser_kernel_promotion_receipt_sha256`, records all kernel checks, keeps `booted_kernel_path=false`, and keeps `kernel_enforcement_claimed=false`.

`status=pass` is reserved for a booted kernel path or a complete verifier transcript. It must set `booted_kernel_path=true`, bind to the handoff digest, PooleGlyph source anchor digest, and parser promotion receipt digest, satisfy every kernel check, match expected and actual instruction counts, and only then set `kernel_enforcement_claimed=true`.

## Claim Guard

The negative fixture is useful because it makes the future output slot explicit while proving the current package refuses enforcement language. A release gate can accept the blocked fixture only when `negative_claim_guard_held=true`, `enforcement_claim_allowed=false`, and both PGVM2/kernel enforcement claims are false.

`lab_kernel_transcript_export_receipt.json` records whether the lab-side transcript contract was actually run. A pending receipt is acceptable only because it is non-claiming; disabled and enabled receipts require a recorded contract run, an exact guest source-anchor/parser-promotion digest pair, a transcript hash that matches the verifier input, and an unchanged verifier-output artifact.

## Boundary

This file is not boot evidence unless a real kernel path emits it. The default fixture is a verifier and schema anchor, not production security proof.
