# PooleKernel bounded lock family (PKLOCK1)

## Status

PKLOCK1 is the bounded N12.2 lock family for the native x86-64 PooleKernel. It
is pre-production evidence. It completes only N12.2 and does not complete N12,
deferred reclamation, general SMP, physical-target qualification, or release.

The authoritative machine-readable files are:

- `specs/native-kernel-locks-contract.json`
- `specs/native-kernel-locks-contract.schema.json`
- `specs/native-kernel-locks-readiness.schema.json`
- `runs/native-kernel-locks-readiness.json`

The implementation is `native/kernel/src/locks.rs`. Scheduler integration is
in `native/kernel/src/scheduler.rs`; the exact four-vCPU selector-22 path is in
`native/kernel/src/main.rs` and `native/kernel/src/arch/x86_64.rs`; the host
contention probe is `native/kernel/src/bin/pklock1_probe.rs`; and
`tools/qualify_native_kernel_locks.py` rebuilds and verifies the bounded
profile.

## Primitive surface

The allocation-free family is built over PKATOM1 and contains:

| Primitive | Contract |
| --- | --- |
| Raw spinlock | FIFO ticket lock with try, unbounded, and finite-attempt acquisition |
| IRQ-save spinlock | Ticket lock with exact interrupt-enable and preemption-depth restoration |
| Sleeping mutex | Fixed eight-waiter queue, ownership, handoff, timeout, cancellation, owner death, and direct priority donation |
| Notification | Fixed eight-waiter FIFO with wake-one, wake-all, timeout, and cancellation |
| Reader-writer lock | Writer-ticketed and writer-preferred try, bounded, and unbounded paths |
| Sequence lock | Ticket-serialized writers and stable-even retrying readers |

Owner token zero is reserved. Non-owner release and recursive acquisition are
rejected. Timed APIs use a caller-supplied finite attempt count or monotonic
deadline; they do not imply a wall-clock latency guarantee.

## Context and order rules

`LockContext` records owner identity, interrupt state, interrupt depth,
preemption depth, sleep permission, and a fixed stack of held ranks. The rank
order is IRQ, run queue, mutex, reader-writer, then sequence. Acquisition must
be strictly increasing and release must be last-acquired-first-released;
same-rank nesting is deliberately rejected in this contract.

The fixed five-node lock-order graph checks an edge for cycles before commit.
Failed IRQ-save acquisition restores both context and graph. An IRQ guard binds
the owner, rank, ticket, and originating lock address so a foreign guard is
rejected before context or lock mutation.

Sleeping waits require task context with interrupts and preemption nesting at
zero. The scheduler bridge supplies `ExternalLock` block and wake reasons plus
one direct external priority-donation slot. PKLOCK1 does not claim NMI-safe
locking or arbitrary interrupt-context sleep behavior.

## Mutex policy

The mutex selects the highest-priority waiter, preserving FIFO order among
equal priorities. A continuously queued waiter becomes mandatory after seven
bypasses. Donation is direct and one level only: the owner receives the
maximum queued waiter priority, and donation is recomputed after handoff,
timeout, cancellation, or teardown.

Handoff reserves ownership for one exact wake receipt. Timeout and cancellation
remove a named waiter once. Owner death clears ownership and donation and wakes
all queued waiters with `OwnerDead`. No transitive donation-chain claim is
made.

## Memory and progress boundaries

Spin handoff publishes with release ordering and observes with acquire ordering.
The reader-writer lock excludes new readers while a writer is pending. A
sequence writer opens an odd interval only from a stable even sequence, writes
the payload, then publishes the next even sequence; readers accept only equal
acquire snapshots.

These rules cover aligned ordinary memory. They do not provide MMIO or DMA
ordering. FIFO and bounded-bypass progress assume the current owner continues
to execute. Sequence readers can retry indefinitely under continuous writes.
No wait-free, reclamation, hotplug, or general-topology guarantee exists.

## Verification layers

The PKLOCK1 qualifier establishes the following on one Windows host:

1. The canonical PKENTRY1 build, formatting, Clippy, and all 206 PooleKernel
   host tests pass under the pinned workspace-local Rust toolchain.
2. Four host threads complete 8,192 FIFO ticket acquisitions with no protected
   update loss or ticket-order mismatch under forced contention.
3. Host receipts cover IRQ and preemption restoration, nested-context
   rejection, eight-waiter mutex fairness and donation, owner death, FIFO
   notification, three-reader/one-writer contention, and three-reader/one-writer
   sequence-lock contention.
4. The default PooleBoot remains distinct and stops before transfer. A
   feature-gated selector-22 boot binary is built independently.
5. Two clean media generations are byte-identical.
6. Two fresh-variable QEMU/OVMF runs use the exact four-core Sandy Bridge TCG
   profile. BSP and APIC IDs 1, 2, and 3 contend on one shared ticket lock and
   produce exactly tickets 0 through 3, acquisition count 4, CPU mask 0xF,
   drained queue, cleared owner, and three installed then revoked aliases.
7. Both runs produce the exact 35-marker transcript, identical framebuffer,
   and identical PBP1 handoff bytes. The independent boot transcript, media
   oracle, and retained-kernel revalidation bindings all pass.
8. Thirty hostile-control categories mutate marker order and fields, host
   receipts, fairness, restoration, owner death, rollback, source allocation,
   input paths, and promotion claims. Every mutation must fail closed.

## Live four-vCPU profile

Selector 22 maps one existing physical page into the three AP address spaces at
virtual address `0x1FE000`. The BSP takes ticket zero and queues the three APs;
the AP trampoline uses locked x86 operations for ticket reservation, ownership,
acquisition count, CPU mask, and serving advancement. The BSP participates in
the same queue and independently validates the final counters and ticket
permutation.

All three AP aliases are revoked before the existing PKSMP5 acknowledged TLB
shootdown, park, scrub, and release sequence. This is one exact topology and
one exact shared lock. Sleeping mutex, notification, reader-writer, and
sequence-lock concurrency are host evidence, as stated by the emitted markers.

## Non-claims and next dependency

PKLOCK1 does not implement RCU, hazard pointers, epochs, ABA-safe object
lifetime, transitive priority donation, arbitrary topology, hotplug, x2APIC,
weak-memory portability, or physical-target qualification. It does not satisfy
the N12 exit gate and makes no signing, release, production-authority, or
production-readiness claim.

The next owner-independent dependency is N12.3: define and qualify deferred
reclamation and ABA-safe lifetime rules over the typed atomics, lock, virtual
memory, and acknowledged shootdown contracts.
