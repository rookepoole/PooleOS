"""PENTEREDRECOVERY1: entered-child exhaustion after an actual owner UD2.

Success releases only after one closed-job attempt. Persistent failure preserves
the image while unrelated services progress. Marker validation is not a guest run.
"""
import re
from runtime import native_deferred_cleanup as deferred, native_shell_orphan as orphan
from runtime import native_shell_process as control

PREFIX = 'POOLEOS:CONTROL '
FIELDS = {
    'PARKED': 'task generation root attempts next pages writes calls ticks slices dispatches',
    'RECOVER': 'task generation root attempts retained_pages recovered children writes dispatches',
    'HELD': 'task generation root attempts next pages writes calls ticks slices dispatches',
}


def parse(marker, event):
    fields = FIELDS[event].split()
    match = re.fullmatch(PREFIX+event+' contract=PSHELLPROC1'+''.join(' '+f+'=([0-9]+)' for f in fields)+' cpl=3 production=0', marker)
    if match is None: raise ValueError('malformed entered recovery record')
    values = list(map(int, match.groups()))
    if any(v >= 1 << 64 for v in values): raise ValueError('entered recovery overflow')
    return dict(zip(fields, values))


def validate_markers(markers, *, bad_owner=False, prepared_stop=False, persistent=False):
    if prepared_stop: raise ValueError('entered recovery cannot use prepared child')
    clean = [(i, m) for i, m in enumerate(markers) if m.startswith(deferred.PREFIX)]
    if len(clean) != 4: raise ValueError('exhaustion requires exactly three failed retries')
    attempts = [deferred.parse(m, e) for (_, m), e in zip(clean, ('DEFER', 'RETRY', 'RETRY', 'EXHAUSTED'))]
    start = attempts[0]['dispatches']
    for n, v in enumerate(attempts):
        if (v['task'], v['generation'], v['attempts'], v['admitted']) != (4, 1, n, 1):
            raise ValueError('exhaustion identity or attempt')
        if v['dispatches'] != start + (0, 64, 192, 448)[n] or v['next'] != (start + (64, 192, 448)[n] if n < 3 else 0):
            raise ValueError('exhaustion backoff changed')
    extra = {e: [(i, parse(m, e)) for i, m in enumerate(markers) if m.startswith(PREFIX+e+' ')] for e in FIELDS}
    if len(extra['PARKED']) != 1 or len(extra['RECOVER']) != 1 or bool(extra['HELD']) != persistent:
        raise ValueError('missing or repeated recovery opportunity')
    park_i, parked = extra['PARKED'][0]
    recover_i, recovered = extra['RECOVER'][0]
    end = recovered['dispatches']
    if end != start + 512: raise ValueError('missing recovery cooldown')
    removed = tuple(PREFIX+e+' ' for e in FIELDS)+(deferred.PREFIX,)
    base_markers = [m for m in markers if not m.startswith(removed)]
    if persistent:
        jobs = [(i, m) for i, m in enumerate(base_markers) if m.startswith(orphan.PREFIX)]
        if len(jobs) != 1: raise ValueError('retained child cannot complete or drain')
        owner = orphan.parse(jobs[0][1], 'OWNER')
        base = control.validate_markers([m for m in base_markers if not m.startswith(orphan.PREFIX)],
            bad_owner=bad_owner, owner_death=True, cleanup_window=(start, 1 << 64), retained_cleanup=True)
        if len(base['admits']) != 1 or [v['task'] for v in base['retires']] != [3]:
            raise ValueError('retained child released or readmitted')
        if owner != dict(task=3, generation=1, root=base['start']['root3'], children=2, dispatches=start):
            raise ValueError('retained owner binding')
        if base['retires'][0]['dispatches'] != start or base['unused'][0]['dispatches'] != start:
            raise ValueError('owner fault not tied to cleanup')
        base.update(owner=owner)
    else:
        base = orphan.validate_markers(base_markers, bad_owner=bad_owner, cleanup_window=(start, end))
    admission = base['admits'][0]
    pages = 12 + (base['program_bytes'][4]+4095)//4096
    if any(v['pages'] != pages for v in attempts): raise ValueError('page loss before rescue')
    if any(parked[k] != v for k, v in dict(task=4, generation=1, root=admission['root'], attempts=0,
            next=start+64, pages=pages, dispatches=start).items()):
        raise ValueError('parked identity or runtime binding')
    if not (0 < parked['calls'] and 0 < parked['ticks'] and 0 < parked['slices'] <= start and parked['writes'] > 0):
        raise ValueError('child never entered or was not scrubbed')
    expected = dict(task=4, generation=1, root=admission['root'], attempts=1, retained_pages=pages if persistent else 0,
        recovered=int(not persistent), children=int(persistent), dispatches=end)
    if any(recovered[k] != v for k, v in expected.items()) or recovered['writes'] <= parked['writes']:
        raise ValueError('incorrect recovery disposition')
    def pos(event, task):
        return next(i for i, m in enumerate(markers) if m.startswith(PREFIX+event+' ') and control.parse(m, event)['task'] == task)
    owner_i = next(i for i, m in enumerate(markers) if m.startswith(orphan.PREFIX+'OWNER '))
    order = [pos('ADMIT', 4), owner_i, pos('RETIRE', 3), clean[0][0], park_i, pos('UNUSED', 5),
        clean[1][0], clean[2][0], clean[3][0], recover_i]
    if not persistent: order.append(pos('RETIRE', 4))
    if order != sorted(set(order)): raise ValueError('recovery lifecycle order')
    job_events = [(i, orphan.parse(m, e)) for i, m in enumerate(markers) for e in orphan.FIELDS if m.startswith(orphan.PREFIX+e+' ')]
    for i, v in [(i, a) for (i, _), a in zip(clean, attempts)]+extra['PARKED']+extra['RECOVER']+job_events:
        before = [s['dispatches'] for m in markers[:i] if m.startswith(PREFIX+'RUN ') for s in [control.parse(m, 'RUN')]]
        after = [s['dispatches'] for m in markers[i+1:] if m.startswith(PREFIX+'RUN ') for s in [control.parse(m, 'RUN')]]
        if not after or not (before[-1] if before else 0) <= v['dispatches'] <= after[0]:
            raise ValueError('recovery outside observed interval')
    pending = [s for s in base['samples'] if start <= s['dispatches'] < end]
    if len(pending) != 8: raise ValueError('missing exhaustion survival window')
    for s in base['samples']:
        if s['dispatches'] >= start and (s['calls4'], s['ticks4']) != (parked['calls'], parked['ticks']):
            raise ValueError('entered child resumed or lost accounting')
    held = extra['HELD']
    if persistent:
        post = [(i, control.parse(m, 'RUN')) for i, m in enumerate(markers) if m.startswith(PREFIX+'RUN ') and control.parse(m, 'RUN')['dispatches'] > end]
        if len(held) != len(post) or len(held) < 3 or held[-1][1]['dispatches']-held[0][1]['dispatches'] < 128:
            raise ValueError('missing persistent survival interval')
        for (i, v), (run_i, sample) in zip(held, post):
            expected = dict(parked, attempts=3, next=0, writes=recovered['writes'], dispatches=sample['dispatches'])
            if v != expected or i != run_i+1: raise ValueError('retained image changed or extra writes occurred')
    return dict(base, entered_recovery_contract='PENTEREDRECOVERY1', deferred_events=attempts,
        parked=parked, recovery=recovered, held=[v for _, v in held], persistent=persistent,
        deferred_attempts=3, recovery_attempts=1, independent_dispatches_before_recovery=512,
        exhausted_entered_recovery_observed=True, general_owner_death_recovery=False, supervisor_restart=False)


def negative_controls(markers, **options):
    validate_markers(markers, **options)
    cases = [markers[:i]+markers[i+1:] for i in range(len(markers)-1)]
    cases += [markers+[markers[-1]], markers+['POOLEOS:PANIC injected']]
    for i, m in enumerate(markers[29:], 29):
        cases.append(markers[:i]+[m]+markers[i:])
        if i+1 < len(markers): cases.append(markers[:i]+[markers[i+1],m]+markers[i+2:])
        for field in re.findall(r' ([a-z0-9_]+)=[0-9]+', m):
            changed = markers.copy()
            changed[i] = re.sub(' '+field+r'=[0-9]+', ' '+field+'=18446744073709551616', m)
            cases.append(changed)
    for number, candidate in enumerate(cases):
        try: validate_markers(candidate, **options)
        except (ValueError, StopIteration): continue
        raise ValueError(f'hostile entered recovery evidence accepted: case {number}')
    return len(cases)
