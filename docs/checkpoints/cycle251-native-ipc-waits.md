# Cycle251 Native IPC Waits And Retirement

Result: PROGRESS. The native user-space integration ISO remains the immediate
milestone, followed by the complete robust N0-N39 microkernel. No new ISO yet.

## Implemented

PKIPC1 now supports PSABI1 call5 advisory endpoint readiness. Private tickets bind
caller, root, root-generation and a non-wrapping wait generation; one wait per task,
no retained user buffer or message reservation. Armed/parked/notified/consumed
states connect to charged, quiescent task suspension and actual saved-context
resumption. Staged scheduler block/wake/consume avoids partial queue/counter changes.
Supervisor cancellation and revoked-endpoint results are distinct. Close/destroy/
owner death invalidate parked waits; stopped-owner detach preserves high-water marks.

Slot retirement requires an architectural revocation hook before root retirement.
Native task adapters implement it; the timer wrapper forwards both revocation and
wait completion. Failed completion or revocation retains retryable ownership.
Required trait methods prevent silently inherited no-op/reject implementations.
The native client checks selected GPR/SIMD and stack state across waits. Both tasks
exchange real transformed8-byte messages and exit91/90 without polling loops.
[Detailed contract, invariants and limits](../native-capability-ipc.md).

## Verified Candidate

-15 qualification checks pass in289.906s.401 debug kernel tests,128 user-entry
  release,17 IPC release,24 VM release,8 ownership compile-fail and10 boot-exit:
  588 Rust executions.43 Python oracle tests and2 incompatible-feature rejections.
-Two fresh62-marker QEMU/OVMF boots each preserve17 containment cases and reject665
  altered-evidence controls. Ordinary unsigned boot denial passes. Read-only media,
  fresh firmware variables, no guest network, host acceleration or host sharing.
-Each IPC run:3 waits,2 readiness wakes,1 cancellation,5 dispatches,0 preemptions,
  9 client calls/4 server calls,10 root writes,1840 measured ticks. Automatic
  retirement removes2 owners/all objects;26 pages and12 scrubbed data pages released.
-Whole probe:349 root writes,616 released pages,283 scrubbed data pages. Earlier
  runtime suite136815074 ticks, unknown-case healthy peer6000479 ticks; measured
  subtotal142817393. One unknown dispatch remains unknown, never a zero/global total.
-All763 native/oracle bindings, captured source files and the owner's dirty report
  remain unchanged throughout the final capture. No full canonical replay is claimed.

Kernel686456 canonical bytes,186 pages, entry0xC000:
`962AB737320243A627AF74E6BA0A8A1A33DA096E03E2D45C8A35AB0B39534CC4`.
Linked image: `FEB7E0EFF629488FFEE72346235E848EBA5E1B80F44A82B3CA3E24137FA1B0DA`.
Receipt `runs/native-user-entry-readiness.json`:
`1744A690DC5276B054724F53BE85493988D8617043E641B86FF5FE3F3B902FCE`.
Capture log: `84D41938F527A8903D5DF231FF8BFC459E6DA8F1796A40FE185D82DF317A0206`.
Raw evidence: `outputs/cycle251-native-seventh`, `outputs/cycle251-live-seventh`.

## Retained Failures

| Attempt | Result And Repair | Seconds | Capture SHA256 |
| --- | --- | --- | --- |
| nativefirst | Test accessed private CpuImage field; fixture now carries its existing admission |6.203|6293B438ECA8A0212D222EB0BC528E21735FD220F22985CBCE60D4B86EDA0AC6|
| nativesecond | Stale synthetic root-write count373 corrected to379 |42.078|F4FD60EAD2D262B9C9256E1A5A401CA76D116D7AB77DD10099490F9338CB96E2|
| nativethird | Text0x9461E exceeded0x94000; reservation moved one page |70.375|1C3C80021E3C5EA0000FB9D3E544A16268340F58734AA730DF256D6C2F788232|
| nativefourth | Guest stopped stage135 after all17 containment cases; timer wrapper lacked wait/revoke forwarding |184.016|F8E579DC237EB302407ECC716C1E6A0E73835876E5D447318CC04CC182B6CE91|
| nativefifth | New line-number diagnostic needed explicit u32-to-u64 conversion |38.407|43FFFA37E65066D96FA240D028A8D9C9606BD6E5CEFE762D0EB5B8C967678CDE|
| nativesixth | Source-forwarding assertion did not accept rustfmt line breaks; whitespace-aware assertion added |40.672|AACE8FAD2B655ED2B90D6DA820A6D95EE838178594813A3EE235A77AB05F2834|

