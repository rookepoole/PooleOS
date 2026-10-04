# Cycle 215: AP-Worker Admission and Executed Controls

Status date: 2026-10-03. Pre-production; no phase or flag closure.
Parent: `db19e3c6cc17363371dc929f804462597b75a846`.
Move: `N12-SCHED-AP-WORKERS-001`, N12.5/N12.6/N12.7 and N36.
Requirements: `ADD-N12-SCHED-AP-WORKERS-001`, `ADD-N36-RECEIPT-COVERAGE-001`.

## Repair and Scope

The recorded AP-worker validator now rejects malformed roots, invalid calendar
dates, wrong JSON types, altered inputs and claims, inconsistent paired runs,
markers, dual-channel digests, summaries, observations, execution topology,
host probe records, native-control evidence, source audits and linked images.
Aggregate admission returns on component errors rather than raising nested-build
exceptions. Measured current kernel identity replaces obsolete pins, and the
relocation count requires an exact integer. This establishes recorded consistency,
not execution freshness, trusted timestamps, authentication or signatures.

Eighteen previously constant-only groups are executed. Fourteen groups compile
the real AP-worker controller against the real SMP/IPI library and verify 59
boundary scenarios. Four source groups execute 58 mutations across callback
allowlists, interrupt-stack gate wiring, register preservation and park/scrub
ordering. Removing a native safeguard or disabling the source audit must cause
the test to fail. Native kernel source itself is unchanged in this cycle.

Two final SandyBridge TCG four-vCPU boots run three AP workers. Each reports
twelve typed calls (nine driver and three service), queued and remote
cancellation, timeout rollback, thirteen reclaimed slots, 102 scrubbed/read-
verified pages and 24,576 stack bytes within 417,792 total scrubbed bytes.
The receipt passes 246 kernel host tests and 34 groups covering 325 cases:
266 rejections plus 59 native boundary scenarios. Counts include overlapping
assertions; they are not independent hardware trials.

## Preserved Failures

The original two-boot diagnostic reported 226 cases including eighteen groups
that did not execute. It is not accepted as post-repair qualification. Its
receipt SHA-256 is `D896E4406E85D11B7CE7756C9F66CC5C5ACD9BEC693D6AA309F2E9DCB040D942`.
The original aggregate gate rejected obsolete image pins. After correcting only
those pins, a 294-case audit found 279 runtime and 178 aggregate false admissions,
with four runtime and nineteen aggregate exceptions. After repair both validators
reject every case cleanly and accept the genuine final receipt.

The first five-test native harness run produced four failure records: the
declared native total was 61 instead of the executed 59; a timeout-guard mutation
was masked by another preflight guard; and two detected failures used an invariant
panic rather than the expected assertion text. The harness was corrected, a
distinct ticket-binding mutation substituted, and all five tests passed. None of
these harness failures is relabeled as a native product defect or a passing run.

## Evidence

- Final receipt: `runs/native-kernel-scheduler-ap-workers-readiness.json`, SHA-256
  `30B59312AF639F6E0B55391FCB33474A9B999E351BCC414E5A8B0384B53A82B4`.
- Final qualifier: 82.687 seconds; log SHA-256
  `B06620B801239E6381B91722D9B146A38F8E0EDC3B2CA346918A635BF2F030DA`.
- Diagnostic baseline: 84.125 seconds; log SHA-256
  `02E0E81B096AB0EDEEFF1DD25C6F54431329A048B7E29574BB3DCCD44B88245A`.
- Failed native harness: log SHA-256
  `A922A8463B9CDD95172CEBE792AE3D85A7E497C5D97EF944A6D8D8C96DDBEC6C`.
- Corrected native harness: 5/5, no skips, 12.394 seconds; log SHA-256
  `8B72F7FD7F645C54D47DB1DBA4BFD68255CB349B4EAFA14096C744811B1F239C`.
- Focused regression: 19/19, no skips, 37.801 seconds; log SHA-256
  `EED2A9C54843FB2CA73BFE1D83BD498E436F16D905CC44337DA93D20AB348499`.

The focused suite rejects the common 294 corruptions and 49 additional malformed
records, plus ten independent aggregate cases. It detects fourteen disabled
AP-worker safeguards and fifteen disabled transaction repairs. Thirty transaction
cases run at both host optimization levels. The positive receipt is not rewritten
to make tests pass. Local raw logs are ignored workspace outputs; the committed
receipt, test sources and checkpoint retain portable evidence and identities.

The initial metadata suite passed 59/62 with three stale progress assertions:
four remaining profiles instead of three, the prior next move, and the prior
qualification status. These are corrected without changing receipt or native
evidence. The failed run remains recorded, log SHA-256
`06C938D9778EBD6E231730AFCA4EB988AD69767B1306D310BA326C73A7931AAC`.
The second run passed 61/62 and exposed one later stale pending-profile count
in the same test. It now asserts the exact three pending profiles. Its log is
`154FF5409A9A80890B01D9681083C8B592FA33A4DC8FB15B9E824450051EBE6D`.
The corrected metadata suite passes 62/62 without skips in 34.281 seconds
(runner 35.063), log SHA-256
`AD3EC6118AD143DA62371EBC2566FC728DB01C6F39D14B499D57DFB6964FFEA1`.
The result covers roadmap, architecture and locked checklist tests only.

## Progress and Merge Boundary

Selected readiness is 24/27. SMP preemption, atomics and locks remain, and at
least seventeen SMP-preemption control groups still need executed evidence.
Next is `N12-SCHED-SMP-PREEMPT-001`. Eleven dependency receipts include the new
AP-worker record; the earlier ten remain unchanged. Twenty-two parent current
progress records are archived verbatim. Source inventory is 1121 Python tests,
not a full-suite pass. The architecture now binds 362 source artifacts.

The unchanged kernel is `PKBUILD1-CYCLE210-N5-KMAP-BOUND-V1-000000001`, canonical
SHA-256 `AE3422B2D44E6EC87AB1D5B51414C023E46F2EE3461A0D0895B9D1242E10D25A`,
with 1323 relocations. Earlier native source, entry/core, receipt/checkpoint
history, phase and flag statuses, 8,996 locked requirements, PooleGlyph Phase65
owner data and demo ISO are preserved. No key, signing, physical hardware,
firmware, media, production promotion or release operation occurs.

Completed tracked checkpoints are backed up on the GitHub development branch in
PR78. A main merge still requires all current dependency checks and the exact-
candidate canonical runtime-inclusive suite, Doctor, release gate, publication
scan and configured GitHub/review gates. The three pending profiles are real
qualification blockers, not missing owner approval. N0 custody, N5 authenticated
boot, general retirement and the wider native production requirements stay open.
