# Native Kernel AP-Local Runtime (PKSMP2)

Status: bounded development evidence; non-promoting; N8 remains partial.

PKSMP2 advances the single-AP PKSMP1 bootstrap into one processor-local runtime instance. In the frozen `pc-q35-11.0`, `SandyBridge,-avx`, two-vCPU TCG profile, APIC ID 1 transitions through 16-bit, 32-bit, and 64-bit startup code and then loads AP-owned runtime state before reporting online.

## Implemented proof surface

- A 32-page low-memory transaction allocates one RX trampoline, four paging pages, one processor-local mailbox page, one GDT/TSS page, one RO/NX IDT page, four RSP0 pages, two two-page IST stacks, and one xstate page.
- Fourteen guard pages and one reserved page are absent from the AP identity map. Thirteen runtime leaves are mapped. Mutable runtime pages are RW/NX.
- The AP executes hardware `LGDT`, `LTR`, and `LIDT`; the BSP subsequently verifies the hardware-set busy TSS descriptor and all installed IDT gates from memory.
- Eight exception gates and nineteen owned interrupt gates are installed. Interrupts stay disabled, and the interrupt gates do not constitute an IPI service.
- The AP enables OSXSAVE, selects x87/SSE in XCR0, initializes architectural x87/SSE state, executes one XSAVE/XRSTOR round trip, and clears its owner token.
- The BSP independently validates processor identity, CPUID, control registers, descriptor state, stack geometry, xstate state, interrupt state, timestamps, and two FNV-1a mailbox checksums.
- Shutdown requires commanded quiescence, a final INIT park, post-AP resource-image validation, revocation, zero verification, and release of all 32 pages.

## Qualification boundary

The canonical readiness receipt requires two clean media generations and two live boots with 42 markers each. Static markers, framebuffer capture, and PBP1 handoff bytes must match exactly. Timestamps and both checksums are dynamic and are independently revalidated on each run. Nineteen hostile-control categories execute 159 rejection cases covering every PKSMP2 marker field, source invariants, layout failures, and unsupported topology models.

PKSMP2 does not implement general SMP, an IPI delivery service, TLB shootdown, scheduler CPU ownership, migration, multiple APs, x2APIC, NUMA, hotplug, physical-target qualification, the N8 exit gate, or production readiness. The next native dependency is capability-gated IPI delivery with acknowledgement and timeout semantics, followed by remote TLB-generation retirement.
