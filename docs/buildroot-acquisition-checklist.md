# Buildroot Acquisition Checklist

Status: draft v0.1

PooleOS Lab is scaffold-ready, not build-ready, until Buildroot and QEMU are installed or otherwise made available.

## Acquisition Options

Preferred first path:

1. Use an official Buildroot release archive or Git checkout.
2. Keep it outside the PooleOS source tree.
3. Pass the path to:

```powershell
.\lab-os\buildroot\scripts\run-build.ps1 -BuildrootPath C:\path\to\buildroot
```

Probe and configure-only evidence commands:

```powershell
.\lab-os\buildroot\scripts\run-build.ps1 -BuildrootPath C:\path\to\buildroot -ProbeOnly -ProbeReport .\runs\buildroot_probe.json
.\lab-os\buildroot\scripts\run-build.ps1 -BuildrootPath C:\path\to\buildroot -ConfigureOnly -ConfigureReport .\runs\buildroot_configure.json
```

If local PowerShell execution policy blocks direct script execution, run the same non-mutating probe through:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\lab-os\buildroot\scripts\run-build.ps1 -BuildrootPath .\sources\buildroot-2026.05 -ProbeOnly -ProbeReport .\runs\buildroot_probe.json
```

Current pinned baseline for lab bring-up:

- Buildroot tag: `2026.05`
- Local source path: `.\sources\buildroot-2026.05`
- Current probe status: `pass`
- Current configure status: `blocked` until WSL prerequisites are installed
- Official Git remote: `https://gitlab.com/buildroot.org/buildroot.git`
- Official download directory: `https://buildroot.org/downloads/`
- Probe expectation: `buildroot_version=2026.05`, `buildroot_git_tag=2026.05`, and a non-empty Git commit.

Alternative later path:

Use a pinned submodule or source mirror only after the public/private source-available boundary is decided.

## Host Requirements

- Python 3 for current PooleOS tooling.
- GNU make for Buildroot.
- Buildroot prerequisites for the host OS.
- QEMU `qemu-system-x86_64` for first boot validation.
- Enough disk space for Buildroot output.

On Windows, run preflight with `--include-wsl` so the report records both native PATH tools and the selected WSL distro's Linux-side tools.

Before installing anything in WSL, emit the non-mutating prerequisite report:

```powershell
python .\tools\pooleos_wsl_prereqs.py --buildroot-path C:\path\to\buildroot --out .\runs\wsl_prerequisites.json
```

The report includes an `install_command` string for operator review, but the command is not executed by PooleOS tooling.

Create the explicit operator action request:

```powershell
python .\tools\pooleos_operator_action.py --wsl-prerequisites .\runs\wsl_prerequisites.json --out .\runs\operator_action_request.json
python .\tools\pooleos_operator_receipt.py --operator-action .\runs\operator_action_request.json --wsl-prerequisites .\runs\wsl_prerequisites.json --out .\runs\operator_action_receipt.json
python .\tools\pooleos_host_prep_note.py --operator-action .\runs\operator_action_request.json --operator-receipt .\runs\operator_action_receipt.json --note-out .\runs\host_prep_note.md --manifest-out .\runs\host_prep_note.json
```

The action request repeats the exact command, records a SHA-256 hash of that command, and states that Codex did not execute it.
The receipt stays `pending_operator_action` until a later prerequisite report shows `status=pass` after the operator-approved host preparation.
The host prep note is the human-facing handoff generated from those two artifacts. Its manifest can be included in `pooleos_release_gate.py` with `--host-prep-note`.

After the prerequisite report reaches `status=pass`, run the WSL-gated configure step:

```powershell
python .\tools\pooleos_wsl_configure.py --buildroot-path C:\path\to\buildroot --prerequisites .\runs\wsl_prerequisites.json --output-dir .\output --out .\runs\buildroot_configure.json
```

If prerequisites are still blocked, this command writes a blocked `pooleos.buildroot_configure` report and does not invoke `make`.

After the configure report reaches `status=pass`, run the WSL-gated image build step:

```powershell
python .\tools\pooleos_wsl_build.py --buildroot-path C:\path\to\buildroot --configure-report .\runs\buildroot_configure.json --output-dir .\output --out .\runs\buildroot_build.json
```

If configure is still blocked, this command writes a blocked `pooleos.buildroot_build` report, does not invoke the image build, and records the planned rootfs path as `.\output\images\rootfs.ext4`.

Bind the probe, WSL prerequisite, configure, and build evidence into the lab image manifest:

```powershell
python .\tools\emit_lab_manifest.py --buildroot-path .\sources\buildroot-2026.05 --buildroot-probe .\runs\buildroot_probe.json --buildroot-configure .\runs\buildroot_configure.json --buildroot-build .\runs\buildroot_build.json --wsl-prerequisites .\runs\wsl_prerequisites.json --release-gate .\runs\release_gate.json --out .\runs\lab_image_manifest.json
```

## Readiness Stages

- `scaffold_ready`: PooleOS Lab files exist, but host build tools are missing or Buildroot path is not supplied.
- `configure_ready`: Buildroot path and GNU make exist, but QEMU is missing.
- `build_ready`: Buildroot path, GNU make, and QEMU are available.
- `blocked`: required PooleOS scaffold files are missing.

## Boundary

Do not claim a bootable image until a real QEMU serial log passes `validate_boot_log.py`.

Do not claim a configured Buildroot output directory until `pooleos.buildroot_configure` reports `status=pass`.

Do not claim a built rootfs image until `pooleos.buildroot_build` reports `status=pass` and `rootfs_image.exists=true`.
