# Cycle 210: Retained Map Growth and Boot Replay

Status date: 2026-10-03. Qualification began 2026-09-30.
Pre-production; not main-merge qualification.
Parent: `6631b01b766453efdf09e2f47a9827fa8eae94a3` (Cycle 209).

## Move and Actual Repair

Initial move `N5-SYMBOLS-SEMANTICS-001` exposed a native boot prerequisite:
the current 148-page kernel collided with the retained stack guard at page 147.
The reconstructed move is `N5-KMAP-001` with `N6-KENTRY-001`, N5/N6/N36,
under `ADD-MEM-001`, `ADD-BOOT-007` and `ADD-N36-RECEIPT-COVERAGE-001`.

The native mapper and independent Python model now reserve 192 kernel pages
(768 KiB). Unused kernel pages and both stack guards remain unmapped. The stack
starts at page 193, uses 36 RW/NX pages, and the 256-page R/NX handoff starts
at page 230. Handoff population must remain inside its first 512-entry table;
the previous two-table bound overstated what the population routine implements.
The temporary VM mapping is now `0xFFFFFFFF801E6000..0xFFFFFFFF801E7000`.
Contracts, probe geometry, diagnostics and synthetic parser fixtures agree.

Native regression accepts 148 and 192 pages and rejects 193 before writing any
of the five output tables. Before repair, 14/15 native tests passed and the
growth case failed. After repair, 15/15 pass in both debug and optimized builds.
The loader's hostile guard request now crosses the actual reserved capacity,
instead of assuming that adding one page must hit the guard.

## Measured Image and Evidence

Build ID: `PKBUILD1-CYCLE210-N5-KMAP-BOUND-V1-000000001`.
Canonical image: 534168 bytes, 148 mapped pages, entry offset `0xA000`,
1323 relocations; loaded image size 606208 bytes.

| Artifact | SHA-256 |
| --- | --- |
| Canonical kernel | `AE3422B2D44E6EC87AB1D5B51414C023E46F2EE3461A0D0895B9D1242E10D25A` |
| Linked kernel, 7091272 bytes | `6B168F59888CE36050918908E9D7DDB4EEA87F4B8A13FF90EB80E26E0C248BD5` |
| Loaded image | `8288BA39AD5B65499B1E59280D3ED9F088609A95760952D1E8489B42CA8391EE` |
| Entry receipt | `080A019D50DBBA7CCA32FAD792D70949A4E0A21DC43E9F52031B371227B56E53` |
| Core receipt | `E752211396320793A4EE7C28FADF9A4DE51A503D17B6D9FF264DDD5F49D43650` |
| Symbol receipt | `D727F88200ED95CED5AC99C1FB0781209A50022668F3935FA8C6969013B6EC4A` |
| Policy receipt | `CE31D5D02151A45731EF0E72E516F5DEF977811B48A527D648F5BB3256F715D1` |
| Loader receipt | `03832C810CAFE4594AD213ACF134172C58350EBE6F9626F500E72F2B4D2BC701` |
| PooleBoot receipt | `681D870EB05CE21E2631A8768559FE7963C7A0929D89737F401F4237B0B73728` |
| Revalidation receipt | `0FE9DEE9CD343895BA46BE1F8DD6405E422ED5773A2405679E1559DD18D5EACD` |
| Transfer receipt | `4521507E4A8055C411809CB7CA4AC77D3507F1A04CF386BA68713BDFD2F5E001` |

All 17 core stages pass; two clean entry builds match with 246 kernel tests and
43 hostile image controls. These are two builds on one host, not two builders.
The final boot receipts contain six fresh VM runs, including two kernel entries.
Loader: 332/332 host cases and 155/155 controls. PooleBoot: 8/8 host cases and
155/155 controls. Revalidation: 36 controls and 32768 differential cases.
Transfer: 58 controls. Symbols: four native tests, 158 controls, 16384 parser
cases and 16384 lookup cases (4484 hits, 5721 misses, 6179 rejects). Policy:
116 controls. Nine retained files total 11952 bytes; the six inner artifacts total
8761 bytes with 8185 payload bytes and a 2615-byte manifest.

Independent reconstruction from the actual new kernel confirms:

- Inner set: `163EDAC3648C52267DAD983A6283D0860668B04B2E9B077A40F1855046A81DB1`.
- Trust policy: `957F07706B7B7CA495B9745CB50721B0698AAE79EBFE87A4BDB8B10F6892CEDC`.
- Trust state: `CC015F3A79444B1BB91B1F7BEB985BEC9024759CAC2A688BA62339CCD48CAEF2`.
- Manifest: `8A73B6E1382F4F241D59676B977CA466CD8A98A2987FE2A49CC4A2397DDC8AD3`.

All 97 focused Python tests pass without skips in 41.579 seconds. The runner
confirms unchanged source and owner report. Log SHA-256:
`EF94D4166CE644A2D557B33092F9930365E45BFB356741C05C94B07AD217CD9F`.
This includes rejecting 650 corrupt symbol records at both runtime and aggregate
admission and 25 independent prior-identity mutations with component validators
deliberately bypassed in the negative test. Counts overlap, not additive coverage.

