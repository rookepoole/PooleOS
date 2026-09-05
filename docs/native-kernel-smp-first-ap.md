# PooleKernel PKSMP1 First-AP Qualification

Status date: 2026-09-05
Selected move: `N8-SMP-FIRST-AP-001`
Contract: `PKSMP1`
Status: bounded qemu64 two-vCPU evidence; non-promoting

## Scope

PKSMP1 is PooleKernel's first executed application-processor lifecycle. Selector 12 is available only in the separately built `development-smp-first-ap` PooleBoot profile. The ordinary PooleBoot product still stops before transfer.

The BSP consumes a checksum-validated `PKACPI1` snapshot after explicitly advancing its new physical-memory manager to the validated post-`ExitBootServices` stage. It selects the lowest enabled non-BSP xAPIC processor from the MADT and rejects x2APIC targets in this profile.

## Bootstrap Resources

One scrubbed 14-page DMA allocation starts at physical `0x1000`:

| Page offsets | Role | AP permissions |
| --- | --- | --- |
| 0 | 336-byte 16/32/64-bit trampoline and private GDT | RX |
| 1-4 | PML4, PDPT, PD, PT | not mapped as AP leaves |
| 5, 10 | stack guards | absent |
| 6-9 | 16 KiB AP stack | RW, NX |
| 11, 13 | per-CPU guards | absent |
| 12 | 96-byte per-CPU mailbox | RW, NX |

The AP page tables identity-map only the trampoline, four stack pages, and one per-CPU page. All four guards are walked as absent. The BSP's temporary high alias is revoked during cleanup.

## Startup And Stop

The BSP sends one asserted INIT, one deasserted INIT, and two SIPIs with HPET-bounded waits. The AP executes real mode, protected mode, and long mode; installs the private root and stack; then records APIC identity, `CPUID.1`, `CR0`, `CR3`, `CR4`, `EFER`, and ordered TSC samples.

The trampoline page remains RX. Its four code/data descriptors have their architectural accessed bits pre-set. This is required because loading a clear-accessed descriptor can cause the processor to write the GDT. During development, QEMU exposed that condition as `#PF(error=0x3, CR2=0x11A4)` followed by a triple fault. Pre-setting the bits fixes the architectural cause without making executable memory writable.

After the AP reports online, the BSP writes the stop command and waits for quiescence. It recomputes the FNV-1a-64 mailbox checksum, validates identity, feature and control state, sends a final INIT to park the AP, restores HPET and PIC state, revokes mailbox and controller aliases, and scrub-releases all 14 pages. A failed final park retains the AP resources and fails closed.

## Evidence Boundary

The qualifier requires two clean kernel builds, two clean PooleBoot builds, two identical media generations, and two fresh QEMU/OVMF runs with two virtual CPUs. Static markers, screenshots, and PBP1 bytes must match. TSC values are dynamic; each run independently validates order and its dependent mailbox checksum before those three fields are normalized for the static-marker comparison.

Seventy-two hostile controls cover marker shape and ordering, topology, low-memory geometry, W^X/NX/guards, startup counts, AP identity and control state, TSC/checksum integrity, final park, complete cleanup, claim overreach, the GDT accessed-bit regression, x2APIC rejection, and missing-target rejection.

The Cycle 157 replay candidate is the unchanged retention-capable Cycle 153
kernel, with 214 host tests, 517,784 canonical bytes and a 144-page image,
SHA-256 `BDEECCB27B1B91406911F91169B9BF5F9DF0439BB39FA0E1882C07E1AF3B81EF`.
Acceptance requires fresh runs bound to these exact inputs; it does not inherit
historical first-AP qualification or prove general concurrent ownership.

## Non-Claims

This is one AP running a bounded bootstrap mailbox loop. It does not provide general SMP, per-CPU descriptor completion, IPI services, TLB shootdown, remote PKVM3 retirement, scheduling, migration, hotplug, NUMA, x2APIC, physical-target evidence, N8 completion, or production readiness. It grants no authority and performs no signing, firmware mutation, release publication, or physical-media write.
