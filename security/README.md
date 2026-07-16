# PooleOS Public Signing Trust

This directory contains public verification material only. Private keys, hardware-key recovery material, passphrases, TPM objects, and production certificates are prohibited.

`owner-adr-signers.allowed` is intentionally empty until Rooke Poole chooses the N0 governance signing-key custody profile and verifies the public-key fingerprint. Its eventual OpenSSH allowed-signers entry must authorize principal `rookepoole` for both the `git` namespace and the PooleOS ADR namespace frozen in `specs/adr-ratification-policy.json`.

`revoked-adr-signers` is the public revocation input. A compromised or retired governance key is added there before a replacement becomes trusted. Governance signing is separate from future Secure Boot, package, update, recovery, and ISO release keys.
