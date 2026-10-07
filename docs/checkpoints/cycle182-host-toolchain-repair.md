# Cycle 182: Host Toolchain Reproduction Repair

Status date: 2026-09-26. Status: **scoped repair verified; not merge-qualified**.
Parent: `e453a67c779d12aff4b8a5460ad8fc5698fd2378`. Main remains qualified
Cycle 176 at `ac15d1d`; PR #78 remains draft. The preceding cloud-status turn
verified backup but made no implementation progress. This cycle resumes the
available engineering action without treating the merge blockers as an impasse.

## Selected Move

`N6-KENTRY-001`, N6.4-N6.6, with N3.3/N3.5/N3.6 host-tool provenance and the
existing `ADD-N36-RECEIPT-COVERAGE-001` / `FLAG-N36-RECEIPT-COVERAGE-001` audit.
N2 inventory is read-only supporting context, not hardware qualification.
Deliverable: deterministic host linker/library selection, rejecting drift and
ambient build overrides, with actual regenerated entry and fixture receipts.
Exit: exact receipt/product reproduction without weakening the comparison.

## Reproduced Cause

The owner-installed newer Visual Studio toolset became available September 23.
The retained rustc link log shows automatic selection of MSVC 14.51.36231.
Seven clean, offline builds isolate the recorded probe-size change:

| Linker | MSVC CRT libraries | Windows SDK | Probe bytes |
| --- | --- | --- | ---: |
| Automatic newer installation | Automatic newer installation | Automatic | 147968 |
| 14.44.35207 | 14.44.35207 | 10.0.18362.0 | 148480 |
| 14.51.36231 | 14.51.36231 | 10.0.18362.0 | 147968 |
| 14.44.35207 | 14.44.35207 | 10.0.28000.0 | 148480 |
| 14.51.36231 | 14.51.36231 | 10.0.28000.0 | 147968 |
| 14.44.35207 | 14.51.36231 | 10.0.18362.0 | 147968 |
| 14.51.36231 | 14.44.35207 | 10.0.18362.0 | 148480 |

Thus the size change follows the **MSVC CRT library tree**, not the linker
executable or SDK in these controlled combinations. This does not identify one
particular CRT object or prove complete binary reproducibility of the ephemeral
probe. Real probe binaries, PE inspections and command logs are retained locally.
The two experiment reports have SHA-256:

- Matrix: `25748BD729DC814C1C9532A198DECBA12AFBB64523CA32FC129F846907A6FAB9`.
- Cross: `75795B2ACB21C8A36D71CEF44FB66A152479EEAB641B9616B501C69E709CB409`.

## Implementation

`specs/native-host-msvc-profile.json` pins MSVC 14.44.35207 and SDK
10.0.18362.0 using four recursive input-tree fingerprints: linker directory,
MSVC libraries, SDK UCRT libraries and SDK UM libraries. The existing bounded
fingerprint algorithm binds sorted relative names and content, including added,
removed and renamed files. There are 720 files and 889212229 bytes. No Microsoft
tool binaries are copied into the public repository or redistributed.

`tools/native_host_toolchain.py` verifies all four trees before selecting an
explicit Cargo host linker and ordered library paths. Missing, altered, extra,
renamed or reparse inputs reject. Roots may be explicitly relocated with
`POOLEOS_HOST_MSVC_ROOT` and `POOLEOS_HOST_WINDOWS_SDK_ROOT`, but their contents
must match the same pins. There is no automatic latest-version fallback.
Defaults use the existing Visual Studio 2022 Build Tools and Windows Kits layout.
No global environment, PATH, installation or system configuration changes.

The shared `isolated_environment` now removes ambient linker/compiler options,
Cargo build/target/profile overrides and Rust wrappers. The ELF qualifier reuses
that setup and verifies the host profile. PKENTRY1 binds six additional host-build
inputs (61 total, including all 39 kernel Rust files) and rejects missing, stale,
wrongly typed or overstated host-profile evidence. Exact reproduction assertions
remain intact. Rust sources and kernel products are unchanged.

