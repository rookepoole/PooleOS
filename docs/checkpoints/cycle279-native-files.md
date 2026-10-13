# Cycle279: Native Bundled Files

Date: 2026-10-13. USI-4 implementation toward the usable native user-space ISO.
The complete robust microkernel remains required after that intermediate milestone.

## Implemented

PFILE1 is a separately compiled isolated read-only file service. The native shell
now lists and reads four immutable public entries through capability IPC, including
multichunk, empty and missing files. Streaming respects console backpressure;
invalid paths and stale file grants reject. Console/process commands still work
when file access is denied. Eight-step atomic admission separates file and console
authority. No new syscall, kernel shell, host mount or writable disk is added.
See [protocol and authority](../native-files.md).

The existing six-owner layout replaces init/counter/shell with file-init/files/
file-shell; console and two diagnostic child roles remain. File init health-polls,
not a general supervisor. Diagnostic children are not the two useful applications.

## Executed Evidence

- Final-source kernel tests:540 default debug and release,556 file-feature debug
  and release. Two new atomic-admission tests; two older feature fixtures repaired.
- User tests:93 debug and93 release, fifteen new tests. All13 user programs rebuild
  independently twice with identical ELF/code bytes and no forbidden imports or
  relocations. Files2815 bytes, file init1458, file shell9512; all fit the existing
 16384-byte RX bound. Eleven ownership compile-fail doctests and Rust checks pass.
- Three final-source file guests: two independent normal builds and one stale-file
  authority control. Actual `ls`/`cat`, repeated/multichunk/empty/missing/invalid-path
  commands run while a worker is attached. Exit/stop/restart/fault controls pass.
- Three ordinary-shell and three deferred-cleanup regression guests pass. The
  latter retain suspended-parent-death cleanup through two failures and192
  independent dispatches. Two default boots plus unsigned denial pass. Total12
  final-source qualified VMs. Three earlier file guests are separate history.
- Initial focused Python oracle suite:16 tests. All fresh capture source snapshots
  and owner reports are unchanged. Final VM receipts bind892 execution inputs.
- File/cleanup kernels115 pages, ordinary shell114, default208/208. File-only RO/
  entry0xE000, default0xD000; total reservation208 and guarded stack36 unchanged.
  Dispatcher local frames49640 files and49784 normal/cleanup are not full stack
  bounds. Default RELRO padding120 bytes and text padding3026 bytes remain.
- Forty-seven generated build/media archives retain failed and successful inputs,
  verified member-by-member before removing only generated hot duplicates.

Public receipt: `runs/native-files-readiness.json`, SHA256
`D021AC1D95EC8DBB99353BE594A453BA160848E16FD42C0F8F2D34400DE1D114`.
Raw serial/console logs, challenges, screenshots, exact ELFs, media and capture/
archive manifests remain in ignored local evidence storage. Older readiness
receipts remain immutable; their source bindings are historical, not current.

The metadata/oracle suite passes282 tests in58.502 seconds (59.61-second capture),
with unchanged source and owner report. Log SHA256
`8021D17C1265A8D8304EC285281D950A4FDA45C651D1EE582584793F52982874`.
These overlapping pre-closeout checks are not the full canonical suite. The final
staged-file validation separately checks current bindings, raw native evidence,
all archived members, program pairs, owner inputs and the publication boundary.

## Failures Preserved

1. Three initial user builds exposed forbidden cross-crate/libc/panic-bound code
   references. Inline protocol definitions, checked slices and bounded local
   comparison repair flat-code generation without weakening relocation/import
   checks. All13 programs are rebuilt twice after the final change.
2. The first file kernel failed deny(warnings): the old console bootstrap was
   unused. Exclude it only from the explicit file feature.
3. The second file kernel overflowed the0xD000 RO region. Select0xE000 only for
   file profiles, leaving the208-page total and ordinary0xD000 layout intact.
4. Feature-host tests found two older console fixtures missing the multipage
   `code_end` field. Repair both and run556 tests in each profile.
5. Three earlier file guests passed before final plain-message handling. A dequeued
   message without reply authority must be dropped without stopping the service.
   Add that host case and replay fresh final-source guests. Earlier success is
   retained but does not substitute for final-source evidence.

Six failed build/test captures, three earlier passing captures and all final
captures remain hash-bound in the public receipt. No failed build is counted as
a VM execution. No timeout or acceptance bound was widened to obtain a pass.

## Progress And Next Move

USI-4 remains partial: bundled files implemented, useful applications0, new ISO0.
Next build two useful separately launched applications with visible computed
results over confined file access. Preserve six owners,32 PMM records,16384-byte
RX and reviewed mapping limits unless separately reviewed. Then qualify remaining
native file/cleanup controls and sustained optical ISO interaction on fresh boots.

Malformed requests, untracked messages and requester death have host tests only;
native injection remains open. Native live-parent deferred completion/restart,
exhaustion/multiple owners, waiting children and pending/claimed request
interleavings also remain. No general supervisor, all-idle recovery clock,
full stack proof, executable trust completion or SMP cleanup claim is made.

Owner checklist SHA256 remains
`A8C94719FAF9428C1F133010BA2603C0270C4E1EFD7327AF8EAB9C8C362ABB3D`.
PooleGlyph Phase65 checkpoint and conformance remain unchanged; no ML sources are
edited or new ML-native generation claimed. Phase66 CoreIR metadata audit remains
the stated PooleGlyph next step. Conventional Rust/compiler/linker tooling is used.

All40 phases,301 subphases,8996 source requirements,59 additions,98 flags (43 open)
and20 gap groups remain represented; no phase/flag closes.1437 Python tests and708
architecture bindings are inventories, not full canonical execution. Full canonical
and release gates were not replayed; historical load/transfer freshness failures
are not asserted repaired. This draft candidate is not merge-qualified or production
ready. Complete robust microkernel, PooleGlyph/PDC and accessible PooleGlass continue
after the usable ISO rather than being replaced by it.
