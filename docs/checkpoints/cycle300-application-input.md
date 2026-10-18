# Cycle300: Isolated Application Input

Started: 2026-10-17. Status: qualified development increment; production remains partial. Parent:
`257abf2affd5139874e7c6cd60d33c7fffe2fc2c`, Cycle299.
The previous goal turn made progress: native surface lifecycle, full guest
qualification, corrected roadmap summaries, exact final audit and cloud push.

## Selected Work

Make the existing isolated application windows directly interactive. Reuse their
kernel-authenticated PWS1 endpoint and existing bounded request/reply slots;
do not grant device access or add a kernel input-policy syscall. An explicit
interactive service/application profile preserves the ordinary four-page apps
and the seven-page window-service ceiling. Start with bounded in-memory text
editing and direct numeric input using the existing application computations;
persistent storage and a complete editor remain separate production work.

Alternatives considered: direct device grants break service isolation; kernel
window routing puts UI policy in the wrong layer; shell-mediated keystrokes tie
focus to shell job authority; a new unsolicited IPC event queue adds kernel
capacity/acknowledgement policy; client polling through the already-owned surface
channel keeps one surface request outstanding and preserves current quotas.
Select the last option, with explicit queue overflow and focus-loss semantics.

## Acceptance Invariants

- AI1: input is selected only by trusted focus plus exact admitted surface
  identity. Kernel-attested sender generation, handle and next sequence must all
  match before a client can drain its own queue; no cross-client reads.
- AI2: two fixed queues, bounded device draining and bounded RPC batches. No
  allocation, new process/device authority, unbounded per-call retry or extra outstanding
  file/surface request. Backpressure cannot reapply or retarget a committed reply.
- AI3: retirement/replacement clears queued input. Focus loss drops unclaimed
  bytes with cancellation rather than silently executing a truncated command.
  Held keys/modifiers are fenced until release across focus/lifetime changes.
- AI4: overflow/reset cancels an affected draft and discards through a delimiter;
  cancellation is owner-bound and cannot migrate into Terminal or another app.
- AI5: applications own their editable state and computation. Surface service
  transports bytes and displays app-authored content; it does not edit documents
  or parse application expressions. File job behavior and failure isolation stay.
- AI6: ordinary profiles retain rejection/behavior and fixed code/mapping limits.
  Independent freestanding builds, exact image budgets and real native runtime
  checks must pass; host tests alone are not application-input qualification.
- AI7: actual QEMU and owned visible VirtualBox input/focus/edit/restart captures,
  exact output, negative authority controls, old-profile regression and cleanup
  precede a new local preview. Keep the Cycle299 receipt/ISO immutable.

## Progress And Boundaries

At cycle entry the authoritative branch matched origin, with only pre-existing `.tmp/` and
`native/.tmp/` untracked. Usage permits work; the available weekly window reports
21% used, with no separate five-hour value. Master-checklist, Phase65 ZIP and
conformance-report hashes still match Cycle299. Phase65 remains the newest live
PooleGlyph checkpoint; Phase66 and native language/PDC gates are unchanged.

This cycle does not complete compositor recovery, native arbitrary overload,
physical devices, persistent files, PooleGlass accessibility, a production ABI,
full canonical/merge gates or any N0-N39 production phase. Record failures and
reconcile exact current evidence here and in the build plan as work proceeds.

## Implementation And Reconstruction

PWS1 op5 is opt-in and requires the exact kernel-attested owner generation,
surface handle and next sequence. Two fixed64-byte queues return at most32 bytes;
cancelled or denied requests cannot drain them. Applications retain one surface
request and drain it before file waits. Each application owns its48-byte scratch
draft and computation; the window service only routes input and displays cells.
Held keys and modifiers are fenced through focus changes. Controller reset now
also clears incomplete set-1 prefixes while retaining known held-key fences.
Input stats retain their Terminal-FIFO meaning, not global app-delivery counts.

The first six freestanding build probes are preserved as failures. They exposed
compiler-emitted GOT/absolute references, bulk-copy/zero helpers and oversized
inlined app code. Repairs keep generic app polling in one local monomorph, use
scalar snapshot initialization and separate queue fields, and preserve every
linker/relocation/page-limit guard. Probe7 builds and audits29 programs: ordinary
window16364/16384 bytes, input Text14857 and Numbers14864/16384, and input window
service24594/28672 with the existing seventh-page probe at24576. No new syscall,
capability, concurrent request slot or code-page allowance was added.

