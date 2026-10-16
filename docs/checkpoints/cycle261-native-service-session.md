# Cycle261: Native Service Session

2026-10-11. PROGRESS. Usable original-native integration ISO first, then the
complete robust microkernel. The production goal stays active. This cycle changes
real kernel startup/dispatch code and executes the separate user programs; it does
not redesign the splash or deliver an interactive ISO.

## Implementation And Evidence

PSESSION1 launches the exact cycle260 PooleInit/PooleCounter binaries through
owned PSTART1 construction and atomic IPC/scheduler admission. Both run in CPL3
with private roots, real PSABI1 calls and their own PSVC1 service-control policy.
The explicit development-session feature does not execute diagnostic injections;
other development selectors reject and ordinary unsigned boot remains denied.

Two independent session-kernel builds reproduce exactly. Two fresh positive guests
each reach512 dispatches,1023/1024 syscalls,512 waits,511 wakes and1024 CR3 writes.
Both tasks' measured runtime increases. These programs block on IPC; the session
records zero timer preemptions, not a new cached-timer spinner qualification.
The malformed-role control embeds the same user code: counter exits120, init's
dependent blocked receive is cancelled, init exits111, both are reaped and all26
pages return with no IPC objects/waits. The kernel remains resident without panic.

Session timers reuse a checked calibration only for their same owner/root/APIC/
HPET context. Calibration storage and lookup compile only into the session profile.
The default diagnostic profile retains fresh calibration and its original timer
layout. Each dispatch still checks the device context, arms, settles, quiesces and
drains. Five host cache tests exercise identity, measurement and lifetime controls.
General frequency drift, migration, suspend and physical hardware are unqualified.

Final combined public evidence: `runs/native-session-readiness.json`. Its nested
session and default-regression receipts preserve their exact source bindings and
media/kernel hashes. No old execution receipt is rewritten. The default replay
passes19 checks,744 overlapping Rust test executions and92 Python oracle tests,
including471 debug kernel tests and158 release user-entry tests. Both fresh
79-marker diagnostic guests retain17 survival cases and1111 hostile-marker
controls each; ordinary unsigned denial also passes. Full canonical qualification
is still pending. Image layout remains205/208 pages with a36-page guarded stack.

Default final capture363.906s, source/owner unchanged;
log E1414122C9A44BDF0F68E9A8A29B9C9CE6A253CE71D971E05A3DBF3A98B78946.
Default kernel SHA2567A9D5E31C548338F5B4DA31D04A16564DC530050D762747197284ED9441833A6.
Final sessionfifth replays the isolated feature build in77.141s, source/owner
unchanged; log0A837A9152736890395B2CD0E381AD82F847F434AB0E956113C92C45F5043E05.
The807 default source bindings and809 session bindings are verified independently.
Positive session marker controls reject152 mutations per guest; bad startup rejects58.
Session bounds stay120 seconds per guest and45 seconds for ordinary denial.
Default diagnostic bounds stay150 seconds per guest. No budget was relaxed for a pass.
Read-only recorded gate projection remains2/27 passing profiles. Three static
source closures remain current: symbols, policy and errata_policy. Entry is now
stale after the shared build-tool changes. This projection ran zero guests and
does not refresh historical canonical execution receipts or qualify a main merge.

Combined checklist/architecture/roadmap/native-oracle metadata passes188 tests
in50.341s, capture51.234s; log
FB1EA2B000D9A455A8D027004258BBE4F19DEED8275A466CAB09897079AD1A51.
Historical conservation and current oracle checks pass124 tests in8.655s,
capture10.047s; log
9735E6DB99ACFE08CB32049C0471393E09F183E57A14EF44A210B260537527A9.
Both captures preserve source and owner-report hashes. Counts overlap and are
not a full-suite or full-canonical claim. Architecture inventory now binds569
sources. The exact public session receipt is allowlisted after structured content
review; neighboring raw/private run names remain denied and secret scanning stays on.

## Retained Failures And Repairs

- oraclefirst failed2 of8 tests because the historical prefix fixture described an
  older layout. Applied the same explicit synthetic current-layout changes used by
  the existing oracle; historical fixture bytes remain untouched. Negative-control
  generation now validates the positive input first. Log
  92B666E69C5A81A188CE469A19C12FED0D33A066F7D0FC145997448BAE3EACC7.
- sessionfirst failed compilation under deny(warnings): feature-only nonreturning
  dispatch made fallback code unreachable. An explicit startup selector fixed the
  control flow without weakening warnings. Log
  6D72CA5C957CFE467088D94F12AE8309FF6CD39E5E591422181EBDC318BCE6CB.
