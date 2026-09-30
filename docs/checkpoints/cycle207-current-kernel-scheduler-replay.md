# Cycle 207: Current-Kernel Scheduler Replay

Status date: 2026-09-30. Execution began September 29; original receipt dates are
retained. Pre-production, single-host virtual qualification.

## Scope

`N12-SCHED-001`, followed by `N12-SCHED-PREEMPT-001` and
`N12-SCHED-DEFERRED-001`, supports N12.4-N12.7 and N36 under
`ADD-N12-SCHED-FOUNDATION-001`, `ADD-N12-SCHED-PREEMPT-001`,
`ADD-N12-SCHED-DEFERRED-001` and `ADD-N36-RECEIPT-COVERAGE-001`.
Entry readiness was 19/27. The three profiles execute the unchanged Cycle 203
kernel; no native source, entry/core, boot204, CPU205 or memory206 receipt changed.

## Fresh Evidence

| Profile | Receipt SHA-256 | Boots | Control Groups | Executed Cases |
| --- | --- | ---: | ---: | ---: |
| Cooperative scheduler | `57048B311D72A5F86677FF6D81B81584A7DECE90AD316DFA4775B5EA9A3149E7` | 2 | 28 | 115 |
| BSP preemption | `8E3EEDDB9C0DFA7270CED165084289E1CE4D96C880BE797D6E0EE2B7EAB3AA14` | 2 | 25 | 226 |
| Deferred work | `FAC1F18E866A871BFEF1F3569CB2667F5FDA36656FC9B0F4384F474C80AB0507` | 2 | 30 | 254 |

Six fresh QEMU/OVMF boots, 83 control groups and 595 executed cases pass. The
case total includes 545 rejection cases and 50 deferred native boundary cases;
it is not 595 independently injected live-guest faults. Each qualifier embeds
the exact current entry receipt with 246 kernel host tests.

Cooperative scheduling executes eight dispatches and sixteen transitions across
two tasks, then clears 32,768 stack bytes. Its Rust/Python host oracle agrees over
4,096 steps, 1,761 dispatches and 2,334 modeled migrations. BSP preemption records
six timer ticks/EOIs, four interrupt-frame switches and 65,536 cleared stack bytes.
Deferred work records eight enqueues, duplicate suppression, six worker dispatches,
queued/running cancellation, flush receipts, five rollbacks with zero leaked slots,
eight free slots at shutdown and 32,768 cleared stack bytes. All remain bounded
BSP diagnostics, not general live task-stack ownership or cross-CPU retirement.

## Preserved Failure

The deferred qualifier and runtime validator passed, but initial aggregate
admission failed with `PKSCHED3 host oracle, source, or linked switch audit changed`.
The serial chain exited 1 because the gate still pinned Cycle 197's image.
Before/after audits preserve the same `FAC1F18E...AB0507` candidate. Updating the
aggregate pin to the independently reproduced Cycle 203 image admits those
unchanged guest bytes. No boot failed or was rerun, and no failed receipt was
accepted. Eleven independent gate cases reject prior/malformed hashes and stale
relocation counts, after the genuine positive passes without mocked validators.

The initial metadata regression passed 50/54 tests. Four current-state assertions
still expected 19/27 or stale scheduler entry evidence. They were corrected to
the measured 22/27 state and exact embedded entry identity; historical hashes and
records remain unchanged. Failed log SHA-256:
`E983C8747B345AA880FEDCE28FAB581D7FC0EAFCB60CCFE9971A4DA4268AA4B4`.
The next run passed 52/54, exposing two later count assertions in those same
tests; they were also reconciled to measured evidence. Its failure log is
`BA5BB5C047FA0AA1EDEDEEA6FB2AEEF1E062A38FB949298E4C549793F5FC3B81`.

## Regression

All **47/47 focused tests** pass with zero skips in 60.817 seconds; bounded runner
elapsed time is 61.703 seconds. Log SHA-256:
`8DF6223B8326D98D78E51DE13ABFE1C82BB06B32DF9EB5BD9583DB0561DDD272`.
Runtime and real aggregate gates reject 768 recorded corruptions: 700 generic
cases plus 26 preemption and 42 deferred control-receipt cases. Tests detect seven
disabled preemption variants, twelve disabled deferred variants, disabled
validators/auditors and the eleven independent linked-identity mutations. Counts
overlap. Unsigned consistency is neither authentication nor exclusion of coherent
forgery. Source and owner data remained unchanged during each bounded execution.

The full cross-profile dependency and entry-provenance suites are still pending
with five stale downstream profiles; no positive test was weakened to admit them.

## Broader Verification

Combined scoped regression passes **166/166**, zero skips, in 218.638 seconds
(runner 219.563 seconds); log SHA-256:
`21FAA36012EBC2A7B1E1FA7C4099C98AFC921C5C06B84BAA62696244C70CAF3E`.
It includes scheduler controls, native SMP/deferred transaction tests in debug
and optimized profiles, entry reproduction, core, host provenance, boot/memory/
CPU aggregate gates, publication and metadata. It does not rerun all unchanged
CPU/memory corruption suites or the five pending downstream profiles.

Repaired metadata passes 54/54, zero skips, in 29.067 seconds (runner 29.844);
log SHA-256 `DF2EE4A647ACDF119B15D1449DA9C3A5F0E078BD6D8A4CA49EEBE0D102A0CD57`.
Conservation verifies 348 source bindings, 19 unchanged archived progress records,
prior checkpoint/native/entry/core/boot/CPU/memory bytes, locked checklist, owner
data, normative charter, demo ISO and every phase/flag status. The 1,090 discovered
tests are inventory, not full execution. Counts overlap; these results do not
establish full canonical qualification or main-merge eligibility.

## Frozen Inputs

- Build ID: `PKBUILD1-CYCLE203-N12-SMP-TXN-V1-00000000001`.
- Canonical kernel: `A943DCB6E41A27F952868F05ED2B3523B47D9D7A7B5DB909EE385205F7CA3B31`.
- Linked kernel: `557687A9F39EEECFFD839A8619D696CEBB4E391B229778162725752C72B4D9AA`.
- Entry receipt: `E90F11157F3416CE2C78650C4605ADF92BF5D7AC19A293E0C105499EF17276A5`.
- Core receipt: `33EE501601ACB8109FA867C2634FAC1C04F43505B4DD6C6D75821545B120BDD8`.

PooleGlyph Phase 65 is still newest. Its manifest/ZIP and the owner's modified
conformance report remain unchanged; Phase 66 Core IR integration remains open.

## Remaining Gates

Selected current-image readiness is **22/27**. Five profiles remain: SMP
scheduling, AP workers, SMP preemption, atomics and locks. `N12-SCHED-SMP-001`
must repair recorded admission and replace its sixteen constant-only controls
with executed evidence before fresh qualification. The existing lower bound of
51 unproven control groups remains: 16 SMP, 18 AP-worker and 17 SMP-preemption.

No phase/flag closure, N12 exit, general task/CPU retirement, physical-hardware
qualification, second builder, new ISO, signing, firmware/media write, release
or production promotion follows. Exact-candidate full canonical/Doctor, release,
publication and GitHub check/review gates still precede main merge. Branch cloud
backup is separate. Next is SMP recorded admission and executed-control work.
