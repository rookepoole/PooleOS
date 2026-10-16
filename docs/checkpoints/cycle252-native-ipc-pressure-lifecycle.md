# Cycle252 Native IPC Pressure And Peer Lifetime

Result: PROGRESS. Usable native user-space ISO first, then the complete robust
N0-N39 microkernel, PooleGlyph/PDC and PooleGlass program. No new ISO yet.

## Implemented

- Explicit six-word user startup arguments initialize RDI/RSI/RDX/RCX/R8/R9 only;
  all other initial GPRs remain zero. Saved resumption does not reapply arguments.
  These are supervisor-selected data, not capabilities or a frozen startup ABI.
- `Slot::cancel_waiting(id,ticket)` accepts only the exact charged, quiescent wait,
  creates a retained Cancelled outcome and never resumes the frame. Reap/revocation
  and scheduler teardown remain mandatory. Failed retirement remains retryable.
- Native peers reuse the same owned slots in place across five generations. Space,
  capability, object and wait high-water marks are never reset. New image insertion
  is separate from deep mapping construction, preserving the existing stack guard.
- PKIPC2 exercises real CPL3 queue-full denial, writable blocking, short output,
  four-byte partial copy-out and intact-message retry, FIFO ordering, stale handles,
  enrolled-owner fault/cancel/wait-cancel/quarantine cleanup and surviving-peer IPC.

## Exact Native Evidence

Final capture `outputs/cycle252-nativethird.json/.log`:15 checks PASS,334.891s.
403 debug kernel tests,130 user-entry release,17 IPC release,24 VM release,
8 compile-fail and10 boot-exit:592 Rust executions.46 Python oracle tests pass;
two incompatible development feature combinations reject.

Two fresh67-marker QEMU/OVMF boots each preserve all17 old containment cases and
the original3-wait/2-wake/1-cancel request/reply. Each rejects800 altered-evidence
controls. Ordinary unsigned boot still denies execution. Read-only media, fresh
firmware variables, no guest network, host acceleration or sharing. All765 native/
oracle source bindings and captured sources remain unchanged, as does owner data.

| Round | Owner Result | Generation | Dispatches | Calls Client/Owner | Waits/Wakes | Revoked | CR3 Writes |
| --- | --- | --- | --- | --- | --- | --- | --- |
|0|Exit92, FIFO/retry|1|5|12/11|3/3|0|10|
|1|User UD fault|2|3|13/0|1/1|1|6|
|2|Preempted cancellation|3|3|13/0|1/1|1|7|
|3|Blocked-wait termination|4|3|13/1|2/1|1|7|
|4|Cleanup quarantine/retry|5|3|13/0|1/1|1|6|

Every surviving client exits93 after actual successful IPC. Generation1 rejects a
zero-generation handle; later generations reject real preceding-lifetime handles.
The partial output case writes4 bytes, returns Fault/4, then receives the original
message intact. Full-queue denial precedes access to an unmapped source. Four
death cases wake the peer with Revoked and deny further send/wait through the old
endpoint. The peer's separately owned endpoint remains usable. Total new measured
ticks1010972;36 root writes;130 released pages;60 scrubbed data pages.

Whole probe:385 root writes,746 released pages,343 scrubbed data pages. Measured
subtotal143828324 ticks includes prior measured suites and the new IPC rounds.
One earlier unmeasured dispatch remains unknown; this is not a complete total.

Kernel694648 canonical bytes,188 pages, entry0xC000,36-page guarded stack:
`7B1EF4DA3098A3102AA2BF132A17E8F0C4A7A312F963B181262E527EC4BF36BD`.
Linked image: `8A55B4369BE8D63B4743AF65B5B77F9265FC20CE2D39B8F95DE28D68CC4877B1`.
Canonical receipt `runs/native-user-entry-readiness.json`:
`DF8F0D515B1DB8817F65F3159B76FAC33C0A73568A92BCEFF7EFB82C210D79F9`.
Capture log: `297A30F9B74F62DF273A913647DF69C06FF1E94F53C14FCED769B7DB510F6223`.

