# Typed Native Launch Control

Contract: PLC1. Cycle303 implements a host-tested broker and explicit authenticated
transport foundation, not connected graphical launching. Existing native binaries
still use PCS1. No startup role, compositor factory, kernel privilege, lease,
mapping, stack allowance or code profile is added.

## Wire Contract

The payload is exactly32 bytes, little endian. Bytes0..4 are `PLC1`; byte4 is
request1 or reply2; byte5 is Start1 or Inspect2; byte6 is Text1 or Numbers2.
Byte7 is zero for requests or the defined reply status. Bytes8..16 contain a
nonzero request sequence below the maximum64-bit value. Bytes16..20 contain
the expected process generation. Bytes20..24 contain zero for a request or
the actual generation for a reply. Bytes24..32 must be zero. There are no raw
task IDs, process handles, endpoints, device grants or command strings.

Replies distinguish Admitted, Running, StopPending, StopClaimed, Retiring,
Absent, Terminal, Denied, LaunchFailed, Stale, Exhausted and Busy. Admitted and
LaunchFailed consume exactly the next generation and are valid only for Start.
Stale reports a different generation without process calls. Exhausted reports
the maximum generation without wrapping. Live/terminal states require a nonzero
matching generation. Denied/Busy/Absent retain the expected generation; Absent
may report a consumed failed-launch generation. A valid codec is not an
authentication or graphical-readiness proof.

## Process Ownership

The existing shell policy owns both factory capabilities. The CLI and broker
share launch transitions, with distinct exclusive pending-operation modes.
Starting an already-owned process first inspects its kernel completion. Running,
stop-pending, stop-claimed and retiring instances cannot be replaced. Only a
validated terminal observation permits a later launch step. Each poll performs
at most one process syscall. Backpressure repeats the same factory generation;
a retained result never repeats an admission. A failed launch consumes its
generation; denied authority does not. No graphical Stop/Terminate action exists.

The fixed broker retains one request/result until matching acknowledgment. Its
monotonic replay fence survives acknowledgment. Busy and stale replies consume
their request sequence without changing CLI work. A malformed process result
poisons the broker while retaining pending ownership; it does not manufacture
completion, free a process, or allow session closure. Callers must retain the
single broker/process-owner pairing for the session lifetime.

The wire generation is the process owner's factory-attempt sequence, not a raw
kernel task ID or surface handle. The current application dispatcher enforces
equality with admitted task generation on its successful path; preparation and
admission errors currently stop the development session. A host `LaunchFailed`
test therefore does not prove native recoverable failure. Before integrating
retry UI, qualify how failed attempts, prepared-image ownership/cleanup, task
generation and surface identity reconcile. Do not infer readiness from a counter
alone or change the existing fail-stop behavior without proving cleanup safety.
This is tracked by `FLAG-N13-LAUNCH-FAILURE-001`.

## Explicit Transport

Ordinary `console_ipc::rpc::Transport` still decodes only PCS1. The separate
`session_control::rpc::Transport` accepts PCS1 and PLC1 after validating the
kernel-supplied envelope against the configured peer and one-use RPC authority.
The compositor-side server sends control requests; the process-owning client
sends control replies. Inverted control/console directions are rejected.
Malformed envelopes, wire data, revoked authority and invalid transport state
poison this opt-in adapter. Backpressure alone is not failure.

Transport direction is not session authorization. The next integration must
bind a control request to an outstanding shell Read, bind its typed result and
acknowledgment, preserve terminal drafts and active file jobs, and reject sequence
exhaustion before any process effect. It must retain exact request/reply bytes
under pressure and suppress duplicate UI activation. No existing entry point
selects this adapter yet. Host fake-kernel tests do not establish native PLC1
execution or native authentication under the new mode.

Proposed session transaction for qualification: a control request replaces only
the response to Read at sequenceS. Its typed result retains S as the request ID,
travels on the next RPC, and is acknowledged with Written at S+1. Ordinary reads
resume at S+2 only after that acknowledgment. Reject exhaustion before launching,
retain the exact messages under pressure, and reject PLC1 while a Write/Close or
file job is active. This is a pending design, not an implemented state machine.

## Admission Gates

Keep the four-page shell and explicit seven-page window profile until a measured
architecture decision changes them. The repaired Cycle303 ordinary shell builds
at15440/16384 bytes; this excludes the currently unused PLC1 integration path.
That944-byte margin is not proof that the final connected shell fits. Measure the
actual connected code, relocation audit, guarded stack paths and embedded kernel
layout before admission. Never use a passing ordinary binary as evidence that
unused broker code has executed.

The rebuilt ordinary kernel remains134/208 pages with36 guarded kernel-stack
pages and the original guarded user-stack page. Its fixed read-only region has
360 bytes of padding before entry0x1C000. Aggregate remaining kernel pages do not
remove that local placement constraint: the connected profile needs an explicit
measured layout decision without silently enlarging allowances.

Native regression of the shared launch/authentication implementation is distinct
from graphical control qualification. Retain Cycle302 as a historical image.
Because the launcher requires exact current source, select a rebuilt ordinary
regression image only after the existing full preview matrix passes. That selection
is not PLC1 promotion. A connected profile must separately pass launch, delayed/failed admission, repeated
activation, app fault/retirement/restart, focus/draft preservation, keyboard access
and QEMU/VirtualBox visual/input checks. Retain failed builds and native attempts.

Compositor recovery, COM2-independent boot, persistent editing, event-driven waits,
all-path stack bounds, accessible PooleGlass, robust microkernel, PooleGlyph/PDC
and all N0-N39 production gates remain required.
