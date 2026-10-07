# Cycle 216: Native SMP-Preemption Transactions

Date: 2026-10-04. Status: host-qualified, current-image boot replay pending.
Move: `N12-SCHED-SMP-PREEMPT-001`, N12.5/N12.6/N12.7 and N36.
Requirements: `ADD-N12-SCHED-SMP-PREEMPT-001`, `ADD-N36-RECEIPT-COVERAGE-001`.

## Native Changes

The actual PKSCHED6 controller now commits acknowledgement, event admission,
offline-stage/timeout/proof and shutdown transactions only after every check
passes. Failed queries do not consume nested diagnostic counters. Frame and
timer epoch exhaustion reject without wrapping or panicking. Counter capacity
is checked before remote publication, and failed operations retain exact state
for retry. These are exclusive-controller transactions, not a proof of general
cross-CPU atomicity or a lock-free scheduler.

Two further counterexamples exposed valid traces that could not advance: a wake
on quantum expiry and multiple remote events sharing a deadline. A bounded
continuation now drains up to four events plus a quantum operation, requiring
each exact remote acknowledgement before proceeding. The timer/frame epoch and
watchdog are charged only once. Interleaving intake, shutdown and another tick
are rejected while a tick is active; duplicate task/sequence admissions reject.
An allocation-free discarded copy checks completion capacity for the whole tick.
Its hypothetical acknowledgements cannot mutate live ownership. The native
hardware caller still requires actual mailbox acknowledgements.

## Verification

- Initial transaction probe: 14 cases per profile, 8 failures at optimization 0
  and 7 at optimization 3. The epoch panic is debug-specific.
- Event diagnostic: two reproducible progress failures in each host profile.
- Final actual-native probe: 27 cases at optimization 0 and 3; 14 disabled
  repairs detected, plus one explicitly redundant-check positive control.
- Core: all 17 stages pass, including debug/optimized ownership tests, 246
  kernel regressions per profile, 15 borrow compile-fail tests and Clippy.
- Entry: two clean linked/canonical builds match, Rust/Python loaded bytes
  match, 246 kernel tests and 43 hostile-image controls pass.
- Selected host regression: 43/43 pass, zero skips, 84.635 seconds. This excludes
  the known failing live-transfer positive test, which remains a merge blocker.
  Counts overlap and are not independent hardware observations.

Final kernel is 538,264 canonical bytes and 610,304 loaded bytes (149 pages),
with entry offset `0xA000` and 1,326 relocations. Text/RELRO/image ends are
`0x75000`/`0x83000`/`0x95000`; the 192-page kernel reservation is unchanged.
Build ID: `PKBUILD1-CYCLE216-N12-SMP-TXN-V1-00000000001`.

| Artifact | SHA-256 |
| --- | --- |
| Canonical kernel | `FD6C2A0C709957B9EDFFC0647D534E060ED68215C075F07D70AB2AEBCA6C81D1` |
| Linked kernel | `5E40AB31AFB4BCE79BEDB32D7B66D64D957B42CA915B2B70D2F15049F90B7D91` |
| Loaded image | `5D660D084136430C0D152EAAF4D29D5704E9B974F6679205BEBAB54F24687967` |
| Entry receipt | `1B5A40C248B02809CFEA397D058973DFD43DE5B85468BA31BD368EE3D8ED7CC7` |
| Core receipt | `8AA5643002A3FBE416C1B40ECA0BD3D1DFAE7785E500ACBD06292FFAFFAB9DCB` |
| Selected regression log | `CA39E66FDE99F24FB48146EB10B031FA6DA5DFE34F8DEF9CB53E45F6A0E619CB` |

## Preserved Failures

All original diagnostics and failed attempts remain in local `outputs/cycle216-*`.
The roadmap binds their log hashes; raw ignored logs are not GitHub attachments.
Two mutation anchors were initially ambiguous; another mutation incorrectly
expected a failure after removing a now-redundant check. The first linker run
exceeded the fixed text boundary by 814 bytes. The first entry run retained an
obsolete size contract. A later entry receipt became stale after its bound test
pin was edited, so admission rejected it. A prematurely started 44-test
regression produced 9 failures and 1 error. Entry was rerun from final sources;
no passing receipt was manually rebound or old guest transcript rewritten.

Progress/architecture/checklist regression now passes 63/63, zero skips,
33.788 seconds; log SHA-256
`513FE08E46FD552224821AEB512C8DFD8BD754CF0A22FB82897847397C2F7949`.
Three prior runs retained 38 failure records, 37 failure records, and six
failures/seven errors respectively. They exposed stale progress assertions,
overbroad archive-name substitution, and omitted unchanged prerequisite gates.
Historical tests now retain byte/count checks and explicitly assert rejection
of old-image receipts; production-positive boot tests are not weakened.
An initial conservation check also caught a dynamic inventory applied to the
Cycle 215 historical line; that line is frozen at its original 1121 tests.

## Current Gaps

Selected readiness is **3/27**: entry, policy and errata only. The other 24
profiles require new-image replay beginning `N5-SYMBOLS-SEMANTICS-001`.
All 23 parent progress records are archived verbatim. Prior live receipts stay
unchanged and historical; only entry/core readiness artifacts are replaced.
`FLAG-N12-SCHED-SMP-PREEMPT-001` is reopened. Seventeen control-execution groups
and SMP-preemption recorded admission remain open. No phase closes.

N0 custody, N5 authentication, general SMP/timer delivery, retirement, independent
builders, physical hardware and the production desktop/ISO remain open. No new
guest boot, general real-time bound, signing, release or production claim is made.
The frozen demo ISO and locked checklist are unchanged. PooleGlyph remains at
Phase 65/66; the owner's modified conformance report is preserved.

## Cloud and Merge

Completed checkpoints through Cycle 215 are verified at GitHub branch commit
`fc30764f3aad04dee7ee363a72a29f26daae94f4`, 48 commits ahead of `main`, in
[PR #78](https://github.com/rookepoole/PooleOS/pull/78). This checkpoint is intended
for the same development branch. Branch backup does not require a main merge.
Main remains `ac15d1d`; the exact-candidate canonical, Doctor, release,
publication and GitHub/review gates must pass before merging. No bypass occurs.
