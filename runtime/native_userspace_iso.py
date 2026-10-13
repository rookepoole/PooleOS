"""Unsigned native user-space optical preview; packaging is not execution proof."""
from __future__ import annotations
import copy
import hashlib
import io
import struct
from demos.native_iso import package as authoring
from runtime import native_iso_media as media, native_kernel_load as load, native_pooleboot as boot

CONTRACT = 'PUSIISO1'
VOLUME = 'POOLEOS_USERSPACE'
PRIMARY_NAME = 'PooleOS-UserSpace-Preview.iso'
SUSTAINED_DISPATCHES = 4096
README = (b'PooleOS Native User-Space Preview\r\n'
          b'Unsigned development image for the pinned one-CPU QEMU/OVMF profile.\r\n'
          b'The native shell, files, Text and Numbers operate through COM2.\r\n'
          b'No installer, persistence, networking, local desktop or hardware qualification.\r\n'
          b'Not a production release. Do not write this optical-only image to physical media.\r\n')


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def optical_profile(base: dict) -> dict:
    result = copy.deepcopy(base)
    args = result['base_argument_template']
    drive = 'if=none,id=pooleos_media,format=raw,readonly=on,file=$MEDIA'
    device = 'virtio-blk-pci-non-transitional,drive=pooleos_media'
    if args.count(drive) != 1 or args.count(device) != 1 or result['machine']['vcpus'] != 1:
        raise ValueError('unexpected one-BSP base media profile')
    args[args.index(drive)] = drive + ',media=cdrom'
    args[args.index(device)] = 'ide-cd,drive=pooleos_media,bus=ide.0,bootindex=1'
    result['devices']['required'] = ['ide-cd' if d == 'virtio-blk-pci-non-transitional' else d
                                     for d in result['devices']['required']]
    result['optical_preview'] = dict(contract_id=CONTRACT, read_only=True, physical_media=False)
    return result


def optical_esp(disk: bytes) -> tuple[bytes, dict]:
    inspection = load.inspect_media_bytes(disk)
    start, end = boot.ESP_START_LBA * 512, (boot.ESP_END_LBA + 1) * 512
    esp = bytearray(disk[start:end])
    # The El Torito image begins at its own LBA zero, unlike the source GPT ESP.
    for offset in (28, 6 * 512 + 28):
        if struct.unpack_from('<I', esp, offset)[0] != boot.ESP_START_LBA:
            raise ValueError('source ESP hidden-sector count changed')
        struct.pack_into('<I', esp, offset, 0)
    return bytes(esp), inspection


def manifest_for(disk: bytes, inspection: dict, variant: str) -> dict:
    if variant not in ('applications', 'bad-file', 'ordinary-denial'):
        raise ValueError('unknown optical preview variant')
    return dict(contract_id=CONTRACT, version='0.1.0-development', variant=variant,
        profile='qemu_ovmf_one_bsp_native_applications', interface='COM2_serial',
        optical_only=True, signed=False, production_ready=False, installer=False,
        persistence=False, networking=False, local_desktop=False, physical_hardware_qualified=False,
        source_disk_sha256=sha(disk),
        files={v['path']: {k:v[k] for k in ('sha256','byte_count')} for v in inspection['files']})


def build_iso(disk: bytes, license_text: bytes, variant: str = 'applications') -> tuple[bytes, dict]:
    if not isinstance(license_text, bytes) or not 0 < len(license_text) <= 65536:
        raise ValueError('bounded license notice required')
    esp, inspection = optical_esp(disk)
    manifest = manifest_for(disk, inspection, variant)
    payloads = {'EFI.IMG':esp, 'MANIFEST.JSON':boot.canonical_json_bytes(manifest),
                'README.TXT':README, 'LICENSE.TXT':license_text}
    library = authoring.load_library()
    with authoring._fixed_authoring_clock():
        iso = library.PyCdlib()
        try:
            iso.new(interchange_level=3, sys_ident='POOLEOS', vol_ident=VOLUME,
                    pub_ident_str='ROOKE POOLE', preparer_ident_str='POOLEOS', app_ident_str=CONTRACT)
            streams = []
            for name, data in sorted(payloads.items()):
                stream = io.BytesIO(data); streams.append(stream)
                iso.add_fp(stream, len(data), iso_path='/'+name+';1')
            iso.add_eltorito('/EFI.IMG;1', bootcatfile='/BOOT.CAT;1', platform_id=0xef,
                             efi=True, boot_load_size=1, media_name='noemul')
            out = io.BytesIO(); iso.write_fp(out); data = out.getvalue()
        finally:
            iso.close()
    return data, inspect_iso(data, disk, license_text, variant)