`host-focus1` passes61 desktop tests (145 filtered), including real PS/2 stream
routing, cross-owner denial, cancelled requests, reply backpressure, queue/draft
overflow, prefix repair and file-job/draft coexistence. `python-focus1` passes52
checks, including the exact-pixel oracle and owned VirtualBox capture bounds.
These are host/preflight evidence, not native input qualification. The native
challenge uses a shorter shell case retaining both application generations and
all four file waits, to make room for direct application input inside the same
240-second guest bound. Full ordinary shell coverage remains a separate cohort.
Native guest tests, independent final builds, current metadata and a new preview
remain pending. The Cycle299 receipt/image and public evidence are unchanged.

`programs1` passes206 debug/release tests and29 independent program pairs. The
first optical link (`optical1`,27.328 seconds) fails before boot: embedded app
data reaches0x1BC88, past the lifecycle layout's0x1A000 boundary. Introduce only
the explicit `development-window-input` selector with0x1C000, dependent on the
existing lifecycle profile. Runtime entry offset and linker selector agree;
208 total image pages and36 guarded stack pages remain fixed. Existing profiles
retain their prior boundaries. No new syscall or process permission is added.

Review also found unread Terminal FIFO bytes could disappear at an interactive
focus boundary without cancelling the partially delivered command. The input
profile now emits Terminal's own cancellation and discards through its next
delimiter; app cancellation cannot become a Terminal command. The ordinary
profile remains unchanged. `programs2` passes207 tests per debug/release and29
independent binary pairs, including exact ELF/code equality and relocation audits
(17.843 wrapper seconds). A new layout test initially expects the wrong Python
exception superclass for an intentionally rejected feature set; `python-focus2`
retains that single test error. Correct it to the actual QualificationError after
the current native diagnostic, then replay affected checks. `optical2` passes all
three full serial scenarios and unsigned-image denial (621.219 wrapper seconds).
The input kernel measures134/208 pages with36 guarded stack pages and888 bytes
remaining in the explicit input read-only boundary. This is not direct-input proof.

`qemu-standard1` fails at the unchanged256-capture bound after70 successful input
actions (102.672 wrapper seconds). Exact frames prove editing, calculation and
held-key focus isolation up to that point, but the incomplete run is not accepted.
Software repainting spans several150ms samples; use600ms initial/300ms retry
sampling, retaining the same12-second action,240-second guest and256-capture
bounds. Once all three focus motion phases finish, retries now only observe paint
instead of reinjecting motion. Host negative tests cover that state and unchanged
capture/deadline bounds. Correct the layout test's exception class; new execution
bindings require a fresh optical cohort before final guest qualification.

`python-focus3` passes36 selected input/lifecycle/mouse/window checks, including
both harness regressions (2.875 wrapper seconds). All seven kernel profiles pass
in debug/release: default582, applications601, desktop607, windows613, capacity614,
lifecycle614 and input614 tests each. `host1` binds the unchanged current sources.
An optical invocation combining the separate terminal and window flags is
rejected at argument validation (`optical3`); no build or guest is launched.
The corrected `optical4` cohort is running on frozen execution sources. Current
architecture/roadmap generation is prepared but cannot advance until the input
receipt and all required real-guest evidence exist. Native input qualification,
legacy replay, convenience ISO and final metadata still remain pending.

`optical4` passes on its frozen source (642.094 seconds); its image matches the
earlier optical2 bytes. `qemu-standard2` then fails at step91 after91 successful
application observations,175 captures and141.234 seconds. `qemu-diagnostic1`
reproduces the same step (135.843 seconds), retaining CPU registers and96MiB of
read-only owned-guest RAM. Both app drafts remain intact, but both surface clients
have4096 polls, no pending request and sticky failure. No task retired. A fully
populated scene has more drawing submissions than the ordinary poll allowance;
the tight pending-request drain can exhaust it while the WM composes.

Keep ordinary clients at4096. Input-profile clients now use65536 bounded polls
for input, draft writes and base result publication. A renderer-work regression
checks two fully populated maximum-viewport scene turns, including queue retry
work; a delayed-peer regression crosses5000 polls successfully and still proves
exact cancellation at65536. `programs3` passes209 tests per debug/release and29
independent binary pairs (24.812 seconds). Input Text/Numbers are14845/14852 bytes;
the service/page and total kernel limits are unchanged. A targeted diagnostic
image is explicitly unqualified and cannot become the final preview evidence.

The603 failed application PPM captures are retained in three lossless ZIP files
under `outputs/cycle300-failed-frame-archives`, with per-file sizes/hashes and
independent decompression verification before raw duplicates were removed. This
recovers approximately1.83GB of local disk space. Receipts, logs, inspected PNGs,
CPU snapshots and memory dumps remain in their original directories.

