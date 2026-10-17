# Run The Native Window Preview

Ten QEMU and two visible VirtualBox checks pass on final source. The local
launch pointer and hash-verified Downloads copy now select this image.

Cycle299, 2026-10-17. Native PooleBoot + PooleKernel, not Linux.
This experimental build draws Terminal and two independent native application
result windows inside the VM and accepts its keyboard. It is not a complete
desktop, PooleGlass environment, installer or production release.

Both full visible VirtualBox mouse/keyboard modes pass: one-byte and four-character
keyboard input, each with 17 pointer steps/41 observed movements at 1024x768.
The challenge verifies 573 keyboard characters, a separate discarded focus-probe
key, exact application/file/recovery results, pixels, sustained progress and owned
cleanup within the unchanged 240-second guest bound. Each run also verifies six
intermediate framebuffer captures against exact process generations: fault/stop
removal, fresh restart and survival of the other application. Both QEMU input
modes also pass on this image. Historical failures remain retained, not rewritten
as successes.

Cycle299 gives the window service read-only process-lifetime observation through
already-held capability authority. It cannot terminate applications. Faulted or
stopped generations lose their surfaces; stale messages cannot resurrect them
or close a newer generation. The explicit seven-code-page service profile and
ordinary four-page application limit are unchanged. Code permissions, stack
guards, fixed process-lease quotas and allocation ownership remain enforced.
The seventh-page probe includes deliberate test padding, not additional UI.

## Start On This Machine

Double-click `Launch-Local-Console.cmd` in the repository root. It opens a
VirtualBox window using the qualified configuration automatically. Click inside
the VM to type. VirtualBox's Host Key (default Right Ctrl) releases captured
keyboard/mouse input. The host
terminal is only the launcher; it is not the guest's keyboard/input interface.

Try commands one at a time:

```text
help
ls
cat /readme.txt
start text
start numbers
text /readme.txt
numbers /numbers.csv
status numbers
```

Text counts bytes/words/lines; Numbers summarizes the bundled integer file.
These are separate native applications using capability IPC and native file
wait/wakeup, not a host simulation or a kernel command interpreter.
Their result windows appear after `start text` and `start numbers`. They are
read-only snapshots, not editors. Stopping/faulting an app now removes its window
and taskbar entry; `status` in Terminal reports process state. A restarted app
opens a fresh window. Automatic restart of the window service itself remains
unimplemented and is not implied by application restart.

To exercise containment: `fault numbers`, then `status numbers`, `start numbers`
and `numbers /numbers.csv`. To finish normally: `stop text`, `status text`,
`stop numbers`, `status numbers`, then `exit`. Wait for each command response.
The shell refuses exit while child tasks are still owned.

For host-side termination use Ctrl+] in the launcher terminal, or close the
VirtualBox window and choose **Power Off**, not Save State. Do not forcibly kill
the launcher process. The controller powers off/unregisters only its recorded
temporary VM and retains its files. Cleanup after abrupt controller-process death
is still unqualified. Sessions have a 15-minute limit; output/logs are bounded.

The input profile is US ASCII with Shift, Enter and Backspace. Mouse focus,
dragging and minimize/taskbar restore have bounded emulator qualification, not
everyday reliability or physical-device qualification. Keep Terminal focused to
type; focused result panes discard keys. No selection, history editing,
scrollback, Unicode/IME, clipboard or interruptible jobs yet.
Files are bundled and read-only; no data persists between sessions.

The console buffers64 decoded characters and polls at most32 device bytes per
turn. On FIFO overflow or input reset it cancels the partial line when the shell
next reads input and discards through Enter; then type the command afresh. That
recovery policy has host-test coverage, not native overload qualification. It
does not interrupt running jobs or recover bytes already lost by the controller.

## Configuration And Safety

The launcher discovers the existing Windows VirtualBox 7.2.20r175154 installation
and checks thirteen base-runtime plus six GUI hashes. This is scoped runtime
identity, not complete host/driver/plugin attestation. No software is installed
and no global configuration or existing VM is changed.

Each launch creates a fresh `PooleOS-Preview-<UUID>` and
`outputs/virtualbox-session-*` directory. Exact settings: 512MiB, one CPU, EFI64,
ICH9, HPET/APIC on, x2APIC off, VBoxVGA/32MiB, no 3D, read-only optical media,
no guest disk/network/shares/USB/remote display. COM1 records diagnostics; COM2
exists for the serial mirror and read-only observation. It is still required.
The launcher handles the loopback connection; the guest input comes from PS/2.

The GUI may retain a registration lock briefly after poweroff. Cleanup retries
only the recognized lock error, with exact ownership/state revalidation, at most
eight attempts. Other failures retain diagnostics and fail explicitly. It never
uses `unregistervm --delete`, deletes VM files or kills global frontend processes.
Each control command retains its 30-second timeout. Close the exact named VM only
if a retained failure requires manual recovery; do not touch unrelated VMs.

## ISO And File Type

Image: `outputs/cycle299-optical3/PooleOS-UserSpace-Preview.iso`.

