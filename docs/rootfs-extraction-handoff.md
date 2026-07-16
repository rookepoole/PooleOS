# Rootfs Extraction Handoff

Status: draft v0.1

The rootfs extraction handoff turns a blocked `rootfs_content_manifest.json` into an operator-reviewed WSL/Linux extraction plan. It emits a JSON handoff and Markdown note containing a copyable bash script that mounts `rootfs.ext4` read-only, copies contents into `runs/rootfs_extracted`, unmounts, and reruns the rootfs content manifest.

Emit the handoff:

```powershell
python .\tools\emit_rootfs_extraction_handoff.py --rootfs-content-manifest .\runs\rootfs_content_manifest.json --note-out .\runs\rootfs_extraction_handoff.md --out .\runs\rootfs_extraction_handoff.json
python .\tools\emit_rootfs_extraction_receipt.py --handoff .\runs\rootfs_extraction_handoff.json --rootfs-content-manifest .\runs\rootfs_content_manifest.json --out .\runs\rootfs_extraction_receipt.json
```

`status=pass` means the handoff is ready for operator review because the rootfs image and image-binding artifact exist and the generated script passes safety checks. `status=blocked` means the handoff is valid but the image or another operator prerequisite is not present. `status=fail` means the source manifest failed or the generated command plan is unsafe or incomplete.

## Safety Boundary

Codex does not run the script. The script refuses a non-empty extraction directory, mounts with `-o ro,loop`, avoids recursive delete operations, unmounts with trap cleanup, and reruns `emit_rootfs_content_manifest.py` after extraction.

## Boundary

This artifact proves only that a safe operator command plan was generated. It does not build the image, mount the image, extract files, claim boot evidence, or prove kernel/PGVM2 enforcement. The rootfs extraction receipt records whether the operator ran this handoff and whether the resulting rootfs content manifest is verified.
