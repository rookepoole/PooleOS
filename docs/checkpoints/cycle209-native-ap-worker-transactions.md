# Cycle 209: Native AP-Worker Transactions

Date: 2026-09-30. Parent: `02fbece947413eda7b47dbc3c022d8a977457e48`.
Move: `N12-SCHED-AP-WORKERS-001`, N12.4-N12.7/N36 and N6 image qualification.
Requirements: `ADD-N12-SCHED-AP-WORKERS-001`, `ADD-N36-RECEIPT-COVERAGE-001`.
Goal active. The intervening cloud-status answer did not advance implementation;
this cycle resumes the existing repair, without restarting completed runs.

## Native Repair

The actual `scheduler_ap_workers.rs` controller could consume queue, priority,
generation, pending-ticket, ownership or shutdown-intake state before returning
a checked-counter error. The new allocation-free stage/validate/commit wrappers
cover enqueue, both dispatch paths, acknowledgement, cancellation, timeout,
reclaim, batch retirement, worker offlining and shutdown. Duplicate suppression
intentionally commits only its diagnostic on a duplicate rejection.

Dispatch locally preflights pending typed consumer commits in transaction order,
not CPU index order, before publishing work. It reserves no remote authority and
does not fabricate an acknowledgement. Actual acknowledgements still require
exact ticket/generation/payload/result/checksum validation. Generation MAX cannot
wrap to zero; aggregate validation uses wide sums. Controller size is bounded
at 2,048 bytes. Exclusive ownership is required; this is not cross-CPU atomicity.

The new fixture compiles the actual native module and links the real kernel
library and IPI constants. It compares complete private state, exercises failure
and retry paths, EOI/stale-ticket fences, competing pending work and service order.
Thirty native cases run in both debug and optimized builds, including twenty
new fault cases. Fifteen independently disabled repairs must fail the suite.

## Preserved Failures

- Before repair: 28 native cases per host profile, 12 passing and 16 failing.
  Log `C02F786B0630E8D7C6EF1F12FA3E5F6F8A0F75DBE4EA78999AB4A234E7CC13A4`.
- First repair failed compilation because Option comparison was not const-stable;
  explicit checked-add matching repaired it. Log
  `74ECE56963B6689C14523713F27CD62884A527BA12E9CE42D82C771FBA3AFFAF`.
- An existing service-order test expected rejection at acknowledgement rather
  than before dispatch. The stronger test verifies both early rejection and the
  retained acknowledgement fence/retry. Log
  `8D31C21C74CE59D378AD2ED1CD8319B6ED5854E90B9EF62729F7888A673C8F9F`.
- Formatting changed a mutation anchor; the harness rejected it, then the exact
  anchor was corrected. Log
  `EF07FB07EF4639002B3E9A41C0B45BE27325A8F624A910C51CE5E80F89BD7FD3`.
- Linker rejects measured text, RELRO and image shortages of 1,150, 144 and 3,572
  bytes. The three logs are respectively
  `6838C356CCE2C342F62F83A8E83911103EDD7E12ADF73E7C7B9FA613F960B2C2`,
  `F7E1E22320A8239F2951EC52CEAE5CA5B5F279355A20B50344ABC89D00E755D7`,
  `CF5826CE9C77B09C012C9B0FEEA692C9607B654555BDFEA55B6600FFAC281A6C`.
  Each endpoint grew by one required page; no failed build was admitted.
- Initial metadata ran 56 tests with 23 failure records (including subtests),
  followed by 53/56 passing after the first correction. Remaining assertions
  still expected old-image evidence to be current. Logs
  `10DB2FC9AACC7A4B4577F8D9F1FF2BD5E55B3EE816785E3DA16458563498DCD9`
  and `E5147F725F88B41A121AA2C63DC35714CCB7F53BECF24DC82790BBBEC083FF4B`.
  Conservation also caught a helper's accidentally replaced hash literal and a
  temporary metadata-test indentation error; the actual checklist never changed.
- Initial combined regression passed 116/117, zero skips, in 163.711 test seconds
  (164.625 runner). Transfer validation still pinned the Cycle 203 build ID.
  It is corrected to the qualified Cycle 209 ID without rebinding old receipts.
  Log `3E7D107D74277F38D93E71AD48473FE6DCDCE3D55D375E45BA6CCBB972A4783E`.
