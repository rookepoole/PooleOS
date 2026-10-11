# Native Development Service Session

PSESSION1, Cycle261. Original PooleBoot/PooleKernel, one-BSP QEMU/OVMF only.
This is the first native execution of the independently built PooleInit and
PooleCounter programs, not full init supervision or an interactive ISO.

## Startup And Authority

The opt-in `development-session` kernel feature uses the validated user-root boot
selector23. Other diagnostic selectors reject; the ordinary unsigned-boot denial
is unchanged. Initialization shares checked descriptors, PMM, retained ACPI and
device-mapping mechanisms. Session dispatch does not run diagnostic injections.
The default kernel still builds its full qualification path separately.

The qualifier validates cycle260's PUSERBIN1 source and byte-equality receipt,
rechecks both independently compiled code images, and supplies their paths to the
kernel build. Two independent session kernels must be byte-identical. Each exact
program byte sequence must occur once in the canonical kernel image. PSTART1 copies
the trusted built-in bytes and arguments into owned images before publication.
This is not a general ELF/PXABI1 loader or signed PINIT1 activation.

The two private roots own 26 pages total. Initial arguments carry the role and
two handle locators. Atomic IPC/scheduler admission must return the expected four
grants before either task runs; argument strings cannot create authority. The
programs execute PSABI1 send/receive/wait/exit and their own PSVC1 service policy.
The kernel does not calculate counter replies on their behalf.

## Dispatch And Failure

Each dispatch restores the task context, settles measured runtime even on a failed
slice, then parks, yields or retires it. Wait completion is identity-bound. Normal
execution has no diagnostic 64-iteration stop; per-dispatch budgets still apply.
The runner validates scheduler state, accounting and restored kernel CR3 after
every slice. Its emitted progress comes from these actual task/IPC mechanisms.

This initial two-program bootstrap declares a mutual dependency. If one task is
dead, a still-blocked wait by the dependent is explicitly cancelled. Cancellation
is repeated only for a newly blocked wait, not an already-notified runnable task.
Revocation and reap preserve existing retained-on-failure ownership. When both
tasks retire, memory must return to baseline and IPC/wait state must be empty;
the kernel remains quiescent. There is no restart or general supervision policy.
Move that policy into user space as the supervisor/launch interface is implemented.

## Timer Calibration

The initial integration timed out because every dispatch repeated calibration.
Read-only QMP register samples and disassembly localized execution to the HPET
calibration loop; progress logs and root-write counts confirmed forward progress.
Only session-owned timers now retain a checked calibration. The single-owner cache
binds the root, APIC identity/version and full HPET capabilities; mutation rejects.
The divider, mapped device context, APIC discovery and HPET configuration are still
checked each time. Every quantum still arms, accounts, quiesces and drains normally.
The default diagnostic timer keeps its previous fresh-calibration behavior and
layout; cache storage and lookup compile only into the session feature.

Five host tests cover reuse, each identity mutation, invalid measurement, invalid
context and a new owner's fresh measurement. No CPU migration, suspend/resume,
frequency drift, physical-hardware or indefinite-uptime guarantee is made. The
normal programs block on IPC and recorded zero timer preemptions; diagnostic
preemption evidence must not be relabeled as cached-session spinner qualification.

## Reproduction And Acceptance

Build programs with `tools/qualify_native_user_programs.py` into a fresh workspace
output directory. Then run `tools/qualify_native_session.py --work-dir
outputs/session-new --program-dir outputs/programs-new` with the verified local
toolchain installed. No administrative access, networked guest, host share,
physical media or host firmware access is used. Generated disk images are private
qualification inputs, not the requested optical ISO or a published demo.

Frozen bounds are 120 seconds for each of two positive guests and one malformed
startup guest, plus 45 seconds for ordinary unsigned denial. The positive oracle
requires eight ordered 64-dispatch intervals, both tasks' increasing calls and
runtime, balanced waits/wakes and actual root switches. QMP pauses the VM before
dual-channel snapshot; only complete log records count. PBP1 and retained-input
bindings must match the actual media/kernel bytes. Host marker mutations alone
are not native execution evidence.

The malformed-startup image embeds the same programs but gives counter a bad
role. Counter exits120, init exits111 after dependency cancellation, and all26
pages return with no objects or outstanding waits. Ordinary PooleBoot must still
deny the unsigned image before kernel entry. See the checkpoint and public receipt
for measured results, retained failures and default-profile regression status.

## Remaining Work

Confined console/input, interactive shell, read-only bundled files, two useful
applications and fresh optical-boot interaction remain before the integration ISO.
Console policy must run in user space with bounded device authority, input/output
backpressure and revocation. Keep untrusted console bytes on a separate channel
from trusted kernel diagnostics; application output cannot forge acceptance markers.
Expand the fixed two-task bootstrap through checked admission before adding services.
Efficient idle, full service supervision/restarts, general loading/resource policy,
native clock-fault recovery and signed production activation remain open. Both
session and diagnostic images retain the205/208-page fixed layout and36-page stack;
startup separation is not a capacity migration. Canonical product-receipt migration
and exact-candidate gates still block main. Full N0-N39, PooleGlyph/PDC and
accessible PooleGlass remain after this intermediate milestone.

Build-feature behavior was checked against the official
[Cargo feature reference](https://doc.rust-lang.org/cargo/reference/features.html).
No third-party kernel/runtime implementation was incorporated.
