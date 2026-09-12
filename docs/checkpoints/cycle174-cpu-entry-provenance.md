# Cycle 174: CPU Entry Provenance And Replay

Status date: 2026-09-12
Selected move: `N7-TRAP-001`, N7.5/N7.6 and dependent N7.1/N7.3/N7.4 profiles.
Status: five CPU qualifiers pass; memory/SMP replay and full qualification pending.

## Implementation

The previous turn made progress by committing and cloud-verifying Cycle 173 at
`c6d2ecb`. This cycle resumes the native production path, not the cloud-only task.

All five CPU-profile validators now require their embedded `build.kernel_entry`
receipt to match the current independently validated PKENTRY1 receipt, including
source and build evidence. Equal canonical image bytes alone are insufficient.
The shared `runtime/native_kernel_profile_evidence.py` check compares JSON-typed
identity, rejecting Python bool/integer and float/integer equality substitutions.
Each profile binds this helper, its tests and the current entry receipt.

Four new test methods cover 80 malformed, stale and numeric-type substitutions
across the five profiles, 20 invalid current-dependency cases, positive synthetic
validator inputs and source-binding coverage. Synthetic inputs are not execution
receipts. Native Rust, canonical kernel, boot behavior and physical hardware are
unchanged; this is a qualification-validator repair and real profile replay.
The broader `ADD-N36-RECEIPT-COVERAGE-001` requirement and flag remain open.

## Executed Evidence

Five qualifiers produce fourteen successful fresh QEMU/OVMF runs and 225 negative
control groups. Each rebuild validates 243 kernel host tests and source-current
PKENTRY1 evidence. One expected TCG exception-limitation probe is counted separately.
All 1,532 observed files, including the new helper and tests, and the owner's
PooleGlyph report remained unchanged during each bounded run.

| Profile | Successful Runs | Controls | Receipt SHA-256 |
| --- | --- | --- | --- |
| PKTRAP1 | 6 | 51 | `8C14786643F1423656AD20D733A1F339CC7036BEB0957CF2945C605DCD40648F` |
| PKCPU1 | 2 | 41 | `F3A67A26D0E749921A1F3AAC6B924C6B74BF71564DBDA2B292B8B844718C0285` |
| PKXSTATE1 | 2 | 43 | `9D66DD4EC4AC145A6639D6A0C50179D112D9221CE8B5224851DB5645CFD3BFE0` |
| PKXEXC1 | 2 | 43 | `CE34466E452D16847F6773764BF55733F0F0C25601E4F37C36B7F13101B916C7` |
| PKMSR1 | 2 | 47 | `AE0AC3771B7C8C749CF2F0AA1700FF35753973F2494A1B34342CB60A96B18632` |

Receipts are exact copies of qualifier output, not edited replacements for runs.
The trap profile checks returning exceptions, terminal double fault and synthetic
malformed-frame rejection. CPU policy is read-only. Xstate retains its bounded
x87/SSE ownership exercise. The two WHPX exception runs each deliver three
exceptions, recover twice and reject the unexpected eager-policy fault. MSR policy
retains eleven support-gated reads with zero MSR writes. Linked exception/MSR
scope audits pass. These are virtualized single-host profiles, not physical-target
or independent-builder qualification.

The 47-test focused CPU, errata, release-boundary and new provenance suite passes.
Log SHA-256: `E2FDC8F1C7AF7331FFDA9A8627ED6780135D0BD3C0EC3A6AE562238EC1136984`.
The core Cycle 172 receipt still validates and all seventeen stage-log hashes match.

## Failure History

The initial provenance test had 70 missing diagnostic expectations: 53 mutated
records were accepted without errors; the rest already had schema errors but no
embedded-entry check. Initial log:
`817F5DBB0F30FE4F7DAEACDE52B8BBEE96DD197978D4AA0101F727AA1547F78F`.

The first repair used dictionary equality and admitted ten numeric-type
substitutions. Those failed tests are retained under log:
`C4DCA67B5449F16171225F92DAE6A2200C146ADAFA3BD0ADAABC7E7D41FE244C`.
JSON-typed comparison repairs the defect; all four new methods pass, log:
`3E7F6DC31416752E175BF8FFD34D9DCDB85BBBB7AA6BEBBBA5A5AF84229CE5CC`.
Earlier Cycle 172's failed full audit and all Cycle 173 history remain preserved.
No failure or source-freshness requirement was waived.

## Remaining Work

The selected native projection passes 24/27. Physical memory, virtual memory and
SMP IPI reject stale evidence. All fourteen older memory/IRQ/SMP/scheduler/atomic/
lock receipts retain their earlier execution cycles; embedded entry provenance
must be replayed even where a narrower selected check passes. Complete transitive
input coverage and independent evidence validation are still required.

The inventory contains 954 Python tests and 237 architecture bindings; discovery
and binding counts are not executed full-suite qualification. All 8,996 checklist
requirements, 57 additions, 40 phases, 301 subphases, 94 flags (35 open), 20 gaps,
phase/flag statuses and exit contracts are preserved. PooleGlyph Phase 65 ZIP,
manifest and owner-modified report are unchanged; Phase 66 Core IR remains next.

N0 custody, native task-stack mapping/context activation, general CPU retirement,
all production CPU/exception/isolation contracts and the signed ISO remain open.
No keys, signatures, firmware, drivers, physical media, frozen demo update,
phase closure, main merge, release or production promotion occurs here.

Next: `N9-PMM-ACPI-CONSUMER-001`, then dependency-ordered VM/IRQ/SMP/scheduler
replay, exact full canonical qualification and publication/review gates. PR #77
remains draft; main remains qualified Cycle 171 at `8006c7b`. The goal is active.