Preflight also found an unqualified Status path; it was qualified before bounded
capture. No failed native run is erased. Text/data start0x95000, RELRO end0xA6000,
image end0xBA000 remain within192 pages. The36-page guarded stack, entry0xC000,
guest120s, ordinary45s, live-child360s and outer900s bounds remain unchanged.

## Continuity And Next Move

Cycle250 receipt is frozen verbatim in `tests/fixtures/cycle250-user-entry-readiness.json`:
`EB1AE8097D9418F95AFCD8ECF41F960C75B3B50E8B6AFC4245602B632D86F48D`.
PooleGlyph Phase65 checkpoint/manifest were freshly inspected; Phase66 Core IR
boundary audit is still next. Owner report remains
`F75E4836FAA9DDD59BA62648FE9542415F2119B659A583FB3F5959F2F5CAE87B`;
Phase65 zip `F3CCEB701CF76274D9464A0958BF6106888FB34F3C0BFBD55DE4ACE03C427ABC`;
master checklist `A8C94719FAF9428C1F133010BA2603C0270C4E1EFD7327AF8EAB9C8C362ABB3D`.
The old execution-source ledger remains historical, not rebound as fresh execution.

N13-CAPABILITY-IPC-001 continues: native enrolled-owner fault/cancel/quarantine/
revocation/stale handles, writable wait/queue saturation/output faults, pending-wait
termination, persistent task generation reuse, authenticated sender/one-use replies,
deadlines and transactional admission. Native2-exit retirement is not all death-path
qualification. Cancellation is trusted supervisor-only; readiness is advisory.
General event multiplexing, service supervision, larger budgets, SMP and production
stack/hardware qualification remain open. Then USI-3 services, USI-4 shell/apps,
USI-5 optical acceptance, followed by the complete robust microkernel program.

No phase/flag closes:40 phases,301 subphases,8996 requirements,59 additions,97 flags/
42 open and20 gaps. USI-1/2 remain partial;3-5 not started. Full candidate replay,
186-page product-contract migration,25 stale native admissions and22 stale static
closures remain. Main is qualified only through233. No merge, release, signature,
promotion, firmware change or physical-media write; branch backup uses draft PR81.

## Closeout

The first142-test metadata capture had2 stale expectations: architecture schema
still capped497 sources and the roadmap test expected Cycle250's qualification
label. Corrected to exact500 sources and the new scoped label; native code and
receipt unchanged.50.990s unittest/51.860s capture, log
`7FD40D8026F9FB9C478008C239CBC9F6D48FBE8CC87CE4A139233E9812CA0FAF`.
The second142-test run exposed the next stale cycle assertion in the same test;
250 was corrected to251 without altering historical250 assertions.52.465s unittest/
53.313s capture, log `E44EAAFA2DB879DEFE3E370DB30A28062620DCE3424200C8EA77D8D0617AB2B3`.

The repaired checklist/architecture/roadmap/oracle suite passes142 tests in54.940s
(55.812s capture), log `19D05F0A0E303D21B9EF1E5612BF6B07538F80C42C10B10B3B5587027F753472`.
Final conservation and publication checks follow metadata recording. Python
inventory is1297 tests; discovery is not full-suite execution. Architecture binds500
sources, and the kernel contains76 Rust files. Current read-only projection remains
2/27 native admissions and5/27 static closures, not new guest evidence. Firmware is
source-current; boot-trust/ELF aggregates remain stale. No host-only result is
promoted to native or production evidence.
