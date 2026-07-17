# PKMAP1 Native Kernel Mapping Contract

## Purpose

PKMAP1 is the smallest live proof that PooleBoot can turn the current PKELF1
mapping plan into hardware-active x86-64 page tables and return safely to UEFI.
It covers one exact 2 MiB higher-half window and deliberately stops before a
retained handoff, `ExitBootServices`, or PooleKernel entry.

The normative machine-readable contract is
`specs/native-kernel-map-contract.json`. The allocation-free Rust core is
`native/kmap`; the only CR3, CPUID, MSR, interrupt, and UEFI operations are in
`native/boot/src/kmap.rs`; and `runtime/native_kernel_map.py` is the independent
Python oracle.

## Preconditions

PKMAP1 fails closed unless paging, PAE, long mode, CR0.WP, CPUID NX, and
EFER.NXE are active and the CPU reports 36-52 physical-address bits. Five-level
paging and PCID are outside this bounded proof. The exact kernel physical,
virtual, entry, image, and four mapping ranges must be aligned, nonoverlapping,
fully covering, inside one 2 MiB window, and W^X-safe.

The active CR3 root and all newly allocated table and kernel endpoints must be
identity reachable in the UEFI environment. PML4 slot 511 must be exactly zero;
PKMAP1 never mutates or shares an occupied higher-half hierarchy.

## Table Construction

PooleBoot allocates four contiguous `EfiLoaderData` pages for a candidate PML4,
PDPT, page directory, and page table. It clones all 512 active PML4 entries,
adds PML4[511], PDPT[510], and PD[0], then emits one 4 KiB leaf per kernel page.
Parent entries are present, writable, supervisor, and executable so effective
leaf policy is controlled at the PT. Leaves are supervisor-only:

- `r`: present, read-only, NX;
- `rx`: present, read-only, executable;
- `rw`: present, writable, NX;
- `rwx`: rejected.

Every unused private entry remains zero. The Rust verifier reconstructs every
expected parent and leaf, including normalized virtual/physical offsets and an
address-independent FNV fingerprint. The independent Python oracle reconstructs
the same values without importing the Rust implementation.

## Active Interval

PooleBoot saves RFLAGS, disables maskable interrupts, issues a compiler fence,
loads candidate CR3, and rereads CR3. During this interval it makes zero UEFI
calls. It walks every high-half kernel page through the candidate root, checks
the exact physical target and effective permissions, requires 4 KiB leaves,
requires the entry to be RX, and hashes all mapped bytes through the live high
alias.

Before activation, PooleBoot snapshots the first and last GOP framebuffer
translations through the firmware root. During activation, it repeats those
walks through the candidate root and requires equality of physical addresses,
page sizes, effective permissions, and PAT/PCD/PWT bits.

## Rollback

PooleBoot always writes the original CR3 after the active observation, even if
activation or verification reports failure. It rereads CR3 and treats any
mismatch as non-returnable: a raw fatal marker is emitted and the CPU halts so
no firmware service can run under an unverified root. Only after exact rollback
does PooleBoot restore interrupts, free the four private pages, and later free
the kernel allocation.

## Qualification And Limits

PKLOAD4 binds the Rust probe, Python oracle, 77 hostile controls, deterministic
build/media reproduction, and two fresh QEMU/OVMF executions. The live marker
sequence must include `KERNEL_MAP_PLAN`, `KERNEL_MAP_ACTIVE`, and
`KERNEL_MAP_ROLLBACK`, and serial/debugcon streams must agree exactly.

This proves temporary activation and rollback for the current product under the
pinned single-host emulator. It does not prove a final address space, dedicated
handoff stack, final framebuffer cache policy, TLB/SMP shootdown, runtime-region
mapping, `ExitBootServices`, kernel execution, target firmware, physical
hardware, a second builder, N5 exit, or production readiness.

## Primary References

- UEFI 2.11, [Boot Services](https://uefi.org/specs/UEFI/2.11/07_Services_Boot_Services.html)
- Intel, [Intel 64 and IA-32 Architectures Software Developer Manuals](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html)
- AMD, [AMD64 Architecture Programmer's Manual Volume 2](https://docs.amd.com/v/u/en-US/24593_3.44_APM_Vol2)
