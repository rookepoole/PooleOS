# Cycle 274: Native Shell Process Control

Date: 2026-10-13. Branch `agent/userspace-integration-iso`, draft PR #81.
Owner priority remains usable native user-space ISO first, robust microkernel after.
This is implemented native integration, not an ISO or production promotion.

## Implemented

PooleControlShell is a separate 6720-byte, two-page CPL3 program. It uses the
existing console service, terminal editing and authenticated PCS1/PRPC1 transport.
Its user-space command policy supports exact `start`, `stop` and `status` commands
for two explicitly diagnostic catalogue entries, `worker` and `fault`. A separate
491-byte PooleWorker runs a version-call loop or executes UD2 at CPL3. Neither
diagnostic counts toward the ISO's two useful applications.

Copied PSTART1 arguments carry locators, not authority. The kernel grants two
generation-bound launch factories to the shell. Call19 admits a child, call18
requests termination, and call20 reports attached/pending/retiring or typed
terminal completion. Restart requires observed terminal completion and a new
sequence/handle generation. Completion is published only after capability
revocation, image reclamation, measured page reduction and scheduler teardown.
Console backpressure cannot repeat a process action. The shell refuses ordinary
exit until all started children have observed terminal results.

The opt-in native dispatcher runs six private images under existing PMM, mapping,
stack and image-capacity limits. The two-page shell needs14 owned pages; other
images13, total79 plus separately charged firmware. No kernel command parser,
Linux component, physical disk access, signing or release operation was added.

## Verification

- 78 user tests pass in debug and release, including18 new command/startup tests.
  Ten independent ELF/code pairs reproduce exactly. Seven earlier programs are
  byte-identical. The earlier PooleShell changes from3569 to3621 bytes and is
  independently replayed rather than assumed compatible.
- 512 kernel tests pass in each profile. The new adapter is an opt-in executable
  integration; no new host-kernel test count is claimed.
- Three fresh process-control guests pass with a frozen180-second per-guest limit.
  Both normal sessions launch two worker generations and two genuine faulting
  generations. Each reaches2432 dispatches/4866 CR3 writes. The denied-factory
  session launches no fault child, but valid worker stop/restart still works;
  it reaches2112/4226.283,283,238 hostile marker mutations reject.
- Shell/console close and all diagnostic images are reclaimed.26 image pages
  remain deliberately owned by the two live background services, whose progress
  continues after retirement. This is not a zero-object shutdown claim.
- Three fresh earlier-shell guests pass commands, editing, invalid input, close
  and denied-peer behavior under their unchanged120-second bounds.
- Two independent process-control kernels agree at112/208 pages; denied also112.
  Earlier-shell profiles113. Fresh default208/208 with120 RELRO padding bytes;
  default boot was not replayed.36 guarded stack pages remain unchanged.
- Initial21 focused Python tests and264 broader pre-closeout checks pass.
  Counts overlap. Inventory1419 Python tests and665 architecture bindings is not a
  full canonical suite pass. Current native qualification binds864 source inputs.

Public receipt: `runs/native-shell-process-readiness.json`.
SHA256: `34D484008939DDA7DF6BBB8EC655124F81E92EE81ADC45602B6C15EECA1F8262`.
Conventional pinned Rust compiler/assembler/linker, not PooleGlyph-generated code.
Raw failures, exact binaries, VM logs and read-only virtual media remain retained.
39 generated build/media archives have verified per-member hashes; raw captures
and ten independently built ELF/code pairs remain directly available locally.
The archive pass stopped on one misnamed remaining media path after preserving
six entries; inspecting the actual filenames and a fresh second batch completed
retention without overwriting the first manifest.

Pre-closeout264-test capture:54.213 seconds test time,55.297 seconds total;
SHA256 `1FFB53154DD49B979CA74A12036CB35140604AB713212EB45A5536458AAEDDB3`.
Its first run failed one stale source-inventory assertion (114 versus115 kernel
files). The exact expected set now includes the interactive dispatcher; frozen
entry evidence still contains79 original inputs. Failed264-test log retained:
`FD7195D451289107395E0FE7C27F8C1248427156DD4EF1ADA4E9C64E5E4F56B2`.
These checks precede final metadata closeout and are not full canonical gating.

## Failures And Repairs

Four user build candidates failed the unchanged relocation-free linker audit.
Inlining startup adapters, bounded byte output, explicit task initialization and
one-time in-place policy binding eliminated external helper/GOT dependencies.
No import, writable-data or relocation restriction was relaxed.

The first kernel compile exposed an index-width mismatch and two different
scheduler TaskId types. Explicit conversions corrected the adapter.

Two real boots hit the existing kernel stack guard before starting user space.
The first array constructor kept an extra six-owner array live; a literal array
still retained large construction temporaries. The final implementation fills
one Option-owned slot at a time and operates through references. Its generated
local frame is48680 bytes, down from69896 for the literal candidate. The six final
VM runs pass without increasing stack capacity. This is a repaired observed
construction path, not a proof of every possible call-chain stack bound.

## Remaining Work

USI-3/4 remain partial; USI-5 is not started. Next implement retained ownership and
retry after post-execution cleanup failures, and explicit owner-death/orphan policy.
Prepared-child stop exists in this opt-in adapter but was not exercised by these
native scenarios. Add those hostile lifecycle cases and stack-bound qualification.
Then implement read-only bundled-file service, two useful separate applications,
and optical ISO packaging with sustained interaction and recovery acceptance.

General executable trust/loading, writable data/heap, local keyboard/display,
efficient idle, resource-exhaustion recovery and exact-candidate canonical gates
remain open. The three previously tracked readiness failures were not rerun as
a full-suite audit. Main merge is not qualified by this scoped checkpoint.

No phase or flag closes:40 phases,301 subphases,8996 requirements,59 additions,
98 flags with43 open,20 gap groups. Existing USI and evidence flags retain these
gaps. Master checklist and live PooleGlyph Phase65 archive/report were rechecked
unchanged. Phase66 Core IR metadata-boundary audit remains next for PooleGlyph.
Complete robust microkernel, PDC, PooleGlyph and accessible PooleGlass development
continues after the usable ISO milestone.
