# Cycle315: Exclusive Kernel Job Ownership

Status: partial native development, not production-ready. Owner direction remains
microkernel first, with desktop as a regression consumer and demo packaging
deferred. Parent commit: `9365371b5445f6c6ac5b500c2f52e4f9586839b7`.

## Kernel Change

Three trusted-kernel API counterexamples first reproduced duplicate Job creation
for one owner, enrollment of one child in two jobs, and raw owner reclamation
before closure. These are integration defects, not demonstrated userspace exploits.
The red run has three assertion failures, zero passes; no compile failure is
being counted as reproduction. Preserve its raw log and receipt under outputs.

Slot-owned claims now make job creation and child enrollment exclusive for the
exact task/image generation. Ownership commits only after validation/capacity.
Closure requires the matching settled terminal owner and cannot reopen its job.
Raw reclaim, reap/detach, abandon and deferred cleanup reject claimed children
and open job owners before revocation, quiescence, memory or retry effects.

The matching job retains membership through failed cleanup. Whole-task release
removes the slot; later insertion makes a fresh generation. Dropping a job retains
its claims and resources, intentionally failing closed. Nested owners must close
their own jobs before a parent can reclaim them, without discarding grandchildren.
No global IDs, heap, unsafe code, widened budgets or userspace authority added.

## Verification

- Three original counterexamples now pass. Six additional tests plus extended
  existing drop coverage exercise invalid/stale/capacity enrollment, raw cleanup,
  deferred budgets/runtime, failed revocation/scrubbing, generation reuse, nested
  closure and independent-job progress.
- Final host kernel profiles: 624 debug, 624 release, 642 ordinary. The earlier
  618-test green run is retained but superseded by expanded final coverage.
- 36 focused native-oracle/budget tests pass. These overlap other selected checks.
- Nine headless QEMU guests pass: three successful exhausted-recovery controls,
  three persistent-failure controls and three ordinary-deferred regressions,
  each profile including a separate denied-authority kernel. Actual owner UD2,
  entered-child accounting and retained-page/no-repeated-write controls remain.
- Independent reconstruction checks both raw logs, console input/output, boot
  media, linked and packed kernel bytes, 1,018 execution source bindings and five
  selected paired user programs with 111 program bindings. Paired kernels match;
  the image remains within 208 pages and guarded stacks remain 36 pages.
- Selected integration/roadmap rerun: 513/513 pass; publication tests: 9/9 pass.
  The 1,661 discovered Python tests are inventory, not a full canonical execution.
  Final serialization uses 15 targeted checks; the staged audit independently
  reconstructs current receipts, all 924 architecture bindings, both retained
  ISO copies and 99 historical receipts before committing the exact 24-file tree.

Aggregate receipt: `runs/native-job-ownership-readiness.json`, SHA256
`545DDBB1D381133AA2AB6852039AB0D835B52B9C35CE6B68E08230D17D68C660`.
The immutable Cycle314 receipt remains at
`AB606AD836D1FB4B1D2CA818BE64739BFFDF347353B05ECE450869AC27592C48`.

The first 513-check integration run passed 510 and failed three stale historical
assertions: Cycle281's changed-source set omitted the newly changed task owner;
Cycle288 and Cycle313 expected the previous next-move title. Update only those
expectations, preserving all historical receipt bytes and their claim boundaries.
Retain `outputs/cycle315-metadata1.log`, SHA256
`EBA8EBEFE3F63920D319383F831062976C3CCDAAB467EE389B66FEF4EB118040`.
The corrected 513-check rerun passes, log SHA256
`3359F35D4572DA99FD0DF3340813AE62E3F91EC3469EC4146158D6AF32595FB7`.
Local final audit: `outputs/cycle315-finalcheck.json`. These selected checks do
not replace full canonical qualification or required GitHub checks; keep PR81
draft and do not merge or promote this candidate.

The source changes are restricted to task/job/cleanup ownership, their host tests
and the native interactive supervisor's mutable ownership calls. User programs,
native fault injection, the independent native oracles and retry limits are
unchanged. Existing limits remain three deferred attempts at 64/128/256 dispatch
delays plus one closed-job recovery after its separate cooldown.

## Remaining Work

This does not implement a global job graph, cycle detection, fair multi-owner
dispatch, lost-supervisor-record recovery or SMP locking. The single-owner native
regression must not be called a multi-owner proof. Next implement a bounded registry
and topology rules, then fair cleanup across failed owners, native multi-owner
controls, capability/IPC revocation and bounded service restart/rebinding.

Partial allocator release, construction/committed-handoff recovery and all-path
stack/SMP isolation remain explicit gaps. No new GUI, ISO or VirtualBox replay;
Cycle308's pointer and both ISO copies are retained. PooleGlyph Phase65 and the
owner's dirty conformance report remain unchanged; Phase66 promotion is pending.
All 40 phases, 301 subphases and 101 flags (46 open) remain. Full canonical
qualification, merge qualification and production promotion are not claimed.

Contract: [Native Job Ownership](../native-job-ownership.md).
