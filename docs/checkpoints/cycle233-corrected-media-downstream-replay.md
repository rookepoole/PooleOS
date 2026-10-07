# Cycle 233: Corrected Media Downstream Replay

Status: pre-production; full exact-candidate qualification pending.
Parent: `7d806ab070563158003974942c422f8b3751346f`.
Branch: `agent/n5-fat32-directory-links`; draft PR #80.
Main remains `bb5e43c3e655db5b8c5676572135471bfd843880`, qualified through Cycle 230.

## Contract And Deliverable

N5.1/N5.8, `N5-FAT32-PARENT-001`, `ADD-N5-FAT32-PARENT-001` and its
open flag. Replay the fourteen remaining downstream profiles against corrected
FAT32 media, reconstruct current source evidence from actual original captures,
and reconcile historical assertions without rewriting historical evidence or
relaxing validators. N8/N9/N12 evidence is dependent, not a phase promotion.

## Execution

All fourteen qualifications pass with 28 fresh successful QEMU/OVMF guest runs,
663 negative-control groups and 2,863 hostile cases. Every qualification retains
its original command, source-before snapshot, log hash and unchanged-source check;
the PooleGlyph owner report remains unchanged. Runs were serial and bounded.
Prior receipt bytes remain in the parent Git tree and local diagnostic copies.

| Profile | Runs | Groups | Cases | Receipt SHA-256 |
|---|---:|---:|---:|---|
| physical_memory | 2 | 191 | 191 | `C38C9D4CF60023EEAE1CFB5550AE79D73EF371B26B10F44BF56F12EF2F37C91C` |
| virtual_memory | 2 | 48 | 48 | `211FA6BD287E2533D42B8FFD7491217E2F2F9DD877821BE1E93CBC5BAFFE52C0` |
| interrupt_time | 2 | 58 | 58 | `1D18A4F1FCDB2EE71FBBC139556E2D909C7E20A69FB4D8E7981759F4EB51B84F` |
| smp_first_ap | 2 | 72 | 72 | `2BE0742DFDFE295CD6FF9D6447D669BECDF3F99A44AFB46E4DBEED2CE3F609D6` |
| smp_percpu_runtime | 2 | 19 | 159 | `4A07915288CE66BB3D2B532FB4B4749DAF158F378E3DC080E222F5055EB61BBC` |
| smp_ipi | 2 | 33 | 609 | `AC993DF3A19BA08E9631196A8804883AAAAF18DFECE9B48C2488E089FB7F29A8` |
| scheduler | 2 | 28 | 115 | `27F0C44FCB9B346C9835B172E4660309C2956AAF03B3140229EA3EB3C495AFF6` |
| scheduler_preempt | 2 | 25 | 226 | `2A7702456C0F3A8C49DFE71B2F555D5D2D35BA2BF9AF1EB22B82FCFF5A491B6C` |
| scheduler_deferred | 2 | 30 | 254 | `F150794A43A04C1D069125A375652AB388B28F9A4B9C2CFBD7B93B42AFAAA55D` |
| scheduler_smp | 2 | 32 | 303 | `B28F2054B66D3404ABB7EB4889DA0080D81E7CD8FFD7B916840CB95CA977DCA3` |
| scheduler_ap_workers | 2 | 34 | 325 | `A9E3ECD5505FA1D924450707C53DCA6F44E0A19E21792F81EF167123C0692562` |
| scheduler_smp_preempt | 2 | 34 | 322 | `DC35D12D58E587A99009D5E1FB561EAC592F5DE4ED2B60176258FFD42BB530E4` |
| atomics | 2 | 29 | 78 | `D266D00705173E3E05D76321DC032C537E049C1E8D87F14F27384D9AEC54E0C3` |
| locks | 2 | 30 | 103 | `6870B22E6F18CA17A4A52B45A714B061862906085BA80BB7FDD9E8C8D5A8C671` |

Exact log/capture hashes, durations and receipt paths are in
`current_corrected_media_replay.receipt_bindings` in the roadmap. The capture map
and raw logs are local under `outputs/cycle233-*`; Git backup does not include
ignored emulator images, logs, tools or private material.

