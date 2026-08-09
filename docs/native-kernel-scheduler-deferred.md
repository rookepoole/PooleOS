# PKSCHED3 bounded deferred work

## Scope

PKSCHED3 advances `N12-SCHED-DEFERRED-001` with one allocation-free deferred-work controller and two fixed BSP kernel workers. It composes the PKIRQ1 local-APIC timer path, the PKSCHED1 scheduler primitives, and the PKSCHED2 interrupt-return foundation. It does not create a general callback facility, driver API, service API, AP scheduler, or production authority.

The selector-17 development profile is isolated behind `development-scheduler-deferred`. Default PooleBoot still stops before transfer. A selector-17 build cannot be combined with another post-transfer development scenario.

## Work identity and storage

The controller owns exactly eight inline slots. It does not use `Vec`, `Box`, `String`, a map, a trait object, a function pointer, or dynamic allocation. Every accepted request contains:

- a nonzero producer key and a bounded source identifier;
- `High` or `Normal` priority;
- one typed operation token: `Add`, `Xor`, or `Fence` with a nonzero operand.

The tokens exist only to make execution and rollback observable. They are not arbitrary kernel callbacks. A work ID is the exact slot index plus a nonzero generation. Reuse increments the generation, and stale cancellation or retirement is rejected.

The lifecycle is `Free -> Reserved -> Queued -> Running -> Completed|Cancelled -> Free`. A slot cannot be reclaimed from `Reserved`, `Queued`, or `Running`. Terminal completion has an exact monotonically increasing receipt sequence.

## Interrupt boundary

The producer API accepts work only from a validated depth-one top half with interrupts disabled and the queue lock held. Worker-context enqueue is rejected to prevent recursion. Duplicate `(source,key)` work remains suppressed until its prior slot is retired.

The live profile delivers one local-APIC one-shot timer interrupt on IST1. The handler enqueues eight requests, rejects one duplicate, and cancels one queued request. It writes EOI before calling `observe_eoi`. That call mints an immutable epoch-one dispatch permit. A zero, stale, or future permit cannot claim work.

## Worker execution

Two fixed 16-KiB worker stacks are reserved in the lower 32 KiB of the already retained 128-KiB bootstrap-stack partition, canary checked, and entered with IF clear through the PKSCHED1 context-switch primitive. They add no image BSS pages and cannot overlap the live bootstrap RSP. The live dispatch trace is:

```text
worker:slot = 0:0,1:2,0:4,1:1,0:5,1:6
```

The first three high-priority operations bypass normal work. The fourth selection must admit the oldest normal item, bounding priority bypass at three. Worker 1 claims slot 6 and requests cancellation while it is `Running`; the operation does not commit. Each worker enters exactly three times, for six dispatches and twelve machine context transitions. CR3, FS base, GS base, and kernel GS base are unchanged.

## Cancellation, flush, and shutdown

Queued cancellation creates a terminal cancellation receipt immediately. Running cancellation records a request; the owning worker observes it before commit and creates exactly one terminal cancellation receipt. Repeated or terminal cancellation is rejected.

A flush token captures the current enqueue watermark. Flush is incomplete while any slot at or below that watermark is reserved, queued, or running. After six dispatches one normal item remains queued, so the watermark-eight flush is still incomplete. Shutdown then:

1. closes intake;
2. cancels the remaining queued item;
3. requires no running or nonterminal item;
4. proves the flush complete;
5. retires all eight terminal slots;
6. clears all 32,768 worker-stack bytes and worker metadata.

The final work result is five completions, three cancellations, sum lane 120, XOR lane 90, and fence lane zero.

## Rollback

A separate live-kernel controller injects faults after reservation, after queue insertion, before execution, before commit, and during cleanup. Every fault is rejected. Reservation and queue faults restore a free slot while retaining the consumed generation. Execution and commit faults return the item to `Queued`. Cleanup failure leaves the completed item owned until a successful retry. The profile observes five rollbacks, eight free slots, and no leaked work.

## Qualification

The qualification requires:

- seven focused PKSCHED3 Rust tests within 173 PooleKernel tests;
- a five-receipt Rust host probe checked by an independent Python priority and operation oracle;
- two byte-identical selector-17 QEMU/OVMF runs with exactly 37 ordered markers;
- exact screenshot and PBP1 handoff equality;
- source audits for fixed storage, EOI ordering, private-stack execution, cleanup, and selector isolation;
- 30 ordered hostile-control categories;
- exact media, kernel, contract, input, and toolchain bindings.

## Claim boundary

PKSCHED3 proves bounded interrupt-deferred work only on the QEMU BSP profile. It does not prove arbitrary callbacks, timer wheels, driver or service consumption, AP dispatch, cross-CPU migration, ring-3 execution, address-space switching, complete per-task architectural state, physical hardware, the N12 exit gate, signing authority, release authority, promotion, or production readiness.
