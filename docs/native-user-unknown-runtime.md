# Unmeasured Dispatch Recovery

PKUSER15, Cycle249, development-only, one BSP with interrupts disabled in the
supervisor. This extends PKUSER13 accounting; it does not recover a broken clock.

## Mechanism

`Slot::run_slice` already quarantines the exact CPU image and driver before entry.
A valid returned slice is retained before cleanup; otherwise accounting stays
unknown. `Slot::account_unknown` now records that missing dispatch atomically in
its running PKSCHED1 task. Both identities, CPU, dispatch ordinal and previous
measured subtotal must agree. The operation adds no ticks and no application
outcome. Replays, valid pending samples and stale/foreign identities reject.

The slot stays quarantined. Its `unmeasured_slices` and the scheduler's
`unmeasured_dispatches` are nonzero; measured ticks are only a subtotal. Current
task operations cannot yield, block, acquire a mutex or add another charge.
The scheduler owner remains current until the caller completes cleanup and
tears it down. This is a trusted kernel orchestration contract, not authority
granted by a numeric task ID. Existing measured-only and legacy paths are not
silently enrolled into this new accounting profile.

Ordinary `abandon` becomes available only after the missing sample is recorded.
It must still stop/drain the owned devices, detach entry state, restore and
verify the original root with a flushing CR3 write, then detach memory ownership.
Every failed cleanup step retains its owner for retry. The native supervisor
scrubs/unmaps/releases that returned owner before scheduler teardown. A dead
scheduler snapshot retains the unknown count until the slot is explicitly reused
with a newer generation. Durable per-generation audit history remains future work.

## Invariants

All rows are ACTIVE, derived from ownership/accounting safety and the integration
acceptance contract. Host tests and fresh exact-binary guest records are distinct.

| ID | Predicate | Verification |
| --- | --- | --- |
| U1 | Missing time is never converted to zero or an estimate | Host subtotal cases; native `total0=unknown`; JSON null |
| U2 | Only a quarantined owner with no valid pending sample may settle unknown | Slot state and pending-sample host tests |
| U3 | CPU, generation, dispatch ordinal and prior subtotal agree before mutation | Host adversarial cases; native stale/CPU denial |
| U4 | Settlement is exact-once and failure-atomic | Host snapshots/sequence; native replay denial |
| U5 | Unknown tasks cannot resume or requeue | Slot state; scheduler current-operation guard; native denials |
| U6 | Settlement itself releases nothing | Host retained-PMM assertions; native five free denials |
| U7 | Device/root failures retain ownership through retries | Host quiescence and after-effect CR3 failure; native pending IRQ retry |
| U8 | No successful application result is invented | Outcome/reap denial; termination-only abandonment |
| U9 | Healthy peer runs after retirement; pages and roots balance | Fresh native progress, exit84, allocator/root-write checks |
| U10 | Existing cases and ordinary unsigned denial remain intact | Two fresh61-marker guests plus ordinary-denial control |
| U11 | New construction does not nest two large probe stack frames | Non-inlined sibling calls, host structural regression, fresh native replay |

## Alternatives And Limits

Zero/estimated time was rejected because it fabricates a measurement. Permanent
pinning remains the fallback if cleanup cannot establish quiescence, but is no
longer mandatory merely because a sample was lost. Scheduler teardown before
hardware cleanup was rejected because it can expose a peer while the old root
or interrupt owner is still active. Combining all cleanup inside scheduler
accounting would couple scheduler policy to device/root ownership; the existing
retained-owner transaction remains the narrower mechanism.

The native fault injection discards a sample only after a real authenticated
CPL3 quantum returns. It also causes an actual pending-local-IRQ drain failure,
then retries while the exact root, descriptors, timer and13 pages remain owned.
It does not simulate a successful application exit and is not a physical HPET
failure, arbitrary corrupted trap, IF0 hang, NMI recovery or persistent restart
journal. Architectural clock/entry failures that cannot safely return still
fail closed. Earlier PKUSER13/14 marker totals describe the first16-case measured
suite; the separate PKUSER15 marker records one unmeasured dispatch and its
healthy peer. They must not be presented as a complete global time total.

The next implementation is original kernel-owned capability tables and bounded
IPC, not additional boot artwork. Reference-only review of the official
[seL4 capability tutorial](https://docs.sel4.systems/Tutorials/capabilities.html)
supports the distinction between an object, rights and a handle resolved in the
calling task's capability space. No seL4 code, ABI or production foundation is
adopted. PooleOS's own N13.5-7/N14.1-3,5-7 requirements remain authoritative.

See [Cycle249 evidence](checkpoints/cycle249-unknown-runtime-recovery.md).
