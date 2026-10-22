"""PAPPSESSION1 oracle. Console text alone never proves native execution."""
from __future__ import annotations
import re
from runtime import native_kernel_transfer as transfer, native_shell as shell, native_files as files
from runtime import native_deferred_cleanup as cleanup
from runtime import native_shell_orphan as job_probe

PROGRAMS = [('PooleFileInit', 'INIT'), ('PooleAppFiles', 'COUNTER'),
            ('PooleConsoleService', 'CONSOLE'), ('PooleAppShell', 'CONSOLE_CLIENT'),
            ('PooleText', 'TEXT'), ('PooleNumbers', 'NUMBERS')]
FIELDS = {
    'RECOVER': 'task generation root attempts retained_pages recovered children writes dispatches',
    'HELD': 'task generation root pages children writes calls ticks dispatches',
    'PRESSURE': 'task generation owner owner_generation target target_generation handle owner_limit dispatches',
    'RELIEF': 'task generation owner owner_generation target target_generation handle owner_limit dispatches',
    'REJECT': 'task generation sequence root owned_pages reason syscalls dispatches',
    'FAILED': 'task generation sequence root published dispatches',
    'SURFACE': 'task generation send entered dispatches',
    'WAIT': 'task generation calls queued claimed completed dispatches',
    'WAKE': 'task generation calls queued claimed completed dispatches',
    'CLAIMED': 'task generation waiting stale_wait_rejected service_task service_generation dispatches',
    'REQUESTER': 'task generation queued claimed completed detached dispatches',
    'START': 'bad_file init_bytes files_bytes console_bytes shell_bytes text_bytes numbers_bytes image_pages firmware_pages root0 root1 root2 root3 root4 root5',
    'HANDOFF': 'task generation control files startup_files bytes entered dispatches',
    'ADMIT': 'task generation sequence handle root owned_pages dispatches',
    'RETIRE': 'task generation outcome calls released_pages dispatches',
    'RUN': 'dispatches cr3_writes extra_flushes pages calls0 calls1 calls2 calls3 calls4 calls5 ticks0 ticks1 ticks2 ticks3 ticks4 ticks5 live_mask generation4 generation5 retired unused',
}
FILE_MARKER = ('POOLEOS:APPS FILES contract=PAPPSESSION1 version=1 init_slot=0 '
               'service_slot=1 shell_slot=3 bad_handle=0 grants=8 cpl=3 production=0')


def launch_failure_options(report: dict) -> dict:
    """Admit only the explicit diagnostic profile, never an ordinary preview."""
    required = ('file_waits', 'window_surfaces', 'window_capacity', 'surface_lifecycle',
                'surface_input', 'launch_shell_admission', 'launch_console_admission',
                'diagnostic_only', 'launch_failure')
    if (not isinstance(report, dict) or any(report.get(name) is not True for name in required)
            or report.get('serial_recovery') is not False):
        raise ValueError('exact diagnostic launch-failure profile required')
    if any(report.get(name, False) is not False for name in ('launch_orphan','orphan_stuck')):
        raise ValueError('orphan recovery requires its separate diagnostic profile')
    quota = report.get('launch_quota', False)
    if type(quota) is not bool:
        raise ValueError('exact boolean quota profile required')
    ordinary = dict(report, diagnostic_only=False, launch_failure=False, launch_quota=False)
    options = dict(profile_options(ordinary), launch_failure=True)
    if quota:
        options['launch_quota'] = True
    return options


def launch_orphan_options(report: dict) -> dict:
    if (not isinstance(report, dict) or report.get('launch_orphan') is not True
            or report.get('launch_quota') is not True or type(report.get('orphan_stuck')) is not bool):
        raise ValueError('exact orphan recovery diagnostic profile required')
    options = launch_failure_options(dict(report,launch_orphan=False,orphan_stuck=False))
    return dict(options,launch_orphan=True,orphan_stuck=report['orphan_stuck'])


def profile_options(report: dict) -> dict:
    """Select the explicit receipt profile; never infer authority from code size."""
    if not isinstance(report, dict):
        raise ValueError('application profile object required')
    names = ('file_waits', 'window_surfaces', 'window_capacity', 'surface_lifecycle',
             'surface_input', 'launch_shell_admission', 'launch_console_admission',
             'diagnostic_only', 'serial_recovery', 'launch_failure', 'launch_quota', 'launch_orphan', 'orphan_stuck')
    flags = {name: report.get(name, False) for name in names}
    if any(type(value) is not bool for value in flags.values()):
        raise ValueError('explicit boolean application profile required')
    if any(flags[name] for name in ('diagnostic_only','serial_recovery','launch_failure','launch_quota','launch_orphan','orphan_stuck')):
        raise ValueError('diagnostic profile is not an ordinary preview')
    if flags['launch_console_admission'] and not flags['launch_shell_admission']:
        raise ValueError('launch console requires launch shell')
    if flags['launch_shell_admission'] and not all(flags[name] for name in names[:5]):
        raise ValueError('launch shell requires complete isolated-input profile')
    return dict(file_waits=flags['file_waits'], windows=flags['window_surfaces'],
                window_capacity=flags['window_capacity'], surface_lifecycle=flags['surface_lifecycle'],
                launch_session=flags['launch_shell_admission'])


