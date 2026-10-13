"""Launch the qualified native ISO through a host serial terminal, not a native GUI."""
from __future__ import annotations
import argparse
import json
import secrets
import socket
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from runtime import native_userspace_iso as optical, native_app_session as apps
from runtime import native_console as console, native_shell as shell, native_session as session
from tools import qualify_native_app_session as qualification, qualify_native_user_entry as source
shared=qualification.shared
LOG_LIMIT=16*1024*1024


def local_file(path: Path, maximum: int) -> bytes:
    resolved=path.resolve(strict=True)
    if not resolved.is_relative_to((ROOT/'outputs').resolve()) or not resolved.is_file():
        raise ValueError('ordinary workspace outputs file required')
    if resolved.stat().st_size > maximum: raise ValueError('oversized input')
    data=resolved.read_bytes()
    if len(data)>maximum: raise ValueError('input grew beyond bound')
    return data


def check_preview(receipt: Path):
    report=json.loads(local_file(receipt,16*1024*1024))
    if (report.get('status')!='pass' or report.get('contract_id')!=optical.CONTRACT
            or report.get('iso_built') is not True or report.get('production_ready') is not False
            or report.get('source_unchanged') is not True or report.get('source_bindings')!=source.source_bindings()):
        raise ValueError('current passing development qualification required; unsigned receipts are not authentication')
    expected=['applications-1','applications-2','bad-file']
    if [v['run_id'] for v in report['guest_runs']]!=expected or report['ordinary_denial']['run_id']!='ordinary-denial':
        raise ValueError('optical controls missing')
    for run in report['guest_runs']:
        entry=report['optical_images'][run['run_id']]
        if run['iso_sha256']!=entry['iso_sha256'] or run['qemu_exit_code']!=0 or not run['interaction']['exact_interaction']:
            raise ValueError('inexact optical guest binding')
        samples=[apps.parse(m,'RUN') for m in run['markers'] if m.startswith('POOLEOS:APPS RUN ')]
        window=run['sustained_window']
        if window!=optical.validate_sustained(samples,window['first_dispatch'],window['last_dispatch']):
            raise ValueError('sustained evidence differs')
        apps.validate_markers(run['markers'],bad_file=run['run_id']=='bad-file',file_waits=report.get('file_waits',False))
    ordinary=report['ordinary_denial']
    if ordinary['qemu_exit_code']!=0 or ordinary['iso_sha256']!=report['optical_images']['ordinary-denial']['iso_sha256']:
        raise ValueError('ordinary denial image differs')
    shared.load.validate_markers(ordinary['markers'])
    entry=report['optical_images']['applications-1']
    path=ROOT/entry['path']
    if path.resolve().parent!=receipt.resolve().parent: raise ValueError('ISO is not beside its receipt')
    data=local_file(path,128*1024*1024)
    disk=local_file(receipt.parent/'applications-1.img',64*1024*1024)
    inspection=optical.inspect_iso(data,disk,(ROOT/'LICENSE').read_bytes())
    if inspection['iso_sha256']!=entry['iso_sha256'] or optical.development_architecture(data)['status']!='pass':
        raise ValueError('qualified image bytes differ')
    return report,path,disk


def terminal_byte(char: str) -> bytes:
    if char in ('\r','\n'): return b'\r'
    if char=='\b': return b'\x08'
    if len(char)==1 and 32<=ord(char)<=126: return char.encode('ascii')
    return b''


def display_text(data: bytes) -> str:
    # Do not forward guest escape sequences to the host terminal.
    return ''.join(chr(b) if b in (8,10,13) or 32<=b<=126 else '?' for b in data)


class Terminal(shared.Interaction):
    def __init__(self, read_key, emit):
        super().__init__(b'',False)
        self.read_key,self.emit=read_key,emit
        self.shown=0
        self.pending=b''
        self.skip_extended=False

    def poll(self, debug):
        if self.sock is None:
            self.sock=socket.create_connection(('127.0.0.1',self.port),timeout=2)
            self.sock.setblocking(False)
        while True:
            try: data=self.sock.recv(4096)
            except BlockingIOError: break
            if not data: raise ValueError('COM2 disconnected')
            self.received.extend(data)
            if len(self.received)>console.CONTROL_PREFIX_LIMIT+65536: raise ValueError('terminal output limit exceeded')
        _,output=console.split_output(bytes(self.received),partial=True)
        if output and not (shell.BANNER.startswith(output) or output.startswith(shell.BANNER)):
            raise ValueError('native shell banner differs')
        self.emit(display_text(output[self.shown:]));self.shown=len(output)
        retired=[apps.parse(m,'RETIRE') for m in session.extract_markers(debug) if m.startswith('POOLEOS:APPS RETIRE ')]
        if {v['task'] for v in retired if v['outcome']==1<<32} >= {2,3}: return True
        if not output.startswith(shell.BANNER): return False
        if not self.pending:
            char=self.read_key()
            if char is not None:
                if self.skip_extended: self.skip_extended=False
                elif char in ('\x00','\xe0'): self.skip_extended=True
                elif char in ('\x1d','\x03'): return True
                else: self.pending=terminal_byte(char)
        if self.pending:
            if self.sent>=8192: raise ValueError('terminal input limit exceeded')
            try: count=self.sock.send(self.pending)
            except BlockingIOError: count=0
            if count:
                self.payload+=self.pending[:count];self.sent+=count;self.pending=self.pending[count:]
        return False


