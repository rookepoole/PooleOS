# Cycle264: Native Console IPC

2026-10-11. Build Plan2.167.0, N13-CAPABILITY-IPC-001, USI-3 partial.
Prior progress: Cycle263 separate IPC program builds committed as6543f0f.
This cycle implements native four-process execution, not a boot-screen redesign.
The usable user-space ISO is still the intermediate objective; complete robust
microkernel development and the full Production Goal Charter continue afterward.

## Implementation And Invariants

PSESSION3 starts four independently compiled programs in private CPL3 roots:
PooleInit1073, PooleCounter1113, PooleConsoleService3032 and PooleConsoleClient1813
code bytes. Their Cycle263 bytes remain unchanged. Admission failure-atomically
installs four owned endpoints, four send grants and one exclusive COM2 capability.
Only the service owns the device. Exact handle/root/generation checks precede
dispatch; fixed kernel identity,205/208 image pages and36-page stack are unchanged.

Task images own52 pages. The first native attempt demonstrated that retained ACPI
snapshot pages also charge this allocator. The repaired profile reserves at most12
firmware pages separately (64 total quota), verifies the post-snapshot charge and
retains the52-page task bound. Actual guests use one firmware page. This is a
bounded accounting correction, not permission for arbitrary image/stack growth.

Four new host tests cover explicit pair isolation/device exclusivity, pressure and
queued acknowledgement ownership after sender retirement, failure-atomic generation
exhaustion, and duplicate/stale identity rejection. The old three-task console
and ordinary default profiles remain separate. No kernel shell or service-policy
implementation was substituted for user programs. NI1-NI7 are recorded in
[the console IPC contract](../native-console-ipc.md).

## Native Evidence

Public receipt: `runs/native-console-ipc-readiness.json`, SHA256:
`AD5BBAF2354CFB90F2FA1ABDF337C7DC76AA06006B407E0712FD125E05EC4101`.
It binds830 console-profile and823 default-regression source files, plus the
unchanged27-source Cycle263 program receipt. Two independent native kernel builds
match exactly, including linked bytes. Canonical IPC kernel SHA256:
`60B321B36692FCA9679F419F9868ED2CFA9E2F93D7ECDCB2EE6839CAAD2B6594`.
Wrong-peer kernel SHA256:
`39D99358EDDCF58FC37C31B910DCD4930417ECC025E2619D001694E31C428915`.
Each is763400 bytes,205 image pages. All four actual program blobs occur exactly
once in each canonical kernel; receipt records also bind linked executable hashes.

Three fresh QEMU/OVMF guests use read-only virtual media, fresh variables, loopback
console/QMP and no guest network, hardware acceleration or device passthrough.
The host waits for actual service progress, sends at most8-byte chunks paced by
exact echo, and sends EOT only after echo and at least256 dispatches.

| Guest | Input/Application Output | Result At512 Dispatches |
| --- | --- | --- |
| IPC1 | 45/45 exact bytes | Service/client exit0;26 pages reaped; init/counter survive |
| IPC2 | 52/52 distinct exact bytes | Service/client exit0;26 pages reaped; init/counter survive |
| Wrong expected peer | 0/0 | Service exit152;13 pages reaped; client still polling; init/counter survive |

The positive inputs include binary and log-like bytes. UART data cannot qualify
kernel observations. Independently cross-checked serial/debugcon markers, boot
prefix, media and retained handoff data establish execution. The marker oracle
rejects64/64/60 hostile mutations; four roots, exact accounting, frozen reaped-task
counters and independent peer progress are checked. These runs observed syscall
budget yields, not timer preemption. Native PCS1 pressure/malformed-request controls
remain; host state-machine/queue tests do not replace them.

Final console capture69.407s, unchanged source/owner snapshots, log SHA256:
`4B3D278F41EB2B6988F0859F2858EC6C623FFAC4C038BD183574FA58B3F54008`.
All23 default regression checks pass (1706 Rust test executions across overlapping
profiles and105 Python oracle tests), including two79-marker containment guests
with17 survival cases and1111 hostile controls each, plus ordinary unsigned-boot
denial. Default capture399.344s, unchanged source/owner snapshots, log:
`C70B13C8FBA7B81519B455479085AEDAA8125C37193DBECECDED4725CE51020A`.
This is scoped native regression, not the full exact-candidate canonical suite.

