# PooleOS Lab OS Decision - Superseded Historical Record

> **Superseded on 2026-07-15 by the native PooleOS architecture reset.** This document records the former QEMU/Buildroot laboratory experiment only. Buildroot and Linux are not production foundations, boot components, kernel components, userspace components, or release-media dependencies for native PooleOS. See `docs/production-goal-charter.md` and `docs/pdc-production-build-plan.md`.

Status: draft v0.1

Date: 2026-06-29

## Decision

PooleOS Lab should start as a QEMU-first Buildroot appliance.

NixOS remains the better later path for a full reproducible PooleOS workstation profile, but Buildroot is the smaller first boot target for a focused appliance whose job is to boot, run PooleOS conformance, emit artifacts, and shut down cleanly.

## Rationale

PooleOS is not ready for a native commodity kernel. The next bootable target should prove:

1. PooleOS can boot as the primary workload in an isolated image.
2. PooleOS can run offline without network services.
3. PooleOS can execute `pooleos_doctor.py`.
4. PooleOS can validate PGB2 bundles and replay proofs.
5. PooleOS can export artifacts through a mounted output path.

Buildroot is the better first fit because it is designed to build small embedded Linux systems including root filesystems, kernels, bootloaders, and toolchains. QEMU is the first runtime target because it supports full-system emulation without risking a physical machine.

NixOS should be revisited when the goal shifts from appliance image to developer workstation image.

## Boundary

This decision does not claim production boot readiness. It establishes the scaffold for the first bootable PooleOS Lab artifact.

## Acceptance Gate For First Boot Image

A first PooleOS Lab image is acceptable when:

- it boots in QEMU;
- it runs without network access;
- it contains the PooleOS runtime files;
- it contains a Python runtime sufficient for current tests;
- `python /opt/pooleos/tools/pooleos_doctor.py --no-runtime` passes;
- `pooleos_release_gate.py` can validate a bundled PGB2 artifact and replay proof;
- artifacts can be copied out through a documented path.

## References Checked

- Buildroot manual: build system for toolchain, root filesystem, Linux kernel image, and bootloader.
- NixOS manual: declarative system configuration and module-based system management.
- QEMU system emulator documentation: full-system emulation target for bootable images.
