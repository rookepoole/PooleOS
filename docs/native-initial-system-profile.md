# Native Initial-System Artifact Profile

Status: candidate, unsigned, development-only, non-promoting  
Profile move: `N5-INIT-SYSTEM-001`
Current inner-format move: `N5-INIT-BUNDLE-001`
Profile contract: `PBASET1`  
Artifact envelope: `PBART1`  
Manifest contract: `PSM1`  
Handoff contract: `PBP1`

## Scope

`PBASET1` freezes the bounded artifact set that PooleBoot must parse,
digest-bind, load, retain, and describe before the N5 transfer work can
continue. It does not authenticate a signer, establish persistent rollback
state, apply microcode, execute firmware, enter recovery, consume symbols,
enforce policy, execute the initial system, or authorize kernel transfer.

The development profile contains exactly seven artifacts. PSM1 records use
the following strict ASCII order; PBP1 records use the numeric role order.

| PSM1 ID | PSM1 type | Format | Canonical path | PBP1 role |
| --- | --- | --- | --- | ---: |
| `a_kernel` | `kernel` | `PKELF1` | `\EFI\POOLEOS\KERNEL.ELF` | 1 |
| `b_initial_system` | `initial_system` | `PBART1` + `PINIT1` | `\EFI\POOLEOS\INITIAL.PBA` | 2 |
| `c_recovery` | `recovery` | `PBART1` | `\EFI\POOLEOS\RECOVERY.PBA` | 3 |
| `d_symbols` | `symbols` | `PBART1` | `\EFI\POOLEOS\SYMBOLS.PBA` | 4 |
| `e_microcode` | `microcode` | `PBART1` | `\EFI\POOLEOS\MICROCOD.PBA` | 5 |
| `f_firmware` | `firmware` | `PBART1` | `\EFI\POOLEOS\FIRMWARE.PBA` | 6 |
| `g_policy` | `policy` | `PBART1` | `\EFI\POOLEOS\POLICY.PBA` | 7 |

The kernel keeps `entry_contract=PKENTRY1` and a nonzero `image_bytes` value.
Every PBART1 artifact uses `entry_contract=none` and `image_bytes=0`. Each
PBART1 file is limited to 1 MiB, and the six-file set is limited to 6 MiB.

## PBART1 Envelope

PBART1 is a fixed 96-byte little-endian header followed by the exact payload.
All reserved bytes and all unknown flags must be zero.

| Offset | Bytes | Field |
| ---: | ---: | --- |
| 0 | 8 | ASCII magic `PBART1` followed by two NUL bytes |
| 8 | 2 | major version, exactly 1 |
| 10 | 2 | minor version, exactly 0 |
| 12 | 2 | header byte count, exactly 96 |
| 14 | 2 | reserved, zero |
| 16 | 4 | PBP1 artifact role, 2 through 7 |
| 20 | 4 | flags, zero for this profile |
| 24 | 8 | artifact version, at least 1 |
| 32 | 8 | payload byte count |
| 40 | 8 | declared image byte count, zero |
| 48 | 32 | SHA-256 of the payload bytes |
| 80 | 16 | reserved, zero |

The parser rejects a wrong magic or version, noncanonical header size,
unknown role, nonzero flags or reserved bytes, zero or oversized payload,
integer overflow, trailing or missing bytes, nonzero image size, a role that
differs from PSM1, a version that differs from PSM1, and a payload digest
mismatch. PSM1 independently binds the size and SHA-256 of the whole PBART1
file.

## Load And Retention

PooleBoot reads each selected path through the same bounded UEFI file protocol
path used for the kernel. It validates file metadata, exact read length, PSM1
whole-file size and digest, and the PBART1 envelope before allocating retained
pages. It then allocates a distinct `EfiLoaderData` page range, copies the
whole file, zeroes page padding, frees the temporary pool, and records the
range. Any failure before `ExitBootServices` closes open handles, frees all
temporary pools, and releases every page allocated by this load transaction.

The final PBP1 loaded-artifacts record contains exactly roles 1 through 7 in
strict order. The kernel entry has `HASH_VERIFIED | EXECUTABLE`; roles 2
through 7 have only `HASH_VERIFIED`. Their physical ranges describe complete
page allocations, their virtual range and entry fields are zero, and their
SHA-256 values equal the corresponding PSM1 whole-file digests. All seven
artifact ranges, the retained page tables, guarded stack, and handoff storage
must be nonempty, page-aligned, pairwise nonoverlapping, and covered by
loader-reserved entries in the final normalized memory map.

No `SIGNATURE_VERIFIED` or `MEASURED` flag may be emitted in this profile.
The PBP1 kernel-entry profile must continue to reject the handoff.

## PINIT1 Inner Bundle

The canonical initial-system payload is no longer an arbitrary text fixture.
It is the 1,764-byte `PINIT1` declaration bundle defined by
`docs/native-initial-system-bundle.md`. An independent host oracle validates
its exact component, service, dependency, abstract-resource, attenuated-
capability, lifecycle, transaction, and rollback declarations and cross-binds
its version to PBART1. Parsing does not allocate a kernel object or authorize
activation. The unsigned development profile must fail activation before any
allocation, capability issuance, or instruction execution.

PooleBoot still validates only PBART1 and treats the inner bytes as opaque.
PooleKernel does not yet parse or activate PINIT1. Those are explicit later
gates rather than inferred consequences of the host qualification.

## Qualification Gate

The bounded move qualifies only when all of the following pass:

1. Rust `no_std` PBART1 parser tests and an independent Python parser agree on
   canonical, hostile, truncation, substitution, overflow, and digest cases.
2. PooleBoot closes the root plus all nine opened file handles, frees all nine
   temporary file pools, retains the kernel plus six PBART1 page ranges, and
   releases the full transaction on every injected pre-exit failure.
3. Independent media inspection binds all selected paths, bytes, sizes,
   versions, roles, digests, page counts, and final PBP1 records.
4. Missing, duplicate, extra, reordered, path-substituted, role-substituted,
   size-substituted, digest-substituted, overlapping, non-loader-reserved, or
   omitted PBP1 artifacts are rejected.
5. Two clean QEMU/OVMF runs from independently generated deterministic media
   produce exactly matching ordered markers and oracle-normalized receipts.
6. Claims remain explicitly false for signatures, trust, persistent rollback,
   PooleBoot inner-semantic enforcement, PooleKernel activation, component
   execution, microcode application, kernel transfer, physical hardware, N5
   completion, and production readiness.
