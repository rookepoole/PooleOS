import copy
import hashlib
import struct
import tempfile
import unittest
from pathlib import Path
from runtime import native_user_program as program

ROOT = Path(__file__).resolve().parents[1]

def fixture():
    code=b"\x31\xed\xc3"
    names=b"\0.text\0.shstrtab\0"
    shoff=4120
    blob=bytearray(shoff+192)
    blob[:16]=b"\x7fELF\x02\x01\x01"+bytes(9)
    struct.pack_into("<HHIQQQIHHHHHH",blob,16,2,62,1,0,64,shoff,0,64,56,1,64,3,2)
    struct.pack_into("<IIQQQQQQ",blob,64,1,5,4096,0,0,len(code),len(code),4096)
    blob[4096:4099]=code
    blob[4099:4099+len(names)]=names
    struct.pack_into("<IIQQQQIIQQ",blob,shoff+64,1,1,6,0,4096,len(code),0,0,16,0)
    struct.pack_into("<IIQQQQIIQQ",blob,shoff+128,7,3,0,0,4099,len(names),0,0,1,0)
    return bytes(blob)

class NativeUserProgramTests(unittest.TestCase):
    def test_object_lookup_separates_shared_prefix_and_rejects_missing_or_duplicate_objects(self):
        from tools.qualify_native_user_programs import codegen_object
        with tempfile.TemporaryDirectory() as temp:
            deps = Path(temp)
            for name in ("PooleConsole", "PooleConsoleClient", "PooleConsoleService"):
                (deps / (name + "-123.rcgu.o")).touch()
            self.assertEqual(codegen_object(deps, "PooleConsole"), deps / "PooleConsole-123.rcgu.o")
            with self.assertRaises(ValueError):
                codegen_object(deps, "Missing")
            (deps / "PooleConsole-456.rcgu.o").touch()
            with self.assertRaises(ValueError):
                codegen_object(deps, "PooleConsole")
    def mutate(self,offset,fmt,value):
        blob=bytearray(fixture()); struct.pack_into(fmt,blob,offset,value); return bytes(blob)
    def test_extracts_exact_single_page_without_execution_claim(self):
        code,record=program.extract(fixture())
        self.assertEqual(code,b"\x31\xed\xc3")
        self.assertEqual(record["code_sha256"],hashlib.sha256(code).hexdigest().upper())
        self.assertEqual((record["entry_offset"],record["load_pages"]), (0,1))
        self.assertFalse(record["native_execution_verified"] or record["production_ready"])
    def test_identification_machine_type_entry_and_header_bounds_reject(self):
        for offset,fmt,values in [(0,"B",[0]),(4,"B",[1]),(7,"B",[3]),(16,"H",[1,3]),
                (18,"H",[3,183]),(20,"I",[0,2]),(24,"Q",[1,4096]),(32,"Q",[0,65]),
                (40,"Q",[0,119,2**64-1]),(48,"I",[1]),(52,"H",[63]),(54,"H",[55]),
                (56,"H",[0,2]),(58,"H",[63]),(60,"H",[0,17]),(62,"H",[0,3])]:
            for value in values:
                with self.subTest(offset=offset,value=value):
                    with self.assertRaises(ValueError): program.inspect(self.mutate(offset,fmt,value))
    def test_segment_permissions_offsets_sizes_and_dynamic_payload_reject(self):
        for offset,fmt,values in [(64,"I",[2,3]),(68,"I",[4,6,7]),(72,"Q",[64,4097,8192]),
                (80,"Q",[4096]),(88,"Q",[4096]),(96,"Q",[0,4097,2**64-1]),
                (104,"Q",[0,4]),(112,"Q",[0,16])]:
            for value in values:
                with self.subTest(offset=offset,value=value):
                    with self.assertRaises(ValueError): program.inspect(self.mutate(offset,fmt,value))
    def test_sections_cannot_add_relocations_writable_data_or_aliases(self):
        for offset,fmt,values in [(4120,"I",[1]),(4188,"I",[2,4,9,11]),(4192,"Q",[2,3,7]),
                (4200,"Q",[1]),(4208,"Q",[0]),(4216,"Q",[2,4097]),
                (4224,"I",[1]),(4228,"I",[1]),(4232,"Q",[3]),(4240,"Q",[8]),
                (4252,"I",[1]),(4256,"Q",[2]),(4272,"Q",[0,2**64-1])]:
            for value in values:
                with self.subTest(offset=offset,value=value):
                    with self.assertRaises(ValueError): program.inspect(self.mutate(offset,fmt,value))
    def test_truncations_and_non_bytes_inputs_reject(self):
        for n in [0,15,63,119,4096,4119,len(fixture())-1]:
            with self.assertRaises(ValueError): program.inspect(fixture()[:n])
        with self.assertRaises(ValueError): program.inspect(bytearray(fixture()))
        with self.assertRaises(ValueError): program.inspect(bytes(program.MAX_FILE+1))
    def test_format_audit_does_not_pretend_to_prove_instruction_semantics(self):
        blob=self.mutate(4098,"B",0x90)
        record=program.inspect(blob)
        self.assertNotEqual(record["code_sha256"],program.inspect(fixture())["code_sha256"])
        self.assertFalse(record["native_execution_verified"])
    def test_linker_source_rejects_got_data_relocations_and_oversize(self):
        text=(ROOT/"native/userspace/linker.ld").read_text()
        for required in [".text.start","FLAGS(5)","*(.data", ".got", ".dynamic", ".rela.*",
                "SIZEOF(.text) <= 4096","SIZEOF(.forbidden) == 0","_start == 0"]:
            self.assertIn(required,text)
    def test_user_runtime_has_no_kernel_or_host_dependency_and_memory_clobbers_are_preserved(self):
        import tomllib
        manifest=tomllib.loads((ROOT/"native/userspace/Cargo.toml").read_text())
        self.assertNotIn("dependencies",manifest)
        self.assertIn("workspace",manifest)
        source=(ROOT/"native/userspace/src/process.rs").read_text()
        for required in ['inlateout("rax")','inlateout("rdx")','in("rdi") 1u64',
                'lateout("rcx") _','lateout("r11") _','call(5, handle','options(nostack)']:
            self.assertIn(required,source)
        self.assertNotIn("options(nomem",source)
        self.assertNotIn("options(readonly",source)
    def test_kernel_and_user_wire_constants_agree_without_linking_implementations(self):
        kernel=(ROOT/"native/kernel/src/user_entry/startup.rs").read_text()
        user=(ROOT/"native/userspace/src/startup.rs").read_text()
        abi=(ROOT/"native/kernel/src/user_entry/syscall.rs").read_text()
        for text in [kernel,user]: self.assertIn('PSTART1\\0',text)
        for required in ["VERSION: u64 = 1", "3 | 4 =>", "send: number == 3", "5 if destination <= 1"]:
            self.assertIn(required,abi)
        envelope=(ROOT/"native/kernel/src/capability_ipc/reply.rs").read_text()
        console=(ROOT/"native/userspace/src/console_ipc.rs").read_text()
        adapter=(ROOT/"native/userspace/src/process.rs").read_text()
        self.assertIn("HEADER_BYTES: usize = 32",envelope)
        self.assertIn("7 => Operation::Receive",abi)
        self.assertIn("BYTES: usize = 32",console)
        self.assertIn("ENVELOPE_BYTES: usize = 64",console)
        rpc=(ROOT/"native/userspace/src/console_ipc/rpc.rs").read_text()
        self.assertIn("call(number, handle, wire.as_mut_ptr()",adapter)
        self.assertIn("self.0.receive(&mut ConsoleCalls)",adapter)
        self.assertIn("(7, self.endpoint)",rpc)
        self.assertIn("(11, self.pending)",rpc)
        self.assertIn("self.peer.decode(&wire)",rpc)
        for name in ("init","counter","console_service","console_client"):
            main=(ROOT/f"native/userspace/src/bin/{name}.rs").read_text()
            self.assertIn("entry!(main)",main)
            self.assertIn("loop {",main)
            self.assertNotIn("std::",main)

if __name__ == "__main__": unittest.main()
