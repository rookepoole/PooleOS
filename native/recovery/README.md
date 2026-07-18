# Native Recovery

This boundary owns the allocation-free `PREC1` policy, mutable-state parser,
and pure recovery transition functions. It does not perform UEFI variable I/O,
grant recovery authority, load a recovery component, or write a disk.

The host-only `prec1-probe` exists for deterministic Python/Rust qualification
and is prohibited from production media. See
`docs/native-recovery-bundle.md` for the frozen candidate contract and explicit
nonclaims.
