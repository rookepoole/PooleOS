# Cycle 194: Current-Kernel Memory and AP Replay

Qualification date: 2026-09-26
Closeout date: 2026-09-27
Status: bounded native qualification; pre-production, not merge-qualified
Selected move: N9-PMM-ACPI-CONSUMER-001, N9.1/N9.2 supporting N10/N36
Parent checkpoint: `6e73492c6c99c41a03c6c71a09de74b2e9d049bf`

## Scope and Execution

Five profiles are freshly executed in dependency order against the unchanged
Cycle 192 mailbox kernel. Every generated receipt passes its independent
runtime validator and the actual release-gate check before admission.

| Profile | Fresh boots | Control groups | Executed rejection cases |
| --- | ---: | ---: | ---: |
| Physical memory / ACPI retention | 2 | 191 | 191 |
| Sparse virtual memory / active-root restore | 2 | 48 | 48 |
| Interrupts and time | 2 | 58 | 58 |
| First application processor | 2 | 72 | 72 |
| Per-CPU runtime | 2 | 19 | 159 |
| Total this cycle | 10 | 388 | 528 |

Each qualifier passes all 246 native kernel host tests. PMM manages 129,079
pages in the bounded profile. VM records 367,405 physical table writes and
validates active-root restoration and retained ownership. IRQ delivers and
acknowledges eight timer interrupts. First-AP verifies 57,344 scrubbed bytes;
per-CPU verifies 131,072 bytes, 27 gates and both independently reconstructed
mailbox checksums before allowing timestamp normalization. These counts do not
prove general topology, hardware support or the N8/N9 phase exit.

No native source or canonical kernel bytes changed. Canonical SHA-256:
`B9AF7DFB13472C0A0D3CBE70036EFAD7C3B792F13FC9944ACEC935B362F0FBA8`.
Build ID: `PKBUILD1-CYCLE192-N8-MBX-ORCL-V01-0000000001`.
The retained IPI192 and CPU193 boots are not included in this cycle's ten boots.

## Receipt Identities

- PMM: `BB5C864CF76128B9D144D360B12792E70C0E2ED6A5986019328967A5B15CF0A8`.
- VM: `2D2FC54F7AC8DB642E5F628CCF381F33C05100D9FE1D1245FE73374A114B2CAF`.
- IRQ: `9FED29AEE36D11165C2F800376DE4EC9BE0E558AB5225170908C6A176F19DE81`.
- First AP: `7B20241B707FBC077AA2DD937354E4347AD7952673491C9CA9A77EDD40C43401`.
- Per-CPU: `4C218EAAEB01673F7F0C45ED9DA92895E6EC564AA6A5EEAA57BFB09162F1B99B`.

The machine roadmap binds each execution log digest and duration. Source and
PooleGlyph owner-report snapshots were unchanged during every qualifier.
Original diagnostic handles were observed to completion, not restarted when
buffered logs were quiet. IRQ completed during the owner's cloud-backup inquiry.

## Regression and History

All 57 focused Python tests pass, zero skips, in 43.642 seconds. They reject
990 corrupted receipt variants through both runtime and actual gate:
234 PMM, 115 VM, 229 IRQ, 159 first-AP and 253 per-CPU. Invalid-output preservation,
malformed root/control cases, source mutations and dynamic checksums are also
tested. The new PMM test observes 189 parser calls for the baseline and 188
marker controls, plus three independently checked PBP1 mutations. Disabling
either the parser or memory-accounting oracle causes qualification to fail.
Focused log SHA-256:
`3D9CF2291DCB897F2ED2443A43C8819640BA3513C62A2EDF228B7601B907CE96`.

One private measurement helper initially assumed IRQ used PMM's summary key
`qemu_run_count`; it raised `KeyError` before writing a result. The corrected
helper counts the validated execution-run array and measures 19/27 selected
checks passing. This helper failure did not invalidate or rerun a guest boot.

Roadmap 194 archives six replaced current records without changing earlier
history. A new regression pins five historical dependency-record digests and
separately verifies fresh receipt identities and current VM ownership evidence.
Architecture inventory becomes 303 bound sources and Python inventory becomes
1,044 discovered tests. Inventory is not a full-suite execution result.
The full exact-candidate canonical/Doctor suite has not passed this candidate.

Initial roadmap/architecture/checklist regression passes 42/42. Conservation
against the parent checkpoint passes, including all earlier checkpoint files.
The initial combined-suite command exited with code 2 before running tests:
`unittest` rejected new test names placed after an interleaved `-v`. Its log is
preserved as `E5BD949E09F100EBA3AF6986500A528EFC66CE300495179FC4558DC29BD5BE74`.
The corrected invocation puts all module names before the final option.

The corrected combined regression passes 307 tests, zero skips, in 289.696
seconds. It includes exact kernel-entry reproduction, CPU/boot/mailbox/IPI/core,
all five newly qualified profiles, roadmap/checklist and publication regression.
Tracked sources and the owner report were unchanged throughout execution.
Log SHA-256: `2C98C22223D5F67165F3499344B0D0898A6913E609955666CDFDD389641D9FBA`.
After recording these results, final metadata and exact-index publication are
rechecked before committing. These checks do not replace full qualification.

## Remaining Work

Next: N12-SCHED-001, followed by BSP preemption, deferred workers, SMP scheduling,
AP workers, SMP preemption, atomics and locks. Inspect real control execution
and raw recorded-run validation before accepting each replay; repair any
confirmed admission gaps under the existing receipt-coverage requirement.
Repair the existing 65 unproven scheduler groups
under ADD-N36-RECEIPT-COVERAGE-001, beginning the PKSCHED3 control audit. Then run
the full exact-candidate canonical, Doctor, publication, configured-check and
review gates before a main merge. These are engineering work, not an approval wait.

No phase, subphase, flag or program gap closes. Forty phases, 301 subphases,
8,996 master requirements, 57 additions, 94 flags (35 open) and 20 program gaps
remain. PooleGlyph remains at Phase 65; its owner-modified report is preserved.
The locked checklist, historical release-gate artifact, demo ISO and normative
charter are unchanged. No new ISO, key use, physical operation, tag, release or
production promotion is claimed. General task/CPU retirement and independent
builders still require their own evidence.
