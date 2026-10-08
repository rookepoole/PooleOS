# Native User-Space Integration ISO

Status: implementation started, Cycle 255, 2026-10-08. No new ISO exists yet.
Owner direction: pursue a usable native user-space integration ISO, then continue
the complete robust microkernel. This is an intermediate milestone, not a
replacement for the Production Goal Charter or its N0-N39 completion gates.

## Scope And Boundaries

- Original PooleBoot and PooleKernel, UEFI, QEMU/OVMF only initially.
- One BSP CPU first; no unqualified physical hardware, installer, persistence,
  networking, host filesystem share, physical-media writes, or device passthrough.
- Boot into an actual isolated user-space session. A captured screen, kernel
  command interpreter, scripted transcript, or another splash is not acceptance.
- Init, console policy, shell, application loading policy, bundled-file service,
  and applications run in user space. Kernel mechanisms enforce their authority.
- A separately labeled unsigned development profile may opt into execution.
  Ordinary PooleBoot trust denial and all production signing gates remain intact.
- No production phase closes because this narrower preview works. No branch
  merges without the existing exact-candidate gates. No release is implied.
- PooleGlyph/PDC native services and PooleGlass remain required later. They do not
  gate the first native shell; no metadata declaration acquires kernel authority.

The owner has prioritized this bounded integration lane. N0-N5 production gaps
remain open and visible; the lane must repair any boot/memory prerequisite it
actually depends on. It does not bypass production architecture or governance.

## Deliverable Acceptance

On a freshly booted optical ISO, a user can operate a native shell, list and read
bundled files, start and stop two actual user-mode applications, observe their
progress, and trigger an application fault while the other application and shell
continue running. Displayed task state comes from real kernel/service state.

The acceptance script must exercise user input, not print a predetermined success
sequence. Retain serial diagnostics, exact ISO/source/tool hashes, raw failures,
and fresh guest-run records. Include repeated clean boots, a bounded sustained
session, invalid requests, resource exhaustion, cancellation, and recovery.
The time/run bounds must be frozen before live qualification, not chosen after
seeing failures. Ship explicit limitations and a documented VM launch command.

## Dependency-Ordered Stages

| Stage | Build Plan Binding | Exit Criterion | Current State |
| --- | --- | --- | --- |
| USI-1 User entry and containment | N7-N9, N12, N13.1-4, N13.6 | Real ring-3 entry, controlled kernel entry/return, private address spaces, timer recovery, and a contained application fault | Cycle249:17 native survival cases, bounded lost-sample retirement and cleanup retry; general admission/quarantine, physical clock, broader watchdog and stack/exception qualification remain |
| USI-2 Capabilities and IPC | N13.5-7, N14.1-3, N14.5-7 | Two isolated tasks communicate only through granted handles; stale handles, oversized messages, cancellation, dead peers, and quota failures reject safely | Cycle255: continuous owned clock across actual request lifetimes and idle; prior completion/cancel/wait/take and service death preserved. Request deadline expiry, transactional admission and sustained budgets remain |
| USI-3 Runtime and services | N16, N20, N21 | Real init, executable loading, service startup/restart, and a confined console/input service | Not started |
| USI-4 Shell and applications | N18, N19, N22, N30 | Interactive user-space shell, read-only bundled files, two applications, observable fault containment | Not started |
| USI-5 Optical integration | N5, N36, N38, N39 | Corrected ISO packaging, fresh end-to-end guest interaction, sustained-session and fault/recovery tests | Not started |

### Immediate Next Move

Current: [Cycle255 continuous clock evidence](checkpoints/cycle255-continuous-service-clock.md).
The owned HPET epoch now spans actual dispatches and idle, with verified teardown.
Bind request deadlines to it, including expiry while all tasks block and poisoned
epoch handling; then transactional admission and sustained service budgets.
Per-dispatch CPU ticks remain distinct from the service clock.
The197-page kernel has208 reserved pages;36-page guarded stack remains unchanged.
Migrate old product receipts and replay exact-candidate canonical gates before main.
Then USI-3 init/confined console/input, USI-4 shell/files/two apps, USI-5 optical ISO.
The completed substeps below are retained as history, not the current next action.

