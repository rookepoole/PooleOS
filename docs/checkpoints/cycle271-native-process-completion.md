# Cycle271: Native Process Completion

Native builds:2026-10-11; checkpoint closeout:2026-10-13. Native user-space integration ISO remains the immediate owner
priority; the complete robust microkernel, PooleGlyph/PDC and PooleGlass follow.
No phase or implementation flag closes. No new ISO or release is claimed.

## Implemented

- PCOMP1 read-only call20 on existing generation-bound process capabilities.
- Explicit attached/pending/claimed/detached states and typed exit/fault/cancel
  outcomes. Detachment never fabricates completion or freed memory.
- Atomic retained completion publication after checked task identity, scheduler
  teardown and trusted dispatcher's physical cleanup. Duplicate publication rejects.
- Launch supersession now waits for completion; mere revoked attachment cannot
  start a new lifetime. Old handle and quota remain until safe supersession.
- Real independently compiled user-space supervisor consumes terminal results
  and requests restarts. The kernel does not own application restart policy.

See [ABI and trust boundary](../native-process-completion.md). The completion
table itself does not prove memory cleanup; the current adapter calls it only
after successful cleanup. General retryable cleanup ownership remains open.

## Verification

496 kernel tests pass in both debug and release;60 user tests pass in both
profiles. Five new kernel completion tests, two new user policy/decoder tests and
four new Python oracle tests cover identity/ABI/encoding/withheld-result failures.
The focused Python group passes55 tests. These are not the full canonical suite.

Seven user programs reproduce exactly across two builds. Six, including the
3569-byte shell, are unchanged from Cycle270. New supervisor code1084 bytes:
`D9D264314120710BAF7F7FA28C45D4AB54D15C2784138A9151295DDA2ABF6E7F`.
Supervisor ELF5392 bytes:
`38442ACFB263191260B0A08991419EAE2C7A7C19DFB9C24D1304F4731179DB20`.
No linker/extractor allowance was widened.

Three fresh QEMU/OVMF guests pass, each bounded at120 seconds:

1. Normal: two257-call child lifetimes, two retained Exit100 results, each withheld
   across one full owner budget dispatch. Supervisor exits0 after898 calls;
   survivor completes8193 calls, including122 dispatches after restart.
2. Independent normal boot repeats the full sequence. Both normal runs show154
   dispatches,308 CR3 writes,52 pages released,24 data pages scrubbed, no objects.
3. Invalid factory generation: no child admission/dispatch; supervisor exits170,
   prepared child cancelled, independent survivor completes, all resources freed.

Three live kernels bind855 source/build/oracle inputs. Independent normal kernels
match byte-for-byte. Normal profile111/208 pages; denied profile109. A fresh default
kernel build uses207/208 pages with36 guarded stack pages. Default RELRO padding
is24 bytes; adaptive segment layout and every profile need review before growth.
The default build was not booted here; no full-stack-bound or production claim.

Public receipt: `runs/native-process-completion-readiness.json`.
Native capture:344.266s; log SHA256
`0F2E695FF00EE8DEBEE15BD40F45D821D5FB20DB7FCC6F272453249A378D1A18`.
Kernel debug/release captures16.438s/16.578s; focused check1.328s; default build13.969s.
The independently parsed receipt and per-capture hashes are retained in the public
record. Generated compiler/media artifacts are preserved with per-member hashes
under the local evidence archive, not silently deleted or counted as cloud backup.

## Failure And Boundary

The first user-program build passed60 host tests per profile but its decoder
emitted forbidden GOTPCREL cross-crate linkage. The linker rejected it before
native execution. Explicit decoder inlining repaired it; the failed receipt/log
remain retained. Successful native runs completed within their original bounds.

The first256-test metadata replay failed five assertions: old cycle/schema
constants, architecture inventory643 instead of649, and a114-file current kernel
source inventory compared with the previous113. The frozen historical79-input
receipt remains unchanged; the new completion test is explicitly listed outside
that older coverage. Failure log SHA256:
`1CC0DDB6FD409CFBA0A90C9956BD3E310138AFC42F0EDAA44AE3DB8A504FF85F`.
A second replay exposed the same test's remaining Cycle270 qualification label;
the failure log is `74F6439E6FED8B41A5C6C1C59C29E6B50739D078B6DF23914BAD83E273B6F197`.
Both attempts are retained; no execution or release gate was relaxed.
The repaired metadata replay passed256 tests in52.843s (capture53.922s), log
`4F79F0FA62AD85D98DDD5D6304F7A8B75902872DA7C0EE024D59FAE67F0A3175`.
This group overlaps the focused tests and is not a full canonical release audit.
The first staged publication scan rejected the new receipt because its exact path
had not been registered. Registration adds only the sanitized public receipt;
raw/private sibling names, secrets and workstation paths remain rejected and are
covered by the boundary tests. The rejected scan/log remain local evidence:
`578602A9805B2B66C948F510C6551A6420804BCF1721B63D925BB75ED4F61717`.

The owner master checklist, live PooleGlyph Phase65 archive/report and all earlier
published readiness receipts remain unchanged. Phase66 Core IR metadata-boundary
audit is still pending. No private inputs, keys, firmware or physical media touched.

Next: wire shell start/stop/status to this lifecycle mechanism, retain actual
cleanup ownership on failure, and qualify native stop/fault completion. Review
the one-page program ceiling before adding file/app commands; do not simply raise
the byte cap without VM/admission/ownership changes. Then a read-only bundled-file
service, two useful separate apps, and fresh optical-ISO interactive acceptance.
Builtins and duplicated counters do not satisfy the app requirement.

Full canonical qualification and the three tracked kernel-load/transfer readiness
failures still block main qualification. PR branch backup is not a release gate.
