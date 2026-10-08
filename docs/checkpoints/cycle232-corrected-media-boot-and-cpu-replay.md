# Cycle 232: Corrected Media Boot And CPU Replay

Date: 2026-10-07. Pre-production, single-host bounded evidence.
Selected move: N5.1/N5.8, `N5-FAT32-PARENT-001`, existing requirement
`ADD-N5-FAT32-PARENT-001` and open flag. Dependent N7 profiles replay on the
corrected media without changing the native kernel or EFI executable products.

## Fresh Qualification

| Profile | Successful Guest Runs | Control Groups | Seconds | Receipt SHA-256 |
| --- | ---: | ---: | ---: | --- |
| Revalidation | 0 | 36 | 25.938 | `5DB8426D14B81635427FECB0EE49B8D163C3EC3152808146D47EEA73784B7AF9` |
| Transfer | 2 | 58 | 73.906 | `C7D5317A580F02373D29E9CCFEB7914BE2F296B929E4F7A0A08C3BC1DC8B5528` |
| Traps | 6 | 51 | 105.407 | `1E50D5BF5314BE0ED6126440B845E1E6BA2C1691959EA393C158AB87E6F7DF69` |
| CPU policy | 2 | 41 | 66.657 | `33D84A43ABAB2632A2B95EDF8A5B5BE9C92159BD96316A1E6EEC8FDCC5994C5B` |
| Xstate policy | 2 | 43 | 76.031 | `788E6512D38C85FE664695F62EBBE8F89FFF81C273B2C18C1FE5532EBFF7DF6D` |
| Xstate exceptions | 2 | 43 | 79.187 | `C4A2D365C751964656BD13E867DCACC81E68AE2B848F1917CE7E29D893AD8A92` |
| Privilege/MSR | 2 | 47 | 76.844 | `3A2ABCC61F7F2A5B8EC6DAEC130F17656021DE45A10583D92A6C693494282694` |

Total: 16 successful fresh guest runs, 319 control groups. Revalidation also
passes 246 kernel host tests and 32,768 Rust/Python differential cases. Transfer
has 30 exact markers, including live PooleKernel entry and retained-file
revalidation ending in unsigned-policy denial. Every admitted report comes from
a terminal successful command with unchanged original source/owner snapshots.
Original process-capture and log hashes are recorded per profile in the roadmap.
Predecessor bytes remain in parent Git and local `outputs/cycle232-prior-*.json`.

The trap profile executes three paired scenarios. Two xstate-exception runs use
WHPX and each records three deliveries, two recoveries and terminal test-only
#NM rejection. One separate expected TCG non-delivery probe is not counted as a
successful exception run. Privilege/MSR observation records 11 reads and ten
global MCA banks, without hardware-state activation. These do not establish
general exception delivery, AVX, production scheduling or physical qualification.

## Regression And Reconstruction

Focused regression: 77/77 pass, zero skips, 176.173s (177.078s runner).
Includes revalidation, transfer, five CPU profiles, current-entry provenance,
malformed recorded controls/runs, terminal-capture failure paths and FAT32
directory links. Source and owner snapshots remain unchanged. Log SHA-256:
`E57E6A9702BEC9A59D0D790BB1ABFAFCA2B284EE638650979160E45C24389A87`.
This is not the full canonical or complete historical-roadmap suite.

The broader architecture/roadmap regression ran 71 tests with 17 failures and
zero skips, in 23.766s (24.578s runner), with unchanged source and owner snapshots.
Failures include stale downstream/source bindings and old historical assertions
against newly refreshed current records. Log SHA-256:
`3E4D7FE6CC49B192EFB7B04B08C43C2F9309BED438BB11F9E542C5D9423D3165`.
These failures remain merge blockers; the focused pass does not supersede them.

The first conservation check detected the generator changing Cycle 231's historical
test inventory from 1,233 to the current 1,234. Freeze the historical count at
1,233 and directly regress that invariant. The current count remains 1,234;
neither inventory count represents successful test execution. No runtime or
qualification guard was relaxed.

An additional structured receipt-delta diagnostic initially asserted that every
execution field would remain identical. The xstate exception receipt disproved
that assumption: its expected TCG limitation debug-console hash differs. The
diagnostic was corrected to record differences rather than require equality.
Host revalidation-probe and two disassembly-text hashes also differ and are
retained. No qualifier, validator or native code was relaxed or changed.
All recorded negative-control results are unchanged. Native kernel and EFI
product identities remain equal; this does not assert all host-tool output is
reproducible. Deterministic summary-log equality is not freshness evidence:
original process captures and exact source snapshots supply that binding.

## Current Gaps

Component admission passes 22/27. Physical memory, virtual memory, SMP IPI,
atomics and locks reject stale dependency bindings. Component admission alone
does not prove freshness: source-current execution coverage is 13/27, comprising
four unaffected profiles, two Cycle 231 captures and seven new captures.

Fourteen source profiles require replay: physical memory, virtual memory,
interrupt/time, first AP, per-CPU runtime, SMP IPI, scheduler, preemption,
deferred work, SMP scheduler, AP workers, SMP preemption, atomics and locks.
Historical dependency and ownership groups are explicitly marked not current;
their old records are archived without changing historical results.

`runs/native_execution_sources.json` remains byte-identical to the original
aggregate and correctly fails on the changed loader receipt. Do not refresh its
hashes from old runs. Rebuild it only from real successful captures after all
affected profiles replay. Full-candidate qualification and historical receipt
assertion reconciliation remain pending; the passing focused suite does not
erase Cycle 231's broad-suite failures or establish a new broad-suite pass.

Exit: all affected profile captures current, then exact-candidate canonical
runtime/bundle/replay, publication and GitHub/review gates before PR #80 merge.
Next exact move: physical-memory replay, then virtual memory, under the same
N5 FAT32 requirement before proceeding through IRQ/SMP and scheduler dependencies.

## Preservation

Main remains `bb5e43c3e655db5b8c5676572135471bfd843880`, qualified through
Cycle 230. The active draft branch is based on Cycle 231 `dc5d74a`; updated source
and checkpoints are eligible for cloud backup, not production promotion. The
owner requested main integration where eligible and cloud preservation. PRs #78
and #79 are already merged; PR #80 must remain draft until the stated gates pass.
Pushing this branch preserves its tracked source, receipts and checkpoint without
claiming a merge. Ignored raw logs, toolchains and local ISO output are not part
of that Git backup.

The kernel remains `FD6C2A0C709957B9EDFFC0647D534E060ED68215C075F07D70AB2AEBCA6C81D1`.
The retained demo ISO remains `3533965B0DFEA0BFC55399929A9770979B50E4077E77201A68B8331D76570378`.
It has not been rebuilt and retains its previously documented defects.
All 8,996 original requirements, 59 additions, 96 flags/41 open and normative
charter requirements are preserved. No phase or flag closes.

PooleGlyph Phase 65 remains newest; the manifest and ZIP hashes match the
preceding checkpoint. The owner's dirty report remains
`F75E4836FAA9DDD59BA62648FE9542415F2119B659A583FB3F5959F2F5CAE87B`.
No language/ABI migration or Phase 66 promotion occurs. Native custody, signed
trust, independent builders, physical validation and the remaining N0-N39 work
remain open. No physical media, firmware, keys, signing or release were used.
