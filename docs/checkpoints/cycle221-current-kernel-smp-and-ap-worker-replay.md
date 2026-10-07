# Cycle 221: Current-Kernel SMP and AP-Worker Replay

Status date: 2026-10-04. Pre-production; single-host virtual-machine evidence.
Parent: `fb69c08c2dd9b429f0bc73bbc43db4e939fac1a5`.
Moves: `N12-SCHED-SMP-001`, then `N12-SCHED-AP-WORKERS-001`.
Scope: N12.4-N12.7/N36, retaining N12.1-N12.3 dependencies.
Requirements: `ADD-N12-SCHED-SMP-001`, `ADD-N12-SCHED-AP-WORKERS-001`,
`ADD-N36-RECEIPT-COVERAGE-001`. Previous turn: progress, not a wait or blocker.

## Execution and Repair

Two profiles each pass two fresh four-vCPU boots on unchanged kernel216:

| Profile | Receipt SHA-256 | Groups / Cases | Runner Seconds |
| --- | --- | ---: | ---: |
| SMP scheduler | `EF7E7BA350D5B0853F4528C61CD2DA9436FA800AA194B1C2AA933D5188CF5D4E` | 32 / 303 | 107.281 |
| AP workers | `BF96F20CEF9D51E75E836B9780A902EF90D8C39D64CC7C881E0694E3884E1A16` | 34 / 325 | 87.078 |

Totals: **four boots, 66 control groups, 628 cases**, comprising 510 rejection
cases and 118 native boundary scenarios. Each qualifier repeats the same 246
kernel host tests; do not add these as independent inventories. Both embedded
entry receipts match the validated current entry including JSON types.
Source and owner data remained unchanged during execution.

SMP evidence covers one cross-CPU wake, two migrations, three transfer ACKs,
six AP dispatches, an offline timeout rollback and stale rejection. AP-worker
evidence covers twelve typed calls, queued and remote cancellation, timeout
rollback, thirteen reclaimed items and three worker retirements. Each profile
verifies cleanup of all 102 retained pages and 417792 cleared bytes.

Both aggregate gates initially reject their otherwise passing fresh candidate
because they expect the previous image hash and 1323 relocations. Independent
component validation and linked-image audit confirm current kernel SHA-256
`FD6C2A0C709957B9EDFFC0647D534E060ED68215C075F07D70AB2AEBCA6C81D1`
and **1326 integer relocations**. Only these four aggregate expectations change.
The exact same candidates then pass complete admission, with no guest reruns,
receipt rewriting or validator bypass. Initial failures remain recorded.

Execution log hashes:
- SMP: `B4AFCEDC4E0B5203EA8C7434E85C6ABD1BFF4D8CFEFFE76250C1A9A84BB46958`.
- Workers: `B06620B801239E6381B91722D9B146A38F8E0EDC3B2CA346918A635BF2F030DA`.

## Regression and Preservation

Focused regression passes **39/39**, zero skips, 81.264s (runner82.172s).
Log: `05D2FC34B99F390064E6EBD07EFA3A7621F9E9FD334B01B8516B819413E9F8B6`.
It rejects 669 corrupted records and 30 independent aggregate cases, including
twelve current-image pin cases. Old hashes/counts and wrong-typed values such
as float1326.0 reject. Tests detect 27 disabled native safeguards and 24 disabled
transaction repairs; source/linked auditors are also challenged.
Counts overlap and this is not full canonical qualification.

Initial metadata regression passes 63/68, with five stale current-progress or
embedded-entry expectations failing (36.058s). The failure log is preserved:
`9BE00A685CE89F4FE7E0392685C7CF8D118A67655AF0F9046660A35027ACE9AB`.
These assertions are corrected against validated current receipts/projection;
historical hashes and failure records are not rewritten.
A second metadata run passes 67/68; a later assertion still expects 22 passing
checks instead of 24. That run (36.708s) is retained at log SHA-256
`6AFA635A478E15677B455DEF1AED12EB2313BA3A821099AE4A4EDBB31B4D7A36`.
Corrected metadata passes **68/68**, zero skips, 36.638s (runner37.422s), log
`E7A4E0912CB45535AC6B98BA6672896F7B9277AEDC25008337FC09D710AA67BF`.
Initial conservation passes all 374 bindings and 25 unchanged parent archives.

All 25 parent progress records are archived unchanged. Phase and flag statuses
are preserved: 94 flags/39 open, 40 phases, 301 subphases, 57 ADD requirements.
No new ADD requirement is necessary. Locked checklist remains 10512 lines,
8996 implementation requirements and 171 sections. Inventory is 1139 Python
tests, not a full-suite pass; the architecture ledger binds 374 sources.
Final metadata/conservation/combined/publication/cloud results are recorded at
closeout. Prior failures remain historical evidence, not passing current runs.

PooleGlyph Phase65 remains newest. Its manifest/ZIP and owner-modified report
are preserved; no source/diagnostics/AST/semantics/Core IR/PGASM/package/VM/ABI/
policy/standard-library/tooling/conformance/performance/release/IP migration.
Phase66 remains unqualified. Native sources, entry/core, boot/CPU218, memory219,
scheduler220 receipts and the demo ISO remain unchanged.

## Next Move and Nonclaims

Selected readiness advances **22/27 to 24/27**. Next:
**N12-SCHED-SMP-PREEMPT-001**, including seventeen still-unproven control groups
and recorded admission, then atomics and locks. N36 shared-helper transitive
binding review remains open. Main merge requires full exact-candidate canonical,
Doctor, release, publication and configured GitHub/review gates. Branch cloud
backup is separate; no new owner approval is needed for the next development.

No general SMP/preemption, full architectural state, ring-3/address-space
switching, general task retirement, hardware qualification, independent builder,
new ISO, phase exit, cryptographic authenticity or production readiness claim.
N0 custody and N5 authenticated boot remain open. No keys, signing, release,
firmware or physical-media action. Raw logs, tools and ISO remain local.
