# PooleOS N0 Owner Decision Packet

- Packet version: 1.0.0
- Status date: 2026-07-16
- Move: `N0-RATIFY-001`
- Status: awaiting Rooke Poole's explicit selections; unsigned and non-promoting

## Read This First

This packet turns the current N0 owner gate into five bounded decisions. It lists the exact proposed ADR bytes, all 38 objective definitions, and every allowed governance-key profile. Nothing is pre-accepted.

Completing the response form authorizes only the selected source dispositions and the next preparation step. It does not generate a key, sign a manifest, merge a branch, create or publish a tag, change repository governance, or claim that PooleOS meets any objective.

## Current Gate

- Pending owner actions: `6`.
- Proposed ADRs: `ADR-0003`, `ADR-0004`.
- Objective definitions: `38` total, `0` measured.
- Trusted public governance signers: `0`.
- Ready for owner review: `true`; ready for signature: `false`.

## Exact Source Set

The packet binds `16` exact files. Binding-list SHA-256: `8F5E4C663D2D6F1BB0D6ECFC7CD85267206A3580B39C96090908DB88A0281E1F`.

| Path | Bytes | SHA-256 |
|---|---:|---|
| `docs/adr/0001-native-pooleos-constitution.md` | 3017 | `6E8D0AD1CF75639F1069D41CA4DA3EC200D999963FA4B7B19E0C27F773CC5834` |
| `docs/adr/0002-reuse-clean-room-and-publication-boundary.md` | 3868 | `01E0B5B8AB15736E6E15F8E994CE0456BC0DF7AB5DD3040B2E5A9D06C1FA8E0F` |
| `docs/adr/0003-language-and-toolchain-split.md` | 4108 | `6F874FDBBA98CE728A230C4AF7798F202D09A63CE7394510C810C1E65932B1B0` |
| `docs/adr/0004-product-names-and-version-namespaces.md` | 2666 | `9798309FC902C2F5E5A8206751DA4423532E25690A2AD23AD4DC116F3566A637` |
| `docs/adr/0005-v1-scope-mission-threats-and-non-goals.md` | 3124 | `1C7924EFE619F39AEF6BAB54ED3981BB5439AE929783C5EACD8FAA08EBF60268` |
| `docs/adr/0006-tcb-and-component-placement.md` | 2912 | `B973BEB8EE7EABCFB677DA892821287DB77214DE0E980B8EE78342C5DE3C2F03` |
| `docs/adr/0007-repository-governance-and-source-tree.md` | 3680 | `F02F1572C1BEDD803B7617E251F0AD4E08942FCE0C4663D21A63CD3FADA17E4D` |
| `specs/native-architecture-constitution.json` | 6015 | `94D8BDDF9BC85DE10D3B7FBF53BA2D0CC1C822C1F573FF94D0F1AB49F7EFF753` |
| `specs/native-v1-objectives.json` | 33416 | `525946A7AA7A7D0F27682810EDD636D7E743C32548ACE442AB208B680A7E8584` |
| `specs/native-v1-objectives.schema.json` | 5437 | `AF4D18B414A65D35ABEBC178AE2B55FFAB3FF5A5CE7D17C8A4CB279A7F038A98` |
| `specs/pooleos-kernel-charter.md` | 12238 | `DFD14DC3D594B419E6C3A1FF4051D4CFA35C1FC18C8DBABF24715C66BFFA2E15` |
| `specs/native-release-architecture-policy.json` | 1765 | `F8B6D491A28D72E3C9B36FAB5B24D446FBD67CD760A9A8B05C7774EB3A691DE5` |
| `docs/publication-boundary.md` | 4739 | `96C614E2EA4C61809CC07C2804936220BCCC64B3B2EEE5D1711888A58FD65FD6` |
| `specs/adr-ratification-policy.json` | 7394 | `ADE9E446A604D224C80D1436D3D1E0AF0DA29A2F567416492BCB133F0E22C111` |
| `runs/adr_ratification_readiness.json` | 8684 | `8DF0A003B43BF341F329822D521561E6956EA6DFE2054379B03B5FB0B42495A9` |
| `docs/adr-ratification-ceremony.md` | 8828 | `372135888F2FEC6BB652E1992D25B5E636CBF23EAB4799A22518F838BC0658FE` |

