# Cycle259: Owned Program Startup

2026-10-11. PROGRESS: native qualification, metadata and conservation PASS. Owner direction remains usable
original-native user-space integration ISO first, then full robust microkernel.
Not Linux, a kernel shell, scripted transcript or splash substitution.

## Implementation

PSTART1 supplies validated built-in program bytes and an owned argument snapshot
to the existing retained image constructor. Entry must lie within actual code.
Up to eight arguments occupy a bounded 512-byte, pointer-free offset block.
Code/arguments copy with physical readback before mapping and publication; failed
copy or preparation retains rollback ownership. Startup metadata binds the full
prepared admission before the architecture selects initial registers.

Seven new Rust tests cover malformed geometry, counts, NUL and exact capacity,
snapshot independence, code/argument copies and zero tails, all changed admission
fields, foreign allocator identity, partial/corrupt writes and cleanup retry.
Three new Python tests require the native startup marker, hostile field/order
controls and source ordering for the bound startup path.

Two additional generation16 tasks validated their copied user argument blocks
and exited102/103 in each of two fresh native boots:79 markers,479 CR3 writes,
1032 released475 scrubbed pages per full probe. Both reject1111 altered-evidence
controls; each startup records120/120 ticks,228 code bytes and112 argument bytes.
Earlier17 containment cases, IPC/deadline/admission/sustained dispatch and ordinary
unsigned-boot denial remain required. This is not actual init or a usable ISO.

## Failures And Repairs

- hostfirst6.219s: compile errors in tests only, missing Vec import and array-to-
  byte-slice coercions. Repaired explicitly; hostsecond466 tests pass18.718s.
  Failed log E74A88DA2F9649D33DCDFE4FEF1B27143C873195CDED8257AD91F81544B2A59F.
- oraclefirst0.984s:61/62 pass, old IPC source assertion still expected direct raw
  arguments. Repaired to require the diagnostic fallback and selected arguments;
  the new test separately requires bound startup before context construction.
  Failed log4E322C9A0F52DB7EE94715D0CA0AA14938840320F397F6464C943A4809AABCAC.
  Corrected62/62 pass0.844s; logA7DA2065BFB6C3BA40DF047CC314739D7CFDCD039762F3D6240F75AA07398815.
- nativefirst39.219s: first six checks pass; freestanding probe compared different
  scheduler TaskId types. Now compares both slot and generation explicitly.
  Failed log1154549D01271E7F0F6A0470F5F9288A8BFC1D9C55793EE4D96CBB36BD97CE94.
- nativesecond95.031s:17 preboot checks pass; text0xA46EE exceeds0xA2000.
  Extended three text pages: data0xA5000, RELRO0xB7000, image0xCD000=205 pages.
  Capacity208 and36-page guarded stack unchanged, leaving3 image pages.
  Failed logB9E73CCE8F04D25E529A5F404A4586ECB642B0BC9937EA261318432271E4B436.

All captures preserve source/owner snapshots. No observation timeout causes a
live run to be restarted. Failed logs are retained, not replaced by later passes.

## Next And Boundaries

Next: normal session boot separated from exhaustive qualification and actual
separately built init, then confined console/input, efficient idle, shell/read-only
files/two applications and fresh optical ISO interaction/sustained-session tests.
General resource policy, native clock-fault recovery and signed PXABI1/PINIT1
activation remain. This bootstrap only copies trusted immutable PIC built-ins in
the existing one-page code/stack layout. Startup records do not grant authority.

Three existing product-readiness failures remain pending current-kernel migration:
- tests.test_native_kernel_load.NativeKernelLoadTests.test_contract_and_readiness_pass_semantic_validation
- tests.test_native_kernel_load.NativeKernelLoadTests.test_readiness_detects_stale_input_and_oracle_divergence
- tests.test_native_kernel_transfer.NativeKernelTransferTests.test_contract_and_generated_readiness_are_current

Full exact-candidate canonical replay still gates main. No ISO/release/key/signing/
firmware/physical-media action. Complete microkernel, PooleGlyph/PDC and accessible
PooleGlass remain required. One unknown runtime sample remains unknown, not zero.

## Conservation

Cycle258 receipt is frozen byte-exact:
EFE6449288127C53CD6D6D3D8D47E0C69ED3E7EB49470F12F1E769495D901C0B.
Master checklist remains8996 requirements,40 phases301 subphases59 additions,
97 flags42 open20 gaps. No closure. Master hash
A8C94719FAF9428C1F133010BA2603C0270C4E1EFD7327AF8EAB9C8C362ABB3D verified.
PooleGlyph Phase65 checkpoint reread; Phase66 CoreIR audit still next. Archive
F3CCEB701CF76274D9464A0958BF6106888FB34F3C0BFBD55DE4ACE03C427ABC verified.
Owner reportF75E4836FAA9DDD59BA62648FE9542415F2119B659A583FB3F5959F2F5CAE87B
and historical ledger65155E981FA217BD9D78218A4E0C0537A574D613ED9FB3E1EBD16511B6A1EA5D unchanged.

## Final Native Capture

All18 checks pass in364.672s, including466 kernel debug tests,734 overlapping
Rust executions,84 Python oracle tests, two incompatible-profile rejections,
two fresh CPL3 probes and ordinary unsigned-boot denial. Source and owner report
remain unchanged. Guest timeout150s, dispatch/timer bounds and36-page guarded
stack unchanged. Kernel205/208 pages,763416 bytes. No live capture remains.

Receipt SHA256:2CB2E882C774CE62FDEF78ACB660968E38A0CA4966A379AE9C30B08CE06FF349.
Kernel SHA256:A2FBA44667D5E5361E6587B021DB6642A00310A7051EF8F77B6DA2DC9342855E.
Log SHA256:ABAEA47878F567C44ED54ADBB6BBD7EBDA7E4A65F2892C80E9F74FA859CFF87B.

Roadmap, architecture, checklist and marker-oracle regression:169 tests pass,
zero skips in52.303s (53.172s capture). Source and owner report unchanged.
Log SHA256:AEAF22A74965029024FEEE45DED9276ACAB533364707D9AD6B4F7E6B74568CCC.
Read-only retained admission projection accepts2/27 profiles; four static source
closures remain current. Neither result is new guest execution or full readiness.

Conservation regression:105 tests pass, zero skips in8.519s (9.891s capture).
Source and owner report unchanged. Master checklist, phase/flag coverage, PooleGlyph
boundary, historical receipt integrity and current startup evidence preserved.
Log SHA256:79BAD3072A8DCAEA8CDF78B0A3B89974267739D413CF606B5B08D0B5DF83DD2B.