N13-CAPABILITY-IPC-001 continues USI-2 without declaring USI-1 complete:

1. Add original kernel-owned typed objects and per-task capability tables. Resolve
   handles against authenticated caller identity; reject forged/stale generations,
   wrong object types, rights amplification and generation wrap. Bound allocation
   and handle counts; define destruction and revocation ownership before reuse.
   Cycle250 implements endpoint-only tables, rights and generations with trusted
   bootstrap delegation and object-wide destruction. Derivation-tree revocation,
   user delegation, audit and general object classes remain open.
2. Add bounded endpoint messages with explicit ABI versions, lengths and rights.
   Copy from owned user memory before publishing a message; define failure-atomic
   queue/charge updates. Do not treat a raw task ID or address as authority.
   Cycle250 implements64-byte/four-message FIFOs with copy-in snapshot and
   queue-preserving output faults. Receive may partially write user memory.
3. Connect wait/wakeup, cancellation, dead-peer cleanup and reply ownership to the
   existing scheduler and retained task lifecycle. Test quota/queue exhaustion,
   duplicate wakeups, revoked endpoints and failure at every mutation boundary.
   Cycle251 implements identity-bound advisory readiness waits, atomic scheduler
   transitions and mandatory retirement hooks. Native3 waits/2 readiness wakes/
   1 cancellation pass; host dead-owner/revocation and failed-completion/revoke
   retry do not replace native death-path qualification. RPC reply tokens remain.
4. Execute an actual request/reply exchange between isolated CPL3 tasks, with
   native denied-handle/oversize/dead-peer controls and surviving-peer progress.
   Preserve all17 containment cases and ordinary boot denial. Broader capability
   transfer, shared-memory IPC, concurrency and full N14 qualification stay explicit.
   Cycle250 proves a real transformed request/reply and native invalid-handle,
   rights, oversize and input-fault denial. Native stale/dead-peer/exhaustion and
   output-fault controls remain; host coverage is not their native replacement.
5. Only then build USI-3 services and USI-4 interaction. Optical packaging must
   boot the actual usable session and pass the acceptance script above.

Cycle252 evidence is [here](checkpoints/cycle252-native-ipc-pressure-lifecycle.md), with
[IPC invariants and gaps](native-capability-ipc.md). The native controls listed above
now have five persistent-slot lifetimes, four enrolled-owner death/recovery paths,
queue-full/writable-wait and four-byte output-fault retry evidence. Pending-wait
termination is implemented. Cycle253 adds sender identity and one-use reply ownership
with a sixth persistent-slot lifetime: [evidence](checkpoints/cycle253-native-ipc-reply-authority.md).
Cycle254 completes bounded request/cancellation ownership and caller notification
on service death or explicit discard. Cycle255 supplies the continuous clock.
Next in step3: epoch-bound request expiry, then transactional admission and
sustained budgets for services.
General quotas, arbitrary revocation races and supervision remain unfinished.
Cycle249 evidence is [here](checkpoints/cycle249-unknown-runtime-recovery.md).
Its sample-loss injection is not a real hardware-clock failure. Keep that limit,
general stack bounds, persistent audit/quarantine and the current197-page product
contract migration visible under FLAG-N13-USERSPACE-ISO-001.

### USI-1 Substeps

1. Admit an owned inactive user image with RX code, RW/NX stack, unmapped guards,
   no hidden aliases, and a bounded initial privilege-return frame. Cycle 234.
2. Bind the kernel half to the owned root using existing memory mechanisms;
   preserve supervisor-only mappings, lifetime holds and invalidation discipline.
   Cycle 235 implements an owned inactive attachment and guarded entry stack.
   Cycle 237 proves activation/restoration at CPL0 with a bounded original-root
   identity adapter, no added temporary aliases, scrubbed data and full release.
   The adapter proves identity and permissions before each physical access and
   is never used while the candidate root is active. Cycle 238 adds guarded UC
   timer mappings and proves three interrupt/EOI pairs under the candidate root,
   verified shutdown and retained-on-failure retirement. This uses the existing
   kernel IST, not the future task-private RSP0/entry path.