Configuration mechanisms are documented by the
[Cargo configuration reference](https://doc.rust-lang.org/cargo/reference/config.html)
and [Microsoft linker reference](https://learn.microsoft.com/en-us/cpp/build/reference/linking?view=msvc-170).
Microsoft documents [library-search precedence](https://learn.microsoft.com/en-us/cpp/build/reference/libpath-additional-libpath?view=msvc-170).
Those mechanisms support selection; they are not evidence of a hermetic host.

## Tests And Preserved Failures

Sixteen new host-profile tests pass, covering four content mutations, extra,
missing and renamed files, reparse entries, malformed profiles, numeric-type
substitution, bad versions, relative roots and environment isolation.
Two entry tests add profile-substitution and six-input source-mutation checks.

The first hostile combined run passed 37 of 38 tests and failed one: the older
fixture qualifier inherited `_LINK_`, which reached its UEFI rust-lld process.
Failure log: `E76BA9D6444174F1401C7265DC880B7A8F35588CADB9393494A86044640BDF7D`.
Shared environment sanitation repairs this demonstrated leak. A new regression
covers the fixture path. Both actual fixture build pairs then reproduce exactly,
and all three fixture negative controls pass. This is static fixture evidence,
not a functional firmware boot.

The final hostile-environment suite passes **39/39 tests, zero skips**, including
byte-for-byte reproduction of both generated receipts and the kernel product.
Log: `F3056EA5AD8415E934307A9947D0E186DB83E3209155DF393D58B34E0F45E2AF`.
Each entry qualification executes 245 Rust kernel host tests, 43 controls and
two matching clean kernel builds. The original Cycle 181 failed combined run
and drift receipt, and this cycle's superseded intermediate receipt, remain
preserved. Neither failure is relabeled a pass.

| Artifact | SHA-256 |
| --- | --- |
| Host profile | `4BD6B069392E11215EE1942425B3A12CE2CAEC6746A9450EAC20B037FC538182` |
| Final entry receipt | `5B3A8DAD63C21416A43074664F9C52B9BE8FB6E906824AF30F805F5FFC65CED5` |
| Final fixture receipt | `87668ADC571427244CD490D172CD01BAA3871709A0D76F7319D665526B68CFB5` |
| Unchanged canonical kernel | `563ED1976CAB4DA773BAE9BCE49F370242C893760E7C221239C1B31F44D969CA` |

## Remaining Work

New provenance is not retroactively attached to old runs. The selected native
projection is **3/27**: entry, kernel revalidation and errata policy pass;
24 dependent checks correctly reject stale entry/fixture provenance. The separate legacy
PKELF1 receipt also needs replay after changing its shared qualifier. The existing
core receipt validates its declared inputs but retains Cycle 177 execution and
incomplete transitive host-tool provenance, not a new current host run.

The first metadata invocation also failed: one nonexistent checklist test-module
name and a stale 4/27 expectation that omitted PPOL1's fixture-receipt binding.
Its log is `A3029FE01A234B96ADE6A6FB9CB3D72F6A285CC10D95F7259A2AC55DFF0394EF`.
The actual final input set measures 3/27; neither the missing module nor the
earlier projection is treated as a successful current-state verification.

The corrected metadata/core/checklist suite passes 45/45 tests; its log is
`6F252C11552C09353605F0491285B71321B479243CB38860F4AE5CB8EE37756F`.
The source inventory discovers 981 Python tests, not 981 executed passes.
Architecture binds 259 paths. A separate conservation check verifies unchanged
native source, every prior historical ledger record, phase/flag states, checklist,
normative charter, kernel product, fixture product bytes, PooleGlyph and demo.

Next: `N5-ELF-001`, then `N5-SYMBOLS-SEMANTICS-001` and ordered boot/CPU/memory
requalification. Before final scheduler receipts, replace at least 65 unsupported
PKSCHED3/4/5/6 rejection attestations with actual, individually bound execution
or explicit non-execution status; continue the broader N36 audit. Then run exact
canonical/Doctor/publication/review gates before merging PR #78 and resuming
N12.3 live task contexts. No merge or main-protection bypass occurs here.

Complete host attestation is still open: system DLLs, OS state, malicious
concurrent replacement, Cargo parent configuration, host executable timestamp
and debug-path reproducibility, installer provenance, signed supply-chain
closure and independent builders are not established by these pins. Later
toolchain updates must be explicit profile changes with requalification.

PooleGlyph remains Phase 65 with no new checkpoint or language/interface change.
Its owner-modified report is preserved; Phase 66 remains open. All 8996 locked
requirements, 57 additions, 40 phases, 301 subphases, 94 flags (35 open) and 20
gaps remain. No phase or flag closes; the normative charter is unchanged.
This is not a new native feature, guest boot, ISO, release or production promotion.
Local raw logs/binaries are not claimed to be cloud-backed public source.
