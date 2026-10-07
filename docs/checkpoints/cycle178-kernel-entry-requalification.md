# Cycle 178: Kernel Entry Requalification

Date: 2026-09-12. Selected move: `N6-KENTRY-001`, N6.4-N6.6.
State: single-host native image qualification; downstream replay pending.
Branch: `agent/n12-dispatch-execution-holds`, [draft PR #78](https://github.com/rookepoole/PooleOS/pull/78).
Production ready: false. No phase, subphase or flag closes.

## Native Image Evidence

The final PKENTRY1 qualifier runs two clean offline builds in separate target
directories. Linked ELF and canonical PKELF1 bytes match exactly, and independent
Rust/Python loaders agree on the loaded bytes. The 245 kernel host tests,
formatting, host/freestanding Clippy and 43 rejection controls pass.

- Build identity: `PKBUILD1-CYCLE177-N12-EX-HLD-V001-0000000001`.
- Linked ELF: 7,032,744 bytes; SHA-256 `50084E1DFDD64A7EBDC884EB041533B50F0F354997E3D9C9BC0CF5B6277C1E11`.
- Canonical image: 530,072 bytes; SHA-256 `563ED1976CAB4DA773BAE9BCE49F370242C893760E7C221239C1B31F44D969CA`.
- Loaded image: 602,112 bytes, 147 pages; entry offset `0xA000`; 1,325 relocations.
- Final generated entry receipt: `runs/native_kernel_entry_readiness.json`.
- Entry receipt SHA-256: `B9E79FE7CABA4931C3654134A68934B732DD77A6F1555179C2E09EF93D6212D6`.
- Implementation bindings: 55, including all 39 kernel Rust sources.

The generated receipt is copied exactly, not edited to refresh bindings.
The entry tests require exact receipt/product reproduction and independently
reject a changed digest for every kernel source. Source and owner PooleGlyph
hashes are checked before and after each bounded qualifier/test invocation.
Execution timestamps are retained separately from the qualifier's established
deterministic status-date field.

No Rust, manifest, contract or kernel bytes change in this cycle. Cycle 177's
core receipt stays current at SHA-256
`7E289FE30319EA9577C66716FE31EB02600E779D8F0E380172D3C3C708900A71`.
Its 17 stage logs and 30 source bindings remain verified host evidence only.

## Failures And Repairs

The first clean qualifier passed, but the existing identity test rejected its
new relocation count because it still pinned 1,321. The release gate separately
retained old kernel-test and image pins. Both now require the measured Cycle 177
identity; the old identity is tested as a rejection case.

Twelve isolated release-gate controls then exposed six numeric substitutions
accepted through Python equality and one null-product exception. The gate now
requires exact integer summary values and exact-typed pinned product values,
and rejects malformed product/summary objects without raising that exception.
The same controls pass after repair. Component validation is deliberately
isolated in this test, so the result does not imply every component schema is
fully hardened or that the original full validation path accepted all mutants.

- Old-pin failure log SHA-256: `E51722C86D91E64E725E006E08A931512FAF8B4A8E779B7C7E5EA6FBEC0A152F`.
- Gate-control failure log SHA-256: `EC5E38DB14072F48C2622A121F51EF8B9B9D73FA69E532583F33603AC51AEF51`.
- Gate-control passing log SHA-256: `A236FDD275CC4E37D913B90BD77AFB2D75581527263C536A7B996A720F5CD6C0`.

The earlier full entry suite reproduced bytes but failed the stale release-gate
baseline. Later tests pass after repair. Earlier successful receipts were
superseded when the test pins and guide changed; their exact inputs, output
hashes and failed runs remain retained privately. No failure is converted into
a passing measurement by changing a receipt.

The first combined 57-test run had two roadmap assertions fail because they
expected the word "stale". With current entry evidence restored, the component
validators correctly report an exact nested-receipt mismatch instead. The tests
now require that specific mismatch diagnostic while still requiring rejection;
the downstream component acceptance rules are unchanged. The failed run is
retained at log SHA-256
`9D4410C58269276DF1307E8DD63596691CD7D9C2417B2A544D38845605C2077B`.

## Progress And Boundaries

The final combined suite passes all **57 tests**: entry (including exact
receipt/product reproduction), the isolated entry gate, roadmap, architecture,
ownership core and checklist coverage. Its retained log SHA-256 is
`4AC7C41FDFE2CF79F96A1BB6E25C6313D84A65DC620BA62BF4B737256142D009`.
This is focused qualification, not the complete runtime-inclusive canonical audit.

Current selected readiness is **3/27**: entry, policy and errata policy.
**24 downstream profiles remain stale**. Their receipts are preserved and
must not be treated as current merely because entry now passes. Cycle 177's
expanded-suite failure and Cycle 176's exact qualified main pass remain separate
historical records. Main stays `ac15d1d`; this draft is not merge-qualified.

The roadmap, plan, charter header, README, schemas, tests and architecture
baseline record this boundary. There are 961 discovered Python tests and 244
architecture bindings; these counts are inventories, not full qualification.
All 8,996 locked requirements, 57 additions, 40 phases, 301 subphases, 94 flags
(35 open) and 20 program gaps remain conserved. The existing N36 evidence flag
covers the gate repair and remaining transitive coverage work.

No fresh QEMU execution, independent builder, physical hardware, live dispatch,
architectural CPU quiescence, signed boot, demo ISO refresh or production
promotion is claimed. PooleGlyph Phase 65 and its owner-modified conformance
report remain untouched; Phase 66 remains the next language boundary.

## Next Move

Execute `N5-SYMBOLS-SEMANTICS-001`, then ordered load/boot/revalidation/transfer,
five CPU profiles and fourteen memory-through-lock profiles. Run the complete
exact-candidate runtime-inclusive canonical audit, publication scan and GitHub
review/check gates before merging. Keep general task contexts, guarded mappings,
CPU retirement, independent builders and physical qualification explicitly open.
