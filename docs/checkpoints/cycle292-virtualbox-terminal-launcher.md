# Cycle292: VirtualBox Terminal Launcher

Date: 2026-10-15. Contract: PVBPREVIEW1. Scope: qualified local unsigned serial
preview, not production, a native desktop or general VirtualBox support.

## Delivered

- `Launch-VirtualBox-Preview.cmd`, `tools/launch_native_virtualbox.py` and
  `runtime/native_virtualbox.py` provide a durable owner-facing launcher.
- Admit only the current source-bound PUSIISO1 ISO and recorded VirtualBox
  7.2.20r175154 runtime. Thirteen files are hash-checked before/after execution.
  Origin is the existing owner installation; no tool install, redistribution,
  Extension Pack dependency or complete host/driver attestation is claimed.
- Create a fresh UUID, retain its expected config path, and verify effective
  settings plus XML before headless start. Only the ISO and owned serial paths
  are attached. No guest network, disk, shares, USB, passthrough or remote display.
- Pause completed sessions, validate actual native markers and PBP1/media binding,
  then verify ownership before stop/unregister. Retain all VM files and logs.
  Existing registrations must match before/after. No global process kill or delete.
- Manual use runs the existing Terminal adapter, with guest escapes sanitized.
  It is explicitly separate from the strict self-test qualification.

## Final Evidence

Public receipt: `runs/native-virtualbox-launcher-readiness.json`, 2506243 bytes,
SHA256 `7CF22EE9BC0A24C53294DDE8FBAD2F64B59AC958E723256F3152515608DC98A6`.
It binds 939 execution inputs and links all retained local capture hashes.

- 32 new synthetic lifecycle/parser tests; 134 focused Python tests pass in 8.165s.
  Coverage includes identity collisions, disabled interfaces, XML additions,
  runtime mutation, after-effect creation/start failures, stop/unregister failures,
  interruption, transport-close failure and noncritical telemetry separation.
- Final optical qualification passes in 234.703s: two normal application sessions,
  stale-file-grant control and ordinary unsigned trust-denial boot, on QEMU/OVMF.
- Two durable VirtualBox self-tests pass in 50.172s and 49.516s. Each validates
  20 native file-wait pairs, exact 557-byte input/1897-byte native response,
  4096-dispatch six-role progress, native fault/restart and hostile marker controls.
  Raw VirtualBox output includes a separate 122-byte firmware prelude.
- Actual Terminal adapter completes 557 injected keystrokes in 32.641s. A separate
  injected Ctrl+] exits after the 31-byte prompt in 8.735s. These are real VM/adapter
  runs, not evidence of a person typing in a visible host window.
- QEMU launcher regression passes in 58.610s. Final count: five QEMU guests and
  four VirtualBox guests. All final captures preserve source and owner report.
- All four VirtualBox sessions verify stopped/unregistered, unchanged prior
  registrations and unchanged runtime/ISO/source identity. Logs stay local.

Native kernel sources did not change this cycle. The fresh independent optical
builds produce the exact Cycle291 ISO: 66109440 bytes, SHA256
`CEB2794D7E63739E31EE827BFDA65F99C38BD3B24D9A09B36554933FABC14E00`.
The 20 source-bound Cycle289 user-program pairs are reused, not rebuilt; no new
host kernel/user Rust test execution is claimed. Architecture binds 776 paths.
Python inventory 1521 is not full canonical execution. Metadata and final staged
verification are additional focused checks, not a promotion gate.

Focused metadata verification passes 366 tests in 111.667s (112.937s capture),
log SHA256 `9D40A1098E2271C9A4D65ABB9FEFC811A81F4A671FBD8CB6BB53B6C08FB8C680`.
The preceding 366-test run had one stale expectation naming the completed
launcher as the current next task; its failed log is preserved with SHA256
`7D2EF927C6C18BDCA441B3B26B768DED3876842148DFA318CD38F24F43E3A020`.
Only that roadmap expectation changed; all 939 execution bindings remain exact.

## Preserved Failures

The first host pass had five synthetic-session fixture errors: a missing socket
address and misuse of reserved `Mock.name`. Corrected before guest execution.
The first optical candidate passed but was superseded after launcher repair.

The first VirtualBox launcher reached application execution, then failed parsing
running-state `VideoMode="1024,768,32"@0,0 1` and `VRDEClients==0`. Full telemetry
parsing also blocked cleanup. The original failed receipt remains unchanged.
Its UUID, name and config path were reverified and that exact VM was stopped and
unregistered; the separate recovery confirms unchanged previous registrations.

The parser now recognizes those exact formats. More importantly, pause/shutdown
use bounded, duplicate-rejecting ownership/state fields without depending on
optional telemetry. Unknown optional reporting cannot block owned shutdown.
New regression cases and a fresh complete current-source replay pass.

## Continuation And Boundaries

The owner's `.iso` is a real EFI El Torito ISO9660 image. Windows' DVD image label
does not change its format. The optical-drive picker accepts it; the virtual
hard-disk picker is the wrong attachment type. The launcher removes that setup
step for this tested host. No physical-media write or host firmware change occurs.

`FLAG-N3-VIRTUALBOX-PREVIEW-001` remains open. Default VirtualBox diagnostics
still have the previously observed stage117 failure; actual fallback watchdog
interrupt delivery there is not qualified. Next: diagnose that kernel diagnostic
failure without weakened assertions, qualify recovery, then resume shell-issued
waiting stop and interruptible jobs. Abrupt controller-process death cleanup,
real human input, standalone packaging and other host/runtime versions also remain.

Use Ctrl+] for normal shutdown, not forced terminal-process termination. Manual
guest limit 900s, self-test 240s, each control command 30s; setup/cleanup separate.
The loopback host transport is not native desktop input. Storage persistence,
networking, isolated drivers, accessible PooleGlass, PooleGlyph/PDC and all N0-N39
microkernel/production work remain. No canonical suite, main merge, signing,
release, production layout or hardware qualification is claimed.

Master checklist hash and Phase65 PooleGlyph checkpoint/conformance hashes were
rechecked unchanged. No owner source or checkpoint was modified. 40 phases,
301 subphases, 8996 source requirements, 59 additions, 99 flags/44 open, 20 gap groups.

Primary references: Oracle [VBoxManage](https://docs.oracle.com/en/virtualization/virtualbox/7.2/user/vboxmanage.html)
and [VM configuration](https://docs.oracle.com/en/virtualization/virtualbox/7.2/user/working-with-vms.html).
