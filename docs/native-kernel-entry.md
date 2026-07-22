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

The qualifier uses the workspace-local pinned Rust toolchain, executes 70 host tests, checks formatting and Clippy, performs two clean offline builds in separate target directories, compares linked and canonical bytes, runs hostile linked-ELF and canonical-PKELF controls, scans for host leakage, and compares exact loaded bytes from the independent Python and Rust PKELF1 implementations. Its deterministic public receipt is `runs/native_kernel_entry_readiness.json`; the current product has a 4,207,912-byte private linked input, a 229,376-byte canonical file, a 270,336-byte loaded image, entry offset `0x8000`, 542 relative relocations, and canonical SHA-256 `06D36FAF5531509097CD03819390AC744DCFD2BD9FB64D1E6F6710DD7796776E`. The product file under `outputs/` remains local generated state.

## Nonclaims

This standalone product qualification does not itself execute the image. `PKXFER1` separately proves that an opt-in feature-enabled PooleBoot build installs retained CR3/RSP, enters PooleKernel under QEMU, executes PKREVAL1, emits matching serial/debugcon evidence, and halts on the unsigned denial; default PooleBoot still stops before transfer. `PKTRAP1` and later CPU receipts cover bounded processor slices. `PKVM2` separately proves one bounded BSP-only candidate-root activation, exact CR3 restoration, a nine-page direct map, and three local invalidation receipts. None of these receipts authenticates a production PBP1 profile, finalizes framebuffer cache/remap/revocation policy, implements SMP shootdown or ring 3, completes target-family or kernel-runtime policy, tests target firmware or physical hardware, reproduces on a second host, produces a bootable ISO, closes N5-N9, or establishes production readiness.
