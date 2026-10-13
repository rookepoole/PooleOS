"""Qualify six real CPL3 roles, useful application results and contained faults."""
from __future__ import annotations
import argparse, json, secrets, socket, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime import native_app_session as probe, native_shell, native_console, native_session
from tools import qualify_native_console_ipc as shared, qualify_native_user_entry as source
from tools.qualify_native_shell_process import program_inputs
from tools.native_build_space import require_space


class Interaction(shared.Interaction):
    def __init__(self, case):
        super().__init__(case.sent, False)
        self.case, self.step, self.expected = case, 0, native_shell.BANNER

    def poll(self, debug):
        if self.sock is None:
            self.sock = socket.create_connection(('127.0.0.1', self.port), timeout=2)
            self.sock.setblocking(False)
        while True:
            try: data = self.sock.recv(4096)
            except BlockingIOError: break
            if not data: raise ValueError('application shell disconnected')
            self.received.extend(data)
            if len(self.received) > native_console.CONTROL_PREFIX_LIMIT+16384: raise ValueError('unbounded application output')
        _, application = native_console.split_output(bytes(self.received), partial=True)
        if not self.expected.startswith(application):
            raise ValueError('application shell differs at step '+str(self.step)+': '+repr(application[-192:]))
        markers = native_session.extract_markers(debug)
        runs = [probe.parse(m,'RUN') for m in markers if m.startswith('POOLEOS:APPS RUN ')]
        if runs and runs[-1]['dispatches'] >= 128 and application == self.expected and self.step < len(self.case.steps):
            byte, response = self.case.steps[self.step]
            if self.sock.send(byte) == 1:
                self.sent += 1; self.step += 1; self.expected += response
        return bool(self.step == len(self.case.steps) and application == self.case.expected
                    and len(runs) >= 8 and all(v['live_mask'] == 3 for v in runs[-2:]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--program-dir', type=Path, required=True)
    args = parser.parse_args(); work, programs = args.work_dir.resolve(), args.program_dir.resolve()
    if not work.is_relative_to(ROOT/'outputs') or not programs.is_relative_to(ROOT/'outputs'):
        parser.error('workspace output paths required')
    storage = require_space(work); work.mkdir(parents=True, exist_ok=False)
    before = source.source_bindings()
    report = dict(cycle=283, contract_id='PAPPSESSION1', status='fail', source_bindings=before,
                  storage_preflight=storage, guest_bound_seconds=240, guest_runs=[], useful_applications=0,
                  bundled_files=False, iso_built=False, production_ready=False)
    try:
        cargo, _, env = shared._toolchain(ROOT/'.toolchains/rust-1.97.0')
        report['program_build'] = program_inputs(programs, env, probe.PROGRAMS)
        lock, profile = shared.tier0.validate_contracts(ROOT)
        qemu = shared.tier0._require_workspace_tool_path(shared.tier0.DEFAULT_QEMU_ROOT, ROOT)
        shared.tier0.verify_local_launch_runtime(lock, qemu, ROOT)
        print('Build two application kernels and a stale-file-grant control', flush=True)
        linked, kernel, plan = shared.entry._build_product(cargo, env, work/'kernel1', features=('development-applications',))
        linked2, kernel2, _ = shared.entry._build_product(cargo, env, work/'kernel2', features=('development-applications',))
        if (linked,kernel) != (linked2,kernel2): raise ValueError('independent kernel mismatch')
        bad_linked, bad, bad_plan = shared.entry._build_product(cargo, env, work/'bad-kernel', features=('development-applications-bad-file',))
        if bad == kernel: raise ValueError('stale grant control is not distinct')
        report['independent_kernel_builds_equal'] = True
        report['kernels'] = {}
        for name, image, link, layout in [('applications',kernel,linked,plan),('bad-file',bad,bad_linked,bad_plan)]:
            for _, key in probe.PROGRAMS:
                if image.count(Path(env[f'POOLEOS_{key}_CODE']).read_bytes()) != 1: raise ValueError('program embedding mismatch')
            (work/f'{name}.elf').write_bytes(image)
            report['kernels'][name] = dict(sha256=shared.sha(image), linked_sha256=shared.sha(link), bytes=len(image), image_pages=layout.image_byte_count//4096)
        development, report['boot_build'] = shared.boot._build_and_test(ROOT/'.toolchains/rust-1.97.0', work/'development', development_feature='development-user-root')
        files, config = shared.load.canonical_artifact_files(), shared.load.canonical_config_bytes()
        for name, image, bad_file in [('applications-1',kernel,False),('applications-2',kernel,False),('bad-file',bad,True)]:
            manifest = shared.load.canonical_manifest_bytes(image, files)
            retained = shared.transfer.canonical_retained_files(manifest, image, files)
            media = shared.load.build_media_bytes(development, config, manifest, image, files)
            if media != shared.load.build_media_bytes(development, config, manifest, image, files): raise ValueError('media mismatch')
            inspected = shared.load.inspect_media_bytes(media)
            path = work/f'{name}.img'; path.write_bytes(media)
            run_dir = work/name; run_dir.mkdir()
            case = probe.scenario(secrets.token_hex(8), bad_file=bad_file)
            interaction = Interaction(case)
            print(f'Native application session {name}: frozen 240-second bound', flush=True)
            try:
                run, _, handoff = shared.boot._execute_once(name, lock, profile, qemu, path, run_dir, 240,
                    marker_validator=lambda m: probe.validate_markers(m, bad_file=bad_file),
                    marker_extractor=native_session.extract_markers, hpet_msi=True, pause_on_completion=True,
                    console_port=interaction.port, console_poll=interaction.poll)
            finally:
                interaction.close()
                sent, output = interaction.payload[:interaction.sent], bytes(interaction.received)
                (run_dir/'console-input.bin').write_bytes(sent)
                (run_dir/'console-output.bin').write_bytes(output)
            _, application = native_console.split_output(output)
            if sent != case.sent or application != case.expected: raise ValueError('inexact application interaction')
            run['interaction'] = dict(nonce=case.nonce, input_hex=sent.hex(), output_hex=output.hex(),
                input_sha256=shared.sha(sent), output_sha256=shared.sha(output), exact_interaction=True,
                kernel_evidence_from_com2=False)
            if run['marker_summary']['program_bytes'] != [report['program_build']['programs'][n]['code_bytes'] for n,_ in probe.PROGRAMS]:
                raise ValueError('observed program sizes differ')
            prefix = run['marker_summary']['transfer_prefix']
            shared.load.validate_oracle_binding(prefix['boot_prefix'], inspected, run['pbp1_transcript'])
            run['transcript_binding'] = shared.transfer.validate_transcript_binding(prefix, run['pbp1_transcript'])
            run['independent_revalidation'] = shared.transfer.validate_revalidation_binding(prefix, handoff, retained)
            run['hostile_marker_cases_rejected'] = probe.negative_controls(run['markers'], bad_file=bad_file)
            run.update(media_sha256=shared.sha(media), kernel_sha256=shared.sha(image))
            report['guest_runs'].append(run)
        if before != source.source_bindings() or program_inputs(programs, env, probe.PROGRAMS) != report['program_build']:
            raise ValueError('source or input drift')
        report.update(status='pass', bundled_files=True, useful_applications=2)
    except Exception as error:
        report['failure'] = f'{type(error).__name__}: {error}'; print(report['failure'], flush=True)
    report['source_unchanged'] = before == source.source_bindings()
    (work/'receipt.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(f"PAPPSESSION1 {report['status']}; useful apps={report['useful_applications']} ISO=0 production=0", flush=True)
    return int(report['status'] != 'pass')


if __name__ == '__main__': raise SystemExit(main())
