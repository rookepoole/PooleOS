# Cycle 167: AP Live Controls Source Checkpoint

Status date: 2026-09-08
Status: unfinished source backup; not merge-qualified or production-ready.
Phase: N12.3, `ADD-N12-CONCURRENCY-RECLAMATION-001`.
Flag: `FLAG-N12-CONCURRENCY-RECLAMATION-001` remains open.
Branch: `agent/n12-ap-execution-ownership`.
Review: [draft PR #76](https://github.com/rookepoole/PooleOS/pull/76).

## Cloud And Main Status

GitHub confirms [PR #75](https://github.com/rookepoole/PooleOS/pull/75) merged
qualified Cycles 162-165. Main is
`6f9399c3cd70ebef2f7610f8b6fdb40ae262e27f`, with tested and merged tree
`c20156f18d2727f7e3c1df73ac05ad8126b9f470`.
Its [recorded qualification receipt](https://github.com/rookepoole/PooleOS/pull/75#issuecomment-5580926148)
records 105/105 canonical gates, 708/708 Doctor checks and a successful full
Python suite with 924 discovered tests. This is historical evidence for that
exact tree, not qualification of the changed Cycle 167 source.

PR #76 is the only open checkpoint PR observed during this backup. Before this
update it contained Cycle 166 commit
`39844b6deab6f76f0faf22d058eb16bf419bb7f5`. GitHub reports no merge conflict,
no requested reviews and no status checks. None of those observations supplies
the missing local canonical qualification. Pushing source to the PR branch
backs it up without marking it ready or merging it into main.

## Changes Since Cycle 166

- The real partial-start and full three-AP startup paths now probe retention
  for each runtime region and both data frames. Both copied-handle release
  APIs and owner-authorized release APIs are checked while execution is possible.
- Probes check that PMM accounting, physical-access counters, owner state and
  exposure masks remain unchanged. Startup rejects owners without the required
  execution exposure. The final INIT park boundary remains an explicit unsafe,
  exact-topology assumption, not proof of general hardware quiescence.
- Existing partial-start and shootdown markers carry observed rejection
  counters. Expected totals are 27 copied-free and 18 owner-release rejections
  per attempt. These expectations are implemented but not yet observed in a
  fresh Cycle 167 guest run.
- Independent marker parsing, source controls, receipt-consistency checks and
  regression tests are added. The intended 249 SMP hostile controls remain
  unmeasured until the qualifier completes; do not count them as passed.
- The entry build identity, measured ELF layout and guarded mapping positions
  are updated. The reclamation qualifier adds explicit AP-owner scope and
  named-test checks; its first run exposes the counting error recorded below.

## Measured Evidence And Failures

PKENTRY1 passes with 243 host tests, 43 ELF negative controls and byte-identical
results from two clean builds on the same host. Canonical kernel SHA-256:
`4C0D2D64D1572FE0ACE3105BE066C89588181CAD7C927765063D7C50187DE7F8`.
It contains 530,072 canonical file bytes, 602,112 loaded bytes, 147 pages and
1,321 relocations. This is not a two-independent-builder result or a new ISO.

The entry run took 38.125 seconds with 1,473 tracked non-receipt files unchanged
during that run. Its log SHA-256 is
`0DBF2445455BAA6667B822408AD4DB25516BC31F12CA64AB7669DBDB2CACA43C`.
Later documentation/qualifier edits mean this is not an exact-final whole-tree
qualification. The public entry readiness artifact binds its narrower scope.

Failures remain recorded, not hidden:

1. Text exceeded the old `0x72000` boundary, reaching `0x7240e`; after shifting
   that boundary, RELRO reached `0x80040`, beyond its old `0x80000` limit.
   Measured page-aligned layout changes repaired both link failures. The final
   boundaries are text/data `0x73000`, RELRO/data `0x81000`, image `0x93000`.
2. The first entry qualifier rejected stale runtime hexadecimal acceptance
   pins. Synchronizing them to the measured layout repaired the qualifier;
   its successful rerun is the PKENTRY1 result above.
3. Reclamation qualification stops at `kernel-regressions-release` because its
   new checker expects 20 passing tests under `physical_memory::tests::retention::`.
   The actual log has 18 there and two under `physical_memory::retention::tests::`.
   All 243 kernel tests, including 11 AP-owner tests, pass. The checker remains
   unrepaired in this source backup. It must account for both namespaces and
   retain negative tests for missing, duplicate and failed cases.

The failed reclamation wrapper's log SHA-256 is
`91359BB361D5B7550725F4085DD8E780495CC5836605509E01EA4771A2247EF4`.
It did not write a new successful reclamation receipt. Its failure prevented
the chained SMP command from starting. No fresh Cycle 167 SMP boot or current
full canonical pass is claimed. Raw logs and build products remain private.

## Remaining Merge Conditions

1. Repair and test the named-test accounting, then rerun the complete
   reclamation qualifier. Preserve the failed run separately.
2. Run fresh bounded headless SMP qualification against the new kernel.
   Independently check both partial/full paths, observed counters, rollback,
   cleanup, exact image identity and the actual hostile-control count.
3. Reconcile guarded map fixtures, source/receipt bindings, release-gate pins,
   architecture baseline, roadmap generator/schema/tests and machine progress
   authorities. Old Cycle 165 receipts cannot qualify the changed image.
4. Replay affected native dependencies in order, beginning
   `N5-SYMBOLS-SEMANTICS-001`, retaining failures and exact source identities.
5. Freeze the final candidate; pass the runtime-inclusive canonical suite,
   release gate, publication scan and applicable GitHub checks/review conditions
   before marking the PR ready and merging.

The roadmap still contains 40 phases, 301 subphases, 57 ADD requirements,
94 flags (35 open), 20 gaps and all 8,996 checklist requirements. This checkpoint
does not complete their reconciliation or change their statuses. N0 custody,
general task-stack ownership and CPU retirement remain separately open.
PooleGlyph, the frozen demo ISO, keys, releases, firmware and physical media
are unchanged. Only source and allowlisted public artifacts belong in this
Git backup; ignored private evidence is not asserted to be cloud-backed up.
