# PooleKernel x86-64

CPU entry, descriptors, faults, interrupts, timers, SMP, context primitives, page-table operations, I/O authorization, and architecture audit fixtures belong here.

`PKENTRY1` begins with `CLI` and `CLD`, verifies the 16-byte direct-jump stack, then calls Rust through the System V AMD64 ABI. The Cycle 101 proof uses only a bounded fixed COM1 candidate and a temporary framebuffer identity-mapping precondition. Discovery, GDT/IDT/TSS, fault entry, page-table ownership, and SMP remain later gates.

