# Lab Guest Autostart

The Lab guest autostart artifact proves the Buildroot overlay is prepared to mount the QEMU shared folder and run PooleOS smoke at boot.

Artifact kind: `pooleos.lab_guest_autostart`

The guest init script is:

```text
/etc/init.d/S99pooleos-lab
```

It attempts:

```text
mount -t 9p -o trans=virtio,version=9p2000.L pooleos_output /mnt/pooleos-output
```

Then it runs:

```text
pooleos-lab-smoke
```

For trap-bearing inputs, the serial log should validate with the `trap-input` boot-log profile, including `POOLEOS_LAB_SHARED_MOUNT_PASS`, `POOLEOS_LAB_INPUT_VERIFY_PASS`, and `POOLEOS_LAB_TRAP_ABI_BOUNDARY_PASS` when the draft ABI boundary receipt is staged and verified.

Emit static evidence with:

```powershell
python .\tools\emit_lab_guest_autostart.py --qemu-shared-folder-contract .\runs\qemu_shared_folder_contract.json --out .\runs\lab_guest_autostart.json
```

This is static overlay evidence only. It becomes boot evidence after QEMU serial output contains the required trap-input markers.
