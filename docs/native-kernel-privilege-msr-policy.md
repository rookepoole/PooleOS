# Native Kernel Privileged-MSR Policy

`PKMSR1` is the Cycle 124, selector-7, opt-in `qemu64` proof for the bounded
N7.3 privileged-MSR policy. It extends `PKXFER1` without changing the ordinary
permanent stop-before-transfer profile.

## Frozen Boundary

One BSP performs support-gated `CPUID`, `CR4`, and `RDMSR` observations with
interrupts disabled, validates the snapshot in allocation-free `no_std` Rust,
emits the same receipt over serial and debugcon, and halts. An independent
Python oracle revalidates the markers and all retained `PBP1` bytes.

The read set is:

- `EFER`, `STAR`, `LSTAR`, `CSTAR`, and `SFMASK` when SYSCALL is advertised;
- `FS_BASE`, `GS_BASE`, and `KERNEL_GS_BASE` in long mode;
- `TSC_AUX` only when RDTSCP is advertised;
- `MCG_CAP` and `MCG_STATUS` only when MCE and MCA are both advertised;
- `MCG_CTL` only when `MCG_CAP.CTLP` is set.

The measured `qemu64` profile does not advertise RDTSCP, so `TSC_AUX` is not
read. It reports ten MCA banks, `MCG_CAP=0x000000000100010A`, and
`MCG_CTL=0xFFFFFFFFFFFFFFFF`. Bit 24 and the all-ones control value are frozen
as emulator compatibility observations only; they are not assigned AMD
architectural meaning and are not generalized to hardware. The profile
performs no MCA bank read. It does not clear retained error state.
The qemu64 profile advertises neither architectural PMU version nor AMD
PerfMonV2, so no performance MSR or `RDPMC` access is allowed and `CR4.PCE`
must remain clear.

## Transaction Rules

System-linkage reset values are not trusted. AMD defines several of them as
undefined. This profile therefore requires the emulator's early linkage,
and FS/GS state to be inactive, but does not generalize those values to
physical hardware. `TSC_AUX` remains unobserved because its support gate is
closed.

Future syscall activation must validate entry assembly, selectors, stack,
exception containment, and return semantics; program canonical linkage and
per-CPU bases; read everything back; then set `EFER.SCE` last. Authority cannot
exist before the whole transaction passes.

Future machine-check activation must bind product-specific bank semantics,
snapshot valid status and status-qualified address/miscellaneous data into
retained storage before clearing anything, and fail closed on context
corruption, lost overflow evidence, recursion, or incoherent per-CPU state.

## Source Boundary

The normative architecture source is AMD64 Architecture Programmer's Manual
Volume 2, publication 24593, revision 3.44, March 2026. The captured PDF is
12,560,767 bytes with SHA-256
`3D9DCB3F68222392D0EDE9970EFC95E31A047A247D54B454123D6981D278C48C`.
It is not redistributed. QEMU's official x86 CPU-model documentation defines
the compatibility-model boundary; live CPUID remains the executable gate.

## Nonclaims

This is not syscall entry, `SWAPGS`, per-thread FS/GS ownership, per-CPU
`TSC_AUX`, a machine-check handler, MCA recovery, PMU ownership, AP state,
target-hardware qualification, user mode, release, or production evidence.
PKMSR1 executes zero MSR or control writes. The shared linked kernel contains
43 `RDMSR` sites: twenty in the established CPU/entry policy paths, one each in
the separately selected PKSMP1 and PKSMP2 lifecycles, and three isolated to the
selector-14 PKSMP5 protected-mode trampoline, long-mode trampoline, and BSP
transaction; selector-18 PKSCHED4 reuses those exact sites without adding a
privileged instruction site. Six more are isolated to the PKSCHED1 live context probe, which
observes FS base, GS base, and kernel GS base before and after switching.
Six more are isolated to the PKSCHED2 preemption launcher, which performs the
same before-and-after FS/GS observation around the exact interrupt-frame switch.
Six more are isolated to PKSCHED3: three in worker preparation and three in
worker clearing, binding before-and-after FS/GS ownership around deferred work.
It contains two typed `IA32_APIC_BASE` `WRMSR` sites in the separately selected
PKIRQ1 `InterruptTime` branch and one `IA32_EFER` long-mode-enablement write in
the separately selected selector-14 PKSMP5 trampoline, also reused by selector-18
PKSCHED4. Source and per-function linked
audits bind every isolation. There are zero signatures, authority grants, authorized
actions, firmware calls, and physical-media writes in this profile.