## Decision 1: ADR-0003 Language and Toolchain

Exact source: `docs/adr/0003-language-and-toolchain-split.md` at SHA-256 `6F874FDBBA98CE728A230C4AF7798F202D09A63CE7394510C810C1E65932B1B0`.

Use Rust 2024 no_std for PooleBoot, PooleKernel, privileged services, and drivers; keep assembly minimal; use freestanding C17 for portable PDC and ABI probes; and keep Python outside production images as a host oracle and harness.

Recommendation: `accept_exactly_as_written`. This is advisory, not an owner selection.

Why this is recommended:

- The split reduces memory-safety exposure in privileged code while keeping explicit stable wire and disk ABIs.
- The one-host Rust and LLD qualification already exercises the selected PE32+ and ELF64 target families without claiming a functional boot.
- C17 remains available for independent portable PDC and ABI checks, and Python cannot become a production-image dependency.

Tradeoffs:

- Rust, LLVM, LLD, core, alloc, and compiler builtins become reviewed external build inputs.
- Unsafe Rust, assembly, generated bindings, and C interoperability require continuing inventory and independent ABI fixtures.
- A later language change requires a reviewed superseding ADR and new toolchain evidence.

Allowed response: `accept_exactly_as_written`, `amend_before_acceptance`, `reject_and_supersede`.

## Decision 2: ADR-0004 Names and Namespaces

Exact source: `docs/adr/0004-product-names-and-version-namespaces.md` at SHA-256 `9798309FC902C2F5E5A8206751DA4423532E25690A2AD23AD4DC116F3566A637`.

Keep PooleOS component names coherent while versioning boot, kernel, syscall, IPC, driver, filesystem, package, update, recovery, desktop, receipt, crash, PGB2, and PGVM2 contracts independently.

Recommendation: `accept_exactly_as_written`. This is advisory, not an owner selection.

Why this is recommended:

- Independent namespaces prevent an unrelated product version from silently changing wire, disk, recovery, or executable compatibility.
- The names match the native architecture constitution and the current PooleGlyph PGB2 and PGVM2 integration boundary.
- Unknown major versions fail closed and persistent layouts never use the unstable native Rust ABI.

Tradeoffs:

- Each public namespace needs its own compatibility, migration, test-corpus, and deprecation policy.
- Renaming a namespace after publication requires explicit migration and compatibility handling.
- PGB2 and PGVM2 remain unfrozen until PooleGlyph Phase 66 and later N34 evidence pass.

Allowed response: `accept_exactly_as_written`, `amend_before_acceptance`, `reject_and_supersede`.

### ADR-0003 Structured Snapshot

| Boundary | Proposed implementation |
|---|---|
| `pooleboot` | Rust 2024 no_std on x86_64-unknown-uefi with efiapi and rust-lld |
| `poolekernel` | Rust 2024 no_std on x86_64-unknown-none ELF64 with bounded x86_64 assembly |
| `privileged_user_space` | Rust 2024 no_std with controlled alloc and generated stable ABIs |
| `portable_pdc_reference` | freestanding C17 |
| `host_evidence` | Python 3 allowed as a non-production oracle and harness |
| `native_rust_abi_on_wire_or_disk` | `false` |
| `cxx_in_v1_tcb` | `false` |
| `third_party_dependencies_default` | `deny` |

### ADR-0004 Structured Snapshot

| Role | Namespace |
|---|---|
| `boot_protocol` | `PBP1` |
| `kernel_object_abi` | `PKABI1` |
| `syscall_abi` | `PSABI1` |
| `ipc_abi` | `PIPC1` |
| `driver_protocol` | `PDRV1` |
| `user_abi` | `PUABI1` |
| `executable_abi` | `PXABI1` |
| `filesystem_format` | `PFS1` |
| `vfs_protocol` | `PVFS1` |
| `package_format` | `PPKG1` |
| `service_supervisor_protocol` | `PINIT1` |
| `update_format` | `PUPD1` |
| `recovery_protocol` | `PREC1` |
| `desktop_protocol` | `PGLASS1` |
| `receipt_format` | `PRCP1` |
| `system_manifest` | `PSM1` |
| `iso_manifest` | `PISO1` |
| `crash_format` | `PCRASH1` |
| `pooleglyph_bytecode` | `PGB2` |
| `pooleglyph_vm` | `PGVM2` |

