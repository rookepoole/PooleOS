# Cycle 197: Native Deferred Transactions

Status date: 2026-09-29
Move: `N12-SCHED-DEFERRED-001`, supporting N12 and N36
Requirements: `ADD-N12-SCHED-DEFERRED-001`, `ADD-N36-RECEIPT-COVERAGE-001`
Status: native host repair verified; changed-image guest qualification pending

## Native Implementation

Real controller tests found state publication before fallible counters completed:
enqueue could retain a partial reservation, claim could consume queue/worker
ownership, completion could alter operation lanes, and cancellation/retirement
could partially finalize work. Batch retirement and shutdown could fail after
earlier slots changed. Premature shutdown could retire completed work before
intake closed. A BeforeExecute fault also consumed priority-bypass accounting.

Fixed-size candidate copies now commit accepted operations and only documented
duplicate/fault diagnostic transitions. Compound dispatch and batch retirement
are transactional. Shutdown rejects before retirement unless intake is closed.
Pre-execution faults preserve fairness. No heap or callback API is introduced.
Transaction integrity here is not a claim of cross-CPU atomicity.

## Verification

The original native probe passed eight tests and failed eleven of nineteen.
Failure log: `91AF75227D825FE8F7DF3AC9E9AAB18C9C50901C0BFBCE3A4C7CE9D9E8215220`.
The same nineteen then passed; log:
`DEA2DEEFCAB48E4BCBE8ACF5D913236DA3B6BC926D97EC2CF447718EED8B18A1`.
Expanded coverage passes 21 tests at both optimization levels 0 and 3, including
seven existing native tests and fourteen new transaction tests. Four separately
compiled disabled shutdown/fairness/cancellation/retirement variants fail.
Expanded log: `26DE0DFB7FEFB5C368F2B76CF84142F6AC86B8C42DAE872EA03B7396270FC45D`.

All 17 native core stages pass in 37.578 seconds, including 246 kernel, 40
lifetime and 19 reclamation tests per host profile, plus 15 compile-fail tests.
Core log: `2AB8D226E34E1EC1FD773B540A39E2E660DA56CAD8E6063453F24A14CBE3DD9D`.
Core receipt: `23E8AEC41CEDD9804EBD24023B4DFC68318AC13BD6DF9DCFD531B1A21A0F5BFE`.

Entry qualification passes two exact clean builds and 43 rejection controls in
38.609 seconds. Log:
`5B006AC3BCB5E5F7BF1AB0368F017F13585D71B9400A5817324AEFEACAC5F53A`.
Entry receipt: `70814DA7358BEE6FA6E5D2341D251ACE57A906BA4FB2E9E12BD8D53677C7E38D`.
Build ID: `PKBUILD1-CYCLE197-N12-DEFERRED-V1-0000000001`.
Canonical image: 530,072 bytes, 1,326 relocations, entry 0xA000, loaded size 602,112.
Kernel SHA-256: `B19D4F7E854ECED3495D88C00F7379061B913EF00477FBD3701929B2F77D80F1`.

The 53-test scoped regression passes without skips in 115.797 seconds and
reproduces the exact entry receipt again. Log:
`42D04FDE2D8E64FEF457773D430D874258DA593C14A74DE1A4DC9CC104838DF7`.
One additional entry-gate test passes twelve rejection cases; log:
`208927165B913AA833216B549755DC2F394BBC064E44FCF4AABEA2281672AE34`.
These are 54 Python methods, not full canonical/Doctor qualification.

The first metadata regression passed 31 of 36 tests and failed five historical
profile assertions that still expected old-image receipts to be current. Log:
`83202FF14EDE1F534879D537ED10B5B2C0D9B563441AF3AF352B773AD690DB00`.
Those assertions now require the embedded-entry mismatch and a rejected current
gate; no historical receipt or positive admission predicate was rewritten.
The corrected metadata, architecture and checklist suite passes all 44 methods
without skips in 8.297 seconds. Log:
`474C2C4792E4322663DB560DDD56279DD7E5DE1806ABC0D2489D16B7F08DE9AF`.
Together with the 54 scoped methods above this covers 98 distinct methods;
it does not replace the full canonical suite or changed-image guest replay.

## Preserved Admission Gap

A genuine old-kernel two-boot baseline passed its original validator and gate
before corruption. Of 121 mutated records, runtime accepted 114, rejected three
and raised four exceptions; the gate accepted 47, rejected 73 and raised one.
Audit SHA-256: `FE54D3F330EF99C6367F01336AD7D0DD909F3CAC07B91B1E603763F39BED5D5F`.
Baseline SHA-256: `CFAE9962A392540B7DFED0C94E174FC48E51DAEFC423B70DCDFD182EAFC22709`.
The old qualifier reports 208 cases in 30 groups, including 14 constant-only
groups. This baseline is diagnostic only, never final qualification. Native
repair does not fix recorded-evidence admission; that work remains open.

## Progress And Next Move

Selected readiness is 3/27 for the changed image. Twenty-four dependencies need
replay starting `N5-SYMBOLS-SEMANTICS-001`, then ordered boot, CPU, memory and SMP
profiles. Repair deferred admission and execute its controls before admitting
fresh deferred evidence, then finish scheduler/atomic/lock qualification and
full exact-candidate checks. The known control gap remains at least 65 groups.

Reopen `FLAG-N12-SCHED-DEFERRED-001`; keep the N36 evidence flag open. Roadmap 197
archives prior current records without rewriting their contents. No phase,
normative charter condition, owner data, demo ISO or production gate changes.
This cycle runs no new-kernel guest, hardware, signing, firmware, physical-media,
tag, release or production action. Exact-source regression, conservation and
index publication checks are required before pushing this checkpoint. A pushed
agent branch is cloud backup, not main-merge or production qualification.
