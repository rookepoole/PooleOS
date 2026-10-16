# Cycle289: Ordinary Application File Waits

Date: 2026-10-13. Prior checkpoint d935a3e delivered the optical preview. This
cycle resumes the robust microkernel program through useful user/kernel integration.

## Decision And Scope

The shell-stop dispatcher already handles Waiting tasks, while active shell jobs
are synchronous and ordinary Text/Numbers previously busy-polled file requests.
Instead of claiming a nonexistent kernel algorithm defect, this cycle connects
ordinary applications to the existing PSABI1 RequestWait path. Dedicated claimed
requester probes, asynchronous shell changes and generalized idle were alternatives;
they remain explicit follow-on work. No production phase or implementation flag closes.

Hard invariants: original native boot/kernel and isolated CPL3 apps; one syscall
per application step; scalar wait arguments; retained request ownership until
authenticated consumption; no changed kernel wait algorithm, capacity or timeout;
strict native wait/wakeup evidence; reproducible optical bytes; unchanged ordinary
unsigned denial; preserved previous preview, historical receipts and owner inputs.

## Implementation

File Client exposes non-consuming wait, including Again and Revoked notification.
Program adds a separate Wait state before Data, rearms if a poll is not ready, and
fails closed on malformed wait results. Revoked wakeup must still reach RequestPoll
to free its request slot. ConsoleCalls sends no pointer/length for RequestWait13.
Host tests preserve one syscall per step and exact peer/frame/sequence checks.

The development dispatcher records WAIT after park and WAKE after successful wait
completion, before user resumption. The oracle correlates task/generation/calls,
pending/completed ownership, event order and intervening samples; missing, forged,
duplicate, reordered and resumed-while-blocked observations reject. Diagnostic
profiles keep their separate cancellation/death contracts. This instrumentation
does not alter the production wait algorithm or grant new user authority.

## Evidence

20 clean independent user program pairs are byte-identical. Only PooleText and
PooleNumbers differ from Cycle287; all18 other program bytes remain equal.
143 user host tests pass in debug and release. Kernel tests pass554 default and
573 application tests per debug/release, plus26 doctests.52 focused Python tests
pass in9.399 seconds. These overlapping counts are not full canonical qualification.

Six fresh read-only QEMU/OVMF optical boots pass. Two normal guests each prove20
park/wake pairs across both generations of both apps. The stale Numbers grant
control proves14 Text pairs and no Numbers file wait. All three complete the exact
557-byte scenario and a4096-dispatch six-role sustained window. A strict launcher
replay adds20 pairs; ordinary unsigned transfer is denied. The actual host Terminal
adapter passes557 injected keys and1897 response bytes. No human keyboard, native
display, physical hardware or performance benchmark is claimed.

Application kernels reproduce across two clean builds. Kernel geometry remains
121/208 reserved image pages and36 guarded stack pages. Each optical variant is
authored twice with exact equality, and both normal images match. The current ISO
is66109440 bytes, SHA256
`17A5D17F11F106F27EA22B6E5939A8F4449496086963245DC3E5002642499969`.
The unchanged production-layout scanner still fails four future paths; the strict
twelve-file development layout passes separately. It is unsigned and virtual-only.

Immutable public receipt: `runs/native-app-file-wait-readiness.json`,1719524 bytes,
SHA256 `FC1BAB005C909467D9995CA2E5F9C5593B5802AA989134629F6A10B5E695852A`.
It binds931 execution inputs,68 user-build inputs, exact prior receipt/source
delta, all native runs, builds and capture identities. Native qualification took
278.641 seconds including builds; each app retained240 seconds and denial45.
Host capture51.719 seconds, launcher84.266, terminal59.875. All preserve source
and owner-report hashes. The live PooleGlyph checkpoints remainPhase65, with
Phase66 Core IR audit next; master checklist/archive/report identities are unchanged.

## Preserved Failures And Retention

Two initial formatter invocations lacked PYTHONPATH and did not run; corrected
invocations passed. The first user build passed134 tests but failed nine shell/app
bridge tests whose mock accepted only RequestPoll. The model now implements the
new non-consuming wait with caller/empty-wire checks. All143 tests then pass in
both profiles; no guest failure or relaxed limit was needed. Failed capture log:
`20689847AD8D88BCB227CFCE3FE1416F1CD78D00BFE354C3AD191D495F5336B4`.

Three older Cycle287 native build trees,3534 files/1303635518 bytes, were retained
on D: with independently checked source/copy hashes before exact workspace copies
were removed. Manifest SHA256
`2B6A1B2B4DC68DCB1EFD294DD860EC6BED6F35FE650FE85039FD89B9DD1487C6`.
Shared host cache, owner temps, previous/current ISO and user program pairs remain.

## Next Move And Open Gates

Qualify the actual shell process-stop permit against a waiting/claimed requester,
including revocation, stale tickets, late replies, both generations and surviving
services. Then make active jobs interruptible. Native revoked-wakeup controls,
general idle/CPU-efficiency measurement, race/stress, service supervision, exhausted
owner recovery, full stack bounds and fresh diagnostic/default guest replays remain.
So do portable packaging/final layout, drivers, input/display, persistence/networking,
PooleGlyph/PDC, accessible PooleGlass and all production/signing gates.

40 phases,301 subphases,8996 requirements,59 additions,98 flags/43 open and20 gap
groups remain. No main merge, signing, tag, publication or production promotion.
Metadata and final staged verification are recorded during closeout below.

The first330-test metadata replay failed three assertions from two stale Cycle288
expectations: schema last_updated_cycle and the qualification-status label. They
are updated to the exact Cycle289 values; no native or production rule was loosened.
The failed run took93.731 seconds (94.953 capture), log SHA256
`53928649E6E815890189F34921A03AF51F4A1519E312BE83C42CC40924E054CF`.
The second replay exposed the next assertion in that same test: candidate-audit
cycle still expected288. Updated to289 while audit status remains not_run. It
failed one of330 tests in95.258 seconds (96.718 capture), log SHA256
`587F5B9BB51334AF696740F5EA0AD5CD34BD97386D20BE528FC1F481F5896F74`.
The repaired full focused metadata replay passes330 tests in93.789 seconds
(95.047 capture), log SHA256
`93B129B668695D0EEA900CEE92E82CEC3F3CD56F54FC2F0E6CCFC8AF3841CB05`.
Inventory is1485 Python tests,764 architecture bindings,931 execution inputs
and68 user inputs. Inventory is not execution; full canonical remains not_run.
