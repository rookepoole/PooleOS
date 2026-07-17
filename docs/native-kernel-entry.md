# Native PooleKernel Entry

`PKENTRY1` is the candidate x86-64 contract for transferring from future PooleBoot code into the first real freestanding PooleKernel product image. The product is a canonical `PKELF1` file built from the `poolekernel` Rust package. The old empty kernel fixture remains under `native/fixtures/poolekernel` and cannot satisfy this boundary.

## Transfer Boundary

PooleBoot must complete authenticated selection, load and relocate the kernel, install final page tables, obtain the final memory map, successfully call `ExitBootServices`, and establish the `PBP1` mappings before a direct jump. `RDI` is the immutable PBP1 virtual address, `RSI` its exact length, `RDX` its magic value, and `RSP` the nonzero canonical 16-byte-aligned initial stack top. The wrapper clears interrupts and the direction flag again, checks the stack without using it, and only then crosses the System V AMD64 ABI into Rust.

The current product validates the handoff envelope, decodes PBP1 without allocation, enforces the kernel-entry profile, and checks exact entry and stack continuity. It records bounded diagnostics in a 4096-byte static ring, attempts a fixed bounded COM1 candidate, and can render a small volatile framebuffer message when its optional mapping precondition holds. Stable panic classes distinguish Rust panic, handoff envelope, decode, profile, continuity, and unexpected-return failures. A nested panic takes a separately marked terminal path.

## Framebuffer Mapping Gap

PBP1 carries a framebuffer physical aperture, not proof of a usable virtual mapping. `ADD-KERNEL-001` therefore requires PooleBoot to identity-map the complete range supervisor-writable and non-executable while preserving its effective firmware/GOP memory type. The mapping begins before transfer, lasts only through early diagnostics, and must be replaced and revoked before graphics authority is delegated to a user-space service. If that mapping cannot be established, PooleBoot must omit the framebuffer record or PooleKernel must ignore it and retain serial/ring diagnostics.

## Product Qualification

Run:

```powershell
python tools/qualify_native_kernel_entry.py --artifact-out outputs/PooleKernel.pkelf
```

The qualifier uses the workspace-local pinned Rust toolchain, executes thirteen host tests, checks formatting and Clippy, performs two clean offline builds in separate target directories, compares linked and canonical bytes, runs hostile linked-ELF and canonical-PKELF controls, scans for host leakage, and compares exact loaded bytes from the independent Python and Rust PKELF1 implementations. Its deterministic public receipt is `runs/native_kernel_entry_readiness.json`; the current canonical product SHA-256 is `BF1176019E9E4AF1C588898F565A6B1F66737517C2D3CA804510C4B0AC1B2E9D`, and the product file under `outputs/` remains local generated state.

## Nonclaims

PKLOAD4 now loads this image, binds it into a temporary pre-exit PBP1 snapshot, temporarily activates and audits exact higher-half W^X mappings, restores the original CR3, and releases the snapshot, table, and kernel pages without executing the entry point. The qualification does not execute `ExitBootServices`, retain page tables or establish the final address space, perform privileged COM1 or framebuffer I/O from PooleKernel, initialize GDT/IDT/TSS, start the kernel runtime, test target firmware, reproduce on a second host, produce a bootable ISO, close N6, or establish production readiness. It performs no signing, merging, release publication, firmware modification, driver loading, privileged probing, or physical-media write.
