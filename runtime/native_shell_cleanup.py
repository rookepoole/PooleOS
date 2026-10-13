"""PRECLAIM1 native retry observations, requiring complete PSHELLPROC1 sessions."""
import re
from runtime import native_shell_process as control

PREFIX = 'POOLEOS:RECLAIM RETRY '
RETRY = re.compile(r'POOLEOS:RECLAIM RETRY contract=PRECLAIM1 task=([45]) generation=([12]) mode=([1-4]) retained_pages=([0-9]+) dispatches=([0-9]+) released_pages=0 ordinary_free_denials=5 no_reentry=1 early_completion_rejected=1 cpl=0 production=0')

def validate_markers(markers: list[str], *, bad_owner: bool = False) -> dict:
    base = control.validate_markers([m for m in markers if not m.startswith(PREFIX)], bad_owner=bad_owner)
    expected = [v for v in base['retires'] if v['task'] >= 4]
    observed = []
    for i, marker in enumerate(markers):
        if not marker.startswith(PREFIX): continue
        match = RETRY.fullmatch(marker)
        if match is None or i+1 == len(markers): raise ValueError('invalid retained cleanup record')
        task, generation, mode, pages, dispatches = map(int, match.groups())
        if mode != 1+(task-4)*2+generation-1 or not 0 < dispatches < 1<<64:
            raise ValueError('invalid failure selection or dispatch')
        following = control.parse(markers[i+1], 'RETIRE')
        if (following['task'], following['generation'], following['released_pages'], following['dispatches']) != (task, generation, pages, dispatches):
            raise ValueError('retry must precede exact completed retirement')
        observed.append(following)
    if observed != expected or len(observed) != (2 if bad_owner else 4):
        raise ValueError('missing duplicate or reordered reclamation evidence')
    return dict(base, cleanup_contract='PRECLAIM1', retained_cleanup_retries=len(observed),
        injected_failure_modes=[1+(v['task']-4)*2+v['generation']-1 for v in observed],
        ordinary_free_denials=5*len(observed), early_completion_denials=len(observed),
        retry_policy='one_immediate_retry_after_each_injected_failure',
        asynchronous_cleanup_recovery=False, owner_death_recovery=False)

def negative_controls(markers: list[str], *, bad_owner: bool = False) -> int:
    validate_markers(markers, bad_owner=bad_owner)
    count = control.negative_controls([m for m in markers if not m.startswith(PREFIX)], bad_owner=bad_owner)
    cases = []
    for i, marker in enumerate(markers):
        if not marker.startswith(PREFIX): continue
        cases += [markers[:i]+markers[i+1:], markers[:i]+[marker]+markers[i:],
                  markers[:i]+[markers[i+1], marker]+markers[i+2:]]
        for field in ('task','generation','mode','retained_pages','dispatches','released_pages',
                      'ordinary_free_denials','no_reentry','early_completion_rejected','cpl','production'):
            changed = markers.copy()
            changed[i] = re.sub(r' '+field+r'=[0-9]+', ' '+field+'=99', marker)
            cases.append(changed)
    for case in cases:
        try: validate_markers(case, bad_owner=bad_owner)
        except ValueError: continue
        raise ValueError('hostile cleanup observation accepted')
    return count + len(cases)
