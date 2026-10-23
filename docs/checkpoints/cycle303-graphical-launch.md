# Cycle303: Typed Graphical Launch Control

Date: 2026-10-18. Status: verified foundation; graphical integration remains partial.
Parent: `69b0dbed067206f5587e4441ecfefd47915aee0a`, Cycle302.
Previous goal turn: progress, with kernel implementation, native qualification,
updated plan/evidence and verified development-branch push. The complete native
production goal remains active; this is not a replacement objective.

## Entry And Selection

At entry, the tracked worktree was clean on `agent/userspace-integration-iso`.
Ordinary usage was allowed; the available weekly window was88% used. No separate five-hour
value is available. The master checklist, Phase65 archive and conformance report
hashes remain unchanged from Cycle302. Phase65 is still the newest checkpoint.
No PooleGlyph/PDC promotion follows from desktop work. Keep all40 phases and301
subphases, accessible PooleGlass and the complete native microkernel path.

Inspect the actual process policy, shell state machine, console IPC, startup
decoder, local window adapter and input manager. The shell owns two factories;
the compositor has read-only lifetime observation. PCS1 has a strict32-byte
payload, authenticated kernel peer envelope and one outstanding exchange.
PooleAppShell has1248 code bytes free; ordinary WindowConsole has20. The input
window profile has an explicit seventh-page probe. Measure compiled code/stack
and embedded kernel layout before native admission; do not silently grow limits.

Alternatives: injected terminal text violates typed control/line ownership;
compositor factories widen authority; a new broker process adds ownership/lease
and lifecycle work; a separate control endpoint is clean but needs new bootstrap
grants and demultiplexing; a typed versioned exchange on the existing console
channel can preserve authority and serialize shell work. Select the latter for
implementation, while retaining the separate-endpoint option if measured coupling
or code capacity disproves it. Host/device delay and missing surface admission
remain alternatives to process failure; admission must not be called a running
window. Legacy PCS1 must continue rejecting the new control wire.

## Active Invariants

- LC1: only the shell's existing factories launch the two catalogued apps. No raw
  task/handle, framebuffer/device grant, unrestricted termination or new privilege
  comes from a graphical request. Restart requires observed terminal completion.
- LC2: exact version/type/length/reserved bytes, caller authentication and bounded
  payloads. Ordinary PCS1 rejects launch messages; a codec alone is not auth proof.
- LC3: request sequence and expected process generation bind every effect.
  Stale/replayed requests do not call launch; pending/reply backpressure cannot
  duplicate an admission. Failed attempts retain correct consumed generations.
- LC4: distinguish pending, admitted, running, retiring, absent and failed/denied
  outcomes. Stop acceptance is not completion; malformed kernel replies fail closed.
- LC5: preserve terminal drafts and in-flight file jobs. Do not synthesize command
  text, steal another application's input, or resurrect retired surfaces.
- LC6: fixed storage/work, one syscall per policy step, original guards/quotas,
  measured freestanding code and stack usage, and explicit layout decisions.
- LC7: host/protocol/probe evidence cannot claim connected graphical/native
  behavior. Qualify the actual new image before preview selection, retain failed
  attempts and the Cycle302 image, and update plan/flags/ledgers truthfully.

## Execution

1. Implement strict PLC1 typed start/inspect requests and results, plus a bounded
   broker around the existing process policy. Challenge replay, stale generations,
   busy/retiring states, malformed replies, rollback and duplicate effects.
2. Connect only an explicit authenticated console control mode and measure its
   compiled shell/window footprint before admitting a graphical profile.
3. Add graphical launch/restart affordances and pending/failure state, preserving
   focus, input lifetime, fixed geometry and application isolation.
4. Build and qualify the actual native profile/ISO with hostile controls and
   ordinary regressions; only observed evidence may advance the preview.

Compositor restart, COM2-independent graphical boot, persistence, accessible
PooleGlass and every remaining production gate continue after this integration.

## Implementation Progress

Steps1 and the transport portion of2 are implemented. PLC1 has strict32-byte
start/inspect requests, generation-related outcomes and immutable valid replies.
The fixed broker retains one pending/result slot, rejects replay and stale
generations, shares process-owner transitions with the CLI and fails closed after
malformed kernel results. The explicit PCS1/PLC1 RPC adapter validates the kernel
peer envelope before decoding, enforces direction and consumes one-use tokens.
Ordinary PCS1 rejects PLC1. There is no terminal-text injection or new authority.

246 userspace tests pass in debug/release, including29 new cases. Two independent
builds of all29 existing programs match with local-relative relocation audits.
The shared refactors change11 binaries;18 remain identical to Cycle302. The
ordinary shell is15440/16384 bytes, leaving944 bytes. Ordinary WindowConsole is
16268/16384; the input window profile remains24594/28672 with its page-seven
probe. These measurements exclude unused PLC1 connection code. No image or
stack limit has been increased.

