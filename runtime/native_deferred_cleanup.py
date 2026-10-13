"""PCLEANUP2: native dispatch-separated retries, never COM2 proof or wall-time claims."""
import re
from runtime import native_shell_orphan as orphan, native_shell_process as control

PREFIX = 'POOLEOS:CLEANUP '
FIELDS = 'task generation attempts next pages dispatches admitted'.split()

def parse(marker,event):
    match = re.fullmatch(PREFIX+event+' contract=PCLEANUP2'+''.join(' '+n+'=([0-9]+)' for n in FIELDS)+' cpl=0 production=0',marker)
    if match is None: raise ValueError('malformed deferred cleanup record')
    values = list(map(int,match.groups()))
    if any(v >= 1<<64 for v in values): raise ValueError('cleanup value overflow')
    return dict(zip(FIELDS,values))

def validate_markers(markers, *, bad_owner=False, prepared_stop=False):
    observed = [(i,m) for i,m in enumerate(markers) if m.startswith(PREFIX)]
    if len(observed) != 3: raise ValueError('deferred cleanup event count')
    a,b,c = [parse(m,e) for (_,m),e in zip(observed,('DEFER','RETRY','COMPLETE'))]
    for n,v in enumerate((a,b,c)):
        if (v['task'],v['generation'],v['attempts'],v['admitted']) != (4,1,n,1): raise ValueError('cleanup identity or attempt')
    if a['next'] != a['dispatches']+64 or b['dispatches'] != a['next'] or b['next'] != b['dispatches']+128 or c['dispatches'] != b['next'] or c['next'] != 0 or c['pages'] != 0:
        raise ValueError('unbounded early delayed or fabricated retry')
    base = orphan.validate_markers([m for m in markers if not m.startswith(PREFIX)],bad_owner=bad_owner,
        prepared_stop=prepared_stop,cleanup_window=(a['dispatches'],c['dispatches']))
    pages = 12+(base['program_bytes'][4]+4095)//4096
    if a['pages'] != pages or b['pages'] != pages: raise ValueError('retained page loss')
    def pos(event,task):
        return next(i for i,m in enumerate(markers) if m.startswith('POOLEOS:CONTROL '+event+' ') and control.parse(m,event)['task']==task)
    if not pos('RETIRE',3) < observed[0][0] < pos('UNUSED',5) < observed[1][0] < observed[2][0] < pos('RETIRE',4):
        raise ValueError('cleanup event order')
    for i,v in zip((p[0] for p in observed),(a,b,c)):
        before = [control.parse(m,'RUN')['dispatches'] for m in markers[:i] if m.startswith('POOLEOS:CONTROL RUN ')]
        after = [control.parse(m,'RUN')['dispatches'] for m in markers[i+1:] if m.startswith('POOLEOS:CONTROL RUN ')]
        if not after or not (before[-1] if before else 0) <= v['dispatches'] <= after[0]: raise ValueError('cleanup outside observed interval')
    pending = [s for s in base['samples'] if a['dispatches'] <= s['dispatches'] < c['dispatches']]
    if len(pending) != 3 or any(s['live_mask'] != 23 or s['pages'] != base['drained']['owned_pages']+pages or s['retired'] != 1 for s in pending):
        raise ValueError('missing retained interval')
    if pending[-1]['calls4'] != next(r['calls'] for r in base['retires'] if r['task']==4): raise ValueError('cleanup calls changed')
    frozen = (pending[0]['calls4'],pending[0]['ticks4'])
    if any((s['calls4'],s['ticks4']) != frozen for s in base['samples'] if s['dispatches'] >= a['dispatches']):
        raise ValueError('retained or reclaimed task resumed')
    return dict(base,cleanup_contract='PCLEANUP2',deferred_events=[a,b,c],deferred_attempts=2,
        independent_dispatches_before_completion=192,exhaustion_native_qualified=False,
        general_waiting_orphan_recovery=False,wall_time_backoff=False)

def negative_controls(markers, *, bad_owner=False, prepared_stop=False):
    validate_markers(markers,bad_owner=bad_owner,prepared_stop=prepared_stop)
    cases = [markers[:i]+markers[i+1:] for i in range(len(markers)-1)]
    for i,m in enumerate(markers):
        if not m.startswith(PREFIX): continue
        cases += [markers[:i]+[m]+markers[i:], markers[:i]+[markers[i+1],m]+markers[i+2:]]
        for field in FIELDS+['cpl','production']:
            v=markers.copy(); v[i]=re.sub(' '+field+r'=[0-9]+',' '+field+'=18446744073709551616',m); cases.append(v)
    for field in ('calls4','ticks4','pages','extra_flushes','live_mask'):
        for i,m in enumerate(markers):
            if m.startswith('POOLEOS:CONTROL RUN '):
                v=markers.copy(); v[i]=re.sub(' '+field+r'=[0-9]+',' '+field+'=18446744073709551616',m); cases.append(v)
    for candidate in cases:
        try: validate_markers(candidate,bad_owner=bad_owner,prepared_stop=prepared_stop)
        except ValueError: continue
        raise ValueError('hostile deferred evidence accepted')
    return len(cases)
