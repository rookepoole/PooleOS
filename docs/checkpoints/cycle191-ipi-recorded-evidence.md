# Cycle 191: IPI Recorded Evidence

Status date: 2026-09-26. Move `N8-SMP-IPI-001`, N8.5/N8.6/N9.5 supporting N36.
This repairs qualification admission, not native kernel features or ISO bytes.

## Demonstrated Gaps

A genuine fresh two-boot baseline passed runtime and aggregate admission. Of 66
corruptions, runtime admitted 48 and the gate admitted 40; the gate also raised
three exceptions. The audit includes successful-exit types, missing runs,
cached observations, per-control count redistribution and coherent changes to
raw frame checksums. Before-audit SHA-256:
`1FE9D8F3E79463176F3FB84ACAED13A0BFE3BD9E88155CA55098C4D7F0C9FD2B`.

Three release-accounting controls previously rejected unequal constants rather
than calling the real validator. Thus the previous reported 249 cases included
246 parser/model rejection executions and three constant comparisons. They are
not retrospectively promoted to meaningful execution coverage.

## Repair And Verification

Both runs now validate strict exit/count types, run IDs and CPU profile, raw
markers and their digest, parsed summaries, handoff and guest-revalidation
bindings, dual-channel agreement, and nonblank matching frames. Complete typed
observations and 17 summary fields bind the parsed evidence. Every one of the
30 control categories has its exact case count checked, independently of totals.
Malformed input rejects cleanly; qualification rejects before replacing output.

The host independently recomputes old/new frame aggregates with separate FNV64
domains and ordered AP masks/addresses. This oracle covers the frozen contiguous
private-resource/frame layout, not arbitrary allocator layouts. Three accounting
controls now call the same validator as marker admission. Disabling that
validator makes the negative-control execution fail, as a permanent test proves.

All 66 original cases now reject with zero validator exceptions. After-audit:
`8D871AC61941C027378508F6538B7078275213082F2C263C5533F577EB39364F`.

Two final headless four-vCPU boots pass 40 markers each, 249 executed rejection
cases across 30 categories and 245 kernel host tests. Each boot exercises three
AP runtimes, partial-start rollback and retry, three remote invalidations, and
cleanup of 96 resource plus six frame pages, with 417,792 bytes verified.
The qualification took 100.594 seconds; all 1,558 tracked files and owner data
were unchanged during execution. Exact generated receipt:
`7ADC371664FB3778A02688DBB521211237A4788CA01EF61B48C410CEF5898B44`.
Qualifier log:
`3A54459FA80BF16849BAE25B15FD7D59B3D30E403057A683A053E7D568C3A23F`.

All 31 focused tests pass, zero skips, in 63.155 seconds (63.812 with runner).
They exercise 528 recorded mutations through runtime and actual gate: 14 exit,
16 run coverage, 23 evidence, three shapes, eight profile/policy, 367 observation,
34 summary, two raw-frame and 61 control-count cases. Additional coverage
includes six root/control shapes, six zero-checksum rejections, four frame-address
mutations, six direct accounting rejections and two output-preservation cases.
Positive live receipts are never rebound. Focused log:
`7D708D7E007B0EF1C94E78E7906A061938A1ECB059A26A6A09571D8EDD9125DF`.

Four payload-only tests passed first; that is consistency evidence, not a new
boot. Initial two boots are superseded, with receipt
`2AA019A85D2C5DC032E5BB7A0F1B714FF27FD6F1772701687594F40B2D3430B6`.
The prior receipt remains preserved separately:
`2B1F8D623D31476F2C8886DFD583BE9514C68A2B3D0DA36BC75DDD13D6823CCA`.

## Open Native Mailbox Work

The guest checks baseline/runtime mailbox checksums for each of three APs, but
PKSMP5 does not export all inputs required for independent host recomputation.
The host currently checks only nonzero/distinct checksum words before normalizing
them. A synthetic test documents that different coherent nonzero checksum values
can compare equal after normalization. This is an explicit limitation, not
fabricated live evidence or proof of complete raw integrity.

Next move `N8-SMP-MAILBOX-ORACLE-001` belongs to existing
`ADD-N36-RECEIPT-COVERAGE-001` and open `FLAG-N36-RECEIPT-COVERAGE-001`:

1. Export complete baseline/runtime mailbox inputs from native PooleKernel on
   both channels, bound to AP identity and snapshot phase.
2. Independently derive both checksums before normalization; reject missing,
   duplicated, reordered, malformed and coherently altered input records.
3. Add direct oracle and actual-gate controls, preserving historical opaque
   receipts and testing real fresh boots on the changed native image.
4. Requalify every affected boot/image dependency, then resume the eight
   scheduler-through-lock profiles and the 65 scheduler control-execution gaps.

This gap blocks merge qualification. The independent oracle is not claimed done.

## Progress And Limits

Selected readiness is 19/27; firmware, trust and ELF separately pass. The bounded
PKAPOWN1 ownership integration is current: two attempts per run, 27 copied-free
and 18 owner-release rejections per attempt. VM187 evidence is retained separately;
this cycle does not repeat those boots. General task-stack/context and CPU
retirement, complete mailbox integrity and full exact qualification remain open.

All 8,996 requirements, 57 additions, 40 phases, 301 subphases, 94 flags (35 open)
and 20 gaps remain. No phase/flag state or normative charter condition changes.
Inventory is 1,028 discovered Python methods and 289 architecture bindings,
not a full-suite pass. Initial combined regression passed 312/314, with two
historical IPI/embedded-entry expectations needing reconciliation after fresh
admission. Its failed log is retained:
`9F94FF8807A23394981C5D659B8AE30F74AF54509C816E67B02D5E55F042477E`.
The assertions now distinguish current IPI from preserved historical receipts.
The combined rerun passes all 314 tests, zero skipped, in 108.812 seconds
(109.641 with runner). Its source-stable log is
`40361D70294E071A558B56D685628287D99225A4AB938293B35FC320474481FA`.
Checklist, history, native products and owner-data conservation pass. This is
scoped regression, not the full canonical suite or main-merge qualification.
Historical full release-gate evidence is not overwritten by a partial projection.

Native Rust/kernel, PooleGlyph Phase 65, the owner's conformance report and frozen
demo ISO are unchanged. Recorded consistency is not authentication, freshness,
independent reproduction, general topology, physical hardware or production
readiness. Main merge still requires full exact qualification and review.
