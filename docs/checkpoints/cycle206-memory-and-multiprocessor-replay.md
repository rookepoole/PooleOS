# Cycle 206: Current-Kernel Memory and Multiprocessor Replay

Status date: 2026-09-29. Pre-production, single-host virtual qualification.

## Scope

`N9-PMM-ACPI-CONSUMER-001`, N9.1/N9.2, followed by N9.3/N9.4 and dependent
N8.1/N8.3/N8.5/N8.6, supporting N10/N36. Requirements: `ADD-MEM-001`,
`ADD-TIME-001` and `ADD-N36-RECEIPT-COVERAGE-001`. Entry readiness was 13/27.
Six fresh profiles execute the unchanged Cycle 203 kernel. No native source,
entry/core receipt, prior boot/CPU receipt or demo ISO changed.

## Fresh Evidence

Each receipt contains two successful QEMU/OVMF boots and current entry evidence
with 246 kernel host tests. Counts below describe executed controls in each
qualifier, not proof of complete production behavior.

| Profile | Receipt SHA-256 | Controls | Cases |
| --- | --- | ---: | ---: |
| Physical memory | `83129AB1A6AC4CBACD2C55DC45B8564BC7C21D9571508405A931978C4E0E8A40` | 191 | 191 |
| Virtual memory | `23EFB1654F8EF006C19DE1E0AA635E7FDD3FA7EE6BE57FE5A7F4F5BC65BDB801` | 48 | 48 |
| Interrupt/time | `8A84236C3725A6CB8C40655BC4171228481535B5BD081BA66F4AF16B0ED118CC` | 58 | 58 |
| First AP | `D4B2ED8AD2463C2EFD1923352DF34A359FF09E41C688354039EB897AD8C770FC` | 72 | 72 |
| Per-CPU runtime | `9543CAC00F85386C15DC788210FA1613BC34840A65FC7BAE6E1C292C0E205314` | 19 | 159 |
| IPI/shootdown | `FFBD31E6CD151CBD6D1E483F5FBD6D4CFA8D5D394E06481BE3F7989AF3FE4A52` | 33 | 609 |

Twelve boots, 421 groups and 1,137 cases pass. Independent PBP1 accounting
agrees with 129,079 final managed pages. Physical-memory evidence covers guarded
metadata, scrub/readback, ledger growth, Boot Services reclaim and ACPI snapshot
retention before held-memory reclaim. Virtual-memory evidence covers a sparse
owned-page map, two CR3 writes, three local invalidations, exact original-root
restoration, retained-free rejection and generation-bound release ordering.

The interrupt profile observes eight local timer deliveries and eight EOIs per
run. First-AP and per-CPU profiles verify online/quiesced/parked sequencing and
57,344/131,072 scrubbed bytes respectively. IPI evidence covers three APs,
nine accepted and three denied deliveries, twelve EOIs, one partial-start rollback
and retry, target/ack mask `0xE`, three bounded remote invalidations, one retired
generation and 102 resources/417,792 bytes scrubbed and released. Each attempt
rejects 27 retained frees and 18 premature owner releases. This is bounded AP/root
ownership, not general task-stack ownership or arbitrary cross-CPU retirement.

All mutations occur within virtual guests. No physical-hardware probe, firmware,
physical-media, key, signing, authority grant or production promotion occurred.
Same-host repeated builds and runs are not independent-builder qualification.

## Preserved Failure

The fresh IPI qualifier and runtime validator passed, but initial admission
failed with `PKSMP5 embedded kernel identity changed`; the serial chain exited 1.
The aggregate gate still pinned the Cycle 197 canonical image. The measured
Cycle 203 pin replaced it; the identical candidate then passed without rewriting
guest evidence or rerunning a boot. Seven independent aggregate-pin cases now
reject, including the immediately previous image, null and empty hashes. These
negative tests isolate the aggregate comparison only after the genuine positive
passes runtime validation. They do not bypass real receipt admission.