The repaired `input-diagnostic2` passes all96 exact application observations,
six lifecycle barriers,17 pointer steps and the332-byte keyboard shell case in
231.671 wrapper seconds, using144 captures. It is explicitly diagnostic-only:
the packaging verifier rejects diagnostic receipts as final guest evidence.
`host2` replays all14 kernel profile/mode combinations on the current binding;
`python-focus4` passes the36 selected checks. The full `optical5` cohort is now
running, before final QEMU/VirtualBox device-input runs and legacy regression.

`optical5` passes the two normal application boots, stale-file-grant control and
ordinary unsigned-image denial in629.703 wrapper seconds on unchanged source.
Its independently rebuilt image matches the targeted diagnostic ISO exactly:
`CC11DBF0F101AB464C0343140DDAEF5BCD5497E19E034D3A0BCF11E7EA8D0304`.
The input kernel remains134/208 pages,36 guarded stack pages,0x1C000 entry and
912 bytes of read-only boundary padding. Final direct QEMU/visible VirtualBox
single/batched input runs and the legacy capacity cohort are running sequentially.
The local preview still points to immutable Cycle299 evidence until these pass.

Both final QEMU modes pass on optical5 (221.219/220.953 wrapper seconds). The
first visible VirtualBox run fails at step23 after23 successful actions: its
held A repeats before the600ms snapshot, so the fixed `draftA` expectation is
invalid. Frame027 shows `draftAA`; all63 captures and the failed receipt remain.
Owned VM stop/unregister, unchanged prior registrations and runtime/source/image
identity checks pass. The sequence stops before the other VirtualBox/legacy runs.
This is not accepted input qualification.

