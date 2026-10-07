# Cycle 205: Current-Kernel CPU Replay

Status date: 2026-09-29. Pre-production, single-host virtual qualification.

## Scope

`N7-TRAP-001`, N7.5/N7.6, followed by N7.1/N7.3/N7.4 CPU dependencies,
under `ADD-N7-XSTATE-001` and `ADD-N36-RECEIPT-COVERAGE-001`. Entry state
was 8/27 selected current-source checks after the Cycle 204 boot replay.
Five fresh CPU receipts now bind the unchanged Cycle 203 kernel. No native
source, entry/core receipt, prior boot receipt or demo ISO was changed.

## Executed Evidence

| Profile | Receipt SHA-256 | Final boots | Controls |
| --- | --- | ---: | ---: |
| Traps | `6CCBE079A996F2257D9605047331DD7FFCF51130F97B4F173E50A68911208674` | 6 | 51 |
| CPU policy | `9EA8402056FB8A83F37AA8A541043B79F55A9AE656AA4B442D6E94AA7FEE8014` | 2 | 41 |
| xstate policy | `48095CE52295F2C8512DD2CBAA7581FE4C1F3DA2EEA5194843299901D35CC551` | 2 | 43 |
| xstate exceptions | `5EEA8DA366205957DF6C735D54A46A6B80EC7264D700F80A5F7D775B02EEAAE0` | 2 | 43 |
| Privilege/MSR policy | `2C4F4AD1A98C3626182DCFEDB1D9C2664BD34E9090905E5C4D96A054CCD11CD7` | 2 | 47 |

Fourteen successful virtual boots and 225 controls passed. Each qualifier
reproduced and validated the current entry product with 246 kernel host tests.
Every final run exited as expected and bound dual-channel markers, retained
handoff bytes and independent kernel revalidation. Repetition is on one host,
not an independent builder or physical-target qualification.

Traps cover three exact returning faults, terminal double-fault containment,
and an explicitly synthetic malformed-frame rejection. CPU policy is a read-only
BSP observation of the qemu64 compatibility model. xstate policy performs two
saves and four restores, clears 8,192 image bytes and makes three allowlisted
guest configuration writes. Two WHPX exception boots each deliver three
exceptions, recover twice and terminally reject the deliberate `#NM` probe;
four configuration and two recovery writes are confined to the virtual guest.
The privilege/MSR profile observes eleven support-gated reads, ten MCA banks,
zero MCA-bank reads, zero MSR writes and no activation. Linked exception/MSR
audits pass. Authority grants, signatures and post-exit firmware calls stay zero.

One separate TCG probe reproduces the declared vector-19 delivery limitation.
It is diagnostic evidence, not one of the fourteen successful boots. No failed
qualifier, superseded new receipt or physical-hardware execution is counted.

## Adversarial Regression

All **54/54 focused tests** passed, zero skips, in 179.343 seconds; log SHA-256
`D2E79D016939E8D878FEDABCF471825C8DEEF0742CF8DB7700042639061E1A29`.
The scope includes:

- 3,398 corrupt control records rejected by both runtime and actual aggregate
  gates: 1,084 trap, 546 CPU, 572 xstate, 572 exception and 624 MSR cases;
- 371 malformed pair-evidence cases: 98 exits, 112 coverage and 161 typed
  marker/transcript/handoff/screenshot cases, including identical corruption
  across both runs so pair equality alone cannot reject it;
- 80 embedded-entry and 20 invalid-current-entry dependency cases;
- 51 executed trap marker-validator calls and detection of a disabled validator;
- 26 aggregate CPU identity/promotion rejection cases, including five additional
  previous-image, zero, null, false and empty hash cases;
- twelve independent entry-gate pin rejections and existing CPU/errata boundaries.

The fresh trap receipt initially passed its runtime validator but the aggregate
gate rejected it with `PKTRAP1 build or feature isolation changed`. Inspection
identified its obsolete kernel197 digest pin, not a native execution failure.
Only that measured image pin was updated to kernel203; added tests require
the prior hash and malformed hashes to remain rejected even with the component
validator bypassed in the negative test. No bypass admits a real receipt.
Cycle 199's original control-admission counterexamples remain historical;
the pre-repair implementation was not rerun or claimed as repaired anew here.

Counts overlap. Finite corruption rejection does not authenticate unsigned
records, exclude coherent forgery, or constitute all-vector or full-system proof.

## Combined Regression

All **242/242 combined scoped tests** passed with zero skips in 364.890 seconds;
log SHA-256 `FB57C8B9D99427CD73CB2F594E8AE0BC58C950796F5F7E5A8D01AB2F66DEB5B0`.
This includes boot and CPU admission, native SMP/deferred transactions, core
validation, exact entry reproduction, host-tool provenance, publication and
metadata. The initial metadata run also passed 52/52 in 24.907 seconds, log
`B31841C8F7022131396AA3E7E67378B4F128B8EA05E3589BC187D576424F2053`.
Source and owner data were unchanged during each execution. Counts overlap.

Initial conservation passes: 346 source bindings, 19 unchanged archived progress
records and 1,087 discovered tests. Discovery is inventory, not full execution.
Prior checkpoints, native bytes, entry/core receipts, owner data, locked checklist,
normative charter, demo ISO and every phase/flag status are preserved. This scoped
regression is not full canonical qualification or main-merge eligibility.

## Frozen Inputs

- Build ID: `PKBUILD1-CYCLE203-N12-SMP-TXN-V1-00000000001`.
- Canonical kernel, 530,072 bytes: `A943DCB6E41A27F952868F05ED2B3523B47D9D7A7B5DB909EE385205F7CA3B31`.
- Linked kernel, 7,046,784 bytes: `557687A9F39EEECFFD839A8619D696CEBB4E391B229778162725752C72B4D9AA`.
- Entry receipt: `E90F11157F3416CE2C78650C4605ADF92BF5D7AC19A293E0C105499EF17276A5`.
- Reclamation-core receipt: `33EE501601ACB8109FA867C2634FAC1C04F43505B4DD6C6D75821545B120BDD8`.
- Trap frame, unchanged: `E9D4CFD48C23DBA760AED5B2049B39DCA49A0D172F680D570082EB0680FDFDBD`.

Each bounded runner observed unchanged source and owner report during execution.
PooleGlyph Phase 65 remains the newest inspected checkpoint; its manifest, ZIP
and dirty owner conformance report were preserved. Phase 66 CoreIR remains
future integration work. Prior checkpoint documents and receipts remain in Git
history; private work directories and raw logs remain local.

## Remaining Gates

Selected current-source readiness is **13/27**. Fourteen memory, interrupt,
SMP, scheduler, atomic and lock profiles still require qualification, beginning
with `N9-PMM-ACPI-CONSUMER-001`. SMP recorded admission and at least 51 later
control groups remain open: 16 SMP, 18 AP-worker and 17 SMP-preemption groups.
All 94 flag statuses, including 37 open flags, and all phase statuses are retained.

No all-vector trap coverage, user-context exception handling, general scheduler
xstate ownership, physical-target errata/microcode acceptance, independent
builder, N7 exit, new ISO, signing, release or production promotion is claimed.
Full exact-candidate canonical, Doctor, release, publication, configured GitHub
checks and review conditions still precede main merge. Cloud branch backup is
separate. Next: physical-memory and ACPI-consumer qualification on these same
kernel bytes, then the ordered downstream replay and scheduler control repairs.
