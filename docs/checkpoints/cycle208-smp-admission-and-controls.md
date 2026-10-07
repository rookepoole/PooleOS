# Cycle 208: SMP Admission and Executed Controls

Date: 2026-09-30. Parent: `bf336b3b7f081657c992383f795949788c7c5b36`.
Move: `N12-SCHED-SMP-001`, N12.4-N12.7/N36, under
`ADD-N12-SCHED-SMP-001` and `ADD-N36-RECEIPT-COVERAGE-001`.
Goal remains active. The preceding backup-status turn did not advance implementation;
this cycle makes a concrete proof-path repair. No live prior worker was resumed.

## Changes

- Strict admission reparses both guest runs and rejects malformed roots, shapes,
  exits, run coverage, markers, summaries, digests, handoff bindings, observations,
  profile types, dates, control counts, host/native probe output and source/linked identity.
- Thirteen compiled-native groups execute 59 scheduler boundary scenarios against
  the unchanged actual module: topology, duplicate queues, stale generations,
  ownership epochs, seven acknowledgement fields for each transfer kind, offline
  timeout, late acknowledgements, rollback, load selection, fairness and idle ownership.
- Three source-audit groups execute 35 register, 10 cleanup and six heap/callback
  mutations. Fourteen GPRs are stack-saved/restored and RBP must remain untouched.
  These source checks do not establish live injected-fault recovery.
- Empty rejection lists and disabled auditors fail. Thirteen disabled native
  safeguards and nine prior transaction-repair mutations are detected.

## Preserved Failures

The genuine diagnostic baseline passed two fresh boots in 78.141 seconds, but
the aggregate gate retained a former image/relocation pin. Its receipt is
`9C4B82AAFA5162900F1C3FEEB2E9E8AAD96B01D601DFBE75C9E5DF7F7329A128`;
log `13585A2EF1DF0382F00F0D754972A92396003A1D0F963BE63FAE3E23BF9E34F1`.
After correcting only the pin to the measured current kernel, the same baseline
passed both positive validators. Of 279 corruptions, runtime accepted 264,
rejected 11 and threw four exceptions; the actual gate accepted 168, rejected 93
and threw eighteen exceptions. That baseline was not admitted as the final receipt.

Initial five-method control tests had one failure and one error: the cleanup
source anchor matched two places, and a broken native variant panicked through
`unwrap()` instead of the required explicit assertion diagnostic. The next pass
had one diagnostic-text failure because the custom assertion omitted the checked
word. Both were harness defects; the native positive scenarios passed throughout.
Failure logs: `41B9E766EF036436851707DF7151724C2DE8E11EFAF79D0CC94FDD23E93A5DD9`
and `00B32EFC644F183B4FD01437E0797AEEFEE0984F808ED5F0FD0416CD1A02ABE5`.
Repaired controls passed 5/5 in 15.817 seconds; log
`4CB234E0203A98948C61090D90A06D1D62A2D3F5095AE73B5407779454A94255`.

## Fresh Qualification

Two new final boots pass 37 markers each, with six AP dispatches, two BSP
dispatches, nine acknowledged operations, one timeout rollback and exact cleanup
of 102 pages / 417,792 bytes. All 32 groups pass 303 cases: 244 rejections and
59 native boundary scenarios. Final receipt:
`31C084B5C7AEA66051FD8E36785C4CE8E2C8FF5FEA2701023CCBDE41BC2540F0`.
Qualifier elapsed 82.500 seconds; log
`B4AFCEDC4E0B5203EA8C7434E85C6ABD1BFF4D8CFEFFE76250C1A9A84BB46958`.
The exact generated receipt passed runtime and aggregate admission before copying;
its predecessor `47382C39021EB7BF6580844B6E4B1F2BAC53C05FD56ECB2313E036C81A1A391C`
is preserved. No manually rebound positive fixture was used.

