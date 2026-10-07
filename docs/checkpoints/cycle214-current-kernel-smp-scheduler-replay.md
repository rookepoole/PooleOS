# Cycle 214: Current-Kernel SMP Scheduler Replay

Date: 2026-10-03. Parent: `5a7bbb02cb7caabfb2d6cfc277aaf1b667e3725b`.
Status: pre-production, scoped qualification only. Previous turn: progress.
Move: `N12-SCHED-SMP-001`, N12.5-N12.7/N36.
Requirements: `ADD-N12-SCHED-SMP-001`, `ADD-N36-RECEIPT-COVERAGE-001`.

## Intake and Scope

Parent intake passes 358 source bindings, 1109 discovered tests and 22/27
selected checks. The locked checklist remains 10512 lines/8996 requirements,
SHA256 `A8C94719FAF9428C1F133010BA2603C0270C4E1EFD7327AF8EAB9C8C362ABB3D`.
PooleGlyph remains Phase65 with manifest
`A2387DD5A9E51BA50493E1E39E5D9B0FCE304BAFDF57567552AB3CE30DAC7CE9`
and ZIP `F3CCEB701CF76274D9464A0958BF6106888FB34F3C0BFBD55DE4ACE03C427ABC`.
The owner-modified conformance report is preserved. No syntax, executable Core IR,
ABI, PGB2/PGVM2 or privilege migration is inferred. Phase66 remains next upstream.
N0 custody and N5 authentication remain open; this move is owner-independent.

## Live Evidence

Two SandyBridge four-vCPU QEMU/OVMF boots pass 37 markers each. The measured
profile executes six AP dispatches, two BSP dispatches, nine acknowledged
operations, one timeout rollback, two stale-ack rejections and exact cleanup
of 102 pages/417792 bytes. All 32 control groups pass 303 cases: 244 rejections
and 59 compiled-native boundary scenarios. Source-audit controls cover 51
register/cleanup/callback mutations. They are not injected hardware faults.

Receipt: `6A7EDCA3DCC42389D55170584C975D9DEAEBA8DBE790A21E13A7E243298FE527`.
Previous receipt: `31C084B5C7AEA66051FD8E36785C4CE8E2C8FF5FEA2701023CCBDE41BC2540F0`.
Qualifier elapsed: 82.594 seconds. Log:
`B4AFCEDC4E0B5203EA8C7434E85C6ABD1BFF4D8CFEFFE76250C1A9A84BB46958`.
The current 246-test kernel receipt is embedded exactly, with canonical SHA256
`AE3422B2D44E6EC87AB1D5B51414C023E46F2EE3461A0D0895B9D1242E10D25A`.
Independent linked audit measures 534168 canonical bytes and 1323 relocations.
Native kernel, entry and core bytes are unchanged this cycle.

## Repair and Preserved Failures

The genuine candidate passed runtime validation, but aggregate admission failed
with `PKSCHED4 host oracle, source, or linked INVLPG audit changed`. Two aggregate
pins still named the old A943 kernel and 1326 relocations. Independent current
entry/linked evidence supports their correction; the identical candidate passes.

Float 1323.0 was rejected by full admission before and after repair. It was
accepted only by the isolated aggregate check with schema/component validation
deliberately bypassed. An explicit integer guard now rejects it independently.
Three added regression cases reject the old hash, old count and equal-valued float.

The first location chosen for that regression was itself a receipt-bound test.
The temporary edit made the candidate's source binding stale; after-audit and
admission stopped before copying. A subsequent suite was mistakenly launched
despite that rejection and still read the old public receipt. It passed 13/18,
with five admission failures, in 29.212 seconds (runner30.109). Failure log:
`88669854A9DED7DBFC07E703B95959F5F92FB516C2E27F9D4490467E87C9D912`.
The aggregate-only regression was moved to the existing release-gate test module.
The bound test was restored byte-for-byte, then runtime and actual aggregate
admission verified and copied the unchanged generated candidate. No positive
receipt was rebound manually and no guest rerun or validation bypass was used.

The corrected 19-test suite passes without skips in 43.153 seconds (runner44.047).
Log: `AFACEB291245818E00FFF30CF69D48EBE6BA167285B51B3AF8B15282ED4BCEBC`.
It rejects 279 generic and 47 additional corrupt records, exercises eleven
independent aggregate cases, detects thirteen disabled native safeguards and
nine disabled transaction repairs, and runs nineteen native tests at each of
optimization levels zero and three. Counts overlap; this is not full canonical
or physical-hardware qualification. All bounded runs retained stable source and
owner-report snapshots. Raw local logs remain under ignored `outputs/cycle214-*`.
Progress/architecture/checklist regression passes 61/61 without skips in 34.397
seconds (runner35.234), log
`99561256817568CF85572EF0270D9F5AA8701DF4431A7A665BCF2E9D2105928A`.
Conservation confirms 359 source bindings, 1111 discovered tests and all 22
parent current records archived exactly, without native or prior-receipt drift.

## Continuity and Next Move

Readiness is 23/27. AP workers, SMP preemption, atomics and locks remain.
AP-worker recorded admission and at least 35 controls (18 AP-worker and 17 SMP
preemption) remain open. Six memory212 and three scheduler213 receipts,
CPU211, boot210, ownership212, native source, entry/core, previous checkpoints,
owner evidence and checklist coverage are retained. Inventory becomes 1111 tests;
the architecture binds 359 files and 22 parent records are archived unchanged.
No phase, flag or production gate closes. The profile-local historical closure
boolean is not the roadmap's broader SMP integration closure.

Demo ISO SHA256 remains
`3533965B0DFEA0BFC55399929A9770979B50E4077E77201A68B8331D76570378`.
No key, signing, tag, release, firmware or physical-media action occurs. General
task/CPU retirement, independent builders, authentication and production remain
unproved. Main merge still requires full exact-candidate canonical, Doctor,
release, publication and GitHub/review gates; branch backup is separate.

Next: `N12-SCHED-AP-WORKERS-001`, repair recorded AP-worker admission and its
eighteen unproven control groups, preserving counterexamples and qualifying fresh
execution before proceeding to SMP preemption, atomics and locks.
