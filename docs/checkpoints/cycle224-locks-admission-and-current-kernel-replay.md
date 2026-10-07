# Cycle 224: Locks Admission and Current-Kernel Replay

Date: 2026-10-07. Pre-production. Goal remains active.
Move: N12.2/N36, `N12-CONCURRENCY-LOCKS-001`.
Existing requirements: `ADD-N12-CONCURRENCY-LOCKS-001` and
`ADD-N36-RECEIPT-COVERAGE-001`. No new requirement or phase/flag closure.

## Outcome

All 27 selected native checks pass on unchanged kernel216. Lock report admission
now reconstructs typed run, summary, hash, handoff, probe, control, source, tool,
boot and media evidence. The aggregate rejects component errors before accessing
malformed nested objects. The qualifier rejects empty control groups and gives
its host subprocess a180-second timeout. No native lock algorithm is changed.

The refreshed receipt is `runs/native-kernel-locks-readiness.json`, SHA-256
`40EC2B1A2A79A6EE2388CBF695CDF95752C672529B5803D979AE994382641BA0`.
Two final SandyBridge four-vCPU virtual boots each produce35 markers, with
30 executed rejection groups/103 cases,9 host-probe records,8192 FIFO host
acquisitions and246 passing kernel tests. Qualifier duration67.797 seconds.
Two earlier diagnostic boots and two pre-cleanup-repair boots are excluded.
All six boots
passed; no failed guest is hidden or counted as final evidence.

The final qualifier log SHA-256 is
`F544F181B3FA3E96D07A5941BB9A85282A9B1F8B2F870BAEF946585B3154046B`.
Its stage-only text matches the diagnostic log, so the log alone does not
uniquely identify execution. Separate source snapshots and receipt hashes do.

## Preserved Defects

The diagnostic receipt SHA-256 was
`16BB7B563380C8AA92BCF73D9A06F5425559E116F865C7DE744D15C349B00889`.
Before repair,576 mutations produced53 invalid runtime admissions and32 invalid
aggregate admissions, plus6 runtime and64 aggregate exceptions. The aggregate
diagnostic bypassed only its schema loader, not component validation, so it
tests the gate's independent shape handling. The genuine receipt passed both.
Those counterexamples remain in `outputs/cycle224-before-audit.json`.

After repair,631 mutations reject through both paths without exceptions, including
both identically corrupted runs, missing/failed exits, count-preserving control
redistribution, stale source identities and malformed nested evidence. Three
disabled validators are detected by executing the controls. These are admission
and control tests, not631 native faults or an exhaustive concurrency proof.

## Regression

The initial focused suite passes21/21, no skips,25.475 seconds (runner26.359 seconds).
It includes lock tests and all fourteen memory-through-lock entry-provenance
profiles. Source and the owner's PooleGlyph report were unchanged during
execution. Log SHA-256:
`E4AC6246B4E4CA55F26B2873A841A94B100C9ACFD40CD0CF2535F5F26830F0AC`.
The fresh positive receipt was never rebound to newer inputs in tests.

The first metadata regression passed68/71 with three stale assertions still
expecting26 passing profiles and one pending. Their replacements use the
independently validated27/27 result; historical counts remain unchanged.
Failed-run log SHA-256:
`0EA5DF94F654CB88C9570FB2A7997F823317AE259B63F00A8530540139E366A7`.

The initial corrected combined regression passes137/137, zero skips,135.301 seconds
(runner136.250 seconds), including71 metadata tests, locks, all-profile entry
provenance, entry, atomics and boot capture. These counts overlap the focused
suite. Source and owner report stayed unchanged. Log SHA-256:
`0D96AE0CA14C364056D7E14BF175144EC399CB214C2AF0BEBD8AA09C48706FB7`.
Conservation verifies382 source bindings and1163 discovered Python tests,
preserving all27 parent current records, earlier history, native sources,
entry/core receipts, normative charter, checklist, PooleGlyph and demo bytes.

