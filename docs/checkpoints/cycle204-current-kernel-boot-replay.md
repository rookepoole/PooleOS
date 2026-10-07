# Cycle 204: Current-Kernel Boot Replay

Status date: 2026-09-29. Pre-production, single-host qualification only.

## Scope

`N5-SYMBOLS-SEMANTICS-001`, N5.6/N5.9 and N36, under existing
`ADD-BOOT-007` and `ADD-N36-RECEIPT-COVERAGE-001`. Entry state was
2/27 selected current-source checks after Cycle 203 repaired native SMP
transactions and changed the kernel. This checkpoint requalifies its six
boot-chain profiles without modifying native kernel code or rebinding old boots.

The retained linked kernel was independently reconstructed into its canonical
and loaded forms. Six measured symbol-image pins and the PSYM1/PPOL1 vectors
were updated. Real kernel-derived retained artifacts, rather than the synthetic
golden kernel, supplied the new independent release-gate trust and inner-set pins.

## Evidence

All six fresh QEMU/OVMF boots passed: two loader boots, two PooleBoot boots,
and two kernel transfers. The latter entered kernel203 and reached the expected
unsigned-development denial halt. Authority grants, authorized actions, state
writes and firmware calls after ExitBootServices remained zero. This is not
authenticated production boot, interactive task execution or a new demo ISO.

| Profile | Receipt SHA-256 | Guest boots | Negative controls |
| --- | --- | ---: | ---: |
| Symbols | `C9FF1E5347A831045E46BCF8DCF2CD77D25497D68BD48B177B80162026901C99` | 0 | 158 |
| Policy | `56E724804B70A4B530D7410D651DF1E88773273C501EE65A7E7DF8D4A659B8B5` | 0 | 116 |
| Kernel load | `AC8B3954741AB689BD07B5875949B2437B63664CD47E09E055C04A65E99701B7` | 2 | 155 |
| PooleBoot | `48A507A2059BC400EA5A2A9F37626874A267870BF946A34E3B0069213787CCDE` | 2 | 155 |
| Kernel revalidation | `2A1230B151E1494B3C6C9EFF712A7529194B5F27180A1CE5D882D1B98733450E` | 0 | 36 |
| Kernel transfer | `95AEEF7FF80A960096D8FC236017C9789ACD7B96DF085E73F857EEADB047AB85` | 2 | 58 |

The qualifiers passed 4 symbol, 6 policy, 331 loader, 8 PooleBoot and 246
kernel host tests in their respective scopes. Symbols exercised 16,384 parser
and 16,384 lookup differential cases; policy and revalidation each exercised
32,768 cases. Matching builds are on one host, not independent-builder proof.
Counts overlap and must not be summed as distinct tests or security guarantees.

Focused regression passed **81/81**, zero skips, in 41.688 seconds. Its log
SHA-256 is `141727F1A0BFA8B4DB577BB43FB30FACFF5A12D0FD6238D607F464585EA6400B`.
It includes 650 corrupted symbol receipts rejected by runtime and actual release
gate, output-preservation tests, host-tool provenance, and 20 new independent
aggregate-gate pin rejections. For the latter, component validators are bypassed
only in the negative test, after a genuine positive passes; old identities,
zero digests, null and false must still fail the aggregate's independent pins.
That bypass is not used to admit any receipt or to run qualification.

Combined scoped regression passed **188/188**, zero failures or skips, in
188.969 seconds; log SHA-256
`4441B394B1762FA1D45558FB3A9F764F6D4B9951B8B111FF192AA493E380B5C7`.
It includes the 81-test boot scope, native SMP/deferred debug and optimized
transaction tests, core validation, exact kernel-entry product/receipt
reproduction, independent entry-gate rejection, host provenance, publication,
roadmap, architecture and checklist checks. Source and owner data remained
unchanged during execution. Results were recorded afterward, not treated as
a full canonical suite or as independent-builder reproduction.

