# QEMU Boot Marker Image Binding

Status: draft v0.1

The QEMU boot marker image binding connects the marker responsibility contract to exact Buildroot scaffold files. It hashes the marker-emitting overlay scripts, guest support wrappers, defconfig, post-build script, and BR2 external metadata so later captured boot evidence can be compared against known image inputs.

Emit the binding:

```powershell
python .\tools\emit_qemu_boot_marker_image_binding.py --marker-contract .\runs\qemu_boot_marker_contract.json --lab-image-manifest .\runs\lab_image_manifest.json --out .\runs\qemu_boot_marker_image_binding.json
python .\tools\emit_rootfs_content_manifest.py --image-binding .\runs\qemu_boot_marker_image_binding.json --image .\output\images\rootfs.ext4 --extracted-rootfs .\runs\rootfs_extracted --out .\runs\rootfs_content_manifest.json
python .\tools\emit_rootfs_extraction_handoff.py --rootfs-content-manifest .\runs\rootfs_content_manifest.json --note-out .\runs\rootfs_extraction_handoff.md --out .\runs\rootfs_extraction_handoff.json
python .\tools\emit_rootfs_extraction_receipt.py --handoff .\runs\rootfs_extraction_handoff.json --rootfs-content-manifest .\runs\rootfs_content_manifest.json --out .\runs\rootfs_extraction_receipt.json
```

`status=pass` means the marker contract and lab image manifest agree with the current Buildroot scaffold, all marker source files are under `rootfs_overlay`, marker text is present in the hashed source files, support wrappers are hashed, and the defconfig/post-build/BR2 external metadata are present.

`status=blocked` means the binding is internally valid but inherits a blocked marker contract, usually because QEMU or the rootfs image is not available yet. `status=fail` means a source hash, source marker, Buildroot manifest entry, lab image manifest value, or boundary flag is inconsistent.

## Bound Files

- `/etc/init.d/S99pooleos-lab`
- `/usr/bin/pooleos-lab-smoke`
- `/usr/bin/pooleos-lab-verify-input`
- `/usr/bin/pooleos-lab-doctor`
- `/usr/bin/pooleos-lab-release-gate`
- `/usr/bin/pooleos-kernel-pgvm2-transcript-contract`
- `lab-os/buildroot/external/Config.in`
- `lab-os/buildroot/external/external.desc`
- `lab-os/buildroot/external/external.mk`
- `lab-os/buildroot/external/configs/pooleos_lab_x86_64_defconfig`
- `lab-os/buildroot/external/board/pooleos_lab/post-build.sh`

## Boundary

This artifact proves source and scaffold binding only. It does not prove a Buildroot rootfs was built, that QEMU booted, or that PGVM2 enforcement happened in the kernel. The transcript contract script is hashed here as a disabled support wrapper, not as execution evidence. The rootfs content manifest is the next evidence layer: it compares these source hashes against an existing built image and extracted rootfs tree.
