# PooleOS N0 Owner Response Receipt

- Status date: 2026-07-16
- Completed move: `N0-OWNER-RESPONSE-001`
- Status: `owner_direction_recorded_hardware_key_unavailable`
- Cryptographic owner signature: `false`
- Production promotion: `false`

## Frozen Input

The original unselected packet remains frozen at SHA-256 `BFE74292B2B695E49D48028B5AE9843571FC23878C355CCA9119D90729041AE0` and repository commit `a106e6ffcee06c4a13c67f2b949fbc1ab8f24bc9`.
It binds source-set SHA-256 `8F5E4C663D2D6F1BB0D6ECFC7CD85267206A3580B39C96090908DB88A0281E1F` and target-set SHA-256 `9C25304CDB72FD037468481BA6437F0D783A2AA496A6144DC5DE659D9CDF2BCF`.

## Recorded Direction

- `ADR-0003`: accept exactly as written; live source status is `accepted-owner-directed`.
- `ADR-0004`: accept exactly as written; live source status is `accepted-owner-directed`.
- Workstation v1: accept `38` target definitions; measured targets remain `0`.
- Governance key: `hardware_fido2_ed25519_sk` selected; FIDO2 hardware key available: `false`.
- Provisional software-key risk: `not_applicable`.
- Public-key publication: `not_yet`.

## Closed Authority Boundary

No key generation, private-key use, signing, merge to main, tagging, or publication is authorized. No public or private key material is present.

## Current Gate

- Trusted governance signers: `0`.
- Detached signature, signed tag, and remote publication receipt: all absent.
- Next move: `N0-HW-KEY-ACQUIRE-001`; blocked because the selected hardware key is unavailable.
- After compatible hardware is obtained, key generation still requires a separate explicit approval.

## Owner Actions

| ID | Status | Detail |
|---|---|---|
| `OWNER-ADR-DISPOSITION-001` | `satisfied_owner_direction_recorded` | ADR-0003 and ADR-0004 exact-acceptance direction is recorded in source status without a signature claim. |
| `OWNER-OBJECTIVES-DISPOSITION-001` | `satisfied_definitions_only` | The Workstation v1 profile and all 38 target definitions are accepted; every target remains unmeasured. |
| `OWNER-SIGNING-CUSTODY-001` | `blocked_hardware_key_unavailable` | hardware_fido2_ed25519_sk is selected, but the owner reports no FIDO2 hardware key is currently available. |
| `OWNER-PUBLIC-KEY-PUBLICATION-001` | `deferred_by_owner` | Public-key publication remains not_yet and no public key or fingerprint is recorded. |
| `OWNER-KEY-GENERATION-001` | `not_authorized` | Key generation or private-key use requires a separate explicit approval after compatible hardware is available. |
| `OWNER-DETACHED-SIGN-001` | `not_authorized` | No manifest signing is authorized or performed by this response. |
| `OWNER-SIGNED-TAG-001` | `not_authorized` | No signed architecture tag is authorized or present. |
| `OWNER-PUBLISH-RECEIPT-001` | `not_authorized` | Merge, public-key registration, tag publication, and release publication remain separately gated. |

## Validation

All `16/16` fail-closed response controls pass.

## Claim Boundary

- This receipt validates an unsigned conversational owner-direction record; it is not an owner cryptographic signature.
- The historical decision packet remains byte-frozen with every original selection unselected so the reviewed input is not rewritten.
- Owner-directed source status does not satisfy the required detached-signature, signed-tag, or remote-publication gates.
- All 38 target definitions are accepted, but all 38 measurements remain open and zero targets are proven met.
- No public key, private key, key handle, passphrase, credential, recovery secret, signature, or publication receipt is present.
- The selected hardware-backed profile cannot be executed because the owner reports no FIDO2 hardware key is available.
- Key generation, private-key use, signing, merge to main, tagging, and publication each remain explicitly unauthorized.
- This receipt does not prove PooleBoot, PooleKernel, native services, PooleGlass, PooleGlyph, PDC backends, hardware support, or a production ISO.
