"""PJOB1: actual parent UD2, retained orphan cleanup and independent survivors."""
import re
from runtime import native_shell_process as control, native_shell_cleanup as cleanup
from runtime import native_prepared_cleanup as prepared, native_shell as shell

PREFIX = 'POOLEOS:JOB '
FIELDS = {'OWNER':'task generation root children dispatches',
          'CHILD':'task generation root prepared remaining published dispatches',
          'DRAINED':'children owned_pages dispatches'}

def parse(line, event):
    names = FIELDS[event].split()
    pattern = PREFIX+event+' contract=PJOB1'+''.join(' '+n+'=([0-9]+)' for n in names)+' cpl=0 production=0'
    match = re.fullmatch(pattern,line)
    if match is None: raise ValueError('malformed job observation')
    values = list(map(int,match.groups()))
    if any(v >= 1<<64 for v in values): raise ValueError('job value overflow')
    return dict(zip(names,values))

def validate_markers(markers, *, bad_owner=False, prepared_stop=False):
    holds = [(i,m) for i,m in enumerate(markers) if m.startswith(prepared.PREFIX)]
    if len(holds) != int(prepared_stop): raise ValueError('prepared hold count')
    dispatch = None
    if prepared_stop:
        match = prepared.HOLD.fullmatch(holds[0][1])
        if match is None: raise ValueError('invalid prepared hold')
        root,dispatch,writes = map(int,match.groups())
        if not 0 < dispatch < 1<<63 or writes != 2*(dispatch-1): raise ValueError('prepared exposure')
    base_markers = [m for m in markers if not m.startswith((PREFIX,prepared.PREFIX))]
    base = cleanup.validate_markers(base_markers,bad_owner=bad_owner,prepared_dispatch=dispatch,owner_death=True)
    observed = [(i,m) for i,m in enumerate(markers) if m.startswith(PREFIX)]
    if len(observed) != 3: raise ValueError('job lifecycle count')
    owner,child,drained = [parse(item[1],event) for item,event in zip(observed,FIELDS)]
    admission = base['admits'][0]
    retires = {v['task']:v for v in base['retires']}
    if set(retires) != {3,4} or len(base['admits']) != 1: raise ValueError('orphan participants')
    death = retires[3]['dispatches']
    if owner != dict(task=3,generation=1,root=base['start']['root3'],children=2,dispatches=death):
        raise ValueError('owner binding')
    if child != dict(task=4,generation=1,root=admission['root'],prepared=int(prepared_stop),remaining=1,published=0,dispatches=death):
        raise ValueError('orphan binding or false observer completion')
    independent_pages = sum(12+(base['program_bytes'][i]+4095)//4096 for i in range(3))
    if drained != dict(children=0,owned_pages=independent_pages,dispatches=death): raise ValueError('job drain')
    def position(event, task):
        return next(i for i,m in enumerate(markers) if m.startswith('POOLEOS:CONTROL '+event+' ') and control.parse(m,event)['task']==task)
    parent_i,child_i,unused_i = position('RETIRE',3),position('RETIRE',4),position('UNUSED',5)
    if not position('ADMIT',4) < observed[0][0] < parent_i < child_i < observed[1][0] < unused_i < observed[2][0]:
        raise ValueError('owner/orphan retirement order')
    if retires[4]['dispatches'] != death or base['unused'][0]['dispatches'] != death:
        raise ValueError('cleanup not in owner retirement window')
    if prepared_stop:
        if root != admission['root'] or not position('ADMIT',4) < holds[0][0] < observed[0][0] or not admission['dispatches'] < dispatch < death:
            raise ValueError('hold outside child lifetime')
        before = [control.parse(m,'RUN')['dispatches'] for m in markers[:holds[0][0]] if m.startswith('POOLEOS:CONTROL RUN ')]
        after = [control.parse(m,'RUN')['dispatches'] for m in markers[holds[0][0]+1:] if m.startswith('POOLEOS:CONTROL RUN ')]
        if not after or not (before[-1] if before else 0) < dispatch <= after[0]: raise ValueError('hold sample window')
    return dict(base,job_contract='PJOB1',owner_death_recovery=True,owner=owner,orphan=child,drained=drained,
                prepared_stop=prepared_stop,held_dispatch=dispatch,asynchronous_cleanup_recovery=False,
                general_owner_death_recovery=False,supervisor_restart=False)

def negative_controls(markers, *, bad_owner=False, prepared_stop=False):
    summary = validate_markers(markers,bad_owner=bad_owner,prepared_stop=prepared_stop)
    base = [m for m in markers if not m.startswith((PREFIX,prepared.PREFIX))]
    count = cleanup.negative_controls(base,bad_owner=bad_owner,prepared_dispatch=summary['held_dispatch'],owner_death=True)
    cases = [markers[:i]+markers[i+1:] for i,m in enumerate(markers) if m.startswith((PREFIX,prepared.PREFIX))]
    for i,m in enumerate(markers):
        if not m.startswith((PREFIX,prepared.PREFIX)): continue
        cases.append(markers[:i]+[m]+markers[i:])
        cases.append(markers[:30]+[m]+markers[30:i]+markers[i+1:])
        for field in re.findall(r' ([a-z0-9_]+)=[0-9]+',m):
            mutated = markers.copy()
            mutated[i] = re.sub(' '+field+r'=[0-9]+',' '+field+'=18446744073709551616',m)
            cases.append(mutated)
    for case in cases:
        try: validate_markers(case,bad_owner=bad_owner,prepared_stop=prepared_stop)
        except ValueError: continue
        raise ValueError('hostile orphan evidence accepted')
    return count+len(cases)

def scenario(nonce, *, bad_owner=False):
    if re.fullmatch(r'[0-9a-f]{16}',nonce) is None: raise ValueError('independent challenge required')
    steps=[]
    def command(line,result,close=False):
        steps.extend((bytes([b]),bytes([b])) for b in line)
        steps.append((b'\r',b'\r\n'+result+(b'' if close else shell.PROMPT)))
    command(b'status worker',b'worker: not started\r\n')
    command(b'start worker',b'worker: admitted\r\n')
    command(b'status worker',b'worker: attached\r\n')
    command(b'echo '+nonce.encode(),nonce.encode()+b'\r\n')
    if bad_owner: command(b'start fault',b'fault: denied\r\n')
    command(b'fault shell ',b'Unknown command.\r\n')
    command(b'fault shellx',b'Unknown command.\r\n')
    command(b'fault shell',b'',True)
    return shell.Scenario('orphan-bad-owner' if bad_owner else 'orphan',nonce,tuple(steps))
