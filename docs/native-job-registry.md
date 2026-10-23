# Native Job Registry

Contract PJOBREG1, Cycle316. Bounded single-supervisor ownership and ancestry
for the native microkernel. This builds on PJOB1/PJOBOWN1, not a userspace ABI.

## Ownership

`Registry<J, C>` owns up to J jobs with C children per job. Both nonzero bounds
are limited by scheduler MAX_TASKS. The native interactive supervisor uses J=6,
C=2 without raising process, memory, retry or recovery limits. The registry owns
records; short-lived Owner views cannot extract, replace or mutate the underlying
Job directly. Dropping a view leaves the record available for exact-ID reacquisition.

Task slots mark managed membership. Standalone Job APIs cannot claim managed
owners/children, and a different registry cannot import them. Enrollment rejects
aliased slot/root identities across jobs and checks the proposed owner's ancestry
before adding an edge. The ancestry walk is bounded by J; a self-edge, cycle or
inconsistent foreign claim rejects before enrollment effects. A managed child may
become a job owner only through its existing registry. Existing exact generation,
terminal-accounting and cleanup ownership checks remain in force.

Retirement removes only closed, drained records. It does not free a task or memory.
A freed owner can leave its closing job in the registry until its children drain.
Same-slot reuse needs the prior job retired and a fresh exact task generation.
Dropping the whole registry retains slot claims and resources; reconstruction of
an entirely lost registry is not implemented or claimed.

## Selection

`next_orphan` performs bounded round-robin selection across closed jobs and then
their children. It advances both cursors when returning one diagnostic Work pair.
Waiting, failed cleanup or retained pages cannot pin the cursors. Selection itself
does not cancel, revoke, write memory, change accounting or consume/reset retries.
The subsequent operation authenticates the actual slot and exact job membership;
the returned task IDs alone grant no authority.

With stable membership and repeated calls, a nonempty closed owner is selected
within J calls and each of its children within J*C calls. This is selection order,
not a wall-clock or SMP fairness guarantee. Admission costs are bounded by the
fixed registry dimensions; no heap, unsafe code or global ID allocator is added.

## Qualification Boundary

Host tests exercise two owners/four children, failed cleanup, nested ownership,
cycles, aliasing, foreign registries, capacity, stale generations and dropped views.
The native supervisor uses the registry for admission/closure/reclamation, but its
existing scenario still has one parent job. Native multi-owner dispatch and native
use of the round-robin selector remain the next implementation step. Existing
headless recovery/persistence/deferred cases are regression evidence only.

No whole-machine job graph, lost-registry recovery, bounded service restart,
capability/IPC lifetime closure, partial allocator release or SMP synchronization
is claimed. Keep all production and eventual signed-ISO gates intact.
