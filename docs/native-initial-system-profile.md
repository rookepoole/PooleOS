# Native Initial-System Artifact Profile

Status: candidate, unsigned, development-only, non-promoting  
Profile move: `N5-INIT-SYSTEM-001`
Current transfer move: `N5-KERNEL-TRANSFER-001`
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

The PSM1 development profile contains exactly seven manifest artifacts. PSM1
records use the following strict ASCII order; final PBP1 additionally retains
PSM1, PBTP1, and PBTS1 as roles 9 through 11 after these seven roles. Role 8 is
reserved for a crash kernel and remains absent.

| PSM1 ID | PSM1 type | Format | Canonical path | PBP1 role |
| --- | --- | --- | --- | ---: |
| `a_kernel` | `kernel` | `PKELF1` | `\EFI\POOLEOS\KERNEL.ELF` | 1 |
| `b_initial_system` | `initial_system` | `PBART1` + `PINIT1` | `\EFI\POOLEOS\INITIAL.PBA` | 2 |
| `c_recovery` | `recovery` | `PBART1` + `PREC1` | `\EFI\POOLEOS\RECOVERY.PBA` | 3 |
| `d_symbols` | `symbols` | `PBART1` + `PSYM1` | `\EFI\POOLEOS\SYMBOLS.PBA` | 4 |
| `e_microcode` | `microcode` | `PBART1` + `PMCU1` | `\EFI\POOLEOS\MICROCOD.PBA` | 5 |
| `f_firmware` | `firmware` | `PBART1` + `PFWM1` | `\EFI\POOLEOS\FIRMWARE.PBA` | 6 |
| `g_policy` | `policy` | `PBART1` + `PPOL1` | `\EFI\POOLEOS\POLICY.PBA` | 7 |

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

The final PBP1 loaded-artifacts record contains roles 1 through 7 followed by
roles 9 through 11 in strict order. The kernel entry has `HASH_VERIFIED |
EXECUTABLE`; every non-kernel entry has only `HASH_VERIFIED`. Non-kernel
`physical_size` is the exact file-byte count, not allocation padding. Their
virtual range and entry fields are zero, and their SHA-256 values equal the
corresponding exact file digests. All ten artifact allocations, retained page
tables, guarded stack, and handoff storage must be nonempty, page-aligned,
pairwise nonoverlapping after page rounding, and covered by loader-reserved
entries in the final normalized memory map.

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

PooleBoot reparses PINIT1 from the exact retained PBART1 pages and requires the
development activation gate to fail at the missing outer signature. Cycle 117
independently repeats the parse, route binding, and denial in host-executed
PooleKernel code. Live kernel execution, authentication, capability creation,
and lifecycle execution remain explicit later gates.

## PREC1 Inner Bundle

The canonical recovery payload is the 992-byte immutable `PREC1` policy in
`docs/native-recovery-bundle.md`. A separate 128-byte mutable state record
tracks authenticated generation, active and pending slots, known-good and
unbootable masks, remaining attempts, safe-mode attempts, and the exact
in-flight nonce. The state checksum detects accidental corruption only; it is
not authentication.

Independent Python and allocation-free `no_std` Rust implementations validate
the policy, state, boot selection, decrement-before-handoff transition,
known-good fallback, bounded safe/recovery routing, authenticated success
receipt, physical-presence requirements, and activation prerequisites. The
unsigned development context is denied before recovery authority or execution.

PooleBoot reparses PREC1 from the exact retained PBART1 pages and requires the
development recovery gate to fail at the missing outer signature, but it does
not read or write PREC1 state. Cycle 117 independently repeats the policy parse
and denial in host-executed PooleKernel code but does not execute recovery. No
UEFI variable, disk, firmware, network, or device-changing operation follows
from this qualification.

## PSYM1 Inner Bundle

The canonical symbol payload is the public-only `PSYM1` diagnostic index in
`docs/native-symbol-bundle.md`. It binds one exact stripped PKELF1 file,
preferred loaded image, build ID, private split-debug product, and source
manifest. All addresses are image-relative offsets; lookup requires an
explicit aligned KASLR runtime base and remains bounded to thirteen steps.

Independent Python and allocation-free `no_std` Rust implementations validate
the format, exact segment geometry, three public functions, name policy,
source-path exclusion, pointer-redaction policy, split-debug correspondence,
and lookup behavior. The full debug ELF is not staged on boot media. The
unsigned development context is denied before target consumption or address
disclosure.

PooleBoot reparses PSYM1 from the exact retained PBART1 pages and requires the
development consumption gate to fail at the missing outer signature. PooleBoot
and PooleKernel do not consume symbols, create a kernel export namespace, grant
a diagnostic capability, or disclose runtime pointers. Those are explicit
later gates rather than inferred consequences of parsing.

## PMCU1 Inner Bundle

The microcode payload is the synthetic never-apply `PMCU1` package described
in `docs/native-microcode-bundle.md`. Independent Python and allocation-free
Rust validators model exact CPU selection, security revision floors,
known-good fallback, reset handling, and receipts. No vendor production
container is included, no privileged CPU revision is observed, and no update
instruction executes.

## PFWM1 Inner Bundle

The firmware payload is the synthetic manifest-only `PFWM1` bundle described
in `docs/native-firmware-manifest.md`. It binds exact component, hardware,
version, dependency, signer, updater, recovery, and external-payload
identities. Only a qualification dry-run and post-reset receipt model exist;
no payload bytes, live inventory, updater driver, capsule call, reset, or
firmware mutation occurs.

## PPOL1 Inner Bundle

The policy payload is the qualification-only `PPOL1` bundle described in
`docs/native-policy-bundle.md`. Its six exact mode records provide compiled-in
safe and recovery floors plus a firmware mode requiring physical presence and
separate authority. Its 11 capability rules exactly cross-bind canonical
PINIT1 routes and can only attenuate declared and already-issued rights.

Independent Python and allocation-free `no_std` Rust validators agree on the
format, route cross-binding, activation boundaries, dry-run decisions, and
durable receipts. The unsigned development context fails first at the missing
outer signature. PooleBoot also reparses those retained policy bytes and checks
the five payload digests and eleven PINIT1 routes. Neither target applies a
decision or creates authority, and PooleGlyph remains non-authoritative pending
its separate Core IR promotion gate.

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
   artifact authentication and authorized semantics, PooleKernel retained-byte
   revalidation or activation, recovery
   execution or symbol consumption, persistent-state I/O, component execution,
   microcode or firmware application, PPOL1 enforcement, PooleGlyph executable
   authority, kernel transfer, physical hardware, N5 completion, and production
   readiness.
