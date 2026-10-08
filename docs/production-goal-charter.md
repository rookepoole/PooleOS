# PooleOS Native Production Goal Charter

Charter version: 2.0.0-native-reset  
Status date: 2026-10-07
Owner and IP holder: Rooke Poole  
Parent objective: production-ready native PooleOS with a Poole-authored microkernel  
Authoritative Build Plan: `docs/pdc-production-build-plan.md`  
Machine ledger: `runs/pdc_production_roadmap.json`  
Master-checklist coverage: `runs/pooleos_native_checklist_coverage.json`  
Last roadmap reconciliation: PooleOS Cycle 237

Cycle 237 proves bounded CPL0 activation and restoration of the owned user root
in two fresh QEMU guests, plus ordinary-boot denial. This is direct kernel
integration progress, not user-mode execution, a usable ISO or production
qualification. Timer recovery, sanitized user entry and fault containment remain
next; no normative requirement changes.
[Cycle 237 evidence](checkpoints/cycle237-live-user-root.md).

Historical Cycle 236 adds the owning CPU-exposure/restoration lifecycle and compiles its
privileged x86-64 adapter. Fresh host tests cover failure quarantine and retained
ownership through restoration and cleanup. The adapter is not boot-wired; actual
ring-3/fault/timer execution and the user-space ISO remain pending. All normative
production requirements remain unchanged.
[Cycle 236 evidence](checkpoints/cycle236-user-root-cpu-lifecycle.md).

Historical Cycle 235 adds an owned inactive user root and guarded kernel-entry stack under
the existing user-space ISO milestone. Retention, failed construction/cleanup,
supervisor permission and ownership boundaries receive host tests. CPU activation,
fault containment and the new ISO remain pending. Normative production scope is
unchanged. [Cycle 235 evidence](checkpoints/cycle235-owned-user-root.md).

Historical Cycle 234 follows the owner's direction to pursue a usable native user-space
integration ISO before continuing the complete robust microkernel. The bounded
milestone and its dependencies are in `docs/native-userspace-integration-iso.md`.
This sequencing direction changes no normative production requirement. Initial
inactive user-image admission is host-tested; live user execution and the new ISO
remain unimplemented. Cycle 233 passed exact qualification and merged as
`507782d` through PR #80; that pass does not qualify this new kernel source.
[Cycle 234 evidence](checkpoints/cycle234-user-entry-foundation.md).

Historical Cycle 233 completes fourteen downstream corrected-media profiles: 28 fresh guest
runs, 663 control groups and 2,863 hostile cases pass. All 27 component/source
checks are current, projected from original captures. All 354 combined tests
pass after reconciliation; the failed attempts remain historical. Full
exact-candidate merge gates remain. No normative charter, native kernel, demo
ISO, phase or flag is promoted.
[Cycle 233 evidence](checkpoints/cycle233-corrected-media-downstream-replay.md).

Historical Cycle 232 replays revalidation, transfer and five CPU profiles on corrected FAT32
media: 16 fresh guest runs, 319 control groups and 77 focused tests pass. Source
coverage is 13/27 current, with 14 downstream profiles pending; the aggregate
source guard remains stale. Native executable bytes, the retained demo ISO and
normative production requirements are unchanged. No phase or flag closes.
[Cycle 232 evidence](checkpoints/cycle232-corrected-media-boot-and-cpu-replay.md).

Historical Cycle 231 repairs the FAT32 media writer and bare directory inspector, with 26
focused tests and four fresh loader/PooleBoot QEMU runs passing. Twenty-one source
profiles still require replay; the original aggregate source guard remains stale
and blocks qualification. Cycle 230 is merged via PR #79 after exact 106/106
canonical and 708/708 Doctor checks. Native executable bytes, the retained demo
and normative completion conditions are unchanged. All work is pre-production.
[Cycle 231 evidence](checkpoints/cycle231-fat32-directory-links.md).

Historical Cycle 230 adds bounded inspection of actual ISO/EFI filesystem bytes, with 19 new
tests passing. The retained demo is rejected for one FAT parent-entry defect and
four absent production objects; the writer repair and broader ISO qualification
are newly flagged. Cycle 229 is merged through PR #78 after exact 106/106 canonical
and 708/708 Doctor checks; its pass does not qualify later edits. No native/ISO
bytes or normative completion conditions changed. All outputs remain pre-production.
[Cycle 230 evidence](checkpoints/cycle230-native-iso-inspection.md).

Historical Cycle 229 adds original-capture bindings for 18 observed data dependencies in
13 specification files. Nineteen focused tests pass. The bounded development
dependency review is complete; full new-candidate, publication and GitHub/review
gates still precede main merge. The preceding exact293383d passes106/106 canonical
and708/708Doctor checks, without qualification of later edits. Native/ISO bytes
and normative production requirements remain unchanged. N36 remains open.
[Cycle 229 evidence](checkpoints/cycle229-reviewed-execution-inputs.md).

Historical Cycle 228 repairs an observed toolchain test failure due solely to the Windows
build observation changing from 26200 to 26300. Every other report byte remains
strictly compared; the original ledger is unchanged. Doctor and the release gate
retain complete failure diagnostics. Nineteen focused tests pass without skips.
Full exact-candidate qualification and dependency review still precede main merge.
Native/ISO bytes and normative requirements are unchanged; branch backup is separate.
[Cycle 228 evidence](checkpoints/cycle228-toolchain-host-observation.md).

Historical Cycle 227 repairs errata recorded admission: 1,742 corrupted records reject through
both paths without exceptions; 34 focused tests and fresh host qualification pass.
All six target-denial reasons remain. Twenty-six other source records, native
kernel, demo ISO and normative completion conditions are unchanged. Next: data/tool
dependency review and full exact-candidate qualification before main merge.
[Cycle 227 evidence](checkpoints/cycle227-errata-recorded-admission.md).
Combined regression passes 126/126 without skips. Explicit data bindings match;
complete read/tool coverage and a passing full qualification remain pending.
Late exact-committed qualification of79adf4a fails:105/106 canonical checks and
707/708 Doctor checks pass, but pooleos:unittest exits1. The outer report loses
individual failure names. Next: retain complete unittest diagnostics and repair
the failure before finishing review and requalifying. Main remains unchanged;
the development branch is cloud-backed. This changes no normative requirement.

Historical Cycle 226 extends static-source coverage to all27 selected profiles and78 Python
files;22 focused tests pass. One fresh errata host qualification retains the exact
target denial, with no guest execution. Eight diagnostic corruptions reveal six
invalid acceptances and two exceptions in each errata admission path. Repair this
merge blocker, review non-Python dependencies, then run full exact-candidate gates.
Native source, demo ISO and normative completion conditions are unchanged.
[Cycle 226 evidence](checkpoints/cycle226-selected-profile-source-coverage.md).
Combined regression passes113/113 without skips; this does not repair the errata
admission defect or establish full canonical qualification. Normative gates stand.

Historical Cycle 225 enforces a separate static-source evidence record for 14 retained
memory-through-lock profiles and 62 distinct Python inputs. Twelve focused tests
pass, including 33 malformed records through component and aggregate checks.
Original boot receipts, native code, ISO and normative charter remain unchanged.
No new guest execution or authentication is claimed. Next: upstream and non-Python
dependency review, then full exact-candidate qualification before main merge.
[Cycle 225 evidence](checkpoints/cycle225-retained-execution-source-closure.md).
Corrected combined regression passes 102/102 without skips. Conservation preserves
28 parent records and 801 native, receipt and historical checkpoint files.

Historical Cycle 224 repairs lock evidence admission and qualifies two final four-vCPU
boots on unchanged kernel216. All27 selected native checks and21 focused tests
pass; both gates reject631 corrupted records. Three disabled validators are
detected. Diagnostic invalid admissions and exceptions remain preserved.
Next N36 shared-helper binding review and full exact-candidate gates before
main merge. No normative requirement, phase/flag, native byte, ISO or production
change. [Cycle 224 evidence](checkpoints/cycle224-locks-admission-and-current-kernel-replay.md).
Final timeout-cleanup regression passes 137/137 and conservation passes. All 14
static helper closures match preserved execution snapshots; runtime enforcement
and broader dependency review remain pending. Initial metadata failures remain
recorded; normative completion conditions are unchanged.

Historical Cycle 223 repairs atomics admission and comment-spoofable instruction auditing.
Two final one-BSP boots and22 focused tests pass;356 corrupted receipts reject.
Eight disabled native guards are detected at optimization0 and3. Original
defects and an invalid no-op test mutation remain preserved. Readiness26/27
leaves locks, N36 shared-helper binding review and full exact-candidate gates
before main merge. No normative condition, phase/flag, native kernel, ISO or
production claim changes. [Cycle 223 evidence](checkpoints/cycle223-atomics-admission-and-instruction-audit.md).

Historical Cycle 222 repairs SMP-preemption admission and seventeen constant-only control
groups on unchanged kernel216. Two final four-vCPU boots and19 focused tests
pass;339 corrupted records reject. Readiness25/27 leaves atomics and locks,
then shared-helper binding review and full exact-candidate qualification before
main merge. No normative condition, phase/flag, native byte, ISO or production
claim changes. [Cycle 222 evidence](checkpoints/cycle222-smp-preemption-admission-and-controls.md).

Historical Cycle 221 qualifies SMP scheduling and AP workers on unchanged kernel216:
four four-vCPU boots, 66 control groups/628 cases and 39 focused tests pass.
Four measured image expectations are corrected; both rejected admissions and
identical candidate receipts remain recorded. Readiness24/27 leaves SMP
preemption, atomics and locks, including seventeen control groups and admission.
Next N12-SCHED-SMP-PREEMPT-001. No normative requirement, phase/flag, native
code, ISO or production status changes. Full qualification precedes main merge.
[Cycle 221 evidence](checkpoints/cycle221-current-kernel-smp-and-ap-worker-replay.md).
Corrected metadata passes 68/68 and conservation passes; two earlier failed
metadata runs remain recorded. Normative completion conditions are unchanged.

Historical Cycle 220 qualifies scheduling, BSP preemption and deferred work on unchanged
kernel216: six virtual boots, 83 control groups/595 cases and 47 focused tests
pass. Two measured image expectations are repaired; the initial failed admission
is retained. Readiness22/27 leaves five profiles from N12-SCHED-SMP-001, plus
seventeen SMP-preemption control groups and admission. No normative condition,
phase, flag, native code, ISO or production status changes. Full exact-candidate
qualification precedes main merge. [Cycle 220 evidence](checkpoints/cycle220-current-kernel-scheduler-replay.md).
Metadata passes 67/67 and conservation passes all 373 bindings and 25 archived
parent records. No normative completion condition changes.

Historical Cycle 219 qualifies memory/IRQ/SMP evidence on unchanged kernel216: twelve virtual
boots, 421 control groups/1137 cases and 93 focused tests pass. Ten measured
accounting/image pins replace obsolete expectations; three failed admissions
remain recorded. Readiness is 19/27, with eight profiles pending from N12-SCHED-001
plus seventeen SMP-preemption control groups and recorded admission. All 25 parent
records are preserved. No normative condition, phase, flag, native code, ISO or
production status changes. Cloud backup remains separate from main qualification.
[Cycle 219 evidence](checkpoints/cycle219-current-kernel-memory-replay.md).
Corrected metadata passes 66/66 and conservation passes; ten initial stale
receipt assertions remain recorded. No normative completion condition changes.

Historical Cycle 218 repairs early QMP capture and qualifies five CPU profiles with refreshed
boot evidence on unchanged kernel216. Twenty final virtual boots and 64 focused
tests pass. Four deterministic pre-repair failures, two initial failed trap runs
and six diagnostic reruns remain separate. Original differing frames were lost
to cleanup; their exact cause is unproven. Readiness is 13/27; fourteen profiles
remain from N9-PMM-ACPI-CONSUMER-001, plus seventeen SMP-preemption control groups
and admission. No normative condition, phase, flag, native byte, ISO or production
claim changes. Shared-helper binding review remains within N36. Full qualification
precedes main merge. [Cycle 218 evidence](checkpoints/cycle218-terminal-capture-and-cpu-replay.md).
Corrected metadata passes 65/65 and conservation passes; five initial stale
expectation failures remain recorded. No normative completion condition changes.

Historical Cycle 217 qualifies six boot-chain profiles on unchanged kernel216. Six fresh
virtual boots, two kernel entries and 97 focused tests pass; the prior failing
live-transfer positive now passes. Initial symbol-address and map-probe failures
are retained and repaired. Readiness is 8/27; nineteen profiles need replay from
N7-TRAP-001, with seventeen SMP-preemption control groups and recorded admission
still open. No normative condition, phase, flag, kernel implementation, demo ISO
or production claim changes. Branch backup remains separate from main qualification.
[Cycle 217 evidence](checkpoints/cycle217-current-kernel-boot-replay.md).
Corrected metadata passes 64/64 and conservation passes; two initial stale
expectation failures are retained. No normative completion condition changes.

Historical Cycle 216 repairs native SMP-preemption transactions and same-tick continuation.
Twenty-seven native cases in both host profiles, fourteen disabled variants,
17 core stages, two matching builds and 43 selected host tests pass. Kernel bytes
changed: readiness is 3/27, with 24 profiles requiring replay from
N5-SYMBOLS-SEMANTICS-001. Seventeen control groups and recorded admission remain;
the SMP-preemption flag is reopened. All initial failures are retained. No phase,
normative condition, demo ISO or production claim changes. Cloud branch backup
is separate from main qualification; the stale live-transfer test remains a gate.
[Cycle 216 evidence](checkpoints/cycle216-native-smp-preempt-transactions.md).
Progress/architecture/checklist regression passes 63/63; earlier metadata and
conservation failures remain recorded. No normative completion condition changes.

Historical Cycle 215 repairs AP-worker admission and eighteen constant-only control groups:
two final four-vCPU boots pass 34 groups/325 cases and 19 focused tests pass.
The suite rejects 343 corrupted records and ten independent gate cases, and
detects 29 disabled native safeguard/transaction variants. Diagnostic baseline
and harness failures remain recorded. Readiness is 24/27; SMP preemption,
atomics, locks and at least 17 control groups remain from
N12-SCHED-SMP-PREEMPT-001. Cloud branch backup is separate from main qualification.
No normative condition, phase, flag, native byte or demo ISO changes.
[Cycle 215 evidence](checkpoints/cycle215-ap-worker-admission-and-controls.md).
Corrected metadata passes 62/62; prior 59/62 and 61/62 runs remain recorded.
Conservation verifies 362 bindings and 22 unchanged archived parent records.

Historical Cycle 214 qualifies the SMP scheduler on unchanged kernel210: two four-vCPU
boots, 32 groups/303 cases and 19 focused tests pass. Measured image pins and
an independent integer-type guard are repaired. Initial source-binding and
premature-regression failures are retained. Readiness is 23/27; four profiles,
AP-worker admission and at least 35 control groups remain from
N12-SCHED-AP-WORKERS-001. Main merge still requires exact-candidate qualification;
branch backup is separate. No normative condition, phase, flag, kernel or ISO changes.
[Cycle 214 evidence](checkpoints/cycle214-current-kernel-smp-scheduler-replay.md).
Metadata passes 61/61; conservation verifies 359 bindings and 22 archived records.

Historical Cycle 213 qualifies scheduler, preemption and deferred work on unchanged kernel210:
six VM boots, 83 control groups covering 595 cases and 47 focused tests pass.
Measured deferred image pins and an isolated exact-integer check are repaired;
full admission already rejected the wrong-typed value. Readiness is 22/27; five
SMP scheduler/atomic/lock profiles, at least 35 control groups and AP-worker
recorded admission remain from N12-SCHED-SMP-001. Main merge still requires full
exact-candidate qualification; development branches provide cloud backup.
No normative condition, phase, flag, native byte or demo ISO changes.
[Cycle 213 evidence](checkpoints/cycle213-current-kernel-scheduler-replay.md).
Corrected metadata passes 60/60; the initial 57/60 stale-progress failure is
preserved. Conservation verifies 358 source bindings and 22 archived records.

