# Native physical-memory foundation

`PKPMM4` is the bounded N9 held-memory-reclaim increment. It is an opt-in, BSP-only, qemu64 Tier-0 development profile selected by PooleBoot selector `8`; the default image still stops before kernel transfer. It supersedes selector-8 `PKPMM3` evidence without promoting N9 or PooleOS to production.

## Ownership boundary

PooleKernel consumes the exact post-`ExitBootServices()` PBP1 map, independently revalidates every normalized UEFI source-type/kind pair, and initially admits only `MEMORY_USABLE` (`EfiConventionalMemory`) pages. Page zero is an explicit null guard. The kernel image, retained handoff, active root, guarded bootstrap stack, and allocator metadata stay protected by immutable source-ledger and active-allocation exclusions.

This follows the UEFI 2.11 boundary: firmware owns the map before `ExitBootServices()`; after successful exit the OS may reclaim unused boot-services memory but must preserve runtime ranges. ACPI reclaimable memory stays held until every required table consumer has copied or released it. Runtime memory, ACPI NVS, MMIO, persistent, unusable, and reserved memory are never candidates in PKPMM4.

Official references:

- <https://uefi.org/specs/UEFI/2.11/07_Services_Boot_Services.html#efi-boot-services-getmemorymap>
- <https://uefi.org/specs/UEFI/2.11/07_Services_Boot_Services.html#efi-boot-services-exitbootservices>

## Bounded manager

The safe Rust manager uses fixed arrays for at most 256 PBP1 source records, 256 free extents, 32 allocation slots, 16 scrub receipts, and two reclaim receipts. It has no heap. Usable and newly admitted ranges are split into DMA (below 16 MiB), DMA32 (16 MiB through 4 GiB), and Normal (above 4 GiB) zones. Ordinary allocation is deterministic first-fit within one requested zone and is capped by a 64-page profile quota.

An allocation handle binds slot, generation, physical range, zone, and owner. Free requires an exact match and rejects stale or repeated handles. Adjacent same-zone extents coalesce. Every content-mutating path proves ledger capacity and arithmetic first. The earlier raw `allocate` and `free` methods remain only for bounded PKVM1/PKVM2 predecessor profiles and are not production APIs.

## Metadata handoff

Selector 8 first builds the complete manager on the validated bootstrap stack. It reserves and scrubs five DMA32 pages under owner `0x4D45`, records scrub receipt 1, marks the allocation release-excluded, and maps the pages supervisor RW/NX at `0xFFFFFFFF80158000` between absent guards.

The complete 14,928-byte manager is copied into the arena, including every source, extent, allocation, scrub-receipt, reclaim-receipt, ownership, stage, and counter slot. A versioned header binds physical start, virtual start, generation, owner, byte count, and page count. FNV-1a-64 over every logical field detects corruption before subsequent manager operations; this is integrity evidence, not cryptographic authenticity.

Only after copy, live mappings, guards, and logical seal validate does the stack manager retire. Mapping or handoff failure removes every installed leaf, scrubs and releases the reservation, restores bootstrap operation, and emits no migration success. The mapped manager rejects its own release and reseals after every attempted mutation.

## Scrub transactions

`allocate_scrubbed` plans without changing ownership, writes zero to every 64-bit word through `PhysicalPageAccess`, reads every word back, and commits only after full verification. `free_scrubbed` validates the exact handle and preflights reinsertion before writing; ownership remains live until the full zero/readback succeeds. Content faults preserve the pre-call ownership state and emit no receipt.

Successful ordinary transactions emit immutable receipts binding sequence, operation, range, generation, owner, zeroed bytes, and verified bytes. Sequence values advance only on success.

## Reclaim stages

PKPMM4 defines a monotonic three-stage lifecycle:

1. `PreExitBootServices`: all held classes are unavailable.
2. `PostExitBootServices`: unused boot-services code/data may be admitted.
3. `AcpiTablesReleased`: ACPI reclaimable ranges may be admitted only after an external table-consumer release event.

