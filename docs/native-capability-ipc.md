# Native Capability IPC

Cycle254 / PKIPC1 (native lifecycle PKIPC2, replies PKIPC3 and requests PKIPC4) is an original, bounded PooleKernel mechanism, not a complete
N13/N14 implementation. It advances USI-2 toward the native user-space ISO.

## Authority And Lifetime

The exclusive BSP owns one `Space`: four task tables, four capability slots per
table, four endpoint objects, four messages per endpoint, and 64 bytes per message.
No heap, user object pointer, ambient task-ID authority or metadata permission is
used. `Run::ipc_caller` authenticates the live syscall trap before constructing a
caller from its kernel-owned TaskId, root and root generation. Registers cannot
select another table. Tables reject duplicate live roots and task-generation reuse.

A handle contains a 32-bit capability-slot generation, 16-bit endpoint type tag,
and 16-bit one-based slot. It is task-local, not secret or globally unique. Guessing
another task's handle does not select that task's table. Slots reference a private
object index/generation and rights. Empty/stale slots, altered types/generations,
wrong roots, and unauthorized operations deny before memory access. An exhausted
generation retires capacity; no counter wraps. Only endpoint objects exist so far.

Trusted bootstrap creates endpoints and delegates attenuated rights. SEND,
RECEIVE, GRANT and DESTROY are distinct. Delegation requires GRANT and cannot add
rights. Close removes one slot; it does not revoke descendants. Destroy removes
the object, its queued messages and every alias. Stopped-owner detach destroys
its endpoints and closes its remaining handles before image release. Other owners'
objects survive. No user-facing creation, grant, close or destroy syscall exists.
Task retirement now calls the mandatory architectural `revoke` hook before root
retirement. Both native task adapters implement it; the timer wrapper forwards it.
Failure retains the task and its memory for cleanup retry. This is automatic
retirement cleanup, not a complete service supervisor. Native fixed owner-fault,
preempted cancellation, blocked cancellation and cleanup-quarantine retry now have
surviving-peer evidence. Quarantined tasks retain authority until stopped cleanup succeeds.

## Development ABI

PSABI1 retains version 1 and existing calls 0-2. Calls 3/4 are nonblocking send/receive:
RAX=operation, RDI=version, RSI=task-local handle, RDX=user buffer, R10=length or
capacity, R8/R9=zero. Return RAX=status and RDX=value. Statuses 0-4 retain their
meaning; 5=Denied, 6=Again (empty/full), 7=TooSmall (value=required message bytes).
Call5 waits for endpoint readiness: RSI=handle, RDX=0 readable or1 writable,
R10/R8/R9=zero. RAX returns0 ready,8 cancelled,9 revoked; RDX returns0. Version,
argument and authority errors retain existing statuses. An already-ready endpoint
returns immediately. Cancellation is supervisor-only; users cannot target a task.
Lengths 1-64, checked user-window addresses, reserved fields and version are checked.
The current 64-call task limit and one-page payload admission remain development
constraints, not adequate long-running service policy.

Copy-in snapshots all bytes before queue publication. A read fault publishes
nothing and consumes no queue capacity. Receive checks capacity first. Copy-out
failure reports the written prefix but retains the entire queued message; retry
can overwrite that prefix. This is queue-atomic, **not destination-memory-atomic**.
Successful receive clears its slot and advances FIFO state once. Full/empty,
invalid handle and short-buffer results do not touch user memory. The exclusive
mutable owner spans authorization, copy and commit. Exact nested copy faults use
the existing recovery record without borrowing the suspended IPC owner.

## Sender And One-Use Replies

Calls6-9 extend the development ABI, not its production freeze. Version remains1,
RSI is a task-local handle, RDX a buffer and R10 a length/capacity; R9 remains zero.

| Call | Authority And Input | Successful Result |
| --- | --- | --- |
|6 Request|SEND endpoint in RSI; owned RECEIVE reply endpoint in R8;1-64 input bytes|Queued payload length; no synchronous wait|
|7 Metadata receive|RECEIVE endpoint;1-96 capacity;R8=0|32-byte header plus payload; total bytes|
|8 Reply|One-use reply token;1-64 input bytes;R8=0|Queued reply length; token consumed|
|9 Discard|One-use reply token;RDX/R10/R8=0|Zero; token consumed without sending|

