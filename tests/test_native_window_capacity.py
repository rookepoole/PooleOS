import copy
import struct
import unittest
from pathlib import Path

from runtime import native_user_program as program
from tests.test_native_user_program import fixture

ROOT = Path(__file__).resolve().parents[1]


class WindowCapacityTests(unittest.TestCase):
    def test_native_oracle_binds_seven_page_console_and_exact_retirement_counts(self):
        import ast
        from runtime import native_app_session as apps
        from tests.test_native_windows import markers
        # Every public input/launcher path must propagate the explicit profile
        # into its post-boot hostile controls, not just the positive validator.
        for name in ('qualify_native_windows','qualify_native_local_console','launch_native_virtualbox'):
            tree=ast.parse((ROOT/f'tools/{name}.py').read_text())
            calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='negative_controls']
            self.assertEqual(len(calls),1)
            values=[k.value for k in calls[0].keywords if k.arg=='window_capacity']
            self.assertEqual(len(values),1)
            expr=compile(ast.Expression(values[0]),name,'eval')
            for report,expected in (({},False),({'window_capacity':False},False),({'window_capacity':True},True)):
                self.assertIs(eval(expr,{'__builtins__':{}},{'report':report}),expected)
        for bad_file in (False,True):
            wide=[]
            for line in markers(bad_file):
                event=next((event for event in ('START','RUN','RETIRE') if line.startswith('POOLEOS:APPS '+event+' ')),None)
                if event:
                    fields=apps.parse(line,event)
                    if event=='START':fields.update(console_bytes=24577,image_pages=fields['image_pages']+6)
                    elif event=='RUN' and fields['live_mask']&4:fields['pages']+=6
                    elif event=='RETIRE' and fields['task']==2:fields['released_pages']+=6
                    line='POOLEOS:APPS '+event+' contract=PAPPSESSION1'+''.join(f' {k}={fields[k]}' for k in apps.FIELDS[event].split())+' cpl=3 production=0'
                wide.append(line)
            report=apps.validate_markers(wide,bad_file=bad_file,windows=True,file_waits=True,window_capacity=True)
            self.assertEqual(report['window_service_code_pages'],7)
            self.assertEqual(next(r for r in report['retires'] if r['task']==2)['released_pages'],19)
            self.assertGreater(apps.negative_controls(wide,bad_file=bad_file,windows=True,file_waits=True,window_capacity=True),100)
            with self.assertRaises(ValueError):apps.validate_markers(wide,bad_file=bad_file,windows=True,file_waits=True)
            with self.assertRaises(ValueError):apps.validate_markers(wide,bad_file=bad_file,window_capacity=True)
            for field,value in (('console_bytes',28673),('console_bytes',24576),('text_bytes',16385),('numbers_bytes',16385),('shell_bytes',16385)):
                import re
                corrupt=[re.sub(' '+field+r'=\d+',f' {field}={value}',line) for line in wide]
                with self.assertRaises(ValueError):apps.validate_markers(corrupt,bad_file=bad_file,windows=True,file_waits=True,window_capacity=True)

    def test_seven_page_profile_is_explicit_and_legacy_limit_is_unchanged(self):
        for size in (16384,16385,20480,20481,24576,24577,28672):
            blob=fixture(size)
            code,record=program.extract(blob,profile='PWCODE1')
            self.assertEqual(len(code),size)
            self.assertEqual(record['contract_id'],'PWCODE1')
            self.assertEqual(record['load_pages'],(size+4095)//4096)
            self.assertFalse(record['native_execution_verified'] or record['production_ready'])
            if size>16384:
                with self.assertRaises(ValueError):program.inspect(blob)
        for size in (28673,32768):
            with self.assertRaises(ValueError):program.inspect(fixture(size),profile='PWCODE1')

    def test_wide_profile_preserves_rx_and_exact_file_memory_geometry(self):
        for offset,fmt,value in ((68,'I',7),(68,'I',6),(88,'Q',4096),(104,'Q',32768),(72,'Q',4097)):
            blob=bytearray(fixture(28672));struct.pack_into('<'+fmt,blob,offset,value)
            with self.assertRaises(ValueError):program.inspect(bytes(blob),profile='PWCODE1')
        blob=bytearray(fixture(28672));shoff=struct.unpack_from('<Q',blob,40)[0]
        for field,value in ((8,7),(32,28671),(56,8)):
            bad=bytearray(blob);struct.pack_into('<Q',bad,shoff+64+field,value)
            with self.assertRaises(ValueError):program.inspect(bytes(bad),profile='PWCODE1')

    def test_unknown_profiles_and_renamed_ordinary_programs_do_not_opt_in(self):
        for profile in ('',None,False,7,'pwcode1','PUSERBIN2'):
            with self.assertRaises(ValueError):program.inspect(fixture(),profile=profile)
        self.assertEqual(program.profile_for('PooleWindowCapacity'),'PWCODE1')
        for name in ('PooleWindowConsole','PooleText','PooleNumbers','PooleWindowCapacity.exe','poolewindowcapacity'):
            self.assertEqual(program.profile_for(name),'PUSERBIN1')

    def test_capacity_object_section_requires_explicit_audit_and_local_readonly_definition(self):
        from tools.qualify_native_user_programs import local_relocations
        audit={'Sections':[{'Section':{'Index':3,'Name':{'Name':'.window_capacity'},'Type':{'Value':1},'Flags':{'Value':6},'Size':20}}],
            'Symbols':[{'Symbol':{}},{'Symbol':{'Name':{'Name':'probe'},'Binding':{'Name':'Local','Value':0},'Section':{'Name':'.window_capacity','Value':3},'Value':0}}],
            'Relocations':[{'Relocs':[{'Relocation':{'Type':{'Name':'R_X86_64_PC32','Value':2},'Symbol':{'Name':'probe','Value':1}}}]}]}
        with self.assertRaises(ValueError):local_relocations(audit)
        self.assertEqual(len(local_relocations(audit,window_capacity=True)),1)
        for mutate in (
            lambda a:a['Sections'][0]['Section']['Flags'].update(Value=7),
            lambda a:a['Sections'][0]['Section']['Name'].update(Name='.window_capacity.forged'),
            lambda a:a['Symbols'][1]['Symbol']['Binding'].update(Name='Global',Value=1),
            lambda a:a['Symbols'][1]['Symbol']['Section'].update(Value=0),
            lambda a:a['Relocations'][0]['Relocs'][0]['Relocation']['Type'].update(Name='R_X86_64_64',Value=1),
        ):
            bad=copy.deepcopy(audit);mutate(bad)
            with self.assertRaises(ValueError):local_relocations(bad,window_capacity=True)

    def test_seventh_page_probe_is_bound_and_default_linker_limit_remains(self):
        from tools.qualify_native_user_entry import source_bindings
        from tools.qualify_native_user_programs import bindings
        paths=('native/userspace/build.rs','native/userspace/src/window_main.rs','native/userspace/src/bin/window_capacity.rs')
        for path in paths:
            self.assertIn(path,source_bindings());self.assertIn(path,bindings())
        linker=(ROOT/'native/userspace/linker.ld').read_text()
        self.assertIn('__poole_capacity_start == 24576',linker)
        self.assertIn('DEFINED(__poole_window_capacity) ? SIZEOF(.text) <= 28672',linker)
        self.assertIn('DEFINED(__poole_launch_candidate) ? SIZEOF(.text) <= 20480 : SIZEOF(.text) <= 16384',linker)
        self.assertIn('!(DEFINED(__poole_window_capacity) && DEFINED(__poole_launch_candidate))',linker)
        self.assertIn('KEEP(*(.window_capacity))',linker)
        source=(ROOT/'native/userspace/src/bin/window_capacity.rs').read_text()
        self.assertIn('capacity_probe(seed) != 0x5647_4540_4b47_4b4a',source)
        self.assertIn('process::exit(158)',source)


if __name__=='__main__':unittest.main()
