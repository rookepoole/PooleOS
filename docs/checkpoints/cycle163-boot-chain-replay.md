# Cycle 163: Current-Kernel Boot-Chain Replay

Status: bounded pre-production evidence; PR #75 remains draft.
Scope: N5.5/N5.6/N5.8, `N5-SYMBOLS-SEMANTICS-001`, with an existing
`ADD-N36-RECEIPT-COVERAGE-001` calendar-validation repair.

## Implementation and Evidence

The PSYM1 public index now binds measured Cycle 162 executable and split-debug
identities. PPOL1 references the new symbol bytes. Fixed synthetic loader and
transfer markers describe the 146-page image and shifted guarded stack and
handoff windows; they are not measured boot evidence. The previous kernel's
entry address and build ID remain explicit rejected cases.

Fresh official qualification passes:

| Component | Verified Scope |
| --- | --- |
| PSYM1 | Four Rust tests; 158 controls; 16,384 parser and 16,384 lookup differential cases; two identical debug builds |
| PPOL1 | Six Rust tests; 116 controls; 32,768 differential cases; zero mismatches |
| PKLOAD6 | 313 host tests; two final boots; 25 ordered markers; 155 controls; exact PBP1 and independent mapping/input agreement |
| PooleBoot | Eight host contract tests; two separate final boots; 25 markers; 155 controls; exact framebuffer agreement |
| PKREVAL1 | 228 kernel host tests; 36 controls; 32,768 rejected mutations across nine retained roles; independent host agreement |
| PKXFER1 | Two final kernel entries; 30 markers; 58 controls; independent live/host nine-file agreement; default-build transfer isolation |

These are six final headless QEMU/OVMF boots, not six physical boots. The two
transfer runs end at the expected unsigned-policy denial with zero signatures,
authority grants, authorized actions, state writes or post-exit firmware calls.
PKREVAL1's separate host fixture is not independently counted as a live boot.
Seventy focused Python tests across seven affected boot-chain modules pass.

Canonical kernel remains 525,976 bytes, 598,016 image bytes, 146 pages and
1,319 relocations; SHA-256:
`D0AA3295F66AF02D48476BCEDC44D962A873E98FBA21F48A6753AA7BB9B24EA4`.
The inner set contains 8,761 bytes; the manifest 2,615 bytes; all nine retained
files total 11,952 bytes. Independently measured inner-set SHA-256:
`864A7094E7ED3AFDF282791CC53D97D5D1CD4064E998D1678BD7ED79EBF6B79D`.

## Failure and Repair

The initial symbol attempts rejected the stale debug identity and obsolete
Rust lookup address. Independent measurement and the repaired regression
produced the final passing symbol receipt. One Python preflight named a
nonexistent test method; the corrected named tests passed.

The first loader qualifier rejected its newly dated receipt because its schema
required exactly `2026-09-05`. The PooleBoot schema had the same defect. Both
now describe date strings and explicitly enforce canonical real calendar
dates in their runtime validators, following the scheduler's existing pattern.
Six valid-date and twenty invalid-date cases pass; invalid cases also reject
through release-gate entry points. This does not fix or promote the shared
schema engine's broader pattern/format coverage. No failed attempt's runs are
included in the six final-boot count. No kernel acceptance boundary was waived.

## Receipts

| Path | SHA-256 |
| --- | --- |
| `runs/native_symbol_readiness.json` | `38CA1F7D1C3FB7A2C69A9185AFA73717509724E6F56B382CF2D897CC0CFEC8EA` |
| `runs/native_policy_readiness.json` | `5D10ED417B85088BB37D936BD11097CBD8887943754E3A65021DB9E8EDC3E605` |
| `runs/native_kernel_load_readiness.json` | `C3995D72501990BEA2F962762D487582E2E995228E69034B704F9C7E9290E041` |
| `runs/native_pooleboot_readiness.json` | `FF0D8154527AEB8EA66FE30F826688652FE9CF48BE85D97B4CBADEBC15C47877` |
| `runs/native-kernel-revalidation-readiness.json` | `BE2192F3D8FEEC60C7510161DADC54ED920EB58EAA9DF348C8E51CE2DEC0F038` |
| `runs/native-kernel-transfer-readiness.json` | `7D07BDA3F3D967D570E22470C4B6890AA058BA5D617290CBDAA9EDFAFAEEEE75` |

## Remaining Work

The measured current projection passes 8/27 selected native checks, including
all six N5 components, PKENTRY1 and unchanged PKERR1. Nineteen downstream
receipts remain stale. This includes the Cycle 162 VM receipt, which binds
the replaced transfer receipt even though its kernel bytes are unchanged.
The historical full Cycle 162 audit remains failed at 81/105, Doctor683/706;
no current full canonical audit is claimed and separate optional runtime
passes are not added to that historical score.

Next: `N7-TRAP-001`, then CPU/xstate/MSR, physical-memory/VM, IRQ/SMP,
scheduler, atomics and locks. Run runtime-inclusive exact-final canonical
qualification with both bundle and replay inputs, then publication and all
GitHub merge/review checks before merging PR #75. Main remains the qualified
Cycle 161 checkpoint through PR #74.

N12.3 execution-stack and general CPU-retirement ownership, N0 custody,
independent builders, target hardware, production trust and the full native
services/desktop/ISO path remain incomplete. No phase or flag closes. All
40 phases, 301 subphases, 57 ADD requirements, 94 flags (35 open), 20 gaps and
8,996 locked checklist requirements are preserved. PooleGlyph Phase 65 and
the owner's modified report, the frozen demo ISO, and production status are
unchanged. No signing, release, driver, firmware or physical-media action.
