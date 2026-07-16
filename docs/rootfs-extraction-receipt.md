# Rootfs Extraction Receipt

Status: draft v0.1

The rootfs extraction receipt records whether an operator ran the rootfs extraction handoff and whether the resulting rootfs content manifest verifies source-to-rootfs continuity. It is the gate between extracted-rootfs evidence and captured QEMU promotion.

Emit the receipt before operator execution:

```powershell
python .\tools\emit_rootfs_extraction_receipt.py --handoff .\runs\rootfs_extraction_handoff.json --rootfs-content-manifest .\runs\rootfs_content_manifest.json --out .\runs\rootfs_extraction_receipt.json
```

Emit the receipt after the operator runs the handoff script and regenerates `rootfs_content_manifest.json`:

```powershell
python .\tools\emit_rootfs_extraction_receipt.py --handoff .\runs\rootfs_extraction_handoff.json --rootfs-content-manifest .\runs\rootfs_content_manifest.json --operator-executed --operator-notes "operator ran reviewed read-only extraction handoff" --out .\runs\rootfs_extraction_receipt.json
```

`status=pending_operator_action` means no operator execution is claimed and captured QEMU promotion remains blocked. `status=verified` means the operator execution flag is set, the rootfs content manifest is `pass`, and every bound file hash matches. `status=verification_failed` means the operator ran the handoff but the resulting manifest did not verify. `status=invalid` means the source handoff or manifest is malformed or failed its own structural checks.

## Boundary

This receipt does not execute the rootfs extraction. It records operator claims and current manifest evidence only. It allows captured-QEMU promotion only when `captured_qemu_promotion_allowed=true`, which requires `status=verified`.

After the receipt is verified and captured QEMU evidence exists, run `tools/emit_qemu_captured_boot_readiness.py` to reconcile the rootfs receipt, captured boot receipt, and `qemu_boot_evidence.captured.json` before using promotion language.
