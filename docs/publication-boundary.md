# PooleOS Public Publication Boundary

Status: owner-directed baseline; legal review pending  
Date: 2026-07-16  
Owner: Rooke Poole  

## Public Repository

`https://github.com/rookepoole/PooleOS` is the source-available public research repository for PooleOS. Public material may include architecture records, original PooleOS source, public specifications, public tests, bounded reference mathematics, non-sensitive receipts, reproducible build metadata, public issue history, and release artifacts approved by the owner.

## Excluded Material

The public repository must not contain:

- internal PDC GPU, CPU, RAM-lane, hash-route, tax-optimizer, or commercial implementation documents unless the owner separately approves publication;
- private benchmark datasets, unpublished results, customer data, contracts, negotiations, or personal data;
- signing private keys, secrets, credentials, recovery secrets, TPM material, or production certificates;
- NDA-derived or redistribution-prohibited documentation, firmware, microcode, fonts, certificates, codecs, or vendor material;
- unfiled patent-enabling details or hidden compiler and runtime optimizations;
- exploit details that have not passed coordinated disclosure review.

Content-addressed public manifests may preserve an excluded input's stable ID, byte count, digest, classification, and claim boundary. They must not expose private local paths or reconstructable private content.

Public signing evidence may include public keys, public-key fingerprints, allowed-signers policy, revocation records, detached signatures, signed tags, and verification receipts. It must never include a private key, hardware-key recovery material, passphrase, seed, TPM object, credential, or secret-bearing command output. The reserved ADR evidence paths are individually allowlisted and remain absent until owner-authorized signing.

The public N0 owner decision packet may include exact public source digests, proposed dispositions, advisory recommendations, objective definitions, custody-profile identifiers, an unfilled response template, and negative-control results. It must keep every owner selection unselected until an explicit response and must never contain a public key before fingerprint review, private material, credentials, signatures, merge authorization, tag authorization, or publication authorization.

## Third-Party Material

Third-party code and data require an allowlisted license, provenance record, exact version and digest, notices, modification record, and assigned owner before publication. Studying a public implementation does not make copied code Poole-authored. Third-party code that is deliberately reused remains under `third_party/` or another clearly attributed boundary.

The historical Buildroot source tree is not published as PooleOS source and cannot satisfy a native architecture gate.

The public native Tier 0 lock, profile, schemas, tools, guide, and readiness ledger may identify third-party QEMU/EDK II inputs by version, source commit, digest, relative runtime role, license metadata, and bounded probe result. Installers, extracted runtime trees, writable firmware-variable copies, launch media, traces, and local run directories remain ignored and unpublished. A public hash or qualification receipt neither grants redistribution rights nor promotes a third-party host tool into PooleOS production media.

The public native-model lock, contract, original TLA+ model sources/configurations, schemas, host tools, guide, normalized counterexample traces, and readiness ledger may identify TLC and Java inputs by version, commit, digest, license metadata, and bounded result. The JRE, `tla2tools.jar`, archives, detached signatures, TLC metadata, and raw output remain ignored and unpublished. Model evidence must preserve finite bounds, assumptions, unmodeled domains, fingerprint limitations, and implementation-trace gaps; it cannot be described as a proof of PooleOS or authorization to freeze an ABI.

## Publication Gate

Before every push or release:

1. inspect staged paths and diffs;
2. run secret and private-path checks;
3. verify ignored private vault paths remain untracked;
4. verify generated artifacts contain no private absolute paths;
5. verify licenses and notices for every included third-party object;
6. verify the commit contains no prohibited production substitute or production-readiness overclaim;
7. obtain owner review for TCB, cryptography, update, filesystem, PDC actuation, licensing, signing, and release changes.

This policy is an engineering control, not legal advice. Component-specific licensing, export, patent, trademark, and redistribution decisions remain subject to owner and qualified legal review.
