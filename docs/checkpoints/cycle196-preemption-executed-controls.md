# Cycle 196: Executed Preemption Controls

Status date: 2026-09-29
Move: `N12-SCHED-PREEMPT-001`, N12.1/N12.2/N12.3/N12.5/N12.6/N12.7 and N36
Requirement: `ADD-N36-RECEIPT-COVERAGE-001`
Status: bounded pre-production qualification; full merge qualification pending

## Implementation And Evidence

Nine constant-only PKSCHED2 control records are replaced with executed checks.
Seven groups run the actual native Rust scheduler/controller on the host:
17 interrupt-frame, 15 context-ownership, two capacity, three deadline, four
duplicate-event, three quantum and six transactional rollback cases. Exact
errors, unchanged snapshots and repeated failing events are checked. Seven
independently compiled disabled-check variants fail the harness as intended.
The harness lives outside kernel product sources; native kernel bytes do not
change. This is not additional privileged native or hardware execution.

Three linked-scope corruptions use disassembly/symbols of the exact linked
kernel. Four retained-stack guard removals exercise source admission. Both
auditors are also disabled in regression tests to ensure controls cannot pass
unconditionally. These audits are not hardware stack fault injection.

Admission now reparses raw paired guest and host evidence, verifies typed
observations and accounting, binds shared validator sources, and requires exact
per-control counts. The release gate fails closed on malformed evidence. The
command-line qualifier validates before creating or replacing output.

Two final guest boots, 246 kernel host tests and 226 rejection cases in 25 groups
pass. The final receipt passes its runtime validator and actual release gate:
`2DFF24BCF02069ADB74E78F53F63A1F3EBF2C1EB478F2DBFF7D27D31E9FD757B`.
Final qualifier elapsed time: 119.953 seconds; log SHA-256:
`C4CA732801FB906F7442652BE154022EA0C59C4E633C31145D785E2F4E5A52F5`.

All 17 focused tests pass with zero skips in 18.887 seconds. They reject 206
general recorded-evidence mutations and 26 additional control-receipt
corruptions through runtime and actual gate, detect disabled validators, and
preserve existing outputs and absent output directories on rejection. Log:
`3691DE7B42E0F1DE99AFB5C59FE41C7AD4B87F741445B8F78404CCD260C9396F`.

## Preserved History

The original two-boot diagnostic baseline used the faulty qualifier and is not
admitted as final. Its log is
`F27418BA8A30BC7A9D927DC2294764FE85E00991A54F2E600DE91D841DF6EA1D`.
No pre-repair corrupt-receipt acceptance audit was performed; no before/after
acceptance counts are inferred from the source finding.

A repaired two-boot receipt passed before shared-validator source bindings were
added. It is superseded, not rebound; its SHA-256 is
`164474EBF4F39568FB862ED1CAEB091D67286C83ED9D1D4D6842564F78B75925`.
Its 17-test pass log is
`87E27BB3D7BF81C7DA72F8DA92612D5A12CF179CE9D33B2F6D8842A3F04B9880`.
An incorrect diagnostic command referenced a nonexistent script and exited
before testing. That failure is retained with log
`453A2C314D2DE1B07BF0BA1C1264761D5302666CAFFDC24C83F1C0E9A26B7E63`.
The initial and final qualifier summary logs are byte-identical; their distinct
command records and source-bound receipts distinguish the runs.

Initial metadata regression passed 38/43. Five assertions still described seven
pending profiles, the now-replaced preemption receipt, or 310 source bindings.
They now preserve historical digest checks while admitting current preemption,
checking deferred work as stale, and expecting six pending profiles and 317
bindings. Failed log:
`AA017E30138D78D74C1EC897A00BE2A2754C2AEC752709A427CED9620761188B`.
A second metadata run passed 41/43 and exposed two further old projection-count
assertions; its failure log is
`FDD9E51069EC121555660AE685A86169F2B1B9480C1D151D86FC6FB6038D9523`.
Corrected metadata passes 43/43, zero skips, in 7.335 seconds; log:
`5C8B473007606E357FF95139D1EA1DB9FD5C87638C5184DDCB341475758E2687`.

## Progress And Boundaries

Selected readiness advances to 21/27, leaving six deferred-through-lock
profiles pending. The known unproven-control lower bound drops from 74 to 65
in four later qualifiers. The historical nine-group finding is retained.
No phase or flag closes. Source inventory is 1,060 Python tests, not a suite
pass. Broader regression passes 339 tests with zero skips in 305.449 seconds,
including exact kernel reproduction; log SHA-256:
`A4D0AA0BCE12B72DF1E456052D10EB8D54132371E2391CA524E121492CD9A800`.
Initial conservation passes, preserving all prior records and owner data.
Final metadata replay, conservation and exact publication scan must precede
the checkpoint commit; full exact-candidate canonical/Doctor qualification still
precedes main merge. Native image remains the Cycle 192 kernel, SHA-256
`B9AF7DFB13472C0A0D3CBE70036EFAD7C3B792F13FC9944ACEC935B362F0FBA8`.

Next: `N12-SCHED-DEFERRED-001`, then SMP scheduling, AP workers, SMP preemption,
atomics and locks, repairing evidence controls before admitting fresh receipts.
Recorded consistency is not authentication, proof of freshness, independent
builders or physical-target qualification. No ISO, key, signing, hardware,
firmware, physical-media, tag, release or production-promotion action occurs.
