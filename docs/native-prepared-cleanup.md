# Owned Prepared Cancellation

Contract: `PCANCEL1`. Cycle276, 2026-10-13. Development-only, single-BSP
interactive integration. This extends retained cleanup, not production recovery.

## Ownership And Ordering

`Slot::cancel_prepared` accepts only the exact occupied task generation in
`Prepared`, with no outcome, slice or pending charge and zero runtime. Its CPU
owner must be inactive, context-free, and user/timer-quiescent. The root comes
from the owned prepared image, not a supplied outcome. Cancellation records
`Cancelled` with zero system calls and enters `Terminated`; it neither executes
the child nor releases memory. Exposed and quarantined states reject.

`Slot::reclaim` then revokes driver authority and transfers original allocation
retention tokens into the existing reclaimer. Erase/readback, finish and release
must complete before slot reuse, scheduler teardown or process completion. Failure
keeps the exact cancellation and allocation ownership. Prepared cleanup does not
switch CR3, enter user mode or shut down a timer it never started.

The interactive dispatcher uses this path for both admitted prepared children and
unused prebuilt children at clean shell shutdown. Other legacy abandonment paths
are not globally migrated. Running children retain the terminal cleanup path.

## Native Qualification

`tools/qualify_native_shell_process.py --prepared-stop` enables a qualification-only
hold: after the scheduler first selects worker generation1, it blocks the task
before CPU activation or user entry. It does not skip the shared sample/control
tail. The real shell then requests stop using its process capability. A physical
erase write fails after effect, memory stays retained, early completion/free/reentry
reject, and one immediate retry completes. Generation2 executes normally.

`PCANCEL1` requires exactly one ordered hold, matching admission/root/generation,
zero first-generation calls/ticks and adjusted actual CR3 writes. It also requires
the entire `PRECLAIM1` cleanup and `PSHELLPROC1` interaction, including faults,
restart, denied authority and surviving tasks. `CONTROL` records' CPL3 session
label does not claim this held child entered ring3; the hold explicitly says
`entered=0 cpl=0`. This is not a user-visible suspend API.

Six kernel tests include78 prepared-page erase/readback failures, stale/exposed
state rejection, revocation/finish failure and generation-safe reuse.526 kernel
tests pass in each host profile. Three prepared guests prove three pre-entry
stops and recover ten total injected failures across prepared/executed children;
50 ordinary-free and ten early-completion denials pass. Three ordinary-shell and
three default/unsigned-denial regressions pass separately. Synthetic transformed
transcripts in unit tests exercise the parser only; they are not execution proof.

Exact receipts and retained failure history are in
[Cycle276](checkpoints/cycle276-prepared-cancellation.md) and
`runs/native-prepared-cleanup-readiness.json`.

## Remaining Boundaries

Owner death/orphans still halt the bounded integration rather than recover.
Parent lease removal does not yet preserve a durable child cleanup roster.
Asynchronous retry, partial allocator-commit failure injection, complete stack
bounds, wider/SMP retirement and general executable trust remain open. Normal
and prepared local frames measure50136/49336 bytes; these are not full bounds.
No mapping, PMM, code, stack or image-capacity limit increased.

Next qualify durable owner-death cleanup, then read-only bundled files and two
useful applications before sustained optical ISO acceptance. No usable ISO,
production trust, release or canonical main qualification is claimed here.
