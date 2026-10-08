# Cycle 239: Bounded Native User Entry

Date: 2026-10-08. Pre-production. USI-1 / N7/N9/N12/N13.3,
`N13-USER-ENTRY-LIVE-001`, `FLAG-N13-USERSPACE-ISO-001` remains open.
No production phase or checklist item closes. This is real kernel development
toward the user-space integration ISO, not another boot-screen redesign.

## Implemented

PKUSER5 executes one fixed, linked assembly payload at CPL3 in the owned task
root. Its RX page and RW/NX stack remain disjoint and guarded. A private seven-
entry GDT adds user selectors 0x33/0x2B; the retained TSS points RSP0 at the
guarded 16-KiB supervisor stack. The #UD/#GP/#PF gates use IST0 so actual user
faults take that stack. Other exception/interrupt gates retain their prior IST.
The TSS I/O bitmap lies outside its limit, denying user port I/O.

IRETQ loads an exact five-word frame with IF set and IOPL zero, after clearing
15 integer registers and establishing user DS/ES and null FS/GS selectors.
Before CPU lifecycle admission, the one-BSP adapter clears FS/GS/kernel-GS bases,
debug registers and LDTR; disables FSGSBASE/RDPMC; enables supported legacy FP;
disables SYSCALL through EFER.SCE and clears available SYSENTER state. Readbacks
must match. Unsupported paging, virtualization and enabled XSAVE/control modes
reject. This first profile supports legacy x87/SSE, not arbitrary extended state.

A full canonical FXSAVE-format image initializes x87 and all XMM payloads,
not just control words. The first actual user fault verifies those bytes and
all integer registers. The payload later poisons XMM0 and uses x87; the terminal
handler observes the XMM poison, and cleanup restores and verifies the complete
legacy FP image before resources can retire. There is no pre-existing kernel FP
owner: the freestanding kernel uses its soft-float ABI. Stricter CPU settings
remain installed until terminal halt; this is not general context restoration.

The pure sequence validator requires exact root, selectors, flags (allowing only
hardware RF), user RSP, private handler-frame address, trap depth, instruction
label offsets, vectors, error codes and relevant CR2. Seven events must occur in
order: initial UD2; denied CLI; denied OUT; disabled SYSCALL; supervisor read
fault; NX stack-execution fault; terminal UD2. Layout arithmetic is bounded before
addition. Rejections never advance the sequence. Controlled return uses a
supervisor-only saved kernel stack pointer checked against the retained boot
stack, restores callee-saved registers and returns with IF clear.

CpuImage marks user exposure before calling the trusted hardware adapter, always
attempts descriptor cleanup after errors, and withholds root restoration/freeing
until same-context cleanup succeeds. Cleanup reinstalls the original descriptor
tables/TSS stack and sanitizes legacy FP state. The stack sentinel now occupies
the low end, because hardware legitimately writes the top during fault entry.

Real execution exposed a shared VM defect: inactive unmapping compared accessed
PTEs with pristine entries. Walks now tolerate only parent A; mapped leaf
transactions accept only A and, for writable mappings, D. Every other permission,
physical-address or reserved-bit difference rejects. The ledger is checked on
translation. Failed protection/unmapping restores the exact observed entry,
including hardware bits; successful protection writes the canonical replacement.
Invalidation acknowledgement remains required before frame reuse. Four new host
tests exercise successful retirement, rollback and exhaustive single-bit
non-bookkeeping corruption, including forbidden dirty bits on read-only leaves.

## Evidence And Failures

Current receipt: `runs/native-user-entry-readiness.json`, SHA-256
`7E55C1665BA04CD484B7F2E652F3014B168EF750FA5A244BD9CD535FB03D0616`.
It binds 738 native/build/oracle inputs. Final capture
`outputs/cycle239-nativefourth.json`: 81.922 seconds, source and owner report
unchanged, log `5384C527639EFB7F9E08F652CD42C0531DDC99F4B6FA2502117B350B23E86501`.

- 315 debug kernel tests, 65 repeated optimized user-entry tests, 24 repeated
  optimized VM tests, five compile-fail tests and ten boot-exit tests pass:
  419 executions, not distinct cases. Fifteen new Rust tests cover this change.
- 18 Python oracle tests, formatting, freestanding kernel/library compilation,
  and two rejected conflicting-feature builds pass.
- Two fresh headless TCG/OVMF guests each emit 34 matching serial/debugcon
  markers: three CPL0 timer/EOI pairs, seven actual CPL3 faults, descriptor
  detachment, original-root restoration, six scrubbed data pages and 13 released
  task pages. One separately owned ACPI snapshot page remains retained.
