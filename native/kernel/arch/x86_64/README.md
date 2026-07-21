# PooleKernel x86-64

CPU entry, descriptors, faults, interrupts, timers, SMP, context primitives, page-table operations, I/O authorization, and architecture audit fixtures belong here.

`PKENTRY1` begins with `CLI` and `CLD`, verifies the 16-byte direct-jump stack, then calls Rust through the System V AMD64 ABI. PKTRAP1 adds a BSP GDT, 64-bit TSS, five present IDT gates, two bounded IST arrays, normalized integer frames, deliberate returning `#BP`/`#UD`/`#PF`, terminal `#DF`, and semantic malformed-frame denial. PKCPU1 adds support-gated read-only CPUID, CR0/CR4, EFER/APIC/PAT/MTRR, and XGETBV observation for a bounded qemu64 development policy; it performs no control-register or MSR writes. Exact target-family and errata policy, SIMD/FPU/xstate ownership, AP-local CPU state, guarded per-CPU descriptors, all-vector interrupt state, page-table ownership, and SMP remain later gates.
