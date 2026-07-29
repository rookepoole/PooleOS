# Poole System Manifest

`poole-manifest` is the allocation-free `no_std` PSM1 parser and exact
SHA-256 artifact-binding layer used by PooleBoot. It accepts only canonical
ASCII/LF manifests, returns caller-owned artifact records, and rejects version,
slot, path, size, format, entry-contract, and digest drift.

The SHA-256 implementation is pinned RustCrypto `sha2` 0.11.0 in portable
software mode and is vendored for offline builds. PSM1 remains an unsigned,
candidate pre-ABI development contract: digest agreement does not establish a
trusted signer, rollback authority, Secure Boot state, or production readiness.
