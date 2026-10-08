# Cycle256: Native Request Deadlines

2026-10-08. Result: PROGRESS, not production or interactive-ISO acceptance.
Selected move N13-CAPABILITY-IPC-001; USI-1/2 partial, USI-3/4/5 not started.
Owner direction remains usable original-native user-space ISO first, then the
complete robust PooleKernel microkernel. No Linux or kernel-shell substitution.

## Implementation

[PKIPC5 contract](../native-request-deadlines.md) extends PSABI1 with call14 timed
Begin and explicit TimedOut/ClockUnavailable statuses. The persistent IPC Space
owns the non-copyable continuous hardware-clock lease and checked epoch high-water
mark. User data cannot forge time or epoch authority. Timed admission requires a
healthy sampled clock and a positive bounded relative interval with checked sum.

Expiry uses first-terminal-wins, prunes late reply authority and retains completion
quota until Take. Existing reply/cancel/discard/death results survive subsequent
expiry or clock faults. All-blocked idle samples real HPET and wakes the exact
client generation; failed resume preserves retry ownership. Read uncertainty,
regression, changed configuration, failed release or expiry-stat overflow cannot
reopen timed admission or lose the lease. Reopened epochs cannot revive old work.

Nine new host tests include boundary times, queued/claimed requests, terminal
ordering, clock failure/restart, arm/park races, retry, quotas, epoch exhaustion,
all64 input-copy fault positions, ABI validation and sticky release failure.
Existing clock operation failure/after-effect and compile-fail ownership tests
remain. Native clock-fault recovery is not established by host fault injection.

Two real private-root client/server lifetimes at persistent generations11/12
expire queued and claimed requests while both tasks are parked. The client wakes
the server without taking its completion; the server's late reply is denied and
an actual acknowledgment is delivered. The client takes TimedOut, checks the ABI,
then exits98; the server exits99. Per lifetime:5 dispatches,0 preemptions,3 waits,
3 wakes,1 idle expiry,10 CR3 writes,9/5 calls,26 released/12 scrubbed pages.
Previous seventeen containment cases and all IPC lifetimes remain intact.

The layout grows by one text page: text0x9E000, RELRO0xB0000, image0xC6000
(198 pages) within unchanged208-page capacity. Entry0xC000 and36-page guarded
stack stay unchanged. No task/watchdog/guest bounds were relaxed.

## Qualification

Exact final receipt: `runs/native-user-entry-readiness.json`, SHA-256
`D0E940208AC74CDA069AAFAD2FED93E3C5F1B97AF8A9E38C592C6E277D72AAA8`.
784 source bindings; source and owner-report snapshots unchanged during capture.
18 checks pass;443 debug kernel,138 optimized user-entry,49 optimized IPC,24 VM,
9 compile-fail,10 boot-exit and15 mapping tests total688 Rust test executions.
76 Python oracle tests and two deliberately incompatible feature builds pass.
These counts overlap suites and do not claim688 distinct tests.

Two fresh read-only QEMU/OVMF boots each emit76 markers and reject1033 altered
evidence controls. Both use software emulation without guest networking or host
acceleration. Ordinary unsigned execution denial also passes. Native totals per
probe:435 CR3 writes,928 released/427 scrubbed data pages, one retained ACPI page.
The known unmeasured dispatch remains unknown, not a fabricated runtime total.

Both timed sessions record epoch2, origin375898821, last416794460, period10000000fs,
elapsed408956390ns and262663 samples. Expiries144985330/349464940ns; ten child
enters/leaves, four mapping windows/revocations and original configuration restored
without counter reset. These are emulated observations, not hardware benchmarks.
Kernel canonical734728 bytes,198-page image, SHA-256
`FA75045265B072F4997550F58E181633D35458CDF6A5F4DA13A22919DA5428A2`.

Final bounded `nativethird` capture:341.688s, return0; log SHA-256
`7186B57A8C8A51528F08AED21CD66A592F1958F7E53640EC73CD042326A7AE12`.
Limits remain150s per guest,420s live child,900s outer capture. Metadata and
conservation closeout are recorded below after their terminal results.

## Failed Attempts And Repairs

1. Initial formatting helper lacked PYTHONPATH; corrected invocation only.
2. `hostfirst`,4.078s: a test compared Scheduler directly without Eq/Debug.
   Repaired to compare published summary/task snapshots. Log
   `3A1732BE77C9E50DA24F2C284B849198109528A82E73A174C1270B581879C661`.
3. `hostsecond`,20.688s:437 passed,5 failed because a test expected96 bytes from
   an8-byte fixture (40-byte envelope). Repaired to64-byte payload and every
   input-copy boundary. Log
   `82821739516DCCEE592001D8331ACE064C00D6D1515E68408168696D91DBC78E`.
