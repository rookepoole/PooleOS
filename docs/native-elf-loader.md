# PKELF1 PooleKernel ELF64 Loader Boundary

Status: Cycle 100 qualified candidate, pre-production and non-promoting
Requirement: `N5-ELF-001`, source section `015`, subphase `N5.5`

## Purpose

PKELF1 is the deliberately narrow ELF64 profile accepted by the future PooleBoot kernel-image path. It is not a general ELF loader or dynamic linker. `native/elf` validates exact bytes without allocation, writes only to caller-owned storage after complete validation, copies three load segments, zeroes BSS, applies bounded relative relocations, and returns the page-permission plan that a later PooleBoot paging path must install.

The host-only `runtime/native_elf_loader.py` is independently written and prohibited from the production boot chain. It generates synthetic images and compares semantic decisions and exact loaded bytes with the Rust implementation.

## Standards Basis

The [ELF header](https://gabi.xinuos.com/elf/02-eheader.html) identifies class, byte order, machine, file type, entry address, and program-header geometry. The [gABI program-loading chapter](https://gabi.xinuos.com/elf/08-pheader.html) makes program headers authoritative for the process image, requires ascending `PT_LOAD` virtual addresses, copies file bytes to the beginning of each memory segment, zeroes the remainder, forbids `p_filesz > p_memsz`, and defines alignment congruence. The [dynamic-array chapter](https://gabi.xinuos.com/elf/09-dynamic.html) defines `DT_RELA`, `DT_RELASZ`, `DT_RELAENT`, and terminal `DT_NULL` entries.

The official [x86-64 psABI source](https://gitlab.com/x86-psABIs/x86-64-ABI/-/raw/master/x86-64-ABI/object-files.tex) requires ELF64 little-endian `EM_X86_64` objects for LP64, uses `Elf64_Rela` explicit addends, and defines `R_X86_64_RELATIVE` as load base plus addend.

UEFI integration is intentionally later. UEFI 2.11 defines `AllocatePages` as contiguous 4 KiB page allocation and identifies `EfiLoaderData` as the normal OS-loader allocation type. See [UEFI Boot Services](https://uefi.org/specs/UEFI/2.11/07_Services_Boot_Services.html). No firmware allocation occurs in this boundary.

## Accepted Profile

The file is an `ET_DYN`, ELF64, little-endian, System V ABI, x86-64 image with exactly seven program headers and no section-header table. Program headers occur in this order: `PT_PHDR`, three `PT_LOAD` entries, `PT_DYNAMIC`, `PT_GNU_RELRO`, and non-executable `PT_GNU_STACK`.

The three load segments are page-aligned, contiguous, image-relative, and exactly `r`, `rx`, and `rw`. `p_offset` equals `p_vaddr`; `p_paddr` is zero. The first two loads are page-complete. The final load ends at exact EOF and may extend into zero-filled BSS. The complete file is at most 1 MiB and the memory image is at most 64 MiB.

The dynamic segment contains exactly `DT_RELA`, `DT_RELASZ`, `DT_RELAENT`, and `DT_NULL`. There are 1-4,096 sorted, unique, eight-byte-aligned `R_X86_64_RELATIVE` entries. Every symbol index is zero. Every addend points inside a loaded segment. Every target starts as zero, lies in file-backed RELRO, and cannot overlap the dynamic or relocation tables. Imports, PLT/GOT resolution, interpreters, TLS, text relocations, unknown segment types, and executable stacks fail closed.

The virtual base is 2 MiB aligned in the bounded high-half window `0xffffffff80000000..0xffffffffc0000000`. The physical base is 4 KiB aligned, at least 1 MiB, and bounded below the conservative 52-bit physical ceiling. A later exact hardware profile may narrow that ceiling.

## Loading Transaction

1. Validate the entire file, every relocation, both base addresses, and caller capacity.
2. Leave caller storage byte-for-byte unchanged on any failure.
3. Zero the complete declared image range.
4. Copy each file-backed load range into its image-relative destination.
5. Apply each relocation as `virtual_base + addend`.
6. Return four page ranges: read-only headers/rodata, read-execute text, post-relocation read-only RELRO, and read-write data/BSS.

The returned plan is normative input to later page-table construction. This cycle does not install page tables or prove processor-enforced W^X.

## Qualification

Run:

```powershell
python tools/generate_native_elf_loader_vectors.py --check
python tools/qualify_native_elf_loader.py
```

The three golden images cover a minimal two-relocation image, a different physical/virtual base with 32 relocations, and the exact 4,096-relocation upper bound. Qualification also builds the no-`std` crate for UEFI and freestanding targets, checks PooleBoot's compile-time dependency, executes named hostile controls, compares deterministic mutations, and verifies exact loaded bytes for every golden image.

## Nonclaims

All current images are synthetic containers, not a functional PooleKernel. PooleBoot does not open a live file, authenticate a signed manifest, allocate firmware pages, install mappings, hash an exact loaded artifact into PBP1, exit boot services, jump to kernel entry, or execute PooleKernel. There is no second-host, target-firmware, physical-media, Secure Boot, signing, ABI-ratification, or production-readiness result. Finite vectors and differential tests are not proof over all ELF files or machine states.
