# Cycle 173: Kernel Entry Provenance And Boot Replay

Status date: 2026-09-12
Selected move: `N5-SYMBOLS-SEMANTICS-001`, N5.6/N5.9 with N6.4-N6.6 prerequisites.
Status: entry and six N5 component qualifiers pass; downstream replay and full qualification remain pending.

## Progress

The preceding turn made progress by preserving the pending source-binding
repair in GitHub at `52c3974` and identifying the failed exact-candidate audit.
This cycle executes that repair's qualification and rebuilds its dependent boot
artifacts. Main remains the qualified Cycle 171 commit `8006c7b`; draft PR #77
preserves development work without declaring it ready to merge.

The raw linked ELF is 7,025,584 bytes, SHA-256
`87B12B0278881804BDDA57132657950CF8CD8F515B7A0CC4BC9E2B6326FA1C0A`.
The 530,072-byte canonical image remains SHA-256
`8A2DA65C86B09F7BCF2D5ACDB90029A5B7B7361581BA841ADC3B62AEE168B625`,
with 602,112 loaded bytes, 147 pages, 1,321 relocations and entry `0xA000`.
Kernel-entry evidence now includes all 38 Rust sources under `native/kernel/src`
among 54 deterministic, unique bindings, including the 24 formerly omitted files.

The entry qualifier passes 243 kernel host tests, 43 negative controls and two
matching clean linked/canonical builds. All eleven entry Python tests pass,
including the exact receipt/product reproduction that failed in Cycle 172 and
per-source digest mutation rejection for all 38 crate sources. These are clean
builds on one host, not independent-builder qualification.

PSYM1 is regenerated from the measured debug identity. Two matching debug builds,
a separate stripped-section check, four Rust tests, 158 negative controls and
32,768 parser/lookup differential cases pass. The guide now correctly distinguishes
canonicalization of the debug product from the separate stripped-build inspection;
the receipt explicitly does not prove equal stripped/debug image plans.

PPOL1's generated contract/vectors and dependent boot artifacts are refreshed.
Policy passes six host tests, 116 controls and 32,768 differential cases.
PKLOAD6 and PooleBoot each pass two fresh QEMU/OVMF runs and 155 controls;
the loader passes 328 host tests, and both profiles validate 25 ordered markers.
PKREVAL1 passes 36 controls, 32,768 differential cases and zero-authority denial.
PKXFER1 passes two fresh development-entry runs, 30 markers and 58 controls.
The six N5 qualifiers total 678 controls and 98,304 differential cases.

There are six successful fresh QEMU runs in this cycle, two each for load,
PooleBoot and transfer. The nine retained files occupy 11,952 bytes; six inner
artifacts occupy 8,761 bytes and bind set SHA-256
`E4B88EAF9B322531292D03EBA9FDCFA6ECABF6EEF7A5210C29D130C8AE321D3A`.
The focused boot-chain suite passes 71 tests, including five old artifact/trust
identity rejection cases. Source and the owner's PooleGlyph report remained
unchanged during each bounded qualification run.

## Evidence

The following are exact SHA-256 identities of generated receipts, not edited
substitutes for execution:

| Receipt | SHA-256 |
| --- | --- |
| PKENTRY1 | `9998F12E922201BA60C46521444BD1AD6CB641A0172B36F4A3552DCF66434A0B` |
| PSYM1 | `A116A0BBB288A6005BDEB4DFE8FF793D8A330C3DB2AA02581D89F9BEFEC8E409` |
| PPOL1 | `9262886C425628FF2732379B5D63683DEF98FF50310F17D8AE9D5FCFF9DC212D` |
| PKLOAD6 | `02AAC204A50A5157228DE5FDA11B0819128BA64431E8A959255A8B99B0236EAA` |
| PooleBoot | `DA8B44DA10144843E0DDF8AD6D6F8DD8490BE68967454E032ADC539ADEB2CDD8` |
| PKREVAL1 | `4F595F788E07D811D5D2CEC16CD944E50E2804B3A8BF22ED8F7A6671BA1D1BC0` |
| PKXFER1 | `295A8C43E1CE81325E09F7C72A3D419207AC98A05CF0D28D2EFAF3B52290E1B4` |

Entry exact-reproduction log:
`5C08B3D67BB61145F1752F60B2D963C67F115F7F06CCC1AAD944A64E4EFF4086`.
Final 71-test boot suite log:
`443A75CD4F40646A100C057B1799443D781998200CBDE102C118FFFFF4861C14`.
Raw logs and workstation paths remain private.

## Failure History

Cycle 172's full audit at `9c111e2` failed 104/105 canonical gates and 707/708
Doctor checks; the kernel-entry linked-ELF reproduction test exposed the omitted
source bindings. Failed report SHA-256:
`D5AF0E1BCA6C6278ED9E506DB2EBBA1E464AED74177DDC73C8EF30B977D52DD4`.

The first Cycle 173 symbol qualifier rejected the prior full-debug identity:
log `D6502837DDF4BCE267A960E661321F995D9C54FAC210FB33AA89A184B1E70752`.
The first policy qualifier rejected stale generated contract/vector bindings:
log `16A404D2AFEA847DC6448188B44F04BE07CF9A46C7C154CA1E94A24CE447A6B2`.
Neither failure was suppressed. Generated fixtures were rebuilt and qualifiers
rerun. A subsequent 69-test suite passed 68 and failed one stale aggregate boot
summary expectation; log
`997E76D598BDAE1AC6A02AF29FD9AE52B2B345D924F56A79F31273C52F04A2D6`.
The measured identities were corrected, old-identity regressions added, and all
71 tests passed. No exact reproduction or source-freshness requirement was relaxed.

Closeout also passed 117 focused tests. The independent record comparison then
caught a pre-existing N36 generator label that substituted today's discovered
test count into a purported Cycle 150 execution summary. That label is corrected
to a current source inventory; the exact former Cycle 172 text is preserved as
superseded history, not execution evidence. All 950 discovered tests have not
been run as a full Cycle 173 qualification suite.

## Remaining Work

The selected native readiness projection passes 22/27 checks. CPU policy, MSR
policy, physical memory, virtual memory and SMP IPI reject stale evidence.
Older five-profile CPU and fourteen-profile memory-through-lock receipts retain
their original execution cycles and hashes; their embedded entry provenance
still needs replay even where a narrower selected check passes. This remains
under `ADD-N36-RECEIPT-COVERAGE-001` and its open flag. Broader transitive-input
coverage and independent reproduction are not closed by the 54 entry bindings.

The Cycle 172 stack core receipt still validates, and all 17 stage-log hashes
match. It proves inactive stack ownership, not guarded task-stack mapping,
architectural context activation, general CPU retirement or automatic receipt
growth. Those N12/N9 implementation tasks remain open.

PooleGlyph remains Phase 65, with Phase 66 Core IR next; its checkpoint ZIP,
manifest and owner-modified report are unchanged. The locked 8,996 requirements,
57 additions, 40 phases, 301 subphases, 94 flags (35 open) and 20 gaps are conserved.
No signing, key custody, firmware, driver loading, physical-media write, frozen
demo update, phase closure, release or production promotion occurred.

Next: `N7-TRAP-001` and dependency-ordered CPU-state provenance replay, then
memory/SMP/scheduler dependencies, exact full canonical qualification and final
publication/review gates before any main merge. The goal remains active.