Initial roadmap/architecture regression passed 43/43, zero skips, in 18.953
seconds; log `E0AF2B0FE42DA70E69212534DAA81B61D1DD564E0EB22027911774C25A0C44C5`.
Initial conservation passed: 345 exact source bindings, all 19 unchanged
parent-current records archived under historical Cycle 203, all prior historical
records and checkpoint documents preserved, and no phase or flag status changed.
The 1,086 discovered tests are an inventory, not full-suite execution. Counts
overlap. Final metadata and staged publication checks precede commit and push.

## Exact Identity

- Build ID: `PKBUILD1-CYCLE203-N12-SMP-TXN-V1-00000000001`.
- Canonical kernel, 530,072 bytes: `A943DCB6E41A27F952868F05ED2B3523B47D9D7A7B5DB909EE385205F7CA3B31`.
- Linked kernel, 7,046,784 bytes: `557687A9F39EEECFFD839A8619D696CEBB4E391B229778162725752C72B4D9AA`.
- Loaded image, 602,112 bytes: `F4698CB6E7DE51E07041410A274E3BE08886D09F51E681290E743E1361858FFC`.
- Entry receipt, unchanged: `E90F11157F3416CE2C78650C4605ADF92BF5D7AC19A293E0C105499EF17276A5`.
- Reclamation core receipt, unchanged: `33EE501601ACB8109FA867C2634FAC1C04F43505B4DD6C6D75821545B120BDD8`.
- Six-artifact inner set, 8,761 bytes: `C48B7C41E73F79F0326B9E0146BF9DC001B902E5A95F5560400FE854530C9B58`.
- Trust policy: `DF9BD076267061F731263B86BDE62EBE161B8666605EDC3AA32606870EEE2049`.
- Trust state: `073CEB317F1B6314274452846AC1959F988EFE9537A72456AEFB493F1DEB69CE`.
- Retained manifest, 2,615 bytes: `EF6A00FE89683E8C44AC8FEF1C1F2F626F82654A5721C18AD44B2307835BD85B`.

The nine retained files total 11,952 bytes. Public symbol offsets and sizes are
unchanged. Native source, manifest, entry/core receipts and the prior demo ISO
are unchanged. PooleGlyph Phase 65 remains the latest inspected checkpoint;
Phase 66 CoreIR integration remains future work, not a boot prerequisite met here.

## Preserved Failures

The first symbol qualification rejected the previous split-debug identity after
27.218 seconds (log `828D527347D619BA596BDF3D39A0D7C913AD51327434A83A276AB7E823699074`).
The next rejected the old PSYM1 golden identity before building, after 0.438
seconds (log `3D1F214FC6B947A144168C40794CD12D35AE025C5E8282AE886A1AD7BCA93F56`).
The pins were measured, then canonical PSYM1 and dependent PPOL1 generators
were run. A fresh qualification passed; neither failed attempt was admitted.
All final bounded runners observed unchanged source and owner report during
execution. Private work directories and logs remain local; public receipts bind
the admitted evidence. Previous checkpoint documents remain immutable.

## Remaining Gates

Selected readiness is **8/27**, with **19** CPU, memory, interrupt, SMP,
scheduler, atomic and lock profiles pending. At least **51** later scheduler
control groups remain unproven: 16 SMP, 18 AP-worker and 17 SMP-preemption
groups. SMP recorded admission also remains open. No phase or flag closes;
94 flags still include 37 open flags. No N5/N6 exit, general cross-CPU atomicity,
hardware qualification, signing, release or production promotion is claimed.

Next: `N7-TRAP-001`, then remaining CPU and downstream dependency replay on
the same kernel. Repair and execute later scheduler controls before admitting
their profiles. Full exact-candidate canonical, Doctor, release, publication,
configured GitHub checks and review conditions still precede merging PR #78.
Cloud branch backup is separate from main-merge qualification.
