# Cycle301: Input Lifetime Boundaries

Started: 2026-10-17. Status: bounded increment complete; production goal active. Parent:
`eb3d94b3562383a415b3574f16db50342cd17e49`, Cycle300.
Previous goal turn: progress. It implemented direct isolated application input,
qualified native guests and independent binaries, updated the plan and pushed
the checkpoint to draft PR81. The full production goal remains active.

## Entry And Selected Work

The branch and origin match at cycle entry; only pre-existing `.tmp/` and
`native/.tmp/` are untracked. Ordinary usage is allowed: the available weekly
window is 51% used, with no separate five-hour value. The owner master checklist,
Phase65 ZIP and PooleGlyph conformance report retain their Cycle300 hashes.
Phase65 remains the latest checkpoint. No language/PDC integration gate changes.

Code inspection finds a gap between decoded input ownership and raw controller
bytes. The window service observes retirement before draining PS/2. Its current
fallback focus can therefore receive bytes that were pending for the dead app;
the held-key fence covers already observed keys, not unseen makes. A controller
reset also clears drag state without quarantining later bytes in the same batch.

Compare mechanisms: retaining fallback focus with only decoded-queue clearing
misses unread bytes; an unbounded flush can stall services; kernel timestamped
input queues require a separately designed driver/interrupt contract; granting
device access to apps breaks isolation; bounded service quarantine with explicit
fresh focus preserves current authority and makes recovery observable. Select
the last mechanism for this increment. Hardware/device-internal delayed bytes
and scheduling ambiguity remain separate from the observable drain boundary.

## Active Invariants

- IL1: asynchronous loss/replacement of the focused surface leaves no implicit
  keyboard recipient. A new valid pointer press must explicitly choose focus.
- IL2: raw bytes available before an observed empty controller read are not
  delivered to a new focus. Quarantine survives a full 32-byte turn and errors;
  it never treats quota exhaustion as an empty device.
- IL3: quarantined keyboard makes/breaks preserve held-key fences and partial
  prefix safety. Pointer bytes may move the cursor but cannot click, drag,
  minimize or restore another surface. A consumed press cannot transfer.
- IL4: input reset clears decoders and cancels affected drafts, then enters the
  same bounded quarantine. It cannot manufacture fresh focus or button authority.
- IL5: trusted surface/lifecycle identity remains authoritative. No new syscall,
  device grant, capability, process lease or mapping/code-page allowance. Keep
  ordinary profiles unchanged and independent binary/host checks explicit.
- IL6: verify native focused/dragging retirement and recovery with actual device
  input and pixel evidence; distinguish serial fault-control commands from guest
  keyboard delivery. Never label host models or diagnostics as final ISO proof.
- IL7: retain failures, old receipts and owner inputs; update plan and evidence.
  Full canonical, PooleGlyph/PDC, accessible PooleGlass, persistent editing and
  every N0-N39 requirement remain open unless independently satisfied.

Strongest planned verifiers: failing-before/passing-after host device streams,
identity and prefix/overflow mutants, fixed-work checks, freestanding independent
builds, native QEMU/owned visible VirtualBox retirement/recovery, source/ISO/pixel
identity, legacy regression and exact staged publication checks. None of these
planned checks is claimed to have passed yet.

## Boundaries And Next Work

An empty polled i8042 read is an observable software boundary, not proof that a
physical keyboard has no internally buffered future report. Do not claim full
physical-device or arbitrary timing/typematic qualification from this policy.
Compositor restart, event-driven waits, fairness/latency, graphical launching,
persistence, portable preview packaging and complete driver isolation remain.
The current source-bound launcher becomes stale during development; retain the
Cycle300 ISO and advance the pointer only after new native qualification.

## Implementation And Counterexample

The initial regression uses the original lifecycle-to-input ordering through a
behavior-preserving boundary wrapper. `regression-before1` fails: unread set-1
make/break for A becomes `Some(97)` in Terminal after the focused app closes,
instead of no delivered byte. The retained log SHA256 is
`65B5E55A6FBEE0973BD88A8E5EEF250D295580BC8796DE3E422F64FD9D726B21`.

