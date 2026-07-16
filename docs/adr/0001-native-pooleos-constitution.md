# ADR-0001: Native PooleOS Constitution

Status: accepted-owner-directed  
Date: 2026-07-16  
Decision owner: Rooke Poole  
Ratification: cryptographic signature pending  
Supersedes: Cycle 1-79 Linux/Buildroot production assumption  
Superseded by: none  
Requirement mappings: N0.1, N0.4, N0.5, N0.8, sections 000.2, 000.3, 001.2, 001.3, 170, ADD-NATIVE-001  

## Context

Earlier PooleOS work proved PGB2, PGVM2, PDC, capability-simulation, and Buildroot/QEMU evidence paths, but it did not create a native operating system. Rooke Poole clarified that PooleOS must have its own UEFI boot process and native microkernel rather than being a Linux distribution or appliance.

## Decision

PooleOS v1 is an original x86-64, little-endian, UEFI-only operating system composed of:

1. a Poole-authored PE32+ UEFI application named PooleBoot;
2. a Poole-authored capability-based microkernel named PooleKernel;
3. a Poole-authored native user ABI, initial system, system servers, driver-domain protocol, storage and network services, application platform, recovery system, installer, and image tooling;
4. PooleGlyph, frozen PGB2/PGVM2 execution, canonical PDC services, and guarded computational backends; and
5. the accessible PooleGlass compositor, desktop, and boot identity.

Linux, Debian, Buildroot, GRUB, Limine, systemd, and Linux userspace are prohibited production substitutes. They may be host tools, references, compatibility targets, or historical evidence only. A release-media conformance check must reject their production markers.

PooleKernel contains privileged mechanisms, not general product policy. General drivers and services run in isolated user-space protection domains. Production loadable kernel modules are prohibited in v1.

## Alternatives

- Debian or Buildroot derivative: rejected because it would not satisfy the owner-directed native architecture.
- Monolithic native kernel: rejected for v1 because it would place general drivers and services inside the TCB.
- Third-party bootloader: rejected for production; useful only as a comparison oracle.
- Legacy BIOS support: rejected from v1 scope.

## Consequences

The native path requires PooleBoot, PooleKernel, ABI, driver, storage, network, graphics, installer, recovery, update, and release work that prior host evidence did not implement. Historical evidence remains valuable but cannot promote a native phase. Architecture phases N0-N5 outrank downstream optimization while open.

## Evidence and Exit Gate

The current goal, Production Goal Charter, Build Plan, PooleKernel Charter, machine constitution, and architecture-conformance policy must agree. Promotion requires owner-controlled cryptographic ratification and passing conformance tests over exact release-media contents.

## Open Items

- `OWNER-SIGN-ADR-0001`: bind this ADR to an owner-controlled signature or signed tag.
- `N3-TOOLCHAIN-001`: qualify and pin the selected freestanding toolchain.
- `N4-QEMU-001`: establish the native-only Tier 0 execution profile.

