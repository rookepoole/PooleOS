# PooleKernel typed atomics (PKATOM1)

## Status

PKATOM1 is the bounded N12.1 atomic substrate for the native x86-64 PooleKernel. It is pre-production evidence, not an N12 exit, lock-family, reclamation, general SMP, physical-target, or production claim.

The authoritative machine-readable files are:

- `specs/native-kernel-atomics-contract.json`
- `specs/native-kernel-atomics-contract.schema.json`
- `specs/native-kernel-atomics-readiness.schema.json`
- `runs/native-kernel-atomics-readiness.json`

The implementation is `native/kernel/src/atomics.rs`. The live selector-21 path is in `native/kernel/src/main.rs`; the host concurrency probe is `native/kernel/src/bin/pkatom1_probe.rs`; and `tools/qualify_native_kernel_atomics.py` rebuilds and verifies the complete bounded profile.

## Type and operation surface

PooleKernel owns transparent wrappers over `core::sync::atomic` for:

- `AtomicU32`
- `AtomicU64`
- `AtomicUsize`
- `AtomicPtr<T>`

The freestanding build fails at compile time unless native 32-bit, 64-bit, and pointer atomics are available. The frozen operations are load, store, exchange, strong and weak compare-exchange, fetch add/subtract, fetch and/or/xor, bounded bit set/clear, fence, compiler fence, and overflow-safe reference acquire/release.

The wrappers are allocation-free. They are intended for aligned, ordinary write-back memory. They do not replace volatile MMIO, establish DMA coherence, prevent ABA, or make referenced objects safe to reclaim.

## Typed ordering contract

Call sites cannot pass an unrestricted ordering to an operation that rejects it. Separate types encode the accepted surface:

| Operation | Accepted orders |
| --- | --- |
| Load | Relaxed, Acquire, SeqCst |
| Store | Relaxed, Release, SeqCst |
| Read-modify-write | Relaxed, Acquire, Release, AcqRel, SeqCst |
| Fence | Acquire, Release, AcqRel, SeqCst |

Compare-exchange accepts nine success/failure pairs. Failure ordering is load-like and may not be `Release` or `AcqRel`; it may not be stronger than the selected success order. The independent Python oracle and the Rust unit tests both reject eleven invalid load, store, fence, and compare-exchange combinations.

Correctness is defined by the language memory model. x86-64 Total Store Order is a target property and never an excuse to omit the operation's explicit compiler ordering.

## Reference counts and progress

`RefCount` accepts initial values from 1 through `u32::MAX - 1`. Acquire rejects a zero or maximum count, and release rejects zero. A successful release reports both the remaining count and whether it became zero.

Reference acquire/release uses a compare-exchange retry loop and therefore has no wait-free or starvation bound. It is not admitted to interrupt context. The live interrupt path uses only bounded, single-operation acquire loads and acq-rel RMWs with no caller retry loop.

Reference-count transition to zero is not reclamation authority. N12 still requires an ABA-safe deferred reclamation design and qualification.

## Verification layers

The PKATOM1 qualifier establishes all of the following on one Windows host:

1. The canonical PKENTRY1 build, formatting, Clippy, and all PooleKernel host tests pass under the pinned workspace-local Rust toolchain.
2. A two-thread host probe completes 4,096 release/acquire publication rounds without a stale payload.
3. Four host threads complete 16,384 fetch-add operations and 4,096 compare-exchange increments without loss.
4. A two-thread sequentially consistent store-buffering probe completes 2,048 rounds without the forbidden both-zero outcome.
5. The final `x86_64-unknown-none` linked kernel contains seven stable audit symbols. Hash-bound `llvm-objdump` output must show the required load/store, `xchgq`, locked `cmpxchgq`, locked `xaddq`, CAS-loop bitwise RMW, and locked sequentially consistent fence classes.
6. The selector-21 UEFI image boots twice with fresh variable stores under the pinned QEMU/OVMF qemu64 TCG profile. Eight local-APIC timer deliveries each observe the release-published value and perform typed acq-rel count and bit-mask updates before EOI.
7. Both runs emit the exact 41-marker transcript and identical framebuffer and PBP1 evidence, then restore the PKATOM1 globals to zero.
8. Twenty-nine hostile control families must reject every declared malformed input or overclaim.

The default PooleBoot binary remains distinct and stops before transfer. Selector 21 exists only in a feature-gated development binary.

## Linked instruction contract

The linked instruction review is deliberately narrow. It checks these exact externally named functions in the final linked product:

| Symbol | Required instruction class |
| --- | --- |
| `poole_atomic_audit_load_acquire` | ordinary `movq` load |
| `poole_atomic_audit_store_release` | ordinary `movq` store |
| `poole_atomic_audit_exchange_seqcst` | memory `xchgq` |
| `poole_atomic_audit_compare_exchange_acqrel` | locked `cmpxchgq` |
| `poole_atomic_audit_fetch_add_relaxed` | locked `xaddq` |
| `poole_atomic_audit_fetch_or_acqrel` | locked `cmpxchgq` retry loop with `orq` |
| `poole_atomic_audit_fence_seqcst` | locked stack operation |

This verifies the current pinned compiler's critical lowering for these shapes. It is not a universal promise about every inlined call site, future compiler, architecture, cache type, or device-memory operation. Tool, disassembly, symbol body, linked image, and canonical image hashes are stored in the readiness receipt.

## Live interrupt profile

Selector 21 reuses the qualified one-BSP PKIRQ1 local-APIC/HPET setup. Before interrupts are enabled, process context release-publishes `0xC0DEC0DE` and clears the atomic count and mask. On each of eight timer deliveries, the handler:

1. acquire-loads and validates the publication;
2. acq-rel increments the delivery count;
3. acq-rel sets the delivery's bit in the mask;
4. performs the existing ordered APIC EOI path.

After interrupts are disabled, process context requires count 8, mask `0x000000FF`, the original publication value, and exact PKIRQ1 delivery/EOI evidence. It then exercises the typed API, emits the bounded markers, clears all three globals with release stores, verifies zero with acquire loads, and halts.

## Non-claims and next dependency

PKATOM1 does not claim general locks, lock ordering, IRQ-safe locks, reader/writer locks, seqlocks, RCU, hazard pointers, deferred reclamation, live multi-AP atomic contention, weak-memory portability, physical hardware, ring 3, N12 completion, signatures, production authority, or production readiness.

The next owner-independent dependency is N12.2: define and qualify the complete PooleKernel lock family and lock-order contract against this typed substrate. Production release remains gated on every applicable N0-N39 requirement and the exact signed ISO receipt.
