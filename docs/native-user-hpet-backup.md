# Native User HPET Backup Deadline

PKUSER14, development single-BSP scope. This is a kernel mechanism for the
user-space integration ISO lane, not a production watchdog or ISO acceptance.

## Mechanism

Each resumable peer quantum acquires an exclusive, non-copyable lease on HPET
comparator zero before user entry. Its one-shot deadline is 50ms, behind the
normal 10ms local-APIC quantum. A physical fixed-edge MSI targets only the BSP
on vector65. No caller-supplied MSI address or vector is accepted. The lease
preserves the original configuration, comparator and route before any writes.
The native adapter publishes its owner before programming the device.

The profile requires a running nonlegacy HPET, 64-bit counter/comparator,
FSB capability, a disabled comparator, empty status and a valid xAPIC ID.
Unsupported hardware is rejected, not silently converted to external timeout.
Programming checks its deadline both before and after enabling the comparator;
overflow, missed programming deadlines, regression and register drift reject.

Vector65 authenticates the user root, selectors, private entry stack and trap
depth. It checks elapsed time and the actual in-service vector, stops both
sources and records a Watchdog outcome without resuming the offending frame.
The existing retained slice and scheduler account this terminal quantum once.
Cleanup disables comparator production, drains only owned vectors64/65 through
the bounded kernel window, verifies empty APIC state, then restores the original
HPET registers before releasing descriptors, roots or pages. Failure keeps the
owner available for retry; no successful application exit is fabricated.

## Invariants

| ID | Predicate | Verification |
| --- | --- | --- |
| HPET-1 | Only an eligible inactive comparator is acquired | Host capability/ownership denials; native preparation |
| HPET-2 | Original registers have an owner before any device effect | Private non-Copy lease; native publish-before-arm; eight post-effect failure cases |
| HPET-3 | Route is fixed to the owned BSP/vector, not caller authority | Host destination matrix; native APIC ID read |
| HPET-4 | No wrap, stale or already-missed deadline grants user entry | Checked arithmetic, before/after-enable sampling, host perturbations |
| HPET-5 | Only an authenticated CPL3 envelope terminates a task | Host root/depth/selector/stack/error/vector denials; actual vector65 ISR check |
| HPET-6 | Backup termination contributes one retained runtime charge | Existing exact-once settlement; per-round and global native conservation |
| HPET-7 | Both sources stop and drain before restore or detach | Host dual-vector/foreign-vector tests; native shutdown order and idle checks |
| HPET-8 | A missing local timer cannot starve the declared peer | Native masked-LVT readback, spinning payload, backup termination and peer exit84 |
| HPET-9 | Every successful arm has exactly one stop and restore | Native lifecycle counters equal settled dispatches |
| HPET-10 | Evidence does not promote unsupported hardware or production | Explicit launch option, independent marker parser, ordinary denial and roadmap assertions |

## Hardware Profile And Alternatives

The qualification launcher opts into the allowlisted boolean `hpet_msi=True`,
which adds only `-global hpet.msi=on`. Default launchers remain unchanged.
Both fresh user probes and the ordinary unsigned-denial control use that option.
It is recorded in receipts; the guest still validates its actual capability.
Pinned QEMU reports v11.0.0-12122-ga4bb4b10c9. Upstream v11.0.0 source inspection
identified MSI as optional and off by default; that upstream source is not
claimed to be the exact fork source or a replacement for runtime verification.

Alternatives considered: the same local timer cannot cover its own suppression;
HPET via I/O APIC needs routing/trigger/ownership work; PIT requires legacy IRQ
routing and offers weaker resolution; PMU NMI needs per-model availability and
precise interrupted-kernel policy; an external VM timeout cannot restore guest
peers. HPET MSI is selected only for the declared emulator profile. A frozen or
misread HPET, broken APIC delivery or IF0 kernel hang remains a counterexample
to any claim of a generally independent watchdog.

## Remaining Work

- I/O-APIC fallback, non-MSI/32-bit timer platforms and physical qualification.
- NMI-based recovery, interrupt-disabled kernel hangs and shared-APIC failure.
- Coherent physical counter reads, reset/drift and wrap-safe clock policy.
- Unknown-measurement emergency accounting and retained-resource recovery.
- Live simultaneous pending local/backup delivery, arbitrary silicon after-mask
  races and partial timer-configuration recovery. Host dual-source tests do not
  constitute native evidence for all races.
- General executable admission, persistent quarantine, full stack/exception,
  extended-state, SMP/async qualification, capability IPC and real services/apps.

The first delivered user integration ISO remains a bounded intermediate product.
Full N0-N39 microkernel, PooleGlyph/PDC services and PooleGlass work remains required.

## Primary References

HPET capability, configuration, comparator and FSB-route register definitions:
[Intel HPET 1.0a, sections2.3.4 and2.3.8-10](https://www.intel.com/content/dam/www/public/us/en/documents/technical-specifications/software-developers-hpet-spec-1-0a.pdf).
Physical MSI destination and fixed-vector delivery:
[Intel SDM volume3A, Message Signalled Interrupts](https://www.intel.com/content/dam/www/public/us/en/documents/manuals/64-ia-32-architectures-software-developer-vol-3a-part-1-manual.pdf).
Emulator capability/property inspection:
[QEMU v11.0.0 HPET implementation](https://github.com/qemu/qemu/blob/v11.0.0/hw/timer/hpet.c).
No external implementation is copied into the native kernel.
