# Native Shell Process Integration

PSHELLPROC1, development-only, Cycle274. See the
[checkpoint](checkpoints/cycle274-native-shell-process-control.md) for measured
results and retained failures. No optical ISO or useful application pair yet.

`PooleControlShell` retains the existing terminal and console transport. Its
PSTART1 role is `control-shell`, followed by receive/send console handles, the
authenticated console peer, and two launch-factory handles. It has no UART grant.
`Processes` binds its factories once; attempts to reset authority or generations
reject. Factory shape checks cannot grant authority: the kernel validates actual
owner/root/generation attachments on every operation.

| Command | Observed Behavior |
| --- | --- |
| `start worker` | Request admission through its factory; repeat the same sequence while pending |
| `status worker` | Read actual attached/stop/retiring or terminal state |
| `stop worker` | Request cancellation; acknowledgement is not completion |
| `start fault` | Launch an isolated diagnostic executing UD2 |
| `status fault` | Report the genuine fault vector from kernel completion |
| `start` after completion | Verify completion, then request the next generation |
| `exit` with outstanding child | Refuse until terminal results are observed |

Names/tokens are exact, case-sensitive and bounded by the existing64-byte line.
No quoting, arbitrary paths, executable discovery or PID-based authority exists.
Each policy poll performs at most one syscall. Invalid/denied/malformed results
cannot invent a process or claim that cleanup completed. The console advances
only after authenticated, sequence-matched replies; backpressure preserves state.

The trusted opt-in dispatcher admits fixed catalogue IDs into two reserved slots.
It reuses owned construction, private roots, scheduler accounting, stop permits
and PCOMP1 publication. It does not parse shell text or choose restart policy.
Normal termination scrubs/releases images before publishing results. Unexpected
construction/cleanup failures halt fail-closed; general retry and orphan policy
are deliberately not claimed. Six images stay within32 PMM records, not an
unbounded process count. Prepared unused images are reclaimed on clean shell exit.

Build programs with `tools/qualify_native_user_programs.py --work-dir
outputs/<fresh-programs>`, then run `tools/qualify_native_shell_process.py
--work-dir outputs/<fresh-capture> --program-dir outputs/<fresh-programs>` using
the pinned local toolchain. This creates development VM media, not an optical ISO.
The adapter features are `development-shell-process` and its denied-factory control
`development-shell-process-bad-owner`. The default production trust path is unchanged.

Three180-second guests use two independently byte-equal normal kernels and a
distinct denied-factory kernel. Fresh nonces and paced actual input exercise the
shell after boot. Exact COM2 captures prove interaction only; separate authenticated
boot/media/source bindings and COM1/debugcon lifecycle observations prove native
execution, fault isolation and retirement. No guest network, host share, hardware
passthrough or host acceleration is used.
