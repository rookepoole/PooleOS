"""PAPPSESSION1 oracle. Console text alone never proves native execution."""
from __future__ import annotations
import re
from runtime import native_kernel_transfer as transfer, native_shell as shell, native_files as files

PROGRAMS = [('PooleFileInit', 'INIT'), ('PooleAppFiles', 'COUNTER'),
            ('PooleConsoleService', 'CONSOLE'), ('PooleAppShell', 'CONSOLE_CLIENT'),
            ('PooleText', 'TEXT'), ('PooleNumbers', 'NUMBERS')]
FIELDS = {
    'START': 'bad_file init_bytes files_bytes console_bytes shell_bytes text_bytes numbers_bytes image_pages firmware_pages root0 root1 root2 root3 root4 root5',
    'HANDOFF': 'task generation control files startup_files bytes entered dispatches',
    'ADMIT': 'task generation sequence handle root owned_pages dispatches',
    'RETIRE': 'task generation outcome calls released_pages dispatches',
    'RUN': 'dispatches cr3_writes extra_flushes pages calls0 calls1 calls2 calls3 calls4 calls5 ticks0 ticks1 ticks2 ticks3 ticks4 ticks5 live_mask generation4 generation5 retired unused',
}
FILE_MARKER = ('POOLEOS:APPS FILES contract=PAPPSESSION1 version=1 init_slot=0 '
               'service_slot=1 shell_slot=3 bad_handle=0 grants=8 cpl=3 production=0')


def parse(line: str, event: str) -> dict:
    names = FIELDS[event].split()
    pattern = 'POOLEOS:APPS '+event+' contract=PAPPSESSION1'+''.join(' '+n+'=([0-9]+)' for n in names)+' cpl=3 production=0'
    match = re.fullmatch(pattern, line)
    if match is None: raise ValueError('malformed application observation')
    values = list(map(int, match.groups()))
    if any(v >= 1 << 64 for v in values): raise ValueError('observation overflow')
    return dict(zip(names, values))


