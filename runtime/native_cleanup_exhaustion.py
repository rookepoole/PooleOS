"""PCLEANUP3: overlapping bounded failures retain owners, not successful cleanup."""
from __future__ import annotations
import re
from runtime import native_app_session as apps, native_kernel_transfer as transfer
from runtime import native_shell as shell, native_files as files

HOLD = 'POOLEOS:EXHAUST HOLD contract=PCLEANUP3'
FIELDS = 'task generation attempts pages writes calls ticks dispatches children'.split()


def parse_hold(marker):
    match = re.fullmatch(HOLD+''.join(' '+n+'=([0-9]+)' for n in FIELDS)+' cpl=0 production=0', marker)
    if match is None: raise ValueError('malformed exhausted-owner observation')
    values = list(map(int, match.groups()))
    if any(v >= 1 << 64 for v in values): raise ValueError('exhausted observation overflow')
    return dict(zip(FIELDS, values))


def validate_markers(markers, *, bad_file=False):
    if len(markers) < 60: raise ValueError('incomplete exhaustion observation')
    arm = transfer.TRANSFER_ARM.fullmatch(markers[23])
    if arm is None or int(arm.group(10)) != 23: raise ValueError('application selector required')
    prefix = markers[:29]
    prefix[23] = re.sub(r'trap_scenario=[0-9]+', 'trap_scenario=0', prefix[23], count=1)
    prefix.append('POOLEOS:KERNEL:TRANSFER-DENIED PASS contract=PKXFER1 terminal=halt entry_count=1 post_exit_firmware_calls=0 signatures=0 authority=0 actions=0 writes=0')
    common = transfer.validate_markers(prefix)
    common['transfer_arm']['trap_scenario'] = 23
    common.pop('kernel_terminal', None)
    common['synthetic_unsigned_terminal_used_for_prefix_parser_only'] = True
    if markers[29] != apps.FILE_MARKER: raise ValueError('file role binding')
    start = apps.parse(markers[30], 'START')
    sizes = [start[n+'_bytes'] for n in ('init','files','console','shell','text','numbers')]
    pages = [12+(n+4095)//4096 for n in sizes]
    roots = [start[f'root{i}'] for i in range(6)]
    if (any(not 0 < n <= 16384 for n in sizes) or len(set(roots)) != 6
        or any(not 0 < r < 1 << 32 or r % 4096 or r == common['transfer_arm']['root'] for r in roots)
        or start['bad_file'] != int(bad_file) or start['image_pages'] != sum(pages)
        or not 0 < start['firmware_pages'] <= 12):
        raise ValueError('startup geometry or authority control')
    admits, handoffs, samples, events, holds = [], [], [], [], []
    live, pending, cleaning, exhausted, frozen = set(range(4)), None, {}, {}, {}
    last_event, last_poll = 0, -1
    expected_holds = []
    for marker in markers[31:]:
        if expected_holds:
            v = parse_hold(marker)
            j = expected_holds.pop(0)
            run = samples[-1]
            if (v['task'] != j or v['generation'] != 1 or v['attempts'] != 3
                or v['pages'] != pages[j] or v['children'] != 2 or v['writes'] == 0
                or v['dispatches'] != run['dispatches']
                or v['calls'] != run[f'calls{j}'] or v['ticks'] != run[f'ticks{j}']):
                raise ValueError('exhausted owner or runtime mismatch')
            previous = next((h for h in holds if h['task'] == j), None)
            if previous is not None and v['writes'] != previous['writes']:
                raise ValueError('writes after cleanup exhausted')
            holds.append(v)
            continue
        if marker.startswith(apps.cleanup.PREFIX):
            event = marker.split()[1]
            if pending is not None or event not in ('DEFER','RETRY','EXHAUSTED'):
                raise ValueError('unexpected cleanup transition')
            v = apps.cleanup.parse(marker, event)
            j, d = v['task'], v['dispatches']
            last_sample = samples[-1]['dispatches'] if samples else 0
            if (j not in (4,5) or j not in live or j in exhausted or v['generation'] != 1
                or v['admitted'] != 1 or v['pages'] != pages[j]
                or not last_sample <= d <= last_sample+64 or d < last_event):
                raise ValueError('cleanup owner, pages or ordering')
            if event == 'DEFER':
                if j in cleaning or v['attempts'] != 0 or v['next'] != d+64:
                    raise ValueError('duplicate or unbounded deferral')
            else:
                old = cleaning.get(j)
                if old is None or v['attempts'] != old['attempts']+1 or not old['next'] <= d <= old['next']+1 or d == last_poll:
                    raise ValueError('early, delayed or unbounded retry')
                # A one-dispatch delay is valid only if another owner used the due slot.
                if d != old['next'] and last_poll != old['next']:
                    raise ValueError('unexplained cleanup delay')
                last_poll = d
                if event == 'EXHAUSTED':
                    if v['attempts'] != 3 or v['next'] != 0 or set(cleaning) != {4,5}:
                        raise ValueError('exhaustion or overlap missing')
                    exhausted[j] = v
                elif v['attempts'] not in (1,2) or v['next'] != d+(64 << v['attempts']):
                    raise ValueError('invalid retry backoff')
            cleaning[j] = v
            last_event = d
            events.append(dict(event=event, **v))
            continue
        event = next((e for e in ('HANDOFF','ADMIT','RUN') if marker.startswith('POOLEOS:APPS '+e+' ')), None)
        if event is None or (pending is not None and event != 'ADMIT'):
            raise ValueError('retirement, restart or unexpected event')
        v = apps.parse(marker, event)
        d = v['dispatches']
        if event != 'RUN':
            j = v['task']
            last_sample = samples[-1]['dispatches'] if samples else 0
            if not last_sample < d <= last_sample+64 or d < last_event or j not in (4,5) or j in live or v['generation'] != 1:
                raise ValueError('admission ordering or reused owner')
            last_event = d
        if event == 'HANDOFF':
            if (v['control'] != (1<<32)|0x10001 or v['files'] != (1<<32)|0x10002
                or v['startup_files'] != v['files']+((1<<32) if bad_file and j == 5 else 0)
                or v['bytes'] != 176 or v['entered'] != 0):
                raise ValueError('handoff authority')
            pending = v; handoffs.append(v)
        elif event == 'ADMIT':
            if (pending is None or any(v[k] != pending[k] for k in ('task','generation','dispatches'))
                or v['sequence'] != 1 or v['handle'] != (1<<32)|0x50000|(j-3)
                or v['root'] != roots[j] or v['owned_pages'] != pages[j]):
                raise ValueError('admission ownership')
            live.add(j); admits.append(v); pending = None
        else:
            if (d != (len(samples)+1)*64 or d < last_event or v['cr3_writes'] != 2*d+len(cleaning)
                or v['extra_flushes'] != len(cleaning) or v['pages'] != sum(pages)
                or v['live_mask'] != sum(1<<j for j in live) or v['retired'] or v['unused']
                or [v['generation4'],v['generation5']] != [int(j in live) for j in (4,5)]):
                raise ValueError('retained ownership or dispatch accounting')
            for j in range(6):
                pair = (v[f'calls{j}'], v[f'ticks{j}'])
                old = (samples[-1][f'calls{j}'],samples[-1][f'ticks{j}']) if samples else (0,0)
                if any(a < b for a,b in zip(pair,old)) or (j < 4 and any(a <= b for a,b in zip(pair,old))):
                    raise ValueError('service stalled or accounting regressed')
                if j in cleaning or j not in live:
                    if j not in live and pair != (0,0): raise ValueError('unadmitted image ran')
                    if pair != frozen.setdefault(j, pair): raise ValueError('stopped image resumed')
                else: frozen.pop(j, None)
            samples.append(v)
            expected_holds = sorted(exhausted)
    if pending or expected_holds or set(exhausted) != {4,5} or len(admits) != 2 or len(events) != 8:
        raise ValueError('incomplete overlapping exhaustion')
    if samples[-1]['dispatches'] < max(v['dispatches'] for v in exhausted.values())+512:
        raise ValueError('post-exhaustion survival too short')
    if not any(v['live_mask'] == 63 and min(v['calls4'],v['calls5'],v['ticks4'],v['ticks5']) > 0 for v in samples):
        raise ValueError('concurrent applications not measured')
    return dict(transfer_prefix=common, start=start, program_bytes=sizes, samples=samples,
                handoffs=handoffs, admits=admits, cleanup_events=events, exhausted_holds=holds,
                bad_file_handle=bad_file, native_execution_requires_guest_binding=True,
                native_exhaustion_qualified=True, multiple_pending_cleanup_owners_qualified=True,
                live_mask_means_admitted_not_runnable=True, retained_pages=sum(pages[4:]),
                successful_recovery=False, claimed_request_interleavings_qualified=False,
                useful_applications=0, iso_built=False, production_ready=False)


def scenario(nonce, *, bad_file=False):
    if re.fullmatch(r'[0-9a-f]{16}', nonce) is None: raise ValueError('challenge required')
    steps = []
    def command(line, result):
        steps.extend((bytes([b]),bytes([b])) for b in line)
        steps.append((b'\r',b'\r\n'+result+shell.PROMPT))
    command(b'start text', b'text: admitted\r\n')
    command(b'start numbers', b'numbers: admitted\r\n')
    command(b'text /version.txt', apps.text_result(files.VERSION))
    rows = list(map(int, files.NUMBERS.splitlines()[1:]))
    command(b'numbers /numbers.csv', b'numbers: file service unavailable\r\n' if bad_file else
            f'numbers: count={len(rows)} sum={sum(rows)} min={min(rows)} max={max(rows)}\r\n'.encode())
    command(b'stop text', b'text: stop requested\r\n')
    command(b'stop numbers', b'numbers: stop requested\r\n')
    for name in (b'text',b'numbers'):
        for action in (b'status',b'start',b'stop'):
            command(action+b' '+name, name+b': retiring\r\n')
    command(b'exit', b'Stop tasks and check status before exit.\r\n')
    command(b'cat /version.txt', files.VERSION)
    command(b'echo '+nonce.encode(), nonce.encode()+b'\r\n')
    return shell.Scenario('exhaustion-stale-file' if bad_file else 'exhaustion-session', nonce, tuple(steps))


def negative_controls(markers, *, bad_file=False):
    count = 0
    cases = [markers[:31], markers+[markers[-1]]]
    stopped = set()
    for i in range(31,len(markers)):
        if markers[i].startswith(apps.cleanup.PREFIX+'DEFER '):
            stopped.add(apps.cleanup.parse(markers[i],'DEFER')['task'])
        cases.append(markers[:i]+markers[i+1:])
        cases.append(markers[:i]+[markers[i]]+markers[i:])
        for field in ('attempts','next','pages','writes','children','generation','cr3_writes','calls4','ticks5',
                      'task','admitted','sequence','handle','root'):
            if field in ('calls4','ticks5') and int(field[-1]) not in stopped: continue
            wrong = re.sub(' '+field+r'=([0-9]+)', lambda m:' '+field+'='+str(int(m[1])+1), markers[i])
            if wrong != markers[i]: cases.append(markers[:i]+[wrong]+markers[i+1:])
    for candidate in cases:
        try: validate_markers(candidate,bad_file=bad_file)
        except ValueError: count += 1
        else: raise ValueError('exhaustion hostile observation accepted: '+str(next((i for i,(a,b) in enumerate(zip(markers,candidate)) if a!=b),len(candidate))))
    return count
