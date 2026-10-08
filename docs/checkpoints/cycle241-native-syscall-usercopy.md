# Cycle 241: Native Syscall And User-Copy Boundary

Date: 2026-10-08. Outcome: verified development progress, not production-ready.
USI-1 / N13.3-N13.4 / `N13-USER-ENTRY-LIVE-001`.
Entering source: `e85b1e46c93dea84a0d1f999616107ecefec89c6` on
`agent/userspace-integration-iso`. Main remains the qualified Cycle233 baseline.

## Implemented

Original PooleKernel PKUSER7 executes x86-64 SYSCALL with supervisor-owned stack
switching, FMASK sanitization, checked user return frames and IRETQ. The
[PSABI1 development profile](../native-syscall-abi.md) specifies register layout,
version1, errors, zero-length behavior and bounded256-byte snapshot copying.
It grants no capability/object authority and is not the full production ABI.

The pure module validates requests, canonical bounded ranges, overflow, return
frames and exact copy-fault context. The privileged module leases/readbacks
STAR/LSTAR/CSTAR/FMASK and EFER.SCE, and arms only linked byte-access fault fixups.
Nested recovery requires depth2/#PF/CPL0, exact CR3/RIP/CR2/access/error bits and
private-stack frame geometry. Other kernel or nested faults remain fatal.
Root/flag/armed-operation invariant failure is fatal, not ordinary user EFAULT.
No aliasing borrow of the suspended syscall session is taken by nested recovery.

Input is completely snapshotted before output, including overlap: an input
fault leaves the destination untouched; an output fault reports its committed
prefix. No output rollback is promised. Every256 input/output fault position
is tested at host level. The real fixed CPL3 payload verifies success, zero
length, bad version/number/flags/count, kernel/wrapping pointers, guard-crossing
input/output and denied write to RX code. It enters once with DF set.

After12 calls a separate checked completion trap verifies the experiment,
disables SCE and clears/readbacks all four entry MSRs. Existing timer recovery
then runs, followed by timer shutdown, descriptor detach, root restoration and
all13 task-page releases. The original disabled-SYSCALL fault remains a separate
earlier test, not a contradiction of later explicitly enabled calls.

## Fresh Evidence

- Receipt: `runs/native-user-entry-readiness.json`, SHA256
  `A1D8F9AF64D05DEBC88757CA1C8D8C84BC6B292F97E07B7FEF14889614416FE5`.
- 742 exact native/build/oracle source bindings unchanged during capture.
- 326 debug kernel +76 repeated user-release +24 repeated VM-release
  +5 compile-fail +10 boot-exit =441 Rust test executions;23 Python oracle tests.
- Format, freestanding library/kernel and two incompatible-feature rejections pass.
- Two fresh headless QEMU/OVMF TCG probes with fresh variables, read-only virtual
  media, no guest networking/host acceleration and exact serial/debugcon match.
- Each36-marker probe: seven legacy user faults,12 syscalls (3 OK,1 version,
  1 unknown,4 arguments,3 copy faults),1 input PF/2 output PFs,1 completion trap,
  three user IRQ/EOIs, two resumes, preserved state and full cleanup.
- 89 independently rejected marker mutations per probe; third ordinary boot
  still denies unsigned execution. These are evidence controls, not89 hardware
  fault injections. User progress counters:3333326 then9999980 in both probes.
- Canonical kernel592568bytes,164pages, entry0xB000, SHA256
  `902067D766A253B0700AC2707AAFF3408964F01D789A1675403FEB91D503EFA1`.
- Native capture88.875seconds, unchanged sources/owner report, log SHA256
  `E159E172F2F322C7F983BB80BFC4BEE7262D272B94E7C78E8AF4C2707BE986C4`.

The first complete native capture passed. Preliminary compile review corrected
an unsafe CR4 read before that capture; no failed guest evidence was discarded.
Raw logs/virtual media remain local under `outputs/cycle241-*`; the public
receipt records hashes and exact commands, not a published bootable ISO.

## Progress And Boundaries

N13.4 advances from not_started to partial; N13.3 stays partial. USI-1 remains
partial; USI-2 through5 are not_started. No phase, implementation flag or
production gate closes.40 phases/301 subphases,8996 checklist requirements,
59 additions,97 flags/42 open and20 gaps remain. Python inventory1267 is not a
claim of a full1267-test run.450 architecture bindings retain the new sources,
ABI documentation, checkpoint and immutable Cycle240 receipt.

Single BSP, fixed admitted RX code/RW-NX stack, no AP/DMA/concurrent mapper,
legacy x87/SSE only. Conditional SMAP access code is compiled, not live-qualified
on this qemu64 profile. No concurrent pin/copy, general NMI/SMP entry, arbitrary
programs, complete ABI restart/cancellation/tracing, or syscall while timer armed
is qualified. Missing-IRQ recovery remains externally bounded, not an independent
native watchdog. Concrete guest hardware/cleanup-failure injection is still open.
These requirements remain under N13.3/4, N12, N35 and the open USI integration flag.

Task exit/reaping/accounting, general fault termination, peer scheduling,
capability IPC, init, confined console/filesystem services, interactive shell,
applications and optical integration are not implemented by this checkpoint.
Historical0xA000 product contracts still need explicit migration and fresh
qualification. Never rebind old execution as current evidence. No full-candidate
canonical qualification, merge, release, signing, physical write or promotion.

## Conservation And Next Move

The first112-test metadata audit had one stale qualification-status expectation:
it still described syscalls as pending. The new syscall and historical-evidence
tests passed. The assertion was updated to the new partial-development status,
not weakened; failure log SHA256 is
`42E223E12DF2FDA32DF014F1446B9F903CAF123836AB53AB77CFF178C30CDB73`.
This48.808-second test run/49.625-second capture changed no source or owner data.
The corrected112-test audit passes in48.713seconds (capture49.532), with unchanged
source/owner data and log SHA256
`F589BFF9A9BB03377AD855AC8CB9A3427ABFA61A2E1ADB580C2E1D28D3D2DE2F`.
Final metadata hashes are regenerated after recording this result; a separate
conservation pass checks those final records before publication-boundary scanning.

Read-only retained-gate projection remains2/27 native admissions current
(policy/errata),5/27 Python source closures current (entry/symbols/policy/
revalidation/errata), with25/22 stale respectively. Firmware is current;
boot-trust/ELF prerequisites are stale. The projection is not new guest execution.

Cycle240 is frozen at `tests/fixtures/cycle240-user-entry-readiness.json`, SHA256
`719E8C31F62451FC9CA485B7D7975BA4CF9388294B5B535CAA1B7775C3A1C097`.
The retained execution ledger is not rewritten. PooleGlyph remains Phase65;
Phase66 is open and the owner's dirty report is preserved byte-for-byte:
`F75E4836FAA9DDD59BA62648FE9542415F2119B659A583FB3F5959F2F5CAE87B`.
Checkpoint ZIP remains `F3CCEB701CF76274D9464A0958BF6106888FB34F3C0BFBD55DE4ACE03C427ABC`.
Locked master checklist remains
`A8C94719FAF9428C1F133010BA2603C0270C4E1EFD7327AF8EAB9C8C362ABB3D`.

Next: implement owned task exit and fault termination with generation-safe
identity, status/accounting, no resume after retirement and retained-on-failure
cleanup; then connect peer scheduling across private roots. Preserve all current
normal/fault/copy/timer/ordinary-denial controls. Capability IPC and confined
services follow before a usable shell and actual optical ISO. Continue the full
robust microkernel after that intermediate preview. No owner action is needed
for the next implementation step.
