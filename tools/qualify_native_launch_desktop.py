"""Observe real graphical PLC1 launches, independent pixels and guarded lifetimes."""
from __future__ import annotations
import argparse
import json
import secrets
import time
from pathlib import Path
from runtime import native_application_input as pixels, native_surface_lifecycle
from tools import qualify_native_local_console as local
from tools.native_build_space import require_space

OPTIONS = dict(file_waits=True, windows=True, window_capacity=True,
               surface_lifecycle=True, launch_session=True)
HEADER_GLYPHS = dict(pixels.GLYPHS, T=(31,4,4,4,4,4,4),
                     N=(17,25,21,19,17,17,17), g=(0,15,17,17,15,1,14))
HEADER_GLYPHS.update({':': (0,12,12,0,12,12,0), '/': (1,2,2,4,8,8,16)})


def inspect_header(data, text):
    w, h, rgb = pixels.frame(data)
    if not text or len(text) > 35 or any(c not in HEADER_GLYPHS for c in text):
        raise ValueError('unsupported launch label')
    for y in range(16):
        for i, char in enumerate(text):
            bits = HEADER_GLYPHS[char][y//2] if y < 14 else 0
            for x in range(12):
                color = '253E37' if x < 10 and bits & (1 << (4-x//2)) else 'F7FAF9'
                at = ((8+y)*w+144+i*12+x)*3
                if rgb[at:at+3] != bytes.fromhex(color):
                    raise ValueError('launch status pixels differ')
    return dict(width=w, height=h, text=text, pixels_verified=len(text)*12*16)


def scenario(nonce, *, launch_failure=False):
    if type(launch_failure) is not bool:
        raise ValueError('explicit graphical diagnostic mode required')
    original = pixels.compact_scenario(local.apps.scenario(nonce, launch_failure=launch_failure))
    steps, actions, command = [], {}, []
    counts = {b'text': 0, b'numbers': 0}
    for step in original.steps:
        command.append(step)
        if step[0] != b'\r':
            continue
        line = b''.join(v[0] for v in command)[:-1]
        if line.startswith(b'start '):
            app = line.split()[1]
            counts[app] += 1
            draft = b'GUI'+nonce.encode()+str(len(actions)).encode()
            steps.extend((bytes([b]), bytes([b])) for b in b'echo '+draft)
            actions[len(steps)] = dict(app=app.decode(), generation=counts[app],
                                      mouse=app == b'text', draft=draft.decode())
            if launch_failure and counts[app] == 2:
                actions[len(steps)]['failure'] = True
            steps.append((b'\r', b'\r\n'+draft+b'\r\n'+local.apps.shell.PROMPT))
        else:
            steps.extend(command)
        command = []
    expected = 3 if launch_failure else 2
    if command or counts != {b'text': expected, b'numbers': expected}:
        raise ValueError('launch scenario incomplete')
    return local.apps.shell.Scenario('native-gui-launch', nonce, tuple(steps)), actions


class Interaction(local.Interaction):
    def __init__(self, *, launch_failure=False):
        # No serial send path: ordinary script bytes also enter as device keys.
        case, self.actions = scenario(secrets.token_hex(8), launch_failure=launch_failure)
        local.qualification.Interaction.__init__(self, case)
        self.inject = None
        self.keyboard_bytes = 0
        self.keyboard_batch = 1
        self.batches = []
        self.completed = set()
        self.ready = False

    def send_ready(self):
        if self.step in self.actions and self.step not in self.completed:
            self.ready = True
            return
        self.ready = False
        return super().send_ready()


class Probe:
    def __init__(self, work):
        self.work, self.step = work, None
        self.phase = 0
        self.sample = self.deadline = 0
        self.x = self.y = None
        self.left = False
        self.evidence, self.events = [], []
        self.action_boundaries = []
        self.captures = 0

    def capture(self, client):
        if self.captures >= 192:
            raise ValueError('launch capture bound')
        path = self.work/f'launch-{self.captures:03}.ppm'
        client.execute('screendump', {'filename': str(path), 'format': 'ppm'})
        self.captures += 1
        return path

    def tick(self, client, interaction, debug):
        if not interaction.ready or interaction.step in interaction.completed:
            return
        now = time.monotonic()
        if self.step != interaction.step:
            self.step, self.phase = interaction.step, 0
            self.deadline, self.sample = now+24, 0
        if now > self.deadline:
            raise TimeoutError(f'GUI launch {self.step} phase {self.phase} not observed')
        if now < self.sample:
            return
        self.sample = now+.35
        action = interaction.actions[self.step]
        failure = action.get('failure') is True
        boundary = None
        starting = self.phase == (1 if action['mouse'] else 0)
        if starting:
            markers = local.native_session.extract_markers(debug)
            identity = (4 if action['app'] == 'text' else 5, action['generation'])
            for kind in ('ADMIT', 'REJECT', 'FAILED'):
                for marker in markers:
                    if marker.startswith('POOLEOS:APPS '+kind+' '):
                        value = local.apps.parse(marker, kind)
                        if (value['task'], value['generation']) == identity:
                            raise ValueError('attempt already observed before fresh graphical input')
            samples = [local.apps.parse(m, 'RUN') for m in markers if m.startswith('POOLEOS:APPS RUN ')]
            if not samples:
                return
            boundary = dict(step=self.step, task=identity[0], generation=identity[1],
                            dispatches=samples[-1]['dispatches'])
        path = self.capture(client)
        data = path.read_bytes()
        w, h, rgb = pixels.frame(data)
        if self.x is None:
            self.x, self.y = w//2, h//2
        if self.phase < 3:
            if action['mouse']:
                target = (200, h-16)
                dx, dy = max(-96, min(96, target[0]-self.x)), max(-96, min(96, target[1]-self.y))
                at = (self.y*w+self.x)*3
                if self.events and rgb[at:at+3] != bytes.fromhex('172B24'):
                    return
                left = self.phase == 1
                events = [{'type': 'rel', 'data': {'axis': 'x', 'value': dx}},
                          {'type': 'rel', 'data': {'axis': 'y', 'value': dy}}]
                if (self.x+dx, self.y+dy) == target and left != self.left:
                    events.append({'type': 'btn', 'data': {'button': 'left', 'down': left}})
                    self.left = left
                client.execute('input-send-event', {'events': events})
                if starting:
                    self.action_boundaries.append(boundary)
                self.events.append(dict(step=self.step, phase=self.phase, events=events))
                self.x += dx
                self.y += dy
                if (self.x, self.y) == target:
                    self.phase += 1
                    if failure and self.phase == 2:
                        self.phase = 3  # Hold the button through failure acknowledgement.
            else:
                interaction.inject([0x3d])
                self.action_boundaries.append(boundary)
                self.events.append(dict(step=self.step, codes=[0x3d]))
                self.phase = 3
            return
        title = 'Text' if action['app'] == 'text' else 'Numbers'
        label = title + ((': launch failed / no surface' if self.phase in (3, 4)
                          else ': absent / no surface') if failure else
                         (': admitted / surface' if self.phase in (3, 4) else ': running / surface'))
        markers = local.native_session.extract_markers(debug)
        admits = [local.apps.parse(m, 'ADMIT') for m in markers if m.startswith('POOLEOS:APPS ADMIT ')]
        identity = (4 if action['app'] == 'text' else 5, action['generation'])
        admitted = {(v['task'], v['generation']) for v in admits}
        if failure:
            if identity in admitted or (identity[0], 3) in admitted:
                raise ValueError('failed or unrequested retry was admitted')
            failed = [local.apps.parse(m, 'FAILED') for m in markers if m.startswith('POOLEOS:APPS FAILED ')]
            if not any((v['task'], v['generation'], v['published']) == (*identity, 1) for v in failed):
                return
        elif identity not in admitted:
            return
        try:
            observed = inspect_header(data, label)
            if failure:
                visible = (action['app'] != 'text', action['app'] != 'numbers')
                observed['absent_surface'] = local.window_frames.inspect_ppm(data, expected=visible)
            else:
                observed['fresh_surface'] = pixels.inspect_rows(data, {identity[0]-4: {6: '', 7: ''}})
        except ValueError:
            return
        self.evidence.append(dict(step=self.step, phase=self.phase, action=action,
                                  frame=path.name, sha256=local.digest(path), pixels=observed))
        if self.phase == 3 and (not action['mouse'] or failure):
            # Repeat a still-held launch key: it must not refocus the new surface.
            if action['mouse']:
                events = [{'type': 'btn', 'data': {'button': 'left', 'down': True}}]
                client.execute('input-send-event', {'events': events})
                self.events.append(dict(step=self.step, events=events, held_repeat=True))
            else:
                interaction.inject([0x3d])
                self.events.append(dict(step=self.step, codes=[0x3d], held_repeat=True))
            self.phase = 4
        elif self.phase in (3, 4):
            if self.left:
                events = [{'type': 'btn', 'data': {'button': 'left', 'down': False}}]
                client.execute('input-send-event', {'events': events})
                self.events.append(dict(step=self.step, events=events, fresh_release=True))
                self.left = False
            key = 0x3c if action['app'] == 'text' else 0x3d
            codes = ([0xbd] if not action['mouse'] else [])+[0x2a, key, key|0x80, 0xaa]
            interaction.inject(codes)
            self.events.append(dict(step=self.step, codes=codes))
            self.phase = 5
        else:
            interaction.completed.add(self.step)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--backend', choices=('qemu', 'virtualbox'), default='qemu')
    parser.add_argument('--virtualbox', type=Path)
    parser.add_argument('--visible', action='store_true')
    parser.add_argument('--launch-failure', action='store_true')
    args = parser.parse_args()
    if args.launch_failure and args.backend != 'qemu':
        parser.error('launch-failure GUI qualification is currently QEMU-only')
    if args.visible and args.backend != 'virtualbox':
        parser.error('visible mode is VirtualBox-only')
    if args.backend == 'virtualbox' and args.virtualbox is None:
        parser.error('explicit VirtualBox executable required')
    if args.launch_failure:
        from tools.launch_native_userspace_iso import _check_qualification
        report, iso, disk = _check_qualification(args.receipt.resolve(), diagnostic_launch_failure=True)
        options = local.apps.launch_failure_options(report)
    else:
        report, iso, disk = local.check_preview(args.receipt.resolve())
        options = local.apps.profile_options(report)
    if report.get('launch_console_admission') is not True or report.get('launch_shell_admission') is not True:
        raise ValueError('explicit native launch console and shell required')
    work = args.work_dir.resolve()
    if not work.is_relative_to(local.ROOT/'outputs') or work == local.ROOT/'outputs':
        raise ValueError('new workspace output directory required')
    storage = require_space(work)
    work.mkdir(parents=True, exist_ok=False)
    before = local.source.source_bindings()
    interaction, probe = Interaction(launch_failure=args.launch_failure), Probe(work)
    result = dict(cycle=311, status='fail', source_bindings=before, storage_preflight=storage,
                  diagnostic_only=args.launch_failure, launch_failure=args.launch_failure,
                  iso_sha256=local.digest(iso), serial_input_bytes=0, production_ready=False,
                  native_plc1_control_verified=False, guest_bound_seconds=240,
                  backend=args.backend, visible=args.visible, application_profile=options,
                  physical_hardware_tested=False)
    started = time.monotonic()
    pointer = None
    try:
        shared = local.qualification.shared
        if args.backend == 'qemu':
            lock, base = shared.tier0.validate_contracts(local.ROOT)
            qemu = shared.tier0._require_workspace_tool_path(shared.tier0.DEFAULT_QEMU_ROOT, local.ROOT)
            shared.tier0.verify_local_launch_runtime(lock, qemu, local.ROOT)
            def control(client, debug):
                def inject(codes):
                    client.execute('input-send-event', {'events': [
                        {'type': 'key', 'data': {'down': not bool(c&128),
                                               'key': {'type': 'number', 'data': c&127}}} for c in codes]})
                interaction.inject = inject
                probe.tick(client, interaction, debug)
            run, _, _ = shared.boot._execute_once('native-gui-launch', lock, local.optical.optical_profile(base),
                qemu, iso, work, 240, marker_validator=lambda m: local.apps.validate_markers(m, **options),
                marker_extractor=local.native_session.extract_markers, hpet_msi=True, pause_on_completion=True,
                console_port=interaction.port, console_poll=interaction.poll,
                capture_log_limit_bytes=local.LOG_LIMIT, guest_control=control,
                frame_validator=native_surface_lifecycle.inspect_ppm)
        else:
            from runtime.native_virtualbox_mouse import PointerClient
            def control(owner, debug):
                nonlocal pointer
                if not interaction.ready:
                    return
                if pointer is None:
                    pointer = PointerClient(owner, args.virtualbox.resolve())
                probe.tick(pointer, interaction, debug)
            local.vbox_run(report, iso, work, interaction, result, args.virtualbox.resolve(),
                           args.visible, control)
            run = result['run']
            if pointer is None:
                raise ValueError('pointer API was not reached')
            pointer.check_shell()
        _, output = local.native_console.split_output(bytes(interaction.received))
        if (interaction.sent != len(interaction.case.sent) or output != interaction.case.expected or
                interaction.keyboard_bytes != interaction.sent or len(probe.evidence) != (16 if args.launch_failure else 10) or
                interaction.completed != set(interaction.actions) or b'start ' in interaction.case.sent):
            raise ValueError('inexact GUI launch or draft-preservation evidence')
        shared.load.validate_oracle_binding(run['marker_summary']['transfer_prefix']['boot_prefix'],
                                           shared.load.inspect_media_bytes(disk), run['pbp1_transcript'])
        result.update(status='pass', run=run, native_plc1_control_verified=True,
                      starts_verified=6 if args.launch_failure else 4,
                      inspections_verified=6 if args.launch_failure else 4,
                      terminal_drafts_preserved=6 if args.launch_failure else 4,
                      held_launch_repeats_verified=4 if args.launch_failure else 2,
                      graphical_failures_verified=2 if args.launch_failure else 0,
                      explicit_fresh_retries_verified=2 if args.launch_failure else 0,
                      hostile_marker_cases_rejected=local.apps.negative_controls(run['markers'], **options))
    except Exception as error:
        result['failure'] = f'{type(error).__name__}: {error}'
    finally:
        interaction.close()
        (work/'keyboard-input.bin').write_bytes(interaction.case.sent[:interaction.sent])
        (work/'console-output.bin').write_bytes(interaction.received)
        result.update(evidence=probe.evidence, events=probe.events, captures=probe.captures,
                      action_boundaries=probe.action_boundaries,
                      keyboard_input_bytes=interaction.keyboard_bytes,
                      source_unchanged=before == local.source.source_bindings(),
                      iso_unchanged=local.digest(iso) == result['iso_sha256'],
                      elapsed_seconds=round(time.monotonic()-started, 3))
        if pointer is not None:
            result['pointer_api_diagnostics'] = pointer.diagnostics
            result['pointer_api'] = dict(events=pointer.records, powershell_sha256=pointer.shell_hash,
                failed=pointer.failed, host_cursor_moved=False, unlocked_per_event=True,
                api_bound_seconds=5, maximum_events=96)
        if not result['source_unchanged'] or not result['iso_unchanged']:
            result['status'] = 'fail'
        (work/'receipt.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(result['status'], result.get('failure', ''), flush=True)
    return int(result['status'] != 'pass')


if __name__ == '__main__':
    raise SystemExit(main())
