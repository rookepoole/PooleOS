# Native physical-memory foundation

`PKPMM1` is the first live N9 physical-memory increment. It is an opt-in, BSP-only, qemu64 Tier-0 development profile selected by PooleBoot selector `8`; the default image still stops before kernel transfer.

## Ownership boundary

PooleKernel consumes the exact post-`ExitBootServices()` PBP1 map, independently revalidates every normalized UEFI source-type/kind pair, and initially admits only `MEMORY_USABLE` (`EfiConventionalMemory`) pages. Page zero becomes an explicit null guard. Boot-services code/data, ACPI reclaimable memory, runtime memory, ACPI NVS, MMIO, persistent, unusable, and reserved memory remain unavailable. The kernel image, retained handoff, and current page-table root must all be covered by PBP1 loader-reserved ranges.

This follows the UEFI 2.11 ownership boundary: firmware owns the map before `ExitBootServices()`; after a successful exit the loader/OS owns unused loader, boot-services, and conventional memory but must preserve runtime ranges. PKPMM1 deliberately holds the broader reclaimable set until PooleOS has explicit subsystem handoff and mapping contracts.

Official references:

- <https://uefi.org/specs/UEFI/2.11/07_Services_Boot_Services.html#efi-boot-services-getmemorymap>
- <https://uefi.org/specs/UEFI/2.11/07_Services_Boot_Services.html#efi-boot-services-exitbootservices>

## Bounded manager

The Rust manager uses fixed arrays for at most 256 PBP1 records, 256 free extents, and 32 active allocation slots. It has no heap and no unsafe block. Usable ranges are split into DMA (below 16 MiB), DMA32 (16 MiB through 4 GiB), and Normal (above 4 GiB) zones. Allocation is deterministic first-fit within one requested zone and is capped by a 64-page profile quota.

An allocation handle binds slot, generation, physical page range, zone, and owner. Free requires an exact match, first proves that the returned extent can be represented, and only then releases accounting and marks the inactive slot as metadata-poisoned. Adjacent same-zone extents can coalesce even when the fixed extent ledger is otherwise full; an unrepresentable non-adjacent free fails transactionally and leaves the allocation live. The live exercise allocates three DMA and eight DMA32 pages, rejects quota overflow, rejects an unavailable Normal request on the qemu64 fixture, frees both allocations, rejects a repeated free, and proves the initial free-extent topology is restored.

## Evidence and limits

Two fresh-OVMF-vars TCG runs must produce identical 40-marker streams, framebuffer captures, and PBP1 bytes. The stream includes an immediate selector receipt and five ordered gates for the entry envelope, development handoff profile, runtime continuity, record/artifact decode, and retained-set revalidation. An independent Python oracle reconstructs all kind totals, zone splits, largest extents, deterministic first-fit addresses, and core ownership directly from PBP1. Forty-eight hostile controls cover marker mutation, map overlap, invalid source/kind pairing, and escaped core ownership.

Cycle 125 also expands the bootstrap stack from eight to fourteen pages (56 KiB) while keeping the low guard at page-table index 64, stack leaves at 65-78, the high guard at 79, and the handoff at 80. The first selector-8 live run exposed the earlier stack ceiling; the expanded stack reached the allocator receipt. The PKTRAP1 rerun then exposed a hard-coded eight-page guard offset that now landed inside the mapped stack. PooleKernel now exports the fourteen-page count and derives the guard address from it, and all three trap scenarios pass again. `ADD-MEM-001` prevents these boot, entry, trap, and allocator boundaries from drifting independently.

`metadata_poison=2` describes stale allocation-ledger state only. PKPMM1 performs zero reads or writes to allocated physical page contents, zero mapping changes, and zero reclaim operations. N9 remains partial until mapped metadata, physical scrubbing, lifecycle reclaim, virtual address spaces, page-table operations, TLB policy, cacheability, heap/caches/stacks, concurrency, randomized stress, reclaim/OOM, target hardware, and second-host evidence are complete.
