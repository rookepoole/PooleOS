# QEMU Boot Evidence

Status: draft v0.1

QEMU boot evidence wraps the boot-log validator with provenance. This lets the release gate distinguish two useful but different facts:

- `fixture`: the trap-input marker contract is covered by a checked-in serial-log fixture.
- `captured_qemu_serial`: a QEMU serial log was captured from a boot attempt and passed the same trap-input validation.

The fixture lives at:

```text
lab-os/qemu/fixtures/trap-input-success.serial.log
```

Emit fixture evidence:

```powershell
python .\tools\emit_qemu_boot_evidence.py --source fixture --out .\runs\qemu_boot_evidence.json
```

Emit captured serial evidence after a QEMU boot:

```powershell
python .\tools\emit_qemu_boot_evidence.py --log .\runs\pooleos-lab-serial.log --source captured_qemu_serial --out .\runs\qemu_boot_evidence.captured.json
```

The Lab launcher can perform the same captured-evidence flow after QEMU exits:

```powershell
python .\tools\emit_qemu_captured_boot_preflight.py --image .\output\images\rootfs.ext4 --shared-output .\runs\qemu_shared --serial-log .\runs\pooleos-lab-serial.log --boot-validation-output .\runs\boot_log_validation.captured.json --qemu-boot-evidence-output .\runs\qemu_boot_evidence.captured.json --qemu-captured-boot-receipt-output .\runs\qemu_captured_boot_receipt.json --out .\runs\qemu_captured_boot_preflight.json
python .\tools\emit_qemu_captured_boot_receipt.py --fixture-evidence .\runs\qemu_boot_evidence.json --captured-evidence .\runs\qemu_boot_evidence.captured.json --out .\runs\qemu_captured_boot_receipt.json
python .\tools\emit_qemu_captured_boot_launch_bundle.py --preflight .\runs\qemu_captured_boot_preflight.json --qemu-shared-folder-contract .\runs\qemu_shared_folder_contract.json --qemu-captured-boot-receipt .\runs\qemu_captured_boot_receipt.json --fixture-evidence .\runs\qemu_boot_evidence.json --release-gate-output .\runs\release_gate.json --out .\runs\qemu_captured_boot_launch_bundle.json
python .\tools\emit_qemu_captured_boot_dry_run_checklist.py --launch-bundle .\runs\qemu_captured_boot_launch_bundle.json --release-gate-output .\runs\release_gate.json --out .\runs\qemu_captured_boot_dry_run_checklist.json
python .\tools\emit_qemu_boot_marker_contract.py --dry-run-checklist .\runs\qemu_captured_boot_dry_run_checklist.json --lab-guest-autostart .\runs\lab_guest_autostart.json --out .\runs\qemu_boot_marker_contract.json
python .\tools\emit_qemu_boot_marker_image_binding.py --marker-contract .\runs\qemu_boot_marker_contract.json --lab-image-manifest .\runs\lab_image_manifest.json --out .\runs\qemu_boot_marker_image_binding.json
python .\tools\emit_rootfs_content_manifest.py --image-binding .\runs\qemu_boot_marker_image_binding.json --image .\output\images\rootfs.ext4 --extracted-rootfs .\runs\rootfs_extracted --out .\runs\rootfs_content_manifest.json
python .\tools\emit_rootfs_extraction_handoff.py --rootfs-content-manifest .\runs\rootfs_content_manifest.json --note-out .\runs\rootfs_extraction_handoff.md --out .\runs\rootfs_extraction_handoff.json
python .\tools\emit_rootfs_extraction_receipt.py --handoff .\runs\rootfs_extraction_handoff.json --rootfs-content-manifest .\runs\rootfs_content_manifest.json --out .\runs\rootfs_extraction_receipt.json
.\lab-os\qemu\scripts\run-pooleos-lab.ps1 -ImagePath .\output\images\rootfs.ext4 -SerialLog .\runs\pooleos-lab-serial.log -BootValidationOutput .\runs\boot_log_validation.captured.json -QemuBootEvidenceOutput .\runs\qemu_boot_evidence.captured.json
python .\tools\emit_qemu_captured_boot_receipt.py --fixture-evidence .\runs\qemu_boot_evidence.json --captured-evidence .\runs\qemu_boot_evidence.captured.json --operator-executed --out .\runs\qemu_captured_boot_receipt.json
python .\tools\emit_qemu_captured_boot_readiness.py --rootfs-extraction-receipt .\runs\rootfs_extraction_receipt.json --qemu-captured-boot-receipt .\runs\qemu_captured_boot_receipt.json --qemu-captured-boot-evidence .\runs\qemu_boot_evidence.captured.json --out .\runs\qemu_captured_boot_readiness.json
python .\tools\emit_kernel_boot_handoff.py --qemu-captured-boot-readiness .\runs\qemu_captured_boot_readiness.json --qemu-boot-marker-contract .\runs\qemu_boot_marker_contract.json --boot-trap-bundle-manifest .\runs\pooleos_boot_trap_bundle_manifest.json --guest-loader-verification .\runs\boot_trap_bundle_verification.json --out .\runs\kernel_boot_handoff.json
python .\tools\emit_kernel_pgvm2_loader_output.py --kernel-boot-handoff .\runs\kernel_boot_handoff.json --pooleglyph-source-anchor .\runs\pooleglyph_source_anchor.json --parser-kernel-promotion-receipt .\runs\pooleglyph_parser_kernel_promotion_receipt.json --kernel-build-id pending-kernel-loader --out .\runs\kernel_pgvm2_loader_output.json
python .\tools\emit_kernel_pgvm2_loader_evidence.py --kernel-boot-handoff .\runs\kernel_boot_handoff.json --kernel-loader-output .\runs\kernel_pgvm2_loader_output.json --pooleglyph-source-anchor .\runs\pooleglyph_source_anchor.json --parser-kernel-promotion-receipt .\runs\pooleglyph_parser_kernel_promotion_receipt.json --out .\runs\kernel_pgvm2_loader_evidence.json
```