def parse(line: str, event: str) -> dict:
    names = FIELDS[event].split()
    pattern = 'POOLEOS:APPS '+event+' contract=PAPPSESSION1'+''.join(' '+n+'=([0-9]+)' for n in names)+' cpl=3 production=0'
    match = re.fullmatch(pattern, line)
    if match is None: raise ValueError('malformed application observation')
    values = list(map(int, match.groups()))
    if any(v >= 1 << 64 for v in values): raise ValueError('observation overflow')
    return dict(zip(names, values))


def validate_markers(markers: list[str], *, bad_file: bool = False, deferred_cleanup: bool = False, file_controls: bool = False, claimed_requester: bool = False, file_waits: bool = False, windows: bool = False, window_capacity: bool = False, surface_lifecycle: bool = False, launch_session: bool = False, launch_failure: bool = False, launch_quota: bool = False, launch_orphan: bool = False, orphan_stuck: bool = False) -> dict:
    if type(launch_orphan) is not bool or type(orphan_stuck) is not bool or launch_orphan and not launch_quota or orphan_stuck and not launch_orphan:
        raise ValueError('orphan recovery requires exact quota diagnostic profile')
    if type(launch_quota) is not bool or launch_quota and not launch_failure:
        raise ValueError('quota challenge requires explicit rejection profile')
    if type(launch_failure) is not bool or launch_failure and not launch_session:
        raise ValueError('launch rejection requires explicit diagnostic launch profile')
    if type(launch_session) is not bool or launch_session and not (file_waits and windows and window_capacity and surface_lifecycle):
        raise ValueError('explicit launch-session input profile required')
    if type(surface_lifecycle) is not bool or surface_lifecycle and not window_capacity: raise ValueError('explicit lifecycle capacity profile required')
    if type(window_capacity) is not bool or window_capacity and not windows: raise ValueError('explicit window capacity profile required')
    if windows and (deferred_cleanup or file_controls or claimed_requester): raise ValueError('unqualified window control profile')
    if sum((deferred_cleanup,file_controls,claimed_requester)) > 1: raise ValueError('unqualified combined control modes')
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
    if any(not 0 < n <= (28672 if window_capacity and i==2 else 20480 if launch_session and i==3 else 16384) for i,n in enumerate(sizes)): raise ValueError('program size bound')
    if launch_session and sizes[3] <= 16384: raise ValueError('five-page launch shell absent')
    if window_capacity and sizes[2] <= 24576: raise ValueError('seventh-page service probe absent')
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
    cleaning, completed, cleanup_events = {}, {}, []
    complete_pending = None
    requesters, requester_pending = [], None
    claimed_waiters, claim_pending = [], None
    waiting, wake_pairs = {}, []
    surfaces, surface_pending = [], False
    failures, rejections, failed = {}, [], []
    pressure, pressure_events = None, []
    job_events, recovery, holds = [], None, []
    final_generation = 3 if launch_failure else 2
    for marker in markers[31:]:
        if marker.startswith(cleanup.PREFIX):
            if pressure is not None:
                raise ValueError('quota pressure was not released before reclamation')
            if launch_failure:
                event = marker.split()[1]
                allowed = ('DEFER','RETRY','EXHAUSTED') if launch_orphan else ('DEFER','COMPLETE')
                if event not in allowed or pending is not None or complete_pending is not None:
                    raise ValueError('invalid rejected-image cleanup event')
                v = cleanup.parse(marker, event)
                task, dispatches = v['task'], v['dispatches']
                rejection = failures.get(task)
                last_sample = samples[-1]['dispatches'] if samples else 0
                if (task != 5 or rejection is None or task in live or task not in owned
                    or v['generation'] != 2 or v['admitted'] != 0
                    or not last_sample <= dispatches <= last_sample+64 or dispatches < last_event):
                    raise ValueError('rejected-image cleanup ownership or ordering')
                if event == 'DEFER':
                    if (task in cleaning or dispatches != rejection['dispatches'] or v['attempts'] != 0
                        or v['pages'] != pages[task] or v['next'] != dispatches+64):
                        raise ValueError('rejected-image deferral differs')
                    cleaning[task] = dict(defer=v, samples=[])
                    if launch_orphan: cleaning[task]['last'] = v
                elif launch_orphan:
                    state = cleaning.get(task)
                    previous = state['last'] if state else None
                    attempt = previous['attempts']+1 if previous else 0
                    if (previous is None or attempt > 3 or v['attempts'] != attempt
                        or dispatches != previous['next'] or v['pages'] != pages[5]
                        or event != ('EXHAUSTED' if attempt == 3 else 'RETRY')
                        or v['next'] != (0 if attempt == 3 else dispatches+(64<<attempt))):
                        raise ValueError('orphan cleanup attempts or bounded backoff differ')
                    state['last'] = v
                else:
                    state = cleaning.get(task)
                    if (state is None or dispatches != state['defer']['next'] or v['attempts'] != 1
                        or v['pages'] != 0 or v['next'] != 0 or not state['samples']):
                        raise ValueError('rejected-image cleanup incomplete')
                    if any(s['calls5'] != 0 or s['ticks5'] != 0 or s['live_mask'] & 32 for s in state['samples']):
                        raise ValueError('rejected image entered')
                    complete_pending = v
                last_event = dispatches
                cleanup_events.append(dict(event=event, **v))
                continue
            if not deferred_cleanup or pending is not None or complete_pending is not None:
                raise ValueError('unexpected cleanup observation')
            event = marker.split()[1]
            if event not in ('DEFER', 'RETRY', 'COMPLETE'): raise ValueError('unexpected cleanup transition')
            v = cleanup.parse(marker, event)
            task, dispatches = v['task'], v['dispatches']
            last_sample = samples[-1]['dispatches'] if samples else 0
            if task not in (4,5) or task not in live or 3 not in live or v['generation'] != generation[task] or v['admitted'] != 1:
                raise ValueError('cleanup lacks live parent and owned child')
            if not last_sample <= dispatches <= last_sample+64 or dispatches < last_event:
                raise ValueError('cleanup event ordering')
            last_event = dispatches
            key = (task, generation[task])
            if event == 'DEFER':
                if task in cleaning or key in completed or v['attempts'] != 0 or v['next'] != dispatches+64 or v['pages'] != pages[task]:
                    raise ValueError('invalid cleanup deferral')
                cleaning[task] = dict(defer=v, retry=None, samples=[])
            else:
                state = cleaning.get(task)
                if state is None: raise ValueError('cleanup has no retained owner')
                if event == 'RETRY':
                    if state['retry'] is not None or v['attempts'] != 1 or dispatches != state['defer']['next'] or v['next'] != dispatches+128 or v['pages'] != pages[task]:
                        raise ValueError('invalid dispatch-separated retry')
                    state['retry'] = v
                else:
                    if state['retry'] is None or v['attempts'] != 2 or dispatches != state['retry']['next'] or v['next'] != 0 or v['pages'] != 0:
                        raise ValueError('invalid cleanup completion')
                    held = state['samples']
                    expected_samples = 3 + int(state['defer']['dispatches'] % 64 == 0)
                    if len(held) != expected_samples or any((s[f'calls{task}'], s[f'ticks{task}']) != (held[0][f'calls{task}'], held[0][f'ticks{task}']) for s in held):
                        raise ValueError('retained task resumed or retention interval missing')
                    for peer in (0,1,2,3):
                        if any(b[f'calls{peer}'] <= a[f'calls{peer}'] or b[f'ticks{peer}'] <= a[f'ticks{peer}'] for a,b in zip(held,held[1:])):
                            raise ValueError('live services stopped during cleanup')
                    complete_pending = v
            cleanup_events.append(dict(event=event, **v))
            continue
        job_event = marker.startswith(job_probe.PREFIX)
        event = marker.split()[1] if job_event else next((e for e in FIELDS if marker.startswith('POOLEOS:APPS '+e+' ')), None)
        if event not in ('HANDOFF','ADMIT','RETIRE','RUN','REQUESTER','CLAIMED','WAIT','WAKE','SURFACE','REJECT','FAILED','PRESSURE','RELIEF','OWNER','CHILD','DRAINED','RECOVER','HELD'): raise ValueError('unknown application event')
        if (job_event or event in ('RECOVER','HELD')) and not launch_orphan:
            raise ValueError('orphan event outside its diagnostic profile')
        if job_event and event not in job_probe.FIELDS:
            raise ValueError('unknown orphan job event')
        if event in ('PRESSURE','RELIEF') and not launch_quota:
            raise ValueError('quota event outside explicit profile')
        if pressure is not None and event != ('RELIEF' if 5 in failures else 'REJECT'):
            raise ValueError('quota pressure/rejection/relief must be contiguous')
        if event in ('REJECT','FAILED') and not launch_failure: raise ValueError('diagnostic rejection outside profile')
        if event == 'SURFACE' and not windows: raise ValueError('surface outside window profile')
        if claim_pending is not None and event != 'REQUESTER': raise ValueError('claimed waiter lacks requester retirement')
        if requester_pending is not None and event != 'RETIRE': raise ValueError('requester not immediately retired')
        if pending is not None and event not in (('SURFACE','ADMIT') if windows else ('ADMIT',)): raise ValueError('handoff not immediately admitted')
        if complete_pending is not None and event != ('FAILED' if launch_failure else 'RETIRE'): raise ValueError('cleanup completion not immediately settled')
        if 4 in failures and event != 'FAILED': raise ValueError('immediate rejection not settled')
        v = job_probe.parse(marker,event) if job_event else parse(marker, event)
        if launch_orphan and v.get('calls', 0) >= 1 << 32:
            raise ValueError('bounded orphan diagnostic syscall count exceeded')
        dispatches = v['dispatches']
        last_sample = samples[-1]['dispatches'] if samples else 0
        if event != 'RUN':
            lower = last_sample if complete_pending is not None or event in ('RECOVER','HELD') else last_sample+1
            if not lower <= dispatches <= last_sample+64 or dispatches < last_event:
                raise ValueError('event ordering')
            last_event = dispatches
            task = v.get('task')
            if event != 'DRAINED' and not 2 <= task <= 5: raise ValueError('unexpected survivor retirement')
        if event == 'OWNER':
            state = cleaning.get(5)
            if (job_events or recovery is not None or state is None or state['last']['attempts'] != 3
                or state['last']['next'] != 0 or not {3,4}.issubset(live)
                or v != dict(task=3,generation=1,root=roots[3],children=2,dispatches=state['last']['dispatches']+1)):
                raise ValueError('owner cancellation is not bound to exhausted child')
            job_events.append(dict(event=event,**v))
        elif event == 'CHILD':
            if (len(job_events) != 1 or 3 in live or 4 in live or recovery is not None
                or v != dict(task=4,generation=1,root=roots[4],prepared=0,remaining=1,published=0,dispatches=job_events[0]['dispatches'])):
                raise ValueError('orphan sibling not reclaimed without parent completion')
            job_events.append(dict(event=event,**v))
        elif event == 'DRAINED':
            if (orphan_stuck or recovery is None or len(job_events) != 2 or failures or cleaning
                or v != dict(children=0,owned_pages=sum(pages[:3]),dispatches=recovery['dispatches']+1)):
                raise ValueError('job drained before retained ownership is released')
            job_events.append(dict(event=event,**v))
        elif event == 'RECOVER':
            state = cleaning.get(5)
            if (recovery is not None or len(job_events) != 2 or live != {0,1,2} or state is None
                or state['last']['attempts'] != 3 or not 0 < v['writes'] < 1<<32
                or v != dict(task=5,generation=2,root=roots[5],attempts=1,
                    retained_pages=pages[5] if orphan_stuck else 0,recovered=int(not orphan_stuck),
                    children=int(orphan_stuck),writes=v['writes'],dispatches=state['last']['dispatches']+64)):
                raise ValueError('unbounded or unauthenticated orphan recovery')
            recovery = v
            if not orphan_stuck: complete_pending = v
        elif event == 'HELD':
            if (not orphan_stuck or recovery is None or not samples or dispatches != samples[-1]['dispatches']
                or holds and dispatches != holds[-1]['dispatches']+64
                or v != dict(task=5,generation=2,root=roots[5],pages=pages[5],children=1,
                    writes=recovery['writes'],calls=0,ticks=0,dispatches=dispatches)):
                raise ValueError('failed recovery changed retained ownership or performed extra writes')
            holds.append(v)
        elif event == 'PRESSURE':
            if (pressure is not None or pressure_events or task != 5 or task in live or task in owned
                or 3 not in live or 4 not in live or generation[task] != 1
                or v != dict(task=5,generation=2,owner=3,owner_generation=1,target=0,
                    target_generation=1,handle=(2<<32)|0x50003,owner_limit=2,dispatches=dispatches)):
                raise ValueError('quota pressure identity, lease or unchanged limit differs')
            pressure = v
            pressure_events.append(dict(event=event, **v))
        elif event == 'RELIEF':
            if pressure is None or task != 5 or task not in failures or v != pressure:
                raise ValueError('quota relief lacks exact retained pressure lease')
            pressure_events.append(dict(event=event, **v))
            pressure = None
        elif event == 'REJECT':
            reason = 2 if launch_quota and task == 5 else 1
            if (task not in (4,5) or task in live or task in owned or task in failures or 3 not in live
                or generation[task] != 1 or v['generation'] != 2 or v['sequence'] != 2
                or v['owned_pages'] != pages[task] or v['reason'] != reason or v['syscalls'] != 0
                or not valid_root(v['root']) or any(v['root'] == roots[j] for j in owned)):
                raise ValueError('rejection identity, authority or image ownership')
            if reason == 2 and (pressure is None or pressure['dispatches'] != dispatches):
                raise ValueError('quota rejection lacks actual pressure boundary')
            roots[task], generation[task] = v['root'], 2
            previous_calls[task] = previous_ticks[task] = 0
            frozen.pop(task, None)
            owned.add(task); failures[task] = v; rejections.append(v)
        elif event == 'FAILED':
            rejected = failures.get(task)
            if (rejected is None or task in live or task not in owned or v['published'] != int(not launch_orphan)
                or any(v[n] != rejected[n] for n in ('task','generation','sequence','root'))):
                raise ValueError('failed launch lacks exact retained permit')
            if task == 4:
                if dispatches != rejected['dispatches'] or complete_pending is not None:
                    raise ValueError('immediate cleanup differs')
            else:
                if complete_pending is None or dispatches != complete_pending['dispatches']:
                    raise ValueError('failure published before deferred reclamation')
                completed[(task,2)] = cleaning.pop(task)
                complete_pending = None
            owned.remove(task); failures.pop(task); failed.append(v)
        elif event == 'SURFACE':
            surface_generation = 2 if launch_failure and v['generation'] == 3 else v['generation']
            if launch_quota and task == 5 and v['generation'] == 3:
                surface_generation = 3
            if (pending is None or surface_pending or any(v[n] != pending[n] for n in ('task','generation','dispatches'))
                or v['entered'] != 0 or v['send'] != (surface_generation<<32)|0x10003):
                raise ValueError('surface lacks exact pre-entry handoff and attenuated grant')
            surfaces.append(v); surface_pending=True
        elif event in ('WAIT','WAKE'):
            if (file_controls or claimed_requester or task not in (4,5) or task not in live
                or task in cleaning or v['generation'] != generation[task] or (bad_file and task == 5)
                or v['calls'] < previous_calls[task]):
                raise ValueError('invalid live file waiter')
            if event == 'WAIT':
                if task in waiting or v['queued']+v['claimed'] != 1 or v['completed'] != 0 or v['calls'] == 0:
                    raise ValueError('wait requires one outstanding request')
                waiting[task] = v
            else:
                parked = waiting.pop(task, None)
                if (parked is None or v['calls'] != parked['calls'] or v['dispatches'] <= parked['dispatches']
                    or v['queued'] != 0 or v['claimed'] != 0 or v['completed'] != 1):
                    raise ValueError('wake requires unchanged calls and one completed request')
                wake_pairs.append(dict(wait=parked,wake=v))
            previous_calls[task] = v['calls']
        elif event == 'CLAIMED':
            if (not claimed_requester or task != 4 or task not in live or v['generation'] != generation[task]
                or v['waiting'] != 1 or v['stale_wait_rejected'] != 1 or v['service_task'] != 1 or v['service_generation'] != 1):
                raise ValueError('invalid claimed waiting requester')
            claim_pending=v;claimed_waiters.append(v)
        elif event == 'REQUESTER':
            if not (file_controls or claimed_requester) or task != 4 or task not in live or v['generation'] != generation[task] or v['queued']+v['claimed'] != 1 or v['completed'] != 0 or v['detached'] != 1:
                raise ValueError('invalid outstanding-request death observation')
            if claimed_requester:
                if claim_pending is None or v['queued'] != 0 or v['claimed'] != 1 or any(v[n] != claim_pending[n] for n in ('task','generation','dispatches')):
                    raise ValueError('claimed waiter and request do not match')
                claim_pending=None
            requester_pending = v
            requesters.append(v)
        elif event == 'HANDOFF':
            if task not in (4,5) or task in live or 3 not in live:
                raise ValueError('handoff outside application lifetime')
            expected = generation[task]+1
            if task in failures or expected > final_generation or v['generation'] != expected or v['control'] != (expected<<32)|0x10001 or v['files'] != (expected<<32)|0x10002:
                raise ValueError('handoff generation or grants')
            if v['startup_files'] != v['files'] + ((1<<32) if bad_file and task == 5 else 0) or v['bytes'] != ((192 if task==4 else 200) if windows else 176) or v['entered'] != 0:
                raise ValueError('startup handoff bytes or authority control')
            pending = v
            handoffs.append(v)
        elif event == 'ADMIT':
            if surface_pending != windows: raise ValueError('window application missing surface grant')
            surface_pending=False
            if pending is None or any(v[n] != pending[n] for n in ('task','generation','dispatches')):
                raise ValueError('admission has no exact owned handoff')
            expected = generation[task]+1
            process_slot = 6-task if file_controls or claimed_requester else task-3
            if surface_lifecycle: process_slot = 2*(task-4)+1
            process_generation = 2 if launch_failure and expected == 3 else expected
            if launch_quota and task == 5 and expected == 3:
                process_generation = 3
            if v['sequence'] != expected or v['handle'] != (process_generation<<32)|0x50000|process_slot or v['owned_pages'] != pages[task]:
                raise ValueError('launch sequence, handle or pages')
            if not valid_root(v['root']) or any(v['root'] == roots[j] for j in owned if j != task) or (expected == 1 and v['root'] != roots[task]):
                raise ValueError('launch root alias')
            if (expected == 1) != (task in owned): raise ValueError('unreclaimed image reused')
            roots[task], generation[task] = v['root'], expected
            previous_calls[task] = previous_ticks[task] = 0
            frozen.pop(task, None)
            live.add(task); owned.add(task); admits.append(v); pending = None
        elif event == 'RETIRE':
            if task in waiting: raise ValueError('unqualified waiting task retirement')
            if task not in live or task not in owned or v['generation'] != generation[task] or v['released_pages'] != pages[task]:
                raise ValueError('retirement identity or pages')
            expected = (1<<32) if task < 4 else (2<<32)|6 if task == 5 and generation[task] == 1 else 4<<32
            if launch_orphan and task in (3,4):
                if (not job_events or dispatches != job_events[0]['dispatches']
                    or task == 3 and len(retires) != 1 or task == 4 and 3 in live):
                    raise ValueError('owner or sibling retired outside exact job closure')
                expected = 4<<32
            if (file_controls or claimed_requester) and task == 4:
                expected = 4<<32 if claimed_requester else (1<<32)|85
                if requester_pending is None or any(v[n] != requester_pending[n] for n in ('task','generation','dispatches')):
                    raise ValueError('probe exit lacks outstanding-request retirement')
                requester_pending = None
            if v['outcome'] != expected or v['calls'] == 0 or v['calls'] < previous_calls[task]:
                raise ValueError('wrong terminal outcome or lost accounting')
            if deferred_cleanup and task >= 4:
                if complete_pending is None or any(v[n] != complete_pending[n] for n in ('task','generation','dispatches')):
                    raise ValueError('retirement before cleanup completion')
                state = cleaning.pop(task)
                if any(s[f'calls{task}'] != v['calls'] for s in state['samples']):
                    raise ValueError('retained terminal calls changed')
                completed[(task,generation[task])] = state
                complete_pending = None
            elif complete_pending is not None:
                raise ValueError('wrong cleanup owner retired')
            # CLOSE reply can retire the console before the shell consumes it.
            # Neither service may exit while either application remains live.
            if task < 4 and (4 in live or 5 in live or failures) and not (launch_orphan and task == 3 and job_events): raise ValueError('service abandoned live children or retained launch')
            previous_calls[task] = v['calls']
            live.remove(task); owned.remove(task); retires.append(v)
        else:
            flushes = sum(r['outcome'] == 4<<32 for r in retires)
            flushes += sum(task not in failures and not (task == 5 and generation[task] == 1) for task in cleaning)
            if dispatches != (len(samples)+1)*64 or dispatches < last_event or v['cr3_writes'] != 2*dispatches+flushes or v['extra_flushes'] != flushes:
                raise ValueError('dispatch/flush accounting')
            if v['pages'] != sum(pages[j] for j in owned) or v['live_mask'] != sum(1<<j for j in live) or [v['generation4'],v['generation5']] != generation[4:] or v['retired'] != len(retires) or v['unused'] != len(failed):
                raise ValueError('lifecycle accounting')
            for j in range(6):
                pair = (v[f'calls{j}'], v[f'ticks{j}'])
                if j in failures and pair != (0,0): raise ValueError('rejected image executed or consumed runtime')
                if j in waiting and pair[0] != waiting[j]['calls']: raise ValueError('blocked task executed syscalls')
                if pair[0] < previous_calls[j] or pair[1] < previous_ticks[j]: raise ValueError('accounting regressed')
                if j < 2 and (pair[0] <= previous_calls[j] or pair[1] <= previous_ticks[j]): raise ValueError('survivor stopped progressing')
                if failures and j < 4 and j in live and (pair[0] <= previous_calls[j] or pair[1] <= previous_ticks[j]):
                    raise ValueError('service stopped during rejected-image retention')
                if j not in live and pair != frozen.setdefault(j, pair): raise ValueError('retired image resumed')
                previous_calls[j], previous_ticks[j] = pair
            samples.append(v)
            for state in cleaning.values(): state['samples'].append(v)
    if launch_orphan:
        if (pending is not None or complete_pending is not None or requester_pending is not None or claim_pending is not None or waiting
            or recovery is None or live != {0,1,2} or owned != ({0,1,2,5} if orphan_stuck else {0,1,2})
            or generation[4:] != [1,2] or [(r['task'],r['generation']) for r in retires] != [(5,1),(3,1),(4,1)]
            or [(a['task'],a['generation']) for a in admits] != [(4,1),(5,1)]
            or len(handoffs) != 2 or len(surfaces) != 2 or len(rejections) != 1
            or set(failures) != ({5} if orphan_stuck else set()) or set(cleaning) != ({5} if orphan_stuck else set())
            or set(completed) != (set() if orphan_stuck else {(5,2)}) or len(failed) != int(not orphan_stuck)
            or len(job_events) != (2 if orphan_stuck else 3)):
            raise ValueError('incomplete rejected orphan lifecycle')
        after = [s for s in samples if s['dispatches'] > recovery['dispatches']]
        if (len(after) < 8 or after[-1]['dispatches'] < recovery['dispatches']+512
            or any(b[f'{field}{peer}'] <= a[f'{field}{peer}'] for a,b in zip(after,after[1:])
                   for peer in (0,1,2) for field in ('calls','ticks'))
            or (len(holds) != len(after) if orphan_stuck else bool(holds))):
            raise ValueError('independent services or bounded retained observation missing')
    elif pending is not None or failures or cleaning or complete_pending is not None or requester_pending is not None or claim_pending is not None or waiting or live != {0,1} or owned != {0,1} or generation[4:] != [final_generation]*2 or len(retires) != 6:
        raise ValueError('incomplete application lifecycle')
    if launch_failure and not launch_orphan and (len(rejections) != 2 or len(failed) != 2 or set(completed) != {(5,2)}):
        raise ValueError('both admission failures and deferred cleanup required')
    if launch_quota and (pressure is not None or len(pressure_events) != 2):
        raise ValueError('complete native quota pressure and relief required')
    if deferred_cleanup and set(completed) != {(4,1),(4,2),(5,1),(5,2)}:
        raise ValueError('both generations require deferred cleanup')
    if file_controls and len(requesters) != 2: raise ValueError('both diagnostic generations required')
    if claimed_requester and (len(requesters) != 2 or len(claimed_waiters) != 2): raise ValueError('both waiting requester generations required')
    if file_waits:
        expected = {(4,1),(4,final_generation)} if bad_file else {(4,1),(4,final_generation),(5,1),(5,final_generation)}
        if launch_orphan: expected = {(4,1)} if bad_file else {(4,1),(5,1)}
        if {(p['wait']['task'],p['wait']['generation']) for p in wake_pairs} != expected:
            raise ValueError('native file wait/wakeup coverage missing')
    concurrent = any(v['live_mask'] == 63 and min(v['calls4'],v['calls5'],v['ticks4'],v['ticks5']) > 0 for v in samples)
    if claimed_requester:
        concurrent = any(v['live_mask'] & (1<<5) and min(v['calls5'],v['ticks5']) > 0 for v in samples)
    if len(samples) < 8 or any(v['live_mask'] != (7 if launch_orphan else 3) for v in samples[-2:]) or not concurrent:
        raise ValueError('concurrent apps or post-retirement survival missing')
    fault = next(r for r in retires if r['task'] == 5 and r['generation'] == 1)
    restart = job_events[0] if launch_orphan else next(a for a in admits if a['task'] == 5 and a['generation'] == final_generation)
    survivors = [v for v in samples if fault['dispatches'] < v['dispatches'] < restart['dispatches']]
    before_fault = [v for v in samples if v['dispatches'] < fault['dispatches']]
    mask = 15 if file_controls or claimed_requester else 31
    peer = 1 if file_controls or claimed_requester else 4
    if not before_fault or not any(v['live_mask'] == mask and v[f'calls{peer}'] > before_fault[-1][f'calls{peer}'] and v['calls3'] > before_fault[-1]['calls3'] for v in survivors):
        raise ValueError('text and shell progress after contained app fault missing')
    result = dict(transfer_prefix=common, start=start, program_bytes=sizes, handoffs=handoffs,
                admits=admits, retires=retires, samples=samples, bad_file_handle=bad_file,
                native_execution_requires_guest_binding=True, useful_applications=0,
                deferred_cleanup=deferred_cleanup, cleanup_events=cleanup_events,
                live_parent_recovery=deferred_cleanup, native_exhaustion_qualified=False,
                multiple_pending_cleanup_owners_qualified=False,
                file_controls=file_controls, requester_deaths=requesters,
                file_wait_pairs=wake_pairs,
                bundled_files=False, iso_built=False, production_ready=False)
    if windows:
        result.update(surface_grants=surfaces, window_profile=True)
    if window_capacity:
        result.update(window_capacity=True,window_service_code_pages=7,ordinary_code_pages_maximum=4)
    if surface_lifecycle:
        result['surface_lifecycle'] = True
    if launch_session:
        result.update(launch_session=True, launch_shell_code_pages=5, native_plc1_control_verified=False)
    if launch_failure:
        result.update(launch_failure=True, diagnostic_only=True, rejections=rejections,
                      failed_launches=failed, graphical_failure_retry_verified=False)
    if launch_quota:
        result.update(launch_quota=True, pressure_events=pressure_events,
                      native_process_quota_recovery=not launch_orphan)
    if launch_orphan:
        result.update(launch_orphan=True,orphan_stuck=orphan_stuck,job_events=job_events,
            orphan_recovery=recovery,retained_observations=holds,supervisor_cancelled_owner=True,
            actual_owner_ud2=False,orphan_cleanup_recovered=not orphan_stuck,
            repeated_recovery_writes_rejected=orphan_stuck,general_owner_death_recovery=False)
    if claimed_requester:
        result.update(claimed_requester=True,claimed_waiters=claimed_waiters,diagnostic_requester_is_useful_app=False,
                      kernel_injected_waiting_cancellation=True,late_reply_denial_asserted_by_native_service=True,
                      exhaustive_request_interleavings=False)
    return result