Historical Cycle 212 qualifies six memory/IRQ/SMP profiles on unchanged kernel210: twelve
VM boots, 421 control groups covering 1137 cases and 93 focused tests pass.
Ten stale accounting/identity pins are reconciled from independently validated
current-image evidence without rewriting or rerunning the passing guests.
Readiness is 19/27; eight scheduler/atomic/lock profiles and at least 35 control
groups remain from N12-SCHED-001, with AP-worker recorded admission still open.
Main merge still requires full exact-candidate qualification. Development branch
cloud backup is separate. No normative condition, phase, flag, native byte or
demo ISO changes. [Cycle 212 evidence](checkpoints/cycle212-current-kernel-memory-and-multiprocessor-replay.md).
Corrected metadata passes 59/59; one initial stale IPI progress assertion failure
is retained. Conservation verifies 357 bindings and 22 archived records.

Historical Cycle 211 qualifies five CPU profiles on unchanged kernel210: fourteen final VM
runs, 225 controls and 55 focused tests pass. Aggregate admission repairs twelve
malformed nested-build exceptions and an isolated float-relocation pin case;
all 80 malformed cases now reject cleanly. Readiness is 13/27; fourteen profiles
and at least 35 control groups remain from N9-PMM-ACPI-CONSUMER-001. Full exact-
candidate qualification still gates main merge; branch cloud backup is separate.
No normative condition, phase, flag, kernel, demo ISO or production status changes.
[Cycle 211 evidence](checkpoints/cycle211-current-kernel-cpu-admission-and-replay.md).
Corrected metadata passes 58/58; the earlier 248/249 combined run is preserved
as failed, with its remaining stale metadata expectation repaired separately.

Historical Cycle 210 repairs the retained guard collision from kernel growth. A 192-page
reservation with before-write overflow rejection passes native boundary tests,
fresh core/entry qualification and six final VM boots, including two kernel entries.
All 97 focused tests pass. Readiness is 8/27; nineteen downstream profiles and
at least 35 unproven control groups remain from N7-TRAP-001. Main merge still
requires full exact-candidate qualification. No normative condition, phase,
flag status, demo ISO or production claim changes.
[Cycle 210 evidence](checkpoints/cycle210-retained-map-growth-and-boot-replay.md).
Combined scoped regression passes 212/212, including 57 repaired metadata tests,
with no skips. Counts overlap; full canonical qualification is still pending.

Historical Cycle 209 repairs native AP-worker state transactions, generation wrap and wide
counter validation. Thirty native cases in two host profiles, fifteen disabled
variants, 17 core stages, two matching builds, 246 kernel tests and 43 image
controls pass. Kernel bytes changed; readiness is 3/27, with 24 profiles needing
replay from symbols/boot. The AP-worker flag is reopened, but no phase closes.
N0 custody, N5 authentication and full exact-candidate merge qualification remain.
No normative condition, demo ISO or production claim changes.
[Cycle 209 evidence](checkpoints/cycle209-native-ap-worker-transactions.md).
Combined scoped regression passes 117/117 and repaired metadata 56/56, zero
skips. Counts overlap; full exact-candidate merge qualification remains pending.

Historical Cycle 208 repairs SMP admission and sixteen constant-only control groups. Two
final virtual boots pass 303 cases; 18 focused tests pass, including 326 recorded
corruption rejections and eight independent gate cases. The diagnostic baseline,
old image-pin failure and two test-harness failures are preserved. Readiness is
23/27; four profiles and at least 35 control groups remain from
N12-SCHED-AP-WORKERS-001. No normative condition, phase, flag, native byte, ISO or
production status changes. Full exact-candidate qualification precedes main merge.
[Cycle 208 evidence](checkpoints/cycle208-smp-admission-and-controls.md).
Combined scoped regression passes 183/183 and repaired metadata 55/55, zero skips.
Counts overlap; the full exact-candidate merge qualification remains pending.

Historical Cycle 207 qualifies cooperative scheduling, BSP preemption and deferred work on
unchanged kernel203: six virtual boots, 83 control groups, 595 executed cases and
47 focused tests pass. The obsolete deferred image-pin failure is preserved and
corrected without guest evidence changes. Selected readiness is 22/27; five
profiles remain from N12-SCHED-SMP-001, plus at least 51 executed-control groups.
No normative condition, phase, flag, native byte, ISO or production status changes.
Full exact-candidate qualification still precedes main merge.
[Cycle 207 evidence](checkpoints/cycle207-current-kernel-scheduler-replay.md).
Combined scoped regression passes 166/166 with zero skips; repaired metadata
passes 54/54 and conservation verifies 348 bindings and 19 unchanged archives.
Counts overlap; full canonical qualification remains pending.

Historical Cycle 206 qualifies six memory/IRQ/SMP profiles on unchanged kernel203: twelve
virtual boots, 421 control groups, 1,137 cases and 93 focused tests pass. The
stale IPI aggregate pin failure is preserved and corrected without rewriting
guest evidence. Selected readiness is 19/27; eight profiles remain from
N12-SCHED-001, plus SMP recorded admission and at least 51 later control groups.
No normative condition, phase, flag, native byte, ISO or production status changes.
Full exact-candidate qualification still precedes main merge.
[Cycle 206 evidence](checkpoints/cycle206-memory-and-multiprocessor-replay.md).
Combined scoped regression passes 283/283 with zero skips; corrected metadata
passes 53/53 and conservation verifies 347 bindings and 19 unchanged archives.
Counts overlap; full canonical qualification remains pending.

Historical Cycle 205 qualifies five CPU profiles on unchanged kernel203: fourteen virtual
boots, 225 controls and 54/54 focused tests pass; one expected TCG limitation
probe is separate. Selected readiness is 13/27, with fourteen downstream profiles
pending from N9-PMM-ACPI-CONSUMER-001 and at least 51 later control groups open.
No normative condition, phase, flag, native byte, ISO or production status changes.
Full exact-candidate qualification still precedes main merge.
[Cycle 205 evidence](checkpoints/cycle205-current-kernel-cpu-replay.md).
Combined scoped regression passes 242/242 with zero skips; metadata passes 52/52
and conservation verifies 346 bindings and 19 unchanged archived records.
Counts overlap; this is not full canonical qualification or main-merge eligibility.

Historical Cycle 204 qualifies six boot-chain profiles on unchanged kernel203: six virtual
boots, two kernel entries, expected unsigned-development denial and 81/81 focused
tests pass. Selected readiness is 8/27, with 19 profiles pending from N7-TRAP-001
and at least 51 later control groups still unproven. No phase, flag, normative
condition, ISO or production status changes. Main merge still requires full
exact-candidate qualification; branch cloud backup does not require main merge.
[Cycle 204 evidence](checkpoints/cycle204-current-kernel-boot-replay.md).
Combined scoped regression passes 188/188 with zero skips; conservation verifies
345 bindings and 19 unchanged archived records. Counts overlap; this is not
full canonical qualification or main-merge eligibility.

Historical Cycle 203 repairs native SMP state transactions. Seven reproduced failures now
pass; 19 native cases in two host profiles, nine disabled-repair variants,
17 core stages, two matching builds, 246 kernel tests and 43 image controls pass.
Kernel bytes changed: selected readiness is 2/27, with 25 profiles requiring
current-image replay from N5-SYMBOLS-SEMANTICS-001. The SMP flag is reopened;
recorded admission and 16 SMP control groups remain within 51 open groups.
Earlier boot evidence is historical. No normative condition, phase, ISO or
production claim changes. Main merge still requires exact-candidate qualification.
[Cycle 203 evidence](checkpoints/cycle203-native-smp-transactions.md).
Combined scoped regression passes 109/109, zero skips; conservation verifies
344 source bindings and 18 unchanged parent progress records. Counts overlap;
this does not establish full canonical qualification or main-merge eligibility.

Historical Cycle 202 repairs deferred-work recorded admission and replaces fourteen
constant-only control groups with executed native/source cases. Two final
virtual boots, 254 cases and all 17 focused tests pass; 315 corrupted records
are rejected. Selected readiness is 22/27, with five profiles pending and at
least 51 unproven groups in later scheduler profiles. Next: N12-SCHED-SMP-001.
No normative condition, phase, flag, kernel byte, ISO or production claim changes.
[Cycle 202 evidence](checkpoints/cycle202-deferred-admission-and-controls.md).
Combined scoped regression passes 144/144 with zero skips; repaired metadata
passes 49/49 and conservation verifies 338 source bindings. Counts overlap.

Historical Cycle 201 qualifies cooperative scheduling and BSP preemption on the unchanged
Cycle 197 kernel: four fresh virtual boots, 53 control groups, 341 rejection cases
and 31 focused tests pass. Selected readiness is 21/27, with six later profiles
pending from N12-SCHED-DEFERRED-001. Deferred admission and at least 65
control-execution groups remain open before full exact-candidate qualification.
No normative condition, phase, flag, kernel byte, ISO or production claim changes.
[Cycle 201 evidence](checkpoints/cycle201-scheduler-and-preemption-replay.md).
Combined scoped regression passes 128 tests, zero skips; repaired metadata passes
48/48 and conservation passes. Full canonical qualification remains pending.

Historical Cycle 200 qualifies six memory/IRQ/SMP profiles on the unchanged Cycle 197
kernel: twelve virtual boots, 421 control groups, 1,137 rejection cases and
93 scoped tests pass. The stale aggregate IPI image pin is repaired; the initial
admission failure and unchanged guest evidence are preserved. Selected readiness
is 19/27, with eight profiles remaining from N12-SCHED-001, then deferred admission,
at least 65 control-execution groups and full exact-candidate merge qualification.
No normative condition, phase, flag, kernel byte, ISO or production claim changes.
[Cycle 200 evidence](checkpoints/cycle200-memory-and-multiprocessor-replay.md).
Combined scoped regression passes 327 tests, zero skips; corrected metadata
passes 47/47 and conservation passes. Full canonical qualification remains pending.

Historical Cycle 199 repairs CPU control-record admission and requalifies five N7 profiles
on the unchanged Cycle 197 kernel. Fourteen final virtual boots, 225 executed
controls and 54 focused tests pass, including 3,398 control-record and 371 paired
execution corruptions. The original 1,084-case counterexample now rejects through
runtime and gate without exceptions; the earlier bad admissions and stale-pin
failure remain preserved. Selected readiness is 13/27 with fourteen profiles
pending from N9-PMM-ACPI-CONSUMER-001, then deferred admission/control repairs and
full exact-candidate merge qualification. No normative condition, phase, flag,
kernel byte, ISO or production claim changes. Backup is separate from merge.
[Cycle 199 evidence](checkpoints/cycle199-cpu-control-admission-and-replay.md).
Combined scoped regression passes 233 tests, zero skips; initial metadata passes
46/46 and conservation passes. Full canonical qualification remains pending.

Historical Cycle 198 repairs recorded symbol admission and replays the boot chain on the
unchanged Cycle 197 kernel. All 650 corrupted records reject without exceptions;
six final virtual boots, two native kernel entries and 80 focused tests pass.
The failed first transfer attempt and identity regression remain preserved.
Selected readiness is 8/27; 19 profiles remain from N7-TRAP-001, followed by
deferred admission/control repairs and full exact-candidate merge qualification.
Development-branch cloud backup is not main-merge or production acceptance.
No normative charter condition, phase, flag, kernel byte or ISO changes.
[Cycle 198 evidence](checkpoints/cycle198-symbol-admission-and-boot-replay.md).
Combined scoped regression passes 178 tests, zero skips; initial metadata
passes 45/45 and conservation passes. Full canonical qualification is pending.

Historical Cycle 197 repairs native deferred transactions, fault fairness and shutdown
ordering. The new kernel passes 21 native tests in two host profiles, four
disabled-fix variants, all 17 core stages, two matching builds and 54 scoped
Python tests. Selected readiness is 3/27; 24 changed-image dependencies require
replay from N5-SYMBOLS-SEMANTICS-001. Deferred recorded-evidence defects and at
least 65 control-execution gaps remain open. The deferred flag is reopened;
no normative charter term, phase, ISO or production condition changes.
[Cycle 197 evidence](checkpoints/cycle197-native-deferred-transactions.md).

Historical Cycle 196: nine constant-only preemption control groups are replaced with
executed native-host and linked/source audit checks. Two final guest boots,
226 rejection cases and 17 focused tests pass, including 232 corrupted records
and seven disabled native validator variants. Selected readiness is 21/27;
six profiles, at least 65 remaining control-execution gaps and full exact-candidate
qualification still precede main merge. Prior history remains unchanged; broader
regression passes 339 tests with zero skips and initial conservation passes. No normative term,
phase, flag, kernel bytes, ISO or production claim changes.
[Cycle 196 evidence](checkpoints/cycle196-preemption-executed-controls.md).

Historical Cycle 195: scheduler admission reparses raw paired execution and host evidence,
typed observations/summaries and exact control counts. Two final guest boots,
115 rejection cases and 14 focused tests pass, including 221 corrupt records.
All 219 original counterexamples now reject without exceptions. Roadmap 195
preserves prior history; selected readiness is 20/27. Seven dependent profiles
remain from N12-SCHED-PREEMPT-001, alongside at least 74 control-execution gaps and full
exact-candidate qualification before main merge. No normative term, phase,
flag, kernel feature, ISO or production claim changes. Combined scoped regression
passes 322 tests, zero skips. Nine newly verified constant-only preemption
controls supplement the prior non-exhaustive 65-control audit; no kernel defect
is inferred from this source-level evidence gap.
[Cycle 195 evidence](checkpoints/cycle195-scheduler-recorded-evidence.md).
The intermediate cloud-backup record remains historical, not rewritten.

Historical Cycle 194: PMM, VM, IRQ, first AP and per-CPU runtime are freshly qualified on
the unchanged Cycle 192 kernel. Ten boots, 528 rejection cases in 388 groups
and 57 focused tests pass, including 990 corrupted-record cases and disabled
PMM parser/oracle detection. Selected readiness is 19/27; eight profiles remain
from N12-SCHED-001, alongside the 65 scheduler control-execution gaps and full
exact-candidate qualification before main merge. Prior evidence is preserved;
no normative term, phase, flag, ISO or production claim changes.
[Cycle 194 evidence](checkpoints/cycle194-memory-runtime-replay.md).
Combined scoped regression passes 307 tests, zero skips; initial metadata passes
42/42 and conservation passes. Qualification date is September 26; closeout is
September 27. This is not the full canonical suite or a main-merge qualification.

Historical Cycle 193: all five N7 profiles are freshly qualified against the unchanged
Cycle 192 kernel. Fourteen guest boots, 225 rejection controls, linked audits
and 51 focused tests pass; the expected TCG limitation probe is not a passing
exception test. The selected projection is 14/27, leaving thirteen profiles
from N9-PMM-ACPI-CONSUMER-001, then scheduler control evidence and full exact
qualification. Historical CPU evidence remains immutable; no normative term,
phase, flag, merge requirement, ISO or production claim changes.
[Cycle 193 evidence](checkpoints/cycle193-current-kernel-cpu-replay.md).
Combined scoped regression passes 249 tests, zero skips. Corrected roadmap and
checklist regression passes 41/41; the initial 40/41 result remains history.

