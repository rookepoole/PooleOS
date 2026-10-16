# Run The Native Window Preview

Cycle295, 2026-10-15. Native PooleBoot + PooleKernel, not Linux.
This experimental build draws Terminal and two independent native application
result windows inside the VM and accepts its keyboard. It is not a complete
desktop, PooleGlass environment, installer or production release.

Current source-bound replay passes five QEMU guests and one visible VirtualBox
guest, including one-byte QEMU keyboard and burst-mode VirtualBox keyboard.
These check actual application recovery, window pixels and owned cleanup.
Both combined mouse/keyboard modes
timed out at240 seconds:537/573 one-byte keys and552/573 burst-mode keys, after
17 pointer steps/50 paced movements each. VirtualBox mouse remains untested.
Do not depend on dragging/minimize/focus for reliable everyday use yet.

## Start On This Machine

Double-click `Launch-Local-Console.cmd` in the repository root. It opens a
VirtualBox window using the qualified configuration automatically. Click inside
the VM to type. Right Ctrl releases VirtualBox's keyboard capture. The host
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
read-only snapshots, not editors. Stopping/faulting an app may leave its last
snapshot visible; use `status` in Terminal for process state. Surface lifecycle
notifications and recovery are still in development.

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
dragging and minimize/taskbar restore are experimental. Keep Terminal focused to
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

Image: `outputs/cycle295-optical2/PooleOS-UserSpace-Preview.iso`.

Convenience copy: `PooleOS-Native-Windows-Cycle295.iso` in Downloads.
Size 66109440 bytes; SHA256:
`F750999E6088D6B67481D5B21B6B35EF2285311B83D7B66B06DD149BD1BD47AD`.

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
.\Launch-Local-Console.cmd --receipt outputs/cycle295-optical2/receipt.json
```

With the configured Python runtime, `-B` and repository `PYTHONPATH`:

```text
tools/qualify_native_app_session.py --work-dir outputs/NEW-OPTICAL --program-dir outputs/cycle295-programs1 --optical --windows
tools/qualify_native_local_console.py --receipt outputs/NEW-OPTICAL/receipt.json --work-dir outputs/NEW-KEYBOARD-QEMU --backend qemu
tools/qualify_native_local_console.py --receipt outputs/NEW-OPTICAL/receipt.json --work-dir outputs/NEW-KEYBOARD-VBOX --backend virtualbox --virtualbox PATH-TO-VBoxManage.exe --visible --keyboard-batch 4
```

Use unused directories. The program directory contains 24 independently rebuilt,
source-bound pairs. Kernel/boot pairs and ISO variants must reproduce exactly;
positive, stale-file-grant and ordinary unsigned-denial controls remain required.
Native keyboard tests inject device scancodes, never serial input, and compare
exact responses and real framebuffer pixels. A human typing is a separate check.
The explicitly selected four-character mode groups make/break scancodes, never
crosses a command delimiter and waits for exact output before the next group.
It is not an unrestricted flood test or a replacement for default one-byte mode.

## Remaining Work

Next: surface lifecycle/restart recovery and native input overload testing, then
general application input and accessible PooleGlass styling. Both combined
pointer modes fail their time bound; a completed pointer sequence alone is not
a passing whole-session test. The console is52 code bytes below its four-page
cap, so further compositor growth requires an explicit architecture decision.
Continue robust microkernel work, persistence, networking and PooleGlyph/PDC.
Default VirtualBox diagnostics still fail stage117; actual watchdog delivery
there remains separately unqualified. This application profile does not close it.

Production layout, hardware drivers, multi-host reproduction, complete runtime
attestation, signing and the full canonical/merge gates remain open.
See the [contract and tracked gaps](native-window-manager.md) and
[input contract](native-window-input.md) and
[checkpoint](checkpoints/cycle295-native-window-input.md).
VirtualBox's [lifecycle controls](https://docs.oracle.com/en/virtualization/virtualbox/7.2/user/vboxmanage.html)
and [optical/EFI setup](https://docs.oracle.com/en/virtualization/virtualbox/7.2/user/working-with-vms.html)
describe the host-side operations.