The input profile now clears focus and capture, quarantines the raw stream and
keeps the existing 32-read turn budget. Only an observed empty read ends the
quarantine; it fences every observed held key and incomplete prefix. Quarantined
motion updates pointer position/button release without generating window actions.
Reset enters the same policy. Ordinary profiles retain their previous behavior.
Interactive surface/lifecycle painting is deferred until the final input/focus
state, avoiding painting an implicit fallback focus before clearing it.

`regression-after1` passes the first seven boundary tests. These are host proofs,
not native retirement qualification. Add replacement/peer preservation coverage,
then independently build and exercise the final native image. Planned native
controls use serial only for explicit fault/stop commands while a pointer drag
and modifier are held; all other shell input remains emulated device input.
They do not claim native arbitrary controller backlog or continuous typematic
stress merely because focused retirement and recovery pass.

`programs1` stops before native compilation: all 217 debug host tests pass, but
the build qualifier still requires the old 209-test inventory. Advance the exact
expected count to the measured 217 (eight new lifetime tests); do not remove the
count guard. Preserve the failed wrapper and debug log, then rebuild under new
source bindings. No native-program or ISO pass is claimed from this attempt.

`programs2` passes 217 tests per debug/release and all 29 independent ELF/code
pairs in 20.954 wrapper seconds. Only PooleWindowInput differs from Cycle300;
the other 28 ELF identities are unchanged. Ordinary window code remains
16,364/16,384 bytes and the explicit service remains 24,594/28,672 bytes.

The new two-scenario native challenge isolates fault/stop control to exactly
24 serial bytes; the rest of the 332-byte shell case uses device keyboard input.
It observes actual drag movement and return, an uppercase app draft proving the
held Shift state, retirement while dragging, no implicit focus or peer draft
input, release/fresh-click recovery and exact lowercase status commands before
releasing Shift. Host pixel mutants reject focus leakage, stale surfaces, peer
draft changes and moved Terminal geometry. The first 42-test Python run finds
an off-by-one parser guard rejecting adjacent nonoverlapping control ranges;
change overlap rejection from greater-or-equal to strictly greater and replay.

`python-focus2` passes all 42 checks in 3.407 wrapper seconds. The first
diagnostic image builds in 24.843 seconds at 134 kernel pages, but
`lifetime-diagnostic1` fails after 39.266 seconds, before any shell input, at
the unchanged critical-service termination guard (stage34004). The failure does
not identify exit/fault/watchdog reason. Preserve the failed guest and add bounded
numeric diagnostics immediately before the same unconditional stop. No failure
is bypassed, no exception is resumed and no live memory is dumped by this change.
Rebuild a separate diagnostic image before drawing conclusions about the cause.

`diagnostic-image2` builds in 22.125 seconds. `lifetime-diagnostic2` fails
before shell input in 9.375 seconds and identifies task2: page fault vector14,
error6 (user write to absent page), RIP0x4001042c, address0x40002fe8.
Disassembly of the exact program maps offset0x42c to a call instruction pushing
below the guarded stack at0x40003000. The service entry reserves0xe08 bytes plus
saved registers; nested composition crosses the one-page user-stack boundary.
This rejects the initial native candidate despite passing host tests. Separate
interactive polling temporaries from the long-lived entry frame; preserve the
ordinary profile's inlining and all stack/mapping guards, then rebuild and replay.

`programs3` passes both 217-test profiles and 29 independent builds. The third
diagnostic boots past startup but fails after the first app admission: task2,
vector14/error6, RIP0x400106e9, address0x40002fb0. Splitting polling alone does
not remove nested composition depth: the entry frame is0xd28 bytes and polling
reserves0x1a8 before calling painting. Return a bounded three-region damage plan
before composition, so polling temporaries have expired before renderer frames
are entered. Preserve this second failed candidate and all fixed stack limits.

The 559 raw Cycle300 final application PPMs were losslessly archived and each
decompressed member/hash verified before scoped removal, recovering1,533,379,312
bytes. Archives/manifests remain under `outputs/cycle301-prior-frame-archives`;
old PNGs, receipts, logs, ISOs and other frames remain. Archive wrapper SHA256:
`6AD2D0D35ACE17CF804C4537383A99E093F8AB396E0C844519237EDB11B4EFD9`.

