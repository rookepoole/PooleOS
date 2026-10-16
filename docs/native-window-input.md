# Bounded Native Window Input

Cycle295. Development policy extending PWS1; not a production input service.
The native window console previously retained one pending decoded character.
The new `desktop/input.rs` policy replaces that slot with a64-byte FIFO backed
by initialized, borrowed user-space storage. No allocator, framebuffer mapping,
raw device authority or new kernel syscall is introduced.

## Invariants

- INPUT-1: accepted queued characters retain FIFO order, including ring wrap.
- INPUT-2: no polling turn consumes more than32 tagged PS/2 bytes. Surface and
  console IPC continue between turns; there is no unbounded input drain.
- INPUT-3: process every decoded mouse button transition in order. Only painting
  is coalesced: compare initial/final scene state, then repaint the scene or old
  and new pointer rectangles. Never sum deltas across clicks and discard edges.
- INPUT-4: only visible Terminal focus accepts keyboard characters. Focus
  transitions discard queued characters; modifier decoding continues so release
  events are not lost. Read-only application panes still discard keyboard input.
- INPUT-5: a full FIFO clears pending characters and prioritizes one Ctrl-C for
  the shell; remaining input is discarded through its line delimiter. A lost
  character must not turn an intended command into an accepted truncated one.
- INPUT-6: a transport reset clears partial packets, modifiers, drag capture and
  queued keys, cancels the partial line and discards through its delimiter.
- INPUT-7: typed port access, display ownership, root/retirement guards, exact
  startup grants, four-code-page and208-page kernel caps remain enforced.
- INPUT-8: qualification retains the240-second whole-guest and12-second mouse
  step bounds. Historical failures are not replaced by a different test mode.

Ctrl-C here cancels a partial command when the shell next reads input; it is not
job interruption. Overflow recovery requires a delimiter before fresh typing is
accepted. Already-delivered partial text is not erased solely by a focus change.
FIFO state cannot repair bytes already lost by the emulated controller itself.

## Accounting And Tests

The policy exposes saturating decoded/delivered/dropped/overrun/reset counters.
Synthetic Ctrl-C is not counted as a received or delivered user character.
Host tests cover FIFO wrapping, overflow before/on a delimiter, preserved
cancellation, focus drops, packet/reset handling, ordered press/drag/release,
and bounded raw-input floods. These counters are not yet exposed as live OS
telemetry; do not claim guest-measured drop counts from host policy tests.

The existing one-byte challenge remains the default. A separately labeled
`--keyboard-batch 4` mode injects at most four characters' actual make/break
scancodes together, then requires exact output before another batch. Batches
cannot cross a command delimiter or bypass the sustained-progress/pointer
barrier. The complete573-byte challenge, real app lifecycle/file waits,
4096-dispatch sustained progress, pixel checks and negative controls remain.
This is bounded burst qualification, not unrestricted typing or mouse flood
acceptance. Each receipt records the selected mode and its batch boundaries.

Both combined QEMU mouse/keyboard attempts failed their unchanged240-second
guest bound: one-byte mode reached537/573 keys, four-character mode552/573.
Each observed17 pointer steps and50 paced movements. The anticipated full-session
burst pass was not observed; neither mode qualifies combined mouse operation.
Independent keyboard-only evidence must not be substituted for that missing pass.

The window console links at16332 bytes, leaving52 bytes under the four-page
cap. Embedded user-code growth requires a windows-only read-only segment/code
boundary of0x18000; the resulting kernel image uses128/208 pages with36 guarded
stack pages. Default/application/terminal boundaries are unchanged. Further
compositor growth needs a deliberate service split or separately verified loader
capacity work, not silent size-limit relaxation.

## Remaining Work

PWS-G1 through G7 remain tracked in the [window contract](native-window-manager.md).
Needed: live overflow telemetry and native reset/overrun injection, interrupt-
driven input and controller loss accounting, sustained high-rate load, application
input delivery, lifecycle notifications/restart, measured render/stack budgets,
accessible PooleGlass and complete canonical/kernel qualification. Mouse and
keyboard acceptance is limited to the exact guest receipts, not physical devices.
See the [build plan](pdc-production-build-plan.md) for the full N0-N39 program.
