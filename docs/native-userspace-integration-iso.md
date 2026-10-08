# Native User-Space Integration ISO

Status: implementation started, Cycle 238, 2026-10-08. No new ISO exists yet.
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
| USI-1 User entry and containment | N7, N9, N12, N13.1-4, N13.6 | Real ring-3 entry, controlled kernel entry/return, private address spaces, timer recovery, and a contained application fault | Cycle 238: two actual CPL0 root/timer/quiescence/restore/release probes pass; ordinary denial preserved; no ring-3 execution yet |
| USI-2 Capabilities and IPC | N13.5-7, N14.1-3, N14.5-7 | Two isolated tasks communicate only through granted handles; stale handles, oversized messages, cancellation, dead peers, and quota failures reject safely | Not started |
| USI-3 Runtime and services | N16, N20, N21 | Real init, executable loading, service startup/restart, and a confined console/input service | Not started |
| USI-4 Shell and applications | N18, N19, N22, N30 | Interactive user-space shell, read-only bundled files, two applications, observable fault containment | Not started |
| USI-5 Optical integration | N5, N36, N38, N39 | Corrected ISO packaging, fresh end-to-end guest interaction, sustained-session and fault/recovery tests | Not started |

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
5. Add a narrow versioned syscall ABI and hardened user copying with recoverable
   faults, bounded lengths, checked arithmetic and stable ownership. Do not use
   raw user pointers or numeric addresses as authority.
6. Connect private address spaces to scheduler execution/lifetime holds. Support
   preemption, exit, cleanup and accounting for the declared single-CPU profile.
7. Contain user #PF/#GP/#UD while treating kernel faults as kernel faults; prove
   that a faulty or spinning task cannot prevent supervisor recovery or peers.

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

## Cycle 238 Live Integration

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