Failures retained: the first host build exposed a private helper visibility error;
the first native build exposed a shared out-of-line slice-copy helper/GOT dependency
and size failures. Following existing cross-crate inline patterns removes those
dependencies without changing the loader. A storage preflight rejected a retry;
seven superseded Cycle301 test media files were losslessly archived and verified
before loose-copy removal, preserving both preview ISOs and all receipts/logs.

Remaining steps2-4: bind control to the shell Read/result/ack session state while
preserving drafts/file jobs; add explicit startup roles and compiled profile;
measure actual connected code/stack; connect graphical launch/restart states and
keyboard access; qualify the actual connected native ISO. The broker and transport
alone do not qualify those behaviors. The final ordinary native regression passes;
the source-matched Cycle303 image is now selected, without claiming PLC1 execution.

[Wire, ownership and admission contract](../native-launch-control.md).

New required open `FLAG-N13-LAUNCH-FAILURE-001`: the current native application
dispatcher uses fail-stop preparation/admission and enforces successful task
generation equal to the factory attempt. Host broker failure/retry tests do not
establish native recoverable failure or its generation/cleanup contract. Prove
ownership-safe native failure, cleanup and retry before claiming graphical failure
recovery. This adds no permission to weaken fail-stop or ownership invariants.

Storage retention later also verified seven superseded qualification-media files
per Cycle298/299/302, keeping every preview ISO, Downloads copy and raw receipt.
Some retention ran during the ordinary regression to avoid exhausting the system
volume; these bounded correctness runs are not performance/latency measurements.

Reconstruction: keeping Cycle302 selected after modifying source would fail the
launcher's current-source check. Do not weaken that gate. Preserve the historical
ISO and select the rebuilt ordinary regression image only after the entire prior
input/lifetime matrix passes on both backends and both input modes. This restores
the source-matched launcher without claiming PLC1/native graphical integration.
The new ordinary kernel is134/208 pages,36 guarded kernel-stack pages and360 bytes
of read-only padding at entry0x1C000. Native preparation failure and connected
code/stack/layout remain explicit next integration gates.

## Native Qualification And Preview

All four ordinary optical controls pass, followed by all eight desktop runs:
standard and four-character input modes, application-input and input-lifetime
challenges, each on QEMU and visible VirtualBox. Total: eight QEMU and four
VirtualBox runs, 384 application observations, 96 ordered lifetime observations
and 48 generation-bound lifecycle pixel barriers. The original 240-second guest
and 12-second action bounds remain. VirtualBox guests stop/unregister cleanly
without changing prior registrations or moving the host cursor.

The evidence reconstruction independently checks exact transcripts and nonces,
markers, native ELF extraction/relocations, source bindings, kernel layout,
archive members/hashes and measured framebuffer pixels. QEMU and VirtualBox
captures were also inspected visually. These are the existing native Terminal,
Text and Numbers windows, not newly connected PLC1 controls or finished PooleGlass.
The public evidence receipt is `runs/native-launch-control-readiness.json`.

The launcher and byte-verified Downloads copy select the ordinary Cycle303 ISO:
`PooleOS-Native-Windows-Cycle303.iso`, 66109440 bytes, SHA256
`4FAC38AA0A631CC2D4D2AD428AAFEE07EE33A2CEB7FAEF8128655D9A6553D8F8`.
The Cycle302 preview ISO and Downloads copy remain unchanged. This is an unsigned
EFI optical development preview, not a standalone distribution, hybrid USB image,
release or production promotion. COM2 and the qualified host launcher are still
required. No kernel source, firmware, keys or physical media changed this cycle.

## Metadata Reconstruction

The first 441-test metadata/integration run failed 11 assertions: the new flag
exceeded the old exact schema count; historical checks retained current-program
counts/equality and the former next-move title; one program-oracle assertion
expected the old combined peer decoder. These failures are retained, not ignored.
The repaired oracle checks strict PCS1 delegation and authenticated payload
decoding on both RPC receive paths. It does not loosen authentication or native
admission. The 13 program-oracle tests pass.

Because that test file is a program-build input, two fresh independent builds
were required. All 29 ELF and extracted-code pairs exactly match the programs
used by the completed native runs. The sole program-source binding change is
`tests/test_native_user_program.py`; all 1000 execution bindings, native receipts
and the selected ISO remain unchanged. The final receipt explicitly records this
oracle-only refresh and preserves the earlier unpublished reconstruction. It
does not replace old native receipts or pretend the VMs ran again after the test
edit. The final program directory is `outputs/cycle303-programs4`.

The corrected 441-test metadata/integration replay passes. Python discovery is
1596 tests, not a claim that the full canonical suite ran. Direct roadmap writes
returned Windows `OSError [Errno 22]`; unchanged bounded retries completed.
The cause is not established. Architecture binds 870 sources, execution 1000,
and program provenance 102. All 40 phases and 301 subphases remain; the flag
inventory is 101, with 46 open. Final source/index, schema reproduction and
publication checks are required before development-branch backup. Main merge,
signing, releases, production readiness and the complete goal remain unqualified.
