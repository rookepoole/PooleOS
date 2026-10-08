# Cycle 240: Native User Timer Preemption

Date: 2026-10-08. Pre-production. USI-1 / N7/N9/N12/N13.3,
`N13-USER-ENTRY-LIVE-001`, `FLAG-N13-USERSPACE-ISO-001` remains open.
No production phase or checklist item closes. The usable integration ISO remains
the intermediate milestone; complete robust native microkernel work follows it.

## Implemented

PKUSER6 extends the fixed PKUSER5 payload beyond its seven contained faults.
A LEA/PAUSE/JMP loop increments R15 without modifying arithmetic flags or the
other14 GPRs. The calibrated10ms one-shot APIC timer interrupts it on the private
16-KiB TSS.RSP0 stack through the timer gate's IST0 entry. Exact CR3, user
selectors/RSP, frame address/size, depth, vector, error and linked instruction
boundaries are checked. R15 must increase strictly on every interrupt; other
GPRs and the captured legacy x87/SSE state must remain unchanged. Two interrupts
resume the task; the third forces the existing supervisor return trampoline.

The pure `user_entry/preemption.rs` sequence validates before committing each
event and rejects replay after the third. Timer budgets reject zero counts,
unsupported HPET periods/widths, stopped/backward clocks and observed intervals
over100ms, with explicit32/64-bit wrapping behavior. Those checks run only on
delivery; an absent interrupt is NOT handled by an independent native watchdog.

The interrupt-side `arch/x86_64/user_preempt.rs` session is separate from the
active Entry/Timer owners, avoiding an interrupt-time mutable alias to either.
It verifies the exact timer ISR bit, LVT mode, expired count and legacy FP image;
masks/stops/readbacks the timer before EOI; checks no remaining ISR/IRR; and
rearms only for the first two deliveries. No AP/DMA/other device owner is admitted.
The combined trusted user driver configures the timer under CpuImage's user
exposure quarantine. It quiesces the timer BEFORE detaching private descriptors.
Failed quiescence withholds root restoration and memory release. Entry also
refuses detachment while interrupt authority remains. General driver failure
cleanup is host-tested; this concrete guest adapter has no injected failure yet.

Actual execution exposed an overstrict flags check: the timer frame contained
0x10202, including RF. The validator now accepts only that extra bit and clears
it on controlled user resumes. Every other single-bit flag difference rejects.
IF, IOPL, DF, TF, AC and reserved bits remain strict. No progress or timer deadline
was relaxed. Failure-only bounded diagnostics preserve the rejected stage/frame.

## Evidence

`runs/native-user-entry-readiness.json` SHA-256:
`719E8C31F62451FC9CA485B7D7975BA4CF9388294B5B535CAA1B7775C3A1C097`.
740 native/build/oracle inputs are byte-bound; source and owner report are
unchanged across the successful89.109s capture. Log SHA-256:
`689C2CF1CCD075998525B9E1B57DE5A9C2E2DFFFFF06A0AE627C2BBDEDBC6E44`.

- 320 debug kernel,70 repeated optimized user-entry,24 repeated optimized VM,
 five compile-fail and ten boot-exit tests pass:429 executions, not unique cases.
 Five new Rust tests cover frame, progress/register, replay, layout and clock
 rejection, including exhaustive non-RF flags.21 Python oracle tests pass.
- Formatting, freestanding kernel/library builds and two intentionally rejected
 conflicting-feature builds pass. All12 qualifier checks pass.
- Two fresh headless TCG/OVMF boots each emit35 exact matching serial/debugcon
 markers: three CPL0 timer pairs, seven CPL3 faults, three CPL3 timer/EOI pairs,
 two resumes, forced return, shutdown/detach/root restoration and13-page release.
 First/last user counter values are3333326/9999979 in each deterministic run;
 they are observed progress, not a performance benchmark or hard deadline proof.
 Six data pages are scrubbed; one separately owned ACPI snapshot page is retained.
- All66 hostile marker mutations per run reject. A third ordinary boot denies
 unsigned execution. Fresh firmware vars, read-only virtual media, no network
 or host acceleration,45s guest/360s live qualifier/900s outer bounds are retained.
 Both PooleBoot variants reproduce in two local builds, not independent builders.

Kernel:592424 bytes,164 memory pages, entry0xB000, SHA-256
`C82A0354338291020944A0D3ECDAE32CDD46E36C692FC4200E007ECB4E252D49`.
Historical0xA000 product contracts remain stale until explicit migration and
fresh replay. Retained execution receipts/closures are not rebound.
Cycle239 is frozen at `tests/fixtures/cycle239-user-entry-readiness.json`:
`7E55C1665BA04CD484B7F2E652F3014B168EF750FA5A244BD9CD535FB03D0616`.

## Retained Failures

1. `nativefirst`:81.672s, live panic before diagnostics, serial SHA-256
   `3E686D26CBFB92FFC92E58F891DC4B08D0AE65629672F9AB32079036911D16C8`.
2. `nativesecond`:34.219s, added diagnostic failed compile because EarlyLogger
   needed its crate qualifier. No guest ran. Log SHA-256
   `3AA71124CA7B60DCA65D2B65C235BCB672B9FBEEC31F131EF82104D63369029A`.
3. `nativethird`:73.063s, timer vector0x40/frame flags0x10202 rejected at
   stage1/Error::Frame despite positiveR15 progress. Serial SHA-256
   `1CD1FAA69593BE6A67EAE0C0F439E136F2058EB2E29C51F92657B0AD17DC3B9A`.
4. `nativefourth`: complete unchanged-source pass after the RF fix above.

The first/third outer logs share SHA-256
`334EAD22F035C962DB9C8B01006F4C11A8BB1A086229EEEF06A71D4A40768853`
because they contain the same generic summary, not identical guest evidence.
Every captured attempt retained its source and owner-report stability result.

Primary references: [Intel SDM event-frame RF semantics](https://cdrdv2-public.intel.com/858456/253669-088-sdm-vol-3b.pdf),
[AMD64 system programming revision3.44](https://docs.amd.com/api/khub/documents/sD1_QL~h4Afq2_tvzxqqSQ/content),
and [Intel system programming/APIC timer](https://www.intel.com/content/dam/www/public/us/en/documents/manuals/64-ia-32-architectures-software-developer-vol-3a-part-1-manual.pdf).
These inform the design; the observed QEMU RF behavior is not a physical-machine
qualification claim, and the references are not independent code validation.

## Remaining Work

This is one fixed task and a healthy timer, not multi-application scheduling,
independent failed-interrupt recovery, full FP/XSAVE context switching, general
user fault termination, arbitrary executable admission, syscall ABI, hardened
user copy, IPC, services, shell, optical ISO or physical-machine support.
The next move is a versioned bounded syscall/user-copy boundary with recoverable
faults, followed by task lifecycle/peer scheduling and capability IPC. Kernel
mechanisms must keep service/loading/shell policy in isolated user space.

The8,996 requirements/59 additions,40 phases/301 subphases,97 flags (42 open),
20 gap categories and445 architecture bindings remain accounted for.1,264 Python
tests are discovered, not claimed fully executed. PooleGlyph/checkpoints remain
Phase65 with the owner-modified report preserved; Phase66 is still open.
Fresh projection remains2/27 native admissions and5/27 retained Python closures
current, with25/22 respectively stale and boot-trust/ELF prerequisites stale.
Full exact-candidate and production gates did not run; no merge is qualified.

Metadata regression:109/109 pass in48.775s (capture49.625), source/owner unchanged,
log `D1D822194CD96CE7390C901C5B43BA106B209A295128DC3786B63198C2D20743`.
