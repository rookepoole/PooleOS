# Cycle 192: Native AP Mailbox Oracle

Status date: 2026-09-26
Move: `N8-SMP-MAILBOX-ORACLE-001`, N8.5/N8.6 supporting N36
Requirement: `ADD-N36-RECEIPT-COVERAGE-001`
Open flag: `FLAG-N36-RECEIPT-COVERAGE-001`
Status: bounded native implementation and replay; pre-production

## Native Implementation

PooleKernel now exports complete saved quiesced AP mailbox inputs under the
versioned `PKMBX1` extension to PKSMP5. The snapshot has five context words,
fifteen baseline words and thirty-eight runtime words. Logging reads saved
state, not released AP memory; the existing forty-marker lifecycle is retained.

The separate Python oracle recomputes baseline and runtime FNV64 checksums and
validates field widths, AP identity and private placement, control/CPU state,
descriptor and guarded-stack geometry, xstate ownership, interrupt/fault state
and timing bounds. All three APs must share the same BSP context. Only validated
timestamp and dependent-checksum variation can normalize. Historical opaque
markers reject. This validates bounded evidence consistency, not authenticity
or resistance to every coherent forgery.

## Exact Native Evidence

Build ID: `PKBUILD1-CYCLE192-N8-MBX-ORCL-V01-0000000001`.
Canonical image: 530,072 bytes, 1,327 relocations, entry offset `0xA000`.
SHA-256: `B9AF7DFB13472C0A0D3CBE70036EFAD7C3B792F13FC9944ACEC935B362F0FBA8`.
Linked image: 7,036,160 bytes, SHA-256
`6FFC3709DDBFD66328B734AD735153FCCEE192B5E68AC5D1EF42D1F6E5DFC980`.
Loaded image: 602,112 bytes, SHA-256
`C91D80EF16FB5EA9EBEFC114EEA7CBC29C33A4BF605CF65B310741124C422FA7`.

Two clean same-host entry builds match. Native host qualification passes 246
kernel tests; reclamation retains 19 pool and 40 lifetime tests per host profile,
15 compile-fail tests, six execution-hold and ten inactive-stack methods. This
does not prove live task/context or general cross-CPU retirement.

Nine admitted bounded receipts bind the exact candidate:

- Core: `B9B486A01F540E93B1178B887E17BBA9FA43B90C5F3956D630AA4A6BA9A6F818`.
- Entry: `C73306B5D5D6CF48C5FB6BBF00155CBD08283920A353C78B5AFF20039119BAB5`.
- Symbols: `546A2D3075FE4FD1F956AD77FF00BBCF2C8642EF386A40FAB1A8CD150EDE009A`.
- Policy: `67522CD25A64FA6DA6CEA98A7BACB8DF61BB04AF49C50A570C94F8326096D838`.
- Loader: `F51E811F7DA5C771BAEFA6437E27D6B48B96035D85AFC9757F2B55AC90C3C0FD`.
- PooleBoot: `25959CA635B90E27AC3AABCB03300DD1EB1C3F6B3B0664B1B3EDEB29BFE8C248`.
- Revalidation: `DF72365F4583614401500AEC332725DC7B63558EA2C63C0E1F55764EF7B1EF6A`.
- Transfer: `132A97CD727B3A135501B5932B75D7ED33CAEA7204B5F0E8F762CA167B65983A`.
- IPI: `D302E39890B500E1D8B732EDE823A62893A0C6453E5E78FC0747FE91DF7CF2F7`.

Eight final virtual executions comprise two each of loader, PooleBoot, transfer
and IPI; four enter the kernel. The final IPI run took 319.219 seconds, including
the linked audit and two four-vCPU boots. It passes 609 rejection cases in 33
groups. Each boot covers three APs, nine accepted/three denied deliveries,
twelve EOIs, timeout/rollback/retry, three remote invalidations, one retired
generation and verified release of 96 resource plus six frame pages, 417,792
bytes. PKAPOWN1 makes two ownership attempts per run with 27 retained-free and
18 owner-release rejections per attempt. This is not general CPU retirement.