Historical Cycle 192: native PKMBX1 export and its host oracle now pass
two final four-vCPU boots and 609 rejection cases. Boot-chain replay passes;
57 scoped regression tests pass. The selected projection is 9/27, with 18
dependent profiles still requiring qualification against the changed kernel.
Roadmap 192 archives the previous current records without rewriting history;
current CPU/VM evidence is explicitly pending. Architecture bindings include
the native export and independent oracle. Next is N7-TRAP-001, followed by the
other affected dependencies, scheduler controls and full exact qualification.
No normative condition, phase, flag or merge requirement changes.
[Cycle 192 evidence and resume order](checkpoints/cycle192-native-mailbox-oracle.md).
Combined scoped regression passes 189 tests, zero skips; conservation passes.
The initial three metadata-test failures and corrected 33/33 result are retained.

Historical Cycle 191: IPI admission validates raw execution, typed accounting,
frame-address checksums and exact control counts; three constant-only controls
now call the real validator. Two final four-vCPU boots, 249 cases in 30 categories
and 31 focused tests pass. All 66 original corruptions reject without exceptions.
Selected readiness is 19/27. Bounded AP ownership is current; native mailbox
export and independent host recomputation remain open and block merge. Next is
N8-SMP-MAILBOX-ORACLE-001 before affected-image replay, eight remaining profiles,
scheduler evidence and full exact qualification. No normative condition, phase,
flag, native feature, ISO or production gate changes.
[Cycle 191 evidence](checkpoints/cycle191-ipi-recorded-evidence.md).
Combined scoped regression passes 314 tests, zero skipped; the initial two
historical-assertion failures are retained. Conservation passes. Full exact
qualification and the open mailbox oracle still precede main merge.

Historical Cycle 190: per-CPU admission validates raw execution, dual checksums,
typed accounting and exact per-control case counts. Two final boots, 159 executed
cases in 19 categories and all 10 focused tests pass. All 69 original corruptions
reject without validator exceptions; failures and superseded boots are retained.
Selected readiness is 18/27, with nine profiles pending from N8-SMP-IPI-001,
scheduler evidence and full exact qualification before main merge. No normative
condition, phase, flag, native feature, ISO or production gate changes.
[Cycle 190 evidence](checkpoints/cycle190-percpu-recorded-evidence.md).

Cycle 190 combined scoped regression passes 282 tests, zero skipped. Conservation
passes. Full exact-candidate qualification remains pending before main merge.

Historical Cycle 189: first-AP validates strict raw recorded execution before
allowing only independently checked TSC/checksum differences. Two final boots,
72controls and12focused tests pass, including159recorded corruptions and six
malformed root/control cases through runtime and actual gate. All67original
cases now reject without validator crashes; initial admissions/exceptions,
superseded boots and two intake-helper failures remain preserved. Selected
readiness is17/27, with ten profiles pending from N8-SMP-PERCPU-RUNTIME-001,
plus scheduler evidence and full exact-candidate qualification before merge.
No normative condition, phase, flag, native feature, ISO or production gate changes.
[Cycle 189 evidence](checkpoints/cycle189-first-ap-recorded-evidence.md).

Cycle 189 combined scoped regressions pass 271 tests, zero skipped. Conservation
passes; development-branch cloud backup is separate from main-merge acceptance.
Full exact-candidate qualification remains pending.

Historical Cycle 188: IRQ enforces strict recorded execution, typed aggregate
observations/summaries and independent calibration bounds. Two final virtual
boots, 58 controls and 12 focused tests pass. All 64 original counterexamples
reject without validator exceptions; 229 permanent recorded mutations and six
malformed root/control cases reject through runtime and actual gate. Selected
readiness is 16/27; eleven profiles remain from N8-SMP-FIRST-AP-001, plus the
65 scheduler control-evidence gaps and full exact-candidate qualification.
Initial admissions/exceptions and superseded boots remain preserved. No normative
condition, phase, flag, kernel feature, ISO or production gate closes.
[Cycle 188 evidence](checkpoints/cycle188-irq-recorded-evidence.md).

Cycle 188 combined scoped regressions pass 258 tests, zero skipped. Conservation
passes; this is not full canonical qualification or production promotion.

Historical Cycle 187: VM enforces strict recorded execution and independently
rederived sparse direct-map accounting. Two final virtual boots, 48 controls
and all 10 focused tests pass; 115 malformed records reject through runtime and
actual gate. The original 46/65 runtime and 45/65 gate admissions and two
superseded initial boots remain preserved. Selected readiness is 15/27; twelve
profiles remain from N8-IRQ-001, plus at least 65 scheduler evidence gaps and
full exact-candidate qualification before PR #78 merge. No normative condition,
phase, flag, kernel feature, ISO or production gate closes.
[Cycle 187 evidence](checkpoints/cycle187-vm-recorded-evidence.md).

Cycle 187 scoped closeout passes 245 distinct methods, zero skips; 16 repeated
host-toolchain executions are not extra distinct tests. The initial 244/245
historical-hash assertion failure is preserved, and conservation passes.

Historical Cycle 186: PMM enforces strict recorded execution and independently
rederived ACPI/memory accounting. Two final virtual boots, 191 marker controls
and all 12 focused tests pass; 234 corrupted records reject through runtime
and actual gate. The prior 62/65 runtime and 61/65 gate admissions and two
initial boots remain preserved. Selected readiness is 14/27; thirteen profiles
remain from N9-VM-DIRECT-MAP-001, plus the existing 65 scheduler control-evidence
gaps and full exact-candidate qualification before PR #78 merge. No normative
condition, phase, flag, kernel feature, ISO or production gate closes.
[Cycle 186 evidence](checkpoints/cycle186-pmm-recorded-evidence.md).

Cycle 186 combined closeout passes 234 tests, zero skips. Its initial 233/234
historical-record assertion failure remains preserved; all 65 original audit
counterexamples now reject. This remains scoped, not full merge qualification.

Historical Cycle 185: five CPU profiles enforce typed recorded-pair evidence;
fourteen final virtual boots and 225 marker controls pass on unchanged kernel
bytes. All 50 focused tests pass, including 371 malformed-record cases through
the runtime and actual release gates. The prior 42 accepted exit mutations,
two gate exceptions, initial test-field failure and six superseded trap boots
remain preserved. Selected readiness is 13/27; fourteen memory-through-lock
profiles need replay from N9-PMM-ACPI-CONSUMER-001. At least 65 scheduler
execution-evidence gaps and full exact-candidate qualification still precede
PR #78 merge. No phase, flag, normative condition, new ISO or production gate
closes. [Cycle 185 evidence](checkpoints/cycle185-cpu-recorded-evidence.md).

Cycle 185 combined closeout passes 221 tests with zero skips after correcting
two old roadmap assertions. The failed 219/221 run remains preserved.
Historical evidence, checklist, native products and owner-data conservation pass;
this is not the full canonical suite or a main-merge qualification.

Historical Cycle 184: six host qualifiers verify isolated pinned inputs; eight
generated boot-chain/prerequisite receipts pass current validation. Typed
profiles, exact input/count schemas, rejected-output preservation and roadmap
repeatability are repaired. All 109 focused tests pass; six final virtual boots
include two kernel entries. Kernel bytes are unchanged. Selected readiness is
8/27; nineteen CPU/memory checks need replay from N7-TRAP-001. At least 65
scheduler controls still lack individually bound rejection execution before
full exact-candidate qualification or PR #78 merge. Failures and superseded
boots remain preserved. No phase, flag, normative condition, ISO or production
gate closes. [Cycle 184 evidence](checkpoints/cycle184-boot-host-provenance.md).

Cycle 184 closeout passes 46 metadata/checklist/core tests, 171 combined
hostile-environment regressions and history/source/product conservation.
The initial schema-pin failure remains preserved, not counted as a pass.
Partial measurements remain separate from the historical release-gate file;
full current-candidate qualification has not run.

Historical Cycle 183: N5-ELF-001 validates typed host-profile evidence and rejects
invalid receipts before output. Entry inherits all 19 declared loader inputs
in 72 bindings; 245 kernel tests and 43 controls pass with unchanged product
bytes. All 59 focused hostile-environment tests pass, including exact receipt
reproduction. The separate ELF gate passes; selected readiness remains 3/27.
Next is N5-SYMBOLS-SEMANTICS-001 and ordered dependent replay, then the existing
65 scheduler execution-evidence gaps and full qualification before PR #78 merge.
The earlier unfinished backup remains historical. No phase, flag or normative
condition closes; no new guest boot, native feature or ISO is claimed.
[Cycle 183 evidence](checkpoints/cycle183-elf-loader-provenance.md).

Historical Cycle 182: controlled builds isolate host-probe size drift to MSVC CRT
libraries. Explicit hash-pinned inputs and shared environment sanitation restore
exact entry and fixture receipt reproduction; 39 hostile-environment regression
tests pass. The earlier fixture option-leak failure is preserved. Kernel bytes
are unchanged, but new entry/fixture provenance leaves 24 of 27 selected checks stale.
Replay N5-ELF-001 and ordered N5/CPU/memory dependencies, resolve the existing
65 scheduler control-evidence gaps, then fully qualify before PR #78 merge.
No phase, flag or normative completion condition changes; this is not complete
host attestation, an independent builder, new guest boot, native feature or ISO.
[Cycle 182 evidence](checkpoints/cycle182-host-toolchain-repair.md).

Historical Cycle 181: fourteen memory-through-lock profiles pass 28 final virtual
boots on the unchanged Cycle 177 kernel; four superseded boots and a pre-guest
failure remain separate. All 27 selected consistency checks pass; 164 focused
tests pass and two skip. At least 65 scheduler control entries lack individually
bound rejection execution, so the reported 660 groups / 2,126 cases are not an
executed-rejection total. The resumed combined suite passes 331 tests, fails
exact entry-receipt reproduction once and skips two. A retained rebuild matches
all kernel product fields and bytes; only the host-probe size differs. Resolve
`N6-KENTRY-001` reproduction before `ADD-N36-RECEIPT-COVERAGE-001`, starting
PKSCHED3, full exact-candidate qualification and any PR #78 merge.
No normative condition, phase, flag or production gate closes. The September 26
resumption reconciles September 12/13 evidence and diagnoses receipt drift,
not new guest boots or native features.
[Cycle 181 evidence and limits](checkpoints/cycle181-memory-qualification.md).

Historical Cycle 180: five CPU profiles pass fourteen fresh virtual boots,
225 controls and 46 focused Python tests. The separate expected TCG exception
diagnostic is not a successful exception boot. Positive regressions now use
untouched generated receipts; nineteen aggregate controls pass. Selected
readiness is 13/27, with fourteen memory-through-lock profiles pending beginning
`N9-PMM-ACPI-CONSUMER-001`. Main stays qualified Cycle 176; draft PR #78 needs
full exact-candidate qualification. No normative condition or phase/flag closes.
[Cycle 180 evidence](checkpoints/cycle180-cpu-qualification.md).

Historical Cycle 179: six N5 components pass qualification on the unchanged kernel,
with six final virtual boots, two kernel entries and 71 focused Python tests.
PKREVAL1 now rejects semantically invalid receipts before output; three cases
and thirteen aggregate identity/count controls pass. Two superseded boots and
prior failures are retained. Selected readiness is 8/27; nineteen CPU/memory
profiles need replay beginning `N7-TRAP-001`. Main remains qualified Cycle 176,
PR #78 stays draft, and no normative completion condition or phase/flag closes.
[Cycle 179 evidence](checkpoints/cycle179-boot-chain-requalification.md).

Historical Cycle 178: the unchanged Cycle 177 kernel passes clean PKENTRY1
reproduction with 245 host tests, 43 controls and 55 source bindings. Twelve
entry-gate controls reject stale identities and wrong numeric types. Selected
readiness is 3/27; 24 dependent profiles need replay beginning
`N5-SYMBOLS-SEMANTICS-001`. No new guest, independent builder, full canonical
pass or production promotion follows. The draft remains unmerged.
[Cycle 178 evidence](checkpoints/cycle178-kernel-entry-requalification.md).

Historical Cycle 177: PKEXEC1 dispatch execution holds and two
scheduler rollback fixes pass all 17 native core stages. The changed image has
2/27 current selected readiness checks and requires fresh entry/dependency
qualification beginning `N6-KENTRY-001`. This draft is not merge-qualified;
the roadmap separates new host evidence from historical live receipts and binds
241 architecture inputs. Main is the qualified Cycle 176
merge of PR #77 at `ac15d1d` (105 canonical gates and 708 Doctor checks).
No normative charter condition or production gate changes.
[Cycle 177 evidence](checkpoints/cycle177-dispatch-execution-holds.md).

Historical Cycle 175: fourteen memory-through-lock profiles pass 28 final virtual
boots, 660 groups and 2,126 rejected cases; two earlier SMP boots are superseded.
All 27 selected native checks pass. Embedded-entry provenance tests and the
repaired SMP malformed-input guard pass; the combined suite passes 161 tests
with two optional skips. Full canonical qualification and publication/review
precede PR #77 merge, then N12.3 task-stack/context and CPU-retirement work.
No phase, flag, normative charter or production condition changes.
[Cycle 175 evidence](checkpoints/cycle175-memory-entry-provenance.md).

Historical Cycle 174: five CPU profiles pass fourteen fresh virtual boots,
225 controls and 47 focused tests. Embedded kernel-entry evidence now requires
exact JSON-typed identity with the current validated receipt. Eighty stale or
malformed substitutions and twenty invalid dependency cases reject. The selected
projection is 24/27; memory/SMP provenance replay and full qualification remain
pending. Next is `N9-PMM-ACPI-CONSUMER-001`. No phase, flag, normative charter
condition or production gate closes; main stays Cycle 171 and PR #77 stays draft.
[Cycle 174 evidence](checkpoints/cycle174-cpu-entry-provenance.md).

Historical Cycle 173: kernel-entry provenance and six N5 components are requalified.
Two matching clean linked/canonical builds, eleven entry tests, 71 boot-chain
tests and six fresh QEMU runs pass. The selected readiness projection is 22/27;
CPU/memory/SMP embedded provenance and full exact-candidate qualification remain
pending. The failed Cycle 172 audit remains historical evidence. Next is
`N7-TRAP-001`; no phase, flag, charter condition or production gate closes.
Main remains qualified Cycle 171; PR #77 remains draft.
[Cycle 173 evidence and remaining work](checkpoints/cycle173-entry-provenance-replay.md).

Historical Cycle 172 cloud-backup status: PR #77 remains draft after a failed exact-source
audit at `9c111e2` (104/105 canonical, 707/708 Doctor). The kernel-entry binding
repair passes 12 focused tests, but entry/symbol/SMP IPI evidence needs replay;
the selected projection is 24/27, with 947 Python tests discovered. Generated
roadmap/architecture records and the following summary remain pre-audit
snapshots until reconciled. Main remains qualified through Cycle 171. Backup
does not waive entry/dependency or full-candidate qualification before merge.

Historical pre-audit Cycle 172 summary:

Cloud closeout: Cycles 166-171 merged through PR #76 at `8006c7b`, after
105 runtime-inclusive canonical gates and 708 Doctor checks passed on the exact
merged tree. Cycle 172 qualifies inactive task-stack ownership on
`agent/n12-task-stack-ownership`: 34 lifecycle tests per host profile, 243 kernel
regressions per profile, 11 compile-fail tests and an unchanged linked image.
Progress and source bindings are reconciled, 34 focused Python tests and all
27 selected native checks pass, and 945 Python tests are discovered. Full
runtime-inclusive exact-final qualification and publication/review remain
separate gates for PR #77. Live context/CPU retirement and receipt-growth
integration remain open. The normative charter is unchanged; no phase, flag or
production condition closes.
[Cycle 172 evidence and merge blockers](checkpoints/cycle172-task-stack-ownership.md).

