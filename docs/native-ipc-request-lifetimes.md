## Caller-Owned Requests

Cycle254 / PKIPC4 adds a separate tracked protocol; existing asynchronous call6
still uses a reply mailbox and does not acquire these guarantees implicitly.

| Call | Inputs | Result |
| --- | --- | --- |
| 10 Begin | SEND endpoint, source address,1..64 bytes | Ok and task-local request handle |
| 11 Take | Request handle, output address,1..96 bytes | Pending: Again; success:32-byte sender header plus payload; terminal error: status and zero bytes |
| 12 Cancel | Request handle; all other arguments zero | Pending becomes Cancelled; already terminal denies |
| 13 Wait | Request handle; all other arguments zero | Return terminal status or block on an identity-bound scheduler ticket |
| 14 Timed Begin | SEND endpoint, source address,1..64 bytes,R8=1..1000000000ns,R9=0 | Ok and epoch-bound request handle; Cycle256/PKIPC5 |

PSABI1 still uses RAX call,RDI version1,RSI handle,RDX address,R10 length;
R8/R9 must be zero for10-13. RAX is status,RDX the returned handle/byte count.
Handle type3 and non-wrapping32-bit generation are separate from endpoint type1
and reply type2. Four request records per task reserve completion storage before
publishing input. Only that authenticated task/root/root-generation may take or
cancel a request. Identical numeric handles in different tables are not global
bearer authority. No allocation, copy or queue failure consumes an empty slot.

The record binds the exact destination object and, after successful metadata
receive7, the receiving Caller. Reply8 commits directly into reserved storage;
Discard9 commits Cancelled. Destination destruction or claimed receiver retirement
commits Revoked. A completed success survives later service death. Cancel invalidates
reply authority; later reply/discard rejects. Caller retirement drops its records.
All generation high-water marks survive retirement. No result depends on a free
reply queue slot. A queued cancelled request can still be read, with token zero;
consuming/reusing its request slot cannot revive the stale route.

Wait observes but does not consume. Take consumes a stored error without touching
user memory, after validating the argument shape. TooSmall or partial output
Fault retains a successful result for retry; only complete copying consumes it.
Completion between arm and park is observed once after parking. Kernel wait
cancellation and client request cancellation remain distinct operations.

This is not synchronous Call, scheduling donation, exactly-once service execution,
rollback, delivery assurance or a deadline. Cancellation controls the terminal
result, not side effects already performed by a service. Dead unclaimed delegated
receivers cannot be inferred from a live shared endpoint. A malicious live service
can still ignore an untimed request; call10 never acquires an implicit deadline.
Current execution is serialized on one BSP; SMP/interleaving qualification remains.

Cycle255 qualifies the [continuous service clock](native-continuous-clock.md) as
a prerequisite. Cycle256 adds [timed request expiry](native-request-deadlines.md)
and the all-blocked wake path through call14. The first terminal result wins;
timeout invalidates late replies but cannot undo a service's previous side effects.

Native generations7-10 prove success, discard, queued service death and claimed
service death. Each client first cancels/consumes a separate request, later waits
and consumes the real outcome, rejects repeat take, queries the ABI and exits97.
Success retries an eight-byte partial completion copy; server reply/discard replay
denies. Intentional service deaths useINT3; assertion failures useUD2. These are
actual isolated tasks, not a shell or general service loader.
