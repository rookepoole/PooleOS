# Cycle 171: Current-Kernel Native Dependency Replay

Status date: 2026-09-09
Scope: N9.1-N9.4 memory/ACPI/VM, dependent N8/N12 profiles, and the existing
N36 recorded-evidence audit. Status: pre-production; full qualification pending.

## Final Live Evidence

| Profile | Final Boots | Markers Per Run | Control Groups | Rejected Cases |
|---|---:|---:|---:|---:|
| PKPMM7 / PKACPI1 | 2 | 45 | 191 | 191 |
| PKVM3 | 2 | 40 | 48 | 48 |
| PKIRQ1 | 2 | 36 | 58 | 58 |
| PKSMP1 | 2 | 38 | 72 | 72 |
| PKSMP2 | 2 | 42 | 19 | 159 |
| PKSMP5 | 2 | 40 | 30 | 249 |
| PKSCHED1 | 2 | 34 | 28 | 115 |
| PKSCHED2 | 2 | 35 | 25 | 178 |
| PKSCHED3 | 2 | 37 | 30 | 208 |
| PKSCHED4 | 2 | 37 | 32 | 209 |
| PKSCHED5 | 2 | 37 | 34 | 226 |
| PKSCHED6 | 2 | 38 | 34 | 232 |
| PKATOM1 | 2 | 41 | 29 | 78 |
| PKLOCK1 | 2 | 35 | 30 | 103 |
| Total | 28 | Profile-Specific | 660 | 2,126 |

Each final qualifier passes 243 kernel host tests on the unchanged Cycle 168
kernel, SHA-256
`8A2DA65C86B09F7BCF2D5ACDB90029A5B7B7361581BA841ADC3B62AEE168B625`.
The image has 530,072 canonical bytes, 602,112 loaded bytes, 147 pages and
1,321 relocations. The runner bounds each profile to 600 seconds and verifies
an unchanged tracked-source snapshot throughout each command. No native Rust
or kernel-image bytes change in this cycle.

Four earlier successful boots, two SMP and two scheduler-preemption, are
preserved as superseded after changes to their bound validators/tests. They
are excluded from the final 28. No guest qualification failed.

## Memory And Ownership

Independent PBP1 accounting and live markers agree on 117,819 usable source
pages, 925 loader-protected pages and 129,079 final managed pages. The one-page
shift follows the current kernel reservation. The five-page manager starts
at `0xFFFFFFFF801BB000`; guarded ledger windows start at
`0xFFFFFFFF801C2000` and `0xFFFFFFFF801E4000`.

VM maps 117,818 owned pages across eleven ranges, with 12,947 hole pages and
243 tables. It records 367,405 table writes, 950,706 temporary PTE writes,
coverage checksum `0x3EA83610CCC8AD5F`, six retained-free rejections, three
local invalidation receipts, exact CR3 restoration and one generation retirement.
The existing ACPI snapshot, reclaim, scrub/readback and rollback controls pass.
General concurrent allocation, task-stack/CPU retirement, and VM data-frame
scrub-before-reuse integration remain open.

## Repairs And Failure History

The old SMP receipt could remain accepted after boot artifacts changed because
its input list did not cover those dependencies. The validator now binds the
current PKXFER1 receipt and all six regenerated canonical boot artifacts.
Both transfer runs must parse and agree with current artifact bytes; both SMP
runs must match that nine-file revalidation observation, including trust-policy
and trust-state digests. Historical receipt consistency is not source currency.

Five new test methods cover input bindings and nine rejection cases: three
consistently replaced boot digests, one stale transfer dependency, four malformed
dependency shapes, and one regenerated artifact-byte mutation. The first three
methods failed before repair (four failures and one missing-field error).
A later shape check exposed four uncaught exceptions; an explicit object check
repairs those failures. Fresh positive SMP execution and the final tests pass.
This does not authenticate evidence or close the broader N36 audit.

The first memory test suite passed 15/17: two aggregate-gate tests retained old
page totals. Nine measured PMM/VM acceptance values and displayed counts were
reconciled, then all 17 passed. After all profiles replayed, the pre-pin selected
projection passed 16/27. Eleven aggregate gates still expected 228 kernel tests;
four also expected the prior image and 1,319 relocations. Those measured pins
were updated without changing the remaining acceptance or non-promotion rules.

Two atomic/lock test labels were corrected before their fresh qualifiers. The
combined suite then found one stale scheduler stack-partition assertion,
146 versus 147 kernel pages. Its repair was followed by fresh qualification.
The final 155-test profile/map/gate suite passes: 153 passed and two optional
local-transcript tests skipped. The live qualifiers separately validate their
own actual transcripts. Final suite log SHA-256:
`C4B3696854EB1C5B8ED32025B98CF5B1DA0BDBC6BA7764B5975F739E80BEC2A0`.

Aggregate regression checks reject twenty memory-accounting mutations and
38 stale host/image values, while replaying seventeen CPU gate controls.
Fourteen separately checked production-overclaim mutations also reject. These
counts are separate from the 660 live-profile control groups above.

The first metadata suite passed 21/23 tests and exposed previous-cycle schema
constants and protocol assertions. Those status references are updated without
changing the charter, phase dependencies, exit criteria or flag dispositions.

## Progress And Next Gate

All 27 selected native checks pass, and reclamation evidence is separately
source-current. The fourteen final receipt hashes are recorded in
`runs/pdc_production_roadmap.json` under `current_dependency_qualification`.
Earlier Cycle 165/168/169/170 records retain their original identities.

Next is runtime-inclusive exact-final canonical qualification, with both bundle
and replay inputs, followed by exact-index publication and GitHub review/merge
gates. Only then resume `N12-CONCURRENCY-RECLAMATION-001` task execution-stack
and general CPU-retirement integration. Main remains qualified Cycle 165 and
PR #76 remains draft at this pre-closeout checkpoint. No new owner action is
needed for this development qualification.

All 40 phases, 301 subphases, 57 added requirements, 94 flags (35 open), twenty
program gaps and 8,996 locked requirements are conserved. No phase or flag
closes. PooleGlyph Phase 65, the owner's modified report, and the frozen demo
ISO are unchanged. N0 custody and the native services, driver isolation,
desktop, hardware and signed production-ISO requirements remain open.
No key, signing, firmware, host-driver or physical-media operation occurs.
