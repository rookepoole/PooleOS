# Cycle 272: Owned Allocation Page Mappings

Date: 2026-10-13. Progress checkpoint, not a usable ISO or production promotion.
Owner priority remains usable native user space first, complete robust microkernel
afterward. Branch: `agent/userspace-integration-iso`; PR #81 remains draft.

## Implemented

PooleShell code is 3569 bytes, leaving 527 under the current 4096-byte limit. Adding
application lifecycle and files requires a real loader extension. Merely raising
the extractor cap would leave admission, copying and return validation incorrect.

`AddressSpace::map_page` now accepts a checked page offset in an exact live PMM
allocation. Mapping records retain both the complete allocation identity and the
offset. No forged single-page subhandle or independent suballocation is created.
`map` retains its strict one-page contract. Owner-side mapping readback now returns
the offset; legacy InitialImage admission explicitly requires zero offset.

Translation, protection and unmapping reconstruct the exact selected physical
page. Cache policy remains allocation-wide, including pending aliases. All offsets
share one frame binding. Whole-allocation free waits for the final mapping and
acknowledged invalidation; failed PMM free retains the receipt for retry. Released
page accounting includes the entire allocation. Limits remain 8 mappings, 4 frame
bindings and 8 pending invalidations; the production PMM record limit is unchanged.

This is an internal trusted-owner mechanism, not a new syscall or user-controlled
mapping authority. The caller still owns exclusive PMM/mapping access. General
cross-address-space sharing, SMP shootdown and teardown recovery are not added.

## Verification

- 503 kernel tests pass in debug and release; seven new tests cover distinct
  offsets and aliases, reordered receipts, invalid/overflow offsets, stale and
  forged handles, individual W+X denial, physical substitution, after-effect
  rollback, cache mismatch while pending, retained-free retry, and fixed capacity.
- Two independently compiled normal kernels are byte-identical. Two normal native
  boots and one denied-owner boot pass within the original 120-second guest bound.
  These use the existing one-page programs; nonzero-offset native execution is
  explicitly not claimed.
- Each normal guest executes two child lifetimes of 257 calls, reports both terminal
  results after a withheld-completion dispatch, runs the 8193-call survivor and
  frees 52 pages with 24 scrubbed data pages. 154 dispatches, 308 CR3 writes and zero
  remaining objects. Denied-owner control executes no child, cancels the prepared
  image and frees 39 pages with 18 scrubbed data pages; supervisor exits 170.
- Normal kernel 111/208 pages; denied 109. Fresh default build 207, 36 guarded stack
  pages and 24 RELRO padding bytes. The default kernel was not booted; full stack
  bounds are not established. User program artifacts from Cycle 271 were revalidated
  against unchanged source and ELF/code identities, not rebuilt this cycle.
- Current source proof binds 855 native/build/oracle inputs. Rust formatting and
  257 focused Python tests pass. Publication-boundary and exact staged evidence
  are checked separately before branch backup; this is not canonical qualification.
  Eight generated build/media archives were checked member-by-member before local
  copies were removed. Metadata test log SHA256:
  `BE8F2750D854C13B1BBDD47DEE34D370D4BF8BD03BB94A9EB0317F7F694C17A0`.

Public receipt: `runs/native-vm-allocation-pages-readiness.json`.
SHA256: `0D08F4E66B02D2E0F3F69CC0B6C7B5B469FE9D67A465FBEA0AADC851295861F5`.
Raw builds, logs, images and diagnostics remain in ignored cycle272 outputs or
hash-verified evidence archives. No physical media, firmware, keys or releases
were used. Build provenance is ordinary pinned Rust compilation.

## Retained Failure

The first host test compile failed: E0451. Test fixtures used Rust struct-update
syntax on AllocationHandle, whose slot is private. Fixed by copying the existing
test handle and mutating only its public fields. PMM encapsulation was not relaxed.
The failed capture is retained; no native execution occurred from that candidate.
Log SHA256: `61C4E4378E9F170A303AEC6DED3B25E19E683DD2C5077B0AABA3BFEBB054A8DD`.

## Invariants And Scope

| Invariant | Verifier | Result |
| --- | --- | --- |
| Full allocation identity remains authoritative; offsets cannot create owners | stale/forged handle and readback tests | pass, host |
| Physical translation uses the selected offset with checked arithmetic | distinct-page, overflow and substitution tests | pass, host |
| Failed writes leave exact prior mapping/binding state | after-effect rollback tests | pass, host |
| No whole-allocation reuse before all mapping/invalidation obligations finish | alias, reordered receipt and retained-free retry tests | pass, host |
| Existing native lifecycle remains functional | three fresh source-bound PCOMP1 guests | pass, legacy single-page lane |
| No increased capacity or unearned ISO/production claim | fixed-capacity tests, budget inspection and roadmap checks | bounded evidence only |

Rejected alternatives: extractor-only size increase (incorrect admission/copy),
one PMM record per code page (unnecessary record pressure), or kernel-resident
commands (violates the user-space milestone). Selected: staged bounded loader
work atop whole-allocation mappings. This preserves the capability microkernel.

## Exact Next Move

1. Extend Program/InitialImage with a bounded code range and one retained code
   allocation. Preserve the current startup address and both stack guards; decide
   the larger-code virtual placement explicitly. Do not silently widen USER_WINDOW.
2. Copy, zero, read back and admit every RX code page and its exact backing offset.
   Reject holes, extra leaves, physical aliases, writable code and range overflow.
   Carry admitted bounds through syscall and timer-return checks, not just entry.
3. Retire and scrub every code page while freeing the full allocation once. Test
   construction failure at later pages and retain cleanup ownership on errors.
4. Only after those mechanisms pass, increase the ELF extraction bound. Independently
   build and natively execute a program crossing page boundaries, with denial and
   cleanup controls, and replay the existing small-program sessions.
5. Integrate genuine shell start/stop/status, native cancellation/fault completion,
   retained supervisor cleanup, bundled read-only files and two useful separate
   apps. Then build and qualify the interactive optical ISO. Builtins/counters do
   not count as useful separate applications.

USI-3 and USI-4 remain partial; USI-5 not started. FLAG-N13-USERSPACE-ISO-001 remains
open. No phase or flag closes. Existing canonical readiness failures and the full
exact-candidate gate remain pending before main. Full robust microkernel/PDC/
PooleGlyph/PooleGlass work remains mandatory after preview acceptance.

## Owner Input Continuity

Master checklist and live PooleGlyph Phase 65 archive/report hashes were rechecked
and unchanged. Latest checkpoint remains Phase 65; Phase 66 Core IR metadata-boundary
audit is still next. No metadata declaration acquires kernel authority. Checklist
coverage remains 8996 requirements, 40 phases and 301 subphases. Source inventory
increases to 1412 Python tests and 651 architecture bindings, not a full-suite pass.
