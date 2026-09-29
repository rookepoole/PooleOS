# Cycle 199: CPU Control Admission and Current-Kernel Replay

Date: 2026-09-29. Pre-production; full canonical qualification and main merge
remain pending. Parent: `ff2d3bf9cd5fb7ed975b3af56971ee1652244b55`.
Selected move: `N7-TRAP-001`, N7.5/N7.6 and dependent N7.1/N7.3/N7.4 profiles,
under existing `ADD-N36-RECEIPT-COVERAGE-001`.

## Repair and Failure History

The initial six-boot trap qualifier passed, but an aggregate-gate regression
failed: that gate still pinned the Cycle 192 kernel hash and 1,327 relocations.
The current image has 1,326 relocations. The corrected pin and two old-image
rejection cases are covered by the final 21-case CPU gate regression.
Initial failing test log:
`D18042EB201DF92A159C8B0B027247C05F63FDB90D5913C99ACB999F40579402`.

After establishing a genuine source-current positive runtime and gate baseline,
the 1,084-case control audit found 663 accepted corruptions through each path.
Runtime rejected 416 and raised five exceptions; the gate rejected 421 without
exceptions. The rows previously checked identifiers and status but did not
strictly require the complete declared control shape.

`recorded_control_errors` now checks exact ordered JSON field/type/value equality
against the profile's declared controls, rejecting extra/missing/wrong fields and
non-JSON values. All five CPU admission wrappers use it and return normalized
errors for non-object roots instead of raising `.get` exceptions. Existing
embedded-entry and paired-run checks remain required. This repairs evidence
admission, not a demonstrated native exception-delivery defect.

Before audit SHA-256:
`1260297B4F4D703D17667851E571291AC57DF9264380389F68F8D0FF00B53972`.
After audit SHA-256:
`9D10D6F8357739B92F195896FFDA1907347F97172388F3EEA7F8781B8F49786E`.
All original 1,084 cases now reject through runtime and actual file-based gate,
with zero exceptions. Both audits establish the genuine positive first.

## Fresh Qualification

All source-bound CPU inputs were frozen before the final chain. Fourteen final
virtual boots and 225 executed controls pass; six initial trap boots are
superseded, not added to the final total. Each qualifier reports the same 246
kernel host tests; that is not 1,230 distinct tests. The expected TCG exception
limitation probe is separate from two successful WHPX exception runs, each with
three deliveries and two recoveries. Guest xstate configuration/recovery writes
occur; no physical hardware or host privileged mutation is claimed.

| Profile | Final Boots | Controls | Receipt SHA-256 |
| --- | ---: | ---: | --- |
| Trap | 6 | 51 | `50D9C781FBC7CF7ED15EE3295028B09DD713BEC0AE53DC909F13F832BD7006B6` |
| CPU policy | 2 | 41 | `98CFFDC8BADF7681B519D8936D5491DE27EBD32B5BE51196AC8EC26C37D39C07` |
| Xstate policy | 2 | 43 | `8B683AC3B32FBB3576771F6D8742B12C412394D98AC9C9A947DF98AC8A876621` |
| Xstate exception | 2 | 43 | `33F94DD2D6D37256D74E7D29411BF0DCB8ADEB6C09EC738F9E62CC73DEBD0AD7` |
| Privilege/MSR | 2 | 47 | `D5027EF6F51ADCCA9A6B33308CA91D8FF617BC08483F91B47F321A88776452FC` |

The final and initial trap summary logs share a hash because their printed
counts are identical. Those logs are not unique execution identities; distinct
receipt hashes, raw evidence and runner records remain preserved locally.

The unchanged kernel is build `PKBUILD1-CYCLE197-N12-DEFERRED-V1-0000000001`,
530,072 canonical bytes, 602,112 loaded bytes, entry `0xA000`, 1,326 relocations.
Kernel SHA-256: `B19D4F7E854ECED3495D88C00F7379061B913EF00477FBD3701929B2F77D80F1`.
Current entry receipt SHA-256:
`70814DA7358BEE6FA6E5D2341D251ACE57A906BA4FB2E9E12BD8D53677C7E38D`.
Native sources, core receipt and trap frame are unchanged.

## Regression and Scope

All 54 focused tests pass with zero skips in 176.656 seconds, including 3,398
control mutations (1,084 trap, 546 CPU, 572 xstate, 572 exception, 624 MSR),
371 paired-run corruptions, 80 embedded-entry cases, 20 invalid current-entry
dependencies and 21 aggregate-gate cases. Every malformed control case runs
through both runtime and the actual gate after a real positive baseline.
The public mutation corpus exactly matches the private audit generator.
Focused log: `D3599A8C5F5C9ECCFE3030674165E0B1D0A60F51C357909883AC5C85B944630B`.

The combined boot/kernel/CPU/deferred/metadata/publication regression passes
233 tests with zero skips in 343.453 seconds, including exact kernel reproduction
and the native deferred transaction checks. Source and owner data remained
unchanged throughout execution. Combined log:
`D1BF6DC903758E38583778E0C507F1BC8E8DAF2568DC3F0973B91D6E678EDEA4`.
Initial metadata passes 46/46 in 14.657 seconds; log:
`E6CCFFEB776508E6218383DF5C0D9B7164609A8C056C8F0D42180D614EAF019B`.
Initial conservation passes, preserving 17 parent current-record snapshots and
verifying all 325 architecture source bindings. This is scoped regression,
not the full canonical suite or authorization for main merge.

Recorded consistency is not authentication, proof of fresh execution, independent
attestation or exclusion of coherent forgery. All-vector containment, guarded
IST, user-context ownership, physical CPU qualification and full N7 exit remain
open. The 1,069 discovered test methods are inventory, not a full-suite pass.

## Remaining Work and Cloud Boundary

The current selected projection passes 13/27. Next:
`N9-PMM-ACPI-CONSUMER-001`, then the remaining memory/VM, IRQ, SMP, scheduler,
atomic and lock dependencies in order. Fourteen profiles remain. Deferred
recorded-evidence admission and at least 65 control-execution groups remain open.
Full exact-candidate canonical/Doctor tests, release gate, publication scan,
configured GitHub checks and review requirements still precede main merge.
Conflict-free GitHub status or an empty check list does not satisfy those gates.

All 40 phases and 301 subphases retain their status: 19 partial, one blocked,
20 not started, zero complete. All 8,996 checklist requirements, 57 ADD items,
94 flags (36 open) and 20 program gaps remain accounted for. Prior checkpoints,
the normative charter, checklist, owner PooleGlyph changes, Phase 65 inputs and
existing demo ISO are preserved. No key use, signing, physical media, firmware,
release, independent builder, new ISO or production promotion occurs.

This checkpoint is intended for development-branch cloud backup through draft
PR #78. Ignored raw logs, toolchains, temporary output and the local ISO are not
part of the Git backup. Qualified main remains `ac15d1d` until merge gates pass.
