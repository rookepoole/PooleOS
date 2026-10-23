# Native Job Ownership

Contract PJOBOWN1, Cycle315. This refines the trusted-kernel PJOB1 API under
N13/N14. It is not a new userspace capability or a production promotion.

## Invariants

- A prepared task generation can create one job. Invalid identity, state or
  capacity leaves its claim unused. Closure is terminal for that generation.
- A child has at most one parent-job claim. Adoption validates identity, state,
  root separation, duplicate membership and bounded capacity before committing
  both records. Membership binds task slot/generation and image root/generation.
- Task slots retain claims independently of the Job value. Dropping a job neither
  releases memory nor allows replacement ownership. Recovery of a lost supervisor
  record remains future work; retention is intentional, not reclamation success.
- Raw reclaim, reap/detach, abandon and deferred reclamation reject enrolled
  children. Open job owners also reject reclamation. Checks precede revocation,
  quiescence, memory writes, state changes and retry-budget consumption.
- Only the matching job can reclaim its child. Failed cleanup retains both
  membership and resource ownership. Successful whole-task reclamation removes
  the slot; only subsequent insertion creates fresh generation-bound claims.
- A job owner may itself be a child. Its own job must close before its parent
  reclaims it. Closing the owner does not discard its children's obligations.
- Existing three deferred retries and one closed-job recovery opportunity remain
  unchanged. No heap, global identifier allocator, unsafe code or widened limits
  are introduced by the ownership checks.

## Evidence and Limits

Host counterexamples cover duplicate owner jobs, duplicate child enrollment and
owner reclamation before closure. Additional tests cover failed enrollment,
dropped jobs, raw cleanup, stale generations, nested owners, deferred budgets and
independent jobs progressing across revocation/scrub failure. These are trusted
kernel API defects, not a demonstrated userspace exploit.

Native regression uses the existing single-owner actual-UD2 entered-child recovery,
persistent-retention and ordinary-deferred profiles. It does not demonstrate
multi-owner fairness. Exact results are recorded in the Cycle315 checkpoint and
`runs/native-job-ownership-readiness.json` after qualification.

Next: bounded multi-owner job registry and topology validation, fair cleanup and
supervisor-record recovery; then capability/IPC revocation and bounded service
restart/rebinding. Global cycle detection, SMP synchronization, partial allocator
release, construction/committed-handoff recovery and all-path stack isolation
remain open. No GUI/ISO work is required for this contract.
