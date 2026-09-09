# Cycle 169: Current-Kernel Boot-Chain Replay

Status date: 2026-09-09
Status: bounded pre-production qualification; PR #76 remains draft.
Scope: N5.5/N5.6/N5.8, `N5-SYMBOLS-SEMANTICS-001`, existing
`ADD-BOOT-010`, `ADD-BOOT-011` and `ADD-N36-RECEIPT-COVERAGE-001`.

## Implementation

A fresh split-debug build independently measured the unchanged Cycle 168
kernel. PSYM1 now binds its canonical, loaded, debug, build-ID and manifest
identities, 147-page geometry and public symbol offsets. PPOL1 and the boot
artifact fixtures reference the new symbol bytes. Fixed synthetic loader and
transfer markers describe the new geometry; they are not measured boot logs.

PSYM1 readiness now requires source-current PKENTRY1 evidence and explicitly
checks matching canonical, loaded, linked-debug, build-ID and image geometry.
Two new regressions first failed against the missing dependency and now pass,
including six independently changed identity/geometry fields. The previous
kernel's Rust entry address remains an explicit rejected lookup gap.
The broader dependency/schema audit remains open under the existing N36 flag.

## Verified Results

| Component | Current Evidence |
| --- | --- |
| PSYM1 | 4 Rust tests, 158 controls, 16,384 parser and 16,384 lookup comparisons, two identical debug builds |
| PPOL1 | 6 Rust tests, 116 controls, 32,768 differential cases, zero mismatches |
| PKLOAD6 | 328 host tests, two fresh boots, 25 ordered markers, 155 controls, exact handoff/mapping agreement |
| PooleBoot | 8 host tests, two additional boots, 25 markers, 155 controls, exact framebuffer agreement |
| PKREVAL1 | 243 kernel tests, 36 controls, 32,768 rejected mutations across nine retained roles |
| PKXFER1 | Two actual kernel entries, 30 markers, 58 controls, independent guest/host nine-file agreement |
| Focused Python | 83 tests passed, zero skipped |

All six qualifier commands passed; tracked sources stayed unchanged during
each command. Separate architecture/roadmap verification passed 22 tests.
This cycle has six final headless QEMU/OVMF boots, including two kernel entries;
there are no failed or superseded guest runs in this cycle. Transfer ends at
the expected unsigned-policy denial with zero signatures, authority grants,
authorized actions, state writes or post-exit firmware calls. Separate host
fixtures, rebuilt images and prior AP boots are not counted as new live boots.

Kernel SHA-256 remains
`8A2DA65C86B09F7BCF2D5ACDB90029A5B7B7361581BA841ADC3B62AEE168B625`:
530,072 canonical bytes, 602,112 loaded bytes, 147 pages, 1,321 relocations.
Split-debug ELF: 7,024,792 bytes, SHA-256
`A4B9D19DC8B38E1F5DB5C8609DAF833B3BED1CBD30DD866981A6C1B3A66FBBF2`.
The six inner artifacts total 8,761 bytes; all nine retained files total
11,952 bytes. Independent host, Rust and live evidence agree on inner SHA-256
`2DC54F8C02425C44DEB80A0F6285CAF4687A90537114902D39BB338C14BD7664`.

## Receipt Bindings

| Path | SHA-256 |
| --- | --- |
| `runs/native_symbol_readiness.json` | `9CA16D389EAC641FADC7DF310476F872C80255E1AFCA5566718C397A944B4170` |
| `runs/native_policy_readiness.json` | `DFC63C64BF2550F45894D5193339BED011E54D33EC6555020BE5B32FE3AA4AE1` |
| `runs/native_kernel_load_readiness.json` | `290EE8726EA27444DFFF1582E2AD412E21AAE38684DD4A2104A1244E0F57104B` |
| `runs/native_pooleboot_readiness.json` | `C3840B0DCAA092FF0B8B283D087AA1908DDB1D39E53437C4FD1BDA2BDDE3CAA5` |
| `runs/native-kernel-revalidation-readiness.json` | `973791A9F07E62B373C19B45AF03A3574AF038EA977C711B65ED44013891C810` |
| `runs/native-kernel-transfer-readiness.json` | `296E089DAAE4EF5F2E908D8ECB4E4883F16EC93DDA33FFA68EECE04A966FA75F` |

Some component schemas retain their original contract-date field; the actual
Cycle 169 execution date and source/command identities are recorded separately.
No timestamp-only refresh is presented as a new test execution.

## Failures And Limits

The two new dependency regressions initially failed. After their repair, the
first 83-test run found two stale policy/state digest expectations in the
PooleBoot release-gate summary. Independent serialized-input measurement and
successful guest receipts agreed on the replacement values. The corrected
gate and all 83 tests pass; no guest rerun was required for this gate-only fix.
The successful final test log SHA-256 is
`09AC75383795125584CA08F1541E4E9B868E6625F7C771E228C47EF9085F9468`.
Failed logs remain private and preserved.

The selected gate projection passes 9/27: six N5 components, entry, pure
errata policy and the existing Cycle 168 SMP receipt. Reclamation is separately
source-verified. Eighteen checks reject stale downstream evidence. The SMP
receipt still passes its declared input checks but used the prior boot
artifact set: require replay with the new set during N8 qualification and
audit transitive input coverage. Its two older boots are not Cycle 169 runs.
The current release-gate diagnostic is partial and explicitly rejects absent
full canonical qualification. The exact passing Cycle 165 report is preserved
as historical evidence, not reused to qualify the changed candidate.

Next: `N7-TRAP-001`, then CPU/xstate/MSR, memory, IRQ/SMP, scheduler, atomic
and lock replay before runtime-inclusive exact-final qualification and merge.
No phase, subphase or flag closes. Preserve 40 phases, 301 subphases, 57 ADDs,
94 flags (35 open), 20 gaps and 8,996 locked checklist requirements.
PooleGlyph Phase 65, the owner's report change, the frozen demo ISO and
kernel bytes are unchanged. N0 custody, independent builders, authenticated
boot, target hardware, native services/desktop and the production ISO remain
incomplete. No signing, release, host-driver, firmware or physical-media action.
