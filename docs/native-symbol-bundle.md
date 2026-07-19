# PooleOS Native Public Symbol Bundle (PSYM1)

Status: candidate pre-ABI, single-host qualified, unsigned, non-promoting.

PSYM1 is the bounded public diagnostic index for one exact PooleKernel image. It is not an executable table, dynamic linker interface, syscall ABI, kernel export namespace, capability grant, or substitute for a private split-debug file. The current development bundle cannot be consumed because all production signature preconditions are false.

## Scope

The N5.6 symbol slice establishes four narrow properties:

1. One deterministic binary representation binds a stripped PKELF1 file, its preferred loaded image, kernel build ID, full split-debug ELF, and source manifest.
2. Python and allocation-free `no_std` Rust implementations parse the same bytes and return the same error taxonomy.
3. Lookup uses image-relative virtual offsets and a bounded binary search; KASLR runtime base is an explicit input.
4. The media profile contains only explicitly public diagnostic names and defaults to runtime-pointer redaction.

It does not enable PooleBoot or PooleKernel consumption. That remains blocked on signatures, target integration, capability-authorized diagnostics, final mappings, and target qualification.

## Research Basis

The format follows the ELF global symbol model (`st_name`, `st_value`, `st_size`, binding, type, and visibility) while replacing section-dependent addresses with a compact image-relative model. ELF string-table rules inform the dense string region. DWARF 5 and GDB separate-debug guidance inform the split-debug binding. Rust v0 names are treated as opaque linker bytes because Rust does not promise them as a stable ABI.

- ELF symbol tables: <https://gabi.xinuos.com/elf/05-symtab.html>
- ELF string tables: <https://gabi.xinuos.com/elf/04-strtab.html>
- DWARF 5: <https://dwarfstd.org/doc/DWARF5.pdf>
- GDB separate debug files: <https://sourceware.org/gdb/current/onlinedocs/gdb.html/Separate-Debug-Files.html>
- Rust v0 mangling: <https://doc.rust-lang.org/beta/rustc/symbol-mangling/v0.html>

## Binary Layout

All integers are little-endian. The parser accepts at most 512 KiB, 16 segments, 4,096 symbols, 127 bytes per name, and 256 KiB of strings.

| Region | Record size | Purpose |
| --- | ---: | --- |
| Header | 384 bytes | Version, flags, geometry, bounds, policies, five identities, body digest |
| Segment table | 32 bytes | Dense image coverage and exact RO/RX/RELRO/RW permissions |
| Symbol table | 48 bytes | Public symbol identity, segment, flags, name slice, offset, and size |
| String region | variable | Dense non-NUL ASCII linker names |

The body SHA-256 covers all bytes after the header. Reserved bytes must be zero. Tables are contiguous, segment IDs and symbol IDs are dense, segments cover the complete image without gaps, and symbols are sorted and nonoverlapping.

## Address Model

Every segment and symbol address is an offset from the loaded image base. The bundle declares:

- Preferred base: `0xFFFFFFFF80000000`
- Window end, exclusive: `0xFFFFFFFFC0000000`
- Slide alignment: 2 MiB
- Current image bytes: `0x40000`
- Current entry offset: `0x8000`

Lookup rejects noncanonical x86-64 addresses, unaligned bases, bases outside the window, and addresses outside the image. A hit returns symbol ID, name, intra-symbol offset, and search-step count. A valid gap returns `unknown`; it never falls back to the preceding symbol.

## Identity Chain

The canonical development bundle binds these exact SHA-256 identities:

| Identity | SHA-256 |
| --- | --- |
| Canonical stripped PKELF1 | `5CBB39B4BFF9A23E8D65E3115FE536D4CDB13EAA372E8DAA5071F1530210132E` |
| Preferred loaded image | `2E031002E303B22C9836F73636A6B6DF4061462293B62DA383A62060A386AA96` |
| Build ID text | `4F29BB22D36F289A892E84DAB4C5C0C90093A61D91844E47CAE35F0A23EFCE48` |
| Full split-debug ELF | `BBCCFB73249138C431F1262D0533297CC8B66614D560E2A1D531DD7EB15E2F1F` |
| `native/kernel/manifest.pkm` | `AA05393FA6A1C33FFAD7AC143FF1E6F16391159E8B10222ECA9E0B1660ED34ED` |

The qualification builds the full debug product twice and requires identical bytes. Both debug builds canonicalize to the exact stripped PKELF1 bytes. A separate release build must have no `.symtab` and no `.debug*` sections and must canonicalize to those same bytes.

## DWARF Provenance

The current linked debug ELF has mixed, explicit provenance. The three leading PooleOS compilation units are rebuilt as DWARF 5. Rust's pinned prebuilt sysroot contributes DWARF 4 units. PSYM1 verifies this observed split and does not claim that the sysroot was rebuilt. Required DWARF 5-era sections include `.debug_info`, `.debug_names`, `.debug_loclists`, and `.debug_rnglists` alongside the symbol and string tables.

Only these real global default-visible functions are selected today:

| Symbol | Offset | Bytes | Policy |
| --- | ---: | ---: | --- |
| `poole_kernel_entry` | `0x8000` | 56 | entry, executable, public diagnostic |
| `poole_kernel_emergency_panic` | `0x822A` | 190 | panic-safe, executable, public diagnostic |
| `poole_kernel_rust_entry` | `0x82E8` | 1,085 | executable, public diagnostic |

## Name And Privacy Policy

On-media names are opaque ASCII and allow only letters, digits, `_`, `.`, `$`, `@`, and `-`; a name may not begin with punctuation. Source paths, host paths, local symbols, private symbols, source lines, types, locals, and private demangling metadata are excluded. The full split-debug ELF is a private build artifact and must not be placed on boot media.

Runtime diagnostics default to pointer redaction. Looking up or formatting a symbol does not authorize disclosure. A future diagnostic capability must separately authorize the session and its disclosure policy.

## Consumption Gate

Target consumption requires every condition below. The first failure is returned deterministically.

1. Outer PBART1, inner PSYM1, manifest, and bound PooleKernel signatures verify.
2. Outer role 4, version, payload digest, and file digest match.
3. All five identities match qualified evidence.
4. Debug correspondence, owned DWARF 5 units, public-only policy, and source-path absence verify.
5. Pointer redaction and diagnostic authorization are active.
6. Runtime base and all parser/lookup capacities satisfy declared bounds.
7. No authority effect is requested.

The synthetic all-true context exists only to test that every gate can be reached. It is not trust evidence. The actual unsigned development context fails at `psym_activation_outer_signature`.

## Qualification

`tools/qualify_native_symbols.py` runs:

- Four Rust host tests, rustfmt, Clippy, and two `no_std` target builds.
- Three generated golden bundles and their lookup samples.
- At least 158 parser, activation, and debug-ELF negative controls.
- 16,384 deterministic parser differential cases with digest-repaired deep mutations.
- 16,384 deterministic lookup differential cases spanning hits, gaps, slides, and invalid requests.
- Two clean reproducible full-debug kernel builds and one separately stripped build.
- Exact public-symbol extraction and debug-to-PSYM1 regeneration.

Passing this qualification closes `N5-SYMBOLS-SEMANTICS-001` only. N5 remains partial, PSYM1 remains pre-ABI and unsigned, and `production_ready` remains false.

Cycle 114 PooleBoot reparses the exact retained PSYM1 bytes and requires this
development gate to fail at `psym_activation_outer_signature`. Cycle 117
independently repeats the exact parse and denial in host-executed PooleKernel
code. Neither path performs a lookup, discloses an address, or creates
diagnostic authority; live PooleKernel execution and consumption remain open.
