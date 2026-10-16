"""Bounded relative events for an admitted, disposable VirtualBox guest only."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

from runtime import native_virtualbox as vbox

ROOT = Path(__file__).resolve().parents[1]
SHELL = Path('C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe')
SCRIPT = ROOT / 'tools/native_virtualbox_mouse.ps1'


def validate_motion(dx, dy, left):
    if (type(dx) is not int or type(dy) is not int or type(left) is not bool
            or not -96 <= dx <= 96 or not -96 <= dy <= 96):
        raise ValueError('bounded integer motion and boolean left button required')


def validate_ack(text, identity, sequence, dx, dy, left):
    if len(text) > 4096:
        raise ValueError('mouse response exceeds bound')
    ack = json.loads(text)
    expected = dict(identity=identity, sequence=sequence, dx=dx, dy=dy,
                    left=int(left), relative=True, unlocked=True)
    if (not isinstance(ack, dict) or ack.keys() != expected.keys()
            or any(type(ack[k]) is not type(v) or ack[k] != v for k, v in expected.items())):
        raise ValueError('mouse event or unlock acknowledgement differs')
    return ack


class PointerClient:
    """Two-operation adapter for the unchanged pointer challenge and pixel oracle."""
    def __init__(self, owner, executable, *, run=subprocess.run):
        if not owner.create_completed or owner.admission is None:
            raise ValueError('owned admitted VM required')
        if owner.info(identity_only=True).get('VMState') != 'running':
            raise ValueError('owned VM must be running')
        self.owner, self.executable, self.run = owner, executable, run
        profile = json.loads((ROOT / 'specs/native-virtualbox-mouse-profile.json').read_bytes())
        if (profile.get('contract_id') != 'PVBMOUSE1'
                or profile.get('maximum_axis_delta') != 96
                or profile.get('event_bound_seconds') != 5
                or profile.get('maximum_events') != 96):
            raise ValueError('mouse profile limits differ')
        self.shell_hash = profile['powershell_sha256']
        self.check_shell()
        self.left = False
        self.records = []
        self.diagnostics = []
        self.failed = False

    def check_shell(self):
        if hashlib.sha256(vbox.bounded_read(SHELL, 4 * 1024 * 1024)).hexdigest().upper() != self.shell_hash:
            raise ValueError('PowerShell executable identity changed')

    def move(self, dx, dy, left):
        validate_motion(dx, dy, left)
        if self.failed or len(self.records) >= 96:
            raise ValueError('mouse channel failed or exhausted')
        self.check_shell()
        sequence = len(self.records)
        command = [str(SHELL), '-NoLogo', '-NoProfile', '-NonInteractive', '-File', str(SCRIPT),
                   '-Identity', self.owner.identity, '-Name', self.owner.name,
                   '-Config', str(self.owner.config), '-Runtime', str(self.executable.parent),
                   '-Dx', str(dx), '-Dy', str(dy), '-Left', str(int(left)), '-Sequence', str(sequence)]
        try:
            result = self.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self.diagnostics.append(dict(sequence=sequence,return_code=result.returncode,
                stdout=result.stdout[:4096].decode('utf-8-sig',errors='replace'),
                stderr=result.stderr[:4096].decode('utf-8-sig',errors='replace')))
            if result.returncode or result.stderr or len(result.stdout) > 4096:
                raise ValueError('mouse API command failed or emitted unexpected output')
            ack = validate_ack(result.stdout.decode('utf-8-sig'), self.owner.identity, sequence, dx, dy, left)
        except Exception:
            # Never retry an event with an unknown side-effect outcome.
            self.failed = True
            raise
        self.records.append({k: v for k, v in ack.items() if k != 'identity'})
        self.left = left

    def execute(self, operation, arguments):
        if operation == 'screendump':
            path = Path(arguments.get('filename', '')).resolve()
            import re
            if (set(arguments) != {'filename', 'format'} or arguments['format'] != 'ppm'
                    or path.parent != self.owner.work.resolve()
                    or not re.fullmatch(r'pointer-(?:before|\d{2}-\d{2})\.ppm', path.name)):
                raise ValueError('owned pointer capture path required')
            png = path.with_suffix('.png')
            self.owner.checked('controlvm', self.owner.identity, 'screenshotpng', png)
            from PIL import Image
            if png.stat().st_size > 32 * 1024 * 1024:
                raise ValueError('pointer capture exceeds bound')
            with Image.open(png) as frame:
                if not 1000 <= frame.width <= 4096 or not 600 <= frame.height <= 2160:
                    raise ValueError('pointer capture geometry differs')
                data = frame.convert('RGB').tobytes()
                path.write_bytes(f'P6\n{frame.width} {frame.height}\n255\n'.encode('ascii') + data)
            return
        if operation != 'input-send-event' or set(arguments) != {'events'}:
            raise ValueError('unsupported pointer operation')
        events = arguments['events']
        if not isinstance(events, list) or len(events) not in (2, 3):
            raise ValueError('two axes and optional left transition required')
        deltas = []
        for event, axis in zip(events, ('x', 'y')):
            if (not isinstance(event, dict) or set(event) != {'type', 'data'}
                    or event['type'] != 'rel' or not isinstance(event['data'], dict)
                    or set(event['data']) != {'axis', 'value'} or event['data']['axis'] != axis):
                raise ValueError('relative pointer axis required')
            deltas.append(event['data']['value'])
        left = self.left
        if len(events) == 3:
            event = events[2]
            if (not isinstance(event, dict) or set(event) != {'type', 'data'}
                    or event['type'] != 'btn' or not isinstance(event['data'], dict)
                    or set(event['data']) != {'button', 'down'} or event['data']['button'] != 'left'):
                raise ValueError('left button transition required')
            left = event['data']['down']
        self.move(*deltas, left)