Historical Cycle 171 pre-closeout: fourteen memory/IRQ/SMP/scheduler/atomic/lock profiles pass
on the unchanged Cycle 168 kernel: 28 final headless boots, 660 control groups
and 2,126 rejected cases. Four superseded boots remain separate. SMP receipt
validation now binds current boot artifacts and rejects malformed dependencies.
Measured gate and test expectations are reconciled; the 155-test focused suite
passes with two optional local-transcript skips. All 27 selected native checks
pass. Full runtime-inclusive exact-final qualification and publication/review
gates still precede PR #76 merge and N12.3 task-stack/CPU-retirement integration.
Main remains qualified Cycle 165 at this pre-closeout checkpoint. No phase,
flag, charter condition or production gate closes.
[Cycle 171 evidence](checkpoints/cycle171-native-dependency-replay.md).

Historical Cycle 170: five trap/CPU/xstate/MSR profiles pass on the unchanged
Cycle 168 kernel, with fourteen fresh headless boots, 225 marker controls and
42 focused tests. One expected TCG exception diagnostic is separate. The trap
gate's old kernel identity pins are repaired; 17 regression cases reject stale
identity and unsupported production/authority claims. The selected projection
passes 14/27; thirteen stale downstream checks plus prior SMP new-artifact
replay remain. Next is N9-PMM-ACPI-CONSUMER-001, then ordered VM/IRQ/SMP,
scheduler/atomic/lock replay and runtime-inclusive exact-final qualification.
Main remains qualified Cycle 165 and PR #76 draft. No phase, flag or charter
completion condition changes. [Cycle 170 evidence](checkpoints/cycle170-cpu-state-replay.md).

Historical Cycle 169: six N5 components pass on the unchanged Cycle 168 kernel.
Six fresh headless boots include two actual kernel entries and nine-file
revalidation before unsigned-policy denial. All 83 focused tests pass, with
new source-current kernel-entry binding in the symbol receipt validator.
The selected projection is 9/27, with 18 rejecting downstream checks and
an additional required replay of the prior AP result against new boot inputs.
Next is N7-TRAP-001, then ordered CPU/memory/IRQ/SMP/scheduler/atomic/lock replay
and runtime-inclusive exact-final qualification before PR #76 can merge.
Main remains qualified Cycle 165; no phase, flag, charter condition or
production gate closes. [Cycle 169 evidence](checkpoints/cycle169-boot-chain-replay.md).

Historical Cycle 168 checkpoint: qualified Cycles 162-165 merged through PR #75 at
`6f9399c3cd70ebef2f7610f8b6fdb40ae262e27f`. The exact merged tree passed
105 canonical gates and 708 Doctor checks. Cycle 168 qualifies bounded AP
runtime/stack/frame ownership in two final four-vCPU runs with 27 copied-free
and 18 owner-release rejections per partial/full attempt, 249 negative cases,
243 kernel tests and 56 focused regressions. The checker, serialized-receipt
and mapping/identity failures are repaired and preserved in the checkpoint.
The machine ledger distinguishes this 4/27 selected-native projection from
historical qualification; 23 changed-image dependencies remain pending.
Next is N5-SYMBOLS-SEMANTICS-001, then ordered replay and runtime-inclusive
exact-final qualification before PR #76 may merge. No charter condition,
phase or flag closes; general task-stack/CPU retirement and N0 remain open.
[Current checkpoint and next move](checkpoints/cycle168-ap-ownership-qualification.md).

Historical Cycle 165 pre-merge summary: fourteen memory, interrupt, SMP, scheduler, atomic and lock
profiles on the unchanged Cycle 162 kernel: 28 final successful headless boots,
660 negative-control groups and 2,120 rejected cases. Six superseded initial
boots are preserved separately after correcting three stale test expectations.
All 27 selected native checks pass; this is not a full canonical or Doctor pass.
Memory layout documentation and measured acceptance pins are reconciled, with
25 stale/off-by-one gate controls and fourteen production-overclaim controls.
PKVM3 data-frame scrub-before-reuse integration remains explicitly open.
No phase, flag, charter scope or production condition changes. Main remains
qualified Cycle 161. Runtime-inclusive exact-final qualification with bundle
and replay inputs, publication and GitHub review gates must pass before merge
and further N12.3 execution-stack/general CPU-retirement ownership work.
N0 custody, PooleGlyph and the frozen demo are unchanged.
[Cycle 165 evidence](checkpoints/cycle165-native-dependency-replay.md).

Historical Cycle 164 completes the trap/CPU/xstate/exception/MSR replay on the unchanged
Cycle 162 kernel. Five live profiles pass fourteen final headless boots,
225 marker controls and 41 focused N7 tests, including the unchanged pure
errata-policy tests. The six pre-backup trap boots are included once; one
expected TCG exception non-delivery diagnostic is counted separately from
the two successful WHPX exception boots. A contradictory profile description
and stale current-summary counts are corrected without changing native code.
The selected native projection is 13/27, with fourteen memory-through-lock
dependencies still requiring replay. Historical full audits are not current
aggregate scores. No phase, flag or production gate closes. Main remains
qualified Cycle 161; draft PR #75 holds the source checkpoint. Next is
N9-PMM-ACPI-CONSUMER-001, followed by VM/IRQ/SMP/scheduler/atomic/lock replay
and runtime-inclusive exact-final qualification before any main merge.
PooleGlyph, the frozen demo, N0 custody and the charter scope are unchanged.
[Cycle 164 evidence](checkpoints/cycle164-cpu-replay.md) supersedes the partial
cloud-backup notice while preserving its historical record.

Historical Cycle 163 completes PSYM1, PPOL1, PKLOAD6, PooleBoot, PKREVAL1 and PKXFER1
replay for the unchanged Cycle 162 kernel. Six final headless boots include
two kernel entries with independent nine-file retained-input agreement.
Seventy focused tests pass. Loader and PooleBoot calendar-date validation
repairs two fixed-day schema blockers, with six valid/twenty invalid cases.
This does not close the existing broader N36 schema/evidence review.
The current selected projection passes 8/27; nineteen downstream receipts
remain stale, including transfer-dependent VM evidence. Historical Cycle 162
81/105 and Doctor683/706 are not current aggregate scores. Main remains
qualified Cycle 161 through PR74; PR75 stays draft pending complete replay
and runtime-inclusive exact-final qualification. No phase/flag closes, and
kernel/demo bytes and PooleGlyph remain unchanged. Next: N7-TRAP-001, then
CPU/memory/IRQ/SMP/scheduler/lock replay before further N12.3 ownership work.
N0 custody and all production exits remain open. Charter scope is unchanged.

Historical Cycle 162 implements mandatory active table/data retention in the native
PKVM3 path, with ownership-preserving failure cleanup and synchronized PKMAP2
retained geometry for the 146-page kernel. 228 kernel tests in both modes,
24 lifetime/19 pool cases, seven compile-fail checks, two identical builds
and two fresh headless VM boots pass. Six allocator rejections are observed
per boot. The selected projection passes 4/27; 23 dependency receipts remain
stale. The actual pre-closeout audit is failed at81/105, Doctor683/706; the
optional PooleGlyph runtime pair was excluded and passes separately without
changing that audit. Runtime-inclusive exact-final qualification still gates
merging. Historical Cycle 161 main was merged
through PR74; its aggregate pass is not inherited by changed image bytes.
N12.3, N0 custody and N36 remain open; no phase or flag closes, and neither
PooleGlyph nor the frozen demo ISO changes. The next owner-independent move
is N5-SYMBOLS-SEMANTICS-001 and dependency-ordered replay before main merge.

Historical Cycle 161 completes the changed-kernel dependency replay begun in Cycle 158.
Fourteen current-source memory, IRQ/SMP, scheduler, atomic and lock profiles
pass 28 final headless boots, 658 control groups and 2,118 rejected cases.
Each qualifier passes 219 kernel host tests on the unchanged mandatory-retention
kernel. All 26 selected native checks and the pre-closeout canonical suite
pass: 105 consistency gates, 708 Doctor checks and 917 discovered Python tests.
Exact-final qualification, publication and GitHub review checks still gate
the main merge; this source checkpoint itself does not assert remote merge.

Two fixed-day scheduler readiness schemas were repaired with explicit runtime
calendar validation and six valid/twenty invalid date cases. The shared small
schema engine still does not enforce pattern/format; the broader N36 audit
remains open. Two overlapping scheduler boots were excluded and replaced by
a frozen-source rerun. The actual failed Cycle 158 full audit is preserved.
No native Rust or demo ISO bytes change and no phase or flag closes.

Next is N12-CONCURRENCY-RECLAMATION-001: active-root, execution-stack and
acknowledged CPU-retirement ownership, followed by independent live evidence.
N0 custody remains separately blocked. The 40 phases, 301 subphases, 57 ADD
requirements, 94 flags (35 open), 20 gaps and all 8,996 locked implementation
requirements are preserved. PooleGlyph Phase 65 and its owner's modified
report are unchanged. This is a pre-production development checkpoint,
not a release, signed ISO, desktop completion or production promotion.

Historical Cycle 160 completes N7-TRAP-001 prerequisite replay for the Cycle 158 kernel:
five live trap/CPU/xstate/MSR profiles pass fourteen fresh headless boots,
225 marker controls and 41 focused Python tests. One expected TCG exception
non-delivery diagnostic is recorded separately. All twelve selected N5/N7
checks pass; fourteen memory/IRQ/SMP/scheduler/atomic/lock checks remain stale.
PKCPU1 recorded-evidence validation now rejects missing or contradictory runs,
with 28 receipt and eight summary/gate mutation cases. This is consistency
validation, not authentication; the broader N36 audit remains open.
No kernel Rust or demo bytes change. The preserved full Cycle 158 audit is
still 80/105 and Doctor684/708, not a new aggregate pass. No phase, flag or
production gate closes. N0 custody and N12.3 active-root, execution-stack and
CPU-retirement ownership remain open. Next is N9-PMM-ACPI-CONSUMER-001, then
VM, IRQ/SMP, scheduler, atomics and locks before full exact-final qualification
and any main merge. PooleGlyph Phase 65, the owner's modified report, all
57 ADD requirements and the complete locked checklist remain unchanged.
The partial checkpoint is already backed up in PR #74 at 4f3b4f6; this
reconciliation remains pre-production and does not promote the frozen demo.

Historical Cycle 159 requalifies the changed kernel's PSYM1, PPOL1, PKLOAD6, PooleBoot,
PKREVAL1 and PKXFER1 dependencies under N5-SYMBOLS-SEMANTICS-001. Six fresh
headless QEMU/OVMF boots include two actual PooleKernel entries; all nine
retained files agree with independent host reconstruction. All six selected
current-source gates and 68 focused Python tests pass. A stale build-ID
regression rejects the previous kernel identity. The native kernel bytes and
frozen demo are unchanged; no phase or flag closes and no N5 exit is claimed.
Nineteen downstream native checks remain stale. The preserved full Cycle 158
audit still records 80/105 and Doctor684/708, not a new current aggregate pass.
Next replay N7-TRAP-001, then CPU, memory, IRQ, SMP, scheduler, atomics and locks
before the full exact-candidate suite and any main merge. N12.3 active-root,
execution-stack and CPU-retirement ownership and N0 custody remain open.
PooleGlyph Phase 65/report and the complete locked checklist remain unchanged.
The source is backed up on the agent branch with draft PR #74; backup is not
release or production promotion.

Historical Cycle 158 implements mandatory physical retention for inactive scheduler-task
page tables and all bound data frames, including aliases and pending unmaps.
All-or-nothing group acquisition/release preserves the full owner on late
failure. Twenty-four task-lifetime tests, nineteen pool tests, 219 kernel
regressions including thirteen retention cases, and seven compile-fail tests
cover the bounded host contract. Active roots, execution stacks and live CPU
quiescence are still open under N12.3 and its existing reclamation flag.
The new build identity changes kernel bytes; Cycle 157's merged canonical pass
is historical, not current-candidate qualification. Replay dependencies before
the next main merge. No phase or flag closes, and the frozen demo is unchanged.
The canonical audit fails 25/105 checks (24 stale native receipts plus the
aggregate check); Doctor passes 684/708. This is recorded failed pre-closeout
evidence, not a qualified current candidate. All 29 focused Python tests pass.
N0 governance custody remains independently blocked. PooleGlyph Phase 65,
the owner's modified report and the complete locked checklist are preserved.
Continue N12-CONCURRENCY-RECLAMATION-001, with changed-image prerequisite
qualification first, then active-root and execution-stack lifecycle ownership.

Historical Cycle 157 completes current-source replay from N8-IRQ-001 through the reopened
N12-CONCURRENCY-LOCKS-001 dependency: twelve fresh profile receipts contain
24 headless QEMU/OVMF boots, 421 control groups and 1,881 rejected cases.
All 26 selected N5/N7/memory/IRQ/SMP/scheduler/atomic/lock gates pass. The
unchanged retention kernel passes 214 host tests in each profile. Stale date,
stack-layout, test-count and linked-kernel acceptance bindings are corrected
from measured evidence; three IRQ/SMP error-formatting paths now return failed
checks for invalid schema records. Two new regression methods cover twelve
production-overclaim and three schema-error cases. The broad N36 receipt audit
remains open. The canonical candidate replay passes all 105 gates and 708 Doctor
checks, including the 917-test suite. This restores only the bounded N12.2
PKLOCK1 milestone and closes its reopened flag. All 57 ADD requirements,
94 flags (35 open),
20 gaps, 40 phases, 301 subphases and locked checklist mapping remain intact.
PooleGlyph Phase 65 and its user-modified report are unchanged. The separate
demo, production boundary, governance custody and N12.3 ownership work remain
unchanged. Checkpoints through Cycle 156 are already on the remote agent branch;
main may advance only after the complete exact-final local and configured
GitHub gates. N12-CONCURRENCY-RECLAMATION-001 is the next engineering move.

Historical Cycle 156 requalifies PKPMM7/PKACPI1 and PKVM3 for the existing unmerged
retention-capable kernel. The exact manager contract is now 15,632 bytes;
old-size contract and marker controls reject. Independent PBP1 accounting
binds the one-page usable-to-loader ownership shift, allocator growth and
reclaim, and the sparse direct map. Final receipts contain four fresh boots
and 237 negative controls; native executable bytes do not change. Shared map
addresses and current checksums are documented from measurements. Retention
does not itself remove direct-map admission. No phase/flag, full canonical
gate, N9/N12 exit, frozen demo, main or production promotion is claimed.
Counts remain 57 ADD requirements, 94 flags (36 open), 20 gaps, 40 phases and
301 subphases with complete locked checklist mapping. Next replay N8-IRQ-001,
first-AP/AP-runtime/IPI, scheduler, atomics and locks; then run the full current
candidate suite. N0 custody and N12.3 mandatory ownership remain open. The
broader N36 recorded-evidence audit is not closed by these live runs.
Four stale PKMAP2 fixture cases were also repaired against current measured
geometry, preserving the specific guard-collision rejection. The focused
current-source gate projection passes fourteen checks; twelve downstream
native checks remain stale. It is not a canonical or Doctor pass.
Historical failures and prior exact-candidate acceptance remain preserved.

