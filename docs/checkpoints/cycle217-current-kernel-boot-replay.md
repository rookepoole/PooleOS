# Cycle 217: Current-Kernel Boot Replay

Status date: 2026-10-04. Pre-production; bounded single-host evidence.

## Scope

`N5-SYMBOLS-SEMANTICS-001`, N5.6/N5.9 and N36, under existing
`ADD-BOOT-007` and `ADD-N36-RECEIPT-COVERAGE-001`. Cycle 216 changed the
kernel and left 24 of 27 selected profiles pending. This cycle reconstructs
symbols and dependent artifacts and replays six boot-chain profiles against
the exact new kernel. No production kernel implementation changed.

The linked image was independently canonicalized and loaded, then compared
with the validated entry receipt. PSYM1 image bounds, public symbol addresses,
debug/build/manifest hashes and PPOL1 vectors now bind those measured bytes.
The native symbol unit test rejects the old entry address. The native PKMAP2
host probe now describes the measured 149-page image; the 192-page reservation
and before-write overflow checks are unchanged. Geometry tests retain the
148-, 149-, 192- and 193-page boundary cases.

## Executed Evidence

All six fresh QEMU/OVMF boots pass: two loader boots, two PooleBoot boots and
two kernel entries. Kernel entry reaches the required unsigned-development
denial halt after revalidating all nine retained files. Authority grants,
authorized actions, state writes and firmware calls after ExitBootServices
remain zero. Virtual media are ordinary read-only files with fresh variable
stores. These are not physical boots, an interactive desktop or production trust.

| Profile | Receipt SHA-256 | Guest Boots | Rejection Controls |
| --- | --- | ---: | ---: |
| Symbols | `E14EFC2D988192967FA21737519A310A6D987AA198E584672CF292B3B50A7311` | 0 | 158 |
| Policy | `EA3A12B78EB5A9B4A5BC7863DF962E97070213983224F670F9D1B3CE215057A4` | 0 | 116 |
| Kernel load | `A1A03D71AADF381FFE34217F74C3BFF583DBFF9EF9EF4FA41CED21EDC9BB0021` | 2 | 155 |
| PooleBoot | `84417647DFCFD04765EE8F0C11BA66538E8DF7A8E58535E2EED9C010317EB0D4` | 2 | 155 |
| Kernel revalidation | `8D35EAC9C8B39857ADC6A2B9596F698D628219996FF4C531176252930A8EC88E` | 0 | 36 |
| Kernel transfer | `B564B4459C810A558DCC55939C674947D771DFB519202D93BE8451D68B749302` | 2 | 58 |

Qualifiers pass 4 symbol, 6 policy, 332 loader, 8 PooleBoot and 246 kernel
host tests in their respective scopes. Symbols exercise 16,384 parser and
16,384 lookup differential cases; policy and revalidation each exercise
32,768 cases. Two clean symbol builds match. Repeated builds are on one host,
not independent-builder proof. Counts overlap and are not summed as distinct tests.

Focused regression passes **97/97**, zero skips, in 40.816 seconds; log SHA-256
`2E2A8BCEAD885B6EE40E0E473D8A2F068830796DCADADA2F30C1A9BF8778014A`.
The previously failing live-transfer positive now passes without exclusion.
The suite includes 650 corrupted symbol receipts rejected by runtime and the
actual aggregate gate, 30 independent artifact/trust pin rejection cases,
16 map tests, host-tool provenance and output-preservation checks. Component
validators are bypassed only inside the independent negative gate tests, never
for admission. Measured gate pins are checked against freshly reconstructed
real-image artifact bytes, not against synthetic golden-kernel data.

## Exact Identity

