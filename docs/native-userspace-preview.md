# Run The Native User-Space Preview

Cycle288, 2026-10-13. Unsigned native PooleBoot + PooleKernel, not Linux.
This is a one-CPU QEMU/OVMF optical preview operated through a host terminal.
It is not a desktop, installer, signed release or hardware-qualified image.

## Launch On This Development Machine

Run `Launch-UserSpace-Preview.cmd` from the repository root. It uses the existing
pinned QEMU/OVMF inputs and Python runtime, checks the current qualification and
exact image/source hashes, and opens no SDL display. Wait for the native prompt.
The actual shell and applications execute in separate guest user address spaces;
the Windows terminal only transports COM2 bytes.

The local pointer is `outputs/native-userspace-preview.json`. The explicit form:

```powershell
.\Launch-UserSpace-Preview.cmd --receipt outputs/cycle288-optical3/receipt.json
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

Image: `outputs/cycle288-optical3/PooleOS-UserSpace-Preview.iso`

Size: 66109440 bytes. SHA256:
`1E4752E3D45972CEA7711AF443C15EFC22CD82558F1A975B6B676ADF6C7841AE`

Do not write it to physical media. It is an optical-only VM image, not a hybrid
USB image. The launcher depends on this repository and its pinned local tools;
it is not a standalone distributable bundle. Unsigned receipts bind local bytes
but do not authenticate them. Source changes make old qualification fail closed.

Use the configured Python runtime with `-B` and repository `PYTHONPATH`:

```text
tools/qualify_native_app_session.py --work-dir outputs/NEW-UNUSED-DIRECTORY --program-dir outputs/cycle287-programs2 --optical
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