def text_result(content: bytes) -> bytes:
    # Independent host expectation, not the Rust app's parsing implementation.
    return f'text: bytes={len(content)} words={len(content.split())} lf={content.count(bytes([10]))}\r\n'.encode()


def scenario(nonce: str, *, bad_file: bool = False, launch_failure: bool = False) -> shell.Scenario:
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
    if launch_failure:
        command(b'start numbers', b'numbers: launch failed\r\n')
        command(b'cat /version.txt', files.VERSION)
    command(b'start numbers', b'numbers: admitted\r\n')
    numbers(b'/numbers.csv', numeric)
    command(b'status numbers', b'numbers: attached\r\n')
    command(b'stop text', b'text: stop requested\r\n')
    command(b'status text', b'text: cancelled\r\n')
    if launch_failure:
        command(b'start text', b'text: launch failed\r\n')
        command(b'cat /version.txt', files.VERSION)
    command(b'start text', b'text: admitted\r\n')
    command(b'text /numbers.csv', text_result(files.NUMBERS))
    command(b'stop text', b'text: stop requested\r\n')
    command(b'status text', b'text: cancelled\r\n')
    command(b'stop numbers', b'numbers: stop requested\r\n')
    command(b'status numbers', b'numbers: cancelled\r\n')
    command(b'exit', b'Bye.\r\n', True)
    return shell.Scenario('stale-app-file' if bad_file else 'application-session', nonce, tuple(steps))


