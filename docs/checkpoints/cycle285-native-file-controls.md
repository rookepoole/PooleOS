# Cycle285: Native File Controls

Date: 2026-10-13. Previous goal turn: progress, Cycle284 committed and pushed as a
draft checkpoint. The owner priority remains an actual user-space integration
ISO, then continued complete robust microkernel development.

## Implementation And Evidence

Add an opt-in PooleFileProbe, selected only for the development-file-controls
profile. Ordinary PooleText/PooleNumbers and all 17 previous ELF/code pairs remain
byte-identical. The probe occupies 2809 bytes/one RX page, has no imports, data
segment or relocations, and passes two independent builds. It is diagnostic,
not a useful application and not a replacement for the ordinary app session.

Each probe generation tests 13 distinct malformed frames: lengths 1/63, bad magic,
unknown operation, reserved byte, zero/MAX sequence, dirty tail, request status,
request total, excessive payload length, traversal path and out-of-range offset.
Each sends an untracked message, validates the tracked bounded error reply, and
then validates an exact version-file response. After 26 completions, a final
tracked begin is followed by exit 85 without consuming the completion. Polling is
bounded; invalid responses fail closed. Host tests exercise bad peer/header/data,
backpressure, distinct errors, retained outstanding state and exhaustion.

The kernel gains a read-only request snapshot, checked against the exact live
task generation. It is not exposed as a syscall, capability or lifetime pin.
The exclusive dispatcher checks one queued/claimed incomplete request before
retirement, then requires the old owner to be detached after cleanup. It emits
kernel observations independently of COM2. Host tests cover queued, claimed,
completed, consumed and stale-generation cases without snapshot mutation.

Three fresh contained QEMU/OVMF guests pass, including a stale numbers-file grant.
Each runs two probe generations, four numeric jobs (denied in the stale case),
three version reads, a contained numeric fault and restart. Each supplies 293 input
bytes, completes 4096 dispatches and rejects 617 hostile evidence mutations. Exact
task/generation retirement barriers prevent racing status requests. All six
observed abandoned requests were queued; none was claimed or completed. Claimed
requester death is therefore host-tested but not newly native-qualified.

Three ordinary application regression guests pass, followed by two default boots
and unsigned trust denial: nine fresh cases total. Kernel host tests pass 553
default and 572 file-control tests per debug/release profile, plus 26 ownership
doctests. User host tests pass 132 per profile; 16 Python oracle tests pass. Normal
application and file-control kernels use 121/208 pages with 36 stack pages; default
uses 208. Six roles, 32 PMM records and 16384-byte user RX bounds are unchanged.
Full call-chain stack bounds are not proven. No current deferred/prepared replay
is claimed; Cycle284 remains immutable historical evidence.

Public immutable receipt: `runs/native-file-controls-readiness.json`, 1761765 bytes,
SHA256 `342A9172364C8C0BBD2E9BFD270762C6F66310101AD50385F55934575B0FB41B`.
It binds 915 execution inputs and 64 user-build inputs, exact guest transcripts,
kernel/media/program identities, independent builds and failure captures. All
captures preserve source and owner-report identity. Final metadata and staged
checks follow documentation closeout; inventory counts are not qualification.

The repaired evidence/roadmap set passes 304 tests in 67.695 seconds (68.766 seconds
including capture), SHA256
`9AF954B64BF1C552F89227191C3CF11E2B0C629F7F228318D25992D5701870E1`.
Final staged replay follows these documentation edits. This is not full canonical
qualification, and the native execution receipt remains immutable.

Reproduce using fresh output directories: first run
`python -B tools/qualify_native_user_programs.py --work-dir outputs/new-programs`,
then `python -B tools/qualify_native_app_session.py --work-dir outputs/new-file-controls --program-dir outputs/new-programs --file-controls`.
Omit `--file-controls` for the ordinary useful-application regression. Required
workspace-local toolchain and QEMU provenance checks remain mandatory.

## Retained Failures

Two native build candidates failed the unchanged flat-program guard. A public
wire builder first generated out-of-line copy/fill imports; inlining narrowed the
failure to the probe. Mutating a caller-owned buffer and checked counter arithmetic
removed remaining copy/overflow-panic imports. A formatter call without PYTHONPATH
failed before running, and the subsequent program qualifier rejected unformatted
code. Corrected environment/formatting precedes the passing programs4 candidate.
No compiler flag, relocation restriction, RX bound or test gate was weakened.

The first file-control guest completed its operations but the oracle rejected its
process handle: Numbers launches first in this scenario, unlike the ordinary Text
first scenario. Corrected the exact profile-specific slot expectation and fixture,
added swapped-handle rejection, and repeated three fresh guests within the frozen
240-second bound. Failed raw captures remain available; no success was fabricated.

Before builds, two older failed application build trees were copied to the evidence
volume. All 2323 files/578159738 bytes were checked by size and SHA256 at both source
and destination before removing the exact workspace copies. The manifest remains
locally retained and hash-bound in the public summary. No shared host target,
current passing evidence, owner temp files or PooleGlyph files were removed.

The first 304-test metadata run failed two stale expectations: the architecture
schema still capped bound sources at 742, and an earlier roadmap assertion expected
"useful applications" in the next-move title. Set the exact bound count to 747
and retain the useful-app scope in the title. No native acceptance rule changed.
Failed capture: 68.594 seconds, SHA256
`023FA3CEDECAC826D3BDD0FB3346F930B4ED62D02EF06AEE4A2775706E544374`.

## Next Move And Boundaries

Next: native cleanup exhaustion, multiple pending owners and waiting/pending/claimed
request interleavings; then optical ISO packaging, fresh boots and sustained input
through a documented interactive VM launcher. COM2 is not local display/input.
Preserve prior build evidence before more large builds on the low-space host.
General supervision, idle, job interruption, full stack bounds, PooleGlyph/PDC and
PooleGlass remain. No ISO, signing, release, main merge or production promotion.

No phase or flag closes: 40 phases, 301 subphases, 8996 requirements, 59 additions,
98 flags/43 open, 20 gap groups. Source inventories: 1459 Python tests, 747 architecture
bindings, 915 execution inputs. Live PooleGlyph remains Phase65; Phase66 Core IR
audit is next. Its prior generated-report change and all owner inputs are preserved.
