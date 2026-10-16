# Cycle288: Native User-Space Optical Preview

Date: 2026-10-13. Previous goal turn: progress, Cycle287 committed/pushed at
763ba1b. Owner priority is a usable native user-space ISO, followed by the full
robust microkernel. This cycle delivers an unsigned, virtual-only serial preview.

## Implementation And Verification

`runtime/native_userspace_iso.py` authors deterministic El Torito media with the
existing hash-pinned pycdlib. It extracts the canonical native ESP, adjusts only
both FAT hidden-sector fields for optical LBA zero, and independently decodes
ISO/FAT structures and every inner file against the original disk. The historical
demo's fixed kernel binding and production architecture policy are unchanged.

Each ISO is authored twice with equal bytes. The two normal ISO variants are
also equal. Image size66109440; SHA256
`1E4752E3D45972CEA7711AF443C15EFC22CD82558F1A975B6B676ADF6C7841AE`.
The development layout has exactly twelve native EFI files. The production
scanner still fails four future release paths. That failure is recorded, not
suppressed as production acceptance; any additional structural/path/content
violation rejects the preview. A forbidden-content negative test confirms this.

Three application optical guests pass: two normal and one stale Numbers file
grant. All557 input bytes and native responses are exact, including changed-file
work, repeated jobs, contained fault, surviving peer, two restart generations and
clean exit. Each holds all six roles live from dispatch704 through4800, with65
consecutive samples and strictly advancing call/timer counters for every role.
This is a bounded scheduling window, not a wall-time performance benchmark.

A fresh ordinary PooleBoot optical guest denies unsigned transfer as before.
The launcher passes a fourth strict application session, including a4096-dispatch
window, then its actual Terminal adapter passes a separate557-key scenario with
1897 response bytes. Keys were injected into the adapter; no human keyboard or
visible host-window test is claimed. Six optical boots total, on one host.

Actual images are read-only, networking is off, OVMF variables are fresh, and
serial/debugcon observations match at a paused snapshot. The normal launcher
uses a host COM2 terminal, not SDL or native graphics. Input/output/log/time bounds,
escape sanitization and process cleanup are enforced. Manual sessions cannot
claim the fixed qualification scenario; their summaries explicitly say so.

No Rust source changed. Fresh normal/bad application kernels are directly
byte-equal to Cycle287. Both PooleBoot profiles reproduce in two clean builds;
eight boot host tests pass per profile. Twenty prior user program pairs retain
exact source binding. Kernel and user host suites were not rerun. The focused
Python suite passes37 tests. Full canonical qualification remains pending.

Public evidence: `runs/native-userspace-iso-readiness.json`,1622725 bytes,
SHA256 `BEE1CDEF65E2B3E3983CE1D981DDA91BB69EDF45208AF1A5D160D35832F545EB`.
It binds931 execution inputs, raw optical/launcher evidence, retained failure
captures, the previous immutable receipt and exact source delta.

## Failures And Retention

The initial synthetic fixture omitted required builder arguments; corrected
canonical test inputs pass. The first optical build failed the production layout
check, leading to the explicit development-only check described above. The first
live optical attempt reached PooleBoot but rejected OVMF's DVD-ROM prelude because
only disk-profile tokens were recognized. Two exact tokens and every-prefix tests
fix capture while leaving arbitrary text rejected. No guest timeout was extended.

The final four-case optical capture passed in237.484 seconds, including builds;
each application guest retained its original240-second limit and ordinary denial
its45-second limit. Launcher self-test passed in59.859 seconds; actual terminal
adapter test in41.938 seconds. The latter uses the manual900-second session bound.
All captures preserved source and owner-report hashes.

Five old/failed trees,5851 files and1948076969 bytes, were independently size/hash
verified at both endpoints before exact workspace copies were removed. Current
passing products, shared host cache, owner temps and PooleGlyph report remain.

## Next Move And Gaps

Resume shell-triggered waiting cancellation, then generalized races/stress,
supervision, exhausted-owner recovery, efficient idle, job interruption and full
stack bounds. Keep final release layout and portable preview packaging open.
Local display/input, drivers, persistence, networking, PooleGlyph/PDC, accessible
PooleGlass and all N0-N39 production/signing gates remain. Historical claimed,
deferred, exhausted and default-kernel profiles were not freshly replayed.

No production phase or flag closes; no main merge, tag, signature or release.
40 phases,301 subphases,8996 requirements,59 additions,98 flags/43 open and20 gap
groups remain. Live PooleGlyph is stillPhase65, withPhase66 Core IR audit next.
Master checklist, Phase65 archive and conformance-report hashes are unchanged.
See [launch instructions](../native-userspace-preview.md).

The first327-test metadata replay failed one stale schema count (757 instead of
764 architecture bindings). Both minimum/maximum counts now require exactly764;
the repaired replay passes327 tests in83.987 seconds (85.125 with capture).
Log SHA256 `6CF50A325B220AFD2EDDE74E166DEC57D79C5C74996722D21C33253E7E08ADD5`.
The failed capture remains recorded in the roadmap. Inventory is1482 Python tests,
not a full-suite run. Launcher LF checkout bytes are explicitly preserved like
the older demo launcher. Final staged artifact/evidence checks follow closeout.

The first final replay passed55 tests but the publication scan blocked the new
receipt because its exact path was not allowlisted. Add only the sanitized public
receipt; explicit raw/private variants and secret/user-path rejection tests remain.
The failed scan/capture is retained; no push occurs before the repaired scan passes.