Cycle 155 reconstructs the current kernel's trap/CPU/xstate/MSR evidence through
fourteen fresh QEMU/OVMF boots in the final receipts, 225 marker controls across
five profiles, 41 focused N7 Python tests and the unchanged current PKERR1 gate.
It also repairs PKTRAP1's acceptance of incomplete or contradictory recorded
run evidence: 25 receipt mutations and eight release-boundary controls reject.
The broader per-profile audit remains required under new
ADD-N36-RECEIPT-COVERAGE-001 and FLAG-N36-RECEIPT-COVERAGE-001.
The focused projection passes twelve selected N5/N7 gates; fourteen downstream
native checks remain stale. This is not a full canonical or Doctor pass.
No kernel bytes, main, frozen demo, signing trust or production status change.
The ledger now has 57 ADD requirements and 94 flags, including 36 open flags;
all locked checklist coverage, 40 phases/301 subphases and 20 gaps remain.
Next re-derive PMM ownership/layout accounting under
N9-PMM-ACPI-CONSUMER-001, then replay VM, interrupts, SMP, scheduler, atomics
and locks before the complete current-candidate suite and merge gate.
N12.2 and N12.3 remain partial/open. N0 custody is independently blocked;
this development step needs no new owner action. Historical failures and
qualification boundaries below remain authoritative for their exact candidates.

Cycle 154 reconstructs the N5 prerequisites for the changed-kernel and reopened
N12.2 lock replay. PSYM1 is rebound from measured debug/loaded/kernel/manifest
identities and independently requalified; PPOL1 now rejects readiness whose
current canonical dependency vectors differ, and binds the payload-reference
implementations. Fresh policy, symbol, loader, aggregate PooleBoot and retained-byte
revalidation qualification pass. Two PKXFER1 runs enter the actual kernel and
reparse nine retained files before terminal unsigned denial; 63 focused Python
tests and all six corresponding boot-chain gates pass. This changes neither
kernel bytes, symbol consumption, signature acceptance, authority nor production
status. Replay the remaining trap/CPU/memory/SMP/scheduler/lock profiles next,
starting with N7-TRAP-001, before the reopened N12.2 milestone can close.
Keep the full dependency and aggregate gate pending until actual replay passes.
The Cycle 154 diagnostic audit still rejects 19 downstream native checks and
the aggregate suite; two omitted CLI inputs were checked separately, not folded
into an invented canonical pass. Preserve this failed audit and its limitation.
No checklist requirement, program gap, N5 exit or reopened lock flag closes.

Cycle 153 implements PKRETAIN1 allocator-enforced retention under the existing
N12.3 reclamation move. Non-copyable tokens protect explicitly retained physical
allocations from every ordinary free path, survive metadata migration and ledger
growth, and fail closed on lost ownership. The three-AP path now retains its old
frames through stop acknowledgements and final INIT parking before scrub/release.
Attempted starts are counted before issuing startup commands, so a missing
online acknowledgement cannot bypass final parking during failure cleanup.
The task-lifetime harness demonstrates retained physical page-table ownership.
Host qualification passes; the linked image and retained boot layout change.
Complete dependency replay and the full current-candidate gate are pending.
The first aggregate attempt, before the final startup-mask repair, failed
25/105 checks; preserve that result and rerun affected evidence, never inherit
its passing subset as a current-candidate aggregate pass.
Cycle 152 is the last fully qualified main baseline; its receipts must not be
inherited for Cycle 153 bytes. No merge, release, demo rebase or production
promotion is authorized by partial qualification. The next move is to finish
this candidate's replay, then mandatory active task/root ownership and an
independent live retirement/failure oracle. N12.3, its flag and all 20 gaps remain
open. See `docs/native-kernel-physical-retention.md`.

Cycle 153 also reopens `FLAG-N12-CONCURRENCY-LOCKS-001` and N12.2 after a
four-participant host probe exposed a stale-counter `QueueFull` result. Raw and
writer-ticket reservation now retry that inconsistent sample; capacity,
wraparound and concurrent progress coverage expands within the existing tests.
Resolve current-source lock/profile and aggregate replay before extending N12.3.
The repair and historical failed run remain documented; no historical pass
overrides the newly discovered regression.

Cycle 152 resumes owner-independent native development under
`N12-CONCURRENCY-RECLAMATION-001`. PKLIFE1 owns the actual PKSCHED4 scheduler
and binds moved inactive PKVM1 address-space resources to PKRECLAIM1 reader
pins, checked task generations, cancellation, retirement and exact-once reclaim.
Nineteen lifetime tests and nineteen pool tests pass in both host profiles;
three borrowing compile-fail tests, 206 unchanged kernel regressions and
freestanding checks pass. Canonical linked boot bytes remain unchanged.
This is serialized inactive-object integration, not active-root ownership,
hardware quiescence, a live selector, ring 3 or production. Existing PMM handle
copyability is an explicit remaining ownership boundary. The next chronological
step is acknowledged remote teardown and physical ownership, followed by an
independent oracle and two-run live failure qualification. N12.3 and its flag
remain open. The isolated demo, governance custody and all 20 gaps are unchanged.
See `docs/native-kernel-task-lifetimes.md` for invariants and retained limitations.

Cycle 151 adds the owner-requested unsigned optical demo and demo-only PooleGlass
static boot renderer without modifying production native source or kernel bytes.
Two fresh QEMU optical boots pass the existing PKLOCK1 diagnostics, dual-channel
handoff checks, and exact boot-frame comparison. The design system and PG-01
through PG-10 implementation register in `docs/pooleglass-design-system.md`
govern the visual direction across the future OS. N29.8 is partial, the UI flag
remains open, and no desktop, live material renderer, animated boot, installer,
hardware qualification or production promotion is implied. N12 reclamation
integration remains the next chronological kernel move. Demo source and extra
qualification live under `demos/native_iso/`; it does not replace any production
gate or resume the paused production goal automatically.

Cycle 150 advances N12.3 with the PKRECLAIM1-CORE bounded object pool:
actual payload ownership, pool-bound generation handles, scoped reader pins,
retirement, exact-once reclamation, exhaustion handling and shutdown retention.
Nineteen tests pass in each of two host profiles, one compile-fail borrow test
and 206 existing kernel tests pass, and freestanding checks pass. The linked
kernel bytes remain identical to Cycle 149. This is host-qualified kernel
library implementation, not live integration. N12.3 and its flag remain open
for actual scheduler/address-space lifecycle binding, acknowledged cross-CPU
quiescence, independent oracle and live failure/rollback qualification. No
governance, hardware, signing, release or production boundary changes.

Cycle 150 also requalifies all 24 dependent native profiles after the first
aggregate attempt correctly rejected stale source bindings. Existing checks
remain unchanged; fresh dependency evidence cannot promote the new core from
host-only qualification to live reclamation integration.

Post-Cycle 149 registration update (2026-09-04): the primary FIDO2 governance
key is enrolled, its exact fingerprint is owner-confirmed, and GitHub SSH
signing-key registration `1158225` is verified for `rookepoole`.
`security/governance-key-registration.json` supersedes earlier unavailable-key
statements for current status; historical owner receipts retain their original
bytes. `N0-HW-KEY-ACQUIRE-001` is satisfied for the primary key. The immediate
move is `N0-GOVERNANCE-CUSTODY-001`: verify an enrollment signature and establish
the separately controlled recovery signer. `FLAG-N0-GOVERNANCE-KEY-001` remains
open for those requirements. Architecture signing and production gates remain
open, and `N12-CONCURRENCY-RECLAMATION-001` remains the next kernel move.

Rooke Poole merged registration PR #68 as `4ade40f`. Post-merge qualification
of that source passed 707 Doctor checks, all 105 consistency-gate checks, and
the publication scan; the full PooleGlyph stack passed in a disposable copy.
Independent recovery remains unprovisioned. No alternate recovery-key profile
is accepted, no recovery key was generated, and no custody or production
requirement was weakened. Owner-independent native development may continue
while this external dependency remains open.

Cycle 149 reconciliation (superseding current Cycle 148 implementation and
next-move values): governance and external-key state are unchanged. The
owner-independent `N12-CONCURRENCY-LOCKS-001` move adds selector 22 PKLOCK1
and closes only `FLAG-N12-CONCURRENCY-LOCKS-001` for one bounded x86-64
development scope. The allocation-free lock family provides FIFO ticket and
IRQ-save spinlocks, a sleeping mutex with direct bounded priority donation,
FIFO notification, a writer-preferred reader-writer lock, and a seqlock.
Five lock ranks, cycle and recursion rejection, owner-death handling,
try/timed paths, and exact rollback are enforced. Nine exact host receipts
include 8,192 FIFO ticket acquisitions. Two exact 35-marker four-vCPU runs
exercise one shared live ticket lock across the BSP and three APs, then revoke
all three shared aliases before shootdown, park, scrub, and release. Ten
focused lock tests within 206 kernel host tests and 30 hostile-control
categories covering 103 rejected cases pass. The canonical kernel is 513,680
bytes in a 585,728-byte, 143-page image with entry `0xA000`, text end
`0x70000`, RELRO end and data start `0x7D000`, 1,295 relocations, and SHA-256
`9029AEE51A4D557EF5B29945985E4A1F07C67DDE9C8C367C80BD1B9EDD9D409E`.
N12.2 is complete only for this frozen profile. Deferred reclamation and
ABA-safe object lifetime, general SMP, ring-3/address-space switching, full
per-task architectural state, target execution, N12 exit, release, and
production remain open. `production_ready=false`; the blocked external move
was `N0-HW-KEY-ACQUIRE-001` at the Cycle 149 engineering close, while
`ADD-N12-CONCURRENCY-RECLAMATION-001` and
`FLAG-N12-CONCURRENCY-RECLAMATION-001` bind
`N12-CONCURRENCY-RECLAMATION-001` as the next owner-independent move. No key,
signature, public-key publication, driver load, firmware change,
physical-media write, tag, release, or production promotion occurred.

Cycle 148 reconciliation (superseding current Cycle 147 implementation and
next-move values): governance and external-key state are unchanged. The
owner-independent `N12-CONCURRENCY-ATOMICS-001` move adds selector 21 PKATOM1
and closes only `FLAG-N12-CONCURRENCY-ATOMICS-001` for the frozen x86-64
scope. Typed integer and pointer atomics, operation-specific ordering, nine
accepted and eleven rejected compare-exchange order pairs, overflow-safe
references, 4,096 publication rounds, 20,480 contended RMW/CAS operations,
2,048 sequential-consistency rounds, seven linked instruction audits, and one
BSP process-to-interrupt ordering profile pass. Seven focused tests within
196 kernel host tests, eight exact host receipts, two exact 41-marker runs,
and 29 hostile-control categories covering 78 rejected cases pass. The
canonical kernel is 513,672 bytes in a 585,728-byte, 143-page image with
1,289 relocations and SHA-256
`3CBDF56E90D957E62FC35EAEFF376580BEBDA3623FE4591AB6718984AB258EB7`.
N12.1 is complete only for this frozen profile. General locks, reclamation,
general SMP, target execution, N12 exit, release, and production remain open.
`production_ready=false`; the blocked external move remains
`N0-HW-KEY-ACQUIRE-001`, while `N12-CONCURRENCY-LOCKS-001` became the next
owner-independent move. No key, signature, public-key publication,
privileged host probe, driver load, firmware change, physical-media write,
tag, release, or production promotion occurred.

Cycle 147 reconciliation (superseding current Cycle 146 implementation and
next-move values): governance and external-key state are unchanged, and no
key, signature, publication, privileged host probe, driver load, firmware
change, physical-media write, tag, release, or production promotion occurred.
The owner-independent `N12-SCHED-SMP-PREEMPT-001` move adds selector 20
PKSCHED6 and closes only `FLAG-N12-SCHED-SMP-PREEMPT-001` for one exact
BSP-0/AP-1,2,3 SandyBridge-minus-AVX development topology. Four
allocation-free timer/event/frame/run-queue lanes apply deterministic cancel,
wake, and migration ordering. Eight live reschedule IPIs and five modeled
exact acknowledgements gate ownership; three two-tick quantum switches
complete; one APIC-4 timeout restores source ownership and rejects its late
acknowledgement; maximum bypass and watchdog age remain two. All eight tasks
retire, all timer/frame owners are revoked, all three APs park, and 102 pages
or 417,792 bytes are scrubbed, verified, and released. Five focused tests
within 189 kernel host tests, seven exact Rust/Python host receipts, two exact
38-marker four-vCPU boots, and 34 hostile-control categories covering 232
rejected cases pass. The canonical kernel is 513,672 bytes in a 585,728-byte,
143-page image with entry `0xA000`, text end `0x70000`, RELRO end and data
start `0x7D000`, 1,264 relocations, and SHA-256
`FCE5C1F2478651D010A2F2781B80494FD0D9721880D33CE8C66A499B35C8DAB6`.
The retained layout now uses two leaf tables and five table pages. AP-local
timer/frame lanes remain bounded semantic inputs; this is not AP-local timer
interrupt delivery or general SMP. General topology/hotplug/x2APIC, complete
atomics/lock/reclamation families, ring-3/address-space switching, full
per-task architectural state, target execution, N12 exit, release, and
production remain open. `production_ready=false`; the blocked external move
remains `N0-HW-KEY-ACQUIRE-001`, while
`ADD-N12-CONCURRENCY-ATOMICS-001` and
`FLAG-N12-CONCURRENCY-ATOMICS-001` bind `N12-CONCURRENCY-ATOMICS-001` as the
next owner-independent move.

Cycle 146 reconciliation (superseding current Cycle 145 implementation and
next-move values): governance and external-key state are unchanged, and no
key, signature, publication, privileged host probe, driver load, firmware
change, physical-media write, tag, release, or production promotion occurred.
The owner-independent `N12-SCHED-AP-WORKERS-001` move adds selector 19
PKSCHED5 and closes only `FLAG-N12-SCHED-AP-WORKERS-001` for one exact
BSP-0/AP-1,2,3 SandyBridge-minus-AVX development topology. Three
allocation-free AP-local queues and workers own fifteen generation-safe slots.
One timer top half enqueues thirteen items; dispatch remains forbidden until
EOI. Twelve exact typed call-function deliveries execute nine timer-driver and
three generation-reclaim consumers on private guarded IST1 stacks. One queued
cancellation and one remote in-flight cancellation complete with exact
semantics; one APIC-4 timeout restores source ownership and rejects its late
acknowledgement; flush reaches eleven completed and two cancelled items before
all thirteen slots are reclaimed. All three workers retire, all three APs
park, and 102 pages or 417,792 bytes are scrubbed, verified, and released. Ten
focused tests within 184 kernel host tests, six exact independent Rust/Python
host receipts, two exact 37-marker four-vCPU boots, and 34 hostile-control
categories covering 226 rejected cases pass. The canonical kernel is 485,000
bytes in a 557,056-byte, 136-page image with entry `0xA000`, text end
`0x69000`, RELRO end and data start `0x76000`, 1,222 relocations, and SHA-256
`D11591395FDD8CD7BEEFA0D847A5C99EB133ED15F8DCDDE3392BFA499DCEDC33`.
This is exact-topology typed AP-worker evidence, not an arbitrary callback API
or complete driver/service runtime. General topology/hotplug/x2APIC, general
SMP timer preemption, complete lock/reclamation families, ring-3/address-space
switching, full per-task architectural state, target execution, N12 exit,
release, and production remain open. `production_ready=false`; the blocked
external move remains `N0-HW-KEY-ACQUIRE-001`, while
`ADD-N12-SCHED-SMP-PREEMPT-001` and
`FLAG-N12-SCHED-SMP-PREEMPT-001` bind `N12-SCHED-SMP-PREEMPT-001` as the
next owner-independent move.