To process an existing serial log without launching QEMU:

```powershell
.\lab-os\qemu\scripts\run-pooleos-lab.ps1 -EmitCapturedEvidenceOnly -SerialLog .\runs\pooleos-lab-serial.log -BootValidationOutput .\runs\boot_log_validation.captured.json -QemuBootEvidenceOutput .\runs\qemu_boot_evidence.captured.json
```

The release gate accepts fixture evidence as regression proof only when `boot_evidence_claimed=false`. It accepts captured evidence as boot evidence only when the embedded boot-log validation passes and `boot_evidence_claimed=true`.

Keep the release slots separate:

```powershell
python .\tools\emit_qemu_captured_boot_receipt.py --fixture-evidence .\runs\qemu_boot_evidence.json --captured-evidence .\runs\qemu_boot_evidence.captured.json --out .\runs\qemu_captured_boot_receipt.json
python .\tools\emit_qemu_captured_boot_launch_bundle.py --preflight .\runs\qemu_captured_boot_preflight.json --qemu-shared-folder-contract .\runs\qemu_shared_folder_contract.json --qemu-captured-boot-receipt .\runs\qemu_captured_boot_receipt.json --fixture-evidence .\runs\qemu_boot_evidence.json --release-gate-output .\runs\release_gate.json --out .\runs\qemu_captured_boot_launch_bundle.json
python .\tools\emit_qemu_captured_boot_dry_run_checklist.py --launch-bundle .\runs\qemu_captured_boot_launch_bundle.json --release-gate-output .\runs\release_gate.json --out .\runs\qemu_captured_boot_dry_run_checklist.json
python .\tools\emit_qemu_boot_marker_contract.py --dry-run-checklist .\runs\qemu_captured_boot_dry_run_checklist.json --lab-guest-autostart .\runs\lab_guest_autostart.json --out .\runs\qemu_boot_marker_contract.json
python .\tools\emit_qemu_boot_marker_image_binding.py --marker-contract .\runs\qemu_boot_marker_contract.json --lab-image-manifest .\runs\lab_image_manifest.json --out .\runs\qemu_boot_marker_image_binding.json
python .\tools\emit_rootfs_content_manifest.py --image-binding .\runs\qemu_boot_marker_image_binding.json --image .\output\images\rootfs.ext4 --extracted-rootfs .\runs\rootfs_extracted --out .\runs\rootfs_content_manifest.json
python .\tools\emit_rootfs_extraction_handoff.py --rootfs-content-manifest .\runs\rootfs_content_manifest.json --note-out .\runs\rootfs_extraction_handoff.md --out .\runs\rootfs_extraction_handoff.json
python .\tools\emit_rootfs_extraction_receipt.py --handoff .\runs\rootfs_extraction_handoff.json --rootfs-content-manifest .\runs\rootfs_content_manifest.json --out .\runs\rootfs_extraction_receipt.json
python .\tools\emit_qemu_captured_boot_readiness.py --rootfs-extraction-receipt .\runs\rootfs_extraction_receipt.json --qemu-captured-boot-receipt .\runs\qemu_captured_boot_receipt.json --qemu-captured-boot-evidence .\runs\qemu_boot_evidence.captured.json --out .\runs\qemu_captured_boot_readiness.json
python .\tools\emit_kernel_boot_handoff.py --qemu-captured-boot-readiness .\runs\qemu_captured_boot_readiness.json --qemu-boot-marker-contract .\runs\qemu_boot_marker_contract.json --boot-trap-bundle-manifest .\runs\pooleos_boot_trap_bundle_manifest.json --guest-loader-verification .\runs\boot_trap_bundle_verification.json --out .\runs\kernel_boot_handoff.json
python .\tools\emit_kernel_pgvm2_loader_output.py --kernel-boot-handoff .\runs\kernel_boot_handoff.json --pooleglyph-source-anchor .\runs\pooleglyph_source_anchor.json --parser-kernel-promotion-receipt .\runs\pooleglyph_parser_kernel_promotion_receipt.json --kernel-build-id pending-kernel-loader --out .\runs\kernel_pgvm2_loader_output.json
python .\tools\emit_kernel_pgvm2_loader_evidence.py --kernel-boot-handoff .\runs\kernel_boot_handoff.json --kernel-loader-output .\runs\kernel_pgvm2_loader_output.json --pooleglyph-source-anchor .\runs\pooleglyph_source_anchor.json --parser-kernel-promotion-receipt .\runs\pooleglyph_parser_kernel_promotion_receipt.json --out .\runs\kernel_pgvm2_loader_evidence.json
```

