# PKMAP2 Retained Kernel Mapping Contract

## Purpose

PKMAP2 extends the validated PKMAP1 kernel alias into retained boot-transfer
storage. PooleBoot builds and audits an exact supervisor higher-half mapping,
adds a guarded 36-page kernel stack and a one-MiB read-only handoff window,
then preserves the kernel and all private page tables across
`ExitBootServices`. The current slice stops before installing the retained CR3,
changing RSP, or calling PooleKernel.

The normative contract is `specs/native-kernel-map-contract.json`. The
allocation-free `no_std` model is `native/kmap`; privileged CPU and UEFI
operations remain in `native/boot/src/kmap.rs`; and
`runtime/native_kernel_map.py` is the independent oracle.

## Preconditions

PKMAP2 fails closed unless paging, PAE, long mode, CR0.WP, CPUID NX, and
EFER.NXE are active and the CPU reports 36-52 physical-address bits. LA57 and
PCID are outside this profile. PML4 slot 511 must be unused. Kernel mapping
ranges must be aligned, nonoverlapping, complete, and W^X-safe.

Retained physical ranges must also be aligned, nonzero, representable, and
pairwise disjoint:

- the current 148-page PooleKernel allocation within a 192-page reservation;
- a second retained leaf table so the guarded stack, handoff, PMM metadata, alternate ledgers, and IRQ MMIO reservation can extend beyond the first 2 MiB window without packing unrelated roles into one table;
- five private page-table pages;
- 36 writable, non-executable stack pages;
- 256 handoff pages, covering one MiB.

The virtual layout uses global retained leaf indices across two page tables.
Index 192 is the low guard, indices 193-228 hold the stack, index 229 is the
high guard, and indices 230-485 hold the handoff. Both guards remain
non-present. The handoff is supervisor read-only and NX. `ADD-MEM-001`
requires boot, entry, trap, and PMM consumers to derive these bounds from one
contract. Unused kernel reservation pages remain absent. The handoff must fit
inside the first leaf table; the second table is not a handoff overflow path.
The bootstrap temporary alias is index 486.
PKPMM7 retains index 487 as the stable-manager low guard, indices 488-492 for
its five-page supervisor RW/NX manager, and index 493 as its high guard. It
reserves guarded 32-page ledger windows at indices 494-527 and 528-561. All of
these leaves are absent in the PKMAP2 construction receipt. Selector 8 installs
only the manager plus the pages owned by one active ledger generation.
PKIRQ1 reserves indices 562-566 as low guard, local APIC, middle guard, HPET,
and high guard. PKMAP2 leaves all five reserved leaves absent; selector 11 may install only the
two supervisor RW/NX PWT/PCD device leaves and must revoke them before halt.

## Table Construction

PooleBoot allocates contiguous `EfiLoaderData` pages for a candidate PML4,
PDPT, page directory, and two page tables. It clones the active PML4 and
installs a private hierarchy at PML4[511], PDPT[510], and PD[0..1]. Exact 4 KiB
leaves encode:

- kernel `r`: present, read-only, NX;
- kernel `rx`: present, read-only, executable;
- kernel `rw`: present, writable, NX;
- stack: present, writable, NX;
- handoff: present, read-only, NX;
- stack guards: absent;
- any writable-executable request: rejected.

The Rust verifier and independent Python oracle reconstruct every parent and
leaf. Exact leaf counts and fingerprints are rebound from each canonical
kernel image, while zero writable-executable leaves remains mandatory.

## Active Audit

PooleBoot saves RFLAGS, disables maskable interrupts, loads the candidate CR3,
and reads it back. No UEFI service is called while that root is active. The
adapter walks every high-half kernel page, verifies physical targets and
effective permissions, requires the entry page to be RX, and hashes the entire
live alias.

The first and last framebuffer translations are compared between the firmware
root and candidate root, including physical address, leaf size, effective
permissions, and PAT/PCD/PWT bits. This proves preservation only; it does not
qualify the final PooleOS framebuffer cache policy.

The original CR3 is restored and read-verified before the final firmware
sequence. A rollback mismatch halts permanently. Successful restoration does
not release the candidate tables: PKMAP2 retains them for the future transfer
slice.

## Retention And Final Map

PKLOAD6 binds the live PKMAP2 marker to the final PBP1 core record and to an
independently normalized UEFI memory map. Kernel, root, stack, and handoff
physical ranges plus exact PSM1, six PBART1, PBTP1, and PBTS1 allocations must
all remain covered by loader-reserved descriptors in the map used for the
successful `ExitBootServices` call. Overlap, omission, wrong memory kind,
guard drift, marker drift, or guest/oracle disagreement rejects the receipt.

## Qualification Boundary

Cycle 210 reproduces the 148-page kernel colliding with the former page-147
guard, then passes 15 native tests in debug and optimized builds with the
192-page reservation. The growth regression accepts 148 and 192 pages, leaves
unused/guard leaves absent, and rejects 193 pages before modifying any table.
Current-image guest qualification is recorded separately in the readiness
receipts; older boot receipts must not be inherited after a layout change.

It does not prove final CR3 activation, stack switching, a transferable signed
PBP1 profile, kernel entry, SMP/TLB policy, runtime-region policy, target
firmware, physical hardware, N5 exit, or production readiness.

## Primary References

- UEFI 2.11, [Boot Services](https://uefi.org/specs/UEFI/2.11/07_Services_Boot_Services.html)
- Intel, [Intel 64 and IA-32 Architectures Software Developer Manuals](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html)
- AMD, [AMD64 Architecture Programmer's Manual Volume 2](https://docs.amd.com/v/u/en-US/24593_3.44_APM_Vol2)
