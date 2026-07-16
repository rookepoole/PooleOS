# Kernel Boot Handoff

Status: draft v0.1

The kernel boot handoff ties captured serial readiness to the guest loader output slot that a future PooleOS kernel or PGVM2 loader must consume. It keeps marker-level proof separate from kernel enforcement proof.

Emit the handoff:

```powershell
python .\tools\emit_kernel_boot_handoff.py --qemu-captured-boot-readiness .\runs\qemu_captured_boot_readiness.json --qemu-boot-marker-contract .\runs\qemu_boot_marker_contract.json --boot-trap-bundle-manifest .\runs\pooleos_boot_trap_bundle_manifest.json --guest-loader-verification .\runs\boot_trap_bundle_verification.json --out .\runs\kernel_boot_handoff.json
```

Then emit the PGVM2 loader evidence stub:

```powershell
python .\tools\emit_kernel_pgvm2_loader_output.py --kernel-boot-handoff .\runs\kernel_boot_handoff.json --pooleglyph-source-anchor .\runs\pooleglyph_source_anchor.json --parser-kernel-promotion-receipt .\runs\pooleglyph_parser_kernel_promotion_receipt.json --kernel-build-id pending-kernel-loader --out .\runs\kernel_pgvm2_loader_output.json
python .\tools\emit_lab_kernel_transcript_export_receipt.py --out .\runs\lab_kernel_transcript_export_receipt.json
python .\tools\emit_kernel_pgvm2_loader_evidence.py --kernel-boot-handoff .\runs\kernel_boot_handoff.json --kernel-loader-output .\runs\kernel_pgvm2_loader_output.json --pooleglyph-source-anchor .\runs\pooleglyph_source_anchor.json --parser-kernel-promotion-receipt .\runs\pooleglyph_parser_kernel_promotion_receipt.json --out .\runs\kernel_pgvm2_loader_evidence.json
```

`status=blocked` means the artifact is structurally valid but captured readiness, marker contract readiness, or guest loader output is missing.

`status=ready_for_kernel_handoff` means captured readiness is ready, the marker contract is passing, the boot trap bundle manifest is passing, and `boot_trap_bundle_verification.json` is present and agrees with the expected trap execution count.

`status=invalid` means a present source artifact has the wrong kind or a source tries to claim a kernel/PGVM2 boundary too early.

## Boundary

This artifact does not execute a kernel loader. `kernel_boundary_claimed=false` and `pgvm2_execution_claimed=false` remain hard requirements. A ready handoff is input to kernel-owned PGVM2 loader evidence, not production security proof.

`lab_kernel_transcript_export_receipt.json` remains pending until the lab transcript contract is actually run. It is included beside the loader output so release gates can distinguish a reserved transcript slot from a verified contract export whose guest PooleGlyph digest pair, transcript hash, and verifier artifact all agree.
