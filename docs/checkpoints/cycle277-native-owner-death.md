# Cycle277: Native Parent-Death Cleanup

Date: 2026-10-13. Selected work: USI-3 lifecycle recovery on the path to an actual
user-space integration ISO. Full robust microkernel development remains required
after the ISO. This checkpoint neither builds an ISO nor closes a production phase.

## Implemented

`PJOB1` retains generation/root-bound child ownership after parent IPC/launch/
process leases disappear. Actual owned slots supply identity, cancellation and
reclamation; failed cleanup cannot erase membership or release ownership early.
The interactive dispatcher adopts/retires children through this mechanism. Exact
user-space `fault shell` triggers a real CPL3 invalid instruction. Independent
console/init/counter services survive while both supervised children are reclaimed.
No new syscall, ambient authority or kernel command interpreter is introduced.
See [mechanism and policy](../native-job-lifecycle.md).

## Evidence

- Kernel debug/release:533 tests each, seven new job tests. Ownership compile-fail
  doctests:11. User-space debug/release:78 each. Focused Python oracle suite:15.
- Ten programs rebuilt twice with exact byte equality, no linked imports or
  relocations; nine match Cycle274. Control shell code6816 bytes, two RX pages;
  code SHA256 `6A1DBD327DAA394FD2B40EA6A9E823553BDDD9A08D18BD5BB28745C4441F594C`.
- Six new parent-death guests: three previously running children and three
  prepared children with zero entry. Each includes actual cleanup failure/retry;
  dead-parent completion publication remains zero, independent console stays live.
- Three ordinary shell and three prepared-stop regression guests pass, including
  restart and diagnostic child faults. Two default boots and unsigned denial pass.
  Total15 passing VMs plus one retained failed attempt, not16 successful boots.
- Sixteen native injected cleanup failures,80 ordinary-free denials and16 early
  completion denials across the new and prepared regression profiles.
- Final execution receipts bind876 source inputs. Program qualifier's embedded
  cycle274 and default qualifier's cycle261 are harness labels, not build dates;
  fresh Cycle277 captures and exact current bindings prove these actual runs.
- Normal112 pages; retry/prepared113; default208/208 with120 RELRO padding bytes.
  Guarded stack36 pages, measured dispatcher local allocation49432 bytes in all
  four interactive profiles. These local measurements are not full stack proof.
- Forty-six build/media archives preserve successful and failed inputs, with
  member hashes checked before removing only generated hot duplicates. No global
  tool changes, firmware, physical media, private keys, release or signing action.

Public receipt: `runs/native-owner-death-readiness.json`, SHA256
`E659BAB1387405ABDC0BB427B5051364232F89F8BC8EBF3A3578D2DEF7D604EB`.
Raw captures, console bytes, QEMU logs, object files and archive manifests remain
in ignored evidence storage. Prior readiness receipts remain frozen history.

The broader focused suite passed274 tests in62.708 seconds (64.078-second
capture), with no source/owner-report drift. Log SHA256
`4DD8949056A33D2D03252DDE1B45405B06D7F5A97C7D77C7C20BE74032568E2B`.
These overlapping oracle/metadata regressions are not the full canonical suite.

## Failures And Reconstruction

1. The initial new oracle inherited the ordinary-session retry count and rejected
   its synthetic owner-death fixture. The new profile now requires exactly one
   retry; existing profile requirements are unchanged. The15-test replay passes.
2. Moving the command wrapper by value emitted GOT `memcpy`, rejected by the
   existing linker guard. Borrowing the existing command state removed the import;
   both fresh program builds reproduce. The guard was not relaxed.
3. The first native owner-death attempt reached the frozen180-second guest timeout:
   the test expected console error-exit, but the independent endpoint owner correctly
   stayed alive. The oracle now requires exact survivor mask7 plus continued
   console/init/counter progress, and the added console-error-exit allowance was
   removed from the kernel. Six fresh guests pass; the failed run is not evidence
   for the final source. No time bound was increased.

Two closeout helper errors occurred before publication: a nonalphanumeric capture
tag was rejected before execution, and the packager initially searched the outer
JSON log instead of the actual user debug/release logs. Tags were corrected and
the actual logs verified and hashed. Neither was a guest or kernel-test failure.

## Progress And Next Move

USI-3 remains partial: prepared/suspended parent-death cleanup now has native
evidence. Waiting-child and pending/claimed-permit cases are host-tested, not
native-qualified interleavings. Scheduled asynchronous retry/backoff/exhaustion,
general supervisor restart, partial allocator-commit failure and complete stack
bounds remain open. Next close the bounded recovery gaps, then replace diagnostic
roles with init/console/shell/read-only file service/two useful apps. Keep the
six-process,32 PMM-record,8 mapping/4 frame-binding and16384-byte RX limits unless
a separate capacity change is reviewed. Sustained optical ISO interaction follows.

Master checklist and PooleGlyph Phase65 checkpoint/conformance hashes were
rechecked unchanged; no PooleGlyph edits or new machine-language claim. This is
conventional Rust/compiler/assembler/linker work, not direct PooleGlyph generation.
All40 phases,301 subphases,8996 source requirements,59 additions,98 flags (43 open)
and20 gap groups remain represented. No phase or flag closes.1429 Python tests and
686 architecture bindings are inventories, not full canonical execution.

The full exact-candidate canonical/release suite was not run. Historical
load/transfer freshness failures are not asserted repaired by these focused tests.
The checkpoint remains a draft-PR development candidate, not merge-qualified or
production-ready. Useful applications0, bundled files false, new integration ISO0.
