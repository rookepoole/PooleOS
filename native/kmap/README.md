# PKMAP1

`poole-kmap` is the allocation-free, `no_std` page-table contract used by the
bounded PooleBoot kernel-mapping proof. It validates one 2 MiB higher-half
window, constructs exact 4 KiB supervisor leaves, walks existing four-level
x86-64 mappings, compares framebuffer translation/cache state, and enforces
activation/rollback/release ordering.

The crate does not allocate pages, write CR3, call UEFI, execute PooleKernel,
or establish the final PooleOS address space. Those operations remain in the
PooleBoot adapter and later native phases.
