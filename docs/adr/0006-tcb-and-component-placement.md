# ADR-0006: Trusted Computing Base and Component Placement

Status: accepted-owner-directed  
Date: 2026-07-16  
Decision owner: Rooke Poole  
Ratification: cryptographic signature and executable-model review pending  
Supersedes: PGVM2-as-kernel framing  
Superseded by: none  
Requirement mappings: N0.4, N4.5-N4.6, N11-N16, ADD-NATIVE-002, ADD-CAP-001, ADD-DRIVER-001  

## Decision

| Domain | Included responsibilities | Explicit exclusions |
|---|---|---|
| PooleBoot boot TCB | firmware protocols, manifest and image verification, memory-map and platform handoff, `ExitBootServices` | drivers after handoff, filesystem policy, PGVM2, PDC, UI |
| PooleKernel ring 0 | CPU privilege, faults, interrupts, timers, SMP, address spaces, page ownership, threads, neutral scheduling, IPC, capabilities, IRQ/I/O/MMIO/DMA delegation, IOMMU enforcement, minimal panic/audit | general drivers, filesystems, network/storage/USB protocols, authentication, packages, PGVM2, PDC, desktop policy |
| Initial system | bootstrap capability allocation, process/pager/service creation, policy handoff | permanent ambient authority, device protocol implementation |
| Privileged servers | process/pager policy, identity, security, VFS, update, recovery, device management, service supervision | direct ungranted hardware access, kernel-memory access |
| Driver domains | one bounded device/resource assignment, protocol execution, restart state | unrelated devices, ambient DMA, policy authority, ring 0 modules |
| Ordinary services/apps | capabilities granted by policy and user consent | ambient authority and direct privileged resources |
| PooleGlyph/PGVM2/PDC | compilation, verification, bounded execution, diagnostics, guarded routing and control services | ring 0 execution and unrestricted actuator authority |
| Recovery TCB | verified minimal boot, inspection, rollback, repair, reinstall, evidence export | automatic trust in failed normal-system state |

Capabilities are unforgeable typed kernel objects with explicit rights, derivation, attenuation, transfer, accounting, revocation, stale-handle defense, and no ambient authority. IPC is the only normal cross-domain control path. DMA-capable production drivers require an IOMMU domain and interrupt-remapping policy before device enablement.

## Consequences

Driver and server failure must be containable and restartable. The microkernel ABI and capability model become high-assurance dependencies. Performance optimizations cannot bypass capabilities or move general policy into ring 0 without a new signed ADR and revised assurance case.

## Evidence and Exit Gate

Executable capability/revocation, IPC, scheduler, page-mapping, DMA, crash, and recovery models must precede ABI freeze. Booted negative tests must prove that unauthorized operations fail, stale authority is not revived, driver crashes remain contained, and kernel state is not corrupted.

