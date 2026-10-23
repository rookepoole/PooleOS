# Cycle294: Native Application Surfaces And Window Manager

Date: 2026-10-15. Overall status: partial. Contract PWS1.
Parent: Cycle293 native local console. Branch: `agent/userspace-integration-iso`.
PR81 remains a draft; no main merge, release, signing or production promotion.

## Delivered

- Native CPL3 compositor/window manager and independent WindowConsole,
  WindowText and WindowNumbers binaries. Terminal and two application-owned
  24x8 result surfaces render real capability-IPC file results.
- Kernel-authenticated surface endpoint, atomic nine-step session admission,
  SEND-only client grants, strict generation/sequence/handle isolation and quotas.
- Bounded PS/2 auxiliary initialization, tagged input syscall, mouse packet
  decoder, focus, dragging, clipping, minimize and taskbar restoration.
- Hardening for cancelled RPC messages, reply backpressure, exact startup
  grants, narrow damage repaint, z-order changes and released drag ownership.
  Existing root/retirement checks and admission budgets remain enforced.

## Current Evidence

Public receipt: `runs/native-window-manager-readiness.json`.
Execution binds 964 inputs; user programs bind 83 inputs. Older readiness
receipts remain unchanged; they do not describe the current source tree.

| Check | Result |
| --- | --- |
| Kernel debug/release, each | default576 / applications595 / desktop601 / windows607 pass |
| User-space debug/release | 172 each pass |
| Independent ELF/code pairs | 24 pairs byte-identical, strict admission preserved |
| Focused Python | 103 pass in8.826s; captured source unchanged |
| Optical profile | 4 QEMU passes: two normal, stale-file denial, unsigned denial |
| QEMU native keyboard | 573 device bytes, zero serial input, exact lifecycle/results/frame pass |
| Visible VirtualBox native keyboard | 573 device bytes, exact lifecycle/results/frame and owned cleanup pass |
| Combined QEMU mouse+keyboard | FAIL at240s guest bound;17 steps/50 paced movements observed;537/573 keys |
| Legacy kernel-entry-inclusive run | 117 tests,5 failures; not canonical qualification |
| Final metadata/integration replay | 386 pass in112.261s; discovered inventory1541, not1541 executed |

Focused Python log SHA256:
`892458A4DB065B4EFFFE2DBF0F46F42BF40E702A0DEFCBC33D711FF21D04CC6C`.
Final metadata log SHA256:
`75971B3F3727446D94962ED96F74BEFA32FC7C350C0AF5A80479776AF256AD17`.
The first metadata attempt ran386 with4 failures from stale cycle/schema
inventory and a historical source-delta expectation. Exact cycle294,807 bound
sources and the added PS/2 path repaired those metadata assumptions; no execution
oracle was weakened. Its retained log SHA256:
`8DDFE0F1BD6393AC03A2C92CF6FAB1DA90FD6EEEC2BBB494A7C8BD4AA8C9377D`.
Test sets overlap; do not add their counts as distinct coverage.
Guest bounds remain240 seconds (unsigned denial45). Host setup/cleanup overhead
can make total wall time larger. No timeout increase is an acceptance shortcut.
VirtualBox mouse, human typing and physical hardware are not qualified.

Current artifacts, retained locally:
`outputs/cycle294-programs6/receipt.json`,
`outputs/cycle294-optical5/receipt.json`,
`outputs/cycle294-keyboardqemu1/receipt.json`,
`outputs/cycle294-keyboardvbox1/receipt.json`,
`outputs/cycle294-mouse2/receipt.json`, and
`outputs/cycle294-keyboardvbox1/final.png`.
Raw VM identities/commands and private owner material are not public evidence.

ISO: `outputs/cycle294-optical5/PooleOS-UserSpace-Preview.iso`, 66109440 bytes,
SHA256 `451E023EDA3A4CDA848C89D8C64D65F27F564D4F88DEF6A76340A3A0F6FEB88C`.
It is a genuine unsigned EFI optical ISO, not a virtual hard disk or portable
production distribution. The configured UARTs/profile remain required.
Window kernel127/208 pages,36 guarded stack pages; console15592 bytes fits the
unchanged four-code-page limit. Production architecture/layout still rejects.

## Failures Preserved

Early freestanding program links exposed implicit copy/panic/GOT dependencies
and code size. In-place encoding, borrowed storage, bounded asynchronous
publishing and audited inlining repaired these without relaxing binary admission.
An initial rodata overflow received a windows-only0x17000 selector, not a larger
total kernel budget. Legacy desktop/application/default selectors remain.

An early optical run exposed blocking publisher latency and fatal handling of
cancelled RPC reply token0. Asynchronous publication and discard-without-apply
repaired those. Full new-window redraw then delayed Ready publication; painting
only new-window/taskbar damage repaired blank first-generation surfaces.

The first pointer attempt failed after a large unpaced relative movement.
Paced96-axis movements now match observed pointer positions, but the current
combined regression still exceeds240 seconds. Diagnostic-only runs remain
unqualified. No failure receipt is overwritten or presented as a pass.

Five legacy entry tests remain failed: contract/receipt currency, per-crate
source mutation, host toolchain mutation, exact qualifier reproduction and
shared-loader binding. Four report stale readiness; the qualifier already
expected exactly246 host tests at the parent commit. This run was observed in
tool output, not a retained hashed test log. Current host suites pass separately;
this does not make the canonical suite pass. Historical receipts stay frozen.

## Roadmap And Next Move

N29.2/.3 now partial; all40 phases/301 subphases/8996 requirements/59 additions,
99 flags44open/20 gap groups remain. No phase becomes complete. Detailed open
PWS-G1 through G7 live in the [contract](../native-window-manager.md).

Next complete an independently bounded pointer/focus scenario and input
backpressure/lifecycle work, then general app input and accessible PooleGlass.
Do not bypass VirtualBox stage117/watchdog, interruptible jobs, complete robust
microkernel, isolated drivers, persistence/networking, PooleGlyph/PDC or N0-N39.
The master checklist, PooleGlyph Phase65 checkpoint and conformance report were
rechecked unchanged; their hashes are in the public receipt. No PooleGlyph
implementation or conformance advancement is claimed this cycle.
