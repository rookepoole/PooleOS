# Bounded Parent-Death Jobs

Contract: `PJOB1`. Cycle277, 2026-10-13. Development-only single-BSP
interactive integration, not a general service manager or restart guarantee.

## Mechanism And Policy

`Job<N>` retains the parent and child task generations, owned physical roots and
root generations independently of revocable IPC, launch and process leases.
Identities come from actual prepared task slots. Only prepared children can join;
duplicate slots/roots, the parent, exhausted capacity and a closing job reject.
The record is non-Clone. It is a relationship, not an allocation token: dropping
it cannot free a task. Slots retain the original memory owners throughout cleanup.

The trusted bootstrap selects cancel-on-parent-death membership before admission.
The shell owns children4/5, including prebuilt children never admitted. Init,
counter and the endpoint-owning console service are independent. There is no new
user-facing job-creation syscall, user-selected kernel authority or automatic
supervisor restart. Broader service policy belongs in later user-space supervision.

The dispatcher observes the exact terminal parent before its cleanup removes
leases. Pending accounting or unknown runtime prevents job closure. Closing is
irreversible. Repeated observation of the same terminal parent is harmless.
Child cancellation accepts prepared/suspended states, an exact waiting ticket,
or an already terminated/reclaiming outcome. Active, mismatched and unsettled
states reject before effects. Membership survives every reclamation failure and
is removed only after the slot's physical cleanup succeeds. Scheduler teardown
and completion publication follow cleanup; the detached parent receives no
completion. Normal live-parent completion and generation-safe restart still work.

## Executed Qualification

The actual CPL3 shell implements exact `fault shell` using UD2. Near matches
remain unknown commands. The qualifier sends independent nonce-bearing input,
starts a worker, checks status, and then faults the shell. Three guests exercise
a previously running child; three hold it before first entry. Each group includes
a denied launch-authority control. Both supervised child allocations disappear;
the independent console, init and counter continue progressing with39 pages.
The shell is not restarted and cannot accept another command after its fault.

`PJOB1` requires ordered parent/child/drain records, exact generations/roots,
zero dead-observer publication, complete existing process/cleanup observations,
exact COM2 interaction, and matching COM1/debugcon kernel evidence. Prepared
children have zero calls/ticks/entry and no additional CR3 switch. Previously
running children cannot reenter and require the existing quiescent-root flush.
Each new guest injects an erase failure and proves retained ownership before one
immediate successful retry. Native waiting-child and scheduled retry paths are
not qualified by these six runs. Synthetic schedules test parsers only.

Seven host tests cover parent cleanup, stale identities, wrong roots, membership
quotas, settled accounting, suspended/waiting children, failed revocation/erase/
finish, job drop and safe next-generation adoption. Existing launch/process tests
also reject owner-death-invalidated pending and claimed permits. Host tests are
not native interleaving evidence. Ordinary shell and prepared-stop regression
guests verify that normal clean-close behavior has not changed.

## Remaining Work

Qualify native waiting children and pending/claimed request interleavings across
parent death. Add bounded scheduled cleanup retry, backoff/exhaustion and retained
failure state without starving other services, reentry or early completion. The
current dispatcher still halts safely on unexpected unrecovered cleanup errors.
General supervision/restart, partial allocator-commit fault injection, full stack
bounds, SMP retirement and wider executable trust remain open. Then build the
read-only file service and two useful apps within the reviewed six-process layout,
followed by sustained optical ISO acceptance. Robust microkernel work continues.

See [Cycle277 evidence](checkpoints/cycle277-native-owner-death.md) and
`runs/native-owner-death-readiness.json`. No production or main qualification.
