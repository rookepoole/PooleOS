# Cycle250 Native Capability IPC

Result: PROGRESS. Native user-space integration ISO remains the immediate product
milestone, followed by the complete robust N0-N39 PooleKernel. No new ISO yet.

## Implemented

PKIPC1 adds original kernel-owned endpoint objects and per-task capability tables,
authenticated caller/root/generation binding, attenuating bootstrap delegation,
stale/type/rights denial, bounded FIFO messages, copy-fault-safe queue commits,
object-wide alias revocation and explicit stopped-owner detach. Actual CPL3 peers
exchange8-byte request/reply messages through two granted endpoints. This is
bounded nonblocking IPC, not complete native RPC or service lifecycle.
[Contract, invariants and remaining work](../native-capability-ipc.md).

N13.5/.7 and N14.1/.2/.5/.7 are partial; N14 moves from not-started to partial.
No phase or implementation flag closes. The inventory remains40 phases,
301 subphases,8996 source requirements,59 additions,97 flags/42 open and20 gaps.
21 phases are partial,1 blocked,18 not started,0 complete.

## Verified Native Candidate

-15 qualification checks pass in289.094s.392 debug kernel tests,126 repeated
  user-entry release tests,11 IPC release tests,24 repeated VM release tests,
  8 ownership compile-fail tests and10 boot-exit tests:571 Rust executions.
-42 Python oracle tests pass; two incompatible development-feature builds reject.
-Two fresh62-marker QEMU/OVMF boots preserve17 containment cases and prove the
  native exchange. Each rejects660 altered-evidence controls; ordinary unsigned
  boot denial also passes. No network, acceleration, host share or writable media.
-Each IPC run:3 dispatches,1 preemption,8 client calls/3 server calls,6 CR3 writes,
  1001454 measured ticks, exit91/90,2 detached owners,0 remaining objects.
  Whole probe:345 CR3 writes,616 released pages,283 scrubbed data pages.
-The earlier16-case runtime suite remains separately measured; the lost-sample
  case still reports one unknown dispatch. No complete global time total is claimed.
-All762 native/oracle bindings, the complete captured source set and the owner's
  dirty PooleGlyph report remain unchanged during final qualification.

Kernel679928 canonical bytes,185 mapped pages, entry0xC000, unchanged192-page cap:
`C640B64B6FF6AEA171468DBC56B0C7AEC4E45956AD28A41ECB842AE2D9672B09`.
Linked image:
`A2536C4773558D2019FB51513CA3A76CA2F12CA393D66EBE708DC8927D9C899A`.
Receipt `runs/native-user-entry-readiness.json`:
`EB1AE8097D9418F95AFCD8ECF41F960C75B3B50E8B6AFC4245602B632D86F48D`.
Final capture log:
`84D41938F527A8903D5DF231FF8BFC459E6DA8F1796A40FE185D82DF317A0206`.
Local raw evidence: `outputs/cycle250-native-third`, `outputs/cycle250-live-third`.

## Retained Failures

1. Initial freestanding adapter compile failed: scheduler and SMP TaskId types were
   compared directly, plus an unqualified ImageAdmission import. Fixed by explicit
   slot/generation comparison and qualified type.38.437s, log
   `D2043B1D2816DF3C76E317B219139B83854688F546E850680C3C602CDAC83AF6`.
2. Second link failed before any guest: text ended0x935FE past0x92000 and relocation
   data ended0xA2100 past0xA2000. Text/data start moved to0x94000, RELRO end0xA5000,
   image end0xB9000, all within the existing cap.71.516s, log
   `BEAD887BC04E5E61AB8F34ED69E62B9C1F51876CB57F72330A9863C177321A97`.

An initial patch context mismatch made no edit; it was corrected after reading the
actual signature. No failing guest was discarded. Guest120s, ordinary45s,
live-child360s, outer900s, entry0xC000 and36-page guarded stack bounds are unchanged.
The new probe is a non-inlined sibling, not nested under earlier constructors.

The first140-test metadata run found one stale detailed N14 `not_started` heading
after its ledger/overview moved to partial. The phase heading and table were
aligned; no native source or receipt changed.53.020s unittest/53.875s capture,
log `037BB8E6DDB1332BED2106EDA734BBAFE19312F49F1EEE7C8E9F6DC5BCCB3C83`.

## Continuity And Limits

Cycle249 receipt is frozen verbatim in
`tests/fixtures/cycle249-user-entry-readiness.json` with SHA256
`08F3170877F13DD5A0171AFB26DCF959B1597D2AA7AC3BFCFBAAA1A774519185`.
PooleGlyph is still Phase65; Phase66 Core IR audit is next. Owner report hash
`F75E4836FAA9DDD59BA62648FE9542415F2119B659A583FB3F5959F2F5CAE87B` and
master checklist hash `A8C94719FAF9428C1F133010BA2603C0270C4E1EFD7327AF8EAB9C8C362ABB3D`
are unchanged. Old execution-source ledger is not rebound as fresh execution.

Next: N13-CAPABILITY-IPC-001 continues with scheduler waits/wakeup, cancellation,
reply identity and task-lifecycle revocation, then USI-3 services, USI-4 shell/apps,
and USI-5 optical acceptance. Host tests of stale handles, exhaustion and dead
owners are not native race qualification. Full candidate qualification,
185-page product-contract migration,25 stale native admissions and22 stale static
closures remain. No merge, production promotion, signing, release, firmware or
physical-media operation occurs. Main remains qualified through Cycle233;
development is backed up through draft PR81.

## Closeout Verification

The corrected checklist/architecture/roadmap/oracle suite passes140 tests in
51.072s (51.922s capture), log
`1A01D445708BE6876EF50417CFC788EF0CCA6AFF42BDAB19815A4EF7A406084E`.
Architecture binds497 sources. The full Python inventory is1295 tests; discovery
is not full-suite execution. Current read-only projection remains2/27 native
admissions and5/27 static closures; it is not new guest evidence. Firmware is
source-current while boot-trust and ELF aggregate gates remain stale. Final
conservation and publication checks follow the metadata recording step; full
canonical qualification is not performed or inferred from these focused results.
