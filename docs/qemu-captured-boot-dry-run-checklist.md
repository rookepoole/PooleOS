# QEMU Captured Boot Dry-Run Checklist

Status: draft v0.1

The captured boot dry-run checklist expands the operator launch bundle into a receipt template for the real QEMU boot path. It records preflight blockers, the command sequence, expected trap-input serial markers, post-capture files, and release-gate arguments.

Emit the checklist:

```powershell
python .\tools\emit_qemu_captured_boot_dry_run_checklist.py --launch-bundle .\runs\qemu_captured_boot_launch_bundle.json --release-gate-output .\runs\release_gate.json --out .\runs\qemu_captured_boot_dry_run_checklist.json
python .\tools\emit_qemu_boot_marker_contract.py --dry-run-checklist .\runs\qemu_captured_boot_dry_run_checklist.json --lab-guest-autostart .\runs\lab_guest_autostart.json --out .\runs\qemu_boot_marker_contract.json
python .\tools\emit_qemu_boot_marker_image_binding.py --marker-contract .\runs\qemu_boot_marker_contract.json --lab-image-manifest .\runs\lab_image_manifest.json --out .\runs\qemu_boot_marker_image_binding.json
python .\tools\emit_rootfs_content_manifest.py --image-binding .\runs\qemu_boot_marker_image_binding.json --image .\output\images\rootfs.ext4 --extracted-rootfs .\runs\rootfs_extracted --out .\runs\rootfs_content_manifest.json
python .\tools\emit_rootfs_extraction_handoff.py --rootfs-content-manifest .\runs\rootfs_content_manifest.json --note-out .\runs\rootfs_extraction_handoff.md --out .\runs\rootfs_extraction_handoff.json
python .\tools\emit_rootfs_extraction_receipt.py --handoff .\runs\rootfs_extraction_handoff.json --rootfs-content-manifest .\runs\rootfs_content_manifest.json --out .\runs\rootfs_extraction_receipt.json
python .\tools\emit_qemu_captured_boot_readiness.py --rootfs-extraction-receipt .\runs\rootfs_extraction_receipt.json --qemu-captured-boot-receipt .\runs\qemu_captured_boot_receipt.json --qemu-captured-boot-evidence .\runs\qemu_boot_evidence.captured.json --out .\runs\qemu_captured_boot_readiness.json
```

`status=pass` means the dry-run checklist is internally consistent and the source launch bundle is ready. `status=blocked` means the checklist is valid but the source launch bundle or captured preflight still has blockers. `status=fail` means the source bundle, preflight, command plan, expected outputs, or release-gate reconciliation are inconsistent.

## Boundary

This artifact is a dry run and receipt template. It does not launch QEMU, create files, install packages, or claim captured boot evidence. The operator receipt fields remain unchecked until a human runs the command plan and records the results.

The marker contract consumes this checklist and the Lab guest autostart artifact to map every expected serial marker to the guest script and PooleOS kernel/PGVM2 boundary that owns the eventual enforcement claim. The marker image binding then hashes the corresponding Buildroot overlay and BR2 external files before any rootfs build or boot claim is made. The rootfs content manifest compares those hashes against extracted rootfs files after an image exists, and the captured boot readiness artifact reconciles rootfs continuity with captured boot evidence before promotion language is allowed.