## Decision 3: Workstation v1 Profile and 38 Targets

Freeze a measurable workstation release profile across reliability, accessibility, compatibility, privacy, and performance without claiming that any target has been measured or met.

- Profile ID: `POOLEOS-WORKSTATION-V1-CANDIDATE`
- Edition: `PooleOS Workstation`
- Architecture and firmware: `x86_64` / `UEFI`
- Support profiles: `TIER0-QEMU-Q35-OVMF-PENDING`, `TIER1-B650M-9800X3D-RTX5070-001`
- Required modes: `normal`, `safe`, `previous_known_good`, `diagnostic`, `live`, `installer`, `recovery`

Recommendation: `accept_exactly_as_written`. This freezes definitions only. `measurement_evidence_accepted` remains `false`.

Why this is recommended:

- The targets are explicit, testable, evidence-bound, and fail closed instead of relying on broad quality claims.
- Acceptance freezes definitions only; all 38 implementation measurements remain open.
- Future evidence may justify a reviewed amendment, but measurements must not be weakened after results are observed merely to manufacture a pass.

Tradeoffs:

- The reliability and fault-injection sample counts require substantial lab and automation time.
- Accessibility and privacy targets apply to installer and recovery paths, not only the normal desktop.
- Performance gates require retained raw distributions and exact hardware, firmware, workload, and clock bindings.

Target-set SHA-256: `9C25304CDB72FD037468481BA6437F0D783A2AA496A6144DC5DE659D9CDF2BCF`.

### Reliability Targets (7)

| ID | Metric | Gate | Minimum run | Applies to | Required evidence |
|---|---|---|---|---|---|
| `REL-T0-BOOT-001` | successful clean tier0 cold boots percent | at least 100 percent; zero tolerance | 10000 sample(s) | tier0, normal, safe, recovery | Retain every seed, launch manifest, serial log, exit reason, and failed boot. |
| `REL-T1-BOOT-001` | successful clean tier1 boot restart shutdown cycles percent | at least 100 percent; zero tolerance | 1000 sample(s) | tier1, normal, safe, recovery | Bind every cycle to exact hardware, firmware, media, power source, and stage markers. |
| `REL-SOAK-001` | fatal kernel or unrecovered system fault count | no more than 0 count; zero tolerance | 1 sample(s), 168 hour(s) | tier0, tier1, normal | Run a declared seven-day mixed workload with retained faults, resource trends, and watchdog events. |
| `REL-UPDATE-001` | recoverable update and rollback fault scenarios percent | at least 100 percent; zero tolerance | 1000 sample(s) | tier0, tier1, update, recovery | Inject interruption at every declared update transition and prove previous-known-good or recovery availability. |
| `REL-FS-POWER-001` | durability contract violations after randomized power cut | no more than 0 count; zero tolerance | 10000 sample(s) | tier0, tier1, poolefs | Check acknowledged-data, metadata, replay, repair, and mount invariants after each cut. |
| `REL-DRIVER-RECOVERY-001` | stale authority or kernel faults after driver crash reset | no more than 0 count; zero tolerance | 10000 sample(s) | tier0, tier1, driver_domains | Exercise process death, reset, revocation, stale completion, DMA teardown, and supervised restart. |
| `REL-RECOVERY-RTO-001` | recovery time objective seconds | no more than 900 seconds at p100 | 100 sample(s) | tier1, recovery | Measure from declared unrecoverable normal-slot failure to usable offline recovery UI and data-repair entry point. |

### Accessibility Targets (8)

