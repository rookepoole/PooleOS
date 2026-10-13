"""Build and observe isolated shell-controlled native processes in three guests."""
from __future__ import annotations
import argparse, json, secrets, socket, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime import native_shell_process as probe, native_user_program, native_shell, native_console, native_session
from runtime import native_shell_cleanup as cleanup
from runtime import native_prepared_cleanup as prepared
from runtime import native_shell_orphan as orphan
from tools import qualify_native_console_ipc as shared, qualify_native_user_entry as source
from tools.qualify_native_user_programs import bindings as program_bindings
from tools.native_build_space import require_space

PROGRAMS = [('PooleInit','INIT'), ('PooleCounter','COUNTER'), ('PooleConsoleService','CONSOLE'),
    ('PooleControlShell','CONSOLE_CLIENT'), ('PooleWorker','WORKER')]

def program_inputs(directory, env):
    receipt = json.loads((directory/'receipt.json').read_bytes())
    if receipt.get('status') != 'pass' or receipt.get('source_unchanged') is not True or receipt.get('direct_byte_equality') is not True or receipt.get('independent_builds') != 2 or receipt.get('source_bindings') != program_bindings():
        raise ValueError('failed or stale program qualification')
    for name,key in PROGRAMS:
        code = (directory/f'build1-{name}.bin').read_bytes()
        if code != (directory/f'build2-{name}.bin').read_bytes() or shared.sha(code) != receipt['programs'][name]['code_sha256']:
            raise ValueError('independent code mismatch')
        for build in ('build1','build2'):
            snapshot = directory/f'{build}-{name}.elf'
            elf = (snapshot if snapshot.is_file() else directory/build/'x86_64-unknown-none/release'/name).read_bytes()
            extracted, record = native_user_program.extract(elf)
            if extracted != code or record['elf_sha256'] != receipt['programs'][name]['elf_sha256']:
                raise ValueError('independent ELF mismatch')
        env[f'POOLEOS_{key}_CODE'] = str(directory/f'build1-{name}.bin')
    return receipt

