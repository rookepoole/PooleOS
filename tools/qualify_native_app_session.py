"""Qualify six real CPL3 roles, useful application results and contained faults."""
from __future__ import annotations
import argparse, json, secrets, socket, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime import native_app_session as probe, native_shell, native_console, native_session
from runtime import native_cleanup_exhaustion as exhaustion
from runtime import native_userspace_iso as optical
from runtime import native_local_console, native_windows
from tools import qualify_native_console_ipc as shared, qualify_native_user_entry as source
from tools.qualify_native_shell_process import program_inputs
from tools.native_build_space import require_space


def cleanup_barriers(payload):
    """Wait before the following command, not by adding post-hoc wall-time sleeps."""
    generations = {b'text': 0, b'numbers': 0}
    result, offset = {}, 0
    for command in payload.split(b'\r')[:-1]:
        offset += len(command)+1
        words = command.split()
        if len(words) == 2 and words[1] in generations:
            if words[0] == b'start': generations[words[1]] += 1
            elif words[0] in (b'stop', b'fault'):
                result[offset] = (4 if words[1] == b'text' else 5, generations[words[1]])
    return result


def retirement_barriers(payload):
    result=cleanup_barriers(payload)
    generation,offset=0,0
    for command in payload.split(b'\r')[:-1]:
        offset+=len(command)+1
        if command==b'start text':
            generation+=1;result[offset]=(4,generation)
    return result


