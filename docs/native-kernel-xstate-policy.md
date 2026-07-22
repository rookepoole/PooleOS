# Native Kernel Xstate Policy (PKXSTATE1)

Status: bounded single-BSP QEMU development proof; pre-production; N7.4 remains partial.

## Purpose

PKXSTATE1 freezes the first executable PooleKernel x87/SSE/XSAVE ownership boundary. It replaces implicit firmware inheritance with an explicit eager policy, bounded per-context images, canonical initialization, round-trip evidence, sensitive-image clearing, and fail-closed context-switch preconditions.

The contract is `specs/native-kernel-xstate-policy-contract.json`. The independent oracle is `runtime/native_kernel_xstate_policy.py`, and the generated receipt is `runs/native-kernel-xstate-policy-readiness.json`.

## Frozen profile

- opt-in PooleBoot feature: `development-xstate-policy`;
- transfer selector: `5`;
- pinned QEMU/OVMF and q35 foundation inherited unchanged from Tier 0;
- distinct CPU overlay: `EPYC-Rome-v4,-avx,-avx2,-fma,-f16c,-pku`;
- one BSP, one vCPU, TCG single-thread, fresh copied VARS per run;
- terminal halt after evidence; no scheduler, SMP, target-hardware, authority, or production promotion.

The overlay does not amend the frozen `qemu64` Tier-0 profile. It is local to the PKXSTATE1 qualification command and is recorded byte-for-byte in its readiness receipt.

## Architectural policy

PKXSTATE1 selects only XCR0 bits 0 and 1: x87 and SSE. CPUID must report x87, FXSAVE/FXRSTOR, SSE, SSE2, XSAVE, OSXSAVE, and both selected XCR0 components. The selected state uses:

- eager save/restore; CR0.TS is clear and any `#NM` is unexpected;
- standard-format `XSAVE64` and `XRSTOR64`;
- XSS zero and no XSAVES/XRSTORS or compacted supervisor format;
- 4,096-byte, 64-byte-aligned per-context areas, with CPUID-reported enabled size bounded to 576-4,096 bytes;
- x87 control word `0x037F`;
- MXCSR `0x1F80`, accepted only after masking against MXCSR_MASK, with architectural fallback `0x0000FFBF` when the reported mask is zero;
- masked x87 and SSE exceptions;
- no kernel SIMD outside the dedicated PKXSTATE1 proof path.

The privileged implementation performs exactly three configuration writes: CR0, CR4, and XCR0. It performs no MSR or firmware write.

## Ownership proof

Two isolated owner images, IDs 10 and 11, receive distinct XMM0 patterns. The kernel saves each image, restores each image, and compares the recovered value exactly. An explicit standard-format canonical image encodes FCW `0x037F`, MXCSR `0x1F80`, zero x87/XMM payloads, and XSTATE_BV `0x3`; it is restored before first use and after the round trip.

Before a semantic context switch is accepted, the pure Rust and Python evaluators require distinct nonzero owners, separate aligned images, the exact XCR0 mask and image size, an initialized incoming image, scheduler-lock ownership, interrupts disabled, no active kernel SIMD, and same-CPU execution. These checks define future scheduler integration preconditions; they do not claim scheduler integration.

After the final canonical restore, both 4,096-byte context images are volatile-zeroed and read back as 8,192 zero bytes. XMM0 is probed as zero. The canonical image initializes every selected component; the receipt does not claim a byte probe of every physical vector register.

## Failure boundary

The oracle rejects marker omission, order and duplication faults; selector or contract drift; missing x87/SSE/XSAVE features; invalid XCR0 or XSS; XSAVES exposure; malformed size or alignment; CR0/CR4 policy faults; noncanonical FCW/MXCSR state; wrong save/restore counts; unsupported XSTATE_BV bits; cross-context contamination; missing scheduler preconditions; kernel SIMD use; incomplete clearing; unexpected `#NM`; unauthorized writes, signatures, grants, actions; and scheduler, SMP, or target overclaims.

## Source binding

The architecture basis is AMD, *AMD64 Architecture Programmer's Manual Volume 2: System Programming*, publication 24593, revision 3.44, March 2026: <https://docs.amd.com/v/u/en-US/24593_3.44_APM_Vol2>.

The exact captured PDF was 12,560,767 bytes with SHA-256 `3D9DCB3F68222392D0EDE9970EFC95E31A047A247D54B454123D6981D278C48C`. The PDF is not redistributed in this repository.

## Open work

- qualify AVX and every selected extended component with dependency-aware XCR0/XSS policy;
- add deliberate `#MF`, `#XM`, and, if a lazy strategy is ever selected, `#NM` delivery/recovery evidence;
- integrate allocation and lifecycle of per-thread images with the real scheduler;
- initialize and compare all AP-local xstate policy before user scheduling;
- define CPU-migration homogeneity and incompatible-state rejection;
- add final linked-machine-code auditing for unintended compiler vector instructions;
- qualify the exact Ryzen 7 9800X3D target and complete the N7 exit gate.
