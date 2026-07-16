# Boot Readiness Checklist

PooleOS Lab may only be called bootable after these checks have current evidence.

## Image

- [x] Buildroot defconfig draft exists.
- [x] Root filesystem overlay draft includes `/opt/pooleos`.
- [ ] Python runtime is present.
- [x] QEMU launch script scaffold exists.
- [x] Serial boot log marker contract exists.
- [ ] Serial boot log is captured from a real QEMU boot.

## Runtime

- [ ] `pooleos_doctor.py --no-runtime` passes inside the image.
- [ ] `pooleos_release_gate.py` passes inside the image against a bundled artifact.
- [ ] A replay proof is emitted inside the image.
- [ ] Artifacts are exported outside the image.
- [ ] Serial log passes `validate_boot_log.py`.

## Boundaries

- [ ] Report explicitly says production_ready is false.
- [ ] No safety/security/physical-device claims are made.
- [ ] Source-available/commercial-rights-reserved posture is preserved.