def validate_markers(markers: list[str], *, bad_file: bool = False) -> dict:
    if len(markers) < 51: raise ValueError('incomplete application session')
    arm = transfer.TRANSFER_ARM.fullmatch(markers[23])
    if arm is None or int(arm.group(10)) != 23: raise ValueError('session selector required')
    prefix = markers[:29]
    prefix[23] = re.sub(r'trap_scenario=[0-9]+', 'trap_scenario=0', prefix[23], count=1)
    prefix.append('POOLEOS:KERNEL:TRANSFER-DENIED PASS contract=PKXFER1 terminal=halt entry_count=1 post_exit_firmware_calls=0 signatures=0 authority=0 actions=0 writes=0')
    common = transfer.validate_markers(prefix)
    common['transfer_arm']['trap_scenario'] = 23
    common.pop('kernel_terminal', None)
    common['synthetic_unsigned_terminal_used_for_prefix_parser_only'] = True
    if markers[29] != FILE_MARKER: raise ValueError('file role binding differs')
    start = parse(markers[30], 'START')
    sizes = [start[n+'_bytes'] for n in ('init','files','console','shell','text','numbers')]
    if any(not 0 < n <= 16384 for n in sizes): raise ValueError('program size bound')
    pages = [12+(n+4095)//4096 for n in sizes]
    roots = [start[f'root{i}'] for i in range(6)]
    def valid_root(r): return 0 < r < 1 << 32 and r % 4096 == 0 and r != common['transfer_arm']['root']
    if start['bad_file'] != int(bad_file) or start['image_pages'] != sum(pages) or not 0 < start['firmware_pages'] <= 12 or len(set(roots)) != 6 or not all(map(valid_root, roots)):
        raise ValueError('startup geometry or authority control')
    owned, live = set(range(6)), set(range(4))
    generation = [1,1,1,1,0,0]
    admits, handoffs, retires, samples = [], [], [], []
    previous_calls, previous_ticks = [0]*6, [0]*6
    frozen, pending, last_event = {}, None, 0
    for marker in markers[31:]:
        event = next((e for e in FIELDS if marker.startswith('POOLEOS:APPS '+e+' ')), None)
        if event not in ('HANDOFF','ADMIT','RETIRE','RUN'): raise ValueError('unknown application event')
        if pending is not None and event != 'ADMIT': raise ValueError('handoff not immediately admitted')
        v = parse(marker, event)
        dispatches = v['dispatches']
        last_sample = samples[-1]['dispatches'] if samples else 0
        if event != 'RUN':
            if not last_sample < dispatches <= last_sample+64 or dispatches < last_event:
                raise ValueError('event ordering')
            last_event = dispatches
            task = v['task']
            if not 2 <= task <= 5: raise ValueError('unexpected survivor retirement')
        if event == 'HANDOFF':
            if task not in (4,5) or task in live or 3 not in live:
                raise ValueError('handoff outside application lifetime')
            expected = generation[task]+1
            if expected > 2 or v['generation'] != expected or v['control'] != (expected<<32)|0x10001 or v['files'] != (expected<<32)|0x10002:
                raise ValueError('handoff generation or grants')
            if v['startup_files'] != v['files'] + ((1<<32) if bad_file and task == 5 else 0) or v['bytes'] != 176 or v['entered'] != 0:
                raise ValueError('startup handoff bytes or authority control')
            pending = v
            handoffs.append(v)
        elif event == 'ADMIT':
            if pending is None or any(v[n] != pending[n] for n in ('task','generation','dispatches')):
                raise ValueError('admission has no exact owned handoff')
            expected = generation[task]+1
            if v['sequence'] != expected or v['handle'] != (expected<<32)|0x50000|(task-3) or v['owned_pages'] != pages[task]:
                raise ValueError('launch sequence, handle or pages')
            if not valid_root(v['root']) or any(v['root'] == roots[j] for j in owned if j != task) or (expected == 1 and v['root'] != roots[task]):
                raise ValueError('launch root alias')
            if (expected == 1) != (task in owned): raise ValueError('unreclaimed image reused')
            roots[task], generation[task] = v['root'], expected
            previous_calls[task] = previous_ticks[task] = 0
            frozen.pop(task, None)
            live.add(task); owned.add(task); admits.append(v); pending = None
        elif event == 'RETIRE':
            if task not in live or task not in owned or v['generation'] != generation[task] or v['released_pages'] != pages[task]:
                raise ValueError('retirement identity or pages')
            expected = (1<<32) if task < 4 else (2<<32)|6 if task == 5 and generation[task] == 1 else 4<<32
            if v['outcome'] != expected or v['calls'] == 0 or v['calls'] < previous_calls[task]:
                raise ValueError('wrong terminal outcome or lost accounting')
            # CLOSE reply can retire the console before the shell consumes it.
            # Neither service may exit while either application remains live.
            if task < 4 and (4 in live or 5 in live): raise ValueError('service abandoned live children')
            previous_calls[task] = v['calls']
            live.remove(task); owned.remove(task); retires.append(v)
        else:
            flushes = sum(r['outcome'] == 4<<32 for r in retires)
            if dispatches != (len(samples)+1)*64 or dispatches < last_event or v['cr3_writes'] != 2*dispatches+flushes or v['extra_flushes'] != flushes:
                raise ValueError('dispatch/flush accounting')
            if v['pages'] != sum(pages[j] for j in owned) or v['live_mask'] != sum(1<<j for j in live) or [v['generation4'],v['generation5']] != generation[4:] or v['retired'] != len(retires) or v['unused'] != 0:
                raise ValueError('lifecycle accounting')
            for j in range(6):
                pair = (v[f'calls{j}'], v[f'ticks{j}'])
                if pair[0] < previous_calls[j] or pair[1] < previous_ticks[j]: raise ValueError('accounting regressed')
                if j < 2 and (pair[0] <= previous_calls[j] or pair[1] <= previous_ticks[j]): raise ValueError('survivor stopped progressing')
                if j not in live and pair != frozen.setdefault(j, pair): raise ValueError('retired image resumed')
                previous_calls[j], previous_ticks[j] = pair
            samples.append(v)
    if pending is not None or live != {0,1} or owned != {0,1} or generation[4:] != [2,2] or len(retires) != 6:
        raise ValueError('incomplete application lifecycle')
    if len(samples) < 8 or any(v['live_mask'] != 3 for v in samples[-2:]) or not any(v['live_mask'] == 63 and min(v['calls4'],v['calls5'],v['ticks4'],v['ticks5']) > 0 for v in samples):
        raise ValueError('concurrent apps or post-retirement survival missing')
    fault = next(r for r in retires if r['task'] == 5 and r['generation'] == 1)
    restart = next(a for a in admits if a['task'] == 5 and a['generation'] == 2)
    survivors = [v for v in samples if fault['dispatches'] < v['dispatches'] < restart['dispatches']]
    before_fault = [v for v in samples if v['dispatches'] < fault['dispatches']]
    if not before_fault or not any(v['live_mask'] == 31 and v['calls4'] > before_fault[-1]['calls4'] and v['calls3'] > before_fault[-1]['calls3'] for v in survivors):
        raise ValueError('text and shell progress after contained app fault missing')
    return dict(transfer_prefix=common, start=start, program_bytes=sizes, handoffs=handoffs,
                admits=admits, retires=retires, samples=samples, bad_file_handle=bad_file,
                native_execution_requires_guest_binding=True, useful_applications=0,
                bundled_files=False, iso_built=False, production_ready=False)


def text_result(content: bytes) -> bytes:
    # Independent host expectation, not the Rust app's parsing implementation.
    return f'text: bytes={len(content)} words={len(content.split())} lf={content.count(bytes([10]))}\r\n'.encode()


def scenario(nonce: str, *, bad_file: bool = False) -> shell.Scenario:
    if re.fullmatch(r'[0-9a-f]{16}', nonce) is None: raise ValueError('independent challenge required')
    steps = []
    def command(line, result, close=False):
        steps.extend((bytes([b]), bytes([b])) for b in line)
        steps.append((b'\r', b'\r\n'+result+(b'' if close else shell.PROMPT)))
    def numbers(path, result):
        command(b'numbers '+path, b'numbers: file service unavailable\r\n' if bad_file else result)
    command(b'status text', b'text: not started\r\n')
    command(b'text /readme.txt', b'text: not started\r\n')
    command(b'start text', b'text: admitted\r\n')
    command(b'start numbers', b'numbers: admitted\r\n')
    command(b'status text', b'text: attached\r\n')
    command(b'status numbers', b'numbers: attached\r\n')
    command(b'exit', b'Stop tasks and check status before exit.\r\n')
    command(b'ls', files.LISTING)
    command(b'cat /version.txt', files.VERSION)
    for content, path in [(files.README,b'/readme.txt'), (b'',b'/empty.txt'), (files.NUMBERS,b'/numbers.csv')]:
        command(b'text '+path, text_result(content))
    rows = list(map(int, files.NUMBERS.splitlines()[1:]))
    numeric = f'numbers: count={len(rows)} sum={sum(rows)} min={min(rows)} max={max(rows)}\r\n'.encode()
    numbers(b'/numbers.csv', numeric)
    numbers(b'/empty.txt', b'numbers: count=0 sum=0 min=0 max=0\r\n')
    numbers(b'/readme.txt', b'numbers: invalid data\r\n')
    command(b'text /missing.txt', b'text: not found\r\n')
    command(b'text /../readme.txt', b'text: invalid path\r\n')
    for _ in range(2):
        command(b'text /version.txt', text_result(files.VERSION))
        numbers(b'/numbers.csv', numeric)
    command(b'fault numbers', b'numbers: fault requested\r\n')
    command(b'status numbers', b'numbers: fault 0x00000006\r\n')
    command(b'text /readme.txt', text_result(files.README))
    command(b'echo '+nonce.encode(), nonce.encode()+b'\r\n')
    command(b'start numbers', b'numbers: admitted\r\n')
    numbers(b'/numbers.csv', numeric)
    command(b'status numbers', b'numbers: attached\r\n')
    command(b'stop text', b'text: stop requested\r\n')
    command(b'status text', b'text: cancelled\r\n')
    command(b'start text', b'text: admitted\r\n')
    command(b'text /numbers.csv', text_result(files.NUMBERS))
    command(b'stop text', b'text: stop requested\r\n')
    command(b'status text', b'text: cancelled\r\n')
    command(b'stop numbers', b'numbers: stop requested\r\n')
    command(b'status numbers', b'numbers: cancelled\r\n')
    command(b'exit', b'Bye.\r\n', True)
    return shell.Scenario('stale-app-file' if bad_file else 'application-session', nonce, tuple(steps))


def negative_controls(markers: list[str], *, bad_file: bool = False) -> int:
    validate_markers(markers, bad_file=bad_file)
    cases = [markers[:i]+markers[i+1:] for i in range(len(markers)-1)]
    cases += [markers+[markers[-1]], markers+['POOLEOS:PANIC injected']]
    for i in range(29,len(markers)):
        for field in ('production','cpl','grants','control','files','startup_files','bytes','entered',
                      'handle','generation','sequence','released_pages','owned_pages','outcome','live_mask','cr3_writes'):
            if ' '+field+'=' in markers[i]:
                changed = markers.copy()
                changed[i] = re.sub(r' '+field+r'=[0-9]+', ' '+field+'='+str((1<<64)-1), changed[i])
                cases.append(changed)
    for case in cases:
        try: validate_markers(case, bad_file=bad_file)
        except ValueError: continue
        raise ValueError('hostile application observation accepted')
    return len(cases)
