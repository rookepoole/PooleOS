# Cycle 238: Owned Root Timer Recovery

Date: 2026-10-08. Pre-production. USI-1 / N9/N12/N13.3,
`N13-USER-ENTRY-LIVE-001`, `FLAG-N13-USERSPACE-ISO-001` remains open.
No production phase or checklist item closes.

## Implemented

PKUSER4 extends the owned task root with APIC and HPET leaves at private
supervisor PT slots 16 and 18. Adjacent slots 15/17/19 remain unmapped.
PTEs are supervisor RW/NX, non-global and strongly uncached through observed
PAT entry 3. Addresses must be distinct, aligned, within the CPU physical width,
and disjoint from non-MMIO handoff ranges, PMM-managed RAM and all inherited
kernel/boot/table/stack/handoff ranges. Preparation and preactivation replay
audit the complete mapping, including guards. Inactive cleanup clears the leaves.
An immutable mapping plan is not device authority; the private privileged
adapter owns the serialized one-BSP ACPI/APIC/PAT/device lease.

CpuImage marks timer exposure before invoking the trusted driver. Success or
failure runs shutdown; uncertain shutdown prevents CR3 restoration, detachment
and allocator release. A verified same-CPU/root retry can recover. Malformed
delivery/EOI/root observations still reject after safe shutdown. Dropping an
unresolved owner preserves allocator retention.

The native probe validates and snapshots ACPI through the existing bounded
consumer, parses MADT/HPET, revokes temporary bootstrap aliases and requires a
single enabled BSP, supported already-enabled xAPIC, matching device identity,
supported LVT shape, supported PAT and HPET counter width/period. It rejects
legacy HPET routing or enabled comparator interrupts. No AP or DMA is started.

The driver masks the legacy PIC and other LVT sources, calibrates the APIC
against HPET, then receives three one-shot interrupts while candidate CR3 is
active. The interrupt handler reads actual CR3 and checks the expected timer
vector, existing kernel descriptor/IST frame, depth and EOI accounting. Every
interrupt window returns with IF clear. Native polling is bounded by both a
finite iteration count and HPET elapsed time; no unbounded HLT is used.

Shutdown masks/readbacks all supported LVT sources, writes/readbacks zero initial
and current counts, requires empty pending/in-service banks, matched delivery/EOI
counts, no error/spurious deliveries and zero trap depth, disables the local
APIC software-enable bit, restores HPET configuration and clears dispatch
authority. The PIC remains masked. This is a development handoff to halt, not
a general device-state restoration protocol. Only verified shutdown permits
the original-root flush and release of the 13 task pages.

The ACPI snapshot is a separate release-excluded allocation: one page remains
retained in each tested guest. Attempted free correctly rejects as metadata
ownership. Resource accounting no longer claims zero total allocated pages.

## Evidence

Current receipt: `runs/native-user-entry-readiness.json`, SHA-256
`73D1664F988357FC457006627277FFFC3B1036808566476B7DB5B1E55A0ED45F`.
It binds 736 native/build/oracle inputs. Retained capture:
`outputs/cycle238-nativefirst.json`, 95.641 seconds, unchanged sources and
PooleGlyph owner report; log SHA-256
`0F4955E9CCF0E1A8A793AE3CD5C9812809CF1378A3E7092E6AD69A40D24CB9EC`.

- 300 debug kernel tests, 54 repeated optimized user-entry tests, five ownership
  compile-fail tests and ten boot-exit tests pass. These are 369 test executions,
  not 369 distinct cases. Twelve new Rust tests cover MMIO policy/layout,
  corruption/aliases, lifecycle ordering, failure quarantine/retry, context
  drift, malformed observations and absence of timer authority.
- 15 Python oracle tests pass, including actual-value corruption of timer root,
  delivery/EOI/quiescence and retained-ACPI accounting. Parser tests use a clearly
  labelled synthetic extension of the immutable Cycle 237 fixture, not claimed
  current execution.
- Formatting, freestanding library/kernel checks and two conflicting-feature
  compile-error controls pass.
