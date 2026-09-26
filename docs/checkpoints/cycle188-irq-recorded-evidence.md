# Cycle 188: Interrupt/Time Recorded Evidence

Status date: 2026-09-26. Move `N8-IRQ-001`, N8.1/N8.3 supporting N36.
This repairs qualification admission, not native kernel features or ISO bytes.

## Demonstrated Gap And Repair

A genuine fresh two-boot baseline passed runtime and actual aggregate gate.
Of 64 malformed records, runtime accepted 52 and the gate accepted 44. One
runtime and four gate evaluations raised exceptions instead of rejecting.
The marker parser also divided by zero for a zero-length calibration sample.
Before-audit SHA-256:
`011B519EB45330A2E04E3C7CCCBF237127A0AEA1D74E895E5209223203515329`.

IRQ now validates strict two-run evidence, unique run IDs, integer zero exits,
parsed marker summaries, marker/frame digests, handoff bindings, guest-bound
revalidation and true channel agreement. Complete aggregate observations and
readiness summaries must match parsed evidence with exact JSON types. Host-test
counts bind to current validated entry evidence. Calibration uses the independent
bounded oracle before frequency arithmetic, including sample, counter and
frequency limits. Malformed shapes fail closed in runtime and aggregate gate.
The qualifier validates before creating a parent or replacing an output file.

All original 64 cases now reject without validator exceptions. The zero sample
raises the declared validation error, not `ZeroDivisionError`. After-audit:
`D06DA52166453BD9E72604ABFF7A6C860D530A64AEB1A7C1CB155817E13350AD`.

## Executed Evidence

Two final qemu64 headless boots pass 36 markers each, 58 individually executed
existing controls and 245 kernel host tests. Each boot reports eight timer
deliveries, eight EOIs, exact normal-path rollback and no AP startup. The final
hostile-environment qualifier took 78.312 seconds with tracked sources and
owner data unchanged. Exact generated receipt SHA-256:
`A8812EE8F48CBA157554EB3264EA945082641014D9E2FE1C7A3982D648FF046B`.
Qualifier log:
`98DE2D5B7B345ED29CFDA5E1BBE0160126A332F0E4319B4AF91FCE66567C4606`.

The two initial boots are superseded, not counted as final qualified runs.
Their receipt is `6AD05F1D92CB328088D56DD064F4D011D818D85FDD15153DF1314F2B7B939076`.
Prior IRQ receipt `19FB9DA0B525064D56126E9EEE159C887A46B4FD1EB6B6DA3646C5F88182E7B2`
remains separately preserved; current evidence is copied exactly, never rebound.

All 12 focused Python tests pass, zero skipped. The 229 recorded mutations
cover 14 exit, 16 coverage, 23 per-run evidence, three shape, 145 observation,
22 summary and six clock cases through runtime and actual gate. Six additional
root/control-shape cases reject. Six direct clock-boundary tests require the
declared error, and two qualifier-output cases preserve existing/absent output.
Focused log:
`8477E89A8F5030CE86DB3659E0C22E57E74AC1E7BDDBEB48D48F86C3F0D3F3A7`.

The combined boot/CPU/PMM/VM/IRQ/core/progress regression passes 258 tests with
zero skipped and no duplicated selectors. Log:
`E7C1BEF95B382EE94A18126281845A2750A43521B8BCFCB17190A1CF68F21810`.
Checklist, historical evidence, phase/flag and owner-data conservation pass.
This is scoped regression, not full canonical or merge qualification.

## Progress And Limits

Selected readiness is 16/27; firmware, boot trust and ELF separately pass.
Eleven profiles remain from `N8-SMP-FIRST-AP-001`: SMP, scheduling, atomics and
locks in dependency order. At least 65 scheduler controls still require
individually bound rejection execution. Full exact-candidate canonical/Doctor,
publication, configured GitHub checks and review still precede PR #78 merge.
The historical release-gate file is not replaced by a partial projection.

Existing `ADD-N36-RECEIPT-COVERAGE-001`, `FLAG-N36-RECEIPT-COVERAGE-001` and
`FLAG-N8-IRQ-001` retain these obligations. All 8,996 master requirements, 57
additions, 40 phases, 301 subphases, 94 flags (35 open) and 20 gaps remain
accounted for. No phase or flag closes. Inventory is 1,011 discovered Python
methods and 286 architecture bindings, not a full-suite pass.

The VM ownership replay remains current only in its declared scope; AP and
combined ownership replay remain pending. Native Rust/kernel, PooleGlyph Phase65
and its owner-modified report, and the frozen demo ISO are unchanged. Recorded
consistency does not prove freshness, authentication, independent builders,
physical hardware, general SMP, panic-time recovery or production readiness.