The [VirtualBox PS/2 implementation](https://github.com/VirtualBox/virtualbox/blob/main/src/VBox/Devices/Input/DevPS2K.cpp)
arms typematic for the last key and cancels it when that key is released.
The revised challenge taps/releases unused F1 after holding A/Shift, leaving
those two keys held while stopping unsolicited repetition before the exact
snapshot. It still injects their repeat makes after focus changes and verifies
that Numbers receives `3`, not `A`, `a` or `#`. No native code, expected pixels,
action count or deadline changes. This harness-only repair requires fresh
execution bindings and downstream replay; targeted VirtualBox validation comes
before the next full cohort.
The same upstream source filters duplicate host key-down events, so submitted
repeat makes do not prove guest delivery on VirtualBox. Retain the direct host
fence tests and mark native continuous-typematic focus/retirement stress open.
Do not promote the controlled held-key scenario into that stronger claim.

`input-diagnostic3` passes the corrected controlled-input scenario in owned
visible VirtualBox (227.797 wrapper seconds), with96 exact application actions,
six lifecycle barriers,17 pointer steps and owned cleanup. `diagnostic-image2`
rebuilds byte-identically to optical5. No native product source changes in this
harness repair. `python-focus5` passes36 checks; `host3`, optical6, both final
device modes on each backend and legacy1 are the final source-bound sequence.
The diagnostic remains explicitly excluded from final guest qualification.

Before the final cohort grows, archive637 additional raw application PPMs from
the two superseded QEMU passes, two diagnostic passes and failed VirtualBox run.
`outputs/cycle300-superseded-frame-archives` retains lossless ZIPs and per-file
hash/size manifests, verified by decompression before removing raw duplicates.
Approximately1.8GB is recovered; all receipts, logs, PNGs and final-cohort files
remain untouched. This is storage maintenance, not deletion of failed evidence.

The final optical6 cohort passes (644.797 wrapper seconds), followed by both
QEMU modes (222.843/220.609 seconds) and both visible VirtualBox modes
(227.328/219.937 seconds). Every device run completes96 app observations,
six lifecycle barriers and17 pointer steps; the332-byte shell case remains exact.
Legacy capacity regression is now running. Publication-path regressions pass9
tests, including secret/user-path and raw/private-variant rejection; discovered
Python inventory is1582, with no import errors, not a full-suite execution.

System-drive pressure requires a further lossless archive of24 superseded
optical2/4/5 media files. Three ZIPs in
`outputs/cycle300-superseded-media-archives` retain every original byte with
per-file and receipt hashes, verified by decompression before raw duplication is
removed. Approximately1.58GB is recovered. Optical6, legacy1, current guest
captures, all receipts and the Cycle299 preview/Downloads image remain untouched.

## Final Native Cohort

Legacy capacity regression passes in 564.422 wrapper seconds, including two
normal boots, stale-file authority and ordinary unsigned denial. It retains the
ordinary profile without input or lifecycle features. Final totals are ten QEMU
and two visible VirtualBox checks, 384 exact application observations and 24
lifecycle pixel barriers. Each direct-input guest preserves the 240-second guest,
12-second action and 256-capture limits. All owned VirtualBox cleanup checks pass.

The packaging verifier reconstructs every final application/lifecycle frame,
pointer sample, shell nonce/output and input sequence, checks independent program
bytes, current source bindings, ordinary-profile regression and retained failures,
and rejects diagnostic-only receipts. The new public receipt is
`runs/native-application-input-readiness.json`, SHA256
`206ECF299017E089B031ED18A6E70997A051F51DD01581399441CA5E30D0289C`.
It records partial production readiness and no canonical/merge/release promotion.
The 66,109,440-byte optical6 ISO has SHA256
`CC11DBF0F101AB464C0343140DDAEF5BCD5497E19E034D3A0BCF11E7EA8D0304`.
Historical Cycle299 evidence and owner-input hashes remain unchanged. Final
metadata, convenience-copy verification, staged publication audit and cloud
backup still precede closeout. The latest available weekly usage is 46% used;
no separate five-hour value is available and no usage hard stop is reported.

`metadata1` runs all 427 selected tests and fails nine assertions in 105.219
wrapper seconds: seven historical tests still require old current source counts,
and two checks encounter the schema's old Cycle299 constant. Update only the
current counts to measured 988 execution/96 program bindings and the schema
constant to 300; retain historical receipt hashes, counts and production gates.
The failed log SHA256 is
`E99447197F9859DD3D9CBECEB9FE03E89642DF1119E13137BF27CA578DB1C38E`.
Native sources and ISO bytes are unchanged by these metadata repairs.

`metadata2` passes 426/427 tests in 125.734 wrapper seconds. The remaining
historical test reaches a previously hidden assertion for the old current
next-move title. Update that assertion to the new active-window lifecycle and
useful-desktop work recorded by Cycle300. Retain the failed log, SHA256
`B1EC7B5F9E575AF57CBDA3D6F654B79F8D72C256EB1EA7EF48DA582C29833DD5`.
The first exact-index publication scan passes 2,089 paths with zero violations;
final documentation changes will be staged and scanned again before commit.

`metadata3` passes all 427 selected tests in 121.922 wrapper seconds with no
discovery errors and unchanged execution source. Log SHA256:
`878B91A5E445AD3CD7CC8C06FF1247492AC666BEF53B49DE82727FE87AA51FD1`.
The 1,582 discovered tests are inventory, not a complete-suite pass. Architecture
binds 849 files; execution binds 988 and program builds bind 96. All native
execution evidence remains exactly current after the metadata-only repairs.

The local launcher now selects `outputs/cycle300-optical6/receipt.json`.
`PooleOS-Native-Windows-Cycle300.iso` is copied without overwrite to Downloads;
its 66,109,440 bytes and SHA256 match the tested ISO. Cycle299's original copy
and receipt remain untouched. The guide documents direct Text/Numbers input,
scratch limits, read-only files and required VM configuration. No production,
release, signing, physical-media or complete-desktop claim is added.

## Final Audit

`final-audit1` passes in 57.500 wrapper seconds. It checks all 50 exact staged
blobs, 84 immutable historical readiness/execution receipts, unchanged owner
inputs, 29 independent ELF/code pairs and relocations, both kernel-image pairs
and distinct controls, final native pixels, runtime identities, owned VM cleanup,
direct ISO-copy byte equality, launcher selection, current source bindings,
generated ledgers/schemas and the successful 427-test capture. The index-only
publication scan passes 2,089 paths with zero violations. Audit log SHA256:
`1C1D2993746E6C7E30E8CBDEF6C9CA41708CCBD8BF008661F21EA826F3F6E4EB`.
This result is recorded through documentation-only closeout; regenerate the
bound ledgers, restage and repeat the exact verifier before committing.

Next: qualify native focused/dragging retirement and input-lifetime boundaries,
then compositor recovery/resynchronization, event-driven waits and useful
graphical launch/edit workflows. Keep continuous typematic and transport stress,
fairness/repaint latency, persistence, scalable services/address spaces,
accessible PooleGlass, full canonical replay and every N0-N39 obligation open.
Push the checkpoint branch and update draft PR81 only after the final verifier
passes. Do not infer main-merge, release or production permission from these
bounded development results.
