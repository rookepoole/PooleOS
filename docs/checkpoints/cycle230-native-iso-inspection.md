# Cycle 230: Native ISO Inspection

Status date: 2026-10-07. Pre-production; production_ready=false.
Selected N0.8 / N0-ISO-INSPECTION-001. The charter remains normative and unchanged.

## Qualified Main

PR #78 merged 2026-10-07T21:11:11Z. Source commit
`31099c64b276f6636dc9ad34db8ea755aa803023` and main commit
`08d4dbe707e546ffb33e0db102ff76dbf8f6daeb` share tree
`5f4e95ddad0b2f3195134b6945067083cdc13943`.
The exact source passed 106/106 canonical and 708/708 Doctor checks with runtime,
bundle and replay inputs in 1103.594s. Unittest returned zero; individual run/skip
counts were not retained. The 1,207 count is discovery inventory, not a pass count.
All 1,635 tracked files and the owner's PooleGlyph report remained unchanged.
Publication scan found zero violations. All 63 checkpoint commits remain on the
retained source branch. This pass does not qualify this checkpoint's later edits.

- Canonical report SHA-256: `75AA0DB76D701C92AF23426BE6A625EE0261F367BB1EC7147C05882C83BC5AE5`.
- Canonical log SHA-256: `CA9FDC2BA04BD0F5520C2F75FD2FC898717EAB12790A964C6E3DB3124DF8F05D`.
- Cloud closeout: https://github.com/rookepoole/PooleOS/pull/78#issuecomment-6046964502.

## Implementation And Evidence

`runtime/native_iso_media.py` decodes a bounded single-namespace ISO9660 optical
image, its EFI El Torito catalog and mirrored FAT32 filesystem. It validates
allocation ownership, paired endian structures, directory paths, aliases, long
file entries, hidden files and padding. `tools/check_native_iso_architecture.py`
applies the unchanged architecture policy to decoded names and content and raw
metadata; fragmented file content is reconstructed before scanning. Required
production objects must be nonempty files in the EFI namespace. Unsupported
formats reject rather than bypass inspection. `--native-iso` integrates an actual
image check with the release gate; no such input means no ISO conformance claim.

The independent synthetic fixture uses the existing pinned host pycdlib wheel for
ISO authoring and its own FAT32 writer. Fixture payloads are non-executable.
Nineteen new tests pass, covering forbidden paths and markers, noncontiguous file
chains, short/long aliases, hidden payloads, malformed metadata, missing objects,
allocation defects and exclusive report output. Independent pycdlib extraction
agrees with the three fixture ISO file payloads. No mount or device write occurs.

Combined architecture suite: 28 run, 27 passed, one expected Windows symlink
permission skip, 8.594s (bounded runner 9.203s). Source and owner report unchanged.
Log SHA-256: `E1B7D7354C0A5A23B956CFA20B857C4C42AF6D2C75D01EC0A800DE409C1DEE46`.
The initial run had nine failing subtests: the fragmentation fixture moved a
cluster but incorrectly truncated its original three-cluster chain. Retaining
the original successor repairs the fixture, without loosening the scanner.
Failure log: `134468D89857ADA579684206CBA194C37DE92BB9D02B6B851F1FF2318BF4DBD9`.

The first combined metadata/source-guard run attempted 124 tests, with one stale
roadmap status-string assertion failing and one expected symlink skip. Update the
test to the newly recorded Cycle 230 state; no gate is relaxed. The failed log is
retained as `1A44C76B9097AEEEC0FF57325EFCB6B969E762E6A4E6CB9BF4D0210F979F090E`.
The final exact-candidate replay is recorded externally, avoiding self-referential
source hashes. Full canonical qualification is still required for a main merge.

## Actual Demo Finding

The retained 66,115,584-byte demo ISO SHA-256 remains
`3533965B0DFEA0BFC55399929A9770979B50E4077E77201A68B8331D76570378`.
Inspection inventories 17 files (five ISO, twelve EFI); all twelve native payload
hashes match the original embedded manifest. The architecture verdict is FAIL:

- EFI directory dotdot references root cluster 2 rather than the required zero.
- `pooleos/PooleKernel.elf` is absent in the required production namespace.
- `pooleos/system/initial-system.bundle` is absent.
- `pooleos/recovery/recovery.bundle` is absent.
- `pooleos/manifest.json` is absent.

A memory-only correction of the parent entry yields structural acceptance while
all four missing-object failures and all twelve native payload hashes remain.
The original ISO is not modified and the writer is not repaired in this cycle.
This isolates a real media-writer defect from expected demo/production differences.
Report SHA-256: `C75EBB6A29C1B71A30FDD97F33540C29D631264E85B3392197E85C3F0E1376FB`.
Demo review runner exits zero in 2.484s; log SHA-256:
`0EB7E48D6E44214F541B4A369DB247AD5B109DBF991719E6CE3142A583414E2C`.

## Preserved Boundaries And Next Move

Add `ADD-N0-ISO-INSPECTION-001` and `ADD-N5-FAT32-PARENT-001` and corresponding
open flags. Preserve the original 8,996 checklist requirements and 57 additions;
there are now 59 additions and 96 flags, 41 open. No phase or existing flag closes.
The unchanged native kernel SHA-256 remains
`FD6C2A0C709957B9EDFFC0647D534E060ED68215C075F07D70AB2AEBCA6C81D1`.
All 27 original selected native receipts and their execution guard remain intact.
The demo contains a historical kernel; no current-kernel demo rebuild is claimed.
No guest boot, hardware run, signature, release or production promotion occurs.
Known-marker absence does not prove native authorship or absence of every substitute.
Supported-layout expansion, long directory aliases, authentication, native parser
agreement, independent builders and hardware remain open requirements.

PooleGlyph remains Phase 65. Manifest SHA-256:
`A2387DD5A9E51BA50493E1E39E5D9B0FCE304BAFDF57567552AB3CE30DAC7CE9`;
checkpoint ZIP SHA-256:
`F3CCEB701CF76274D9464A0958BF6106888FB34F3C0BFBD55DE4ACE03C427ABC`.
The owner-dirty conformance report remains
`F75E4836FAA9DDD59BA62648FE9542415F2119B659A583FB3F5959F2F5CAE87B`.
Phase 66 is not qualified and no cross-repository edit is made.

First qualify and cloud-back up this exact candidate; main merge requires full
canonical, publication and GitHub/review gates. Next native move:
`N5-FAT32-PARENT-001`, repair the writer, inspect regenerated media independently,
then identify and replay affected source-bound boot/media evidence. Preserve all
historical failures and receipts. N0 custody remains an independent owner blocker.