class Interaction(shared.Interaction):
    def __init__(self, case, deferred_cleanup=False, file_controls=False, exhaust_cleanup=False, sustained=False):
        super().__init__(case.sent, False)
        self.case, self.step, self.expected = case, 0, native_shell.BANNER
        self.barriers = cleanup_barriers(case.sent) if deferred_cleanup else {}
        self.observed_barriers = set()
        self.retirements = retirement_barriers(case.sent) if file_controls else {}
        self.observed_retirements = set()
        self.exhaust_cleanup = exhaust_cleanup
        self.exhaustion_barrier = case.sent.index(b'stop numbers\r')+len(b'stop numbers\r') if exhaust_cleanup else None
        self.exhaustion_observed = False
        self.sustained_barrier = case.sent.index(b'start numbers\r')+len(b'start numbers\r') if sustained else None
        self.sustained_first = None
        self.sustained_evidence = None

    def send_ready(self):
        byte, response = self.case.steps[self.step]
        if self.sock.send(byte) == 1:
            self.sent += 1; self.step += 1; self.expected += response

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
        exhausted = [probe.cleanup.parse(m,'EXHAUSTED') for m in markers if m.startswith(probe.cleanup.PREFIX+'EXHAUSTED ')]
        if runs and runs[-1]['dispatches'] >= 128 and application == self.expected and self.step < len(self.case.steps):
            if self.step == self.sustained_barrier:
                if self.sustained_first is None:
                    ready = [s for s in runs if s['live_mask'] == 63 and
                             all(s[f'calls{i}'] > 0 and s[f'ticks{i}'] > 0 for i in range(6))]
                    if not ready: return False
                    self.sustained_first = ready[-1]['dispatches']
                end = self.sustained_first + optical.SUSTAINED_DISPATCHES
                if runs[-1]['dispatches'] < end: return False
                self.sustained_evidence = optical.validate_sustained(runs, self.sustained_first, end)
            if self.step == self.exhaustion_barrier:
                if {(v['task'],v['generation']) for v in exhausted} != {(4,1),(5,1)}: return False
                self.exhaustion_observed = True
            if self.step in self.barriers:
                completed = [probe.cleanup.parse(m,'COMPLETE') for m in markers if m.startswith(probe.cleanup.PREFIX+'COMPLETE ')]
                if self.barriers[self.step] not in {(v['task'],v['generation']) for v in completed}: return False
                self.observed_barriers.add(self.step)
            if self.step in self.retirements:
                retired=[probe.parse(m,'RETIRE') for m in markers if m.startswith('POOLEOS:APPS RETIRE ')]
                if self.retirements[self.step] not in {(v['task'],v['generation']) for v in retired}: return False
                self.observed_retirements.add(self.step)
            self.send_ready()
        if self.exhaust_cleanup:
            return bool(self.step == len(self.case.steps) and application == self.case.expected
                        and self.exhaustion_observed and len(exhausted) == 2 and runs
                        and runs[-1]['dispatches'] >= max(v['dispatches'] for v in exhausted)+512
                        and len([m for m in markers if m.startswith(exhaustion.HOLD)]) >= 16)
        return bool(self.step == len(self.case.steps) and application == self.case.expected
                    and len(runs) >= 8 and all(v['live_mask'] == 3 for v in runs[-2:]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--program-dir', type=Path, required=True)
    parser.add_argument('--deferred-cleanup', action='store_true')
    parser.add_argument('--file-controls', action='store_true')
    parser.add_argument('--exhaust-cleanup', action='store_true')
    parser.add_argument('--claimed-requester', action='store_true')
    parser.add_argument('--optical', action='store_true')
    parser.add_argument('--desktop', action='store_true', help='opt-in native local-console optical development profile')
    parser.add_argument('--windows', action='store_true', help='opt-in native application surfaces and window manager')
    args = parser.parse_args(); work, programs = args.work_dir.resolve(), args.program_dir.resolve()
    if args.desktop and not args.optical: parser.error('local console requires the optical development profile')
    if args.windows and (not args.optical or args.desktop): parser.error('windows requires optical and is separate from the terminal profile')
    if sum((args.deferred_cleanup,args.file_controls,args.exhaust_cleanup,args.claimed_requester,args.optical)) > 1: parser.error('separate control profiles required')
    if not work.is_relative_to(ROOT/'outputs') or not programs.is_relative_to(ROOT/'outputs'):
        parser.error('workspace output paths required')
    storage = require_space(work); work.mkdir(parents=True, exist_ok=False)
    before = source.source_bindings()
    report = dict(cycle=296 if args.windows or args.desktop else 292 if args.optical else 287 if args.claimed_requester else 286 if args.exhaust_cleanup else 285 if args.file_controls else 284 if args.deferred_cleanup else 283,
                  contract_id=optical.CONTRACT if args.optical else 'PCLAIM1' if args.claimed_requester else 'PCLEANUP3' if args.exhaust_cleanup else 'PFILECONTROL1' if args.file_controls else 'PAPPRECOVERY1' if args.deferred_cleanup else 'PAPPSESSION1',
                  optical=args.optical, optical_images={}, file_waits=args.optical,
                  local_console=args.desktop or args.windows, window_surfaces=args.windows, graphical_desktop=False,
                  claimed_requester=args.claimed_requester,
                  exhaust_cleanup=args.exhaust_cleanup,
                  file_controls=args.file_controls,
                  deferred_cleanup=args.deferred_cleanup, status='fail', source_bindings=before,
                  storage_preflight=storage, guest_bound_seconds=240, guest_runs=[], useful_applications=0,
                  bundled_files=False, iso_built=False, production_ready=False)
    try:
        cargo, _, env = shared._toolchain(ROOT/'.toolchains/rust-1.97.0')
        selected=[('PooleFileProbe' if args.file_controls and key=='TEXT' else name,key) for name,key in probe.PROGRAMS]
        if args.desktop:
            selected=[('PooleDesktopConsole' if key=='CONSOLE' else name,key) for name,key in selected]
        if args.windows:
            selected=[({'CONSOLE':'PooleWindowConsole','TEXT':'PooleWindowText','NUMBERS':'PooleWindowNumbers'}.get(key,name),key) for name,key in selected]
        if args.claimed_requester:
            selected=[({'TEXT':'PooleWaitingFileProbe','COUNTER':'PooleClaimedFiles'}.get(key,name),key) for name,key in probe.PROGRAMS]
        report['program_build'] = program_inputs(programs, env, selected)
        lock, profile = shared.tier0.validate_contracts(ROOT)
        qemu = shared.tier0._require_workspace_tool_path(shared.tier0.DEFAULT_QEMU_ROOT, ROOT)
        shared.tier0.verify_local_launch_runtime(lock, qemu, ROOT)
        if args.optical: profile = optical.optical_profile(profile)
        print('Build two application kernels and a stale-file-grant control', flush=True)
        extra = ('development-shell-deferred-cleanup',) if args.deferred_cleanup else ()
        normal_features=('development-file-controls',) if args.file_controls else ('development-applications',)+extra
        bad_features=('development-file-controls','development-applications-bad-file') if args.file_controls else ('development-applications-bad-file',)+extra
        if args.desktop:
            normal_features=('development-desktop',)
            bad_features=('development-desktop','development-applications-bad-file')
        if args.windows:
            normal_features=('development-windows',)
            bad_features=('development-windows','development-applications-bad-file')
        if args.exhaust_cleanup:
            normal_features=('development-app-cleanup-exhaustion',)
            bad_features=normal_features+('development-applications-bad-file',)
        if args.claimed_requester:
            normal_features=('development-claimed-requester',)
            bad_features=normal_features+('development-applications-bad-file',)
        linked, kernel, plan = shared.entry._build_product(cargo, env, work/'kernel1', features=normal_features)
        linked2, kernel2, _ = shared.entry._build_product(cargo, env, work/'kernel2', features=normal_features)
        if (linked,kernel) != (linked2,kernel2): raise ValueError('independent kernel mismatch')
        bad_linked, bad, bad_plan = shared.entry._build_product(cargo, env, work/'bad-kernel', features=bad_features)
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
            if args.optical:
                variant = 'bad-file' if bad_file else 'applications'
                license_text = (ROOT/'LICENSE').read_bytes()
                iso, iso_report = optical.build_iso(media, license_text, variant)
                if iso != optical.build_iso(media, license_text, variant)[0]: raise ValueError('optical build mismatch')
                iso_report['architecture'] = optical.development_architecture(iso)
                if iso_report['architecture']['status'] != 'pass': raise ValueError('optical architecture rejected')
                if name == 'applications-2' and iso_report['iso_sha256'] != report['optical_images']['applications-1']['iso_sha256']:
                    raise ValueError('normal optical images differ')
                path = work/(optical.PRIMARY_NAME if name == 'applications-1' else name+'.iso')
                path.write_bytes(iso)
                iso_report.update(path=path.relative_to(ROOT).as_posix(), independent_builds_equal=True)
                report['optical_images'][name] = iso_report
            run_dir = work/name; run_dir.mkdir()
            scenario=probe.file_control_scenario if args.file_controls else probe.scenario
            if args.exhaust_cleanup: scenario=exhaustion.scenario
            case = probe.file_control_scenario(secrets.token_hex(8),bad_file=bad_file,claimed_requester=True) if args.claimed_requester else scenario(secrets.token_hex(8), bad_file=bad_file)
            interaction = Interaction(case, args.deferred_cleanup, args.file_controls or args.claimed_requester, args.exhaust_cleanup, sustained=args.optical)
            validator = (lambda m: exhaustion.validate_markers(m,bad_file=bad_file)) if args.exhaust_cleanup else (lambda m: probe.validate_markers(m, bad_file=bad_file, deferred_cleanup=args.deferred_cleanup, file_controls=args.file_controls,claimed_requester=args.claimed_requester,file_waits=args.optical,windows=args.windows))
            print(f'Native application session {name}: frozen 240-second bound', flush=True)
            try:
                run, _, handoff = shared.boot._execute_once(name, lock, profile, qemu, path, run_dir, 240,
                    marker_validator=validator,
                    marker_extractor=native_session.extract_markers, hpet_msi=True, pause_on_completion=True,
                    console_port=interaction.port, console_poll=interaction.poll,
                    frame_validator=native_windows.inspect_ppm if args.windows else native_local_console.inspect_ppm if args.desktop else None,
                    capture_log_limit_bytes=16*1024*1024 if args.optical else None)
            finally:
                interaction.close()
                sent, output = interaction.payload[:interaction.sent], bytes(interaction.received)
                (run_dir/'console-input.bin').write_bytes(sent)
                (run_dir/'console-output.bin').write_bytes(output)
            _, application = native_console.split_output(output)
            if sent != case.sent or application != case.expected: raise ValueError('inexact application interaction')
            if interaction.observed_barriers != set(interaction.barriers): raise ValueError('cleanup barriers not observed')
            if interaction.observed_retirements != set(interaction.retirements): raise ValueError('retirement barriers not observed')
            if args.exhaust_cleanup and not interaction.exhaustion_observed: raise ValueError('exhaustion barrier not observed')
            if args.optical:
                if not interaction.sustained_evidence: raise ValueError('sustained optical window missing')
                run['sustained_window'] = interaction.sustained_evidence
                run['iso_sha256'] = iso_report['iso_sha256']
            run['interaction'] = dict(nonce=case.nonce, input_hex=sent.hex(), output_hex=output.hex(),
                input_sha256=shared.sha(sent), output_sha256=shared.sha(output), exact_interaction=True,
                cleanup_barriers_observed=len(interaction.observed_barriers),
                retirement_barriers_observed=len(interaction.observed_retirements),
                exhaustion_barrier_observed=interaction.exhaustion_observed,
                kernel_evidence_from_com2=False)
            if run['marker_summary']['program_bytes'] != [report['program_build']['programs'][n]['code_bytes'] for n,_ in selected]:
                raise ValueError('observed program sizes differ')
            prefix = run['marker_summary']['transfer_prefix']
            shared.load.validate_oracle_binding(prefix['boot_prefix'], inspected, run['pbp1_transcript'])
            run['transcript_binding'] = shared.transfer.validate_transcript_binding(prefix, run['pbp1_transcript'])
            run['independent_revalidation'] = shared.transfer.validate_revalidation_binding(prefix, handoff, retained)
            run['hostile_marker_cases_rejected'] = exhaustion.negative_controls(run['markers'],bad_file=bad_file) if args.exhaust_cleanup else probe.negative_controls(run['markers'], bad_file=bad_file, deferred_cleanup=args.deferred_cleanup, file_controls=args.file_controls,claimed_requester=args.claimed_requester,file_waits=args.optical,windows=args.windows)
            run.update(media_sha256=shared.sha(media), kernel_sha256=shared.sha(image))
            report['guest_runs'].append(run)
        if args.optical:
            ordinary, report['ordinary_boot_build'] = shared.boot._build_and_test(ROOT/'.toolchains/rust-1.97.0', work/'ordinary')
            if ordinary == development or b'POOLEBOOT/0.1 TRANSFER_ARM PASS' in ordinary:
                raise ValueError('ordinary/development boot boundary differs')
            manifest = shared.load.canonical_manifest_bytes(kernel, files)
            disk = shared.load.build_media_bytes(ordinary, config, manifest, kernel, files)
            (work/'ordinary-denial.img').write_bytes(disk)
            iso, inspection = optical.build_iso(disk, license_text, 'ordinary-denial')
            if iso != optical.build_iso(disk, license_text, 'ordinary-denial')[0]: raise ValueError('ordinary optical mismatch')
            path = work/'ordinary-denial.iso'; path.write_bytes(iso)
            inspection.update(path=path.relative_to(ROOT).as_posix(), independent_builds_equal=True)
            report['optical_images']['ordinary-denial'] = inspection
            run_dir = work/'ordinary-denial'; run_dir.mkdir()
            print('Ordinary optical unsigned-denial control: frozen 45-second bound', flush=True)
            run, _, _ = shared.boot._execute_once('ordinary-denial', lock, profile, qemu, path, run_dir, 45,
                marker_validator=shared.load.validate_markers, marker_extractor=native_session.extract_markers, hpet_msi=True)
            if any('USER-ROOT' in m or 'POOLEOS:KERNEL:ENTRY' in m for m in run['markers']):
                raise ValueError('ordinary boot entered development path')
            shared.load.validate_oracle_binding(run['marker_summary'], shared.load.inspect_media_bytes(disk), run['pbp1_transcript'])
            run['iso_sha256'] = inspection['iso_sha256']
            report['ordinary_denial'] = run
            report['iso_built'] = True
        if before != source.source_bindings() or program_inputs(programs, env, selected) != report['program_build']:
            raise ValueError('source or input drift')
        report.update(status='pass', bundled_files=True, useful_applications=1 if args.file_controls or args.claimed_requester else 2)
    except Exception as error:
        report['failure'] = f'{type(error).__name__}: {error}'; print(report['failure'], flush=True)
    report['source_unchanged'] = before == source.source_bindings()
    (work/'receipt.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(f"{report['contract_id']} {report['status']}; useful apps={report['useful_applications']} ISO={int(report['iso_built'])} production=0", flush=True)
    return int(report['status'] != 'pass')


if __name__ == '__main__': raise SystemExit(main())
