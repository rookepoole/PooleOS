# Native Application Shell Bridge

Cycle282 implements the compiled user-space bridge for PAPP1. Native catalogue
wiring and guest qualification remain open. This is not an ISO acceptance receipt.

## Programs And Authority

`PooleAppShell` combines the existing console shell, streaming read-only file
commands, process-handle lifecycle policy and a bounded application job engine.
`PooleAppFiles` is a separately selected file-service policy. Legacy `PooleFiles`
still admits only its two exact configured peers. The app-aware service additionally
admits kernel-authenticated role slots4/5, across valid generations, only with a
live tracked reply token. It neither trusts a payload identity nor creates grants.
The native catalogue must reserve those roles exclusively for these two apps.
Kernel retirement revokes their requests and already-claimed reply authority.
Queued messages with no live reply authority are dropped; a denied reply does not
terminate the file service. This is a bounded role policy, not a general VFS ACL.

Shell control receives on its existing owned endpoint. Console traffic uses
caller-owned completions, so it cannot be mistaken for an application request.
The two application slots map to `text` and `numbers`, not arbitrary task IDs.
The process policy supplies the current admitted launch sequence and actual lease.
The native integration must verify that this sequence equals child generation;
the shell never accepts a generation provided by application payload bytes.

## Commands And State

- `start text|numbers`, `status text|numbers`, `stop text|numbers` use existing
  launch/process syscalls. Stop acceptance is not retirement or permission to exit.
- `text /PATH` and `numbers /PATH` operate on a started process. The app sends
  tracked READY; the shell returns RUN with the canonical path; the app reads the
  confined file service and sends RESULT; the shell acknowledges before displaying.
- `fault text|numbers` sends an authenticated FAULT job. The application binary's
  existing CPL3 UD2 path performs the fault; host tests model its terminal outcome.
- `ls`, `cat`, console editing and common shell commands retain existing behavior.
  Unknown names, nested/invalid paths, missing files and invalid numeric data do
  not become privileged commands or fabricated successful output.

Each job poll makes at most one syscall, including observation, receive, reply,
discard and stop. One cached READY per app and at most one transient reply/discard
are retained. Kernel-authenticated peer generation, kind, sequence, canonical
64-byte wire, status and successful-result bounds must agree. Foreign, stale and
untracked traffic cannot supply a result. Invalid authenticated app traffic blocks
that app; the selected job discards held replies and requests stop. Other apps
are not stopped by the selected app's protocol fault.

The32768-poll budget is bounded work, not elapsed time. Alternating kernel process
observations detect stop/fault/exit while a job waits. Timeout revokes held reply
authority and requests stop without inventing completion. Sequence exhaustion
returns the last acknowledged result, blocks further jobs until restart and never
wraps or kills the shell. A changed generation during a job aborts without stopping
the new child. Restart resets the job sequence only after actual process retirement
and new admission. The current shell serializes user commands; job cancellation
by interactive Ctrl-C and efficient sleeping remain future work.

## Qualification Boundary

127 Rust tests per debug/release profile include both actual application state
machines connected to the shell bridge in an IPC/lifecycle model. File data comes
from the actual immutable bundle responder; dedicated server tests exercise its
opt-in ACL. The model is not a real scheduler or memory-isolation proof. Tests cover
repeated changed-file workloads, empty/missing/invalid files, ACK backpressure,
malformed READY, foreign/stale/plain messages, app death, deliberate fault, restart,
revoked reply, mid-job generation change, timeout, result bounds and exhaustion.

17 ELF/code pairs independently reproduce with locked offline compilation and
unchanged no-import/no-writable-segment/no-final-relocation/object-target checks.
The app shell is15136 bytes (four RX pages); app file service2823 (one page).
13 prior binaries match exactly. PooleFiles and PooleFileShell changed; their old
native evidence is historical and must be replayed. No heap, RX limit increase,
new syscall, kernel parser or kernel source change is included.

Native integration must retain startup ownership metadata, derive actual SEND-only
control/file grants inside admission, and call Cycle281's owned startup replacement
before dispatch. Admission commits first; exclusive BSP/IF0 ownership must span
both operations and any handoff failure must retain owners and prevent dispatch.
Combined failure-atomic rollback is not implemented. Verify six roles,32 PMM records,
stack use and existing mapping limits in real guests. Then qualify both apps,
fault/recovery, remaining file/cleanup controls and sustained optical ISO operation.
All full-microkernel, PooleGlyph/PDC and PooleGlass obligations remain afterward.
