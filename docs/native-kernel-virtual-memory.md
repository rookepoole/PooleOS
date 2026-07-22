# PKVM1 Inactive Virtual-Memory Foundation

## Purpose

PKVM1 is the first bounded PooleKernel-owned virtual-memory implementation. It
freezes the initial 48-bit address bands and implements generation-bound 4 KiB
map, protect, and unmap transactions over a real four-level x86_64 hierarchy.
The hierarchy is deliberately inactive: it contains one lower-half user test
window and no kernel execution mapping, so loading it into CR3 is forbidden.

The normative contract is
`specs/native-kernel-virtual-memory-contract.json`. The allocation-free core is
`native/kernel/src/virtual_memory.rs`; the ring-0 physical adapter is in
`native/kernel/src/main.rs`; and
`runtime/native_kernel_virtual_memory.py` is the independent evidence oracle.

## Frozen Layout

PKVM1 classifies canonical 48-bit addresses into these non-authoritative bands:

- page zero through 64 KiB is the low-address guard;
- the remaining lower canonical half is user space;
- the upper canonical half begins at `0xFFFF800000000000`;
- `0xFFFF900000000000..0xFFFFD00000000000` is reserved for a future direct map;
- `0xFFFFFFFF80150000..0xFFFFFFFF80151000` is the one-page PKMAP2
  bootstrap temporary mapping;
- `0xFFFFFFFF80000000..0xFFFFFFFFC0000000` remains the PKMAP2 kernel window.

The implemented slice is only the 2 MiB user window beginning at
`0x0000000040000000`. The wider layout is frozen so later direct-map, KASLR,
stack, metadata, and pager work cannot silently collide with this foundation.

## Physical Ownership

PKVM1 obtains one contiguous four-page DMA32 allocation from PKPMM1 for PML4,
PDPT, page-directory, and page-table pages, plus one separate data frame. Every
handle carries the PKPMM1 allocation slot, generation, range, zone, and owner.
Stale or wrong-owner handles fail before a PTE is touched.
The adapter reads the physical-address width directly from BSP CPUID leaf
`0x80000008` and accepts only 36 through 52 bits. It does not depend on the
optional PBP1 CPU-bootstrap record, which the current development handoff does
not carry.

The newly allocated pages are not inherited identity mappings. The privileged
adapter instead proves that PKMAP2 retained its own four page-table frames as
identity-mapped, verifies that leaf 336 is initially absent, and exclusively
uses that leaf as a one-page bootstrap mapping. Every target-page transition
revokes the old leaf, executes `INVLPG`, installs the new supervisor-only,
writable, NX leaf, executes `INVLPG` again, and verifies the resulting physical
translation before volatile access. `finish` revokes and verifies the final
alias before PKPMM1 frees the table allocation.

The qualified profile performs exactly 4,104 writes to the inactive tables, 40
writes to the active PKMAP2 bootstrap leaf, and 40 corresponding hardware
`INVLPG` operations. It returns both PKPMM1 allocations with zero residue.

## Transactions

Map and protect operations validate canonicality, page alignment, the bounded
window, PMM ownership, supervisor/user policy, W^X, and cache aliases before
mutation. A leaf change is committed only after exact write/readback. Failure
restores and verifies the old leaf before returning an error; the mapping ledger
changes only after commit.

Unmap is split into three operations. `begin_unmap` clears and verifies the leaf
but quarantines the frame. `acknowledge_inactive` records that this root has
never been active and therefore cannot have a cached translation.
`complete_unmap` releases the frame only after every alias is gone and every
pending receipt is acknowledged. A host-injected write failure proves exact
leaf rollback; the live profile proves mixed-cache alias rejection, W^X
rejection, and premature-reuse rejection.

## Qualification

Selector 9 builds a distinct development PooleBoot profile and runs twice with
fresh OVMF variable stores under pinned single-threaded qemu64 TCG. Both runs
must match all 40 ordered markers, screenshots, and PBP1 bytes. The independent
oracle derives the first DMA32 free extent from the live PBP1 map and requires
the table and data allocations to match deterministic PKPMM1 first fit. Thirty-
nine hostile controls mutate selector, layout, ownership, translations,
permissions, cache state, transaction counts, release state, inactive-table
writes, bootstrap-leaf writes, invalidation counts, and the PBP1 binding.

## Claim Boundary

PKVM1 does not load its root into CR3, activate the direct-map band, or send an
inter-processor shootdown. Selector 9 does activate one PKMAP2 bootstrap
temporary leaf and executes local `INVLPG` only to manage that active alias. It
does not implement PCID, huge pages, KASLR, copy-on-write, user-fault delivery,
stack growth, a pager, heap, SMP, reclaim, pressure, or OOM policy. Its inactive
root receipts and bootstrap-leaf invalidations are not evidence for an active
PKVM1 address-space TLB protocol. N9 remains partial and production remains
false.

## Primary References

- Intel 64 and IA-32 Architectures Software Developer Manuals
- AMD64 Architecture Programmer's Manual, Volume 2
- `models/tla/PooleVirtualMemory.tla`
- `docs/native-kernel-map.md`
- `docs/native-kernel-physical-memory.md`
