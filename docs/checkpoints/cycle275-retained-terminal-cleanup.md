# Cycle 275: Retained Terminal Cleanup

Date: 2026-10-13. Scope: USI-3 lifecycle foundation for the user-space integration
ISO, not another boot-screen redesign. No phase or implementation flag closes.

## Implemented

`RetiredImage` retains the original allocation tokens through whole-allocation
erase/readback, finish, and allocator release. CPU restoration transfers those
tokens directly. `Slot::reclaim` preserves failed cleanup and terminal results in
an occupied `Reclaiming` slot, denies reentry/reuse, and empties only after full
success. Native terminal retirement now uses this path before scheduler teardown
and process-completion publication. Prepared abandonment is not migrated.

The opt-in native fault adapter performs real after-effect write, corrupt-write,
read and finish failures. It verifies no release, no reentry and no early
completion, then performs one controlled immediate retry with the normal physical
memory adapter. `PRECLAIM1` independently validates these records and the entire
shell interaction. [Contract and boundaries](../native-retained-cleanup.md).

## Evidence

Public receipt: `runs/native-retained-cleanup-readiness.json`, SHA-256
`D9108F3F91E3E0B38E5E82311A9CB6F11F2D05B6E9A10E3040958D859541B86F`.
It binds 869 current execution sources and exact binaries, input/output bytes,
raw serial/debugcon hashes, build receipts and transcript controls.

| Check | Actual result |
| --- | --- |
| Kernel debug and release | 520 tests each; eight new tests |
| Ownership compile-fail tests | 10 pass, 15 other doctests filtered |
| User runtime debug and release | 78 tests each |
| Initial Python oracle suite | 15 pass |
| Broader pre-closeout regression | 267 pass in54.725s; counts overlap earlier checks |
| Page-boundary cleanup campaign | 78 injected cases; retry retains exact outcome |
| Injected native shell guests | 3 pass; 10 failures, 50 free denials, 10 early-completion denials |
| Ordinary native shell guests | 3 pass; process controls and fault survival preserved |
| Default regression | 2 diagnostic boots plus ordinary unsigned-boot denial pass |
| Program provenance | 10 retained Cycle274 independent ELF/code pairs re-extracted and verified; no fresh program build claimed |
| Rust formatting | Pass |

Native injected transcript mutations reject 334/339/266 altered cases; these are
parser controls, not additional VM runs. Bounds stayed at 180 seconds per shell
guest, 150 seconds per default diagnostic guest and 45 seconds for ordinary denial.
All captures report unchanged source and owner conformance input during execution.
Broader regression log SHA-256:
`00A81BAAFD8B854D4285F72C0F8EA93A1CD5388311D4A242BA8BE2838E86953E`.
It is not the full canonical audit; exact-candidate final checks follow separately.
There were no unexpected build/guest failures in this cycle. The ten intentionally
injected cleanup failures remain in the raw logs and are the tested recovery cases.
Earlier cycles' failures and receipts remain frozen, not overwritten.
The first closeout helper failed on an incorrect archive lookup (`kernel1` instead
of the recorded `kernel` directory), before final focused tests/publication scan.
Only the helper lookup was corrected; artifacts and acceptance checks were not
changed. Its failed log is retained with SHA-256
`2A416C7CA25FFC7D198030FA6735B2A8D46382A49A8A8F157D9D070578452DEE`.

Normal shell kernels use 112 pages; injected kernels use 113; each pair of
independent normal builds matches exactly. Default uses 208/208 pages, 36 guarded
stack pages and 120 RELRO padding bytes. Default linked SHA-256 is
`3CDD825224F9EE0CCA82A513380FD3CEC24EC7693DA94A7D399B894A4AB04491`,
canonical SHA-256 `CD567E041041F00E3190F44BB3618EDC96B5FBB5B096C3E27A99F51DEC3986F4`.
The fresh native default regression matches the earlier budget-build bytes exactly.
Disassembly measures interactive local-frame allocation at 51,384 bytes, versus
48,680 in Cycle274. This is not a full stack bound. No limits were enlarged.

Twenty generated build/media archives were verified member-by-member before
removing their hot duplicates. Raw transcripts, kernels and captures remain local;
private paths and raw owner documents are not included in the public receipt.
Automatic reservation/restore remains an open storage requirement.

Owner inputs remain unchanged: checklist
`A8C94719FAF9428C1F133010BA2603C0270C4E1EFD7327AF8EAB9C8C362ABB3D`,
PooleGlyph Phase65 checkpoint
`F3CCEB701CF76274D9464A0958BF6106888FB34F3C0BFBD55DE4ACE03C427ABC`,
conformance report
`F75E4836FAA9DDD59BA62648FE9542415F2119B659A583FB3F5959F2F5CAE87B`.
No PooleGlyph source was edited; Phase66 CoreIR metadata-boundary audit remains
upstream work. Metadata never grants execution authority.

## Gaps And Next Move

Terminal ownership/retry is implemented only in the stated bounded path.
Prepared-stop migration and native qualification, owner-death/orphan policy,
asynchronous retry scheduling and injected partial allocator-commit failure remain.
General executable trust, writable data/heap, efficient idle, physical hardware
and full call-chain/interrupt stack bounds remain unqualified.

Next close the prepared/owner-death lifecycle boundary, implement read-only bundled
files and two useful separate applications, then sustained optical ISO acceptance.
Diagnostic workers and fault payloads do not count as useful apps. The complete
robust microkernel, PDC, PooleGlyph and accessible PooleGlass remain the destination.

USI-3/4 remain partial; USI-5 has not started. Conservation: 40 phases, 301 subphases,
8,996 requirements, 59 additions, 98 flags (43 open), 20 gap groups. The planned
1,422-test and 673-binding inventories are not full canonical qualification.
No canonical full replay, main merge, key use, signing, firmware modification,
physical-media write, release or production promotion occurred in this cycle.
