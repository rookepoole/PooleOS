# PKIRQ1 Native Interrupt and Time Substrate

## Status

PKIRQ1 is the Cycle 135 bounded one-BSP implementation slice for N8.1 and N8.3. It is pre-production development evidence. It does not close `FLAG-N8-IRQ-001`, N8, or any production gate because no application processor is started and no real IPI, SMP shootdown, I/O APIC route, MSI/MSI-X lease, public clock API, or physical-target run exists.

The authoritative machine-readable contract is `specs/native-kernel-interrupt-time-contract.json`. The exact qualification receipt is `runs/native-kernel-interrupt-time-readiness.json`.

## Implemented Boundary

The opt-in `development-interrupt-time` PooleBoot feature passes selector 11 in `R10`. The ordinary PooleBoot profile remains a permanent stop-before-transfer path. PBEXIT1 validates the shared bounded development-selector range; PKIRQ1 accepts only its own selector. Other explicitly built development features, including selector 12 first-AP startup, have separate qualification contracts and do not expand this profile.

PooleKernel re-executes PKPMM7 to obtain the already copied and read-back-verified PKACPI1 snapshot. PKIRQ1 then walks the entire MADT without AML execution. It recognizes local APIC, x2APIC, I/O APIC, interrupt-source override, NMI source, local APIC NMI, local APIC address override, and x2APIC NMI structures. Known structures require exact lengths. Reserved flag encodings, duplicate processors, duplicate I/O APIC IDs, duplicate bus/source overrides, duplicate LAPIC address overrides, invalid LINT values, unaligned addresses, capacity exhaustion, missing processors, and a missing enabled processor fail closed. Unknown structures are counted and skipped only by their validated declared length.

The HPET table parser accepts only system-memory GAS descriptions with bounded 64-bit register shape, alignment, access size, minimum tick, and page-protection values. The retained snapshot remains the source of table bytes; the profile does not dereference reclaimed firmware table pages.

## Mapping And Controller Transaction

PKMAP2 reserves the following absent leaves in its shared two-leaf retained layout. These are global 4 KiB page indices, not indices within one leaf table:

| Leaf | Purpose |
|---:|---|
| 514 | low MMIO guard |
| 515 | local APIC |
| 516 | middle MMIO guard |
| 517 | HPET |
| 518 | high MMIO guard |

The LAPIC and HPET leaves are installed as supervisor RW/NX with PWT=1, PCD=1, and PAT=0. Translation readback must prove the exact physical target, permissions, and effective uncacheable bits. All three guards must remain absent. Only those two simultaneous mappings are allowed, and both are revoked and independently re-walked before the terminal result.

With IF clear, PKIRQ1 validates CPUID APIC support, rejects active x2APIC mode, binds IA32_APIC_BASE to the MADT address and CPU physical width, and binds the MMIO APIC ID to the CPUID initial ID and an enabled MADT local-APIC processor. It saves IA32_APIC_BASE and the APIC task-priority, spurious, timer, thermal, performance, LINT0, LINT1, error, divide, and initial-count registers. It saves HPET configuration and both legacy PIC masks. When MADT declares PCAT compatibility, both PICs are masked and read back before local APIC operation.

The vector ledger reserves exceptions 0-31, timer 64, future IPI vectors 224-239, APIC error 240, and spurious 255. Duplicate ownership fails closed. Future IPI vectors are reservations only; no IPI is sent.

PKIRQ1 masks the relevant LVTs, enables the local APIC software bit with vector 255, clears the error-status register through its required write pair, sets divide-by-16, and calibrates a masked one-shot LAPIC timer over a bounded ten-millisecond HPET interval. It then installs the timer/error/spurious gates and opens exactly eight `sti; hlt; cli` windows. The timer and APIC-error handlers write EOI; the spurious handler does not. Success requires exactly eight timer deliveries, eight EOIs, zero APIC errors, zero spurious deliveries, and zero remaining ISR bits.

## Time Arithmetic

`HpetClock` supports 32-bit and 64-bit counters. Every sample is bounded to at most half the counter range, so a 32-bit wrap is unambiguous. A 64-bit backward sample is rejected as regression. Elapsed ticks and femtosecond products use checked `u128` arithmetic, and conversion must fit `u64` nanoseconds.

APIC calibration accepts only one-to-one-thousand-millisecond samples and frequencies from 100 kHz through 10 GHz. Timer count derivation uses checked arithmetic, rounds any nonzero sub-tick interval to one, and saturates at `u32::MAX`. This is a local development clock. It is not invariant-TSC calibration, a watchdog, timer queue, TSC-deadline implementation, or a public time API.

## Restore Boundary

On the successful path, interrupts are disabled before rollback. PKIRQ1 masks the timer, restores every saved APIC register, restores HPET configuration, restores both legacy PIC masks with readback, restores IA32_APIC_BASE if it changed, revokes both MMIO leaves, verifies all mappings and guards absent, and emits the terminal marker with IF clear.

Normal-path exact restore is qualified. Panic-time recovery after every possible partial controller or clock mutation is not yet qualified. A fatal mid-transaction failure currently halts; comprehensive recovery journaling is required before this code can promote.

## Reproduction

From the repository root, using only the pinned workspace-local Rust and QEMU/OVMF inputs:

```powershell
python tools/qualify_native_kernel_interrupt_time.py
python -m unittest tests.test_native_kernel_interrupt_time
```

Qualification requires two byte-identical clean PooleKernel builds, two byte-identical feature-enabled PooleBoot builds, two deterministic ordinary-file media generations, two fresh-variable qemu64 TCG executions, exact marker/screenshot/PBP1 equality, independent boot and handoff binding, all 214 current kernel host tests, and all 58 hostile controls.

The Cycle 157 replay candidate is the unchanged retention-capable Cycle 153
kernel: 517,784 canonical bytes, a 589,824-byte/144-page image, and SHA-256
`BDEECCB27B1B91406911F91169B9BF5F9DF0439BB39FA0E1882C07E1AF3B81EF`.
Current-source acceptance requires a fresh receipt bound to this documentation
and the implementation. Historical profile success is not that acceptance.

## Nonclaims

The measured qemu64 APIC version, HPET period, APIC frequency, ACPI structure counts, and MMIO addresses are emulator-profile facts. They are not AMD Ryzen 7 9800X3D facts. No AP startup, per-CPU area, IPI, TLB shootdown, I/O APIC programming, external IRQ, NMI delivery, MSI/MSI-X, affinity, capability delegation, interrupt remapping, scheduler tick, user delivery, firmware mutation, physical-media write, signature, authority grant, release, or production promotion follows from PKIRQ1.