Cycle 145 reconciliation (superseding current Cycle 144 implementation and
next-move values): governance and external-key state are unchanged, and no
key, signature, publication, privileged host probe, driver load, firmware
change, physical-media write, tag, release, or production promotion occurred.
The owner-independent `N12-SCHED-SMP-001` move adds selector 18 PKSCHED4 and
closes only `FLAG-N12-SCHED-SMP-001` for one exact BSP-0/AP-1,2,3
SandyBridge-minus-AVX development topology. Its allocation-free controller
owns four run queues, four idle owners, and eight generation-tagged task slots.
One cross-CPU wake and two migrations commit only after exact AP
acknowledgements bind task generation, owner epoch, source and target CPU,
attempt, sequence, operation, status, error, and result. Each AP dispatches two
local tasks and the BSP dispatches two. One deliberate APIC-4 timeout preserves
the source queue and owner epoch, withholds target ownership, and rejects a late
acknowledgement; a stale task generation is rejected independently. All eight
tasks retire, all three APs quiesce and park, and 102 pages or 417,792 bytes are
scrubbed, verified, and released. Eight focused tests within 173 kernel host
tests, five exact independent Rust/Python host receipts, two exact 37-marker
four-vCPU boots, and 32 hostile-control categories covering 209 rejected cases
pass. The PKENTRY1 layout was expanded without changing its `0xA000` entry or
557,056-byte, 136-page image: text now ends at `0x66000`, RELRO ends at
`0x74000`, and writable data begins there. The canonical kernel is 476,808
bytes with 1,181 relocations and SHA-256
`9C23236E85A6D2C7AEEFDA12F3CEC202DC3BF34B89D9CEAEEBB7037A079DA168`.
The first selector-18 execution exposed an exact low-guard stack fault at
`RSP/CR2=0xFFFFFFFF80088BC8`, 1,080 bytes below the former 32-page stack. The
shared retained layout now provides a 36-page, 144-KiB stack between the same
absent guards and preserves one spare page-table leaf. A full dependency replay
from PKLOAD6 through PKSCHED4 passed after the repair, with refreshed PBP1,
PKPMM7, PKVM3, and downstream receipt identities.
This is exact-topology SMP scheduler evidence, not general SMP. General
topology/hotplug/x2APIC, general timer preemption, AP-local deferred workers and
driver/service consumers, arbitrary callbacks, complete lock/reclamation
families, ring-3/address-space switching, full per-task architectural state,
target execution, N12 exit, release, and production remain open.
`production_ready=false`; the blocked external move remains
`N0-HW-KEY-ACQUIRE-001`, while `ADD-N12-SCHED-AP-WORKERS-001` and
`FLAG-N12-SCHED-AP-WORKERS-001` bind `N12-SCHED-AP-WORKERS-001` as the next
owner-independent move.

Cycle 144 reconciliation (superseding current Cycle 143 implementation and
next-move values): governance and external-key state are unchanged, and no
key, signature, publication, privileged host probe, driver load, firmware
change, physical-media write, tag, release, or production promotion occurred.
The owner-independent `N12-SCHED-DEFERRED-001` move adds selector 17 PKSCHED3
and closes only `FLAG-N12-SCHED-DEFERRED-001`. Its allocation-free eight-slot
controller freezes generation-safe work identity, typed Add/Xor/Fence
operations, duplicate suppression, EOI-gated dispatch, a maximum three-item
high-priority bypass, queued and running cancellation, flush watermarks, exact
retirement and shutdown, and five rollback boundaries. One real PKIRQ1
local-APIC timer top half enqueues eight items and issues EOI before any worker
dispatch. Two fixed BSP workers use private 16-KiB stacks inside retained
bootstrap memory, alternate across slots `0,2,4,1,5,6`, enter three times each,
and perform twelve exact hardware context transitions. Five items complete,
three cancel, all eight retire, interrupt-controller state and MMIO mappings
are restored, and all 32,768 worker-stack bytes are cleared. Seven focused
tests within 165 kernel host tests, five exact independent Rust/Python host
receipts, two exact 37-marker qemu64 runs, and 30 hostile-control categories
covering 208 rejected cases pass. The exact kernel is 460,424 canonical bytes
in a 557,056-byte, 136-page image with 1,125 relocations and SHA-256
`FC13CF79E94318FAE10AFF9E7198036B30C587CF2BFD10457A045ACC6EB7665E`.
This is bounded BSP deferred-work evidence with typed built-in operations, not
the complete N12 scheduler or a callback API. Driver/service consumers,
AP-local run queues and workers, remote reschedule IPIs, cross-CPU wake and
migration, ring-3/address-space switching, complete per-task architectural
state, target execution, N12 exit, release, and production remain open.
`production_ready=false`; the blocked external move remains
`N0-HW-KEY-ACQUIRE-001`, and `ADD-N12-SCHED-SMP-001` plus
`FLAG-N12-SCHED-SMP-001` bind `N12-SCHED-SMP-001` as the next
owner-independent move.

Cycle 143 reconciliation (superseding current Cycle 142 implementation and
next-move values): governance and external-key state are unchanged, and no
key, signature, publication, privileged host probe, driver load, firmware
change, physical-media write, tag, release, or production promotion occurred.
The owner-independent `N12-SCHED-PREEMPT-001` move adds selector 16 PKSCHED2
and closes only `FLAG-N12-SCHED-PREEMPT-001`. It composes PKSCHED1 and PKIRQ1
through an allocation-free eight-event controller and exact 176-byte
interrupt frames. Two exact 35-marker qemu64 BSP runs open six one-shot timer
windows and reproduce task trace `0,1,2,0,3,3` with causes
`none,quantum,wake,block,wake,none`. Six frames are saved, four are restored,
six EOIs are issued, four hardware switches occur, and four isolated 16-KiB
task stacks each enter exactly once. Pending work returns to zero; all tasks
retire; controller state and MMIO mappings are restored; and 65,536 stack
bytes are cleared. Seven focused tests within 158 kernel host tests and 25
hostile-control categories covering 178 rejected cases pass. The exact kernel
is 443,504 canonical bytes in a 557,056-byte, 136-page image with 1,086
relocations and SHA-256
`A5DE1DBD2ECA9243D90C2EAA2BEDCAC4B0FCC5E4A4779073E398C6722F30B943`.
This is bounded BSP timer/wakeup preemption evidence, not the complete N12
scheduler. Deferred reclamation/workers, live AP dispatch and cross-CPU
migration, ring-3/address-space switching, complete per-task FS/GS and
xstate/debug/PMU ownership, target execution, N12 exit, release, and
production remain open. `production_ready=false`; the blocked external move
remains `N0-HW-KEY-ACQUIRE-001`, and the next owner-independent move is
`N12-SCHED-DEFERRED-001`.

Cycle 142 reconciliation (superseding current Cycle 141 implementation and
next-move values): governance and external-key state are unchanged, and no
key, signature, publication, privileged host probe, driver load, firmware
change, physical-media write, tag, release, or production promotion occurred.
The owner-independent `N12-SCHED-001` move adds selector 15 PKSCHED1 and closes
only `FLAG-N12-SCHED-FOUNDATION-001`. Its allocation-free four-CPU/eight-task
core freezes generation-safe task identity, four deterministic queues,
priorities 1-31, maximum bypass 7, affinity, modeled migration, accounting,
yield/block/wake/cancel/timeout/teardown transitions, one-mutex direct priority
inheritance, bounded references, and a raw spinlock. A deterministic Rust and
Python campaign agrees over 4,096 steps, 1,761 dispatches, 2,334 migrations,
and checksum `0x23B76E2F80E2B747`. Two exact 17-marker qemu64 BSP runs execute
eight cooperative dispatches and sixteen context transitions across two
distinct 16-KiB stacks through an exact linked-image-audited 18-instruction,
36-byte switch. They preserve one CR3 and the declared excluded architectural
state, retire both task contexts, and clear 32,768 stack bytes. Fourteen
scheduler tests within 151 kernel host tests and 28 hostile-control categories
covering 115 rejected cases pass. The exact kernel is 425,984 canonical bytes
in a 507,904-byte, 124-page image with 1,042 relocations and SHA-256
`AFED4AF858404D83CD77215C118F8478C88E91BDDC0F0B1ABAC3C9324B6ED602`.
This is a cooperative BSP foundation, not the complete N12 scheduler.
Interrupt timer/wakeup preemption, deferred work, live AP dispatch and
cross-CPU migration, ring-3/address-space switching, per-task FS/GS and full
xstate/debug/PMU ownership, general locks, target execution, N12 exit, release,
and production remain open. `production_ready=false`; the blocked external
move remains `N0-HW-KEY-ACQUIRE-001`, and the next owner-independent move is
`N12-SCHED-PREEMPT-001`.

Cycle 141 reconciliation (superseding current Cycle 140 implementation and
next-move values): governance and external-key state are unchanged, and no
key, signature, publication, privileged host probe, driver load, firmware
change, physical-media write, tag, release, or production promotion occurred.
The owner-independent `N8-SMP-MULTI-AP-001` move upgrades selector 14 to
PKSMP5 and closes only its bounded flag. On one exact four-vCPU
`SandyBridge,-avx` TCG topology, BSP APIC ID 0 owns three private AP runtimes
for APIC IDs 1, 2, and 3 with dynamic local masks `0x2`, `0x4`, and `0x8`.
One injected APIC-4 timeout after APs 1 and 2 start proves final-INIT parking,
alias revocation, complete scrub/release, and fresh allocation before retry.
The successful retry brings all three APs online simultaneously, records nine
accepted and three forged-capability-denied deliveries, twelve EOIs, three
one-page remote invalidations, and aggregate target/ack mask `0xE`. Reclaim is
rejected twice before all unique acknowledgements arrive; generation 1 then
retires, every AP quiesces and final-INIT parks, and all 96 runtime plus six
frame pages are scrubbed, read-verified, and released. Two exact 40-marker
runs, 30 hostile-control categories covering 243 rejected cases, and 137
kernel host tests pass; each resource lifecycle verifies 417,792 bytes. The
exact kernel is 409,600 canonical bytes in a 458,752-byte, 112-page image with
985 relocations and SHA-256
`8118ED5F7761B9D36A4A65EFF1BC1856C5182D5733CE95A8BEEB24D1C2435F8D`.
General topology/x2APIC, address-space-wide or concurrent-generation
shootdown, scheduler ownership, production capability authority, target
execution, N8/N9 exit, release, and production remain open.
`production_ready=false`; the blocked external move remains
`N0-HW-KEY-ACQUIRE-001`, and the next owner-independent move is
`N12-SCHED-001`.

Cycle 140 reconciliation (superseding current Cycle 139 implementation and
next-move values): governance and external-key state are unchanged, and no
key, signature, publication, privileged host probe, driver load, firmware
change, physical-media write, tag, release, or production promotion occurred.
The owner-independent `N9-SMP-SHOOTDOWN-001` move upgrades selector 14 to
PKSMP4 and closes only its bounded flag. On the frozen two-vCPU
`SandyBridge,-avx` TCG profile, one AP fills a translation for one page from
one AP-owned root, validates a checksum-bound generation-2 request, executes
exactly one linked-image-audited `INVLPG`, observes the replacement frame, and
acknowledges the exact generation, root, page, target mask, sequence, and
attempt. The BSP proves one offline-target timeout with same-attempt retry,
rejects premature reclaim, and releases the retired frame only after exact
acknowledgement. Two exact 40-marker runs, 25 hostile-control categories
covering 169 rejected cases, and 132 kernel host tests pass; all 32 runtime
pages plus both data frames, 139,264 bytes, are scrubbed, read-verified, and
released. The exact kernel is 409,600 canonical bytes in a 458,752-byte,
112-page image with 969 relocations and SHA-256
`95DDA27784DA944A9C0F5B04029255EDE4DE1BB0684A8EA10DCFC07E686B59A2`.
General multi-AP or address-space-wide shootdown, concurrent generations,
scheduler ownership, production capability authority, target execution,
N8/N9 exit, release, and production remain open. `production_ready=false`;
the blocked external move remains `N0-HW-KEY-ACQUIRE-001`, and the next
owner-independent move is `N8-SMP-MULTI-AP-001`.

Cycle 139 reconciliation (superseding only Cycle 138 closeout-integrity
metadata): main-integration preflight reproduced all 819 Cycle 138 tests but
found six stale bindings because the PBTRUST1 readiness writer had hashed CRLF
working bytes before Git stored LF. The same platform-default newline defect
was present in the new PKSMP3 writer and would have made its architecture
binding stale after checkout. Both writers now force LF and have byte-level
regression tests. PBTRUST1, PKLOAD6, PKREVAL1, PKXFER1, every affected
CPU/xstate/MSR/memory/SMP receipt, PKSMP3, and PooleBoot were requalified in
dependency order against committed-byte semantics. The exact kernel, bounded
PKSMP3 behavior, phase/subphase status, flags, gaps, and production boundary
do not advance. `production_ready=false`; no key, signature, firmware change,
physical-media write, tag, release, or production promotion occurred. The
blocked external move remains `N0-HW-KEY-ACQUIRE-001`; the next
owner-independent engineering move remains `N9-SMP-SHOOTDOWN-001`.

Cycle 138 reconciliation (superseding the historical Cycle 137 paragraph
below): governance and external-key state are unchanged. The selected
`hardware_fido2_ed25519_sk` device remains physically unavailable;
`N0-HW-KEY-ACQUIRE-001` remains the blocked external move; and no key,
signature, privileged-hardware, firmware, physical-media, publication,
release, or production-promotion action occurred. The owner-independent
`N8-SMP-IPI-001` move closes only its bounded PKSMP3 development transport.
On the frozen two-vCPU `SandyBridge,-avx` TCG profile, APIC ID 1 installs six
fixed vectors and acknowledges six allowlisted operation classes behind a
checksum-bound development capability. Two exact 39-marker runs observe six
accepted and four denied deliveries, ten EOIs, one bounded offline-APIC
timeout, panic latching, stop quiescence, final-INIT parking, post-execution
descriptor/xstate/APIC-table validation, capability and alias revocation, and
exact scrub/release of all 32 pages or 131,072 bytes. Eighteen hostile-control
categories cover 120 independently rejected cases and 130 kernel host tests
pass. The exact kernel is 409,600 canonical bytes in a 458,752-byte, 112-page
image with 959 relocations and SHA-256
`6B8A9C2C3EAC559E1D9CB5965800A1671DB8F487F149861300D4EDCB279B3A11`.
N8.6 is partial only. The capability is a fixed development token; the
shootdown operation records transport but performs zero TLB invalidations,
and call-function exposes no arbitrary callback. Real generation-bound remote
invalidation and deferred reclaim, production capability authority, scheduler
CPU ownership, multi-AP and live partial-start fault injection, target
hardware, N8/N9 exit, release, and production remain open. The next
owner-independent move is `N9-SMP-SHOOTDOWN-001`; PooleGlyph Phase 66 may
proceed in parallel without outranking N0-N9.

Cycle 137 reconciliation (superseding the historical Cycle 136 paragraph
below): governance and external-key state are unchanged. The selected
`hardware_fido2_ed25519_sk` device remains physically unavailable;
`N0-HW-KEY-ACQUIRE-001` remains the blocked external move; and no key,
signature, privileged-hardware, firmware, physical-media, publication,
release, or production-promotion action occurred. The owner-independent
`N8-SMP-PERCPU-RUNTIME-001` move closes only its bounded PKSMP2 lifecycle. On
the frozen two-vCPU `SandyBridge,-avx` TCG profile, APIC ID 1 loads one
processor-local GDT/TSS/IDT, guarded RSP0/IST1/IST2 stacks, x87/SSE owner
state, eight exception gates, and nineteen owned interrupt gates. The
32-page below-1-MiB transaction has thirteen mapped leaves, fourteen absent
guards, and one absent reserved page. The BSP verifies the hardware-set busy
TSS descriptor, all 27 gates, and one XSAVE/XRSTOR round trip before it
commands quiescence, final-INIT parks the AP, revokes all aliases, zeroes and
read-verifies 131,072 bytes, and releases all 32 pages. Two exact 42-marker
runs, 19 hostile-control categories covering 159 independently rejected
cases, and 122 kernel host tests pass. The exact kernel is 409,600 canonical
bytes in a 458,752-byte, 112-page image with 919 relocations and SHA-256
`214F32214494E632063238337551C355BFED150B9B49846DB8A927584B8E47F0`.
N8.5 remains partial. General SMP, multi-AP startup, capability-gated IPI
delivery and acknowledgement, TLB shootdown, scheduler CPU ownership, live
partial-start fault injection, target hardware, N8 exit, release, and
production remain open. The next owner-independent move is `N8-SMP-IPI-001`;
PooleGlyph Phase 66 may proceed in parallel without outranking N0-N9.

