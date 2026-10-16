# Cycle 234: User-Entry Foundation

Date: 2026-10-07. Status: focused native checks pass; live integration pending.
Selected move: N13.3 / `N13-USER-ENTRY-001`, under existing `ADD-CAP-001` and the
owner-directed user-space integration ISO milestone. No production promotion.

## Entry And Owner Direction

The owner requested a usable native user-space integration ISO and explicitly
retained subsequent development of the complete robust microkernel. This cycle
starts that lane, not a boot-screen redesign or a substitute OS architecture.
The detailed scope, stages, acceptance criteria and follow-on work are in
`docs/native-userspace-integration-iso.md`.

Verified parent: PR #80 merged Cycle 233 into main at
`507782dfde4a554434173fdae7a1b25a170414ce`, tree
`89e0575f31d074a3eb071cc93fda7cdfbd909f35`, after exact-candidate
106/106 canonical checks and 708/708 Doctor checks. The merged tree and all
1,646 tracked GitHub objects were verified. Canonical report hash:
`867A9E802442D124B2CCA6922BDFB04FDA023B43E0CE0F262C38B868D7775650`.
That evidence qualifies the parent, not this new source.

## Implementation

- `native/kernel/src/user_entry.rs`: allocation-free inactive user-image
  admission using the existing PKVM1 address-space and PMM ownership mechanisms.
- Checks exactly four table pages, all 2,048 entries, two owned distinct data
  frames, RX code, RW/NX stack, unmapped adjacent stack guards, no other mappings,
  physical width, owner-side mapping identity, and generation-valid allocations.
- Rejects unsupported page flags, malformed parents, stale/freed/reused frames,
  aliases, pending teardown, access failures and noncanonical/overflowing layout.
- Builds a five-word initial IRETQ frame with fixed user selectors and flags.
  Added descriptor constants are not installed into the live GDT.
- An internal owner-mapping accessor in `virtual_memory.rs` allows independent
  comparison with raw page-table bytes; inspection makes no page-table writes.

## Executed Checks

`runs/native-user-entry-readiness.json` records exact native source hashes and
the retained command/log identities from `tools/qualify_native_user_entry.py`.

| Check | Result |
| --- | --- |
| Initial focused debug run | 14/14 new tests pass |
| First retained qualifier | Formatting fails for the new VM accessor; no behavioral test failed in this attempt |
| Corrected format check | Pass |
| Full kernel host debug suite | 260/260, zero failures/ignored tests |
| Optimized user-entry host suite | 14/14, zero failures/ignored tests; repeats the focused cases |
| Freestanding x86-64 library compilation | Pass |
| Native sources and owner report stable during final qualifier | Pass |
| Fresh guest runs / new ISO | 0 / none |

The focused cases include mutations of every parent/leaf bit, hidden mappings,
guard violations, stale ownership, aliases, and failure at every one of the 2,048
table reads. These are executed Rust host tests, not injected guest CPU faults.
Raw first-attempt failure remains under `outputs/cycle234-user-entry-first`;
passing logs remain under `outputs/cycle234-user-entry-final` and the final
public-receipt rerun under `outputs/cycle234-user-entry-public`.

The first 82-test roadmap/coverage/baseline run has 36 failures and four errors;
the second has eight failures and one error; the third has one stale projection
count assertion. These are retained as metadata/source-admission reconciliation
failures, not passing runs. Their log hashes are respectively
`49D18233955C2D27CB09DA00FEB43EEA6CC530B5D282FCD9307C0EF66F435300`,
`E2271A8313E616540997AC87CF6B7C74FC873B0E8F77FE4C28C7589AC1AD8711`, and
`A18CDF6E62EC49CAF0D453E3A0E9FE90B9E15BA664DD51551C29EC09B7DE0910`.
Historical tests now verify the unchanged receipt hashes separately from actual
current-source admission, including its exact failure diagnostic. Forged receipt
content and a disabled entry validator must fail that projection check. The
native admission functions and production release guards are unchanged.

Corrected metadata regression: **82/82 pass**, zero failures/errors/skips, in
67.934 seconds (68.750 seconds including capture). Log SHA-256
`B151F969732A91C2152EADE786DA970759EA85E0B1C1DCC389B38C688E38A47A`.
Source and owner report remain unchanged during that run. This checks historical
integrity and current non-promotion; it does not turn the 25 stale native
component admissions into passing runtime evidence.

The first indexed publication check failed on the two newly introduced run
receipts because they were not explicitly allowlisted. No upload occurred.
Their public-content review admits only these two exact filenames, retains
private/secret rejection, and removes machine-specific command/log paths.
The qualifier was rerun after fixing Windows newline translation so published
receipt bytes and Git blob bytes agree. Earlier attempt logs remain retained.
Final conservation and publication regression: 27/27 pass in 94.326 seconds,
with source and owner report unchanged. Log SHA-256
`8A62B68FB5B027AE1B7CD2879B8C39B9BD0FCF0D8EFB6F347C555010672F7D53`.

## Current Qualification Boundary

`runs/native-user-entry-gate-projection.json` records a read-only projection:
2/27 retained component admissions still pass; 25 reject the changed native
source. The separate 27-profile static source-closure check still passes and
must not be confused with current kernel execution. Old guest receipts were not
rewritten, relabeled, or newly promoted. Full new-image/guest/candidate qualification
is pending, so this checkpoint is not merge-qualified or production-ready.

No CR3 activation, live GDT change, user-mode execution, syscall, capability, IPC,
shell, driver, application or new ISO is demonstrated. The old ISO is retained
unchanged. Admission is an ownership-locked snapshot, not execution authority;
actual CPU state, kernel-half attachment, stack ownership, and fault containment
must be established before user code executes.

## Progress And Conservation

N13 and N13.3 are partial. USI-1 has host admission only; USI-2 through USI-5 are
not started. `FLAG-N13-USERSPACE-ISO-001` remains open. Existing checklist
requirements already cover this lane: 8,996 items and 59 research additions are
retained. No production phase or existing flag closes; N0-N39 stays authoritative.

PooleGlyph remains Phase 65: checkpoint archive SHA-256
`F3CCEB701CF76274D9464A0958BF6106888FB34F3C0BFBD55DE4ACE03C427ABC`.
Phase 66 remains the promotion boundary. The owner's dirty conformance report
remains untouched at SHA-256
`F75E4836FAA9DDD59BA62648FE9542415F2119B659A583FB3F5959F2F5CAE87B`.
No key, signing, release, firmware, driver-loading or physical-media action.

## Exact Next Move

`N13-USER-ENTRY-LIVE-001`: attach validated supervisor mappings and lifetime-held
kernel-entry stacks, install the development-only user descriptor/entry boundary,
then perform a bounded actual ring-3 entry/return/fault probe in QEMU. Preserve
ordinary trust denial, test forbidden memory/I/O and unsafe return state, and do
not add a user-space shell until the architectural boundary works.