Final review then tightened the timeout implementation. A plain Cargo timeout
could leave a child probe running on Windows. File-backed capture avoids waiting
on an inherited output pipe; timeout cleanup targets only the launched Cargo
process tree, waits for termination and fails if cleanup is unconfirmed. Mocked
success/failure cleanup paths are tested; no real probe timeout was observed.
The earlier passing receipt
`2754EAC48AFEAB0C251DBC448BC531EC76069C38A842D4BE502649AC068A13A8`
and initial regression/publication reports remain superseded evidence. The final
receipt above comes from another fresh qualification, not changed input hashes
on that earlier receipt.

The final timeout-cleanup regression passes 137/137, zero skips, 135.545 seconds
(runner 136.485 seconds). It includes the cleanup success/failure paths, locks,
all-profile entry provenance, atomics, capture and 71 metadata tests. Source and
owner report remained unchanged. These counts overlap the initial combined suite.
Final log SHA-256:
`5077FC39F2E8CBD50C02945D1FFC5415577EA97FA5859C6448AE1B0EBCC24588`.

The exact old lock receipt is retained at
`tests/fixtures/cycle181-locks-readiness.json`, extracted from parent commit
`9dc6de31f2fdf4430ca4714ec4a9245cc85748ec` without alteration. SHA-256:
`837AF50A257AA54316E72014E4B63BB6B18E33161E42FD854A849F2D7AE96F79`.
It preserves historical kernel-entry and boot evidence; it is not current proof.

## Boundaries and Next Move

Recorded consistency does not authenticate execution or establish freshness,
independent builders, hardware behavior, general task retirement or production.
The shared source audit is token-based scope checking, not a machine-code proof.
The separate live AP ticket probe does not qualify every host lock primitive on
real hardware. Broader N36 coverage and transitive dependency closure remain open.

A preliminary AST import inventory of the14 memory-through-lock qualifier/runtime
pairs finds35-38 local Python modules per closure. Each report lacks explicit
path/hash records for20-27 of these modules;17 are common, including
`runtime/native_tier0.py`, `runtime/native_binary.py`,
`runtime/native_kernel_revalidation.py` and `tools/qualify_native_kernel_load.py`.
No recorded explicit hash in those closures is stale. This is a conservative
inventory, not proof that the executions used wrong source: imported-but-unused
modules may be included, other dependency receipts may supply bindings, and
dynamic imports, data and process/tool dependencies are outside this inventory.
Reconciliation against preserved successful command-run snapshots accounts for
all 14 profiles. Each current receipt exactly matches its producer's output;
the recorded log hash verifies, and every module in its static import closure
is present in the producer's source snapshot and unchanged now. No static source
path is missing or stale. This does not itself integrate a runtime guard or
establish authentication, dynamic/data/tool closure or an independent builder.
The next move can use that retained evidence instead of assuming all profiles
need another boot. Reconciliation report SHA-256:
`890AC3472499E07097F845625BCF7386096DE668600C752D089944D7269D090A`;
script SHA-256:
`3A355CA00D569F0DFE35D7F6F997CB0A0541D0CBB43898FDD66FAF50128260AE`.
Local audit report SHA-256:
`D09C9DA173797D63FFFCFA7C0E9E01F1D986DF929372C2E69D9F725DD55FA499`;
audit script SHA-256:
`BF4024B9D592F3797AB7A1D91B183A3BD0481132A36F5B2B94789C3C36DC0E0A`.

All27 parent progress records remain archived. Checklist10512 lines/8996
requirements/171 sections,40 phases/301 subphases,94 flags/39 open and57 additions
are unchanged. PooleGlyph stays at Phase65; manifest/ZIP hashes and the owner's
dirty conformance report remain unchanged. No syntax, Core IR, PGB2/PGVM2, ABI
or IP migration is accepted. Phase66 remains unqualified.

Kernel canonical SHA-256 remains
`FD6C2A0C709957B9EDFFC0647D534E060ED68215C075F07D70AB2AEBCA6C81D1`.
The existing demo ISO remains
`3533965B0DFEA0BFC55399929A9770979B50E4077E77201A68B8331D76570378`.
No signing, key use, privileged probe, firmware/media mutation, tag/release or
production promotion occurred. Cloud branch backup and main acceptance differ.

Next: `N36-RECEIPT-COVERAGE-001`, shared-helper transitive-binding review and full
exact-candidate canonical/Doctor/release/publication/GitHub/review qualification
before merging PR78. N0 custody, N5 authentication, full architectural task
state, general retirement, hardware and independent builders remain open.
