"""PCANCEL1: a selected-but-unentered child is stopped through retained cleanup."""
import re
from runtime import native_shell_process as control, native_shell_cleanup as cleanup

PREFIX = 'POOLEOS:PREPARED HOLD '
HOLD = re.compile(r'POOLEOS:PREPARED HOLD contract=PCANCEL1 task=4 generation=1 root=([0-9]+) dispatches=([0-9]+) cr3_writes=([0-9]+) calls=0 ticks=0 state=blocked entered=0 cpl=0 production=0')

def validate_markers(markers: list[str], *, bad_owner: bool = False) -> dict:
    indices = [i for i,m in enumerate(markers) if m.startswith(PREFIX)]
    if len(indices) != 1: raise ValueError('one exact prepared hold required')
    index = indices[0]
    match = HOLD.fullmatch(markers[index])
    if match is None: raise ValueError('invalid prepared hold')
    root, dispatch, writes = map(int, match.groups())
    if not 0 < root < 1 << 32 or root % 4096 or not 0 < dispatch < 1 << 63 or writes != 2*(dispatch-1):
        raise ValueError('prepared identity or exposure accounting')
    base = cleanup.validate_markers(markers[:index]+markers[index+1:], bad_owner=bad_owner, prepared_dispatch=dispatch)
    admission = next(v for v in base['admits'] if v['task'] == 4 and v['generation'] == 1)
    retirement = next(v for v in base['retires'] if v['task'] == 4 and v['generation'] == 1)
    admit_index = next(
        i for i,m in enumerate(markers) if m.startswith('POOLEOS:CONTROL ADMIT ') and control.parse(m,'ADMIT') == admission)
    retire_index = next(i for i,m in enumerate(markers) if m.startswith('POOLEOS:CONTROL RETIRE ') and control.parse(m,'RETIRE') == retirement)
    if not admit_index < index < retire_index or root != admission['root'] or not admission['dispatches'] < dispatch < retirement['dispatches']:
        raise ValueError('hold is not inside the exact prepared lifetime')
    before = [control.parse(m,'RUN')['dispatches'] for m in markers[:index] if m.startswith('POOLEOS:CONTROL RUN ')]
    after = [control.parse(m,'RUN')['dispatches'] for m in markers[index+1:] if m.startswith('POOLEOS:CONTROL RUN ')]
    if not after or not (before[-1] if before else 0) < dispatch <= after[0] or retirement['calls'] != 0:
        raise ValueError('hold ordering or execution claim')
    return dict(base, prepared_contract='PCANCEL1', prepared_stops=1, prepared_child_entered=False,
        held_scheduler_dispatches=1, hold=dict(root=root, dispatches=dispatch, cr3_writes=writes),
        prepared_cleanup_retention=True, owner_death_recovery=False)

def negative_controls(markers: list[str], *, bad_owner: bool = False) -> int:
    summary = validate_markers(markers, bad_owner=bad_owner)
    index = next(i for i,m in enumerate(markers) if m.startswith(PREFIX))
    base = markers[:index]+markers[index+1:]
    count = cleanup.negative_controls(base, bad_owner=bad_owner, prepared_dispatch=summary['hold']['dispatches'])
    cases = [base, markers[:index]+[markers[index]]+markers[index:], markers[:29]+[markers[index]]+markers[29:index]+markers[index+1:]]
    for name in ('task','generation','root','dispatches','cr3_writes','calls','ticks','entered','cpl','production'):
        changed = markers.copy()
        changed[index] = re.sub(r' '+name+r'=[0-9]+', ' '+name+'=99', changed[index])
        cases.append(changed)
    for case in cases:
        try: validate_markers(case, bad_owner=bad_owner)
        except ValueError: continue
        raise ValueError('hostile prepared cancellation evidence accepted')
    return count + len(cases)
