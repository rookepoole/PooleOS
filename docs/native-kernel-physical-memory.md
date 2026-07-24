# Native physical-memory foundation

`PKPMM6` is the N9 automatic allocator-metadata growth increment. It is
an opt-in, BSP-only, qemu64 Tier-0 development profile selected by PooleBoot
selector `8`; the default image still stops before kernel transfer. It preserves
the PKPMM5 generation transaction and PKPMM4 lifecycle-gated reclaim proofs
while checking exact post-operation pressure before each scrubbed allocate or
free. It does not promote N9 or PooleOS to production.

## Ownership boundary

PooleKernel consumes the exact post-`ExitBootServices()` PBP1 map,
independently revalidates every normalized UEFI source-type/kind pair, and
initially admits only `MEMORY_USABLE` (`EfiConventionalMemory`) pages. Page zero
is an explicit null guard. The kernel image, retained handoff, active root,
guarded bootstrap stack, stable manager, active ledger generation, and all
other allocations remain protected by immutable source-ledger and active-
allocation exclusions.

This follows the UEFI 2.11 boundary: firmware owns the map before
`ExitBootServices()`; after successful exit the OS may reclaim unused Boot
Services memory but must preserve runtime ranges. ACPI reclaimable memory stays
held until every required table consumer has copied or released it. Runtime
memory, ACPI NVS, MMIO, persistent, unusable, and reserved memory are never
PKPMM6 candidates.

Official references:

- <https://uefi.org/specs/UEFI/2.11/07_Services_Boot_Services.html#efi-boot-services-getmemorymap>
- <https://uefi.org/specs/UEFI/2.11/07_Services_Boot_Services.html#efi-boot-services-exitbootservices>

## Stable manager

The allocation-free Rust bootstrap manager contains bounded arrays for 256
PBP1 source records, 256 free extents, 32 allocations, 16 scrub receipts, and
two reclaim receipts. It divides ranges into DMA (below 16 MiB), DMA32 (16 MiB
through 4 GiB), and Normal (above 4 GiB) zones. Allocation is deterministic
first-fit within one requested zone and has a 64-page development-profile
quota.

Selector 8 reserves and scrubs five DMA32 pages under owner `0x4D45`, marks the
allocation release-excluded, and maps the complete 15,376-byte manager
supervisor RW/NX at `0xFFFFFFFF80160000` between absent guards. Its versioned
header and FNV-1a-64 logical checksum bind every ownership field. Mapping or
handoff failure revokes every installed leaf, scrub-releases the reservation,
and leaves the bootstrap manager usable. This is corruption detection, not
cryptographic authentication.

The bootstrap arrays remain available for construction and rollback. Once a
ledger generation is active, every ordinary allocator, scrub, reclaim, and
integrity operation addresses the active mapped generation; no shadow fixed
array is authoritative.

## Ledger generations

PKPMM6 reserves two alternate virtual windows in the retained PKMAP2 leaf
table. Each window has 32 data-page slots and independent absent low/high
guards. Window A data begins at `0xFFFFFFFF80167000`; window B begins at
`0xFFFFFFFF80189000`. Only the pages owned by the current generation are
present.

The live profile materializes four generations:

1. Generation 2 maps four pages with capacities `256/32/256/16/2` for free
   extents, allocations, source records, scrub receipts, and reclaim receipts.
2. Checked pressure automatically maps generation 4 in eight pages with
   capacities `512/64/512/32/4`.
3. The next pressure threshold maps generation 8 in fifteen pages with
   capacities `1024/128/1024/64/8`.
4. The final successful threshold maps generation 16 in twenty-nine pages with
   capacities `2048/256/2048/128/16`; its successful retirement advances the
   stable descriptor to generation 32.

Before every automatic scrubbed allocate or free, the manager computes exact
post-operation demand. Growth reserves one allocation slot and four scrub
receipts so a failed candidate can be scrub-released and the requested
operation retried. The measured run performs 121 checks, sees eight pressure
triggers, completes three automatic growths across sixty allocation/free
cycles, and records four soft fallbacks. A doubled next layout would require 58
pages, so the bounded 32-page window rejects it. Operations that still fit the
active generation continue through the soft fallback; a request that does not
fit is rejected before physical reads, physical writes, ownership changes, or
receipt commitment.

Each transaction completes capacity and aligned-layout preflight, reserves and
zero-verifies candidate pages, marks them release-excluded, maps the alternate
guarded window, copies every complete ledger, seals and verifies both manager
and generation, commits one descriptor switch, revokes the old mapping, then
zero-verifies and releases the retired pages. The generation checksum covers
the header, complete capacity-sized ledgers, and stable-manager ownership
state.

