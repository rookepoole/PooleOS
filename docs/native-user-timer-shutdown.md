# Native User Timer Shutdown

PKUSER12 is a bounded, exclusive one-BSP xAPIC one-shot timer shutdown mechanism.
It extends USI-1; it is not an interrupt-controller framework or a kernel watchdog.

## Mechanism

Masking the LVT or software-disabling the APIC does not prove that queued work is
gone. Intel describes pending IRR/ISR state surviving software disable and EOI
clearing the highest-priority in-service request. See the
[Intel SDM Volume 3A, sections10.4.3,10.8.4-5](https://www.intel.com/content/dam/www/public/us/en/documents/manuals/64-ia-32-architectures-software-developer-vol-3a-part-1-manual.pdf).
Therefore this mechanism does not blindly EOI or discard an occupied ISR.

The owning driver masks sources and stops the count, then validates exact LVT
vector/mode, initial/current counts, all IRR/ISR banks, edge-triggered timer state
and delivery/EOI accounting. An unrelated pending vector or any outside-handler
ISR occupancy rejects before enabling interrupts. Device/memory ownership remains
held when an operation fails, including failures after effects.

A small assembly window records its kernel RSP, executes STI/NOP/NOP/NOP/CLI and
returns with IF clear. The early dispatcher handles this path before normal user
dispatch. It authenticates the exact root lease, kernel selectors, saved IF,
depth, RIP interval, saved RSP and handler stack location. It acknowledges only
the exclusively owned timer ISR. It cannot dispatch or resume a user frame.

The window opens even after an initially empty pending snapshot. At most32 windows
are attempted; more than two drain deliveries, inconsistent counters or persistent
pending/sending state reject. A successful drain is followed by device shutdown
readback and an empty IRR/ISR check before dispatch authority is revoked. Only
then may user descriptors detach, the root retire, and retained pages be released.

## Acceptance Invariants

- TD1: root, timer mappings, descriptors and stack remain owned through shutdown.
  Verify native quarantine state, exact CR3, attached user entry and retained frees.
- TD2: no foreign pending/in-service work is acknowledged. Test all255 foreign
  vectors and unowned timer ISR in the shared host policy; inspect the live handler.
- TD3: actual pending and post-snapshot timer arrivals drain at CPL0/IF0 boundaries.
  Require real APIC IRR and native delivery/EOI counts, not synthetic transcript.
- TD4: failed cleanup prevents restart/reap/free and a bounded retry can finish.
  Require one native failed window,13 retained pages,five free denials,two restart
  denials,one reap denial and a surviving peer exiting84.
- TD5: every prior construction/containment case and default unsigned denial stays
  required. Qualify two fresh native guests and independent hostile marker checks.
- TD6: no ISO, general admission, timing completeness or production claim follows.
  Preserve charter, phase/flag status, immutable older receipts and owner inputs.

## Evidence Scope

Host policy cases cover idle/pending/late delivery, all unrelated vectors, stale
in-service timer state, device shape, accounting mismatch, missing delivery,
delivery-status persistence and failures after stop/delivery effects with retry.
The live late case first observes empty IRR, then forces a real one-shot timer
arrival before stop. It does not establish every silicon pipeline delay after
masking. The native failure is an injected window error, not a claim of real
hardware failure. The failed task is abandoned after recovery, not restarted.

The new round adds a quarantined quantum whose execution result is not committed
to the scheduler. Its displayed zero accepted preemptions/runtime is not zero CPU
consumption. Terminal and failed-cleanup runtime accounting is the next dependency.
Generic persistent hardware faults, ambiguous ISR recovery, partial configuration
failure recovery, full stack bounds, native #SS, SMP/XSAVE/SMAP/async and independent
missing-IRQ recovery remain open. External test bounds are not kernel watchdogs.

## Test Bound Revision

The initial90-second fresh boot timed out after the original14 rounds. A separately
labeled180-second diagnostic used the exact unchanged candidate/media and finished
all15 rounds in93.844s. That diagnostic is not qualification. Before new fresh
qualification, the expanded test's bound is frozen at120seconds; default unsigned
denial remains45seconds. No payload loops, containment cases, device checks or
success criteria are removed. The failed run and diagnostic are preserved.