Add `--qemu-captured-boot-preflight`, `--qemu-captured-boot-launch-bundle`, `--qemu-captured-boot-dry-run-checklist`, `--qemu-boot-marker-contract`, `--qemu-boot-marker-image-binding`, `--rootfs-content-manifest`, `--rootfs-extraction-handoff`, `--rootfs-extraction-receipt`, `--qemu-captured-boot-receipt`, `--qemu-captured-boot-readiness`, `--kernel-boot-handoff`, `--kernel-pgvm2-loader-output`, and `--kernel-pgvm2-loader-evidence` to the full release-gate command. The dry-run checklist records the launch/checklist arguments, the marker contract records the serial marker ownership boundary, the image binding hashes the source files that should land in the Buildroot image, the rootfs content manifest compares those hashes against extracted rootfs contents when available, the extraction handoff emits the reviewed WSL/Linux command plan, the extraction receipt blocks captured-QEMU promotion until continuity is verified, the readiness artifact permits promotion language only when rootfs and captured boot evidence agree, the kernel handoff connects that readiness to guest loader output without claiming kernel or PGVM2 enforcement, the loader output fixture reserves the booted-kernel output slot without claiming enforcement, and the PGVM2 loader evidence records the kernel-owned checks that a future booted kernel output must satisfy.

After a real capture exists, also add `--qemu-captured-boot-evidence .\runs\qemu_boot_evidence.captured.json` to the full release-gate command.

## Boundary

This artifact proves marker-level execution evidence only. The downstream kernel handoff and PGVM2 loader evidence keep that proof separate from future booted kernel loader evidence. None of these artifacts proves production readiness, hardware support, security isolation, or full kernel enforcement.