Convenience copy: `PooleOS-Native-Windows-Cycle299.iso` in Downloads.
Size 66109440 bytes; SHA256:
`691826E53A6EEAB9947C74F405E75B34C4D3DE4455C50D15CADD3AB1F8F5FCBC`.
The ISO contains the lifecycle-profile kernel/service, not Cycle298 bytes.
Final-source replay and convenience-copy hash verification pass.

Windows may call this a "DVD Disc Image". It is still a real ISO9660 image with
an EFI El Torito boot entry. It belongs in a VM's **optical-drive** picker, not
the virtual-hard-disk picker. Do not extract or rename its embedded EFI image.
Use the launcher on this machine: enabling EFI alone is not the full tested
configuration, and manually attaching the ISO without COM2 is insufficient.

This is optical-only, not a hybrid USB image. Do not write it to physical media.
The launcher requires this repository and the recorded local tools; it is not a
standalone distributable bundle. Unsigned receipts bind local bytes but do not
authenticate them. Source changes make old qualification fail closed.

## Other Entry Points And Reproduction

`Launch-VirtualBox-Preview.cmd` retains the host serial-terminal mode.
`Launch-UserSpace-Preview.cmd` retains headless QEMU/OVMF serial mode; it does
not open SDL, which previously crashed on this host. Both use the current pointer
`outputs/native-userspace-preview.json`. The new visible entry point is:

```powershell
.\Launch-Local-Console.cmd --receipt outputs/cycle299-optical3/receipt.json
```

From the repository root with the configured Python runtime:

```text
python -B -m tools.qualify_native_app_session --work-dir outputs/NEW-OPTICAL --program-dir outputs/cycle299-programs2 --optical --windows --window-capacity --surface-lifecycle
python -B -m tools.qualify_native_local_console --receipt outputs/NEW-OPTICAL/receipt.json --work-dir outputs/NEW-KEYBOARD-QEMU --backend qemu
python -B -m tools.qualify_native_local_console --receipt outputs/NEW-OPTICAL/receipt.json --work-dir outputs/NEW-KEYBOARD-VBOX --backend virtualbox --virtualbox PATH-TO-VBoxManage.exe --visible --keyboard-batch 4
python -B -m tools.qualify_native_windows --receipt outputs/NEW-OPTICAL/receipt.json --work-dir outputs/NEW-MOUSE-QEMU
python -B -m tools.qualify_native_windows --receipt outputs/NEW-OPTICAL/receipt.json --work-dir outputs/NEW-MOUSE-BURST-QEMU --keyboard-batch 4
python -B -m tools.qualify_native_windows --receipt outputs/NEW-OPTICAL/receipt.json --work-dir outputs/NEW-MOUSE-VBOX --backend virtualbox --virtualbox PATH-TO-VBoxManage.exe --visible
python -B -m tools.qualify_native_windows --receipt outputs/NEW-OPTICAL/receipt.json --work-dir outputs/NEW-MOUSE-BURST-VBOX --backend virtualbox --virtualbox PATH-TO-VBoxManage.exe --visible --keyboard-batch 4
```

Use unused directories. The program directory contains 26 independently rebuilt,
source-bound pairs. Kernel/boot pairs and ISO variants must reproduce exactly;
positive, stale-file-grant and ordinary unsigned-denial controls remain required.
Native keyboard tests inject device scancodes, never serial input, and compare
exact responses and real framebuffer pixels. A human typing is a separate check.
The explicitly selected four-character mode groups make/break scancodes, never
crosses a command delimiter and waits for exact output before the next group.
It is not an unrestricted flood test or a replacement for default one-byte mode.
Automated VirtualBox mouse qualification additionally checks the pinned installed
PowerShell executable and exact COM registration. It does not change execution
policy or move the host cursor. Normal interactive launching does not use that
test helper; VirtualBox supplies the user's device input.

## Remaining Work

Next: bounded input to application surfaces, native retirement while focused or
dragging, compositor restart/resynchronization, launch controls and useful
editable applications. Native input overload and accessible PooleGlass styling
remain separate requirements. Bounded emulator pointer evidence does
not establish unrestricted input or physical-device behavior. The console
has an explicit seven-page capacity profile. Its 24594-byte test image includes
deliberate padding and has 4078 bytes below the 28672-byte ceiling; ordinary
WindowConsole has 48 bytes free at 16336/16384. The fixed probe starts at 24576,
so future service growth/layout changes require fresh build and execution checks.
Service separation and scalable address spaces remain required; no hardware
speedup is claimed.
Continue robust microkernel work, persistence, networking and PooleGlyph/PDC.
Default VirtualBox diagnostics still fail stage117; actual watchdog delivery
there remains separately unqualified. This application profile does not close it.

Production layout, hardware drivers, multi-host reproduction, complete runtime
attestation, signing and the full canonical/merge gates remain open.
See the [contract and tracked gaps](native-window-manager.md) and
[input contract](native-window-input.md), [rendering contract](native-rendering.md)
and [capacity contract](native-window-capacity.md),
[checkpoint](checkpoints/cycle298-window-capacity.md).
VirtualBox's [lifecycle controls](https://docs.oracle.com/en/virtualization/virtualbox/7.2/user/vboxmanage.html)
and [optical/EFI setup](https://docs.oracle.com/en/virtualization/virtualbox/7.2/user/working-with-vms.html)
describe the host-side operations.
