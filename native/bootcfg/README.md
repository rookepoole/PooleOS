# PooleOS PBC1 boot configuration

This crate is the dependency-free, allocation-free, `no_std` parser for the
bounded PBC1 PooleOS boot-configuration contract. Callers supply entry storage;
the parser borrows canonical UTF-8/ASCII fields directly from the input bytes.

PooleBoot depends on and re-exports this crate so incompatible parser changes
break the boot build. The current PooleBoot proof does not yet open a filesystem
configuration, select an entry, load an artifact, or satisfy the N5 exit gate.
The `pbc1-probe` binary is host-only differential-test transport and is excluded
from firmware builds.