## Failures And Repair

Preflight:402 tests passed, one new test incorrectly expected1 syscall from a
fixture that retains2. Corrected the assertion, not task accounting.

First bounded attempt:97.953s. Host/oracle checks passed; linking rejected text
end0x9645E beyond the0x95000 reservation. Added two pages within the existing192-page
cap: text/data0x97000, RELRO0xA8000, image0xBC000. No entry/stack/run-bound weakening.
Log `C2F04067395F32E786A95F57C896C218597B3C3375A1439F415489AC4FBE194B`.

Second attempt:187.171s. All older native cases passed; the new constructor hit
the kernel stack guard. Actual #PF error2: RIP0xFFFFFFFF8006623F,
RSP/CR2=0xFFFFFFFF800C0F80. Linked disassembly places it at the second4KiB stack
probe in PreparedImage::validate_timer. Passing large owned slots through nested
constructors compounded live stack frames. Repair: reuse peers/slots by mutable
reference and reinstall only a retired image; preserve split non-inlined build/
install paths. Both fresh guests then passed. General stack-bound proof is still
required; no guard was removed or stack enlarged.
Log `198EBA13EC0FE3121CC1B0134A9D5196D327CF1E928826F2E142335D2DE108BB`.

All failed candidate directories and logs remain. Guest120s, ordinary45s,
live-child360s and outer900s limits are unchanged.

## Continuity And Boundaries

Cycle251 receipt frozen verbatim in `tests/fixtures/cycle251-user-entry-readiness.json`:
`1744A690DC5276B054724F53BE85493988D8617043E641B86FF5FE3F3B902FCE`.
PooleGlyph Phase65 checkpoint and manifest freshly read; Phase66 Core IR boundary
audit remains next. Owner report unchanged:
`F75E4836FAA9DDD59BA62648FE9542415F2119B659A583FB3F5959F2F5CAE87B`.
Master checklist unchanged:
`A8C94719FAF9428C1F133010BA2603C0270C4E1EFD7327AF8EAB9C8C362ABB3D`.
Old execution-source evidence remains historical, never relabeled as fresh.

N13-CAPABILITY-IPC-001 next: authenticated sender identity, one-use reply ownership,
deadlines, transactional bootstrap/admission and sustained service budgets. Then
init/console, shell/files/two apps and optical ISO acceptance. Full N0-N39 work
continues afterward. Fixed single-BSP lifetimes do not prove arbitrary concurrency,
all revocation/wake/kill races, derivation-tree revocation, persistent supervision,
general quota recovery, service restart policy or production stack/hardware safety.
Four tasks/64 lifetime calls remain development bounds. Supervisor wait cancellation
and task termination are distinct; no user cancellation authority is granted.

No phase or flag closes.40 phases,301 subphases,8996 requirements,59 additions,
97 flags/42 open and20 gaps remain. USI-1/2 partial;3-5 not started. Full exact-
candidate canonical replay and188-page product-contract migration remain before
main merge. Main remains qualified through233. No release, signature, promotion,
firmware operation or physical-media write. Final metadata/publication checks are
recorded separately after the exact native receipt; no full-suite claim follows.

## Closeout

Initial metadata run:146 tests,145 passed/1 failed,51.863s unittest/52.703s capture.
The provenance test incorrectly advanced a frozen historical input count from79
to81. Kept that receipt immutable, corrected the assertion to78 current Rust files/
79 historical inputs, and explicitly recorded the two new unbound historical paths.
No native source or evidence changed. Log:
`CAEDBE24E305B14452E8C95CF43AE6F9253437EA0C7078355526F9A2B5B376ED`.

Repaired metadata suite:146 PASS in51.140s (51.984s capture), unchanged source and
owner report. Log `8ED4461BBBFE5D4DC69EC3D245FDA699F9428CA0077B0E5497B5B22AED4B0AB2`.
Architecture binds504 sources. Python inventory1301 is discovery, not full-suite
execution. Final conservation/staged-byte/publication checks follow this recording.
