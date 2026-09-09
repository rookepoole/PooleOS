# Native PooleKernel Entry

`PKENTRY1` is the candidate x86-64 product-side contract for transferring from PooleBoot into the first real freestanding PooleKernel image. The product is a canonical `PKELF1` file built from the `poolekernel` Rust package. The old empty kernel fixture remains under `native/fixtures/poolekernel` and cannot satisfy this boundary. The separate `PKXFER1` receipt owns the opt-in QEMU-only live-execution claim.

## Transfer Boundary

PooleBoot must complete authenticated selection, load and relocate the kernel, install final page tables, obtain the final memory map, successfully call `ExitBootServices`, and establish the `PBP1` mappings before a direct jump. `RDI` is the immutable PBP1 virtual address, `RSI` its exact length, `RDX` its magic value, and `RSP` the nonzero canonical 16-byte-aligned initial stack top. The wrapper clears interrupts and the direction flag again, checks the stack without using it, and only then crosses the System V AMD64 ABI into Rust.

The current product validates the handoff envelope, decodes PBP1 without allocation, distinguishes the authenticated production profile from the exact QEMU-only development profile, and checks handoff address, length, entry, stack, CR3, IF, and DF continuity. PKREVAL1 then independently reparses exact retained PSM1, six PBART1 inner files, PBTP1, and PBTS1 bytes and requires exact unsigned-policy denial before any authority path. The kernel records bounded diagnostics in a 4096-byte static ring, emits matching COM1 and QEMU debugcon bytes, and can render a small volatile framebuffer message when its optional mapping precondition holds. Stable panic classes include transfer-state and reentry failures as well as Rust panic, handoff envelope, decode, profile, continuity, retained-byte revalidation, and unexpected return.

## Framebuffer Mapping Gap

PBP1 carries a framebuffer physical aperture, not proof of a usable virtual mapping. `ADD-KERNEL-001` therefore requires PooleBoot to identity-map the complete range supervisor-writable and non-executable while preserving its effective firmware/GOP memory type. The mapping begins before transfer, lasts only through early diagnostics, and must be replaced and revoked before graphics authority is delegated to a user-space service. If that mapping cannot be established, PooleBoot must omit the framebuffer record or PooleKernel must ignore it and retain serial/ring diagnostics.

## Product Qualification

Run:

```powershell
python tools/qualify_native_kernel_entry.py --artifact-out outputs/PooleKernel.pkelf
```

The qualifier uses the workspace-local pinned Rust toolchain, executes the exact
243-test kernel suite, checks formatting and Clippy, and performs two clean
offline builds in separate target directories. It compares linked and canonical
bytes, requires the contract build ID once in PKMID1 and once in the live
diagnostic literal, runs hostile ELF controls, scans for host leakage, and
compares loaded bytes from independent Python and Rust PKELF1 implementations.
Its public receipt is `runs/native_kernel_entry_readiness.json`; the receipt's
source bindings must be current before its image identity may be accepted.

The Cycle 167 candidate has a measured 530,072-byte canonical file and
602,112-byte, 147-page image: entry `0xA000`, text end `0x73000`, RELRO end
and writable-data start `0x81000`, image end `0x93000`. PKMAP2 reservations
move by one page with the image guard. The exact SHA-256 and relocation count
belong to the source-bound receipt, not an inherited historical image.
The product file under `outputs/` remains local generated state.

## Nonclaims

This standalone product qualification does not itself execute the image. `PKXFER1` separately proves that an opt-in feature-enabled PooleBoot build installs retained CR3/RSP, enters PooleKernel under QEMU, executes PKREVAL1, emits matching serial/debugcon evidence, and halts on the unsigned denial; default PooleBoot still stops before transfer. `PKTRAP1` and later CPU receipts cover bounded processor slices. `PKVM3` separately proves one bounded BSP-only candidate-root activation. `PKSMP5` separately proves three-AP startup, rollback/retry, fixed development IPI delivery, and one-page-per-root remote invalidation on one frozen emulator topology. None of these receipts authenticates a production PBP1 profile, finalizes framebuffer cache/remap/revocation policy, implements a scheduler, general topology or general SMP shootdown, ring 3, complete target-family or kernel-runtime policy, target firmware or physical hardware qualification, second-host reproduction, a bootable ISO, N5-N9 exit, or production readiness.
