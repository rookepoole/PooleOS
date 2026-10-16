# Cycle265: Native Tracked Console Requests

Date: 2026-10-11. Previous progress: a21916721fd68981080b98c72d7b2be080ac92c0
on `agent/userspace-integration-iso`, draft PR81. Goal remains active. This is
implementation and native execution progress toward the usable integration ISO,
not another boot-screen change and not a production promotion.

## Implemented

- New user-space PRPC1 adapter uses existing tracked Begin10/Take11, Receive7 and
  one-use Reply8. One pending request/token survives backpressure. Kernel-produced
  peer identity and exact envelope/status/length are checked before PCS1 processing.
- Revoked9/zero is terminal and distinct from empty input or retry. Client exits163.
  Successful completion is consumed exactly once; committed close replies survive
  sender retirement. Kernel request semantics are reused, not weakened.
- PSESSION4 declares PRPC1 and records exact retirement dispatches. Frozen CR1-CR7
  require both bad-peer tasks to retire by64 dispatches with at most8 between them.
  The PSESSION3 oracle and old receipt identities remain historical and unchanged.
- Six user transport tests, two kernel lifetime/pressure tests and five Python
  oracle tests cover retained pending state, malformed authority/status/length,
  one-use completion, full caller mailbox, death before/after receive, committed
  reply survival, independent pair progress, exact bounds and false evidence.

## Executed Evidence

Public receipt: `runs/native-console-rpc-readiness.json`, SHA256
`6271FC899C9D4E6AF575D1CB2E1DE98AC012AFD898CB88DBFCAAD79D6CBA0260`.
It binds833 console sources,826 default sources and29 program-build sources.
Counts overlap; they are not unique-test totals or full canonical qualification.

- Two independent locked offline user builds match all five programs. All39 host
  tests pass in debug/release. Service code3096 bytes, SHA256
  `F282F3252131A4CFA97EDB27C4C3EFBE6F1BE666240A65A2D8166D0B3E2573EF`;
  client1900 bytes, SHA256
  `9418F58F51E936B65358984487919D140FAC91D5D4FB1D7A8C0B63A5ADB4568C`.
  Each remains one RX page, entry0, no imports/writable segments/remaining
  relocations. Prior init1073/counter1113/echo1288 program records match exactly.
- Three fresh read-only QEMU/OVMF guests use four private roots and one retained
  firmware page. Positive inputs45/52 bytes echo exactly; both programs exit0 at
  dispatch357/358 and402/403. Bad-peer service exits152 at6; client exits163 at7.
  All reclaim26 pages; independent init/counter reach512 dispatches. No timer
  preemption occurs in these budget-yielding sessions. Each rejects64 marker
  mutations. User UART output cannot become trusted kernel evidence.
- Console kernel tests483 debug/release; all24 default regression checks pass,
  with1710 overlapping Rust executions and110 Python oracle tests. Two fresh
  default containment guests each retain79 markers,17 survival cases and1111
  rejected mutations. Ordinary unsigned boot still denies kernel entry.
- Native capture73.219s, default capture397.828s; source and owner report unchanged
  during each. Native capture log SHA256
  `74024238F9E73F3AE7A2EF9598872C76586FC94ADFC56D049D2B9D6480481F1A`;
  default capture log SHA256
  `F04931359069B0D4EC53FC36D769392B8BAC3C41C3C7F69EDE89282371E01211`.
- Separate byte/source replay confirms two matching canonical/linked console
  kernels and all embedded programs. Normal canonical kernel SHA256
  `BF64CE3E828C855ACF4D08927DF47CC6A7962207B91C75422AB86AE092BC9A9F`;
  bad-peer SHA256
  `6C8DD2469A2B022C840B533B408835C4809949ECD5B6F1341AF7EAC381871FA6`.
  Both763400 bytes/205 pages. Image reservation208 and guarded stack36 unchanged.

Pre-closeout metadata:216/216 pass,52.265s tests/53.265s capture, log SHA256
`92161305BD7873507FDF11145CE0BC85326244BAB9DBCAF5FE5787902C278A3C`.
Conservation:152/152 pass,9.316s tests/10.781s capture, log SHA256
`85EB06589A51998C452F83ED3057C1E05707D422A9C318A38F98D23213E82D12`.
Both hold source and owner report unchanged during capture. Final artifact/source
checks run after this metadata is recorded; their receipts remain in ignored
`outputs/cycle265-*` evidence. No final-commit or full-canonical claim follows from
these earlier overlapping suites.1371 tests are discovered, not all executed.

## Failures And Preservation

The first focused run passed40/41: an old static test required the removed
`call(7, self.receive, ...)` wrapper. The test now follows the real ConsoleCalls
buffer wrapper plus RPC Receive7/Take11 path. Rebuilt source-bound program receipt
and reran41/41. Failed log SHA256
`0B5F1BBDD29C73934E48D9192FB5E09DDE36F3DDD0924443102C11BA0B25CA11`;
passing log SHA256
`C64E201AB6B33BEDFB0F0861EE346E599779C876F62738B8482E7D5EF9EADF1A`.
No native/code-build failure occurred in this cycle. A read-only debug-log lookup
used a nonexistent filename; corrected to `pooleos.debugcon.log`, not a guest error.

Storage: archived7 prior-cycle final-build objects,7 current console-build/media
objects and6 default-build/media objects. Each explicit resolved target stayed
under the intended outputs prefix; every archive member/count/hash was verified
before source removal. Total49 archives across264/265. Raw logs, receipts,
canonical ELFs and failures remain; final independent replay checks archives.
No broad tree cleanup, owner scratch deletion or physical-media writes occurred.

Live PooleGlyph remains Phase65; next Phase66 CoreIR metadata audit. Owner report,
Phase65 archive and the master-checklist SHA256 remain unchanged. No PooleGlyph
changes or reinterpretation of its machine-language maturity are claimed.

## Limits And Next Move

This fixes authenticated peer-death termination, not automatic restart, recovery
of a live-but-stalled service, user supervision, general loading or efficient idle.
The legacy nine bootstrap grants remain, including unused mailbox transport
grants; review least authority with the upcoming admission change. The existing
Peer decoder's Receive-only comment also needs clarification when next touching
program sources: PRPC1 validates and normalizes the authenticated envelopes before
using that decoder. No grant or decoder behavior is widened by this checkpoint.

Four fixed IPC/endpoint/bootstrap slots cannot host all five minimum demo roles.
Next: reviewed capacity and lifecycle authority for init/console/shell/two apps,
including ownership/rollback, image/stack measurement and native pressure/malformed
requests. Then real shell/read-only files/useful apps and optical ISO acceptance.
No shell, usable ISO or production release exists from this checkpoint.

Known main blockers remain the three native-kernel-load/transfer readiness tests
listed in the receipt plus full exact-candidate canonical qualification. Focused
default regression does not replace that gate. Forty phases301 subphases8996
requirements59 additions98 flags43 open20 gap groups remain. Full robust
microkernel, PDC/PooleGlyph, signed trust and accessible PooleGlass follow the
integration ISO. No phase closure, merge, signing, tag or release was performed.