All 27 component checks and 27 source profiles now pass. The aggregate
`runs/native_execution_sources.json` has SHA-256
`65155E981FA217BD9D78218A4E0C0537A574D613ED9FB3E1EBD16511B6A1EA5D`.
It is reconstructed from 27 validated original command captures, not by assigning
current hashes to old executions. Four unaffected rows (entry, symbols, policy,
errata policy) remain exactly unchanged. Twenty-three affected profiles were
replayed across Cycles 231-233.

The complete preceding aggregate is preserved byte-for-byte at
`tests/fixtures/cycle229-execution-sources.json`, SHA-256
`9C64EC020BD4D98182DAB38EF65EA7ABBFC15EC3EFD98BA188D6E005C2AE5295`.
It still fails the current-source guard. Seven replaced Cycle 232 progress records
are archived and independently pinned to their parent's canonical JSON hashes.

## Regression And Reconstruction

The initial focused run executed 273 tests in 403.096 seconds: 272 passed,
one failed, zero skipped. Its immutable log SHA-256 is
`EED18F16536CBD1859514373DB6F23D6FDA69E8CC7A09473CF626ECE87D17A1B`;
runner time 404.156 seconds. The failure compared the new current aggregate with
the earlier reviewed-input migration. The test now compares that migration with
the hash-pinned historical aggregate and separately requires current admission.
Historical roadmap bindings likewise compare old hashes with the frozen ledger
and current bytes with the current ledger. New tests reject forged historical
hashes, swapped paths and mutated current bytes. Runtime guards are unchanged.
The corrected combined run passes all 354 tests (273 native/source checks and
81 roadmap/architecture/checklist tests), zero failures and zero skips, in
483.078 seconds (runner 484.156). Source and owner snapshots remain unchanged.
Log SHA-256: `872060D24021CC9EF18FEE684D3C576D7E260D6184D95926235E744208FCE0CD`.

The first metadata run executed 81 tests: 76 passed and five failed, zero skipped,
in 70.488 seconds (runner 71.313). Log SHA-256:
`B4EB11F8B17CDEFAE9B60FB9564D4BB39C23165D0ECB36F9A114942A99481C87`.
Three assertions still expected the preceding current projection; two failures
came from the schema's preceding-cycle constant. Those current-state expectations
are updated to measured values; immutable historical assertions remain pinned.

The previous Cycle 232 broad run (71 tests, 17 failures) remains preserved in its
historical record. It is not erased or relabeled as successful.

## Conservation And Boundaries

Native kernel SHA-256 remains
`FD6C2A0C709957B9EDFFC0647D534E060ED68215C075F07D70AB2AEBCA6C81D1`.
All embedded entry records, 28 native EFI product records across the fourteen
profiles, and negative-control records are unchanged. Guest clock/checksum changes,
five host-probe executable changes and preemption disassembly/symbol-text changes
are retained. Exact causes and reproducibility of those host outputs are not
claimed. Deterministic logs alone are not fresh-execution evidence.

Retained demo ISO SHA-256 remains
`3533965B0DFEA0BFC55399929A9770979B50E4077E77201A68B8331D76570378`.
It was not rebuilt; its previously identified structural and production-object
gaps remain. No new kernel, ISO, signature, key, firmware or physical-media action.

The locked checklist still has 8,996 requirements; all 59 additions, 96 flags
(41 open), 40 phases and 301 subphases retain their status. PooleGlyph remains at
Phase 65; Phase 66 is unqualified and no ABI or owner file changed. Its owner report
SHA-256 remains `F75E4836FAA9DDD59BA62648FE9542415F2119B659A583FB3F5959F2F5CAE87B`.

Source consistency is not authentication, full dynamic/tool closure, independent
build reproduction, physical-hardware qualification, general task-state/retirement
integration, phase completion or production readiness. `production_ready=false`.

## Exact Next Move

Historical-regression reconciliation is complete. Finish conservation and publication scan;
commit and push this checkpoint to the existing branch. Run canonical qualification
with runtime, bundle and replay on the exact committed candidate, then check the
release/publication and GitHub review/merge requirements before merging PR #80.
Do not bypass a failing or unverified gate merely to save work in the cloud.
