# Native PooleKernel Transfer (`PKXFER1`)

## Scope

`PKXFER1` is the first live PooleBoot-to-PooleKernel control transfer. It is an opt-in, QEMU-only development proof for `N5-KERNEL-TRANSFER-001`; it is not the authenticated production entry profile and it does not complete N5 or N6.

The ordinary PooleBoot build remains fail-closed at `POOLEBOOT/0.1 STOP BEFORE TRANSFER`. Only a build with Cargo feature `development-transfer` can arm `PKXFER1`. The feature-enabled path accepts only the exact unsigned development envelope already produced by `PKLOAD6`, independently executes `PKREVAL1` in PooleKernel, records the expected `pbtrust_policy_unsigned` denial, and halts. It grants no capability or operational authority.

## Ownership Boundary

After successful `ExitBootServices`, PooleBoot makes no boot-service or protocol call. This follows the UEFI ownership boundary described by the [UEFI 2.11 System Table chapter](https://uefi.org/specs/UEFI/2.11/04_EFI_System_Table.html) and the current-`MapKey` and retry rules in [UEFI 2.11 Boot Services](https://uefi.org/specs/UEFI/2.11/07_Services_Boot_Services.html).

PooleBoot then validates and records exactly one development transfer:

1. Final PBP1 bytes are unchanged after successful `ExitBootServices`.
2. The retained PKMAP2 root, stack, handoff mapping, and kernel entry are nonzero, aligned, canonical, and mutually bound.
3. Only CR3 PWT/PCD low bits inherited from firmware are permitted; PCID remains disabled by PKMAP2's CPU profile.
4. Signature verifications, authority grants, actions, state writes, and post-exit firmware calls are all zero.
5. A one-shot lifecycle changes from `Armed` to `Dispatched`; replay rejects.
6. No PooleBoot instruction is expected to run after the terminal jump.

## Entry ABI

The transfer uses the integer-register subset of the [System V AMD64 ABI](https://gitlab.com/x86-psABIs/x86-64-ABI/-/blob/master/x86-64-ABI/low-level-sys-info.tex):

| State | Value |
|---|---|
| `RDI` | canonical virtual address of exact immutable PBP1 bytes |
| `RSI` | exact PBP1 byte count |
| `RDX` | little-endian `PBP1` magic as `u64` |
| `RSP` | 16-byte-aligned exclusive bootstrap-stack top |
| `CR3` | retained PKMAP2 root plus only permitted PWT/PCD bits |
| `IF` | clear |
| `DF` | clear |

PooleBoot executes `cli`, `cld`, installs CR3 and RSP, and jumps to the PBP1-bound entry. The PooleKernel assembly wrapper repeats `cli` and `cld`, validates the incoming stack without a language call, captures CR3 and RFLAGS in `R8` and `R9`, then calls the Rust entry using a correctly aligned stack. Intel instruction and control-register semantics are anchored to the [Intel 64 and IA-32 Software Developer Manuals](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html).

## Kernel Intake

PooleKernel accepts this development path only when the normal authenticated `validate_kernel_entry_profile` rejects and the exact development profile passes. That profile requires:

- `DEVELOPMENT_MODE | BOOT_SERVICES_EXITED` and no other boot flags;
- exactly core, memory-map, optional framebuffer, and loaded-artifact records;
- exactly ten artifact descriptors and no random-seed or signature records;
- null UEFI system-table and runtime-service pointers;
- exact runtime entry, handoff address and length, stack, CR3 root, IF, and DF continuity;
- one kernel entry only.

PooleKernel then reparses six PBART1 files and their inner contracts, PSM1, PBTP1, and PBTS1 directly from the nine retained byte ranges. It reconstructs the retained-set digest and PBTRUST1 observation instead of accepting PooleBoot's summaries as authority.

## Evidence Protocol

Each successful qualification run contains 30 ordered markers: 23 pre-transfer PooleBoot markers, `TRANSFER_ARM`, the one-way boundary, and five PooleKernel markers:

1. `POOLEOS:KERNEL:ENTRY PASS`
2. `POOLEOS:KERNEL:STATE PASS`
3. `POOLEOS:KERNEL:PBP1 PASS`
4. `POOLEOS:KERNEL:PKREVAL PASS`
5. `POOLEOS:KERNEL:TRANSFER-DENIED PASS`

PooleKernel sends identical CRLF-normalized bytes to COM1 and QEMU debugcon. The qualifier requires exact channel equality, reconstructs the PBP1 transcript independently, binds it to the media oracle and all transfer-critical fields, reruns PKREVAL1 in Python over the exact nine files, and requires guest/host equality.

Run the focused qualification with:

```powershell
python tools\qualify_native_kernel_transfer.py
```

The generated public receipt is `runs/native-kernel-transfer-readiness.json`. The qualifier performs two clean PooleKernel builds, two clean feature-enabled PooleBoot builds, a separate feature-disabled isolation build, two byte-identical media generations, two fresh-vars QEMU/OVMF runs, exact marker/frame/PBP1 comparisons, and 57 hostile marker controls.

The receipt also binds the current standalone PKENTRY1, PKREVAL1, and default
PKLOAD6 receipts. Any upstream kernel, retained semantic artifact, trust record,
or ordinary stop-path refresh therefore makes PKXFER1 stale until the complete
live proof is rerun.

## Remaining Work

`PKXFER1` does not validate an authenticated production PBP1 profile, target firmware, physical hardware, persistent state, a second independent builder, an ISO, or production promotion. The framebuffer still relies on the inherited firmware translation and cache attributes; final remapping and revocation remain mandatory. Descriptor tables, exception containment, memory management, capabilities, scheduling, IPC, initial user space, PooleGlyph, PDC, drivers, and PooleGlass remain downstream work.

The owner's broader authorization for signing and privileged operations is recorded separately. It removes an approval category but does not supply a FIDO2 key, safe target identity, backups, qualification evidence, or permission to bypass any charter gate.
