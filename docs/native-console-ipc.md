# Native Console IPC

Cycle263, 2026-10-11. Host tests and independent executable builds pass; native
admission remains pending. The invariants below were frozen before implementation.
See the [checkpoint](checkpoints/cycle263-console-ipc-programs.md). No native execution
evidence exists until separately admitted programs run in a fresh guest. Keep Cycle262
console echo as historical evidence, never relabel it as interprocess console I/O.

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
