# Native Console Tracked Requests

Cycle266 replays the unchanged user transport on the expanded IPC core and
reviewed207/208-page layout, preserving the original36-page guarded stack.
See [current evidence](checkpoints/cycle266-native-session-capacity.md).
The Cycle265 image sizes and executions below remain historical.

Cycle265, 2026-10-11. The invariants below were frozen before implementation.
Three fresh native guests now pass exact echo/close and bounded peer-death
termination; all24 default regression checks pass. See the
[checkpoint](checkpoints/cycle265-native-console-rpc.md) for receipts and limits.
Cycle264 remains immutable historical evidence for the previous transport.

Use existing PSABI1 tracked Begin10/Take11, Receive7 and one-use Reply8.
PCS1 payload/sequence/device rules remain unchanged. PRPC1 replaces the old
send3/mailbox transport; it is not wire-compatible transport negotiation with it.
PSESSION4 must explicitly identify PRPC1. Neither user program links the kernel.

- CR1: One outstanding client request or service reply token. Backpressure retains
  exact state and cannot submit another request or repeat a committed UART write.
  Handles come only from successful kernel calls, not payloads or startup text.
- CR2: Receive7 validates the configured sender, exact64-byte envelope/32-byte
  payload, and nonzero generation-bound reply token before processing PCS1.
  Take11 validates the configured service identity and a zero reply-token field.
  Token shape checks are sanity checks, not authority; the kernel owns validation.
- CR3: Service Reply8 consumes its token only on exact successful32-byte transfer.
  Successful Take11 consumes the client request before decoding its completion.
  Again6/zero means pending; all unexpected status/value combinations are fatal.
- CR4: Revoked9/zero from Take11 is a distinct terminal outcome, not empty input,
  EOF, retry or a claim of successful service recovery. Client exits163. No timeout
  inference or unauthenticated peer-status probe may manufacture this outcome.
- CR5: A close reply already committed to caller-owned completion storage survives
  service retirement and endpoint/mailbox pressure. An unfinished request completes
  as revoked when its receiver/endpoint dies; it does not require mailbox space.
- CR6: Fresh positive guests echo distinct host input, then both console programs
  exit0/reclaim26 pages and independent init/counter continue to512 dispatches.
  Wrong-peer control must service-exit152 then client-exit163, reclaim26 pages and
  preserve independent progress. Freeze the control bound: both retire by64
  dispatches, and client retirement occurs within8 dispatches of service retirement.
  No native pressure/malformed-request claim without separate native controls.
- CR7: Preserve ordinary unsigned denial, default containment, fixed205/208 image
  and36-page stack bounds, retained failures and prior immutable receipts. Kernel
  request semantics are reused, not weakened to fit the console. No shell/ISO,
  restart/general init/loading, efficient idle, hang recovery or production claim.

Alternatives considered: existing tracked completions (selected); empty-mailbox
inference (cannot distinguish idle from dead); periodic duplicate sends (side effects
and no authoritative death outcome); new kernel peer-watch API (unnecessary added
mechanism); timed reads alone (idle input is not service death). Live-but-stalled
service recovery, deadlines and interrupt-driven input remain later work.