def orphan_scenario(nonce: str, *, bad_file: bool = False) -> shell.Scenario:
    original = scenario(nonce, bad_file=bad_file, launch_failure=True)
    command, starts, steps = bytearray(), 0, []
    for byte, response in original.steps:
        if byte == b'\r':
            if command == b'start numbers': starts += 1
            if starts == 2:
                steps.append((byte, b'\r\n'))
                return shell.Scenario('rejected-orphan', nonce, tuple(steps))
            command.clear()
        else:
            command.extend(byte)
        steps.append((byte, response))
    raise ValueError('rejected launch command missing')


def file_control_scenario(nonce: str, *, bad_file: bool = False, claimed_requester: bool = False) -> shell.Scenario:
    if re.fullmatch(r'[0-9a-f]{16}', nonce) is None: raise ValueError('independent challenge required')
    steps=[]
    def command(line, result, close=False):
        steps.extend((bytes([b]), bytes([b])) for b in line)
        steps.append((b'\r',b'\r\n'+result+(b'' if close else shell.PROMPT)))
    def numbers():
        values=list(map(int,files.NUMBERS.splitlines()[1:]))
        result=f'numbers: count={len(values)} sum={sum(values)} min={min(values)} max={max(values)}\r\n'.encode()
        command(b'numbers /numbers.csv',b'numbers: file service unavailable\r\n' if bad_file else result)
    command(b'start numbers',b'numbers: admitted\r\n')
    numbers()
    for _ in range(2):
        command(b'start text',b'text: admitted\r\n')
        command(b'status text',b'text: cancelled\r\n' if claimed_requester else b'text: exit 0x00000055\r\n')
        command(b'cat /version.txt',files.VERSION)
        numbers()
    command(b'fault numbers',b'numbers: fault requested\r\n')
    command(b'status numbers',b'numbers: fault 0x00000006\r\n')
    command(b'cat /version.txt',files.VERSION)
    command(b'echo '+nonce.encode(),nonce.encode()+b'\r\n')
    command(b'start numbers',b'numbers: admitted\r\n')
    numbers()
    command(b'stop numbers',b'numbers: stop requested\r\n')
    command(b'status numbers',b'numbers: cancelled\r\n')
    command(b'exit',b'Bye.\r\n',True)
    return shell.Scenario('claimed-requester-controls' if claimed_requester else 'file-request-controls',nonce,tuple(steps))


