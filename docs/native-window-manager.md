# PWS1 Native Window Preview

Cycle294, 2026-10-15. Status: partial development evidence, not production.
This opt-in `development-windows` profile extends the native desktop profile;
it does not replace the default kernel or its diagnostics. Window composition
and application logic execute in CPL3. Applications never receive framebuffer
addresses, raw I/O authority, or arbitrary screen-coordinate authority.

## Surface Boundary

The console owns a dedicated PRPC1 surface endpoint separate from blocking PCS1
console reads. Bootstrap admission has nine atomic steps; the original eight
exported bootstrap handles retain their meaning. Application startup uses six
arguments and three distinct typed SEND-only grants: control, files, surfaces.
Legacy five-argument startup remains strict and unchanged for other profiles.

PWS1 frames are exactly 64 bytes: magic, opcode/status, sequence, logical handle,
offset, length, a 32-byte payload and canonical zero padding. Operations are
OPEN, WRITE, CLEAR and CLOSE. Reserved fields, noncanonical trailing bytes,
sequence zero/MAX, non-ASCII content, control characters and out-of-range spans
reject without surface mutation or sequence advance. Identity comes from the
kernel's authenticated 96-byte RPC envelope, never from a client claim.

Only application slots 4/5 may own one 24x8 character surface each. Storage is
384 bytes borrowed by the compositor; no allocator or client mapping is needed.
Owner generation, monotonic logical handle and exact next sequence reject stale,
cross-client and replayed requests. A new generation clears old content. CLOSE
clears its own surface and prevents reopening that generation. Process death
does not yet send a lifecycle notification; retained result snapshots are not
liveness indicators. Cross-client isolation here is a bounded implementation
and test claim, not a comprehensive formal proof of the whole microkernel.

The server retains a reply across backpressure without applying a request twice.
Dead-client reply failures are discarded. Cancelled/plain queue messages with
reply token zero are ignored without applying their payload. Clients perform
bounded asynchronous submit/poll, cancel after 4096 polls, and consume the
cancellation completion. Publisher failure disables only display publishing;
backend file/results IPC continues. Automatic display resynchronization is open.

## Native Display And Input

Three fixed windows use a retained software compositor: Terminal and read-only
PooleText/PooleNumbers result panes. The manager controls z-order, focus, title
dragging, clamping, minimize and taskbar restore. Close releases drag ownership
and restores available focus. Geometry admits 640x480 through 4096x2160.
Clipping and cell-range repaint keep damage local; new surfaces paint only their
own window plus taskbar without taking keyboard focus. Focus/order/geometry
changes repaint the scene. There is no atomic double-buffered presentation yet.

The terminal stays a separate native shell interface; apps report actual file
results. A pending publication is drained before an app issues its next file
read, preserving the one-outstanding-request/wait contract. The app publisher
shows Ready, Result snapshot or Job failed. Frozen post-retirement results remain
visible; service restart and lifecycle-state synchronization are still needed.

The kernel exposes fixed i8042 ports only through the authorized console syscall
path. New operation 26 requires canonical zero arguments; operation 25 retains
legacy keyboard behavior. Input tags distinguish keyboard, auxiliary mouse and
reset/error. Initialization drains at most 64 bytes, enables auxiliary input and
uses bounded ACK handling for defaults/reporting; no reset/A20 or arbitrary
controller command is exposed. Errors, resend and floods fail closed.

The three-byte mouse decoder checks packet synchronization, signed 9-bit deltas,
Y inversion and overflow. Overflow/reset releases buttons and partial state.
PS/2 input is BSP-polled, not an interrupt-driven general device service.
Nonterminal focus discards keyboard characters in this read-only preview: it
does not yet deliver input events to applications. Type slowly, one command at a
time; high-rate typing/motion, wheel, selection, USB and absolute pointing remain
unqualified. No physical hardware input test was performed.

## Evidence And Budgets

`runs/native-window-manager-readiness.json` is explicitly partial. It preserves
five passing current QEMU guests and one passing visible VirtualBox keyboard
guest separately from the failed combined pointer guest. Native keyboard runs
each use 573 emulated device bytes and zero serial input. Exact shell output,
app fault/restart and file waits, 4096-dispatch progress, frame pixels and owned
VM cleanup are checked. The frame oracle verifies layout/ink, not OCR of every
result value; serial output and process markers supply independent result checks.

The failed combined test observed 17 pointer steps and 50 paced movements,
including focus, drag, minimize/restore and return-to-terminal, but stopped at
the unchanged 240-second guest bound after 537/573 keyboard bytes. Per-step bound
is 12 seconds; host injection caps each axis delta at 96 and waits for observed
pixels. Unpaced large movement previously lost expected displacement. Neither
that failure nor the current combined timeout is converted into qualification.
VirtualBox mouse qualification and human interaction remain open.

Kernel host tests: default576, applications595, desktop601, windows607 in each
debug/release. User-space172 per profile; 24 independently identical ELF/code
pairs, no imports/writable segments/linked relocations, unchanged four-code-page
limit. Window console15592 bytes, Text9727 and Numbers9718. Window kernel127 of
208 pages, 36 guarded stack pages, windows-only rodata selector0x17000. Existing
root/retirement guards, strict binary admission and production layout rejection
remain. 103 focused Python tests pass; five legacy entry checks still fail.

## Remaining Work

These sub-items extend FLAG-NATIVE-UI-001 and FLAG-N13-USERSPACE-ISO-001;
they do not close either flag or any phase.

- PWS-G1: separate a bounded pointer/focus completion scenario from the longer
  lifecycle regression, or optimize measured input/render pacing without
  increasing timeouts or weakening oracles; then qualify VirtualBox mouse.
- PWS-G2: process retirement/status notifications, compositor restart,
  generation resynchronization, retry after display backpressure and stale
  retained-view prevention; adversarial lifecycle interleavings.
- PWS-G3: bounded input buffering/coalescing, overflow/drop accounting, typeahead
  and burst tests. Poll/paint work must not starve IPC, input or app deadlines.
- PWS-G4: general application input delivery, launch UI, resize and surface
  quotas beyond two read-only panes, window close/application-stop distinction,
  session policy and file manager/editor integration.
- PWS-G5: atomic presentation, double buffering, measured render/stack budgets,
  overload/fuzz tests and compositor fault containment/recovery.
- PWS-G6: accessible PooleGlass liquid glass, Unicode/shaping, HiDPI, keyboard-only
  focus/navigation, contrast and reduced-motion/transparency. Current flat UI is
  a functional foundation, not final visual design.
- PWS-G7: refresh legacy kernel-entry qualification independently (four stale
  binding failures and the existing exactly-246-tests expectation), retain the
  unchanged historical evidence, investigate VirtualBox default stage117 and
  actual watchdog delivery, then waiting-stop/interruptible jobs and full replay.

Persistence, networking, isolated general drivers, USB/virtio GPU, robust SMP
microkernel, tandem PooleGlyph/PDC and every N0-N39 production requirement remain.
See the [build plan](pdc-production-build-plan.md),
[checkpoint](checkpoints/cycle294-native-windows.md), and
[local launch guide](native-userspace-preview.md).
