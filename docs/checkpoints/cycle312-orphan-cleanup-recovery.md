# Cycle312: Rejected Orphan Cleanup Recovery

Started 2026-10-20; reconciled 2026-10-22. Kernel implementation, native controls
and selected integration checks verified. Production incomplete.
Parent `9d5b50a43924aedd09fc822737d34e04a04383ac`, Cycle 311. The previous turn made
verified, committed and pushed progress. Preserve all owner files, historical
evidence and the Cycle308 preview. Live PooleGlyph remains Phase65, with the
Phase66 Core IR audit pending. On resumption, ordinary usage is allowed; the
weekly window is 0% consumed, but a separate five-hour figure is unavailable.

## Scope And Invariants

N13/N14, consumed by N27/N29, under FLAG-N13-LAUNCH-FAILURE-001,
FLAG-N13-USERSPACE-ISO-001, FLAG-N13-USERSTACK-001 and FLAG-NATIVE-UI-001.

- R1: all three ordinary deferred attempts and original backoff remain bounded.
  Exhaustion alone never authorizes new work or publishes launch completion.
- R2: a real terminal owner closes its exact job. Only that job can authorize
  one additional whole-image recovery attempt for an exact exhausted child.
- R3: recovery requires a quiescent scheduler, exact accounting, unreused slot,
  retained image identity and a 64-dispatch cooldown. No raw identity can free it.
- R4: consume the recovery opportunity before touching memory. Persistent failure
  retains ownership and cannot trigger repeated writes or reopen the retry budget.
- R5: successful recovery clears membership only after all pages are reclaimed;
  no launch reply is resurrected for a dead owner. Independent services survive.
- R6: native success and persistent-fault controls, ordinary regression, hostile
  tests and byte/source reconstruction are required. Existing evidence is history,
  not qualification of the changed kernel. Preserve failed attempts.

Alternatives considered: retain indefinitely, reset the retry budget, free by raw
identity, or add a separately bounded closed-job recovery operation. Select the
last: it adds an actual recovery path without unbounded retry or forced release.
The native owner-control will use explicit supervisor cancellation, not claim an
actual UD2 fault or arbitrary asynchronous death. Persistent corruption remains
retained, not falsely repaired. General recovery and service restart remain
kernel work. Full desktop matrices and immutable demo packaging remain eventual
preview acceptance requirements, not the immediate milestone.

## Owner Direction And Next Kernel Work

The 2026-10-22 owner direction supersedes the earlier demo-first ordering. Resume
microkernel development; use the desktop only as a regression workload. Preserve
the bootable-ISO final objective and all acceptance gates, but defer redesign,
demo packaging and the full desktop matrix as immediate work.

Next extend entered-child recovery in `user_entry/task/cleanup.rs` and its
ownership tests: preserve nonzero measured runtime and scheduler accounting,
require quiescence and exact closed membership, and test success and persistent
failure without reentry or a second write opportunity. The existing entered-task
test covers ordinary deferred cleanup, not exhausted closed-job recovery.
Follow with actual owner-fault native controls and multiple retained owners;
then capability/IPC revocation and generation-safe service supervision. Keep
partial allocator release, construction/committed-handoff recovery and all-path
stack/isolation work explicit. Do not claim these gaps are closed by Cycle312.

## Progress

Implemented the closed-job-only recovery API, exact deferred-state validation,
cooldown and pre-access opportunity consumption. Added dispatcher integration,
separate success/persistent diagnostic features, strict event/input profiles,
hostile observation controls and seven Python test methods. The two new Rust
ownership tests cover admitted/unadmitted retained children, successful and
persistent recovery, live/foreign job denial, early state, stale identity,
clock/accounting rejection, active CPU denial and unchanged ordinary budgets.

The first native success cohort passes four QEMU optical boot controls with
source_unchanged=true: two ordinary challenge executions, one stale-file-grant
execution and ordinary unsigned denial. Each successful recovery waits 64
dispatches after the third exhausted attempt, suppresses the dead parent's
completion and releases the final 16 pages. Three surviving services continue.

The final frozen-source cohort passes: 631 kernel tests in each debug-orphan,
release-orphan and ordinary host profile, 143 focused checks, and 13 QEMU guests
covering success, persistent failure, ordinary optical controls and ordinary
graphical regression. The latter includes ten rendered observations and four
preserved drafts; it is regression evidence, not a new desktop milestone.
Persistent failure retains all16 rejected-image pages with zero child calls/ticks
and no repeated writes. Successful recovery releases them. Both retain progress
in three independent services. Counts overlap; this is not full canonical replay.

Independent aggregate reconstruction passes: raw logs and inputs, paired native
images, original pixels,31 unchanged paired user programs and all1,016 execution
bindings agree. The receipt is `runs/native-orphan-cleanup-readiness.json`, SHA256
`D9117AB2AC990C6985C4EC06BFE32712E87BD4CCDA7F7C1FD2128C73AB5345C2`.
All505 selected integration/metadata checks and nine publication-boundary unit
tests pass, including all eight master-checklist coverage checks and the new
kernel-first ordering assertions. The1,653 discovered Python tests are inventory,
not a full canonical execution result. Architecture bindings total913; program
bindings remain111. No phase or flag closes:40 phases,301 subphases and101 flags
(46 open) remain.

Keep the checkpoint on the development branch and PR81 in draft. The exact staged
tree must pass final reconstruction, schema/generator checks, historical receipt
preservation and publication scanning before commit/push. No merge, replacement
preview, tag, release or production promotion is authorized by this evidence.

## Preserved Diagnostics

The initial focused host checks found an invalid duplicate-key test fixture and
an overly permissive unbounded diagnostic syscall observation. Corrected the
fixture and added the bounded orphan-profile check; the 17 focused tests then
passed. Preserve focused1/2 failures and focused3 success, not just final logs.
The first seven cleanup tests passed before final native/oracle source freeze;
they are intermediate evidence, not final current-source qualification.

Independent review found a second verifier gap after the first success cohort:
a forged constant nonzero calls/ticks value across the entire rejected-image
interval could evade monotonic accounting checks. Require exactly zero for
every retained rejected image and add both whole-interval negative controls.
The 17 focused checks pass after that correction. The owned persistent-fault
QEMU process was stopped; its wrapper recorded failure and the cohort exited.
Preserve that interrupted run and the earlier successful native/host receipts
as historical intermediate evidence. A fresh full source-bound cohort is
required; do not relabel the old receipts or skip source identity checks. That
fresh cohort subsequently passed as recorded above.

The first aggregate reconstruction attempt omitted the optical variant when
checking bad-file/unsigned-denial media, so its strict manifest comparison
rejected. Correct the reconstruction caller to pass the exact variant; do not
alter images, receipts or the validator to make that check pass.

The first selected metadata run executed505 checks:504 passed and one failed
because the historical Cycle288 test still asserted the previous current next
move. Update that current-direction assertion to the owner's kernel-first
order, preserving every historical receipt and its hash, then rerun the suite.
That rerun passes505/505; the failed first run remains preserved.
