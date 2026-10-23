# Cycle 262: Native User Console

Date: 2026-10-11. Plan: 2.165.0-native-user-console. Move:
N13-CAPABILITY-IPC-001, USI-3. Development branch only; not a release or ISO.

## Outcome

PooleConsole now runs as independently compiled original Rust at CPL3 alongside
PooleInit and PooleCounter in three private roots. The kernel authenticates each
PSABI1 byte-port call against task/root/root-generation and an exclusive,
generation-tagged COM2 lease. User code configures the UART, handles bounded
transmit/receive backpressure and echoes actual host input. There is no kernel
command interpreter or scripted interactive transcript.

Six kernel console tests cover all 2048 register/value write combinations,
wrong/stale/type/root/generation handles, no-effect rejection, nonwrapping lease
generations, admission rollback and preservation of existing authority. Byte I/O
permits no IRQ/DMA enabling, raw-port selection or user IOPL. Trusted quiescence
disables interrupts and resets FIFOs after admission and after revocation. Driver
detach revokes authority before image memory is returned.

The independently compiled user library has 21 tests in each of debug and release,
including startup decoding, UART sequencing, error handling, buffering and EOT
drain/exit. Seven Python console tests attack observations, echo/prelude byte
handling, host pacing, feature boundaries and guest launch options. Existing
program/session tests remain in the default regression.

Frozen UC1-UC7 predicates and alternatives are in
[the console contract](../native-user-console.md). The implementation chooses a
small polled UART driver first; virtio/framebuffer/input-seat ownership remains
future work. Console IPC, shell and efficient idle are not implemented here.

## Exact Native Evidence

Public receipt: `runs/native-console-readiness.json`, SHA256
`1EAE64B23ACA07915F011368E693FCB9012BFD528C3B7A051A67D5AEE804C87B`.
It embeds the unchanged final console capture and fresh default regression.
Console bindings: 820; default regression: 815; program build: 21. Local raw
captures remain under `outputs/cycle262-console-fourth` and
`outputs/cycle262-regression-live-second`; these local paths are not public
artifact availability promises.

Two independent program/kernel builds match byte-for-byte. No user ELF has imports,
writable segments or remaining relocations; object references remain local
PC-relative. Each program fits one RX page, entry offset0:

| Program | Code Bytes | Code SHA256 |
| --- | ---: | --- |
| PooleInit | 1073 | C18D6E5D0D66F11ED9DCB0018B196E0D442BC21F2CE51C92430756CDEA6F13C0 |
| PooleCounter | 1113 | CA8EEC284AA0E65FC462439B2594313ABC1F7F7CBD01CF85667C78324AEE7A12 |
| PooleConsole | 1288 | 91C9B3747E73DE9612D13222A6F2D13B4657A53C40E806DC9358245573507583 |

Console kernel: 763400 bytes, SHA256
`EAE96FDBBE682A1D5E0AD314308B84A7EC75A414DE31D6E6DC9EC7EBC9BF102D`.
Bad-handle kernel SHA256
`3F79E2C76740FB49A5103A501997B9DCD47C1E70AFFE55CA2680A06F61E49403`.
Fixed image geometry stays205/208 pages and guarded stack36 pages. The console-only
task-image quota is48 pages, increased from32 to admit three13-page images. The
default diagnostic quota stays32; no image/stack or timeout enlargement.

Three fresh, read-only, network-disabled QEMU/OVMF guests, no host acceleration,
each bounded120 seconds with separate loopback COM2 capture:

| Guest | Input / App Output Bytes | Console Exit | Final Dispatches | Pair Calls | Console Calls | Pages After Reap |
| --- | --- | ---: | ---: | --- | ---: | ---: |
| Positive1 | 55 / 75 | 0 | 512 | 759 / 760 | 8388 | 26 |
| Positive2 | 53 / 73 | 0 | 512 | 763 / 764 | 8260 | 26 |
| Bad handle | 0 / 0 | 131 | 512 | 1023 / 1020 | 2 | 26 |

Positive inputs differ and include binary/log-like text. Application output must
equal the20-byte banner plus exact host input. The separate275-byte observed
firmware/loader prelude is retained, strictly token-validated and never counted as
trusted kernel evidence. Two alive and two post-retirement observations establish
console budget progress and independent pair survival;13 pages are reclaimed,
retired console counters stop. Each run rejects60 hostile marker mutations. Kernel
COM1/debugcon acceptance streams match independently. Native timer preemption was
not observed in these polled runs: positive budget yields131/129; preemptions0.
This is not native cached-timer spinner qualification or an uptime claim.

Final console capture:68.656s, log SHA256
`7BD6A6BC662A09CDCB80F70210DFA2A5286137B2B48BF27C48BEF64CC28D66E5`.
The final default regression took402.188s and passed22 checks:1698 overlapping Rust
test executions and99 Python oracle tests. Console-feature kernel tests477 debug
and477 release are included; the default kernel count is471. Two fresh79-marker
diagnostic boots preserve17 survival cases and1111 hostile-marker rejections each,
with the original150-second guest bound. Ordinary unsigned denial still prevents
kernel entry. Regression log SHA256
`3077E5856014FA9E3E96A111F8E0F861BD2EC85B4DCF34EFD066F1429ADE050D`.
Source and owner-report snapshots were unchanged during each accepted capture.