- All 51 marker mutation cases per run reject. The third ordinary boot still
  denies unsigned transfer. Fresh firmware variables, read-only virtual media,
  no guest network/host acceleration and 45-second guest bounds are retained.
  Both PooleBoot variants reproduce in two local builds. This is not independent
  OS reproduction or optical ISO qualification.

The linked kernel is 591,512 bytes / 164 memory pages, entry offset 0xB000,
SHA-256 `02C00A48D793B3956F6FACC0BA4F88AEB2F3882D4B5C6C4524EF516A6C3B4EFA`.
R ends at0xB000, RX at0x80000, RELRO at0x90000, image at0xA4000. Loads stay
page-aligned and permission-separated within the existing 192-page bootstrap
capacity, now also enforced by a linker assertion. Old 0xA000 product contracts
and receipts stay historical/stale until explicit migration and fresh replay.

Failures are retained, not promoted into successes:

1. Initial local compile found a diverging-closure inference problem and three
   missing explicit unsafe blocks. These were fixed before captured builds.
2. `nativefirst` failed linking at fixed RO/RELRO/BSS limits, before any guest.
   Its 49.516-second capture log is
   `DB767A3142AFF14EE47EA1FB37D70663778C6F160A4EA5ECFDD7A09885508627`.
3. `nativesecond` boot halted at runtime continuity because the native entry
   constant still named0xA000 after the linker moved to0xB000. It was corrected.
   Capture69.578s; guest serial hash
   `718DE3FC84AFC9ACD6F89C116DF0B96C0325536BA5B6C5F5DFBD896F47724745`.
4. `nativethird` completed CPL3 faults/return but halted at unmap stage24 due to
   accessed-bit mismatch. Capture70.719s; guest serial hash
   `2929ED87D1A46F19F920C66410AE4E0822214C6DA0DEB1FCFD6CDD92B9194FF2`.
   Both failed outer logs happen to hash identically because they report only
   the generic panic summary; the distinct raw guest logs preserve the causes.
5. `nativefourth` passes the complete unchanged-source sequence above.

Historical Cycle238 is frozen at `tests/fixtures/cycle238-user-entry-readiness.json`,
SHA-256 `73D1664F988357FC457006627277FFFC3B1036808566476B7DB5B1E55A0ED45F`.
Earlier capture receipts and the execution-source ledger are not rebound.

Primary implementation references: [AMD64 system programming, revision3.44](https://docs.amd.com/v/u/en-US/24593_3.44_APM_Vol2),
[Intel SDM](https://cdrdv2-public.intel.com/868137/325462-089-sdm-vol-1-2abcd-3abcd-4.pdf),
and [Rust freestanding target](https://doc.rust-lang.org/rustc/platform-support/x86_64-unknown-none.html).
These informed descriptor, 64-bit interrupt/IRET, I/O, paging A/D, fast-entry and
FP-state handling; they are not independent validation of this implementation.

## Boundaries And Exact Next Move

No timer is armed during the fixed CPL3 payload. Its instruction/fault sequence
is statically bounded; arbitrary programs and user-driven execution are not
admitted. No spinning-task watchdog, general preemption/state switching, XSAVE
ownership, versioned syscall ABI, hardened user copy, capability IPC, service,
shell, application session or new ISO is claimed. User architectural/descriptor
error cleanup is host-tested, not injected into guest hardware. Physical-machine
support and general SMP/device/DMA operation remain unqualified.

Next: extend the private entry/frame ownership to bounded timer preemption from
CPL3 and supervisor recovery from a spinning payload, then integrate a narrow
versioned syscall/user-copy ABI and capability IPC. Follow with isolated init,
console and file services, interactive shell/two apps, and the optical integration
ISO. Continue the complete robust microkernel after that preview.

The 8,996 locked requirements,59 additions,40 phases,301 subphases,97 flags
(42 open) and20 gap categories remain. PooleGlyph Phase65/checkpoints and its
owner-modified report remain unchanged; Phase66 is not implemented here.
Measured projection remains2/27 native admissions current and5/27 retained
Python source closures current; boot-trust/ELF prerequisites are stale. Full
exact-candidate qualification and merge gates have not run. Production is false.

Metadata replay passes 105/105 tests in48.597s (capture49.406), with source/owner
unchanged; log `8B84D6C8793446D5212E84F37C440524D684D77852671281766E5069650AC7FC`.
The initial104/105 pass retained an obsolete CPL0 qualification-status assertion;
it was corrected without changing native evidence. Failed log
`B351D09B82DFD8F99FD24600AC9B2FE149076325A005B6A4ACD2029FE0B02D07`.
Architecture bindings now cover441 files; discovery reports1,260 Python tests,
which is an inventory, not a full-suite execution claim.
