# Cycle 180: Current-Kernel CPU Qualification

Status date: 2026-09-12. Pre-production; no phase, flag or release promotion.
Selected move: `N7-TRAP-001`, N7.5/N7.6, then N7.1/N7.3/N7.4 CPU/xstate/MSR
qualification. Related requirement: `ADD-N7-XSTATE-001`; evidence work remains
under `ADD-N36-RECEIPT-COVERAGE-001`. Prior turn: progress, with Cycle 179
backed up at `82bf4c1ecdd20c0bbe584d86906a061a84167642` through draft PR #78.
Main remains qualified Cycle 176 at `ac15d1da5304eab19ae3ed098d26cdcadfa78156`.

## Executed Native Evidence

All five profiles reproduce the unchanged Cycle 177 kernel. Each embeds the
exact current PKENTRY1 receipt, including 245 host tests, 43 entry controls,
two matching clean builds and 55 implementation bindings. Canonical kernel:
`563ED1976CAB4DA773BAE9BCE49F370242C893760E7C221239C1B31F44D969CA`.
Current entry receipt:
`B9E79FE7CABA4931C3654134A68934B732DD77A6F1555179C2E09EF93D6212D6`.

| Profile | Fresh Boots | Controls | Generated Receipt SHA-256 |
| --- | ---: | ---: | --- |
| PKTRAP1 | 6 | 51 | `2A997942A2AD844814BF4FE5A6C14D51A1C7A24044796D82FCEC73C3A403BD2C` |
| PKCPU1 | 2 | 41 | `9BD6F02A53B34281CB60A13C86CEC26AC99C06F02958FFA23ABAB26A0A54A136` |
| PKXSTATE1 | 2 | 43 | `669B861DBA9E62A2BCD532BB37A87207DE9D2CC389CA92B2A0B1FF86B2C996C3` |
| PKXEXC1 | 2 | 43 | `1BFC2D346562896621E72EBAABF05B224ECF517B1050E172DBF426AEF247BFB8` |
| PKMSR1 | 2 | 47 | `D6198669F7CE065B48D64EEEF3774C213E94B8DD0C1FA537B66B1BCDAE6ECFE0` |

Fourteen final boots and 225 controls pass. One additional expected TCG
exception non-delivery diagnostic is recorded separately, not counted as a
successful exception boot. The two actual exception boots use the existing
WHPX profile; other runs use the locked TCG profiles. All guests use bounded,
headless, fresh-vars execution with read-only scratch media and no NIC/shares.
No host driver installation, physical probe, firmware or physical-media write
occurs. Local builds are not independent builders.

The trap scenarios cover exact returning breakpoint, invalid-opcode and
guard-page exceptions, terminal double-fault containment, and rejection of an
explicitly synthetic malformed frame. CPU policy is read-only observation.
The xstate profile saves/restores and clears bounded x87/SSE context images.
Each WHPX exception run delivers three exceptions, recovers from two and
rejects unsupported state. The MSR profile makes eleven support-gated reads,
with zero MSR/control writes, MCA-bank reads or PMU reads. Exception/MSR linked
machine-code audits pass. These are bounded development profiles, not the
complete processor, user-context, scheduler or production exception contract.

## Test And Gate Repairs

Positive provenance regressions now consume untouched generated CPU receipts.
They no longer refresh source or embedded-entry fields in memory. Each mutation
campaign first requires a valid positive baseline. Eighty stale/malformed entry
substitutions and twenty invalid current-entry dependencies reject across all
five profiles. This is scoped to those profiles, not complete transitive proof.

The initial positive test rejects all five old receipts; its failure is
retained. After fresh trap execution, six of seven trap tests pass but the
aggregate gate rejects the old image/count pins. The gate now requires the
measured canonical digest and 1,325 relocations. Nineteen CPU gate controls
pass: fifteen promotion/authority cases plus four isolated stale digest/count
cases, including the immediately preceding image. No runtime validator is
weakened, and actual positive receipts precede the isolated gate tests.

| Retained Attempt | Log SHA-256 |
| --- | --- |
| Stale positive provenance, five failures | `5EEA6835CA744F30DC5426A5F51D300FB28215CD93B8324B35F6234695FC1AF0` |
| Old trap acceptance pins, one failure | `E53187039E6C4B2716D7E0C1D94E4FD6B7D8BEE80EC4CA79C1077B23B57BA4AF` |
| Repaired trap suite, seven passes | `DB43E2566D2F756E67AF84086CCB487962FD824DD03BBB149879AD0E7E62480C` |
| Focused CPU suite, 46 passes | `5F0968C7EA5288C3E189D04E06EEB246951C6AF40EB59C89307EC3301B92754D` |

A local measurement helper initially treated a string path as a Path object
and stopped before output. Normalizing the path repaired the helper; this was
not a guest failure and did not cause duplicate replay. Final measurement
checks each exact copied receipt, full component validation, every recorded
marker summary, both diagnostic channels, independent retained-file agreement,
all execution/log hashes, unchanged entry and the core's seventeen stage hashes.

The combined closeout passes 174/174 tests in 44.753 seconds, covering the CPU
suite, six-component boot chain, exact kernel-entry reproduction, entry gate,
roadmap, architecture, core ownership and checklist. Its log SHA-256 is
`3AD4D8BB548AF766F38E89B8A602D265D430207F184DAB616A25D8CC6AF4E27B`.
Tracked source and the owner's PooleGlyph report stayed unchanged throughout.
This includes the 46-test CPU subset; the counts are not additive.

## Progress And Boundaries

Selected current readiness is 13/27. All five CPU gates and the prior eight
entry/boot/errata gates pass; fourteen memory-through-lock profiles remain
stale. Full canonical and Doctor qualification have not been rerun. The 962
discovered Python tests are an inventory, not a full-suite pass.

Plan 2.83.0 and roadmap Cycle 180 preserve all 8,996 locked requirements,
57 ADD items, 40 phases, 301 subphases, 94 flags (35 open) and 20 gaps. The
architecture baseline adds this checkpoint for 250 direct bindings. All old
CPU receipts are retained in Git history and local exact backups; fourteen
old memory receipts remain unchanged. Historical qualification is not current
acceptance. The N36 flag records the stronger genuine-positive test boundary.

Native Rust, kernel bytes, the current entry/core and six boot-chain receipts,
PooleGlyph Phase 65 and the owner's modified conformance report, the frozen
PooleGlass demo ISO and normative charter remain unchanged. There is no
language/AST/semantic/Core IR/PGB2/PGVM2/ABI/policy migration or promotion.

Next: `N9-PMM-ACPI-CONSUMER-001`, then VM/IRQ/SMP/scheduler/atomic/lock replay,
full exact-candidate qualification and publication/review before PR #78 merge.
N12.3 live task contexts and architectural CPU retirement follow. N0 custody,
applicable target errata/microcode authority, all-vector/guarded-IST/user-mode
qualification, independent builders and physical execution remain open.
No signed release, new ISO or production completion is claimed.
