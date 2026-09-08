# Cycle 164: Current-Kernel CPU-State Replay

Status date: 2026-09-08
Scope: N7.1/N7.3-N7.6, selected `N7-TRAP-001` and dependent CPU-state replay.
Status: bounded pre-production qualification; no N7 exit or main-merge claim.

## Verified Results

| Profile | Successful Boots | Marker Controls | Bounded Result |
|---|---:|---:|---|
| PKTRAP1 | 6 | 51 | Three returning faults, terminal double fault, synthetic semantic malformed-frame rejection |
| PKCPU1 | 2 | 41 | CPUID/control-state policy, five MSR reads, no state writes |
| PKXSTATE1 | 2 | 43 | x87/SSE context separation, two saves/four restores, 8,192 cleared image bytes |
| PKXEXC1 | 2 | 43 | WHPX exception delivery, two recoveries and terminal test-only `#NM`, linked-code audit |
| PKMSR1 | 2 | 47 | Eleven support-gated MSR reads, no bank/PMU reads or activation, linked-code audit |
| Total | 14 | 225 | One exact unchanged kernel, bounded virtualized profiles only |

The six trap boots were completed before the partial cloud checkpoint and
are included once, not rerun or double-counted. One separate TCG diagnostic
observes the expected floating-point exception non-delivery and fail-closed
panic. It is excluded from the fourteen successful boots. All 41 focused
N7 tests pass: 33 for the five live profiles plus eight unchanged pure
errata-policy tests. Each live qualifier also passes 228 kernel host tests.
The 21 roadmap/architecture tests also pass, for 62 combined focused tests.
Discovery finds 921 Python tests; this is not a full-suite execution claim.

Canonical kernel SHA-256 remains
`D0AA3295F66AF02D48476BCEDC44D962A873E98FBA21F48A6753AA7BB9B24EA4`:
525,976 canonical bytes, 598,016 image bytes, 146 pages and 1,319 relocations.

## Repairs and Evidence

The earlier partial checkpoint corrected only the trap release gate's stale
kernel/relocation pin after actual qualification. Its original 6/7 focused
test result and repaired 7/7 result remain recorded. The four subsequent
qualifiers all pass without changing their executable contracts or native Rust.

The exception guide incorrectly called its two WHPX runs TCG in one bullet.
That description now matches the actual profile, and the fresh receipt binds
the corrected document. Stale current summary rows are updated from measured
kernel and test counts. A roadmap regression binds all five receipt hashes,
common kernel identity, actual boot/control totals and the separately counted
diagnostic. These changes do not close the existing broader N36 evidence audit.

Exact public receipt SHA-256 values:

- PKTRAP1: `B68232FF7FC5C121D8D16423D61BD54E4D1E0E03388C1EBF9DBA21246CD86234`
- PKCPU1: `C6332B796B5B812B5751E3A33E4910CCE122C39AEF80DD92AAB63C5051891F3A`
- PKXSTATE1: `BBA6B1312C832DA9C0BFE1669A4F65E83844F3666BDA4F79A205D8E8EEF0BA81`
- PKXEXC1: `F679F40FDD7E3E06D18784BAA1947EE5B4B22176A97B3177D048BDD268381E18`
- PKMSR1: `9573D12F8C939A22FD29BDF06D4CFBC3134EB9141785B8A72000E73BC16C3173`

## Progress and Remaining Work

The selected native projection passes 13/27 checks. Fourteen memory-through-lock
receipts remain stale. This is not a full canonical or Doctor run; the failed
Cycle 162 audit remains historical at 81/105 and Doctor683/706. Main remains
the qualified Cycle 161 baseline. Draft PR #75 carries source backup, not a
waiver of qualification, publication or review gates.

Next is `N9-PMM-ACPI-CONSUMER-001`, followed by transfer-dependent VM, interrupts,
SMP, scheduler, atomics and locks. Then run exact-final canonical qualification
with bundle, replay and optional runtime inputs before considering a merge.
Do not repeat completed N5/N7 qualifiers unless their actual inputs change.

All 40 phases, 301 subphases, 57 added requirements, 94 flags (35 open), twenty
gaps and 8,996 locked implementation requirements remain conserved. No phase
or flag closes. PooleGlyph Phase 65 and its owner's modified report, the kernel
bytes and the frozen demo ISO are unchanged. N0 custody, target errata, user
state, general CPU retirement, native services, desktop and signed production
ISO work remain open. No new owner action is needed for the next emulator replay.
