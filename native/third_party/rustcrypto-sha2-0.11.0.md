# RustCrypto SHA-2 0.11.0 Intake

PooleBoot uses the RustCrypto `sha2` crate only for SHA-256 artifact-byte
binding in the candidate PSM1 development path.

- Upstream: `https://github.com/RustCrypto/hashes`
- Registry version: `sha2` 0.11.0
- Registry crate SHA-256: `446BA717509524CB3F22F17ECC096F10F4822D76AB5C0B9822C5F9C284E825F4`
- License: `MIT OR Apache-2.0`
- Cargo default features: disabled
- UEFI backend: forced portable `soft` with compact rounds
- Source closure: all nine locked registry packages are under `native/vendor`
  with Cargo `.cargo-checksum.json` verification and exact checksums recorded in
  `specs/native-boot-digest-provider.json`

The dependency is frozen for deterministic offline qualification. No upstream
source is modified. This intake is not a cryptographic audit, signature system,
trust anchor, rollback mechanism, measured-boot implementation, or production
approval. N6 and N15 retain those gates.
