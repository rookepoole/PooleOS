# PKMAP2 Retained Kernel Mapping Contract

## Purpose

PKMAP2 extends the validated PKMAP1 kernel alias into retained boot-transfer
storage. PooleBoot builds and audits an exact supervisor higher-half mapping,
adds a guarded eight-page kernel stack and a one-MiB read-only handoff window,
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

- the 48-page PooleKernel allocation;
- four private page-table pages;
- eight writable, non-executable stack pages;
- 256 handoff pages, covering one MiB.

The virtual layout reserves low and high guard pages around the stack. Both
guards remain non-present. The handoff range begins after a fixed alignment gap
and is supervisor read-only and NX.

## Table Construction

PooleBoot allocates contiguous `EfiLoaderData` pages for a candidate PML4,
PDPT, page directory, and page table. It clones the active PML4 and installs a
private hierarchy at PML4[511], PDPT[510], and PD[0]. Exact 4 KiB leaves encode:

- kernel `r`: present, read-only, NX;
- kernel `rx`: present, read-only, executable;
- kernel `rw`: present, writable, NX;
- stack: present, writable, NX;
- handoff: present, read-only, NX;
- stack guards: absent;
- any writable-executable request: rejected.

The Rust verifier and independent Python oracle reconstruct every parent and
leaf. `pkmap2_probe` emits an address-independent retained-layout fingerprint;
the qualified value is `DCA9DC32D914438D`.

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

PKLOAD5 binds the live PKMAP2 marker to the final PBP1 core record and to an
independently normalized UEFI memory map. Kernel, root, stack, and handoff
physical ranges must all remain covered by loader-reserved descriptors in the
map used for the successful `ExitBootServices` call. Overlap, omission, wrong
memory kind, guard drift, marker drift, or guest/oracle disagreement rejects
the receipt.

## Qualification Boundary

The current receipt passes 14/14 `poole-kmap` tests, the Rust/Python probe
comparison, two exact OVMF boots, and all PKMAP2 integration controls. It proves
retention through successful `ExitBootServices` and a firmware-free halt.

It does not prove final CR3 activation, stack switching, a transferable signed
PBP1 profile, kernel entry, SMP/TLB policy, runtime-region policy, target
firmware, physical hardware, N5 exit, or production readiness.

## Primary References

- UEFI 2.11, [Boot Services](https://uefi.org/specs/UEFI/2.11/07_Services_Boot_Services.html)
- Intel, [Intel 64 and IA-32 Architectures Software Developer Manuals](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html)
- AMD, [AMD64 Architecture Programmer's Manual Volume 2](https://docs.amd.com/v/u/en-US/24593_3.44_APM_Vol2)
