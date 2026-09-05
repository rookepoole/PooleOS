# PooleGlass Visual System

Version: 0.1.0, native design direction, Cycle 151.
Owner: Rooke Poole. Status: demo boot artwork implemented; desktop specification,
not a claim of an implemented compositor, accessibility stack, or design award.

## Identity

PooleGlass is PooleOS's original liquid-glass visual language. A clear optical
P inside a fine circular rim introduces the system. The material is transparent
glass with narrow silver highlights, restrained aqua refraction, and a small
rose reflection. It is not opaque chrome, a glowing orb, or a decorated app tile.
The wordmark is simply **PooleOS**, with normal letter spacing and quiet,
high-contrast typography. Do not put a promotional slogan on the boot screen.

The design must work through a whole day of real workstation use. Content comes
first. Glass identifies system navigation and transient controls; documents,
code, tables, terminals, settings forms, and security decisions retain stable
opaque reading surfaces. No glass-on-glass nesting or blurred text. Avoid a
monochromatic blue/purple desktop and avoid decorative cards around page sections.

Machine-readable proposed values live in `specs/pooleglass-design-tokens.json`.
These are design targets, not hardware performance measurements. Production
code must eventually consume one versioned token contract, not copied constants
in each application. The firmware demo has an intentionally bounded subset.

## Materials

| Material | Use | Required behavior |
|---|---|---|
| Canvas | Files, text, code, tables, settings bodies | Opaque graphite or neutral white; no background distortion |
| Glass regular | Window chrome, task switcher, system navigation | Controlled tint and edge highlight; bounded backdrop sampling |
| Glass clear | Sparse controls over an inspected image or media | Only where measured contrast passes; never behind long text |
| Solid accessible | Reduced transparency, high contrast, low-power fallback | Same geometry and semantics, opaque fill, explicit border |
| Trusted solid | Login, permissions, secrets, updates, destructive actions | Unambiguous system-owned identity; no untrusted backdrop sampling |
| Recovery solid | Safe graphics and recovery | No shader, compositor, animation, or normal-session dependency |

Use one restrained 1-pixel separator and at most one shallow shadow for hierarchy.
Repeated item panels and dialogs use at most an 8-pixel radius. Tool buttons are
stable squares with familiar icons, focus rings, and accessible names. A circle
is appropriate for an icon-only launcher or indicator, not for every setting.

Backdrop sampling must be clipped to the owning surface's authorized composition
region. Do not sample protected content across sessions, desktops, secure prompts,
or capture boundaries. Cached glass textures must be invalidated when their
source changes ownership or privacy state. These are N29 protocol requirements,
not claims established by the static bitmap.

## Color And Type

Graphite `#0C0F14`, white `#EEF2F5`, and steel `#A4B1BD` establish the demo.
The full shell adds neutral light surfaces, aqua selection, green success,
amber warning, red danger, and rose only as a restrained optical accent.
Status always has an icon or text label in addition to color.

Set type by semantic role, not viewport-width formulas: 14/20 body, 12/16
secondary, 18/24 section, and 32/40 screen title are initial logical-pixel targets.
User text scaling takes priority. A boot wordmark is brand artwork, not the
desktop's standard title size. Use normal letter spacing and no uppercase
microcopy for dense controls. Keep line lengths comfortable and labels localizable.

Production font selection, shaping, fallback, hinting, emoji, RTL, script coverage,
and licensing remain N29.4 work. The demo uses pre-rasterized Bitstream Vera
lettering with its notice included on the ISO; it does not embed a font engine or
claim arbitrary text, Unicode, or screen-reader support.

## Motion And Boot

1. Firmware draws a bounded static mark. It must never wait for an animation,
   network request, GPU driver, or external asset decoder.
2. Native diagnostics and machine-readable boot evidence proceed independently.
   A pretty frame must not represent completed stages that have not occurred.
3. After a verified early-user-space display service is ready, the future animated
   transition may resolve a subtle edge reflection into the same stationary mark.
4. Use one short transition, not an endless spinner or fake progress percentage.
   Error, timeout, cancellation, or recovery must interrupt presentation immediately.
5. Reduced motion selects the same static composition. Reduced transparency and
   high contrast select an opaque, legible treatment. No flashing or large parallax.
6. Transition to login or the shell without changing the logo geometry abruptly.
   The compositor must not hold up system readiness while it catches up visually.

Suggested motion tokens: 120 ms response, 180 ms surface change, and at most
800 ms for an optional boot reveal. No minimum boot delay is required. Ease out
gently, never bounce security prompts. These timings require target measurements.

**Cycle 151 reality:** the UEFI demo renders the new static image. PooleKernel then
replaces it with its existing diagnostic console. There is no animated boot,
desktop transition, real-time refraction, or production accessibility preference
reader yet. A host-controlled demo pause may hold the actual guest boot frame
for inspection; this is not guest animation and is excluded from boot timing.

## Whole-System Application

| Surface | Design direction | Native implementation home |
|---|---|---|
| Boot and safe graphics | Same P, stable wordmark, immediate diagnostic fallback | N5.1, N6 framebuffer lifecycle, N29.8 |
| Login and lock | Quiet background, opaque trusted credential area, visible session identity | N22.2, N29.3 |
| Desktop and windows | Unframed workspace, glass chrome, solid content, clear active focus | N29.1-N29.3 |
| Launcher and task switcher | Compact icon grid/list, keyboard search, stable window previews | N29.3, N29.5 |
| Files and terminal | Efficient lists, breadcrumbs and clear selection; opaque document/console | N19, N22.3-N22.4, N30 |
| Settings and control center | Sidebar, dense aligned controls, small glass navigation layer | N29.3, N29.5 |
| Notifications | Readable bounded items, quiet urgency, dismissal and history | N21.4, N29.3 |
| Permissions and secrets | Trusted opaque surfaces with exact requesting app and scope | N15, N22, N29.3 |
| PooleGlyph and PDC tools | Inspectable matrices, units, provenance and explicit result states | N31-N35, N29.5 |
| Installer and update | Clear target identity, durable progress, error recovery over ornament | N23.3-N23.5 |
| Recovery and diagnostics | Same type/color roles; independent solid rendering and serial path | N6, N23.5 |
| Native applications | Shared semantic controls, tokens and accessibility tree | N29.5, N30 |

