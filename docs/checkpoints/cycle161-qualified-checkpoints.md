# Cycle 161 Qualified Native Checkpoints

Status date: 2026-09-07. Pre-production development source, not a release.

This checkpoint completes dependency replay for the Cycle 158 mandatory
inactive task-table/frame-retention kernel. Cycles 158-160 were already
backed up on the remote `agent/n12-mandatory-task-retention` branch in PR #74.
They remained off main because their changed-kernel evidence was incomplete.
The actual pre-closeout canonical audit now passes. Exact-final qualification,
publication and GitHub review checks remain required before a normal main merge;
the PR records the subsequent remote merge outcome.

## Measured Evidence

- Fourteen refreshed memory, IRQ/SMP, scheduler, atomic and lock profiles.
- Twenty-eight successful final headless QEMU/OVMF boots, 658 negative-control
  groups and 2,118 rejected cases, with 219 kernel host tests per qualifier.
- All 26 selected native dependency checks pass against current sources.
- Fourteen forced production-overclaim cases reject through the release checks
  with the outer schema loader withheld.
- The pre-closeout canonical invocation passes 105/105 consistency checks and
  708/708 Doctor checks, including the suite with 917 discovered Python tests.
- Both the bundle and replay-proof inputs were supplied to the canonical run.

Kernel build identity remains
`PKBUILD1-CYCLE158-N12-RETAIN-V002-0000000001`, with 1,305 relocations and
canonical SHA-256
`18EDADA10E141DBADA8C95C1C0B3454696122C5E96C528F45E0AECE6ADD2F07D`.
No native Rust or frozen demo ISO bytes change in Cycle 161.

## Failures And Repairs

The old acceptance pins initially passed only 15/26 selected checks despite
valid fresh receipts. After verifying the new receipts, the exact host-test,
relocation and linked-kernel bindings were updated; all 26 checks then passed.
Previous synthetic parser examples were not changed to imitate live evidence.

Two scheduler readiness schemas incorrectly required one fixed date. Their
runtime validators now check a canonical calendar date explicitly. Six valid
and twenty invalid date cases pass, including component and release-path
rejections. The shared small schema validator still does not enforce
pattern/format; this repair does not close the broader N36 schema/evidence audit.

The first cooperative-scheduler run overlapped a validator edit. Its two passing
boots are preserved but excluded from final evidence. A second, frozen-source
qualification supplies the two scheduler boots counted above.

The earlier failed Cycle 158 full audit is preserved separately, SHA-256
`BB43C8A08A390893B48CDB8259752AC431D9A9AADBDDA63A2227EA347697DE4B`.
The new actual pre-closeout canonical receipt is
`5F7F3DEBE21ADA7974016D2EB112E141BBE664E5A18F95F96CCB248102027A46`.
The separate 26-check projection is
`1C353A94A929736E47B9AAABD627415DF27CB4AC182127E394A2E5E5BDB657E1`.
That projection is not a substitute for the canonical suite.

## Remaining Work

Next is `N12-CONCURRENCY-RECLAMATION-001`: active-root, execution-stack and
acknowledged CPU-retirement ownership, followed by independent live evidence.
Mandatory retention of inactive tables and bound frames does not prove those
remaining lifetimes, arbitrary payload ownership or raw-alias isolation.
N0 custody and broader N36 review remain open.

Plan 2.67.0 and reconciliation 161 preserve all 40 phases, 301 subphases,
57 ADD requirements, 94 flags (35 open), 20 gaps and 8,996 locked implementation
requirements. No phase or flag closes. PooleGlyph Phase 65 and the owner's
modified report remain unchanged. Private logs, toolchains, signing material
and ISO build products are not part of the public source checkpoint. Isolated
disposable test signatures confer no governance or production trust.