No guest run failed or was superseded in this cycle. Prior historical admission
defects and repairs remain preserved, not claimed as new discoveries here.

Initial metadata regression passed 50/53 tests, with three failures from current-
progress assertions still expecting the earlier 13/27 state. Those assertions
were corrected to the measured 19/27 state; historical expectations were not
rewritten. The failed log is retained with SHA-256
`99AC81E9227F00608F528A5FE1ADA10F6C0516C52BCD2735C6848F76ED2DD1BA`.

## Regression

All **93/93 focused tests** passed, zero skips, in 124.203 seconds; log SHA-256
`56A861856A52EACFEBB95935FB0C1954A13089477F1663D5FF1A7130B0D55FE0`.
They reject 1,896 recorded-evidence corruptions through runtime and real aggregate
gates: PMM 234, VM 115, IRQ 229, first AP 159, per-CPU 253 and IPI 906. Tests also
exercise 360 raw mailbox mutations, seven independent IPI image pins and twenty
memory-summary cases. PMM tests observe 189 marker-validator calls and detect a
disabled parser or memory oracle. Counts overlap; unsigned evidence consistency
is not authentication and cannot exclude coherent forgery.

The full fourteen-profile memory-entry-provenance suite remains pending with
the eight downstream profiles. Current embedded entry identities for all six
fresh profiles are verified by their runtime validators and the measured ledger.

## Broader Verification

All **283/283 combined scoped tests** passed, zero skips, in 324.219 seconds;
log SHA-256 `07BF462CF9D3769C3B98B69ABE16B9E7443E4733025A911CFB2BDAC940D3008F`.
This includes the six-profile scope, boot admission, native SMP/deferred
transactions, core validation, exact entry reproduction, host provenance,
publication and metadata. Source and owner data were unchanged during execution.
It does not rerun the unchanged CPU205 corruption suite or all downstream profiles.

Corrected metadata passed 53/53, zero skips, in 27.844 seconds; log SHA-256
`B6410FA2EB9047D5E2765ACAA7B7E59ED5DAE53FF8B0220EA47CB36CB5145492`.
Conservation verifies 347 source bindings, 19 unchanged archived progress records,
all prior checkpoint documents, native/entry/core/boot/CPU bytes, locked checklist,
owner data, normative charter, demo ISO and every phase/flag status. The 1,088
discovered tests are inventory, not a full-suite result. Counts overlap; none of
these scoped checks establishes full canonical qualification or merge eligibility.

## Frozen Inputs

- Build ID: `PKBUILD1-CYCLE203-N12-SMP-TXN-V1-00000000001`.
- Canonical kernel: `A943DCB6E41A27F952868F05ED2B3523B47D9D7A7B5DB909EE385205F7CA3B31`.
- Linked kernel: `557687A9F39EEECFFD839A8619D696CEBB4E391B229778162725752C72B4D9AA`.
- Entry receipt: `E90F11157F3416CE2C78650C4605ADF92BF5D7AC19A293E0C105499EF17276A5`.
- Core receipt: `33EE501601ACB8109FA867C2634FAC1C04F43505B4DD6C6D75821545B120BDD8`.

Each bounded execution observed unchanged source and owner report. PooleGlyph
Phase 65 remains newest; its manifest, ZIP and dirty owner conformance report
were preserved. Phase 66 CoreIR remains future integration work.

## Remaining Gates

Selected current-image readiness is **19/27**. Eight scheduler, atomic and lock
profiles remain, starting with `N12-SCHED-001`. SMP recorded admission and at least
51 later control groups remain open: 16 SMP, 18 AP-worker and 17 SMP-preemption.
No phase or flag status changes. No N8/N9 exit, general CPU lifecycle, user-task
contexts, hardware support, new ISO or production acceptance is claimed.

Full exact-candidate canonical/Doctor, release, publication, configured GitHub
checks and review qualification still precede main merge. Cloud branch backup is
separate. Next: cooperative scheduler and preemption/deferred qualification on
these kernel bytes, followed by SMP recorded-admission and executed-control work.
