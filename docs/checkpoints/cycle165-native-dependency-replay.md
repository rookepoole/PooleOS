# Cycle 165: Current-Kernel Native Dependency Replay

Status date: 2026-09-08
Scope: N9.1-N9.4 memory/ACPI/VM, then existing N8/N12 dependency profiles.
Status: pre-production; selected native checks pass, full qualification pending.

## Final Evidence

| Profile | Final Boots | Markers Per Run | Control Groups | Rejected Cases |
|---|---:|---:|---:|---:|
| PKPMM7 / PKACPI1 | 2 | 45 | 191 | 191 |
| PKVM3 | 2 | 40 | 48 | 48 |
| PKIRQ1 | 2 | 36 | 58 | 58 |
| PKSMP1 | 2 | 38 | 72 | 72 |
| PKSMP2 | 2 | 42 | 19 | 159 |
| PKSMP5 | 2 | 40 | 30 | 243 |
| PKSCHED1 | 2 | 34 | 28 | 115 |
| PKSCHED2 | 2 | 35 | 25 | 178 |
| PKSCHED3 | 2 | 37 | 30 | 208 |
| PKSCHED4 | 2 | 37 | 32 | 209 |
| PKSCHED5 | 2 | 37 | 34 | 226 |
| PKSCHED6 | 2 | 38 | 34 | 232 |
| PKATOM1 | 2 | 41 | 29 | 78 |
| PKLOCK1 | 2 | 35 | 30 | 103 |
| Total | 28 | Profile-Specific | 660 | 2,120 |

All final receipts use the unchanged Cycle 162 kernel:
`D0AA3295F66AF02D48476BCEDC44D962A873E98FBA21F48A6753AA7BB9B24EA4`,
525,976 canonical bytes, 598,016 image bytes, 146 pages and 1,319 relocations.
Every live qualifier passes 228 kernel host tests. The independent PBP1,
marker, lifecycle and linked-instruction checks retain their bounded scopes.

Six initial scheduler-preemption, atomic and lock boots are preserved as
superseded evidence after correcting their bound tests. They are excluded
from the 28 final boots. Each qualification batch verifies that tracked
non-receipt source stays unchanged throughout execution.

## Repairs and Failure History

The memory guide still described a 144-page layout. Its manager, ledger,
stack, handoff and guard positions now match the implemented 146-page layout.
Historical Cycle 156 measurements are explicitly labeled as historical.
The VM guide no longer claims that its data-release path scrubs the frame;
scrub-before-reuse integration remains open.

The initial memory/map suite passed 23/24 tests: only obsolete release-gate
page totals failed. Actual source usable, loader-protected and final managed
pages are 117,820, 924 and 129,080. Independent reconstruction accounts for
the two extra protected kernel pages. VM maps 117,819 owned pages across
eleven ranges with 12,946 hole pages and 243 tables; it retains six ordinary
free rejections, three local invalidation receipts and exact generation retirement.

After live replay, the pre-pin projection passed 16/27. Eleven gates still
expected the old 219-test kernel, with four also expecting the old linked
image and 1,305 relocations. Only measured acceptance pins and displayed
counts changed; validation and non-promotion conditions remain enforced.

The wider 142-test sweep then found three stale test expectations. Their
corrections were followed by the three fresh qualifier reruns above. A new
test initially selected the switch-audit key for INVLPG profiles; that test
setup was corrected to the actual distinct audit keys before final execution.

The final 142-test profile/map/gate suite passes with two optional local
transcript skips. Fresh live qualifiers validate their own actual transcripts.
Six memory-accounting and nineteen host/image stale-value controls reject,
as do fourteen separately checked production-overclaim mutations.

## Progress and Remaining Gates

All 27 selected native checks pass, including the earlier current N5/N7 chain.
This is not a full canonical or Doctor pass. The failed Cycle 162 audit remains
historical at 81/105 and Doctor683/706; it is not a current aggregate score.
Main remains qualified Cycle 161; draft PR #75 is the source backup.

Next: full runtime-inclusive exact-final canonical qualification with both
bundle and replay inputs, then publication and GitHub review/merge gates.
Only afterward resume `N12-CONCURRENCY-RECLAMATION-001` execution-stack and
general CPU-retirement ownership. Keep data-frame hygiene explicit in N9/N12.
No new owner action is required for the next development qualification.

All 40 phases, 301 subphases, 57 added requirements, 94 flags (35 open),
twenty program gaps and 8,996 locked requirements are conserved. No phase or
flag closes. Existing N36 evidence review remains open. PooleGlyph Phase 65,
its owner's modified report and the frozen demo ISO are unchanged. N0 custody,
hardware, native services, desktop and signed production ISO gates remain open.
No key, signing, release, firmware, driver or physical-media operation occurs.
