# Native Launch Session

Cycle304 extends PLC1 with an opt-in session binding and a build-only PLCODE1
shell candidate. It does not select a new kernel, ISO or graphical control.
The ordinary four-page PUSERBIN1 admission remains unchanged.

## Ownership And Ordering

The console service can replace only its outstanding Read response at sequence
S with a typed request. The shell must independently have Read S outstanding.
The shell's ApplicationCommands retains the same Files, Jobs and
ApplicationProcesses owners. No command text is injected, no factory is copied
to the compositor, and active writes, close handshakes and file/job work are not
interrupted.

Both sides reserve S+1 for Written and S+2 for the resumed console request before
any process effect. S+2 must remain strictly below u64::MAX. The shell replies
with the exact request identity and observed status; the service verifies every
identity field before acknowledging. Service results are visible only after the
acknowledgment is accepted. The shell clears only its pending Read and advances
the sequence after receiving that exact acknowledgment. Draft bytes, overflow
rejection, CRLF suppression, output position and command route are unchanged.

Each wrapper poll performs at most one IPC operation or one process-owner step.
Typed values are retained through backpressure. A malformed exchange, foreign
kernel peer, revoked completion or wrong acknowledgment permanently poisons that
session. A failed session does not replay admission, discard an owned child or
claim successful cleanup. Native critical-service failure policy still applies;
recoverable native launch preparation is a separate open requirement.

Connection owns the existing authenticated PRPC1 Transport and its Calls adapter.
The end-to-end host test runs both real session wrappers and both real transports
with a fake kernel enforcing single pending completions and one-use reply tokens.
This proves host protocol behavior, not the real kernel or native scheduling.

## Explicit Build Profile

The connected PooleLaunchShell has a separate `launch-session` Cargo feature and
`launch-shell` PSTART1 role. It has no new capabilities or host/kernel dependency.
Default builds omit this candidate. Its first native link under the ordinary
four-page profile was rejected: .text measured 0x4C08 = 19464 bytes.

PLCODE1 permits at most five RX code pages, 20480 bytes, for this named build
candidate only. It is mutually exclusive with the seven-page window-service
profile. The extractor still rejects the candidate under ordinary PUSERBIN1.
The linker still rejects writable data, imports and relocations. Two independent
candidate builds produce identical ELF and code bytes; object relocations are
audited for defined local read-only relative targets. This is not loader trust.

No kernel mapping or embedded image layout accepts PLCODE1 yet. The candidate
is not an executable boot profile. The current input-profile embedded read-only
region had only 360 spare bytes in Cycle303, less than the shell's 4024-byte
growth over PooleAppShell. A reviewed page/layout change is required, including
guard preservation, immutable mappings, executable-range validation and image
budget checks. Do not merely raise a global code limit or replace the old shell.

## Next Admission Gates

1. Bind a matching console/window-service role and explicit kernel session profile.
   Account for its compiled code, startup arguments, embedded image offsets and
   every RX/NX mapping. Keep factories in the shell and the original guard policy.
2. Measure nested startup, broker, parser, file/job and error-path stack use;
   qualify guarded-stack execution. Static code size is not a stack bound.
3. Add keyboard-accessible launch/inspect/restart states to the native window
   manager. Display admission separately from authenticated surface publication
   and observed running status. Preserve input focus and held-key/drag fences.
4. Exercise real cross-process request/reply, backpressure, stale/repeated/failed
   controls, terminal drafts and concurrent file work in QEMU and VirtualBox.
5. Build and independently verify a new optical ISO, exact pixels/transcripts,
   full relevant native regression and the source-bound launcher selection.
   Keep historical images and receipts unchanged.

The prior 29 ordinary program images are all byte-identical to Cycle303, but this
does not convert historical native evidence into current-source qualification.
No new ISO or native guest run is claimed. The current preview pointer is retained;
its strict source check must remain enabled and can reject this newer tree.
Compositor recovery, COM2-independent boot, persistent files, event-driven waits,
fairness, accessibility, PooleGlass, complete microkernel, PooleGlyph/PDC and
all remaining N0-N39 production gates stay open.
