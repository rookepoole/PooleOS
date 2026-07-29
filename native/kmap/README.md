# PKMAP2

`poole-kmap` is the allocation-free, `no_std` x86-64 page-table contract used
by PooleBoot. It preserves the PKMAP1 exact 4 KiB supervisor kernel mapping and
adds a retained eight-page guarded stack plus a one-MiB read-only/NX handoff
window. Independent walkers and fingerprints cover kernel permissions, guard
absence, retained-range overlap, framebuffer translation/cache preservation,
and exact leaf contents.

The crate does not allocate firmware pages, write CR3, call UEFI, switch RSP,
or execute PooleKernel. Those operations belong to the PooleBoot adapter and
later native phases.
