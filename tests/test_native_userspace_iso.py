"""Synthetic packaging/parser tests; no synthetic result is guest evidence."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from runtime import native_userspace_iso as iso, native_kernel_load as load, native_elf_loader as elf
from tests.test_native_kernel_load import synthetic_pooleboot
from tools import launch_native_userspace_iso as launcher, qualify_native_user_entry as source
from tools import qualify_native_app_session as qualification

ROOT = Path(__file__).resolve().parents[1]


def samples():
    return [dict(dispatches=d, live_mask=63, generation4=1, generation5=1,
                 **{f'{n}{i}':d+i for n in ('calls','ticks') for i in range(6)})
            for d in range(128,4225,64)]


class NativeUserSpaceIsoTests(unittest.TestCase):
    def test_exact_optical_firmware_tokens_allow_partial_delivery_not_arbitrary_text(self):
        for token in launcher.console.CONTROL_SEQUENCES:
            for i in range(len(token)+1):
                self.assertEqual((token[:i],b''),launcher.console.split_output(token[:i],partial=True))
            self.assertEqual((token,b'UNKNOWN'),launcher.console.split_output(token+b'UNKNOWN'))
        changed=b'BdsDxe: loading unrecognized text\r\n'
        self.assertEqual((b'',changed),launcher.console.split_output(changed,partial=True))

    def test_all_new_execution_inputs_bound_before_staging(self):
        bindings=source.source_bindings()
        for p in ('runtime/native_userspace_iso.py','tools/launch_native_userspace_iso.py',
                  'tools/qualify_native_app_session.py','tests/test_native_userspace_iso.py',
                  'Launch-UserSpace-Preview.cmd','demos/native_iso/package.py','demos/native_iso/bootstrap.py',
                  'demos/native_iso/toolchain.json','LICENSE'):
            self.assertEqual(iso.sha((ROOT/p).read_bytes()),bindings[p])

    def test_terminal_bytes_and_host_escape_sanitization(self):
        self.assertEqual(b'\r',launcher.terminal_byte('\n'))
        self.assertEqual(b'\x08',launcher.terminal_byte('\b'))
        self.assertEqual(b'A',launcher.terminal_byte('A'))
        for char in ('\x00','\x1b','\xff','AB',''):
            self.assertEqual(b'',launcher.terminal_byte(char))
        self.assertEqual('?[31mX?\r\n',launcher.display_text(b'\x1b[31mX\xff\r\n'))

    def test_terminal_backpressure_and_extended_key_do_not_send_controls(self):
        keys=iter(['\x00','K','A',None,'\x1d'])
        output=qualification.native_shell.BANNER
        emit=Mock(); terminal=launcher.Terminal(lambda:next(keys),emit)
        terminal.sock=Mock();terminal.sock.recv.side_effect=BlockingIOError
        terminal.sock.send.side_effect=[BlockingIOError,1]
        with patch.object(launcher.console,'split_output',return_value=(b'',output)):
            self.assertFalse(terminal.poll(b''));self.assertFalse(terminal.poll(b''))
            self.assertFalse(terminal.poll(b''));self.assertFalse(terminal.poll(b''))
            self.assertFalse(terminal.poll(b''));self.assertTrue(terminal.poll(b''))
        self.assertEqual(b'A',terminal.payload);self.assertEqual(1,terminal.sent)
        terminal.close();terminal.sock.close.assert_called_once()

    def test_terminal_disconnect_and_output_overflow_reject(self):
        for chunks in ([b''],[b'x'*(launcher.console.CONTROL_PREFIX_LIMIT+65537)]):
            terminal=launcher.Terminal(lambda:None,lambda text:None)
            terminal.sock=Mock();terminal.sock.recv.side_effect=chunks
            with self.assertRaises(ValueError): terminal.poll(b'')

    def test_input_path_refuses_non_output_files_and_oversize(self):
        with self.assertRaises(ValueError): launcher.local_file(ROOT/'LICENSE',65536)
        (ROOT/'outputs').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'outputs') as directory:
            path=Path(directory)/'input';path.write_bytes(b'xx')
            with self.assertRaises(ValueError): launcher.local_file(path,1)

    def test_profile_is_optical_isolated_and_does_not_mutate_base(self):
        base=json.loads((ROOT/'specs/native-tier0-profile.json').read_bytes()); saved=copy.deepcopy(base)
        p=iso.optical_profile(base)
        self.assertEqual(saved,base)
        self.assertIn('ide-cd,drive=pooleos_media,bus=ide.0,bootindex=1',p['base_argument_template'])
        self.assertFalse(p['machine']['network_enabled'])
        self.assertIn('if=none,id=pooleos_media,format=raw,readonly=on,file=$MEDIA,media=cdrom',p['base_argument_template'])
        for mutate in ('cpu','drive','duplicate'):
            bad=copy.deepcopy(base)
            if mutate=='cpu': bad['machine']['vcpus']=2
            elif mutate=='drive': bad['base_argument_template'].remove('virtio-blk-pci-non-transitional,drive=pooleos_media')
            else: bad['base_argument_template'].append('virtio-blk-pci-non-transitional,drive=pooleos_media')
            with self.assertRaises(ValueError): iso.optical_profile(bad)

    def test_sustained_window_requires_all_six_roles_at_every_sample(self):
        self.assertEqual(65,iso.validate_sustained(samples(),128,4224)['samples'])
        for field in ('dispatches','live_mask','generation4','generation5',*[f'{n}{i}' for n in ('calls','ticks') for i in range(6)]):
            bad=samples();bad[7][field]=0
            with self.subTest(field=field),self.assertRaises(ValueError): iso.validate_sustained(bad,128,4224)
        for bad in (samples()[:-1],samples()[::-1],samples()+[samples()[-1]]):
            with self.assertRaises(ValueError): iso.validate_sustained(bad,128,4224)
        for first,last in ((True,4097),(0,4096),(128,4160),(129,4225)):
            with self.assertRaises(ValueError): iso.validate_sustained(samples(),first,last)

    def test_license_and_variant_reject(self):
        for license_text in (b'',b'x'*65537,'text'):
            with self.assertRaises(ValueError): iso.build_iso(b'',license_text)
        with self.assertRaises(ValueError): iso.manifest_for(b'',{},'release')

    def test_actual_packaging_roundtrip_and_hostile_bytes(self):
        # Synthetic PE plus canonical parser fixtures, never booted or called an OS.
        kernel=elf.build_fixture('minimal_relative_v1')
        disk=load.build_media_bytes(synthetic_pooleboot(),load.canonical_config_bytes(),load.canonical_manifest_bytes(kernel),kernel)
        data,report=iso.build_iso(disk,b'Synthetic test license\n')
        self.assertEqual(data,iso.build_iso(disk,b'Synthetic test license\n')[0])
        self.assertFalse(report['native_execution_verified'])
        self.assertEqual(12,len(report['files']))
        self.assertEqual(report,iso.inspect_iso(data,disk,b'Synthetic test license\n'))
        architecture=iso.development_architecture(data)
        self.assertFalse(architecture['production_layout_passed'])
        self.assertEqual('fail',architecture['production_architecture']['status'])
        with self.assertRaises(ValueError): iso.development_architecture(data[:-2048])
        forbidden,_=iso.build_iso(disk,b'Linux version TEST')
        with self.assertRaises(ValueError): iso.development_architecture(forbidden)
        with self.assertRaises(ValueError): iso.inspect_iso(data,disk,b'changed')
        with self.assertRaises(ValueError): iso.inspect_iso(data,disk,b'Synthetic test license\n','bad-file')
        for offset in (0,16*2048+40,data.index(b'Synthetic test license'),data.index(b'POOLEOS_USERSPACE')):
            bad=bytearray(data);bad[offset]^=1
            with self.subTest(offset=offset),self.assertRaises(ValueError): iso.inspect_iso(bytes(bad),disk,b'Synthetic test license\n')
        with self.assertRaises(ValueError): iso.inspect_iso(data[:-2048],disk,b'Synthetic test license\n')


if __name__=='__main__': unittest.main()
