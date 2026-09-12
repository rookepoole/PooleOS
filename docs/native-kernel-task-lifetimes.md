# PKLIFE1 Task Lifetimes

Cycle 177 advances `N12-CONCURRENCY-RECLAMATION-001`, N12.3, source section
031.3 and `ADD-N12-CONCURRENCY-RECLAMATION-001`. The existing requirement and
flag remain open. This is original, allocation-free `no_std` kernel code,
host-executed and freestanding-checked, not a new guest boot selector.

## Mandatory Physical Ownership

`Resources::new(space, stack, payload, manager)` acquires allocator retention for
the four-page `PKSTACK1` inactive stack, the four-page root allocation and every distinct frame bound to the actual
inactive PKVM1 object. This includes frames with pending invalidations and
multiple virtual aliases. Retention is no longer an optional generic payload.
There is no public unretained constructor or mutable address-space escape.
The stack must have owner label `0x1701` and exactly four pages. Retention is
acquired in the same transaction as the tables and frames, not after admission.
This contract covers prepared inactive stack storage, not guarded mappings,
architectural context activation or active PKVM3 root/context integration.

The crate-private PKPMM group operation validates every handle, duplicate,
retention and metadata-exclusion condition before reserving a contiguous,
nonwrapping identity range or changing allocation records. A failure in the
last member leaves the first member unchanged. Group release also validates
every token before clearing any record; failure returns the entire owner for
retry, including after manager migration or identity mismatch. These are
serialized transactions under exclusive manager access, not hardware atomics
over the whole group, power-loss transactions or interrupt-safe allocation.

`into_parts(manager)` consumes an exclusive resource owner after scheduler
reclamation (or before admission), ends table/frame retention, and returns the
inactive PKVM1 object, an exclusive non-Copy `InactiveStack` owner and the original
payload. The stack remains retained until `release_scrubbed(manager, access)`
verifies complete zeroing/readback and commits a scrub receipt. Failure returns
the stack owner for retry. No page free or pending unmap receipt is implied by
`into_parts`. Dropping or forgetting resources or the stack owner retains pages.
This remains a trusted-kernel ownership boundary: copyable low-level handles,
raw memory backends and duplicate PKVM1 metadata are not capabilities. No
global physical-manager uniqueness or protection against raw alias writes is
implied.

## Implementation

`native/kernel/src/reclamation/task_lifetimes.rs` composes the actual PKSCHED4
`SmpScheduler`, PKRECLAIM1 `Pool`, and PKVM1 `AddressSpace`. A task binding owns
the moved address-space object, retained inactive stack and payload, not a caller-supplied generation
claim. Pool owner labels derive from the controller's checked task generation
and the address space's PMM-backed root generation. Duplicate physical roots
are rejected within the namespace, including roots awaiting reclamation.
Overlapping stack physical page ranges also reject, including different root
allocations from distinct manager namespaces. Reclamation must release the old
binding before its stack range can be admitted again in that scheduler.

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
returns the actual resource object only after all ordinary readers and explicit
execution holds release their pins. A task slot
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
| TL10 | Copied stack identity never grants ordinary allocator release | Mandatory table/frame/stack transaction, readonly owner access and copied-free tests |
| TL11 | Scrub or receipt-capacity failure retains the exclusive stack owner | Seven write/read/corruption fault cases, wrong-manager check and 16/17 receipt-capacity boundary |

## Dispatch Execution Ownership

PKEXEC1 `Dispatch` is an opaque, non-Copy, non-Clone ticket plus resource pin.
`TaskLifetimes::stage_dispatch` preflights admission and acquires that pin before
mutating the runnable queue. Its `resources()` view names the actual retained
root, stack and payload. A copied `ticket()` remains only scheduler protocol
identity, not reclamation authority.

Scheduler completion may retire the task, but the execution pin stays held.
Dropping, forgetting or unwinding a Dispatch deliberately retains its reader.
Only consuming unsafe `confirm_quiescent` releases it. The architecture caller
must prevent every current and future CPU use of the context, root and stack,
revoke resumable contexts and aliases, and complete applicable invalidations.
An ACK, Dead state, timeout or offline label does not discharge that obligation.
For unpublished work, the caller must also prevent later publication.

The handle does not pin Storage's address or enumerate allocations inside a
generic payload. Stable architectural storage and raw-pointer validity remain
separate adapter obligations. No guest selector or hardware handoff consumes
Dispatch yet. Host tests invoke the unsafe boundary only where no CPU or
external context ever acquired the resources.

