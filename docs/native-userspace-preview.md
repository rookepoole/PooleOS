# Run The Native User-Space Preview

Cycle291, 2026-10-15. Unsigned native PooleBoot + PooleKernel, not Linux.
This is a one-CPU optical preview operated through a host terminal.
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
instructions; selecting an ISO as a virtual hard disk will not work.

Shell input and output use COM2 serial, not the virtual display and keyboard.
Attaching the ISO therefore does not give you an interactive desktop in the
VirtualBox window. Use the tested QEMU terminal launcher below for now.

The exact Cycle291 ISO completed two isolated VirtualBox7.2.20r175154 application
sessions: shell commands, native file waits, Text/Numbers, application fault and
restart, and4096 dispatches of six-role progress. The tested profile is512MiB,
one CPU, EFI64, ICH9, HPET/APIC enabled, x2APIC disabled, optical media read-only,
no guest disk/network/shares, COM1 diagnostics and COM2 loopback transport.
The kernel now handles HPET without MSI, reset I/O APIC identity and zero-tick
budget yields. Earlier stage34365 failure is repaired for this application profile.

A packaged VirtualBox terminal launcher is still pending; changing EFI alone is
not a substitute for the tested full profile. Default VirtualBox diagnostics
still fail stage117, and actual fallback watchdog interrupt delivery there has
not been qualified. QEMU routed diagnostics do verify that delivery and recovery.
These are scoped VM results, not general VirtualBox/hardware support.

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
.\Launch-UserSpace-Preview.cmd --receipt outputs/cycle291-opticalfinal/receipt.json
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

Cycle290 tested the unchanged terminal adapter with injected keys and exact
responses; Cycle291 replays the source-bound launcher self-test. A person
typing in a visible Windows terminal was not separately tested. ASCII input,
Enter and Backspace are supported; cursor/history editing is not implemented.
Guest escape sequences are sanitized before display on the host.

## Image And Reproduction

Image: `outputs/cycle291-opticalfinal/PooleOS-UserSpace-Preview.iso`

Size: 66109440 bytes. SHA256:
`CEB2794D7E63739E31EE827BFDA65F99C38BD3B24D9A09B36554933FABC14E00`

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
No policy was weakened. Four QEMU application sessions, two VirtualBox sessions,
two QEMU routed diagnostics and two ordinary trust-denial boots pass on one host.
The broader diagnostic profile remains207/208 image pages; additional diagnostic
growth needs an explicit layout/capacity review. This is not general stress,
second-host reproduction, physical hardware or full canonical qualification.
Kernel cleanup/race/recovery, drivers, local input/display, persistence, networking,
PooleGlyph/PDC, accessible PooleGlass, final layout and signing remain open.
