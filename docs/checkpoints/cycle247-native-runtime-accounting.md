# Cycle 247: Native Runtime Accounting

Date: 2026-10-08. Result: PROGRESS, not production readiness or phase exit.
Move: N13-USER-ENTRY-LIVE-001, USI-1 / N8, N12 and N13. The owner priority is a
usable native user-space integration ISO, followed by the complete robust N0-N39
microkernel. This cycle adds kernel mechanisms, not a splash. No new ISO exists.

## Implementation

PKUSER13 measures each authenticated returned peer quantum, including terminal
partial quanta and the quantum whose subsequent cleanup fails. The exclusive
task slot retains its charge before fallible quiescence or root suspension.
Scheduler settlement checks current CPU/task identity, generation, dispatch
ordinal and previous total; all failure checks precede mutation. Checked totals
cannot wrap. Zero-resolution terminal samples are valid but still replay-protected.
Pending or unknown charges prevent resume, cancellation, detach and abandonment.
Copying a public observation cannot submit a charge. Cleanup retry cannot charge
again. See [invariants and limits](../native-user-runtime-accounting.md).

Missing/malformed measurements stay explicitly unknown and retain resources;
ordinary abandonment is not an emergency recovery policy. The charge window is
HPET arm-to-event, including in-quantum kernel work, excluding later cleanup and
scheduling. It is not pure user-instruction time. Legacy nonresumable diagnostic
tasks remain outside the accounting claim.

## Verification

The final full focused capture passes in275.843 seconds with14 checks:368 debug
kernel,115 repeated user-release,24 repeated VM-release,8 compile-fail and10 boot-
exit Rust executions (525 total, not525 distinct tests);36 Python oracle tests;
formatting; freestanding compilation; and two incompatible-feature denials.
Two fresh58-marker native guests pass, plus one ordinary unsigned-denial boot.
Each rejects563 modified-evidence controls. Guest120s, ordinary45s, live-qualifier
360s and outer900s bounds are unchanged. No workload case was removed.

Each fresh guest settles148 dispatches and rejects148 duplicate charges. Runtime
total125809412 HPET ticks equals119003541 accepted-preemption ticks plus5805842
ticks from28 terminal samples plus1000029 failed-cleanup ticks. Per-task retained
totals match scheduler totals before teardown. All15 survival cases,119 accepted
preemptions,307 CR3 writes,538 released pages,247 scrubbed data pages,83 scrubbed/
released construction pages, and three timer-drain delivery/EOI pairs remain.
Failed cleanup still does not fabricate an application result or accepted
preemption; its consumed time is now charged. The healthy peer continues to exit84.

All754 native/build/oracle source bindings and the owner-modified PooleGlyph
report remain unchanged during qualification. Fresh variable copies, read-only
virtual media, no guest network, no host acceleration and exact serial/debugcon
matching are recorded. This is emulator execution, not physical or ISO acceptance.

- Receipt: `runs/native-user-entry-readiness.json`, SHA-256 `A406DF5C9EE84C48DCEB9B560A05A33A96AAF19D847FF9B86E30D8583E82BB8B`.
- Capture log: `5A7AEAED20BE8E6574F86F9DBF15C0D7CF6FD88C82FD5831F1D8C5FCF60DA52D`.
- Kernel:659272 bytes,180 pages, entry0xC000, SHA-256 `5C999DC4AA3A23E470548C38082E4F3489324AD760A280C130CFDC8FF92C261D`.
- Linked kernel: `EAD89FE30FD1A599455DE7EE78D8E16F427EF6DB8518A0791900666AD1701FE7`.
- Frozen Cycle246 receipt: `tests/fixtures/cycle246-user-entry-readiness.json`, SHA-256 `A77030BD8C2557C85D5670D7EDE5C17876C6B05F5EF5E303BC8C82126FC3A6F8`.

## Failed Attempts And Repairs

1. Initial full native qualification failed linking in69.234s. Read-only content
   reached0xB238 beyond0xB000 and text0x8E2FE beyond0x8E000. Read-only/text boundary
   moved to0xC000, text/data to0x90000, RELRO end0xA0000 and image end0xB4000.
   Segment permissions, contiguity,192-page cap and36-page guarded stack remain.
   Log: `DB012F5F6368E962F1A6E8B48EC1D53AE9E5FF5446924D4FFC47D6501B2AA65D`.
2. The next attempt failed in85.219s with native panic0x1006 before user entry:
   runtime continuity rejected the stale0xB000 entry constant. It now matches
   linker0xC000; a host regression checks the constant against linker text start.
   No continuity assertion was weakened. Log:
   `BA82F5AB427610974E67D1C072AFB51BAE4E259B872C6E904B293EF2D162B750`.
3. Final qualification rebuilt from scratch and passed. The failed attempts
   remain failures, not reinterpreted as success. Source and owner data remained
   unchanged in every bounded capture.

Earlier focused runs passed367 kernel tests before the added linker regression
(13.81s test time,24.468s capture), and36 oracle tests (0.101s,0.672s capture).
Logs respectively `3C7910CA2C76B7EAB0C83D924758599BDF487190104ECA04B05C8431CB53CFD0`
and `524AF3E85FC4ABFF185927F0132C9C5620CD2A75FA661171A0ED07CEA65B80A5`.

## Progress And Remaining Gaps

USI-1, N12 and N13 stay partial; USI-2 through USI-5 are not started. No phase or
flag closes:40 phases,301 subphases,8996 mapped requirements,59 additions,97 flags
(42 open) and20 program gaps. The open integration flag now explicitly records
unknown-runtime emergency recovery and coherent physical clock sampling/reset/
drift. Broad complete-runtime accounting remains false, not promoted by PKUSER13.

Next: native independent missing-IRQ recovery and explicit unknown-measurement
accounting/quarantine recovery, then capability IPC, confined services, shell/apps
and actual optical ISO. General executable admission, persistent quarantine,
partial timer configuration, silicon timer races, complete N3.7 stack bounds,
native #SS/general exceptions, XSAVE/SMAP/SMP/async and hardware remain open.
An external120s guest bound is not a native watchdog. Production-contract migration
for180pages/entry0xC000, stale prerequisites and full exact-candidate replay remain
required before merge; the old execution ledger is not rebound to the new image.
No signing, release publication, firmware, physical-media operation or production promotion.

PooleGlyph remains observed Phase65 with Phase66 next. Its checkpoint and
owner-modified report are untouched; metadata does not gain kernel authority.
The locked master checklist and zero-unmapped coverage are conserved.

Metadata closeout passes131/131 tests in51.090s (51.938s capture), zero skips;
source and owner report unchanged. Log SHA-256:
`7DD0B1FA58A6F4F6BCAA32188264AF914DF0B4E23F2CC5AE8DC45E5EA767E239`.
Discovery finds1286 Python tests with zero import errors, not a full1286 execution
claim. Read-only gate projection retains2/27 current native admissions and5/27
current static source closures, with25 and22 respectively stale. Firmware is
current; boot-trust and ELF prerequisites remain stale. Projection is not new
guest qualification. Architecture now binds480 sources. Full canonical suite,
product-contract migration and exact-candidate qualification remain pending.