Every control needs default, hover, focused, pressed, selected, disabled, busy,
error, and disconnected states where meaningful. Focus must not move or disappear
when transparency changes. Use icons for tools, swatches for colors, segments for
modes, toggles for binary values, steppers/inputs for quantities, menus for choices,
and tabs for views. Do not invent unlabeled gestures or icon-only destructive
decisions. Use a licensed established icon family, with provenance, when the
toolkit is implemented; do not rasterize the entire desktop into a mockup.

## Accessibility And Performance Gates

The W3C thresholds are adopted as design test targets for native UI, not as a
claim of web or OS certification: at least 4.5:1 for ordinary text, 3:1 for large
text and meaningful non-text controls, and a 7:1 high-contrast text target.
Measure worst-case backgrounds and every state; blur is not a contrast guarantee.
Keyboard-only operation, visible unobscured focus, screen-reader semantics,
200 percent text scaling, magnification, RTL, localization, reduced motion and
transparency all require native implementation and tests. [WCAG 2.2](https://www.w3.org/TR/WCAG22/)

Provisional budgets at a declared 1080p software-composition profile:
60 Hz presentation target, 16.67 ms total frame budget, at most 3 ms for material
effects, two cached backdrop layers, 24 logical-pixel blur radius maximum, and
64 MiB material-cache ceiling. Treat these as unmeasured starting hypotheses.
Record p50/p95/p99, missed frames, startup latency, memory, CPU/GPU time, power,
thermal state and idle redraws. Idle surfaces must not animate continuously.
If budgets are exceeded, reduce effect quality or select solid surfaces while
preserving content and interaction. Do not silently lower input responsiveness.

UEFI has a different budget: the whole demo executable stays below the existing
256 KiB limit, assets are fixed-size compile-time arrays, rendering allocates no
heap memory, and the bitmap needs no guest-side PNG decoder. Tests cover the
minimum 320x200 through ultrawide host renderings and both RGB/BGR packing.
Only the actual 1280x800 QEMU display is guest-qualified in this cycle.

## Implementation Register

All rows inherit `FLAG-NATIVE-UI-001` and `ADD-UI-001`; none close N29 or N39.
The optional demo is subordinate to the chronological kernel work, whose next
move remains `N12-CONCURRENCY-RECLAMATION-001`.

| Item | State | Acceptance evidence still required |
|---|---|---|
| PG-01: optical P and demo wordmark | Implemented, demo only | Production intake and target display qualification |
| PG-02: UEFI static rendering | Two fresh QEMU optical boots pass | Physical GOP modes, final framebuffer remap/revocation |
| PG-03: semantic design tokens | Specified | Versioned toolkit consumption and migration tests |
| PG-04: material renderer | Open, N27/N29.2/N29.6 | Software reference, bounded sampling, GPU differential and crash recovery |
| PG-05: window and control states | Open, N29.3/N29.5 | Functional native workflows and input/focus tests |
| PG-06: accessibility preferences | Open, N29.7 | Persistent preferences, native semantics, manual assistive-tech testing |
| PG-07: animated boot | Open, N29.8 | Early-userspace service, stage binding, cancellation, static fallback |
| PG-08: trusted and recovery UI | Open, N15/N22/N23/N29 | Anti-spoofing, privacy boundaries, independent recovery renderer |
| PG-09: fonts and icons | Partial demo provenance only | Production font/icon selection, shaping, licenses and update ownership |
| PG-10: visual acceptance | Open, N36/N38 | Exact-profile capture matrix, layout/contrast/focus/motion/performance evidence |

Required future capture matrix: 640x480 recovery; 1280x800; 1920x1080;
2560x1440; ultrawide; rotated portrait; 100/150/200 percent scale; light/dark;
high contrast; reduced transparency/motion; long localized and RTL labels;
software/GPU failure; low memory; detached display; locked and recovery sessions.
Screenshots supplement, never replace, interaction and accessibility evidence.

## Provenance And Research

`demos/native_iso/boot/assets/pooleglass-emblem.png` is original AI-generated
PooleOS artwork, created using the built-in image-generation tool and refined
once. The final prompt is retained in `demos/native_iso/boot/assets/ARTWORK.md`.
`encoding.json` records source and compact asset hashes. The bitmap is
pre-rendered glass; no physical-material simulation or production font engine is
claimed. Generated branding still needs owner visual acceptance and normal
trademark/originality review before production promotion.

Apple's material guidance is a design reference for separating control layers
from content and adapting transparency, not a dependency or permission to copy
its proprietary implementation. PooleOS does not run SwiftUI or use Apple system
materials. [Apple materials guidance](https://developer.apple.com/design/human-interface-guidelines/materials)

The optical ISO uses an EFI no-emulation El Torito entry, not a legacy BIOS
loader or hybrid USB partition layout. This choice is based on the UEFI optical
media definition. [UEFI media access](https://uefi.org/specs/UEFI/2.10/13_Protocols_Media_Access.html)
