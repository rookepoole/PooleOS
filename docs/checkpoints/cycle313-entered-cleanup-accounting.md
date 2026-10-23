# Cycle313: Entered Task Cleanup Accounting

2026-10-22. Kernel fix, focused/native verification and selected integration
checks complete. Production incomplete. Parent
`ad14e0094614ad136de76e6b5c617739b882c76d`. The previous goal turn made verified,
committed and pushed progress. Current priority is microkernel development,
not demo packaging. Preserve owner files, all historical evidence and Cycle308.
Live PooleGlyph remains Phase65; Phase66 Core IR audit is pending. All eight
master-checklist checks pass. Ordinary usage is allowed; the weekly window was
3% consumed at entry, with no separate five-hour figure available.

## Kernel Work

N13/N14 under the existing launch-failure, user-stack and user-space flags.
Entered-child cleanup must bind both measured ticks and execution-slice ordinal
to the scheduler. Equal ticks alone do not establish equal execution history.

- E1: reject a mismatched entered-task slice count before scheduler parking,
  memory writes or recovery-budget consumption; preserve both owners.
- E2: check the same invariant on ordinary deferred polls and closed-job recovery.
- E3: entered exit/cancellation retains its exact outcome and runtime through
  exhaustion, success or persistent failure; no reentry or duplicate revocation.
- E4: preserve the original three attempts, cooldown and single closed-job
  opportunity. No forced release, retry reset or early slot reuse.
- E5: require independent host regression and native deferred owner-death
  regression before calling this checkpoint verified. Do not relabel historical
  desktop results as current or claim native exhausted entered-child coverage
  from host-only tests.

The host counterexample uses the same task identity and tick total with one or
three scheduler dispatches against two settled task slices. This is a trusted
kernel integration validation gap, not evidence of a userspace exploit.
Alternatives considered: ticks-only acceptance, rejecting all entered recovery,
or binding the actual slice ordinal. Select ordinal binding so legitimate
recovery remains available without weakening accounting.

## Evidence And Remaining Work

The first exact-name test invocation matched zero tests; it is not evidence.
The corrected invocation reproduced the admission error. A second regression
also reproduced consumption of recovery on a mismatched scheduler ledger.
Preserve mismatch-red1, mismatch-red2 and mismatch-red3 logs/receipts.

Implementation now checks both ticks and slice count at deferral and polling.
Two new host tests cover admission and exhausted recovery for already-entered
children with exit/cancellation, success/persistent failure and hostile ledger
substitution. All nine cleanup tests pass. The full debug and release deferred
profiles pass615 tests each; the ordinary desktop-feature profile passes633.
These feature sets intentionally discover different test counts. Twenty focused
Python checks pass. Three current-source non-optical QEMU guests pass actual
owner UD2, entered-worker deferred cleanup and denied-authority controls.

Independent reconstruction passes for raw input/logs and retained boot
transcripts, paired kernels, exact media and five selected paired user programs.
All1,016 execution bindings match; only the cleanup implementation and its Rust
test file differ from Cycle312. The new receipt is
`runs/native-entered-cleanup-readiness.json`, SHA256
`CA00EE4A95634DC5128FDD0138D9F8C048255D0DEB3AF1ABA3674B8688345302`.
All506 selected integration/roadmap checks pass, including all eight checklist
coverage tests. The1,654 discovered Python tests are inventory, not full canonical
execution. Architecture bindings total916; execution bindings remain1,016 and
program bindings111. Counts overlap. All40 phases,301 subphases and101 flags
(46 open) remain. No new ISO, GUI replay or preview selection.

Keep this checkpoint on the development branch and PR81 in draft. Before commit
and push, require the exact staged audit, source/artifact reconstruction,
generator/schema checks,97 unchanged historical receipts and publication scan.
Do not merge or promote this bounded evidence.

Next: native exhaustion/recovery of already-entered children following real owner
faults, extending the existing non-optical shell profile rather than adding demo
packaging; then multiple-owner fairness, capability/IPC revocation and bounded
service restart/rebinding. Partial allocator release, construction and committed
handoff recovery, all-path stacks, scheduler isolation and all N0-N39 gates
remain. No new ISO, preview, merge or production promotion in this cycle.
