# Cycle 225: Retained Execution Source Closure

Date: 2026-10-07. Pre-production. Goal active. Previous turn: progress.
Move: N36.1, `N36-RECEIPT-COVERAGE-001`; existing `ADD-N36-RECEIPT-COVERAGE-001`.
No new requirement, phase completion or flag closure.

## Implemented

`runtime/native_execution_sources.py` validates the static Python import closure
of fourteen memory-through-lock execution profiles. The canonical record is
`runs/native_execution_sources.json`, SHA-256
`5C3F114B99CDE45A8EF6796CE7C16976040EFA3EDCD3436D93BE7D439BABEBB5`.
It covers 35-38 files per profile, 62 distinct files overall. Relative imports and
package initializers are included. Missing source, changed source, incomplete or
duplicate coverage, unsafe paths and recognized dynamic import/code operations
fail closed. The aggregate release gate executes this additional check.

The qualifier projects preserved command-run captures only after checking the
expected producer command, successful exit, unchanged-source observation, exact
current receipt/output bytes, retained log hash and every source hash in the
original execution snapshot. It does not update old profile input hashes. The
public record contains repository-relative source paths and hash identities,
not private absolute commands or raw local logs. Publication allowlists admit
only this named new record. Original profile receipts remain byte-identical.

The fourteen captures are the verified memory/IRQ/SMP runs from Cycle219,
scheduler/preemption/deferred runs from Cycle220, SMP/AP-worker runs from Cycle221,
retained SMP-preemption run from Cycle222, final atomics run from Cycle223 and
final lock cleanup run from Cycle224. This cycle performs zero new guest boots.

## Verification and Failure History

The first projection correctly stopped rather than invent a result, but its
command comparison did not account for a recorded Windows backslash separator.
Only separator normalization was corrected; the capture bytes and their hash
remain unchanged. A dedicated regression covers this case. Failed execution log:
`5D1BE8CC07802DE0E6E4FB9CB4615E7D10B70DE8A25D3364F4A7A7A5F30418D0`.
The corrected projection passes in 9.406 seconds, log:
`BD0F3E51C87B18BB8AED0D174028DAF2C94957B77212BCEF345A215983B8BE48`.

Focused suite: 12/12, zero skips, 16.490 seconds (runner17.344 seconds). Log:
`96523A51A6EB4F4466BAEF21182820D925D047507DD327BC3ED29368D5686C99`.
Tests use explicit synthetic captures for malformed and state-change controls;
one additional test admits the actual retained record and aggregate path.
They cover 33 malformed records through both validators; a shared-leaf change
invalidates all fourteen synthetic profile captures. Other cases exercise
relative imports, package initialization, missing imports, recognized dynamic
imports, changed logs, substituted output, failed execution, wrong producer,
unsafe paths, missing records and Windows path identity. Source and owner report
remained unchanged during execution. These are not new native faults or boots.

The first combined regression passed 101/102 with zero skips. One roadmap test
still expected the former shared-helper next-step label; it was corrected to the
new upstream/non-Python scope. The failure is retained, not counted as a pass:
181.581 seconds (runner182.563), log
`0F5FC9421945B47F37FE95C772FACCCB5E73158F7C65FCE4DECCEB2533076B4A`.

Corrected combined regression: 102/102, zero skips, 185.299 seconds (runner186.219).
It includes source closure, retained entry provenance, locks, publication controls
and 72 metadata methods; counts overlap the focused suite. Source and owner data
remained unchanged. Log:
`50F368CE66E375EEFC5FF65234BC17EC7C4F8D16C2ACC89E428A0533132F815F`.
Conservation verifies 387 architecture bindings, 1176 discovered Python tests,
28 unchanged parent archives and 801 preserved native, receipt and checkpoint files.

## Boundaries and Next

This guard establishes recorded static source consistency. It is not execution
authentication: capture hashes refer to retained local evidence, not signatures
or an independent builder. It is not an arbitrary-Python dependency proof.
Recognized dynamic constructs fail closed; obfuscated loading, interpreter and
environment provenance, non-Python inputs and subprocess/tool closure require
separate review. Data/tool/image dependencies already present in original
receipts remain enforced by those validators; complete coverage is not inferred.
The thirteen upstream selected profiles are not yet covered by this new guard.
An inventory of captures from Cycles216-224 finds exact successful producer
outputs and unchanged static closures for twelve of those thirteen. Errata policy
has no matching capture within that search window. Search earlier evidence before
requiring a new bounded host qualification; absence in this window does not prove
that no earlier execution evidence exists. Upstream inventory report:
`5A454E2F109890BE24ED7CDA57935EDD1F479AA9986CAF3D7A285A3C18AB7C84`;
script `89141C2164AF8B63D880C5781D826E4A34AC6078AEC58B4A4CC9FB277E405DCB`.

Next: `N36-RECEIPT-COVERAGE-001`, review those upstream profiles and non-Python
dependency bindings, then full exact-candidate canonical/Doctor/release/publication/
GitHub/review gates before merging PR78. Do not repeat the already-accounted
fourteen boots without evidence of a changed or missing execution dependency.
All 27 previously selected native checks remain current, not a full-suite pass.

All 28 parent current progress records are archived unchanged. Native source,
kernel216, entry/core/profile receipts, demo ISO, normative charter, checklist
10512 lines/8996 requirements/171 sections and phase/flag inventories are unchanged.
PooleGlyph remains at Phase65 with the same checkpoint and owner-dirty report;
Phase66 remains unqualified. No syntax/CoreIR/PGB2/PGVM2/ABI/IP migration occurs.
N0 custody, N5 authentication, full architectural task state, general retirement,
physical hardware and independent builders remain open. No signing, key use,
firmware/media operation, tag, release or production promotion occurred.
