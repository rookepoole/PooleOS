# PKUSER10 User State Containment

Cycle 244, USI-1 / N12.5-7 and N13.3,6. This extends the original native
PooleKernel peer scheduler. It does not admit arbitrary programs or produce an ISO.

## Entry And Return

The entry envelope and the proposed user return state have separate checks.
Wrong root, kernel/foreign selectors, recursion, private handler-stack mismatch,
unexpected event/error codes and unsupported system exceptions remain fatal
kernel invariant failures. A valid owned entry with invalid user RIP, RSP or
RFLAGS instead produces a terminal `InvalidReturn` for that task. The rejected
frame is never saved for resumption or passed to IRETQ. Repeated calls, preemption
and exit cannot change its outcome. Rejected requests do not consume a syscall.

Timer termination still acknowledges the owned interrupt and verifies device
state. Both termination paths disable syscall authority and return through a
known kernel frame. Timer quiescence, descriptor detachment, flushing root
restoration and verified release remain mandatory. Cleanup errors retain the
owner rather than freeing referenced state. Final termination ticks are still
not included in scheduler accounting; that is separate unfinished work.

## Exception Entry

User exception gates for vectors 0,1,3,4,5,6,11,12,13,14,16,17,19 use IST=0 and
the task's private TSS.RSP0. Only breakpoint vector3 receives DPL3 for INT3.
The other gates do not grant software interrupt access. Error shapes are checked;
page faults still reject reserved/unsupported classes. NMI, double fault, invalid
TSS, device-not-available, machine check and unsupported exceptions are not
converted into ordinary task failures.

The common trap prologue clears AC before Rust dispatch, without requiring the
SMAP-specific CLAC instruction. CLD remains mandatory. Saved user flags stay in
the hardware frame; the kernel's live flags must satisfy the entry mask. A
contained debug exception acknowledges DR6 only after task validation and rejects
unexpected hardware breakpoint/general-detect/task-switch status. It does not
enable a debugger or grant access to debug registers.

[Intel SDM Volume 3A, revision 090](https://cdrdv2-public.intel.com/874249/253668-090-sdm-vol-3a.pdf),
sections 7.12.1.2-3, 7.14 and the exception reference, informs gate privilege,
flag handling and private-stack delivery. Vendor semantics are requirements,
not proof that this implementation or emulator conforms.

## Live Cases And Emulator Limit

Four existing rounds cover exit, UD2, cancellation and syscall quota. Ten new
rounds cover syscall with kernel/noncanonical RSP, NT, AC, a return RIP just past
the code page, timer entry with kernel RSP and AC, divide error, TF single-step,
INT3, and noncanonical stack access. A separate private-root peer must progress
after every stop, preserve sampled integer/legacy FP state and exit84. Every
round reclaims both images. The old privilege, copying, timer and task tests remain.

The stack-access test initially required architectural #SS(0), but this exact
QEMU 11.0.0 TCG runner delivered #GP(0). A failure-only diagnostic reproduced
vector13 at user RIP 0x400000BF. The behavior matches upstream
[QEMU issue928](https://gitlab.com/qemu-project/qemu/-/issues/928) and
[issue4205](https://gitlab.com/qemu-project/qemu/-/work_items/4205).
The revised TCG-only probe records that observed vector explicitly. Its oracle
sets `architectural_stack_fault_qualified=false` and rejects a substituted #SS
claim. This establishes peer survival for this emulator's actual exception,
not native #SS delivery. No kernel exception semantics are changed to match TCG.

The additional natively executed exception vectors are 0,1,3. The vector12
handler and full declared table have host policy/static routing coverage, not
fresh native delivery qualification. Other unexercised classes, TCG selector
semantics, physical hardware, XSAVE/SMP/async entry and general SMAP remain open.

## Next Dependencies

Under `FLAG-N13-USERSPACE-ISO-001`: transactional spawn rollback, pending/late
timer recovery, final-quantum accounting and independent missing-IRQ recovery
must precede general application admission. Then capability IPC, confined
services, shell/apps and the actual optical ISO. The 90-second external guest
bound is not a kernel watchdog. No production promotion or N12/N13 exit follows
from this checkpoint. Full microkernel development continues after the usable ISO.
