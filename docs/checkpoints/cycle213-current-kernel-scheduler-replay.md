# Cycle 213: Current-Kernel Scheduler Replay

Date: 2026-10-03. Status: pre-production, scoped qualification only.
Parent: `b183dfa57b842236f261ec495eebdca45cdb2b27`.
Move: `N12-SCHED-001`, then preemption and deferred work; N12.4-N12.7/N36.
Requirements: `ADD-N12-SCHED-FOUNDATION-001`, `ADD-N12-SCHED-PREEMPT-001`,
`ADD-N12-SCHED-DEFERRED-001`, `ADD-N36-RECEIPT-COVERAGE-001`.

## Intake and Deliverable

The locked 10512-line, 8996-requirement, 171-section checklist remains bound at
SHA256 `A8C94719FAF9428C1F133010BA2603C0270C4E1EFD7327AF8EAB9C8C362ABB3D`.
Parent intake validates 357 source bindings, 1108 discovered tests and 19/27
selected readiness checks. PooleGlyph Phase 65 remains unchanged: manifest
`A2387DD5A9E51BA50493E1E39E5D9B0FCE304BAFDF57567552AB3CE30DAC7CE9`, ZIP
`F3CCEB701CF76274D9464A0958BF6106888FB34F3C0BFBD55DE4ACE03C427ABC`.
The owner's dirty report is preserved. No ABI or source-syntax promotion follows.

This cycle delivers three fresh current-image receipts and a stricter aggregate
deferred identity check, not new kernel bytes. N0 custody and N5 authentication
remain unresolved and do not prevent this bounded owner-independent move.

## Executed Evidence

| Profile | Fresh boots | Groups | Cases | Receipt SHA256 |
| --- | ---: | ---: | ---: | --- |
| Scheduler | 2 | 28 | 115 | `687FC1818AB0E00E533AFAD88D4C905807543F9F78676233CC332B9A25F9BE69` |
| Preemption | 2 | 25 | 226 | `CAFD7C7140E8912246E1CFA52EA3BEC2382FD519DE824DFE9B41E1CA2CA44DD2` |
| Deferred | 2 | 30 | 254 | `E956D15D43CEA3B0E5E14821115123DE69DAEFB9E75AC46C2F89A159CD93219F` |

All six boots pass on kernel `AE3422B2D44E6EC87AB1D5B51414C023E46F2EE3461A0D0895B9D1242E10D25A`.
The 595 cases comprise 545 executed rejections and 50 compiled-native boundary
cases. Each qualifier uses the current 246-test kernel evidence. Linked switch
scope remains 18 instructions/36 bytes, with 1323 image relocations.

All 47 focused tests pass, no skips, in 61.783 seconds (runner 62.704).
Log SHA256 `3941A59CEFFBF5D290FF9D3CF2095AD3B0D6AC0970DCF865A1219E2508B5E385`.
Coverage includes 700 generic recorded mutations, 26 additional preemption and
42 additional deferred mutations, 14 independent linked-identity cases,
seven disabled preemption and twelve disabled deferred native variants.
Source and owner report remain unchanged during execution. Case and test counts
overlap; no full canonical or physical-hardware qualification is claimed.

Qualifier logs, respectively:
`05FDDA173940B525A595C1426BC1D07FB610D321F79F5CF33C3A58364A100696`,
`C4CA732801FB906F7442652BE154022EA0C59C4E633C31145D785E2F4E5A52F5`,
`E12A45434566B849DD8DC27938DC5EE50E8BFA45D9F58DD3867479C1C06D291E`.
Local audit records are in ignored `outputs/cycle213-*`; this checkpoint and
tracked receipts retain their important identities and outcomes for cloud backup.

## Preserved Failures and Repair

All guests passed. Deferred admission initially failed with
`PKSCHED3 host oracle, source, or linked switch audit changed` because aggregate
pins still named the old A943 kernel and 1326 relocations. Current entry and
linked evidence independently establish AE3422 and 1323. Updating those two pins
admits the identical candidate, with no schema/component bypass or guest rerun.

A diagnostic then substituted float 1323.0 for integer 1323. Full admission
rejected it before and after repair. Only an isolated aggregate pin, with schema
and component validation deliberately bypassed, accepted it before repair.
An explicit integer type guard now rejects it independently. The regression
retains a genuine passing positive and rejects old hashes/counts, null, boolean,
empty hash and the equal-valued float. This is defense-in-depth repair, not a
claim that a malformed receipt passed the full release gate.

Initial progress/architecture/checklist regression passed 57/60 in 32.354 seconds
(runner 33.172), with three stale progress assertions. Log SHA256
`ADF15E460BCB8CD21E92EB6E06D9246E8B1A33E53B6805C67B688696F4709D33`.
Those assertions still expected eight pending profiles and stale deferred
evidence. They are corrected to five pending profiles and the admitted deferred
receipt, while SMP remains explicitly pending. The failed run is not a pass.
Corrected metadata passes 60/60 with no skips in 34.041 seconds (runner 34.828),
log `4ED07E0803CF5E14C092475A750AC8A5362ED2F25E3898D5871C76B88119B953`.
The first retry launcher invocation rejected a hyphenated tag before spawning
tests; its alphanumeric correction launched the recorded passing run.

## Continuity and Remaining Work

Readiness is 22/27 selected profiles. Five remain: SMP scheduler, AP workers,
SMP preemption, atomics and locks. AP-worker recorded admission and at least
35 unproven control groups (18 AP-worker, 17 SMP-preemption) remain open.
Cycle 208's sixteen repaired SMP control groups are not still counted as open.
Retained memory212, CPU211, boot210, ownership212, entry/core and native source
are unchanged. All phase/flag statuses and prior checkpoints are preserved.
Current metadata targets 358 bindings, 1109 test inventory and 22 archived
parent records. Those counts are not execution evidence.

The demo ISO remains SHA256
`3533965B0DFEA0BFC55399929A9770979B50E4077E77201A68B8331D76570378`.
No ISO rebuild, release, key operation, firmware or physical-media write occurs.
General task/CPU retirement, physical hardware, authentication and production
completion remain unproved. Main stays qualified Cycle 175 until exact-candidate
canonical, Doctor, release, publication and GitHub/review gates pass. Checkpoints
can be backed up on PR #78's branch without bypassing those gates.

Next: `N12-SCHED-SMP-001`, replay the already repaired SMP qualifier on the
current image, then address AP-worker admission and remaining control execution.
