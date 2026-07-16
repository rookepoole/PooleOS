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

## Third-Party Material

Third-party code and data require an allowlisted license, provenance record, exact version and digest, notices, modification record, and assigned owner before publication. Studying a public implementation does not make copied code Poole-authored. Third-party code that is deliberately reused remains under `third_party/` or another clearly attributed boundary.

The historical Buildroot source tree is not published as PooleOS source and cannot satisfy a native architecture gate.

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