An intermediate repaired receipt passed two boots in 80.172 seconds:
`F41F52E82975EBF8BAEB0F1BA34E5CCA8EC91BD307F7E456D2CC8953BBA334DA`.
It is superseded only because review corrected the source-audit field from
"saved" to "preserved": fourteen stack-saved registers plus untouched RBP.
Its 18/18 regression took 44.078 test seconds / 45.000 runner seconds; log
`B5F300419FC4528161C70E57806BA7DABFA8FFA0ED4865608D7D5AFF29101D80`.
Six boots ran in total: two final, two diagnostic, two superseded. None failed.

Final focused regression passes 18/18, zero skips, 43.037 test seconds / 43.891 runner
seconds. Log: `6CFB867BF66A5649ED611A9419F0F595377E1D98AD1FFFFABCEEFD478E49ACC0`.
Both boundaries reject all 279 original corruptions without exceptions; another
47 record mutations and eight independent aggregate checks pass. Nineteen native
transaction tests pass at optimization levels zero and three. Counts overlap.
Every bounded run retained unchanged source and owner-report snapshots.

The first metadata pass was 44/47 with three stale assertions: two expected five
pending profiles, and one expected the now-current SMP entry to remain stale.
The historical-entry check now uses the still-pending AP-worker receipt, without
altering historical hashes. Failure log:
`ED544BB52B327FBE15CB5C48322F20F674D8D66E4D5D639D3D165B14D5A4EFFD`.
The second pass included eight checklist tests and passed 53/55; two later
assertions still expected five pending profiles and 22 passing checks. Those
expectations were corrected to four and 23. No native runtime failure occurred.
Second failure log:
`D3035C52EEE4D1E97C16BBA6DB0A738F161657DC243D64F36BD1DA2E2530F6CC`.

Repaired metadata passes 55/55, zero skips, 29.237 test seconds / 30.000 runner
seconds; log `B230C6D837A92A60C31FCDF74006D714957F58C21E16B68165EA7B2CC8CAC864`.
The combined scoped regression passes 183/183, zero skips, 246.093 test seconds /
247.031 runner seconds; log
`C6ED9CEC90D55F7EF6DD2B176AA4621E25ECD5BC596616AD0ED20592977AE4BE`.
It covers scheduler controls and transactions, entry/core and host provenance,
boot/memory and selected dependency gates, publication, roadmap, architecture
and checklist. It also runs 19 SMP and 21 deferred native tests in both debug
and optimized builds. Source and owner data stayed unchanged during execution.
These counts overlap the focused tests; this is not the full canonical suite.

## Preserved Scope

Kernel203 remains byte-identical: canonical SHA-256
`A943DCB6E41A27F952868F05ED2B3523B47D9D7A7B5DB909EE385205F7CA3B31`,
530,072 canonical bytes, 602,112 image bytes, 1,326 relocations and entry `0xA000`.
Entry/core and qualified boot204/CPU205/memory206/scheduler207 receipts are retained.
The checklist and coverage stay locked at 10,512 lines / 8,996 requirements.
PooleGlyph Phase 65 remains metadata-only; its manifest/ZIP hashes and dirty
owner conformance report are unchanged. Phase 66 executable Core IR remains next
in that lane. There is no syntax, ABI, PGB2/PGVM2 or cross-repository migration.

Readiness is 23/27. No phase or flag closes; SMP integration/closure review remains
open. At least 35 constant-only groups remain in AP workers and SMP preemption.
N0 custody, N5 authentication, general task/CPU retirement, independent builders,
physical qualification, N12 exit and production remain unproven. No native feature,
new ISO, signing, key, firmware, physical-media, tag or release action occurred.
Recorded consistency is not authentication or proof against coherent forgery.
The current demo ISO is unchanged; ignored media/raw logs/tools are not Git backup.
Source inventory is 1,100 Python tests, not 1,100 executed tests. The architecture
baseline binds 351 files and the roadmap archives all 19 prior current records.

## Next Move

`N12-SCHED-AP-WORKERS-001`: inspect recorded evidence admission and the eighteen
constant-only groups, preserve genuine counterexamples, repair and test native
boundaries as indicated, then qualify fresh AP-worker execution. SMP preemption,
atomics and locks follow before full exact-candidate canonical/Doctor/release/
publication/GitHub check-review qualification and main merge.
