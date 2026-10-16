# Cycle255 Continuous Service Clock

2026-10-08. Goal ACTIVE; prior turn PROGRESS and saved as c958058. This cycle
implements PKCLOCK1, a continuous owned HPET epoch across task dispatch and idle.
The usable native user-space ISO remains the immediate milestone; full robust
N0-N39 PooleKernel, PooleGlyph/PDC and PooleGlass development continues afterward.

## Verified Candidate

Fifth native capture PASS,18 focused checks,328.953s:
434 debug kernel +138 user release +40 IPC release +24 VM release +9 compile-fail
+10 boot-exit +15 mapping =670 Rust executions.52 user-root oracle and22 focused
mapping/load/transfer tests pass; two incompatible feature builds reject.
Two fresh73-marker QEMU/OVMF boots each reject955 altered-evidence cases and
preserve all17 older containment cases, five pressure/death rounds, authenticated
reply authority and four tracked-request lifetimes. Ordinary unsigned denial PASS.
Read-only virtual media, fresh vars, no guest network, host acceleration or sharing.

Native log SHA25647DDC58097DE63251D14F930A719E3A3222A728B7C53B7B850222AF4F89326AF.
Receipt `runs/native-user-entry-readiness.json` SHA256
D52730EE4BDF217718BCB099DB9CAC2AC3E3F5610A1E84B1CEBF7F968181E793.
780 native/source dependency bindings verified by the qualifier. No native source
edits follow this capture. Kernel730184 bytes/197 pages, canonical
3BB97AD1DAFCD8A14203C4A38D503FD7FA72DAAE90661EBDD2B39F9BF22162FE;
linked975C1D8AFB3FE604A0F3BE285166106E09E3A6A8D5FFD251C04ED871399D85B2.

Each guest: raw origin339322151,last375894633,period10000000fs;
365724820ns elapsed,18381 samples,4000710ns across four bounded idle intervals,
12 child enters/12 leaves,6 mapping windows/6 verified revocations,24 MMIO writes.
The counter is never reset; original configuration is restored after child drain.
Whole probe still415 CR3 writes,876 released pages,403 scrubbed data pages.
The historical unmeasured dispatch remains unknown, not included in fabricated
complete runtime totals. This clock is not summed task CPU accounting.

## Implementation And Repairs

Non-copyable lease ownership precedes device writes; prepare rejects unsupported
counter width/period/revision, legacy routing and active comparators. Samples
allow equal raw values but poison the epoch on regression, overflow, uncertain
reads or configuration changes. Release failures retain the lease for retry.
Eight new host tests exercise each prepare/start/sample/release hardware failure,
including writes that take effect before returning an error, and boundary math.

Native ownership persists while task constructors keep their existing strict
supervisor mapping rules. Kernel MMIO exists only during acquisition, idle and
release windows; tasks use their separately validated timer mappings. Every
window removal checks raw zero leaves and translation failure. Final teardown
replays the complete empty temporary/metadata/ledger/MMIO region.

Failed captures are retained, all with unchanged source and PooleGlyph owner:
1. First218.453s: acquisition succeeded, then stage2094 rejected task restart
   because permanent kernel MMIO violated PreparedImage's absent-leaf rule.
   Raw guestC82A96F6D9FD05E2CEF82D735077F72FB8816945BA26D87C46C2184E3737690E.
2. Second223.765s: six mapping windows repaired restart; all four request rounds
   passed, then generic finish failed at stage2111. Raw guest
   F8CA555B19E333F0196933C7365992CB53635D1FDD085D9AE4D2D5C37D590465.
3. Third58.297s: added diagnostics/readback exceeded text0x9C000 by398 bytes.
   Log1849DBE84F007683B3A69F4011430D5FEFF7A05269E58FC55C30B92C1FD970B4.
4. Fourth198.063s: explicit stage5010 isolated the wrong TableMemory finish
   contract. It requires a temporary RAM alias; the clock never created one.
   Raw guest4A1CBE834787352593BA9E9D3D3FC7C2F997C93F8F6085CDC9C1D22D5A225455.

First/second/fourth outer summaries have the same log SHA256
71D30FF5DB19AB42E248C93AD442E342D17FE551765BBD2848DDD8FDBBC9E47C;
their distinct raw guest hashes above prevent conflating the failures.
Repair uses the correct empty-region verification, not a weakened admission gate.
Image grew196->197 pages within unchanged208-page capacity, text0x9D000,
RELRO0xAF000,image end0xC5000. Entry0xC000,36-page guarded stack,150s guest,
420s live-child and900s outer bounds remain unchanged.

Host preflight434 PASS33.469s, log
311A18214DC05F5D1E91BBBEF451D5D137F471D9D28A7855F4144DCEA757AE3C.
Initial52-test oracle PASS, log
E5B5B9035A7C545C72BCA7488EA566F10C75AD650A674E46E488A52228855B10.
Focused metadata PASS:155 tests,52.038s unittest/52.891s bounded capture,
zero failures/skips; source and PooleGlyph owner unchanged. Log SHA256
4CE08830E5981CF1672FDB0794327C5109150760CDDF2DE85693C71B4B7EF53D.
Conservation PASS:91 tests in8.290s/9.609s bounded capture; no failures/skips,
source and owner unchanged. Log SHA256
FF0968540099D3CB5A90E7224E5786D0A80DAA404C9F72DE656BBCF6611B98C2.
Final post-documentation replay and publication checks have separate local receipts;
this historical integrity replay is not fresh execution of older native profiles.
Architecture inventory has523 bound paths; test discovery has1310 tests,
not a claim that the full canonical suite ran or passed.

## Open Work

No timed IPC or new user ABI yet. Bind request deadlines to a clock epoch,
preserve first-terminal-wins through late replies/cancellation, wake once and
expire requests while all tasks are blocked. Define poisoned-epoch handling;
then transactional service admission and sustained budgets, init/console/input,
shell/files/two applications and actual optical ISO acceptance.

No interactive ISO, full canonical pass, main merge or production promotion.
Three older load/transfer readiness assertions still fail and remain named in
the focused receipt; product migration and exact-candidate canonical replay gate
main. No SMP, physical-clock failure recovery,32-bit wrap extension, suspend/resume
or general service recovery is claimed. Current native setup failures halt with
retained ownership. [Clock contract](../native-continuous-clock.md).

PooleGlyph Phase65 checkpoint re-read; Phase66 Core IR boundary audit remains next.
Owner conformance report unchanged F75E4836FAA9DDD59BA62648FE9542415F2119B659A583FB3F5959F2F5CAE87B.
Master checklist unchanged A8C94719FAF9428C1F133010BA2603C0270C4E1EFD7327AF8EAB9C8C362ABB3D.
Historical execution ledger unchanged65155E981FA217BD9D78218A4E0C0537A574D613ED9FB3E1EBD16511B6A1EA5D.
Cycle254 receipt frozen byte-for-byte as a historical fixture. No owner files,
signing keys, release tags, firmware or physical media changed.
