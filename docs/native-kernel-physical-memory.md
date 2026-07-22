# Native physical-memory foundation

`PKPMM2` is the bounded N9 physical-page scrubbing increment. It is an opt-in, BSP-only, qemu64 Tier-0 development profile selected by PooleBoot selector `8`; the default image still stops before kernel transfer. It supersedes the selector-8 `PKPMM1` evidence without promoting N9 or PooleOS to production.

## Ownership boundary

PooleKernel consumes the exact post-`ExitBootServices()` PBP1 map, independently revalidates every normalized UEFI source-type/kind pair, and initially admits only `MEMORY_USABLE` (`EfiConventionalMemory`) pages. Page zero becomes an explicit null guard. Boot-services code/data, ACPI reclaimable memory, runtime memory, ACPI NVS, MMIO, persistent, unusable, and reserved memory remain unavailable. The kernel image, retained handoff, and current page-table root must all be covered by PBP1 loader-reserved ranges.

This follows the UEFI 2.11 ownership boundary: firmware owns the map before `ExitBootServices()`; after a successful exit the loader/OS owns unused loader, boot-services, and conventional memory but must preserve runtime ranges. `PKPMM2` deliberately holds the broader reclaimable set until PooleOS has explicit subsystem handoff and mapping contracts.

Official references:

- <https://uefi.org/specs/UEFI/2.11/07_Services_Boot_Services.html#efi-boot-services-getmemorymap>
- <https://uefi.org/specs/UEFI/2.11/07_Services_Boot_Services.html#efi-boot-services-exitbootservices>

## Bounded manager

The safe Rust manager uses fixed arrays for at most 256 PBP1 records, 256 free extents, and 32 active allocation slots. It has no heap. Usable ranges are split into DMA (below 16 MiB), DMA32 (16 MiB through 4 GiB), and Normal (above 4 GiB) zones. Allocation is deterministic first-fit within one requested zone and is capped by a 64-page profile quota.

An allocation handle binds slot, generation, physical page range, zone, and owner. Free requires an exact match and rejects stale or repeated handles. Adjacent same-zone extents coalesce. The free path proves that the returned extent can be represented before it performs any physical write, so fixed-ledger exhaustion cannot scrub a page that remains owned by a live handle.

The earlier raw `allocate` and `free` methods remain only for the bounded `PKVM1` and `PKVM2` predecessor profiles. They are not production APIs and are not covered by the `PKPMM2` page-content claim.

## Scrub transaction

`allocate_scrubbed` plans a first-fit allocation without changing the free or ownership ledgers. Through the `PhysicalPageAccess` boundary it writes zero to every 64-bit word of every planned page and then reads every word back. Only a complete zero-and-readback pass commits the allocation slot and returns its handle. A failed access or comparison restores the pre-call ownership state and emits no receipt.

`free_scrubbed` first validates the exact live handle and preflights extent reinsertion. It then zeroes and reads back every word while the handle remains owned. Only success releases the slot, reinserts and coalesces the extent, poisons inactive metadata, and emits a release receipt. A failed release scrub leaves the handle live and the pages unavailable for reuse.

Each successful transaction emits an immutable value receipt binding sequence, operation kind, start page, page count, generation, owner, zeroed byte count, and verified byte count. Sequences start at one and advance only after success.

## Live adapter

The selector-8 adapter maps exactly one physical page at a pre-existing supervisor RW/NX temporary virtual address. Changing the physical page writes one leaf PTE and invalidates that virtual address. Volatile writes and reads operate only through that alias. After the profile, `finish()` clears the leaf, invalidates it, and proves translation is absent. This is a temporary bootstrap mechanism, not a direct-map or complete address-space claim.

The live profile performs this exact lifecycle:

1. Allocate two DMA32 pages, zero and read them back, and emit allocation receipt 1.
2. Fill both pages with `0xA5A55A5AC3C33C3C` and verify the pattern.
3. Zero and read back both pages before release, then emit release receipt 2.
4. Reject the stale handle, quota overflow, and an unavailable Normal request.
5. Reallocate the exact first-fit range with a greater generation, prove every word is zero, and emit allocation receipt 3.
6. Zero and read back the range before final release, emit receipt 4, and revoke the temporary alias.

The resulting live counters are 8 scrubbed and verified pages, 32,768 scrubbed bytes, 32,768 verified bytes, 5,120 64-bit physical writes, 6,144 64-bit physical reads, 28 temporary leaf writes, and 28 local invalidations. Final allocated pages are zero.

## Failure and hostile evidence

Host tests inject a partial allocation write failure, a release readback mismatch, and an extent-ledger preflight failure. They prove that failed allocation does not create a handle, failed release retains its handle, and preflight rejection performs no physical writes. The lifecycle test also proves exact first-fit reuse advances generation and contains no stale pattern.

Two fresh-OVMF-vars TCG runs must produce identical 40-marker streams, framebuffer captures, and PBP1 bytes. An independent Python oracle reconstructs source-kind totals, zone splits, largest extents, deterministic DMA32 first fit, and core ownership directly from PBP1. Sixty-three hostile controls mutate every contract-bearing marker field plus map overlap, source-kind pairing, and core ownership.

Cycle 125 expanded the bootstrap stack from eight to fourteen pages (56 KiB) and bound the guard derivation through `ADD-MEM-001`. `PKPMM2` preserves that geometry.

N9 remains partial. The evidence does not activate reclaimable ranges, move metadata to a durable mapped arena, implement complete kernel/user address spaces, qualify concurrent or SMP allocation and TLB policy, provide heap/object caches/kernel stacks, cover pressure/OOM behavior, or establish target-hardware and second-host results.
