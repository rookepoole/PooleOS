# Native Kernel Target Errata Policy

PKERR1 is the Cycle 121 policy-only boundary for `N7-ERRATA-POLICY-001`.
It freezes the exact Ryzen 7 9800X3D identity, direct-product firmware
security floors, mandatory feature rejection, RDSEED handling, source
applicability, and unresolved errata and microcode evidence gates.

PKERR1 does not read or write an MSR, load a driver, stage microcode, change
firmware, or authorize kernel activation. The no_std Rust evaluator lives in
`native/cpupolicy`; an independent Python evaluator reproduces every decision.

## Exact Target

- vendor: `AuthenticAMD`;
- CPUID signature: `0x00B40F40`;
- decoded family/model/stepping: `26/68/0` (`1Ah/44h/0h`);
- product: AMD Ryzen 7 9800X3D, Granite Ridge, Zen 5;
- target profile: `TIER1-B650M-9800X3D-RTX5070-001`.

The sanitized Windows CPUID transcript is evidence of a bounded host
observation. It is not native per-processor qualification.

## Firmware Floors

AMD-SB-7033 names `ComboAM5PI 1.2.0.3c` for Granite Ridge microcode-signature
verification mitigation. AMD-SB-7055 names `ComboAM5PI 1.2.0.3i` and
`ComboAM5PI 1.2.8.0` as remediated Ryzen 9000 versions for the Zen 5 RDSEED
failure. PKERR1 therefore uses `1.2.0.3i` as the combined comparison floor and
still requires a stable board-vendor firmware mapping.

For GIGABYTE B650M GAMING PLUS WIFI revisions 1.0/1.1/1.2, the first recorded
stable release meeting the stronger direct-product floor is F39 with AGESA
1.2.8.0. For revision 1.3 it is FA7 with AGESA 1.2.8.0. Exact board revision is
still unknown, so the current target fails before either lineage can be chosen.
The observed F32/AGESA 1.2.0.2b state is below both combined floors.

No BIOS image was downloaded or flashed. GIGABYTE's displayed four-character
checksums are recorded as non-cryptographic metadata and are not file identity
or authenticity evidence.

## Microcode And Errata Gaps

Windows reports normalized revision `0x0B404023` for all 16 logical processor
registry records. That is an unprivileged OS report, not a direct
`MSR_PATCH_LEVEL` observation, and AMD does not publish it as a client security
floor in the applicable sources. PKERR1 forbids promoting it into one.

AMD document 58251 is a Revision Guide for Family 1Ah Models 00h-0Fh. The
target is Model 44h, so PKERR1 rejects 58251 as target errata evidence. The
public-source audit did not locate an applicable Family 1Ah Models 40h-4Fh
revision guide. N7.2 remains partial until an applicable AMD guide or reviewed
vendor response and a defensible microcode-floor rule are bound.

## RDSEED Boundary

AMD-SB-7055 identifies the 16-bit and 32-bit RDSEED forms as affected on Zen 5;
the 64-bit form is not affected. Before remediated firmware is proven, PKERR1
allows only masking RDSEED from discovery or a reviewed 64-bit-only path that
treats zero as failure and retries. Unknown handling fails closed.

## Current Decision

The current target is denied for exactly six reasons:

1. exact motherboard revision is unknown;
2. F32 is below the stable board-firmware floor;
3. AGESA 1.2.0.2b is below the combined AMD security floor;
4. the Windows revision is not trusted native per-processor evidence;
5. no applicable direct AMD numeric client microcode floor is bound;
6. no applicable public Model 44h revision guide is bound.

The denial creates zero authority grants, zero authorized actions, and zero
state writes. A synthetic all-true fixture exists only to prove that each
validator branch is reachable; it is not target or trust evidence.
