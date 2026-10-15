"""Synthetic lifecycle tests; live guest evidence is recorded separately."""
from contextlib import ExitStack
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

from runtime import native_virtualbox as vbox
from tools import launch_native_virtualbox as launch, qualify_native_user_entry as source

ROOT = Path(__file__).resolve().parents[1]
IDENTITY = '11111111-1111-4111-8111-111111111111'
PRIOR = '22222222-2222-4222-8222-222222222222'
MEDIA = '{33333333-3333-4333-8333-333333333333}'


def fixture(owner, iso, port=12345):
    info = dict(vbox.SECURITY, UUID=owner.identity, name=owner.name, CfgFile=str(owner.config),
                VMState='poweroff', uartmode1='file,' + str(owner.work / 'com1.log'),
                uartmode2=f'tcpclient,127.0.0.1:{port}')
    root = ET.Element('VirtualBox', xmlns='http://www.virtualbox.org/')
    machine = ET.SubElement(root, 'Machine', uuid='{' + owner.identity + '}', name=owner.name, OSType='Other_64')
    media = ET.SubElement(ET.SubElement(machine, 'MediaRegistry'), 'DVDImages')
    ET.SubElement(media, 'Image', uuid=MEDIA, location=str(iso))
    hardware = ET.SubElement(machine, 'Hardware')
    network = ET.SubElement(hardware, 'Network')
    ET.SubElement(ET.SubElement(network, 'Adapter', slot='0'), 'NAT')
    ports = ET.SubElement(hardware, 'UART')
    ET.SubElement(ports, 'Port', slot='0', enabled='true', IOBase='0x3f8', IRQ='4',
                  path=str(owner.work / 'com1.log'), hostMode='RawFile')
    ET.SubElement(ports, 'Port', slot='1', enabled='true', IOBase='0x2f8', IRQ='3',
                  server='false', path=f'127.0.0.1:{port}', hostMode='TCP')
    controller = ET.SubElement(ET.SubElement(hardware, 'StorageControllers'), 'StorageController',
                               name='PooleOS-Optical', type='AHCI', PortCount='1')
    attached = ET.SubElement(controller, 'AttachedDevice', type='DVD', port='0', device='0')
    ET.SubElement(attached, 'Image', uuid=MEDIA)
    return info, root


def fields(info):
    return '\n'.join(k + '=' + ('"' + v + '"' if k.startswith('uartmode') else json.dumps(v))
                     for k, v in info.items())


class FakeCommand:
    def __init__(self):
        self.registry = {PRIOR}
        self.calls = []
        self.state = 'poweroff'
        self.fail = None
        self.foreign = False
        self.extra = ''

    def __call__(self, *args):
        args = tuple(map(str, args))
        self.calls.append(args)
        verb = args[0]
        if self.fail == (verb, 'before'):
            raise TimeoutError('synthetic before-effect failure')
        stdout = ''
        if verb == 'list':
            stdout = '\n'.join('"opaque name" {' + i + '}' for i in sorted(self.registry))
        elif verb == 'createvm':
            self.registry.add(self.owner.identity)
            self.owner.config.parent.mkdir(parents=True)
            self.owner.config.write_bytes(ET.tostring(self.xml))
        elif verb == 'showvminfo':
            info = dict(self.info, VMState=self.state)
            if self.foreign:
                info['name'] = 'foreign owner'
            stdout = fields(info) + self.extra
        elif verb == 'startvm':
            self.state = 'running'
        elif verb == 'controlvm':
            self.state = 'paused' if args[-1] == 'pause' else 'poweroff'
        elif verb == 'unregistervm':
            self.registry.remove(self.owner.identity)
        if self.fail == (verb, 'after'):
            raise TimeoutError('synthetic after-effect failure')
        return subprocess.CompletedProcess(args, 0, stdout, '')


class VirtualBoxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name).resolve()
        self.command = FakeCommand()
        self.owner = vbox.OwnedVm(self.work, self.command, IDENTITY)
        self.iso = self.work / 'preview.iso'
        self.info, self.xml = fixture(self.owner, self.iso)
        self.command.owner, self.command.info, self.command.xml = self.owner, self.info, self.xml

    def validate(self, info=None, xml=None, port=12345):
        vbox.validate_config(self.info if info is None else info,
            ET.tostring(self.xml if xml is None else xml), IDENTITY, self.owner.name,
            self.owner.config, self.iso, self.work / 'com1.log', port)

    def test_source_bindings_include_launcher_profile_and_lifecycle(self):
        bindings = source.source_bindings()
        for name in ('runtime/native_virtualbox.py', 'tools/launch_native_virtualbox.py',
                     'Launch-VirtualBox-Preview.cmd', 'specs/native-virtualbox-preview-profile.json',
                     'tests/test_native_virtualbox.py'):
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest().upper(), bindings[name])

    def test_fields_preserve_raw_uart_paths_and_decode_other_paths(self):
        value = 'C:\\tmp\\new\\file'
        text = 'uartmode1="file,' + value + '"\nCfgFile=' + json.dumps(value) + '\n rec_screen0\n'
        self.assertEqual({'uartmode1': 'file,' + value, 'CfgFile': value}, vbox.read_fields(text))

    def test_fields_reject_duplicates_malformed_and_oversize(self):
        for text in ('x=1\nx=1', '"x"=1\nx=1', 'unknown', 'uartmode1=1', 'uartmode1="x"y"',
                     'x=' + '1' * (vbox.TEXT_LIMIT + 1), '""=1', 'x=on'):
            with self.subTest(text=text[:20]), self.assertRaises(ValueError):
                vbox.read_fields(text)

    def test_registry_parser_requires_unique_valid_uuid(self):
        self.assertEqual(set(), vbox.registrations(''))
        self.assertEqual({PRIOR}, vbox.registrations('"name with spaces" {' + PRIOR + '}'))
        for text in ('x', '"x" {bad}', ('"x" {' + PRIOR + '}\n') * 2, 'x' * (vbox.TEXT_LIMIT + 1)):
            with self.assertRaises(ValueError):
                vbox.registrations(text)

    def test_running_video_tuple_and_double_equals_vrde_count(self):
        text = 'VideoMode="1024,768,32"@0,0 1\nVRDEClients==0'
        self.assertEqual({'VideoMode': '"1024,768,32"@0,0 1', 'VRDEClients': 0}, vbox.read_fields(text))

    def test_malformed_running_telemetry_is_not_admitted(self):
        for text in ('VideoMode="1024,768,32"@x,0 1', 'VideoMode="1024,768,32"@0,0 1 trailing',
                     'VRDEClients=0', 'VRDEClients==x', 'VRDEClients==-1'):
            with self.assertRaises(ValueError):
                vbox.read_fields(text)

    def test_identity_projection_rejects_duplicates_and_oversize(self):
        for text in ('UUID="x"\n"UUID"="x"', 'x' * (vbox.TEXT_LIMIT + 1)):
            with self.assertRaises(ValueError):
                vbox.read_identity(text)

    def test_shutdown_does_not_depend_on_optional_telemetry_parser(self):
        self.owner.create(self.iso, 12345)
        self.owner.start()
        self.command.extra = '\nVideoMode=unknown future telemetry\nother optional text'
        with self.assertRaises(ValueError):
            self.owner.info()
        self.owner.pause()
        self.assertTrue(self.owner.cleanup()['unregistered'])

    def test_only_exact_firmware_prelude_removed(self):
        raw = vbox.FIRMWARE_PREFIX + vbox.ENTRY
        for i in range(len(raw) + 1):
            self.assertEqual(b'', vbox.serial_payload(raw[:i], partial=True))
        self.assertEqual(vbox.ENTRY + b'kernel', vbox.serial_payload(raw + b'kernel'))
        for bad in (b'', vbox.ENTRY, b'arbitrary' + raw, raw.replace(b'ENTRY', b'FAIL!')):
            with self.assertRaises(ValueError):
                vbox.serial_payload(bad)

    def test_bounded_file_read(self):
        path = self.work / 'log'
        path.write_bytes(b'123')
        self.assertEqual(b'123', vbox.bounded_read(path, 3))
        with self.assertRaises(ValueError):
            vbox.bounded_read(path, 2)

    def test_runtime_exact_file_profile_and_mutation(self):
        files = {}
        for name in vbox.TOOLS:
            (self.work / name).write_bytes(name.encode())
            files[name] = hashlib.sha256(name.encode()).hexdigest().upper()
        profile = dict(contract_id=vbox.CONTRACT, files=files)
        exe = self.work / 'VBoxManage.exe'
        self.assertEqual(files, vbox.verify_runtime(exe, profile))
        for key, replacement in (('contract_id', 'wrong'), ('files', {})):
            with self.assertRaises(ValueError):
                vbox.verify_runtime(exe, dict(profile, **{key: replacement}))
        bad = copy.deepcopy(profile)
        bad['files']['VBoxManage.exe'] = 'a' * 64
        with self.assertRaises(ValueError):
            vbox.verify_runtime(exe, bad)
        (self.work / 'VBoxVMM.dll').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            vbox.verify_runtime(exe, profile)

    def test_effective_settings_require_exact_types_and_values(self):
        self.validate()
        for key in vbox.SECURITY:
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.validate(dict(self.info, **{key: None}))
        with self.assertRaises(ValueError):
            self.validate(dict(self.info, cpus=True))

    def test_identity_state_and_serial_destination_changes_reject(self):
        for key, value in (('UUID', PRIOR), ('name', 'other'), ('CfgFile', 'elsewhere'),
                           ('VMState', 'running'), ('uartmode2', 'tcpclient,0.0.0.0:12345'),
                           ('uartmode1', 'file,foreign')):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.validate(dict(self.info, **{key: value}))
        for port in (True, 0, -1, 65536):
            with self.assertRaises(ValueError):
                self.validate(port=port)

    def test_xml_rejects_shares_disks_passthrough_snapshots_and_enabled_network(self):
        for path, tag in (('Machine/Hardware', 'SharedFolders'), ('Machine/Hardware', 'USB'),
                          ('Machine/Hardware', 'HostPci'), ('Machine', 'Snapshot'),
                          ('Machine', 'ExtraData'), ('Machine/MediaRegistry', 'HardDisks')):
            xml = copy.deepcopy(self.xml)
            ET.SubElement(xml.find(path), tag)
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                self.validate(xml=xml)
        for path, key, value in (('Machine/Hardware/Network/Adapter', 'enabled', 'true'),
                ('Machine/Hardware/StorageControllers/StorageController/AttachedDevice', 'type', 'HardDisk'),
                ('Machine/Hardware/StorageControllers/StorageController/AttachedDevice', 'passthrough', 'true'),
                ('Machine/MediaRegistry/DVDImages/Image', 'uuid', ''),
                ('Machine/MediaRegistry/DVDImages/Image', 'location', 'foreign.iso'),
                ('Machine/Hardware/UART/Port', 'path', 'foreign'),
                ('Machine/Hardware/StorageControllers/StorageController', 'PortCount', '2')):
            xml = copy.deepcopy(self.xml)
            xml.find(path).set(key, value)
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.validate(xml=xml)

    def test_xml_entities_namespace_and_duplicate_hardware_reject(self):
        args = (IDENTITY, self.owner.name, self.owner.config, self.iso, self.work / 'com1.log', 12345)
        for xml in (b'<!DOCTYPE x>', b'<!ENTITY x>', b'x' * (vbox.TEXT_LIMIT + 1), b'<VirtualBox/>'):
            with self.assertRaises(ValueError):
                vbox.validate_config(self.info, xml, *args)
        ET.SubElement(self.xml.find('Machine/Hardware'), 'UART')
        with self.assertRaises(ValueError):
            self.validate()

    def test_complete_lifecycle_owns_only_new_uuid_and_retains_files(self):
        self.owner.create(self.iso, 12345)
        self.owner.start()
        self.owner.pause()
        result = self.owner.cleanup()
        self.assertTrue(all(result[k] for k in ('stopped', 'unregistered', 'prior_registrations_unchanged')))
        self.assertEqual({PRIOR}, self.command.registry)
        self.assertTrue(self.owner.config.exists())
        flat = [item for call in self.command.calls for item in call]
        self.assertNotIn('--delete', flat)
        self.assertNotIn('--delete-all', flat)
        for n in range(1, 37):
            i = flat.index(f'--nic{n}')
            self.assertEqual('none', flat[i + 1])
        for call in self.command.calls:
            if call[0] in ('modifyvm', 'controlvm', 'startvm', 'unregistervm', 'storageattach', 'storagectl'):
                self.assertEqual(IDENTITY, call[1])

    def test_existing_registration_or_config_is_never_mutated(self):
        self.command.registry.add(IDENTITY)
        with self.assertRaises(ValueError):
            self.owner.create(self.iso, 12345)
        self.assertFalse(self.owner.create_attempted)
        self.assertEqual([('list', 'vms')], self.command.calls)
        self.command.registry.remove(IDENTITY)
        self.owner.config.parent.mkdir(parents=True)
        self.owner.config.write_bytes(b'existing')
        with self.assertRaises(ValueError):
            self.owner.create(self.iso, 12345)
        self.assertEqual(b'existing', self.owner.config.read_bytes())

    def test_start_requires_admission_and_rechecks_effective_config(self):
        with self.assertRaises(ValueError):
            self.owner.start()
        self.owner.create(self.iso, 12345)
        self.info['nic36'] = 'nat'
        with self.assertRaises(ValueError):
            self.owner.start()
        self.assertFalse(any(c[0] == 'startvm' for c in self.command.calls))

    def test_after_effect_creation_failure_still_cleans_owned_registration(self):
        self.command.fail = ('createvm', 'after')
        with self.assertRaises(TimeoutError):
            self.owner.create(self.iso, 12345)
        self.assertTrue(self.owner.create_attempted)
        self.assertTrue(self.owner.cleanup()['unregistered'])
        self.assertEqual({PRIOR}, self.command.registry)

    def test_before_effect_creation_failure_remains_explicitly_unconfirmed(self):
        self.command.fail = ('createvm', 'before')
        with self.assertRaises(TimeoutError):
            self.owner.create(self.iso, 12345)
        result = self.owner.cleanup()
        self.assertFalse(result['unregistered'])
        self.assertIn('creation outcome unconfirmed', result['errors'][0])

    def test_configuration_failure_cleans_created_vm(self):
        self.command.fail = ('modifyvm', 'after')
        with self.assertRaises(TimeoutError):
            self.owner.create(self.iso, 12345)
        self.assertTrue(self.owner.cleanup()['unregistered'])

    def test_after_effect_start_failure_powers_off_owned_vm(self):
        self.owner.create(self.iso, 12345)
        self.command.fail = ('startvm', 'after')
        with self.assertRaises(TimeoutError):
            self.owner.start()
        self.assertTrue(self.owner.cleanup()['unregistered'])
        self.assertIn(('controlvm', IDENTITY, 'poweroff'), self.command.calls)

    def test_foreign_identity_refuses_cleanup_mutation(self):
        self.owner.create(self.iso, 12345)
        self.owner.start()
        self.command.foreign = True
        result = self.owner.cleanup()
        self.assertFalse(result['stopped'])
        self.assertFalse(any(c[0] == 'controlvm' for c in self.command.calls))
        self.assertIn(IDENTITY, self.command.registry)

    def test_cleanup_poweroff_failure_retains_vm_and_failure(self):
        self.owner.create(self.iso, 12345)
        self.owner.start()
        self.command.fail = ('controlvm', 'before')
        result = self.owner.cleanup()
        self.assertFalse(result['stopped'])
        self.assertTrue(result['errors'])
        self.assertIn(IDENTITY, self.command.registry)

    def test_unregistration_failure_does_not_claim_success(self):
        self.owner.create(self.iso, 12345)
        self.command.fail = ('unregistervm', 'before')
        result = self.owner.cleanup()
        self.assertTrue(result['stopped'])
        self.assertFalse(result['unregistered'])

    def test_other_registration_change_is_detected_and_not_undone(self):
        self.owner.create(self.iso, 12345)
        self.command.registry.remove(PRIOR)
        result = self.owner.cleanup()
        self.assertTrue(result['unregistered'])
        self.assertFalse(result['prior_registrations_unchanged'])
        self.assertNotIn(PRIOR, self.command.registry)

    def test_command_timeout_recorded_and_no_shell_or_visible_console(self):
        command = vbox.Command(self.work / 'VBoxManage.exe')
        with patch.object(vbox.subprocess, 'run', side_effect=subprocess.TimeoutExpired('test', 30)) as run:
            with self.assertRaises(subprocess.TimeoutExpired):
                command('list', 'vms')
            self.assertEqual(vbox.COMMAND_SECONDS, run.call_args.kwargs['timeout'])
            self.assertNotIn('shell', run.call_args.kwargs)
        self.assertEqual('TimeoutExpired', command.records[0]['failure'])