3. Install user descriptors and a valid kernel-entry stack/TSS; add a minimal
   reviewed IRETQ entry/return path. Clear non-argument registers and initialize
   segment/base, debug, and supported extended state without leaking kernel data.
4. Enter one static user task in a separately gated development profile and
   prove the actual CPL, kernel return, and denied privileged operations in QEMU.
   Cycle239 completes this bounded probe and substep3 for legacy x87/SSE only:
   seven ordered faults on the private RSP0 stack, sanitized state, denied
   privileged operations, kernel return, descriptor detach and complete release.
   Cycle240 extends the probe with three timer preemptions of a spinning payload,
   two state-preserving resumes and forced kernel return. General task admission
   and peer scheduling remain unfinished under substeps5-7.
5. Add a narrow versioned syscall ABI and hardened user copying with recoverable
   faults, bounded lengths, checked arithmetic and stable ownership. Do not use
   raw user pointers or numeric addresses as authority.
   Cycle241 proves12 actual SYSCALLs with checked IRETQ and three exact copy
   faults per guest. Input failure is destination-atomic; output failure reports
   its committed prefix. Ownership is exclusive BSP/IF0 with fixed mappings,
   not general pinning. Production ABI freeze, SMAP CPU coverage, concurrent
   mapping, asynchronous entry and syscall/timer concurrency remain open.
6. Connect private address spaces to scheduler execution/lifetime holds. Support
   preemption, exit, cleanup and accounting for the declared single-CPU profile.
   Cycle242 implements owned sequential exit/fault termination, scoped-generation
   task identity, status/syscall accounting, retained-on-failure cleanup and reap.
   This is not a scheduler connection. Full spawn rollback, nonfatal dispatch
   budget handling and general syscall stack admission remain necessary.
7. Contain user #PF/#GP/#UD while treating kernel faults as kernel faults; prove
   that a faulty or spinning task cannot prevent supervisor recovery or peers.
   Cycle240 proves healthy-timer recovery for one fixed task only. Failed timer
   delivery is externally guest-bounded, not covered by a native independent
   watchdog; general fault/peer progress and device-failure recovery remain open.
   Cycle242 separately terminates fixed #UD/#GP/#PF tasks without resuming their
   frames, then restores the root and frees memory. The new fixed tasks have no
   armed timer, and surviving-peer progress is not established.

Cycle243 connects substeps6-7 to PKSCHED1: two actual private-root tasks, timer
suspension/resumption, cancellation, task-only call-limit termination and proven
survivor progress. The syscall stack may move within its owned page. Historical
statements above describe each earlier cycle, not current completion. Remaining
USI-1 work now follows [PKUSER13 limits](native-user-runtime-accounting.md):
Cycle245 verifies bounded construction rollback and Cycle246 adds bounded owned
timer draining, exact cleanup quarantine/retry and surviving-peer progress.
Cycle247 adds retained, exactly-once accounting for all authenticated returned
peer quanta, including terminal and failed-cleanup samples. The arm-to-event
charge includes in-quantum kernel overhead, not just user instructions.
Cycle248 adds a separate HPET MSI deadline for local-timer suppression, with
owned stop/drain/restore and positively charged terminal recovery. It requires
working HPET clock/APIC delivery/IF, not NMI recovery or general hardware coverage.
General spawn admission, persistent quarantine/partial timer configuration and
slot-commit recovery, complete stack/exception/selector qualification, arbitrary
timer races, independent missing-delivery recovery, unknown-measurement emergency
recovery and coherent physical clock sampling remain. Missing measurements stay
unknown with resources retained; legacy diagnostic paths remain unaccounted.
General admission stays disabled until these contracts are qualified.