`programs4` and `programs5` reject an ordinary-profile code-size regression;
the corresponding diagnostic-image attempts reject their failed program
receipts before building. Restoring the exact ordinary pointer-paint sequence
fixes that regression. `programs6` passes both217-test profiles and29 independent
program pairs in18.203 seconds. Only PooleWindowInput differs from Cycle300;
all28 other ELF identities remain unchanged. No budget is raised.

`diagnostic-image6` builds in21.937 seconds at134 kernel pages. Its ISO SHA256 is
`CC437211E7AF65EC0753E940AB49C68E1AE6495ACE2FDD9681D9E7BA5E996F47`.
`lifetime-diagnostic6` passes the QEMU challenge in158.922 wrapper seconds with
24 lifetime observations and six lifecycle barriers. It is explicitly diagnostic,
not a qualified preview. Its98 raw application PPMs are retained in a verified
lossless archive, recovering301,057,568 bytes. VirtualBox diagnostic and full
final-cohort qualification are the next checks. A production stack-depth/high-water
gate remains open; successful scenarios do not establish all-path stack safety.

`vbox-lifetime-diagnostic6` passes the same24-observation challenge in153.828
wrapper seconds with owned cleanup. Its88 raw PPMs are losslessly retained,
recovering207,619,456 bytes. The final sequential cohort begins only after both
diagnostics pass under the current993 execution bindings. All seven kernel
profiles pass debug/release (582/601/607/613/614/614/614); `python-focus3` passes42
checks in3.375 wrapper seconds. Final optical, ordinary input, lifetime and
legacy guests are in progress. Public receipt generation, launcher promotion,
metadata replay and commit remain gated on those final results.

The final optical cohort passes in627.515 wrapper seconds: two independent
normal boots, stale-file-grant rejection and ordinary unsigned denial. The
ordinary direct-input regression passes QEMU standard/burst in224.062/223.094
seconds and visible VirtualBox standard in236.406 seconds. Each observes96
application states, six lifecycle barriers and17 pointer steps with332 device
keyboard bytes and no serial controls. VirtualBox burst, the four final lifetime
challenges and legacy capacity regression remain pending. Intermediate captures
are losslessly archived only after each completed guest, with decompressed hashes
verified before scoped removal; final frames, logs and receipts remain available.

`vbox-input-burst1` fails after152.984 wrapper seconds at lifecycle step121.
All96 app observations and17 pointer steps pass, but no retirement marker arrives
within the unchanged12-second observation bound. COM2 reports Numbers fault6;
COM1 ends midway through a RUN record before any RETIRE. Cleanup passes. The
kernel COM1 sink disables itself after4096 unsuccessful transmit-ready polls;
that is a plausible cause, not proven by these logs. Preserve the failed receipt,
logs and164 archived frames. The cohort stops, with no preview promotion. Perform
one unchanged replay under a new tag, without altering source, ISO, time bounds
or acceptance. Even a passing replay cannot close diagnostic-transport reliability;
track diagnosis and bounded record delivery under the existing N3 preview flag.

The single unchanged `vbox-input-burst2` replay passes in226.281 seconds with
all96 app observations, six lifecycle barriers,17 pointer steps and owned cleanup.
Source/ISO identities and all bounds are unchanged. This is retained passing
scenario evidence, not resolution of the preceding intermittent diagnostic loss.
`qemu-lifetime-standard1` passes the final optical image in167.844 seconds with
24 ordered lifetime observations, six lifecycle barriers and exact channel counts.
The other three final lifetime runs and legacy regression are still in progress.

The remaining final lifetime guests pass: QEMU burst159.000 seconds, visible
VirtualBox standard155.860 and burst145.734. All four final lifetime runs have
24 ordered observations, six lifecycle pixel barriers,24 serial control bytes
and308 device keyboard bytes, exact transcripts, unchanged sources/media and
owned cleanup. Combined with the four ordinary-input passes, the eight passing
interactive guests cover384 app observations,96 lifetime observations and48
lifecycle pixel barriers. The failed additional VBox burst attempt remains
unresolved diagnostic-repeatability evidence; it is not included as a pass.
Legacy optical capacity regression is now running before package/audit closeout.