- sessionsecond hit120 seconds after128 dispatches. Read-only QMP register samples,
  disassembly and83 observed root writes localized repeated calibration, not a
  deadlock. Session-owned calibration reuse fixed this. Qualification log
  751801B060CC6BD089EE603EDD27F4F795791FF46B514B310EA7106DF0DD5884.
  The25/30-second diagnostic replays are not qualifications; logs
  2B8E2585AA0FD4FE14367DEE51A1A51614DEA9F214DC48A847AFC95123984E58 and
  C1E95E732426562DC7842C4164D4EF86CF99246E8C34E2F9731E67CB45D9159C.
- sessionthird passed both positive guests but bad startup found a real lifecycle
  gap: counter exited while init remained blocked on its own still-valid receive
  endpoint. Fixed explicit mutual-dependency cancellation for this bootstrap pair;
  this is not general endpoint EOF or user-space supervision. Log
  DB08F1D72860AD04C27246574F38BC949467748272E0A9215E76CC2272C172C1.
  sessionfourth then passed76.672s, log
  0A837A9152736890395B2CD0E381AD82F847F434AB0E956113C92C45F5043E05.
- regressionfirst/second passed all18 pre-guest checks, then timed out at150 seconds
  near the final service tests. Captures228.031/226.907s; both log hashes
  E1DC70D77EB5F067F82408259EC7A3A97EFB5B53123C1C42EC956B4EF1536595.
  A separately labeled160-second diagnostic replay completed157.125s, proving
  forward progress, not a qualification pass under a changed limit. Calibration
  fields and lookup were then compiled out of the default profile. regressionthird
  stopped at formatting before any guest; log
  97FF4AABAD64C0DE557DBDAE1966BAAF28A7BC86CF0836B903D071A80B55FC6F.
  After the line-wrap repair, regressionfourth passed the original bounds.

All captured source and owner-report checks stayed unchanged during their runs.
Failed artifacts remain private under outputs; no failed evidence is promoted.
The first metadata run had3 stale-inventory assertions among188 tests: two new
kernel sources and the now-stale entry source closure. Updated exact inventories
and current projection expectations, not the historical receipts. Capture44.672s;
log44B1D43A9468C8977E65E8A4EBB6C1C36C34C4374FE6F0DD0458AE168F375391.

## Boundaries And Next Move

No console/input, shell, read-only file service, two usable applications or optical
integration ISO exists yet. Next: bounded console/input authority and backpressure,
separate untrusted user output from trusted diagnostic evidence, extend checked
admission beyond two tasks, then genuine input-driven shell/files/apps and optical
acceptance. The fixed bootstrap dependency policy must become user-space service
supervision; restart/launch policy is not implemented here. Efficient idle, general
resource policy, clock-fault recovery and signed PXABI1/PINIT1 activation stay open.

Three product-readiness failures still block canonical promotion:
- tests.test_native_kernel_load.NativeKernelLoadTests.test_contract_and_readiness_pass_semantic_validation
- tests.test_native_kernel_load.NativeKernelLoadTests.test_readiness_detects_stale_input_and_oracle_divergence
- tests.test_native_kernel_transfer.NativeKernelTransferTests.test_contract_and_generated_readiness_are_current

Cycle259 receipt SHA2CB2E882C774CE62FDEF78ACB660968E38A0CA4966A379AE9C30B08CE06FF349
is preserved as historical, not asserted current after kernel source changes.
Cycle260 program receipt SHA880B7F588AB683E3AC2D317D231BF5D821525CB63343D10EC953C39FFD6DDFD8
and its19 program-source bindings remain current and unchanged.
No phase/flag closes:40 phases301 subphases8996 requirements59 additions97 flags42
open20 gaps. Full microkernel, PooleGlyph/PDC and accessible PooleGlass remain.
PooleGlyph Phase65 checkpoint/manifest reread; Phase66 CoreIR audit remains next.
Master A8C94719FAF9428C1F133010BA2603C0270C4E1EFD7327AF8EAB9C8C362ABB3D,
archive F3CCEB701CF76274D9464A0958BF6106888FB34F3C0BFBD55DE4ACE03C427ABC,
owner report F75E4836FAA9DDD59BA62648FE9542415F2119B659A583FB3F5959F2F5CAE87B,
historical ledger65155E981FA217BD9D78218A4E0C0537A574D613ED9FB3E1EBD16511B6A1EA5D
were verified unchanged. Owner temporary trees are preserved. No main merge,
signing, release, firmware access or physical-media action is part of this cycle.
