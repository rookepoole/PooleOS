# PooleOS ADR Ratification and Governance-Key Ceremony

Status: owner direction recorded; selected hardware key unavailable; signatures, tag, merge, and publication unauthorized
Date: 2026-07-16
Move: `N0-RATIFY-001`
Decision and signing authority: Rooke Poole

## Purpose and Boundary

This ceremony converts the exact bytes of ADR-0001 through ADR-0007 and six required architecture sources into an owner-ratified architecture set. The six-source set explicitly includes `specs/native-v1-objectives.json` and its schema. A separate manifest statement accepts the candidate Workstation v1 profile and all 38 target values as definitions while explicitly accepting no measurement evidence. The ceremony uses an OpenSSH `SSHSIG` detached signature with a PooleOS-specific namespace, followed by an owner-signed annotated Git tag over the revision that contains the manifest and signature.

The ceremony does not generate or approve a Secure Boot key, release-media key, package/update key, recovery key, PooleBoot binary, PooleKernel image, or ISO. GitHub verification supplements the owner trust root; it does not replace the detached signature or owner-signed tag.

## Current Evidence

- ADR-0001 through ADR-0007 are `accepted-owner-directed` but cryptographically unsigned.
- `POOLEOS-WORKSTATION-V1-CANDIDATE` carries owner-directed acceptance for all 38 target definitions; zero targets have measured implementation evidence.
- `specs/n0-owner-response.json` and `runs/n0_owner_response_receipt.json` bind the completed response to the exact historical packet and pass 16/16 fail-closed controls.
- `hardware_fido2_ed25519_sk` is selected, but Rooke Poole reports no FIDO2 hardware key is currently available. Software-key risk is therefore `not_applicable`.
- Public-key publication remains `not_yet`. Key generation, private-key use, signing, merge, tagging, and publication remain separately gated and unauthorized.
- The public allowed-signers file has zero keys. No local Git signing key, GPG backend, or GitHub SSH signing key was configured when this package was generated.
- PRs #1 through #5 are merged into public `main`. Required signed-commit enforcement must not be enabled until the remaining pre-signing history and merge strategy are resolved under `N1-SCM-CLOSE-001`.
- `docs/n0-owner-decision-packet.md` and `runs/n0_owner_decision_packet.json` remain a byte-frozen historical review surface over 16 exact sources. Every original packet selection remains unselected so the reviewed input is not rewritten after the response.

## Recorded Decisions and Remaining Gates

The completed response records the following unsigned owner direction:

1. ADR-0003 and ADR-0004: accept exactly as written.
2. Workstation v1 and all 38 target values: accept exactly as definitions, with no measurement acceptance.
3. Governance-key profile: `hardware_fido2_ed25519_sk`; hardware availability: `do_not_have`; software-key risk: `not_applicable`.
4. Public-key publication: `not_yet`.

The next gate is `N0-HW-KEY-ACQUIRE-001`: Rooke Poole obtains a compatible FIDO2 security key. After that, key generation or use still requires a separate explicit approval. Public fingerprint review, allowed-signer registration, detached signing, merge, signed tagging, and publication each remain later separately gated actions.

Any future amendment or rejection stops this ceremony. The affected source must be revised or superseded, the baseline regenerated, and the complete set reviewed again.

## Custody Rules

- Keep every private or hardware-key stub outside the PooleOS tree, outputs, handoffs, cloud sync, and Git history.
- Use a dedicated governance key. Do not reuse future Secure Boot, package, update, recovery, or production release keys.
- Maintain a separately controlled recovery signer; do not place primary and recovery material on the same device or backup.
- Require a passphrase for a software key and owner presence for a hardware key.
- Record only public keys, SHA-256 fingerprints, key profile, activation/revocation state, and public GitHub key identity.
- Add a compromised or retired public key to `security/revoked-adr-signers` before trusting a replacement.

## Owner-Executed Procedure

These commands are examples for owner review. Codex must not execute key generation, GitHub registration, signing, tag creation, or branch-enforcement changes without explicit approval.

1. Create a dedicated key outside the repository. Prefer a hardware key:

