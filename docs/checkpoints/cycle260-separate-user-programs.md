# Cycle260: Separately Built User Programs

2026-10-11. PROGRESS. The prior cycle259 changed authoritative source and native
evidence; this cycle adds original user-space executables, not a new boot image.
The full goal remains active. Usable native integration ISO first, full robust
microkernel afterward; no Linux, kernel shell or splash substitute.

## Implementation And Evidence

Standalone native/userspace contains PooleInit, PooleCounter, independent PSTART1
decoding, PSABI1 IPC wrappers and PSVC1 service-control policy. Init commands
startup and ordered counter work; the service commits state only after reply send.
No allocator, host API, kernel dependency, general loader or new authority.

Final qualification:15 Rust host tests in each debug/release configuration,
two independently compiled builds with byte-identical ELF and extracted code.
PUSERBIN1 format extraction and LLVM object relocation audit pass. Source19
bindings and six toolchain input hashes remain unchanged.
Final capture4.172s; no native execution this cycle.
Receipt runs/native-user-program-readiness.json SHA256:
880B7F588AB683E3AC2D317D231BF5D821525CB63343D10EC953C39FFD6DDFD8.
Final build logF129707865C067468F361928774DCD44B27127F4ED2E0CF0B1BF38E9AB507B3E.

| Program | Code Bytes | ELF Bytes | Code SHA256 |
| --- | ---: | ---: | --- |
| PooleInit | 1054 | 5360 | 652744F7106618D27399FC985BDAB42E0BEE3FDF0033B14AFE11F1E8D66C5E87 |
| PooleCounter | 1094 | 5400 | 78E45268BBEA7EC8D4985DECEB54A7E5F88E27961941C533C926EF2F2722A7C5 |

Each has one RX code page, entry0, no writable segment/import/remaining relocation.
Each object has four local R_X86_64_PLT32 references. This is bounded compilation
and format evidence, not instruction-semantic or CPL3 execution proof.
Nine Python format/source/ABI-control tests passed before the final build.
Combined checklist/architecture/roadmap/native-user-root/program metadata:
179 tests passed in53.111s, capture53.968s, unchanged source and owner report.
Log480233E6944BD51CB0C5B61DD4C1B8764F91AB17FBEC749A47608045EAAA516D.

## Failed Attempts And Repairs

- programsfirst6.359s:15 debug/15 release pass; LTO could not consume installed
  core bitcode. Switched to repository-style non-LTO. Log
  F8D90CCA097718749C799451017912E50C0A274B612CC5AE14C80415606AB010.
- programssecond2.672s: linker rejected mixed relocation and PROGBITS output types.
  Split the forbidden relocation sections; retained zero-size assertions. Log
  C978B6C8A8483B5ECD535F97386F5E205A586855B08176ADE28DAD8D9218ECFB.
- programsthird2.609s: code0x1120 plus forbidden data0xB8 exceeded the contract.
  Link-map diagnosis identified slice/overflow panic formatting and GOT references.
  Explicit checked decoder arithmetic/ranges removed panic formatting without
  disabling overflow checks. Log
  71C42F01CF8BB21E7D728D414BFE13775C90672EA1853173FF0EA588325EC0BF.
- programsfourth2.656s: code fit but GOT0x38 remained. Made small cross-crate
  runtime methods inline-capable. Log
  1EAF701909E88F50C757F0938D539D71DC2346F36D43CE6E6D3181C51D3F9B81.
- programsfifth2.688s and programssixth2.953s: remaining cross-crate GOT calls.
  Object relocation inspection identified Message encode/decode; exposed their
  bodies for inlining as well. Logs
  7DE384FF68C170B5B3F7DC0C0E526BB5AA0202BA3D45328081BD010644FEF44A and
  19856FACF62C2518BC80794BC9058D95CAE2138CAB6557C2D693B4E6BD332811.
- mapfirst1.719s and mapsecond1.735s reproduce the same rejected layouts for
  diagnosis; not extra qualification passes. Logs
  30E3D5623330E07D010459A8727942651FFA0E8F177991C45CEAB737532DFF8A and
  F61C6905DB9044518EEA7B0A3DF486D33912FD685EC58297276AAB2AA967C7D4.

programsseventh passed3.390s. Final programseighth adds object relocation and
toolchain-input auditing and reproduces the exact same program bytes.
No capture source drift or owner-report drift. No failed evidence erased.

Initial publication scan rejected the new readiness receipt because no explicit
public-ledger exception existed (1797 paths, one violation; capture51.672s).
LogCCE2AF4ABF825312E72CD5A1D45647AE259F2CF1C233D17D8888E62285B023A9.
Reviewed the complete receipt: only public relative paths, hashes, bounded results
and nonclaims. Added its exact path to the existing public-ledger policy and
gitignore exceptions, with positive coverage and neighboring private/raw names
still rejected. Secret/private-path checks and all other exclusions are unchanged.

## Conservation And Next

Kernel and PooleBoot sources are unchanged. Cycle259 native receipt remains
byte-exact and its790 bindings are checked, not re-executed. No fresh guest run
is claimed. The205/208-page kernel still needs normal-boot/profile separation.
Current native startup evidence is259; separate user-program build evidence is260.
Read-only recorded gate projection remains2/27 passing profiles; four static
source closures remain current (entry, symbols, policy, errata_policy).
This projection performed zero guest runs and is not canonical qualification.
Conservation suite:115 tests passed in8.345s, capture9.672s; unchanged source and
owner report. This overlaps the179-test metadata run and is not115 new tests.
LogB02565DA862CE933DBC0D8DB915C1499A0CF506E7FC19FC5A10314AC60E61155.

Next: connect these exact programs to a normal session boot path, bind granted
handles and prove real CPL3 IPC/preemption and fault containment. Then confined
console/input, efficient idle, shell/read-only files/two apps and optical ISO.
Host compilation does not qualify PSABI1 adapter execution or stack usage.
No child launch, restart supervisor, interactive service, signed PXABI1/PINIT1
activation or usable ISO exists yet. USI-1/2/3 partial;4/5 not started.

Three product-readiness tests remain unresolved:
- tests.test_native_kernel_load.NativeKernelLoadTests.test_contract_and_readiness_pass_semantic_validation
- tests.test_native_kernel_load.NativeKernelLoadTests.test_readiness_detects_stale_input_and_oracle_divergence
- tests.test_native_kernel_transfer.NativeKernelTransferTests.test_contract_and_generated_readiness_are_current

Full exact-candidate canonical gates still block main. No phase/flag closure.
Master8996 requirements/40 phases301 subphases59 additions97 flags42 open20 gaps.
Master SHA256 A8C94719FAF9428C1F133010BA2603C0270C4E1EFD7327AF8EAB9C8C362ABB3D.
PooleGlyph Phase65 remains newest and was reread; Phase66 CoreIR audit stays next.
Archive F3CCEB701CF76274D9464A0958BF6106888FB34F3C0BFBD55DE4ACE03C427ABC.
Owner report F75E4836FAA9DDD59BA62648FE9542415F2119B659A583FB3F5959F2F5CAE87B.
Historical execution ledger65155E981FA217BD9D78218A4E0C0537A574D613ED9FB3E1EBD16511B6A1EA5D.
All verified unchanged. Owner .tmp trees preserved.
No release, signing, main merge, firmware or physical-media action.
