# PSABI1 Development Syscall Profile

Current extension, Cycle253: calls6-9 add asynchronous request, metadata receive,
one-use reply and discard. Call6 uses R8 for an owned reply endpoint; the other
calls still require R8=0. Metadata receive returns a32-byte LE header plus payload,
with kernel-authenticated sender identity and a task-local reply token. Existing
calls0-5 retain their layouts; raw receive4 denies requests requiring metadata.
This is not a frozen production ABI or synchronous Call protocol.

Cycle251 baseline: calls3/4 send/receive through granted endpoint handles;
call5 waits for readable/writable readiness with scheduler suspension and checked
resumption. Statuses5-9 add Denied, Again, TooSmall, Cancelled and Revoked. See the
[current IPC contract](native-capability-ipc.md) for the exact register layout,
copy semantics, ownership, cancellation and remaining limits. Calls0-2 below are
the historical baseline; statements about missing IPC/blocking describe Cycle242.

Cycle 242, PKUSER7/PKUSER8. N13.3/N13.4 partial implementation; not the complete frozen
production ABI, N13 exit, application runtime, or integration ISO qualification.
This original PooleKernel implementation grants no capability or object authority.

## Registers and Results

Transport is x86-64 SYSCALL with checked IRETQ return. RAX is the call number;
RDI is version 1; RSI is source; RDX is destination; R10 is byte count; R8 is flags
and R9 is reserved (both zero). RAX returns status, RDX returns result. RCX/R11
are architectural clobbers; other general registers are preserved. Return clears
DF/RF, requires IF and reserved bit 1, and rejects unsupported flag bits.

| Call | Request | Result |
| --- | --- | --- |
| 0 | Version; source/destination/count zero | OK, version 1 |
| 1 | Copy within caller's admitted user window; 0..256 bytes | OK, copied bytes |
| 2 | Exit; RSI=u32 status, destination/count zero | Valid exit never returns |

Status numbers: OK=0, VERSION=1, UNKNOWN=2, ARGUMENTS=3, FAULT=4. Validation order
is version, flags/reserved, number, then per-call arguments. Unsupported versions
and numbers never execute a copy. There is no implicit version downgrade.

Nonempty ranges must have checked addition and fit the canonical lower user
window. Range membership is not permission: actual page protections still apply.
Zero length performs no memory access and ignores pointer values. Unaligned
addresses are supported. All input bytes are snapshotted before any output:
input fault means no destination changes; output fault reports the exact committed
prefix, with no rollback promise. Overlap uses snapshot semantics. No automatic
retry, restart, blocking, cancellation, IPC, or scheduling action is implemented.

## Entry and Fault Ownership

One BSP exclusively owns the active private root, mappings, guarded entry stack,
and descriptor state. No AP, DMA, mapping mutation, or interruptible kernel copy
is admitted. STAR/LSTAR/CSTAR/FMASK are programmed and read back before EFER.SCE;
the software stub saves user RSP to supervisor storage and switches stacks before
any push. FMASK clears TF/IF/DF/IOPL/NT/RF/AC. There is no SYSRET, SWAPGS, shared
kernel stack, or general SMP/NMI entry claim. Checked return requires the admitted
root, exact initial user stack, private entry frame, user selectors and code page.

Only an armed byte-load/store instruction's exact nested CPL0 page fault can be
recovered: depth, root, RIP, CR2, access kind, error bits, private stack bounds and
frame geometry must match. It changes RIP only to that operation's linked fixup.
Unrelated nested/kernel faults remain fatal. Wrong root, unexpected armed copy,
or unsafe processor flags are fatal internal invariants, not user FAULT results.
Conditional STAC/CLAC bounds each access when CR4.SMAP is active; that path is not
claimed live-qualified on the current qemu64 guest. General concurrent pin/copy,
SMAP CPU coverage and asynchronous interruption remain required future work.

## Development Experiment and Cleanup

The fixed CPL3 payload makes 12 calls: 3 successful, 1 version rejection, 1 unknown
call, 4 invalid-argument rejections and 3 faulting copies. Actual faults include
input guard crossing, output guard crossing (four committed bytes), and attempted
write to the RX code page. A DF-set caller checks entry masking. A separate
completion trap verifies experiment counts, disables SCE and clears/readbacks all
four entry MSRs before the existing three-interrupt user preemption experiment.
These fixed counts are qualification assertions, not application ABI restrictions.
The profile still has a bounded development dispatch budget of 64 calls.

Cycle242 separately exercises valid non-returning Exit42 after a version query,
plus owned #UD/#GP/#PF termination. See [task lifecycle](native-task-lifecycle.md).
The strict initial user RSP and dispatch-budget violations are still fatal
development invariants, not acceptable general application containment. They
must be replaced before arbitrary programs are admitted. Exit does not change
the existing copy semantics or grant capabilities.

Timer shutdown precedes descriptor detachment, root restoration and frame release.
No user pointer or entry MSR may survive task cleanup. Syscalls while a user timer
is armed, arbitrary programs, peer scheduling and
full FP/XSAVE isolation remain unqualified. The missing-interrupt watchdog remains
an external emulator timeout, not a native independent watchdog.

## Primary Architecture References

- [Intel SDM Volume 2, SYSCALL](https://cdrdv2-public.intel.com/782156/325383-sdm-vol-2abcd.pdf):
  RCX/R11, STAR/LSTAR/FMASK, and software-owned stack switching.
- [Intel SDM Volume 3A](https://cdrdv2-public.intel.com/874249/253668-090-sdm-vol-3a.pdf):
  privilege transitions, page faults, long-mode interrupt frames and IRETQ.
- [Intel SDM updates, SMAP/STAC/CLAC](https://cdrdv2-public.intel.com/874239/252046-082-sdm-change-document.pdf).

The normative production charter and native architecture constitution remain in
force. This document records a development subset, not production promotion.