def inspect_iso(data: bytes, disk: bytes, license_text: bytes, variant: str = 'applications') -> dict:
    expected_esp, source = optical_esp(disk)
    inventory = media.inspect(data)
    outer, inner = inventory['iso'], inventory['esp']
    if inventory['structural_issues'] or inventory['esp_path'] != 'EFI.IMG':
        raise ValueError('optical filesystem has structural issues')
    if set(outer) != {'EFI.IMG','BOOT.CAT','MANIFEST.JSON','README.TXT','LICENSE.TXT'}:
        raise ValueError('optical namespace differs')
    if data[16*media.BLOCK+40:16*media.BLOCK+72].rstrip(b' ') != VOLUME.encode():
        raise ValueError('optical volume identity differs')
    manifest = manifest_for(disk, source, variant)
    expected = {'EFI.IMG':expected_esp, 'MANIFEST.JSON':boot.canonical_json_bytes(manifest),
                'README.TXT':README, 'LICENSE.TXT':license_text}
    if any(outer[name]['data'] != blob for name,blob in expected.items()):
        raise ValueError('optical payload differs from its bound source')
    decoded = {p:dict(sha256=sha(v['data']),byte_count=len(v['data']))
               for p,v in inner.items() if v['data'] is not None}
    if decoded != manifest['files']:
        raise ValueError('independently decoded native files differ')
    return dict(contract_id=CONTRACT, iso_sha256=sha(data), byte_count=len(data),
        esp_sha256=sha(expected_esp), source_disk_sha256=sha(disk), variant=variant,
        kernel_sha256=decoded['EFI/POOLEOS/KERNEL.ELF']['sha256'],
        files=decoded, structural_issues=[], source_disk_bound=True,
        optical_only=True, signed=False, production_ready=False, native_execution_verified=False)


def development_architecture(data: bytes) -> dict:
    from tools.check_native_iso_architecture import scan_iso
    production = scan_iso(data)
    # The unchanged release policy requires the future production tree. The
    # preview uses the loader's exact PKLOAD6 tree; retain every release failure.
    expected = {'esp:/pooleos/'+p for p in ('PooleKernel.elf','system/initial-system.bundle',
                                          'recovery/recovery.bundle','manifest.json')}
    violations = production['violations']
    if (not production['structural_passed'] or len(violations) != 4
            or {v['path'] for v in violations} != expected
            or any(v['type'] != 'required_path_missing_or_empty' or v['rule'] != 'required_paths' for v in violations)):
        raise ValueError('preview has violations beyond the explicit release-layout mismatch')
    inner = media.inspect(data)['esp']
    required = {boot.FALLBACK_PATH,load.CONFIG_PATH,load.MANIFEST_PATH,load.KERNEL_PATH,
                *(v[4] for v in load.ARTIFACT_DEFINITIONS),load.TRUST_POLICY_PATH,load.TRUST_STATE_PATH}
    if {p for p,v in inner.items() if v['data'] is not None} != required:
        raise ValueError('preview native EFI namespace differs')
    return dict(status='pass',scope='development_PKLOAD6_layout_only',
                production_architecture=production,production_layout_passed=False,
                production_ready=False,production_promotion_allowed=False)


def validate_sustained(samples: list[dict], first: int, last: int) -> dict:
    if type(first) is not int or type(last) is not int or first <= 0 or last-first != SUSTAINED_DISPATCHES:
        raise ValueError('exact sustained dispatch window required')
    selected = [s for s in samples if first <= s['dispatches'] <= last]
    if [s['dispatches'] for s in selected] != list(range(first,last+1,64)):
        raise ValueError('sustained samples missing or reordered')
    for s in selected:
        if s['live_mask'] != 63 or s['generation4'] != 1 or s['generation5'] != 1:
            raise ValueError('both first-generation apps must remain live')
        if any(s[f'calls{i}'] <= 0 or s[f'ticks{i}'] <= 0 for i in range(6)):
            raise ValueError('all six roles must execute')
    for a,b in zip(selected,selected[1:]):
        if any(b[f'{n}{i}'] <= a[f'{n}{i}'] for i in range(6) for n in ('calls','ticks')):
            raise ValueError('role stopped progressing in sustained window')
    return dict(first_dispatch=first,last_dispatch=last,dispatches=last-first,
                samples=len(selected),all_six_roles_progress=True,wall_time_benchmark=False)
