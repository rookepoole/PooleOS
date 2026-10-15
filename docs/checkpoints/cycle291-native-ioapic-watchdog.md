# Cycle291: Owned Interrupt Routing And VirtualBox User Space

Date:2026-10-15. Previous goal turn: early serial repair exposed the first-slice
failure. Current move follows the owner's unusable ISO report under
N3/N5/N8/N12/N13/N18/N36/N39; the complete native charter remains active.

## Root Causes And Implementation

The file is a real ISO9660 image with an EFI El Torito boot entry. VirtualBox
accepts it as optical media. Its HPET timer0 configuration reports
`ffffffff00000030`: no FSB/MSI capability. The mandatory watchdog previously
rejected first user entry, then the accounting check hid that original error.
Failure-only serial diagnostics now preserve the original timer/entry error.

The new noncopyable I/O APIC lease selects only a pristine masked nonlegacy
GSI16..31 advertised by HPET and excludes MADT overrides/NMIs. It validates
controller version/identity, serializes selector/window access on the sole BSP
at IF0, publishes ownership before effects and verifies writes. Stop order is
HPET source, masked route, APIC IRR/ISR drain, HPET restoration, route/ID restore.
Failures retain ownership for retry. This is not a general shared IRQ allocator.

VirtualBox's MADT advertises controller ID1 while the register is reset0. Only
that reset identity may be initialized, and only after every redirection entry
is proved pristine and rechecked immediately before writes. Nonzero foreign IDs,
active routes and changed hardware are rejected. The original ID is restored.
The third device page is supervisor RW/NX, uncached and non-RAM with absent
guards; full leaf and physical-alias audits include it. Ordinary timer probes
retain their two-page plan. The continuous clock binds the complete child plan
but maps only its own APIC/HPET pair; exact child equality remains enforced.

Longer VirtualBox sessions also exposed budget yields whose actual start/end
HPET counter was equal. A fixed4096-read loop accepts the first real positive
sample. Stalled/regressing counters, changed periods and read failures reject;
no tick is fabricated and terminal/wait zero-duration semantics are unchanged.
Watchdog diagnostics report actual MSI or I/O APIC transport. Existing frozen
MSI summaries remain compatible; new routed evidence explicitly names the route.

