# Sustained Service Dispatch

PKSERVICE1 extends the original single-BSP user-task mechanism with replenished,
bounded syscall dispatches. It is not a new syscall ABI, complete resource policy,
service supervisor or an interactive ISO. PSABI1 request/return registers remain.

## Execution Policy

Normal native PeerEntry creates Run::sustained. A dispatch admits at most64 syscall
attempts, including requests subsequently rejected for version, number, arguments
or permissions. Existing bounded copy/IPC operations and hardware timer preemption
remain. The pure Run cannot begin another dispatch while one is open, accept
calls while it is closed, or reopen after a terminal outcome.

After a nonblocking syscall consumes the final allowance, the architectural
adapter saves the POST-handler frame, including result RAX/RDX and sanitized
flags, plus legacy floating-point state. It reports BudgetYield, shuts down the
owned entry/timer state and restores the supervisor root. It does not rewind RIP,
reexecute the syscall, fabricate a timer interrupt or turn the completed call
into a failed syscall. This is ordinary completion followed by a scheduling point.

Blocking preserves its existing wait/ticket and notification protocol; exit/fault
remains terminal, including on the allowance boundary. Timer preemption also closes
the dispatch without killing the service. Only the next trusted driver execution
replenishes the allowance. A user cannot invoke that Rust supervisor operation.
Slot requires settled accounting and valid reactivation before another execution.

Run retains a checked64-bit lifetime syscall count across all dispatches.
Exhaustion produces CallCounterExhausted before another request executes; no wrap,
reset or saturating replacement of accounting is allowed. Slice/Outcome validation
accepts legitimate totals above64 but still checks identity, root, reason, positive
budget-yield runtime and a completed allowance. Driver reports are trusted kernel
observations, not a user-supplied source of authority.

Run::new and the explicitly selected diagnostic peer retain the old64-call
lifetime termination control. That diagnostic is not the default service policy.

## Ownership And Scheduling

BudgetYield follows the existing suspended-task ownership path. Positive measured
runtime remains pending until the matching scheduler dispatch settles it exactly
once. Unsettled/unknown samples deny activation and cancellation. Failed quiescence
or root restoration retains the CPU/image and charge in quarantine for recovery.
After settlement, a supervisor may cancel the suspended service and reap it without
resuming its saved state. General user-directed cancellation still needs authority.

The quantum timer remains the CPU-time bound; the syscall allowance bounds kernel
work between scheduler visits even when user code floods syscalls. Replenishment
is dispatch-based, not a wall-clock token bucket or reserved CPU bandwidth.
Current qualification establishes interleaving of equal-priority peers, not
starvation freedom across priorities, SMP fairness or hard-real-time scheduling.

## Evidence And Limits

Host checks cover repeated dispatches beyond64 total calls, exhausted/closed
dispatch denial, repeated begin/end, invalid trap/return frames, rejected request
charges, exact-boundary exit,64-bit exhaustion, forged budget reports, settlement
before reentry/cancel, duplicate settlement and failed-cleanup retention.

The native exercise repeatedly copies eight actual user bytes and verifies the
returned status/length, destination and preserved registers across allowance
boundaries. One task faults after256 calls; its peer continues through512 copies
and Exit100. The fresh-guest receipt and checkpoint establish measured results,
not this specification. Earlier diagnostic termination and all containment, IPC,
deadline and admission cases must still pass with ordinary unsigned boot denial.

The copy test is not a proof of exactly-once arbitrary device or service effects.
It does verify post-call register/data preservation; the implementation saves the
post-handler continuation without replay. Kernel clock failure recovery, efficient
interrupt-driven idle, owned executable/argument policy and supervision remain.
Other existing checked scheduler/runtime counters still have finite exhaustion
boundaries; this is not an infinite-duration or production uptime claim.

Next: separate qualification from normal session bootstrap, bind owned user
executables and arguments, then init/confined console/input, shell/files/two apps
and optical ISO acceptance. Full robust microkernel, PooleGlyph/PDC and accessible
PooleGlass remain required after the bounded ISO milestone.
