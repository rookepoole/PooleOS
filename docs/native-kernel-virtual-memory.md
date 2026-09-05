# PKVM3 PMM-Owned Sparse Direct Map

## Scope

PKVM3 is the Cycle 134 `N9-VM-DIRECT-MAP-001` increment. It replaces the
fixed nine-page PKVM2 mapping with a dynamically sized, generation-bound,
sparse physical direct map derived from PKPMM7 ownership. The selector-10
profile installs the candidate in CR3 on one bootstrap processor with
interrupts disabled, exercises one user frame and three live leaf mutations,
restores the exact retained root, and releases data and table generations only
after exact invalidation and retirement receipts.

This is real native kernel work, but it is not a complete VM subsystem. The
canonical contract is `specs/native-kernel-virtual-memory-contract.json` and
the deterministic live receipt is
`runs/native-kernel-virtual-memory-readiness.json`.

## Ownership Authority

`PhysicalMemoryManager::direct_map_manifest` is the only admission authority.
It merges every current free extent with every active allocation that is not
marked `release_excluded`, sorts and coalesces the resulting physical ranges,
and rejects overlap, arithmetic overflow, capacity overflow, or accounting
drift. Release-excluded allocations are counted but omitted. A PKRETAIN1 token
instead prevents ordinary freeing without changing direct-map admission; the
physical-memory host tests verify that distinction. The manifest binds its
PMM generation, exact ranges, mapped-page count, gap-page count, retained
exclusion count, first and ending page, write-back cache policy, and a 64-bit
FNV coverage checksum.

The VM path previews the manifest to size its tables, allocates one contiguous
DMA32 table generation and the following data frame, then asks PKPMM7 to
reconstruct and compare the complete manifest before materialization. This
works because allocation changes ownership category without changing admitted
coverage. A stale or forged range set, generation, count, boundary, cache
policy, or checksum fails closed.

The live qemu64 profile covers 117,821 owned pages in eleven ranges. It leaves
12,944 pages of physical holes unmapped. Its selector does not run the separate
PKACPI1 retained-snapshot lifecycle, so the live retained-exclusion count is
zero; a host test inserts a release-excluded allocation and proves the resulting hole
is excluded and untranslated.

## Sparse Topology

The direct map begins at `0xFFFF900000000000`, using PML4 slot 288 and the
formula `DIRECT_MAP_START + physical_address`. PKVM3 derives one leaf table for
each occupied 2 MiB physical region and one directory table for each occupied
1 GiB region. The bounded development profile permits at most 512 leaf tables,
four directory tables, and 288 ownership ranges.

Table order is deterministic: candidate PML4, user PDPT, user PD, user PT,
direct-map PDPT, sorted direct directories, then sorted direct leaf tables.
Every admitted physical page receives one supervisor RW/NX, 4 KiB, write-back
leaf. Holes, held firmware pages, loader-retained pages, metadata-retained
pages, and other release-excluded ownership receive no direct leaf. PWT or PCD
on an audited leaf is rejected as an incompatible cache alias. Large pages are
not admitted.

The current live topology contains 237 direct leaf tables, one direct
directory, and five fixed tables, for 243 generation-owned table pages. It
retains the exact PKMAP2 kernel image, RX entry, 36-page guarded stack, and
read-only/NX PBP1 handoff mappings. The bootstrap temporary alias is revoked
and translation-checked immediately before activation.

## Transaction Lifecycle

1. Build the sparse candidate through the volatile PKMAP2 temporary mapper and
   read back every table transition.
2. Audit every admitted leaf, each range edge, every sparse gap, inherited
   kernel permissions, stack guards, handoff boundaries, cache attributes, and
   physical-address-width constraints.
3. Require BSP 0, IF clear, and exact retained CR3; install the candidate and
   require exact readback. A failed activation restores and verifies the old
   root.
4. Write/read probe byte `0xA5`, protect the user leaf from RW/NX to RX, revoke
   the user leaf, and revoke the data direct alias. Each commit creates a
   root-, generation-, CPU-, address-, kind-, and sequence-bound local INVLPG
   receipt. Hardware Accessed/Dirty bits are preserved; all other drift fails.
5. Reject data-frame reuse until both unmap receipts are exact, then scrub and
   release that allocation.
6. Reject root retirement for any active-processor count other than one with
   `ShootdownRequired`. For the one-BSP profile, restore and read back the
   retained root, perform the local context flush implicit in CR3 replacement,
   and mint one exact generation-retirement receipt.
7. Keep old-generation reclamation deferred until that receipt is supplied,
   zero and verify all 243 inactive table pages, revoke the temporary alias,
   then release the table generation. Missing, stale, reordered, or
   remote-pending receipts are rejected.

Host fault injection covers manifest forgery, retained sparse holes, cache
attribute drift, candidate-write rollback, CR3 rollback, premature reuse,
missing and stale retirement receipts, and the future multi-processor
shootdown dependency.

## Qualification

Two fresh-vars QEMU/OVMF executions reproduce the same 40 markers, framebuffer,
and exact PBP1 transcript. Two hundred fourteen PooleKernel host tests, 43 PKENTRY1
controls, and 46 PKVM3 hostile controls pass. An independent Python oracle
reconstructs PMM ranges, page-zero exclusion, DMA32 first fit, topology,
addresses, gap counts, and the coverage checksum from the PBP1 transcript.

The Cycle 156 replay records 117,821 mapped pages, eleven ranges, 12,944 gap
pages, 237 direct leaf tables, one direct directory, 243 total table pages,
checksum `0x64E09067B6BFDCB3`, 367,408 physical table writes, 950,682 temporary-PTE
writes and matching bootstrap invalidations, two CR3 writes, three local leaf
invalidations, and one generation-retirement receipt. The 517,784-byte
canonical kernel occupies a 144-page, 589,824-byte image, has 1,304 relocations,
and SHA-256 `BDEECCB27B1B91406911F91169B9BF5F9DF0439BB39FA0E1882C07E1AF3B81EF`.
The independent PBP1 oracle accounts for one additional loader-protected page
and one fewer admitted direct-map page than the preceding receipt. The table
topology and CR3, invalidation, and retirement sequence are unchanged. This
replay changes no native executable bytes and does not qualify concurrent
retention or general inter-processor reclamation.

## Remaining Boundary

PKVM3 itself executes no inter-processor shootdown. PKSMP5 separately proves
three exact AP-side one-page invalidations and aggregate acknowledgement for
three private roots and one generation, but general address-space-wide or
concurrent-generation shootdown remains mandatory. Concurrent allocation and incremental
map replacement, huge-page promotion/demotion, PCID and global-page policy,
KASLR, COW, ring 3, user faults, stack growth, pager IPC, heaps, MMIO and
PAT/MTRR qualification, pressure/OOM behavior, target hardware, second-host
reproduction, and the N9 exit gate also remain open. Signatures, authority
grants, authorized actions, and production claims are all zero.