The broader regression passes 212/212 without skips in 275.617 seconds (runner
276.625 seconds), including AP/SMP/deferred native transactions, core and exact
entry reproduction, host provenance, boot and 57 repaired metadata tests. Log:
`41A610A52599C58359FECB18DB666E6E14F953E496EBCD08594A5FAFBCD1D3AF`.
Source and owner report remained unchanged. Final mapping regression again
passes all fifteen native cases in both profiles; log:
`51CA1E8C2A7488F50E0472DE17907CFBFC2930D1B2B1B97D8071EE42ACAD3FB3`.
Conservation verifies 21 unchanged archives, 355 source bindings and 1105
discovered Python tests. These results were executed before being recorded here.

## Preserved Failed Attempts

These local diagnostic logs are retained, not counted as accepted qualification.
The cloud checkpoint records their identities; local scratch outputs are not
implicitly claimed to be uploaded.

| Tag | Cause | Log SHA-256 |
| --- | --- | --- |
| symbols | Stale native lookup address | `29860EB2FE9255BE128D9565E6C9398F761292AFC8BE260981503DE9BB653FDF` |
| symbols2 | Stale expected lookup outcome counts | `D357455B148D15009B4E1AB43730A3E9FA825351CA7ADCDF9D2DF43F92346C10` |
| policy | Stale generated contract/vectors | `77243B4B0B3896809C76CC157B9096536ADBF186496BCEB645880005E951E118` |
| load | Actual kernel/retained guard collision | `9DDE37AEA9DAE0CEC429EE7537E3F3D1E1AD01722698A564B53CCA8578B76B89` |
| guardBefore | Test harness integer type mismatch | `52514B4C37FA99F7B94C7705A326A210969D2320D98B35CF19FE7AC8CD3471B6` |
| guardBefore2 | Reproduced native capacity failure | `DCB5B9910CEF4D72DB145149DB6238A1B940761E68EF551B01BC0174B1C6927D` |
| mapPython | Old 147-page expected geometry | `F96D02FD5DC17DCB8AB9196ABFD90CC92870776C31E33826BA0A264E066BD7D7` |
| entry | Old build-ID schema constant | `BFC77DF62CDFC2FDE1D92B8D67E634D6C21CA641C2865C5A232864AC294AA921` |
| entry2 | Old embedded entry-contract digest | `8B7A2FD1407928AFC246EC5F5DC7F60F934DCBAB0DBC2237D990731ED7A4687E` |
| load2 | One-page mutation no longer crossed reserved boundary | `06753CB44EA4BF1205EBE4096ED7A07C27F7F499EA9DFAE55FF9174229F0C3E0` |

Earlier passing symbol/policy and core measurements were provisional and are
superseded by final symbols4, policy3, core4, entry3, load3, boot2, revalidation2
and transfer2. Prior Cycle 209 entry/core receipts and all 21 current roadmap
records remain archived as history, never relabeled as new-kernel proof.

The first metadata regression passed 52/57 with no skips: two pending-profile
counts, one refreshed-symbol expectation and two architecture binding-count
assertions were stale. Log:
`5BB36D5B27F9CDD02D97E078BCD49D996EB4544868ED8983E460D135AA1CFF73`.
Initial conservation detected the same old 354-binding schema limit. The
architecture generator rejected an unsupported date argument before execution;
it was rerun using its documented interface. Neither diagnostic is a pass claim.

## Remaining Gates and Cloud Boundary

Selected readiness is 8/27. Nineteen CPU, memory, interrupt, SMP, scheduler,
atomic and lock profiles need current-image replay beginning `N7-TRAP-001`.
At least 35 executed-control groups remain unproven: eighteen AP-worker and
seventeen SMP-preemption groups. AP-worker admission still needs repair.
Full canonical qualification of the exact candidate, publication-boundary scan,
release gate, configured GitHub checks and review conditions still gate main.
PR #78 is a development backup, not production promotion.

No phase or flag status closes. Boot ends at unsigned-denial-halt: zero new
authority, state writes and post-exit firmware calls. No authenticated trust,
physical boot, second builder, firmware update, media write, release, main merge
or production readiness is claimed. The demo ISO remains unchanged at
`3533965B0DFEA0BFC55399929A9770979B50E4077E77201A68B8331D76570378`.

Checklist coverage stays 10512 lines, 8996 requirements, 171 sections and 57
added requirements. Its source and coverage hashes remain unchanged. PooleGlyph
Phase 65 manifest/ZIP remain `A2387DD5A9E51BA50493E1E39E5D9B0FCE304BAFDF57567552AB3CE30DAC7CE9`
and `F3CCEB701CF76274D9464A0958BF6106888FB34F3C0BFBD55DE4ACE03C427ABC`.
The owner's modified conformance report is untouched; Phase 66 remains next.
