# Cycle299: Generation-Bound Surface Lifecycle

Started: 2026-10-17. Status: native implementation, full guest replay and expanded
metadata qualification pass. Production readiness remains partial.
Parent: `d676f57411415fc6be7c90627857439384de7d44`, Cycle298.
The preceding goal turn made progress: kernel capacity qualification, repaired
host-runtime replay, metadata checks, checkpoint commit and cloud push completed.

## Selected Work

Connect actual process lifetime to isolated native application surfaces. Reuse
read-only PPROC1 inspection leases and PCOMP1 state, with trusted launch-time
observer replacement. Keep the existing four total/two-per-owner lease limits.
Expose a bounded read-only query over authority already held by the caller;
a supplied slot/generation does not grant authority. No application termination
right is delegated to the compositor. Ordinary window and capacity profiles
remain regression targets; the lifecycle path is opt-in.

Alternatives considered: client CLOSE alone cannot report faults; shell-sent
notifications introduce a second lifecycle authority and message-loss recovery;
raw task-ID lookup would bypass capabilities; new kernel notification queues
duplicate existing process state and add backpressure; persistent old/new leases
would consume the fixed quota. Selected: preflight observer replacement before
failure-atomic launch, then commit without a dispatch window. An old observer is
replaced only after recorded completion; admission failure preserves it.

## Acceptance Invariants

- SL1: only a trusted admitted Inspect lease authorizes observation. Foreign,
  stale-owner, forged-root, future-generation and ambiguous queries fail closed.
- SL2: replacing an observer and admitting its child is atomic on the exclusive
  BSP. No partial grant, quota leak, spent-generation reuse or stale completion
  may authorize a new lifetime. Parent control remains separate.
- SL3: exact generation retirement clears surface bytes and its handle while
  retaining the generation tombstone. Old requests/events cannot resurrect or
  close a new surface; another client's surface remains unchanged.
- SL4: detached or superseded authority means unavailable, not proven physical
  reclamation. Only PCOMP1 terminal completion proves the recorded completion.
- SL5: closing a window cancels its drag/focus state and taskbar availability.
  Pending surface replies cannot reapply an old operation or block retirement.
- SL6: native fault/stop disappearance, restart, other-app survival, input modes,
  final pixels, real ISO boot and owned VM cleanup need current-source evidence.
  Existing timing, memory, ownership and publication controls remain enforced.

## Verification And Progress

The first six observer host tests and41 desktop-focused tests passed. The first
independent program build passes187 user tests in debug/release, then fails the
freestanding link: a checked `enumerate` increment retained core panic-location
data with an absolute relocation. The object identifies core's enumerate.rs:82.
Replace the two fixed-size iterator loops with explicit bounded indexing; keep
the no-writable-data/no-relocation linker checks unchanged. Retain programs1's
failed receipt, log and object; no native execution is inferred from host tests.
The corrected `programs2` attempt passes:26 independent ELF/code pairs and187
user tests in each debug/release profile. The wrapper records24.015 seconds,
unchanged sources and log SHA256
`0E5F65CD8CAE1C28AF762691045875B6EE98456C38C4688FA9B78207008E6EDF`.
The six lifecycle barrier tests cover exact generations, absence of retired
pixels, survival of the other pane, single-character/batched input gating and
all oracle call-site opt-ins. Focused2 passes77 overlapping Python tests.
Its first local fixture omitted the final marker newline; the real parser
correctly ignored that incomplete record. Correct the fixture, not the parser.
The first full kernel matrix stops on an unused test import in non-lifecycle
profiles. Scope the Request import to the lifecycle feature and rerun all six
profiles in debug/release as host2; retain the first failed host log.
At that point no new ISO, production phase, signing, merge or release was claimed.
Host3 passes all six kernel profiles in debug/release:582/601/607/613/614/614.
Host2 also exposed two old syscall27-unknown assertions; those now retain the
ordinary-profile rejection and unconditional syscall28 rejection while the new
lifecycle-specific test covers syscall27 shape and version. The first optical
guest reaches useful file work but halts at stage34433 on faulting Numbers.
Trace: `finish_retire` still expected one completion recipient; the new profile
correctly publishes to the parent AND the Inspect-only observer. Update that
exact profile-specific count, preserving completion-after-reclamation and the
ordinary one-parent rule. Add observer/parent-death fan-out checks; retain
optical1's191.0-second failure and replay on fresh source. Kernel budget132/208
pages and36 guarded stack pages passed before that guest failure.
Host4 passes all12 kernel profile/mode runs after the fan-out fix. Focused3
passes77 tests in2.397 seconds (wrapper2.875); log SHA256
`4CC84CDB37157D8A87F1976A4CCFFEB9E6530BDC08787F639A20C58627A11591`.
Current discovery finds1573 tests with zero errors, not a full-suite pass.
Execution binds978 files, programs89 and planned architecture bindings836.
The rebuilt kernel remains132/208 pages; no capacity or time limit is relaxed.
Owner checklist, PooleGlyph Phase65 ZIP and conformance report match the recorded
hashes. Phase65 remains newest; its next checkpoint is the Phase66 Core IR audit.

