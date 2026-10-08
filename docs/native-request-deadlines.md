# Native Request Deadlines

Contract PKIPC5, development-only PSABI1 extension. This is original PooleKernel
code for one exclusive BSP with IF/DF/AC clear, not a stable production ABI.

## Ownership And Time

The persistent IPC Space now owns the non-copyable PKCLOCK1 Lease as well as the
request records. Each successful prepare allocates a checked, nonzero clock epoch;
closing/reopening cannot reuse an epoch. The native adapter retains only device
mapping/root/PAT/child authority, not a second competing counter owner. No raw
timestamp or user-provided clock identity grants expiry authority.

Prepare publishes ownership before start writes hardware. Timed admission requires
a successfully sampled, healthy running clock. Request deadlines carry the epoch
and checked absolute nanoseconds derived from a bounded positive relative interval.
CPU charge totals remain unrelated to service elapsed time.

Syscall14 uses rdi=PSABI1 version1, rsi=endpoint SEND handle, rdx=owned user buffer,
r10=1..64 bytes, r8=relative timeout1..1000000000 nanoseconds, r9=0. Existing calls
0..13 retain their argument contracts. Returns the caller-owned completion handle
on success. Status10 is TimedOut; status11 is ClockUnavailable. Existing request
wait/take/cancel operations retain their authority and quota rules.

## Arbitration And Failure

The native syscall adapter validates its complete frame before sampling the clock,
then performs the bounded IPC operation under the same exclusive IF0 ownership.
This sample is the serialized admission point, not a hard-real-time promise about
the final copy instruction. A reply admitted before expiry may finish copying after
that time; a failed copy does not commit success. The next observation can expire it.
Deadline delivery latency includes bounded kernel/dispatch work and idle polling.

At now >= deadline, the first terminal outcome wins. Reply, cancellation, discard,
owner death and timeout cannot replace one another once committed. Expiry invalidates
claimed reply authority while retaining completion capacity until the caller takes it.
Queued payloads may still be read but carry no live reply token; timeout is neither
rollback nor exactly-once service execution. Side effects already performed remain.

Uncertain reads, regression, changed clock configuration or accounting overflow
poison the epoch. Pending timed requests receive ClockUnavailable; earlier terminal
outcomes survive. The lease remains owned, admission stays closed, and a release
failure is sticky until hardware restoration and a fresh epoch. Pending deadlines
prevent ordinary clock closure. Untimed requests do not acquire implicit deadlines.

Existing wait tickets map timeout to the scheduler's TimedOut reason and unavailable
clock to OwnerGone. Clock failure remains a distinct user status. Wait registration,
park, notification and resume preserve their retry-safe, exactly-once ownership.

## Native Exercise And Limits

Two real private-root client/server lifetimes use dedicated control endpoints. One
request expires while queued, the other after its server has claimed the reply token.
Both tasks are parked at expiry; HPET polling wakes the client. Before taking the
completion, the client wakes the server, which attempts a denied late reply and sends
an acknowledgment. The client then takes the retained timeout and both tasks exit.

The bounded native idle path polls the real HPET with at most2000000 samples per
idle interval. It is not interrupt-driven power-efficient idle. General supervision,
arbitrary service admission, sustained budgets, interrupt-driven idle, SMP clocks,
physical stopped-clock recovery, suspend/resume and production ABI remain open.
Clock-fault delivery/restart is host-tested; the live adapter still halts on an
unexpected clock failure while retaining ownership. Do not claim live recovery.

The usable ISO still requires init, confined console/input, shell, bundled files,
two applications and fresh optical boot interaction. Full microkernel, PooleGlyph/PDC
and accessible PooleGlass requirements remain after that milestone.
