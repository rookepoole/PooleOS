# Cycle283: Native User-Space Applications

Date:2026-10-13. Previous cycle classified as progress: application shell/file policy
compiled, host-tested, committed and pushed. This cycle connects the native launch
path and qualifies useful apps. Owner priority remains the user-space integration
ISO, followed by the complete robust microkernel.

## Implemented And Verified

Actual PooleAppShell/PooleAppFiles/PooleText/PooleNumbers run in the six-role native
session. Launch hands off actual SEND-only grants through owned startup bytes before
dispatch. Child generation and launch sequence agree across two generations each.
On handoff failure owners remain retained; admission/handoff are not one rollback
transaction. [Detailed contract](../native-app-session.md).

Three fresh application guests pass, including stale numbers-file authority. Each
receives557 input bytes/37 commands. Normal apps compute changed results, coexist,
fault and restart. Text/shell continue after numbers UD2; child pages are reclaimed
before service exit. Dispatches7936/7808/7744; hostile rejections757/747/742.
Nine regression guests pass: three legacy files, three prepared-child deferred
cleanup, two default kernel and unsigned denial. All passing captures retain stable
source/owner bindings. Independent kernels and17 program ELF/code pairs match.

Kernel tests per debug/release:551 default,567 files,570 apps;26 ownership doctests.
Nine new Python tests pass. App kernel121/208 pages, files/deferred115, default208;
36 guarded stack pages remain. No PMM-record or user-RX increase. App-only RO/entry
boundary0x13000 has4296 padding bytes. Full stack bounds remain unproven.

Public receipt: `runs/native-app-session-readiness.json`,2138460 bytes, SHA256
`9A5A0855F6253BF225E4AB92390D107B9411EF7C1A17EE7F5A1FBC7E677E92E6`.
912 execution inputs. Application capture158.469 seconds, SHA256
`EEF611C7E91F7A4142F9FFFDD3790ED85233C5A2CEF22423003518D7F625479A`.
Host capture103.422 seconds, SHA256
`62EC570A455AFEEB4A4EA2B640E2C2B60DA078E0057E6AB3A02A3C4472544C3B`.
Regression capture531.437 seconds, SHA256
`774500B087B52A2AE3017260E0C4C9116E083EA8493198E813AC70B291FBED78`.
Metadata/staged checks revalidate schemas, roadmap, binary pairs, owner hashes,
immutable historical receipts and the exact publication boundary.
The repaired metadata/oracle suite passes295 tests in63.929 seconds,65.015 including
capture; log SHA256
`16BD7F3C645E2B96068004B7FA117DAC9B36AE70414435D15D3EAD9B6D061172`.
Final staged replay follows these closeout edits; neither check is full canonical
qualification. The public native receipt remains immutable during metadata closeout.

## Preserved Failures And Repair

The first synthetic oracle test expected20 calls where its fixture generated30;
expectation repaired, failed capture retained. The first native guest progressed
into shutdown but timed out at its frozen240-second bound. Partial console I/O,
debug trace and timeout state remain local, not promoted.

The oracle assumed shell must exit before console. CLOSE replies permit the reverse;
the repaired rule requires both apps retired before either service exits. A new
regression test covers this. A second diagnostic froze360 seconds, then was deliberately
interrupted after discovering repeated timer calibration on restarted programs.
Only initial launch had enabled the per-owner cache. Restart now measures into its
own fresh cache; no previous owner sample is reused. The original240-second bound
was restored before rebuilding and all three passing guests. The failed timeout
and intentional connection-reset are retained. No safety or import check was removed.

The first295-test metadata run failed one old inventory assertion: current kernel
source files increased from126 to128, while its immutable historical receipt still
binds79. The test now names both newly uncovered paths; it does not rewrite that
old receipt. Current lane fields also distinguish actual apps/page counts from
historical diagnostic and stack-frame observations. Failed metadata log SHA256
`D0D4AE2A91601C6B6706882E2B2EEB0202EFA1300D4B3B7A3F379E6843D7DEC0`.

## Next Move And Gaps

Close native malformed/untracked file requests, requester death, live-parent
deferred completion/restart, exhausted/multiple cleanup owners, waiting children
and pending/claimed request interleavings. Then build the optical ISO and exercise
sustained input on fresh boots through an operable VM launcher. Current COM2 is
not local keyboard/display. No new ISO, full canonical suite, main merge, signing,
release or production promotion is claimed.

General supervision, efficient idle, interactive job abort, full stack bounds,
complete microkernel, PooleGlyph/PDC and accessible PooleGlass remain required.
No phase/flag closes:40 phases301 subphases8996 requirements59 additions98 flags43
open20 gap groups.1450 Python tests,740 architecture bindings and912 execution
inputs are inventories, not canonical execution counts. PooleGlyph Phase65 remains
latest; Phase66 Core IR audit is next. Owner inputs and historical receipts remain
unchanged. Owner temp directories are untouched. The shared host build target is
not deleted or archived. Generated build/evidence directories remain local.