4. `nativefirst`,79.875s: all preboot checks passed, but text0x9DC0E exceeded
   reservation0x9D000. Added one page within unchanged capacity. Log
   `5829C70E745D9156469BEED5564D4120FE08B42035BEDC56379525E035034B6C`.
5. `nativesecond`,236.468s: preboot checks passed; native round0 failed stage6008.
   `diagnostic`,158.313s exposed client task0/calls9/UD2 after three waits/wakes and
   idle expiry. ABI query left RDX=1, but Exit requires RDX=0. Cleared RDX before
   Exit98 and added a source guard. Diagnostic log
   `6433D61FBF7EE571CFD7E288C5A3ED621608D56B80E916C424E251B0AFA1FE35`;
   guest log `D9EC7A986823377E6532F663A2CBAA2F0B66EF481FC83010BB9BF670C71CBEC0`.

Earlier passing host/oracle checks are intermediate evidence, not substituted
for the final repaired candidate. Failed logs and captures remain under ignored
`outputs/cycle256-*`; the machine roadmap retains attempts and exact hashes.

## Limits And Next Move

Deadline arbitration is the authenticated syscall-entry sample under exclusive
BSP/IF0 ownership. A reply admitted before expiry may finish bounded copying after
that instant; this is not a hard-real-time deadline at the last instruction.
Timeout is not side-effect rollback or exactly-once execution. Idle polls at most
2000000 real HPET samples per interval, not power-efficient interrupt-driven sleep.
Unexpected native clock errors still halt while retaining ownership; native
recovery, SMP clocks, stopped-clock handling,32-bit wrap and suspend remain open.

Next: transactional service admission with retained rollback, sustained service
budgets instead of fixed lifetime syscall limits, and interrupt-driven idle.
Then init/confined console/input, interactive shell, read-only bundled files,
two real user applications and optical ISO interaction/fault-containment tests.

The three existing product-readiness failures remain visible:
- `tests.test_native_kernel_load.NativeKernelLoadTests.test_contract_and_readiness_pass_semantic_validation`
- `tests.test_native_kernel_load.NativeKernelLoadTests.test_readiness_detects_stale_input_and_oracle_divergence`
- `tests.test_native_kernel_transfer.NativeKernelTransferTests.test_contract_and_generated_readiness_are_current`

Migrate198-page product contracts and replay the full exact-candidate canonical
suite before main. This focused pass is not full-suite, merge or release approval.
No usable ISO was built; no key, signature, tag, release, firmware or physical-media
operation occurred. Full microkernel, PooleGlyph/PDC and PooleGlass remain required.

## Conservation

Cycle255 receipt frozen byte-exact at `tests/fixtures/cycle255-user-entry-readiness.json`:
`D52730EE4BDF217718BCB099DB9CAC2AC3E3F5610A1E84B1CEBF7F968181E793`.
Master checklist reread:8996 implementation requirements remain represented across
40 phases/301 subphases with59 additions,97 flags/42 open and20 gaps. No closure.
Checklist source hash `A8C94719FAF9428C1F133010BA2603C0270C4E1EFD7327AF8EAB9C8C362ABB3D`.
PooleGlyph Phase65 checkpoint reread; Phase66 Core IR audit remains next. Owner's
existing generated report is unchanged:
`F75E4836FAA9DDD59BA62648FE9542415F2119B659A583FB3F5959F2F5CAE87B`.
Historical execution ledger unchanged:
`65155E981FA217BD9D78218A4E0C0537A574D613ED9FB3E1EBD16511B6A1EA5D`.

Metadata closeout passes158 tests, zero skips,52.295s unittest/53.141s bounded
capture, with source and owner-report snapshots unchanged. Log SHA-256
`91344E385EE6EDB40E22C78080A48CD8868E0802E100E14DA8E40CBE9E48B7A2`.
Current architecture inventory binds530 paths. Static retained-admission projection
remains2/27 passing and four static source closures; it is not new guest execution.
Conservation passes94 tests, zero skips,8.261s unittest/9.610s bounded capture;
source and owner-report snapshots unchanged. Log SHA-256
`9AADC9BC5CA60E21F5303F8B9259161E6CCCE711E71DA332AA5DEDCFC14135E9`.
The1759-path pre-staging boundary scan passed with zero violations; its scope
excludes newly staged paths. Final commit guards therefore separately check every
staged blob against disk, all784 native bindings,1313-test discovery (not full
execution), generated-artifact consistency and the staged-path publication scan.
Their terminal receipts remain in `outputs/cycle256-*`; do not infer full canonical
qualification from any of these bounded checks.
