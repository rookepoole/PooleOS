# Cycle 227: Errata Recorded Admission

Date: 2026-10-07. N36.1 / `N36-RECEIPT-COVERAGE-001`.

## Late Full Qualification Failure

The exact committed precloseout candidate `79adf4aa452daf36f52e24b99c176c49b2523935`,
tree `d63edf6d0fd4a1490dba0497a0cfe2379d692df2`, ran the canonical gate with runtime,
bundle and replay inputs. It completed in 1,089.266s with exit 1: 105/106 canonical
checks and 707/708 Doctor checks passed. The failing Doctor check is
`pooleos:unittest` (exit 1). This is not a timeout. The outer report drops the
individual test failure details; their count and cause remain undiagnosed.
All 1,632 tracked source files and the owner's PooleGlyph report were unchanged.
Log SHA-256 `7DFDB6EFFAF983852F69D9A2FCE89E16FC6800455D4DCE1299F4CEC7953D3F21`;
report SHA-256 `E65E0CCEEEF63D7C8E8C6E0F6F2BD0E65807D88DF14E76F253664261C8A75FE4`.
Later progress-only edits are not covered by that exact-source execution.

Immediate next move: retain full unittest diagnostics, repair the failure, finish
the dependency review and rerun the exact-candidate gates. Do not merge this draft
while the full suite fails. The development checkpoint is already backed up on
GitHub; this failure does not invalidate the separately recorded scoped passes.

Additional admission-side observation covers 2,287 non-Python reads across 320
repository paths with zero drift from original execution snapshots. The 330 reads
without direct explicit pairs need transitive interpretation, not a missing-file
claim. Existing pins for four Rust executables, two target-library trees, all
3,368 QEMU runtime files and firmware, and four MSVC/SDK trees match. No subprocess
was launched by this pin check. These checks do not prove complete compiler/host
closure or reconstruct historical tool snapshots. Report digests are retained in
the machine roadmap. No native bytes, phase status or production claim changed.

## Scoped Repair
Existing `ADD-N36-RECEIPT-COVERAGE-001`.
Parent: `14513f4d247a61fe184675c523f0e2b5d05f4cbb`.
Previous cycle: progress, not an owner-action impasse. The full native goal stays
active. Main merge remains conditional on the remaining qualification gates.

## Repair

`runtime/native_kernel_errata_policy.py` now reconstructs all recorded fields,
requiring exact JSON types and canonical valid dates. It verifies the current
input bindings, lock-derived compiler version, build counts, no-I/O source audit,
all sixteen unique ordered registry records, zero-authority current and synthetic
decisions, independently reconstructed vector outcomes, each ordered control,
summary, claims, open items and non-claims. Booleans do not substitute for integers;
empty/missing/extra/ill-typed sections, nonfinite numbers and cyclic component
inputs reject. The underlying target policy and native evaluator are unchanged.

The schema explicitly requires the nested evidence fields and boolean boundaries.
The aggregate gate stops on component errors and independently enforces exact
integer summary counts and boolean claims. Contract equality is also JSON-typed.
The toolchain lock already consumed by the qualifier, plus the new adversarial
test source, now appear in implementation bindings. Open-item text is shared with
the qualifier, without changing its twelve requirements. No arbitrary receipt
hash is accepted as a substitute for semantic reconstruction.

## Preserved Counterevidence

The original eight counterexamples are preserved in Cycle 226 and all now reject.
A wider pre-repair audit ran against that genuine receipt before validator edits:

| Path | Mutations | Invalid Accepted | Exceptions |
| --- | ---: | ---: | ---: |
| Component, before | 1,708 | 1,085 | 54 |
| Aggregate, before | 1,708 | 1,015 | 165 |
| Component, after | 1,742 | 0 | 0 |
| Aggregate, after | 1,742 | 0 | 0 |

Both genuine receipts passed their contemporaneous validators. The same recursive
mutation generator exercises omissions, shape changes, reordered arrays, added
fields and typed scalar substitutions. Two new bound-input records add 34 cases.
The after-audit mutates the genuinely requalified current receipt, not stale
evidence with hashes rewritten to manufacture a positive control. This is a finite
corpus, not proof against every possible malformed input or validator fault.

Before report: `5A3B216F91770E31B7C7F475F17537797452778106C2FF5E6E67754DED3349C8`.
Before log: `0A44FE5566E80C69BC43CCCA050E7602126FD9281847930FDC7C89A11D4D1A37`, 20.453s.
After report: `50F2B0C86748F5D7444BE1E50007E195A7B5A7ACB89B1BBCDCED6A27B186D6C9`.
After log: `EE617BFD6FD5872350DC9AE9AB57E47F1560AEB29586D33C322AF5323BF38EE4`, 21.672s.
Audit script: `7A76965746399414038839E081D1E63CE2D6643C399183F497422E9C32882469`.