class Interaction(shared.Interaction):
    def __init__(self, case, *, owner_death=False):
        super().__init__(case.sent, False)
        self.case, self.step, self.expected = case, 0, native_shell.BANNER
        self.final_mask = 7 if owner_death else 3

    def poll(self, debug):
        if self.sock is None:
            self.sock = socket.create_connection(('127.0.0.1', self.port), timeout=2)
            self.sock.setblocking(False)
        while True:
            try: data = self.sock.recv(4096)
            except BlockingIOError: break
            if not data: raise ValueError('control shell disconnected')
            self.received.extend(data)
            if len(self.received) > native_console.CONTROL_PREFIX_LIMIT+8192: raise ValueError('unbounded shell output')
        _, application = native_console.split_output(bytes(self.received), partial=True)
        if not self.expected.startswith(application): raise ValueError('process shell output differs from challenge: '+repr(application[-160:]))
        markers = native_session.extract_markers(debug)
        runs = [probe.parse(m,'RUN') for m in markers if m.startswith('POOLEOS:CONTROL RUN ')]
        if runs and runs[-1]['dispatches'] >= 128 and application == self.expected and self.step < len(self.case.steps):
            byte, response = self.case.steps[self.step]
            if self.sock.send(byte) == 1:
                self.sent += 1; self.step += 1; self.expected += response
        return bool(self.step == len(self.case.steps) and application == self.case.expected
            and len(runs) >= 8 and all(v['live_mask'] == self.final_mask for v in runs[-2:]))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--program-dir', type=Path, required=True)
    parser.add_argument('--cleanup-retry', action='store_true')
    parser.add_argument('--prepared-stop', action='store_true')
    parser.add_argument('--owner-death', action='store_true')
    args = parser.parse_args(); work, programs = args.work_dir.resolve(), args.program_dir.resolve()
    if not work.is_relative_to(ROOT/'outputs') or not programs.is_relative_to(ROOT/'outputs'):
        parser.error('workspace output paths required')
    storage = require_space(work); work.mkdir(parents=True, exist_ok=False)
    before = source.source_bindings()
    report = dict(cycle=277, contract_id='PJOB1' if args.owner_death else 'PCANCEL1' if args.prepared_stop else 'PRECLAIM1' if args.cleanup_retry else 'PSHELLPROC1', status='fail', source_bindings=before,
        storage_preflight=storage, guest_bound_seconds=180, guest_runs=[], useful_applications=0,
        bundled_files=False, iso_built=False, production_ready=False)
    oracle = cleanup if args.cleanup_retry else probe
    features = ('development-shell-cleanup-retry',) if args.cleanup_retry else ('development-shell-process',)
    bad_features = ('development-shell-cleanup-retry','development-shell-process-bad-owner') if args.cleanup_retry else ('development-shell-process-bad-owner',)
    if args.prepared_stop:
        oracle = prepared
        features = ('development-shell-prepared-stop',)
        bad_features = ('development-shell-prepared-stop', 'development-shell-process-bad-owner')
    if args.owner_death:
        oracle = orphan
        if not args.prepared_stop:
            features = ('development-shell-cleanup-retry',)
            bad_features = ('development-shell-cleanup-retry', 'development-shell-process-bad-owner')
    try:
        cargo, _, env = shared._toolchain(ROOT/'.toolchains/rust-1.97.0')
        report['program_build'] = program_inputs(programs, env)
        lock, profile = shared.tier0.validate_contracts(ROOT)
        qemu = shared.tier0._require_workspace_tool_path(shared.tier0.DEFAULT_QEMU_ROOT, ROOT)
        shared.tier0.verify_local_launch_runtime(lock, qemu, ROOT)
        print('Build two process-shell kernels and denied-factory control', flush=True)
        linked, kernel, plan = shared.entry._build_product(cargo, env, work/'kernel1', features=features)
        linked2, kernel2, _ = shared.entry._build_product(cargo, env, work/'kernel2', features=features)
        if (linked,kernel) != (linked2,kernel2): raise ValueError('independent kernel mismatch')
        bad_linked, bad, bad_plan = shared.entry._build_product(cargo, env, work/'bad-kernel', features=bad_features)
        if bad == kernel: raise ValueError('denied authority control is not distinct')
        report['independent_kernel_builds_equal'] = True
        report['kernels'] = {}
        for name, image, link, layout in [('shell',kernel,linked,plan),('bad-owner',bad,bad_linked,bad_plan)]:
            for _, key in PROGRAMS:
                if image.count(Path(env[f'POOLEOS_{key}_CODE']).read_bytes()) != 1: raise ValueError('program embedding mismatch')
            (work/f'{name}.elf').write_bytes(image)
            report['kernels'][name] = dict(sha256=shared.sha(image), linked_sha256=shared.sha(link), bytes=len(image), image_pages=layout.image_byte_count//4096)
        development, report['boot_build'] = shared.boot._build_and_test(ROOT/'.toolchains/rust-1.97.0', work/'development', development_feature='development-user-root')
        files, config = shared.load.canonical_artifact_files(), shared.load.canonical_config_bytes()
        for name, image, bad_owner in [('control-1',kernel,False),('control-2',kernel,False),('bad-owner',bad,True)]:
            manifest = shared.load.canonical_manifest_bytes(image, files)
            retained = shared.transfer.canonical_retained_files(manifest, image, files)
            media = shared.load.build_media_bytes(development, config, manifest, image, files)
            if media != shared.load.build_media_bytes(development, config, manifest, image, files): raise ValueError('media mismatch')
            inspected = shared.load.inspect_media_bytes(media)
            path = work/f'{name}.img'; path.write_bytes(media)
            run_dir = work/name; run_dir.mkdir()
            case = (orphan if args.owner_death else probe).scenario(secrets.token_hex(8), bad_owner=bad_owner)
            oracle_options = dict(bad_owner=bad_owner)
            if args.owner_death: oracle_options['prepared_stop'] = args.prepared_stop
            interaction = Interaction(case, owner_death=args.owner_death)
            print(f'Native process shell {name}: frozen 180-second bound', flush=True)
            try:
                run, _, handoff = shared.boot._execute_once(name, lock, profile, qemu, path, run_dir, 180,
                    marker_validator=lambda m: oracle.validate_markers(m, **oracle_options),
                    marker_extractor=native_session.extract_markers, hpet_msi=True, pause_on_completion=True,
                    console_port=interaction.port, console_poll=interaction.poll)
            finally:
                interaction.close()
                sent, output = interaction.payload[:interaction.sent], bytes(interaction.received)
                (run_dir/'console-input.bin').write_bytes(sent)
                (run_dir/'console-output.bin').write_bytes(output)
            _, application = native_console.split_output(output)
            if sent != case.sent or application != case.expected: raise ValueError('inexact process shell interaction')
            run['interaction'] = dict(nonce=case.nonce, input_hex=sent.hex(), output_hex=output.hex(),
                input_sha256=shared.sha(sent), output_sha256=shared.sha(output), exact_interaction=True,
                kernel_evidence_from_com2=False, useful_applications=0)
            if run['marker_summary']['program_bytes'] != [report['program_build']['programs'][n]['code_bytes'] for n,_ in PROGRAMS]:
                raise ValueError('observed program sizes differ')
            prefix = run['marker_summary']['transfer_prefix']
            shared.load.validate_oracle_binding(prefix['boot_prefix'], inspected, run['pbp1_transcript'])
            run['transcript_binding'] = shared.transfer.validate_transcript_binding(prefix, run['pbp1_transcript'])
            run['independent_revalidation'] = shared.transfer.validate_revalidation_binding(prefix, handoff, retained)
            run['hostile_marker_cases_rejected'] = oracle.negative_controls(run['markers'], **oracle_options)
            run.update(media_sha256=shared.sha(media), kernel_sha256=shared.sha(image))
            report['guest_runs'].append(run)
        if before != source.source_bindings() or program_inputs(programs, env) != report['program_build']:
            raise ValueError('source or input drift')
        report['status'] = 'pass'
    except Exception as error:
        report['failure'] = f'{type(error).__name__}: {error}'; print(report['failure'], flush=True)
    report['source_unchanged'] = before == source.source_bindings()
    (work/'receipt.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(f"PSHELLPROC1 {report['status']}; useful apps=0 files=0 ISO=0 production=0", flush=True)
    return int(report['status'] != 'pass')

if __name__ == '__main__': raise SystemExit(main())
