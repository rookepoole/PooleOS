# Run The Native Window Preview

Cycle303's controlled native qualification passes on QEMU and visible VirtualBox.
The local launcher and byte-verified Downloads copy select this checkpoint.

Cycle303, 2026-10-18. Native PooleBoot + PooleKernel, not Linux.
This experimental build draws Terminal and two independent native application
windows inside the VM and accepts focused keyboard input. It is not a complete
desktop, PooleGlass environment, installer or production release.

Cycle303 adds a host-tested typed launch broker and authenticated transport,
but does not connect graphical launch controls yet. The ordinary shared-code
image is rebuilt and requalified: eight QEMU and four VirtualBox runs, including
the complete two-mode input/lifetime matrix. Start applications through Terminal
as below. This checkpoint does not add a launch button or change the UI design.

The controlled device challenge covers96 exact app-input observations, a332-byte
shell case,17 pointer steps and six generation-bound lifecycle pixel barriers.
Both single-character and four-character shell-input modes must pass on QEMU and
visible VirtualBox. Editing, calculations, draft overflow recovery, fresh restart,
peer survival and cleanup retain the240-second guest and12-second action bounds.
The longer557-byte serial workflow is separately replayed. Historical failures
remain retained, not rewritten as successes. Native continuous-typematic stress
is not qualified by this controlled scenario: VirtualBox may filter duplicate
host makes before they reach the guest.

The lifetime challenge adds24 ordered observations per guest: fault or exit
while the app has focus, an active drag and Shift held, followed by release and
fresh explicit focus. Its24 serial fault/stop-control bytes are separate from308
device-keyboard bytes. Both modes pass on both backends. One additional Cycle301
VirtualBox burst attempt lost COM1 retirement diagnostics while COM2 reported
the fault; an unchanged replay passed. The cause and diagnostic repeatability
remain open. This preview is not an everyday-reliability qualification.

Cycle302 adds a bounded retained COM1 queue and a separate diagnostic image that
recovers an exact record after a controlled stall. It does not establish the
historical interruption's cause, qualify permanent-device failure, or replace
the ordinary image's input/lifetime regression requirements. Overflow rejection
is sticky; no apparently valid continuation is invented across a lost-byte gap.
See the [bounded serial contract](native-bounded-serial.md).

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

Text counts bytes/words/lines; Numbers summarizes signed32-bit integers.
These are separate native applications using capability IPC and native file
wait/wakeup, not a host simulation or a kernel command interpreter.
Their windows appear after `start text` and `start numbers`. Click Text and type
`PooleOS native`, then Enter: Bytes14, Words2, Lines0. Click Numbers and type
`3, -2 8`, then Enter: Rows3, Sum9, Min-2, Max8. Numbers accepts a list, not
expressions. Backspace edits; Ctrl+C clears the scratch draft. Enter evaluates
without adding a newline. The two bottom rows hold at most48 ASCII characters.
A49th character clears the draft and reports `Input limit`; press Enter or Ctrl+C
before starting afresh. These are scratch tools, not persistent document editors.
File commands above still work and do not replace the app's scratch draft.

Stopping/faulting an app removes its window
and taskbar entry; `status` in Terminal reports process state. A restarted app
opens a fresh window with an empty draft. Automatic restart of the window service itself remains
unimplemented and is not implied by application restart.
If the focused app disappears, neither another app nor Terminal inherits focus
or pending input. Release the mouse button, then click the intended window.
When the button was already up and no release packet arrives, the first
click-and-release may be consumed; the next click selects focus. Held modifiers
remain fenced until released. Keyboard-only recovery is not implemented yet.

To exercise containment: `fault numbers`, then `status numbers`, `start numbers`
and `numbers /numbers.csv`. To finish normally: `stop text`, `status text`,
`stop numbers`, `status numbers`, then `exit`. Wait for each command response.
The shell refuses exit while child tasks are still owned.

For host-side termination use Ctrl+] in the launcher terminal, or close the
VirtualBox window and choose **Power Off**, not Save State. Do not forcibly kill
the launcher process. The controller powers off/unregisters only its recorded
temporary VM and retains its files. Cleanup after abrupt controller-process death
is still unqualified. Sessions have a 15-minute limit; output/logs are bounded.

The input profile is US ASCII with Shift, Enter, Backspace and app Ctrl+C. Mouse focus,
dragging and minimize/taskbar restore have bounded emulator qualification, not
everyday reliability or physical-device qualification. Click the intended window
before typing. No selection, history editing,
scrollback, Unicode/IME, clipboard or interruptible jobs yet.
Files are bundled and read-only; no data persists between sessions.
If focus changes while decoded keys remain unclaimed, the affected input is
cancelled rather than silently truncated. An app can show `Input reset`; press
Enter to finish discarded input before typing a fresh draft. Already consumed
scratch input is retained across ordinary focus changes.

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

