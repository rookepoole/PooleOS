# Cycle 244: User State Containment

Date: 2026-10-08. Outcome: verified development progress, not production-ready.
USI-1 / N12.5-7 and N13.3,6 / `N13-USER-ENTRY-LIVE-001`.
Entering commit: `c57058fc51b643aa6171c32fe0c9b16c725b6aab` on
`agent/userspace-integration-iso`. Qualified main remains at Cycle233.

## Implemented

[PKUSER10](../native-user-state-containment.md) separates kernel-owned entry
invariants from invalid user RIP/RSP/RFLAGS. Invalid syscall/timer return state
terminates only its task, never resumes and never executes the rejected request.
Private-RSP0 exception gates, pre-dispatch AC cleanup and validated DR6 cleanup
contain more user faults. Kernel-origin and ownership failures remain fatal.
No PooleGlyph ABI, production ABI or capability authority changes.

## Qualification

- 748 exact unchanged native/build/oracle bindings.
- 349 debug kernel +99 user-release +24 VM-release +7 compile-fail +10 boot-exit
  =489 Rust test executions. 33 Python oracle tests, format, freestanding checks
  and two incompatible-feature build denials pass.
- Two fresh headless QEMU/OVMF TCG guests, read-only virtual media, fresh vars,
  no guest networking or host acceleration, matching serial/debugcon streams.
- Each54-marker guest: 140 peer dispatches, 113 preemptions, 14 survival cases,
  56 post-stop survivor quanta, 291 CR3 writes, 429 released pages, 198 scrubbed
  data pages and one retained ACPI page. Existing controls remain passing.
- Six invalid-return terminations and four additional fault cases per guest.
  New live exception vectors are 0,1,3; native #SS is explicitly unqualified.
- 493 altered-evidence controls reject per guest. A third ordinary unsigned
  boot denies kernel execution. No optical ISO or interactive session yet.
- Kernel626488 bytes,172 pages, entry0xB000; reservations unchanged. SHA256
  `572B391DA29A204F22A21B1777A185449A114100735D0571FFCE0AB96D1DBC87`.
- Receipt `runs/native-user-entry-readiness.json`, SHA256
  `3D6D3860572C99A08B6E0322D61C92BADBC9D0D71ED513D40DAB06AEE6891271`.
- Native capture260.656seconds, source/owner unchanged; log SHA256
  `93DE3CD234064943B0F0D6701E612D1229397CA0F2DE8BE764F52E148F763405`.

## Failures And Reconstruction

The new host regression first reproduced `Err(Frame)` instead of task-only
termination for a bad RSP. The red test failed behaviorally, not at compilation;
capture7.687seconds, exit101, log
`96EBBE5D066DF82CD0B2FF3205B091F314CA56FED64D42A789BD61749EEBEDAC`.

First full capture174.359seconds passed host checks and13 live rounds, then
failed stage113 in the final stack-access case; log
`CD4E67D1790051DEA8CC82D4A3E0D7688567FC29EFB21CB291296663A30E7ED7`.
The diagnostic capture114.375seconds reproduced #GP(0), vector13, at0x400000BF,
not architectural #SS(0). Log
`6B9D407A402E93670F7D90FA8A56A9A17ADEE0AFC389DC32ED27D1A84A12B4BA`;
debugcon SHA256 `2E4A5DF6283C07AADD18AC3154BB3DFC9780A6E9128E5B06D6F27C288673327E`.
Both captures preserve unchanged source/owner bytes and their failed status.
Upstream reports support the emulator diagnosis; the design note cites them.
Acceptance was narrowed to explicit TCG containment, with a regression preventing
native #SS promotion. The complete focused suite and two fresh guests then reran.

An earlier21.125second development wrapper included `cargo fmt` and was correctly
rejected as non-immutable input. Its child returned0 but produced no inherited
output; it is not qualification evidence. Later captured suites supply the proof.
Guest bounds were set to90seconds before the first expanded14-round run;
ordinary denial remains45seconds. These are external bounds, not native watchdogs.

## Progress And Remaining Gaps

Plan2.147.0-native-user-state-containment retains40 phases,301 subphases,
8996 requirements,59 additions,97 flags/42 open and20 gaps. N12/N13 remain partial;
no phase or flag closes.465 architecture bindings include this checkpoint,
the design note and immutable Cycle243 receipt. Python inventory1280 is discovery,
not a claim of running the entire suite. Metadata verification is recorded below.

Next: transactional spawn rollback, pending/late timer recovery and complete
accounting; then capability IPC, confined services, shell/apps and optical ISO.
Independent missing-IRQ recovery, unqualified exception/selector semantics,
full XSAVE/SMP/async/SMAP, physical hardware and production gates remain open.
Image172pages/entry0xB000 still needs product-contract migration and prerequisite
replay. Old source-bound receipts are never rebound. Full exact-candidate gates
have not run, so no merge, release, signing or production promotion is claimed.
The robust N0-N39 microkernel and PooleGlyph/PDC/PooleGlass objective remains active.

## Conservation

Frozen Cycle243 receipt: `tests/fixtures/cycle243-user-entry-readiness.json`,
SHA256 `AD4EAA1FD5D80FD564F603D69A083EF2F904452767C1F416F6E6D477C48C8F1E`.
Execution ledger: `65155E981FA217BD9D78218A4E0C0537A574D613ED9FB3E1EBD16511B6A1EA5D`.
PooleGlyph Phase65/66 checkpoint and manifest re-inspected; no newer checkpoint.
Owner-modified report retained: `F75E4836FAA9DDD59BA62648FE9542415F2119B659A583FB3F5959F2F5CAE87B`.
Checkpoint ZIP: `F3CCEB701CF76274D9464A0958BF6106888FB34F3C0BFBD55DE4ACE03C427ABC`.
Master checklist: `A8C94719FAF9428C1F133010BA2603C0270C4E1EFD7327AF8EAB9C8C362ABB3D`.
No owner action is required for the next engineering step.

Initial metadata replay passed123/125; both failures identified the same stale
schema constant (Cycle243 instead of244), not a kernel regression. The constant
was advanced without weakening validation, records regenerated and the full
metadata suite rerun. Failed replay51.812seconds/capture52.64seconds, log
`4AE4F4B075610C9962C99532DE9A4BFE7BFFF9727AF4CE593F2FBDD07EF47A78`.

The final125-test metadata replay passes in50.505seconds/capture51.344seconds,
source/owner unchanged; log
`0519929E37E9B41292BF97773DB5ED010F9226326F128634C08446A8BA84A12F`.
Records are regenerated after recording results and checked again. The read-only
projection remains2/27 current native admissions and5/27 current Python closures,
with25/22 stale; firmware is current and boot-trust/ELF prerequisites remain stale.
That projection does not manufacture new execution evidence or permit a merge.
