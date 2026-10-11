# Native Console IPC

Cycle264, 2026-10-11. Native four-process admission, exact IPC echo, close/reap and
wrong-peer rejection pass in fresh guests. The rejected peer's client still polls;
bounded peer-death recovery, shell and optical ISO remain open. See the
[current checkpoint](checkpoints/cycle264-native-console-ipc.md).
The CI invariants below were frozen before Cycle263 executable implementation;
its [build-only checkpoint](checkpoints/cycle263-console-ipc-programs.md) and Cycle262
non-IPC echo evidence remain historical, not newly executed evidence.

## Decision

Build PooleConsoleService and PooleConsoleClient as separate freestanding user
programs. The service owns UART policy, the client exercises real IPC wrappers;
neither links the kernel implementation. Use existing PSABI1 send3/receive7
operations and the kernel-produced sender envelope. A dedicated endpoint pair
will grant send-only peer handles during later trusted admission. Kernel shell,
payload-asserted sender identity, broad port authority and shared-memory shortcuts
are rejected. A general multiplexer, reply-token RPC, virtio driver and interrupts
remain later work, not silently claimed by this single-client boundary.

## Frozen Invariants

- CI1: PCS1 is32 bytes: magicPCS1, kind byte, length byte, two zero reserved bytes,
  LE sequence u64,16 payload bytes with zero unused tail. Read/Close/Written/Closed
  have no payload; Write has1..16 bytes; Input has one byte. Sequence is1..MAX-1.
  Unknown kind, reserved/trailing data, size errors and wrap reject.
- CI2: the receive7 envelope is four LE u64s: sender slot, generation, reply token,
  payload size. Verify exact configured peer identity, zero reply token and size32
  before parsing payload. Startup handles/peer locators do not grant authority.
- CI3: one owned pending request/response, no heap, no unbounded queues. At most
  one transport or bounded UART operation group per state-machine step. Backpressure
  retains request, response and write cursor; it cannot repeat a consumed input byte
  or successful output write. Do not consume another request while a reply is pending.
- CI4: Read waits by bounded UART polls and returns one byte. Write acknowledges
  only after every byte is accepted by the UART. Close drains TEMT, sends Closed,
  then retires. Device/protocol/transport errors fail closed; no retry after fatal
  error without terminating/reconstructing the service. No kernel polling policy.
- CI5: the separate client uses Read/Input then Write/Written, or EOT then
  Close/Closed, validates each sequence/kind and commits only after successful
  transport. It is an echo client, not a shell, supervisor or second useful app.
- CI6: two independent offline locked builds must match. Keep single RX-page,
  no imports/writable segments/remaining relocations and local PC-relative object
  references. Host protocol/device/transport tests do not prove native execution.
- CI7: free-space preflight precedes user-build output creation. Never delete
  failed evidence to satisfy acceptance. Explicitly scoped generated-directory
  archives must match original member counts/hashes before originals are removed.

## Next Native Integration

Admit service/client in addition to init/counter, using four private roots and
four bounded endpoints. Authenticate granted handles before dispatch, set an
explicit52-page task-image requirement without silently enlarging fixed kernel
image/stack bounds, and preserve ordinary unsigned-boot denial. Test exact serial
input crossing service/client IPC, reply backpressure, invalid sender/request,
driver/client termination and independent init/counter survival. Existing source
receipts remain historical after source changes. No current ISO or native IPC
execution claim follows from this build-only step.

User-space shell, file service/two useful applications, supervision/loading,
efficient idle, clock recovery, optical ISO, full robust microkernel, signed trust,
PooleGlyph/PDC and accessible PooleGlass remain required.
## Native Admission Qualification (Cycle264)

NI1: PSESSION3 admits four distinct owned CPL3 roots and nine actual grants before
dispatch: init/counter endpoints, service/client endpoints, service-only COM2.
The task-image allowance is exactly 52 pages, with at most 12 separately accounted
retained ACPI pages (64 total allocator quota); fixed kernel image/stack bounds
remain. The first 52-total-page attempt failed at the fourth image because the
allocator also owns the firmware snapshot; that failure remains in Cycle264 logs.
NI2: Independently built service/client program bytes are embedded exactly once;
two separately built kernel images match. Boot prefix, media, retained inputs and
transcript remain independently bound to the exact candidate.
NI3: Two fresh guests must echo different host-supplied binary/log-like input
through PCS1 with exact bytes, then service/client exit0 on EOT. Both 13-page
images are reaped, counters freeze, and init/counter continue past512 dispatches.
NI4: A distinct wrong-expected-peer guest must reject the genuine kernel sender
with service exit152 and zero application output. Its polling client remains
live: this is an explicit unresolved peer-death notification/supervision gap,
not recovered or gracefully closed. The independent pair must keep progressing.
NI5: Host admission tests exercise all four members, cross-pair authority denial,
message pressure, rollback, stale generations, queued acknowledgement surviving
sender retirement, and full object cleanup. Host tests are not native pressure
or fault-recovery qualification.
NI6: Strict observation parsing rejects missing/replayed/mutated roots, counts,
ownership and retirement. UART bytes never become trusted kernel observations.
NI7: Keep earlier receipts immutable/historical; record every failure and source
change; do not promote shell, ISO, general supervision, signed trust or production.
