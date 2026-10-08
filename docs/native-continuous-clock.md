# Continuous Service Clock

Cycle255 / PKCLOCK1. This is a prerequisite for request deadlines, not a timed IPC
implementation or a user clock ABI. Qualification is recorded separately in the
Cycle255 checkpoint. Existing request calls10-13 remain unchanged.

## Ownership

`user_entry::timer::clock::Lease` owns a continuous 64-bit HPET counter epoch,
independent of a task's charged CPU quantum. Prepare validates the hardware
revision, counter width, period, disabled legacy routing and idle comparators.
The privileged adapter publishes its non-copyable owner before enabling the
counter, preserves every unrelated configuration bit and never resets the counter.

A serialized child timer may arm its own comparator but cannot acquire the global
configuration or reset/stop the parent counter. Each dispatch checks the exact
root, PAT and physical device plan, samples the parent before calibration, and
samples again only after child shutdown, interrupt drain and register restoration.
The parent retains ownership across task termination and allocator reuse.

Elapsed nanoseconds are calculated from `(raw - origin) * period_fs / 1_000_000`
using a 128-bit intermediate and checked narrowing. Equal samples are valid at
sub-counter resolution. Absolute conversion retains fractional progress across
samples. Regression, overflow, changed capabilities/configuration or a failed
read poisons the epoch; later samples cannot fabricate a time value.

## Mapping Lifetime

Task construction and revalidation continue to require the original boot supervisor
mapping, including absent bootstrap MMIO leaves. The parent therefore uses six
short kernel mapping windows in the native probe: acquisition, four idle intervals
and release. Its counter keeps running while these aliases are absent. Tasks use
their independently validated supervisor-only UC/NX device mappings.

Every kernel window uses the existing guarded mapping adapter. Removal verifies
both raw device leaves are zero and an independent page-table walk reports missing
translations. Before dropping the parent, the complete temporary/metadata/ledger/
MMIO reserved region must be empty. The RAM-mapping `TableMemory::finish` contract
does not apply to this MMIO-only owner.

The parent releases only after no child or task entry remains active, the IPC
space is empty, and APIC ISR/IRR and HPET interrupt sources are idle. Failed
register writes may have taken effect: the lease remains available for cleanup
retry. This development adapter halts on uncertain ownership instead of pretending
to provide general service recovery.

## Qualification Boundary

The native probe must preserve all earlier containment and request cases, execute
twelve clock-owned dispatches, prove four bounded idle advances after both tasks
have retired, restore the original configuration, and revoke six mapping windows.
Raw origin/last counter, period, elapsed nanoseconds, samples and idle time are
bound by a separate Python oracle. Task CPU accounting remains separate; its
historical unmeasured dispatch stays unknown.

This does not qualify physical hardware, SMP clock synchronization, 32-bit wrap
extension, suspend/resume, wall time, NMI recovery or independent stopped-clock
detection. No clock epoch can be reused as authority for requests after teardown.
The current polling bound detects a non-progressing idle experiment, not every
possible physical clock failure.

Next: bind caller-owned request deadlines to this epoch, expire them before late
reply/cancel decisions and while all tasks are blocked, preserve first-terminal-
wins, wake once, and retain failed-clock/teardown ownership. Then transactional
service admission, sustained budgets, init/console/input, shell/files/two apps and
the optical integration ISO. Full production microkernel development continues.

## Reference

The [Intel IA-PC HPET Specification 1.0a](https://www.intel.com/content/dam/www/public/us/en/documents/technical-specifications/software-developers-hpet-spec-1-0a.pdf),
sections2.3.4-2.3.8, defines the capability, global enable, counter and comparator
registers. In particular, disabling global enable halts the main counter; equal
consecutive reads can occur below its resolution. These hardware semantics inform
this implementation, not an external validation or certification of PooleKernel.
