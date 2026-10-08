# Cycle258: Sustained Service Dispatch

2026-10-08. PROGRESS; focused native qualification passes. Not production or
interactive-ISO acceptance; full exact-candidate canonical qualification remains.
Selected move N13-CAPABILITY-IPC-001; USI-1/2 partial, USI-3/4/5 not started.
Owner direction remains usable original-native user-space ISO first, then full
robust PooleKernel. No Linux, kernel command interpreter or splash substitution.

## Implementation

[PKSERVICE1 contract](../native-sustained-service-dispatch.md) replaces the normal
native peer's64-call lifetime kill with a64-attempt dispatch allowance. A completed
nonblocking call at the boundary saves its POST-handler result/frame and legacy
FP state, yields to the real scheduler, settles measured runtime and resumes on a
later dispatch. No syscall replay, invented timer interrupt or user-controlled
refill. Exit, blocking, fault and timer paths retain their distinct semantics.
Explicit diagnostic peers and legacy Run::new keep the old lifetime control.

Cumulative calls are checked64-bit counts. Counter exhaustion terminates before
another effect, never wraps or resets. Replenishment is denied while dispatch is
open or the task terminal. Existing Slot ownership prevents reactivation or
cancellation while runtime settlement is pending/unknown; failed cleanup retains
ownership and measurement. BudgetYield supports settled suspended cancellation.

Eight added host tests cover repeated dispatches beyond64, closed/exhausted/
mid-dispatch denial, invalid entries/returns, rejected request charges, terminal
boundary behavior, counter overflow, forged budget reports, cancellation and
cleanup-failure retention. Three added Python tests bind native field/order proof
and post-handler frame preservation; historical diagnostics remain.

Two native persistent tasks at generation15 copy eight real user bytes per call,
verify status/length/data/register preservation, and alternate through budget
yields. Task0 faults after256 calls; task1 continues to512 copies and Exit100
(513 calls). Observed14 dispatches,12 budget yields, no timer preemptions,28 CR3
writes, four surviving budget yields after the fault and26 released/12 scrubbed
pages. Both fresh boots match the frozen predictions.

## Final Native Qualification

Final capture nativethird passes in369.078s, exit0, source and owner snapshots
unchanged. All18 checks pass:459 kernel debug tests,146 user release tests,
57 IPC release tests,720 overlapping Rust executions overall,81 Python oracle
tests, freestanding/compile-fail checks, two fresh native guests and ordinary
unsigned boot denial. Each boot emits78 ordered markers and rejects1085
altered-evidence controls, retaining all17 earlier containment cases.

Each full probe restores475 CR3 writes and releases1006/scrubs463 data pages.
Service roots are24645632/24698880; measured runtime ticks are64895/129787 in each
fresh guest. These are measured samples, not a performance or uptime guarantee.
The frozen bounds remain150s/guest,420s/live child and900s/outer capture. The
normal service policy intentionally changed; diagnostic lifetime control did not.

Current receipt: runs/native-user-entry-readiness.json, SHA256
EFE6449288127C53CD6D6D3D8D47E0C69ED3E7EB49470F12F1E769495D901C0B.
Final log C224EB054B881CBE1952C3A67548E8576FB8E105B0B7EAC8EF546E80383466D6.
Canonical kernel751128 bytes, SHA256
E77A290055C7C8DF3C9730E8E9B0159024E36036D9A748FF2477B3DC33DBB104.
Receipt binds788 source inputs. Native/oracle/qualifier inputs remain frozen after
this pass; closeout documentation cannot substitute for native qualification.

## Failed Attempts And Repairs

- hostcompile16.797s:450 tests passed/one failed. The old forged-preemption fixture
  treated65 lifetime calls as invalid; that is now legitimate service behavior.
  Replaced it with an actually invalid budget report and explicit counter-reason
  mismatch. Log C9AED9A4F0F388C346ED5E37FC66DEB796E412A51BF009693F90AB83B0CB81BE.
