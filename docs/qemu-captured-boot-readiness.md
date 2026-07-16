# QEMU Captured Boot Readiness

Status: draft v0.1

The captured boot readiness artifact reconciles the three proof inputs required before PooleOS can use captured-QEMU promotion language:

- verified rootfs extraction receipt
- captured QEMU boot receipt
- present and valid `qemu_boot_evidence.captured.json`

Emit the readiness artifact:

```powershell
python .\tools\emit_qemu_captured_boot_readiness.py --rootfs-extraction-receipt .\runs\rootfs_extraction_receipt.json --qemu-captured-boot-receipt .\runs\qemu_captured_boot_receipt.json --qemu-captured-boot-evidence .\runs\qemu_boot_evidence.captured.json --out .\runs\qemu_captured_boot_readiness.json
```

`status=blocked` means the artifact is structurally valid but one or more promotion requirements are unmet. This is the expected state before rootfs extraction and real QEMU capture both complete.

`status=ready_for_promotion` means all three proof inputs agree and `promotion_language_allowed=true`.

`status=invalid` means a present source artifact is structurally wrong or contradicts captured-QEMU provenance, such as fixture evidence being passed in the captured slot.

After readiness becomes `ready_for_promotion`, emit the kernel boot handoff:

```powershell
python .\tools\emit_kernel_boot_handoff.py --qemu-captured-boot-readiness .\runs\qemu_captured_boot_readiness.json --qemu-boot-marker-contract .\runs\qemu_boot_marker_contract.json --boot-trap-bundle-manifest .\runs\pooleos_boot_trap_bundle_manifest.json --guest-loader-verification .\runs\boot_trap_bundle_verification.json --out .\runs\kernel_boot_handoff.json
python .\tools\emit_kernel_pgvm2_loader_output.py --kernel-boot-handoff .\runs\kernel_boot_handoff.json --pooleglyph-source-anchor .\runs\pooleglyph_source_anchor.json --parser-kernel-promotion-receipt .\runs\pooleglyph_parser_kernel_promotion_receipt.json --kernel-build-id pending-kernel-loader --out .\runs\kernel_pgvm2_loader_output.json
python .\tools\emit_kernel_pgvm2_loader_evidence.py --kernel-boot-handoff .\runs\kernel_boot_handoff.json --kernel-loader-output .\runs\kernel_pgvm2_loader_output.json --pooleglyph-source-anchor .\runs\pooleglyph_source_anchor.json --parser-kernel-promotion-receipt .\runs\pooleglyph_parser_kernel_promotion_receipt.json --out .\runs\kernel_pgvm2_loader_evidence.json
```

## Boundary

This artifact does not run QEMU, mount a rootfs, or create boot evidence. It only decides whether existing proof artifacts are strong enough to permit captured-QEMU promotion language. Kernel enforcement and production readiness still require later kernel-owned loader and isolation evidence, beginning with `kernel_boot_handoff.json` and `kernel_pgvm2_loader_evidence.json`.
