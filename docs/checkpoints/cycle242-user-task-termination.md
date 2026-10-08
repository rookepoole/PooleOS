# Cycle 242: Owned User-Task Exit And Fault Termination

Date: 2026-10-08. Outcome: verified development progress, not production-ready.
USI-1 / N13.1,N13.2,N13.6 / `N13-USER-ENTRY-LIVE-001`.
Entering source: `c0d58c4331e020a59cc809bbb5f6694832814e92` on
`agent/userspace-integration-iso`. Main remains qualified through Cycle233.

## Implemented And Verified

[PKUSER8 lifecycle](../native-task-lifecycle.md) adds an exclusive task owner,
generation-scoped identity, terminal status/accounting, PSABI1 non-returning
Exit(u32), and termination of user #UD/#GP/#PF. The exact root/private entry frame
binds execution. Invalid user RIP/RSP may terminate without being resumed.
Unexpected kernel/unsupported faults remain fatal. Syscall authority and entry
references are revoked before root restoration, detach, scrubbing and release.

Four sequential native task lifetimes record Exit42, UD2, CLI and a denied kernel
read. All reject restart/reap repetition and direct premature PMM freeing. Slot
reuse rejects old task IDs; generation never wraps. Host failure injection checks
execution/quiescence/CR3 errors, corrupted outcomes, occupied insertion and retained
memory. Failed cleanup cannot invent an exit result or silently release memory.
Reap returns detached resources, not a claim that the caller has freed them.

Fresh final qualification passes:

- 745 unchanged exact native/build/oracle input bindings.
- 336 debug kernel +86 repeated user-release +24 repeated VM-release +7 ownership
  compile-fail +10 boot-exit =463 Rust test executions;26 Python oracle tests.
- Format, freestanding library/kernel and two conflicting-feature build denials.
- Two fresh headless QEMU/OVMF TCG boots, fresh variables, read-only virtual media,
  no guest networking or host acceleration, matching serial/debugcon transcripts.
- Each40-marker guest retains seven original user faults,12 copy-profile calls,
  three copy faults, three user timer interrupts/two resumes; then the four
  independently owned task lifetimes terminate and release memory.
- Ten measured CR3 writes,65 task pages released,30 data pages scrubbed, one
  retained ACPI page.157 evidence mutations rejected per guest, not hardware
  fault injections. A third ordinary unsigned boot still denies kernel execution.
- Kernel609096 bytes,168 pages, entry0xB000, SHA256
  `6CC8332F688D963134DE49B78A5474DD51B4203DC1722F56ED27FB42D45C1A8A`.
- Receipt `runs/native-user-entry-readiness.json`, SHA256
  `DC81C8D1361A0E1460E8154B688C28F3BB06DB7B259FB7EF63F99A703A26C2C3`.
- Final capture93.515seconds, source/owner data unchanged, log SHA256
  `7F3B032BC7C7115D2AEF9783A5579C43FB55CB9C67E6DC48B76F0F54479A7EB0`.

## Preserved Failure And Repair

The first complete capture passed host checks but failed optimized linking before
any guest: text reached0x81B0E beyond its0x80000 reservation. Its92.109-second
capture changed no source/owner bytes; log SHA256
`57B247E22DC1FEEEFE2727984310F6E4AF306628DBD959E58D63D13974D6F092`.
The linker text reservation grows four pages to0x84000; later section boundaries
shift by four pages, preserving their prior capacity. The image is168pages,
within the unchanged192-page cap, with the same0xB000 entry. All native/host/
guest controls were rebuilt and rerun on the repaired source. No failed guest
was discarded. Raw captures and virtual media remain local under `outputs/cycle242-*`.

## Progress, Limits And Next Move

N13.1, N13.2 and N13.6 become partial; N13.3/4 stay partial. No phase, flag or
production gate closes.40 phases/301 subphases,8996 requirements,59 additions,
97 flags/42 open and20 gaps remain.456 architecture bindings retain the new
sources, lifecycle document, checkpoint and immutable Cycle241 receipt.
Python inventory1271 is not a claim that the full inventory ran.

This is one BSP with four fixed sequential payloads, not a peer scheduler or
arbitrary-program runtime. Those payloads have no armed timer. Strict initial
syscall RSP and64-call limits can still halt the kernel; full spawn allocation
rollback is absent. These are explicit development restrictions, not production
containment. SMAP/concurrent copy, async/SMP entry, full XSAVE, independent
missing-IRQ watchdog and concrete guest hardware-failure injection remain open.

Next: timer-driven peer execution across two private roots, preserved state and
surviving-peer progress after exit/fault; then capability IPC, confined services,
shell/apps and optical ISO. Product contracts need explicit0xB000/168-page
migration and fresh replay. No full-candidate qualification, merge, release,
signing, physical write or promotion occurs here. Full robust N0-N39 microkernel
development continues after the intermediate usable ISO. No owner action is
needed for the next implementation step.

## Conservation

Cycle241 is frozen at `tests/fixtures/cycle241-user-entry-readiness.json`, SHA256
`A1D8F9AF64D05DEBC88757CA1C8D8C84BC6B292F97E07B7FEF14889614416FE5`.
The execution ledger remains unchanged, not rebound to later code. PooleGlyph
Phase65 is unchanged and Phase66 stays open; the owner's dirty conformance report
is preserved, SHA256 `F75E4836FAA9DDD59BA62648FE9542415F2119B659A583FB3F5959F2F5CAE87B`.
Checkpoint ZIP remains `F3CCEB701CF76274D9464A0958BF6106888FB34F3C0BFBD55DE4ACE03C427ABC`.
Locked master checklist remains
`A8C94719FAF9428C1F133010BA2603C0270C4E1EFD7327AF8EAB9C8C362ABB3D`.
The116-test checklist/architecture/roadmap/oracle metadata suite passes in
50.335seconds (capture51.188), with unchanged source/owner data and log SHA256
`58E42335CAC463E8531CEDA5AF91950373EB0212F91E52789291E0DCDD647733`.
Final records are regenerated after recording that result and separately checked.
Read-only source projection finds2/27 native admissions current (policy/errata)
and5/27 Python source closures current (entry/symbols/policy/revalidation/errata).
25/22 remain stale; firmware is current, boot-trust/ELF prerequisites stale.
This projection is not new execution. No new ISO or interactive session is claimed.