| ID | Metric | Gate | Minimum run | Applies to | Required evidence |
|---|---|---|---|---|---|
| `ACC-WCAG-AA-001` | applicable wcag 2 2 level a and aa criteria mapped and passing percent | at least 100 percent; zero tolerance | 1 sample(s) | normal, installer, recovery, pooleglass | Publish an applicability crosswalk; native-software exceptions require an explicit rationale and equivalent test. |
| `ACC-KEYBOARD-001` | required workflows completable keyboard only percent | at least 100 percent; zero tolerance | 25 sample(s) | normal, installer, recovery | Include login, permissions, settings, update, rollback, diagnostics, backup, restore, and shutdown workflows. |
| `ACC-SEMANTICS-001` | required controls with programmatic name role state value percent | at least 100 percent; zero tolerance | 100 sample(s) | normal, installer, pooleglass | Verify through an independent accessibility-tree inspector and representative assistive client. |
| `ACC-TEXT-SCALE-001` | required workflows without loss at text scale percent | at least 100 percent at 200 percent text scale; zero tolerance | 25 sample(s) | normal, installer, recovery, pooleglass | Reject clipped, overlapped, hidden, unreachable, or semantically truncated required content. |
| `ACC-CONTRAST-001` | minimum normal text contrast ratio | at least 4.5 ratio; zero tolerance | 100 sample(s) | normal, installer, recovery, pooleglass | Also require 3:1 for large text and essential non-text boundaries in every required theme. |
| `ACC-REDUCED-MOTION-001` | required surfaces honoring reduced motion percent | at least 100 percent; zero tolerance | 25 sample(s) | boot_identity, normal, installer, recovery, pooleglass | Disable nonessential animation and preserve static progress and error state without timing dependence. |
| `ACC-FLASH-001` | maximum flashes per second | no more than 3 flashes per second at p100; zero tolerance | 25 sample(s) | boot_identity, normal, installer, recovery, pooleglass | Analyze every animation, transition, warning, and error effect including failure fallbacks. |
| `ACC-RECOVERY-001` | required recovery workflows with keyboard high contrast static and serial alternative percent | at least 100 percent; zero tolerance | 15 sample(s) | safe, diagnostic, recovery | Publish screen-reader and braille boundaries; graphical failure must retain keyboard and serial/GOP operation. |

### Compatibility Targets (6)

| ID | Metric | Gate | Minimum run | Applies to | Required evidence |
|---|---|---|---|---|---|
| `COMP-SUPPORTED-HARDWARE-001` | advertised hardware profiles with exact qualification receipts percent | at least 100 percent; zero tolerance | 2 sample(s) | tier0, tier1 | Advertise only exact tested firmware, device, media, and feature combinations. |
| `COMP-VERSION-001` | unknown major boot abi ipc driver package and pgb2 versions accepted | no more than 0 count; zero tolerance | 100 sample(s) | all_profiles | Exercise older, newer, malformed, colliding, and downgrade version identifiers independently. |
| `COMP-PATCH-001` | declared v1 patch compatible contract tests passing percent | at least 100 percent; zero tolerance | 100 sample(s) | v1_patch_releases | Bind each public contract to a declared compatibility window and retained previous-version corpus. |
| `COMP-POSIX-SUBSET-001` | advertised posix source subset items with conformance evidence percent | at least 100 percent; zero tolerance | 1 sample(s) | native_user_abi | Keep POSIX as an explicitly enumerated source-level subset; unimplemented calls are not advertised. |
| `COMP-LINUX-ABI-001` | linux abi kernel module or driver compatibility claims | no more than 0 count; zero tolerance | 1 sample(s) | all_profiles | Release-tree and documentation scans must reject Linux ABI, module, or driver promotion claims. |
| `COMP-WINDOWS-ABI-001` | windows binary or driver compatibility claims | no more than 0 count; zero tolerance | 1 sample(s) | all_profiles | Windows remains a development host and is not a production ABI or driver source. |

### Privacy Targets (7)

