"""Disposable, identity-bound VirtualBox preview lifecycle; never owns existing VMs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET

CONTRACT = 'PVBPREVIEW1'
COMMAND_SECONDS = 30
TEXT_LIMIT = 1024 * 1024
FIRMWARE_PREFIX = b'\x1b[2J\x1b[01;01H\x1b[=3h\x1b[2J\x1b[01;01H' * 3
ENTRY = b'POOLEBOOT/0.1 ENTRY\r\n'
TOOLS = frozenset(('VBoxManage.exe', 'VBoxHeadless.exe', 'VBoxHeadless.dll', 'VBoxSVC.exe',
    'VBoxSDS.exe', 'VBoxC.dll', 'VBoxProxyStub.dll', 'VBoxRT.dll', 'VBoxVMM.dll',
    'VBoxDD.dll', 'VBoxDD2.dll', 'VBoxDDU.dll', 'VBoxSupLib.dll'))
SECURITY = dict(memory=512, cpus=1, firmware='EFI64', chipset='ich9', hpet='on',
    apic='on', x2apic='off', ioapic='on', longmode='on', paravirtprovider='none',
    graphicscontroller='vboxvga', vram=32, accelerate3d='off', clipboard='disabled',
    clipboard_file_transfers='off', draganddrop='disabled', vrde='off', usb='off',
    ehci='off', xhci='off', audio='none', audio_in='off', audio_out='off',
    uart1='0x03f8,4', uart2='0x02f8,3', uarttype1='16550A', uarttype2='16550A',
    uart3='off', uart4='off', lpt1='off', lpt2='off', boot1='dvd', boot2='none',
    boot3='none', boot4='none', recording_enabled='off', recording_started='off',
    teleporterenabled='off', encryption='disabled')
SECURITY.update({'nested-hw-virt': 'off', 'autostart-enabled': 'off',
                 'tracing-enabled': 'off', 'tracing-allow-vm-access': 'off'})
SECURITY.update({f'nic{i}': 'none' for i in range(1, 37)})


def read_fields(text: str) -> dict:
    if len(text.encode('utf-8')) > TEXT_LIMIT:
        raise ValueError('VM information exceeds bound')
    fields = {}
    for line in text.splitlines():
        if not line or re.fullmatch(r' rec_screen[0-9]+', line):
            continue
        key, separator, value = line.partition('=')
        if not separator:
            raise ValueError('malformed machine-readable record')
        if key.startswith('"'):
            key = json.loads(key)
        if not isinstance(key, str) or not key or key in fields:
            raise ValueError('duplicate or invalid VM information key')
        # VBox7.2 emits unescaped Windows paths in UART mode values only.
        if re.fullmatch(r'uartmode[1-4]', key):
            if len(value) < 2 or value[0] != '"' or value[-1] != '"' or '"' in value[1:-1]:
                raise ValueError('malformed UART mode')
            fields[key] = value[1:-1]
        elif key == 'VideoMode':
            # Running guests add this non-JSON tuple, even in machine-readable mode.
            if not re.fullmatch(r'"[0-9]+,[0-9]+,[0-9]+"@-?[0-9]+,-?[0-9]+ [0-9]+', value):
                raise ValueError('malformed video mode')
            fields[key] = value
        elif key == 'VRDEClients':
            if not re.fullmatch(r'=[0-9]+', value):
                raise ValueError('malformed VRDE client count')
            fields[key] = int(value[1:])
        else:
            fields[key] = json.loads(value)
    return fields


def registrations(text: str) -> set[str]:
    if len(text.encode('utf-8')) > TEXT_LIMIT:
        raise ValueError('VM registry output exceeds bound')
    result = set()
    for line in text.splitlines():
        match = re.fullmatch(r'".*" \{([0-9A-Fa-f-]{36})\}', line)
        if match is None:
            raise ValueError('malformed VM registry record')
        identity = str(uuid.UUID(match[1]))
        if identity in result:
            raise ValueError('duplicate VM registration')
        result.add(identity)
    return result


def read_identity(text: str) -> dict:
    if len(text.encode('utf-8')) > TEXT_LIMIT:
        raise ValueError('VM information exceeds bound')
    # Shutdown needs positive ownership, not successful parsing of optional telemetry.
    keys = r'(?:UUID|name|CfgFile|VMState)'
    return read_fields('\n'.join(line for line in text.splitlines()
        if re.match(r'(?:' + keys + '|"' + keys + r'")=', line)))


def serial_payload(raw: bytes, *, partial: bool = False) -> bytes:
    expected = FIRMWARE_PREFIX + ENTRY
    if partial and expected.startswith(raw):
        return b''
    if not raw.startswith(expected):
        raise ValueError('unexpected VirtualBox diagnostic prelude')
    return raw[len(FIRMWARE_PREFIX):]


def bounded_read(path: Path, limit: int) -> bytes:
    if path.stat().st_size > limit:
        raise ValueError('file exceeds preview bound')
    with path.open('rb') as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError('file grew beyond preview bound')
    return data


def verify_runtime(executable: Path, profile: dict) -> dict:
    executable = executable.resolve(strict=True)
    if (executable.name != 'VBoxManage.exe' or profile.get('contract_id') != CONTRACT
            or set(profile.get('files', {})) != TOOLS):
        raise ValueError('declared VirtualBox runtime profile required')
    observed = {}
    for name, expected in profile['files'].items():
        if not isinstance(expected, str) or not re.fullmatch('[0-9A-F]{64}', expected):
            raise ValueError('invalid runtime hash')
        path = (executable.parent / name).resolve(strict=True)
        if path.parent != executable.parent:
            raise ValueError('runtime file escapes installation')
        digest = hashlib.sha256(bounded_read(path, 128 * 1024 * 1024)).hexdigest().upper()
        if digest != expected:
            raise ValueError('VirtualBox runtime changed; requalification required: ' + name)
        observed[name] = digest
    return observed


def check_identity(info: dict, identity: str, name: str, config: Path) -> None:
    if (info.get('UUID') != identity or info.get('name') != name
            or not isinstance(info.get('CfgFile'), str)
            or Path(info['CfgFile']).resolve() != config.resolve()):
        raise ValueError('VM ownership identity differs; no mutation authorized')


def validate_config(info: dict, xml: bytes, identity: str, name: str,
                    config: Path, iso: Path, com1: Path, port: int) -> None:
    check_identity(info, identity, name, config)
    for key, expected in SECURITY.items():
        if type(info.get(key)) is not type(expected) or info[key] != expected:
            raise ValueError('effective VM setting differs: ' + key)
    if info.get('VMState') != 'poweroff':
        raise ValueError('new VM must be powered off before admission')
    if (not isinstance(port, int) or isinstance(port, bool) or not 0 < port < 65536
            or info.get('uartmode1') != 'file,' + str(com1)
            or info.get('uartmode2') != f'tcpclient,127.0.0.1:{port}'):
        raise ValueError('serial transport is not the owned file and loopback listener')
    if len(xml) > TEXT_LIMIT or b'<!DOCTYPE' in xml or b'<!ENTITY' in xml:
        raise ValueError('unsupported VM XML')
    root = ET.fromstring(xml)
    ns = '{http://www.virtualbox.org/}'
    if root.tag != ns + 'VirtualBox' or len(root) != 1:
        raise ValueError('one VM definition required')
    for element in root.iter():
        if not element.tag.startswith(ns):
            raise ValueError('foreign VM XML namespace')
        element.tag = element.tag[len(ns):]
    machine = root[0]
    if (machine.tag != 'Machine' or machine.get('uuid') != '{' + identity + '}'
            or machine.get('name') != name or machine.get('OSType') != 'Other_64'
            or sorted(e.tag for e in machine) != ['Hardware', 'MediaRegistry']):
        raise ValueError('unexpected machine, snapshot, extra data or media')
    hardware = machine.find('Hardware')
    allowed = {'Memory', 'Paravirt', 'Boot', 'Display', 'Firmware', 'BIOS', 'Network',
               'UART', 'AudioAdapter', 'Clipboard', 'StorageControllers', 'Chipset', 'CPU', 'HPET'}
    tags = [e.tag for e in hardware]
    if len(tags) != len(set(tags)) or not set(tags).issubset(allowed):
        raise ValueError('unexpected hardware, host share or passthrough')
    network = hardware.find('Network')
    if network is not None and any(e.tag != 'Adapter' or e.get('enabled', 'false') != 'false' for e in network):
        raise ValueError('guest network is enabled')
    registry = machine.find('MediaRegistry')
    if len(registry) != 1 or registry[0].tag != 'DVDImages' or len(registry[0]) != 1:
        raise ValueError('only one optical image is allowed')
    image = registry[0][0]
    if image.tag != 'Image' or Path(image.get('location', '')).resolve() != iso.resolve():
        raise ValueError('optical image differs')
    if not re.fullmatch(r'\{[0-9a-fA-F-]{36}\}', image.get('uuid', '')):
        raise ValueError('optical image UUID required')
    uuid.UUID(image.get('uuid')[1:-1])
    controllers = hardware.find('StorageControllers')
    if controllers is None or len(controllers) != 1:
        raise ValueError('one optical controller required')
    controller = controllers[0]
    if (controller.tag != 'StorageController' or controller.get('name') != 'PooleOS-Optical'
            or controller.get('type') != 'AHCI' or controller.get('PortCount') != '1'
            or len(controller) != 1):
        raise ValueError('optical controller differs')
    attached = controller[0]
    if (attached.tag != 'AttachedDevice' or attached.get('type') != 'DVD'
            or attached.get('port') != '0' or attached.get('device') != '0'
            or attached.get('passthrough', 'false') != 'false' or len(attached) != 1
            or attached[0].tag != 'Image' or attached[0].get('uuid') != image.get('uuid')):
        raise ValueError('hard disk, physical drive or foreign attachment rejected')
    uart = hardware.find('UART')
    if uart is None or len(uart) != 2:
        raise ValueError('two owned serial ports required')
    expected_ports = [dict(slot='0', enabled='true', IOBase='0x3f8', IRQ='4', path=str(com1), hostMode='RawFile'),
                      dict(slot='1', enabled='true', IOBase='0x2f8', IRQ='3', server='false',
                           path=f'127.0.0.1:{port}', hostMode='TCP')]
    for node, expected in zip(uart, expected_ports):
        if node.tag != 'Port' or any(node.get(k) != v for k, v in expected.items()):
            raise ValueError('serial port differs')


class Command:
    def __init__(self, executable: Path):
        self.executable = executable
        self.records = []

    def __call__(self, *args):
        started = time.monotonic()
        try:
            result = subprocess.run([str(self.executable), *map(str, args)], capture_output=True,
                text=True, timeout=COMMAND_SECONDS, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except BaseException as error:
            self.records.append(dict(args=list(map(str, args)), failure=type(error).__name__))
            raise
        self.records.append(dict(args=list(map(str, args)), code=result.returncode,
            stdout=result.stdout, stderr=result.stderr, elapsed_seconds=round(time.monotonic() - started, 3)))
        if len(result.stdout.encode()) + len(result.stderr.encode()) > TEXT_LIMIT:
            raise ValueError('command output exceeds bound')
        return result


class OwnedVm:
    def __init__(self, work: Path, command, identity: str | None = None):
        self.work, self.command = work, command
        self.identity = str(uuid.UUID(identity)) if identity else str(uuid.uuid4())
        self.name = 'PooleOS-Preview-' + self.identity
        self.config = work / 'VMs' / self.name / (self.name + '.vbox')
        self.before = None
        self.create_attempted = False
        self.create_completed = False
        self.admission = None

    def checked(self, *args):
        result = self.command(*args)
        if result.returncode:
            raise RuntimeError('VirtualBox command failed: ' + str(args[0]))
        return result.stdout

    def info(self, *, identity_only=False):
        text = self.checked('showvminfo', self.identity, '--machinereadable')
        info = read_identity(text) if identity_only else read_fields(text)
        check_identity(info, self.identity, self.name, self.config)
        return info

    def create(self, iso: Path, port: int):
        self.before = registrations(self.checked('list', 'vms'))
        if self.identity in self.before or self.config.exists():
            raise ValueError('refusing to reuse an existing VM')
        # Retain the intended identity before create/register can have effects.
        self.create_attempted = True
        self.checked('createvm', '--name', self.name, '--uuid', self.identity,
            '--basefolder', self.work / 'VMs', '--ostype', 'Other_64', '--register')
        self.create_completed = True
        self.info()
        self.checked('modifyvm', self.identity, '--memory', '512', '--cpus', '1', '--firmware', 'efi64',
            '--chipset', 'ich9', '--ioapic', 'on', '--x86-x2apic', 'off', '--x86-hpet', 'on',
            '--paravirt-provider', 'none', '--graphicscontroller', 'vboxvga', '--vram', '32',
            '--accelerate-3d', 'off', '--boot1', 'dvd', '--boot2', 'none', '--boot3', 'none', '--boot4', 'none',
            '--audio-enabled', 'off', '--audio-in', 'off', '--audio-out', 'off',
            '--usb-ohci', 'off', '--usb-ehci', 'off', '--usb-xhci', 'off',
            '--clipboard-mode', 'disabled', '--clipboard-file-transfers', 'disabled',
            '--drag-and-drop', 'disabled', '--vrde', 'off', '--recording', 'off', '--teleporter', 'off',
            '--nested-hw-virt', 'off', '--autostart-enabled', 'off', '--tracing-enabled', 'off',
            '--tracing-allow-vm-access', 'off', '--uart1', '0x3f8', '4',
            '--uart-mode1', 'file', self.work / 'com1.log', '--uart2', '0x2f8', '3',
            '--uart-mode2', 'tcpclient', f'127.0.0.1:{port}',
            *[item for n in range(1, 37) for item in (f'--nic{n}', 'none')])
        # Turning x2APIC off in the same command also resets APIC on this version.
        self.checked('modifyvm', self.identity, '--apic', 'on')
        self.checked('storagectl', self.identity, '--name', 'PooleOS-Optical', '--add', 'sata',
            '--controller', 'IntelAhci', '--portcount', '1', '--bootable', 'on')
        self.checked('storageattach', self.identity, '--storagectl', 'PooleOS-Optical',
            '--port', '0', '--device', '0', '--type', 'dvddrive', '--medium', iso)
        text = self.checked('showvminfo', self.identity, '--machinereadable')
        info = read_fields(text)
        validate_config(info, bounded_read(self.config, TEXT_LIMIT), self.identity, self.name,
                        self.config, iso, self.work / 'com1.log', port)
        (self.work / 'configuration.txt').write_text(text, encoding='utf-8')
        self.admission = (iso, port)
        return info

    def start(self):
        if self.admission is None:
            raise ValueError('configured admission required')
        iso, port = self.admission
        validate_config(self.info(), bounded_read(self.config, TEXT_LIMIT), self.identity,
                        self.name, self.config, iso, self.work / 'com1.log', port)
        self.checked('startvm', self.identity, '--type', 'headless')

    def pause(self):
        if self.info(identity_only=True).get('VMState') != 'running':
            raise ValueError('owned guest is not running')
        self.checked('controlvm', self.identity, 'pause')
        if self.info(identity_only=True).get('VMState') != 'paused':
            raise ValueError('pause not confirmed')

    def cleanup(self) -> dict:
        result = dict(stopped=False, unregistered=False, prior_registrations_unchanged=False, errors=[])
        if not self.create_attempted:
            return dict(result, stopped=True, unregistered=True, prior_registrations_unchanged=True)
        try:
            current = registrations(self.checked('list', 'vms'))
            if self.identity in current:
                info = self.info(identity_only=True)
                if info.get('VMState') in ('running', 'paused', 'stuck'):
                    self.command('controlvm', self.identity, 'poweroff')
                    info = self.info(identity_only=True)
                if info.get('VMState') not in ('poweroff', 'aborted'):
                    raise ValueError('shutdown not confirmed; VM retained')
                result['stopped'] = True
                self.command('unregistervm', self.identity)
            else:
                if not self.create_completed:
                    raise ValueError('creation outcome unconfirmed; ownership intent retained')
                result['stopped'] = True
            after = registrations(self.checked('list', 'vms'))
            result['unregistered'] = self.identity not in after
            result['prior_registrations_unchanged'] = after == self.before
        except Exception as error:
            result['errors'].append(f'{type(error).__name__}: {error}')
        return result
