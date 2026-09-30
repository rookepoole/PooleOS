# Cycle 201: Current-Kernel Scheduler and Preemption Replay

Date: 2026-09-29. Pre-production; not full-canonical or main-merge qualification.
Parent: `8612c2b337be336400870d75e1a16e06fcf47d25`.
Selected: `N12-SCHED-001`, then `N12-SCHED-PREEMPT-001`, supporting
N12.1/N12.2/N12.5/N12.6/N12.7 and N36 under existing
`ADD-N36-RECEIPT-COVERAGE-001`.

## Measured Execution

Two profiles pass four fresh virtual boots, 53 control groups and 341 executed
rejection cases. Both qualifiers pass the same 246 kernel host tests; repeated
execution does not multiply distinct coverage. No failed or superseded guest
runs occurred this cycle. Each generated receipt was admitted only after its
runtime validator and actual aggregate gate passed. Earlier receipts remain
available in Git history and local archives; no old evidence was rebound.

| Profile | Boots | Groups | Cases | Receipt SHA-256 |
| --- | ---: | ---: | ---: | --- |
| scheduler | 2 | 28 | 115 | `FF5A23F5D19B5D009BC5D9823CBB29D0B74343684D5AE4D051345D3AF0A5D7E8` |
| scheduler_preempt | 2 | 25 | 226 | `00F89E715A57EB75F734C8C4E26E5867614E061EF1BD4DF3575FDA439F4D0750` |

Scheduler execution verifies two live tasks, eight dispatches, sixteen machine
transitions and 32,768 cleared stack bytes. Its independent 4,096-step host
stress trace records 1,761 dispatches and 2,334 modeled migrations; those
migrations are not live cross-CPU execution. Preemption verifies four live
tasks, six timer ticks and EOIs, four interrupt-frame switches and 65,536
cleared stack bytes. Both remain bounded BSP profiles, not ring-3 scheduling,
general per-task architectural state or general CPU retirement.

Kernel bytes remain 530,072 canonical bytes and 602,112 loaded bytes, with
1,326 relocations and build `PKBUILD1-CYCLE197-N12-DEFERRED-V1-0000000001`.
Kernel SHA-256:
`B19D4F7E854ECED3495D88C00F7379061B913EF00477FBD3701929B2F77D80F1`.
Unchanged entry receipt:
`70814DA7358BEE6FA6E5D2341D251ACE57A906BA4FB2E9E12BD8D53677C7E38D`.

Scheduler qualifier: 135.797 seconds, log
`A05D356DCFD64DA45E0725945AEE1EEB96E15E160E1589353424DC46CA535D20`.
Preemption qualifier: 123.453 seconds, log
`C4CA732801FB906F7442652BE154022EA0C59C4E633C31145D785E2F4E5A52F5`.

## Adversarial Regression

All 31 focused tests pass with zero skips in 35.797 seconds. Runtime and actual
gate reject 453 malformed recorded-evidence cases: 221 scheduler, 206 generic
preemption and 26 additional preemption-control cases. Native preemption
controls execute 50 rejection cases; linked-switch and retained-stack audits
exercise three and four cases respectively. Tests detect seven deliberately
disabled native checks and two disabled auditors. Host-only fault injection
and linked/source audits are not physical hardware faults. Source and owner
snapshots remain unchanged throughout each bounded worker.

Focused log SHA-256:
`34BE546EFB85C71B4DE8BF7E0642F771333FB650B4F982B7193A17D0191A3985`.
These test and control counts overlap; they are not summed as distinct tests.
Recorded consistency is not authenticity, freshness, independent-builder
attestation or proof against coherent forgery.

## Remaining Work

The initial metadata regression passed 45/48. Three assertions retained old
scheduler-entry freshness, remaining-profile count and next-move expectations.
They are reconciled to current evidence without modifying historical records.
The failure is metadata reconciliation, not a guest or native-runtime failure.
Initial metadata log:
`4E6A21C3CFD6738F996D004E6EF6D20DBA28EEC4E68995A4BD95E03F15AD1428`.
A second metadata run passed 47/48 and exposed a later assertion in the entry
test that still expected 19 current checks instead of 21. That assertion is
also reconciled; its original failure log is preserved:
`F84FEF323F093C515FA73D17D1E3538094EB3186A439A563A5CBE19E7AAC06ED`.

Repaired metadata passes 48/48 with zero skips in 18.328 seconds, log
`9DC0D60BA092B1F648F84F6CDDFB653349B17436AE6087717141488191CA0350`.
The combined scoped regression passes 128 tests with zero skips in 171.172
seconds. It covers entry/core, deferred transactions, IRQ, scheduler/preemption,
publication and metadata, including 21 native deferred tests in debug and
optimized builds. Source and owner snapshots stayed unchanged during execution.
Combined log:
`AFBC14EF6CB5715473F8ED9739AD8A5A3B5B08721B3272B7712922CC4CDC417D`.
Initial conservation passes with 17 archived parent records and 327 bindings.
The combined run preceded result recording; final metadata is checked separately.
These overlapping scoped checks do not replace full canonical qualification.

Selected readiness is 21/27. Next: `N12-SCHED-DEFERRED-001`. Repair the known
recorded-admission defects and replace its 14 constant-only control groups
with individually executed negative cases before generating a new receipt.
Then qualify SMP scheduling, AP workers, SMP preemption, atomics and locks.
The aggregate lower bound of 65 unproven control groups remains open; this
cycle replays already repaired preemption coverage rather than closing those
later gaps. Full exact-candidate canonical/Doctor/release/publication/configured
GitHub checks and review qualification still precede main merge.

Six memory/IRQ/SMP profiles remain current Cycle 200 evidence. CPU/boot/core
records retain their earlier execution cycles. All 17 parent current-record
snapshots are archived under Cycle 200 without changing older history. No phase
or flag closes: 40 phases, 301 subphases, 8,996 requirements, 57 additions,
94 flags (36 open), and 20 gaps remain accounted for. The 1,072 discovered
Python tests are inventory, not a full-suite pass.

N0 custody and signatures, N5 authenticated boot and persistent trust state,
general live task/CPU retirement, PooleGlyph Phase 66, independent builders,
physical-target evidence and production remain open. The native sources,
locked checklist and coverage, normative charter, owner-modified PooleGlyph
report, unrelated receipts and existing demo ISO are preserved.

No new native feature, key use, signature, driver load, firmware/media operation,
tag, release, new ISO or production promotion is claimed. This is a development
checkpoint for PR #78; main remains qualified `ac15d1d`. Ignored raw logs,
tools, temporary directories and local ISO output are outside the Git backup.
