# ADR-0004: Product Names and Version Namespaces

Status: accepted-owner-directed

Date: 2026-07-16  
Decision owner: Rooke Poole  
Ratification: owner-directed acceptance recorded; cryptographic signature and trademark review pending

Supersedes: none  
Superseded by: none  
Requirement mappings: N0.3, section 000.3  

## Context

Boot, kernel, IPC, driver, storage, package, update, recovery, PDC, and PooleGlyph boundaries require separate version namespaces. Reusing one product version for incompatible wire and disk formats would make recovery and rollback unsafe.

## Proposed Decision

| Role | Canonical name | Machine namespace |
|---|---|---|
| Product | PooleOS | `POOLEOS` |
| Bootloader | PooleBoot | `PBOOT` |
| Kernel | PooleKernel | `PKERNEL` |
| Boot protocol | Poole Boot Protocol | `PBP1` |
| Kernel object ABI | Poole Kernel ABI | `PKABI1` |
| Syscall ABI | Poole System ABI | `PSABI1` |
| IPC ABI | Poole IPC | `PIPC1` |
| Driver protocol | Poole Driver Protocol | `PDRV1` |
| User ABI | Poole User ABI | `PUABI1` |
| Executable ABI | Poole Executable ABI | `PXABI1` |
| Filesystem | PooleFS | `PFS1` |
| VFS protocol | Poole VFS | `PVFS1` |
| Package format | Poole Package | `PPKG1`, `.ppkg` |
| Package command/service | poolepkg | `poolepkg` |
| Service supervisor | PooleInit | `PINIT1` |
| Update format | Poole Update | `PUPD1` |
| Recovery environment | PooleRecovery | `PREC1` |
| Desktop shell | PooleGlass | `PGLASS1` |
| Receipt format | Poole Receipt | `PRCP1` |
| System manifest | Poole System Manifest | `PSM1` |
| ISO manifest | Poole ISO Manifest | `PISO1` |
| Crash format | Poole Crash Record | `PCRASH1` |
| Language bytecode | PGB2 | `PGB2` |
| Language VM | PGVM2 | `PGVM2` |

PDC services use descriptive identities `pdc-refd`, `pdc-routed`, and `pdc-controld`; names do not grant device authority.

Each namespace has its own major/minor compatibility policy. Every binary or wire object starts with magic, format version, header size, total size, flags, and integrity fields appropriate to its threat model. Unknown major versions fail closed; unknown optional minor fields are accepted only when length-delimited and policy permits. Persistent and wire fields use explicit little-endian fixed-width types. Rust-native layout is forbidden.

## Consequences

The proposed names reserve implementation space without claiming trademark clearance. Renaming before public binary compatibility is cheaper than after N5, N13, N19, N23, or N39 artifacts ship.

## Evidence and Exit Gate

Owner acceptance, conflict and trademark research, generated constant registries, duplicate/magic collision tests, and independent ABI fixtures are required before this ADR becomes accepted.