No unsafe user execution is permitted just because an admission function passes.
NX/write protection, kernel stack ownership, correct interrupt return, privilege
state, CPU time limits, and supported architectural-state isolation are entry
requirements, not items deferred until after the demo.

### USI-2 Through USI-5 Substeps

1. Implement generation-safe object/endpoint handles and rights attenuation.
   Test forged, cross-task, revoked, duplicate and stale handles before services.
2. Implement bounded IPC with reply identity, copy limits, cancellation/deadlines,
   peer death, cleanup and per-task resource budgets.
3. Load bounded native user executables from a declared development initial
   bundle. Validate segment ranges, overlap, W^X, entry, stack and resource bounds.
   Initial bundle declarations alone are not proof of service execution.
4. Start init and a console service with explicit grants. Serial interaction may
   come first, but label it honestly; guest keyboard/display integration follows
   through confined services. General drivers and shell policy stay out of ring 0.
5. Provide a read-only bundled-file service and small user runtime. Implement
   shell commands for help, task inspection, file listing/reading, launch, stop,
   and explicit fault testing. Do not present host files as guest storage.
6. Run two applications with distinct address spaces and bounded workloads.
   Prove progress survives one app's exit, invalid access, and forced termination.
7. Rebuild the optical image from corrected media tools and the exact integration
   products. Preserve the older demo separately; its receipts cannot qualify this
   image. Test the ISO itself, not only a disk image or host library.

## Cycle 249 Unknown Runtime Recovery

[Checkpoint](checkpoints/cycle249-unknown-runtime-recovery.md) records two fresh
61-marker guests with17 survival cases. The new case records missing time as
unknown, forbids requeue/zero charging, retains the exact cleanup owner and lets
a healthy peer continue after retirement.545 Rust executions and40 oracle tests
pass. The stack-guard failure and sibling-call repair are retained. Next: USI-2
capability/IPC groundwork, without closing general USI-1 or production gaps.

## Historical Cycle 248 Native HPET Backup Recovery

[Checkpoint](checkpoints/cycle248-native-hpet-backup.md) records two fresh60-marker
guests with16 survival cases,156 settled dispatches,30 terminal samples and one
HPET backup recovery each. The local timer mask is read back; a genuine spinning
user task terminates through vector65 and its peer finishes. Both sources stop,
drain and restore before detach.539 Rust executions and38 parser tests pass.
Next: unknown-runtime quarantine recovery, then USI-2 capability IPC. Physical
clocks, non-MSI/I/O-APIC fallback, NMI and simultaneous pending-source qualification
remain separately required. No interactive ISO or general watchdog claim follows.

## Historical Cycle 247 Native Runtime Accounting

[Checkpoint](checkpoints/cycle247-native-runtime-accounting.md) records two fresh
58-marker guests. Each settles148 dispatches,28 terminal samples and one failed-
cleanup quantum;148 duplicate charges reject. Scheduler totals match retained
slot and independent event-class totals. Existing15 survival cases,307 root
writes,538 released pages,247 scrubbed data pages and unsigned denial remain.
525 Rust executions and36 Python oracle tests pass. No interactive ISO yet.
Next: independent missing-IRQ and unknown-runtime recovery, then capability IPC.
This is bounded one-BSP peer accounting, not complete production CPU accounting.

## Historical Cycle 246 Owned Timer Shutdown

[Checkpoint](checkpoints/cycle246-owned-timer-shutdown.md) records two fresh
57-marker guests with15 survival cases,148 dispatches,119 accepted preemptions
and307 root writes each. Pending/late one-shot work drains only through an owned
kernel window; injected cleanup failure retains13 pages until successful retry.
The healthy peer continues to exit84.538 pages are released and247 data pages
scrubbed; ordinary unsigned boot still denies execution. Next: terminal and
failed-cleanup quantum accounting, independent missing-IRQ recovery, then IPC.
The consumed failed-cleanup quantum is not yet included in the119 accepted
preemptions. No broad timer-race or complete-accounting claim follows.

