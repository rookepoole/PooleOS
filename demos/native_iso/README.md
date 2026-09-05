# PooleOS Native Optical Demo

An unsigned QEMU-only ISO containing real PooleBoot and PooleKernel, plus the
demo-only PooleGlass static boot renderer. No Linux kernel, GRUB, web desktop,
installer, physical-media writes, persistent guest disk, host share, or network.

The presentation is intentionally separate from `native/`: a small Cargo
workspace compiles the existing PooleBoot entry source and dependencies while
substituting only the pure `identity_rgb` pixel function. The canonical kernel
remains SHA-256 `9029AEE51A4D557EF5B29945985E4A1F07C67DDE9C8C367C80BD1B9EDD9D409E`.
Production loader source, defaults, qualification runners and receipts are not
modified to admit a different boot screen. This demo does not close N5, N29 or N39.

## Run The Local Demo

After building and qualifying, open `Launch-PooleOS-Demo.cmd` on this workstation.
It uses the existing workspace runtime and a clearly labeled host capture viewer.
Headless QEMU boots the actual ISO; the viewer holds its actual captured boot
image for eight seconds, then shows the actual native kernel diagnostic console.
QEMU stops after validation. Close the viewer when finished. The pause is
host-controlled presentation, not a boot-time or animation measurement.

The unchanged kernel replaces the splash with its early diagnostic console.
`POOLEOS:KERNEL:LOCKS-RESULT PASS contract=PKLOCK1` means the bounded diagnostic
completed. This is not an interactive desktop or live guest input surface. Closing
the viewer early cancels the demo and may produce a cancellation message; it
does not write to a physical disk. `--auto-close` supports a bounded launcher test.

The pinned QEMU Windows SDL display path crashed during local testing, including
with OpenGL disabled. Its underlying host crash cause remains unresolved; that
path is disabled in this launcher. The replacement uses the qualified headless
emulator and Tk/Pillow to show actual QMP captures, not simulated guest output.

Manual entry using an available Python runtime with Pillow:

```powershell
python -B demos/native_iso/launch.py
```

The default package is `outputs/native-demo-iso-pooleglass-v1/`. The launcher
requires that exact local ISO, source-image binding, build receipt, qualification
receipt, and compiled pixel oracle. A copied ISO can boot independently in a
compatible UEFI VM, but other hypervisors and physical machines are unqualified.
Do not flash this optical-only ISO to USB or use it as an installer.

## Rebuild And Qualify

Prerequisites: the repository's pinned Rust/Windows linker and QEMU/OVMF closures,
Python 3.11+, and Pillow for host-side PNG evidence conversion. `bootstrap.py`
downloads only the hash-pinned, host-only pycdlib wheel into the dedicated demo
tool directory; it does not install globally or change PATH. The wheel and its
license remain host-side, outside the ISO.

```powershell
python -B demos/native_iso/bootstrap.py
python -B demos/native_iso/build.py --out-dir outputs/my-demo-build
python -B demos/native_iso/qualify.py --package-dir outputs/my-demo-build
python -B demos/native_iso/launch.py --package-dir outputs/my-demo-build
python -B -m unittest discover -s demos/native_iso -p "test_*.py" -v
```

Use a new output directory for each build. Earlier attempts are retained, never
overwritten. Qualification uses fresh OVMF variables twice, only a read-only
El Torito CD-ROM, a loopback-only QMP channel, no guest NIC, and no host disk.
It checks the complete existing PKLOCK1 marker grammar, equal serial/debug PBP1,
media bindings, and exact rendered pixels against the compiled host oracle.
This is one-host/two-run evidence, not independent implementation or second-host
reproduction. Diagnostic markers here are unsigned.

`package.py` validates only this fixed five-file ISO profile. With its required
source disk during qualification, it validates the existing GPT/FAT32 payload,
the exact embedded ESP and manifest, and the canonical kernel identity. Without
that disk its inspection is structural only. It is not a general ISO parser,
signature verifier, arbitrary download scanner, or the production release gate.
Local SHA-256 receipts detect accidental substitutions; they are not authenticated
release metadata. Do not use the launcher with untrusted build directories.

`build.json`, `qualification.json`, `SHA256SUMS.txt`, raw PPM frames, real PNG
captures and serial/debug logs are local evidence in the output directory.
The first screenshot attempt captured the later kernel console and failed;
qualification now captures the actual splash at `FRAME READY`, then separately
requires kernel completion. No pixel validator was relaxed to accept the console.

## Design And Remaining Work

See `docs/pooleglass-design-system.md` and `specs/pooleglass-design-tokens.json`.
The original artwork, compact data, generation prompt, encoding receipt, and
typography notice are in `boot/assets/`. The guest has no PNG or font parser for
the boot image. Native compositor materials, animation, user preferences, trusted
UI and full accessibility remain explicit open work under `FLAG-NATIVE-UI-001`.

Automated production CI still qualifies the canonical native products separately.
This demo requires its additional build and optical qualifier; passing the
existing aggregate gate alone is not evidence that a new demo ISO works.
Public release signing, second-host reproduction, target hardware, installer,
hybrid media, and production promotion are not part of this deliverable.
