# PBC1 native boot configuration candidate

## Status and scope

PBC1 is the Cycle 99 candidate boot-configuration boundary for
`N5-BOOTCFG-001` and locked-checklist section 015.3. It defines one canonical,
bounded representation that can be parsed without allocation by PooleBoot and
independently by host qualification code. It also defines the entry data needed
to prepare later normal, safe, previous, recovery, and diagnostic selection
work from section 015.7.

The authoritative machine-readable contract is
`specs/native-boot-config-contract.json`. PooleBoot has a compile-time path
dependency on `native/bootcfg` and re-exports it as `pooleboot::boot_config`.
The standalone Cycle 99 receipt proves only parser and compile-time integration.
Cycle 102 PKLOAD1 separately proves that the current UEFI executable opens and
parses the exact live `\EFI\POOLEOS\BOOT.CFG` bytes; that later proof does not
make this parser receipt a trusted-selection or manifest-consumption result.

## Firmware-path basis

UEFI 2.11 Simple File System opens a volume root and performs subsequent file
operations through `EFI_FILE_PROTOCOL`. Its `Open()` contract treats a leading
backslash as the volume root and permits `.` and `..` path modifiers. PBC1
therefore accepts only absolute backslash paths rooted below
`\EFI\POOLEOS\`, rejects both dot components, and uses an uppercase restricted
alphabet so configuration bytes have one portable spelling before future FAT
lookup behavior is implemented.

References:

- [UEFI 2.11, Simple File System and OpenVolume](https://uefi.org/specs/UEFI/2.11/13_Protocols_Media_Access.html#efi-simple-file-system-protocol-openvolume)
- [UEFI 2.11, EFI_FILE_PROTOCOL.Open](https://uefi.org/specs/UEFI/2.11/13_Protocols_Media_Access.html#efi-file-protocol-open)
- [UEFI 2.11, Boot Manager](https://uefi.org/specs/UEFI/2.11/03_Boot_Manager.html)

The root restriction is PooleOS policy, not a claim that UEFI itself rejects
other roots or dot components.

## Canonical grammar

The file is printable ASCII without spaces, comments, blank lines, BOM, CR, or
NUL. Every line ends in LF and the file ends in LF. Keys, entries, and fields
appear in exactly this order:

```text
POOLEOS-BOOTCFG/1.0
entry_count=<1..8>
default_entry=<id>
timeout_ms=<0..30000>
boot_attempt_limit=<1..8>
entry.<id>.mode=<normal|safe|previous|recovery|diagnostic>
entry.<id>.slot=<1..4>
entry.<id>.manifest=<root-confined .PBM path>
entry.<id>.manifest_max_bytes=<1..1048576>
end=PBC1
```

The four entry lines repeat once per declared entry. Entry identifiers are
strictly increasing ASCII and match `[a-z][a-z0-9_]{0,30}`. Decimal values are
canonical unsigned values with no sign and no leading zero except `0`. Full
keys must be unique; unknown keys and incompatible versions fail closed.

## Bounds

| Surface | Bound |
| --- | ---: |
| Configuration | 16,384 bytes |
| Line | 320 bytes |
| Lines | 64 |
| Entries | 8 |
| Identifier | 31 bytes |
| Manifest path | 240 bytes |
| Path component | 64 bytes |
| Manifest artifact | 1,048,576 bytes |
| Timeout | 30,000 ms |
| Boot attempts | 8 |
| Slot | 4 |

The Rust API borrows strings from the input and requires caller-owned storage:

```rust
parse(bytes, &mut entry_storage)
validate_manifest_size(configured_limit, observed_size)
```

No heap, filesystem, firmware service, global mutable state, or unsafe block is
used by the parser.

## Qualification

`tools/qualify_native_boot_config.py` builds and runs 12 Rust host tests, builds
the parser and the PooleBoot library for `x86_64-unknown-uefi` and
`x86_64-unknown-none`, compares three full semantic golden summaries, executes
64 named hostile controls, and compares 16,384 deterministic cases between the
Rust parser and the independently implemented Python oracle. The host probe is
test transport only and is not part of firmware or a release artifact.

The hostile register covers encoding, line and file bounds, duplicate and
unknown keys, order, truncation, incompatible versions, canonical numbers,
overflow, range failures, entry identifiers, all path-escape forms, output
capacity, declared-count mismatch, and configured/observed artifact sizes.

## Non-claims and next dependency

This standalone PBC1 evidence does not itself prove live filesystem discovery,
trusted entry selection, boot-menu behavior, manifest consumption, hashing,
signature verification, rollback, PBP1 population, ExitBootServices,
PooleKernel execution, target firmware, physical media, or production
readiness. PKLOAD1 separately proves one fixed-untrusted live read and parse.
PBC1 remains a pre-ABI candidate until separately ratified.

The current owner-independent N5 dependency is `N5-MANIFEST-001`: a canonical
bounded manifest, independent parser, digest/version/size/slot binding, and
manifest-driven development selection with no signature or trust claim. Live
configuration loading should follow only when filesystem discovery and signed
manifest policy can be integrated without weakening these boundaries.
