# Native Capability IPC

Cycle250 / PKIPC1 is an original, bounded PooleKernel mechanism, not a complete
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
The explicit probe teardown is not yet automatic service-lifecycle enforcement.

## Development ABI

PSABI1 retains version 1 and existing calls 0-2. Calls 3/4 are nonblocking send/receive:
RAX=operation, RDI=version, RSI=task-local handle, RDX=user buffer, R10=length or
capacity, R8/R9=zero. Return RAX=status and RDX=value. Statuses 0-4 retain their
meaning; 5=Denied, 6=Again (empty/full), 7=TooSmall (value=required message bytes).
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

## Invariants And Tests

| ID | Predicate | Current Verifier |
| --- | --- | --- |
| IPC-AUTH | Caller/table/root/generation and typed rights must match | Host identity/type/rights tests; native invalid handle and wrong-direction denial |
| IPC-REUSE | Stale cap/object/task generations never regain authority | Host close/reuse, object destruction and exhaustion tests |
| IPC-BOUND | Finite allocation and queues; no mutation on quota failure | Host table/object exhaustion, FIFO wrap/full/empty tests |
| IPC-COPY | Input fault publishes nothing; output fault does not dequeue | Every one of64 fault offsets in host tests; native unmapped copy-in denial |
| IPC-OWN | Detach invalidates owned objects before root release | Host dead-owner/unrelated-peer test; native explicit owner teardown |
| IPC-NATIVE | Real isolated user programs exchange actual bytes | Two fresh native boots, separate roots, transformed8-byte request/reply |
| IPC-CONSERVE | No older containment/ordinary-denial regression |17 survival cases, exact runtime/root accounting and ordinary denial per qualification |

The native client rejects an invalid handle, receive through SEND-only authority,
65-byte send and unmapped source. It sends 8 bytes; the server reads and transforms
them, sends 8 reply bytes, and exits 90. The client checks those bytes and exits 91.
Both kernel-owned tables are explicitly detached, all endpoints disappear, and
26 pages/12 data-scrub pages are released. Polling is bounded development code,
not scheduler blocking. Native stale/revoked/dead-peer/queue-saturation/copy-out
controls are still needed even though corresponding core host tests pass.

## Next Required Work

1. Add owned wait records, atomic block/wake and cancellation transitions; no lost
   wake, duplicate completion, stale task generation or detached saved context.
2. Integrate detach/revocation into success, fault, cancel and quarantine paths,
   with cleanup retry, explicit dead-peer results and retained ownership on failure.
3. Add authenticated sender identity, one-use reply ownership, deadlines and
   cancellation races. Two ordinary queues are not authenticated RPC reply tokens.
4. Add native saturation, stale/revoked handle, partial output, dead-peer and
   repeated lifecycle tests. Keep quotas failure-atomic across all mutations.
5. Before general services: transactional bootstrap/admission, derivation-tree
   revocation, user delegation, generated wire layouts, audit provenance, shared
   memory/notifications, concurrency/SMP, priority propagation and sustained policy.

The bootstrap helper currently retains partial state on error and the diagnostic
halts; it is not a transactional general loader. Capacity exhaustion and object
destruction have host coverage, not a general pressure/recovery policy. Queue
clearing is logical initialization, not a physical secure-erasure claim. Broader
stack, exception, clock, hardware and product-contract qualification remain open.

## Reference Boundary

The official [seL4 capability tutorial](https://docs.sel4.systems/Tutorials/capabilities.html)
was reviewed 2026-10-08 for the distinction between an object, a rights-bearing
capability and caller-local lookup. The [IPC tutorial](https://docs.sel4.systems/Tutorials/ipc.html)
was available on this review. They are reference material only: PooleKernel imports
no seL4 implementation, ABI or verification claim. PKIPC1's bounded queued
nonblocking development protocol is PooleOS-specific. A kernel command shell,
foreign microkernel or scripted screen is not an alternative acceptance route.
