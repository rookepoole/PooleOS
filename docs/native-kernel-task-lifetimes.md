# PKLIFE1 Task Lifetimes

Cycle 158 advances `N12-CONCURRENCY-RECLAMATION-001`, N12.3, source section
031.3 and `ADD-N12-CONCURRENCY-RECLAMATION-001`. The existing requirement and
flag remain open. This is original, allocation-free `no_std` kernel code,
host-executed and freestanding-checked, not a new guest boot selector.

## Mandatory Physical Ownership

`Resources::new(space, payload, manager)` now acquires allocator retention for
the four-page root allocation and every distinct frame bound to the actual
inactive PKVM1 object. This includes frames with pending invalidations and
multiple virtual aliases. Retention is no longer an optional generic payload.
There is no public unretained constructor or mutable address-space escape.
Execution stacks and active PKVM3 roots are not covered by this contract.

The crate-private PKPMM group operation validates every handle, duplicate,
retention and metadata-exclusion condition before reserving a contiguous,
nonwrapping identity range or changing allocation records. A failure in the
last member leaves the first member unchanged. Group release also validates
every token before clearing any record; failure returns the entire owner for
retry, including after manager migration or identity mismatch. These are
serialized transactions under exclusive manager access, not hardware atomics
over the whole group, power-loss transactions or interrupt-safe allocation.

`into_parts(manager)` consumes an exclusive resource owner after scheduler
reclamation (or before admission), ends retention, and returns the inactive
PKVM1 object and original payload. It does not free pages or waive pending
unmap receipts. Dropping the resources or storage never releases their pages.
This remains a trusted-kernel ownership boundary: copyable low-level handles,
raw memory backends and duplicate PKVM1 metadata are not capabilities. No
global physical-manager uniqueness or protection against raw alias writes is
implied.

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
| TL8 | Every admitted root and bound/pending frame resists ordinary free | Mandatory group constructor; all-frame, alias and pending-invalidation tests |
| TL9 | Late acquisition/release failure cannot partially transfer retention | Sparse group, stale/duplicate/conflicting handle, wrong-manager and migration tests |

## Qualification

The existing `tools/qualify_native_reclamation_core.py` now emits a version 1.3
source-bound receipt that includes PKLIFE1. Nineteen core tests and twenty-four
lifetime tests run separately in both debug and optimized host profiles. Seven
compile-fail borrowing tests, 219 kernel regressions (13 retention tests), formatting,
host Clippy and freestanding x86-64 Clippy also run. Every subprocess has a
180-second limit; source hashes are checked before and after qualification.

The harness uses the actual PBP1 codec to initialize PKPMM7, materializes real
PKVM1 page-table words in bounded host-backed storage, moves AddressSpace into
the task controller, and verifies explicit unmap/invalidation/release after
reclamation. The page-table backend is simulated; no hardware TLB is tested.

A canonical linked build must reproduce the exact new digest frozen in the
qualifier. The initial build rejected the Cycle 157 digest as expected: the
kernel remains 517,784 bytes/144 pages but now has 1,305 relocations. Build ID
is `PKBUILD1-CYCLE158-N12-RETAIN-V002-0000000001`. Changed bytes require fresh
downstream boot evidence; the old aggregate pass is historical only. A matching
digest alone would not prove whether a function is reachable from a selector.
PKENTRY1 independently reproduces two identical clean linked/canonical builds
with 219 host tests and 43 rejection controls. The final canonical SHA-256 is
`18EDADA10E141DBADA8C95C1C0B3454696122C5E96C528F45E0AECE6ADD2F07D`.
The isolated Cycle 151 demo is left frozen, not relabeled as a PKLIFE1 demo.

## Remaining Work

1. Bind active PKVM3 roots, their data and architectural execution stacks to
   mandatory retention and scheduler context ownership. Inactive PKVM1 tables
   and bound frames are now mandatory, but arbitrary payload allocations are
   not enumerated. Replay the changed kernel's dependencies before any merge.
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
