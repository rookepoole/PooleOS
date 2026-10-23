# Cycle263: Console IPC Programs

2026-10-11. Build Plan2.166.0, N13-CAPABILITY-IPC-001, USI-3 partial.
The previous turn made verified progress: Cycle262 native console echo was pushed
as50843ec. This turn adds executable IPC service/client components, not a new guest
run or ISO. Kernel sources, fixed205/208 image geometry and36-page stack are unchanged.

## Implementation

`PooleConsoleService` owns UART policy and `PooleConsoleClient` is a separate echo
qualification client. PCS1 frames are32 bytes with strict kind/length/sequence,
reserved fields and unused-tail checks. PSABI1 send3/receive7 wrappers accept only
exact transfer lengths and validate the kernel-produced sender slot/generation,
zero reply token and payload size before decoding. Argument text supplies locators,
not authority. Expected peer identity must later be granted/bound by native admission.

One pending request/response bounds memory without allocation. Read consumes one
byte; Write accepts up to16 bytes with an owned cursor; Close waits for hardware
drain and a sent acknowledgement. Busy transport/device retains state and never
repeats successful output or consumed input. Fatal errors terminate the programs;
there is no resume-after-fatal-error guarantee. No second request is consumed while
a reply is pending. The client validates response kind/sequence and echoes all
non-EOT data through the service, then closes. It is not a shell or supervisor.

Thirty-three Rust tests pass in both debug/release, including12 new tests for wire
mutations/truncation, kernel envelope identity/token/length, startup metadata,
request/reply pressure, partial writes, close/drain, replay, device/transport failure,
client mismatch, sequence exhaustion and complete separate state-machine exchange
of255 non-EOT byte values under varying backpressure. The latter is a host model,
not native IPC execution. CI1-CI7: [frozen contract](../native-console-ipc.md).

## Exact Build Evidence

`runs/native-console-ipc-program-readiness.json`, SHA256:
`99129FBA86A8BDD2897CA17EAA4957C0BBED786D808B8B842CB5CFD188F7619D`.
27 source bindings; six compiler/linker/sysroot input hashes; two independent
offline locked builds with exact ELF/code equality. All programs have entry0,
one RX page, zero writable segments/imports/remaining relocations; object references
are local PC-relative. Actual new program identities:

| Program | Code Bytes | Code SHA256 |
| --- | ---: | --- |
| PooleConsoleService | 3032 | FE75D2A7C5D4DD6F39D0652645FDE81AE072108477D7BF61F4B96028F9040F4E |
| PooleConsoleClient | 1813 | DF9024F847386B40CFBC7D32D60663BA90CD758875DECAE775B937114D9F0441 |

Service ELF7344 bytes, SHA256
`D0A961BB96064120B10E1D324E8CE97D5CCC9706AF4AE986C2152868115FD74C`;
client ELF6120 bytes, SHA256
`E0BAE7FFE7EC9D59E330D9286BBE2EE272A8BA4E658D0B5C62EFBE5F04809579`.
The existing PooleInit, PooleCounter and PooleConsole ELF/code records match
Cycle262 exactly. This preserves binary identity, not fresh execution evidence.

Final build capture5.265s, source/owner snapshots unchanged, log SHA256
`6738CB5CD6735393BD7EDB53EE3EB3B8B9C18D99FC9A4135A18978E62E1C9929`.
Thirty focused Python tests pass (0.040s, capture0.735s), log
`2D565F15EFAF9611C497B445F7537E9FD07065D8ED026ACC5ECB8F29DC3126B2`.
No kernel rebuild or guest was run. Old native source-wide receipts remain historical
after user-program/harness changes. Full canonical regression was not performed.

