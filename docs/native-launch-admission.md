# Native Launch-Shell Admission

Cycle305 extends the measured Cycle304 PLCODE1 build profile into the opt-in
native `development-launch-session` profile. This is a shell-admission step,
not qualification of native PLC1 messages or graphical launch controls.

## Authority And Memory

`Program::new` retains its four-page maximum. The trusted six-role startup selects
`Program::launch_shell` only for shell slot3 and `Program::window_service` only
for console slot2. Their bounds are five and seven code pages respectively.
The launch feature inherits the existing input/lifecycle/window profile; it
does not introduce another capability, driver, service or syscall.

The measured19464-byte shell occupies five owned RX code pages. Its stack remains
one RW/NX page with absent guards on both sides; the eight-mapping VM capacity
is unchanged. Startup, entry-offset and entire owned page-table readback
validation apply to every leaf, including the fifth code page. Ordinary
applications cannot acquire the larger allowance through their startup bytes.

The session physical-page quota explicitly adds one page for this shell. Startup,
running and retirement marker validation independently account for that page.
Removing it from any of those totals must reject the transcript.
The embedded read-only boundary is0x1D000 instead of the ordinary input profile's
0x1C000. The208-page kernel ceiling and36 guarded kernel-stack pages remain.
Actual linked size and padding must be measured, not inferred from source.

## Role And Build Selection

Slot3 receives the exact `launch-shell` role and the original eight startup
arguments. All original handles and process-factory ownership remain with the
shell. The ordinary `app-shell` role remains selected without the new feature.
The kernel builder allowlists the new profile and its stale-file-grant control.
It does not accept an unreviewed combination with serial fault injection.

`qualify_native_app_session --launch-shell-dir` requires the optical isolated-input
profile and a separately qualified PLCODE1 build under workspace outputs.
The ordinary six-program receipt and the separate candidate receipt remain
distinct. Each selected source receipt and its actual paired binaries must be
revalidated at entry and exit; a replacement does not rewrite either report.

## Required Evidence

- Host admission tests cover code boundaries, entry offsets, owned leaves,
  permissions, aliases, stack guards and unchanged ordinary limits.
- Independent freestanding kernels must match. Exact embedded programs, boot
  handoff, page accounting, application commands, file waits, contained faults,
  restart and final shell retirement require actual native observations.
- Both normal guests and the stale-file-grant control must satisfy the opt-in
  oracle. The ordinary unsigned-boot denial remains separate.
- Preserve rejected runs, source bindings and actual artifact hashes. Neither
  guest output nor a source-only test alone proves admission correctness.

## Remaining Integration

The selected window service is still the ordinary console server. It exercises
the new shell's ordinary PCS1 branch, not PLC1 requests/results/acknowledgments.
Next implement the matching window-service role and connection, bounded control
intents, mouse and keyboard activation, and visible distinctions between
admission, liveness and a published surface. Never synthesize terminal text.
The ordinary window-input binary uses24594/28672 bytes, and the measured kernel
read-only margin is only432 bytes. Re-measure the connected server before
changing any profile: spare code allowance does not imply spare embedded space.

Qualify stale/repeated/delayed controls, draft and file-job preservation, focus
and lifetime fences, real failure cleanup, nested guarded-stack paths, and both
QEMU and VirtualBox before selecting a new connected desktop ISO. Observed
paths do not establish production all-path stack bounds. Compositor recovery,
COM2-independent boot, persistence, event-driven waits, accessible PooleGlass,
the complete microkernel, PooleGlyph/PDC and all N0-N39 gates remain required.