```powershell
ssh-keygen -t ed25519-sk -O verify-required -C "PooleOS ADR governance signing key" -f "$HOME\.ssh\pooleos_adr_ed25519_sk"
```

Use `ecdsa-sk` only when the authenticator or OpenSSH build does not support Ed25519-SK. The provisional software fallback prompts for a required passphrase:

```powershell
ssh-keygen -t ed25519 -a 100 -C "PooleOS provisional ADR governance signing key" -f "$HOME\.ssh\pooleos_adr_ed25519"
```

2. Inspect the public fingerprint and independently confirm the file selected for the ceremony:

```powershell
ssh-keygen -lf "$HOME\.ssh\pooleos_adr_ed25519_sk.pub"
```

3. Add only that public key to GitHub as an SSH signing key, then place the exact public key in `security/owner-adr-signers.allowed` using this form:

```text
rookepoole namespaces="git,pooleos-adr-ratification-v1@github.com/rookepoole/PooleOS" <PUBLIC_SSH_KEY>
```

4. After explicit acceptance of all seven exact ADR bindings and the exact objectives definitions, generate the canonical unsigned manifest. Add `--accept-software-key-risk` only for the provisional software profile:

```powershell
python .\tools\prepare_adr_ratification.py --owner-accept-all-exact --owner-accept-objectives-exact
```

5. Review the manifest's seven ADR decisions, six bound-source digests, explicit 38-target objectives acceptance, and `measurement_evidence_accepted=false`; then sign its exact bytes under the frozen namespace:

```powershell
Get-FileHash .\runs\adr_ratification_manifest.json -Algorithm SHA256
ssh-keygen -Y sign -f "$HOME\.ssh\pooleos_adr_ed25519_sk" -n "pooleos-adr-ratification-v1@github.com/rookepoole/PooleOS" -O hashalg=sha512 .\runs\adr_ratification_manifest.json
python .\tools\verify_adr_ratification.py --allow-publication-pending
```

6. Commit the manifest, signature, public trust files, and regenerated ledgers through the reviewed workflow. Resolve the historical unsigned topic work before enabling required signed commits on `main`.

7. Once the exact evidence revision is the public `main` tip, create and verify the immutable annotated tag using the same owner key:

```powershell
git -c gpg.format=ssh -c user.signingkey="$HOME\.ssh\pooleos_adr_ed25519_sk" tag -s pooleos-architecture-v1.0.0 -m "Rooke Poole ratifies the PooleOS native architecture v1.0.0"
git -c gpg.format=ssh -c gpg.ssh.allowedSignersFile=security/owner-adr-signers.allowed -c gpg.minTrustLevel=fully tag -v pooleos-architecture-v1.0.0
git push origin main refs/tags/pooleos-architecture-v1.0.0
python .\tools\verify_adr_ratification.py --verify-remote
```

The verifier records architecture ratification only when the detached signature, annotated tag, tag-contained evidence, remote tag object, peeled commit, and exact remote `main` tip all agree. The resulting receipt still states `production_ready=false`, `production_promotion_allowed=false`, `objectives_measurements_complete=false`, and `full_n0_exit_evidence_present=false`.

## Failure and Recovery

- A missing objectives-acceptance flag, wrong profile/count, changed objective or schema byte, wrong namespace, unknown principal, changed ADR byte, changed bound source, noncanonical JSON encoding, malformed signature, revoked key, unsigned tag, moved tag, or remote mismatch fails closed.
- Never force-move `pooleos-architecture-v1.0.0`. Revoke and create a new versioned ratification tag after a reviewed superseding ADR.
- If the owner loses access before signing, discard the unsigned manifest and restart with a newly reviewed public key.
- If compromise occurs after publication, preserve the old receipt, publish revocation evidence, rotate trust through a new reviewed commit, and create a new signed architecture version.

## Primary References

- Git SSH signing and allowed signers: `https://git-scm.com/docs/git-config`
- Git signed tags: `https://git-scm.com/docs/git-tag`
- OpenSSH namespaced signatures: `https://man.openbsd.org/ssh-keygen`
- GitHub signature verification: `https://docs.github.com/en/authentication/managing-commit-signature-verification/about-commit-signature-verification`
- GitHub hardware SSH keys: `https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent`
