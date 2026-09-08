# PKRECLAIM1 Core

Cycle 152 adds [PKLIFE1 task lifetimes](native-kernel-task-lifetimes.md): actual
PKSCHED4 scheduler ownership and moved inactive PKVM1 address spaces, protected
by this pool. Nineteen additional tests pass in each host profile and two more
borrow compile-fail cases pass. The current source-bound receipt is version
1.1. This advances the first remaining integration step below only for the
serialized inactive-address-space scope; live CPU quiescence remains open.

Cycle 150 advances `N12-CONCURRENCY-RECLAMATION-001`, N12.3, source requirement
031.3 and `ADD-N12-CONCURRENCY-RECLAMATION-001`. The requirement and flag remain
open. This is original `no_std` PooleKernel code with host execution evidence,
not a new live boot selector, allocator integration, CPU grace period or
production memory-safety certification.

## Mechanism

`native/kernel/src/reclamation.rs` owns a fixed array of actual Rust values.
The existing PKLOCK1 ticket lock serializes short metadata operations through
its nonwaiting try path. PKATOM1 counters track outstanding scoped reader pins.
There are no heap allocations, arbitrary callbacks or destructors under the
gate. Contention returns `Busy`; this profile has no fairness or wait-free
guarantee. Pin destruction uses one release RMW without acquiring the gate.

Each slot follows `Free -> Live -> Retired -> Free`. Publish transfers T into
the pool. Pin admission is possible only while Live. Retire closes admission
without invalidating existing pins. Reclaim transfers T back to the caller
exactly once, only after an acquire load observes zero outstanding pins.
The caller, outside the metadata gate, chooses when to run T's destructor.

Opaque handles borrow their pool and bind its identity, slot and generation.
They cannot be forged through the safe API, applied to another pool, or used
after slot reuse. A handle does not itself retain the object. Dereferencing
requires a non-cloneable scoped pin. Generations never wrap; exhausted slots
are withheld permanently. Configurable positive pin and generation budgets
make exhaustion testable without changing arithmetic semantics.

Task and address-space generation labels are checked on retire and reclaim.
These are trusted caller labels, NOT capabilities, authentication, scheduler
registration or proof that another CPU stopped accessing mapped memory.
Pins may cross host threads when T is Send + Sync; they are not CPU-local
tokens. No integer handle ABI or raw pointer escape is provided.

## Safety Invariants

| ID | Predicate | Verification |
| --- | --- | --- |
| RC1 | Only initialized Live/Retired slots own T | State-transition tests, exact-once destructor tests, unsafe-block audit |
| RC2 | Every accessible payload borrow retains a counted pin | Opaque RAII guard, compile-fail lifetime test, four-reader retirement test |
| RC3 | Retirement excludes new pins before zero-count reclamation | One metadata gate, release/acquire counter ordering, final-drop race |
| RC4 | Pool and slot reuse cannot revive an old handle | Borrowed pool identity, monotonic generations, foreign/stale/exhaustion tests |
| RC5 | Failed admission preserves value and existing ownership | Owner, capacity, pin-budget and shutdown tests |
| RC6 | Pressure and shutdown never force a pinned object free | Retention, forgotten-pin and drain tests |
| RC7 | Host evidence cannot close live or production gates | Exact-source receipt validation and promotion-mutation tests |

UnsafeCell metadata and payload storage are separate: an exclusive metadata
borrow cannot alias a payload reference. Only the gate holder increments pin
counts; concurrent decrements cannot invalidate the preflight overflow bound.
Retired slots admit no new readers, and the acquire zero-load observes the
release sequence of prior pin drops. T must be Send + Sync for shared pool
access. Exclusive pool destruction drops remaining initialized values; a
forgotten pin cannot subsequently be accessed. If a payload destructor panics
during pool destruction, remaining values may leak, not become double-freed.
The production kernel still aborts on panic; unwind recovery is host-only.

