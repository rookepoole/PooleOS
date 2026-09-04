# PooleOS Public Signing Trust

This directory contains public verification material only. Private keys, hardware-key recovery material, passphrases, TPM objects, and production certificates are prohibited.

`owner-adr-signers.allowed` contains Rooke Poole's owner-confirmed ED25519-SK governance public key. Its OpenSSH entry authorizes principal `rookepoole` for both the `git` namespace and the PooleOS ADR namespace frozen in `specs/adr-ratification-policy.json`.

`governance-key-registration.json` records the explicit fingerprint confirmation and exact GitHub SSH signing-key registration readback, ID `1158225`, on 2026-09-04. Enrollment signature verification and separate recovery custody remain pending. Registration is not an architecture signature, completed custody ceremony, or production-release approval.

`revoked-adr-signers` is the public revocation input. A compromised or retired governance key is added there before a replacement becomes trusted. Governance signing is separate from future Secure Boot, package, update, recovery, and ISO release keys.
