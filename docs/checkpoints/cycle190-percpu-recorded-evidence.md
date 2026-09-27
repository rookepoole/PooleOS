# Cycle 190: Per-CPU Recorded Evidence

Status date: 2026-09-26. Move `N8-SMP-PERCPU-RUNTIME-001`, N8.5 supporting N36.
This repairs qualification admission, not native kernel features or ISO bytes.

## Demonstrated Gap

A genuine fresh two-boot baseline passed runtime and aggregate admission. Of 69
corruptions, runtime accepted 57 and the aggregate gate accepted 48. One runtime
and four gate evaluations raised exceptions. This included redistribution of
case counts between control categories while keeping the total unchanged.
Before-audit SHA-256:
`1E6B18B306586F79AF8B345A14202075390D3423883CD38256180629F3513358`.

## Repair

Both raw runs now independently validate marker grammar, the frozen CPU profile,
typed parsed summaries, successful integer exits, raw marker/frame digests,
handoff and guest-revalidation bindings, and channel agreement. Timestamps and
both dependent mailbox checksums validate before normalization. Static markers,
frames and handoff records must match. Full aggregate observations and all 20
summary fields bind parsed evidence and validated kernel-entry host-test counts.

Every one of the 19 control categories now has its exact executed case count
bound independently of the grand total. Malformed objects reject cleanly. The
qualifier validates before creating an output directory or replacing a file.
No previous profile implementation or shared evidence helper was changed.

All 69 original cases now reject with no validator exceptions. After-audit:
`94F7EE3D5D95AFA8DD59647DD918E7FDA47876E0EFBA176E77B5CE955E690D30`.

## Executed Evidence

Two final headless two-vCPU boots pass 42 markers each, 159 individually executed
rejection cases in 19 categories, and 245 kernel host tests. Each boot installs
one AP-local descriptor set, three guarded stack classes, one x87/SSE round trip
and 27 gates. It commands quiescence, parks the AP, validates resources and
scrubs/verifies/releases 32 pages or 131,072 bytes. The final run took 71.797
seconds; tracked sources and owner data stayed unchanged. Exact receipt:
`1E1778C2E204F40D8D12C992BFF7DCEFC20067D16F9DFE1BC83CCCECFE8BD9B7`.
Qualifier log:
`6AA6B171C06F825AB34FD35B6DC0F0C4AE1B3C3BDBEA115B9A29D1DDD4812575`.

Two initial boots are superseded and not counted as final qualification; receipt
`A15F3A44972D7A5472D62EE5D62CABCE61872CBD44C1FA15B5022DA356CB450A`.
The prior receipt remains preserved separately:
`03B2E751984D8FADBB64302748E3D4CBB025F5DF285D665AAD8399CDA9DC07C2`.

All 10 focused tests pass, zero skipped, in 9.374 seconds (10.000 with runner).
The 253 permanent recorded mutations cover 14 exits, 16 coverage cases, 23
per-run evidence cases, three shapes, seven dynamic/profile policy cases, 108
observations, 40 summary values, three raw-stop cases and 39 control counts.
They run through both runtime and the actual gate with a genuine passing baseline.
Six extra root/control shapes, four raw-normalization failures and two output-
preservation cases are covered. Positive live receipts are never rebound.
Focused log:
`61B27EBF0AA15CC269E4C45EDD3DAEA30E3BEA454E63863603BAA0ACCD32FDC0`.

Combined scoped regression passes 282 distinct tests, zero skipped, in 77.336
seconds (78.141 with runner), with tracked source and owner data unchanged. Log:
`30B8009003B608F0DC78D7B837BF65750E7263551C4DB69577B0E933085BD262`.
Checklist, history, native-product and owner-data conservation pass. This is not
the full canonical suite, main-merge acceptance or production qualification.

## Remaining Work

Selected readiness is 18/27; firmware, boot trust and ELF separately pass.
Nine IPI-through-lock profiles remain from `N8-SMP-IPI-001`, followed by at least
65 scheduler controls needing individually bound rejection execution and full
exact canonical/Doctor/publication/configured-check/review qualification before
PR #78 merge. Partial projections do not replace the historical full gate.
Existing `ADD-N36-RECEIPT-COVERAGE-001` tracks the admission repair.

All 8,996 requirements, 57 additions, 40 phases, 301 subphases, 94 flags (35 open)
and 20 gaps remain. No phase or flag status changes. Inventory is 1,021 discovered
Python methods and 288 architecture bindings, not a full-suite pass. VM ownership
evidence remains scoped and unchanged; broader AP resource ownership and combined
retirement replay still depend on later profiles.

Native Rust/kernel, PooleGlyph Phase 65 and the owner-modified conformance report,
and the frozen demo ISO remain unchanged. Saved consistency is not authentication,
freshness, independent reproduction, general SMP or architectural CPU retirement.
Live failure injection at every INIT/SIPI boundary, general AP recovery, physical
hardware and production readiness remain unproved.
