# PooleOS Lab Boot Log Contract

Status: draft v0.1

The QEMU serial log is the first boot evidence source for PooleOS Lab.

The first boot-smoke script must emit these markers:

```text
POOLEOS_LAB_BOOT_START
POOLEOS_LAB_DOCTOR_PASS
POOLEOS_LAB_RELEASE_GATE_PASS
POOLEOS_LAB_ARTIFACT_EXPORT_PASS
POOLEOS_LAB_BOOT_DONE
```

The markers are deliberately plain ASCII so they survive serial logs, CI consoles, and low-feature init environments.

When trap-bearing QEMU shared-folder inputs are expected, validate the serial log with profile `trap-input`. That profile also requires:

```text
POOLEOS_LAB_AUTOSTART_START
POOLEOS_LAB_SHARED_MOUNT_PASS
POOLEOS_LAB_INPUT_VERIFY_PASS
POOLEOS_LAB_TRAP_ABI_BOUNDARY_PASS
POOLEOS_LAB_AUTOSTART_DONE
```

Use:

```powershell
python .\tools\validate_boot_log.py .\runs\pooleos-lab-serial.log --profile trap-input --out .\runs\boot_log_validation.json
```

For release-gate evidence with source provenance, wrap the same validation in QEMU boot evidence:

```powershell
python .\tools\emit_qemu_boot_evidence.py --source fixture --out .\runs\qemu_boot_evidence.json
python .\tools\emit_qemu_boot_evidence.py --log .\runs\pooleos-lab-serial.log --source captured_qemu_serial --out .\runs\qemu_boot_evidence.captured.json
```

The Lab launcher also supports `-BootValidationOutput`, `-QemuBootEvidenceOutput`, and `-EmitCapturedEvidenceOnly` so captured serial logs can be validated directly from the QEMU workflow.

`source=fixture` validates the marker contract but keeps `boot_evidence_claimed=false`. `source=captured_qemu_serial` may claim boot evidence only when the trap-input validation passes.

The release gate keeps fixture and captured evidence in separate slots: use `--qemu-boot-evidence` for fixture evidence, and `--qemu-captured-boot-evidence` plus `--qemu-captured-boot-receipt` for real captured serial evidence.

Emit the marker responsibility contract when preparing a captured boot handoff:

```powershell
python .\tools\emit_qemu_boot_marker_contract.py --dry-run-checklist .\runs\qemu_captured_boot_dry_run_checklist.json --lab-guest-autostart .\runs\lab_guest_autostart.json --out .\runs\qemu_boot_marker_contract.json
python .\tools\emit_qemu_boot_marker_image_binding.py --marker-contract .\runs\qemu_boot_marker_contract.json --lab-image-manifest .\runs\lab_image_manifest.json --out .\runs\qemu_boot_marker_image_binding.json
python .\tools\emit_rootfs_content_manifest.py --image-binding .\runs\qemu_boot_marker_image_binding.json --image .\output\images\rootfs.ext4 --extracted-rootfs .\runs\rootfs_extracted --out .\runs\rootfs_content_manifest.json
python .\tools\emit_rootfs_extraction_handoff.py --rootfs-content-manifest .\runs\rootfs_content_manifest.json --note-out .\runs\rootfs_extraction_handoff.md --out .\runs\rootfs_extraction_handoff.json
python .\tools\emit_rootfs_extraction_receipt.py --handoff .\runs\rootfs_extraction_handoff.json --rootfs-content-manifest .\runs\rootfs_content_manifest.json --out .\runs\rootfs_extraction_receipt.json
```

The marker contract maps each required `trap-input` marker to its guest emitter, post-capture evidence role, and PooleOS kernel/PGVM2 boundary. It keeps `boot_evidence_claimed=false` and `security_boundary_claimed=false`. The image binding hashes the Buildroot overlay emitters, support wrappers, and external metadata without claiming that a rootfs was built or booted. The rootfs content manifest compares those hashes against extracted rootfs files once the image exists.

## Boundary

Presence of these markers proves only that the configured smoke path ran inside the image. It does not prove production readiness, hardware support, security isolation, or full benchmark coverage.
