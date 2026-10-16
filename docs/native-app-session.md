# Native Application Session

Cycle283 implements the opt-in PAPPSESSION1 catalogue: PooleFileInit, PooleAppFiles,
PooleConsoleService, PooleAppShell, PooleText and PooleNumbers occupy six distinct
owned CPL3 address spaces. This is COM2 serial-console integration, not a desktop,
optical ISO, general executable loader or production profile.

## Launch And Ownership

The two application roles are prepared but not scheduled at bootstrap. Authorized
launch uses existing atomic admission to derive SEND-only control/file capabilities
from live shell/file-service endpoints and publish the process lease. The dispatcher
retains actual returned handles, not guessed generations. The child's owned176-byte
startup block is replaced and read back before dispatch. Startup metadata is
copyable; Slot/CpuImage still owns all memory and execution authority. Metadata
cannot independently activate the image. Launch sequence must equal child generation.

Exclusive BSP, kernel CR3, no active user context and IF/DF/AC clear span handoff.
Admission commits first. A handoff error halts with owners retained; combined
rollback and asynchronous handoff-error recovery are not implemented. User policy
authenticates kernel peer identities, never a payload-supplied sender identity.

The bad-file profile changes only the numbers application's startup file-handle
generation to a nonzero ungranted generation. Control, process lease, console and
text remain valid. File jobs report unavailable before/after restart; deliberate
UD2 still executes and is contained. This is not a denied process-launch control.

## Native Acceptance

Two independent kernel builds match directly. Six unique embedded programs bind
to independently reproduced ELF/code pairs. Two normal guests and one stale-file
guest receive independent nonces and557 bytes of real byte-stepped input across37
commands. Results cover changed/empty/missing/invalid files, repeated jobs, both apps
alive, numbers UD2, surviving text/shell work, both restarts and final retirement.

The oracle checks handoffs, generations/handles, distinct roots, owned pages,
progress, CR3 writes and cleanup. COM2 is never kernel evidence. Boot/PBP1/retained
images are independently cross-bound. Synthetic fixtures and mutations are parser
tests, not guest evidence. CLOSE can retire console after its reply before shell
consumes it; both apps must be retired before either service exits.

Guests complete7936/7808/7744 dispatches and reject757/747/742 hostile marker cases.
App kernel121/208 pages,36 guarded stack pages. Six roles,32 PMM records and16384-byte
RX remain unchanged. App-only RO/entry boundary0x13000; file/default0xE000/0xD000.
Nine additional file/deferred-cleanup/default/unsigned-denial guests pass.

## Restart Repair And Limits

The first run progressed into shutdown but timed out at240 seconds. Restarted
session programs had not enabled their calibration cache, recalibrating on every
dispatch. A360-second diagnostic was deliberately interrupted after finding this.
Restart now creates a fresh identity-bound cache and measures for its own owner,
never reusing the old owner's sample. The original240-second bound was restored
before three passing guests. Build plus all three runs take158.469 seconds; this
is not a general performance benchmark or efficient-idle claim.

Default551/file567/app570 kernel tests pass per debug/release, plus26 ownership
doctests and nine new Python oracle/wiring tests. Existing127 user tests/profile
and17 binary pairs remain bound; their host tests were not rerun this cycle.

Before optical acceptance: native malformed/untracked file requests and requester
death, live-parent deferred completion/restart, cleanup exhaustion/multiple owners,
and waiting/pending request interleavings. Then package and operate the actual ISO
on fresh boots with sustained input and a documented interactive VM launch path.
Local display/input, job interruption, full stack bounds, general supervision,
efficient idle and physical hardware remain open. Complete microkernel,
PooleGlyph/PDC, PooleGlass and all production gates remain required afterward.

Current Cycle287 update: ordinary applications and queued/malformed/untracked
file controls pass fresh native regression. The separate `--claimed-requester`
profile qualifies two blocked claimed-requester cancellations, stale waiters and
diagnostic-service late-reply denial per guest. See
[Cycle287](checkpoints/cycle287-native-claimed-requester.md). Targeted lifecycle
controls now precede actual optical packaging; generalized races/recovery remain
in the full microkernel program. Earlier numbers above are historical Cycle283.

Receipt: `runs/native-app-session-readiness.json`.
Reproduce: `python -B tools/qualify_native_app_session.py --work-dir outputs/NEW --program-dir outputs/CURRENT-PROGRAMS`.
Both paths must be workspace outputs and the program receipt must match current inputs.
