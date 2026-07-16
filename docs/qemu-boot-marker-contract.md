# QEMU Boot Marker Contract

Status: draft v0.1

The QEMU boot marker contract maps the required `trap-input` serial markers to the guest-side emitter, trap-bundle verification role, post-capture evidence files, and the current PooleOS kernel/PGVM2 responsibility boundary.

Emit the contract:

```powershell
python .\tools\emit_qemu_boot_marker_contract.py --dry-run-checklist .\runs\qemu_captured_boot_dry_run_checklist.json --lab-guest-autostart .\runs\lab_guest_autostart.json --out .\runs\qemu_boot_marker_contract.json
python .\tools\emit_qemu_boot_marker_image_binding.py --marker-contract .\runs\qemu_boot_marker_contract.json --lab-image-manifest .\runs\lab_image_manifest.json --out .\runs\qemu_boot_marker_image_binding.json
python .\tools\emit_rootfs_content_manifest.py --image-binding .\runs\qemu_boot_marker_image_binding.json --image .\output\images\rootfs.ext4 --extracted-rootfs .\runs\rootfs_extracted --out .\runs\rootfs_content_manifest.json
python .\tools\emit_rootfs_extraction_handoff.py --rootfs-content-manifest .\runs\rootfs_content_manifest.json --note-out .\runs\rootfs_extraction_handoff.md --out .\runs\rootfs_extraction_handoff.json
python .\tools\emit_rootfs_extraction_receipt.py --handoff .\runs\rootfs_extraction_handoff.json --rootfs-content-manifest .\runs\rootfs_content_manifest.json --out .\runs\rootfs_extraction_receipt.json
python .\tools\emit_kernel_boot_handoff.py --qemu-captured-boot-readiness .\runs\qemu_captured_boot_readiness.json --qemu-boot-marker-contract .\runs\qemu_boot_marker_contract.json --boot-trap-bundle-manifest .\runs\pooleos_boot_trap_bundle_manifest.json --guest-loader-verification .\runs\boot_trap_bundle_verification.json --out .\runs\kernel_boot_handoff.json
python .\tools\emit_kernel_pgvm2_loader_output.py --kernel-boot-handoff .\runs\kernel_boot_handoff.json --pooleglyph-source-anchor .\runs\pooleglyph_source_anchor.json --parser-kernel-promotion-receipt .\runs\pooleglyph_parser_kernel_promotion_receipt.json --kernel-build-id pending-kernel-loader --out .\runs\kernel_pgvm2_loader_output.json
python .\tools\emit_kernel_pgvm2_loader_evidence.py --kernel-boot-handoff .\runs\kernel_boot_handoff.json --kernel-loader-output .\runs\kernel_pgvm2_loader_output.json --pooleglyph-source-anchor .\runs\pooleglyph_source_anchor.json --parser-kernel-promotion-receipt .\runs\pooleglyph_parser_kernel_promotion_receipt.json --out .\runs\kernel_pgvm2_loader_evidence.json
```

`status=pass` means the marker map matches `runtime.boot_log.required_markers_for_profile("trap-input")`, the dry-run checklist and guest autostart artifact agree on the marker sequence, and each marker has a responsibility boundary. `status=blocked` means the map is valid but inherits unresolved dry-run blockers. `status=fail` means a source artifact, marker sequence, source script, evidence role, or boundary record is inconsistent.

## Marker Ownership

| Marker | Guest owner | Boundary |
| --- | --- | --- |
| `POOLEOS_LAB_AUTOSTART_START` | `/etc/init.d/S99pooleos-lab` | guest init overlay |
| `POOLEOS_LAB_SHARED_MOUNT_PASS` | `/etc/init.d/S99pooleos-lab` | guest shared-folder mount |
| `POOLEOS_LAB_INPUT_VERIFY_PASS` | `pooleos-lab-smoke` and `pooleos-lab-verify-input` | guest trap-bundle verifier |
| `POOLEOS_LAB_TRAP_ABI_BOUNDARY_PASS` | `pooleos-lab-smoke` and `pooleos-lab-verify-input` | guest draft trap ABI boundary verifier |
| `POOLEOS_LAB_BOOT_START` | `pooleos-lab-smoke` | guest smoke script |
| `POOLEOS_LAB_DOCTOR_PASS` | `pooleos-lab-smoke` and `pooleos-lab-doctor` | guest doctor wrapper |
| `POOLEOS_LAB_RELEASE_GATE_PASS` | `pooleos-lab-smoke` and `pooleos-lab-release-gate` | guest release-gate wrapper |
| `POOLEOS_LAB_ARTIFACT_EXPORT_PASS` | `pooleos-lab-smoke` | guest artifact export |
| `POOLEOS_LAB_BOOT_DONE` | `pooleos-lab-smoke` | guest smoke script |
| `POOLEOS_LAB_AUTOSTART_DONE` | `/etc/init.d/S99pooleos-lab` | guest init overlay |

## Boundary

This artifact does not launch QEMU, execute PGVM2 bytecode, or claim kernel enforcement. It keeps `execution_performed=false`, `boot_evidence_claimed=false`, and `security_boundary_claimed=false`. The image-binding artifact adds source hashes for marker emitters, support wrappers, defconfig, post-build script, and BR2 external metadata. The rootfs content manifest compares the guest files after a rootfs is built and extracted, but still does not prove QEMU booted.

PooleGlyph checkpoint review through Phase 65 shows that the current v0.5-dev package is a public-safe metadata and diagnostic surface, with Phase 66 recommended as a Core IR boundary audit. PooleOS should therefore consume PooleGlyph artifacts through bridge manifests and explicit evidence contracts until kernel PGVM2 loader evidence can prove booted enforcement.
