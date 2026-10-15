# Cycle293: Native On-Screen Console And Keyboard

Date: 2026-10-15. Contract: PDISPLAY1. Owner direction: build toward a useful
native desktop, not another boot-screen redesign. Native PooleBoot/PooleKernel
remain the foundation; this is not a Linux-based environment.

## Delivered

Value-only capability-controlled display commands, bounded queued framebuffer
writes in the retained boot root, and read-only emulated PS/2 input mediation.
Independent CPL3 `PooleDesktopConsole` supplies ASCII text, scrolling, editing,
cursor and keyboard policy while retaining the existing shell/application IPC.
`Launch-Local-Console.cmd` opens a disposable visible VirtualBox session; its
serial channel only observes guest output. N18, N22 and N27 become partial.
N29 gains initial display-protocol/font evidence, not a completed compositor.

The [contract](../native-local-console.md) and [launch guide](../native-userspace-preview.md)
describe exact scope and operation. `runs/native-local-console-readiness.json`
records the final source-bound qualification after the GUI-unlock cleanup repair.
Earlier failed and superseded guests are preserved separately.

## Verification

- 21 independently rebuilt user-program pairs match byte-for-byte. 150 user-space
  tests pass debug/release. Local console is 7964 code bytes/two pages with no
  imports or linked relocations; all existing program contracts remain enforced.
- Final native host matrix: 576 default, 595 application and 601 desktop kernel
  tests pass per debug/release profile. Capture 102.234s, log SHA256
  `175895E605697428B61D0CB7201FBFB0E942EBA8BE7D66CCC677BBDD2EE1C1B7`.
- 75 focused Python tests pass in 8.935s after GUI retry regression coverage.
- Pre-cleanup-repair optical qualification passes two normal sessions, stale
  file-grant control and ordinary unsigned denial in 556.015s. Its separate QEMU
  native-keyboard session passes 573 input bytes with zero serial input.
- The first visible VirtualBox run completes native commands, application
  recovery and valid 1024x768 pixels, but fails unregistration while GUI-locked.
  Its original failed receipt is retained. The recorded UUID/name/config were
  reverified; the exact stopped VM was unregistered and prior registrations
  confirmed unchanged. This is not relabeled as a passing qualification.

Final replay: four optical QEMU guests pass in 589.953s; the QEMU keyboard
scenario passes in 176.859s; visible VirtualBox keyboard execution passes in
171.718s; and the actual visible-launcher adapter passes in 14.0s with a
programmatic stop at the native shell banner. These are five QEMU and two visible
VirtualBox guests. Both keyboard scenarios deliver 573 bytes through the emulated
device, zero through serial, with exact application responses, file waits,
fault/restart, a 4096-dispatch progress window and checked terminal pixels.
Both VirtualBox runs confirm stopped/unregistered status and unchanged prior
registrations. Human typing and abrupt launcher-process death remain unqualified.

The final ISO is 66109440 bytes and byte-identical to the pre-cleanup-fix build:
`18DE7FF006DA3A7B963A8D8F312984BDCEC87CEE6A34E21E6CB20575B5E68CB9`.
Public receipt SHA256:
`A8F2875556FEB5973332D2A9D78CAAC9A43C26872524ACDEE9715B976BB71429`.
Execution binds 950 inputs; user programs bind 73. Capture receipts preserve exact
logs, source snapshots and unchanged owner-conformance hashes. The three early
program failures have inner receipts/build logs, but no outer capture receipt.

## Failures And Repairs

Initial independent program builds exposed GOT/panic/libc dependencies and an
implicit memcpy when moving cell storage. Checked arithmetic, bounded policy
and initialized borrowed storage repair these without relaxing binary admission.
An early host assertion still expected syscall21 to be unknown in every profile;
it now remains unknown in the default profile and is explicitly tested when
desktop-enabled. That early assertion was observed in tool output, not a capture.

Desktop rodata exceeded the application-only 0x13000 region. A desktop-only 0x15000
selector preserves the 208-page total cap and existing profiles. Actual boots then
caught raw-GOP versus PBP1 format numbering, followed by flush-before-retirement
under a terminated task's CR3. Both contracts were corrected with guards intact.
The next complete app session was rejected by the splash-color screenshot check;
the new terminal has its own hostile-tested pixel oracle, without weakening boot
verification. Changed-cell scrolling removes unnecessary full-viewport redraws.

Visible VirtualBox introduced an asynchronous GUI session-lock release after
poweroff. Cleanup now retries only the recognized lock error within a fixed
attempt bound, checking exact ownership/state before each retry. Failure remains
explicit and leaves diagnostics; no existing VM or global process is killed.

The first metadata replay ran 378 tests with five stale historical-source
assertions failing. Older program bindings remain frozen at their original
hashes; current program input count is 73 and kernel Rust file count is 133.
Tests now distinguish those historical receipts from current-cycle bindings.
The failed 92.921s capture remains intact, log SHA256
`78097B1A79C85AC3A303206734673EE6DF8CECECAB5B927464779B858EF4AC4C`.
The repaired replay passes all 378 tests in 112.226s (capture 113.484s), log SHA256
`4D97476B26B8A4CA9FEC309EBE676F4CD12628DBF0CF5F8E07D503CC6DB94B9D`.
Python discovery finds 1533 tests; this is inventory, not a full-suite pass.
The architecture ledger binds 790 paths. Historical public readiness receipts
remain unchanged. Final index/publication validation is recorded separately in
the local `outputs/cycle293-finalcheck*` artifacts before checkpoint publication.

## Continuation

Next: isolated surfaces and input focus, then a native windowed desktop with
real application views, pointer input and accessible PooleGlass. Continue robust
microkernel development alongside this development lane. Keep VirtualBox stage117,
actual fallback watchdog delivery, waiting-stop/interruptible jobs, hardware
drivers, persistence, networking, PooleGlyph/PDC and all production gates open.

40 phases/301 subphases/8996 checklist requirements/59 additions, 99 flags/44 open
and 20 gap groups remain. Phase counts become 24 partial, 1 blocked, 15 not started,
0 complete. No exit gate is closed. Full canonical, merge, signing and production
qualification are not claimed. The local Phase65 PooleGlyph checkpoint, owner
conformance report and master-checklist hashes were rechecked unchanged.
