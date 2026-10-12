# Native Process Launch Authority

PLAUNCH1, Cycle268. Development-only bounded launch mechanism and separately
compiled user-space policy. Complements PPROC1; not a general exec/service manager.

## Authority And ABI

Trusted bootstrap may grant two global launch leases. Each reserves a distinct
empty IPC child slot and binds a nonzero catalogue program ID to the owner's full
task/root generations. Type6 handles have checked, nonwrapping generations. A raw
program ID, task ID, pointer or requested code buffer never confers authority.

PSABI1 call19 takes a launch handle and nonzero u32 operation sequence; remaining
arguments must be zero. Same-sequence calls poll the same operation, including
after child death. Only the exact next sequence can start another operation after
completion/failure and absent child attachment. Superseding a completed operation
releases its already-revoked process handle. Sequence exhaustion rejects.

States: Idle -> Pending -> Claimed -> Complete(process handle) or Failed. A
non-Clone/non-Copy permit is claimed once. Dropping it retains Claimed; it does not
retry implicitly. Owner detach/revocation invalidates leases and stale permits.
The exclusive dispatcher revalidates full identity, sequence and child slot.

## Atomic Admission And Ownership

The adapter must match the trusted catalogue, finish slice accounting, restore
the kernel root/flags and prove the previous owning task Slot fully empty before
reuse. A new admission step grants an InspectTerminate PPROC1 handle. Child image
attachment, scheduler enrollment, IPC grants, process handle and launch completion
commit without a dispatch window. Rollback removes newly installed process grants
before detaching newly attached tables; generations remain spent.

Admission failure leaves the prepared image with its existing owner. Failed
completion is legal only after construction rollback or when nothing was allocated.
Retained cleanup must retain the claim and ownership. Attachment revocation is
not evidence of page reclamation. General retry/quarantine policy remains open.

## User-Space Policy

PooleSupervisor is independently compiled, not kernel policy or an assembly-only
test controller. PSTART1 arguments supply a typed launch handle and lifetime limit
1..16. Each policy step makes at most one call. It polls call19, monitors the
returned process attachment using call17, and requests the next sequence only
after revocation. Policy completion exits0; transport denial exits170. It currently
has no interactive stop command, exit-reason service or general orphan policy.

The native adapter qualifies a fixed two-lifetime worker and independent survivor.
The first child is prepared but never attached/activated before the user request;
its first launch is admission. Restart constructs a new owned image only after
full previous cleanup. Bad factory generation causes no child dispatch and owned
cancellation of the prepared image. The separately qualified PPROC1 stop path
still handles suspended and waiting targets; the supervisor does not yet combine
these paths into a general interactive service manager.

## Evidence And Remaining Work

See [Cycle268](checkpoints/cycle268-native-process-launch.md) and the byte-bound
`runs/native-process-launch-readiness.json`. Host tests cover request strictness,
quotas/generation exhaustion, revocation/owner death, duplicate claims, atomic
rollback and retained failed claims. Native guests qualify two starts/retirements,
invalid authority, prepared cancellation and continued independent execution.
They do not prove every owner-death/cleanup race or injected native allocation failure.

Kernel image208/208 pages,36-page guarded stack; default RELRO padding152 bytes.
Capacity/profile review is mandatory before growth. Keep complete call-chain stack
proof, PMM-record limits, efficient idle, signed executable trust/loading, truthful
exit results and retained cleanup recovery open. Next integrate real shell/input,
read-only bundled files and two useful applications before optical ISO acceptance.
The complete robust microkernel, PooleGlyph/PDC and accessible PooleGlass remain
required afterward. No production, main-merge or usable-ISO claim follows here.
