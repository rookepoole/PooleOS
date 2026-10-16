# Cycle290: Early Serial Repair And VirtualBox Diagnosis

Date:2026-10-15. Previous goal turn: progress, with verified optical structure and
documented loading instructions. This cycle follows the owner's real demo friction
under N3/N5/N8/N12/N13/N18/N36/N39; it does not replace the full native charter.

## Observed Failure And Repair

VirtualBox7.2.20r175154 accepts the actual ISO as a SATA optical disc. A new,
isolated512MiB/one-CPU EFI64/ICH9 VM has HPET/APIC enabled, networking disabled,
no guest disk, host share, passthrough or clipboard. COM1 is captured; COM2 connects
only to a loopback listener. Each observation is bounded to120 seconds. Existing
VM registrations are unchanged; every test VM is stopped and unregistered while
its files remain available. No host security/firmware/driver settings changed.

The first setup attempt left APIC disabled when x2APIC was disabled in the same
CLI invocation. It failed before guest startup. A separate APIC-on command and
effective-configuration assertions corrected this. The next boot reached a
kernel panic, but serial diagnostics were absent. A repeat captured guest-only
RAM and the exact linked image's symbols/page tables recovered the early ring:
serial absent, six prepared tasks, USER-ROOT DENIED stage34365, panic0x101F.
The stack confirms the interactive dispatcher; stage34365 is its first slice
accounting check. The original run_slice failure still needs diagnosis. A marker
declaring CPL3 intent is not evidence that user-space execution succeeded.

`early_serial::probe` now waits for receive-ready before reading the sentinel,
rejects receive errors/wrong data, bounds polling at4096 and always exits loopback.
The same actual VirtualBox profile with the rebuilt ISO reports serial present
and the underlying panic directly after2.407 seconds. This verifies the serial
repair, not VirtualBox usability, timer/accounting recovery or native GUI support.
The UART contract is consistent with [TI's TL16C550C datasheet](https://www.ti.com/lit/ds/symlink/tl16c550c.pdf).

## Verification And Artifacts

Seven new Rust tests cover immediate/delayed/final-poll readiness, exact timeout,
floating-bus rejection, all four receive-error bits and wrong sentinel, including
normal-mode restoration on failure. Kernel suites pass561 default/580 application
tests per debug/release profile plus26 doctests. Host capture158.313 seconds,
SHA256 `C4138E2D93CFE1B0BA6BACB7021840B869B375106138CD9F5A73E0309F1AECF2`.

Six QEMU optical boots pass: two normal, stale Numbers authority, unsigned denial,
launcher and actual injected-key terminal adapter. The three main sessions and
launcher preserve exact native file waits, fault containment/restart and sustained
4096-dispatch six-role progress. Terminal557 input bytes/1897 response bytes match.
Optical capture358.469s; launcher69.984s; terminal41.078s. No timeout was raised.
Two clean application kernels reproduce and remain121/208 pages with36 stack pages.
Twenty retained Cycle289 user program pairs are unchanged/source-bound; they were
not rebuilt and their143-per-profile host tests were not rerun this cycle.

ISO: `outputs/cycle290-optical/PooleOS-UserSpace-Preview.iso`,66109440 bytes,
SHA256 `129F2232C8EE126A80C84CE71BDC9BD97DB925521275BE0C462D4224AB5E3E65`.
Public receipt: `runs/native-early-serial-readiness.json`,1742827 bytes,
SHA256 `23EEEC229EFAD8D953CB9984256B487732EB93AC46466725A595ED016A691D03`.
It binds932 execution inputs, current optical/terminal evidence, sanitized
VirtualBox observations and hashes of retained local artifacts. Raw VM configs,
guest core and host logs are not published. VirtualBox is the existing owner
installation, not a newly pinned or release-qualified development toolchain.

The source delta from the immutable Cycle289 receipt is one added native file
and four changed files. Prior receipts/images remain intact. Master checklist,
PooleGlyph Phase65 archive and owner conformance-report hashes are unchanged;
Phase66 remains the tandem language next step. The source-available IP boundary
and license are unchanged. Full canonical suite, default/diagnostic guest replay,
physical keyboard/hardware, signing, main merge and production are not claimed.

## Preserved Diagnostic Mistakes

The first core reader rejected omitted MMIO segments; it now skips zero-file-size
segments and requires present RAM for each read. The first instruction lookup
used a relocated address against the unrelocated ELF; relative-address lookup
identified the panic halt. Missing optional elftools was not installed; existing
LLVM and structured ELF decoding sufficed. The first receipt assembly wrongly
expected empty COM2; exact retained bytes are UEFI console prelude only, not the
native shell. Final assembly verifies that prelude. No failing guest became a pass.

The first focused metadata run executed331 tests with two failures in96.268s
(capture97.844s; SHA256
`9C17CC92E7F8824F9932C5A8169806EB32F1A9D665EAF5A193C0C0C4F4CE9CF8`).
Historical tests still expected128 live kernel source files and43 open flags.
The current source inventory is129, including the new early serial module, and
the new VirtualBox flag makes44 open. Exact historical receipt/input counts
remain unchanged; the current-source delta explicitly includes the added file.

The corrected focused metadata replay passes331 tests in94.956s (capture96.156s),
SHA256 `BE36722B97582D8EB8F9BD61987582CF615F16F0F1E32858CB339CB3BB2E7A3E`.
Both captures preserve source/owner inputs. Initial12-test preflight and the
two repaired assertions also pass. Suites overlap; none is full canonical.
Architecture binding now includes765 paths; all earlier receipts remain immutable.

## Next Move

`FLAG-N3-VIRTUALBOX-PREVIEW-001` stays open: expose the original slice/driver error,
repair the actual platform dependency with bounded failure/rollback tests, and
qualify a real VirtualBox shell/application session. Do not bypass runtime
accounting or disable host protections. Resume shell-issued waiting-stop and
interruptible jobs afterward; complete robust microkernel, all N0-N39, local
input/display, persistence, networking, PooleGlyph/PDC and PooleGlass remain.
Current inventory1486 Python tests is not execution. Final staged verification
is retained with the commit/PR closeout; full canonical and production remain open.
