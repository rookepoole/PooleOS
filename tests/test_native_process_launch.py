import unittest
from runtime import native_process_launch as launch
from tests.test_native_session import fixture

def markers(bad=False):
    def row(event,**values):
        assert list(values)==launch.FIELDS[event].split()
        return "POOLEOS:KERNEL:LAUNCH-"+event+" PASS contract=PLAUNCH1"+"".join(f" {k}={v}" for k,v in values.items())
    data=fixture()[:29]
    data.append(row("START",bad_owner=int(bad),supervisor_bytes=936,root0=0x1100000,root1=0x1200000,root2=0x1300000,image_pages=39,firmware_pages=1))
    if bad: data.append(row("CANCELLED",prepared=1,calls=0,released_pages=13,scrubbed_data_pages=6))
    else:
        for n in (1,2):
            data.append(row("ADMITTED",sequence=n,child_generation=n,root=0x1100000,handle=(n<<32)|0x50001,owned_pages=13))
            data.append(row("RETIRED",sequence=n,child_generation=n,calls=257,released_pages=13,scrubbed_data_pages=6))
    data.append(row("RESULT",launched=0 if bad else 2,retired=0 if bad else 2,prepared_cancelled=int(bad),supervisor_exit=170 if bad else 0,supervisor_calls=2 if bad else 600,child_calls=0 if bad else 514,survivor_calls=8193,survivor_after_restart=0 if bad else 100,ticks0=0 if bad else 10,ticks1=20,ticks2=30,dispatches=130 if bad else 151,cr3_writes=260 if bad else 302,released_pages=39 if bad else 52,scrubbed_data_pages=18 if bad else 24,objects_remaining=0))
    return data+[launch.END]

class NativeProcessLaunchTests(unittest.TestCase):
    def test_program_inputs_require_exact_sources_and_original_or_preserved_elf(self):
        import json,tempfile
        from pathlib import Path
        from tests.test_native_user_program import fixture as elf_fixture
        from runtime import native_user_program
        from tools.qualify_native_process_launch import program_input,program_bindings
        elf=elf_fixture();code,meta=native_user_program.extract(elf)
        for snapshot in (False,True):
            with tempfile.TemporaryDirectory() as temp:
                p=Path(temp);env={}
                receipt=dict(status='pass',source_unchanged=True,direct_byte_equality=True,independent_builds=2,source_bindings=program_bindings(),programs={'PooleSupervisor':meta})
                for b in ('build1','build2'):
                    path=p/f'{b}-PooleSupervisor.elf' if snapshot else p/b/'x86_64-unknown-none/release/PooleSupervisor'
                    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(elf)
                    (p/f'{b}-PooleSupervisor.bin').write_bytes(code)
                (p/'receipt.json').write_text(json.dumps(receipt))
                self.assertEqual(program_input(p,env)[1],code)
                self.assertEqual(Path(env['POOLEOS_SUPERVISOR_CODE']).read_bytes(),code)
                key=next(iter(receipt['source_bindings']));del receipt['source_bindings'][key]
                (p/'receipt.json').write_text(json.dumps(receipt))
                with self.assertRaises(ValueError):program_input(p,{})
                receipt['source_bindings']=program_bindings();(p/'receipt.json').write_text(json.dumps(receipt))
                (p/'build2-PooleSupervisor.bin').write_bytes(b'bad')
                with self.assertRaises(ValueError):program_input(p,{})
    def test_two_lifetimes_and_denied_owner_are_distinct(self):
        for bad in (False,True):
            r=launch.validate_markers(markers(bad),bad_owner=bad)
            self.assertEqual(len(r['lifetimes']),0 if bad else 2)
            self.assertFalse(r['iso_built'] or r['production_ready'])
            with self.assertRaises(ValueError):launch.validate_markers(markers(bad),bad_owner=not bad)
    def test_omissions_replays_and_numeric_claims_reject(self):
        for bad in (False,True):self.assertGreater(launch.negative_controls(markers(bad),bad_owner=bad),60)
    def test_generation_root_completion_and_runtime_bounds_reject(self):
        for i,a,b in [(32,'child_generation=2','child_generation=1'),(32,'root=17825792','root=18874368'),(-2,'cr3_writes=302','cr3_writes=301'),(-2,'survivor_after_restart=100','survivor_after_restart=151'),(-2,'ticks1=20',f'ticks1={1<<64}'),(-2,'dispatches=151','dispatches=513')]:
            m=markers();self.assertIn(a,m[i]);m[i]=m[i].replace(a,b)
            with self.assertRaises(ValueError):launch.validate_markers(m)
    def test_exact_complete_terminal_required(self):
        self.assertEqual(launch.COMPLETION,(launch.END+'\r\n').encode())
        data=markers();data[-1]+=' forged=1'
        with self.assertRaises(ValueError):launch.validate_markers(data)