- Two fresh headless TCG/OVMF probes each produce 33 matching serial/debugcon
  markers, including three timer deliveries/EOIs and verified quiescence. All
  35 field/order/selector marker mutations per run reject. A third default boot
  still denies unsigned transfer, with no development kernel entry.
- Fresh firmware variable copies, read-only virtual media, no guest networking
  or host acceleration, loopback QMP and 45-second guest bounds are retained.
  Both PooleBoot variants reproduce across two clean local builds; generated
  virtual disk bytes repeat and pass independent inspection. This is not a
  distributed ISO or two-independent-builder OS reproduction.

The canonical kernel remains 583,320 bytes / 160 image pages, SHA-256
`55C654291448DD5DEF53C25AC8F7162CFCFF6AC933CBDD386A47B97E90A37B56`.
No linker limit or memory permission was relaxed in this cycle.

Two initial local compile checks exposed an APIC-offset integer type mismatch
and missing test-module imports/constant. They were repaired before the captured
qualification; no guest was attempted in those failed compile checks. The first
complete captured host/freestanding/guest run passed. No failed guest run is
being replaced with host-model success.

Historical Cycle 237 readiness is frozen byte-for-byte at
`tests/fixtures/cycle237-user-entry-readiness.json`, SHA-256
`9D4AF96F0267010526F7BED917CF12546410379AB2EF97432244349E90AD3BCA`.
Older receipts and the retained execution-source ledger remain unchanged.

Implementation references: [Intel SDM, APIC timer and memory-type definitions](https://cdrdv2-public.intel.com/868137/325462-089-sdm-vol-1-2abcd-3abcd-4.pdf)
and [Rust freestanding x86-64 target](https://doc.rust-lang.org/rustc/platform-support/x86_64-unknown-none.html).
The timer uses masked delivery plus a zero initial count to stop, then verifies
pending/in-service state separately. The pinned freestanding target uses a
soft-float/no-red-zone ABI. This bounded kernel interrupt path does not establish
user extended-state isolation; that remains required before ring-3 execution.

## Boundaries And Next Move

Actual timer delivery remains CPL0 on the existing kernel IST. The guarded
private stack is only accessed as data; it is not yet installed as task RSP0.
No ring-3 execution, sanitized user architectural state, user fault containment,
syscalls, capability IPC, services, shell, apps or new optical ISO is claimed.
Shutdown failures are exercised with host drivers, not fault-injected into QEMU
hardware. General MMIO/device authority, SMP timers, IOAPIC routing, DMA/IOMMU,
physical-machine support and sustained preemption remain open.

Next: user descriptors/TSS and reviewed IRETQ entry with sanitized registers,
segment/base/debug/extended state; demonstrate actual user entry/return and
contained fault/timer recovery. Then integrate IPC, isolated services and the
interactive shell/apps into the requested bootable ISO. The full robust native
microkernel program continues after that milestone.

All 8,996 locked requirements, 59 additions, 40 phases, 301 subphases, 97 flags
(42 open) and 20 native gap categories remain. PooleGlyph Phase 65 and the
owner-modified conformance report were inspected without modification; Phase 66
is not implemented here. The 25 stale native admissions and 22 stale Python
source closures remain stale; boot-trust/ELF prerequisites are pending and the
firmware prerequisite still passes. Full exact-candidate canonical qualification
has not run. This focused pass does not authorize merge or production promotion.

Initial metadata replay passed 98/101 tests in 49.152 seconds (capture 49.968),
with unchanged source/owner data. Three failures identified two omissions: the
roadmap schema still required Cycle 237, and the historical source delta did
not name the two new Rust modules. These expectations were reconciled without
rebinding old execution evidence. Failed log:
`28F210DDA41B258EC84E3CF48BCD7685046C3A35BB1EA1169374287ECBA525CA`.

Corrected metadata replay passes 101/101 in 48.658 seconds (capture 49.484),
with unchanged source and owner report; log
`27C1DAA43925B3E2A1DDEE07ACF07262EA4BB20507B028661D3039A2B37D8513`.
The architecture baseline binds 437 files. Discovery finds 1,256 Python test
methods; this inventory is not a claim that the full suite executed.