Read-only scheduler admission also preflights transaction and equal-priority
bypass counter exhaustion. Both previously reproduced partial-queue-mutation
failures now reject before mutation. This is a dispatch-specific guarantee.

## Cycle 177 Qualification

The schema 1.6 core receipt binds 30 source inputs. All 17 stages pass, including
245 kernel tests, 40 lifecycle tests per debug/release profile, 19 pool tests
and 15 compile-fail cases. Six explicit execution tests exercise retained stack
storage and full scrub, three lost-handle modes, pin exhaustion, invalid
admission, independent CPU holds and stale-generation ACK rejection. Thirty
parser controls reject missing, duplicate, failed, ignored or relocated cases.

The canonical kernel changes to SHA-256
`563ED1976CAB4DA773BAE9BCE49F370242C893760E7C221239C1B31F44D969CA`.
Its final core receipt is
`7E289FE30319EA9577C66716FE31EB02600E779D8F0E380172D3C3C708900A71`.
Only 2/27 selected native readiness checks remain current; entry and downstream
replay begin at `N6-KENTRY-001`. There is no new guest, hardware, general CPU
quiescence or full-candidate qualification claim.
[Cycle 177 evidence](checkpoints/cycle177-dispatch-execution-holds.md).

## Historical Cycle 172 Qualification

The existing `tools/qualify_native_reclamation_core.py` emits a version 1.5
source-bound receipt that includes PKLIFE1 and PKSTACK1. Nineteen pool tests and
34 lifecycle tests run separately in both debug and optimized host profiles.
Eleven compile-fail borrowing tests, 243 kernel regressions (20 retention and
11 AP-resource cases), formatting, host Clippy and freestanding x86-64 Clippy
also pass. Every subprocess has a
180-second limit; source hashes are checked before and after qualification.

The harness uses the actual PBP1 codec to initialize PKPMM7, materializes real
PKVM1 page-table words in bounded host-backed storage, moves AddressSpace into
the task controller, and verifies explicit unmap/invalidation/release after
reclamation. The page-table and physical-access backend is simulated; no hardware
TLB or CPU stack activation is tested. All 16,384 stack bytes are zeroed and
read-verified before successful release. The 128-generation scheduler test uses
a fresh fully drained manager per eight-task batch; it does not establish an
unbounded receipt ledger. A separate test proves 16 successful scrub releases
and rejection of the seventeenth without physical writes or ownership loss.

The 17-stage Cycle 172 qualifier rebuilds the same 530,072-byte linked kernel,
SHA-256 `8A2DA65C86B09F7BCF2D5ACDB90029A5B7B7361581BA841ADC3B62AEE168B625`.
No new guest selector calls this generic task-resource code. Twenty-seven
selected native receipt checks pass by source/current-image revalidation; no
new QEMU execution is claimed. Full current-candidate qualification remains a
separate merge gate. [Cycle 172 evidence](checkpoints/cycle172-task-stack-ownership.md).

## Historical Cycle 158 Qualification

Cycle 158's version 1.3 receipt ran 19 pool and 24 lifecycle tests per profile,
219 kernel regressions, 13 retention cases and seven compile-fail tests.

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

1. Join the prepared inactive stack owner to guarded mappings, active PKVM3
   roots/data and actual scheduler architectural contexts. Bounded active-root
   and AP ownership exists separately; it is not general task CPU retirement.
   Inactive tables, bound frames and stack storage are mandatory here, but
   arbitrary payload allocations are not enumerated.
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
5. Integrate existing PMM receipt-ledger growth/migration and pressure handling
   with stack release. The fixed-backend capacity test proves retention on
   exhaustion, not automatic growth or eventual reclamation under pressure.

The removal/reclamation distinction follows the
[kernel RCU design reference](https://docs.kernel.org/RCU/whatisRCU.html), not
Linux implementation code. Rust's
[UnsafeCell aliasing contract](https://doc.rust-lang.org/core/cell/struct.UnsafeCell.html)
continues to constrain the underlying pool. Rust's
[forget contract](https://doc.rust-lang.org/core/mem/fn.forget.html) permits safe
code to omit destructors, so releasing allocator retention must not depend on a
destructor running. RCU and forget references reviewed 2026-09-09; no third-party
code or dependency was added. This is not a Linux production dependency.