Qualified development image: `outputs/cycle303-optical1/PooleOS-UserSpace-Preview.iso`.

Verified convenience copy: `PooleOS-Native-Windows-Cycle303.iso` in Downloads.
Size 66109440 bytes; SHA256:
`4FAC38AA0A631CC2D4D2AD428AAFEE07EE33A2CEB7FAEF8128655D9A6553D8F8`.
The ISO contains the explicit input-profile kernel/service and interactive apps.
Final-source native replay and convenience-copy hash verification pass.

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
.\Launch-Local-Console.cmd --receipt outputs/cycle303-optical1/receipt.json
```

From the repository root with the configured Python runtime:

```text
python -B -m tools.qualify_native_app_session --work-dir outputs/NEW-OPTICAL --program-dir outputs/cycle303-programs4 --optical --windows --window-capacity --surface-lifecycle --surface-input
python -B -m tools.qualify_native_windows --receipt outputs/NEW-OPTICAL/receipt.json --work-dir outputs/NEW-MOUSE-QEMU
python -B -m tools.qualify_native_windows --receipt outputs/NEW-OPTICAL/receipt.json --work-dir outputs/NEW-MOUSE-BURST-QEMU --keyboard-batch 4
python -B -m tools.qualify_native_windows --receipt outputs/NEW-OPTICAL/receipt.json --work-dir outputs/NEW-MOUSE-VBOX --backend virtualbox --virtualbox PATH-TO-VBoxManage.exe --visible
python -B -m tools.qualify_native_windows --receipt outputs/NEW-OPTICAL/receipt.json --work-dir outputs/NEW-MOUSE-BURST-VBOX --backend virtualbox --virtualbox PATH-TO-VBoxManage.exe --visible --keyboard-batch 4
```

Use unused directories. The program directory contains29 independently rebuilt,
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

For the distinct lifetime challenge, run `tools.qualify_native_input_lifetime`
with the same `--receipt`, a new `--work-dir`, and each backend/batch combination
above. It intentionally uses the separately counted serial controls described
earlier, not an all-device-input claim. Each run retains the240-second guest and
12-second action bounds and192-capture ceiling. Diagnostic-only images cannot
qualify the local preview.

## Remaining Work

Next: authenticated graphical launch controls, compositor restart/resynchronization,
local graphical boot without the COM2 helper, efficient event waits and persistent
editing. Native input
overload/reset, continuous-typematic stress and accessible PooleGlass styling
remain separate requirements. Bounded emulator pointer evidence does
not establish unrestricted input or physical-device behavior. The console
has an explicit seven-page capacity profile. Its 24594-byte test image includes
deliberate padding and has 4078 bytes below the 28672-byte ceiling; ordinary
WindowConsole has116 bytes free at16268/16384. The fixed probe starts at24576,
so future service growth/layout changes require fresh build and execution checks.
Service separation and scalable address spaces remain required; no hardware
speedup is claimed.
The input-only kernel uses134/208 pages,36 guarded stack pages and a0x1C000
read-only boundary with360 bytes of padding. Interactive accepted-request polls
are limited to65536 attempts; ordinary clients retain4096. This is not a
wall-clock responsiveness guarantee. Repaint latency and partial frames need
separate presentation work. Two intermediate cursor frames in Cycle301 settled
in subsequent recorded frames; atomic presentation/double buffering is not
implemented. Native stack overflows were repaired by ending input polling before
nested painting, without enlarging guards. All-path stack-depth/high-water
verification remains open as `FLAG-N13-USERSTACK-001`.
Continue robust microkernel work, persistence, networking and PooleGlyph/PDC.
Default VirtualBox diagnostics still fail stage117; actual watchdog delivery
there remains separately unqualified. This application profile does not close it.

Production layout, hardware drivers, multi-host reproduction, complete runtime
attestation, signing and the full canonical/merge gates remain open.
See the [contract and tracked gaps](native-window-manager.md) and
[input contract](native-window-input.md), [rendering contract](native-rendering.md)
and [capacity contract](native-window-capacity.md),
[application-input contract](native-application-input.md),
[input-lifetime contract](native-input-lifetime.md),
[launch-control contract](native-launch-control.md),
[current checkpoint](checkpoints/cycle303-graphical-launch.md).
VirtualBox's [lifecycle controls](https://docs.oracle.com/en/virtualization/virtualbox/7.2/user/vboxmanage.html)
and [optical/EFI setup](https://docs.oracle.com/en/virtualization/virtualbox/7.2/user/working-with-vms.html)
describe the host-side operations.