Stages may advance one step and may not skip or regress. Reclaiming a class before its stage is rejected. The live profile proves positive boot-services admission and rejects early ACPI admission; the host suite separately proves positive ACPI admission after the final stage. PKPMM4 does not claim that a real ACPI subsystem has reached that stage.

## Reclaim transaction

Reclaim uses the immutable PBP1 source ledger as its source of truth. It streams candidate ranges with a scalar `ReclaimCursor` in three complete passes:

1. Preflight source arithmetic, class eligibility, zone splits, retained-source and active-allocation overlap exclusion, coalesced free-ledger capacity, final managed-page totals, receipt capacity, and checksums without changing physical memory or metadata.
2. Zero and read back every admitted page while ownership remains held.
3. Commit preflighted extents, ownership totals, class state, sequence, and one immutable receipt without fallible work.

The implementation intentionally carries no full reclaim-extent snapshot. An earlier dual-array plan consumed enough bootstrap-stack space to stop the live kernel after PKREVAL1; the streamed cursor removed that stack pressure while preserving the same complete preflight semantics. Source audit rejects reintroduction of a fixed `[Extent; MAX_RECLAIM_EXTENTS]` reclaim plan.

A content fault can leave part of the still-held physical range zeroed, so PKPMM4 does not claim byte-level rollback. It does preserve source ownership, free ledgers, managed totals, receipt slots, and sequence, records scrub/reclaim rollback audit counters, and prevents partial admission. Repeating a successful class request returns the exact prior receipt without physical access or state mutation.

## Live adapter and evidence

The adapter uses one supervisor RW/NX temporary alias for physical zero/readback and invalidates it on every remap. `finish()` revokes that alias, proves its translation absent, and revalidates all five metadata leaves and both guards.

The live PKPMM4 profile performs metadata migration, rejects metadata release, advances to `PostExitBootServices`, admits Boot Services exactly once, proves exact idempotence, rejects early ACPI admission, then executes the predecessor ordinary allocate/fill/release/exact-reuse lifecycle. Two fresh-OVMF-vars TCG runs reproduce the same 42 markers, framebuffer captures, and PBP1 bytes.

An independent Python oracle derives target source records, retained exclusions, zone splits, coalesced ranges, free-ledger merge, checksums, and final accounting directly from PBP1. The focused gate passes 79 PooleKernel host tests and 109 hostile controls. Exact live results are:

| Measure | Result |
| --- | ---: |
| PBP1 entries | 97 |
| Conventional usable source pages | 117,919 |
| Initial / final managed pages | 117,918 / 129,168 |
| Boot Services source records / admitted ranges / pages | 70 / 12 / 11,250 |
| Admitted DMA / DMA32 / Normal pages | 2,018 / 9,232 / 0 |
| ACPI reclaimable pages still held | 11 |
| Loader pages protected | 825 |
| Pre/post free extents | 11 / 13 |
| Reclaim coalesces / total coalesces | 10 / 12 |
| Scrubbed and verified pages / bytes | 11,263 / 46,133,248 |
| Physical word writes / reads | 5,767,680 / 5,768,704 |
| Temporary PTE writes / invalidations | 22,543 / 22,543 |
| Range checksum | `0x5A485D4A5725EED8` |
| Reclaim receipt checksum | `0x4D3EBF743B7F2CCC` |

The Cycle 130 kernel retains the prior 70-page geometry: fourteen bootstrap-stack pages, 256 handoff pages, one temporary alias, five metadata pages, and two metadata guards all remain inside the one-page leaf table.

## Nonclaims

N9 remains partial. PKPMM4 has bounded fixed ledgers and no scalable growth, metadata retirement, concurrent/SMP allocator protocol, complete ACPI consumer integration, complete kernel/user address spaces, SMP TLB shootdown, heap/object caches, general kernel stacks, pressure/OOM policy, target-hardware qualification, or second-host result. It performs no signature verification, authority grant, authorized action, firmware mutation, physical-media write, release, or production promotion.
