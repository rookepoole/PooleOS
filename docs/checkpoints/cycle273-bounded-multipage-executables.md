# Cycle 273: Bounded Multipage Executables

Date: 2026-10-13. Native loader progress, not a usable ISO or production release.
Owner direction remains usable native user space first, robust microkernel after.
Branch `agent/userspace-integration-iso`; PR #81 remains draft.

## Implemented

Program and InitialImage now admit one through four code pages, up to 16384 bytes.
Construction retains one whole PMM code allocation, copies and reads back every
word across page boundaries, zeroes unused bytes, and maps each exact offset RX.
The complete four-table admission audit rejects holes, extra leaves, altered
permissions, wrong offsets, physical aliases and invalid range/guard geometry.
ImageAdmission carries the exclusive code end through syscall/timer return checks.
The existing lower return bound remains the entry point; independently built
programs still require entry offset zero. This is not an arbitrary ELF loader.

The native physical-memory adapter accepts the bounded code shape without relaxing
stack/table ownership. Larger programs live at user-window offset 16 pages, above
the unchanged stack and guards. One-page placement and PSTART1 arguments remain
compatible. User window, mapping/frame limits, PMM records, syscall ABI and stack
sizes are unchanged. Retirement scrubs every page and frees the whole allocation
only after its last mapping is removed. Never-exposed construction failures retain
their complete cleanup owner; general post-execution cleanup retry is still open.

The independent linker/extractor cap increased only after the core loader tests
passed. One RX segment, no writable data/imports/relocations, and local relative
object relocations remain mandatory. PooleMultiSupervisor is a diagnostic binary:
its startup jumps through offsets 0,4096,8192,12288, counts the visited pages, and
runs the existing supervisor policy from the fourth page. It is not a useful app.

## Verification

- 512 kernel tests pass in debug and release, including nine new tests for full
  code-range readback, every code-leaf bit, wrong backing offsets/permissions,
  overflow, stack guards, later-page write/readback failures, retained cleanup,
  page rounding, native access shape, and syscall/timer return bounds.
- 60 user-runtime tests pass per profile. Eight independently compiled ELF/code
  pairs reproduce exactly; the earlier seven remain byte-identical. The new
  executable contains 13392 code bytes, requiring four pages.
- Six fresh QEMU/OVMF guests pass under unchanged 120-second per-guest bounds:
  two normal and one denied-owner run for both four-page and legacy supervisors.
  Each profile's two independently built normal kernels are identical.
- Four-page normal sessions execute two 257-call child lifetimes, consume deferred
  completion, run the 8193-call survivor, and reclaim 55 pages/27 scrubbed data
  pages. Denied ownership executes no child and reclaims 42/21. Zero objects remain.
  Legacy sessions retain their 52/24 and 39/18 totals. Normal dispatches154/CR3
  writes308; denied130/260. These prove normal multipage retirement, not injected
  native multipage fault-cleanup recovery.
- All four normal kernel builds use111/208 pages; both denied builds109. Two fresh
  default builds agree exactly at208/208 pages, 120 RELRO padding bytes and36
  guarded stack pages. One emitted a diagnostic link map; the other used unchanged
  product flags. Default boot and shell interaction were not replayed this cycle.
- 23 initial focused Python tests,260 broader focused metadata/oracle tests, and
  Rust formatting pass. Exact-index publication checks run separately at closeout.
  Counts overlap and are not a canonical qualification pass. Current native
  bindings cover856 inputs. Metadata log SHA256:
  `B71247531CC8121F6A677D409F4FFEDA11F5175B188E1F9B1D94D5EDB7768D46`.

Public receipt: `runs/native-multipage-program-readiness.json`.
SHA256: `0EB85EB64094DACA9AC8258F90D1F4BDD016E728FBE27681401DB5B09C218DB6`.
Conventional pinned Rust compilation/assembly/linking, not PooleGlyph generation.
Raw failures, builds, logs and media remain in ignored outputs or verified evidence
archives. No physical-media, firmware, key, tag or release operation was performed.

## Failures And Repair

Two host test compiles failed: three IPC fixtures lacked the new code-end field,
then a new test referenced the timer constant in the wrong module. Both fixtures
were corrected; no production interface was weakened.

The first default link exceeded208 pages. A retained link map measured209 pages,
including74136 RELRO bytes. Admission-only arithmetic repair was insufficient.
Explicit checked address/copy/retirement calculations now return errors instead
of adding arithmetic panic paths. Final RELRO use73608 bytes and text624062 bytes
fit the original limit. The guard, compiler settings and linker capacity were not
raised. All failed captures and their hashes are retained in the public receipt.
Default capacity is still fully used and must be reviewed before further growth.

## Invariants And Scope

| Invariant | Verification | Result |
| --- | --- | --- |
| Exact whole-allocation ownership and offsets | stale/shape/offset/readback tests | host pass |
| Bounded RX code, unchanged RW stack and guards | range/leaf mutation/alias tests | host pass |
| Every copied page and failed construction remain owned | later-page failure and scrub retry tests | host pass |
| Actual execution and return on later pages | source/ELF-bound four-page supervisor guests | native pass |
| Every code page retires; legacy programs remain valid | six guests and exact PMM reductions | bounded native pass |
| No bootstrap capacity expansion | failing link retained; two final 208-page builds | pass, no spare pages |
| No ISO/general-loader/production promotion | scoped receipt, roadmap and publication checks | not claimed |

Rejected: extractor-only relaxation, per-page forged handles, widening bootstrap
capacity to hide growth, or substituting kernel-resident shell commands. The
selected implementation extends existing owned construction and admission.

## Next Move And Remaining Gaps

Integrate real shell start/stop/status with generation-bound process capabilities
and completion. Preserve ownership across failed post-execution cleanup, then
exercise native stop/fault completion and owner-death cases. Add read-only bundled
files and two separately launched useful applications, followed by optical ISO
packaging and sustained interactive acceptance. Do not count this diagnostic or
existing shell builtins as those apps. Keep executable trust, writable data/heap,
local input/display, efficient idle, full call-chain stack proof, PMM limits and
default image headroom explicit. Full microkernel/PDC/PooleGlyph/PooleGlass work
continues after the usable integration milestone.

USI-3/4 remain partial; USI-5 not started. No phase/flag closes:40 phases,301
subphases,8996 requirements,59 additions,98 flags (43 open),20 gap groups.
1415 Python tests and654 architecture bindings are inventories, not full-suite
passes. The three tracked canonical readiness failures and exact-candidate full
gate remain unresolved before main. Historical receipts are not rewritten.

Master checklist and live PooleGlyph Phase65 checkpoint/archive/report were
rechecked unchanged. Phase66 Core IR metadata-boundary audit remains next.
Metadata declarations confer no kernel execution or capability authority.
