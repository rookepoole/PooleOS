# PKTRAP1 bounded BSP exception entry

## Scope

`PKTRAP1` is the first live PooleKernel descriptor-table and exception-entry milestone. It extends the opt-in, QEMU-only `PKXFER1` development transfer with three mutually exclusive scenario features while preserving selector `0` for the ordinary unsigned terminal-denial path and preserving the feature-disabled PooleBoot stop-before-transfer path.

This milestone is deliberately smaller than N7. It proves one BSP GDT, one long-mode TSS, one 256-entry IDT allocation with five present exception gates, distinct 8192-byte IST1 and IST2 arrays, a normalized 176-byte integer trap frame, three exact returning synchronous exceptions, one terminal processor-delivered double fault, and one fail-closed semantic malformed-frame control. It does not claim AP-local state, all-vector coverage, external interrupts, NMI, machine check, SIMD/FPU preservation, guarded IST mappings, recursion recovery, or production readiness.

## Transfer selector

PooleBoot validates a shared `DevelopmentTransfer.trap_scenario` value in `0..=4`, places it in `R10`, records it in the `PKXFER1` transfer-arm marker, and jumps once after successful `ExitBootServices`. PKTRAP1 owns only selectors `1..=3`; selector `4` belongs exclusively to PKCPU1. The PooleKernel assembly wrapper preserves the original stack-top argument and places the seventh System V integer argument on the stack before its Rust call.

| Selector | Cargo feature | Terminal result |
| --- | --- | --- |
| `0` | `development-transfer` | Existing unsigned `PKXFER1` denial and halt |
| `1` | `development-trap-returning` | Return from deliberate `#BP`, `#UD`, and guard-page `#PF`; then halt |
| `2` | `development-trap-double-fault` | Contain processor-delivered `#DF` on IST2; then halt |
| `3` | `development-trap-malformed-frame` | Reject a synthetic semantic selector corruption; then halt |
| `4` | `development-cpu-policy` | Separate PKCPU1 read-only CPU-policy observation; outside PKTRAP1 |

The three trap features imply `development-transfer` and are compile-time mutually exclusive. None is a default feature.

## Descriptor state

The BSP builds five GDT entries: null, ring-0 long-mode code, ring-0 data, and the two slots occupied by a 64-bit TSS descriptor. It initializes TSS `RSP0` from the retained PKMAP2 bootstrap stack, IST1 from a private fault array, IST2 from a distinct double-fault array, and disables the I/O bitmap by placing its base at the end of the 104-byte TSS.

The IDT allocation has the architectural 256-entry capacity. Present ring-0 interrupt gates are installed only for `#BP` (3), `#UD` (6), `#DF` (8), `#GP` (13), and `#PF` (14). Vectors 3, 6, 13, and 14 use IST1; vector 8 uses IST2. After `LGDT`, far control transfer, segment reload, `LTR`, and `LIDT`, PooleKernel reads back GDTR, IDTR, CS, SS, TR, and RFLAGS and validates the exact limits, selectors, stack ranges, and disabled interrupt flag before any deliberate fault.

The IST arrays are aligned, bounded, and distinct, but remain part of the kernel data mapping. They have no independent non-present guard pages. The production path must allocate per-CPU guarded stacks before N7 can close.

## Uniform frame

Assembly stubs synthesize error code zero for vectors without a hardware error code and place the vector above either the synthetic or hardware error code. The common stub saves all fifteen general-purpose registers and passes this normalized tail to Rust:

`vector, error_code, rip, cs, rflags, rsp, ss`

The dispatcher accepts depth exactly one; kernel code/data selectors; clear IF and DF; canonical saved RIP/RSP; an exact deliberate origin RIP; the expected IST range; exact error code zero; and exact CR2 for the page-fault case. Only then may it replace RIP with the frozen resume label. The corrected canonical-address predicate now checks bit 47 and its required upper-bit sign extension, closing the earlier acceptance of both noncanonical hole edges.

## Fault scenarios

The returning scenario executes `INT3`, `UD2`, and a read from the verified non-present low guard page below the PKMAP2 bootstrap stack. The first frame already names the post-`INT3` resume address; the `#UD` and `#PF` frames are advanced only to their exact assembly resume labels after validation.

The double-fault scenario removes the otherwise valid `#GP` gate and executes a segment load with a selector beyond the five-entry GDT. The initial contributory `#GP` cannot be delivered, causing the processor to deliver `#DF` through its valid IST2 gate. The handler validates vector 8, error code zero, exact origin, selectors, flags, depth, and IST2 residence, emits the terminal result, and halts. It never returns with the intentionally damaged IDT.

The malformed-frame scenario first validates a real `#BP` frame. It then copies the semantic observation, substitutes the kernel data selector for the expected code selector, requires the pure validator to return `TrapError::CodeSelector`, emits a denial that explicitly identifies `source=synthetic_semantic`, and halts. It does not claim corrupt hardware-frame injection or `IRETQ` hardening against arbitrary frames.

## Qualification

`tools/qualify_native_kernel_trap.py` builds the fixed PooleKernel twice through PKENTRY1, builds the default PooleBoot profile twice, builds each trap profile twice, generates each profile's media twice, and executes two fresh-vars QEMU/OVMF runs per scenario. It requires exact markers, screenshots, and final PBP1 bytes within each scenario; independent media, handoff, and retained-file bindings; dual serial/debugcon agreement; and all 51 marker hostile controls.

The public outputs are `runs/native-kernel-trap-readiness.json` and `runs/native-kernel-trap-frame.ppm`. The receipt remains single-host, QEMU-only, unsigned, non-promoting, and `production_ready=false`.

## Remaining N7 work

- N7.1: PKCPU1 closes only a bounded qemu64 BSP CPUID/feature/topology/address-width observation; exact Tier 1 inventory and AP-local policy remain open.
- N7.2: PKERR1 freezes a pure exact-target policy and exact current denial; applicable Model 40h-4Fh errata authority, a direct numeric microcode floor or ratified replacement, native per-processor evidence, kernel integration, and target qualification remain open.
- N7.3: PKCPU1 closes only a bounded read-only qemu64 CR0/CR4/EFER/XCR0/APIC/PAT/MTRR observation; target state plus syscall/GS/TSC_AUX/MCE/performance MSRs remain open.
- N7.4: PKXSTATE1 proves only bounded eager x87/SSE standard-XSAVE ownership on one QEMU BSP; AVX/extended state, deliberate xstate exceptions, real scheduler/thread integration, AP state, migration, final machine-code SIMD audit, and target evidence remain open.
- N7.5: per-CPU GDT/TSS/IDT, guarded RSP0/IST mappings, AP bring-up integration, generated assembly/Rust offsets, and user-transition frames.
- N7.6: all exceptions, NMI and machine check, external interrupt entry, recursion and stack-exhaustion policy, persistent crash records, recovery routing, and broad adversarial tests.
- Qualification: second independent host, target firmware, physical hardware, and measured production profiles.

The architectural references are the Intel 64 and IA-32 System Programming Guide, the System V x86-64 psABI, and Rust's `x86_64-unknown-none` platform contract, as frozen in `specs/native-kernel-trap-contract.json`.