def manual_summary(markers):
    # Arbitrary user commands cannot meet the fixed two-generation test scenario.
    starts=[apps.parse(m,'START') for m in markers if m.startswith('POOLEOS:APPS START ')]
    if len(starts)!=1 or starts[0]['bad_file']!=0 or markers.count(apps.FILE_MARKER)!=1:
        raise ValueError('normal native application startup missing')
    return dict(scope='manual_serial_session_not_a_qualification',startup=starts[0],production_ready=False)


def run_session(receipt: Path, work: Path, interaction, self_test: bool):
    report,path,disk=check_preview(receipt)
    if not work.resolve().is_relative_to((ROOT/'outputs').resolve()): raise ValueError('workspace session path required')
    work.mkdir(parents=True,exist_ok=False)
    before=source.source_bindings()
    lock,base=shared.tier0.validate_contracts(ROOT)
    qemu=shared.tier0._require_workspace_tool_path(shared.tier0.DEFAULT_QEMU_ROOT,ROOT)
    shared.tier0.verify_local_launch_runtime(lock,qemu,ROOT)
    result=dict(contract_id=optical.CONTRACT,status='fail',self_test=self_test,production_ready=False,
                iso_sha256=report['optical_images']['applications-1']['iso_sha256'],
                source_bindings=before,host_terminal=True,native_gui=False,guest_bound_seconds=240 if self_test else 900)
    try:
        run,_,handoff=shared.boot._execute_once('launcher-self-test' if self_test else 'manual-session',
            lock,optical.optical_profile(base),qemu,path,work,result['guest_bound_seconds'],
            marker_validator=(lambda m: apps.validate_markers(m,file_waits=report.get('file_waits',False))) if self_test else manual_summary,
            marker_extractor=session.extract_markers,hpet_msi=True,pause_on_completion=True,
            console_port=interaction.port,console_poll=interaction.poll,capture_log_limit_bytes=LOG_LIMIT)
        if self_test:
            case=interaction.case
            _,output=console.split_output(bytes(interaction.received))
            if interaction.payload[:interaction.sent]!=case.sent or output!=case.expected or not interaction.sustained_evidence:
                raise ValueError('launcher self-test did not complete exact interaction')
            prefix=run['marker_summary']['transfer_prefix']
            shared.load.validate_oracle_binding(prefix['boot_prefix'],shared.load.inspect_media_bytes(disk),run['pbp1_transcript'])
            result['sustained_window']=interaction.sustained_evidence
            result['nonce']=case.nonce
        result.update(status='pass',run=run)
    except Exception as error:
        result['failure']=f'{type(error).__name__}: {error}'
        print(result['failure'],file=sys.stderr)
    finally:
        interaction.close()
        (work/'console-input.bin').write_bytes(interaction.payload[:interaction.sent])
        (work/'console-output.bin').write_bytes(bytes(interaction.received))
        result['source_unchanged']=before==source.source_bindings()
        if not result['source_unchanged']: result['status']='fail'
        (work/'receipt.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return int(result['status']!='pass')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt',type=Path)
    parser.add_argument('--work-dir',type=Path)
    parser.add_argument('--self-test',action='store_true')
    args=parser.parse_args()
    try:
        receipt=args.receipt or ROOT/json.loads(local_file(ROOT/'outputs/native-userspace-preview.json',4096))['receipt']
        work=args.work_dir or ROOT/'outputs'/('preview-session-'+str(time.time_ns()))
        if args.self_test:
            interaction=qualification.Interaction(apps.scenario(secrets.token_hex(8)),sustained=True)
        else:
            if sys.platform!='win32' or not sys.stdin.isatty(): raise ValueError('interactive Windows terminal required')
            import msvcrt
            print('PooleOS unsigned native preview. Host serial terminal; no native desktop.\n'
                  'Ctrl+] closes the VM. Session limit: 15 minutes. No persistent storage.\n',flush=True)
            def emit(text):
                sys.stdout.write(text);sys.stdout.flush()
            interaction=Terminal(lambda:msvcrt.getwch() if msvcrt.kbhit() else None,emit)
        return run_session(receipt,work,interaction,args.self_test)
    except (OSError,ValueError,KeyError,TypeError) as error:
        print(f'Preview refused: {error}',file=sys.stderr);return 1


if __name__=='__main__': raise SystemExit(main())
