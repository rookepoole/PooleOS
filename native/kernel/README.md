# Kernel

PooleKernel common mechanisms and architecture-specific code live here. General drivers, filesystems, networking, storage policy, PGVM2, PDC policy, and desktop behavior do not.

The x86-64 implementation boundary is `arch/x86_64/`. Cycle 101 introduces the first product crate and `PKENTRY1` direct-jump boundary. The linked image is canonicalized into PKELF1 after pinned LLD emits the real position-independent code and relative relocations.

This boundary validates PBP1 before using records, writes allocation-free early ring and bounded COM1 logs, can render a fixed early framebuffer alphabet when PKENTRY1's temporary identity mapping is present, records a deterministic build identity, and halts after the entry proof. It does not establish page tables, descriptor tables, interrupts, memory management, user mode, live PooleBoot transfer, or N6 completion.
