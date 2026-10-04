# Cycle 222: SMP-Preemption Admission and Controls

Status date: 2026-10-04. Pre-production, single-host evidence.
Parent: `5bd982f8cf6aad3cba4ac91823be7cbcd31e8887`.
Move: `N12-SCHED-SMP-PREEMPT-001`, N12.5-N12.7/N36, retaining N12.1-N12.4.
Requirements: `ADD-N12-SCHED-SMP-PREEMPT-001`, `ADD-N36-RECEIPT-COVERAGE-001`.
The intervening cloud-status response made no implementation progress. The
diagnostic process was confirmed terminal, its result preserved, and work resumed.

## Implemented and Verified

Replaced seventeen constant-only control groups: fifteen run **61 native
boundary scenarios**, and two execute **46 source-audit rejection mutations**.
The harness compiles the actual Rust controller against the native scheduler;
it does not substitute a Python model. Cases cover CPU/APIC, frame/timer epochs,
stack bounds, deadlines/order, ACK binding and ownership, offline timeout,
source rollback, late ACK, watchdog, bounded fairness, and duplicate admission.
Source mutations cover AP register save/restore and park/scrub/release checks.
They are not privileged guest fault injection or general concurrency proof.

Recorded admission now reconstructs both guest transcripts, summaries, hashes,
handoff bindings, exact typed counts, probe results, source and linked audits.
Malformed roots and nested records reject without exceptions. The aggregate
gate independently checks the measured current image and integer relocation
count. The old optional temporary-log test now checks both retained transcripts.

Two final four-vCPU boots pass **34 groups/322 cases**: 261 rejection cases and
61 native scenarios. Final receipt SHA-256:
`6BA9A37CF1C6E067085858399302364376B07F5918D12D88439EB3E060E6E4D3`.
Runner182.562s; qualification log:
`32DC2A4F71B6B64BD879B86B7BF320B6707E712CE2B501643C06AF9AFB08F0EA`.
Each qualifier repeats the same 246 kernel host tests; do not add inventories.

Focused regression passes **19/19**, zero skips,48.173s (runner49.094s):
`02FD21CDA360173C162EAFDD2170A9A7BC626A593919F0ABC04655FE5CC56723`.
Runtime and aggregate admission reject288 generic and51 additional corrupt
records. Eleven isolated aggregate cases reject with component validation
disabled. Tests detect15 disabled safeguards and14 disabled transaction repairs.
The existing27 native transaction/continuation tests pass at optimization0 and3.
Source and owner report remained unchanged during execution. Counts overlap;
this is not full canonical qualification.

## Preserved Failures

The original diagnostic's two boots passed, but runtime admission accepted273
of288 corrupted receipts, rejected11, and threw four exceptions. The aggregate
rejected obsolete image pins. Original receipt:
`5DEFF9E6E8E9DDB28B9970E9359260EAAB5D73875FC33FE03A997D9F1391A273`.
Diagnostic log:
`5A56B9FF83DB43A371DE1BE3FA26672B7FE0C31E1D20FE8E0B73A4E56A15BF21`.

Initial native harness regression failed one of five tests: disabling a
redundant watchdog check was masked by another check. A discriminating stored
watchdog-bound mutation replaced it. Failure log:
`73A5E6FC6BF3D4B07844D46D82C6702B0060947917F5357E1D80842E6D6F5A17`.
An initial focused run passed18 tests and skipped one temporary-log test;
the strict runner rejected that incomplete run. Log:
`68D5F65E7B557A92DCDC383893B90C422D023A29A264DACFC9C34F669E82A084`.
Two passing intermediate candidates (four boots) were superseded by test-file
changes, first an inventory assertion, then the retained-transcript test.
Across this cycle: eight successful boots, only two in the final receipt;
six diagnostic/superseded boots excluded. No failed guest boot was observed.

## Progress and Boundaries

Readiness **24/27 -> 25/27**. Next `N12-CONCURRENCY-ATOMICS-001`, then locks,
N36 shared-helper transitive-binding review and full exact-candidate canonical,
Doctor, release, publication and GitHub/review checks before main merge.
The known seventeen control groups are repaired; broader N36 remains open.

All25 parent current-progress records are archived. Phase/flag statuses remain:
40phases,301subphases,94flags/39open,57ADD requirements. No new ADD is needed.
The locked checklist remains10512lines,8996requirements,171sections. The new
inventory is1149 Python tests, not a full pass; architecture binds377 sources.
The initial metadata run executed69 tests with17 failure records from stale
current-progress assertions and the prior-cycle schema. Log SHA256
`4D209E8E02E6C2A16B4C9727BBBC47B8A6B57A501637DE3423D58D9331277920` is
retained, not admitted as a pass. The second run passed67/69 with two remaining
current-profile assertions (log `CD5C09A733464EEF374BAC32507ECB152E5FEEE666C44E352BE747030FD901CA`).
Corrected metadata passes69/69, zero skips,36.550s (runner37.359s), log
`3BFFDFB4AA86B875CC9F675F58B97967D69B439B6D58FEDFDA7821E00A395486`.
Initial conservation detected substitution of the current test count into
Cycle221 historical evidence; that count is now frozen at1139. Corrected
conservation passes all 377 bindings, 25 archived parent records, the 1,149-test
inventory, and unchanged native, checklist, owner, ISO and normative-charter bytes.

Combined regression passes **167/167**, zero skips, in 241.386s (runner 242.375s).
Log SHA-256: `6696145C03D306EDC61DA3AE3E622CE53BB7481F6A218384971D74661F116751`.
It includes the focused, retained SMP/AP-worker/IPI/capture, and 69 metadata
tests; these counts overlap and are not a full canonical pass. Source and owner
data remained unchanged during execution. Only progress documentation and its
generated bindings change for closeout; these receive a final metadata replay,
conservation check and exact-index publication scan before branch backup.
Cloud backup is through PR #78, not a main merge or production promotion.

Kernel216, entry/core and earlier profile receipts are unchanged, as is the
demo ISO. PooleGlyph Phase65 remains newest; manifest/ZIP and owner-modified
report are unchanged. No language, Core IR, VM, ABI, policy or IP migration;
Phase66 remains unqualified. N0 custody, N5 authentication, full architectural
state, general retirement, physical hardware and independent builders remain
open. No phase/flag closure, signing, firmware/media action or production claim.
