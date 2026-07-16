# Native Tier 0 QEMU/OVMF Qualification

Status: Cycle 88 non-promoting foundation evidence. N4 remains partial.

## Purpose

`POOLEOS-TIER0-Q35-1` is the first native-only emulator contract for PooleOS. It replaces the historical Buildroot launch path for all forward native work. QEMU and OVMF remain host development inputs; neither is a PooleOS production component.

The contract freezes:

- versioned `pc-q35-11.0` rather than the moving `q35` alias;
- TCG with one thread, `qemu64`, one vCPU, and 512 MiB RAM;
- virtual UTC RTC plus fixed `icount` settings;
- read-only OVMF code flash and a fresh writable variables copy for every launch;
- no default devices, guest network, host share, passthrough, vhost, VFIO, USB redirection, or host accelerator;
- modern non-transitional VIRTIO block over PCI;
- file-backed serial, debugcon, QEMU trace, and ISA debug-exit channels;
- an opt-in loopback-only GDB overlay;
- dry-run launch by default and no arbitrary QEMU arguments.

## Supply-Chain Lock

`specs/native-tier0-lock.json` distinguishes three things which must not be conflated:

1. The current upstream source target is QEMU `11.0.2`, tag object `0AB45D2A...`, commit `E545D8BB...`. Local release-signature verification remains open.
2. The bounded Windows runner is Stefan Weil's `20260422` package, which reports QEMU `11.0.0` at provider commit `A4BB4B10...`. Its exact installer, executable, and complete extracted runtime tree are hashed.
3. The runner's bundled OVMF traces to QEMU's EDK II submodule commit `4DFDCA63...`, not the newer target `edk2-stable202605` commit `B03A21A6...`.

The installer's SHA-512 matches the publisher record. Its Authenticode certificate is expired and is explicitly not an acceptance signal. Production promotion requires source-rebuilt QEMU and OVMF, verified provenance, notices, SBOM, vulnerability review, redistribution review, and second-builder reproduction.

The Android emulator binary and the provider's QEMU `11.0.50` development build are exact-hash negative candidates. Neither can substitute for the accepted runner.

Primary references:

- QEMU releases and signing key: `https://www.qemu.org/download/`
- QEMU system invocation: `https://qemu.readthedocs.io/en/v11.0.0/system/invocation.html`
- EDK II stable releases: `https://github.com/tianocore/edk2/releases`
- VIRTIO 1.3: `https://docs.oasis-open.org/virtio/virtio/v1.3/virtio-v1.3.html`

## Workspace-Local Acquisition

The runtime belongs below ignored `.toolchains/`; it must not be committed, installed globally, or added to global `PATH`.

The current evidence was acquired by downloading `qemu-w64-setup-20260422.exe`, verifying its published SHA-512, and extracting the NSIS package without executing it. The expected extracted root is:

```text
.toolchains/qemu-w64-20260422-extracted/
```

The qualifier rejects a different installer name, size, SHA-256, SHA-512, QEMU executable, version line, q35 capability, required device capability, firmware byte, or runtime-tree byte.

## Qualification

Run:

```powershell
python .\tools\qualify_native_tier0.py
python .\tools\validate_artifact.py .\runs\native_tier0_readiness.json --schema .\specs\native-tier0-readiness.schema.json
python -m unittest tests.test_native_tier0 -v
```

Qualification performs no PooleOS boot. For each of the two profiles it:

1. builds the normalized command twice and requires identical hashes;
2. creates a private temporary placeholder block file and a fresh OVMF variables copy;
3. starts q35 with `-S`, so no guest CPU instruction begins;
4. connects to a temporary loopback QMP endpoint;
5. enables QMP, requests quit, and requires a clean response;
6. verifies the variables copy still matches the immutable template;
7. repeats the probe and compares normalized QMP summaries.

Cycle 88 passes four of four paused machine instantiations and 18 of 18 negative controls. The evidence records zero boot claims and no absolute local path.

## Launching Native Media

The launcher accepts no free-form QEMU arguments. It is dry-run-only unless `--execute` is explicitly supplied.

```powershell
python .\tools\run_native_tier0.py `
  --profile bootstrap-debug `
  --media .\runs\native-tier0\media\pooleboot-native.img `
  --run-dir .\runs\native-tier0\launch-001
```

Secure-firmware preparation uses:

```powershell
python .\tools\run_native_tier0.py `
  --profile secure-firmware-prep `
  --media .\runs\native-tier0\media\pooleboot-native.img `
  --run-dir .\runs\native-tier0\launch-secure-001
```

`--debug` adds paused loopback GDB at `127.0.0.1:1234`. `--execute` launches the process with the media read-only and writes the receipt under the run directory. Every run directory must be new or empty, and every OVMF variables file is copied from the locked template.

The launcher always leaves boot, serial-validation, debug-exit, Secure Boot, PooleKernel, and production claims false. Later protocol-specific evidence must validate those facts from exact serial and exit receipts.

## Open N4 Work

- source-build QEMU `11.0.2` and OVMF `edk2-stable202605`;
- replace the Windows candidate's unavailable guest-memory-dump disable control;
- boot original PooleBoot media and validate serial/reset/debug-exit behavior;
- add symbol, LLDB, snapshot, packet, and disk-capture workflows;
- stage the remaining VIRTIO 1.3 console, net, input, GPU, RNG, balloon, and IOMMU profiles;
- add malformed ACPI, SMBIOS, PCI, VIRTIO, USB, storage, and network campaigns;
- add executable capability, IPC, scheduler, page-map, boot-slot, rollback, and PooleFS models;
- cross-check model traces against implementation traces;
- reproduce the exact tool closure on a second clean host.

No item in this document proves PooleBoot boot, PooleKernel execution, a VIRTIO driver, Secure Boot, guest determinism, N4 completion, or production readiness.
