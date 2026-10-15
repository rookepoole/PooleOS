# Run The Native User-Space Preview

Cycle290, 2026-10-15. Unsigned native PooleBoot + PooleKernel, not Linux.
This is a one-CPU QEMU/OVMF optical preview operated through a host terminal.
It is not a desktop, installer, signed release or hardware-qualified image.

## ISO File Type And VirtualBox

Windows may describe an `.iso` as a "Disc Image File" or "DVD Disc Image".
That description does not make it a different format. The file linked below is
an actual ISO9660 optical image with an EFI El Torito boot entry, not a VDI or
VHD hard disk. Do not rename it or extract the embedded `EFI.IMG` for loading.

To select it in VirtualBox, power off the intended test VM, open **Settings >
Storage**, select its optical drive (often labeled **Empty**), then use the disc
icon and **Choose a disk file** to select `PooleOS-UserSpace-Preview.iso`.
Do not use the **existing virtual hard disk** picker. If no optical drive exists,
add an optical drive under a storage controller first. Enable **EFI** in the VM's
system settings; this image has no legacy BIOS boot path. These are media-loading
instructions, not a claim that PooleOS has passed a VirtualBox boot test.

The current qualification is QEMU/OVMF only. Shell input and output use COM2
serial, not the virtual display and keyboard. Successfully attaching the ISO
therefore does not establish that the preview is usable in the VirtualBox window.
Use the tested launcher below for the current interactive preview. Actual tests
on VirtualBox7.2.20 confirm optical attachment and entry into PooleKernel, but the
first task slice fails at stage34365/panic0x101F before a usable shell session.
Cycle290 repairs the previously missing kernel serial diagnostics. VirtualBox
user-space interaction and a qualified reproducible configuration remain open;
enabling EFI alone does not repair that kernel/platform failure.

Before Cycle290, a read-only recheck confirmed the original Cycle289 image's hash
`17A5D17F11F106F27EA22B6E5939A8F4449496086963245DC3E5002642499969`,
the EFI boot catalog, `EFI/BOOT/BOOTX64.EFI`, and no structural issues in the
bounded ISO/FAT inspector. This was not a new guest boot. Oracle documents optical
media attachment and EFI under [Working with Virtual Machines](https://docs.oracle.com/en/virtualization/virtualbox/7.2/user/working-with-vms.html).

## Launch On This Development Machine

Run `Launch-UserSpace-Preview.cmd` from the repository root. It uses the existing
pinned QEMU/OVMF inputs and Python runtime, checks the current qualification and
exact image/source hashes, and opens no SDL display. Wait for the native prompt.
The actual shell and applications execute in separate guest user address spaces;
the Windows terminal only transports COM2 bytes.

The local pointer is `outputs/native-userspace-preview.json`. The explicit form:

```powershell
.\Launch-UserSpace-Preview.cmd --receipt outputs/cycle290-optical/receipt.json
```

Try these commands individually, waiting for each result:

```text
ls
cat /readme.txt
start text
start numbers
text /readme.txt
numbers /numbers.csv
status text
status numbers
fault numbers
status numbers
text /version.txt
start numbers
numbers /numbers.csv
stop text
status text
stop numbers
status numbers
exit
```

Text computes counts; Numbers summarizes signed integers in the bundled file.
Their file requests use native kernel wait/wakeup. Jobs are still synchronous:
the shell cannot yet interrupt an active job to accept another command.
The fault command intentionally faults Numbers inside this development guest.
`exit` refuses while children remain owned. `Ctrl+]` closes the entire VM from
the host. Sessions also stop at 15 minutes or bounded input/output/log limits.
Each launch gets fresh firmware variables and a new `outputs/preview-session-*`
evidence directory. There is no networking, host share, persistent guest disk,
passthrough, physical-media write or host firmware change.

The terminal adapter was tested with injected keys and exact responses. A person
typing in a visible Windows terminal was not separately tested. ASCII input,
Enter and Backspace are supported; cursor/history editing is not implemented.
Guest escape sequences are sanitized before display on the host.

## Image And Reproduction

Image: `outputs/cycle290-optical/PooleOS-UserSpace-Preview.iso`

Size: 66109440 bytes. SHA256:
`129F2232C8EE126A80C84CE71BDC9BD97DB925521275BE0C462D4224AB5E3E65`

Do not write it to physical media. It is an optical-only VM image, not a hybrid
USB image. The launcher depends on this repository and its pinned local tools;
it is not a standalone distributable bundle. Unsigned receipts bind local bytes
but do not authenticate them. Source changes make old qualification fail closed.

Use the configured Python runtime with `-B` and repository `PYTHONPATH`:

```text
tools/qualify_native_app_session.py --work-dir outputs/NEW-UNUSED-DIRECTORY --program-dir outputs/cycle289-programs2 --optical
tools/launch_native_userspace_iso.py --receipt outputs/NEW-UNUSED-DIRECTORY/receipt.json --work-dir outputs/NEW-SESSION-DIRECTORY --self-test
```

The retained program directory supplies 20 independently built, source-bound
program pairs; the qualifier builds fresh kernel and PooleBoot pairs. It then
authors each optical variant twice and checks exact bytes, independent ISO/FAT
decoding, actual boot transcripts and exact user interaction. Use unused output
directories to preserve failures. Qualification time limits are fixed before run.

## Remaining Gates

The release architecture scanner still fails four future production paths; the
preview's exact twelve-file PKLOAD6 layout has a separate development-only check.
No policy was weakened. Four strict application sessions, ordinary trust denial
and the terminal-adapter session passed on one host. This is not general stress,
second-host reproduction, physical hardware or full canonical qualification.
Kernel cleanup/race/recovery, drivers, local input/display, persistence, networking,
PooleGlyph/PDC, accessible PooleGlass, final layout and signing remain open.
