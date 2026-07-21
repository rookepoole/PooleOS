# Kernel

PooleKernel common mechanisms and architecture-specific code live here. General drivers, filesystems, networking, storage policy, PGVM2, PDC policy, and desktop behavior do not.

The x86-64 implementation boundary is `arch/x86_64/`. Cycle 101 introduces the first product crate and `PKENTRY1` direct-jump boundary. The linked image is canonicalized into PKELF1 after pinned LLD emits the real position-independent code and relative relocations.

This boundary validates PBP1 before using records, writes allocation-free early ring and bounded COM1 logs, can render a fixed early framebuffer alphabet when PKENTRY1's temporary identity mapping is present, records a deterministic build identity, and halts after the ordinary entry proof. PKTRAP1 additionally installs a bounded BSP-only GDT/TSS/IDT and executes three QEMU-only exception scenarios. PKCPU1 adds a mutually exclusive selector-4 profile that reads and validates a bounded qemu64 CPUID, CR0/CR4/EFER, XCR0, and APIC/PAT/MTRR snapshot without changing CPU or MSR state. It does not establish target-family or errata policy, xstate ownership, AP-local CPU state, per-CPU descriptors, all-vector interrupts, memory management, user mode, a production PooleBoot transfer, or N6/N7 completion.

Cycle 105's bounded PKLOAD4 path reads this canonical product through live UEFI filesystem calls, materializes and validates it in firmware pages, hashes it, binds its live allocation into a temporary pre-exit PBP1 snapshot, temporarily activates and audits its PKMAP1 higher-half alias, restores the original CR3, and releases every temporary page. PBP1 stack and CR3 remain zero, the kernel-entry profile rejects, and no transferable PBP1 or PooleKernel execution occurs yet.