A precommit mapping or integrity fault restores the exact previous descriptor,
revokes the candidate window, and scrub-releases the candidate allocation. A
postcommit retirement fault keeps both allocations owned, records pending
retirement, blocks another growth, and requires explicit retry. Host fault
tests cover mapping failure, corruption, retirement failure, successful
retirement retry, pressure rollback with retry headroom, repeated growth, soft
fallback, and hard pre-effect rejection. The live run records four mapping
events, 83 ledger PTE writes, four guards, three revoked generations totaling
27 pages, and one retained 29-page generation.

## Scrub and reclaim

`allocate_scrubbed` plans without changing ownership, writes zero to every
64-bit word, reads every word back, and commits only after full verification.
`free_scrubbed` validates the slot, generation, range, zone, and owner; it
preflights reinsertion before content writes and leaves ownership live on any
fault. Adjacent same-zone extents coalesce. Successful operations emit immutable
sequence, range, generation, owner, zeroed-byte, and verified-byte receipts.

The monotonic reclaim stages remain `PreExitBootServices`,
`PostExitBootServices`, and `AcpiTablesReleased`. Stages cannot skip or regress.
The live profile admits Boot Services only at the second stage and rejects ACPI
admission before the third. The host suite separately proves positive ACPI
admission after explicit release; PKPMM6 does not claim a real ACPI consumer has
issued that release.

Reclaim streams the immutable PBP1 ledger through complete arithmetic,
capacity, retained-overlap, active-overlap, free-ledger, receipt, and checksum
preflight; full zero/readback while ownership remains held; then an infallible
metadata commit. A content fault may leave held bytes zeroed but preserves
ownership, ledgers, totals, receipts, and sequence. Exact repeats return the
prior immutable receipt without physical access.

## Live evidence

The privileged adapter uses one supervisor RW/NX temporary alias for physical
scrub/readback, invalidates every remap, and revokes it before terminal success.
It independently validates stable-manager guards plus both ledger-window guards
and proves exactly one final ledger mapping retained.

Two fresh-OVMF-vars TCG runs reproduce the same 43 markers, framebuffer bytes,
and PBP1 bytes. An independent Python oracle derives source classes, manager and
generation first-fit ownership, retired-generation free space, zone splits,
coalescing, reclaim checksums, and final accounting directly from PBP1. The
focused gate passes 84 PooleKernel host tests and 147 hostile controls.

| Measure | Result |
| --- | ---: |
| PBP1 entries | 97 |
| Conventional usable source pages | 117,911 |
| Initial / final managed pages | 117,910 / 129,160 |
| Stable manager / final active ledger pages | 5 / 29 |
| Ledger page sequence | `4 / 8 / 15 / 29` |
| Final ledger capacities | `2048/256/2048/128/16` |
| Retired generations / pages | 3 / 27 |
| Pressure checks / triggers / automatic growths | 121 / 8 / 3 |
| Soft fallbacks / hard pre-effect rejections | 4 / 1 |
| Boot Services source records / ranges / pages | 70 / 12 / 11,250 |
| Admitted DMA / DMA32 / Normal pages | 2,018 / 9,232 / 0 |
| ACPI pages held / loader pages protected | 11 / 833 |
| Reclaim pre/post free extents | 12 / 14 |
| Reclaim / total coalesces | 10 / 72 |
| Scrubbed and verified pages / bytes | 11,462 / 46,948,352 |
| Physical word writes / reads | 5,869,568 / 5,870,592 |
| Temporary PTE writes / invalidations | 22,798 / 22,798 |
| Ledger checksum | `0xF7AD111CA266071D` |
| Reclaim range / receipt checksums | `0x5A485D4A5725EED8` / `0xE1F4C87AE4009940` |

The Cycle 132 image occupies 78 pages. The retained layout uses indices 78 and
93 as stack guards, 79-92 for the stack, 94-349 for PBP1, 350 for the temporary
alias, 351/357 for stable-manager guards, 352-356 for the manager, 358/391 for
window A guards and 359-390 for its data, and 392/425 for window B guards and
393-424 for its data.

## Nonclaims

N9 remains partial. PKPMM6 proves serial checked automatic growth only inside
two bounded 32-page windows. It deliberately fails closed when exact demand no
longer fits and a 58-page next generation cannot be represented. There is no
concurrent, interrupt-context, or SMP allocator protocol, complete ACPI
consumer integration, complete
generation-owned address space, SMP TLB shootdown, heap/object cache, general
kernel stack allocator, pressure/OOM policy, target-hardware qualification, or
second-host result. The profile performs no signature verification, authority
grant, authorized action, firmware mutation, physical-media write, release, or
production promotion.