The interrupt design was checked against the
[Intel HPET specification](https://www.intel.com/content/dam/www/public/us/en/documents/technical-specifications/software-developers-hpet-spec-1-0a.pdf),
[ACPI MADT definitions](https://uefi.org/specs/ACPI/6.5/05_ACPI_Software_Programming_Model.html), and
[Intel I/O APIC register descriptions](https://cdrdv2-public.intel.com/631120/631120-002.pdf).
Oracle's device source was read as a behavior reference; no external implementation
was copied. PooleOS source-available licensing and PooleGlyph IP boundaries are unchanged.

## Verification

15 added Rust tests cover six route cases, two HPET route cases, three mapping
cases and four bounded-yield cases, including every modeled after-effect write
failure and retry. Final kernel suites:576 default and595 application tests in
both debug/release plus26 doctests. Final host capture32.843s,
SHA256 `30A162C610D213608D6459F0C7FEE33F961F3ADF02F2B7F08CB58127F9024161`.
The focused transport-oracle suite independently passes63 Python tests.

Two complete QEMU default diagnostic boots with MSI disabled prove actual
I/O APIC watchdog delivery/recovery plus subsequent IPC/clock/task cleanup;
1111 hostile-marker cases reject per run. Ordinary boot denial also passes.
Final capture331.828s, SHA256
`D21027914270D65060C0DE93733D015882833E5E2E01A801622791454623DA74`.
Five further QEMU boots cover two normal optical application sessions, stale
file authority, ordinary denial and launcher self-test. Application kernels
reproduce independently.20 retained Cycle289 program pairs remain byte/source
bound; user programs and their host tests were not rebuilt/replayed this cycle.

Two fresh VirtualBox7.2.20r175154 sessions pass the strict application oracle,
native file waits, exact557-byte input/1897-byte output, fault/restart and4096
dispatches of six-role progress. Both mount the same final ISO read-only.
Each uses512MiB/oneCPU, EFI64/ICH9, HPET/APIC on, x2APIC off, no guest network,
disk, host shares or passthrough; COM2 connects only to loopback.240-second guest
bounds are fixed before execution. Both VMs stop/unregister and prior owner
registrations remain unchanged. Raw configs and host logs remain local.
The existing owner VirtualBox install is not a pinned release-qualified tool.

The immutable public receipt `runs/native-ioapic-watchdog-readiness.json` binds934
execution inputs, exact ISO/kernel hashes, captures and sanitized guest evidence.
Local captures are `outputs/cycle291-*.json`; final media is
`outputs/cycle291-opticalfinal/PooleOS-UserSpace-Preview.iso`. The local launch pointer
is advanced only after these checks. Prior receipts/images remain immutable.

Final ISO:66109440 bytes, SHA256
`CEB2794D7E63739E31EE827BFDA65F99C38BD3B24D9A09B36554933FABC14E00`.
Public receipt:2213987 bytes, SHA256
`751C324F30A25ADC146D0DD558F2134937E741076FA13711D1755920B400C691`.
Final optical capture233.641s; VirtualBox captures50.203s/48.75s with guest
observations43.172s/42.984s; launcher57.796s. The public receipt records exact hashes.

## Failed Attempts Retained

Early compile failures exposed a shadowed page count, a changed two-page clock
API and an unused diagnostic proof. The ordinary default image initially grew
to210 pages against its208-page limit; outlining the constructor alone did not
help. Shared noinline log emitters reduced it to207 without increasing any
layout/stack bound. Final application image is121 pages, guarded stack36 pages.

Initial VirtualBox attempts successively exposed no MSI, reset controller ID
and zero-tick yields. One completed command scenario was not accepted by the
host oracle because firmware clear-screen escapes preceded the ENTRY marker on
the same line. The helper now removes only that exact observed three-sequence
prefix and then validates every complete marker; no marker is synthesized.
The first routed QEMU diagnostic recovered the watchdog but failed stage4098
when the continuous clock expected a two-page child plan. The complete child
plan fix is covered by both final successful default guest runs.

Default VirtualBox diagnostics still fail stage117 in peer scheduler checks.
The exact cause is not established; do not call it timing merely because the
profile is faster. This is not a full VirtualBox diagnostic pass or proof of
actual watchdog interrupt delivery there. Two helper failures occurred before
useful default-guest evidence: invocation after a failed build and encoding an
already-bytes completion marker. All are preserved, not counted as successes.

## Owner Inputs And Next Move

Master checklist SHA256
`A8C94719FAF9428C1F133010BA2603C0270C4E1EFD7327AF8EAB9C8C362ABB3D`,
PooleGlyph Phase65 archive
`F3CCEB701CF76274D9464A0958BF6106888FB34F3C0BFBD55DE4ACE03C427ABC`,
and owner conformance report
`F75E4836FAA9DDD59BA62648FE9542415F2119B659A583FB3F5959F2F5CAE87B`
were rechecked and unchanged across captures. Phase66 CoreIR audit remains the
tandem language next step. No owner file was modified.

Keep `FLAG-N3-VIRTUALBOX-PREVIEW-001` open: package reproducible source-bound
VirtualBox serial launch for the owner, investigate stage117 without weakening
assertions, and separately qualify actual VirtualBox watchdog recovery. Then
resume waiting-stop and interruptible jobs. Full N0-N39 microkernel, PDC,
PooleGlyph, local input/display, storage/networking and PooleGlass remain.
No GUI, physical keyboard/hardware, signing, release, main merge, production
layout or full canonical qualification is claimed. Python inventory1488 is not
execution; final metadata/publication closeout is recorded separately.

## Metadata Preflight

The initial10-test preflight ran13.406s with two failures: the new VirtualBox
assertion compared total COM2 capture to shell-only bytes, and the architecture
schema still capped bindings at765. Raw COM2 is2019 bytes: the exact122-byte
observed firmware prelude plus1897 shell bytes. Tests now bind both the precise
prefix and these separate counts, without dropping arbitrary output. The schema
requires exactly769 bindings after the four new explicit paths; it is not relaxed
to an unbounded inventory. Native guest evidence and previously published receipts are unchanged.

The first333-test metadata run then failed two stale source assertions in103.588s
(capture105.422s, SHA256
`954BED3EE5EF65DBC8C16D750F2241BC443306E3C1B9F70C2841DFC578FD79E0`).
The historical source-delta set now explicitly includes both I/O APIC files.
The application calibration test now requires exactly one watchdog-aware timer
constructor followed by exactly one fresh calibration-cache setup for both
initial launch and restart. Its old literal constructor name was stale; the
requirement is not weakened. Because that test is execution-fingerprinted, the
earlier successful candidate is retained locally and the final source fingerprint
receives fresh qualification rather than inheriting an unrecorded rebind.

The earlier uncommitted receipt remains byte-for-byte in
`outputs/cycle291-pre-metadata-readiness.json`, SHA256
`45196800A89813172CA3C9313FB229895F6A78CBCA96C525A94EF90318BAAEC2`.
Its sole changed execution input is the calibration source test. Fresh host,
routed-kernel, optical, two VirtualBox and launcher runs pass for the corrected
fingerprint; the complete ISO is byte-identical. Initial evidence is not relabeled.
The corrected calibration/source-delta preflight passes23 tests in1.115s.

Final focused metadata replay passes333 tests in104.176s (capture105.375s),
SHA256 `954F9D6C2407F0753FF2F398FF14A68161B12EB7190811B31BC66A62D3EA6822`.
Both failed and passing captures preserve their before/after source and owner
inputs. Architecture now binds769 paths; execution binds934. Suites overlap and
are not the full canonical run. Final staged/publication verification is retained
with the commit/PR closeout. A hash-verified convenience copy of the exact ISO is
provided in Downloads as `PooleOS-UserSpace-Preview-Cycle291.iso`.
Run focused source-fixture preflight before expensive guest captures next cycle.

The initial staged closeout passed120 tests in24.794s and all binary/history
checks, then the publication scan rejected the new ledger as not yet explicitly
public (2009 paths, one `private_run_artifact` violation). Capture90.375s,
SHA256 `59464D04E9C0869DC286563D0B43A9C8F2BD9F02C39A93ACD6EA76BC0E8D15EC`.
Only the sanitized exact ledger path is added to the existing allowlist. Tests
require its raw/private sibling paths and secret/user-path content to remain
rejected. No wildcard, secret scanner or private-vault rule is relaxed. These
publication-test changes do not change the934 execution inputs or ISO bytes.
