# Owned VirtualBox Pointer Qualification

Cycle297, PVBMOUSE1. This is an emulated-device verification path, not a new
guest driver, host pointer controller, general automation endpoint or production
hardware qualification. PWS1 surface authority and PWINPUT1 remain unchanged.

## Interface And Provenance

The installed VBoxManage 7.2.20 help lists keyboard injection and screenshot
commands, but no mouse injection. Oracle's [SDK reference](https://download.virtualbox.org/virtualbox/7.2.2/SDKRef.pdf)
documents relative IMouse.putMouseEvent and shared session locking. The installed
SDK constants confirm Shared=1, Running=6 and Unlocked=1. Compatibility is tested
against the installed runtime, not inferred solely from the older API document.

A PowerShell helper uses the installed COM interface for one relative event.
No SDK package is installed, execution policy changed, global PATH changed,
webservice enabled or host cursor moved. The existing 19-file visible VirtualBox
runtime check remains required. A separate profile pins the PowerShell executable;
this is scoped runtime identity, not complete PowerShell/OS/DLL attestation.

## Invariants

- VBM-1: only a newly created and admitted OwnedVm may construct the adapter.
  The helper validates canonical UUID, exact generated name, config path and
  Running state before locking and again through the shared session.
- VBM-2: validate the two COM class registrations and their exact installed
  server paths before object creation. Use a shared session, never a settings
  write lock; unlock in finally and require confirmation before recording success.
- VBM-3: accept integer relative x/y deltas in [-96,96], a boolean left button,
  zero wheel movement and at most 96 events. Do not expose arbitrary COM calls,
  absolute motion, host input, keyboard injection or machine control here.
- VBM-4: each helper process has a five-second limit and exact event/identity/
  sequence acknowledgement. An error, timeout or unconfirmed effect poisons the
  channel; never retry an event. Parent cleanup retains exact VM ownership checks.
- VBM-5: screenshots belong to the owned output directory, have bounded geometry
  and size, and convert actual RGB pixels losslessly into the shared PPM oracle.
  No synthetic screenshot can establish native execution.
- VBM-6: the same 17-step cursor/focus/drag/minimize/restore plan and whole
  keyboard/application/recovery challenge must pass. API acknowledgement is not
  pointer success. Keep 240-second guest and 12-second observation limits.

## Scope

One-byte and four-character keyboard modes have separate outcomes. Each complete
run checks 573 challenge characters with zero serial input, a discarded key while
a read-only application has focus, exact application/file/lifecycle responses,
4096-dispatch all-six-role progress, final pixels, runtime hashes and owned cleanup.
Movement count depends on guest geometry; every bounded intermediate position
requires observed cursor pixels, not just injection acknowledgement.

Actual outcomes and retained failures belong in the Cycle297 checkpoint and
receipt. No Rust source, guest authority, code-page limit or image/stack budget
changes are implied. The 40-byte window-service code margin, lifecycle/restart
recovery, general application input, overload/reset telemetry, accessible
PooleGlass, full microkernel, PooleGlyph/PDC and N0-N39 gates remain open.
