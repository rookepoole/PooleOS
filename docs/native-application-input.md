# Native Application Input

Status: Cycle300 controlled application-input qualification passes on QEMU and
visible VirtualBox. This is development-only PWS1 behavior, not a stable
production ABI, general input stress qualification or completed desktop.
The acceptance record is [Cycle300](checkpoints/cycle300-application-input.md).

## Authority And Wire Contract

The explicit input profile uses PooleWindowInput, PooleInputText and
PooleInputNumbers. Kernel feature `development-window-input` depends on the
existing lifecycle/capacity/window features. It changes the embedded-image
read-only boundary to0x1C000; existing profiles retain their old boundaries.
The total208-page kernel ceiling,36 guarded kernel-stack pages, four-page app
ceiling and seven-page service ceiling are unchanged. Input does not add a
syscall, process lease, device grant or extra simultaneous RPC request.

PWS1 remains64 bytes. Op5 polls application input only in the explicit input
profile; ordinary decoding rejects it. Requests have status/offset/length/data
all zero. The service requires kernel-attested sender slot4 or5, exact admitted
generation, live surface handle and next sequence. Rejections do not advance
sequence or consume input. Successful requests advance the same sequence used by
surface writes. Clients validate the window service's kernel-attested slot2,
generation1, handle, op and sequence before consuming a response.

An ordinary response has offset0 and up to32 input bytes. Offset1 is a reset
notification with zero payload. Only Ctrl-C, Backspace, Enter and printable ASCII
are admitted. Reserved/trailing bytes, oversized or malformed payloads fail
closed. This narrow character protocol is not IME, Unicode, keybinding or raw
device support. Apps do not gain access to PS/2 ports or the framebuffer.

Ordinary clients retain4096 completion-poll attempts. Interactive clients use a
separate65536-attempt finite budget for both input and result/draft publication.
A host renderer-work regression bounds two maximum-viewport, fully populated
scene compositions including fixed display-queue retry work within that budget.
Native snapshots exposed both interactive clients exhausting the old4096 limit
while still alive. Timeout still cancels/takes the same request exactly once and
fails closed; this budget adds no request slot and is not a wall-clock guarantee.
The budget starts after request acceptance. Queue-full submissions retain the
existing retryable result between application work turns; there is no overall
submission deadline or guarantee of progress after compositor failure. A poll
call itself does not loop waiting for queue space.

The native challenge holds A/Shift but taps/releases unused F1 to stop
unsolicited device typematic before the exact snapshot. It submits repeated
makes after focus changes. VirtualBox can filter duplicate host key-down events
before the guest, so this is controlled focus/editing evidence, not general
native typematic-stress qualification. Direct repeat suppression has host tests;
native continuous-repeat focus/retirement stress remains open. See the
[VirtualBox keyboard implementation](https://github.com/VirtualBox/virtualbox/blob/main/src/VBox/Devices/Input/DevPS2K.cpp).

## Bounded Routing

Two fixed64-byte queues bind input to the admitted surface generation/handle.
Trusted window focus selects a queue; the client cannot request another owner.
The device drain remains bounded to32 tagged bytes per service poll. The service
retains a committed reply during backpressure instead of draining again or
retargeting it. Cancelled queued requests have no reply authority and cannot
consume data. Retirement/replacement scrubs queued bytes and pending reset state.

Focus loss cancels unclaimed queued input, preventing execution of a truncated
draft. Overflow and controller reset also signal cancellation and discard through
a delimiter. Application cancellation is owner-bound. Unread Terminal FIFO bytes
are separately cancelled on interactive focus loss; its existing partial-command
state is not silently continued after dropping bytes. Input statistics retain
their Terminal-FIFO meaning and must not be cited as global app-delivery counts.

A physical-key fence suppresses keys/modifiers already held at a focus or lifetime
boundary until their release. Character decoding clears held modifier state at
that boundary while retaining Caps Lock mode. Controller reset clears partial
set-1 prefixes, but retains known held-key fences. Mouse transitions, capture,
minimize/restore and process-bound surface retirement remain in the existing WM.

## Application Behavior

Each isolated app owns a48-byte in-memory scratch draft, rendered in its two
bottom rows. Backspace edits the draft, Ctrl-C clears it, and Enter computes a
result. PooleText reports byte/word/LF counts. PooleNumbers accepts comma/space
separated signed32-bit integers and uses the existing checked accumulator for
count, sum, minimum and maximum. It is not an expression parser or spreadsheet.
The49th character cancels the draft and blocks through Enter, rather than
computing a truncated numeric value. Transport reset also clears the draft.

File jobs retain their existing acknowledgements and file wait behavior. A new
file result may replace result rows but does not overwrite the scratch draft.
Manual results cannot be immediately replaced by an older file snapshot. App
restart creates a fresh draft and surface identity. Nothing is persistent yet.

## Qualification Boundary

Host tests cover malformed/foreign/stale/replayed requests, queue ownership,
cancellation, backpressure, focus fencing, keyboard prefix repair, overflow and
file-job coexistence. Independent freestanding ELF/code builds must match and
pass the unchanged local-relative relocation audit before guest execution.

Native acceptance requires exact shell output, six lifecycle pixel barriers,
mouse drag/minimize/restore, direct app typing/editing, held-key focus isolation,
checked numeric results, overflow recovery and blank fresh-generation drafts.
The pixel oracle compares every pixel of expected rows against a frozen glyph
fixture; visual plausibility alone is insufficient. Emulated tests use QEMU and
owned disposable VirtualBox guests, never physical-media writes or host cursor
movement. Each guest remains bounded to240 seconds and each input observation
to12 seconds. No passing result is claimed until the actual run completes.

Remaining production work includes persistent editable documents, richer input,
native arbitrary overload testing, focused-process death scenarios, compositor
restart/resynchronization, launch controls, accessibility and PooleGlass. Existing
microkernel, PooleGlyph/PDC, canonical qualification and N0-N39 gates remain open.
Focused/dragging death must also challenge undecoded controller bytes at the
asynchronous focus boundary, not just already-decoded held keys. Repaint latency
and partial-frame visibility need separate measurement and presentation work;
the12-second qualification deadline is not an interactive latency target.
Replace busy completion polling with a separately qualified event-wait path as
the service ABI matures. Measure scheduler fairness and bounded wakeup under
composition load; the larger finite work budget alone proves none of those
production latency or efficiency properties.