`outputs/cycle299-optical2/receipt.json` passes all four final-source optical
checks: two normal boots, stale-file-authority control and ordinary unsigned
denial. Independent kernel/media builds match. Fault/restart/stop, all-role
sustained progress, exact outputs, terminal retirement and final cleared-window
pixels pass. Wrapper650.594 seconds; sources unchanged; log SHA256
`94AD51A54BF82A8F8AD4ADABB9FDAA0F65A5DEB6EEA39D3254C7BB5A2BEF6BE6`.
The240-second per-session and45-second denial bounds are unchanged. Legacy
capacity replay and both QEMU/VirtualBox device modes were still pending then.
Do not infer the six intermediate lifecycle pixel barriers from this serial
cohort or promote the local preview pointer before full device verification.

`outputs/cycle299-legacy1/receipt.json` also passes all four optical controls on
current source without the lifecycle opt-in. Wrapper576.235 seconds; unchanged
source. Its concise stdout log has the same text/hash as optical2, while the
distinct source-bound receipts, kernels, images and frame oracles identify the
two actual profiles. This preserves the ordinary completion-recipient path;
old receipts are not relabeled as a fresh regression. Full device runs follow.

QEMU single-character device mode passes as `qemu-standard1`, wrapper211.203
seconds, unchanged source and ISO. All17 pointer steps,573 keyboard bytes,
six intermediate lifecycle pixel barriers and exact generation records pass.
Actual captured fault-removal and restart frames were visually inspected:
Numbers and its taskbar entry disappear while Text/Terminal remain; the fresh
Numbers generation returns and displays the new result. No host simulation.
Burst QEMU and both VirtualBox modes remain pending at this observation.
`qemu-burst1` subsequently passes the same17 pointer steps,573 keyboard bytes
and six lifecycle barriers in four-character mode; wrapper203.094 seconds.
Both QEMU device runs retain the existing12/240-second bounds. VirtualBox runs
use owned headless guests this cycle; visible GUI-mode tests from Cycle298
remain historical, not a new visible-mode claim.
The first headless VirtualBox attempt then fails at the first lifecycle capture:
the adapter's owned-path allowlist recognizes only prior pointer filenames.
`vbox-standard1` is a failed125.281-second attempt, not native lifecycle
acceptance. Its runtime is unchanged; VM stop/unregister and unchanged prior
registrations are confirmed with no cleanup errors. Add only the six exact
`lifecycle-00.ppm` through `lifecycle-05.ppm` names inside the owned work directory,
retaining capture size/geometry checks. Tests reject sibling paths, index06,
wrong widths and wrong suffixes, and verify every RGB byte in all six conversions.
Focused4 passes77 checks (wrapper2.860 seconds). Only the Python adapter and its
test changed; native Rust and89 program bindings remain exact. Host4 is retained
as current-native-Rust host evidence, not claimed to have rerun after the Python
fix. Replay all native guest cohorts on fresh bindings: optical3, visible
vbox-standard2/vbox-burst1, qemu-standard2/qemu-burst2 and legacy2. Prior passes
remain historical snapshots; their receipts are never rewritten.
The new `optical3` cohort passes all four controls on the final execution
bindings in 609.047 seconds, with unchanged source. Its normal ISO is 66109440
bytes, SHA256 `691826E53A6EEAB9947C74F405E75B34C4D3DE4455C50D15CADD3AB1F8F5FCBC`,
identical to the pre-capture-fix native image. The visible VirtualBox replay has
started. Its actual initial frame shows the native Terminal and two isolated
result panes; the desktop remains a basic functional prototype, not PooleGlass.
Both visible VirtualBox modes now pass on the final source and ISO:
`vbox-standard2` in 219.469 wrapper seconds and `vbox-burst1` in 199.610.
Each verifies 17 pointer steps, 41 observed movements, 573 keyboard bytes,
zero serial input, six exact-generation lifecycle pixel barriers, exact output,
unchanged runtime and complete owned cleanup. The actual removal/restart PNGs
were inspected: Numbers disappears without disturbing Text, then returns with
the fresh result. `qemu-standard2` also passes all six lifecycle barriers and
17 pointer steps on final source in 221.828 wrapper seconds. Its actual 1280x800
fault-removal frame was inspected; the remaining application and Terminal stay
visible and the retired pane's region is cleared. `qemu-burst2` passes in
207.234 wrapper seconds with unchanged source and ISO, completing all four
full device modes and their 24 lifecycle barriers. The final legacy cohort is
running; no compatibility pass is inferred merely from the new profile's success.