## Historical Cycle 245 Transactional Construction

[Checkpoint](checkpoints/cycle245-transactional-user-construction.md) records
two fresh55-marker guests. Each rolls back one real quota failure and six
post-write construction failures, retries six cleanup failures, scrubs/releases
83 construction pages and resumes the healthy peer to exit84. Existing14
containment rounds remain passing. Totals:512 released pages,235 scrubbed data
pages and291 root writes. Quotas/stack guards stay unchanged after repairing the
new constructor's stack overflow. Next: timer shutdown/accounting, then IPC.
There is no interactive session or new ISO yet.

## Historical Cycle 244 Invalid User State Containment

[Checkpoint](checkpoints/cycle244-user-state-containment.md) records two fresh
54-marker guests, each140 dispatches/113 preemptions/14 survival cases. Invalid
RIP/RSP/RFLAGS stop only the offender. New native exception vectors0,1,3 are
contained; the stack-access case records TCG's #GP and does not qualify #SS.
All429 task pages are released,198 data pages scrubbed and291 root writes checked.
Ordinary unsigned boot still denies execution. The next dependency is transactional
spawn rollback, then timer recovery/accounting, capability IPC and services.

## Historical Cycle 243 Preemptive Peer Scheduling

[Checkpoint](checkpoints/cycle243-native-user-peer-scheduling.md) records two
fresh44-marker guests, each40 peer dispatches/33 preemptions/four survival cases,
91 actual root writes,169 released pages and78 scrubbed data pages. GPR/legacy FP
state survives switching. Ordinary denial passes. This is usable kernel machinery,
not an interactive user session or optical ISO. Remaining USI-1 containment work
precedes general application admission; capability IPC and services follow.

## Historical Cycle 242 Owned Task Termination

[Checkpoint](checkpoints/cycle242-user-task-termination.md) and
[task lifecycle](native-task-lifecycle.md) bind four sequential task generations,
Exit42, fatal user faults, restart/stale-ID denial and actual memory reclamation.
Two fresh40-marker guests plus ordinary unsigned-boot denial pass. Across the
original experiment and four new tasks, each guest makes ten actual root writes,
releases65 pages and scrubs30 data pages. No actual user-space session or ISO is
claimed. Next: preemptive private-root peers with failure containment.

## Historical Cycle 241 Live System Calls

[Checkpoint](checkpoints/cycle241-native-syscall-usercopy.md) and
[PSABI1 development subset](native-syscall-abi.md) bind the actual instructions,
return frame, errors, copy semantics, fault fixups and cleanup. The12-call count
is the fixed test workload, not the production application contract. Version and
self-memory-copy operations grant no kernel object or endpoint authority.

Two fresh36-marker probes each reject89 evidence mutations, finish the original
seven privilege faults,12 calls/three copy faults, completion trap, three user
timer interrupts/two resumes and full task-memory retirement. The ordinary
unsigned-boot control still denies entry. No general SMAP/SMP/NMI qualification,
task exit, fault termination, peer scheduler, service or ISO exists from this
cycle. These are next dependencies, not omitted preview requirements.

## Cycle 234 Implementation

`native/kernel/src/user_entry.rs` implements `PKUSER1` admission for the existing
PKVM1 four-table inactive address space, with exactly one code and one stack
page. It reads all 2,048 table entries, cross-checks PMM ownership and mapping
identity, rejects other mappings and reserved/unsupported flags, and constructs
an initial five-word IRETQ frame with fixed unprivileged selectors and flags.
Hardware accessed/dirty bookkeeping is tolerated only in the declared positions.

The user descriptor constants reserve GDT indices 5 and 6 after the existing
two-slot TSS. They are not installed. The existing live GDT, trap handlers, CR3
switch paths and boot scenario selection are unchanged. A returned snapshot is
not a capability and cannot authorize execution after state changes.

The first image is intentionally smaller than a shell. General ELF segments,
multiple stack/data pages, kernel-half attachment, live CPU transition, fault
containment, capabilities, IPC and services are still required. Do not turn this
host-tested library into an assertion that ring 3 has run.

