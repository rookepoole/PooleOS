# Cycle 175: Memory Entry Provenance And Dependency Replay

Status date: 2026-09-12
Selected move: `N9-PMM-ACPI-CONSUMER-001`, N9.2-N9.4; dependent N8 and N12 profiles.
Status: fourteen final profiles and 27 selected gates pass; full canonical audit pending.

## Implementation

The previous completed goal cycle, 174, made verified progress at `d3eec83`.
The intervening cloud-status check was read-only. This cycle resumes development.

Fourteen memory, interrupt, SMP, scheduler, atomic and lock validators now
validate embedded PKENTRY1 evidence against the current validated entry receipt.
They reuse the unchanged CPU provenance helper and bind that helper, the new
tests and the current entry receipt. Atomics retains its existing
`kernel_summary.entry_readiness` layout; the others use `build.kernel_entry`.
Exact JSON-typed identity rejects stale source/build evidence and numeric type
substitutions even when the canonical kernel hash matches.

Four new test methods cover 224 embedded substitutions, 56 invalid current
dependencies, positive provenance inputs and source bindings. These synthetic
inputs test validators; they are never written over execution receipts.
The work advances `ADD-N36-RECEIPT-COVERAGE-001` under its existing open flag.
No native Rust, kernel instructions, CPU helper, CPU tests or boot policy changed.

## Executed Evidence

Fourteen final qualifiers pass 28 fresh virtual boots, 660 control groups and
2,126 rejected cases. Two earlier successful SMP boots are superseded after the
shape-handling repair below, making 30 successful boots executed this cycle.
Each qualifier rebuilds PKENTRY1 and validates 243 kernel host tests. All 1,534
observed source files and the owner's PooleGlyph report remained unchanged during
each run. Reports are exact copies of generated output.

| Profile | Final Boots | Groups | Cases | Receipt SHA-256 |
| --- | --- | --- | --- | --- |
| physical_memory | 2 | 191 | 191 | `1E0BFE165847F44D378BCE34E8CBB80381B5D55461BE184926A18098DC2A428A` |
| virtual_memory | 2 | 48 | 48 | `70BFA62FA783F8D86192C9A4B2D09B25E6C95651091B696BF0DEF55781B1FD22` |
| interrupt_time | 2 | 58 | 58 | `9B8701771419F236BBCB2EFDD113252FC7AB475F9627BCC3EDE193ED0A06C23F` |
| smp_first_ap | 2 | 72 | 72 | `8091CE3463ED7B176694453A2BAC3CDE12A4A99B62A0C0556B631A484BAE9A55` |
| smp_percpu_runtime | 2 | 19 | 159 | `CB5F40B6A9126277E63683C6445143ED4743AA5A1B4C27D41B35A27732D82012` |
| smp_ipi | 2 | 30 | 249 | `33AC859F22E4D973B44B69C33C1F135FDC281DDDC7AB14833157BCC0616AC93F` |
| scheduler | 2 | 28 | 115 | `7B88A628040CF2D56EF20C82597F28EEEF4BBA8EF7E54530DB18504E87C59784` |
| scheduler_preempt | 2 | 25 | 178 | `DD7D25E4519AD547C83F455E8F07D68D460AFDBF7008497399773FBF621A7F85` |
| scheduler_deferred | 2 | 30 | 208 | `5DD7943E2BA0DF888ABD5BB0B07CA7E9A993667AE9F0BCFEF934153E2AD1BA8C` |
| scheduler_smp | 2 | 32 | 209 | `C1CDB80614A014295892BE0830EE53AF69302517F28B0F06BDC148A4BBD59FBE` |
| scheduler_ap_workers | 2 | 34 | 226 | `A1E4BBF2533C5CBD6A7606AF1668033203947244243B1E15511453E2FE2E5A71` |
| scheduler_smp_preempt | 2 | 34 | 232 | `BA92D612301355611C744B2E80B04D7F18DE864A680BC8B7DBAADD4B29FE043F` |
| atomics | 2 | 29 | 78 | `AA89BA7799FFCA130B87B36CA30347128C717F6F60184CCAFC09EE02C72CAD1C` |
| locks | 2 | 30 | 103 | `F9E8B7754343DD02CF44D0FD7394294C3A2B43F4B4D308D5AF2606C083283496` |

The final 163-test profile/map/gate/provenance suite passes 161 tests with two
optional local-transcript skips in 9.846 seconds. Log SHA-256:
`B5D0E9EF3233B99A40AD13F871B576C5C2D7C77BB3B50723BAF3BC79666CA5F5`.
The initial eight CPU/memory provenance methods also pass. The selected native
projection passes 27/27, including all three formerly stale checks. The unchanged
Cycle 172 reclamation-core receipt validates and all seventeen stage-log hashes
match. This is not execution of the full canonical qualification suite.

## Failure History

The initial provenance tests failed 294 diagnostic expectations: 224 embedded
cases, 56 current-dependency cases and fourteen binding assertions. Some malformed
inputs already had schema errors; this count is not 294 silently accepted records.
The red log is `2C45A58F8338B38362EA2A385CE562409C530235D2EFF79FDC14D0CAA72C1564`;
the eight-method green log is
`88D170488AA6763AEBCD0FA793B4E8D36748415BF0520A06493FAC8FB1128D8B`.

The first combined regression run found four exceptions for non-object SMP
receipts because the new lookup preceded the existing schema-return guard.
Failure log: `D9471CEF7EFCA4438D8C0208AAD3A09E8616B025A1984805BF12CAA7BD009075`.
Restoring a non-dictionary early return preserves schema rejection. Five focused
methods pass, log
`9300CE6CFC047B18FD4E52AF928F4B3CA45380B80B3ECEC6BB410C5A9D55A671`.
Declared input comparisons identified SMP IPI for replay. Its replacement
qualifier passes two boots in 72.781 seconds, log
`8DB9072B8081D12AEFB5CCFAA5BA304DE04720D77B70ED7FA52140A6F4D5BD78`.
All fourteen profiles then validate and the combined regression suite passes.
Initial reports, the initial 27-check projection and the failed tests are retained.
The historical Cycle 172 failed full audit is not overwritten or waived.

## Boundaries And Next Move

These are single-host virtual profiles. Entry consistency does not authenticate
receipts or prove complete transitive input coverage, independent reproduction,
general malformed-input handling, physical hardware, arbitrary topology or SMP.
N9 still lacks complete user VM, PCID/COW, general pressure/OOM and concurrent
allocation. N12.3 still needs live guarded task stacks, architectural context
activation, general CPU retirement and automatic scrub-receipt growth integration.
The host-only PKSTACK1 work is not promoted to a live task-stack claim.

All 8,996 requirements, 57 additions, 40 phases, 301 subphases, 94 flags (35 open),
20 gaps, phase/flag states and exit contracts remain unchanged. The inventory is
958 discovered Python tests and 239 architecture bindings, not a full-suite pass.
PooleGlyph Phase 65 ZIP/manifest and owner-modified report are unchanged; Phase 66
Core IR remains next in that repository. The frozen demo ISO is unchanged.

Next: exact full canonical qualification with both bundle and replay inputs and
runtime checks, followed by publication/review gates for PR #77. Only after that
qualified baseline, resume `N12-CONCURRENCY-RECLAMATION-001` task-stack/context
and CPU-retirement implementation. N0 custody remains separately blocked; no owner
action is needed for the next qualification. PR #77 remains draft and main stays
qualified Cycle 171. No phase closure, signing, physical-media/firmware action,
release, main merge or production promotion is claimed. The full goal is active.
