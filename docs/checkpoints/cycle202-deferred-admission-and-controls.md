# Cycle 202: Deferred Admission and Executed Controls

Date: 2026-09-29. Pre-production; not full-canonical or main-merge qualification.
Parent: `27a73092bc0512ad01a33e8e7b60e1a360447187`.
Move: `N12-SCHED-DEFERRED-001`, N12.1-N12.7 and N36 under existing
`ADD-N36-RECEIPT-COVERAGE-001`. No phase or implementation flag closes.

## Reproduced Defects

A genuine pre-repair diagnostic receipt was generated on the current kernel,
without rebinding old evidence. Its two boots and 246 kernel tests passed, but
14 constant-only control groups made it unsuitable as final qualification.
The aggregate gate additionally retained the old product hash and 1,327
relocations. Correcting only those independently measured pins made the
unchanged positive receipt pass both runtime and actual gate.

Of 273 corrupted records, the old runtime accepted 258, rejected 11 and threw
four exceptions. With only the pins corrected, the gate accepted 164, rejected
90 and threw 19 exceptions. The original gate failure and both before audits
are preserved. Pre-repair receipt SHA-256:
`929191330266F7C0D5BD51963F5EE39539177F3D227E1512618FB8C68AC87BFF`.
Pin-corrected before audit:
`982DC9897D7B87DC11A9643CDE5A31090B73C85D25A1B767AAF00DCEF6A04EB1`.

## Implemented Repair

Deferred admission now fails closed on malformed roots/builds/controls, checks
canonical calendar dates and exact JSON types, reparses both runs and their
handoff/revalidation/frame evidence, reconstructs observations and the host
trace, and validates exact per-control records and source/product bindings.
The aggregate gate returns immediately on invalid admission, avoiding unsafe
nested access. The linked product must match the validated entry receipt.

The fourteen constant-only groups are replaced with twelve executable native
groups and two source-audit groups. The actual controller runs 50 host boundary
scenarios covering capacity, duplicates, top-half context, recursion, EOI,
priority, cancellation, flush, generations, five fault points and shutdown.
Some scenarios verify successful transitions; these are not 50 rejected API
calls. Six heap/callback mutations and four retained-worker-stack guard
mutations exercise the source auditor. Empty rejection lists cannot pass.
All twelve deliberately disabled native variants and a disabled source auditor
are detected. Source mutations are not privileged hardware fault injection.

The initial five-test control run failed because the flush mutation matched
two source locations; no native failure was inferred from that test setup error.
After narrowing the mutation target, all five tests passed. Failed log:
`7E5C9727611260390C0512899E8C8F97CA6516229AB6A6BB549BC3162534F95F`.
Repaired control log:
`876088AAD3E5632AB972DDF46DB3DBDE00C5707C45D456EE591323BCCDFBD09E`.

## Qualified Evidence

Two fresh final selector-17 boots pass on the unchanged kernel. Each observes
eight enqueued items, five completions, three cancellations, six worker
dispatches, twelve context transitions, five fault rollbacks, eight free slots
and 32,768 cleared worker-stack bytes. The 30 groups cover 254 executed cases:
194 marker/probe/path rejections, 50 native boundary scenarios and ten source
rejections. Two earlier diagnostic boots are separate, not additional final
qualification. The final qualifier passed all 246 kernel host tests.

Receipt SHA-256:
`5DEB81D744D08EC14895631699B64A9573F57587F6D3520476A7A57E01262F3A`.
Qualification log (92.812 seconds):
`E12A45434566B849DD8DC27938DC5EE50E8BFA45D9F58DD3867479C1C06D291E`.
Both real validators reject all 273 original corruptions with zero exceptions;
after audit: `A73B80AEE5A2D653628911AEEAACF9A503118BEB98A844B71DE8EC4C6DFAD798`.
Another 42 malformed control/source/build fields are rejected by both paths.
All 17 focused tests pass with zero skips in 33.296 seconds, including the
21 native transaction regressions in debug and optimized host builds.
Focused log: `9F919ACB3EFD449692172D20810F95AB2E672944358E3479F17506C1244A2731`.
Counts overlap and must not be summed as independent coverage.

## Closeout Regression

The first metadata run passed 42/49: seven stale expectations still named the
previous cycle, binding/profile counts and deferred-evidence state. The second
passed 47/49, with one obsolete pending count and one nonexistent historical
audit key. The actual historical Cycle 201 audit remains unchanged; correcting
the references and current-state expectations yields 49/49, zero skips.
First failed log: `53C42EAD791C3EE3CF6188AD5C5E53E1920287E57FEBB7DF49CF7495DC918658`.
Second failed log: `E3644F0F78B7D92746557FF35EAB75F429E80124D17413165FAB293A2413D648`.
Repaired log: `958559B270220C750D101074C77D004F4BA9415934C096937BABD5C05249F008`.

Combined scoped regression passes 144/144, zero skips, in 196.625 seconds.
It covers entry/core reproduction, IRQ, scheduler/preemption, deferred controls
and transactions, publication and metadata. It includes the focused and metadata
tests, so these counts are not additive. Sources and the owner report remained
unchanged during execution. Combined log:
`2CF0A1DF614AEAF90FB41206E59D002F73A88AE6BCF1DE0EC6BC7323E6F503D1`.
Conservation passes: 17 parent current records archived unchanged, 338 current
architecture bindings, locked checklist and prior receipts preserved. The
1,081-test inventory is discovery, not full-suite execution. This is checkpoint
validation, not full canonical qualification or approval to merge into main.

## Remaining Work

Selected readiness is 22/27. At least 51 constant-only groups remain across
SMP scheduling (16), AP workers (18) and SMP preemption (17). Next is
`N12-SCHED-SMP-001`: inspect and repair its recorded admission and execute its
16 missing groups before a fresh receipt. Then AP workers, SMP preemption,
atomics and locks require qualification, followed by the full exact-candidate
canonical/Doctor/release/publication/GitHub-check/review gates before main merge.

Kernel SHA-256 remains
`B19D4F7E854ECED3495D88C00F7379061B913EF00477FBD3701929B2F77D80F1`;
530,072 canonical bytes, 602,112 loaded bytes and 1,326 relocations.
The eight retained memory/AP/scheduler receipts remain earlier-cycle evidence.
No native controller code, key, signature, physical hardware, firmware, media,
tag, release, new ISO or production promotion changed. Recorded consistency
is not authentication, freshness, independent reproduction or forgery immunity.
N0 custody, N5 authenticated boot, general live task/CPU retirement, PooleGlyph
Phase 66, independent builders and the full production gates remain open.
The locked 8,996 requirements, 57 additions, 40 phases, 301 subphases, 94 flags
(36 open), 20 gaps, owner PooleGlyph changes and existing demo ISO are preserved.