| ID | Metric | Gate | Minimum run | Applies to | Required evidence |
|---|---|---|---|---|---|
| `PRIV-TELEMETRY-DEFAULT-001` | profiles with telemetry enabled by default | no more than 0 count; zero tolerance | 7 sample(s) | all_profiles | Inspect every shipped profile, first-run path, update, recovery, and diagnostic mode offline. |
| `PRIV-PRECONSENT-NETWORK-001` | undeclared outbound connections before explicit user authorization | no more than 0 count; zero tolerance | 100 sample(s), 24 hour(s) | normal, installer, recovery | Retain packet captures for clean install, first boot, login, update UI, diagnostics, and recovery. |
| `PRIV-STABLE-ID-001` | stable device or user identifiers exported without explicit scope | no more than 0 count; zero tolerance | 100 sample(s) | all_profiles | Test logs, network protocols, crash paths, package operations, and support exports for correlation identifiers. |
| `PRIV-DIAGNOSTIC-REDACTION-001` | diagnostic exports with unreviewed secret or identifier findings | no more than 0 count; zero tolerance | 1000 sample(s) | diagnostic, recovery, support_export | Run seeded-secret and seeded-identifier corpora through preview, redaction, archive, and transport paths. |
| `PRIV-CONSENT-REVOCATION-001` | optional data collection workflows with visible consent and revocation percent | at least 100 percent; zero tolerance | 10 sample(s) | normal, diagnostic, support_export | Consent must be specific, reversible, non-coercive, and independently auditable. |
| `PRIV-RETENTION-001` | default local diagnostic retention days | no more than 30 days at p100 | 100 sample(s), 744 hour(s) | normal, diagnostic | Verify quota, expiry, clock-change, low-space, backup, restore, and user-clear behavior. |
| `PRIV-CRASH-UPLOAD-001` | automatic crash upload paths | no more than 0 count; zero tolerance | 100 sample(s) | normal, safe, diagnostic | Crash artifacts remain local until a per-export preview and explicit user action. |

### Performance Targets (10)

| ID | Metric | Gate | Minimum run | Applies to | Required evidence |
|---|---|---|---|---|---|
| `PERF-BOOT-MARKER-001` | pooleboot entry to first serial or gop marker milliseconds | no more than 1000 milliseconds at p99 | 1000 sample(s) | tier0, tier1, all_boot_modes | Measure from UEFI image entry, excluding firmware time, with serial as the independent clocked marker. |
| `PERF-KERNEL-INIT-001` | poolekernel entry to pooleinit ready milliseconds | no more than 2000 milliseconds at p99 | 1000 sample(s) | tier1, normal, safe, recovery | Use signed stage markers and retain timeout, dependency, driver, and fallback state. |
| `PERF-LOGIN-READY-001` | uefi handoff to interactive login milliseconds | no more than 15000 milliseconds at p95 | 1000 sample(s) | tier1, normal | Measure cold and warm populations separately and include software-rendered fallback. |
| `PERF-FRAME-P95-001` | pooleglass frame time p95 milliseconds | no more than 16.67 milliseconds at p95 | 100000 sample(s), 1 hour(s) | tier1, 2560x1440, normal | Use representative window, text, transparency, input, and notification workloads with raw frame times. |
| `PERF-FRAME-P99-001` | pooleglass frame time p99 milliseconds | no more than 33.34 milliseconds at p99 | 100000 sample(s), 1 hour(s) | tier1, 2560x1440, normal | Report animation, reduced-motion, reduced-transparency, and software-rendered populations separately. |
| `PERF-INPUT-LATENCY-001` | input to visible response p95 milliseconds | no more than 50 milliseconds at p95 | 10000 sample(s), 1 hour(s) | tier1, normal, pooleglass | Bind physical input timestamp, event delivery, application response, composition, and scanout observation. |
| `PERF-IDLE-MEMORY-001` | clean idle resident memory bytes | no more than 2147483648 bytes at p95 | 100 sample(s), 0.5 hour(s) | tier1, normal, software_rendered_fallback | Include kernel, services, drivers, compositor, caches, and retained diagnostic memory after a declared quiet period. |
| `PERF-IDLE-CPU-001` | clean idle total cpu utilization p95 percent | no more than 2 percent at p95 | 1800 sample(s), 0.5 hour(s) | tier1, normal | Measure one-second samples with network disconnected and scheduled maintenance separately declared. |
| `PERF-POWER-REGRESSION-001` | release candidate idle power regression from accepted baseline percent | no more than 10 percent at p95 | 30 sample(s), 15 hour(s) | tier1, normal | Bind external instrumentation, ambient conditions, firmware, device state, display state, and workload; never override hard thermal limits. |
| `PERF-IPC-001` | local 64 byte call reply p99 microseconds | no more than 100 microseconds at p99 | 1000000 sample(s), 0.25 hour(s) | tier1, low_load, same_numa_node | Retain raw distributions and report cross-core, loaded, timeout, cancellation, and priority-inversion cases separately. |