Cycle 136 reconciliation (superseding the historical Cycle 135 paragraph
below): governance and external-key state are unchanged. The selected
`hardware_fido2_ed25519_sk` device remains physically unavailable;
`N0-HW-KEY-ACQUIRE-001` remains the blocked external move; and no key,
signature, privileged-hardware, firmware, physical-media, publication,
release, or production-promotion action occurred. The owner-independent
`N8-SMP-FIRST-AP-001` move closes only its bounded PKSMP1 lifecycle. On a
two-vCPU qemu64 profile, PooleKernel selects APIC ID 1 from the retained MADT,
allocates fourteen pages below 1 MiB, installs four absent guards plus an RX
16-to-32-to-64-bit trampoline and guarded RW/NX stack/mailbox, performs one
INIT-SIPI-SIPI sequence, observes the AP online in long mode, commands stop,
validates quiescence and the dynamic mailbox checksum, issues a final INIT
park, revokes aliases, scrubs and verifies 57,344 bytes, and releases all
fourteen pages. Two exact 38-marker runs, 72 hostile controls, and 111 kernel
host tests pass. Live fault investigation found and fixed an RX-GDT accessed-
bit write that had caused an AP page fault and triple fault; every trampoline
descriptor is now pre-accessed. The exact kernel is 335,872 canonical bytes in
a 376,832-byte, 92-page image with 855 relocations and SHA-256
`6596CB332EB24813089F95A00AC979C892C47235943CB0E73E3979ED9901B725`.
N8.5 is partial only. General SMP, AP-local GDT/TSS/IDT/RSP0/IST/xstate and
interrupt state, multi-AP startup, IPIs, shootdown, live partial-start fault
injection, target hardware, N8 exit, release, and production remain open. The
next owner-independent move is `N8-SMP-PERCPU-RUNTIME-001`; PooleGlyph Phase 66
may proceed in parallel without outranking N0-N9.

Cycle 135 reconciliation (superseding the historical Cycle 134 paragraph
below): governance and external-key state are unchanged. The selected
`hardware_fido2_ed25519_sk` device remains physically unavailable;
`N0-HW-KEY-ACQUIRE-001` remains the blocked external move; and no key,
signature, privileged-hardware, firmware, physical-media, publication,
release, or production-promotion action occurred. The owner-independent
`N8-IRQ-001` move now has a bounded one-BSP implementation but remains open as
an encompassing flag. PKIRQ1 walks the retained validated MADT and HPET
descriptions, validates local-xAPIC identity, reserves 51 vectors, installs
guarded uncacheable LAPIC/HPET mappings, masks and restores the legacy PIC,
calibrates checked one-shot local-APIC time against HPET, and opens exactly
eight interrupt windows. Two exact 36-marker qemu64 runs deliver eight timer
interrupts and eight EOIs with zero APIC-error, spurious, or remaining ISR
bits; normal completion restores APIC, HPET, PIC, IA32_APIC_BASE, and MMIO
state. Ninety-nine kernel host tests and 58 hostile controls pass. The exact
kernel is 323,584 canonical bytes in a 364,544-byte, 89-page image with 812
relocations and SHA-256
`2ACD4A5EF30CA1A4A22711FD31E2A259A5C87D97BCE7FB1BF49A3488B3FC02B2`.
N8.1 and N8.3 are partial only. I/O APIC routing, MSI/MSI-X, complete time
services, panic-path rollback, first-AP startup, per-CPU state, IPIs, SMP
shootdown, target hardware, and N8 exit remain open. The next
owner-independent move is `N8-SMP-FIRST-AP-001`; PooleGlyph Phase 66 may
proceed in parallel without outranking N0-N9.

Cycle 134 reconciliation (superseding the historical Cycle 133 paragraph
below): governance and external-key state are unchanged. The selected
`hardware_fido2_ed25519_sk` device is still physically unavailable; no key or
signature exists; and `N0-HW-KEY-ACQUIRE-001` remains the blocked external
move. No cryptographic, privileged-hardware, firmware, physical-media,
publication, release, or production-promotion action occurred. The
owner-independent `N9-VM-DIRECT-MAP-001` move is complete only within its
bounded one-BSP scope. PKPMM7 reconstructs a generation-bound ownership
manifest from every free extent and active non-release-excluded allocation,
coalesces eleven exact write-back ranges, and excludes retained ownership.
PKVM3 derives and audits a 243-table topology before activation, maps 117,887
supervisor RW/NX pages, leaves 12,878 gap pages absent, and binds checksum
`0x341CF729ADB26B52`. Forged manifests, retained-hole admission, PWT/PCD drift,
partial writes, CR3 rollback, premature reuse, and absent or stale retirement
receipts fail closed. Three local invalidation receipts gate the data frame;
one exact root/generation/BSP/local-context-flush receipt gates table scrub and
release. Ninety-one kernel host tests and two exact 40-marker qemu64 runs pass
46 hostile controls with 367,474 physical table writes and 950,234 temporary-
PTE writes and invalidations. The exact kernel is 299,008 canonical bytes in a
339,968-byte, 83-page image with 729 relocations and SHA-256
`5B581CC1D1ABEB163D0984D12144CA5016C44B46A28B190A6DFCBDCDA689A255`.
N9 remains partial: PKVM3 deliberately rejects more than one active processor
until AP startup, interrupt delivery, and real inter-processor shootdown exist;
remote deferred reclaim, concurrent replacement, huge pages, PCID, COW, user
faults, pager IPC, heaps, broad MMIO/cache policy, pressure/OOM, target
hardware, and N9 exit remain open. `N8-IRQ-001` is the next owner-independent
move; PooleGlyph Phase 66 may proceed in parallel without outranking N0-N9.

Cycle 133 reconciliation (superseding the historical Cycle 132 paragraph
below): the governance and external-key state is unchanged. The selected
`hardware_fido2_ed25519_sk` device is still physically unavailable, no key or
signature exists, and `N0-HW-KEY-ACQUIRE-001` remains the blocked external
move. No cryptographic, privileged-hardware, firmware, physical-media,
publication, release, or production-promotion action occurred. The
owner-independent `N9-PMM-ACPI-CONSUMER-001` move is complete within its
bounded one-BSP scope. PBLIVE4 adds one canonical ACPI2 RSDP record; PKACPI1
validates RSDP/XSDT and exactly one APIC/FACP/HPET/MCFG table, copies and
read-verifies 600 source bytes into a 616-byte release-excluded scrubbed
snapshot, and supplies opaque evidence for the lifecycle transition.
PKPMM7 then admits eleven ACPI reclaimable pages under a second immutable
receipt while retaining the snapshot. Eighty-eight kernel host tests, two
exact 45-marker qemu64 runs, and 191 hostile controls pass. Closeout found and
fixed two real cross-stage contract defects: PKTRAP1 and PKVM2 still used a
retired 14-page stack constant after PooleBoot had moved to 32 pages. Both now
consume the shared 32-page geometry and their live profiles pass. The exact
kernel is 299,008 canonical bytes in a 339,968-byte, 83-page image with 693
relocations and SHA-256
`D9EF9B10B56BF779B155BD18DE55853874CCC032D2A3E5E7841B918F08CDE1F2`.
PKVM2 records 5,640 bootstrap writes and invalidations after the ACPI consumer
is included. N9 remains partial: AML, full platform discovery, a complete
generation-owned physical direct map, SMP shootdown/deferred reclaim,
interrupt-context and concurrent allocation, heaps, pager, pressure/OOM,
target hardware, and N9 exit remain open. The next owner-independent move is
`N9-VM-DIRECT-MAP-001`; PooleGlyph Phase 66 may proceed in parallel without
outranking N0-N9.

Historical Cycle 132 reconciliation: the seven-record native constitution, public/private boundary, architecture baseline, and conformance policy remain partial evidence. The historical completed owner response directs ADR-0003, ADR-0004, and all 38 Workstation v1 definitions while accepting zero measurements. Rooke Poole selected `hardware_fido2_ed25519_sk`, reported no available key, accepted no software-key substitution, and deferred public-key publication at that time; that receipt remains immutable. The selected physical key is still unavailable, the trust store remains empty, and no key was generated or used. Standing Authority Amendment V2 permits ordinary repository and fully gated clean-merge work. Later owner authorization approves compatible-key acquisition, key generation/use, public-key publication, signing, secrets use, privileged probes, driver loading, firmware changes, physical-media writes, tags/releases, and production promotion as operation categories, but it does not supply the key, owner presence, custody/recovery procedure, backups, recovery media, a separately identified safe target, qualified mechanisms, passing release evidence, or permission to bypass this charter. None of those operation categories were exercised in Cycle 132. `N0-HW-KEY-ACQUIRE-001` remains the blocked external move. PooleGlyph remains at the Phase 65/66 boundary with its existing generated-report change preserved and no policy authority inferred from metadata. Cycles 97-131 qualify bounded unsigned boot through PKPMM5 explicit ledger growth and one PKVM2 active-root transaction without production promotion. Cycle 132 closes only the bounded serial scope of `FLAG-N9-PMM-GROWTH-AUTOMATION-001`: selector-8 PKPMM6 checks exact post-operation demand before every automatic scrubbed allocate/free, reserves one allocation and four scrub-receipt slots for complete failed-growth rollback and retry, and grows all active ledgers through 4/8/15/29-page generations with final capacities 2048/256/2048/128/16. Three predecessors totaling 27 pages are revoked, zeroed, read-verified, and retired. The measured sequence records 121 pressure checks, eight triggers, three automatic growths, sixty successful cycles, and four soft fallbacks; a host test proves one hard rejection before physical reads/writes, ownership changes, or receipt commitment because the required 58-page next layout exceeds a bounded 32-page window. An independent Python oracle reconstructs all first-fit generations, alternating windows, retired holes, ownership, pressure counters, reclaim coalescing, and physical access counts. Two exact fresh-vars qemu64 runs emit 43 markers and pass 147 hostile controls plus 84 kernel host tests. They manage 117,911 source-usable and 129,160 final pages, keep eleven ACPI pages held, protect 833 loader pages, scrub and verify 11,462 pages and 46,948,352 bytes, and perform 5,869,568 physical writes, 5,870,592 reads, and 22,798 temporary-PTE writes and invalidations. Growth checksum `0xF7AD111CA266071D` binds the sequence. The retained-layout shift rebinds PKVM2 to 5,560 temporary writes and invalidations. Closeout also fixes and directly guards an identity split so PKMID1 and the live diagnostic both carry `PKBUILD1-CYCLE132-N9-PMM-GROWTH-AUTOMATION-001`. The dependent kernel identity is 278,528 canonical bytes, 319,488 image bytes, and 78 pages with 667 relocations and SHA-256 `CDF33067B2421550BB03A4796FF9A92AE54D40B2575188632BF2C208449B882E`. N9.1-N9.4 remain partial. Complete ACPI consumer integration, complete direct-map and SMP TLB policy, deferred reclaim, huge pages, PCID, COW, user faults, pager IPC, heaps/object caches, MMIO/cache qualification, interrupt-context/concurrent allocation, general pressure/OOM policy, target hardware, N9 exit, trust, persistent state, framebuffer, N4-N8, userspace, drivers, filesystems, PooleGlass, installer, signed ISO, and production gates remain open. `N9-PMM-ACPI-CONSUMER-001` is the next owner-independent move, while PooleGlyph Phase 66 may advance in parallel without outranking N0-N9.

The preceding Cycle 132-136 reconciliations are retained as historical
evidence; the Cycle 137 reconciliation at the head of this charter is
authoritative.

## 1. Objective

Build and deliver production-ready PooleOS as an original x86-64 UEFI operating system and reproducible, signed, bootable `.iso` image.

The production system consists of a Poole-authored `PooleBoot.efi`, a Poole-authored capability-based PooleKernel microkernel, native system servers and isolated driver domains, native storage/network/graphics/audio/user services, PooleGlyph with frozen PGB2/PGVM2 execution, canonical Poole Defect Calculus runtimes and bounded control lanes, and an accessible original Liquid Glass PooleGlass desktop and boot identity.

Linux, Debian, Buildroot, GRUB, Limine, systemd, and Linux userland are not the production foundation. They may be host tools, historical scaffolds, behavioral references, or comparison environments only. No artifact containing those production substitutions may satisfy a PooleOS native phase, boot, kernel, driver, media, or release gate.

## 2. Normative Requirements

The locked `PooleOS_From_Scratch_Master_Checklist.md` is the leaf-requirement authority:

- path: `sources/requirements/sha256/a8c94719faf9428c1f133010ba2603c0270c4e1efd7327af8eab9c8c362abb3d/PooleOS_From_Scratch_Master_Checklist.md`;
- SHA-256: `A8C94719FAF9428C1F133010BA2603C0270C4E1EFD7327AF8EAB9C8C362ABB3D`;
- 416,063 bytes;
- 10,512 lines;
- 171 sections numbered `000-170`;
- 8,998 checkbox lines;
- 8,996 implementation requirements after excluding the two generated-metadata checkbox lines.

Every source line is covered by the machine ledger. Every implementation requirement must be completed or explicitly dispositioned through a signed release-profile decision. No source line may be silently deleted, summarized away, or treated as completed merely because it is mapped into the plan.

Research additions in the coverage ledger are separately identified as `ADD-*`. They extend the master checklist without pretending to be original checklist text.

## 3. Native Architecture Contract

The production boot chain is:

```text
UEFI firmware
  -> signed PooleBoot.efi
  -> verified boot manifest
  -> verified PooleKernel and initial system/recovery bundles
  -> PooleKernel microkernel
  -> root resource manager and service supervisor
  -> isolated driver domains and native system servers
  -> PooleGlyph / PGB2 / PGVM2 and PDC services
  -> PooleGlass compositor, desktop, applications, installer, and recovery
```

PooleKernel is a minimal mechanism-only TCB. It owns privileged CPU entry, exceptions, interrupts, timers, SMP, address spaces, page ownership, threads, neutral scheduling, IPC, capabilities, IRQ/MMIO/I/O/DMA delegation, IOMMU enforcement, and minimal panic/audit foundations.

PooleKernel does not own general filesystems, networking, USB policy, storage protocols, GPU commands, audio policy, package management, authentication policy, PDC planning, PGVM2 execution, or desktop behavior. Those execute in capability-confined user-space domains. Production loadable kernel modules are prohibited in v1 unless a later reviewed ADR reopens the TCB and its assurance case.

No process receives ambient authority. Every file, endpoint, service, device, memory region, interrupt, DMA mapping, portal, PDC action, and policy operation is reached through explicit attenuable and revocable capabilities.

## 4. Initial Supported Scope

The initial target is:

