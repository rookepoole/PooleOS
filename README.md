# PooleOS

PooleOS is a source-available, commercial-rights-reserved native operating system owned and directed by Rooke Poole. It is being built as an original `PooleBoot.efi` UEFI loader, an original capability-based PooleKernel microkernel, isolated native system and driver services, PooleGlyph/PGB2/PGVM2 execution, canonical Poole Defect Calculus services, and an accessible PooleGlass desktop.

PooleGlyph IP is owned by Rooke Poole. PooleOS follows the same source-available path unless the owner later adopts a different licensing structure.

**Qualified baseline:** checkpoints through Cycle 233 are merged into `main`
at `507782d` via [PR #80](https://github.com/rookepoole/PooleOS/pull/80).
The exact candidate passed 106/106 runtime-inclusive canonical gates and 708/708
Doctor checks, including bundle and replay inputs. The merged tree matches that
candidate. This is a development baseline, not a production release, and its
qualification does not extend to later source changes.

**Current development checkpoint:** Cycle243 runs two real user tasks under the
native scheduler with separate address spaces and timer-driven context switches.
Two fresh boots each pass40 dispatches and33 preemptions, with continued peer
progress after exit, fault, cancellation and syscall-budget exhaustion.481 Rust
test executions and29 Python oracle tests pass. Next: finish admission/containment
hardening, then IPC, services, shell/apps and the user-space integration ISO.
No interactive session or new ISO yet; the complete robust microkernel remains
the production objective. [Evidence](docs/checkpoints/cycle243-native-user-peer-scheduling.md).

**Historical development checkpoint:** Cycle242 adds owned user-task exit and fatal
fault termination. Two fresh native guests each run four sequential tasks, reject
stale IDs and restart/reap repetition, and fully reclaim their memory.336 debug
kernel tests,110 repeated optimized tests, seven compile-fail checks, ten boot-exit
tests and26 Python oracle tests pass. Existing copy-fault and timer controls pass.
Next: preemptive peer scheduling, then IPC, confined services, shell/apps and the
user-space integration ISO. No interactive session or new ISO yet; full robust
microkernel development continues after the preview.
[Evidence](docs/checkpoints/cycle242-user-task-termination.md).

**Historical development checkpoint:** Cycle241 adds real native user-space system
calls and bounded, recoverable memory copying. Two fresh QEMU guests each pass
12 calls, three deliberate copy faults, entry-MSR cleanup, timer recovery and
all13 task-page releases.326 debug kernel tests,100 repeated optimized tests,
five compile-fail checks, ten boot-exit tests and23 Python oracle tests pass.
Next: task exit/fault termination and peer scheduling, then IPC, confined
services, a usable shell and optical ISO. There is no interactive session or
new ISO yet; full robust microkernel work continues after that preview.
[Evidence](docs/checkpoints/cycle241-native-syscall-usercopy.md).

**Historical development checkpoint:** Cycle 240 proves timer preemption of a spinning
ring-3 task in two fresh native QEMU boots. Each run resumes the task twice with
preserved integer/legacy FP state, then forces kernel recovery on the third
interrupt. Timer shutdown, descriptor detachment, root restoration and all13
task-page releases pass.320 debug kernel tests,94 repeated optimized tests and
ordinary unsigned-boot denial pass. Next: bounded syscall/user-copy mechanisms,
task lifecycle and peer scheduling, then IPC, services, shell/apps and optical ISO.
There is no interactive session or new ISO yet; full robust microkernel work
continues after that preview. [Evidence](docs/checkpoints/cycle240-user-timer-preemption.md).

**Historical development checkpoint:** Cycle 239 executes a real, bounded ring-3
payload in two fresh native QEMU boots. Private-stack fault handling denies
privileged operations, kernel reads and stack execution; controlled return,
descriptor cleanup and all 13 task-page releases pass. Live testing also fixed
VM cleanup of CPU-accessed page entries. There are 315 passing debug kernel
tests, 89 repeated optimized tests and preserved ordinary-boot denial.
Next: user-mode timer preemption, then IPC, services, shell/apps and optical ISO.
This is not yet an interactive OS or a new ISO. Full microkernel development
continues after that preview. [Evidence](docs/checkpoints/cycle239-bounded-user-entry.md).

**Historical development checkpoint:** Cycle 238 delivers and acknowledges three
timer interrupts under the owned task root in each of two fresh native QEMU
boots. Guarded supervisor-only uncached MMIO mappings and verified timer shutdown
protect restoration and task-memory release. All 300 kernel host tests, 54
optimized focused tests, five compile-fail checks, ten boot-exit tests, 15 Python
oracle tests and the default-boot denial control pass. This is still CPL0, not
user-program execution or a new ISO. Next: sanitized ring-3 entry and contained
faults, then IPC, services, shell/apps and optical packaging. Full microkernel
development continues after the integration ISO.
[Evidence](docs/checkpoints/cycle238-owned-root-timer.md).

**Historical development checkpoint:** Cycle 237 boots the real native kernel into
an owned task address space at CPL0, exercises its guarded supervisor stack,
restores the boot address space and releases all 13 allocated pages. Two fresh
QEMU probes and an ordinary-boot denial control pass, alongside 288 kernel host
tests, 42 optimized focused tests, five compile-fail checks, ten boot-exit tests
and 13 Python regression tests. Live testing also fixed an APIC register read.
No user-mode task or new ISO exists yet. Next: timer-backed recovery, sanitized
user entry and contained faults, followed by IPC/services/shell integration.
[Evidence](docs/checkpoints/cycle237-live-user-root.md).

**Historical development checkpoint:** Cycle 236 adds the kernel's owning user-root
CPU lifecycle and a privileged x86-64 adapter. Failed switches/restoration keep
memory retained until verified recovery and detach. All 284 host kernel tests,
38 optimized focused tests, five compile-fail checks and freestanding kernel/
library checks pass, as do 84 roadmap/coverage checks. The adapter is not
boot-wired: no user-mode task or new ISO
exists yet. Next is bootstrap/timer integration and a bounded real guest probe.
[Evidence](docs/checkpoints/cycle236-user-root-cpu-lifecycle.md).

**Historical development checkpoint:** Cycle 235 adds an owned inactive user root,
validated supervisor mappings, and a guarded 16-KiB kernel-entry stack. Failed
preparation/cleanup preserves physical ownership until verified detach. This
advances the native user-space integration ISO; no ring-3 execution or new ISO
exists yet. All 272 kernel host tests, 26 optimized user-entry tests, two
compile-fail checks and 83 metadata tests pass. Live CPU-state/entry/fault integration and fresh guest qualification
remain required. [Evidence](docs/checkpoints/cycle235-owned-user-root.md).

**Historical development checkpoint:** Cycle 234 starts the owner-directed
[native user-space integration ISO](docs/native-userspace-integration-iso.md).
PKUSER1 adds owned inactive user-image admission, strict page-table checks,
guarded RX/RW-NX layout, and an initial unprivileged IRETQ frame. All 260 kernel
host tests, 14 optimized focused tests, format and freestanding-library checks
pass. No ring-3 task has run and no new ISO has been built. Changed kernel source
invalidates 25 of 27 retained component admissions; fresh guest qualification and
exact-candidate gates remain required before merge. The original full microkernel
and N0-N39 production goals remain mandatory after preview delivery.
[Cycle 234 evidence](docs/checkpoints/cycle234-user-entry-foundation.md).

**Historical development checkpoint:** Cycle 233 completes all fourteen remaining
corrected-media profile replays: 28 fresh guest runs, 663 control groups and
2,863 hostile cases pass. All 27 component and source checks are current, with
the aggregate reconstructed from original captures. All 354 combined regression
tests pass with zero skips after historical-assertion and schema reconciliation;
the failed attempts remain recorded. Exact-candidate gates still precede PR #80 merge.
The kernel and retained demo ISO are unchanged; this is not a production release.
[Evidence](docs/checkpoints/cycle233-corrected-media-downstream-replay.md).

**Historical development checkpoint:** Cycle 232 replays kernel revalidation,
boot-to-kernel transfer and five CPU profiles on the corrected FAT32 media.
All 16 fresh guest runs, 319 control groups and 77 focused regression tests pass.
Source-current coverage is 13/27 profiles; 14 memory, interrupt, SMP, scheduling,
atomic and lock profiles still require replay. Component checks pass 22/27;
the aggregate source guard correctly remains blocked. Next: physical memory,
then virtual memory and the remaining dependencies. Native executable bytes and
the retained demo ISO are unchanged. [Evidence](docs/checkpoints/cycle232-corrected-media-boot-and-cpu-replay.md).

**Historical development checkpoint:** Cycle 231 repairs the generated EFI FAT32
root-parent link and validates directory dot entries. All 26 focused tests and
four fresh loader/PooleBoot QEMU runs pass. Twenty-one dependent profiles still
need replay: the aggregate source guard correctly rejects the stale evidence.
This work can be backed up in a draft PR but is not yet eligible for main merge.
[Cycle 231 evidence](docs/checkpoints/cycle231-fat32-directory-links.md).
Next: kernel revalidation, then transfer and remaining dependent profiles.
Native executable bytes and the retained demo ISO are unchanged; no production
or N5 completion claim is made.

**Historical development checkpoint:** Cycle 230 adds inspection of actual ISO and
embedded EFI FAT32 bytes. All 19 new tests pass; the combined architecture suite
has 27 passes and one expected Windows symlink-permission skip. The unchanged demo
has 17 inventoried files but fails production architecture policy: a FAT root-parent
entry is incorrectly encoded, and four required production objects are absent.
[Cycle 230 evidence](docs/checkpoints/cycle230-native-iso-inspection.md).
Next: qualify this exact candidate before main merge, then repair the native media
writer and replay affected evidence. Native kernel and retained demo are unchanged.

**Historical development checkpoint:** Cycle 229 binds the remaining 18 observed
data dependencies, covering 13 specification files, to their original successful
execution snapshots. All 19 focused guard tests pass; the original 27 native
receipts and execution/source fields are preserved. The scoped data, media and
tool review is complete for a development merge, not production qualification.
[Cycle 229 evidence](docs/checkpoints/cycle229-reviewed-execution-inputs.md).
The preceding exact commit `293383d` passed 106/106 canonical and 708/708 Doctor
checks. The new candidate must pass its own full gates before PR #78 is merged.
Native kernel and demo ISO are unchanged; this remains pre-production.

**Historical development checkpoint:** Cycle 228 repairs the reproduced toolchain
test failure caused by the Windows host build changing from 26200 to 26300.
The test independently measures that build and still compares every other report
byte exactly. The original qualification ledger is preserved. Doctor and the
release gate now retain full failure diagnostics; all **19 focused tests** pass.
[Cycle 228 evidence](docs/checkpoints/cycle228-toolchain-host-observation.md).
Full exact-candidate qualification and the remaining dependency review still
precede the main merge. The integration branch provides cloud backup separately.
Native kernel and demo ISO are unchanged; this remains pre-production.

**Historical development checkpoint:** Cycle 227 repairs errata evidence admission.
Both validation paths reject **1,742 corrupted records without exceptions** and
accept the genuinely requalified receipt. All **34 focused tests** pass. The
hardware policy still denies the target for the same six reasons; no kernel or
demo ISO bytes changed. Twenty-six other source records remain untouched.
[Cycle 227 evidence](docs/checkpoints/cycle227-errata-recorded-admission.md).
Late full qualification of `79adf4a` **failed**: 105/106 canonical checks and
707/708 Doctor checks pass, but the Python regression command exits 1. The outer
report does not retain the individual failing test names. Next: capture that
failure in full and repair it, finish dependency review, then qualify the exact
candidate before merging PR #78. The checkpoints are cloud-backed; pre-production.
Combined regression passes **126/126**, zero skips. The explicit data-binding
inventory is consistent; coverage of all actual file reads and tool inputs remains
to be reviewed before a successful full canonical qualification.

**Historical development checkpoint:** Cycle 226 expands the source guard to all
27 selected profiles and 78 Python files; **22/22 focused tests** pass. A fresh
errata host run passes while retaining the hardware denial. Its receipt validator
has a demonstrated defect: six corrupted records are accepted and two malformed
records raise exceptions in both validation paths. This blocks the main merge.
[Cycle 226 evidence](docs/checkpoints/cycle226-selected-profile-source-coverage.md).
Next: repair errata admission, finish data/tool dependency review, then exact
canonical qualification. Checkpoints are backed up on the integration branch;
cloud backup does not require a main merge. Native kernel and demo ISO unchanged.
Combined regression passes **113/113**, zero skips. This is scoped testing, not
full canonical qualification or evidence that the known errata defect is repaired.

**Historical development checkpoint:** Cycle 225 adds a release-gate check for the
static Python source dependencies of 14 retained execution profiles. It binds 62
distinct files to their original run snapshots; changed helpers invalidate the
record. All 12 focused tests pass. No boot receipt was rewritten or relabeled fresh.
[Cycle 225 evidence](docs/checkpoints/cycle225-retained-execution-source-closure.md).
Upstream and non-Python dependency review, then full exact-candidate qualification,
still precede the main merge. Pre-production; native kernel and demo ISO unchanged.
Combined regression passes **102/102**, with zero skips. Upstream capture search
accounts for 12 of 13 additional profiles; errata policy needs earlier evidence
reconciliation before deciding replay. No full-suite or merge qualification claimed.

**Historical development checkpoint:** Cycle 224 repairs lock evidence admission.
Two final four-CPU virtual boots and **21/21 focused tests** pass; both validators
reject 631 corrupted records. All **27/27 selected native checks** now pass.
[Cycle 224 evidence](docs/checkpoints/cycle224-locks-admission-and-current-kernel-replay.md).
Next: shared-dependency binding review and full exact-candidate qualification
before merging [PR #78](https://github.com/rookepoole/PooleOS/pull/78) into main.
Checkpoints remain cloud-backed on the development branch. Kernel and demo ISO
bytes are unchanged. Pre-production; no phase or production gate closes.
The final timeout-cleanup regression passes **137/137**, zero skips, including 71
metadata tests. All 14 static helper closures match their original execution
snapshots; guard integration and broader dependency review remain pending.
Conservation verifies 382 source bindings and preserves all 27 parent records.

**Historical development checkpoint:** Cycle 223 repairs atomics evidence admission
and linked instruction auditing. Two final virtual boots and **22/22 focused
tests** pass; 356 corrupted receipts reject, and eight disabled native guards
are detected at optimization levels 0 and 3. Readiness is **26/27**, with locks
remaining. [Cycle 223 evidence](docs/checkpoints/cycle223-atomics-admission-and-instruction-audit.md).
Next: `N12-CONCURRENCY-LOCKS-001`, then shared-helper binding review and full
qualification before main merge. Checkpoints use [PR #78](https://github.com/rookepoole/PooleOS/pull/78).
Kernel and demo ISO are unchanged. Pre-production; no phase or production gate closes.
The final combined regression passes **146/146**, zero skips, including 70
metadata tests. Conservation verifies 379 source bindings and preserves all
26 parent progress records; initial admission and metadata failures are retained.

**Historical development checkpoint:** Cycle 222 repairs SMP-preemption evidence
validation and replaces seventeen unexecuted control groups. Two final four-vCPU
boots and **19/19 focused tests** pass, with 339 corrupted receipts rejected.
Readiness is **25/27**; atomics and locks remain. Kernel and demo ISO are unchanged.
[Cycle 222 evidence](docs/checkpoints/cycle222-smp-preemption-admission-and-controls.md).
Next: `N12-CONCURRENCY-ATOMICS-001`, then locks and full qualification before
main merge. Checkpoints are backed up through [PR #78](https://github.com/rookepoole/PooleOS/pull/78).
Pre-production; no phase or production gate closes.
The combined regression passes **167/167**, zero skips, including 69 progress
and architecture tests. Conservation verifies 377 source bindings and preserves
all 25 parent progress records.

**Historical development checkpoint:** Cycle 221 qualifies SMP scheduling and AP
workers on the unchanged kernel: **four four-vCPU boots** and **39 focused tests
pass**. Four obsolete measured expectations are corrected; both initial rejected
admissions are retained. Readiness **24/27** leaves SMP preemption, atomics and
locks, including seventeen control groups and recorded admission.
[Cycle 221 evidence](docs/checkpoints/cycle221-current-kernel-smp-and-ap-worker-replay.md).
Next: `N12-SCHED-SMP-PREEMPT-001`. Full qualification still gates main merge;
checkpoints are cloud-backed through [PR #78](https://github.com/rookepoole/PooleOS/pull/78).
Native implementation and demo ISO are unchanged. Pre-production.
Corrected metadata passes 68/68; earlier failed runs remain recorded.
Conservation verifies 374 source bindings and 25 unchanged parent archives.

**Historical development checkpoint:** Cycle 220 qualifies scheduling, BSP preemption
and deferred work on the unchanged kernel: **six virtual boots** and **47 focused
tests pass**. Two obsolete image expectations are corrected from independent
measurement; the initial admission failure is retained. Readiness is **22/27**;
five profiles and seventeen SMP-preemption control groups remain.
[Cycle 220 evidence](docs/checkpoints/cycle220-current-kernel-scheduler-replay.md).
Next: `N12-SCHED-SMP-001`. Main merge requires full qualification; checkpoints
are cloud-backed through [PR #78](https://github.com/rookepoole/PooleOS/pull/78).
Native implementation and demo ISO are unchanged. Pre-production.
Progress/architecture/checklist tests pass 67/67. Conservation preserves all 25
parent progress records and verifies 373 bound sources.

**Historical development checkpoint:** Cycle 219 qualifies memory, interrupts and
multiprocessor foundations on the unchanged rebuilt kernel. **12 virtual boots**
and **93 focused tests** pass. Ten obsolete measured gate expectations are
updated; the three initial rejected admissions remain recorded.
Selected readiness is **19/27**; eight scheduler/atomic/lock profiles and seventeen
SMP-preemption control groups remain. [Cycle 219 evidence](docs/checkpoints/cycle219-current-kernel-memory-replay.md).
Source checkpoints are cloud-backed through [PR #78](https://github.com/rookepoole/PooleOS/pull/78);
main still requires full qualification. Native code and the demo ISO are unchanged.
Next: `N12-SCHED-001`. Pre-production; no physical-hardware or general retirement claim.
Corrected progress tests pass 66/66; the initial ten failures remain recorded.
Conservation verifies 372 source bindings and all 25 archived parent records.

**Historical development checkpoint:** Cycle 218 fixes a screenshot capture race and
qualifies the rebuilt kernel's CPU profiles. **20 final virtual boots** and
**64 focused tests** pass. Native kernel and boot code are unchanged.
Selected readiness is **13/27**; fourteen memory-through-lock profiles and
seventeen SMP-preemption control groups remain. Initial failures are preserved.
[Cycle 218 evidence](docs/checkpoints/cycle218-terminal-capture-and-cpu-replay.md).
Checkpoints are cloud-backed through [PR #78](https://github.com/rookepoole/PooleOS/pull/78);
main requires full qualification. The demo ISO is unchanged.
Next: `N9-PMM-ACPI-CONSUMER-001`. Pre-production, not physical-hardware qualification.
Corrected progress/architecture/checklist tests pass 65/65; the initial five failures
are retained. Conservation verifies 371 bindings and all 24 parent progress records.

**Historical development checkpoint:** Cycle 217 qualifies the boot chain against
the rebuilt kernel: six virtual boots, two kernel entries and **97/97 focused
tests pass**. Symbol addresses and the host mapping probe now match the 149-page
image; the formerly failing live-transfer test passes. Kernel implementation is
unchanged. Selected readiness is **8/27**, with nineteen downstream profiles
pending from `N7-TRAP-001`. Seventeen SMP-preemption control groups remain open.
[Cycle 217 evidence](docs/checkpoints/cycle217-current-kernel-boot-replay.md).
Checkpoints are backed up through [PR #78](https://github.com/rookepoole/PooleOS/pull/78);
main merge still requires full qualification. The demo ISO is unchanged.
Unsigned-denial boot evidence is not production trust. Pre-production.
Progress/architecture/checklist tests pass 64/64; prior failures are retained.

**Historical development checkpoint:** Cycle 216 repairs native SMP-preemption
transactions and same-tick event/quantum progress. Twenty-seven native cases
pass in both host profiles, fourteen disabled repairs are detected, and all
17 ownership/core stages plus two clean matching kernel builds pass. The
selected host regression passes 43/43. The new 149-page kernel has not yet
booted in this cycle: readiness is **3/27**, with 24 profiles needing replay
from `N5-SYMBOLS-SEMANTICS-001`. The stale live-transfer positive remains a
failing merge gate, and seventeen scheduler control groups remain open.
[Cycle 216 evidence](docs/checkpoints/cycle216-native-smp-preempt-transactions.md).
Checkpoints are backed up on the development branch in
[PR #78](https://github.com/rookepoole/PooleOS/pull/78); main merge requires
full exact-candidate qualification. The demo ISO is unchanged. Pre-production.
Progress, architecture and checklist tests pass 63/63, with earlier failures retained.

**Historical development checkpoint:** Cycle 215 repairs AP-worker evidence admission
and replaces eighteen constant-only control groups with executed checks. Two final
four-vCPU boots pass 34 groups covering 325 cases. All 19 focused tests pass,
including 343 corrupted records, ten independent gate cases and 29 disabled
safeguard/transaction variants. Earlier diagnostic and harness failures are retained.
Selected readiness is **24/27**; SMP preemption, atomics and locks remain, with
at least 17 unproven control groups. Next: `N12-SCHED-SMP-PREEMPT-001`.
[Cycle 215 evidence](docs/checkpoints/cycle215-ap-worker-admission-and-controls.md).
Completed checkpoints are cloud-backed on the branch in
[PR #78](https://github.com/rookepoole/PooleOS/pull/78); merge to main still requires
the exact-candidate canonical, Doctor, release, publication and review gates.
Native kernel and demo ISO bytes are unchanged. This is pre-production evidence.
Corrected progress, architecture and checklist tests pass 62/62, no skips.

**Historical development checkpoint:** Cycle 214 qualifies the SMP scheduler on the
unchanged Cycle 210 kernel. Two four-vCPU boots and 19 focused tests pass,
including 326 corrupted records and 22 disabled native variants. Measured image
pins and an independent integer-type check are repaired. An initial source-binding
mistake and failed 13/18 regression remain recorded; the corrected suite passes.
Readiness is **23/27**. AP workers, SMP preemption, atomics and locks remain,
with at least 35 unproven control groups. Next: `N12-SCHED-AP-WORKERS-001`.
[Cycle 214 evidence](docs/checkpoints/cycle214-current-kernel-smp-scheduler-replay.md).
Branch backup in [PR #78](https://github.com/rookepoole/PooleOS/pull/78) is separate
from main qualification. Native kernel and demo ISO bytes are unchanged.
Progress, architecture and checklist tests pass 61/61 with no skips.

**Historical development checkpoint:** Cycle 213 qualifies scheduler, preemption
and deferred work on the unchanged Cycle 210 kernel. Six VM boots and 47 focused
tests pass, including 768 corrupted records and 19 disabled native variants.
Two measured image pins and an isolated integer-type check are repaired without
rewriting guest evidence. Selected readiness is **22/27**; five SMP scheduling,
atomic and lock profiles, at least 35 control groups and AP-worker recorded
admission remain. Next: `N12-SCHED-SMP-001`.
[Cycle 213 evidence](docs/checkpoints/cycle213-current-kernel-scheduler-replay.md).
Checkpoints are backed up on the branch in [PR #78](https://github.com/rookepoole/PooleOS/pull/78).
Main merge still requires full exact-candidate qualification. Native kernel and
demo ISO bytes are unchanged; this is not production qualification.
Corrected progress/architecture/checklist tests pass 60/60; three initial stale
progress assertions remain recorded as failures.

**Historical development checkpoint:** Cycle 212 qualifies memory, virtual memory,
interrupts, first-AP startup, per-CPU runtime and IPI on the unchanged Cycle 210
kernel. Twelve VM boots and all 93 focused tests pass. Ten obsolete accounting
and identity pins are reconciled from independent evidence; original admission
failures remain recorded. Selected readiness is **19/27**; eight scheduler,
atomic and lock profiles, at least 35 control groups and AP-worker recorded
admission remain open. The next move is `N12-SCHED-001`.
[Cycle 212 evidence](docs/checkpoints/cycle212-current-kernel-memory-and-multiprocessor-replay.md).
Development checkpoints are backed up through the branch in
[PR #78](https://github.com/rookepoole/PooleOS/pull/78); main merge requires the
full exact-candidate qualification suite. No native bytes, phase status or demo
ISO changes in this cycle. This is not production qualification.
Corrected progress/architecture/checklist tests pass 59/59; the initial stale
IPI assertion failure remains recorded.

**Historical development checkpoint:** Cycle 211 qualifies five CPU profiles on the
unchanged Cycle 210 kernel: 14 final VM runs, 225 controls and 55 focused tests
pass. Receipt admission now rejects 80 malformed nested-build cases without
exceptions and enforces an integer relocation count. Readiness is **13/27**;
14 downstream profiles and at least 35 control groups remain. Checkpoints are
saved on the development branch in [PR #78](https://github.com/rookepoole/PooleOS/pull/78).
Main merge still requires full exact-candidate qualification. No phase or flag
closes; the kernel and demo ISO are unchanged.
[Cycle 211 evidence](docs/checkpoints/cycle211-current-kernel-cpu-admission-and-replay.md).
Corrected metadata passes 58/58. The earlier combined run remains recorded as
248/249, with its stale metadata assertion repaired; no full-suite pass is claimed.

**Historical development checkpoint:** Cycle 210 fixes a real boot-layout failure:
the 148-page kernel collided with the old retained-stack guard. A 192-page
reservation, unmapped guards, NX permissions and before-write overflow rejection
now pass native boundary tests and six final VM boots, including two kernel entries.
The 97-test scoped regression passes without skips. Readiness is **8/27**;
19 downstream profiles and at least 35 control groups remain. Work is backed up
on the development branch; main merge requires full exact-candidate qualification.
No phase or flag closes, and the demo ISO is unchanged.
[Cycle 210 evidence](docs/checkpoints/cycle210-retained-map-growth-and-boot-replay.md).
Combined regression passes 212/212 with no skips, including 57 repaired metadata
tests. Counts overlap the focused tests; full canonical qualification is pending.

**Historical development checkpoint:** Cycle 209 repairs native AP-worker failure
atomicity, generation wrap and counter validation. Thirty native cases in each
of two host profiles and fifteen disabled-repair variants pass. Core qualification
passes all 17 stages; two clean kernel builds match, with 246 kernel tests and
43 hostile image controls passing. This is kernel implementation, not live-boot
qualification. Changed kernel bytes leave **3/27** selected checks current;
24 profiles require replay from symbols and the boot chain. The AP-worker flag
is reopened, no phase closes, and the demo ISO is unchanged.
[Cycle 209 evidence](docs/checkpoints/cycle209-native-ap-worker-transactions.md).
Combined scoped regression passes 117/117, zero skips, including 56 repaired
metadata tests. Counts overlap the focused tests; prior failures are preserved.
Full exact-candidate qualification still precedes main merge and production.

**Historical development checkpoint:** Cycle 208 repairs SMP evidence admission and
replaces sixteen constant-only reports with executed controls. Two final virtual
boots pass 303 cases, including 59 compiled-native boundary scenarios. All 18
focused tests pass: 326 corrupted records and eight independent gate cases reject;
thirteen disabled native safeguards and nine transaction-repair variants are caught.
Readiness is **23/27**. AP workers, SMP preemption, atomics and locks remain, with
at least 35 unproven control groups. Native kernel and demo ISO bytes are unchanged;
this is pre-production qualification, not a phase closure or main-merge approval.
[Cycle 208 evidence](docs/checkpoints/cycle208-smp-admission-and-controls.md).
Combined scoped regression passes 183/183 and repaired metadata 55/55, zero skips.
Counts overlap; the full exact-candidate merge qualification remains pending.

**Historical development checkpoint:** Cycle 207 qualifies cooperative scheduling,
BSP preemption and deferred work on unchanged kernel203. Six virtual boots,
83 control groups covering 595 executed cases and 47 focused tests pass. Tests
reject 768 recorded corruptions and eleven independent linked-identity mutations;
19 disabled native variants are detected. The stale deferred image-pin failure
is retained and corrected without rewriting guest evidence. Readiness is **22/27**;
five profiles and at least 51 later control groups remain from `N12-SCHED-SMP-001`.
No phase, flag, native byte, demo ISO or production status changes. Full
exact-candidate qualification still precedes main merge; branch backup is separate.
[Cycle 207 evidence](docs/checkpoints/cycle207-current-kernel-scheduler-replay.md).
Combined scoped regression passes 166/166, zero skips; repaired metadata passes
54/54 and conservation verifies 348 bindings and 19 unchanged archived records.
Counts overlap; full canonical qualification remains pending.

**Historical development checkpoint:** Cycle 206 qualifies six memory, interrupt
and multiprocessor profiles on unchanged kernel203. Twelve virtual boots,
421 control groups covering 1,137 cases and 93 focused tests pass. Tests reject
1,896 corrupted records, 360 raw-mailbox cases and seven independent IPI image
pins. The initial stale-pin admission failure is preserved and corrected.
Selected readiness is **19/27**; eight scheduler, atomic and lock profiles remain
from `N12-SCHED-001`, plus SMP recorded admission and at least 51 control groups.
No phase, flag, native byte, demo ISO or production status changes. Main merge
still requires full exact-candidate qualification; cloud branch backup is separate.
[Cycle 206 evidence](docs/checkpoints/cycle206-memory-and-multiprocessor-replay.md).
Combined scoped regression passes 283/283, zero skips; corrected metadata passes
53/53 and conservation verifies 347 bindings and 19 unchanged archived records.
Counts overlap; full canonical merge qualification remains pending.

**Historical development checkpoint:** Cycle 205 qualifies five CPU profiles on
unchanged kernel203. Fourteen virtual boots, 225 controls and 54 focused tests
pass; one expected TCG limitation probe is separate. Tests reject 3,398 corrupted
control records, 371 run-evidence cases and 26 aggregate identity/promotion cases.
Selected readiness is **13/27**; fourteen downstream profiles remain from
`N9-PMM-ACPI-CONSUMER-001`, plus at least 51 later scheduler control groups.
No phase, flag, native byte, demo ISO or production status changes. Main merge
still requires full exact-candidate qualification; cloud branch backup is separate.
[Cycle 205 evidence](docs/checkpoints/cycle205-current-kernel-cpu-replay.md).
Combined scoped regression passes 242/242 with zero skips; metadata passes
52/52 and conservation verifies 346 bindings and 19 unchanged archived records.
Counts overlap; these are not the full canonical merge gates.

**Historical development checkpoint:** Cycle 204 qualifies the boot chain on the
repaired Cycle 203 kernel. Six fresh virtual boots pass, including two kernel
entries ending in the expected unsigned-development denial. All 81 focused
tests pass, including 650 corrupted symbol records and 20 independent old-image
pin rejections. Selected readiness is **8/27**, with 19 profiles pending from
`N7-TRAP-001` and at least 51 later scheduler control groups still unproven.
Kernel bytes and the demo ISO are unchanged. This is pre-production, not full
canonical merge qualification or a phase closure.
[Cycle 204 evidence](docs/checkpoints/cycle204-current-kernel-boot-replay.md).
Combined scoped regression passes 188/188 with zero skips; conservation verifies
345 bindings and 19 unchanged archived progress records. Counts overlap.

**Historical development checkpoint:** Cycle 203 repairs native SMP scheduler
transactions so rejected acknowledgements, dispatch, cancellation, timeout and
retirement cannot partially change ownership or queues. Seven reproduced native
failures now pass; 19 native tests pass in debug and optimized profiles, and nine
disabled-repair variants are detected. All 17 core stages and two matching builds
pass. The kernel changed, so selected current-image readiness is **2/27**;
25 dependent profiles need replay from `N5-SYMBOLS-SEMANTICS-001`.
The SMP flag is reopened. Its recorded admission and 16 control groups remain
open within the 51-group lower bound. Earlier boots remain historical evidence.
No new ISO, new-kernel guest boot, phase closure or production promotion is claimed.
[Cycle 203 evidence](docs/checkpoints/cycle203-native-smp-transactions.md).
Combined scoped regression passes 109/109, zero skips; conservation verifies
344 source bindings and 18 unchanged archived progress records. This is not
full canonical merge qualification.
Development checkpoints are backed up on the branch in
[PR #78](https://github.com/rookepoole/PooleOS/pull/78); main merge still requires
full exact-candidate qualification. Branch backup does not require main merge.

**Historical development checkpoint:** Cycle 202 repairs deferred-work evidence
admission and replaces 14 unexecuted controls with actual native/source tests.
Two final virtual boots and all 17 focused tests pass, including 315 corrupted
records rejected and twelve disabled native variants detected. Selected readiness
is 22/27; five profiles and at least 51 later scheduler control groups remain.
Next: `N12-SCHED-SMP-001`. Kernel bytes and the demo ISO are unchanged.
[Cycle 202 evidence](docs/checkpoints/cycle202-deferred-admission-and-controls.md).
This is pre-production work, not full canonical merge qualification.
Combined scoped regression passes 144/144 with zero skips; repaired metadata
passes 49/49 and conservation verifies 338 source bindings. Counts overlap.

**Historical development checkpoint:** Cycle 201 qualifies native cooperative
scheduling and BSP timer/wakeup preemption on the unchanged Cycle 197 kernel.
Four fresh virtual boots, 53 control groups, 341 rejection cases and 31 focused
tests pass. The tests reject 453 malformed records and detect seven disabled
native preemption checks. Selected readiness is 21/27; six profiles remain.
Next is `N12-SCHED-DEFERRED-001`: repair deferred admission and executed-control
coverage before its replay. No phase, flag, new ISO or production promotion.
[Cycle 201 evidence](docs/checkpoints/cycle201-scheduler-and-preemption-replay.md).
Combined scoped regression passes 128 tests, zero skips; repaired metadata passes
48/48 and conservation passes. This is not full canonical merge qualification.

**Historical development checkpoint:** Cycle 200 qualifies six memory, interrupt and
multiprocessor profiles on the unchanged Cycle 197 kernel: twelve final virtual
boots, 421 control groups and 1,137 executed rejection cases. All 93 scoped tests
pass, including 1,896 malformed receipts and independent memory/IPI gate tests.
An old aggregate IPI image pin is repaired without rewriting guest evidence.
Selected readiness is 19/27; eight scheduler-through-lock profiles, deferred
evidence/control repairs and full exact-candidate merge qualification remain.
Next is `N12-SCHED-001`. No phase, new ISO or production promotion is claimed.
[Cycle 200 evidence](docs/checkpoints/cycle200-memory-and-multiprocessor-replay.md).
Combined scoped regression passes 327 tests with zero skips. Corrected metadata
passes 47/47; conservation verifies 17 archived parent records and 326 bindings.
These checks do not replace the full canonical merge qualification.

**Historical development checkpoint:** Cycle 199 repairs CPU control-record admission
and requalifies five N7 profiles on the unchanged Cycle 197 kernel. Fourteen final
virtual boots, 225 executed controls and 54 focused tests pass. All 3,398 malformed
control records and 371 paired-run corruptions reject through runtime and gate.
Selected readiness is 13/27; fourteen memory/IRQ/SMP/scheduler/atomic/lock profiles,
deferred evidence/control repairs and full exact-candidate qualification remain.
Next is `N9-PMM-ACPI-CONSUMER-001`. Development-branch backup is not main-merge
acceptance; no new ISO, phase completion or production readiness is claimed.
[Cycle 199 evidence and merge blockers](docs/checkpoints/cycle199-cpu-control-admission-and-replay.md).
Combined scoped regression passes 233 tests, zero skips. Initial metadata passes
46/46; conservation preserves 17 parent records and verifies 325 source bindings.

**Historical development checkpoint:** Cycle 198 repairs recorded symbol-evidence
admission and requalifies the boot chain on the repaired Cycle 197 kernel.
All 650 corrupted-record cases reject without validator exceptions. Six final
virtual boots pass, including two native kernel entries and the expected unsigned
development halt. All 80 focused Python tests pass. Selected readiness is 8/27;
19 CPU and downstream profiles, deferred evidence/control repairs and full
exact-candidate qualification still precede main merge. Cloud backup on the
development branch is separate from merge acceptance. No new ISO or production
readiness is claimed.
[Cycle 198 evidence and merge blockers](docs/checkpoints/cycle198-symbol-admission-and-boot-replay.md).
Combined scoped regression passes 178 tests, zero skips, including exact kernel
reproduction. Earlier evidence and owner/checklist/ISO conservation pass.

**Historical development checkpoint:** Cycle 197 repairs native deferred-work
transactions, fault-path priority accounting and shutdown ordering. Eleven
original native failures are repaired; 21 native tests pass in debug and optimized
builds, and four deliberately disabled fixes are detected. All 17 core stages,
two matching kernel builds and 54 scoped Python tests pass. Kernel bytes changed;
selected readiness is 3/27, requiring 24 dependency replays before full merge
qualification. Deferred receipt admission and 65 known control-execution gaps
remain open. The demo ISO is unchanged. No new-kernel guest boot is claimed.
[Cycle 197 evidence and replay order](docs/checkpoints/cycle197-native-deferred-transactions.md).

**Historical development checkpoint:** Cycle 196 replaces nine constant-only
preemption control groups with executed native-host and linked/source audit
checks. Two final guest boots, 246 kernel host tests, 226 rejection cases and
17 focused tests pass, including 232 corrupt receipts and seven disabled native
validator variants. Selected readiness is 21/27; six profiles, at least 65
remaining control-execution gaps and full exact-candidate qualification still
precede main merge. Native kernel bytes and the demo ISO are unchanged.
[Cycle 196 evidence and next steps](docs/checkpoints/cycle196-preemption-executed-controls.md).
Broader regression passes 339 tests with zero skips; this is not the full
canonical suite or production qualification.

**Historical development checkpoint:** Cycle 195 repairs scheduler recorded-evidence
admission. Two fresh guest boots, 115 rejection cases and 14 focused tests pass,
including 221 corrupted receipts. All 219 original audit counterexamples now
reject without validator exceptions. Roadmap 195 preserves prior results and
tracks 20/27 selected checks passing; seven profiles and at least 74 control-
execution gaps remain before full exact-candidate qualification and main merge.
The audit found nine additional constant-only preemption controls alongside
the previously known 65. Architecture binds 310 sources. No kernel or ISO changed.
[Cycle 195 evidence and next steps](docs/checkpoints/cycle195-scheduler-recorded-evidence.md).
The intermediate cloud-backup checkpoint remains immutable history. Combined
scoped regression passes 322 tests, zero skips; this is not a full qualification.

**Historical development checkpoint:** Cycle 194 requalifies physical memory,
virtual memory, interrupts/time, first AP and per-CPU runtime on the unchanged
Cycle 192 kernel. Ten fresh guest boots, 528 rejection cases in 388 groups and
57 focused regression tests pass. Selected readiness is 19/27; eight scheduler-
through-lock profiles and 65 scheduler control-execution gaps remain before
full exact-candidate qualification and main merge. No kernel bytes or ISO changed.
[Cycle 194 evidence and next steps](docs/checkpoints/cycle194-memory-runtime-replay.md).
Combined regression passes 307 tests, zero skips, including exact kernel-entry
reproduction. Roadmap/checklist regression passes 42/42; conservation passes.

**Historical development checkpoint:** Cycle 193 requalifies all five N7 profiles
against the Cycle 192 kernel: trap recovery/containment, CPU policy, xstate
ownership, xstate exceptions and read-only privilege/MSR policy. Fourteen fresh
guest boots, 225 rejection controls and 51 focused regression tests pass.
The selected readiness projection is now 14/27, with thirteen profiles pending
from physical memory onward. No kernel bytes or demo ISO changed this cycle.
The draft remains unqualified for main merge or production.
[Cycle 193 evidence and next steps](docs/checkpoints/cycle193-current-kernel-cpu-replay.md).
Combined regression passes 249 tests, zero skips; corrected roadmap/checklist
regression passes 41/41. The initial stale-count failure remains recorded.

**Historical development checkpoint:** Cycle 192 implements native `PKMBX1` saved
AP mailbox export and independent host validation. Two final four-vCPU IPI boots,
609 rejection cases and 57 focused regression tests pass, alongside boot-chain
replay. The changed kernel's selected projection is 9/27; 18 dependent profiles
still require qualification, starting with `N7-TRAP-001`. Roadmap 192 preserves
the prior evidence as history, with current CPU/VM status explicitly pending.
This is not a merge-qualified build, new ISO or release.
[Cycle 192 evidence and next steps](docs/checkpoints/cycle192-native-mailbox-oracle.md).
Both intermediate cloud-backup records remain unchanged.
Combined regression passes 189 tests, zero skips; reconciliation and conservation
pass. The initial three metadata-test failures remain recorded.

**Historical development checkpoint:** Cycle 191 repairs IPI recorded execution,
frame-address checksum validation and release-accounting control execution.
Two final four-vCPU boots, 249 rejection cases and all 31 focused tests pass;
528 corrupted records reject through runtime and actual gate. Selected readiness
is 19/27. Next is native AP mailbox export and independent host recomputation,
then affected-image replay, eight remaining profiles and full qualification.
Kernel/demo bytes are unchanged; the mailbox gap still blocks main merge.
[Cycle 191 evidence and next steps](docs/checkpoints/cycle191-ipi-recorded-evidence.md).
Combined scoped regression passes 314 tests, zero skipped; the initial two
historical-assertion failures are retained. Conservation passes. This remains
a pre-production development checkpoint, not a new ISO or release.

**Historical development checkpoint:** Cycle 190 repairs per-CPU recorded evidence,
dual-checksum validation and per-control case-count binding. Two final boots,
159 executed cases across 19 categories and all 10 focused tests pass. All 69
original corruptions now reject without validator exceptions. Selected readiness
is 18/27; nine profiles remain from IPI, followed by scheduler evidence and full
qualification before main merge. Kernel and demo bytes remain unchanged.
[Cycle 190 evidence and next steps](docs/checkpoints/cycle190-percpu-recorded-evidence.md).
Combined scoped regression passes 282 tests, zero skipped; checklist, history
and owner-data conservation pass. The checkpoint remains pre-production.

**Historical development checkpoint:** Cycle 189 repairs first-AP recorded evidence
while preserving independently validated timestamp/checksum variation. Two final
boots and 72 controls pass; all 12 focused tests pass, including 159 corrupt-record
and six malformed root/control cases through runtime and actual gate. Selected
readiness is 17/27; ten profiles remain from per-CPU runtime, followed by scheduler
evidence and full qualification before main merge. Kernel and demo bytes are unchanged.
[Cycle 189 evidence and next steps](docs/checkpoints/cycle189-first-ap-recorded-evidence.md).
Combined scoped regressions pass 271 tests with zero skips; checklist, history
and owner-data conservation pass. Development checkpoints are saved on
[`agent/n12-dispatch-execution-holds`](https://github.com/rookepoole/PooleOS/tree/agent/n12-dispatch-execution-holds)
under [draft PR #78](https://github.com/rookepoole/PooleOS/pull/78).
Cloud backup does not require merging unqualified work into `main`.

**Historical development checkpoint:** Cycle 188 repairs interrupt/time recorded
execution, typed accounting, calibration bounds and fail-closed malformed input.
Two final boots and 58 controls pass; all 12 focused tests pass, including 229
corrupt-record cases and six malformed root/control cases through runtime and
actual gate. Selected readiness is 16/27; eleven SMP-through-lock profiles plus
scheduler evidence and full qualification remain before main merge. Native kernel
and ISO bytes are unchanged; this remains pre-production qualification.
[Cycle 188 evidence and next steps](docs/checkpoints/cycle188-irq-recorded-evidence.md).
Combined scoped regressions pass 258 tests with zero skips; checklist, history
and owner-data conservation pass.

**Historical development checkpoint:** Cycle 187 repairs VM recorded execution and
sparse direct-map accounting admission. Two final virtual boots and 48 controls
pass; all 10 focused tests pass, including 115 malformed receipts rejected through
runtime and actual gate. Selected readiness is 15/27, with twelve profiles pending
from interrupt/time and further scheduler evidence/full qualification before main
merge. Kernel and ISO bytes are unchanged; this is pre-production qualification.
[Cycle 187 evidence and next steps](docs/checkpoints/cycle187-vm-recorded-evidence.md).
Combined scoped regressions pass 245 distinct methods; the initial historical
assertion failure and 16 repeated host-toolchain executions are documented.

**Historical development checkpoint:** Cycle 186 repairs PMM recorded execution and
ACPI/memory accounting admission. Two final virtual boots and 191 controls pass;
all 12 focused tests pass, including 234 corrupted receipts rejected through
runtime and actual gate. Selected readiness is 14/27; thirteen profiles remain
from virtual memory, plus scheduler evidence and full qualification before main
merge. Kernel bytes and the demo ISO are unchanged; this is pre-production.
[Cycle 186 evidence and next steps](docs/checkpoints/cycle186-pmm-recorded-evidence.md).
The combined scoped regression suite passes 234 tests, zero skipped; the
initial historical-record assertion failure remains documented.

**Historical development checkpoint:** Cycle 185 repairs CPU recorded-execution
validation and two malformed-input gate exceptions. Five profiles pass fourteen
final virtual boots and 225 marker controls on unchanged kernel bytes. All 50
focused tests pass, including 371 malformed-record cases through runtime and
actual gates. Selected readiness is 13/27; fourteen memory-through-lock replays
are next from `N9-PMM-ACPI-CONSUMER-001`. At least 65 scheduler evidence gaps and
full qualification still block a main merge. This is not a new kernel feature,
ISO or production release. Earlier failures and superseded boots are retained.
[Cycle 185 evidence and next steps](docs/checkpoints/cycle185-cpu-recorded-evidence.md).
The combined CPU/boot/progress closeout passes 221 tests with zero skips;
checklist, history, native products and owner-data conservation also pass.

**Historical development checkpoint:** Cycle 184 qualifies boot-chain host provenance.
Six qualifiers now verify isolated pinned host inputs, and eight generated
receipts pass current validation. All 109 focused tests pass; six final virtual
boots include two kernel entries. Kernel bytes remain unchanged. Selected
readiness is 8/27, with nineteen CPU/memory dependencies next from `N7-TRAP-001`.
At least 65 scheduler execution-evidence gaps and full qualification still block
a main merge. This is not a new ISO or a production-ready release.
[Cycle 184 evidence and next steps](docs/checkpoints/cycle184-boot-host-provenance.md).
The combined closeout passes 171 tests with zero skips; checklist, historical
evidence, source and product conservation also pass.

**Historical development checkpoint:** Cycle 183 completes shared-loader and entry
provenance qualification. Invalid loader receipts reject before output, and
entry inherits the loader's declared inputs. All 59 focused tests pass under
hostile environment overrides, including exact receipt reproduction; kernel
bytes are unchanged. The ELF gate passes, while 24 of 27 selected downstream
checks still need replay. The 65 scheduler execution-evidence gaps and full
qualification remain open. This is not a new ISO or a merge-qualified release.
[Cycle 183 evidence and next steps](docs/checkpoints/cycle183-elf-loader-provenance.md).

**Historical development checkpoint:** Cycle 182 repairs host build reproducibility.
Controlled builds isolate the drift to MSVC runtime libraries; pinned inputs and
shared environment sanitation restore exact entry and fixture reproduction.
All 39 focused hostile-environment regressions pass. Kernel bytes are unchanged;
24 dependent checks require replay under the new provenance, and 65 scheduler
control-evidence gaps remain. This is not a new ISO or merge-qualified release.
[Cycle 182 evidence and next steps](docs/checkpoints/cycle182-host-toolchain-repair.md).

**Historical checkpoint:** Cycle 181 replays fourteen memory-through-lock
profiles with 28 final virtual boots; 164 focused tests pass and two skip.
All 27 selected consistency checks pass, but at least 65 scheduler control
groups lack individually bound execution evidence. The September 26 closeout
also fails exact entry-receipt reproduction: 331 tests pass, one fails and two
skip. A preserved rebuild confirms identical kernel bytes; only a host probe's
recorded size differs. Progress ledgers now describe Cycle 181. Next resolve
`N6-KENTRY-001` reproduction, then scheduler control evidence and full
qualification. This remains a pre-production checkpoint, not merge-qualified.
[Cycle 181 status and resume order](docs/checkpoints/cycle181-memory-qualification.md).

**Last completed development checkpoint:** Cycle 180 qualifies five CPU profiles with
fourteen fresh virtual boots, 225 controls and 46 focused regression tests.
Positive tests now require untouched generated receipts. Selected readiness is
13/27; fourteen memory-through-lock profiles remain, beginning
`N9-PMM-ACPI-CONSUMER-001`. This is not a new ISO or a main-qualified release.
The combined CPU/boot/entry/progress closeout passes 174 tests.
[Cycle 180 evidence](docs/checkpoints/cycle180-cpu-qualification.md).

**Historical checkpoint:** Cycle 179 requalifies the six-component
native boot chain: six final virtual boots, two kernel entries, independent
nine-file revalidation and 71 passing Python tests. Invalid revalidation
receipts now reject before output. Eight of 27 selected checks pass;
nineteen CPU/memory profiles still need replay, beginning `N7-TRAP-001`.
This is pre-production development, not a new ISO or main-qualified release.
[Cycle 179 evidence](docs/checkpoints/cycle179-boot-chain-requalification.md).

**Development backup:** [draft PR #78](https://github.com/rookepoole/PooleOS/pull/78)
tracks Cycles 177 onward on
`agent/n12-dispatch-execution-holds`. Cycle 179's combined
closeout suite passed 128 tests. Source checkpoints on this branch are separate
from qualified `main`; private execution logs and media are not part of this backup.

**Historical checkpoint:** Cycle 178 requalifies the kernel entry:
two clean matching builds, 245 kernel tests, 43 rejection controls and complete
39-file kernel-source binding. Twelve entry-gate controls reject stale image
pins and wrong numeric types. Three of 27 selected checks pass; 24 downstream
profiles still need replay. Next is `N5-SYMBOLS-SEMANTICS-001`.
[Cycle 178 evidence and limitations](docs/checkpoints/cycle178-kernel-entry-requalification.md).

**Historical checkpoint:** Cycle 177 adds native dispatch execution
holds and two scheduler admission rollback fixes. All 17 core qualification
stages pass, but the changed kernel needs fresh entry and dependency replay:
only 2 of 27 selected readiness checks are current. This draft is not
merge-qualified. The roadmap separates current host evidence from historical
live receipts; the next qualification move is `N6-KENTRY-001`.
[Cycle 177 status and remaining work](docs/checkpoints/cycle177-dispatch-execution-holds.md).

**Historical checkpoint:** Cycle 175 qualifies fourteen memory-through-lock profiles:
28 final fresh virtual boots, 660 control groups and 2,126 rejected cases. All
27 selected native readiness checks pass. Embedded kernel-entry checks now reject
224 stale/malformed/type substitutions and 56 invalid dependencies; the combined
suite passes 161 tests with two optional skips. An SMP shape-handling regression
was fixed and replayed, with two earlier boots retained as superseded evidence.
Cycle 176 subsequently passed full canonical qualification and merged
[PR #77](https://github.com/rookepoole/PooleOS/pull/77).
No new live task-stack, frozen demo or production claim follows.
[Cycle 175 evidence and next move](docs/checkpoints/cycle175-memory-entry-provenance.md).

**Historical checkpoint:** Cycle 174 requalifies five native CPU profiles on
`agent/n12-task-stack-ownership`, tracked by [PR #77](https://github.com/rookepoole/PooleOS/pull/77).
Fourteen fresh virtual boots, 225 controls and 47 focused tests pass. Embedded
kernel-entry receipts must match current validated evidence with exact JSON types;
80 malformed/stale/type substitutions and 20 invalid dependency cases reject.
Selected readiness checks pass 24/27. Memory/SMP provenance replay and the full
audit remain pending; this draft is not merge-qualified. The canonical kernel
and frozen demo ISO are unchanged. No production claim follows.
[Cycle 174 evidence and next move](docs/checkpoints/cycle174-cpu-entry-provenance.md).
Cycle 173's entry and boot-chain replay remains preserved in its
[historical checkpoint](docs/checkpoints/cycle173-entry-provenance-replay.md).

Historical Cycle 171 pre-closeout evidence: memory-through-lock replay on the
unchanged Cycle 168 kernel, originally on `agent/n12-ap-execution-ownership`.
Twenty-eight final headless boots pass across fourteen profiles, with 660
negative-control groups and 2,126 rejected cases. SMP evidence now binds the
current boot artifacts and rejects stale or malformed transfer dependencies.
All 27 selected native checks pass. The 155-test profile/map/gate suite has
153 passes and two optional local-transcript skips. Four superseded boots
and all failing-then-passing regressions are preserved.
Full runtime-inclusive exact-final qualification and publication/review gates
subsequently passed; PR #76 records their exact-source receipt and verified merge.
That development qualification does not make PooleOS production-ready.
[Cycle 171 proof, failures and next move](docs/checkpoints/cycle171-native-dependency-replay.md).
[Prior CPU-state evidence](docs/checkpoints/cycle170-cpu-state-replay.md).
[Prior boot-chain evidence](docs/checkpoints/cycle169-boot-chain-replay.md).
[Prior AP ownership evidence](docs/checkpoints/cycle168-ap-ownership-qualification.md).

Historical Cycle 165 pre-merge summary: memory-through-lock dependency replay:
fourteen profiles, 28 final headless boots, 660 negative-control groups and
2,120 rejected cases. All 27 selected native checks pass. The 142-test profile
suite passes with two optional local-transcript skips. Full runtime-inclusive
qualification and publication/review gates were then pending for draft PR #75;
main then remained qualified Cycle 161. No native kernel, PooleGlyph or demo ISO bytes
change, and no phase or production gate closes.
[Cycle 165 checkpoint](docs/checkpoints/cycle165-native-dependency-replay.md).

Historical Cycle 164 completes current-kernel trap and CPU-state replay: five live
profiles pass fourteen headless boots, 225 marker controls and 41 focused
N7 tests. One expected TCG exception diagnostic is counted separately.
The selected native projection now passes 13/27; fourteen memory-through-lock
dependencies and full exact-final qualification remain pending before merging
draft PR #75. Main remains qualified Cycle 161. Kernel bytes, PooleGlyph and
the separate demo ISO are unchanged; PooleOS remains pre-production.
[Cycle 164 checkpoint](docs/checkpoints/cycle164-cpu-replay.md).

Historical Cycle 163 requalifies the current kernel's boot chain: six fresh virtual
boots include two PooleKernel entries that independently revalidate nine
retained files before the expected unsigned-policy halt. Seventy focused
tests pass, including repairs to two fixed-date receipt validators. All six
boot-chain gates pass; nineteen downstream dependencies still need replay,
starting with traps and CPU state. Main remains qualified Cycle 161 and
PR #75 remains draft. Kernel bytes and the separate demo ISO are unchanged;
PooleOS remains pre-production.
[Cycle 163 checkpoint](docs/checkpoints/cycle163-boot-chain-replay.md).

Historical Cycle 162 adds mandatory ownership of active page tables and data frames.
The kernel rejects copied-handle frees and keeps pages retained when cleanup
fails. The larger image's guarded boot mapping is updated and independently
checked. 228 kernel tests and two fresh headless VM boots pass; the live path
observes six retained-free rejections. Other changed-image dependencies still
need replay before merging; the candidate audit is failed at 81/105 gates.
Main holds the qualified Cycle 161 checkpoint merged through
[PR #74](https://github.com/rookepoole/PooleOS/pull/74);
the demo ISO is unchanged. PooleOS remains pre-production.
[Cycle 162 checkpoint](docs/checkpoints/cycle162-active-root-retention.md).

Historical Cycle 161 completes qualification of the mandatory native task-retention
checkpoint: 28 final memory/SMP/scheduler/lock virtual boots and 2,118 negative
cases pass. All 26 selected native checks and the pre-closeout canonical suite
pass, including 105 consistency gates and 708 Doctor checks. Scheduler receipts
now validate real calendar dates instead of one fixed day. Subsequent exact-final
qualification and publication/review checks passed, and PR #74 merged as
`a4c3c27`. Active-root ownership is developed in Cycle 162; execution-stack
ownership remains open. The separate
demo ISO is unchanged; PooleOS remains pre-production.
[Checkpoint details](docs/checkpoints/cycle161-qualified-checkpoints.md).

Historical Cycle 160 completes current-kernel trap, CPU, x87/SSE and read-only MSR replay:
fourteen fresh virtual boots, 225 marker controls and 41 focused tests pass.
The CPU receipt validator now rejects missing and contradictory recorded
evidence. All twelve selected boot-chain/N7 checks pass; fourteen downstream
memory/SMP/scheduler/lock checks and the full candidate suite remain pending.
Physical-memory qualification is next. Source is backed up in draft PR #74;
main and the frozen demo ISO remain unchanged. PooleOS is pre-production.
[Checkpoint details](docs/checkpoints/cycle160-cpu-evidence.md).

Historical Cycle 159 requalifies the updated kernel's boot chain: six fresh headless
virtual boots include two actual PooleKernel entries and independent checking
of all nine retained files. All six selected boot-chain gates and 68 focused
tests pass. Nineteen downstream native checks and the full qualification replay
remain pending, starting with N7 traps. The latest full audit is still the
preserved failed Cycle 158 result, not a new aggregate pass. Source checkpoints
are on GitHub with draft PR #74; the demo ISO is unchanged and PooleOS remains
pre-production. [Checkpoint details](docs/checkpoints/cycle159-cloud-backup.md).

Historical Cycle 158 makes physical-page retention mandatory for inactive scheduler-task
page tables and bound data frames, including aliases and pending unmaps.
Group failure preserves every resource for retry. The bounded host harness
covers 24 lifetime tests, 19 pool tests, 219 kernel tests and seven compile-fail
checks. Active roots, execution stacks and live CPU retirement remain open.
The new kernel requires fresh dependency qualification before merging; main
already contains the qualified Cycles 153-157 checkpoint through PR #73.
The separate demo ISO is unchanged. PooleOS remains pre-production.
The full new-candidate audit fails 25/105 checks because downstream receipts
are stale and the aggregate suite is not passing; 29 focused Python tests pass.

Historical Cycle 157 completes current-kernel interrupt, SMP, scheduler, atomic and lock
replay: twelve refreshed profiles, 24 final virtual boots and 1,881 negative
cases pass. All 26 selected native dependency gates pass. Invalid IRQ/SMP
receipts now produce failed checks instead of error-formatting exceptions.
The canonical suite passes all 105 gates and 708 Doctor checks, including the
917-test suite. The bounded N12.2 lock milestone closes again; N12.3 resource
ownership remains next. Checkpoints are backed up on GitHub's
`agent/n12-physical-retention` branch, with main merge subject to exact final
qualification and publication/review checks. Native kernel bytes, the separate
demo ISO and production status are unchanged.

Historical Cycle 156 requalifies the allocator, ACPI memory reclamation and sparse virtual
memory for the retention-capable kernel. The manager contract now matches its
measured 15,632-byte layout, with regressions rejecting the old size. Four final
virtual boots and 237 negative controls pass; independent accounting confirms
the larger kernel protects one additional page. Kernel bytes and the demo ISO
are unchanged. Interrupts and SMP are next, followed by scheduler/lock replay
and the full candidate gate. This is pre-production memory qualification, not
a new desktop or a production release.

Cycle 155 replays the current kernel's exception, CPU, x87/SSE and MSR profiles:
fourteen fresh virtual boots, 225 marker controls and 41 focused Python tests
pass. Trap receipts now reject missing runs, duplicated scenarios and altered
results; broader receipt review is explicitly flagged. All twelve selected
boot-chain/N7 gates pass, but fourteen memory/SMP/scheduler/lock checks still
need current-source replay. PMM ownership and layout reconstruction is next.
Main and the demo ISO remain unchanged; this is pre-production development,
not a full candidate gate pass or a new kernel feature.

Cycle 154 requalifies the native boot chain for the unmerged kernel candidate.
Symbol identities now match measured executable/debug bytes, and policy
readiness rejects stale canonical dependency vectors. Fresh loader and
PooleBoot runs pass, followed by two real PooleKernel entries that reparse all
nine retained files and halt at the expected unsigned-policy boundary. All six
boot-chain gates and 63 focused regressions pass. Downstream CPU, memory, SMP,
scheduler and lock replay plus the full candidate gate remain required. Main,
the demo ISO and production status are unchanged.

Cycle 153 is an unmerged [physical-retention candidate](docs/native-kernel-physical-retention.md).
The allocator rejects copied-handle frees for explicitly retained pages, and
the three-AP teardown now waits for stop acknowledgement and final parking
before releasing old frames. Host ownership/lifetime tests and two fresh
four-CPU boots pass after a one-page kernel/layout expansion. Qualification also
found and repaired stale-counter ticket admission; its lock milestone is
reopened pending full current-source dependency replay. Cycle 152 remains the
last main baseline with a passing aggregate gate. The demo ISO is unchanged;
no production or current-candidate aggregate pass is claimed.

Cycle 152 adds [PKLIFE1 task lifetimes](docs/native-kernel-task-lifetimes.md):
the real scheduler now has an optional native controller that retains moved
inactive address spaces and task payloads until retirement and final reader
release. It prevents premature task-slot reuse and handles cancellation,
pending dispatch, timeout and shutdown. Nineteen new lifetime tests pass in
both host profiles, alongside the pool suite and 206 kernel regressions.
This controller is not wired into a guest selector yet. Active-root ownership
and acknowledged cross-CPU reclamation are next. The existing demo stays frozen.

Cycle 150 adds the [PKRECLAIM1 object-lifetime core](docs/native-kernel-reclamation-core.md)
to PooleKernel: generation-bound handles, reader pins, deferred reclamation,
exact-once payload transfer and shutdown retention. Nineteen tests pass in
each of two host profiles plus 206 kernel regressions and freestanding checks.
The linked boot kernel remains byte-identical to Cycle 149. Scheduler and
cross-CPU integration are next; N12.3 and production remain open.
All 24 dependent native qualification profiles were rerun against the updated
source. Their emulator evidence does not establish live use of the new core.

## Native Architecture Contract

Linux, Debian, Buildroot, GRUB, Limine, and systemd are not production foundations or release-media dependencies. QEMU, OVMF, EDK II, Windows, WSL, Linux, and Buildroot may be used only as development tools, references, compatibility environments, or historical evidence.

The production chain is:

```text
x86-64 UEFI firmware
-> signed PooleBoot.efi
-> verified PooleKernel plus initial-system and recovery bundles
-> PooleKernel capability microkernel
-> isolated native servers and user-space driver domains
-> native application, PooleGlyph/PGB2/PGVM2, and PDC services
-> PooleGlass compositor and desktop
-> reproducible signed PooleOS ISO
```

The ring-0 boundary is defined in `specs/pooleos-kernel-charter.md`. General device drivers, filesystems, networking, graphics, audio, PGVM2, PDC, package management, authentication policy, and desktop behavior stay outside the kernel TCB. Production loadable kernel modules are prohibited in v1.

## Authoritative Plan

- `docs/production-goal-charter.md`: completion contract and per-turn next-best-move protocol.
- `docs/pdc-production-build-plan.md`: comprehensive native build plan with 40 phases and 301 explicit subphases.
- `runs/pdc_production_roadmap.json`: schema-validated machine roadmap, dependencies, status, evidence, gaps, and flags.
- `runs/pooleos_native_checklist_coverage.json`: exact line and section mapping from the locked master checklist to N0-N39.
- `docs/adr/`: seven-record native architecture constitution and required ADR template.
- `runs/native_architecture_baseline.json`: deterministic byte binding for the ADRs, constitution, plan, policy, checklist, license, and repository identity.
- `specs/native-v1-objectives.json`, `docs/native-v1-objectives.md`, and `runs/native_v1_objectives_readiness.json`: 38 measurable owner-directed v1 definitions, zero measurements, cryptographic-signature boundary, and ten fail-closed controls.
- `specs/adr-ratification-policy.json`, `docs/adr-ratification-ceremony.md`, and `runs/adr_ratification_readiness.json`: secret-free owner-signing contract binding six exact decision sources and 38 objective definitions, explicit zero-measurement boundary, and deterministic custody-pending ledger. `security/governance-key-registration.json` binds the owner-confirmed ED25519-SK public key to GitHub signing-key registration 1158225; no private material is included.
- `docs/n0-owner-decision-packet.md`, `specs/n0-owner-decision-packet.schema.json`, and `runs/n0_owner_decision_packet.json`: byte-frozen 16-source historical owner review surface retaining every original selection as `UNSELECTED` and 12 fail-closed packet controls.
- `specs/n0-owner-response.json`, `runs/n0_owner_response_receipt.json`, and `docs/n0-owner-response-receipt.md`: deterministic historical response binding, 2/2 ADR and 38/38 definition dispositions, selected unavailable FIDO2 profile, 16 fail-closed controls, and the exact zero key/signing/merge/tag/publication authority recorded when that receipt was created; current conditional execution authority is separately recorded in the Goal Charter.
- `specs/native-toolchain-lock.json`, `specs/native-target-contract.json`, and `runs/native_toolchain_qualification.json`: exact Rust inputs, freestanding target contracts, and bounded one-host PE32+/ELF64 evidence.
- `docs/native-toolchain-qualification.md`: reproduction procedure, exact fixture hashes, discovered PE nondeterminism, and open gates.
- `specs/hardware-support-policy.json`, `specs/tier1-hardware-target.json`, and `specs/native-standards-register.json`: hardware support tiers, exact Tier 1 identity, evidence/safety gates, and primary-source standards metadata.
- `tools/collect_tier1_hardware.ps1`, `runs/tier1_hardware_observation.json`, `runs/hardware_target_readiness.json`, and `docs/hardware-target-and-lab-safety.md`: bounded user-mode CPUID collection, sanitized host observation, deterministic N2 readiness ledger, privacy boundary, and safe capture procedure.
- `specs/native-tier0-lock.json`, `specs/native-tier0-profile.json`, and `runs/native_tier0_readiness.json`: exact QEMU/OVMF supply-chain lock, versioned Q35/TCG/VIRTIO profile, paused machine probes, and fail-closed N4 readiness evidence.
- `docs/native-tier0-qemu.md`, `tools/qualify_native_tier0.py`, and `tools/run_native_tier0.py`: isolated acquisition/qualification procedure and a dry-run-first native-media launcher with no arbitrary QEMU argument channel.
- `specs/native-model-toolchain-lock.json`, `specs/native-model-contract.json`, and `runs/native_model_readiness.json`: exact TLC/Java lock, finite N4 model contract, complete safe-state checks, required hostile counterexamples, normalized traces, and explicit non-promotion boundary.
- `models/tla/`, `docs/native-formal-models.md`, `tools/bootstrap_native_models.ps1`, and `tools/qualify_native_models.py`: bounded boot-slot rollback, capability derivation/revocation, virtual-memory ownership/map/unmap/shootdown, IPC, scheduler, and PooleFS transaction/recovery models plus workspace-local deterministic reproduction.
- `specs/native-pooleboot-proof.json`, `runs/native_pooleboot_readiness.json`, `docs/native-pooleboot-proof.md`, and `tools/qualify_native_pooleboot.py`: bounded unsigned PooleBoot PE32+ aggregate proof, deterministic twelve-file GPT/FAT32 development media, two exact pinned OVMF runs, twenty-five ordered serial/debugcon markers, exact retained-page PINIT1/PREC1/PSYM1/PMCU1/PFWM1/PPOL1/PSM1/PBTP1/PBTS1 parsing, PBTRUST1 policy/state cross-binding and unsigned-policy denial, retained PKMAP2/PBLIVE4/PBEXIT1 evidence with one ACPI2 RSDP firmware-table record and ten loaded-artifact descriptors, static GOP-frame evidence, 155 hostile controls, zero authority/action/state/hardware effects, and explicit authentication/live-PooleKernel-revalidation/kernel-activation-or-consumption/kernel-entry/target-firmware/N5 nonclaims.
- `specs/native-boot-handoff-contract.json`, `native/handoff`, `native/livehandoff`, `runtime/native_boot_handoff.py`, `runtime/native_live_boot_handoff.py`, and `runs/native_boot_handoff_readiness.json`: candidate PBP1 firmware-to-kernel bytes, dependency-free `no_std` codec and live builder, independent synthetic and transcript oracles, golden vectors, hostile controls, final-map-bound post-exit development production, and non-promoting differential evidence.
- `specs/native-boot-config-contract.json`, `native/bootcfg`, `runtime/native_boot_config.py`, `docs/native-boot-config.md`, and `runs/native_boot_config_readiness.json`: candidate PBC1 boot grammar, allocation-free `no_std` parser, PooleBoot compile-time integration, independent oracle, 64 hostile controls, and explicit live-filesystem/N5 nonclaims.
- `specs/native-elf-loader-contract.json`, `native/elf`, `runtime/native_elf_loader.py`, `docs/native-elf-loader.md`, and `runs/native_elf_loader_readiness.json`: candidate PKELF1 ELF64 `ET_DYN` profile, allocation-free `no_std` loader, independent oracle, exact loaded bytes, 129 hostile controls, and explicit firmware-allocation/paging/transfer nonclaims.
- `specs/native-kernel-entry-contract.json`, `native/kernel`, `runtime/native_kernel_image.py`, `docs/native-kernel-entry.md`, and `runs/native_kernel_entry_readiness.json`: real 517,784-byte canonical PKELF1 PooleKernel product in a 589,824-byte, 144-page image, fixed `0xA000` entry, page-aligned `0x71000` text and `0x7E000` RELRO/data boundaries, PKENTRY1 handoff intake, bounded early diagnostics and panic classes, 214 host tests, exact two-build reproduction, 43 hostile controls, 1,304 relocations, and canonical SHA-256 `BDEECCB27B1B91406911F91169B9BF5F9DF0439BB39FA0E1882C07E1AF3B81EF`; live bounded subsystem slices are qualified separately through PKLOCK1.
- `specs/native-system-manifest-contract.json`, `specs/native-boot-digest-provider.json`, `native/manifest`, `runtime/native_system_manifest.py`, `docs/native-system-manifest.md`, and `runs/native_system_manifest_readiness.json`: canonical PSM1 grammar and artifact bindings, PBDIGEST1 vendored SHA-256 provider boundary, independent oracle, 64 hostile controls, 16,384 differential cases, 1,027 digest cases, and explicit unsigned/security-review nonclaims.
- `specs/native-initial-system-contract.json`, `native/initsys`, `runtime/native_initial_system.py`, `docs/native-initial-system-bundle.md`, and `runs/native_initial_system_readiness.json`: canonical PINIT1 initial-system declarations, allocation-free `no_std` parser, independent host oracle, dependency/capability/resource/lifecycle validation, unsigned activation denial, 120 hostile controls, 16,384 differential cases, and explicit no-authority/no-execution nonclaims.
- `specs/native-recovery-contract.json`, `native/recovery`, `runtime/native_recovery.py`, `docs/native-recovery-bundle.md`, and `runs/native_recovery_readiness.json`: canonical PREC1 immutable recovery policy and separate mutable state, allocation-free `no_std` parser/transition engine, independent host oracle, exact A/B eligibility and decrement-before-handoff behavior, known-good fallback, bounded safe/recovery routing, authenticated receipt and physical-presence rules, unsigned activation denial, 144 hostile controls, 16,384 parser/state plus 8,192 transition differential cases, and explicit no-state-I/O/no-authority/no-execution nonclaims.
- `specs/native-symbol-contract.json`, `native/symbols`, `runtime/native_symbols.py`, `docs/native-symbol-bundle.md`, and `runs/native_symbol_readiness.json`: canonical PSYM1 public-only image-relative diagnostic index, exact stripped/loaded/build/debug/source identity, allocation-free `no_std` parser and bounded lookup, independent host/debug-ELF oracle, split-debug correspondence, pointer-redaction and source-path privacy rules, 158 hostile controls, 16,384 parser plus 16,384 lookup differential cases, and explicit no-consumption/no-export/no-authority nonclaims.
- `specs/native-microcode-contract.json`, `native/microcode`, `runtime/native_microcode.py`, `docs/native-microcode-bundle.md`, and `runs/native_microcode_readiness.json`: canonical synthetic-only PMCU1 package wrapper, exact AMD CPU identity, opaque payload and metadata digests, revision/floor and reset-known-good selection, BSP/AP apply prerequisites, mixed-revision and post-apply checks, allocation-free `no_std` implementation, independent oracle, 174 hostile controls, 40,960 differential cases, and explicit no-vendor-validation/no-privileged-observation/no-update nonclaims.
- `specs/native-firmware-contract.json`, `native/firmware`, `runtime/native_firmware.py`, `docs/native-firmware-manifest.md`, and `runs/native_firmware_readiness.json`: canonical synthetic-only PFWM1 manifest for three external-payload components and two dependencies, exact hardware/version/signer/updater/recovery identities, one-transaction topological order, 47 dry-run prerequisites, post-reset receipt checks, allocation-free `no_std` implementation, independent oracle, 101 hostile controls, 32,768 differential cases, and explicit no-payload/no-live-inventory/no-driver/no-apply nonclaims.
- `specs/native-policy-contract.json`, `native/policy`, `runtime/native_policy.py`, `docs/native-policy-bundle.md`, and `runs/native_policy_readiness.json`: canonical qualification-only PPOL1 policy with six exact modes, eleven PINIT1-cross-bound capability rules, default-deny authority intersection, monotonic attenuation, safe/recovery floors, firmware physical-presence separation, durable decision receipts, allocation-free `no_std` implementation, independent oracle, 116 hostile controls, 32,768 differential cases, and explicit no-live-enforcement/no-authority/no-PooleGlyph-execution nonclaims.
- `specs/native-boot-trust-contract.json`, `native/trust`, `runtime/native_boot_trust.py`, `docs/native-boot-trust.md`, and `runs/native_boot_trust_readiness.json`: PBTRUST1 separate 320-byte immutable-policy and 256-byte mutable acceptance-state records plus the PBSTATE1 pure authenticated-anchor/two-copy backend model; allocation-free `no_std` and independent Python validation; 12/12 Rust tests; 105 hostile controls; 32,768 differential cases; nine interrupted-transition recovery cases; live fourteen-binding unsigned-policy denial; zero cryptography, backend I/O, key/signature/authority/write effects; and no persistent-backend or production claim.
- `docs/native-initial-system-profile.md`, `native/artifact`, `native/inner`, `native/trust`, `runtime/native_boot_artifact.py`, `runtime/native_inner_live.py`, `runtime/native_boot_trust.py`, `specs/native-kernel-load-contract.json`, `native/bootload`, `native/boot/src/exit.rs`, `native/bootexit`, `runtime/native_kernel_load.py`, `docs/native-kernel-load.md`, and `runs/native_kernel_load_readiness.json`: PKLOAD6 live UEFI PBC1/PSM1/PKELF1/PBART1/PBTP1/PBTS1 intake, transactional zero-padded load/cleanup, exact retention of PSM1, six PBART1 files, PBTP1, and PBTS1, six-format retained-page parsing, PBTRUST1 cross-binding and exact unsigned-policy denial, retained PKMAP2 file/root/36-page guarded-stack/handoff ranges, final five-record PBLIVE4 with one ACPI2 RSDP and ten loaded-artifact descriptors, bounded PBEXIT1, successful `ExitBootServices`, exact guest/oracle agreement, 155 hostile controls, and explicit unsigned/no-authority/no-state-I/O/no-live-PooleKernel-activation/stop-before-transfer nonclaims.
- `specs/native-kernel-revalidation-contract.json`, `native/kernel/src/revalidation.rs`, `native/kernel/src/bin/pkreval1_probe.rs`, `runtime/native_kernel_revalidation.py`, `tools/qualify_native_kernel_revalidation.py`, `docs/native-kernel-revalidation.md`, and `runs/native-kernel-revalidation-readiness.json`: PKREVAL1 allocation-free `no_std` PooleKernel reparse of exact retained PSM1, six PBART1 inner files, PBTP1, and PBTS1; manifest/payload/route/trust binding reconstruction; loader-summary substitution and post-load mutation rejection; 196 kernel Rust tests; 8 Python tests; 36 hostile controls; 32,768 deterministic mutation rejects; exact unsigned-policy denial; zero authority/actions/writes; and explicit standalone-execution nonclaims.
- `specs/native-kernel-transfer-contract.json`, `native/boot/src/exit.rs`, `native/bootexit`, `native/kernel`, `runtime/native_kernel_transfer.py`, `tools/qualify_native_kernel_transfer.py`, `docs/native-kernel-transfer.md`, and `runs/native-kernel-transfer-readiness.json`: PKXFER1 opt-in QEMU-only one-way development transfer with the default stop path preserved; retained CR3 and guarded RSP installation; IF/DF clearing; exact SysV register intake; live nine-file PKREVAL1; two exact fresh-vars QEMU/OVMF runs; 30 ordered markers; exact serial/debugcon/PBP1 agreement; 58 hostile controls; terminal unsigned denial; and zero signature, authority, action, state-write, or post-exit-firmware effects.
- `specs/native-kernel-trap-contract.json`, `native/kernel/src/arch/x86_64.rs`, `runtime/native_kernel_trap.py`, `tools/qualify_native_kernel_trap.py`, `docs/native-kernel-trap.md`, and `runs/native-kernel-trap-readiness.json`: PKTRAP1 BSP-only QEMU descriptor/exception milestone with a five-entry GDT, TSS, 256-entry IDT allocation and five present gates, distinct bounded IST arrays, uniform 176-byte integer frames, three returning deliberate exceptions, terminal double-fault containment, semantic malformed-frame rejection, six exact runs, 51 hostile controls, and explicit per-CPU/all-vector/guarded-stack/NMI/machine-check/production nonclaims.
- `specs/native-kernel-cpu-policy-contract.json`, `native/kernel/src/arch/x86_64.rs`, `runtime/native_kernel_cpu_policy.py`, `tools/qualify_native_kernel_cpu_policy.py`, `docs/native-kernel-cpu-policy.md`, and `runs/native-kernel-cpu-policy-readiness.json`: PKCPU1 BSP-only qemu64 read-only CPUID/control/XCR0/APIC/PAT/MTRR policy milestone with independent Rust/Python validation, two exact QEMU/OVMF runs, 35 ordered markers, 41 hostile controls, five MSR reads, zero MSR/control writes, zero authority/actions, and explicit target-family/errata/xstate/AP-local/target-hardware/production nonclaims.
- `specs/native-kernel-errata-policy-contract.json`, `native/cpupolicy`, `runtime/native_kernel_errata_policy.py`, `tools/qualify_native_kernel_errata_policy.py`, `docs/native-kernel-errata-policy.md`, and `runs/native-kernel-errata-policy-readiness.json`: PKERR1 exact Ryzen 7 9800X3D identity, mandatory-feature, board-lineage, stable BIOS/AGESA, microcode-evidence, direct-source-applicability, and RDSEED rejection policy with independent `no_std` Rust/Python evaluators, 128 vectors, 24 hostile controls, exact six-reason current denial, zero privileged reads/effects, and explicit applicable-errata-guide and numeric-microcode-floor stop-ship gaps.
- `specs/native-kernel-xstate-policy-contract.json`, `native/kernel/src/xstate.rs`, `runtime/native_kernel_xstate_policy.py`, `tools/qualify_native_kernel_xstate_policy.py`, `docs/native-kernel-xstate-policy.md`, and `runs/native-kernel-xstate-policy-readiness.json`: PKXSTATE1 bounded one-BSP eager standard-format x87/SSE ownership with exact XCR0/XSS, canonical initialization, isolated owner round trips, sensitive-image clearing, fail-closed switch preconditions, kernel-SIMD prohibition, 31 kernel tests, two exact QEMU/OVMF runs, 43 hostile controls, and explicit scheduler/SMP/target/production nonclaims.
- `specs/native-kernel-xstate-exception-contract.json`, `native/kernel/src/xstate_exception.rs`, `runtime/native_kernel_xstate_exception.py`, `tools/qualify_native_kernel_xstate_exception.py`, `docs/native-kernel-xstate-exception.md`, and `runs/native-kernel-xstate-exception-readiness.json`: PKXEXC1 bounded one-BSP deliberate x87 `#MF` and SIMD `#XM` delivery with exact recovery and resume, terminal test-only `#NM` eager-policy rejection, one expected TCG non-delivery diagnostic, two exact WHPX QEMU/OVMF runs, 41 markers, 43 hostile controls, and a hash-bound LLVM linked-image machine-code audit with explicit scheduler/user-task/SMP/target/production nonclaims.
- `specs/native-kernel-privilege-msr-policy-contract.json`, `native/kernel/src/privilege_msr.rs`, `runtime/native_kernel_privilege_msr_policy.py`, `tools/qualify_native_kernel_privilege_msr_policy.py`, `docs/native-kernel-privilege-msr-policy.md`, and `runs/native-kernel-privilege-msr-policy-readiness.json`: PKMSR1 bounded one-BSP qemu64 read-only system-linkage, FS/GS, support-gated TSC_AUX, global MCA, and PMU policy with two exact TCG QEMU/OVMF runs, 35 markers, 47 hostile controls, eleven live MSR reads, zero runtime writes, and a hash-bound 43-`RDMSR`/three-`WRMSR` linked-image scope audit that isolates PKSMP1, PKSMP2, selector 14, PKSCHED1, PKSCHED2, PKSCHED3, and PKIRQ1 sites from the read-only PKMSR1 profile.
- `specs/native-kernel-physical-memory-contract.json`, `native/kernel/src/acpi.rs`, `native/kernel/src/physical_memory.rs`, `runtime/native_kernel_physical_memory.py`, `tools/qualify_native_kernel_physical_memory.py`, `docs/native-kernel-physical-memory.md`, and `runs/native-kernel-physical-memory-readiness.json`: PKPMM7 bounded one-BSP live PBP1 ownership plus PKACPI1 RSDP/XSDT/APIC/FACP/HPET/MCFG validation, retained scrubbed snapshot, opaque release evidence, separate Boot Services/ACPI reclaim receipts, and the generation-bound PKVM3 ownership manifest. Automatic 4/8/15/29-page ledger growth, rollback/retry headroom, three predecessor retirements, soft fallback, hard pre-effect rejection, snapshot copy/readback, malformed-table denial, idempotence, retained exclusions, and 196 kernel host tests pass. The current two-run profile consumes 98 PBP1 entries, admits 117,823 source-usable pages, manages 129,083 pages, protects 921 loader pages, emits 45 markers per run, and passes 191 hostile controls with explicit no-AML/no-interrupt-context/no-concurrency/no-SMP/no-target/no-production boundaries.
- `specs/native-kernel-virtual-memory-contract.json`, `native/kernel/src/active_virtual_memory.rs`, `runtime/native_kernel_virtual_memory.py`, `tools/qualify_native_kernel_virtual_memory.py`, `docs/native-kernel-virtual-memory.md`, and `runs/native-kernel-virtual-memory-readiness.json`: PKVM3 bounded one-BSP active-root profile derives a generation-owned sparse write-back direct map from the complete PMM manifest. It installs 117,822 supervisor RW/NX pages across eleven ranges using 243 contiguous DMA32 table pages, leaves 12,943 gap pages absent, preserves the exact inherited 36-page guarded-stack layout, rejects retained holes and PWT/PCD drift, proves transactional write and CR3 rollback, and gates reuse with three local invalidation receipts plus one exact generation-retirement receipt. Two exact 40-marker QEMU runs, 46 hostile controls, and the 196-test kernel suite pass with explicit no-general-shootdown/no-ring-3/no-heap/no-pager/no-production boundaries. PKVM1 and PKVM2 remain predecessor foundations.
- `specs/native-kernel-interrupt-time-contract.json`, `native/kernel/src/interrupt_time.rs`, `runtime/native_kernel_interrupt_time.py`, `tools/qualify_native_kernel_interrupt_time.py`, `docs/native-kernel-interrupt-time.md`, and `runs/native-kernel-interrupt-time-readiness.json`: PKIRQ1 bounded one-BSP xAPIC/HPET profile walks retained MADT/HPET data, reserves 51 vectors, uses three MMIO guards and two transient uncacheable leaves, masks/restores the legacy PIC, calibrates checked one-shot time, delivers exactly eight timer interrupts and EOIs, restores normal-path state, and passes two exact 36-marker QEMU runs plus 58 hostile controls without AP, IPI, I/O-APIC, MSI, target, or production claims.
- `specs/native-kernel-smp-first-ap-contract.json`, `native/kernel/src/smp.rs`, `native/kernel/src/arch/x86_64.rs`, `runtime/native_kernel_smp_first_ap.py`, `tools/qualify_native_kernel_smp_first_ap.py`, `docs/native-kernel-smp-first-ap.md`, and `runs/native-kernel-smp-first-ap-readiness.json`: PKSMP1 bounded two-vCPU qemu64 profile starts exactly one AP through a guarded below-1-MiB RX trampoline/mailbox transaction, observes required long-mode state, commands stop, validates quiescence and dynamic checksum, final-INIT parks the AP, revokes aliases, scrubs and releases fourteen pages, and passes two exact 38-marker runs plus 72 hostile controls without general-SMP, IPI, shootdown, target, N8-exit, or production claims.
- `specs/native-kernel-smp-percpu-runtime-contract.json`, `native/kernel/src/smp_runtime.rs`, `runtime/native_kernel_smp_percpu_runtime.py`, `tools/qualify_native_kernel_smp_percpu_runtime.py`, `docs/native-kernel-smp-percpu-runtime.md`, and `runs/native-kernel-smp-percpu-runtime-readiness.json`: PKSMP2 adds one processor-local AP runtime with an AP-owned GDT/TSS/IDT, guarded RSP0/IST stacks, x87/SSE owner state, and 27 hardware-verified gates. Its 32-page transaction passes two exact 42-marker runs, 19 hostile-control categories covering 159 rejected cases, and exact 131,072-byte scrub/release without IPI, shootdown, scheduler, target, N8-exit, or production claims.
- `specs/native-kernel-smp-ipi-contract.json`, `native/kernel/src/smp_ipi.rs`, `runtime/native_kernel_smp_ipi.py`, `tools/qualify_native_kernel_smp_ipi.py`, `docs/native-kernel-smp-ipi.md`, and `runs/native-kernel-smp-ipi-readiness.json`: PKSMP5 runs three private AP runtimes on one exact four-vCPU `SandyBridge,-avx` topology. Dynamic local masks `0x2/0x4/0x8`, aggregate target/ack mask `0xE`, one APIC-4 partial-start timeout, complete park/scrub/release rollback, fresh retry, three one-page remote invalidations, acknowledgement-gated retirement, and final cleanup pass. Two exact 40-marker runs observe nine accepted and three denied deliveries, twelve EOIs, three invalidations, one retirement, and exact release of 102 pages or 417,792 bytes; 30 hostile-control categories cover 243 rejected cases and 196 kernel host tests pass. This is not general topology or general shootdown, and no arbitrary callback, production capability, scheduler, target, N8/N9-exit, or production claim is made.
- `specs/native-kernel-scheduler-contract.json`, `native/kernel/src/scheduler.rs`, `native/kernel/src/bin/pksched1_probe.rs`, `runtime/native_kernel_scheduler.py`, `tools/qualify_native_kernel_scheduler.py`, `docs/native-kernel-scheduler.md`, and `runs/native-kernel-scheduler-readiness.json`: PKSCHED1 adds a bounded allocation-free four-CPU/eight-task scheduler core with generation-safe identities, deterministic fixed-priority run queues, affinity and modeled migration, exact wake/cancel/timeout/teardown behavior, selected synchronization and lifetime primitives, a 4,096-step Rust/Python oracle campaign, and an exact live 18-instruction cooperative BSP switch over two isolated 16-KiB stacks. Fourteen scheduler tests within 196 kernel tests, two exact 17-marker qemu64 runs, and 28 hostile-control categories covering 115 rejected cases pass. PKSCHED2 and PKSCHED3 separately add bounded BSP preemption and deferred workers; live AP dispatch, ring 3, address-space switching, full per-task architectural state, target qualification, N12 exit, and production remain open.
- `specs/native-kernel-scheduler-preemption-contract.json`, `native/kernel/src/scheduler_preempt.rs`, `native/kernel/src/bin/pksched2_probe.rs`, `runtime/native_kernel_scheduler_preempt.py`, `tools/qualify_native_kernel_scheduler_preempt.py`, `docs/native-kernel-scheduler-preemption.md`, and `runs/native-kernel-scheduler-preemption-readiness.json`: PKSCHED2 composes PKSCHED1 and PKIRQ1 through an allocation-free bounded event controller and exact interrupt frames. Two exact selector-16 qemu64 BSP runs reproduce six timer windows, task trace `0,1,2,0,3,3`, quantum/wakeup/block causes, six saves, four restores, six EOIs, four switches, one entry per task, zero pending events, four task retirements, MMIO rollback, and 65,536 cleared stack bytes; 7 focused tests within 196 kernel tests and 25 hostile-control categories covering 178 rejected cases pass without live AP, ring 3, address-space, target, N12-exit, or production claims.
- `specs/native-kernel-scheduler-deferred-contract.json`, `native/kernel/src/scheduler_deferred.rs`, `native/kernel/src/bin/pksched3_probe.rs`, `runtime/native_kernel_scheduler_deferred.py`, `tools/qualify_native_kernel_scheduler_deferred.py`, `docs/native-kernel-scheduler-deferred.md`, and `runs/native-kernel-scheduler-deferred-readiness.json`: PKSCHED3 adds an allocation-free eight-slot deferred-work controller with generation-safe IDs, typed operations, duplicate suppression, EOI-gated dispatch, bounded priority bypass, queued and running cancellation, flush watermarks, five fault rollback boundaries, exact shutdown, and two private BSP worker stacks inside retained bootstrap memory. Two exact selector-17 qemu64 runs dispatch six jobs over twelve hardware context transitions, complete five and cancel three, scrub all 32,768 worker-stack bytes, and pass 30 hostile-control categories covering 208 rejected cases. Arbitrary callbacks, driver/service consumers, AP dispatch and migration, ring 3, address spaces, target hardware, N12 exit, and production remain open.
- `specs/native-kernel-scheduler-smp-contract.json`, `native/kernel/src/scheduler_smp.rs`, `native/kernel/src/bin/pksched4_probe.rs`, `runtime/native_kernel_scheduler_smp.py`, `tools/qualify_native_kernel_scheduler_smp.py`, `docs/native-kernel-scheduler-smp.md`, and `runs/native-kernel-scheduler-smp-readiness.json`: PKSCHED4 adds an allocation-free exact-topology four-CPU/eight-task scheduler over PKSMP5. One cross-CPU wake, two migrations, and six AP-local dispatches commit behind exact acknowledgements; one APIC-4 timeout rolls back without ownership loss; late and stale-generation acknowledgements are rejected; all tasks retire; and all 102 AP runtime/frame pages or 417,792 bytes are scrubbed, verified, and released. Eight focused tests within 196 kernel tests, five exact Rust/Python receipts, two exact 37-marker four-vCPU boots, and 32 hostile-control categories covering 209 rejects pass. General topology/hotplug/x2APIC, general SMP preemption, AP-local deferred workers and driver/service consumers, arbitrary callbacks, ring 3, address-space/full architectural switching, target hardware, N12 exit, and production remain open.
- `specs/native-kernel-scheduler-ap-workers-contract.json`, `native/kernel/src/scheduler_ap_workers.rs`, `native/kernel/src/bin/pksched5_probe.rs`, `runtime/native_kernel_scheduler_ap_workers.py`, `tools/qualify_native_kernel_scheduler_ap_workers.py`, `docs/native-kernel-scheduler-ap-workers.md`, and `runs/native-kernel-scheduler-ap-workers-readiness.json`: PKSCHED5 adds three allocation-free AP-local workers and fixed typed timer-driver and generation-reclaim consumers on the exact PKSCHED4 topology. Thirteen enqueues, twelve typed AP calls, EOI-gated dispatch, queued and remote cancellation, one offline timeout rollback, flush-before-reclaim, bounded priority bypass, three worker retirements, and exact 102-page cleanup pass 10 focused tests within 196 kernel tests, six Rust/Python receipts, two exact 37-marker four-vCPU boots, and 34 hostile-control categories covering 226 rejects. Arbitrary callbacks, a general driver/service framework, general topology or SMP preemption, ring 3, address spaces, target hardware, N12 exit, and production remain open.
- `specs/native-kernel-scheduler-smp-preempt-contract.json`, `native/kernel/src/scheduler_smp_preempt.rs`, `native/kernel/src/bin/pksched6_probe.rs`, `runtime/native_kernel_scheduler_smp_preempt.py`, `tools/qualify_native_kernel_scheduler_smp_preempt.py`, `docs/native-kernel-scheduler-smp-preempt.md`, and `runs/native-kernel-scheduler-smp-preempt-readiness.json`: PKSCHED6 composes bounded timer/wakeup semantics with exact-topology scheduler and AP-worker ownership. Four timer/event/frame/run-queue lanes, deterministic cancel/wake/migration ordering, eight live acknowledgement-gated reschedule IPIs, three quantum switches, one offline rollback, watchdog/fairness bounds, eight task retirements, and exact 102-page cleanup pass 5 focused tests within 196 kernel tests, seven Rust/Python receipts, two exact 38-marker four-vCPU boots, and 34 hostile-control categories covering 232 rejects. AP-local timer interrupts, general SMP/topology, ring 3, address spaces, target hardware, N12 exit, and production remain open.
- `specs/native-kernel-atomics-contract.json`, `native/kernel/src/atomics.rs`, `native/kernel/src/bin/pkatom1_probe.rs`, `runtime/native_kernel_atomics.py`, `tools/qualify_native_kernel_atomics.py`, `docs/native-kernel-atomics.md`, and `runs/native-kernel-atomics-readiness.json`: PKATOM1 freezes allocation-free typed `u32`, `u64`, `usize`, and pointer atomics with operation-specific order types, nine accepted and eleven rejected compare-exchange order pairs, overflow-safe reference counts, 4,096 release/acquire publication rounds, 20,480 contended RMW/CAS operations, 2,048 sequential-consistency rounds, eight exact Rust/Python host receipts, seven linked x86-64 instruction audits, two exact selector-21 41-marker BSP-interrupt boots, and 29 hostile-control categories. This completes N12.1 only for the exact x86-64 scope; general locks, live multi-AP atomic contention, deferred reclamation, non-x86 portability, target hardware, N12 exit, and production remain open.
- `specs/native-kernel-locks-contract.json`, `native/kernel/src/locks.rs`, `native/kernel/src/bin/pklock1_probe.rs`, `runtime/native_kernel_locks.py`, `tools/qualify_native_kernel_locks.py`, `docs/native-kernel-locks.md`, and `runs/native-kernel-locks-readiness.json`: PKLOCK1 freezes an allocation-free FIFO ticket/IRQ-save/sleeping-mutex/notification/writer-preferred-reader-writer/seqlock family, five-rank lock-order graph, direct bounded priority donation, seven-bypass fairness, owner-death and rollback rules, nine host receipts with 8,192 ticket acquisitions, two exact selector-22 35-marker four-vCPU boots, and 30 hostile-control categories covering 103 rejected mutations. This completes N12.2 only for the bounded x86-64 scope; deferred reclamation and ABA-safe lifetime, general SMP, target hardware, N12 exit, and production remain open.
- `specs/native-kernel-map-contract.json`, `native/kmap`, `runtime/native_kernel_map.py`, `docs/native-kernel-map.md`, and `tests/test_native_kernel_map.py`: PKMAP2 exact 144-page supervisor 4 KiB kernel mapping across two retained leaf tables, 36-page guarded stack, read-only handoff, one temporary leaf, five retained supervisor RW/NX manager leaves, two alternate guarded 32-page PMM ledger windows, and a guarded five-page IRQ MMIO reservation ending at global leaf 517, with CR0.WP/NX/W^X enforcement, active-root audit, framebuffer translation/cache preservation, exact CR3 restoration, complete nine-file retained coverage, and retained/no-transfer boundaries.
- `specs/native-boot-exit-contract.json`, `native/bootexit`, `runtime/native_boot_exit.py`, `docs/native-boot-exit.md`, and `tests/test_native_boot_exit.py`: PBEXIT1 final-map/current-key ordering, bounded stale-key retry, post-attempt restrictions, zero post-exit firmware calls, and permanent pre-transfer-stop contract.
- `specs/native-release-architecture-policy.json`: extracted-release conformance policy with executable negative tests.
- `docs/publication-boundary.md`: public source-available and private evidence-vault boundary.
- `specs/pdc-production-roadmap.schema.json`: roadmap validation contract.
- `specs/pooleos-native-checklist-coverage.schema.json`: checklist-coverage validation contract.

The locked source checklist has SHA-256 `A8C94719FAF9428C1F133010BA2603C0270C4E1EFD7327AF8EAB9C8C362ABB3D`, 10,512 lines, 171 numbered sections, 8,998 checkbox lines, and 8,996 implementation items after its two generated-metadata checkboxes are excluded. Every source line and requirement is mapped; mapping does not imply completion.

Current engineering baseline remains Cycle 149: 40 phases remain non-complete. `FLAG-N12-CONCURRENCY-LOCKS-001` is closed and N12.2 is complete only for PKLOCK1's bounded allocation-free lock family, context/rank rules, direct priority donation, fairness, owner death, rollback, host contention, and one exact four-vCPU live ticket-lock profile. Deferred reclamation and ABA-safe lifetime, AP-local timer interrupt delivery, arbitrary callbacks, a general driver/service framework, general topology/hotplug/x2APIC, general SMP preemption, ring 3, address-space and full per-task architectural switching, target hardware, N12 exit, and production remain open, so `production_ready=false`. After Cycle 149, the owner-present hardware-key enrollment and owner-confirmed public-key registration completed on 2026-09-04. `N0-GOVERNANCE-CUSTODY-001` is now the immediate external move: verify an enrollment signature and the separately controlled recovery signer. No real governance signature, firmware mutation, physical-media write, tag, release, or production promotion occurred during registration. `N12-CONCURRENCY-RECLAMATION-001` remains the next owner-independent kernel move.

## Validation

Rooke Poole merged the governance registration in PR #68 (`4ade40f`). That
source passed 707 Doctor checks, the 105-check consistency gate, and the public
boundary scan; the full PooleGlyph stack passed separately. Independent
recovery remains unprovisioned, with no alternate recovery profile accepted.
This is pre-production qualification, not a signature or release.

```powershell
python .\tools\generate_native_checklist_coverage.py
python .\tools\generate_native_v1_objectives_readiness.py
python .\tools\verify_native_v1_objectives.py
python .\tools\generate_adr_ratification_readiness.py
python .\tools\generate_n0_owner_decision_packet.py
python .\tools\generate_n0_owner_response_receipt.py
python .\tools\sanitize_tier1_hardware_capture.py --capture .\runs\tier1_hardware_capture.private.json --out .\runs\tier1_hardware_observation.json
python .\tools\generate_hardware_target_readiness.py
python .\tools\verify_hardware_target.py
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\bootstrap_native_toolchain.ps1
python .\tools\qualify_native_toolchain.py
python .\tools\qualify_native_tier0.py
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\bootstrap_native_models.ps1
python .\tools\qualify_native_models.py
python .\tools\qualify_native_boot_handoff.py
python .\tools\generate_native_boot_config_vectors.py
python .\tools\qualify_native_boot_config.py
python .\tools\generate_native_elf_loader_vectors.py --check
python .\tools\qualify_native_elf_loader.py
python .\tools\qualify_native_kernel_entry.py --artifact-out .\outputs\PooleKernel.pkelf
python .\tools\generate_native_system_manifest_vectors.py --check
python .\tools\qualify_native_system_manifest.py
python .\tools\generate_native_initial_system_vectors.py --check
python .\tools\qualify_native_initial_system.py
python .\tools\generate_native_recovery_vectors.py --check
python .\tools\qualify_native_recovery.py
python .\tools\generate_native_symbol_vectors.py --check
python .\tools\qualify_native_symbols.py
python .\tools\generate_native_microcode_vectors.py --check
python .\tools\qualify_native_microcode.py
python .\tools\generate_native_firmware_vectors.py --check
python .\tools\qualify_native_firmware.py
python .\tools\generate_native_policy_vectors.py --check
python .\tools\qualify_native_policy.py
python .\tools\qualify_native_boot_trust.py
python .\tools\qualify_native_kernel_load.py
python .\tools\qualify_native_kernel_revalidation.py
python .\tools\qualify_native_kernel_transfer.py
python .\tools\qualify_native_kernel_trap.py
python .\tools\qualify_native_kernel_cpu_policy.py
python .\tools\qualify_native_kernel_errata_policy.py
python .\tools\qualify_native_kernel_xstate_policy.py
python .\tools\qualify_native_kernel_xstate_exception.py
python .\tools\qualify_native_kernel_privilege_msr_policy.py
python .\tools\qualify_native_kernel_physical_memory.py
python .\tools\qualify_native_kernel_virtual_memory.py
python .\tools\qualify_native_kernel_interrupt_time.py
python .\tools\qualify_native_kernel_smp_first_ap.py
python .\tools\qualify_native_kernel_smp_percpu_runtime.py
python .\tools\qualify_native_kernel_smp_ipi.py
python .\tools\qualify_native_kernel_scheduler.py
python .\tools\qualify_native_kernel_scheduler_preempt.py
python .\tools\qualify_native_kernel_scheduler_deferred.py
python .\tools\qualify_native_kernel_scheduler_smp.py
python .\tools\qualify_native_kernel_scheduler_ap_workers.py
python .\tools\qualify_native_kernel_scheduler_smp_preempt.py
python .\tools\qualify_native_kernel_atomics.py
python .\tools\qualify_native_kernel_locks.py
python .\tools\qualify_native_pooleboot.py
python .\tools\generate_native_production_roadmap.py
python .\tools\generate_native_architecture_baseline.py
python -m unittest discover -s tests
python .\tools\check_publication_boundary.py
python .\tools\pooleos_doctor.py --pooleglyph <POOLEGYPH_REPO>
```

The generators and qualifiers are deterministic: tests reproduce the checklist, roadmap, architecture baseline, objectives-readiness, governance receipts, native toolchain, hardware/Tier 0/model evidence, native PooleBoot, PBP1/PBC1/PSM1/PBART1 and all six inner formats, PBTRUST1/PBSTATE1, PKELF1, PKENTRY1, PKLOAD6/PBLIVE4/PKMAP2/PBEXIT1, PKREVAL1, PKXFER1, PKTRAP1, PKCPU1, PKERR1, PKXSTATE1, PKXEXC1, PKMSR1, PKPMM7, PKACPI1, PKVM1, PKVM2, PKVM3, PKIRQ1, PKSMP1, PKSMP2, PKSMP5, PKSCHED1 through PKSCHED6, PKATOM1, and PKLOCK1 ledgers byte for byte. Cycle 149 collects 902 Python tests and carries 206 kernel host tests plus 291 aggregate PKLOAD6 Rust tests. Source-bound readiness writers and `bootstrap_native_toolchain.ps1` are explicitly LF-canonical before dependent hashes are captured. Doctor runs the full PooleGlyph stack from a temporary source mirror while preserving its generated reports and run log. The roadmap inventories 102 canonical evidence artifacts; the exact 105-check non-promoting consistency-gate invocation evaluates 62 explicit/default artifact paths and keeps `production_ready=false`.

The public repository currently carries source, specifications, tests, and explicitly allowlisted deterministic ledgers. The historical N0 packet retains every field unselected, and the owner-response ledger contains no public key, private key, signature, credential, or secret. The sanitized hardware observation excludes raw firmware bytes, raw CPUID registers, device identifiers, user paths, and TPM material. Native model, boot, protocol, parser, loader, kernel-entry, live-load, revalidation, and transfer ledgers publish only relative bindings, bounded results, hashes, and claim limits; local product bytes, QEMU/OVMF runtime, generated media, screenshots, raw logs, and operational metadata remain ignored. The separately recorded, explicitly authorized public-key registration contains only the governance public key, fingerprint, and sanitized registration metadata. Real governance signing remains pending custody verification; registration does not ratify ADRs or promote production. Raw internal PDC inputs, private benchmarks, historical images, uncleared firmware, secrets, and private signing material remain in the ignored private evidence vault.

## Current PDC Evidence

The Cycle 74-79 PDC chain is valid reference evidence and is carried into N32-N33. It does not prove native-kernel or production-backend execution.

## PDC Math Reference

Cycle 74 adds the first source-bound executable PDC contract:

- `runs/pdc_source_intake.json`: seven verified content-addressed authorities plus a nonpromoting raw-candidate index.
- `specs/pdc-math-contract-v0.1.md` and `runs/pdc_math_contract.json`: axes, flattening, periodic boundaries, matrices, channels, numerical bounds, hashes, variants, and claim boundaries.
- `runtime/pdc_reference.py`: independent scalar-stencil and dense Kronecker-matrix oracles.
- `runs/pdc_golden_vectors.json`: binary, wraparound, planar, rectangle, line, PMphi, cuboid, and shell vectors.

Regenerate and validate the chain:

```powershell
python .\tools\emit_pdc_source_intake.py --out .\runs\pdc_source_intake.json
python .\tools\emit_pdc_math_contract.py --source-intake .\runs\pdc_source_intake.json --out .\runs\pdc_math_contract.json
python .\tools\emit_pdc_golden_vectors.py --math-contract .\runs\pdc_math_contract.json --out .\runs\pdc_golden_vectors.json
python .\tools\validate_artifact.py --schema .\specs\pdc-golden-vectors.schema.json .\runs\pdc_golden_vectors.json
```

The dense matrices are bounded specification oracles, not production routes. The raw package index is inventory, not imported or reproduced benchmark evidence.

## PDC Exact Verifier Reproduction

Cycle 75 imports four canonical verifier sources into `sources/pdc/verifiers/sha256/`, verifies 46/46 embedded manifest entries, and preserves six source-run CSVs under `runs/pdc_verifier_source_outputs/`. `runtime/pdc_verifier_reproduction.py` independently checks the declared 841 rectangle, 80 line-hole, 720 arbitrary-mask, 1,225 inversion, 729 cuboid, and 729 shell cases against `PDC-MATH-0.1`; all 4,324 cases pass with zero semantic mismatch.

```powershell
python .\tools\emit_pdc_verifier_intake.py --out .\runs\pdc_verifier_intake.json
python .\tools\emit_pdc_verifier_reproduction.py --verifier-intake .\runs\pdc_verifier_intake.json --math-contract .\runs\pdc_math_contract.json --out .\runs\pdc_verifier_reproduction.json
python .\tools\validate_artifact.py --schema .\specs\pdc-verifier-intake.schema.json .\runs\pdc_verifier_intake.json
python .\tools\validate_artifact.py --schema .\specs\pdc-verifier-reproduction.schema.json .\runs\pdc_verifier_reproduction.json
```

The source runners emitted CRLF CSVs on Windows while the published files use LF. Typed rows and canonical LF hashes match for all six outputs; raw byte equality is intentionally not claimed. These are exact finite-domain verifier results, not all-size theorems or production backend evidence.

## PDC Representation ABI

Cycle 76 freezes `PDC-REP-0.1` over dense binary, sorted sparse binary, LSB-first bit-packed binary, finite IEEE-754 probability fields, and checked native-buffer snapshots. Ten directed conversion paths bind shape, axes, dtype, byte/bit order, offset, padded strides, ownership provenance, mutability provenance, checked `u64` span arithmetic, and representation-specific storage hashes without changing `PDC-MATH-0.1` semantics.

```powershell
python .\tools\emit_pdc_representation_contract.py --out .\runs\pdc_representation_contract.json
python .\tools\emit_pdc_representation_receipt.py --representation-contract .\runs\pdc_representation_contract.json --out .\runs\pdc_representation_receipt.json
python .\tools\validate_artifact.py --schema .\specs\pdc-representation-contract.schema.json .\runs\pdc_representation_contract.json
python .\tools\validate_artifact.py --schema .\specs\pdc-representation-receipt.schema.json .\runs\pdc_representation_receipt.json
```

The receipt tests 10 lattice-bearing golden cases and all 3,099 representation-applicable exact fields through four round trips each, repeats the applicable PDC result, and passes 13 fail-closed malformed-input checks. Three golden formula records and 1,225 inversion formula rows have no lattice payload; they remain explicitly excluded and digest-bound rather than being described as converted fields. Native storage is snapshotted reference evidence: actual C pointers, mutable outputs, device buffers, and kernel validation remain later gates.

## PDC Boundary and Metamorphic Corpus

Cycle 77 adds `PDC-GOLDEN-0.2` without replacing the original Cycle 74 vectors. It publishes all 54 binary state/support pairs, eight empty/full/singleton/wrap/padding fixtures, 32 periodic translations, 40 joint axis/shape permutations, and six explicit non-relations. The receipt executes 206 direct/scalar/matrix field evaluations and 824 representation round trips with zero mismatch.

```powershell
python .\tools\emit_pdc_golden_metamorphic_corpus.py --out .\runs\pdc_golden_metamorphic_corpus.json
python .\tools\emit_pdc_golden_metamorphic_receipt.py --corpus .\runs\pdc_golden_metamorphic_corpus.json --out .\runs\pdc_golden_metamorphic_receipt.json
python .\tools\validate_artifact.py --schema .\specs\pdc-golden-metamorphic-corpus.schema.json .\runs\pdc_golden_metamorphic_corpus.json
python .\tools\validate_artifact.py --schema .\specs\pdc-golden-metamorphic-receipt.schema.json .\runs\pdc_golden_metamorphic_receipt.json
```

Complement, shape reinterpretation, PMphi-as-storage, nonperiodic translation, 2D-as-A26, and fractional-probability-as-binary are explicitly rejected or excluded. This closes the supported periodic P1 reference gate; it does not qualify native C, optimized routes, kernels, UI, or boot media.

## PDC Q/P Probability and Typed Channels

Cycle 78 freezes `PDC-QP-0.1`. Distinct tagged APIs prevent feature vectors, probability values, typed gate/cardinality readouts, geometry spectra, and collapsed one-bit state from being interchanged. The receipt checks fixed-order dynamic programming against independent polynomial and bounded brute-force oracles, verifies center and neighbor derivatives, and recomputes all 42 imported gate, identity/not, half-adder, full-adder, and cardinality cases instead of trusting embedded pass markers.

```powershell
python .\tools\emit_pdc_qp_contract.py --out .\runs\pdc_qp_contract.json
python .\tools\emit_pdc_qp_receipt.py --contract .\runs\pdc_qp_contract.json --out .\runs\pdc_qp_receipt.json
python .\tools\validate_artifact.py --schema .\specs\pdc-qp-contract.schema.json .\runs\pdc_qp_contract.json
python .\tools\validate_artifact.py --schema .\specs\pdc-qp-receipt.schema.json .\runs\pdc_qp_receipt.json
```

All 54 feature thresholds, 10 full probability cases, 12 brute-force cases, 270 DP/polynomial checks, 260 derivative-oracle checks, 104 finite-difference checks, 42 typed cases, and 16 negative checks pass with zero mismatch. The v5.5 field benchmark, perturbation stability, and PooleGlyph/PGB2 typed exposure remain open; this is classical measured-field evidence, not quantum-state reconstruction.

## Native Kernel Principle

Native implementation proceeds from a frozen architecture and executable models into the smallest bootable TCB, then moves policy and drivers into capability-confined user space:

```text
signed architecture ADRs and clean-room boundary
-> hermetic x86-64 UEFI toolchain and QEMU/OVMF profile
-> PooleBoot and frozen boot protocol
-> PooleKernel entry, memory, interrupts, SMP, and diagnostics
-> ring 3, syscalls, IPC, capabilities, and IOMMU confinement
-> isolated VIRTIO reference drivers and native system services
-> PooleGlyph/PGB2/PGVM2 and PDC services
-> PooleGlass, installer, recovery, signed reproducible ISO
```

## Historical Cycle 1-79 Artifacts

The remaining lab commands and artifacts below preserve the Cycle 1-79 PGB2, PDC, Buildroot/QEMU, and capability-simulator evidence. They are useful regression and provenance inputs but are **non-promoting** for native PooleOS. A Buildroot image, Linux rootfs, fixture boot marker, or simulated capability proof cannot satisfy any PooleBoot or PooleKernel release gate.

- `specs/pooleos-kernel-charter.md`: kernel-level invariants and production-readiness gates.
- `specs/claim-lanes.schema.json`: machine-readable claim-lane record shape.
- `specs/channel-trace.schema.json`: JSON artifact shape for typed channel telemetry.
- `specs/pgb2-bundle.schema.json`: sectioned JSON bundle for PGB1-compatible code plus PooleOS trace/provenance sections.
- `specs/signed-membrane.schema.json`: benchmark-lane signed membrane metric artifact.
- `specs/replay-proof.schema.json`: deterministic replay proof record for a bundle and declared reference case.
- `specs/isolation-proof.schema.json`: static microkernel region/capability proof artifact.
- `specs/boot-trap-bundle-manifest.schema.json`: lab boot-readiness manifest for trap-bearing PGB2 bundle inputs.
- `specs/qemu-shared-folder-contract.schema.json`: host-side QEMU shared-folder staging contract.
- `specs/lab-guest-autostart.schema.json`: guest init-time mount and smoke autostart evidence.
- `specs/qemu-boot-evidence.schema.json`: QEMU serial boot evidence with fixture versus captured-source provenance.
- `specs/qemu-captured-boot-preflight.schema.json`: non-mutating preflight for real captured QEMU boot launches.
- `specs/qemu-captured-boot-launch-bundle.schema.json`: operator-facing command bundle for a real captured QEMU boot.
- `specs/qemu-captured-boot-dry-run-checklist.schema.json`: operator dry-run checklist and receipt template for captured QEMU boot handoff.
- `specs/qemu-boot-marker-contract.schema.json`: marker-to-emitter responsibility contract for the QEMU trap-input boot path.
- `specs/qemu-boot-marker-image-binding.schema.json`: hashes marker emitters and Buildroot scaffold files for the QEMU trap-input boot path.
- `specs/rootfs-content-manifest.schema.json`: compares bound marker/support files against a built and extracted rootfs tree.
- `specs/rootfs-extraction-handoff.schema.json`: operator-reviewed WSL/Linux read-only rootfs extraction command plan.
- `specs/rootfs-extraction-receipt.schema.json`: operator receipt that gates captured-QEMU promotion on verified rootfs continuity.
- `specs/qemu-captured-boot-receipt.schema.json`: receipt that keeps fixture and captured QEMU boot evidence in separate handoff slots.
- `specs/qemu-captured-boot-readiness.schema.json`: reconciles verified rootfs, captured boot receipt, and captured evidence before promotion language.
- `specs/buildroot-build.schema.json`: WSL-gated Buildroot image build report that binds the planned rootfs image path before captured-boot promotion.
- `specs/kernel-boot-handoff.schema.json`: ties captured readiness to guest loader output without claiming kernel/PGVM2 enforcement.
- `specs/kernel-pgvm2-loader-output.schema.json`: defines the booted kernel loader output slot and current non-claiming negative fixture.
- `specs/lab-kernel-transcript-export-receipt.schema.json`: records whether the lab transcript contract ran and whether the exported transcript was accepted without over-claiming.
- `specs/kernel-pgvm2-loader-evidence.schema.json`: records the kernel-owned PGVM2 loader checks and parser-promotion receipt gate without claiming enforcement before booted output exists.
- `tools/verify_kernel_pgvm2_loader_transcript.py`: converts a complete booted-kernel transcript into `kernel_pgvm2_loader_output.json`.
- `lab-os/buildroot/.../pooleos-kernel-pgvm2-transcript-contract`: disabled lab-side transcript emitter contract for future kernel loader output.
- `specs/capability-trap-proof.schema.json`: PGB2-style region/capability trap proof artifact.
- `specs/capability-trap-fuzz.schema.json`: deterministic closed-by-default trap fuzz evidence.
- `specs/pgb2-trap-encoding.schema.json`: draft byte encoding evidence for capability trap operations.
- `specs/pgb2-trap-execution.schema.json`: byte-level simulator evidence for draft PGB2 trap programs.
- `specs/pgb2-trap-abi-boundary-receipt.schema.json`: release-gated receipt that keeps draft trap bytes separate from a frozen kernel ABI.
- `specs/pooleglyph-source-anchor.schema.json`: live PooleGlyph source/checkpoint anchor artifact.
- `specs/pooleglyph-bridge-manifest.schema.json`: PooleGlyph v0.5-dev metadata bridge surface for PooleOS artifact lanes.
- `specs/pooleglyph-core-ir-boundary-receipt.schema.json`: distinguishes metadata-only PooleGlyph declarations from public Core IR executable candidates before parser-to-kernel promotion.
- `specs/pooleglyph-core-ir-executable-audit.schema.json`: audits executable Core IR candidates separately from metadata-only zero-program outputs before permission/trap promotion.
- `specs/pooleglyph-parser-kernel-promotion-receipt.schema.json`: release-gated parser-to-kernel receipt that remains blocked until Phase 66 evidence permits handoff.
- `docs/pooleglyph-checkpoint-deep-inspection.md`: refreshed Phase 65 PooleGlyph checkpoint inspection and PooleOS integration boundary.
- `specs/permission-capability-matrix.schema.json`: PooleGlyph-derived permission/capability/resource matrix for trap-proof inputs.
- `specs/pgb2-draft.md`: draft PGB2/PGVM2 kernel contract.
- `tools/pooleos_doctor.py`: verification entry point for the scaffold and PooleGlyph baseline.

Emit a reference channel trace:

```powershell
python .\tools\emit_channel_trace.py --case rectangle-2x2 --out .\runs\rectangle_trace.json
```

Emit and validate a draft PGB2 bundle:

```powershell
python .\tools\emit_pgb2_bundle.py --case six-support --out .\runs\six_support.pgb2.json
python .\tools\validate_pgb2_bundle.py .\runs\six_support.pgb2.json
```

Attach signed membrane smoke metrics to a bundle:

```powershell
python .\tools\emit_pgb2_bundle.py --case six-support --include-signed-metrics --out .\runs\signed_smoke.pgb2.json
```

Attach trap encoding and execution evidence to a bundle:

```powershell
python .\tools\emit_pgb2_bundle.py --case six-support --include-signed-metrics --trap-encoding .\runs\pgb2_trap_encoding.json --trap-execution .\runs\pgb2_trap_execution.json --out .\runs\signed_trap_evidence.pgb2.json
python .\tools\validate_pgb2_bundle.py .\runs\signed_trap_evidence.pgb2.json
```

Emit a replay proof:

```powershell
python .\tools\emit_replay_proof.py --bundle .\runs\six_support.pgb2.json --case six-support --out .\runs\six_support.replay.json
```

Emit a Lab boot trap-bundle manifest:

```powershell
python .\tools\emit_boot_trap_bundle_manifest.py --bundle .\runs\signed_trap_evidence.pgb2.json --replay-proof .\runs\signed_trap_evidence.replay.json --trap-execution .\runs\pgb2_trap_execution.json --out .\runs\pooleos_boot_trap_bundle_manifest.json
```

Stage QEMU shared-folder inputs for the Lab image:

```powershell
python .\tools\pooleos_qemu_prepare_inputs.py --shared-dir .\runs\qemu_shared --bundle .\runs\signed_trap_evidence.pgb2.json --replay-proof .\runs\signed_trap_evidence.replay.json --boot-trap-bundle-manifest .\runs\pooleos_boot_trap_bundle_manifest.json --pgb2-trap-abi-boundary-receipt .\runs\pgb2_trap_abi_boundary_receipt.json --out .\runs\qemu_shared_folder_contract.json
.\lab-os\qemu\scripts\run-pooleos-lab.ps1 -PrepareInputsOnly -SharedOutputPath .\runs\qemu_shared -TrapBundlePath .\runs\signed_trap_evidence.pgb2.json -ReplayProofPath .\runs\signed_trap_evidence.replay.json -BootTrapBundleManifestPath .\runs\pooleos_boot_trap_bundle_manifest.json -Pgb2TrapAbiBoundaryReceiptPath .\runs\pgb2_trap_abi_boundary_receipt.json
```

The ABI receipt flag is optional during the first bootstrap staging pass, then required for the guest to emit `POOLEOS_LAB_TRAP_ABI_BOUNDARY_PASS`. When `pooleos_release_gate.py` is invoked with `--pgb2-trap-abi-boundary-receipt`, the QEMU shared-folder contract must also stage `pgb2_trap_abi_boundary_receipt.json`.

Emit Lab guest autostart evidence:

```powershell
python .\tools\emit_lab_guest_autostart.py --qemu-shared-folder-contract .\runs\qemu_shared_folder_contract.json --out .\runs\lab_guest_autostart.json
```

Emit QEMU boot evidence from the trap-input fixture, or from a captured serial log after boot:

```powershell
python .\tools\emit_qemu_boot_evidence.py --source fixture --out .\runs\qemu_boot_evidence.json
python .\tools\emit_qemu_boot_evidence.py --log .\runs\pooleos-lab-serial.log --source captured_qemu_serial --out .\runs\qemu_boot_evidence.captured.json
```

The Lab QEMU launcher emits captured evidence automatically after a real boot unless `-SkipBootEvidence` is passed:

```powershell
python .\tools\emit_qemu_captured_boot_preflight.py --image .\output\images\rootfs.ext4 --shared-output .\runs\qemu_shared --serial-log .\runs\pooleos-lab-serial.log --boot-validation-output .\runs\boot_log_validation.captured.json --qemu-boot-evidence-output .\runs\qemu_boot_evidence.captured.json --qemu-captured-boot-receipt-output .\runs\qemu_captured_boot_receipt.json --out .\runs\qemu_captured_boot_preflight.json
python .\tools\emit_qemu_captured_boot_receipt.py --fixture-evidence .\runs\qemu_boot_evidence.json --captured-evidence .\runs\qemu_boot_evidence.captured.json --out .\runs\qemu_captured_boot_receipt.json
python .\tools\emit_qemu_captured_boot_launch_bundle.py --preflight .\runs\qemu_captured_boot_preflight.json --qemu-shared-folder-contract .\runs\qemu_shared_folder_contract.json --qemu-captured-boot-receipt .\runs\qemu_captured_boot_receipt.json --fixture-evidence .\runs\qemu_boot_evidence.json --release-gate-output .\runs\release_gate.json --out .\runs\qemu_captured_boot_launch_bundle.json
python .\tools\emit_qemu_captured_boot_dry_run_checklist.py --launch-bundle .\runs\qemu_captured_boot_launch_bundle.json --release-gate-output .\runs\release_gate.json --out .\runs\qemu_captured_boot_dry_run_checklist.json
python .\tools\emit_qemu_boot_marker_contract.py --dry-run-checklist .\runs\qemu_captured_boot_dry_run_checklist.json --lab-guest-autostart .\runs\lab_guest_autostart.json --out .\runs\qemu_boot_marker_contract.json
python .\tools\emit_qemu_boot_marker_image_binding.py --marker-contract .\runs\qemu_boot_marker_contract.json --lab-image-manifest .\runs\lab_image_manifest.json --out .\runs\qemu_boot_marker_image_binding.json
python .\tools\emit_rootfs_content_manifest.py --image-binding .\runs\qemu_boot_marker_image_binding.json --image .\output\images\rootfs.ext4 --extracted-rootfs .\runs\rootfs_extracted --out .\runs\rootfs_content_manifest.json
python .\tools\emit_rootfs_extraction_handoff.py --rootfs-content-manifest .\runs\rootfs_content_manifest.json --note-out .\runs\rootfs_extraction_handoff.md --out .\runs\rootfs_extraction_handoff.json
python .\tools\emit_rootfs_extraction_receipt.py --handoff .\runs\rootfs_extraction_handoff.json --rootfs-content-manifest .\runs\rootfs_content_manifest.json --out .\runs\rootfs_extraction_receipt.json
.\lab-os\qemu\scripts\run-pooleos-lab.ps1 -ImagePath .\output\images\rootfs.ext4 -SharedOutputPath .\runs\qemu_shared -TrapBundlePath .\runs\signed_trap_evidence.pgb2.json -ReplayProofPath .\runs\signed_trap_evidence.replay.json -BootTrapBundleManifestPath .\runs\pooleos_boot_trap_bundle_manifest.json -Pgb2TrapAbiBoundaryReceiptPath .\runs\pgb2_trap_abi_boundary_receipt.json -SerialLog .\runs\pooleos-lab-serial.log -BootValidationOutput .\runs\boot_log_validation.captured.json -QemuBootEvidenceOutput .\runs\qemu_boot_evidence.captured.json
python .\tools\emit_qemu_captured_boot_receipt.py --fixture-evidence .\runs\qemu_boot_evidence.json --captured-evidence .\runs\qemu_boot_evidence.captured.json --operator-executed --out .\runs\qemu_captured_boot_receipt.json
python .\tools\emit_qemu_captured_boot_readiness.py --rootfs-extraction-receipt .\runs\rootfs_extraction_receipt.json --qemu-captured-boot-receipt .\runs\qemu_captured_boot_receipt.json --qemu-captured-boot-evidence .\runs\qemu_boot_evidence.captured.json --out .\runs\qemu_captured_boot_readiness.json
python .\tools\emit_kernel_boot_handoff.py --qemu-captured-boot-readiness .\runs\qemu_captured_boot_readiness.json --qemu-boot-marker-contract .\runs\qemu_boot_marker_contract.json --boot-trap-bundle-manifest .\runs\pooleos_boot_trap_bundle_manifest.json --guest-loader-verification .\runs\boot_trap_bundle_verification.json --out .\runs\kernel_boot_handoff.json
python .\tools\emit_kernel_pgvm2_loader_output.py --kernel-boot-handoff .\runs\kernel_boot_handoff.json --pooleglyph-source-anchor .\runs\pooleglyph_source_anchor.json --parser-kernel-promotion-receipt .\runs\pooleglyph_parser_kernel_promotion_receipt.json --kernel-build-id pending-kernel-loader --out .\runs\kernel_pgvm2_loader_output.json
python .\tools\emit_lab_kernel_transcript_export_receipt.py --out .\runs\lab_kernel_transcript_export_receipt.json
python .\tools\emit_kernel_pgvm2_loader_evidence.py --kernel-boot-handoff .\runs\kernel_boot_handoff.json --kernel-loader-output .\runs\kernel_pgvm2_loader_output.json --pooleglyph-source-anchor .\runs\pooleglyph_source_anchor.json --parser-kernel-promotion-receipt .\runs\pooleglyph_parser_kernel_promotion_receipt.json --out .\runs\kernel_pgvm2_loader_evidence.json
```

The lab transcript receipt stays non-claiming until a real contract run is recorded. Recorded runs are accepted only when the transcript contains exactly one `POOLEOS_KERNEL_GUEST_ENV` audit line for both the PooleGlyph source-anchor and parser-promotion hashes, those values match the host verifier, and the transcript and verifier-output artifact hashes remain bound.

If QEMU already produced a serial log, re-emit the captured evidence without booting again:

```powershell
.\lab-os\qemu\scripts\run-pooleos-lab.ps1 -EmitCapturedEvidenceOnly -SerialLog .\runs\pooleos-lab-serial.log -BootValidationOutput .\runs\boot_log_validation.captured.json -QemuBootEvidenceOutput .\runs\qemu_boot_evidence.captured.json
```

Emit the captured-boot receipt. Before a real QEMU capture exists, this records a pending captured slot while preserving fixture evidence:

```powershell
python .\tools\emit_qemu_captured_boot_receipt.py --fixture-evidence .\runs\qemu_boot_evidence.json --captured-evidence .\runs\qemu_boot_evidence.captured.json --out .\runs\qemu_captured_boot_receipt.json
python .\tools\emit_qemu_captured_boot_launch_bundle.py --preflight .\runs\qemu_captured_boot_preflight.json --qemu-shared-folder-contract .\runs\qemu_shared_folder_contract.json --qemu-captured-boot-receipt .\runs\qemu_captured_boot_receipt.json --fixture-evidence .\runs\qemu_boot_evidence.json --release-gate-output .\runs\release_gate.json --out .\runs\qemu_captured_boot_launch_bundle.json
python .\tools\emit_qemu_captured_boot_dry_run_checklist.py --launch-bundle .\runs\qemu_captured_boot_launch_bundle.json --release-gate-output .\runs\release_gate.json --out .\runs\qemu_captured_boot_dry_run_checklist.json
python .\tools\emit_qemu_boot_marker_contract.py --dry-run-checklist .\runs\qemu_captured_boot_dry_run_checklist.json --lab-guest-autostart .\runs\lab_guest_autostart.json --out .\runs\qemu_boot_marker_contract.json
python .\tools\emit_qemu_boot_marker_image_binding.py --marker-contract .\runs\qemu_boot_marker_contract.json --lab-image-manifest .\runs\lab_image_manifest.json --out .\runs\qemu_boot_marker_image_binding.json
python .\tools\emit_rootfs_content_manifest.py --image-binding .\runs\qemu_boot_marker_image_binding.json --image .\output\images\rootfs.ext4 --extracted-rootfs .\runs\rootfs_extracted --out .\runs\rootfs_content_manifest.json
python .\tools\emit_rootfs_extraction_handoff.py --rootfs-content-manifest .\runs\rootfs_content_manifest.json --note-out .\runs\rootfs_extraction_handoff.md --out .\runs\rootfs_extraction_handoff.json
python .\tools\emit_rootfs_extraction_receipt.py --handoff .\runs\rootfs_extraction_handoff.json --rootfs-content-manifest .\runs\rootfs_content_manifest.json --out .\runs\rootfs_extraction_receipt.json
python .\tools\emit_qemu_captured_boot_readiness.py --rootfs-extraction-receipt .\runs\rootfs_extraction_receipt.json --qemu-captured-boot-receipt .\runs\qemu_captured_boot_receipt.json --qemu-captured-boot-evidence .\runs\qemu_boot_evidence.captured.json --out .\runs\qemu_captured_boot_readiness.json
python .\tools\emit_kernel_boot_handoff.py --qemu-captured-boot-readiness .\runs\qemu_captured_boot_readiness.json --qemu-boot-marker-contract .\runs\qemu_boot_marker_contract.json --boot-trap-bundle-manifest .\runs\pooleos_boot_trap_bundle_manifest.json --guest-loader-verification .\runs\boot_trap_bundle_verification.json --out .\runs\kernel_boot_handoff.json
python .\tools\emit_kernel_pgvm2_loader_output.py --kernel-boot-handoff .\runs\kernel_boot_handoff.json --pooleglyph-source-anchor .\runs\pooleglyph_source_anchor.json --parser-kernel-promotion-receipt .\runs\pooleglyph_parser_kernel_promotion_receipt.json --kernel-build-id pending-kernel-loader --out .\runs\kernel_pgvm2_loader_output.json
python .\tools\emit_lab_kernel_transcript_export_receipt.py --out .\runs\lab_kernel_transcript_export_receipt.json
python .\tools\emit_kernel_pgvm2_loader_evidence.py --kernel-boot-handoff .\runs\kernel_boot_handoff.json --kernel-loader-output .\runs\kernel_pgvm2_loader_output.json --pooleglyph-source-anchor .\runs\pooleglyph_source_anchor.json --parser-kernel-promotion-receipt .\runs\pooleglyph_parser_kernel_promotion_receipt.json --out .\runs\kernel_pgvm2_loader_evidence.json
```

Emit a static microkernel isolation proof:

```powershell
python .\tools\emit_isolation_proof.py --out .\runs\microkernel_isolation.json
python .\tools\validate_artifact.py --schema .\specs\isolation-proof.schema.json .\runs\microkernel_isolation.json
```

Emit a PGB2-style capability trap proof:

```powershell
python .\tools\emit_capability_trap_proof.py --isolation-proof .\runs\microkernel_isolation.json --out .\runs\capability_trap_proof.json
python .\tools\validate_artifact.py --schema .\specs\capability-trap-proof.schema.json .\runs\capability_trap_proof.json
```

Emit a live PooleGlyph source anchor:

```powershell
python .\tools\emit_pooleglyph_source_anchor.py --pooleglyph <POOLEGYPH_REPO> --out .\runs\pooleglyph_source_anchor.json
python .\tools\validate_artifact.py --schema .\specs\pooleglyph-source-anchor.schema.json .\runs\pooleglyph_source_anchor.json
```

Emit a PooleGlyph bridge manifest:

```powershell
python .\tools\emit_pooleglyph_bridge_manifest.py --source-anchor .\runs\pooleglyph_source_anchor.json --pooleglyph <POOLEGYPH_REPO> --out .\runs\pooleglyph_bridge_manifest.json
python .\tools\validate_artifact.py --schema .\specs\pooleglyph-bridge-manifest.schema.json .\runs\pooleglyph_bridge_manifest.json
```

Emit a PooleGlyph Core IR boundary receipt:

```powershell
python .\tools\emit_pooleglyph_core_ir_boundary_receipt.py --bridge-manifest .\runs\pooleglyph_bridge_manifest.json --pooleglyph <POOLEGYPH_REPO> --out .\runs\pooleglyph_core_ir_boundary_receipt.json
python .\tools\validate_artifact.py --schema .\specs\pooleglyph-core-ir-boundary-receipt.schema.json .\runs\pooleglyph_core_ir_boundary_receipt.json
```

Emit a PooleGlyph executable Core IR audit:

```powershell
python .\tools\emit_pooleglyph_core_ir_executable_audit.py --core-ir-boundary-receipt .\runs\pooleglyph_core_ir_boundary_receipt.json --out .\runs\pooleglyph_core_ir_executable_audit.json
python .\tools\validate_artifact.py --schema .\specs\pooleglyph-core-ir-executable-audit.schema.json .\runs\pooleglyph_core_ir_executable_audit.json
```

Emit the parser-to-kernel promotion receipt:

```powershell
python .\tools\emit_pooleglyph_parser_kernel_promotion_receipt.py --core-ir-executable-audit .\runs\pooleglyph_core_ir_executable_audit.json --out .\runs\pooleglyph_parser_kernel_promotion_receipt.json
python .\tools\validate_artifact.py --schema .\specs\pooleglyph-parser-kernel-promotion-receipt.schema.json .\runs\pooleglyph_parser_kernel_promotion_receipt.json
```

Emit a PooleGlyph-derived permission/capability/resource matrix and bind it into trap proof:

```powershell
python .\tools\emit_permission_capability_matrix.py --bridge-manifest .\runs\pooleglyph_bridge_manifest.json --core-ir-boundary-receipt .\runs\pooleglyph_core_ir_boundary_receipt.json --core-ir-executable-audit .\runs\pooleglyph_core_ir_executable_audit.json --parser-kernel-promotion-receipt .\runs\pooleglyph_parser_kernel_promotion_receipt.json --pooleglyph <POOLEGYPH_REPO> --out .\runs\permission_capability_matrix.json
python .\tools\emit_capability_trap_fuzz.py --isolation-proof .\runs\microkernel_isolation.json --permission-capability-matrix .\runs\permission_capability_matrix.json --out .\runs\capability_trap_fuzz.json
python .\tools\emit_capability_trap_proof.py --isolation-proof .\runs\microkernel_isolation.json --permission-capability-matrix .\runs\permission_capability_matrix.json --capability-trap-fuzz .\runs\capability_trap_fuzz.json --out .\runs\capability_trap_proof.json
python .\tools\emit_pgb2_trap_encoding.py --trap-proof .\runs\capability_trap_proof.json --out .\runs\pgb2_trap_encoding.json
python .\tools\emit_pgb2_trap_execution.py --trap-encoding .\runs\pgb2_trap_encoding.json --out .\runs\pgb2_trap_execution.json
python .\tools\emit_pgb2_trap_abi_boundary_receipt.py --trap-encoding .\runs\pgb2_trap_encoding.json --trap-execution .\runs\pgb2_trap_execution.json --bundle .\runs\signed_trap_evidence.pgb2.json --boot-trap-bundle-manifest .\runs\pooleos_boot_trap_bundle_manifest.json --qemu-shared-folder-contract .\runs\qemu_shared_folder_contract.json --out .\runs\pgb2_trap_abi_boundary_receipt.json
python .\tools\validate_artifact.py --schema .\specs\pgb2-trap-abi-boundary-receipt.schema.json .\runs\pgb2_trap_abi_boundary_receipt.json
```

Emit a release-gate report:

```powershell
python .\tools\pooleos_release_gate.py --bundle .\runs\signed_trap_evidence.pgb2.json --replay-proof .\runs\signed_trap_evidence.replay.json --lab-manifest .\runs\lab_image_manifest.json --boot-trap-bundle-manifest .\runs\pooleos_boot_trap_bundle_manifest.json --qemu-shared-folder-contract .\runs\qemu_shared_folder_contract.json --lab-guest-autostart .\runs\lab_guest_autostart.json --qemu-boot-evidence .\runs\qemu_boot_evidence.json --qemu-captured-boot-preflight .\runs\qemu_captured_boot_preflight.json --qemu-captured-boot-launch-bundle .\runs\qemu_captured_boot_launch_bundle.json --qemu-captured-boot-dry-run-checklist .\runs\qemu_captured_boot_dry_run_checklist.json --qemu-boot-marker-contract .\runs\qemu_boot_marker_contract.json --qemu-boot-marker-image-binding .\runs\qemu_boot_marker_image_binding.json --rootfs-content-manifest .\runs\rootfs_content_manifest.json --rootfs-extraction-handoff .\runs\rootfs_extraction_handoff.json --rootfs-extraction-receipt .\runs\rootfs_extraction_receipt.json --qemu-captured-boot-receipt .\runs\qemu_captured_boot_receipt.json --qemu-captured-boot-readiness .\runs\qemu_captured_boot_readiness.json --kernel-boot-handoff .\runs\kernel_boot_handoff.json --kernel-pgvm2-loader-output .\runs\kernel_pgvm2_loader_output.json --lab-kernel-transcript-export-receipt .\runs\lab_kernel_transcript_export_receipt.json --kernel-pgvm2-loader-evidence .\runs\kernel_pgvm2_loader_evidence.json --wsl-prerequisites .\runs\wsl_prerequisites.json --operator-action .\runs\operator_action_request.json --operator-receipt .\runs\operator_action_receipt.json --host-prep-note .\runs\host_prep_note.json --buildroot-probe .\runs\buildroot_probe.json --buildroot-configure .\runs\buildroot_configure.json --buildroot-build .\runs\buildroot_build.json --isolation-proof .\runs\microkernel_isolation.json --capability-trap-proof .\runs\capability_trap_proof.json --capability-trap-fuzz .\runs\capability_trap_fuzz.json --pgb2-trap-encoding .\runs\pgb2_trap_encoding.json --pgb2-trap-execution .\runs\pgb2_trap_execution.json --pgb2-trap-abi-boundary-receipt .\runs\pgb2_trap_abi_boundary_receipt.json --pooleglyph-source-anchor .\runs\pooleglyph_source_anchor.json --pooleglyph-bridge-manifest .\runs\pooleglyph_bridge_manifest.json --pooleglyph-core-ir-boundary-receipt .\runs\pooleglyph_core_ir_boundary_receipt.json --pooleglyph-core-ir-executable-audit .\runs\pooleglyph_core_ir_executable_audit.json --pooleglyph-parser-kernel-promotion-receipt .\runs\pooleglyph_parser_kernel_promotion_receipt.json --permission-capability-matrix .\runs\permission_capability_matrix.json --pdc-source-intake .\runs\pdc_source_intake.json --pdc-math-contract .\runs\pdc_math_contract.json --pdc-golden-vectors .\runs\pdc_golden_vectors.json --pdc-verifier-intake .\runs\pdc_verifier_intake.json --pdc-verifier-reproduction .\runs\pdc_verifier_reproduction.json --pdc-representation-contract .\runs\pdc_representation_contract.json --pdc-representation-receipt .\runs\pdc_representation_receipt.json --pdc-golden-metamorphic-corpus .\runs\pdc_golden_metamorphic_corpus.json --pdc-golden-metamorphic-receipt .\runs\pdc_golden_metamorphic_receipt.json --pdc-qp-contract .\runs\pdc_qp_contract.json --pdc-qp-receipt .\runs\pdc_qp_receipt.json --pdc-qp-stability-contract .\runs\pdc_qp_stability_contract.json --pdc-qp-stability-receipt .\runs\pdc_qp_stability_receipt.json --out .\runs\release_gate.json
```

Emit a Lab image manifest:

```powershell
python .\tools\emit_lab_manifest.py --buildroot-path .\sources\buildroot-2026.05 --buildroot-probe .\runs\buildroot_probe.json --buildroot-configure .\runs\buildroot_configure.json --buildroot-build .\runs\buildroot_build.json --wsl-prerequisites .\runs\wsl_prerequisites.json --release-gate .\runs\release_gate.json --out .\runs\lab_image_manifest.json
```

Run host preflight:

```powershell
python .\tools\pooleos_preflight.py --buildroot-path C:\path\to\buildroot --include-wsl --out .\runs\host_preflight.json
```

Emit a non-mutating WSL prerequisite report:

```powershell
python .\tools\pooleos_wsl_prereqs.py --buildroot-path .\sources\buildroot-2026.05 --out .\runs\wsl_prerequisites.json
```

Emit the operator approval request for WSL package installation:

```powershell
python .\tools\pooleos_operator_action.py --wsl-prerequisites .\runs\wsl_prerequisites.json --out .\runs\operator_action_request.json
python .\tools\pooleos_operator_receipt.py --operator-action .\runs\operator_action_request.json --wsl-prerequisites .\runs\wsl_prerequisites.json --out .\runs\operator_action_receipt.json
python .\tools\pooleos_host_prep_note.py --operator-action .\runs\operator_action_request.json --operator-receipt .\runs\operator_action_receipt.json --note-out .\runs\host_prep_note.md --manifest-out .\runs\host_prep_note.json
```

The host prep note is generated from the action request and receipt. It quotes the exact WSL command, the command SHA-256, and the verification commands to run after operator-approved host preparation.

Run a no-build Buildroot probe once a Buildroot tree is available:

```powershell
.\lab-os\buildroot\scripts\run-build.ps1 -BuildrootPath .\sources\buildroot-2026.05 -ProbeOnly -ProbeReport .\runs\buildroot_probe.json
python .\tools\pooleos_release_gate.py --bundle .\runs\six_support.pgb2.json --replay-proof .\runs\six_support.replay.json --buildroot-probe .\runs\buildroot_probe.json --out .\runs\release_gate.json
```

Current lab source baseline: official Buildroot tag `2026.05`, commit `313414b92c2501a2bc123ffa1b6383dca464de05`.

Run only the Buildroot defconfig step and emit structured evidence:

```powershell
.\lab-os\buildroot\scripts\run-build.ps1 -BuildrootPath .\sources\buildroot-2026.05 -ConfigureOnly -ConfigureReport .\runs\buildroot_configure.json
python .\tools\pooleos_release_gate.py --bundle .\runs\six_support.pgb2.json --replay-proof .\runs\six_support.replay.json --buildroot-probe .\runs\buildroot_probe.json --buildroot-configure .\runs\buildroot_configure.json --out .\runs\release_gate.json
```

Run the WSL-gated defconfig step after emitting WSL prerequisites:

```powershell
python .\tools\pooleos_wsl_configure.py --buildroot-path .\sources\buildroot-2026.05 --prerequisites .\runs\wsl_prerequisites.json --output-dir .\output --out .\runs\buildroot_configure.json
python .\tools\pooleos_wsl_build.py --buildroot-path .\sources\buildroot-2026.05 --configure-report .\runs\buildroot_configure.json --output-dir .\output --out .\runs\buildroot_build.json
```

The build report remains `blocked` until configure passes and `.\output\images\rootfs.ext4` exists with a recorded hash.

## Quick Check

From this directory:

```powershell
python .\tools\pooleos_doctor.py
```

To run the full current PooleGlyph stack as part of the check:

```powershell
python .\tools\pooleos_doctor.py --full
```