Header: four little-endian u64 values at offsets0/8/16/24: sender task slot,
sender task generation, reply token, payload length. Payload begins at32. Sender
comes from the authenticated kernel Caller at enqueue, never from payload fields.
It is historical identity data, not proof of current liveness, a task capability,
badge, scheduling donation or user-selected credential. Roots are never disclosed.
Ordinary sends and replies return token0. A queued request whose return route has
been revoked remains readable with its historical sender and token0.

Each task has four separate reply slots. Tokens encode a non-wrapping32-bit slot
generation, type tag2 and one-based slot. They cannot be delegated or used as SEND,
RECEIVE, endpoint-destroy or readiness authority. Successful metadata receive
commits a token bound to the requester/root/root-generation, exact return handle/
object generation and original request endpoint. No permanent SEND grant is added.
The requester's reply endpoint must be owned by that requester. Tokens survive
closure of the server's receive handle, but not destruction of the request object.

Metadata receive checks output size and reply-slot quota before touching memory.
Short/full results do not dequeue. A copy-out fault reports its exact prefix but
does not mint a token or consume the message, even if token bytes were already
written. Only complete copy-out commits authority. Call4 denies queued requests
instead of silently dropping their reply route; call7 handles both message kinds.
Reply checks route and destination capacity before input access; input faults and
full mailboxes retain the token. Successful enqueue consumes it exactly once.
Discard recovers reply-slot capacity without sending. Close/destroy/detach prune
invalid reply slots while retaining high-water marks; task retirement clears its
own reply authority before image reuse. Queued historical sender data grants none.

Thirteen new host tests exhaust64 request/reply input-fault offsets and96 envelope
output-fault offsets, short output, spoofed callers, wrong types/tasks/generations,
replay, full reply queues, reply-slot exhaustion/discard/reuse, counter exhaustion,
return-route revocation, dead requesters/servers and ABI errors. PKIPC3 reuses the
same native slots at generation6. Real CPL3 tasks validate sender IDs, deny a wrong
return endpoint, recover an8-byte output prefix with an unminted-token denial,
retry a faulting reply input, consume/reject replay of a reply, then reuse and
discard its slot. The client checks transformed bytes. No permanent server SEND
capability exists. [Exact evidence](checkpoints/cycle253-native-ipc-reply-authority.md).

These are asynchronous primitives, not complete RPC: no per-request correlation
ID, deadline, synchronous Call, automatic cancellation result or guaranteed reply
capacity. Discard and service death do not yet notify a client waiting on its own
reply endpoint. Services must not be admitted assuming those guarantees. Add
kernel-owned request/deadline/cancellation accounting before general service use.

## Wait Ownership

One outstanding wait per task stores caller/root/root-generation, handle/object,
readiness and a non-wrapping64-bit ticket generation. No user buffer is retained.
The ticket is private kernel identity, not a user capability. States are Armed,
Parked, Notified, then consumed. An IPC slice saves the checked user context and
legacy FX state, quiesces both timers/entry state, restores the original root and
settles measured runtime before scheduler blocking. Waiting tasks cannot activate.

Scheduler block/wake/consume stage a bounded copy and commit after validation.
Wrong CPU/generation, uncharged dispatch, wrong wait kind, overflow and duplicate
notification reject without partially modifying the IPC transition. Generic event
wakes cannot wake an IPC waiter. The supervisor polls after every quantum and
park, closing the arm/park readiness gap. Each wake commits independently; a later
failure does not undo earlier wakes. This relies on the exclusive single-BSP owner.

Completion checks the ticket and scheduled wake reason, validates and patches
saved RAX/RDX/flags, consumes the wake and releases the wait once. Driver completion
must be failure-atomic; no fallible operation follows successful context update.
Required trait methods prevent wrappers from silently defaulting these operations.
Close/destroy/dead-owner invalidation produces Revoked for a parked peer; cancelling
a parked wait produces Cancelled. Detach clears the stopped task's own wait; its
supervisor must also tear down that scheduler identity. Generations survive detach.

`Slot::cancel_waiting` terminates a charged, quiescent waiter with its exact ticket
without completing or resuming the saved frame. Reap still runs revocation and
root retirement; the supervisor then removes the scheduler identity. Host tests
cover both parked and already-notified waits, wrong tickets, unsettled accounting,
repeat termination and failed-retirement retry. Native evidence includes one
parked owner termination and denied use of its detached ticket, not all wake/kill races.

Readiness is advisory, not a reservation: another operation may consume a message
or fill capacity before the resumed task retries. A notified Ready may precede later
revocation; the subsequent transfer must revalidate. There is no user-memory loan,
blocking copy, direct RPC, deadline, wait-many or automatic user-request restart.

## Invariants And Tests

