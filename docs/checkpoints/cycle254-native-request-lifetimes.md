# Cycle254 Native Request Lifetimes

2026-10-08. Goal ACTIVE; PROGRESS, not production completion. USI-2 partial.
Two fresh72-marker QEMU/OVMF boots pass all17 older containment cases, five
pressure/death rounds, prior reply authority and four new tracked-request lifetimes.
935 altered-evidence controls per guest and ordinary unsigned denial pass.
Read-only virtual media, fresh vars, no guest network, host acceleration or sharing.

Exact candidate17 focused checks PASS,329.906s outer capture:
426 debug kernel +130 user release +40 IPC release +24 VM release +8 compile-fail
+10 boot-exit +15 mapping =653 Rust executions.50 user-root oracle and22 mapping/
load/transfer oracle tests pass; two incompatible feature builds reject.
Log SHA2566076B20F81ECE3D25E260DCDB8E17B2F61933CF18C417AB52D3F614F440380B8.
Receipt `runs/native-user-entry-readiness.json` SHA256
61C580013B54AC0D4FB638A5F5C65D6C0CEA3FE51612399773E48FE26D5B67A7.
Kernel725976 bytes/196 image pages; canonical
5F0721E2DE60A6E772506035C25EEC7DD5ED640408E4B61A2B3C3CA8A244430F;
linked B27A7439F23E43BEC667F360161A7C6BC4AE6DA502ADDCB97AAAA60EBF4886AB.

Each new round:3 dispatches,0 preemptions,1 wait/1 wake,6 CR3 writes.
Calls [11,5]/[10,5]/[10,0]/[10,2], outcomes Ok/Cancelled/Revoked/Revoked.
Measured ticks [2001,1482]/[1332,1394]/[1332,58]/[1332,1137].
Whole probe415 CR3 writes,876 released pages,403 scrubbed data pages.
The earlier one unknown dispatch remains unknown; measured subtotals are not a
complete global runtime total. Metadata closeout validation recorded separately below.

No new interactive ISO. No full canonical pass or main merge. Three older
load/transfer readiness assertions still fail the current tree; named explicitly
in the focused receipt and preserved as production-gate blockers. The focused
PASS does not suppress those failures. All four failed native captures below
are retained. No native source edits after the passing qualification.

First metadata capture:152 tests/17 failures,20.323s unittest/21.203s capture,
log B7F4BF884D9546A4C01E30DA641F6846B2C219D2D8348547541423EA3DC67B14.
Repaired stale schema cycle/source counts, current source delta86 vs old79 inputs,
and historical/current mapping distinction. Refreshed recorded gate projection:
2/27 retained profile admissions pass,4/27 static source closures current;
revalidation closure is now stale too. This read-only projection is not execution.
Second metadata capture:152 tests/5 failures,39.138s unittest/39.968s capture,
log59CF735A43CEF94BE5D1CD0311E6391258E2A0C0EF68BDFFE8318A2D9439CAA0.
Repaired expected stale-profile count23 and comparison with the release gate's
existing first-eight-errors display limit; all errors still cause rejection.
Final metadata capture152/152 PASS,51.682s unittest/52.531s capture,
log F7978994F628C4094A2A7CDE8CE894584B5252E52B8D55BB9C3EC6AA65D91980.
This validates roadmap/history/current bindings, not the full canonical suite.

Real kernel changes: per-caller request storage, type3/generation32 tokens,
Begin/Take/Cancel/Wait syscalls10-13, one terminal outcome, reserved completion
capacity, service-object/claimed-receiver revocation, existing scheduler parking
and wake completion, no mailbox capacity dependency. Four records per task.

Host426 tests initially PASS21.219s, log
A8CA55B505E02B82C78969F64F2128EE1488785F4E08AF1980834F5A448D8062.
Ten new tests cover all64 request/reply input offsets and96 completion copy
offsets, ownership/type/root/generation spoofing, first-terminal-wins, successful
reply preserved through subsequent death, delegated receiver death, queue-full
independent completion, slot pressure and non-wrapping generations, caller death,
completion before park, single wake and single take.

Failure history, all captures source/owner stable:
1. Nativefirst64.250s linker text9AFFE>99000/RELROAA290>AA000/BSSBF098>BF000.
   Log099C049433016F12368CE377FB66F3DD19A392B7C307F39F7126F17BDEEAABC7.
2. Nativesecond40.594s old-layout synthetic marker prefix rejected50 oracle tests.
   Log0A4A8096188057875E0DEE50FA4DBDDC14F7023492574BF297EB42C384A4AD72.
3. Nativethird43.937s3 old product-readiness assertions fail. Actual mapping/marker
   tests pass. Keep3 assertions and current-drift facts; not a full-suite pass.
   LogD5C814136CA7A3EE27DC0D0AD0C097F3816FF56B490B7BD7EBDDA2F5F1CE7D08.
4. Nativefourth194.594s120-second guest timeout after all old cases and new success
   lifetime. LogF8500D4AA33DAB8C3C0859454AD3BF2FA18A92F36BB523B11082FD1C4B5B9009.
   Explicit harness contract reconstruction to150s guest/420s child before fifth;
   no kernel task/timer/dispatch/stack bound change. Predict complete under150s.

Supplemental preflights: initial oracle after insertions48pass/2fail(final marker
index and synthetic root count repaired); expanded66 tests65pass/1fail(stale VM
layout marker repaired); broad87 tests84pass/3 old receipt failures retained.
None substitutes for exact-candidate native qualification.

Capacity migration192->208: guard208,stack209..244,guard245,handoff246..501,
temporary502,metadata guards503/509 anddata504..508. Five retained table pages
and36-page stack unchanged.196-page image text9C000/RELROAE000/endC4000.
Rust/Python include192,193,208 legal and209 pre-write rejection. Update real
VM-LAYOUT marker/spec and synthetic current-layout strings, not historical files.

Native test generations7..10 reuse two owned slots with22/23 payload kinds;
success/discard/queued death/claimed death, each client cancels a prior request,
consumes it, checks stale delivery has no live token, then waits/takes one actual
result and executes a version query/exit97. Server success/discard exits96;
deliberate deaths areINT3, test assertion failuresUD2. No server SEND-to-client grant.

Deadline gap: existing HPET ownership is dispatch-scoped and mapped only under
task roots. Summed CPU ticks are not a shared monotonic deadline clock. Keep this
as the next explicit kernel integration prerequisite, then transactional admission,
durable task budgets, init/console/input, shell/files/two apps and optical ISO.
Cancellation only controls terminal delivery; not rollback/exactly-once side effects.

Owner PooleGlyph Phase65 checkpoint andmanifest freshly read; Phase66 remains
next. Owner onlydirty tests/reports/conformance_report.json preserved
F75E4836FAA9DDD59BA62648FE9542415F2119B659A583FB3F5959F2F5CAE87B.
Master checklist preserved A8C94719FAF9428C1F133010BA2603C0270C4E1EFD7327AF8EAB9C8C362ABB3D.
Main remotely507782dfde4a554434173fdae7a1b25a170414ce; branch/PR81 prior9c0e82a.
No main merge, signing, release, firmware or physical-media operation.
