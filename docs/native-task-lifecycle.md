# PKUSER8 Development Task Lifecycle

Cycle251 adds a Waiting state, charged quiescent IPC suspension, exactly-once
notified resumption, and mandatory authority revocation before Slot retirement.
Native adapters and their timer wrapper implement the hooks; failed revocation
retains the root for retry. See [IPC lifetime and remaining work](native-capability-ipc.md).
This does not qualify arbitrary service supervision or every enrolled-owner death path.

Historical Cycle 242 baseline. Cycle243 extends this lifecycle with retained
suspend/resume, cancellation and task-only call-limit termination; see
[PKUSER9 peer scheduling](native-user-peer-scheduling.md) for current scope.
The sequential measurements and follow-on list below describe Cycle242 only.

Original PooleKernel, one BSP, fixed admitted payloads. Partial
N13.1/N13.2/N13.6, not a complete task API, scheduler, or production contract.

## Ownership And Identity

`user_entry::task::Slot` exclusively owns a `CpuImage` and the exact architectural
cleanup driver. A persistent slot increments its nonzero generation on successful
insertion; overflow fails without wrapping. It uses the existing `TaskId` shape,
but identity is scoped to that slot's lifetime, not globally unique, a capability,
or admission to the scheduler's runnable queue. Occupied insertion returns both
new owners unchanged. The slot and its owned image cannot be copied or bypassed.

Prepared -> Active -> Terminated -> detached is the successful lifecycle.
Before any potentially effective CPU operation, state becomes Quarantined.
Execution/cleanup errors retain ownership and PMM holds. Only explicit cleanup
recovery can detach a quarantined task; it cannot fabricate an application exit
or restart it. Cleanup failure may be retried, not ignored. Dropping owners
retains physical allocations rather than asserting unobserved quiescence.

`reap` returns the terminal outcome and detached resource owner after entry-state
quiescence, fresh CPU checks, flushing restoration of the original root and
verified inactive detachment. Reaping alone is not physical deallocation: the
caller must still scrub data, remove mapping holds, and release all allocations.

## Exit And Fatal User Faults

PSABI1 development call 2 exits with RSI as a u32 status; RDX/R10/R8/R9 are zero
and RDI is version 1. Valid exit does not return to the caller. Other call errors
retain the existing explicit version/unknown/argument/fault result semantics.

The architecture adapter installs private entry state, initializes legacy FP/GPR
state, enables the existing syscall entry and enters CPL3. Exact owned root,
user CS/SS, private entry-frame position and non-nested context bind termination.
User #UD, #GP and ordinary user #PF record a terminal outcome. Reserved page-table
bits, unsupported fault classes and kernel/nested invariant failures remain fatal.
Faulting user RIP/RSP need not be valid because termination never returns there.

Exit/fault disables SCE and clears the entry MSRs before the controlled CPL0
return. The owning adapter then removes descriptor/FX/entry references before
root restoration. Repeated execution, exit-state mutation, stale identity and
repeated reaping fail. Outcomes bind identity, root, reason and syscall count.

## Measured Development Scope

Four tasks run sequentially through one persistent slot: query then Exit42,
UD2, CLI, and a denied supervisor-memory read. Generations 1..4 may reuse physical
pages only after the preceding image is detached, scrubbed and freed. This is not
simultaneous peer execution. Each task releases 13 pages, scrubs six data pages,
and rejects direct freeing of all five retained allocation handles before reap.
The earlier privilege/copy/timer experiment is retained separately. Together the
guest observes ten actual root writes, 65 released pages and 30 scrubbed pages,
leaving only the preexisting one-page ACPI snapshot allocation.

Host tests inject execution, quiescence and CR3 failures, corrupt outcomes and
exercise generation exhaustion. Those are mocks, not live hardware-fault tests.
Two independent fresh guest boots exercise real exit/fault instructions and
cleanup. Their parser mutation controls test evidence rejection, not hardware.

## Required Follow-On Work

- Two runnable private-root tasks, timer-driven switching, saved register/FP
  state, peer survival after exit/fault, cancellation and bounded CPU accounting.
- Remove the fixed initial syscall RSP restriction and replace the 64-call
  development budget's kernel-fatal behavior before arbitrary programs. These
  limits are not a production containment design.
- Transactional spawn construction with rollback at every allocation/mapping
  step; current live construction halts on failure. Slot insertion and cleanup
  failures are covered, not the full spawn operation.
- Namespace-wide identity allocation, wait/event delivery, capabilities, IPC,
  general executable loading and confined user services.
- Syscalls while a task timer is armed, independent missing-interrupt recovery,
  async/SMP/NMI entry, general XSAVE and SMAP/concurrent mapping coverage.

The four new fixed payloads do not arm a timer. The previous spinning-task timer
test remains a distinct experiment. Neither establishes arbitrary-program
liveness or a usable shell/ISO. These remain under `FLAG-N13-USERSPACE-ISO-001`,
N12/N13/N35 and the integration plan; no phase or production gate is closed.

## Primary References

- [Intel SDM Volume 3A](https://cdrdv2-public.intel.com/874249/253668-090-sdm-vol-3a.pdf):
  privilege transitions, exceptions, page-fault error bits and IRETQ frames.
- [AMD64 Architecture Programmer's Manual, Volume 2](https://docs.amd.com/api/khub/documents/sD1_QL~h4Afq2_tvzxqqSQ/content):
  long-mode protection, exception handling and system instructions.

These architecture references inform the original implementation; they do not
independently validate it. No Linux runtime or kernel implementation is used.
