# Native Text Rendering Cost

Cycle296, PRENDER1. Development rendering work, not a general compositor or
production performance claim. PWS1 surface ownership and PWINPUT1 input policy
remain unchanged; no new kernel syscall, device authority or mapping is added.

## Invariants

- RENDER-1: all256 glyph input bytes retain the exact four tile masks, positions,
  dimensions and colors. Invalid/unsupported font bytes retain existing fallback.
- RENDER-2: coordinate overflow and transport failure stop before later tiles.
  No out-of-range shift, implicit panic/import, writable section or linked relocation.
- RENDER-3: blank-cell omission is only valid after the compositor clears the
  terminal's damaged background to PAPER. The API explicitly names ink repaint;
  ordinary repaint and direct writes continue clearing cells as before.
- RENDER-4: sparse/dense text, scrolling, empty/offscreen damage and cell-edge
  clipping produce the same pixels as full-cell rendering through the same clip.
  No pixel outside the requested damage rectangle changes.
- RENDER-5: the four-code-page,208-page kernel and36-page guarded stack limits
  remain unchanged. A faster algorithm cannot bypass native binary admission.
- RENDER-6: existing240-second whole-guest,12-second pointer-step and sustained
  progress bounds remain. Earlier timeouts stay in their historical receipts.

## Implementation

The 5x7 font still renders at2x scale into12x16 cells using four tiles. A16-byte
constant table expands four font bits into the left tile's byte. The fifth bit
forms the right tile's two pixels; each expanded row is duplicated vertically.
Only four source-row iterations per tile replace the former64 pixel iterations.
The eighth source row and unused tile columns remain zero padding.

The window compositor fills terminal background before `repaint_ink_region`.
That method visits damaged cells and omits space glyphs. It does not become a
general transparent repaint API or replace ordinary terminal cell clearing.
The blank48x19 terminal host oracle requires3648 old tile calls and zero new
tile calls, with identical background/cursor pixels and two fill calls in both.
This drawing-command count is not a measured wall-time or hardware speedup.

## Capacity And Failure History

The first candidate introduced implicit overflow-panic linkage in a new index
expression. Saturating index arithmetic removed that unsupported dependency.
Parallel tile-mask accumulation and a32-entry table still exceeded the code cap.
Outlining the existing damage helper reduced code but introduced a forbidden GOT
entry, so that candidate is rejected. The final16-entry, single-mask renderer
passes strict linking at16344 bytes:40 bytes free,12 fewer than Cycle295.
It improves rendering work, not the unresolved desktop code-capacity constraint.

Further lifecycle/desktop features require an evidence-backed service split or
separately qualified loader capacity work. Do not silently enlarge admission.
Fresh full program, window/legacy-terminal guest and input evidence is required
before claiming current native qualification. See the build plan/checkpoint for
actual receipts and remaining failures, not this mechanism description alone.

## Open Work

Surface retirement/status/restart, native overflow/reset injection and loss
telemetry, VirtualBox mouse, general application input, useful interactive apps,
accessible PooleGlass, interruptible jobs, full microkernel and all N0-N39 gates
remain. No physical-device, production, signing or full-canonical claim follows.