- Build ID: `PKBUILD1-CYCLE216-N12-SMP-TXN-V1-00000000001`.
- Canonical kernel, 538,264 bytes: `FD6C2A0C709957B9EDFFC0647D534E060ED68215C075F07D70AB2AEBCA6C81D1`.
- Linked kernel, 7,158,864 bytes: `5E40AB31AFB4BCE79BEDB32D7B66D64D957B42CA915B2B70D2F15049F90B7D91`.
- Loaded image, 610,304 bytes: `5D660D084136430C0D152EAAF4D29D5704E9B974F6679205BEBAB54F24687967`.
- Entry receipt, unchanged: `1B5A40C248B02809CFEA397D058973DFD43DE5B85468BA31BD368EE3D8ED7CC7`.
- Core receipt, unchanged: `8AA5643002A3FBE416C1B40ECA0BD3D1DFAE7785E500ACBD06292FFAFFAB9DCB`.
- Six-artifact inner set, 8,761 bytes: `AE7180A6C8126B2C2AAA119C24C8B53451E41EB2BF8DD0E259EB0DB947264C84`.
- Trust policy: `6691BF1BE2B76D48EB8D934CB11F113FBDC450038FDDC8A252F982A5BE5306AF`.
- Trust state: `8B93EDE9F95AE1F9AF8379B386982B8ECB81F124A38B10171717EBEF84FA0EA0`.
- Retained manifest, 2,615 bytes: `4AE6C6A9AEAF6EE9A27951BCC236756B441C03A82E2B9C1DA595A08BA6A3E76A`.

The nine retained files total 11,952 bytes. The canonical leaf fingerprint is
`82B27FBAFC6749D4`; the retained probe fingerprint is `EE090139DA9C45A5`.
Kernel source, kernel manifest, entry/core receipts, the locked checklist and
demo ISO are unchanged. PooleGlyph Phase 65 remains the newest checkpoint;
its manifest/ZIP hashes and the owner's dirty conformance report are preserved.
Phase 66 executable Core IR is still unqualified.

## Failure History

The first symbol run failed one of four native host tests because a lookup
still used the old address (7.250 seconds; log
`2F320C2718DF0920FA81936E219A136D2862CDCB967FE6F304261E75CF19CAD2`).
After measured test repair, fresh qualification passed (44.484 seconds; log
`39D622078702BC250B96EFD6CACB9EC04214EB6EEF0062BCFD4BF83419DC0038`).

The first loader run stopped before guest execution when the native probe's
148-page geometry diverged from the independent oracle (113.969 seconds; log
`D7F82960B1721F0C33B80D25454E22F93B5C6898FDAAC8CCB566B3DE25865FEF`).
The corrected probe passed fresh qualification (112.688 seconds; log
`CC1FBEAB3FC5A0A5A76A3484B496A2DE75EABE264CBA137E4D02C21421E34E9B`).
No failed receipt was admitted. Initially stale aggregate artifact pins rejected
the genuine new receipts until independent measurement reconciled them; the
guest evidence was not modified or rerun for that host-only pin correction.

The initial metadata run passed 62/64 tests: two expectations still used the
previous pending-profile count or compared a historical hash with a current
receipt (log `B1893D84AF98B11CCFA7E19154CB3D03C36A3DFE1D1F3D3F4DD15B0B738E4055`).
Corrected metadata passes **64/64**, zero skips, in 33.634 seconds; log
`04E55F077CB6E2AF9C5DD08979A128FC326764EE74BA05AD9C927656D578A751`.
Conservation passes for 369 source bindings, 24 unchanged parent progress
records, 1125 discovered tests, all prior checkpoints and all phase/flag
statuses. Only the six boot receipts are replaced. The final combined suite,
staged publication scan and remote verification are recorded in closeout logs
and the PR; these counts are not a full canonical or production qualification.

## Remaining Gates

Actual selected readiness is **8/27**, with **19** CPU, memory, interrupt,
SMP, scheduler, atomic and lock profiles awaiting the current-image replay.
At least 17 SMP-preemption control groups and recorded admission remain open.
No phase or flag closes; there are 94 flags, 39 open. Full canonical, Doctor,
release, publication and configured GitHub/review gates still precede main merge.
No signed activation, general SMP, independent builder, physical qualification,
release, new ISO or production promotion is claimed. Branch backup is separate.

Next: `N7-TRAP-001`, then CPU and downstream replay on unchanged kernel216;
repair remaining scheduler admission/controls before full merge qualification.
