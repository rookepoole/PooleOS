# Cycle295: Bounded Native Window Input

Date: 2026-10-15. Overall status: partial.
Contract PWINPUT1. Parent: Cycle294 native application surfaces/window manager.
Branch: `agent/userspace-integration-iso`. PR81 remains draft.

## Delivered

- Native WindowConsole now owns a borrowed 64-character FIFO instead of a
  single pending character. Every poll consumes at most32 tagged PS/2 bytes.
- All decoded mouse transitions update window state; only painting is coalesced.
  Focus changes drop unread queued keys. Result panes still discard keyboard input.
- Overflow schedules Ctrl-C before any new command bytes, drops the affected
  line through its delimiter, and preserves cancellation across focus changes.
  Transport reset clears modifiers, partial mouse packets and drag capture.
  This cancels a partial shell line when read, not an already-running job.
- Six new host policy tests cover FIFO wrap, overflow/delimiter recovery, focus,
  bounded raw floods, mouse press/drag/release and transport reset.
- An explicit four-character keyboard injection mode retains the entire573-byte
  challenge and exact output/lifecycle/framebuffer oracles. Default one-byte
  injection, all timeouts and all pointer barriers remain unchanged.
- The windows-only kernel rodata boundary moves from0x17000 to0x18000 within
  the unchanged208-page image capacity. Other selectors and36-page stack remain.

## Current Evidence

`outputs/cycle295-programs1/receipt.json` passes178 user-space tests per profile
and24 independently reproduced native ELF/code pairs. WindowConsole is16332
bytes, leaving52 bytes within its unchanged four-code-page admission budget.

`outputs/cycle295-optical2/receipt.json` passes two ordinary optical sessions,
stale-file-authority rejection and ordinary unsigned-boot denial. Kernel128/208
pages,36 guarded stack pages. The development ISO is unsigned; production
layout remains rejected. Source bindings965; user-program bindings84.

Public receipt: `runs/native-window-input-readiness.json`.
Only WindowConsole changes binary identity; the other23 native programs remain
byte-identical to294. Current execution binds965 inputs; program builds84.

| Check | Result |
| --- | --- |
| Kernel debug/release, each | default576 / applications595 / desktop601 / windows607 pass |
| User-space debug/release | 178 each pass |
| Independent ELF/code pairs | 24 pairs byte-identical; strict admission preserved |
| Focused Python | 107 pass in8.758s; captured source unchanged |
| Optical profile | 4 QEMU passes: two normal, stale-file denial, unsigned denial |
| QEMU one-byte native keyboard | 573 device characters, zero serial input, exact lifecycle/results/frame pass |
| Visible VirtualBox burst keyboard | 573 characters in groups of at most4; exact lifecycle/results/frame and owned cleanup pass |
| Combined QEMU mouse + one-byte keyboard | FAIL at240s guest bound;17 steps/50 paced movements;537/573 keys |
| Combined QEMU mouse + burst keyboard | FAIL at240s guest bound;17 steps/50 paced movements;552/573 keys |
| Metadata/integration replay | 391 pass; discovered inventory1546, not a full-suite execution |

Passing keyboard sessions include exact573-byte challenge/response, real file
waits, both application generations, fault containment, recovery and all six
roles'4096-dispatch sustained window. Optical/keyboard evidence totals five
passing QEMU guests and one passing visible VirtualBox guest. Do not add
overlapping test counts as distinct coverage. The burst mode did not produce
the anticipated combined mouse pass; neither combined receipt is accepted.
Guest bounds remain240 seconds, ordinary unsigned denial45; host setup/cleanup
can make wrapper wall time longer. No bound or oracle was relaxed.

Focused log SHA256:
`092ACCD863A55C6DFBC18D277B448840A13EDE769EDEB5E79B407C046EF04CF8`.
First captured metadata replay:391 tests in113.807s, source unchanged, log SHA256
`454842313CF7023F3BBE878EF5B951F1D2498D58B2FB48744F4D41E32324E594`.
Final exact-candidate replay and publication records are retained locally under
`outputs/cycle295-metadata2.*`, `outputs/cycle295-finalcheck.json` and
`outputs/cycle295-publication.json`; these do not replace the canonical suite.
Raw input receipts are retained under `outputs/cycle295-mouse-standard1`,
`outputs/cycle295-mouse-burst1`, `outputs/cycle295-keyboardqemu1` and
`outputs/cycle295-keyboardvbox1`. Native GUI capture:
`outputs/cycle295-keyboardvbox1/final.png`. VM identities/commands and private
owner material remain local, not public evidence.

ISO: `outputs/cycle295-optical2/PooleOS-UserSpace-Preview.iso`,66109440 bytes,
SHA256 `F750999E6088D6B67481D5B21B6B35EF2285311B83D7B66B06DD149BD1BD47AD`.
Unique Downloads copy: `PooleOS-Native-Windows-Cycle295.iso`. The local launcher
pointer selects this receipt; previous images remain intact. It is a genuine
unsigned EFI optical ISO requiring the recorded VM/UART profile, not a portable
production distribution or a hybrid physical-media image.

## Failure History And Claim Boundary

The first freestanding link failed on code size and implicit copy/panic/GOT
dependencies. Borrowed storage and modular ring arithmetic repaired those
without widening user-code admission. The first optical attempt exceeded the
windows rodata boundary; the narrow selector repair does not enlarge total
kernel capacity. Failed logs/receipts and all Cycle294 receipts remain intact.

Overflow/reset behavior is host-tested, not native guest-qualified. No live drop
counter telemetry, VirtualBox mouse, physical input/hardware, general application
input, editor, file manager, complete surface lifecycle, compositor restart,
accessible PooleGlass, persistence, networking or production readiness is claimed.
Five legacy kernel-entry failures last observed in294 remain open, not silently
replayed or cleared. No canonical full-suite pass, merge, signing or release.

## Next Move

Harden surface lifecycle and qualify native input overload recovery. Resolve the
retained one-byte combined-pointer timeout; qualify VirtualBox mouse separately.
Continue general application input and useful applications while maintaining the
complete robust microkernel and all N0-N39, PooleGlyph/PDC and PooleGlass gates.
The [input contract](../native-window-input.md) records INPUT-1 through INPUT-8
and retains the window contract's PWS-G1 through PWS-G7.

Roadmap totals remain40 phases/301 subphases/8996 requirements/59 additions,
99 flags44open/20 gap groups,24 partial/1 blocked/15 not started/0 complete.
Master checklist, PooleGlyph Phase65 checkpoint and conformance report remain
unchanged; their identities are retained in the public receipt. No PooleGlyph
implementation or conformance advancement is claimed this cycle.
