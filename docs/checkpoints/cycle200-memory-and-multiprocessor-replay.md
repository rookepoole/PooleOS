# Cycle 200: Current-Kernel Memory and Multiprocessor Replay

Date: 2026-09-29. Pre-production; not full-canonical or main-merge qualification.
Parent: `ad22edd4be88c84d50ee5be59cce5c433b1f2b7c`.
Selected: `N9-PMM-ACPI-CONSUMER-001`, N9.1/N9.2 supporting N10/N36, then
dependent VM, IRQ and N8 AP/IPI profiles. Existing requirement:
`ADD-N36-RECEIPT-COVERAGE-001`.

## Measured Execution

Six profiles pass twelve final virtual boots, 421 control groups and 1,137
executed rejection cases. Every qualifier passes the same 246 kernel host
tests; repeated execution does not make these distinct test inventories.
There are no superseded guest runs this cycle.

| Profile | Boots | Control Groups | Rejection Cases | Receipt SHA-256 |
| --- | ---: | ---: | ---: | --- |
| physical_memory | 2 | 191 | 191 | `C4AD82F6B52D987F303DB02E5FBFEF7B782277168ACD921A0B27510AFB6E328B` |
| virtual_memory | 2 | 48 | 48 | `52526BF1B46D4739B636032D6BAFDA774E31495EF1F381863B0785BFF6E2FF13` |
| interrupt_time | 2 | 58 | 58 | `558819215BF1EE636FEFBE496BD5F06612B1362DF92D29AD4A8E771CE9A7F2BA` |
| smp_first_ap | 2 | 72 | 72 | `6293B3B799ED48F4F923AD6483C218D68D4EBA885EE2A02C04825929B7845B31` |
| smp_percpu_runtime | 2 | 19 | 159 | `31C04EFD10CD2BE8E1DBCDF3E08655AB525909987E61F83E52D1CAD907543888` |
| smp_ipi | 2 | 33 | 609 | `1CECF18AF71AA97276AF28BC6AFA1815649A110B50084ACDFEFAA6A2D2468619` |

PMM manages 129,079 pages with independently checked ACPI retention and gated
reclaim. VM records 367,405 physical table writes and checks active-root
restoration and page ownership. IRQ delivers and acknowledges eight timer
interrupts. First AP verifies 57,344 scrubbed bytes; per-CPU verifies 131,072
bytes and 27 descriptor gates. IPI starts three APs in a four-vCPU profile,
checks partial-start rollback and fresh retry, performs three remote TLB
invalidations and verifies 417,792 scrubbed bytes. Each partial/full ownership
attempt rejects 27 retained-free and 18 premature owner-release operations.
General task-stack and CPU-retirement integration remain unverified.

Kernel bytes are unchanged: 530,072 canonical bytes, 602,112 loaded bytes,
1,326 relocations, build `PKBUILD1-CYCLE197-N12-DEFERRED-V1-0000000001`.
Kernel SHA-256:
`B19D4F7E854ECED3495D88C00F7379061B913EF00477FBD3701929B2F77D80F1`.
Entry receipt:
`70814DA7358BEE6FA6E5D2341D251ACE57A906BA4FB2E9E12BD8D53677C7E38D`.
The host core receipt remains the Cycle 197 evidence. Current VM/IPI execution
does not silently regenerate or relabel that host record.

## Repaired Admission Pin

The final IPI qualifier passed and its independent runtime validator accepted
the fresh receipt. Admission nevertheless failed at the aggregate gate:
`PKSMP5 embedded kernel identity changed`. The gate retained Cycle 192's
`B9AF7DFB13472C0A0D3CBE70036EFAD7C3B792F13FC9944ACEC935B362F0FBA8` hash.

The before audit preserves that failure against the genuine fresh candidate.
Only the aggregate pin and an independent gate test changed. The same candidate,
with unchanged source-bound inputs, passes both runtime and gate after repair.
The five preceding receipts were already validated and admitted. The chain's
exit code 1 records an admission rejection, not a guest failure. No failed boot
is relabeled, no receipt is rewritten to fabricate execution, and no extra
guest run is counted. Four independent wrong-image/type cases reject after a
genuine positive baseline, with component validators isolated to exercise the
aggregate pin itself.

## Regression

All 93 scoped tests pass with zero skips in 121.922 seconds. They include 1,896
corrupted saved receipts through runtime and actual gate: 234 PMM, 115 VM,
229 IRQ, 159 first AP, 253 per-CPU and 906 IPI. The suite also checks 360 raw
mailbox mutations, disabled PMM parser/accounting and IPI validator/oracle
detection, invalid-output preservation, 20 memory gate cases and four new
independent IPI pin cases.
Focused log SHA-256:
`0492DA3723BE1ED1565D43A4674EF948EF0862969D5E31F64B73C51BD8CD7B5A`.

Source and owner-data snapshots stayed unchanged during each bounded worker.
Short qualifier summary logs can repeat across cycles because their printed
counts are identical; they are not unique execution identities. Fresh receipt
identities and separate raw evidence are retained. Recorded consistency is
not freshness, authentication, independent-builder attestation or exclusion
of coherent forgery.

## Remaining Work

The first metadata run passed 41/47 tests. Six assertions still expected current
memory/IPI receipts to contain the old kernel. They are reconciled to validate
current receipts separately from preserved historical hashes and records.
The initial failure log is retained:
`FD309DC9C6C222B6415AA193577477CA14E9E72E1441DBD5551401B2B7D058F6`.
This was a metadata reconciliation failure, not a new guest or runtime failure.

Corrected metadata passes all 47 tests with zero skips in 17.609 seconds.
Log SHA-256:
`8F6A7844FD179AF3170B9E97166E49AD873834299261BC572D5ADBF5BFEB2A16`.
Combined scoped regression passes 327 tests with zero skips in 472.891 seconds,
covering boot, kernel entry/core, CPU, memory/IRQ/SMP, metadata and publication
checks. Source and owner-data snapshots remain unchanged throughout that run.
Log SHA-256:
`F568E4C6D77BEF54DEACFAA2181B0E81C6B3F5A2DBBF4A8261C28B3D825211AA`.
This run preceded result recording; the final metadata is checked separately.
Initial conservation passes: 17 archived parent current records, 326 architecture
bindings and 1,071 discovered tests. These are scoped checks, not full canonical
merge qualification, and the test counts overlap rather than adding together.

Current selected readiness passes 19/27. Next: `N12-SCHED-001`, then BSP
preemption, deferred work, SMP scheduling, AP workers, SMP preemption, atomics
and locks. Eight profiles still require current-image qualification. Deferred
recorded-admission repairs and at least 65 control-execution groups remain
open under the existing N36 requirement. Full exact-candidate canonical/Doctor,
publication, configured GitHub checks and review gates still precede main merge.

Roadmap history must preserve all parent current-record snapshots and earlier
checkpoints. No phase or flag closes: 40 phases, 301 subphases, 8,996 requirements,
57 additions, 94 flags (36 open) and 20 gaps remain accounted for. The 1,071
discovered tests are inventory, not a full-suite pass. Native sources, the
locked checklist and coverage, normative charter, PooleGlyph Phase 65 and the
owner-modified report, earlier non-replaced receipts and existing demo ISO
remain unchanged.

No new native kernel feature, independent builder, physical hardware operation,
key use, signature, firmware/media change, release, ISO or production promotion
is claimed. This checkpoint is for development-branch backup through draft
PR #78; main remains qualified `ac15d1d` until full merge requirements pass.
Ignored raw logs, tools and local ISO output are not part of the Git backup.