def negative_controls(markers: list[str], *, bad_file: bool = False, deferred_cleanup: bool = False, file_controls: bool = False, claimed_requester: bool = False, file_waits: bool = False, windows: bool = False, window_capacity: bool = False, surface_lifecycle: bool = False, launch_session: bool = False, launch_failure: bool = False, launch_quota: bool = False, launch_orphan: bool = False, orphan_stuck: bool = False) -> int:
    options = dict(bad_file=bad_file, deferred_cleanup=deferred_cleanup, file_controls=file_controls,
        claimed_requester=claimed_requester,file_waits=file_waits,windows=windows,window_capacity=window_capacity,
        surface_lifecycle=surface_lifecycle,launch_session=launch_session,launch_failure=launch_failure,
        launch_quota=launch_quota,launch_orphan=launch_orphan,orphan_stuck=orphan_stuck)
    validate_markers(markers, **options)
    cases = [markers[:i]+markers[i+1:] for i in range(len(markers)-1)]
    cases += [markers+[markers[-1]], markers+['POOLEOS:PANIC injected']]
    for i in range(29,len(markers)):
        for field in ('production','cpl','grants','control','files','startup_files','bytes','entered','send',
                      'handle','generation','sequence','released_pages','owned_pages','outcome','live_mask','cr3_writes',
                      'attempts','next','pages','admitted','dispatches','queued','claimed','completed','detached',
                      'waiting','stale_wait_rejected','service_task','service_generation',
                      'reason','syscalls','published','root') + (('children','retained_pages','recovered','writes','calls','ticks') if launch_orphan else ()):
            if ' '+field+'=' in markers[i]:
                changed = markers.copy()
                changed[i] = re.sub(r' '+field+r'=[0-9]+', ' '+field+'='+str((1<<64)-1), changed[i])
                cases.append(changed)
    for index, case in enumerate(cases):
        try: validate_markers(case, **options)
        except ValueError: continue
        changed = next((line for line, original in zip(case, markers) if line != original), '<length>')
        raise ValueError(f'hostile application observation accepted: case {index}: {changed}')
    return len(cases)
