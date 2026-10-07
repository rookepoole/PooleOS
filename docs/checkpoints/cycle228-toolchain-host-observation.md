# Cycle 228: Toolchain Host Observation and Failure Diagnostics

Status: focused pass; full exact-candidate qualification pending at commit time.
Date: 2026-10-07. Move: N36.1 / N36-RECEIPT-COVERAGE-001.
Requirement and flag: existing ADD-N36-RECEIPT-COVERAGE-001 and
FLAG-N36-RECEIPT-COVERAGE-001, still open. Production readiness: false.

## Observed Failure

Parent commit `03355140368b00b5d453442f6bb161a6ad767ee1`, tree
`c3d7c0e8b7ea2a3b21a02ff89dd22d46536d0cd6`, was inspected without source changes.
The fail-fast unittest diagnostic attempts 882 tests in 779.435s, with one failure
and one skip. It stops at the first failure; it is not a complete suite pass or
proof of the entire failure set of the prior canonical run.

`test_generator_reproduces_public_ledger_when_local_toolchain_is_available`
compares the new compiler-fixture report byte-for-byte with the historical ledger.
The sole difference is Cargo's verbose Windows version: build 26200 became 26300.
A fresh qualification and recursive typed report comparison establish this narrow
difference. `sys.getwindowsversion()` independently reports 10.0.26300. The two
fixture targets each build twice with identical bytes, and all three negative
controls pass. These are empty UEFI/ELF compiler fixtures, not a PooleOS boot.

The previous canonical failure remains immutable: commit
`79adf4aa452daf36f52e24b99c176c49b2523935` passed 105/106 canonical and 707/708
Doctor checks; unittest exited 1 after 1089.266s. Its wrapper lost individual
failure names. The new diagnostic identifies an actionable failure, not a
retrospective complete explanation of that earlier run.

## Repair and Verification

The reproduction test independently observes the Windows build. It changes only
that field in an expected copy of the original report, then compares fresh output
bytes exactly. It does not normalize actual output or alter the historical ledger.
Major/minor version, edition, compiler identities, executable/library/input hashes,
artifact bytes, counts and typed claims remain strict. Ten altered-report cases
remain unequal; malformed, missing, duplicate and unsupported observations reject.
The shared qualifier is unchanged, avoiding invalidation of unrelated evidence.

Doctor now retains complete failed-command output and partial timeout output.
The outer release gate likewise preserves failed Doctor output. Successful command
tails remain compact, while nonzero exits, timeouts and startup errors still fail.
Tests cover synthetic nested failures, real stderr/stdout, empty output, startup
failure and timeout text/bytes/None.

All 19 focused tests pass with zero skips in 2.175s (runner 3.094s). Source and
owner snapshots are unchanged during execution. The initial repair inserted the
timeout handler at the wrong exception block; three timeout subtests failed.
That placement was corrected and the original exception block restored before
the passing run. Both logs are retained. A pre-existing taskkill subprocess
ResourceWarning occurred; read-only process checks confirmed the reported child
PIDs had exited. No shared process-control implementation was changed here.

## Evidence Digests

Ignored local logs contain complete diagnostic output; hashes bind those exact
observations without publishing host-local payloads in the source repository.

| Evidence | SHA-256 |
| --- | --- |
| Fail-fast diagnostic log | B726AD7EECB65CD5FA6C8E8AB59EB4D9AD5D1559568E6E9F4E7468E1BEB06B24 |
| Fresh fixture qualification log | 7EBFEE07F63812AABD560649F6F1AA496532BE44CDEE3414A3E79F0FFDB74023 |
| Initial failed repair log | 4D602A5A49E65BA9D30B1593168061FA92486C045C34421E88B96ED24F09F006 |
| Corrected focused log | 9D805995ED97026A694E3382BFC6197AE57F47E77A70FCD2B71C41431520020E |
| Prior failed canonical report | E65E0CCEEEF63D7C8E8C6E0F6F2BD0E65807D88DF14E76F253664261C8A75FE4 |
| Prior failed canonical log | 7DFDB6EFFAF983852F69D9A2FCE89E16FC6800455D4DCE1299F4CEC7953D3F21 |

## Boundaries and Next Move

Native source, all original native receipts, checklist coverage, PooleGlyph Phase
65 anchor and owner-dirty report, demo ISO and normative charter conditions are
preserved. Phase 66 is not newly qualified. No guest boot, hardware mutation,
signing, release, production promotion or main merge occurs in this checkpoint.
All 29 prior current progress records are archived under Cycle 227.

Next: qualify the exact committed source using the runtime-inclusive canonical
gate with signed-bundle and replay inputs. Retain any failure, repair it and rerun
as required. Complete remaining non-Python data/tool dependency review, publication
boundary scan and GitHub/review gates before main merge. The integration branch
provides cloud backup independently. Passing this bounded repair does not close
N36, N0 key custody, N5 authentication, task-state, hardware, second-builder or
production requirements. No new duplicate requirement or flag is created.
