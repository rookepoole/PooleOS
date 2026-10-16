# Native Process Authority

PPROC1, Cycle267. Contract frozen before qualification, 2026-10-11.
This is the bounded stop/inspection mechanism for USI-3, not a complete init,
shell, executable loader, start/restart interface, or usable ISO.

## Active Invariants

| ID | Predicate | Strongest planned verifier |
| --- | --- | --- |
| PC1 | Trusted grants bind full owner and target task/root generations; no raw task ID authority, self-control, user delegation or rights escalation | Rust hostile identity/rights tests and CPL3 denial controls |
| PC2 | Four global process leases, two per owner, checked nonwrapping generations; failure has no side effects; IPC quotas unchanged | Rust exhaustion/reuse tests, linked footprint and session regression |
| PC3 | PSABI1 calls17/18 accept only a handle and zero unused arguments; absent authenticated caller denies | ABI tests and native syscall execution |
| PC4 | Stop returns Again while pending; inspect Ok/1 means authority attached, Revoked/0 means detached, neither proves memory freed | Host state tests, exact native marker and actual PMM cleanup checks |
| PC5 | A pending stop is claimed once; validate owner, target and lease again immediately before effect on the quiescent BSP after current-slice accounting | Host invalidation/drop tests and native driver checks |
| PC6 | Revocation/death/reuse invalidates queued or claimed authority; dropped claims do not reissue; cleanup failures retain ownership | Host stale-permit tests, existing task cleanup regressions and native reclamation |
| PC7 | Authorized cancellation preserves an independent user process; target pages release only through existing owned retirement | Two fresh bounded native guests plus containment/session regressions |

The safe core never executes, schedules or frees a task. The architecture adapter
authenticates the caller using its owned trap/run. A stop permit is non-clonable;
it can be revalidated for a retained cleanup attempt until target retirement.
Claimed work is not silently requeued if its consumer drops it. Revoke releases
the lease, not the target's memory. Target death leaves a revoked observation
until owner death or trusted lease revocation. This consumes bounded quota.

The dispatcher must own the exact task incarnation exclusively, settle its
runtime accounting, restore the original kernel root and quiesce execution before
applying cancellation. A memory-reaped result requires successful Slot retirement,
scrubbing/release and scheduler teardown; capability detachment alone is insufficient.
SMP, arbitrary policy, executable trust, automatic retry supervision and a user
close/delegate operation remain open. Prepared, waiting and suspended cancellation
paths must be distinguished, not reported as interchangeable evidence.

## Design Reference

The [seL4 capability tutorial](https://docs.sel4.systems/Tutorials/capabilities.html)
and [TCB API](https://docs.sel4.systems/projects/sel4/api-doc.html) illustrate
explicit capability authority for thread control. PPROC1 is an original bounded
PooleKernel mechanism, not seL4 code, API compatibility, or inherited verification.
The existing PooleKernel owned cancellation/retirement and generation rules are
the implementation authority. No external reference qualifies this implementation.

## Qualification State

Two fresh native guests pass, plus the default containment/denial and six-process
console regressions. [Cycle267 evidence](checkpoints/cycle267-native-process-authority.md).
No real supervisor, shell or ISO is claimed.
Native contract: two fresh 120-second guests, each with two sequential lifetimes
of three private images and at most256 dispatches per round. First stop targets
a timer-suspended task; second targets an IPC waiter. The survivor must complete
1024 checked copies and exit100; controller must observe revocation and exit104.
Each round must return39 pages and scrub18 data pages. CR3 writes are exactly
twice dispatches plus one mandatory retirement flush for the cancelled image.
This corrects the new harness's initial missing-flush expectation, not the kernel
retirement rule; both failed guests and diagnostic values are retained.

All PC1-PC7 predicates pass within the specified host/native scope. Prepared-task
stop through this ABI, native owner-death/revocation during retained cleanup,
general restart and arbitrary teardown races remain unqualified. After cancellation
commits, the kernel's retained Slot/image owns cleanup even if the original stop
capability is later invalidated; a stale permit must not authorize another lifetime.
Current native unexpected cleanup failures halt with ownership retained. A resilient
supervisor needs explicit cleanup/retry policy and truthful completion observations.