## Decision 4: Governance-Key Custody

Recommendation: `hardware_fido2_ed25519_sk`. The hardware-key availability placeholder in the owner's prior authorization was not resolved, so availability remains explicitly unselected.

| Profile | Key type | Assurance | Separate risk acceptance |
|---|---|---|---|
| `hardware_fido2_ed25519_sk` | `sk-ssh-ed25519@openssh.com` | recommended hardware backed user presence | `false` |
| `hardware_fido2_ecdsa_sk` | `sk-ecdsa-sha2-nistp256@openssh.com` | hardware backed fallback when ed25519 sk is unavailable | `false` |
| `passphrase_ed25519_provisional` | `ssh-ed25519` | provisional preproduction owner custody | `true` |

Private material must stay outside the PooleOS tree, outputs, handoffs, cloud sync, Git history, and this conversation. The primary governance key remains separate from recovery, Secure Boot, package, update, and release keys.

## Decision 5: Public-Key Publication

After a key exists, independently inspect its fingerprint. The recommended disposition is `approve_after_fingerprint_review`, which permits publishing only the public key and fingerprint to `security/owner-adr-signers.allowed` and GitHub's SSH signing-key registry. It does not authorize any signature.

## Owner Response Form

Reply with this block completed. Use only one allowed value per field. Leave amendment details as `none` when accepting exact text.

```text
POOLEOS-N0-OWNER-RESPONSE-V1
ADR-0003: <accept_exactly_as_written | amend_before_acceptance | reject_and_supersede>
ADR-0004: <accept_exactly_as_written | amend_before_acceptance | reject_and_supersede>
WORKSTATION-V1-AND-38-TARGETS: <accept_exactly_as_written | amend_before_acceptance | reject>
FIDO2-HARDWARE-KEY-AVAILABLE: <have | do_not_have | unsure>
GOVERNANCE-KEY-PROFILE: <hardware_fido2_ed25519_sk | hardware_fido2_ecdsa_sk | passphrase_ed25519_provisional>
PROVISIONAL-SOFTWARE-KEY-RISK-ACCEPTED: <yes | no | not_applicable>
PUBLIC-KEY-PUBLICATION: <approve_after_fingerprint_review | not_yet>
AMENDMENT-DETAILS: <none | exact requested changes>
I-CONFIRM-DEFINITION-ACCEPTANCE-IS-NOT-MEASUREMENT-ACCEPTANCE: <yes>
I-CONFIRM-THIS-DOES-NOT-AUTHORIZE-KEY-GENERATION-SIGNING-MERGING-TAGGING-OR-PUBLICATION: <yes>
```

## What Happens After the Response

1. Codex validates that every selection is explicit and internally consistent.
2. An amendment or rejection stops the ceremony while the affected source is revised or superseded and the packet is regenerated.
3. Exact acceptance permits a separate source-status and unsigned-manifest preparation change.
4. Key generation, public-key registration, detached signing, merge, signed tagging, and publication remain separately approved checkpoints.

## Validation

- Schema and semantic validation: `true`.
- Negative controls: `12/12` pass.
- Owner acceptance recorded: `false`.
- Signature authorized: `false`.
- Publication authorized: `false`.
- Production promotion allowed: `false`.

## Claim Boundary

- This packet is unsigned preparation evidence and is not owner acceptance or cryptographic ratification.
- Recommendations are advisory; every owner selection remains explicitly unselected.
- All 38 objective definitions are listed, but all 38 implementation measurements remain open.
- No public key, private key, credential, recovery secret, hardware-key stub, signature, tag, or publication receipt is included.
- The packet does not authorize Codex to merge, sign, publish, change governance, probe privileged hardware, load a driver, modify firmware, or write physical media.
- Architecture disposition does not prove PooleBoot, PooleKernel, native services, PooleGlass, PGB2, PGVM2, PDC backends, or a production ISO.