## Failures And Reconstruction

- The first program link exposed GOTPCREL references across the user-library
  boundary. Inlining small syscall/bootstrap/driver wrappers restored local
  PC-relative code without weakening the linker or relocation audit.
- A first focused host-test compile used whole-Scheduler equality without its
  required traits. The assertion now compares the existing summary and validates
  invariants; production traits were not added just to satisfy the test.
- An initial formatting command used the virtual workspace manifest with no
  target. Formatting was rerun through the actual kernel/user manifests.
- Console attempt1 rejected OVMF escape output before the user banner (45.766s,
  log `C761B277EEA70E43AE880A01D5968620C7145A0A997651A0E9BDC292B40A5E0F`).
  Attempt2 exposed fixed BdsDxe/PooleBoot text (44.985s, log
  `F274AE995B5C62F5E95B042A8C7AB95FC23C68A5A1D368F521F261290A0D818C`).
  Prior qualified diagnostics and boot source confirmed the exact tokens. The
  parser now preserves a4096-byte-bounded whitelist and fails unknown prefixes;
  it does not strip arbitrary output. Added rejection/fragmentation tests.
- Attempt3 passed (72.125s), then a rollback test and qualification source changed.
  Its receipt was retained as superseded; attempt4 rebuilt/re-executed the final
  source. No old execution was rebound to new sources.
- Default-regression attempt1 failed after401.562s with OSError28 (disk full).
  Log `B4E87E7C6B027B49B6F1D191975B2F864980E4ABDCFCA9DB60719935A18E0663`.
  It is not a qualified run even though earlier checks/guest loops progressed.
  The zero-length ordinary-denial image and failed receipt remain. Nineteen
  archives preserve only this cycle's superseded/failed generated media and build
  directories. Every member was counted and SHA256-compared before deleting its
  uncompressed original, with resolved path/reparse-point checks. About825MB was
  recovered. Archive manifest SHA256
  `FB3C2DDEAABA01377D9CF6CCB3EB2611A6381B7946F6C9D9CF151EDB1A8A4242`.
  An initial directory-parent lookup error stopped the helper after six images;
  no unverified directory was removed. The corrected helper verified existing
  archives before proceeding. A fresh full retry passed; acceptance bounds did
  not change. New open storage/preflight risk remains, not automatically closed.

## Progress And Boundaries

The initial staged-artifact replay passed52/54 tests (105.602s; capture106.609s).
The index scan and its release-boundary wrapper both rejected the same new public
receipt, whose exact filename had not been allowlisted. No other violation was
reported. Added only `runs/native-console-readiness.json` to the public ledger
allowlist/ignore exception, retaining content scanning. Tests explicitly keep its
raw/private siblings, secrets and workstation paths rejected. Failed log SHA256
`764A1D8CDC639821E484FE0F9E924DC6139EC915A26C3FB4A23916D4D069657D`.

The initial metadata run passed195/196 tests (51.785s; capture52.750s), failing
only an older test's assertion that the *current* next move has N13/N14 phases.
The current console/shell lane also involves N16/N22. That assertion was moved
into Cycle262 coverage with the exact expanded phase list; historical guest
digests/oracles were unchanged. Failed log SHA256
`DF0270E9F3E67F489B815B9DFAC538A8A10280840B1BBBA3F997A14ADE87CC6B`.

Pre-closeout metadata/oracle replay:196/196 pass,51.861s, capture52.843s, log SHA256
`C8C754AC7D15C317DCA3251C9703EF89AD28210BCEA80F6C34E825DF0C8EE1F6`.
Conservation:132/132 pass,8.882s, capture10.359s, log SHA256
`A6B89BB0F678BE2223559CBDA98A0F71062AC381A24D3C19C6720978FFFF30AE`.
Counts overlap; source/owner snapshots stayed unchanged during each capture.
These results precede serialization of their own summaries, not exact-final-commit
or full canonical qualification. Final staged-artifact/publication results belong
to the associated PR and local closeout capture. Test discovery alone is not
execution. Inventory:1351 Python tests,
580 architecture source bindings. Master checklist remains8996 requirements,
40 phases301 subphases59 additions20 gap groups. No phase or existing flag closes;
new `FLAG-N36-EVIDENCE-STORAGE-001` makes98 flags,43 open.

PooleGlyph remains Phase65; its owner-modified conformance report and checkpoint
archive were not changed. The original master checklist, execution-source ledger
and Cycle259/260/261 receipts remain byte-identical. Older program/session records
are explicitly historical after source changes, not silently promoted.

Next: console IPC queues/backpressure and authenticated clients, then native shell,
bundled-file service, two useful applications, fault/survivor interaction and fresh
optical ISO acceptance. Full init supervision, restarts/general loading, resource
policy, efficient idle, native clock recovery, signed PXABI1/PINIT1, PooleGlyph/PDC,
accessible PooleGlass and all N0-N39 obligations remain. The205/208 image margin,
three known kernel-load/transfer readiness failures and exact-candidate canonical
qualification still gate main. No merge, release, signing, hardware mutation or
physical-media write is authorized by this receipt; no usable ISO is claimed.