Qualification command:

```powershell
python -B tools/qualify_native_user_entry.py --work-dir outputs/a-new-user-entry-run
```

## Cycle240 Live Integration

[User Timer Preemption Evidence](checkpoints/cycle240-user-timer-preemption.md)
records two fresh35-marker guests and ordinary denial. Each spinning task makes
progress between three actual timer interrupts. Fourteen GPRs and legacy FP
state survive the two resumes; the third interrupt returns to the kernel.
Device shutdown precedes private-stack descriptor detachment and page release.
Next: versioned bounded syscall and recoverable user-copy mechanisms, then
task exit/peer scheduling and capability IPC. No interactive ISO exists yet.

## Historical Cycle239 Live Integration

[Bounded User Entry Evidence](checkpoints/cycle239-bounded-user-entry.md) records
two real CPL3 fault/return/cleanup probes. This also fixes shared VM retirement
of CPU-accessed page entries. Next is bounded timer recovery from CPL3, then a
versioned syscall/user-copy ABI and capability IPC. No interactive session or
optical ISO is claimed. The full robust microkernel remains the production goal.

## Historical Cycle 238 Live Integration

[Owned Root Timer Evidence](checkpoints/cycle238-owned-root-timer.md) records two
fresh native CPL0 root/timer probes and ordinary denial. Each probe receives
three timer interrupts under its own CR3, then verifies quiescence before root
restoration and task-page release. ACPI snapshot ownership is counted separately.
The timer has native poll/time bounds; stopped-clock or missing-delivery paths
cannot wait forever. Host driver-failure tests enforce memory quarantine, but
these failures have not yet been injected into the guest hardware adapter.

## Historical Cycle 237 Live Integration

[Live User Root Evidence](checkpoints/cycle237-live-user-root.md) records two
fresh native CPL0 probes and one default-denial boot, current source hashes,
host/freestanding checks, hostile marker controls and retained failures.
Selector 23 is development-only and excludes all other development scenarios.
That historical version does not execute its static user UD2 payload, enter ring 3, enable interrupts,
run user fault recovery or build an optical ISO.

To include live execution in a new bounded qualification:

```powershell
python -B tools/qualify_native_user_entry.py --work-dir outputs/new-user-host --live-work-dir outputs/new-user-guests --out outputs/new-user-receipt.json
```

Both directories must be new. This focused receipt is not the canonical
production qualification. Firmware identity mappings are an explicit bootstrap
precondition, not inherited task authority or a general-purpose direct map.

## Follow-On Microkernel Work

Historical Cycle 236 evidence: [User Root CPU Lifecycle](checkpoints/cycle236-user-root-cpu-lifecycle.md).
PKUSER3 consumes PKUSER2 ownership and retains pages across uncertain CPU writes,
restoration and failed detach. Its compiled privileged adapter is not wired into
boot and has no fresh guest evidence. Inherited supervisor ownership, serialized
physical access, current stack/code preservation and the one-BSP lease remain
explicit trusted-adapter preconditions, not facts established by a host model.

After preview acceptance, continue N0-N39: generalized task/address-space
lifecycle, robust SMP and architectural-state switching, concurrency/teardown,
capability revocation, priority/deadline behavior, IPC pressure and cancellation,
IOMMU/driver isolation, recovery and sustained fault/soak testing. Expand to the
declared hardware profiles only with their separate evidence. The preview is a
vehicle for exercising these mechanisms, not a reason to abandon them.

## Research References

- [AMD64 system programming manual, revision 3.44](https://docs.amd.com/v/u/en-US/24593_3.44_APM_Vol2): privilege, descriptors, paging, and interrupt context.
- [AMD64 instruction manual, revision 3.37](https://docs.amd.com/v/u/en-US/24594_3.37): IRET and privilege-transition semantics.
- [Intel architecture manuals](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html): independent vendor reference for the eventual entry/return review.

These are architectural references, not external validation of PooleKernel.