| ID | Predicate | Current Verifier |
| --- | --- | --- |
| IPC-AUTH | Caller/table/root/generation and typed rights must match | Host identity/type/rights tests; native invalid handle and wrong-direction denial |
| IPC-REUSE | Stale cap/object/task generations never regain authority | Host close/reuse, object destruction and exhaustion; native five persistent-slot generations and old-handle rejection |
| IPC-BOUND | Finite allocation and queues; no mutation on quota failure | Host table/object exhaustion; native full queue, FIFO drain, writable wake and retry |
| IPC-COPY | Input fault publishes nothing; output fault does not dequeue | Every one of64 fault offsets in host tests; native input denial and four-byte partial-output retry |
| IPC-OWN | Detach invalidates owned objects before root release | Host failed-hook retry; native exit/fault/preempted-cancel/wait-cancel/quarantine retirement and surviving peer |
| IPC-WAIT | Charged, quiescent tasks block and consume one identity-bound wake | Host arm/park arrival, stale/replay/cancel/revoke/overflow tests; native three waits/two wakes/one cancellation |
| IPC-NATIVE | Real isolated user programs exchange actual bytes | Two fresh native boots, separate roots, transformed8-byte request/reply |
| IPC-CONSERVE | No older containment/ordinary-denial regression |17 survival cases, exact runtime/root accounting and ordinary denial per qualification |

The native client rejects an invalid handle, receive through SEND-only authority,
65-byte send and unmapped source. It sends 8 bytes; the server reads and transforms
them, sends 8 reply bytes, and exits 90. The client checks those bytes and exits 91.
The client first receives a supervisor cancellation, then both tasks block for
request/reply readiness without polling loops. Native selected GPR/SIMD and stack
checks survive resumption. Both tables retire automatically, all endpoints disappear,
and26 pages/12 data-scrub pages are released.

The separate PKIPC2 experiment reuses two owned slots through five generations
without resetting Space or its cap/object/wait high-water marks. Startup arguments
select only public test values; table lookup still authenticates every call. Each
round fills a four-message queue and rejects a fifth send before touching its
unmapped source. The first drains FIFO messages, rejects a short receive, recovers
a real four-byte partial output fault without dequeue, wakes a writer and completes
the transformed sum. Later rounds retire an enrolled owner through fault, preempted
cancellation, blocked cancellation or cleanup failure/retry. A waiting peer receives
Revoked, rejects further transfer/wait on the destroyed endpoint and completes
independent IPC on its surviving object. Generation1 rejects a zero-generation
handle; generations2-5 reject actual prior handles. Each round releases26 pages and
scrubs12 data pages. [Exact evidence](checkpoints/cycle252-native-ipc-pressure-lifecycle.md).

## Next Required Work

1. Add an owned monotonic deadline clock. Cycle254 supplies caller-owned tracked
   completion/cancellation and dead-service notification via calls10-13; see
   [request semantics](native-ipc-request-lifetimes.md). Call6 remains asynchronous
   mailbox delivery; no synchronous call, deadline or execution rollback guarantee.
2. Extend beyond the five fixed native lifetimes: arbitrary close/destroy/wake/kill
   interleavings, quota recovery, generation exhaustion, persistent quarantine and
   sustained pressure. Never reset authority counters to make a case pass.
3. Before general services: transactional bootstrap/admission, derivation-tree
   revocation, user delegation, generated wire layouts, audit provenance, shared
   memory/notifications, concurrency/SMP, priority propagation and sustained policy.

The bootstrap helper currently retains partial state on error and the diagnostic
halts; it is not a transactional general loader. Capacity exhaustion and object
destruction have host coverage and bounded native lifecycle evidence, not a general pressure/recovery policy. Queue
clearing is logical initialization, not a physical secure-erasure claim. Broader
stack, exception, clock, hardware and product-contract qualification remain open.

## Reference Boundary

The official [seL4 capability tutorial](https://docs.sel4.systems/Tutorials/capabilities.html)
was reviewed 2026-10-08 for the distinction between an object, a rights-bearing
capability and caller-local lookup. The [IPC tutorial](https://docs.sel4.systems/Tutorials/ipc.html)
was reviewed again for one-time replies on2026-10-08 at its [current page](https://docs.sel4.systems/Tutorials/ipc).
They are reference material only: PooleKernel imports
no seL4 implementation, ABI or verification claim. PKIPC1's bounded queues and
advisory readiness development protocol are PooleOS-specific. A kernel command shell,
foreign microkernel or scripted screen is not an alternative acceptance route.
