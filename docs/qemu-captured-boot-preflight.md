# QEMU Captured Boot Preflight

Status: draft v0.1

The captured boot preflight is a non-mutating report for the real QEMU launch path. It checks the expected image, optional kernel, QEMU executable, serial log parent directory, shared folder, and captured evidence output paths before launching the VM.

Emit the report:

```powershell
python .\tools\emit_qemu_captured_boot_preflight.py --image .\output\images\rootfs.ext4 --shared-output .\runs\qemu_shared --serial-log .\runs\pooleos-lab-serial.log --boot-validation-output .\runs\boot_log_validation.captured.json --qemu-boot-evidence-output .\runs\qemu_boot_evidence.captured.json --qemu-captured-boot-receipt-output .\runs\qemu_captured_boot_receipt.json --out .\runs\qemu_captured_boot_preflight.json
```

`status=pass` means the launch inputs are ready. `status=blocked` means the report is valid but one or more required launch prerequisites are missing, such as the image, QEMU command, or shared folder. `status=fail` is reserved for unsafe configuration such as colliding output paths.

After emitting the pending captured-boot receipt, assemble the operator command bundle:

```powershell
python .\tools\emit_qemu_captured_boot_launch_bundle.py --preflight .\runs\qemu_captured_boot_preflight.json --qemu-shared-folder-contract .\runs\qemu_shared_folder_contract.json --qemu-captured-boot-receipt .\runs\qemu_captured_boot_receipt.json --fixture-evidence .\runs\qemu_boot_evidence.json --release-gate-output .\runs\release_gate.json --out .\runs\qemu_captured_boot_launch_bundle.json
```

## Boundary

This preflight does not build the Lab image, launch QEMU, create directories, or claim boot evidence. Captured boot proof still requires `qemu_boot_evidence.captured.json` from a validated serial log.
