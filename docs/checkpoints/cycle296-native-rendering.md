# Cycle296: Native Rendering Cost

Date: 2026-10-15. Status: partial, native replay passed. Contract PRENDER1.
Parent: Cycle295. Branch `agent/userspace-integration-iso`; PR81 remains draft.

The previous goal turn made progress: bounded input was implemented, tested,
committed and pushed, with both failed combined mouse tests retained. This turn
targets unnecessary native rendering work without changing those test bounds.

## Delivered

Compact row expansion preserves all 256 glyph inputs and 1024 tile masks. The
window terminal omits blank glyphs only after its background is cleared. Four
new host tests cover exhaustive pixel masks, failure/overflow propagation,
sparse/dense clipped repaint after scrolling, unchanged pixels outside damage,
and elimination of 3648 blank-terminal tile calls. Two fill calls remain.

Current program qualification: `outputs/cycle296-programs3/receipt.json`.
182 user-space tests pass per debug/release; 24 independent native ELF/code pairs
reproduce. WindowConsole is 16344 bytes, 40 below the unchanged four-page cap.
DesktopConsole is 7980 bytes. Only these two program identities change, and both
have fresh optical execution evidence below.
This is not a solution to the code-capacity gap; do not call it reclaimed room.

## Failures Preserved

`cycle296-programs1` fails the code/dependency gate despite host test success.
Saturating index arithmetic removes implicit panic linkage; `programs2` still
fails size. Diagnostic maps1/2 remain oversized. Map3 outlines the existing
damage helper but creates a forbidden GOT entry; it is rejected. Map4 fits with
only12 bytes free. Map5's16-entry table leaves40 bytes and is the final mechanism
used for the independent `programs3` qualification. No link gate is weakened.

The first metadata run executes 392 tests with one failure: a current-candidate
audit assertion still expects Cycle295. It is corrected to Cycle296, retaining
the assertions that the full canonical audit is not run and not passed.
`outputs/cycle296-metadata1.json` and its log preserve that failed attempt.

## Native Evidence

Four windowed optical checks pass on the new 128/208-page image. All three
application/control framebuffer captures are byte-identical to Cycle295.
Both unchanged combined pointer modes pass: one-byte and four-character burst,
each 17 steps/50 paced movements and 573 keyboard characters, exact application
responses, file waits, fault/restart, and 4096-dispatch all-six-role progress.
The 240-second whole-guest and 12-second pointer-step bounds remain fixed.

Visible VirtualBox burst keyboard passes all 573 device characters, exact
application/file/lifecycle results, framebuffer pixels and owned-VM cleanup.
The shared legacy terminal also passes four optical checks. Both profiles include
two normal boots, stale-file authority denial and ordinary unsigned-boot denial.
No guest runtime, code-page, image-capacity or stack bound was relaxed.

| Evidence | Result | Local Receipt |
| --- | --- | --- |
| Window optical | 4 checks pass | `outputs/cycle296-optical1/receipt.json` |
| Legacy terminal optical | 4 checks pass | `outputs/cycle296-desktop1/receipt.json` |
| Full QEMU pointer, one-byte keyboard | Pass | `outputs/cycle296-mouse-standard1/receipt.json` |
| Full QEMU pointer, four-character keyboard | Pass | `outputs/cycle296-mouse-burst1/receipt.json` |
| Visible VirtualBox, four-character keyboard | Pass; owned cleanup verified | `outputs/cycle296-keyboardvbox1/receipt.json` |
| Kernel default/apps/desktop/windows | 576/595/601/607 per debug/release | `outputs/cycle296-host-summary.json` |
| Focused Python integration | 107 pass | `outputs/cycle296-focused.json` |
| Metadata/integration replay after stale-cycle repair | 392 pass | `outputs/cycle296-metadata2.json` |

There are 10 passing QEMU guest checks and 1 visible VirtualBox keyboard guest.
Counts describe these scoped runs, not a full canonical qualification or an
independent hardware benchmark. Public receipt: `runs/native-rendering-readiness.json`.
The Python sets overlap; 1547 is discovered inventory, not full-suite execution.
Architecture records bind 814 sources; execution binds 965, program builds 84.
Before commit, require a final staged 392-test replay in
`outputs/cycle296-metadata3.json`, exact-index publication scanning, all 24 binary
pairs and both optical kernel pairs rechecked, current framebuffer identities,
owned VirtualBox cleanup/runtime identity, owner-input hashes and unchanged
historical receipts. Closure evidence is retained in
`outputs/cycle296-finalcheck.json` and `outputs/cycle296-publication.json`.

## ISO Handoff

Window image: `outputs/cycle296-optical1/PooleOS-UserSpace-Preview.iso`.
Size: 66109440 bytes. SHA256:
`8B4D32976D7C85E44F7D14915013AE4AB3EE4E28B392F0073F4318C8089881A2`.
The launcher pointer selects this receipt for `Launch-Local-Console.cmd` and an
identical `PooleOS-Native-Windows-Cycle296.iso` is verified in Downloads. This is an unsigned
local optical preview requiring the documented VM configuration, including COM2.
It is not a portable production release, installer or physical-media image.

## Next And Boundaries

All Cycle295 and earlier readiness receipts remain unchanged, including their
historical pointer timeouts. The implementation changes user-space rendering;
kernel mechanisms and authority are unchanged and regression-tested.

Next qualify VirtualBox pointer input, then resolve desktop program capacity
before adding surface lifecycle/recovery and general app input. Keep native
overload/reset telemetry, VirtualBox mouse,
stage117/watchdog, five legacy entry failures, accessible PooleGlass,
PooleGlyph/PDC and every N0-N39 production requirement open. No phase completion,
canonical-suite pass, merge, signing, release or production promotion is claimed.

[Rendering contract](../native-rendering.md). Master checklist and PooleGlyph
Phase65/checkpoint report hashes were rechecked unchanged this turn. No language
implementation or conformance advancement is claimed.