## Fresh Qualification

The bounded errata qualifier passed in 10.937s with unchanged source/owner
snapshots: six Rust host tests, two no_std builds, 128 cross-language vectors and
24 controls. It still denies the target for all six frozen reasons. Registry
access was read-only and unprivileged; no MSR, privileged probe, driver, firmware
or physical-media operation occurred. Zero QEMU boots were needed.

Current receipt: `975C57DDFB54EDB9C1573D2A1B5ABD5B2242996B7FE32028740780A22319ABD8`.
Qualification log: `8DC57B55A31EC23061832E2377C460920D370AF0A1F1A7F90F0840FBCAD8C0E5`.
The log contains the same summary text as the earlier run; its identical hash is
not the provenance proof. The distinct real execution capture binds the changed
source snapshot and exact output. Only `inputs` differs in the readiness JSON.

Only the errata entry in `runs/native_execution_sources.json` is replaced from
that real capture. The other 26 source records and receipts are unchanged.
Current source record: `6DF3A8CBD4F56CC4CB3A3D7FB232C0B7C8EEBE0D647AFB7F2587358DC319D409`.
All 27 selected profiles and 78 distinct Python inputs remain covered.
`tests/fixtures/cycle226-errata-readiness.json` preserves the old receipt at
`9C25E26A8C53AF2A908DE41F51887E15AC7571C7C79EDF1318BAC13539F489B0`.
`tests/fixtures/cycle226-execution-sources.json` preserves the old source record at
`B67E6FEB381D0799182F88378A455B31C4718E8404B5B12B12CF9D1AA06AF7DD`.

## Regression And Boundaries

Focused suite: 34/34 tests pass, zero skips, 52.752s (runner 53.609s), with source
and owner snapshots unchanged. Log:
`201AD2F586C1448CACFA24B5E0AC20B1E917FFE757FFC3B740FC7075AA33C84D`.
The suite includes the 1,742 corruption cases, original eight counterexamples,
date boundaries, stale evidence, lock changes, nonfinite/cyclic inputs, typed
contract mutations and vector/control reconstruction. Two disabled admission
variants and two disabled qualifier-control variants are detected; one independent
aggregate integer-guard test survives a disabled component validator. These are
host-side controls, not disabled native safeguards or hardware fault injection.

Combined regression passes 126/126 without skips, 225.293s (runner 229.390s),
including 74 metadata tests and the focused suite. Source and owner are unchanged.
Log: `EC2A1761ABF628C3226A1A143E4D2ABB5D140E76E3B32646347AD24DBF6C8996`.
Counts overlap and are not a full canonical pass. Conservation passes 393 source
bindings, 1,192 discovered tests, 29 unchanged archived parent records and 802
unchanged native/receipt/historical files. All 27 selected consistency checks and
the separate source guard pass; this does not close N36 or qualify main merge.

An additional explicit-binding inventory examines all 27 receipts and confirms
their original capture hashes. It finds 2,855 non-Python path/hash pairs: 2,392
repository pairs covering 292 unique paths match current bytes and the original
source snapshots. Another 462 pairs name 19 logical EFI-media paths, not missing
repository files; the single `$RUST_TOOLCHAIN` token resolves to the separately
hash-verified atomic disassembler. No explicit pair remains unclassified.
This does not prove that every actual file read or tool invocation is represented;
logical media bytes were not independently rebuilt by this inventory.
Inventory: `53D3F63D3421664BF5BC7EB0FC06A1B96BFA797DE0758441A6784A1C9C725B99`.
Classification: `7D7D64AE801FBACE84AC3D13D04A7261B43E514CE2ECDEAC1E173A16446BD557`.
Next review should address dependencies absent from explicit pairs, not repeat
these already-accounted repository comparisons or mistake volume paths for files.

No native kernel, demo ISO, PooleGlyph boundary, owner data, phase/flag status or
normative charter completion condition changes. Source-available IP boundaries
remain intact. No signing, keys, tags, releases or production promotion occurred.
N0 custody, N5 authentication, complete native task state, hardware qualification,
independent builders and the signed production ISO remain open.

Exact next move: continue `N36-RECEIPT-COVERAGE-001` by retaining complete unittest
failure diagnostics and repairing the failed suite. Finish the non-Python data and
tool review, then run full exact-candidate canonical/Doctor/release/
publication/GitHub/review gates before main merge. Do not repeat unaffected boots
by default. Recorded consistency is not authentication, fresh native hardware
measurement or production qualification. No new owner authorization is needed.
