# Cycle 218: Terminal Capture and CPU Replay

Status date: 2026-10-04. Pre-production; single-host bounded evidence.

## Scope and Repair

`N7-TRAP-001` advances N7.5/N7.6 and dependent N7.1/N7.3/N7.4, with
N5 evidence replay and N36 under existing `ADD-N36-RECEIPT-COVERAGE-001`.
The intake incorrectly listed N7.2 instead of N7.6; no exact-target errata
qualification occurred. Native boot and kernel source bytes are unchanged.

The first two returning-trap boots produced equal execution markers but unequal
screenshots. The qualifier removed those original frames, so the precise differing
pixels cannot be proved. A six-boot diagnostic rerun passed and retained its raw
frames locally. These eight initial runs are not final evidence.

Inspection found `_execute_once` captured at PooleBoot's `FRAME READY` marker
while PooleKernel could subsequently paint its banner. A deterministic nine-test
harness reproduced four failures with that ordering. Capture now occurs only
after the completion marker and successful marker/transcript validation. No new
delay, frame comparison relaxation, guest change or validator bypass was added.
All nine tests pass, including timeout, panic, early exit, missing/invalid frames,
nonzero QEMU exit and cleanup cases.

Retained early image SHA-256:
`E9D4CFD48C23DBA760AED5B2049B39DCA49A0D172F680D570082EB0680FDFDBD`.
Final 1280x800 trap image SHA-256:
`6AA5C90B92B580D07C11397FB89D44E2EBD090C04D526AC3E9F5D37A7B355B58`.
Their changed-pixel bounding box is `(0, 0, 299, 23)`, the kernel banner.
This supports the stage distinction, not attribution of the lost pair.

## Fresh Execution

| Profile | Receipt SHA-256 | Final Boots | Controls |
| --- | --- | ---: | ---: |
| Kernel load | `CD0F9CFBA4472AE5F6BB98EE20D244447A4E50C276C39E9D81581132989C4B68` | 2 | 155 |
| PooleBoot | `AE2223ED615B076835A28BCD003618B2E89213B4A4E2DB8BA10D0D4394F4EBB9` | 2 | 155 |
| Kernel transfer | `B0B3AE877F3EE222FB19E50CD2891A955B8C9B1E3A3E42267FE0A15092D9D1B2` | 2 | 58 |
| Traps | `0437D9C2185674D5A5A7F084F14EFE662489969EA7AB77078B701E2FFD371A4C` | 6 | 51 |
| CPU policy | `588DD2BCA4C19D48C1E564FD075830F2D8A8DE67C764CB26080CD458A9BCB1E0` | 2 | 41 |
| Xstate policy | `DAEC34625644276E711EBAE5854F303FAC2770651AD5681D2A59A302D9ACFF75` | 2 | 43 |
| Xstate exceptions | `616936D78BA36C437C4E20BDE5FE8E7D45C059E90F915D2F2520D934AB058FD6` | 2 | 43 |
| Privilege/MSR policy | `634265F8626719A9707355132EE4D72E9BD01979DDFB17533139E932CDE01C93` | 2 | 47 |

All **20 final virtual boots pass**: fourteen CPU boots with 225 controls and
six boot-chain runs with 368 controls. Two exception runs use WHPX; one separate
expected TCG limitation probe is not counted as a passing exception run. Each
exception run records three deliveries, two recoveries and one terminal test-only
#NM rejection. These bounded profiles do not prove general user exception delivery,
AVX support, independent builders or physical-hardware qualification.

The 149-page kernel remains
`FD6C2A0C709957B9EDFFC0647D534E060ED68215C075F07D70AB2AEBCA6C81D1`,
with 1,326 relocations. Entry receipt
`1B5A40C248B02809CFEA397D058973DFD43DE5B85468BA31BD368EE3D8ED7CC7`
and core receipt
`8AA5643002A3FBE416C1B40ECA0BD3D1DFAE7785E500ACBD06292FFAFFAB9DCB`
are unchanged. Each CPU receipt embeds that exact validated entry. The aggregate
trap gate initially rejected obsolete image pins; measured replacement admits
the identical fresh guest evidence.

## Regression and Failures

Focused regression: **64/64 PASS**, zero skips, 182.617s (runner183.500s), log
`D0F982CB117B90DD22986C1F97A68A7652DFFEF1357C7278852CD1C06AB9C546`.
It exercises 3,398 corrupted control records and 371 corrupted run-evidence cases
through runtime and aggregate admission; 33 independent identity/promotion cases,
80 malformed nested-build cases and the nine capture tests also pass. Validator
bypass is limited to isolated negative pin tests, never real admission. Counts
overlap and are not a full canonical suite.

- Initial paired-frame failure: 98.141s, log `FF72BC4F0ECA5B1149FAA1E2BCD625A9ACA0B3DB6EC3BFF78748A2C4CA2C3390`.
- Diagnostic pre-repair pass, not admitted: 107.141s, log `A7D909C2B3CCFF4B54B6D332F6507A8FAC16CD007F7A832C3C16D328A4486BB4`.
- Before-repair capture suite: 5/9 pass, log `72E043DE76FBEE53F42B70EE3481FA38904E1E8EA768A047D1AEAC2098350983`.
- Corrected capture suite: 9/9 pass, log `5FAA431992507D7A26725EE9425F7A31F9FC82D585A4E78F0FF5672DA043278A`.

Initial metadata regression: 60/65 pass, five failures from obsolete current-CPU
receipt/projection expectations, 28.123s (runner28.922s), log
`068A764B7EB518E08C2501B009E844ABDDB26A12E54710EC1055D972BCCA56FA`.
Corrected metadata: **65/65 PASS**, zero skips, 34.444s (runner35.234s), log
`D0387F4AFA5C258580A31CC91F56550A53875B1CBBB30A7F82F1359EE5412E83`.
Historical identities and unfinished-profile rejection checks remain intact.

Initial conservation passes: 24 archived parent records, 371 architecture bindings,
1135 discovered tests, unchanged prior checkpoints and phase/flag statuses, receipt
`1242B163B215B70567057B00DFF53EF9AF9124E3D4FB3BA4C30C71A85DBEDA5C`.
Final combined regression, conservation, staged publication and remote verification
are recorded in closeout logs and the PR after these tracked documentation edits.
Earlier aggregate passes are not inherited after source changes.

## Remaining Work

Actual selected readiness is **13/27**, up from 8/27. Fourteen memory, interrupt,
SMP, scheduler, atomic and lock profiles need current-image evidence. Seventeen
SMP-preemption control groups and recorded admission remain open. Shared-helper
transitive-binding review stays under the existing N36 flag; direct binding is
not a complete dependency audit.

All 24 parent progress records and prior checkpoints remain historical evidence.
No phase or flag closes: 94 flags, 39 open. The locked checklist remains 10,512
lines, 8,996 requirements and 171 sections. PooleGlyph Phase65 remains newest;
manifest/ZIP hashes and the owner's changed conformance report are preserved.
No language/ABI/compatibility change or migration occurs; Phase66 remains unqualified.

The demo ISO is unchanged. No main merge, release, signing, firmware change,
physical-media write or production promotion follows. Full canonical/Doctor/
release/publication and configured GitHub/review gates precede main merge;
cloud branch backup is separate.

Next: **N9-PMM-ACPI-CONSUMER-001**, then memory/IRQ/SMP and scheduler replay,
remaining SMP-preemption admission/controls, atomics/locks and full exact-candidate
qualification on unchanged kernel216.
