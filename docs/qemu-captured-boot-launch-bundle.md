# QEMU Captured Boot Launch Bundle

Status: draft v0.1

The captured boot launch bundle is an operator-facing handoff artifact for the real QEMU boot path. It reads the shared-folder contract, captured boot preflight, pending or captured boot receipt, and fixture evidence path, then emits the exact command plan for staging inputs, regenerating preflight evidence, launching QEMU, rebuilding evidence from an existing serial log, and emitting the captured-boot receipt.

Emit the bundle:

```powershell
python .\tools\emit_qemu_captured_boot_launch_bundle.py --preflight .\runs\qemu_captured_boot_preflight.json --qemu-shared-folder-contract .\runs\qemu_shared_folder_contract.json --qemu-captured-boot-receipt .\runs\qemu_captured_boot_receipt.json --fixture-evidence .\runs\qemu_boot_evidence.json --release-gate-output .\runs\release_gate.json --out .\runs\qemu_captured_boot_launch_bundle.json
```

`status=pass` means the referenced preflight is launch-ready and the bundle is internally consistent. `status=blocked` means the bundle is valid but one or more launch prerequisites remain blocked, such as a missing image or QEMU executable. `status=fail` means the referenced artifacts disagree or are unsafe to use.

Emit the dry-run checklist from the bundle before a real operator launch:

```powershell
python .\tools\emit_qemu_captured_boot_dry_run_checklist.py --launch-bundle .\runs\qemu_captured_boot_launch_bundle.json --release-gate-output .\runs\release_gate.json --out .\runs\qemu_captured_boot_dry_run_checklist.json
python .\tools\emit_qemu_boot_marker_contract.py --dry-run-checklist .\runs\qemu_captured_boot_dry_run_checklist.json --lab-guest-autostart .\runs\lab_guest_autostart.json --out .\runs\qemu_boot_marker_contract.json
python .\tools\emit_qemu_boot_marker_image_binding.py --marker-contract .\runs\qemu_boot_marker_contract.json --lab-image-manifest .\runs\lab_image_manifest.json --out .\runs\qemu_boot_marker_image_binding.json
python .\tools\emit_rootfs_content_manifest.py --image-binding .\runs\qemu_boot_marker_image_binding.json --image .\output\images\rootfs.ext4 --extracted-rootfs .\runs\rootfs_extracted --out .\runs\rootfs_content_manifest.json
python .\tools\emit_rootfs_extraction_handoff.py --rootfs-content-manifest .\runs\rootfs_content_manifest.json --note-out .\runs\rootfs_extraction_handoff.md --out .\runs\rootfs_extraction_handoff.json
python .\tools\emit_rootfs_extraction_receipt.py --handoff .\runs\rootfs_extraction_handoff.json --rootfs-content-manifest .\runs\rootfs_content_manifest.json --out .\runs\rootfs_extraction_receipt.json
python .\tools\emit_qemu_captured_boot_readiness.py --rootfs-extraction-receipt .\runs\rootfs_extraction_receipt.json --qemu-captured-boot-receipt .\runs\qemu_captured_boot_receipt.json --qemu-captured-boot-evidence .\runs\qemu_boot_evidence.captured.json --out .\runs\qemu_captured_boot_readiness.json
```

## Boundary

This bundle does not launch QEMU, create host files, install packages, or claim boot evidence. It is a deterministic operator command plan. The marker contract adds ownership and kernel-boundary mapping, the image binding hashes the source-side Buildroot inputs, and the rootfs content manifest can compare extracted image contents, but captured boot proof still requires `qemu_boot_evidence.captured.json` from a validated real serial log. Promotion language also requires `qemu_captured_boot_readiness.json`.