- Second combined regression passed 116/117 with one error, zero skips, in
  172.417 test seconds (173.343 runner): the synthetic transfer fixture still
  carried Cycle 203's ID. Its current-ID baseline and old-ID negative cases are
  corrected, with explicit baseline acceptance before mutation checks. No guest
  transcript is changed. Log
  `1AB00AB6C637EF2DBF33D9B7AE607D13D79721679AD793C7E6ED9D1C0074E8F6`.

## Qualification

Six AP/SMP/deferred transaction Python methods pass with zero skips, including
30/19/21 native cases per optimization level and 15/9/4 disabled variants.
Runner 31.047 seconds; log
`401921DBF877082D913FDB223D23DFF814CF04D269351C09E85A9626801209AE`.
All 17 core stages pass in 39.547 seconds, including 246 kernel regressions,
19 core and 40 lifecycle tests per profile and 15 compile-fail borrow checks.
Core log `2AB8D226E34E1EC1FD773B540A39E2E660DA56CAD8E6063453F24A14CBE3DD9D`.
Entry qualification passes two clean matching builds, 246 kernel tests and 43
hostile image controls in 38.390 seconds. Log
`812247C631861F134E36E05396EF5D5167953BCFF34A0322E7CA7A343FF45D3E`.
All bounded executions preserved source and the owner's PooleGlyph report.

Build ID: `PKBUILD1-CYCLE209-N12-APW-TXN-V1-00000000001`.
Canonical 534,168 bytes, SHA-256
`72C37783A5729229E6A259E38DC8DF55034FD467B77839FFFC4AA62B66E33EBF`.
Linked 7,091,272 bytes, SHA-256
`B29916B90D42010CCDBDCC8927E10F8FCEEF14020CA037051367CCB4CC29F841`.
Image 606,208 bytes; 1,323 relocations; entry `0xA000`; text end `0x74000`,
RELRO end `0x82000`, image end `0x94000`. Page alignment and W^X are unchanged.
Entry receipt `81D4EF8ABBF735A1A39B3E8D40966A9C299377BC36E77C469CCAA61BCB8788E8`
binds 76 inputs including all 39 kernel Rust sources. Core receipt is
`DD0436EFBAD686C4AB352EB1B4FF97F20158BB53DA7B44E3A7AC7F8143EA814F`.
Two builds on this machine are not independent-builder reproduction.

Final combined scoped regression passes 117/117, zero skips, in 163.739 test
seconds (164.703 runner). Log
`6A2F2869405F2693416AFF31CF008539BBDF7EDEBD651D2C5D608D134D094EEC`.
It covers AP/SMP/deferred transactions, core, exact entry receipt/product
reproduction, pinned host tools, transfer parsing and stale-ID rejection,
independent entry-gate controls, publication boundaries and all 56 metadata
tests. Source and owner report remained unchanged during execution. These counts
overlap the prior focused results and do not constitute the full canonical suite.
Conservation verifies twenty unchanged parent records, 354 source bindings,
1,103 discovered Python tests, 94 flags with 38 open, unchanged phase statuses,
and unchanged prior boot receipts, checklist, owner data, ISO and normative charter.

## Gaps And Next Move

Current measured readiness is 3/27: entry, policy and errata pass. Twenty-four
profiles require changed-image replay. Prior live receipts remain unchanged and
historical, not rebound to new bytes. All twenty parent current records are
archived before changing their status. The AP-worker flag is reopened; no phase
closes. Eighteen constant-only AP groups and seventeen SMP-preemption groups
remain, together with AP recorded-evidence admission. Host transaction tests do
not replace those controls or live fault recovery.

N0 custody, N5 authentication, general task/CPU retirement, independent builders,
hardware and production remain open. Checklist coverage stays locked at 10,512
lines and 8,996 requirements. PooleGlyph Phase 65, its ZIP and dirty owner report
are preserved; Phase 66 Core IR remains its next metadata-to-execution boundary.
The existing demo ISO is unchanged. No key, signing, firmware, physical-media,
tag, release or main-merge action occurs. Full exact-candidate qualification
still precedes merge; source-branch backup is separate from promotion.

Next: `N5-SYMBOLS-SEMANTICS-001`, qualify symbols and dependent boot profiles for
the new image, then CPU, memory and scheduler replay before AP admission/control
repair and qualification. Do not rerun completed host tests merely to fabricate
a new receipt identity.
