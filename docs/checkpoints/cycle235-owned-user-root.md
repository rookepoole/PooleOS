# Cycle 235: Owned User Root And Entry Stack

Date: 2026-10-07. Move: `N13-USER-ENTRY-LIVE-001`, USI-1 / N9/N12/N13.3.
Status: inactive preparation host checks pass; live integration remains pending.

## Entry And Contract

The previous turn made progress: Cycle 234 implemented PKUSER1 and published
commit `f2aedd750cecce8dfd6e75bf5f306d289c9d5576` in draft PR #81. The goal is
active again. The owner-directed usable native user-space ISO remains the next
milestone, followed by complete N0-N39 microkernel development. No boot redesign.
Main remains the separately qualified Cycle 233 baseline, not this development.

The locked checklist hash/counts and PooleGlyph Phase 65 checkpoint were
rechecked. PooleGlyph archive SHA-256 remains
`F3CCEB701CF76274D9464A0958BF6106888FB34F3C0BFBD55DE4ACE03C427ABC`;
the owner's dirty report remains untouched at
`F75E4836FAA9DDD59BA62648FE9542415F2119B659A583FB3F5959F2F5CAE87B`.
Phase 66, production owner custody and all other release gaps remain open.

## Kernel Implementation

`user_entry/prepared.rs` adds PKUSER2, an owning inactive preparation object:

- consumes the existing PKVM1 space and retains its actual tables/data frames,
  a four-page entry stack, and three private supervisor stack-table pages;
- checks the boot-retained PKMAP2 kernel subtree, image entry permissions, full
  retained stack/handoff mappings, guards, physical width and physical overlap;
- inherits only supervisor root slot 511, never firmware identity mappings;
- maps the private RW/NX entry stack at root slot 256, with both adjacent guards
  absent and no other entries in that subtree;
- replays user and supervisor admission after writes and readback;
- rejects every unsupported bootstrap extension, including metadata/MMIO and
  temporary-map entries, until a live adapter supplies an explicit contract;
- prevents copied allocation handles from freeing prepared resources, exposes
  no mutable address space or retention tokens, and retains pages on owner loss;
- detaches and verifies cleanup before ending retention. Failed writes, readback,
  finish or cleanup keep a retryable owning object, never a passing admission.

The existing PMM retention check is factored for reuse before physical cleanup,
so a different allocator cannot authorize writes using matching copied handles.
The implementation is safe Rust and allocation-free outside the host test fake.

## Invariants And Verification

| Invariant | Evidence / Boundary |
| --- | --- |
| U1: no live authority from a snapshot | No CR3/GDT/TSS/IRETQ path or active lifecycle API added |
| U2: only the declared supervisor and stack roots | Exact root/subtree readback, guards, unsupported-entry and bit-mutation tests |
| U3: no premature physical reuse | Atomic PMM retention, copied-handle rejection, dropped-owner and foreign-manager tests |
| U4: failures retain ownership | Every preparation read/write failure, silent write corruption, failed detach/finish, verified retry |
| U5: user mapping identity survives preparation | Full PKUSER1 replay; corruption at finish rejects and remains quarantined |
| U6: scope and history remain honest | Frozen Cycle 234 receipt; fresh source-bound Cycle 235 receipt; zero guest/ISO claims |

The first full host run had 269 passes and three failures. Two exposed missing
page acquisition during cleanup after partial construction. Cleanup now prepares
each still-owned table page before zeroing it. The third was a fixture quota
too small for its additional wrong-layout allocation; only that test fixture's
quota changed. Original log: `outputs/cycle235-user-entry-first/kernel_host_debug.log`.
The corrected run passed 272 tests; final replay also adds supervisor re-audit
and two compile-fail ownership checks. Earlier results are not relabeled.

Final commands/results are retained in `runs/native-user-entry-readiness.json`.
Final rerun: 272/272 kernel host tests, 26/26 repeated optimized user-entry tests,
two compile-fail ownership tests, format and freestanding compilation pass.
Receipt SHA-256:
`967233D0AFDAD3B8485A93EE74AB759E2BC6E2E1EEA6690499F8DF97E5B22EFD`.
The first 83-test metadata run had one stale status-string expectation and 82
passes. Its failed log is retained at SHA-256
`58B74451D885355953C1583C6144627899EB34E105050BFADA77DE7092FBAE6C`.
The assertion is updated to the measured inactive-preparation status; no native
admission validator or production gate is relaxed.
Corrected metadata regression: 83/83 pass, zero skips/failures/errors, 68.951
seconds. Log SHA-256
`00FB0B10C6609DB7628D6F9612E7D1EC394BE869B3B47600650AB5637F825914`.
Source and owner-report snapshots remain unchanged through both metadata runs.
This is host-executed memory preparation and freestanding compilation, not CPU
privilege testing. Fresh guest execution and exact-candidate qualification are
still required before merge. The 25 stale native component admissions remain
failures, not inherited passes. Main, prior guest receipts and the demo ISO stay
unchanged.

## Next And Non-Claims

The prepared root cannot yet be activated. The live adapter must hold and audit
boot mappings through the transition, reconcile the bootstrap temporary mapping
mechanism with the strict snapshot, support needed timer/MMIO lifetimes, ensure
scrubbed executable/stack contents, and transfer ownership into a CPU-exposed
lifecycle with retirement-based teardown. Inactive abort cannot be reused after
CR3 activation. Then install descriptors/TSS/entry stacks, initialize supported
architectural state, and prove bounded actual CPL3 entry, return, timer recovery
and contained faults in QEMU before shell work.

`N13-USER-ENTRY-LIVE-001` stays selected and open. Existing
`FLAG-N13-USERSPACE-ISO-001` tracks these prerequisites. No phase, checklist item,
production flag, syscall, capability, IPC, service, shell, ISO, hardware, signing,
release or production gate is claimed complete. All 8,996 items and 59 research
additions remain mapped; mapping is not completion.

Architecture reference: [Intel system programming manual, paging protection](https://cdrdv2-public.intel.com/874249/253668-090-sdm-vol-3a.pdf).
The hardware reference informs the permission contract; it does not validate this implementation.
