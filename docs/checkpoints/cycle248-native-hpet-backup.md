# Cycle 248: Native HPET Backup Recovery

Date: 2026-10-08. Result: PROGRESS, not a phase exit or production readiness.
Move: N13-USER-ENTRY-LIVE-001, USI-1 / N8, N12 and N13.
The owner priority remains a usable native user-space integration ISO followed
by the complete robust N0-N39 microkernel. No new ISO exists this cycle.

## Implementation

PKUSER14 introduces exclusive HPET comparator ownership, a fixed BSP MSI route
on vector65 and a 50ms backup deadline for the normal10ms local timer. Original
registers are retained before device writes; failed programming or restoration
keeps the owner. Deadline programming, routing, capability and post-enable
timing are checked. The local timer mask and initial count are read back.
An authenticated watchdog trap terminates only its user task. Its time enters
the existing exactly-once retained accounting path. Both sources stop and drain
before HPET restoration and descriptor/root/page release.
[Mechanism, invariants, alternatives and primary references](../native-user-hpet-backup.md).

The launcher explicitly opts into QEMU HPET MSI; default profiles are unchanged.
Both fresh user guests and ordinary-denial control record this option. The guest
checks actual capability rather than trusting a host launch declaration.

## Final Verification

The final focused capture passes14 checks in308.313s:375 debug kernel tests,
122 repeated user-release tests,24 repeated VM-release tests,8 compile-fail tests
and10 boot-exit tests:539 Rust executions, not539 distinct tests. All38 Python
oracle tests, formatting, freestanding library/adapter compilation and both
incompatible-feature denials pass.

Two fresh60-marker guests and an ordinary unsigned-denial boot pass. Each user
guest rejects601 altered-evidence controls and completes16 containment rounds:
156 settled dispatches,30 terminal samples,156 duplicate-charge denials,
125 accepted preemptions,323 CR3 writes,564 released pages,259 scrubbed data pages,
83 scrubbed/released construction pages and three shutdown delivery/EOI pairs.
The masked-local-timer spinner terminates through actual HPET delivery; the
healthy peer subsequently exits84. All156 backup arms have exactly one stop
and restore; no device owner remains.

Each guest's136813730 HPET ticks equals125006970 preemption ticks plus10806705
terminal ticks plus1000055 failed-cleanup ticks. The backup termination contributes
5000028 ticks, not an invented zero. Per-task and scheduler totals agree.
This includes in-quantum kernel work, not just user instructions.

All757 native/build/oracle bindings, the full outer source snapshot and the
owner-modified PooleGlyph report remain unchanged during the final capture.
Fresh variable copies, read-only virtual media, no guest network/acceleration,
exact serial/debugcon equality and clean QMP quit are recorded. Guest120s,
ordinary45s, live qualifier360s and outer900s bounds remain unchanged.

- Receipt: `runs/native-user-entry-readiness.json`, SHA-256 `1182CB4054D0882F07AD51DD96097CC5C49E4AC999D9E1621D47E547FB91CE15`.
- Kernel:663464 bytes,181 pages, entry0xC000, SHA-256 `A26606833AC1B53FD9AB1824F16C13BDA7B5DB7904C144F82CD7FD99CEBCEAC1`.
- Linked kernel: `A78613BA0909C8E87546EA1FBD880EA9E0A1F625C116E86E32686EB98C0592D8`.
- Final capture log: `173B5AFE6A5B7587AEAFA0F30913DF43C771322923A78573905A34AFEF49E336`.
- Frozen Cycle247 receipt: `tests/fixtures/cycle247-user-entry-readiness.json`,
  SHA-256 `A406DF5C9EE84C48DCEB9B560A05A33A96AAF19D847FF9B86E30D8583E82BB8B`.

## Failure History

1. The first full native attempt failed linking in82.250s: text0x9013E exceeded
   the0x90000 boundary by318 bytes. One page was added: text/data0x91000,
   RELRO0xA1000, image end0xB5000. Entry0xC000, permissions, contiguity,
   192-page capacity and36-page guarded bootstrap stack remain unchanged.
   Log: `203316956591B4C047D1A77EE4BA29FEAB2EE12AB675DCF1FA9813145BAE00A3`.
2. The second attempt's14 checks and three guests passed in306.922s, but the
   outer capture rejected the qualifier's write to its tracked canonical output.
   The only changed path was `runs/native-user-entry-readiness.json`;757
   implementation bindings and owner data were unchanged. This is not recorded
   as a clean capture. Its log hash matches the final terse pass log above;
   distinct command, source snapshots, timing and receipts identify the runs.
3. The final attempt adds local timer register readback and writes its candidate
   receipt to ignored output. It passes with zero changed source paths; only
   afterward is the exact candidate copied to the canonical receipt. No source
   or owner-state invariant was weakened to accept a mutable capture.

Earlier bounded checks:375 kernel tests in13.91s/24.015s capture, log
`1D764BFC9FFD12E840C21BBAF66553F23C56A5407A91B3A95E474E3E1F5CC013`;
38 parser tests in0.128s/0.687s capture, log
`3C6F8891E67B3EAE851CB42CE605FBF4858DC05209E062A0036ACABAA6B1F010`.
Two setup commands failed before execution (missing helper import path and a
mistyped working directory); corrected without changing acceptance criteria.

The initial metadata regression ran134 tests in51.618s/52.469s capture with two
failures: stale67-source inventory (now70) and the prior cycle's qualification
label. The new three-source set and bounded HPET status expectation are updated;
the historical79-input execution binding remains unchanged, not promoted.
Log: `98B09CA66FDB772DBCB9207CE512084A72E68CCFCB2F56D7885E2A6D0395E0B4`.

## Remaining Path

USI-1, N12 and N13 remain partial; USI-2 through5 remain not started. Next:
explicit unknown-measurement emergency accounting and retained-resource recovery,
then capability IPC, init/confined services, shell/files/two apps and actual ISO
interaction. Missing time remains unknown, not zero; legacy diagnostic tasks
remain outside the broad accounting claim.

HPET backup shares the clock, APIC delivery and IF requirement. It is not NMI
recovery, protection against IF0 hangs, or generally independent watchdog
qualification. I/O-APIC/non-MSI/32-bit fallback, native simultaneous pending
sources, physical coherent clock/reset/drift, partial timer configuration,
general quarantine/admission, complete stack/exception/state/SMP/async coverage
remain open under the integration flag. No phase or flag closes.

The build plan conserves40 phases,301 subphases,8996 requirements,59 additions,
97 flags/42 open and20 program gaps. PooleGlyph remains observed Phase65 with
Phase66 Core IR boundary audit next; its owner report is untouched. The master
checklist remains byte-bound with zero unmapped requirements.

Read-only gate projection remains2/27 current native admissions and5/27 current
static closures;25 and22 stale respectively. Firmware is current; boot-trust
and ELF prerequisites remain stale. This is not new execution evidence.
Product-contract migration for181pages, full exact-candidate replay and canonical
gates remain required before merge. No signing, release, firmware, physical media
or production promotion occurs. Architecture binds486 sources.

Final metadata regression passes134/134 tests in51.304s/52.218s capture, zero
skips, with source and owner report unchanged. Log SHA-256:
`209FAA3282CDA7E17EAE4514978470FFE4F66D5A8571F645ADE2CA535A0ED5A4`.