## Final Native Cohort

`legacy2` passes all four capacity-profile optical controls in 574.016 wrapper
seconds on final source. The complete final cohort is ten QEMU and two visible
VirtualBox checks, all passing with unchanged source/image and unchanged bounds.
All four full input runs verify 17 pointer steps, 573 keyboard bytes, zero serial
input and six lifecycle pixel barriers each. Both native framebuffer sizes were
visually inspected. Owned VirtualBox cleanup is complete, with prior registrations
unchanged and no cleanup errors. Both native crates pass `cargo fmt --check`.

The public receipt is `runs/native-surface-lifecycle-readiness.json`, SHA256
`A5D51ADEE585DD7FA07C5525C4FCDAD6686A9FAEEE3C67DD0A63BF416C097521`.
It binds 978 execution sources and 89 program sources; all 26 independently built
ELF/code pairs match. Packaging independently rechecks every intermediate capture,
exact input/output challenge, generation barrier, cursor pixel sample and native
marker trace. It preserves the failed program, host, optical and VirtualBox
attempts rather than rewriting them. Only the two Python capture paths differ
from host4; native Rust and native ISO bytes remain exact.

The tested ISO is copied without replacing Cycle298 to Downloads as
`PooleOS-Native-Windows-Cycle299.iso`; its SHA256 matches the optical3 image above.
The local preview pointer now selects optical3. Immutable-history,
publication-boundary and staged-byte checks gate cloud checkpointing; the local
final audit result is retained as `outputs/cycle299-finalcheck.json`.

The first expanded metadata run executes 418 tests in 117.232 seconds and fails
two stale inventory assertions: the architecture schema still required exactly
828 bound files, and the historical-entry test expected 134 current Rust files
instead of 135 after the observer test module was added. The frozen historical
entry still has exactly 79 inputs. Update the exact schema to 836 and add the
new file to the exact current-minus-historical set; do not weaken either audit.
Retain `metadata1` and its log SHA256
`5B2408B3C85F67BC920E2C5A88EC94CA9E57F021A0607621EBF238528EAD66F6`.
Reconcile three stale current gap-summary lines that incorrectly claimed no
native input/shell/compositor existed. Preserve their previous wording under
`historical_cycle298_user_space_gap_summary`; keep production requirements open.
These are metadata-only changes; the 978 execution and 89 program bindings,
native products and public lifecycle receipt remain unchanged.

The corrected `metadata2` run passes all 418 overlapping tests in 115.892 test
seconds (119.015 wrapper seconds), with unchanged execution sources and zero
discovery errors. Log SHA256
`C537F27C76FD4539E2A30504DE2406C6BAAB2298A399CC10C0949001EF4C857D`.
1573 discovered Python tests are inventory, not a full canonical execution.
Final bookkeeping regenerates and independently compares the documentation-bound
architecture and roadmap artifacts; no further native or tested metadata-code
change is made. Architecture binds 836 files. Coverage remains 40 phases, 301
subphases, 8996 checklist requirements and 59 additions; no phase or flag closes.
The source-available checkpoint remains on the agent branch/draft PR81, subject
to the exact final audit. It is not a main merge, signed release or production
promotion. Existing history, owner inputs and unrelated temporary files stay
unchanged.

The complete microkernel, PooleGlyph/PDC, accessible PooleGlass, useful apps,
native input overload/recovery, service restart and all N0-N39 gates remain.
