# Cycle 231: FAT32 Directory Links

Date: 2026-10-07. Native PooleOS, pre-production. Selected move:
`N5-FAT32-PARENT-001`, existing `ADD-N5-FAT32-PARENT-001` and open
`FLAG-N5-FAT32-PARENT-001`. Deliverable: correct bounded EFI FAT32 directory
encoding and independent rejection tests, followed by source-bound boot replay.
No phase or flag is closed. This is media tooling, not new kernel execution.

## Main And Cloud Baseline

Checkpoints through Cycle 230 are merged via
[PR #79](https://github.com/rookepoole/PooleOS/pull/79).
Exact candidate `ea61a79e2ded5b00710f33334522868af0650736` passed 106/106
canonical and 708/708 Doctor checks with runtime, bundle and replay in 1099.250s.
All 1,641 tracked files and the owner report were unchanged during execution.
The unittest command passed; individual pass counts were not retained. The
1,227 discovered tests are inventory, not a reported successful test count.

Fresh draft/ready preflights checked publication evidence, branch protection,
clean mergeability, reviews and review threads. No protection was bypassed or
weakened. Squash merge at 2026-10-07T22:09:25Z produced main
`bb5e43c3e655db5b8c5676572135471bfd843880`; its tree
`0334a2a845c40868c88a6025b0f7ed0023d9aa02` equals the qualified source tree.
The source branch is retained. This pass does not qualify subsequent N5 edits.

Canonical report SHA-256:
`03BBCC4E3712D025A199CC09D49E60EDAD893016C36C7294A551D7FAFD94AAA3`.
Canonical log SHA-256:
`D762E6D322E8E84451ACD0140C51C80AB1A3E7EDBBBC6FDF580216121D0AC7DC`.
Detailed merge closeout:
[PR evidence](https://github.com/rookepoole/PooleOS/pull/79#issuecomment-6047835367).
Tracked checkpoints/source are cloud-backed; ignored raw logs, tool trees and
local ISO files are not automatically uploaded by Git.

## Implementation And Negative Evidence

The writer previously encoded EFI/.. as root cluster 2. It now writes zero.
The bare inspector checks all four dot entries: physical slot order, short
names, directory attributes, zero sizes and exact self/parent cluster values.
The extended loader inspector already compares reconstructed media exactly;
it inherits the corrected writer without a separate source edit.

[Microsoft FAT specification](https://www.scs.stanford.edu/~zyedidia/docs/_other/fat.pdf)
sections 6.5/6.6 specify directory dot links and the special root-parent encoding.
This is bounded profile evidence, not a claim of complete FAT conformance.

Five new test methods cover independent valid inventory, deterministic output,
17 bad field cases, four bad slot arrangements and extended load media. Before
the repair, the red run had 24 failing assertions/subtests across five methods.
Red log: `07D130745A0EF68A8465C85846450E45772B2549D870ED220657DD18F4017861`.

The first real loader qualifier attempt failed after 148.297s: the newly added
loop reused `name`, replacing the ESP label with bytes and breaking JSON output.
No successful receipt was admitted. Renaming the loop variables and adding
label/JSON assertions fixed it. Failed log:
`CA338C10FCEC488B06953A091C84BF5C35C7E758B7D9637732D194E10104759E`.

Final focused suite: 26/26 pass, zero skips, 9.453s (10.375s runner). Source and
owner report unchanged during execution. Log:
`B9A905ADDABEA6E77B350704D752D13809CA8BDB48A648475DD7AF39257ADF66`.
The synthetic 64 MiB fixture differs from its recorded old hash by one byte at
offset 2082362, from 2 to 0. Reversing that byte in memory reproduces the old hash.
This is a fixture-only delta, not a claim about every generated ISO.

## Fresh Native Receipts

Loader: 332/332 host tests, two guest runs, 25 markers, 155/155 negative controls,
101.610s. Receipt `runs/native_kernel_load_readiness.json` SHA:
`D8285B4D2395D6F7A84E955752C2AEDA1FE705CF6EF4AB72BBAE6B2C7BB59A9F`.
Log: `CC1FBEAB3FC5A0A5A76A3484B496A2DE75EABE264CBA137E4D02C21421E34E9B`.
Original capture: `0DD8C995911733AF63D46674728A8AE242AEFE3F4ACDF61ACEB1634FD04FF8CF`.

PooleBoot: 8/8 report host tests, two clean builds/media, two guest runs, 25 markers,
155/155 controls, 96.797s. Receipt `runs/native_pooleboot_readiness.json` SHA:
`6EF67ABC56F0E71E69E8796DB8D12781CDA24CF3B097D5E4F1097AC0E659AB0A`.
Log: `56338F6E2175B97E50BB1E2377476252F07B88CAAEAF64E220040A84FE086C65`.
Original capture: `A463E02C843CBE916CE2266A8219742CC8478DF413BCDD7030A3F2279E4AA986`.

Both successful captures terminated with unchanged source/owner snapshots and
passed admission. Predecessor receipt bytes remain in parent Git and local
`outputs/cycle231-prior-*` copies. Generated media SHA:
`C45A2136EA999C11FCB94651278E4BCF0A6B276F69BEB2DD683852940A1FAFC2`.
All 12 native payload records and EFI bytes match the preceding receipts.
EFI SHA: `0EC539F673AFF331AF7863ECF5D2A437438FF6B8172AEE168EEECEECB0CFA9FB`.
There are four successful fresh guest runs; the failed attempt is not counted.
These profiles stop before kernel transfer and preserve unsigned-trust denial,
zero authority/state writes, `n5_exit=false` and `production_ready=false`.

## Remaining Work And Preservation

Measured component checks pass 20/27. Transfer, trap, CPU policy, privilege/MSR,
SMP IPI, atomics and locks checks fail due to changed dependency bindings.
That component projection is not execution freshness: only 6/27 profiles are
source-current (four unaffected plus the two freshly qualified profiles).

Twenty-one profiles require real replay in dependency order: revalidation,
transfer, trap, CPU policy, xstate policy/exception, privilege/MSR, physical and
virtual memory, interrupt/time, first AP, per-CPU runtime, SMP IPI, scheduler,
preemption, deferred work, SMP scheduler, AP workers, SMP preemption, atomics,
and locks. Preserve the original aggregate execution-source record until real
captures are available; it currently rejects the changed loader receipt.
No rehashing of old captures into current claims is permitted.

Broader regression (all FAT, ISO, architecture-baseline and roadmap tests) ran
94 tests in 27.971s, with 17 failing assertions/subtests and zero skips. Failures
retain stale dependency, aggregate-capture and prior-receipt binding checks.
Log: `03FB3E5408DBE8A2A60E0DCA34FC71172E78C86E88FA0D16DBD0C552A6EFE8B0`.
The initial broader run also exposed outdated projection expectations; those
metadata assertions now reflect measured partial progress, without relaxing the
execution guards. Initial log:
`45D274BF407B12A0DDAC8DF9F2DDDDFE20D84747DF558B5F6A0FCEF8500010E1`.
The broad suite is not green, and is not superseded by focused metadata testing.

Exit gate: all affected source profiles replayed and aggregate guard current,
then exact-candidate canonical/runtime/bundle/replay, publication and GitHub
checks before main merge. Current repair branch may be backed up as a draft.
Next exact move: revalidation, then transfer under `N5-FAT32-PARENT-001`.

All 8,996 original requirements, 59 additions, 96 flags/41 open, 40 phases and
301 subphases are retained. Original checklist SHA:
`A8C94719FAF9428C1F133010BA2603C0270C4E1EFD7327AF8EAB9C8C362ABB3D`.
PooleGlyph Phase 65 remains the newest checkpoint; Phase 66 is not qualified.
The owner-dirty report is preserved at SHA:
`F75E4836FAA9DDD59BA62648FE9542415F2119B659A583FB3F5959F2F5CAE87B`.
Native kernel remains `FD6C2A0C709957B9EDFFC0647D534E060ED68215C075F07D70AB2AEBCA6C81D1`.
Retained demo ISO remains `3533965B0DFEA0BFC55399929A9770979B50E4077E77201A68B8331D76570378`:
its older writer defect and four missing production objects are not repaired by
changing today's host writer. No keys, firmware, physical media or release
publication were used. Native custody/authentication, independent builders,
physical qualification and remaining N0-N39 work stay open.