- nativefirst40.125s: host debug/release and VM checks passed; freestanding adapter
  found three IPC diagnostic call arrays still u32. Migrated them to u64.
  Log43C80C379E744C4D91A0FA0BB0570921BC63C42BD31E125318753CC69A7C905C.
- nativesecond79.297s: all17 preboot checks passed, but text0xA19CE exceeded0xA1000.
  Grew one text page: data0xA2000, RELRO0xB4000, image0xCA000=202 pages.
  Entry0xD000, capacity208 and36-page guarded stack remain unchanged.
  Log71CB95A352CF0E16A733D491A455867079FDEF10D281B9BA32F54B17A4210F49.

Failed capture logs remain under outputs/cycle258-* and are not replaced by later
passes. All captures keep source and owner snapshots stable; no timeout was used
to restart a live process. Earlier intermediate checks do not replace final proof.

## Limits And Next Move

The allowance bounds syscall work per dispatch, not wall-clock rate or reserved
CPU share. The native test establishes equal-priority interleaving, not arbitrary
priority starvation freedom or SMP scheduling. Existing checked scheduler/runtime
counters still have finite exhaustion boundaries; indefinite uptime is not proved.
Copy verification is not exactly-once arbitrary device/service execution.

Next: owned executable/argument service bootstrap and actual init, with normal
session startup separated from exhaustive qualification. Then confined console/
input, efficient interrupt-driven idle, shell/read-only files/two apps and optical
ISO interaction plus sustained-session/fault-recovery acceptance. General resource
policy and native clock-fault recovery remain. One unknown dispatch stays unknown.

202/208 image pages leaves6. Resolve profile/layout pressure or review a capacity
migration before exhaustion, without deleting required qualification. Three known
product-readiness failures remain:
- tests.test_native_kernel_load.NativeKernelLoadTests.test_contract_and_readiness_pass_semantic_validation
- tests.test_native_kernel_load.NativeKernelLoadTests.test_readiness_detects_stale_input_and_oracle_divergence
- tests.test_native_kernel_transfer.NativeKernelTransferTests.test_contract_and_generated_readiness_are_current

Current product contracts and full exact-candidate canonical replay still gate
main. No ISO, key, signature, tag, release, firmware or physical-media action.
Full microkernel, PooleGlyph/PDC and accessible PooleGlass requirements remain.

## Conservation

Cycle257 receipt is frozen byte-exact at tests/fixtures/cycle257-user-entry-readiness.json:
BA8701DCAD3D4327692EF75C32FAF13549C81ED559F79E9BAC4C852B23EEA775.
Checklist remains8996 requirements across40 phases/301 subphases,59 additions,
97 flags/42 open and20 gaps; no closure.
Checklist A8C94719FAF9428C1F133010BA2603C0270C4E1EFD7327AF8EAB9C8C362ABB3D.
PooleGlyph Phase65 checkpoint reread; Phase66 Core IR audit remains next.
Archive F3CCEB701CF76274D9464A0958BF6106888FB34F3C0BFBD55DE4ACE03C427ABC verified.
Owner report F75E4836FAA9DDD59BA62648FE9542415F2119B659A583FB3F5959F2F5CAE87B
remains unchanged; historical ledger
65155E981FA217BD9D78218A4E0C0537A574D613ED9FB3E1EBD16511B6A1EA5D is conserved.
Metadata closeout passes165 tests with zero skips,52.795s unittest/53.641s capture.
Source and owner snapshots remain unchanged. Log SHA256
239AFD4549C0F663C6D43AB5027C9E1B2152748FDC5B378622E6E76B21B0AF19.
Architecture inventory binds540 paths. Retained-admission projection is2/27
passing with four static source closures; this is not new guest execution.
Conservation passes101 tests with zero skips,8.397s unittest/9.719s capture,
source and owner snapshots unchanged. Log SHA256
DDDDD84E9A9E4574B23695F3B2D0F85ED1B12870DD6975357F4843385D8BF7A9.
Final staged-blob, native-binding, generated-artifact,1320-test discovery and
staged-path publication checks are retained separately under outputs/cycle258-*.
Discovery is not execution; none of these focused checks is full canonical
qualification. The development branch remains unqualified for main or release.
