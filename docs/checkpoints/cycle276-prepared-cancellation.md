# Cycle 276: Owned Prepared Cancellation

Date: 2026-10-13. Scope: USI-3 lifecycle support for the usable user-space
integration ISO. No phase, flag, production or main-merge gate closes.

## Implemented

`Slot::cancel_prepared` derives cancellation from the exact owned, unexposed image
and task generation. It rejects active, suspended, terminal and quarantined state,
pending accounting and stale identity. Cancellation is not execution or cleanup
completion. Both admitted and unused prepared children in the interactive path
now use retained `Slot::reclaim` before slot reuse and completion publication.
Other legacy abandonment paths are not globally migrated.

The qualification-only scheduler hold blocks worker generation1 before activation
or entry. The actual shell requests stop; an after-effect erase failure preserves
ownership, denies early completion/free/reentry, then a controlled retry succeeds.
Generation2 runs normally. No timer shutdown or CR3 change is charged to the
unentered child. Shared accounting/control checks still run after the hold.
[Contract and boundaries](../native-prepared-cleanup.md).

## Evidence

Public receipt: `runs/native-prepared-cleanup-readiness.json`, SHA-256
`5ADE4D93938ACDB459ECDE14A1CD0F0DB89A701BF1088FF86AB80B826B58862F`.
It binds872 current execution sources, independent kernel builds, retained user
programs, exact interaction input/output and serial/debugcon/PBP1 transcripts.

| Check | Actual result |
| --- | --- |
| Final kernel debug and release | 526 pass each; six new tests |
| User runtime debug and release | 78 pass each; sources unchanged |
| Initial Python oracle suite | 17 pass; synthetic fixtures are parser-only |
| Broader pre-closeout regression | 270 pass in55.563s; counts overlap earlier suites |
| Prepared page-boundary campaign | 78 failures retain exact ownership/outcome; retry succeeds |
| Final prepared native guests | 3 pass; three held children never enter; each next generation executes |
| Injected cleanup cases in those guests | 10 total, including three prepared erases;50 free and10 early-completion denials |
| Final ordinary shell guests | 3 pass; real start/stop/status, restart, fault survival and denied authority |
| Final default regression | 2 diagnostic boots and ordinary unsigned-boot denial pass |
| Superseded pre-format native runs | 9 pass, retained separately; not final-source execution evidence |
| Total native executions this cycle | 18, of which9 qualify final source |
| Program provenance | 10 retained Cycle274 independent ELF/code pairs re-extracted and verified, not rebuilt |
| Rust formatting | Final check passes |

Final prepared transcripts reject302/302/244 hostile mutations. These are parser
checks, not extra VM runs. Frozen bounds remain180s per shell guest,150s per
default diagnostic and45s for ordinary denial. The final qualifiers take215.438s,
191.437s and321.328s respectively. Captures report unchanged source and owner
conformance input while executing. No new ownership-doctest run is claimed.
Broader regression log SHA-256:
`BEE08B084B7CFA808E4C9800F12C3209759D265067B2EE5E06E9D978C2F76E7D`.
This is not the full canonical audit; exact-final closeout is recorded separately.

Normal/prepared kernel images use111/112 pages; each pair of independent builds
matches exactly. Default remains208/208 pages,36 guarded stack pages and120 RELRO
padding bytes. Canonical default SHA-256
`CD567E041041F00E3190F44BB3618EDC96B5FBB5B096C3E27A99F51DEC3986F4`
matches Cycle275; linked SHA-256
`282C131F5923FB77B38BB70A7EC4A2069B04FB2DB931EFE2303BD6D528F21E76`
does not. Canonical equality is not linked-byte equality. Measured interactive
local frames are50136 bytes normal and49336 prepared; full call-chain/interrupt
stack bounds remain unproven. No capacity limit increased.

## Failures And Reconstruction

The first host run had525 passes and one failed test fixture: it tried to insert
an already-exposed CPU owner, which the existing insertion guard correctly
rejects. The repaired test checks that earlier rejection and the unexposed-image
guard. Neither guard was weakened. Failed log SHA-256:
`BD9D625FDE8E188AFD7A379E490CB37FC4BCCA73F29092519C11966DD4A0CEF6`.

The first formatting check rejected the order of two test-module declarations.
Its log SHA-256 is
`526E77CBD5EF00DAEAC96F273310243B887C29978E6B99B8684B510BF68CFBD8`.
An initial packaging attempt refused the failed formatting gate before writing
a public receipt. Module order was corrected; final kernel host tests and all
nine native runs were repeated against the exact new source bindings. The earlier
nine successful native runs and their original bindings remain separate history.
Acceptance bounds, marker checks and capacity limits were not relaxed.

Thirty-eight generated build/media archives retain both attempts and were verified
member-by-member before hot-duplicate removal. Raw guest logs, canonical images,
receipts and captures remain local. Automatic reservation/restore remains open.
Prior published readiness receipts are not overwritten or relabeled as current.

Owner inputs remain unchanged: master checklist
`A8C94719FAF9428C1F133010BA2603C0270C4E1EFD7327AF8EAB9C8C362ABB3D`,
PooleGlyph Phase65 checkpoint
`F3CCEB701CF76274D9464A0958BF6106888FB34F3C0BFBD55DE4ACE03C427ABC`,
conformance report
`F75E4836FAA9DDD59BA62648FE9542415F2119B659A583FB3F5959F2F5CAE87B`.
PooleGlyph sources are unedited; Phase66 CoreIR metadata-boundary audit remains
upstream work. Metadata does not grant execution authority. Binaries here use
the pinned conventional Rust compiler/assembler/linker, not PooleGlyph generation.

## Gaps And Next Move

Next implement durable parent/child ownership across removal of parent leases,
explicit orphan policy, prepared/runnable/waiting/reclaiming child cleanup,
pending/claimed launch and stop handling, stale-generation rejection and unrelated
task survival. Existing unexpected-shell-exit/live-child halts are not recovery.
Asynchronous cleanup retry, partial allocator-commit fault injection, general
prepared migration, full stack bounds and executable trust remain open.

Then implement read-only bundled files and two useful separately launched apps,
replacing diagnostic roles within the six-process layout, followed by sustained
optical ISO acceptance. Diagnostic workers/fault programs do not count as apps.
Full robust microkernel, PooleGlyph, PDC and accessible PooleGlass work continues
after this intermediate milestone; writable storage/heap, local input/display,
efficient idle and physical-hardware qualification remain visible requirements.

USI-3/4 are partial; USI-5 has not started. Conservation remains40 phases,
301 subphases,8996 requirements,59 additions,98 flags (43 open),20 gap groups.
The1425-test and679-binding inventories are not full canonical execution evidence.
Full canonical requalification and existing readiness repairs still gate main.
Known prior failures remain unresolved in `NativeKernelLoadTests` methods
`test_contract_and_readiness_pass_semantic_validation` and
`test_readiness_detects_stale_input_and_oracle_divergence`, and
`NativeKernelTransferTests.test_contract_and_generated_readiness_are_current`.
They were not rerun as a full canonical campaign this cycle; this is not a claim
that they are the only remaining full-suite failures.
No new usable ISO, main merge, key use, signing, firmware or physical-media write,
tag, release or production promotion occurred.
