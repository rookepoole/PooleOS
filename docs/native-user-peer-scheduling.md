# PKUSER9 Native Preemptive User Peers

Cycle 243, USI-1, partial N12.5-7 and N13.1-4,6. Original PooleKernel;
one BSP and fixed development payloads, not arbitrary-program admission.

## Mechanism

The existing PKSCHED1 `Scheduler` owns two runnable queue entries. Each task's
exclusive `Slot` owns its CPU image, private root, guarded entry stack and exact
timer/entry cleanup driver. Queue dispatch is matched to slot and generation;
these IDs are not capabilities or a global namespace. Both 13-page images exist
before dispatch and their roots must differ. No Linux runtime is involved.

Each dispatch activates the selected private root, restores its saved 15 GPRs,
five-word IRETQ frame and 512-byte legacy x87/SSE state, and arms a calibrated
10-ms one-shot APIC timer. Timer entry captures state, accounts observed HPET
ticks, acknowledges the interrupt, disables syscall authority, and returns to
the kernel. Timer shutdown precedes descriptor detachment and a flushing switch
to the original scheduler root. Only then does the task become Suspended. All
PMM holds remain live; it is not detached or reclaimable between quanta.

Resume revalidates CPU identity/mode, ownership and the entire admitted mapping
set before MOV CR3. Present parents tolerate only hardware A bits; present leaves
tolerate A/D. Absent guards remain exactly zero. Permissions and physical targets
cannot change. Checked saved user frames never contain kernel stack pointers.
Execution, quiescence, context or restore failures quarantine the owner and block
resume/free. Cancellation accepts only the exact suspended identity and never
reenters saved state. Final reap still requires a fresh flushing restoration.

The development syscall stack may move within its one owned page. The 65th
attempt after 64 accepted calls terminates only that task with CallLimit instead
of halting the kernel. The quota is a development policy, not a production ABI.

## Fresh Execution

Four rounds pair a survivor with a task that exits42, faults with UD2, spins until
cancelled after its third quantum, or exhausts its syscall budget. The survivor
must make measured progress after the first task stops and eventually exit84.
Payloads check integer registers, stack data, XMM0/XMM15 and x87 state after
switching. These live checks sample state; host round-trip tests check all 15
saved GPR fields. Spinner cancellation does not reach its terminal state checks.

Each of two fresh guests measured 40 dispatches, 33 preemptions and 16 surviving
peer quanta after termination across the four rounds. There were 91 actual CR3
writes including the earlier probes, 169 pages released and 78 data pages
scrubbed. The old privilege/copy/timer and four sequential task controls remain.
Each guest's 44-marker transcript rejects 249 altered-evidence cases; those are
parser controls, not hardware-failure injections. The third ordinary unsigned
boot still denies kernel execution. See the Cycle243 checkpoint for exact hashes.

## Remaining Integration Work

- USI-1 admission containment: transactional allocation/mapping rollback for
  spawn, task-only rejection of invalid user return frames, and contained handling
  of all admitted user exception classes. Current invariant/unsupported-frame
  failures remain kernel-fatal. Do not admit arbitrary binaries yet.
- Armed-timer teardown races: a pending APIC interrupt causes conservative
  quarantine, not proven peer continuation. Add explicit pending/late/missing
  interrupt tests and a qualified recovery protocol. The existing elapsed-time
  guard runs only when an interrupt arrives; the external 45-second guest bound
  is not an independent native watchdog.
- Complete CPU accounting: current runtime ticks cover completed preempted
  quanta, not the final sub-quantum before exit/fault. General fairness, priorities,
  blocking/wakeup, wait events and sustained workloads remain unqualified.
- No asynchronous kernel preemption, AP migration, general FS/GS/debug/PMU state,
  full XSAVE, concurrent mapping/DMA or general SMAP qualification. Kernel runs
  IF0 under exclusive legacy-state ownership; this is not full SMP scheduling.
- Then USI-2 capability handles and IPC, USI-3 init/loading/confined console,
  USI-4 shell/files/apps and USI-5 optical ISO. No session or ISO exists yet.

These items remain under `FLAG-N13-USERSPACE-ISO-001` and N12/N13/N35. No phase
or production gate closes. Product contracts require explicit 0xB000/172-page
migration and fresh prerequisite replay; old receipts are not rebound to new code.

## Architecture Reference

[Intel SDM Volume 3A, revision 090](https://cdrdv2-public.intel.com/874249/253668-090-sdm-vol-3a.pdf)
informs privilege transitions, interrupt return, page-table A/D behavior and APIC
timer handling. Vendor semantics are a design input, not proof of implementation.
