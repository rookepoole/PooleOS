# Cycle 159 Boot-Chain Replay Checkpoint

Status date: 2026-09-05. Pre-production; not eligible for merge to main.

Cycle 159 completes the six selected N5-SYMBOLS-SEMANTICS-001 boot-chain
prerequisite checks for the Cycle 158 kernel, not the full candidate suite.
The charter, build plan and roadmap now record reconciliation 159. No phase,
subphase, flag, gap or production gate closes here. The earlier in-progress
backup remains in Git at `84e5af4`, with draft PR #74 targeting main.

## Saved State

- Main contains checkpoints through Cycle 157 in merged PR #73, commit
  `4ad5b11c2f833b39f37f91106a3f1df1426b1174`.
- Cycle 158 mandatory inactive-task physical retention was already backed up
  on `agent/n12-mandatory-task-retention`, commit
  `8edcd322b4a4fb33f887d89e81b950117472d7fa`.
- This checkpoint adds measured symbol identities, regenerated PSYM1 and
  dependent PPOL1 vectors, and six genuinely rerun qualification receipts.
- PKREVAL1's host-test expectation now matches the 219 measured kernel tests.
  Its old receipt was rejected before actual requalification. Loader/transfer
  fixtures and release checks now bind current measured source and guest bytes.

## Verified Scope

The symbol qualifier passed four Rust tests, 158 negative controls, 16,384
parser comparisons, 16,384 lookup comparisons and two identical debug builds.
The independent stripped build matches the same canonical kernel bytes.
The policy qualifier passed 116 controls and 32,768 comparisons with zero
mismatches. Its old symbol-dependent inputs were rejected before regeneration.
PKLOAD6 passed 304 host tests, two fresh boots and 155 controls. PooleBoot
passed eight host tests, two additional fresh boots and 155 controls. PKREVAL1
passed 219 kernel tests, 36 controls and 32,768 rejected mutations spanning all
nine retained roles. PKXFER1 passed two real kernel entries, 30 ordered markers,
58 controls and exact nine-file guest/host revalidation with unsigned denial.
All six selected gates and 68 focused Python tests pass, including a regression
that rejects substitution of the previous build ID. This remains a single-host
qualification, not independent-builder or physical-target reproduction.

Kernel identity remains `PKBUILD1-CYCLE158-N12-RETAIN-V002-0000000001`;
canonical SHA-256:
`18EDADA10E141DBADA8C95C1C0B3454696122C5E96C528F45E0AECE6ADD2F07D`.
Six fresh headless QEMU/OVMF boots are included in the final receipts. No kernel
Rust implementation or demo ISO changes are included in this checkpoint.

## Merge Blocker And Resume Point

The latest full audit is still Cycle 158's actual failed result: 80/105 checks
passed, with 24 stale native checks and the aggregate check failing. The full
audit has not been rerun for this checkpoint. Its SHA-256 remains
`BB43C8A08A390893B48CDB8259752AC431D9A9AADBDDA63A2227EA347697DE4B`.
Focused passes do not replace that audit or authorize a main merge.

The current focused projection passes six checks, with nineteen downstream
native checks still rejecting stale receipts. Its SHA-256 is
`D089D039F396D3DFD822E27C3D9F5C87AB8C029E64CC0C656E498BA9174A5C46`.
Next is N7-TRAP-001, then CPU/xstate/MSR, memory, IRQ/SMP, scheduler, atomics and
locks before the exact-final canonical, publication and configured GitHub checks
and any main merge. Active-root and execution-stack ownership follow prerequisite
replay. N0 custody and N36 cross-profile evidence review remain separately open.

Only publication-approved source, fixtures and public receipts belong in this
Git checkpoint. Private diagnostic logs, local build products, keys and ISO
media are not included. Branch backup is not a release or production promotion.
