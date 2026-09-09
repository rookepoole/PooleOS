# Cycle 168: Bounded AP Execution Ownership

Status date: 2026-09-08
Status: bounded native qualification; changed-image dependency replay pending.
Phase: N12.3, `ADD-N12-CONCURRENCY-RECLAMATION-001`.
Flags: `FLAG-N12-CONCURRENCY-RECLAMATION-001` and
`FLAG-N36-RECEIPT-COVERAGE-001` remain open.
Branch: `agent/n12-ap-execution-ownership`,
[PR #76](https://github.com/rookepoole/PooleOS/pull/76).

## Actual Kernel Progress

The real three-AP path now retains each 32-page runtime region, including its
execution and exception stacks, and both one-page data allocations. Every CPU
that may share these regions is recorded before startup. Copied handles cannot
release them; owner-authorized release rejects possible execution and preserves
retention through fallible scrubbing, readback and allocator commit.

Two final four-vCPU `SandyBridge,-avx` QEMU runs exercise both partial startup
and full startup. Each attempt observes 27 copied-free and 18 owner-release
rejections, with no PMM accounting, physical-access or owner-state side effects.
The partial attempt parks its two started APs, scrubs/releases all allocated
regions, and retries with fresh allocations. The full attempt completes three
AP-local runtimes, validated IPIs, remote invalidation and acknowledgement,
parking, alias revocation and scrubbed release of 96 runtime pages and six
frame pages. Each attempt verifies 417,792 bytes before reuse.

Final INIT remains an explicit unsafe exact-mask boundary on this controlled
topology. These observations do not establish arbitrary CPU hotplug, general
task-stack ownership, all hardware quiescence conditions or general retirement.

## Final Evidence

Kernel identity: `PKBUILD1-CYCLE168-N12-AP-OWN-V002-0000000001`.
Kernel SHA-256:
`8A2DA65C86B09F7BCF2D5ACDB90029A5B7B7361581BA841ADC3B62AEE168B625`.
Measured geometry: 530,072 canonical bytes, 602,112 loaded bytes, 147 pages,
1,321 relocations and entry offset `0xA000`.

| Check | Final Result |
|---|---|
| PKENTRY1 | 243 host tests, 43 negative controls, two identical clean same-host builds |
| Kernel regressions | 243 passed in both debug and release |
| Reclamation pool / task lifetime tests | 19 / 24 passed in each host profile |
| Retention / AP-owner tests | 20 / 11 passed in each kernel host profile |
| Compile-fail documentation tests | 9 passed |
| Formatting, Clippy, freestanding link | Pass |
| PKSMP5 | Two final guest runs, 40 markers each, 30 groups / 249 rejected cases |
| Focused Python regressions | 56 passed, zero skipped |
| Architecture / roadmap regressions | 22 passed; 228 exact architecture source bindings |
| Rust / Python retained-map probe | Exact fingerprint agreement: `73396E416CE24E46` |
| Selected native dependency checks | 4 of 27 current; 23 require replay |

Final public receipt SHA-256 bindings:

- Entry: `0BC2368946D26877B0214211EBA0EC62958C62AADE0A1C31965EE7C5D2F6F42B`.
- Reclamation: `98646A6726A0925B58B2D1F554E9E3EDD03A582B02D83D2D30D3C83959D52CCB`.
- SMP: `E9C8A4A81AFF9C5BD9266C481C60012249228CA56E26399A6B99B5A8AF42FE24`.

The four current selected checks are entry, policy, pure errata policy and SMP
IPI. Reclamation is separately source-verified and is not silently added to
that 27-check denominator. The full Python discovery count is 933; discovery
is not a claim that all 933 tests passed on this candidate.

## Failures And Repairs

1. The new reclamation checker expected all 20 retention tests in one module;
   the actual passing log had 18 public-module and two internal-module tests.
   Separate namespace checks now enforce all 20 plus 11 AP-owner cases. New
   negative tests first exposed acceptance of extra failed/ignored records;
   missing, duplicate, failed, ignored and relocated cases now reject.
2. The first guest completed AP cleanup, but the transfer oracle still expected
   the Cycle 162 build ID. The oracle and a new contract-agreement test now bind
   the current identity. This first failed validation is retained separately.
3. The larger kernel left an old temporary-map diagnostic and map fixtures.
   The diagnostic now matches `0xFFFFFFFF801B9000..0xFFFFFFFF801BA000`; the
   retained probe, guards, mapping counts and fingerprints are synchronized.
   New measured entry/kernel bytes are qualified rather than inheriting 167.
4. Two successful guest executions exposed a saved-receipt mismatch: Python
   tuples became JSON lists. The observation now uses arrays, and qualification
   validates after JSON conversion. Stored runs and aggregate observations
   must match independently parsed markers. Malformed receipt shapes reject.
5. Focused testing found remaining old RX/fingerprint and relocation/hash
   expectations. They were corrected from measured output. Final entry/SMP
   qualification was repeated after the last source-bound test correction.
6. Backup validation found that the architecture schema and test still required
   225 sources after three AP/checkpoint bindings were added. Both now require
   exactly 228, with explicit checks for the new paths. All 22 architecture and
   roadmap tests pass; the first failed metadata run is preserved separately.

Four earlier completed guest runs are superseded by the final two; the one
failed guest-validation run is separate. They are not counted as additional
final qualification. Raw failed and successful logs remain private and are
retained. The final focused-test log SHA-256 is
`2335BB2003682A27475F196CA02E4FAF83C7DCB1C72B2F730CF6D51A019C4200`.

## Progress And Merge Boundary

Main remains exact-final qualified Cycle 165 through
[PR #75](https://github.com/rookepoole/PooleOS/pull/75), commit
`6f9399c3cd70ebef2f7610f8b6fdb40ae262e27f`, tree
`c20156f18d2727f7e3c1df73ac05ad8126b9f470`.
Its 105-gate, 708-Doctor and 924-discovered-test successful qualification is
historical, bound to receipt SHA-256
`621EFC831F7FB4F29990D2E27CD26FC6BB78B6AE11453FAB856BF7615B7DED34`.
It does not qualify this changed kernel. The roadmap preserves prior boot,
CPU and dependency records as historical instead of repointing their hashes.

No phase, subphase, ADD requirement or flag closes. Counts remain 40 phases,
301 subphases, 57 ADD requirements, 94 flags (35 open), 20 gaps and 8,996 locked
checklist requirements. Whole-OS production functionality remains incomplete.
PooleGlyph Phase 65, the owner's local report change and the frozen demo ISO
are unchanged. No signing, release, firmware, driver or physical-media action
occurs. This is not a new ISO or production promotion.

Next move: `N5-SYMBOLS-SEMANTICS-001`, then dependency-ordered boot, CPU, memory,
interrupt, scheduler, atomic and lock replay for the exact new image. Before
PR #76 can merge, the final source must pass runtime-inclusive canonical
qualification, publication scanning, the release gate and all applicable
GitHub checks and review conditions. N0 custody remains a separate owner gate.

Cloud backup does not require a main merge. PR #76 remains a draft carrying
this source checkpoint and its public-safe receipts. The current selected
projection rejects 23 stale dependencies; no full Cycle 168 canonical run is
claimed. The retained Cycle 165 release-gate report is historical only and
must not be used to qualify this candidate. Private logs and raw media remain
local and are excluded from the source backup.
