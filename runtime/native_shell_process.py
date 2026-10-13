"""Native shell process observations; COM2 text is never kernel evidence."""
from __future__ import annotations
import re
from runtime import native_kernel_transfer as transfer, native_shell as shell

FIELDS = {
    'START': 'bad_owner init_bytes counter_bytes console_bytes shell_bytes worker_bytes image_pages firmware_pages root0 root1 root2 root3 root4 root5',
    'ADMIT': 'task generation sequence handle root owned_pages dispatches',
    'RETIRE': 'task generation outcome calls released_pages dispatches',
    'UNUSED': 'task released_pages dispatches',
    'RUN': 'dispatches cr3_writes extra_flushes pages calls0 calls1 calls2 calls3 calls4 calls5 ticks0 ticks1 ticks2 ticks3 ticks4 ticks5 live_mask generation4 generation5 retired unused',
}

def parse(line: str, event: str) -> dict:
    names = FIELDS[event].split()
    pattern = 'POOLEOS:CONTROL '+event+' contract=PSHELLPROC1'+''.join(' '+n+'=([0-9]+)' for n in names)+' cpl=3 production=0'
    match = re.fullmatch(pattern, line)
    if match is None: raise ValueError('malformed shell process observation')
    values = list(map(int, match.groups()))
    if any(v >= 1 << 64 for v in values): raise ValueError('observation overflow')
    return dict(zip(names, values))