- x86-64 long mode, little endian;
- UEFI only; no legacy BIOS requirement;
- GPT and a deterministic UEFI-bootable ISO/ESP layout;
- QEMU/OVMF Tier 0 reference profile;
- one exact Tier 1 physical profile based on the inventoried Gigabyte B650M GAMING PLUS WIFI, AMD Ryzen 7 9800X3D, NVIDIA RTX 5070 GOP path, Samsung 970 PRO NVMe, Realtek RTL8125 Ethernet, exact USB input, and selected audio path;
- permanent serial and GOP/software-rendered recovery;
- native accelerated RTX graphics as research until separately qualified;
- exact hardware identifiers and firmware revisions, not generic family claims.

The release profile decides whether Wi-Fi, Bluetooth, suspend, hibernation, AHCI, cameras, printers, scanners, USB4, Thunderbolt, advanced volume management, and other optional classes are required. Unsupported features must fail predictably and be published.

## 5. PooleGlyph Contract

Develop PooleGlyph machine language itself and PooleOS in tandem. PooleGlyph is not merely a dependency to import after it is finished: language design, frontend, semantic model, Core IR, assembly, package format, virtual machine, standard library, tools, conformance, optimization, security, release, and PooleOS integration are all governed production work.

At the start of each active cycle:

1. inspect the newest checkpoint, manifest, hashes, release notes, conformance evidence, and repository status;
2. preserve user changes and never rewrite the dirty generated conformance report merely to obtain a clean tree;
3. update the PooleGlyph source anchor and boundary records only from observed evidence;
4. keep parser-to-kernel/system promotion blocked until Phase 66 executable Core IR evidence is accepted;
5. never promote metadata-only declarations into executable or privileged authority.

Every tandem cycle must also:

- classify changes across source syntax, diagnostics, AST, semantics, Core IR, PGASM, PGB2, PGVM2, host ABI, policy, standard library, tools, conformance, performance, release, and IP boundaries;
- update a cross-repository compatibility matrix and identify required migrations before either repository consumes changed bytes;
- retain a public-safe deterministic reference path and independent validators for every canonical representation;
- keep experimental language features behind explicit version/profile gates and preserve stable compatibility windows;
- reject semantic, effect, resource, determinism, or authority drift introduced by optimization or private acceleration;
- advance Phase 66 first, followed by evidence-gated v0.5 stabilization, v0.6 AST-parser replacement, v0.7 modules/standard-library expansion, v0.8 process/runtime prototype, v0.9 replay/debug polish, and v1.0 stable public language.

Rooke Poole owns the PooleGlyph and PooleOS IP. Their source-available path does not make every implementation detail public: canonical specifications, formats, reference toolchain/runtime, and conformance evidence must remain sufficient for independent review, while private PooleMath methods and optimization strategy remain segregated and cannot substitute for public-safe reference behavior or PooleOS security enforcement.

PGB2 must become a canonical signed binary package format. PGVM2 must become a bounded deterministic virtual machine with independent verification, typed effects, explicit capabilities, quotas, deadlines, cancellation, cleanup, traps, replay, and version negotiation. PooleGlyph policy may narrow existing authority but cannot create kernel/device authority. Private or optimized compilers and backends must reproduce the declared reference semantics, effects, authority, and bounded outputs before promotion.

Recovery and safe mode must not require PooleGlyph.

## 6. PDC Contract

Preserve and extend the existing source-bound PDC evidence without expanding its claims.

Required work includes:

- canonical binary, planar, geometric, Q/P, probability, signed, and matrix contracts;
- exact source intake and finite verifier reproduction;
- representation, metamorphic, perturbation, and negative corpora;
- source-bound signed-dynamics benchmark reproduction;
- portable deterministic `libpdc` with stable native ABI;
- differential scalar, CPU, RAM, GPU, PooleOS, and bounded rescue paths;
- guarded promotion, invalidation, regret, fallback, and receipts;
- observation-first PDC system control, independent policy gate, lane-specific actuators, watchdog, rollback, and safe neutral controls.

PDC and Q/P results remain bounded to exact models, workloads, data, hardware, and tests. Q/P is a classical transform over measured or simulated fields, not unknown-state reconstruction. Finite empirical results do not establish universal physical, quantum, medical, legal, financial, security, or hardware behavior.

PDC must never control boot trust, signing roots, key storage, recovery availability, firmware flashing, undocumented voltage/clock operations, or hard thermal safety limits.

## 7. UI and Boot Identity Contract

PooleOS must provide an original coherent Liquid Glass visual system across desktop, shell, applications, installer, settings, permissions, diagnostics, and recovery.

The Cycle 151 design direction is `docs/pooleglass-design-system.md`, with initial
semantic tokens in `specs/pooleglass-design-tokens.json`. Its implementation
register is subordinate to the N0-N39 dependency order and this charter.
Do not mark native rendering, accessibility, animation, or performance complete
from a bitmap, design document, host preview, or a successful demo boot alone.

Required properties include:

- stable layouts and restrained effects appropriate to a production workstation;
- balanced palette and semantic status colors;
- keyboard, pointer, touch where supported, focus, text scaling, magnification, screen reader, captions/speech boundary, braille boundary, high contrast, and color-vision support;
- reduced transparency, reduced motion, software rendering, safe graphics, and non-composited recovery;
- frame time, startup, memory, CPU, GPU, thermal, and power budgets;
- trusted UI for authentication, permissions, secrets, updates, destructive actions, and recovery;
- no visual effect that obscures errors, security state, destructive consequences, or focus;
- compositor/asset/shader/native-GPU failure must not prevent serial/GOP recovery.

The boot identity consists of a static firmware-safe PooleOS mark and a later early-userspace animated Liquid Glass transition. Animation is presentation only. Signed machine-readable stage markers prove boot progress independently. Reduced-motion and static fallback are mandatory.

## 8. Security, Recovery, and Update Contract

The project must define and test:

- offline and intermediate signing roots, development-key isolation, rotation, revocation, expiry, compromise, and release ceremony;
- UEFI PK/KEK/db/dbx state, Secure Boot, artifact verification, minimum secure version, measured boot, TPM event log, and recovery keys;
- capability attenuation, derivation, transfer, revocation, generation safety, quotas, teardown, and no ambient authority;
- W^X, NX, SMEP, SMAP, control-flow and transient-execution mitigations tied to exact CPU/microcode;
- IOMMU and interrupt-remapping confinement before bus mastering;
- reviewed cryptography, entropy health, CSPRNG readiness, secret stores, trust stores, MAC, and privacy defaults;
- signed packages and compromise-resilient update roles with threshold keys, expiry, rollback, freeze, and mix-and-match protection;
- immutable A/B system slots, bounded boot attempts, previous-known-good, safe mode, recovery, installer interruption handling, backup, and restore;
- recovery that remains simpler and less dependent than normal operation.

Any unresolved data-loss, privilege, boot-loop, signing, rollback, firmware, recovery, secret, or DMA escape defect is stop-ship.

## 9. Build and Supply-Chain Contract

Release-critical builds must be hermetic, offline where declared, source-controlled, dependency-complete, and reproducible.

The release chain must bind:

- exact source revision and tree hash;
- compiler, assembler, linker, sysroot, host tools, configuration, environment, and flags;
- generated ABI and standards data;
- third-party source, patches, firmware, microcode, fonts, Unicode/timezone/root-certificate data, and licenses;
- PooleBoot, PooleKernel, every server/driver/library/application, PooleGlyph/PGB2/PGVM2, PDC, UI assets, system/recovery images, and ISO;
- tests, raw failures, fuzz corpora, power-cut images, hardware profile, benchmark data, SBOM, provenance, signatures, and approvals.

Use SPDX 3.0.1-compatible SBOM, SLSA 1.2-compatible provenance, and in-toto-style signed supply-chain links or a reviewed equivalent. Verification must be independent from the build that produced the artifact.

Two clean independent builders must reproduce declared unsigned artifacts and ISO bytes. Any unavoidable signing nondeterminism must be specified and bound so the exact signed distributed bytes remain traceable to reproducible unsigned inputs.

## 10. Evidence and Claim Discipline

Never convert a fixture, mockup, schema pass, static proof, model, host test, simulator, Buildroot image, ISO filename, one QEMU boot, one physical boot, visual animation, or finite benchmark into a broader production claim.

For every promoted requirement:

- retain specification/ADR, source revision, implementation, positive and hostile tests, raw outputs, environment, hardware/firmware identity, toolchain, hashes, recovery evidence, documentation, and signed receipt;
- bind evidence to the exact input and output artifacts;
- preserve failed runs and negative results;
- distinguish normative conformance, tested behavior, observed behavior, hypothesis, research, and unsupported behavior;
- require independent reproduction where the Build Plan or release profile says so.

## 11. Standing Execution Authority

Standing Authority Amendment V2 authorizes Codex to:

- read, edit, build, test, document, commit, branch, push, and manage pull requests, issues, labels, milestones, project metadata, and draft release material needed by this charter;
- install hash-pinned non-administrative tools under a dedicated PooleOS tools directory without changing global `PATH` or system-wide configuration, while recording source, version, hash, license, and provenance;
- run read-only unprivileged hardware and operating-system inventory commands;
- create or strengthen GitHub Actions, rulesets, required checks, branch protections, vulnerability reporting, and repository security controls;
- mark a Codex-authored draft PR ready and merge it, including into `main`, only when the exact candidate passes the canonical qualification suite, publication-boundary scan, release gate, all configured required GitHub checks, clean-merge check, and review gates, with no blocking review request or unresolved thread;
- merge into non-default `agent/*` integration branches and delete only Codex-created remote `agent/*` branches after merge.

Codex may not force-push, bypass protections, rewrite shared history, delete `main` or a user-created branch, weaken governance, alter repository visibility/ownership/billing, expose secrets, or treat an ordinary permitted merge as production promotion. A later Cycle 118 owner statement, reaffirmed before Cycle 124 closeout, supplies explicit categorical authorization to acquire a compatible FIDO2 key; generate/use the selected key; publish its public key; sign; use secrets without exposing them; run privileged probes; load drivers; change firmware; write physical media; publish tags/releases; and promote production. These are permissions, not evidence or instructions to act immediately. Key work still requires the selected physical device, owner presence, reviewed custody and recovery, exact fingerprint review, and no private-material disclosure. Privileged, driver, firmware, disk, media, boot, TPM, device, and installation work still requires a bounded reviewed mechanism, verified backups and recovery media where applicable, a separately identified safe target, stop conditions, and retained evidence. Tag/release publication or production promotion still requires every charter release gate to pass for the exact bytes. No newly authorized cryptographic, privileged-hardware, mutating, publication, release, or promotion action occurred through Cycle 137; Cycles 132-137 used only host builds and non-promoting virtual-machine execution. Historical owner packets and receipts remain immutable records of the authority that existed when they were created.

## 12. Per-Turn Next-Best-Move Loop

Every active goal turn must:

1. Read this charter, the Build Plan, machine roadmap, checklist coverage ledger, current flags, release gaps, latest cycle log, and previous handoff.
2. Reinspect the live PooleGlyph checkpoint folder and repository state, then decide whether the selected move belongs in PooleOS, PooleGlyph, or a coordinated cross-repository change.
3. Confirm the locked master checklist and coverage manifest still match their expected hashes/counts.
4. Determine the earliest unmet dependency and highest-risk unblocked native requirement.
5. Select the smallest proof-strengthening move that advances the native critical path without relying on an unfrozen downstream interface.
6. State the selected phase, subphase, requirement IDs, entry evidence, expected artifact, negative cases, and exit criterion.
7. Implement in the smallest ownership boundary and preserve unrelated user changes.
8. Run proportionate unit, integration, malformed, adversarial, concurrency, fault, recovery, and regression tests.
9. Validate all touched schemas/artifacts and rerun the checklist coverage guard when source or mapping changes.
10. Update the Build Plan, machine roadmap, phase/subphase status, item dispositions, implementation flags, gaps, risks, evidence hashes, release gate, cycle log, README, and handoff.
11. Record honest non-claims and any newly discovered required work. Never hide a blocker to preserve a schedule or phase count.
12. End with the exact next dependency-ordered move.

Architecture work N0-N5 outranks downstream optimization while those foundations remain unclosed. PDC signed dynamics and the PooleGlyph machine-language lane beginning with Phase 66 may proceed in parallel but cannot substitute for native boot progress.

## 13. Phase Contract

The authoritative completion range is `N0-N39`.

- N0-N4 establish constitution, governance, hardware, toolchain, emulation, reference devices, and formal models.
- N5-N11 establish PooleBoot, boot trust, CPU, interrupts/time/SMP, memory, platform discovery, and IOMMU.
- N12-N16 establish scheduling, capability objects, IPC/isolation, security, and user-space driver domains.
- N17-N24 establish storage, input, PooleFS, user ABI, services, sessions, update/recovery, and power/firmware health.
- N25-N30 establish networking, graphics, audio, desktop/accessibility, and application platform.
- N31-N35 establish observability, PDC, PooleGlyph, reliability, watchdogs, and fault containment.
- N36-N39 establish full verification, supply chain, qualification, and exact signed native ISO release.

A phase may be marked complete only when every mapped required item and applicable research addition passes its Build Plan exit gate with immutable evidence.

## 14. Bootable ISO Contract

The production `.iso` is UEFI-native and PooleOS-owned. It must define and verify:

- deterministic El Torito EFI/GPT/ESP layout and volume metadata;
- signed PooleBoot, manifest, PooleKernel, initial system, recovery, native drivers/services, PooleGlyph/PGB2/PGVM2, PDC, PooleGlass, installer, packages, and evidence;
- architecture-conformance rejection of Linux kernels, Buildroot/Debian rootfs, GRUB/Limine, systemd, and undeclared host artifacts;
- exact root/system/recovery continuity and boot-stage hashes;
- normal, safe, previous-known-good, diagnostic, live, installer, recovery, shutdown, and reboot paths;
- clean QEMU/OVMF matrix and exact Tier 1 physical-media boots;
- damaged media, unsupported hardware, low memory, missing devices, failed drivers/services, failed update, rollback, and recovery;
- independent reproducibility, signatures, checksums, SBOM, provenance, source, support matrix, limitations, and release receipt;
- proof that tested and signed ISO bytes are the distributed ISO bytes.

## 15. Completion Gate

Do not mark this goal complete until all of the following are true for the exact supported release profile:

- all 8,996 implementation requirements are complete or explicitly excluded by signed scope disposition;
- all applicable `ADD-*` requirements are complete;
- all required N0-N39 phases and subphases are complete;
- PooleOS is source-controlled and every release byte has provenance and licensing records;
- PooleBoot and PooleKernel are original, reviewed, reproducible, signed native components;
- capability, IPC, memory, scheduler, IOMMU, driver isolation, storage, PooleFS, network, security, update, recovery, and fault-containment gates pass;
- the promoted PooleGlyph revision, Phase 66 boundary, source/semantic/Core IR/PGASM/PGB2/PGVM2/host-ABI contracts, compatibility profile, public/private IP boundary, independent conformance, and native capability enforcement are accepted for the release profile;
- PDC reference and native/backends agree within declared contracts and bounded control lanes pass rollback/watchdog gates;
- accessible PooleGlass Liquid Glass, software-rendered fallback, static/animated boot identity, installer, and recovery pass;
- external review closes all critical and high findings;
- two clean independent builders reproduce declared bytes;
- the exact signed ISO boots and operates from clean media in every supported QEMU and physical hardware profile;
- live/install/recovery/update/rollback/power-loss/soak/security/accessibility/support tests pass;
- exact source, SBOM, provenance, signatures, hardware matrix, limitations, recovery, support, and incident records ship;
- no `STOP_SHIP` flag is open;
- the signed release receipt sets `production_ready=true` for one exact ISO SHA-256.

Until then, every artifact is explicitly a research build, developer preview, lab image, alpha, beta, or release candidate. The goal persists across cycles and must not be marked complete merely because one milestone, phase, boot, UI demonstration, benchmark, or ISO assembly succeeds.
