# ADR-0007: Repository Governance and Source Tree

Status: accepted-owner-directed  
Date: 2026-07-16  
Decision owner: Rooke Poole  
Ratification: branch protection, signed-tag, and retention controls pending  
Supersedes: none  
Superseded by: none  
Requirement mappings: N1.1, N1.3-N1.7, section 004  

## Decision

PooleOS begins as a monorepo at `https://github.com/rookepoole/PooleOS` with `main` as the protected integration branch. Rooke Poole owns technical, IP, licensing, signing, and release authority. Changes normally use reviewed topic branches; TCB, cryptography, filesystem, update, PDC actuation, licensing, signing, and release changes require owner review.

The public repository contains source-available material only. Private evidence remains in ignored local or separately access-controlled vaults under ADR-0002. No push may silently include a previously ignored private path.

Native production source is rooted under `native/`:

- `native/boot/`: PooleBoot and firmware interface;
- `native/kernel/`: PooleKernel common and `arch/x86_64` code;
- `native/abi/`: canonical generated ABI schemas, headers, and fixtures;
- `native/system/`: initial system and privileged servers;
- `native/drivers/`: isolated user-space drivers;
- `native/runtime/`: libc, language support, and core utilities;
- `native/pdc/` and `native/pooleglyph/`: native integration boundaries;
- `native/ui/`: graphics, compositor, PooleGlass, accessibility, and boot identity;
- `native/security/`, `native/recovery/`, and `native/image/`: trust, recovery, installer, and media tooling;
- `native/tests/`: native unit, ABI, emulator, fault, and conformance tests;
- `native/third_party/`: approved attributed source only.

Existing root `runtime/`, `tools/`, `tests/`, `specs/`, and `runs/` are host-side reference, evidence, planning, and transition surfaces. They are not native release-image components unless a later migration record moves reviewed code under `native/`.

Generated files live only in declared generated directories and identify their generator and source digest. Public/private headers, host/target tools, architecture-independent/architecture-specific code, vendored source, patches, firmware, device databases, Unicode/timezone data, tests, fuzzers, benchmarks, examples, and documentation remain visibly separated.

## Commit and Release Policy

Initial import may be an unsigned bootstrap commit because no owner signing key is configured on the host. It cannot satisfy signed-release gates. Production commits and tags require the later signing-custody policy, protected branch rules, immutable release refs, retained CI evidence, and review records.

## Open Items

- configure branch protection and private vulnerability reporting;
- choose owner-controlled commit/tag signing technology and custody process;
- define contributor agreement, reviewer quorum, emergency authority, severity, retention, deprecation, compatibility, and incident policies;
- create required subsystem ADRs from section 002.3 before each ABI is frozen.
