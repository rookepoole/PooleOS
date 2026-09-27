# Cycle 189: First-AP Recorded Evidence

Status date: 2026-09-26. Move `N8-SMP-FIRST-AP-001`, N8.5 supporting N36.
This strengthens qualification admission, not native kernel features or ISO bytes.

## Gap And Repair

A genuine fresh two-boot baseline passed runtime and the actual aggregate gate.
Of 67 corruptions, the runtime admitted 55 and the gate admitted 46. One runtime
and four gate evaluations raised exceptions instead of rejecting. Before-audit:
`5E3DD35914AB8A5B32DB6EB1D62898948F5C7FAAC7651EA97AFB5FBB935A3C90`.

First-AP now validates two uniquely identified raw runs, integer zero exits,
typed parsed summaries, raw marker/frame digests, handoff bindings, guest-bound
revalidation and true channel agreement. Each raw run independently validates
TSC ordering and the mailbox checksum before comparison. Only the two TSC values
and their dependent checksum may differ; static lifecycle and CPU-state markers,
handoff and frames must match. Complete aggregate observation and typed summary
bind the first parsed run and current validated kernel-entry host-test counts.
Malformed inputs fail closed and the qualifier validates before writing output.

All 67 original cases now reject without validator exceptions. After-audit:
`FF815E0DA6C952176E0430FBBC574BEC28FB5AE0DFA3355ED03BB98B0958D730`.

## Executed Evidence

Two final headless two-vCPU boots pass 38 markers each, 72 individually executed
existing controls and 245 kernel host tests. Each boot starts, quiesces and parks
one AP, then scrubs/verifies/releases 14 pages or 57,344 bytes. The final hostile
run took 72.750 seconds with tracked sources and owner data unchanged.
Exact generated receipt:
`5777FF2F8C1FC296FF4C4C1CB2233B4674DF5B1BBA15C9A7F06300DD25946841`.
Qualifier log:
`D2823B8479F27386573962DB57FA0DC7211F656CDEC4BDF03C890911B24C5242`.

Two initial boots are superseded, not final qualification; receipt
`358AB331BA34A0F207AFE93CEFFA45A355AE2DD6332EF0F9C9FBA0A9FD92C42C`.
Prior receipt `58F0EBEEA6C844714D4E57568C56987C0A9E03D92A9D29421974A6D7C91FD5AC`
remains preserved separately. Current positive receipts are never rebound.

All 12 focused tests pass, zero skipped. The 159 permanent recorded corruptions
cover 14 exit, 16 coverage, 23 per-run evidence, three shape, two dynamic-policy,
69 observation, 30 summary and two raw-stop cases through runtime and actual gate.
Six additional root/control cases and two output-preservation cases pass. A
separate synthetic payload-only test accepts one valid dynamic variation and
rejects bad checksum, coherent static CPU-state drift and unequal frames. It
does not certify fresh execution or run through a fake current-source positive.
Focused log:
`9D496774589156953AB92E2112CC5D1D73620B1A7F4DCAD3E007CA89F507B999`.

Combined scoped regressions pass 271 distinct tests with zero skips in 67.766
seconds (69.062 seconds including the bounded runner). Sources and owner data
remain unchanged during the run. Log:
`2F82DB7E7017340835E7FC84456145C49805EA3054A93BC59F2DCDFCA87B7CDD`.
Checklist, historical evidence, native products and owner-data conservation pass.
This is not the full canonical qualification suite or main-merge acceptance.

Two private intake-helper attempts failed on stale pins (cycle198 versus188,
then18 versus19 prerequisites). After correction all19 prerequisites pass.
Those failures are retained, not OS failures or successful initial intake.
The separate live baseline continued under its original handle without restart.

## Remaining Work

Selected readiness is 17/27; firmware, boot trust and ELF separately pass.
Ten profiles remain from `N8-SMP-PERCPU-RUNTIME-001` through locks. At least65
scheduler controls still need individually bound rejection execution before
full exact canonical/Doctor/publication/configured-check/review qualification
and PR #78 merge. The historical release-gate file is not replaced by a partial
projection. Existing `ADD-N36-RECEIPT-COVERAGE-001` tracks this admission repair.

All 8,996 requirements, 57 additions, 40 phases, 301 subphases, 94 flags (35open)
and20 gaps are retained. No phase or flag status changes. Inventory is1,016
discovered Python methods and287 architecture bindings, not a full-suite pass.
The separately qualified VM ownership record is unchanged; broader AP runtime
and combined ownership replay remain pending.

Native Rust/kernel, PooleGlyph Phase65 and owner-modified report, and frozen
demo ISO bytes remain unchanged. Recorded consistency is not authentication,
freshness, independent reproduction, general SMP or architectural CPU retirement.
Live failures at every INIT/SIPI boundary, general AP recovery, physical hardware
and production readiness remain unproved.
