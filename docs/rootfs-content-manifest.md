# Rootfs Content Manifest

Status: draft v0.1

The rootfs content manifest connects the QEMU boot marker image binding to a built rootfs image. It hashes `output/images/rootfs.ext4` when present, and when an extracted rootfs directory is supplied, it compares the guest files back to the source hashes recorded by `qemu_boot_marker_image_binding.json`.

Emit the manifest:

```powershell
python .\tools\emit_rootfs_content_manifest.py --image-binding .\runs\qemu_boot_marker_image_binding.json --image .\output\images\rootfs.ext4 --extracted-rootfs .\runs\rootfs_extracted --out .\runs\rootfs_content_manifest.json
python .\tools\emit_rootfs_extraction_handoff.py --rootfs-content-manifest .\runs\rootfs_content_manifest.json --note-out .\runs\rootfs_extraction_handoff.md --out .\runs\rootfs_extraction_handoff.json
python .\tools\emit_rootfs_extraction_receipt.py --handoff .\runs\rootfs_extraction_handoff.json --rootfs-content-manifest .\runs\rootfs_content_manifest.json --out .\runs\rootfs_extraction_receipt.json
```

`status=pass` means the rootfs image exists, the extracted rootfs tree exists, and every bound guest file matches the source hash from the marker image binding. `status=blocked` means the artifact is valid but the image, extracted rootfs tree, or upstream marker image binding is not ready. `status=fail` means the supplied extracted rootfs is missing a bound file or a file hash differs from the source binding.

## Bound Guest Files

- `/etc/init.d/S99pooleos-lab`
- `/usr/bin/pooleos-lab-smoke`
- `/usr/bin/pooleos-lab-verify-input`
- `/usr/bin/pooleos-lab-doctor`
- `/usr/bin/pooleos-lab-release-gate`

## Boundary

This artifact does not build, mount, or extract `rootfs.ext4`. It reads an existing image path and an optional extracted rootfs tree. Matching hashes prove source-to-rootfs file continuity only; they do not prove QEMU booted or that PGVM2 enforcement happened in the kernel. Use the rootfs extraction handoff when an operator needs exact read-only WSL/Linux extraction commands.
