# Native physical-memory foundation

`PKPMM3` is the bounded N9 guarded allocator-metadata increment. It is an opt-in, BSP-only, qemu64 Tier-0 development profile selected by PooleBoot selector `8`; the default image still stops before kernel transfer. It supersedes selector-8 `PKPMM2` evidence without promoting N9 or PooleOS to production.

## Ownership boundary

PooleKernel consumes the exact post-`ExitBootServices()` PBP1 map, independently revalidates every normalized UEFI source-type/kind pair, and initially admits only `MEMORY_USABLE` (`EfiConventionalMemory`) pages. Page zero becomes an explicit null guard. Boot-services code/data, ACPI reclaimable memory, runtime memory, ACPI NVS, MMIO, persistent, unusable, and reserved memory remain unavailable. The kernel image, retained handoff, and current page-table root must all be covered by PBP1 loader-reserved ranges.

This follows the UEFI 2.11 ownership boundary: firmware owns the map before `ExitBootServices()`; after a successful exit the loader/OS owns unused loader, boot-services, and conventional memory but must preserve runtime ranges. `PKPMM3` deliberately holds the broader reclaimable set until PooleOS has explicit subsystem handoff and mapping contracts.

Official references:

- <https://uefi.org/specs/UEFI/2.11/07_Services_Boot_Services.html#efi-boot-services-getmemorymap>
- <https://uefi.org/specs/UEFI/2.11/07_Services_Boot_Services.html#efi-boot-services-exitbootservices>

## Bounded manager

The safe Rust manager uses fixed arrays for at most 256 PBP1 source records, 256 free extents, 32 allocation slots, and 16 scrub receipts. It has no heap. Usable ranges are split into DMA (below 16 MiB), DMA32 (16 MiB through 4 GiB), and Normal (above 4 GiB) zones. Allocation is deterministic first-fit within one requested zone and is capped by a 64-page profile quota.

An allocation handle binds slot, generation, physical page range, zone, and owner. Free requires an exact match and rejects stale or repeated handles. Adjacent same-zone extents coalesce. The free path proves that the returned extent can be represented before it performs any physical write, so fixed-ledger exhaustion cannot scrub a page that remains owned by a live handle.

The earlier raw `allocate` and `free` methods remain only for the bounded `PKVM1` and `PKVM2` predecessor profiles. They are not production APIs and are not covered by the `PKPMM3` page-content or metadata claim.

## Metadata handoff

The selector-8 profile first builds the complete manager on the validated bootstrap stack. It then reserves the first five DMA32 pages under owner `0x4D45`, zeroes and reads back all five pages, records scrub receipt 1, and marks that allocation release-excluded. The architecture adapter installs five supervisor RW/NX write-back leaves at `0xFFFFFFFF80158000` with one absent guard on each side.

The complete 14,616-byte manager object is copied into the arena. This includes all source, extent, allocation, receipt, ownership, and counter capacity, not only currently populated records. A versioned header binds physical start, virtual start, generation, owner, byte count, and page count. FNV-1a-64 over every logical header field, ledger slot, and counter detects corruption before each later manager operation. This is an integrity check, not a cryptographic authenticity claim.

Only after the copy, live mapping, guards, and logical seal validate does the stack-resident manager enter the retired state. Mapping or handoff failure unmaps every installed metadata leaf, scrubs and releases the reservation, restores bootstrap operation, and emits no successful migration result. The mapped manager rejects release of its own allocation and reseals after every attempted mutating operation.

## Scrub transaction

`allocate_scrubbed` plans a first-fit allocation without changing the free or ownership ledgers. Through the `PhysicalPageAccess` boundary it writes zero to every 64-bit word of every planned page and then reads every word back. Only a complete zero-and-readback pass commits the allocation slot and returns its handle. A failed access or comparison restores the pre-call ownership state and emits no receipt.

`free_scrubbed` first validates the exact live handle and preflights extent reinsertion. It then zeroes and reads back every word while the handle remains owned. Only success releases the slot, reinserts and coalesces the extent, poisons inactive metadata, and emits a release receipt. A failed release scrub leaves the handle live and the pages unavailable for reuse.

Each successful transaction emits an immutable value receipt binding sequence, operation kind, start page, page count, generation, owner, zeroed byte count, and verified byte count. Sequences start at one and advance only after success.

## Live adapter

The selector-8 adapter maps one physical page at a supervisor RW/NX temporary virtual address for scrub and readback. Changing the physical page writes one leaf PTE and invalidates that virtual address. Five adjacent, separately owned leaves retain the metadata arena. `finish()` clears and invalidates the temporary leaf, proves its translation absent, then re-walks all five metadata mappings and both guards. The retained arena is not a direct map or complete address-space claim.

The live profile performs this exact lifecycle:

1. Reserve and scrub five DMA32 metadata pages, emit receipt 1, install the guarded mapping, copy and seal the complete manager, and retire the bootstrap copy.
2. Reject release of the metadata allocation.
3. Allocate the next two DMA32 pages, zero and read them back, and emit receipt 2.
4. Fill both ordinary pages with `0xA5A55A5AC3C33C3C` and verify the pattern.
5. Zero and read back both pages before release, then emit receipt 3.
6. Reject the stale handle, quota overflow, and an unavailable Normal request.
7. Reallocate the exact ordinary first-fit range with a greater generation, prove every word is zero, and emit receipt 4.
8. Zero and read back the ordinary range before final release, emit receipt 5, revoke the temporary alias, and retain the guarded metadata mapping.

The resulting live counters are 13 scrubbed and verified pages, 53,248 scrubbed bytes, 53,248 verified bytes, 7,680 64-bit physical writes, 8,704 64-bit physical reads, 43 total leaf writes, and 43 local invalidations. Five leaf writes install the retained arena. Final allocated pages are five because the metadata allocation remains live and release-excluded.

## Failure and hostile evidence

Host tests inject a partial allocation write failure, a release readback mismatch, and an extent-ledger preflight failure. Four additional tests prove complete-ledger migration and release exclusion, mapping-failure reservation rollback, corrupted-handoff unmap and rollback, and rejection of the next operation after mapped metadata corruption. The ordinary lifecycle test proves exact first-fit reuse advances generation and contains no stale pattern.

Two fresh-OVMF-vars TCG runs must produce identical 41-marker streams, framebuffer captures, and PBP1 bytes. An independent Python oracle reconstructs source-kind totals, zone splits, post-reservation extents, deterministic DMA32 first fit, metadata placement, and core ownership directly from PBP1. Eighty-seven hostile controls mutate every contract-bearing marker field plus map overlap, source-kind pairing, and core ownership. The focused gate passes 74 PooleKernel host tests.

The 70-page Cycle 129 kernel places the fourteen-page bootstrap stack at leaf indices 71-84, retained handoff at 86-341, temporary alias at 342, metadata low guard at 343, metadata pages at 344-348, and metadata high guard at 349. All indices derive from shared constants and remain inside the one-page leaf table.

N9 remains partial. The bounded arena has no growth, retirement, reclaim, concurrency, or SMP protocol. The evidence does not activate reclaimable ranges, implement complete kernel/user address spaces or SMP TLB policy, provide heap/object caches or general kernel stacks, cover pressure/OOM behavior, or establish target-hardware and second-host results.
