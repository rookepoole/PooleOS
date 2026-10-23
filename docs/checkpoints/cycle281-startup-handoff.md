# Cycle281: Owned Startup Handoff

Date:2026-10-13. Previous cycle classified as progress: two bounded freestanding
application programs were compiled, verified and pushed. This cycle implements
the kernel handoff needed to deliver their actual granted handles before entry.
The owner priority remains a usable native user-space ISO, then the full robust
microkernel. No boot-screen redesign or alternative OS foundation is introduced.

## Implemented

Owned pre-entry PSTART1 replacement checks task/image identity, encoded length and
old bytes, writes only the startup block and checks final bytes. Memory failure
quarantines the retained owner, preventing partial-data execution. Existing launch
admission is tested with actual control/file SEND grants, no endpoint ownership
or delegation, restart generations and rollback at the second grant/process quota.
[Mechanism and integration contract](../native-startup-handoff.md).

The native dispatcher does not call the new API yet. Shell app commands and the
file-server app policy remain to be built. Admission and byte handoff are not one
failure-atomic transaction; the exclusive BSP dispatcher must prevent intervening
dispatch and fail closed on handoff error. That constraint is explicitly tracked.

## Verified

-551 default kernel tests in debug/release and567 file-profile tests in debug/release.
-11 new tests: seven startup/ownership tests and four launch-capability tests.
-26 whole-kernel ownership doctests; earlier11-test counts were a filtered subset.
- Every startup word tested for original mismatch, read failure, after-effect
  write failure, corrupt write and final read failure; both finish failures reject.
- Three grant generations reject both old handles; failed admission leaves no
  child authority/scheduler change and preserves live service endpoints.
- Existing user-program source bindings remain identical to Cycle280. Binaries
  were not rebuilt and historical native sessions were not replayed this cycle.

Public receipt:`runs/native-startup-handoff-readiness.json`, SHA256
`545A0332F327A13110B0B865545743EBA3E1D743FA96FCB23418258A147698A1`.
It records903 execution-source inputs as inventory, not a native execution claim.
The passing profile capture SHA256 is
`E3AD428CB7C8F0046037D42F5DB56044728BDA0C56695AAD2BD5272915D13F0D`.

The repaired metadata/oracle suite passes284 tests in58.347 seconds,59.422 seconds
including capture, with stable source and owner-report snapshots. Log SHA256
`25F8255C3EE66C9C27C7F4971D9DF42B7A62B0B0C9E2752DF5B0E249F3BB7000`.
These overlapping checks do not replace the full canonical suite. Final staged
verification rechecks receipt/source/owner hashes, historical receipts, schemas,
roadmap generation and the publication boundary after these closeout edits.

## Preserved Failures

The first run passed544 tests but failed seven new tests: their fixture lacked an
instantiated stack page. Adding the fixture's `prepare_page` repaired the tests;
the implementation and rejection conditions were not weakened. Failed log SHA256
`67A8E5D2876DBD47D30F85FD338703A3C74C73CB32315ED0C9EB02EB37CDDB56`.

The initial profile wrapper observed567/567/26 passes but incorrectly expected11
doctests, copied from an earlier filtered run. The whole-kernel expected count was
corrected to26 and a fresh capture passed. Failed wrapper log SHA256
`83B433B0C52CC0166FE935675EBA1FAE1F974EDFC204687A293E45077524E12D`.

The first284-test metadata replay found one stale source-gap inventory: the two
new kernel modules increased126 current Rust files versus the79 bound in the
historical entry receipt. Update the exact gap set/count, leaving that historical
receipt unchanged. Failed metadata log SHA256
`F1E9337EDD8F2BE44976FC3750EDD9B0705068A8384D5611BB427FC4A697F306`.

## Next Move

Implement the shell's application command/result bridge and bounded file-client
authorization, then connect the native launch catalogue to this handoff. Qualify
actual changed-input results, repeated jobs, stop/restart and contained faults;
then remaining file/cleanup controls and sustained optical ISO operation. Keep
six roles,32 PMM records,16384-byte RX and existing mapping/stack bounds pending
explicit measurement. Full robust microkernel, PooleGlyph/PDC and PooleGlass follow.

No new VM, native useful app, ISO, merge qualification, release or production claim.
No phase or flag closes.40 phases301 subphases8996 requirements59 additions98 flags,
43 open20 gap groups remain;1439 Python tests/725 architecture bindings are inventories.
Full canonical/release gates are not run. The owner checklist, Phase65 PooleGlyph
checkpoint and conformance hashes are unchanged; Phase66 remains its next step.
No owner files or PooleGlyph implementation changed. No new binary archives were
needed; the retained shared host build directory is not removed.