class SessionTests(unittest.TestCase):
    def simulate(self, *, poll_error=None, close_error=None, cleanup_ok=True, source_changed=False):
        (ROOT / 'outputs').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / 'outputs') as directory, ExitStack() as stack:
            work = Path(directory) / 'session'
            iso = Path(directory) / 'image.iso'
            info = dict(source_bindings={}, optical_images={'applications-1': {
                'iso_sha256': hashlib.sha256(b'ISO').hexdigest().upper()}})
            owner = Mock(identity=IDENTITY)
            owner.name = 'owned'
            owner.checked.return_value = '7.2.20r175154\n'
            owner.cleanup.return_value = dict(stopped=cleanup_ok, unregistered=cleanup_ok,
                prior_registrations_unchanged=True, errors=[])
            interaction = Mock(sock=Mock(), payload=b'', sent=0, received=bytearray())
            interaction.poll.side_effect = poll_error
            interaction.poll.return_value = True
            interaction.close.side_effect = close_error
            stack.enter_context(patch.object(launch, 'check_preview', return_value=(info, iso, b'disk')))
            stack.enter_context(patch.object(launch.vbox, 'verify_runtime', return_value={}))
            stack.enter_context(patch.object(launch.vbox, 'OwnedVm', return_value=owner))
            stack.enter_context(patch.object(launch.vbox, 'Command', return_value=Mock(records=[])))
            stack.enter_context(patch.object(launch.vbox, 'bounded_read', return_value=vbox.FIRMWARE_PREFIX + vbox.ENTRY))
            stack.enter_context(patch.object(launch.source, 'source_bindings', side_effect=[{}, {'changed': 'x'} if source_changed else {}]))
            listener = Mock()
            listener.getsockname.return_value = ('127.0.0.1', 12345)
            stack.enter_context(patch.object(launch, 'listener_socket', return_value=listener))
            stack.enter_context(patch.object(launch, 'manual_summary', return_value={'scope': 'synthetic'}))
            stack.enter_context(patch.object(launch, 'local_file', return_value=b'ISO'))
            code = launch.run_session(Path(directory) / 'receipt.json', work, Path(__file__), interaction, False)
            owner.cleanup.assert_called_once()
            return code, json.loads((work / 'receipt.json').read_bytes())

    def test_manual_scope_success_is_not_qualification(self):
        code, result = self.simulate()
        self.assertEqual(0, code)
        self.assertEqual('manual_serial_session_not_qualification', result['scope'])
        self.assertFalse(result['production_ready'])

    def test_interrupt_still_cleans_vm(self):
        code, result = self.simulate(poll_error=KeyboardInterrupt())
        self.assertEqual(130, code)
        self.assertEqual('cancelled', result['status'])

    def test_poll_failure_still_cleans_vm(self):
        code, result = self.simulate(poll_error=ValueError('synthetic'))
        self.assertEqual(1, code)
        self.assertIn('synthetic', result['failure'])

    def test_transport_close_failure_cannot_skip_vm_cleanup(self):
        code, result = self.simulate(close_error=OSError('synthetic close'))
        self.assertEqual(1, code)
        self.assertEqual(['OSError'], result['close_errors'])

    def test_unconfirmed_cleanup_or_source_change_fails_session(self):
        for args in ({'cleanup_ok': False}, {'source_changed': True}):
            code, result = self.simulate(**args)
            self.assertEqual(1, code)
            self.assertEqual('fail', result['status'])


if __name__ == '__main__':
    unittest.main()