The pre-closeout integration/roadmap suite passed 203 tests in 52.115s
(capture 53.125s), log SHA256
`F4AA07539D543A4715CAB0FDBC81B9013720FE7E6AEC32CBFB2FC3CD7C576AFB`.
The historical-evidence conservation suite passed 139 tests in 8.815s
(capture 10.297s), log SHA256
`5C70023CA4B603167DBD0B9F860BC15BB80D724F8D75EE44BF7B99622C6E194B`.
Both captures recorded unchanged source and owner-report snapshots. These suites
overlap and precede this result-recording edit; they are not a combined unique-test
count or the final-commit/full-canonical gate. The final staged-artifact check is
recorded separately in the PR closeout and local handoff to avoid self-rebinding.

## Retained Failures

- Attempt1 passed33 host tests in each profile but linking rejected generated
  memcpy/panic helpers and unsupported relocatable data (5.187s; log
  `B918D64F29552D4FD2D2012BFE7B30447A65C34649C0A5EA8C80A9F50F329385`).
  Bounded array construction and checked cursor/slices removed dynamic-copy and
  unchecked-index helpers without weakening linker/format gates.
- Attempt2 still rejected a peer-envelope loop's generated slice/add panic paths
  (4.407s; log `F1338278C8FEE6FF1DBF5FEFBE09565D8A346AF1C290B52B48824C7BDA081A6D`).
  Object relocation and panic-location data identified the exact line. Fixed-size
  chunk iteration removed those paths while preserving full envelope validation.
- Attempt3 linked, but object selection for PooleConsole also matched its new
  Service/Client prefixes (4.578s; log
  `E77F56647F550363DC67BA70D0B3E6F112DEF352F59E6E176310852434D8EAE9`).
  Exact binary-name/hash delimiter selection fixes this. A focused test verifies
  shared prefixes remain separate and missing/duplicate objects still reject.
- Attempt4 passed; final helper/test changes required a fresh attempt5 rather
  than rebinding its receipt. All attempts remain under cycle263 output names.

## Storage And Continuity

Initial C: free space was352563200 bytes. Twelve explicitly selected generated
build directories from cycles261/262 were archived. Member counts, paths and every
SHA256 were verified against originals before literal-path removal; reparse points
and archive escape/duplicate entries reject. Raw receipts/logs and canonical
standalone binaries remain. About610MB was recovered, to962764800 bytes before new
builds. Archive manifest hashes:
`A0CC83EA601E1BAABAED253FDE8C9988335E105DE4C0537F1C6DC0F72EFA1376`,
`680060944C258E14A0599949ECED5829E1700A32779D34FF8047ECBDC83AC9A2`.

User-program qualification now checks destination-volume free space before
creating output or invoking the toolchain, with a512MiB floor. It is a point-in-time
observation, not a reservation or guarantee against concurrent disk use. Five
preflight tests cover exact floor, shortage/no creation, nearest ancestor, invalid
floor/observation failure, and actual qualifier ordering. Broader kernel/guest
preflight and reproducible restoration remain under open storage risk; no automatic
deletion/retention is embedded in the build tool.

Live PooleGlyph remains Phase65 with Core IR boundary audit next; its checkpoint
and owner-modified report are untouched. Master checklist/execution ledger and
Cycle259-262 receipts remain byte-identical. Inventory1358 Python tests and589
architecture bindings is not test execution.40 phases301 subphases8996 requirements,
59 additions98 flags43 open20 gap groups are preserved; no phase/flag closes.

## Next

Admit service/client alongside init/counter in four private roots. Bind endpoint
handles and sender identities, explicitly account for52 image pages, and qualify
fresh serial input through real IPC, malformed requests, pressure, termination
and independent pair survival. Preserve fixed image/stack bounds or separately
review any required layout repair. Then implement the native shell, bundled files,
two useful applications, fault interaction and optical ISO acceptance. General
loading/supervision/restarts, efficient idle, resource policy, native clock recovery,
signed PXABI1/PINIT1, full robust microkernel, PooleGlyph/PDC and accessible PooleGlass
remain. Three known kernel-load/transfer readiness failures and full exact-candidate
canonical gates still block main. No merge/release/signing/hardware mutation.
