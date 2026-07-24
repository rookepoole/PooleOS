# PKVM2 Bounded Active Virtual-Memory Root

## Scope

PKVM2 is PooleKernel's first bounded, kernel-complete page-table root that is
actually installed in CR3. It advances the inactive PKVM1 foundation without
claiming a complete virtual-memory subsystem or satisfying the N9 exit gate.
The qualified selector-10 profile runs on one bootstrap processor with
interrupts disabled, maps one user page, directly maps its eight table pages
and one data page, performs three live leaf mutations, restores the exact
original root, scrubs every owned page, and releases both allocations.

The canonical contract is
`specs/native-kernel-virtual-memory-contract.json`; this note explains the
design and its deliberately narrow evidence boundary.

## Threat Model

PKVM2 fails closed against these bounded threats:

- activating a candidate built from a stale root, on a non-BSP CPU, or while
  maskable interrupts are enabled;
- losing or weakening inherited kernel, entry, guarded-stack, or PBP1 handoff
  mappings while constructing the candidate;
- mapping a frame outside the two generation-owned PKPMM1 allocations;
- accepting an occupied direct-map root slot or leaving the bootstrap alias
  active before CR3 installation;
- treating x86-64 hardware Accessed or Dirty updates as unauthorized drift;
- mutating an active leaf without a root-, generation-, address-, CPU-, and
  sequence-bound local invalidation receipt;
- freeing the data frame before both user and direct-map aliases are revoked;
- freeing table pages while their root is active, or failing to restore the
  exact original CR3 after activation or readback failure.

This profile does not defend an SMP system, execute ring 3, or validate MMIO,
PAT/MTRR, speculative-execution, side-channel, or physical fault behavior.

## Address Layout

The contract freezes canonical 48-bit addresses for this profile:

- user probe page: `0x0000000040000000`;
- inherited kernel half: PML4 indices 256 through 511 except index 288;
- bounded direct-map base: `0xFFFF900000000000`, PML4 index 288;
- inherited kernel entry: exact RX mapping at `0xFFFFFFFF80000000`;
- inherited kernel stack: exact 14 mapped pages with both guard pages absent;
- inherited PBP1 handoff: exact first and last pages, read-only and NX.

PKVM2 allocates eight contiguous DMA32 table pages in this order: candidate
PML4, user PDPT, user PD, user PT, direct-map PDPT, direct-map PD, direct-map
PT0, and direct-map PT1. A second one-page allocation immediately follows for
the probe data. The direct map covers exactly those nine owned pages with
supervisor RW/NX 4 KiB leaves. It is not a general physical-memory map.

## Lifecycle

1. Copy the current PKMAP2 PML4, construct fresh user and direct-map branches,
   and audit every inherited and owned mapping through the temporary bootstrap
   mapper.
2. Revoke the bootstrap alias, require BSP 0 with IF clear, verify the expected
   original root, install the candidate, and require exact CR3 readback.
3. Write and read the data probe through its live direct-map alias.
4. Change the user leaf from RW/NX to RX and issue local `INVLPG` receipt 1.
5. Remove the user leaf and issue local `INVLPG` receipt 2.
6. Remove the data direct-map leaf and issue local `INVLPG` receipt 3.
7. Reject premature data reuse until both unmap receipts are present, then
   scrub and free the data frame.
8. Restore and read back the exact original CR3, scrub all eight inactive table
   pages through the bootstrap mapper, revoke that alias, and free the tables.

If candidate CR3 readback fails, PKVM2 immediately writes the exact original
CR3 and returns an activation failure. Host fault injection proves that path.
Table-leaf rollback is likewise host-tested when an active hardware write
fails; no invalidation receipt is minted for a mutation that did not commit.

## Architectural Bits

x86-64 may set Accessed on traversed entries and Dirty on the written data
leaf. PKVM2 permits only those architectural changes while an entry is active,
preserves them across permission changes, and rejects every other observed-bit
drift. This distinction is required for a live root; byte-for-byte equality to
the pre-activation entry would be incorrect after hardware traversal.

## Qualification Boundary

The live oracle requires two byte-identical QEMU/OVMF runs, 40 exact markers,
46 hostile controls, deterministic binding to the PBP1 DMA32 first-fit
transcript, and source audits for the no-heap core and volatile privileged
adapter. The canonical run performs 8,720 physical table writes, 5,528
bootstrap temporary-PTE writes and invalidations, two CR3 writes, and three
active local invalidations. Signature, authority, action, and production counts
remain zero.

PKVM2 does not implement AP startup or TLB shootdown, deferred SMP reclaim,
huge pages, PCID, KASLR, copy-on-write, user faults, stack growth, pager IPC,
heap policy, pressure/OOM handling, or a complete generation-owned direct map.
It has no target-hardware or second-host evidence. Those remain explicit N9
work; PKVM2 is pre-production evidence only.