def validate_markers(markers: list[str], *, bad_owner: bool = False, prepared_dispatch: int | None = None, owner_death: bool = False) -> dict:
    if prepared_dispatch is not None and (type(prepared_dispatch) is not int or not 0 < prepared_dispatch < 1 << 64):
        raise ValueError('invalid prepared dispatch')
    if len(markers) < 40: raise ValueError('incomplete process session')
    arm = transfer.TRANSFER_ARM.fullmatch(markers[23])
    if arm is None or int(arm.group(10)) != 23: raise ValueError('session selector required')
    prefix = markers[:29]
    prefix[23] = re.sub(r'trap_scenario=[0-9]+', 'trap_scenario=0', prefix[23], count=1)
    prefix.append('POOLEOS:KERNEL:TRANSFER-DENIED PASS contract=PKXFER1 terminal=halt entry_count=1 post_exit_firmware_calls=0 signatures=0 authority=0 actions=0 writes=0')
    common = transfer.validate_markers(prefix)
    common['transfer_arm']['trap_scenario'] = 23
    common.pop('kernel_terminal', None)
    common['synthetic_unsigned_terminal_used_for_prefix_parser_only'] = True
    start = parse(markers[29], 'START')
    sizes = [start[n+'_bytes'] for n in ('init','counter','console','shell','worker')]
    if any(not 0 < n <= 16384 for n in sizes): raise ValueError('program size bound')
    pages = [12+(n+4095)//4096 for n in sizes+[sizes[-1]]]
    roots = [start[f'root{i}'] for i in range(6)]
    def valid_root(r): return 0 < r < 1 << 32 and r % 4096 == 0 and r != common['transfer_arm']['root']
    if start['bad_owner'] != int(bad_owner) or start['image_pages'] != sum(pages) or not 0 < start['firmware_pages'] <= 12 or len(set(roots)) != 6 or not all(map(valid_root, roots)):
        raise ValueError('startup geometry or authority control')
    owned, live = set(range(6)), set(range(4))
    generation = [1,1,1,1,0,0]
    admits, retires, unused, samples = [], [], [], []
    previous_calls, previous_ticks = [0]*6, [0]*6
    frozen = {}
    last_event = 0
    for marker in markers[30:]:
        event = next((e for e in FIELDS if marker.startswith('POOLEOS:CONTROL '+e+' ')), None)
        if event not in ('ADMIT','RETIRE','UNUSED','RUN'): raise ValueError('unknown process event')
        v = parse(marker, event)
        dispatches = v['dispatches']
        last_sample = samples[-1]['dispatches'] if samples else 0
        if event != 'RUN':
            if not last_sample < dispatches <= last_sample+64 or dispatches < last_event:
                raise ValueError('event ordering')
            last_event = dispatches
            task = v['task']
            if not 2 <= task <= 5: raise ValueError('unexpected survivor retirement')
        if event == 'ADMIT':
            if owner_death and (task != 4 or 3 not in live): raise ValueError('admission outside owner lifetime')
            if task not in (4,5) or task in live or (bad_owner and task == 5): raise ValueError('unauthorized admission')
            expected = generation[task]+1
            if expected > (1 if owner_death else 2) or v['generation'] != expected or v['sequence'] != expected or v['handle'] != (expected<<32)|0x50000|(task-3) or v['owned_pages'] != pages[task]:
                raise ValueError('launch generation or handle')
            if not valid_root(v['root']) or any(v['root'] == roots[j] for j in owned if j != task) or (expected == 1 and v['root'] != roots[task]):
                raise ValueError('launch root alias')
            if (expected == 1) != (task in owned): raise ValueError('unreclaimed image reused')
            roots[task] = v['root']
            generation[task] = expected
            previous_calls[task] = previous_ticks[task] = 0
            frozen.pop(task, None)
            live.add(task); owned.add(task); admits.append(v)
        elif event == 'RETIRE':
            if task not in live or task not in owned or v['generation'] != generation[task] or v['released_pages'] != pages[task]:
                raise ValueError('retirement identity or pages')
            expected = (1<<32) if task < 4 else (4<<32) if task == 4 else (2<<32)|6
            if owner_death:
                if task == 3: expected = (2<<32)|6
                if task == 2: raise ValueError('independent console retired')
                if task != 3 and 3 in live: raise ValueError('orphan retirement before owner death')
            zero_calls = task == 5 or (prepared_dispatch is not None and task == 4 and generation[task] == 1)
            if v['outcome'] != expected or (v['calls'] == 0) != zero_calls or v['calls'] < previous_calls[task]:
                raise ValueError('wrong terminal outcome or lost accounting')
            if not owner_death and task == 3 and (4 in live or 5 in live): raise ValueError('shell abandoned live children')
            previous_calls[task] = v['calls']
            live.remove(task); owned.remove(task); retires.append(v)
        elif event == 'UNUSED':
            if not (bad_owner or owner_death) or task != 5 or 3 in live or task in live or task not in owned or generation[task] != 0 or v['released_pages'] != pages[task]:
                raise ValueError('invalid unused image cleanup')
            owned.remove(task); unused.append(v)
        else:
            expected_flushes = sum(r['task'] == 4 and r['calls'] > 0 for r in retires)
            held = int(prepared_dispatch is not None and dispatches >= prepared_dispatch)
            if dispatches != (len(samples)+1)*64 or dispatches < last_event or v['cr3_writes'] != 2*(dispatches-held)+expected_flushes or v['extra_flushes'] != expected_flushes:
                raise ValueError('dispatch/flush accounting')
            if v['pages'] != sum(pages[j] for j in owned) or v['live_mask'] != sum(1<<j for j in live) or [v['generation4'],v['generation5']] != generation[4:] or v['retired'] != len(retires) or v['unused'] != len(unused):
                raise ValueError('lifecycle accounting')
            for j in range(6):
                pair = (v[f'calls{j}'], v[f'ticks{j}'])
                if prepared_dispatch is not None and j == 4 and generation[j] == 1 and pair != (0,0):
                    raise ValueError('prepared child executed')
                if pair[0] < previous_calls[j] or pair[1] < previous_ticks[j]: raise ValueError('accounting regressed')
                if j < (3 if owner_death else 2) and (pair[0] <= previous_calls[j] or pair[1] <= previous_ticks[j]): raise ValueError('survivor stopped progressing')
                if j not in live and pair != frozen.setdefault(j, pair): raise ValueError('retired image resumed')
                previous_calls[j], previous_ticks[j] = pair
            samples.append(v)
    final_generations = [1,0] if owner_death else [2,0 if bad_owner else 2]
    survivors = {0,1,2} if owner_death else {0,1}
    if live != survivors or owned != survivors or generation[4:] != final_generations or len(unused) != int(bad_owner or owner_death):
        raise ValueError('incomplete launch/stop/restart session')
    needs_live_worker = not (owner_death and prepared_dispatch is not None)
    if len(samples) < 8 or any(v['live_mask'] != sum(1<<j for j in survivors) for v in samples[-2:]) or (needs_live_worker and not any(v['live_mask'] & 16 and v['calls4'] > 0 and v['ticks4'] > 0 for v in samples)):
        raise ValueError('live worker or post-retirement survival missing')
    return dict(transfer_prefix=common, start=start, program_bytes=sizes, admits=admits, retires=retires,
        unused=unused, samples=samples, bad_owner=bad_owner, native_execution_requires_guest_binding=True,
        useful_applications=0, bundled_files=False, iso_built=False, production_ready=False)

def scenario(nonce: str, *, bad_owner: bool = False) -> shell.Scenario:
    if re.fullmatch(r'[0-9a-f]{16}', nonce) is None: raise ValueError('independent challenge required')
    steps = []
    def command(line, result, close=False):
        steps.extend((bytes([b]), bytes([b])) for b in line)
        steps.append((b'\r', b'\r\n'+result+(b'' if close else shell.PROMPT)))
    command(b'status worker', b'worker: not started\r\n')
    command(b'start worker', b'worker: admitted\r\n')
    command(b'status worker', b'worker: attached\r\n')
    command(b'exit', b'Stop tasks and check status before exit.\r\n')
    command(b'start fault', b'fault: denied\r\n' if bad_owner else b'fault: admitted\r\n')
    command(b'status fault', b'fault: not started\r\n' if bad_owner else b'fault: fault 0x00000006\r\n')
    command(b'echo '+nonce.encode(), nonce.encode()+b'\r\n')
    if not bad_owner:
        command(b'start fault', b'fault: admitted\r\n')
        command(b'status fault', b'fault: fault 0x00000006\r\n')
    command(b'start kernel', b'Unknown command.\r\n')
    command(b'stop worker', b'worker: stop requested\r\n')
    command(b'status worker', b'worker: cancelled\r\n')
    command(b'start worker', b'worker: admitted\r\n')
    command(b'status worker', b'worker: attached\r\n')
    command(b'stop worker', b'worker: stop requested\r\n')
    command(b'status worker', b'worker: cancelled\r\n')
    command(b'exit', b'Bye.\r\n', True)
    return shell.Scenario('bad-owner' if bad_owner else 'process-control', nonce, tuple(steps))

def negative_controls(markers: list[str], *, bad_owner: bool = False, prepared_dispatch: int | None = None, owner_death: bool = False) -> int:
    validate_markers(markers, bad_owner=bad_owner, prepared_dispatch=prepared_dispatch, owner_death=owner_death)
    cases = [markers[:i]+markers[i+1:] for i in range(len(markers)-1)]
    cases += [markers+[markers[-1]], markers+['POOLEOS:PANIC injected']]
    for i in range(29,len(markers)):
        for field in ('production=0','cpl=3'):
            changed = markers.copy(); changed[i] = changed[i].replace(field, field.split('=')[0]+'=99')
            cases.append(changed)
        for field in ('handle','generation','released_pages','owned_pages','outcome','live_mask','cr3_writes'):
            if ' '+field+'=' in markers[i]:
                changed=markers.copy(); changed[i]=re.sub(r' '+field+r'=[0-9]+', ' '+field+'=0', changed[i])
                cases.append(changed)
    for case in cases:
        try: validate_markers(case, bad_owner=bad_owner, prepared_dispatch=prepared_dispatch, owner_death=owner_death)
        except ValueError: continue
        raise ValueError('hostile process observation accepted')
    return len(cases)
