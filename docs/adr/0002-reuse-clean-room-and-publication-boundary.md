# ADR-0002: Reuse, Clean-Room, and Publication Boundary

Status: accepted-owner-directed  
Date: 2026-07-16  
Decision owner: Rooke Poole  
Ratification: cryptographic signature and legal review pending  
Supersedes: none  
Superseded by: none  
Requirement mappings: N0.2, N1.4-N1.6, section 000.2, section 003, ADD-REUSE-001  

## Context

"From scratch" must distinguish Poole-authored production code from public standards, build tools, attributed third-party components, firmware, and knowledge obtained from other implementations. The public GitHub repository must also preserve the PooleGlyph-style source-available IP boundary.

## Decision

PooleBoot, PooleKernel, the native ABI family, Poole libc, shell, core utilities, PooleFS, native service and driver protocols, PooleGlass, installer, recovery, package/update formats, and release tooling are Poole-authored components.

Public specifications and lawful hardware documentation are primary implementation authorities. External code is never relabeled as Poole-authored:

- copied or adapted code lives in an attributed third-party boundary with license, provenance, patches, digest, SBOM, and owner approval;
- permissively licensed implementations may be studied only under a recorded provenance review; core Poole-authored code is implemented from specifications and independent tests;
- clean-room separation is required for nonpublic protocols, risky reverse engineering, NDA material, or any source study that could contaminate an original implementation claim;
- NDA-derived knowledge remains segregated as its terms require;
- reverse engineering must be lawful, documented, and independently reviewed before publication.

Vetted third-party cryptography and font rasterization may be ported only outside ring 0 after license, constant-time or memory-safety, provenance, and update review. UEFI verification code in PooleBoot receives separate TCB review. Official Unicode, timezone, certificate, and similar data may be consumed under recorded terms.

Vendor firmware or microcode may be loaded only when redistribution or user-supplied installation is lawful, exact bytes are hashed, external trust is declared, updates and revocations are handled, and the receiving driver is capability-confined. Unknown redistribution rights block inclusion in public source or release media.

POSIX is a compatibility reference, not PooleOS identity. Linux ABI and kernel-module compatibility are prohibited in v1. Windows application compatibility is deferred beyond v1 and, if later accepted, must remain a user-space compatibility domain. PooleGlyph and reference PDC are required for the production release but not for the first PooleBoot or kernel proof of life; optimized PDC routes cannot block early boot.

The public repository excludes internal implementation documents, private benchmarks, customer material, credentials, private keys, NDA material, unfiled patent-enabling details, hidden optimizations, and redistribution-uncleared binaries. Hash-only public provenance is permitted.

## Consequences

Some local evidence is deliberately ignored by Git and cannot be reproduced from the public checkout alone. Public CI must identify that boundary instead of pretending private evidence is present. Production release review still requires authorized access to all private inputs that affect release bytes or claims.

## Evidence and Exit Gate

`LICENSE`, `NOTICE.md`, `docs/publication-boundary.md`, `.gitignore`, third-party inventories, and staged-file scans must agree. Legal review and owner signature remain release requirements.

## Open Items

- component-specific license classification beyond the repository default;
- contributor agreement and patent policy;
- jurisdiction-specific reverse-engineering, export, and firmware advice;
- trademark conflict searches and registrations.

