"""Controlled native drag/held-modifier retirement, with explicit serial controls."""
import time
from runtime import native_input_lifetime as frames, native_application_input as cells
from tools.qualify_native_windows import WindowInteraction, bounded_motion, local


class LifetimeInteraction(WindowInteraction):
    def __init__(self, keyboard_batch=1):
        super().__init__(keyboard_batch, True, True)
        self.pointer_done = True
        self.controls = frames.controls(self.case.sent)
        self.allowed = set()
        self.recovered = set()
        self.completed = set()
        self.serial_controls = bytearray()
        self.connection = None

    def blocked(self):
        for n, control in enumerate(self.controls):
            if (self.step == control['start'] and n not in self.allowed or
                self.step == control['end'] and n not in self.recovered or
                self.step == control['status_end'] and n not in self.completed):
                return True
        return super().blocked()

    def wrap(self, connection):
        self.connection = connection
        return super().wrap(connection)

    def send_ready(self):
        if self.blocked():
            return
        if any(c['start'] <= self.step < c['end'] for c in self.controls):
            byte, response = self.case.steps[self.step]
            if self.connection is None:
                raise ValueError('unbound control channel')
            try:
                sent = self.connection.send(byte)
            except BlockingIOError:
                return
            if sent != 1:
                raise ValueError('control channel did not accept one byte')
            self.serial_controls.extend(byte)
            self.sent += 1
            self.step += 1
            self.expected += response
            return
        return super().send_ready()


class LifetimeProbe:
    MAX_CAPTURES = 192
    ACTION_SECONDS = 12

    def __init__(self, work):
        self.work = work
        self.scenario = 0
        self.step = 0
        self.pending = False
        self.deadline = 0
        self.sample = 0
        self.captures = 0
        self.evidence = []
        self.movements = []
        self.codes = []
        self.width = None

    @property
    def done(self):
        return self.scenario == 2

    def finish(self, record):
        self.evidence.append(dict(scenario=self.scenario, step=self.step, **record))
        self.pending = False
        self.deadline = 0
        self.step += 1
        if self.step == 12:
            self.step = 0
            self.scenario += 1

    def tick(self, client, interaction, debug):
        if self.done or not interaction.sustained_evidence:
            return
        control = interaction.controls[self.scenario]
        if interaction.step < control['start']:
            return
        now = time.monotonic()
        if not self.deadline:
            self.deadline = now+self.ACTION_SECONDS
        if now > self.deadline:
            raise TimeoutError(f'input lifetime scenario {self.scenario} step {self.step}')
        if self.width is None:
            path = self.work/'pointer-before.ppm'
            client.execute('screendump', {'filename': str(path), 'format': 'ppm'})
            local.window_frames.inspect_ppm(path.read_bytes())
            self.width, self.height, _ = cells.frame(path.read_bytes())
            self.x, self.y, self.left = self.width//2, self.height//2, False
        target = control['target']
        app_x, app_y = self.width-(320 if target == 0 else 336), 72 if target == 0 else 264
        if self.step == 5:
            interaction.allowed.add(self.scenario)
            _, output = local.native_console.split_output(bytes(interaction.received), partial=True)
            retired = [local.apps.parse(m, 'RETIRE') for m in local.native_session.extract_markers(debug)
                       if m.startswith('POOLEOS:APPS RETIRE ')]
            if interaction.step == control['end'] and output == interaction.expected and any(
                    (r['task'], r['generation']) == (target+4, 1) for r in retired):
                self.finish(dict(event='RETIRE', task=target+4, generation=1, control_bytes=len(control['command'])))
            return
        if self.step == 11:
            interaction.recovered.add(self.scenario)
            _, output = local.native_console.split_output(bytes(interaction.received), partial=True)
            if interaction.step == control['status_end'] and output == interaction.expected:
                interaction.inject([0xaa])
                self.codes.append(dict(scenario=self.scenario, step=self.step, codes=[0xaa]))
                interaction.completed.add(self.scenario)
                self.finish(dict(event='STATUS', step_ack=interaction.step, exact_response=True))
            return
        motion = {
            0: (app_x+100, app_y+12, False), 1: (app_x+100, app_y+12, True),
            2: (app_x+60, app_y+44, True), 3: (app_x+100, app_y+12, True),
            6: (40, 60, True), 8: (40, 60, False), 9: (40, 60, True), 10: (40, 60, False),
        }.get(self.step)
        if not self.pending:
            if motion is not None:
                tx, ty, tl = motion
                dx, dy = bounded_motion(self.x, self.y, tx, ty)
                x, y = self.x+dx, self.y+dy
                left = tl if (x, y) == (tx, ty) else self.left
                events = [{'type': 'rel', 'data': {'axis': 'x', 'value': dx}},
                          {'type': 'rel', 'data': {'axis': 'y', 'value': dy}}]
                if left != self.left:
                    events.append({'type': 'btn', 'data': {'button': 'left', 'down': left}})
                client.execute('input-send-event', {'events': events})
                self.x, self.y, self.left = x, y, left
            else:
                codes = [0x2a, 0x1e, 0x9e] if self.step == 4 else [0x2c, 0xac]
                interaction.inject(codes)
                self.codes.append(dict(scenario=self.scenario, step=self.step, codes=codes))
            self.pending = True
            self.sample = now+.6
            return
        if now < self.sample:
            return
        if self.captures >= self.MAX_CAPTURES:
            raise ValueError('input lifetime capture bound exhausted')
        self.sample = now+.3
        path = self.work/f'application-{self.captures:03}.ppm'
        self.captures += 1
        client.execute('screendump', {'filename': str(path), 'format': 'ppm'})
        data = path.read_bytes()
        try:
            if (frames.pixel(data, self.x, self.y) != bytes.fromhex('172B24') or
                frames.pixel(data, self.x+1, self.y+6) != b'\xff\xff\xff' or
                frames.pixel(data, self.x, self.y+17) != bytes.fromhex('172B24')):
                raise ValueError('pointer did not arrive')
            arrived = motion is None or (self.x, self.y, self.left) == motion
            observation = None
            if arrived and self.step in (1, 2, 3):
                x, y = (app_x-40, app_y+32) if self.step == 2 else (app_x, app_y)
                if frames.pixel(data, x, y) != bytes.fromhex('508D78'):
                    raise ValueError('drag/focus not observed')
                observation = dict(focused_border=[x, y, '508D78'])
            elif arrived and self.step == 4:
                observation = cells.inspect_rows(data, {target: {6: 'A', 7: ''}})
            elif arrived and self.step >= 6:
                observation = frames.boundary(data, target, focused_terminal=self.step >= 9)
        except ValueError:
            return
        record = dict(frame=path.name, sha256=local.digest(path), observation=observation)
        if motion is not None:
            self.movements.append(dict(scenario=self.scenario, step=self.step,
                                       x=self.x, y=self.y, left=self.left, **record))
        if not arrived:
            self.pending = False
            return
        self.finish(record)
