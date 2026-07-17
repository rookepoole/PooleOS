# PSM1 Native System Manifest Boundary

Status: bounded unsigned digest-bound non-promoting proof
Contract: `PSM1`
Move: `N5-MANIFEST-001`
Receipt: `runs/native_system_manifest_readiness.json`

## Scope

PSM1 is the canonical development manifest consumed between PBC1 boot
configuration and PKELF1 loading. It binds a selected slot and minimum secure
version to ordered artifacts with exact type, format, version, root-confined
UEFI path, file bytes, image bytes, SHA-256 digest, and entry contract.

This cycle proves deterministic parsing and digest equality. The manifest is
unsigned and therefore untrusted. Digest equality against attacker-controlled
manifest bytes is integrity consistency, not authentication.

## Canonical Grammar

The manifest is strict printable ASCII plus LF, must end in LF, and admits no
blank lines, comments, whitespace, BOM, CRLF, duplicate keys, unknown keys, or
alternate field order. It starts with `POOLEOS-SYSTEM-MANIFEST/1.0` and ends
with `end=PSM1`.

The bounded profile permits at most 65,536 bytes, 384 bytes per line, 192
lines, and 16 artifacts. Artifact identifiers and paths are canonical and
ordered; paths are absolute uppercase UEFI paths confined below
`\EFI\POOLEOS`. Exactly one kernel must use `PKELF1` and `PKENTRY1` with
nonzero file and image bounds.

## Implementations

- `native/manifest` is the allocation-free `no_std` Rust parser used by
  PooleBoot.
- `runtime/native_system_manifest.py` is an independently written Python
  encoder/parser/oracle used only for host qualification.
- `native/boot/src/kload.rs` reads the manifest selected by live PBC1, binds
  slot/version/path/size/digest/entry fields, and hashes the kernel before
  allocation and again before materialization.
- PBDIGEST1 pins vendored RustCrypto `sha2` 0.11.0 with default features off,
  the `soft-compact` UEFI backend, Cargo checksums, and reproducible source-path
  remapping to `/pooleos/native`.

The provider remains a candidate pending independent cryptographic,
supply-chain, and target-backend review. Its inclusion does not promote the
manifest to a trusted state.

## Qualification

Run:

```powershell
python .\tools\generate_native_system_manifest_vectors.py --check
python .\tools\qualify_native_system_manifest.py
```

Current bounded evidence includes 8/8 Rust tests, two `no_std` target builds,
one PooleBoot UEFI integration build, 3/3 golden vectors, 64/64 named hostile
controls, 16,384 Rust/Python differential cases, three standard SHA-256
vectors, and 1,024 deterministic independent digest cases with zero mismatch.

PKLOAD2 separately proves two exact 61,440-byte PooleBoot builds, two exact
four-file media images, two fresh-vars QEMU/OVMF runs, nineteen ordered
markers, forty hostile controls, exact guest/oracle agreement, and complete
load-then-release cleanup.

## Nonclaims

- No manifest signature, trusted signer, Secure Boot authorization, db/dbx
  decision, TCG2 measurement, TPM policy, or persistent rollback enforcement.
- No completed independent security review or production promotion of the
  digest provider.
- No retained kernel pages, installed page tables, live PBP1, final memory-map
  retry, `ExitBootServices`, kernel transfer, or N5 exit.
- No second builder, target firmware, physical-media write, ISO, release, or
  production-readiness claim.
