# PKCPU1 read-only CPU policy

## Scope

`PKCPU1` is the first bounded PooleKernel CPU discovery and control-state policy milestone. It maps checklist requirements `020.1` and `020.2` into partial N7.1 and N7.3 evidence without claiming N7 completion. The profile is opt-in, QEMU-only, BSP-only, terminal, and non-promoting.

PooleBoot feature `development-cpu-policy` extends `PKXFER1`, selects value `4` in the existing `R10` development-scenario field, and remains mutually exclusive with the three `PKTRAP1` profiles. Feature-disabled PooleBoot still stops before transfer. Selector `0` still performs the unsigned `PKXFER1` terminal denial, and selectors `1..3` retain their frozen trap meanings.

## Observation boundary

After PKENTRY1, PBP1 intake, runtime-state validation, and independent PKREVAL1 complete, the kernel performs only:

- fixed CPUID leaf and subleaf reads for vendor, brand, family, model, stepping, baseline and optional features, address widths, cache, topology, thermal, performance, random-instruction, virtualization, encryption, MCE/MCA, invariant-TSC, and XSAVE discovery;
- read-only `MOV` from CR0 and CR4;
- `XGETBV(0)` only when CPUID reports OSXSAVE, which reflects an already-enabled CR4.OSXSAVE state;
- typed `RDMSR` wrappers for IA32_EFER, IA32_APIC_BASE, IA32_PAT, IA32_MTRR_CAP, and IA32_MTRR_DEF_TYPE, each gated by the corresponding architectural prerequisite.

There is no `WRMSR`, `XSETBV`, CR0 write, CR4 write, microcode application, firmware call, device access, interrupt enable, or return to PooleBoot in this profile.

## Fail-closed policy

The Rust kernel and independent Python oracle both enforce the following first-slice rules:

- vendor must be `AuthenticAMD` or `GenuineIntel`; brand bytes must be printable ASCII followed only by optional NUL padding;
- CPUID must expose basic leaf 7 and extended leaf `0x80000008`, a valid decoded identity, at least one logical processor, physical width 36 through 52, and 48-bit linear addresses;
- FPU, TSC, MSR, PAE, CX8, APIC, MTRR, PGE, CMOV, PAT, FXSR, SSE, SSE2, SYSCALL, NX, and long mode are mandatory;
- CR0 must have PE, MP, ET, NE, WP, and PG set and EM, TS, NW, and CD clear;
- CR4 must have PAE, OSFXSR, and OSXMMEXCPT set; PGE capability is mandatory but activation may wait for kernel global-page ownership; LA57, VMXE, SMXE, PKE, CET, and PKS are forbidden in this Tier 0 profile;
- UMIP, FSGSBASE, PCIDE, OSXSAVE, SMEP, and SMAP may remain disabled, but any enabled bit must have matching CPUID support;
- CPUID.OSXSAVE, CR4.OSXSAVE, leaf `0xD`, and XCR0 must agree; when observed, XCR0 must include x87 and SSE and no unsupported component;
- EFER must show active long mode and NX, reject unknown bits, and leave SVM disabled;
- the MSR read set must equal the five-entry allowlist; APIC base, PAT memory types, MTRR capabilities, default type, enable state, and fixed-range dependency must pass reserved-bit checks.

Optional-disable behavior is deliberate. Discovery is not activation, and an unavailable optional feature is not a failure unless the current control state tries to enable it.

## Evidence

`tools/qualify_native_kernel_cpu_policy.py` independently builds the canonical PooleKernel twice, builds default and `development-cpu-policy` PooleBoot profiles twice, proves profile isolation, creates the same ordinary workspace image twice, and boots it twice under the pinned `qemu64`, `pc-q35-11.0`, single-vCPU TCG Tier 0 profile with fresh copied OVMF variable stores. It requires exact serial/debugcon markers, screenshot bytes, and PBP1 bytes across both runs and reuses the PKLOAD6 and PKREVAL1 transcript-binding oracles.

The six PKCPU1 markers cover discovery, topology/cache, features, XSAVE, control/MSR state, and the zero-effect terminal result. Forty-one hostile controls mutate marker structure, selector, identity, widths, required features, feature-state relationships, CR0/CR4/EFER/XCR0, every MSR policy class, and all zero-authority result fields. The committed readiness record is `runs/native-kernel-cpu-policy-readiness.json`.

The qualified Tier 0 observation is `AuthenticAMD`, family 15, model 107, stepping 1, with 40-bit physical and 48-bit linear addresses. It observes CR0 `0x80010033`, CR4 `0x668`, EFER `0xD00`, APIC base `0xFEE00900`, PAT `0x0007040600070406`, MTRR capability `0x508`, MTRR default type `0xC06`, and the exact five-entry MSR read mask. These values are frozen as two-run qemu64 evidence, not target expectations.

## Claim boundary

The pinned `qemu64` model is intentionally limited and QEMU does not recommend it as an optimal or secure production CPU model. Exact two-run Tier 0 agreement therefore tests determinism and policy plumbing, not the AMD Ryzen 7 9800X3D target.

Target family/model/stepping acceptance, a public Granite Ridge revision guide, microcode revision policy, errata mitigations, AP-local discovery, x87/SSE/AVX/XSAVE context ownership, dynamic state transitions, target firmware, and physical-hardware measurements remain open. The existing sanitized Windows Tier 1 inventory is planning evidence only and is not consumed as native PKCPU1 qualification. No part of this receipt authorizes signing, publication, production promotion, firmware mutation, driver loading, or physical-media writes.

## Normative references

- AMD64 Architecture Programmer's Manual Volume 2, revision 3.44: <https://docs.amd.com/v/u/en-US/24593_3.44_APM_Vol2>
- AMD CPUID Specification, publication 25481 revision 2.34: <https://www.amd.com/content/dam/amd/en/documents/archived-tech-docs/design-guides/25481.pdf>
- QEMU x86 CPU models: <https://www.qemu.org/docs/master/system/qemu-cpu-models.html>
- AMD Ryzen 7 9800X3D official support page: <https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen/ryzen-9000-series/amd-ryzen-7-9800x3d.html>
