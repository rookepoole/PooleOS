# Native Kernel Xstate Exceptions (PKXEXC1)

Status: bounded single-BSP QEMU development proof; pre-production; N7.4 remains partial.

## Purpose

PKXEXC1 extends the parent PKXSTATE1 eager x87/SSE ownership policy with real exception delivery. It deliberately creates one x87 invalid-operation `#MF`, one scalar SSE invalid-operation `#XM`, and one terminal test-only `#NM`. The first two handlers validate their trap frame and pending architectural state, perform one bounded recovery write, and resume at an exact assembly label. The `#NM` handler confirms the eager-policy violation without sampling x87/SSE state and halts.

The contract is `specs/native-kernel-xstate-exception-contract.json`. The independent oracle is `runtime/native_kernel_xstate_exception.py`, and the generated receipt is `runs/native-kernel-xstate-exception-readiness.json`.

## Frozen Profile

- opt-in PooleBoot feature `development-xstate-exception` and transfer selector `6`;
- pinned QEMU/OVMF q35 foundation with WHPX hardware acceleration and CPU overlay `EPYC-Rome-v4,-avx,-avx2,-fma,-f16c,-pku`;
- one BSP, one vCPU, TCG single-thread, two runs with fresh copied VARS;
- parent PKXSTATE1 policy re-executed and validated before exception gates are installed;
- vectors 7, 16, and 19 installed as ring-0 interrupt gates on IST1;
- execution on a host reporting `AMD Ryzen 7 9800X3D 8-Core Processor`, without promoting the virtualized receipt into bare-metal target qualification;
- terminal halt after evidence, with no scheduler, SMP, target-hardware, authority, or production promotion.

## Exception Paths

The x87 helper loads FCW `0x037E`, computes zero divided by zero, and executes `FWAIT` at an exported fault label. Vector 16 validates a zero error code, exact fault RIP, IST1 frame, unmasked invalid-operation and summary status, and canonical MXCSR. `FNINIT` is the sole recovery write; the handler verifies FCW `0x037F`, cleared relevant FSW bits, unchanged MXCSR `0x1F80`, rewrites RIP to the exported resume label, and returns once.

The SIMD helper loads MXCSR `0x1F00`, computes scalar zero divided by zero with `DIVSS`, and traps at an exported fault label. Vector 19 validates a zero error code, exact fault RIP, IST1 frame, MXCSR invalid status with its mask clear, and canonical x87 state. Loading MXCSR `0x1F80` is the sole recovery write before exact resume and return.

The terminal helper sets only CR0.TS and immediately executes `FNOP`. Vector 7 validates the exact origin and confirms the eager-policy violation. It does not execute x87, SSE, FXSAVE, XSAVE, or state-recovery instructions, because any such operation while TS remains set could recurse. The path is a qualification injection, not a lazy-switch implementation.

## TCG Limitation

Pure QEMU TCG does not reliably deliver unmasked x86 floating-point exceptions. The PKXEXC1 limitation probe observes `DIVSS` return with MXCSR `0x1F01`: invalid status is set, its mask is clear, and CR4.OSXMMEXCPT remains set, but vector 19 is absent. This matches the open QEMU Project report [issue 215](https://gitlab.com/qemu-project/qemu/-/issues/215). The passing exception matrix therefore uses WHPX hardware acceleration. Tier 0 and the parent PKXSTATE1 proof remain on their frozen TCG profiles.

## Machine-Code Boundary

The qualifier builds a fresh linked PooleKernel and audits its disassembly with workspace-local `llvm-objdump` from Rust 1.97.0 `llvm-tools-preview`. The executable is 35,279,360 bytes, SHA-256 `84DE1EDCEFED12FEB797F8B1C41DEBA99B6116A6BB3B80A1832FFF2CC06F2F94`, and reports LLVM `22.1.6-rust-1.97.0-stable`. Its official archive SHA-256 is `671B509EC2C9220916D25D8FD546E71EFB552439F8E7AE75CE53208D9395DFB4`; the license is Apache-2.0 WITH LLVM-exception.

The audit requires the exact `FWAIT`, `DIVSS`, CR0.TS write, `FNOP`, `FNINIT`, and `LDMXCSR` forms in named scopes and rejects vector-register instructions outside the established PKXSTATE1/PKXEXC1 allowlist. A synthetic disassembly mutation must be rejected. This is evidence for the exact linked image, not a proof about future binaries.

## Source Binding

The architectural basis is AMD, *AMD64 Architecture Programmer's Manual Volume 2: System Programming*, publication 24593, revision 3.44, March 2026: <https://docs.amd.com/v/u/en-US/24593_3.44_APM_Vol2>.

The captured PDF was 12,560,767 bytes with SHA-256 `3D9DCB3F68222392D0EDE9970EFC95E31A047A247D54B454123D6981D278C48C`. The PDF is not redistributed in this repository.

## Open Work

- define user-task floating-point exception policy and delivery semantics;
- integrate xstate images with real thread lifecycle and the scheduler;
- qualify AP initialization, SMP homogeneity, and CPU migration behavior;
- qualify AVX and every subsequently selected extended component;
- run the same exception matrix on the exact Ryzen 7 9800X3D target;
- complete the remaining N7 architecture and target-hardware exit gates.