Shutdown permanently seals publish and pin admission but permits outstanding
pins to finish and owners to retire/reclaim. Drained means sealed and all slots
Free. Forgotten pins, dead readers or CPUs that never acknowledge teardown
retain their objects. Timeout, pressure or an offline label cannot clear pins.
This chooses retention over unsafe reuse; eventual reclamation is not promised.

## Qualification

Current Cycle 158 qualification is recorded by the version 1.3 receipt and
`docs/native-kernel-task-lifetimes.md`: 19 core tests, 24 lifetime tests, 219
kernel tests (13 retention cases) in both host profiles, seven compile-fail
checks, formatting and host/freestanding Clippy. Mandatory retention now covers
inactive task tables and all bound/pending frames. The identified image has
SHA-256 `18EDADA10E141DBADA8C95C1C0B3454696122C5E96C528F45E0AECE6ADD2F07D`.
Its changed bytes require fresh downstream qualification. The canonical audit
fails 25/105 checks; no current full-suite pass or live reclamation is claimed.

The following describes the historical Cycle 149/152 qualification, not the
current runner's counts or expected image:

Run with the repository's pinned Python and Rust toolchain:

```text
python tools/qualify_native_reclamation_core.py --work outputs/reclamation-core-fresh-run
python -m unittest tests.test_native_reclamation_core
```

The runner retains raw logs locally, binds source SHA-256 values before and
after execution, enforces a 180-second limit per command, and emits
`runs/native-kernel-reclamation-core-readiness.json` only after all stages pass.
It runs 19 core and 19 task-lifetime tests in debug and optimized host profiles,
three borrow compile-fail tests, 206 preexisting kernel regressions, formatting, host Clippy and
freestanding x86-64 Clippy with warnings denied. A canonical linked-kernel
rebuild must also retain the exact
513,680-byte Cycle 149 SHA-256
`9029AEE51A4D557EF5B29945985E4A1F07C67DDE9C8C367C80BD1B9EDD9D409E`;
otherwise previous live receipts cannot be inherited. Host stress covers four
readers, 128 recycle generations, admission/retire races, one-winner concurrent
reclamation, and a last-drop ordering check before thread join. This is finite
host evidence, not exhaustive interleaving exploration or weak-memory proof.

Cargo integration-test discovery tries to link the freestanding kernel bin for
Windows, which cannot unwind. The runner instead uses pinned rustc's test
harness against the exact Cargo-built library. Optimized host tests explicitly
use unwind-compatible libraries; the override is removed before freestanding
checks. No production panic profile or system-wide environment is changed.

## Remaining Work

1. Extend the implemented scheduler/inactive-task retention to active roots
   and architectural execution-stack lifecycles.
2. Couple retirement to acknowledged cross-CPU quiescence, alias revocation,
   TLB shootdown and complete park/scrub/release ordering on the frozen topology.
3. Qualify timeout, cancellation, offline/death, memory-pressure and shutdown
   sequences, including late or stale acknowledgements and rollback.
4. Add an independent state oracle, live selector and immutable two-run evidence
   before closing `FLAG-N12-CONCURRENCY-RECLAMATION-001` or N12.3.

No general RCU, epochs, hazard-pointer algorithm, hotplug, raw-reference
reclamation, physical hardware, N12 exit or production claim is made.

## Design References

The removal/reclamation distinction is informed by the
[Linux RCU design explanation](https://cdn.kernel.org/doc/html/latest/RCU/whatisRCU.html).
Linux is a design reference, not an implementation dependency. This core uses
scoped object pins because the current scheduler has no general grace-period
contract; it does not implement Linux RCU.
Rust's [UnsafeCell rules](https://doc.rust-lang.org/core/cell/struct.UnsafeCell.html)
and [MaybeUninit ownership rules](https://doc.rust-lang.org/core/mem/union.MaybeUninit.html)
govern payload aliasing and exact-once ownership transfer. Reference review:
2026-09-04. No external code was copied or dependency added.
