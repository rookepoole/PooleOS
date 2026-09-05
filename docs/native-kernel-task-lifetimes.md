# PKLIFE1 Task Lifetimes

Cycle 152 advances `N12-CONCURRENCY-RECLAMATION-001`, N12.3, source section
031.3 and `ADD-N12-CONCURRENCY-RECLAMATION-001`. The existing requirement and
flag remain open. This is original, allocation-free `no_std` kernel code,
host-executed and freestanding-checked, not a new guest boot selector.

## Implementation

`native/kernel/src/reclamation/task_lifetimes.rs` composes the actual PKSCHED4
`SmpScheduler`, PKRECLAIM1 `Pool`, and PKVM1 `AddressSpace`. A task binding owns
the moved address-space object and payload, not a caller-supplied generation
claim. Pool owner labels derive from the controller's checked task generation
and the address space's PMM-backed root generation. Duplicate physical roots
are rejected within the namespace, including roots awaiting reclamation.

`Storage::attach` requires an exclusive borrow and permits one controller per
storage lifetime. The controller owns its scheduler and exposes no mutable
scheduler or raw pool handle. A scoped reader retains the storage borrow and
object pin independently of the controller's mutable borrow. Thus readers may
survive scheduler mutations and controller destruction, but storage cannot be
replaced while an accessible reader remains. The module forbids unsafe code;
it reuses the already-audited pool's storage and atomic implementation.

Creation validates task parameters before consuming finite pool generations.
Failures return the original address space and payload. A private rollback
also preserves those resources if the scheduler rejects unpublished admission.
Task generations use checked `u32` increments; pool generations never wrap.
TaskId remains a namespace-local lookup ID, not a capability or authentication.

Only Dead scheduler tasks with no pending scheduler transaction may retire.
Runnable or blocked cancellation removes queue ownership before retirement.
Remote dispatch retains ownership through pending-transfer and Running states;
the existing exact scheduler acknowledgement validation remains unchanged.
Local dispatch and explicit completion retire the resulting Dead task.
Never-activated cancellation uses a serialized activate/cancel pair inside the
controller; no dispatch, guest execution or callback occurs in that pair.

Retirement closes new pin admission. Existing readers remain usable. Reclaim
returns the actual resource object only after the final pin drops. A task slot
cannot be recreated while its previous resources are still retained, even when
the scheduler already says Dead. The new generation rejects stale IDs.

Shutdown permanently seals admission and new dispatch, but permits existing
acknowledgements, offline-probe rollback, cancellation, completion and reclaim.
A missing ACK or forgotten reader retains storage; no timeout fabricates
quiescence. Dropping the controller seals and abandons unreclaimed resources in
Storage. Exclusive Storage destruction may drop remaining Rust payloads, but
does not release their physical allocations. That path may leak physical
memory; it is not a production supervisor recovery strategy.

## Invariants

| ID | Required Predicate | Evidence |
| --- | --- | --- |
| TL1 | One controller owns every scheduler mutation in the namespace | Private scheduler/pool, exclusive one-shot attachment, borrow compile-fail test |
| TL2 | Actual address-space ownership and root generation remain bound | Moved PKVM1 values, root duplicate/released checks, actual PMM/VM harness |
| TL3 | Running, pending and nonretired resources cannot be reclaimed | Transfer, cancellation, bad-ACK, timeout and state tests |
| TL4 | Last reader release precedes ownership return and slot reuse | Four-reader test, pinned retirement, 128 exact recycle/destructor cases |
| TL5 | Failure does not lose payloads or grant ownership | Parameter, finite-budget, stale-ID, duplicate-root, pin-budget tests |
| TL6 | Shutdown or owner loss cannot force a pinned object free | Forgotten-reader, pending-shutdown, controller-drop and sealed-admission tests |
| TL7 | Host object evidence does not imply physical quiescence | Strict receipt fields, promotion mutation tests, explicit boundaries below |

## Qualification

The existing `tools/qualify_native_reclamation_core.py` now emits a version 1.1
source-bound receipt that includes PKLIFE1. Nineteen core tests and nineteen
lifetime tests run separately in both debug and optimized host profiles. Three
compile-fail borrowing tests, 206 unchanged kernel regressions, formatting,
host Clippy and freestanding x86-64 Clippy also run. Every subprocess has a
180-second limit; source hashes are checked before and after qualification.

The harness uses the actual PBP1 codec to initialize PKPMM7, materializes real
PKVM1 page-table words in bounded host-backed storage, moves AddressSpace into
the task controller, and verifies explicit unmap/invalidation/release after
reclamation. The page-table backend is simulated; no hardware TLB is tested.

A canonical linked build must still exactly reproduce the 513,680-byte kernel
SHA-256 `9029AEE51A4D557EF5B29945985E4A1F07C67DDE9C8C367C80BD1B9EDD9D409E`.
That confirms the new library slice is not yet reachable from a live selector.
The isolated Cycle 151 demo is left frozen, not relabeled as a PKLIFE1 demo.

## Remaining Work

1. Bind active address-space and physical-allocation ownership, not merely the
   inactive PKVM1 object. Existing PMM handles are copyable and PKVM1 permits
   metadata reconstruction; callers can still access those lower-level APIs.
   Namespace duplicate detection is not a global physical-ownership proof.
2. Join scoped object pins to the exact PKSMP5 alias revocation, acknowledged
   shootdown, CPU park, scrub verification and allocator-release path. A Dead
   task, scheduler ACK, offline label or zero Rust pins is not a CPU grace period.
3. Add an independent lifecycle oracle, a live selector, two immutable runs,
   stalled/stale-ACK and partial-failure cases, rollback, interrupt/preemption
   boundaries and acknowledged shutdown. Never force release to make progress.
4. Extend beyond this four-CPU/eight-task serialized controller only after the
   bounded integration passes. General RCU, epochs, hotplug, shared process
   address spaces, ring 3, capability authority, interrupt-safe allocation,
   target hardware, N12 exit and production remain unqualified.

The removal/reclamation distinction follows the
[kernel RCU design reference](https://docs.kernel.org/RCU/whatisRCU.html), not
Linux implementation code. Rust's
[UnsafeCell aliasing contract](https://doc.rust-lang.org/core/cell/struct.UnsafeCell.html)
continues to constrain the underlying pool. Reviewed 2026-09-04. No third-party
code or dependency was added.
