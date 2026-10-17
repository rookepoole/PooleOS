# Native Surface Lifecycle

Cycle299 development integration of PWS1, PPROC1 and PCOMP1. This is not a new
production ABI or a complete graphical desktop. The ordinary four-page window
binary remains separate from the explicit seven-page `PooleWindowLifecycle`.

## Authority And Atomicity

Trusted launch preflights an Inspect-only observer lease for the window service.
The parent's InspectTerminate lease and child IPC/scheduler admission retain the
existing failure-atomic transaction. Observer commit follows only successful
admission under the same exclusive BSP operation, without allocation, callback
or dispatch. User-requested extra Process grants remain rejected. Four total
process leases and two leases per owner remain the limits.

A completed, revoked, detached old observer may be replaced for a strictly newer
child generation. Failure preserves the old observer and scheduler state. A
spent lease generation, ambiguous observer, live old child, forged owner or
missing observer blocks admission. This exclusive-BSP proof must be revisited
before concurrent launch or SMP dispatch is enabled.

The opt-in `development-window-lifecycle` syscall27 takes a task slot and
generation only as a selector within an already-held exact Inspect lease.
No supplied identity creates authority. Reserved arguments must be zero;
invalid/future identities and ambiguous or forged authority fail closed.
There is no compositor termination right. Ordinary profiles reject syscall27.

## Window Policy

At most two read-only queries per poll run independently of a pending PWS1
reply. Both observations are validated before either surface changes. Exact
PCOMP1 terminal completion, detached state or a superseded observation makes
the corresponding generation unavailable. The last two are NOT proof that
physical memory reclamation completed.

Retirement clears the matching surface cells and handle, retains its generation
tombstone, removes the window/taskbar entry, and restores surviving focus.
Old OPEN/WRITE requests cannot resurrect it; old retirement cannot close a
new generation. Closing a dragged window preserves the consumed button press
until release, preventing a held press from clicking through to another window.
Restarted applications publish through fresh kernel-attested IPC generations.

## Evidence And Remaining Work

Acceptance invariants SL1-SL6, actual attempts, failures and test outcomes live
in [the checkpoint](checkpoints/cycle299-surface-lifecycle.md). Six native pixel
barriers must corroborate fault removal, restart, stop removal, restart and
both final stops with exact task-generation kernel records. The device scenario
also retains 17 pointer steps and 573 keyboard bytes in single/four-byte modes,
240-second guest bounds, 12-second observation bounds and owned VM cleanup.

Host tests alone do not establish native behavior. Native lifecycle stress
during active drag/focus, compositor restart/resynchronization, service
separation, general application input, launch controls, useful editable apps,
native overflow/reset telemetry and accessible PooleGlass remain open.
No signing, release, production, physical-device or phase-completion claim.
