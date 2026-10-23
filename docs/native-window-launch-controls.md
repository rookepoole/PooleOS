# Native Window Launch Controls

Cycle306 adds a bounded window-manager client for the existing PLC1 session.
It is an opt-in native candidate, not yet selected by the boot profile.
The native regression continues to use PooleWindowInput and the admitted
PooleLaunchShell. Do not describe that regression as GUI-triggered PLC1 traffic.

## Authority And Input

The shell retains process factories. Controls sends one typed Start or Inspect
intent and waits for the real session server to acknowledge its result. There
is no terminal-command injection, extra endpoint, automatic stale/failure retry,
or queue behind an outstanding action. Cached attempt sequences come only from
bound replies; they are not task generations, surface handles or lease numbers.
Admission and authenticated surface presence are displayed independently.

A fresh left click on an unavailable application taskbar entry requests Start.
An available entry restores the existing window. Right click requests Inspect.
F1/F2/F3 select Terminal/Text/Numbers; Shift requests Inspect for an application.
Control/Alt combinations do not launch. Held keys and buttons require release;
prefixes, quarantine and input resets do not synthesize a fresh gesture.
Reset cancels only an unsent queued intent. A sent request must finish its
acknowledgment protocol; resetting input does not undo a process effect.
Publishing a new surface does not steal focus.

## Native Candidate

`PooleLaunchConsole`, feature `launch-desktop`, accepts only `launch-console`
startup with the existing six arguments and capabilities. The ordinary
`window-console` role remains distinct. The candidate uses the real PLC1
server/transport, native PS/2 input adapter and retained window/surface renderer.
Its build is qualified separately with:

```text
python -B -m tools.qualify_native_user_programs --launch-console --work-dir outputs/<fresh-directory>
```

The existing PWCODE1 seven-page maximum, page-seven execution probe, RX-only
segment, position-independent local relocations and no-import rules remain.
Renderer and transport reuse remove duplicated machine code without expanding
the loader, process mapping capacity or stack guards.

Only the launch entry uses the new 48-by-19 compact terminal buffer (912 bytes).
Ordinary windows retain their 80-byte row stride and 1920-byte backing store.
The shared terminal tracks a nonzero stride and bounds every cell access.
Differential tests compare every visible write, scroll, cursor operation and
full repaint, including surrounding canaries. The compiler's entry-frame
allocation falls from3384 to2392 bytes; this is not an all-path stack bound.
Nested calls, failures and native guarded execution must still be qualified.

## Required Integration

1. Add an explicit native desktop feature selecting this role only in the
   trusted window-service slot and the existing launch shell in its slot.
2. Recheck paired kernel embedding, quotas, startup roles and guarded stack
   paths. Do not widen limits or substitute the candidate into an old receipt.
3. Demonstrate actual mouse/key Start/Inspect/restart, retained terminal drafts,
   file work, delayed/stale/failure replies and independent surface publication.
4. Replay isolated application input, lifetime/focus/held-input barriers and
   visible state on QEMU and VirtualBox before selecting a new connected ISO.
5. Continue all N0-N39 gates, including compositor recovery, persistent storage,
   event-driven scheduling, native launch-failure cleanup, all-path stack bounds,
   complete microkernel, PooleGlyph/PDC and accessible PooleGlass.

The Cycle303 preview pointer and all historical evidence remain unchanged.
No production, accessibility, complete desktop or release qualification follows.
