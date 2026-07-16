# PooleOS Architecture Decision Records

Architecture Decision Records (ADRs) are immutable decision snapshots. Superseding an accepted ADR requires a new ADR that names the prior record; accepted records are not silently rewritten to make history appear cleaner.

## Status Values

- `proposed`: engineering proposal not yet accepted by the decision owner.
- `accepted-owner-directed`: accepted by an explicit Rooke Poole direction in this development thread.
- `accepted-signed`: accepted and bound to an owner-controlled cryptographic signature or signed release tag.
- `superseded`: replaced by a named later ADR.
- `rejected`: retained as a reviewed but rejected alternative.

An owner-directed ADR is not equivalent to a cryptographically signed ADR. The N0 exit gate remains open until every required constitution record has the required signature and review evidence.

## Required Header

Every ADR records its ID, title, status, date, decision owner, ratification state, requirement mappings, and supersession relationship. Machine evidence in `runs/native_architecture_baseline.json` binds the exact bytes of the current constitution set.

## Constitution Set

- `0001-native-pooleos-constitution.md`
- `0002-reuse-clean-room-and-publication-boundary.md`
- `0003-language-and-toolchain-split.md`
- `0004-product-names-and-version-namespaces.md`
- `0005-v1-scope-mission-threats-and-non-goals.md`
- `0006-tcb-and-component-placement.md`
- `0007-repository-governance-and-source-tree.md`

`0000-template.md` is the required template for subsequent decisions.

