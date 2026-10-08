# Cycle 243: Native Preemptive User Peers

Date: 2026-10-08. Outcome: verified development progress, not production-ready.
USI-1 / N12.5-7 and N13.1-4,6 / `N13-USER-ENTRY-LIVE-001`.
Entering source: `17f760dd7a3a509cdf1c56b7b0671c0f2116ddb7` on
`agent/userspace-integration-iso`. Main remains qualified through Cycle233.

## Implemented

[PKUSER9](../native-user-peer-scheduling.md) connects actual private-root CPL3
tasks to the existing PKSCHED1 scheduler. Timer-driven suspend/resume preserves
registers, checked IRET state and legacy FP; entry/timer authority is quiesced
before restoring the scheduler root. Suspended tasks retain exclusive PMM holds.
Resume audits CPU identity and mappings, including valid hardware A/D updates.
Cancellation and syscall-budget exhaustion terminate only the selected task.
The syscall stack can move within its admitted page. No arbitrary programs yet.

Two tasks coexist in each of four rounds: exit, user fault, spinner cancellation,
and call-limit termination. Each survivor must continue and exit84. Final reap
scrubs/releases memory and rejects restart, repeated reap and premature free.
Five new lifecycle failure-injection tests, two context tests and two page-table
tests supplement the existing cases. Mock failures are not live hardware evidence.

## Qualification

- 748 unchanged exact native/build/oracle input bindings.
- 345 debug kernel +95 user-release +24 VM-release +7 compile-fail +10 boot-exit
  =481 Rust test executions;29 Python oracle tests; format and freestanding pass.
- Two incompatible development-feature builds reject as required.
- Two fresh headless QEMU/OVMF TCG guests with read-only virtual media, fresh
  variables, no guest network or host acceleration, matching serial/debugcon.
- Each44-marker guest:40 peer dispatches,33 preemptions, four survival cases,
  16 post-stop survivor quanta,91 CR3 writes,169 pages released,78 data pages
  scrubbed and one retained ACPI page. Existing privilege/copy/timer controls pass.
- 249 evidence mutations reject per guest. A third ordinary unsigned boot denies
  kernel execution. No ISO, signing, physical media or hardware probe involved.
- Kernel626488 bytes,172 pages, entry0xB000, SHA256
  `8D34D5807B660A88D4D819A6723109FC463D3D582419FA40E9A3C98CBB10C41E`.
- Receipt `runs/native-user-entry-readiness.json`, SHA256
  `AD4EAA1FD5D80FD564F603D69A083EF2F904452767C1F416F6E6D477C48C8F1E`.
- Final native capture138.687seconds, source and owner data unchanged, log SHA256
  `F42498A75742F006D5EF5433C4119C86985748491A36B5B2BB94373D5922B8D1`.

## Preserved Failures

The positive host A/D resume test initially failed at a second exact comparison
in the shared root validator. Both typed comparisons were repaired, preserving
exact-zero guards and rejection of dirty parent entries and permission changes.
The final debug/optimized suites reran that positive case and all negatives.

First complete capture70.812seconds passed host checks but failed linking before
guest entry: text reached0x8585E beyond0x84000. Source/owner bytes stayed unchanged;
log SHA256 `CF2A8F616763992CDB80A1F2034F92D2B7F77AD8F7F784641826DA59CC0C7778`.
Text reservation extends four pages to0x88000; RELRO/image boundaries shift to
0x98000/0xAC000 without reducing their capacity. Entry0xB000 and192-page cap stay.
The complete focused suite and fresh guests reran. An initial wrapper invocation
used a hyphenated capture tag and rejected before running tests; the corrected
alphanumeric tag was used for both preserved captures. No guest failure discarded.

## Progress And Next Move

Plan2.146.0-native-user-peer-scheduling keeps all40 phases,301 subphases,
8996 requirements,59 additions,97 flags/42 open and20 gaps. N12/N13 remain partial;
no phase or flag closes.462 architecture bindings include the three new modules,
this checkpoint, the design note and frozen Cycle242 receipt. Python inventory
1275 is discovery, not a claim that all tests ran.

Next: close USI-1 admission/containment gaps (transactional spawn, invalid user
return frames, armed-timer teardown races and accounting), then capability IPC,
confined services, shell/apps and actual optical ISO. Current fixed payloads
prove healthy-timer peer progress, not arbitrary-program or device-failure
containment. Independent missing-IRQ watchdog, full XSAVE/SMP/async entry,
SMAP/concurrent copying, physical hardware and all production gates stay open.
The source-bound product contracts need explicit0xB000/172-page migration and
fresh replay. Full exact-candidate qualification has not run; no merge or release.
Full robust N0-N39 development continues after the intermediate usable ISO.

## Conservation

Cycle242 frozen receipt `tests/fixtures/cycle242-user-entry-readiness.json`:
`DC81C8D1361A0E1460E8154B688C28F3BB06DB7B259FB7EF63F99A703A26C2C3`.
Execution ledger remains unchanged, never rebound to later code. PooleGlyph stays
at Phase65/66; its owner-modified report is preserved, SHA256
`F75E4836FAA9DDD59BA62648FE9542415F2119B659A583FB3F5959F2F5CAE87B`.
Checkpoint ZIP `F3CCEB701CF76274D9464A0958BF6106888FB34F3C0BFBD55DE4ACE03C427ABC`;
master checklist `A8C94719FAF9428C1F133010BA2603C0270C4E1EFD7327AF8EAB9C8C362ABB3D`.
The120-test metadata suite passes in50.675seconds (capture51.5), source/owner
unchanged, log `CFA4D6907BB1B7653CF60750A7124AD638D2A3B492A13321E0F98A400295AF77`.
The first metadata attempt passed119/120: an unnecessary checklist-date override
differed from its canonical default. Restoring the default reproduced the prior
ledger exactly; no checklist requirement changed. Failure capture51.828seconds,
log `CDEA5538B3352587474AEE5626C05FC57244C004BA8313C09810F7C68F217105`.
Final records are regenerated after recording these outcomes and checked again.
Read-only projection retains2/27 native admissions and5/27 Python source closures
current,25/22 stale; firmware is current, boot-trust/ELF prerequisites stale.
This is source-consistency inspection, not new execution or production promotion.
No owner action is needed for the next engineering step.