Console-feature kernel host tests pass481 debug and481 release; release capture
16.235s, log `F5B2A32935806365D4EA480FC5FC71F6E6E8114C4FC7B790FF8209092725B9B3`.
Thirty-six focused Python tests pass; the final default regression additionally
replays the six new oracle tests after their hermetic-environment repair.
The corrected metadata suite passes210 tests in51.541s (capture52.547s), log
`7F759096E0012B16F21B6FA3C6F8F9122AE727DD5410FE9EE421B8BA8565D4ED`.
Conservation passes146 tests in9.092s (capture10.563s), log
`FC6FE4B138FD06F6DC9759A0D0A83C5B2FB07F7A1985CFD29AD9C096A676609D`.
Both captures preserve source/owner snapshots and precede this result-recording
edit. Overlapping counts are not unique-test totals or production qualification.
Final staged-artifact evidence is recorded separately in the PR/local handoff to
avoid self-rebinding the checkpoint.

## Retained Failures And Repairs

- Native attempt1 rejected unused three-task bootstrap imports under the new
  four-task feature. Narrow cfg/import selection repaired it without relaxing
  warnings.12.766s; log `2C9BCF418F337D459F782FB51F62B4D44C5EC78D1DC3D018BD7B10C17A39F2AF`.
- Native attempt2 denied fourth-image construction at stage20104 before dispatch:
  52 total pages omitted retained ACPI ownership. The bounded52+12 accounting repair
  above resolves it.49.64s; log `A582546F04ED91CA0B1B2743ABC8C38FCB6A29B8DF05D566E40951F8C1E456B5`.
- Native attempts3/4 passed but were superseded after explicit new-file bindings
  and the oracle-test repair. Attempt5 binds the final sources; no old receipt was
  relabeled as a new execution.
- Default attempt1 passed481 console tests but the harness still expected477.
  Updated the expected count to include the four new admission tests.61.5s; log
  `0C0543F6FF32BA14EFB0F0D8211ED3E2673C1CEE51564A88963FA8DC24DF18D5`.
- Default attempt2's new source-binding test tried Git in the intentionally scrubbed
  compiler PATH. Mocking an empty Git inventory proves explicit new-file bindings
  and removes the incidental test dependency without broadening PATH.74.625s;
  log `C88DFD1F3E9E8C980AAFE083878AD0F1656472616F84F60DB01CE2F3348545DB`.
- A documentation patch context mismatch made no changes; exact reread/reapplication
  repaired it. No test or native evidence was discarded for this editing failure.
- Metadata attempt1 passed209 of210 tests; a historical-receipt inventory assertion
  omitted the newly added admission-test file (105 current Rust source files, not104;
  the old79-input receipt remains frozen). The exact difference set/count was updated.
  Capture53.14s; log `2CCEC8440E248E393F5F95F65A1F733BE1608FC9BC8E03B554F2734EE23CA09A`.

## Continuity And Limits

Console qualification now performs512MiB free-space preflight before output/build
creation. It is an observation, not a reservation.29 explicit cycle-owned generated
build/media objects were archived to the designated evidence volume; all member
paths/counts/SHA256 values were verified before literal-path removal. Raw failures,
logs, receipts and standalone binaries remain. Broader build-space protection and
reproducible restoration stay open under FLAG-N36-EVIDENCE-STORAGE-001.

PooleGlyph remains Phase65 with Core IR boundary audit next; live checkpoint and
owner report are untouched. Master checklist, execution-source ledger and old
user-entry/program/session/console receipts stay byte-identical. Inventory1365
Python tests and595 architecture bindings is not suite execution.40 phases301
subphases8996 requirements59 additions98 flags43 open20 gap groups are conserved.
No phase/flag closes, no merge/tag/release/signing or hardware mutation occurred.

## Next

Repair the observed polling peer-death gap with authenticated bounded notification
or recovery, then prove native pressure/malformed-request and death paths. Review
capacity/resource/lifecycle admission: the four-slot bootstrap cannot host the five
minimum roles (init, console, shell, two usable apps). Implement actual shell,
read-only bundled files, application start/stop/fault interaction and fresh optical
ISO acceptance. No scripted transcript or kernel command interpreter substitutes.
General user supervision/restarts/loading/trust, efficient idle, clock recovery,
signed activation, full robust microkernel, PDC/PooleGlyph and accessible PooleGlass
remain. Three known kernel-load/transfer readiness failures and full canonical gates
still block main; PR81 remains a development checkpoint, not production promotion.