Review clarification: the consumed-press fence requires an observed release.
When the button was already up and no post-boundary release packet arrives, the
first click-and-release is consumed and the following press can select focus.
The native challenge covers held-button release/fresh-press recovery, not every
physical pointer state or seamless one-click recovery. Preserve this limitation
in the launch guide and contract; do not broaden the measured usability claim.

Legacy optical capacity regression passes in574.094 seconds: two normal boots,
stale-file rejection and ordinary unsigned denial, on unchanged final sources.
The passing final-source cohort totals12 QEMU and4 visible VirtualBox checks.

The first packaging audit rejects an intermediate application movement frame
because it adds a three-pixel cursor check where the existing app movement
contract checked only its tip. Retained `package1` reproduces the failure with
log SHA256 `F8666625121E7C03C468B9191CB2ED5653DA2884CD272463A5C9E15F4F3B1904`.
QEMU burst `application-133.ppm` has tip/body pixels but its tail at(1060,101)
is the app background; the immediately following recorded movement frame134 at
the same position has all three cursor pixels. This is a partial repaint, not
atomic presentation. Preserve both exact hashes and require the complete next
movement frame for each such observation; keep full cursor checks for the
pointer and lifetime probes. No guest oracle or timeout changes. Atomic/double-
buffered presentation remains open; the audit must not invent that guarantee.

`package2` passes reconstruction in13.922 seconds, including both partial cursor
frames (QEMU133 to134 and VBox119 to120), exact control channels, source/ISO/pixel
identities, historical receipt preservation and16 passing final-source guests.
Public receipt SHA256:
`35C46536C1E7B66B7DF4B5EC478F9F5A9ABE11AAFA1F42E5D94C650057C36367`.
The local preview pointer advances only after this pass, preserving the old
pointer. Downloads `PooleOS-Native-Windows-Cycle301.iso` is directly byte-equal to
the66,109,440-byte optical image, SHA256
`CC437211E7AF65EC0753E940AB49C68E1AE6495ACE2FDD9681D9E7BA5E996F47`.
No release publication or physical-media write occurs. Metadata and staged audit
remain pending. All40 phases/301 subphases remain in scope; one required stack
flag is added without closing a phase. Owner hashes and latestPhase65 are unchanged.

`metadata1` executes434 checks in123.312 wrapper seconds with one failure: an
older test still expects44 current open flags. The new required stack flag makes
45 of100 total flags open. Correct that exact current-count assertion without
changing historical receipts or closing the flag. Discovered Python inventory is
1589 with no discovery errors, not a full-suite pass. Failed log SHA256:
`FC85EEAE1C18375C63F12B3C3E00315F4B87FB969E295330C32C0553C882438E`.
Replay the complete metadata selection after regenerating the bound ledgers.

`metadata2` passes all434 checks in122.594 wrapper seconds. Inventory1589 has
no discovery errors; this is not a full canonical execution. Log SHA256:
`251F2E80EC326085960D5F794F899CA30165FBEB0D13CF022B0815E8ED2C0CDB`.
Current counts are857 architecture files,993 execution bindings and97 program
inputs; all40 phases/301 subphases and100 flags (45 open) remain represented.
Stale current-binding counts in older metadata tests now reference97, while
historical receipts retain their original counts and hashes. Final staged audit
and branch push remain pending; production promotion is not authorized by these
partial qualification results.

## Closeout And Next Move

Precommit audit passes30 exact staged blobs,85 immutable historical readiness/
execution receipts, independent program/kernel products, current source binding,
native marker/transcript/pixel reconstruction, pinned VBox/runtime cleanup,
owner-input hashes and direct Downloads ISO byte equality. Publication scan:
2097 paths, zero violations. This closing note and dependent generated ledgers
are revalidated before commit/push; no source or native image changes follow
qualification. Keep PR81 draft. No full canonical replay, main merge, signing,
release publication, physical-media write or production promotion occurs.

Next: diagnose bounded COM1 delivery, add least-authority graphical application
launch/restart, then compositor recovery/resynchronization and persistent editing.
Retain atomic presentation, event waits, fairness/latency, native backlog/reset/
typematic stress and all-path stack verification as separate acceptance gates.
No owner action is required for those engineering steps. Complete microkernel,
PooleGlyph/PDC, accessible PooleGlass and all N0-N39 requirements remain active.