## Adversarial And Failure Evidence

The 57-test scoped regression passes with zero skips. It covers 906 corrupted
records and 360 raw mailbox mutations through runtime and the actual gate;
receipt hashes are recomputed so rejection cannot rely solely on an old hash.
It also detects a deliberately disabled independent oracle and rejects omitted
contract/export fields. Log SHA-256:
`10F42ABFF988C39A72B1AF910A01825D4D1AFCFB1AAD267FC3DAC225B8A80FE6`.

Two initial passing IPI boots were superseded when the disabled-oracle test
changed a source input bound by the qualifier. Fresh final execution replaced
them; there was no rebinding of old evidence. Initial entry, symbol and policy
failures from stale contract/fixture data, private admission-helper errors, a
6/27 stale-pin projection and a 4/6 boot-gate test failure remain preserved.

The boot-gate repair initially used the minimal fixture's trust hashes for the
real image. Independent reconstruction corrected this, followed by 6/6 and then
57/57 passing regressions. Real retained bytes/manifest are 11,952/2,615, not the
golden fixture's 11,950/2,613. Stale and fixture-only identities explicitly reject.
Both paths deny unsigned policy; no authority, actions or writes are granted.
See the unchanged [initial backup](cycle192-unfinished-cloud-backup.md) and
[qualified-mailbox backup](cycle192-mailbox-qualified-backup.md) for intermediate
results, logs and limitations.

## Reconciliation And Remaining Work

Roadmap 192 archives all eleven previous current records under Cycle 191 without
altering them. Entry/core/boot/IPI records bind new receipts. CPU qualification
is pending, and the old VM ownership receipt is explicitly not current-image
evidence. Historical qualified-profile lists are not copied into current ones.
The 299 architecture bindings include the native implementation, oracle and
tests. Source discovery finds 1,041 Python tests; discovery is not execution.

The initial reconciliation run passed 30/33 tests. Two schemas retained prior
cycle/count constants and one historical ownership assertion compared an old
receipt with the new file. Corrections preserve exact new constants and the
old receipt's historical binding. The failed log is retained as
`F563058F91B4F389F1670EDB0D3F63CB239535B04F612DB687D2096AD7B9B698`.

Corrected reconciliation passes 33/33. Combined regression passes 189 tests with
zero skips in 135.414 seconds, covering mailbox/IPI, entry, boot-chain, host
toolchain, ownership core, roadmap, architecture and checklist guards. Log:
`A006B6EE240A27783BA4D24B6E5FAF8B357081C1F2145835AF2AAC7EB2643BFA`.
It includes exact entry-receipt reproduction. Conservation passes against the
completed Cycle 191 tree. Stale CPU/memory/scheduler positive suites are not
claimed to pass and are not replaced with rebound positive fixtures.

Selected readiness is 9/27. The decrease from historical 19/27 reflects a changed
kernel invalidating old dependent evidence, not disappearance of implementation.
No phase, subphase, flag or checklist item closes. Full exact-candidate, second-
builder, physical hardware and production qualification are still absent.

1. N7: run `N7-TRAP-001`, CPU policy, xstate policy, xstate exceptions and
   privilege/MSR qualification against the new image, retaining hostile cases.
2. N9/N8: requalify physical memory, VM, interrupt/time, first AP and per-CPU
   runtime. The independently qualified IPI profile does not replace these.
3. N12: replay scheduler, preemption, deferred work, SMP scheduling, AP workers,
   SMP preemption, atomics and locks. Repair the 65 outstanding scheduler
   control-execution gaps without treating declared counts as executed cases.
4. N36: run full exact-candidate canonical/Doctor, publication, configured GitHub
   and review gates before PR #78 is ready for main merge.

PooleGlyph remains Phase 65; the owner-modified conformance report is preserved.
The frozen 8,996 requirements, 57 additions, 40 phases, 301 subphases, 94 flags
(35 open), demo ISO and historical full release gate are unchanged. No new ISO,
signing, physical-media action, release or production promotion is claimed.
