# Cycle 187: Virtual-Memory Recorded Evidence

Status date: 2026-09-26. Move `N9-VM-DIRECT-MAP-001`, N9.3/N9.4 supporting
N36. This is a pre-production qualification repair, not a new kernel feature.

## Demonstrated Gap And Repair

A genuinely generated initial VM receipt passed runtime and actual gate. Of 65
corruptions, the runtime accepted 46 and the gate accepted 45. Initial audit:
`EFF8C3152C0878F32B6E9A37F10563F9442E717A85C5518E9346C29C1FC17579`.
The two initial boots remain superseded evidence, not final qualified runs.

VM now requires strict recorded-pair coverage, integer zero exits, exact typed
parsed summaries, marker/frame digests, handoff bindings, guest-bound
revalidation and true dual-channel agreement. Each handoff independently
rederives PMM ownership and sparse direct-map accounting. Saved per-run oracles,
aggregate observation, independent accounting and complete readiness summary
must agree with exact JSON types. Existing retention, root restoration and
local invalidation checks remain mandatory. The actual gate retains its
separately specified profile expectations. The qualifier revalidates before
creating an output directory or replacing evidence.

## Executed Evidence

Two final headless qemu64 virtual boots pass 40 markers each, 48 existing marker
controls and 245 embedded kernel host tests. The hostile-environment run took
72.359 seconds with tracked sources and owner data unchanged. The public
receipt is an exact copy of generated output, SHA-256
`F2CC0C55F09600DE728D2BDAB1F26855EF7BE624AF9F6B1D00B4F16D9418A1FC`.
Prior VM receipt `4AFEA30E25DB4DCD0D9038E01D3FE1CC6EE5D82DBAB4595A4631D34902460BB7`
and initial candidate `5CEEE0A862C985CC314ECA7AA229A1C2669B5460E8D90FF6B704AF5934623FB1`
remain preserved separately.

All 10 focused Python tests pass, zero skipped. There are 115 permanent
malformed-record cases through both runtime and actual gate: 14 exit, 16
coverage, 28 evidence, 7 aggregate accounting and 50 summary mutations.
Genuine positive receipts are validated first and never rebound. Two qualifier
cases preserve an existing file and absent parent directory when rejected.
Focused log: `03B75B553C37E1B8F472D2F700A16775DBA8CF512CB80835F2C83896876FC32A`.
All 65 original audit corruptions now reject in both validators.

The initial combined run passed 244/245 tests. One historical assertion still
compared the Cycle 181 VM hash with the replacement current receipt. It now
preserves that old identity separately. The failed log remains retained:
`0DAD750AFEF0A44C901ED6033E80194D75F052F7ACE078E3DB12FD91DD8202F4`.

The repaired combined suite passes all 245 distinct test methods with zero
skips. One host-toolchain module was accidentally listed twice, so its raw
run has 261 passing executions, including 16 repeats, not 261 distinct tests.
Log: `8E01E333BBBEECF3C3FC578DE0D149BCDA4C0B8516A43E383924C2C9D8646FE1`.
Final checkpoint checking uses the deduplicated module list. This is still a
scoped regression suite, not full canonical or merge qualification.

The bounded virtual profile covers 117,818 owned pages across 11 sparse ranges,
243 table pages, three active local invalidations, two CR3 writes with exact
restoration, one retirement receipt and six retained-page free rejections.
It does not establish general SMP mappings, ring 3, target-hardware behavior,
production memory capacity or complete N9 acceptance.

## Progress And Remaining Work

Selected readiness is 15/27; firmware, boot trust and ELF separately pass.
PMM, CPU, boot-chain, kernel-entry and native-core receipts remain unchanged.
Current ownership evidence records this VM replay separately: active-root
replay is current, but AP replay and combined live ownership remain pending.
Twelve profiles remain from `N8-IRQ-001`: interrupt/time, then SMP, scheduler,
atomics and locks in dependency order. At least 65 scheduler controls still
require individually bound rejection execution. Exact full canonical/Doctor,
publication, configured GitHub checks and review still precede PR #78 merge.
The historical release-gate file is not replaced by a partial projection.

Existing `ADD-N36-RECEIPT-COVERAGE-001` and its open flag track this work.
All 8,996 master requirements, 57 additions, 40 phases, 301 subphases, 94 flags
(35 open) and 20 gaps remain accounted for. No phase or flag closes. Inventory
is 1,006 discovered Python tests and 285 architecture bindings, not a full-suite
pass. Prior failure records and normative production conditions remain intact.

Native Rust, kernel bytes, PooleGlyph Phase 65 and its owner-modified report,
and the frozen demo ISO remain unchanged. Recorded consistency is not freshness
or authentication, an independent builder, a new ISO or production readiness.
