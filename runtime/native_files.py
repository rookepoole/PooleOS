"""PFILE1 file-session oracle. COM2 contents are not kernel execution evidence."""
from __future__ import annotations
import re
from runtime import native_shell as shell, native_shell_process as control

PROGRAMS = [('PooleFileInit', 'INIT'), ('PooleFiles', 'COUNTER'),
            ('PooleConsoleService', 'CONSOLE'), ('PooleFileShell', 'CONSOLE_CLIENT'),
            ('PooleWorker', 'WORKER')]
README = (b'PooleOS native user-space integration\r\n'
          b'This immutable bundle is served by an isolated user process over capability IPC.\r\n'
          b'No host filesystem is mounted.\r\n')
VERSION = b'PooleOS native development / PFILE1\r\n'
NUMBERS = b'value\r\n3\r\n5\r\n8\r\n13\r\n21\r\n'
LISTING = b'/readme.txt\r\n/version.txt\r\n/numbers.csv\r\n/empty.txt\r\n'

def validate_markers(markers: list[str], *, bad_owner: bool = False) -> dict:
    # The shared runner's third-control boolean means bad file grant in this lane,
    # not a denied launch factory. Both process factories remain valid.
    if len(markers) <= 29:
        raise ValueError('missing file launch binding')
    expected = ('POOLEOS:CONTROL FILES contract=PSHELLPROC1 version=1 init_slot=0 '
                f'service_slot=1 shell_slot=3 bad_handle={int(bad_owner)} grants=8 cpl=3 production=0')
    if markers[29] != expected:
        raise ValueError('file roles or authority control differ')
    result = control.validate_markers(markers[:29] + markers[30:])
    result.update(file_contract='PFILE1', file_service_slot=1, file_shell_slot=3,
                  legacy_counter_field_means_file_service=True, bad_file_handle=bad_owner,
                  bundled_files=False, file_contents_require_exact_com2_and_binary_binding=True)
    return result

def scenario(nonce: str, *, bad_owner: bool = False) -> shell.Scenario:
    base = control.scenario(nonce)
    steps = []
    def command(line: bytes, result: bytes, *, local: bool = False):
        if bad_owner and not local:
            result = b'File service unavailable.\r\n'
        steps.extend((bytes([b]), bytes([b])) for b in line)
        steps.append((b'\r', b'\r\n' + result + shell.PROMPT))
    command(b'ls', LISTING)
    command(b'cat /version.txt', VERSION)
    command(b'cat /readme.txt', README)
    command(b'cat /numbers.csv', NUMBERS)
    command(b'cat /empty.txt', b'')
    command(b'cat /missing.txt', b'File not found.\r\n')
    command(b'cat /../readme.txt', b'Invalid path.\r\n', local=True)
    command(b'cat /' + b'x' * 40, b'Invalid path.\r\n', local=True)
    command(b'cat /version.txt', VERSION)
    command(b'ls /', LISTING)
    split = base.sent.index(b'exit\r')
    if any(len(sent) != 1 for sent, _ in base.steps):
        raise ValueError('base scenario is no longer byte stepped')
    return shell.Scenario('file-denied' if bad_owner else 'file-session', nonce,
                          base.steps[:split] + tuple(steps) + base.steps[split:])

def negative_controls(markers: list[str], *, bad_owner: bool = False) -> int:
    validate_markers(markers, bad_owner=bad_owner)
    cases = []
    for field in ('version', 'init_slot', 'service_slot', 'shell_slot', 'bad_handle', 'grants', 'cpl', 'production'):
        bad = markers.copy()
        bad[29] = re.sub(r' ' + field + r'=[0-9]+', ' ' + field + '=99', bad[29])
        cases.append(bad)
    cases.extend([markers[:29] + markers[30:], markers[:30] + [markers[29]] + markers[30:]])
    for case in cases:
        try:
            validate_markers(case, bad_owner=bad_owner)
        except ValueError:
            continue
        raise ValueError('hostile file launch accepted')
    return len(cases) + control.negative_controls(markers[:29] + markers[30:])
