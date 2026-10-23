"""Bounded real-device challenge while the shell remains blocked at its prompt."""
import copy
import time
from runtime import native_application_input as oracle
from tools import qualify_native_local_console as local


def actions():
    state={i:{0:'Ready',1:'',2:'',3:'',4:'',5:'',6:'',7:''} for i in (0,1)}
    result=[];draft=['','']
    def add(codes=None,focus=None,label='edit'):
        result.append(dict(codes=codes,focus=focus,label=label,expected=copy.deepcopy(state)))
    def clear(app):
        draft[app]='';state[app].update({6:'',7:''});add([0x1d,0x2e,0xae,0x9d],label='cancel-draft')
    def text(app,payload,values=None):
        for char in payload:
            if char=='\r':
                if values is None:state[app].update({0:'Job failed',1:'',2:'',3:'',4:'',5:''})
                else:state[app].update(oracle.result_rows(app,values))
            elif char=='\b':draft[app]=draft[app][:-1]
            else:draft[app]+=char
            state[app].update({6:draft[app][:24],7:draft[app][24:]})
            if len(draft[app])>48:state[app].update({6:'Input limit',7:''})
            add(local.scancodes(char.encode()),label='commit' if char=='\r' else 'edit')
    text(0,'PooleOX\bS native\r',[14,2,0])
    clear(0);text(0,'draft')
    # F12 is outside the desktop F1-F3 controls; stop typematic while holding A/Shift.
    draft[0]+='A';state[0][6]=draft[0];add([0x2a,0x1e,0x58,0xd8],label='hold-key-and-shift')
    add(focus=1,label='focus-numbers-with-held-keys')
    draft[1]='3';state[1][6]='3';add([0x1e,0x2a,0x04,0x84],label='held-repeat-suppressed')
    add([0x9e,0xaa],label='release-held-keys')
    text(1,', -2 8\r',[3,9,-2,8])
    clear(1);text(1,'9'*49+'\r')
    clear(1);text(1,'4 6\r',[2,10,4,6])
    add(focus=0,label='refocus-retains-draft')
    clear(0);text(0,'new\r',[3,1,0])
    return result


class InputProbe:
    def __init__(self, work):
        self.work=work;self.actions=actions();self.index=0;self.sent=False
        self.deadline=0;self.sample=0;self.move_pending=False;self.focus_phase=0
        self.evidence=[];self.movements=[];self.codes=[];self.captures=0
    @property
    def done(self):return self.index==len(self.actions)
    def capture(self,client):
        if self.captures>=256:raise ValueError('application capture bound exhausted')
        path=self.work/f'application-{self.captures:03}.ppm'
        client.execute('screendump',{'filename':str(path),'format':'ppm'})
        self.captures+=1
        return path
    def tick(self,client,interaction,pointer):
        if self.done:return
        now=time.monotonic();action=self.actions[self.index]
        if not self.sent:
            self.deadline=now+12;self.sample=now+.6;self.sent=True
            if action['codes'] is not None:
                interaction.inject(action['codes']);self.codes.append(dict(step=self.index,codes=action['codes']))
                return
        if now>self.deadline:raise TimeoutError(f'application input step {self.index} {action["label"]} not observed')
        if now<self.sample:return
        if action['focus'] is not None and self.focus_phase<3:
            x=pointer.w-(320 if action['focus']==0 else 336)+100
            y=(72 if action['focus']==0 else 264)+12
            left=self.focus_phase==1
            if not self.move_pending:
                dx=max(-96,min(96,x-pointer.x));dy=max(-96,min(96,y-pointer.y))
                target_left=left if (pointer.x+dx,pointer.y+dy)==(x,y) else pointer.left
                events=[{'type':'rel','data':{'axis':'x','value':dx}},{'type':'rel','data':{'axis':'y','value':dy}}]
                if target_left!=pointer.left:events.append({'type':'btn','data':{'button':'left','down':target_left}})
                client.execute('input-send-event',{'events':events})
                pointer.x+=dx;pointer.y+=dy;pointer.left=target_left
                self.move_pending=True;self.sample=now+.6
                return
            path=self.capture(client);w,h,pixels=oracle.frame(path.read_bytes())
            at=(pointer.y*w+pointer.x)*3
            if pixels[at:at+3]!=bytes.fromhex('172B24'):self.sample=now+.3;return
            self.movements.append(dict(step=self.index,x=pointer.x,y=pointer.y,left=pointer.left,frame=path.name,sha256=local.digest(path)))
            self.move_pending=False
            if (pointer.x,pointer.y,pointer.left)!=(x,y,left):return
            self.focus_phase+=1
            if self.focus_phase<3:return
        else:path=self.capture(client)
        self.sample=now+.3
        try:result=oracle.inspect_rows(path.read_bytes(),action['expected'])
        except ValueError:return
        if action['focus'] is not None:
            w,h,pixels=oracle.frame(path.read_bytes())
            x=w-(320 if action['focus']==0 else 336);y=72 if action['focus']==0 else 264
            at=(y*w+x)*3
            if pixels[at:at+3]!=bytes.fromhex('508D78'):return
        self.evidence.append(dict(step=self.index,label=action['label'],frame=path.name,expected=action['expected'],**result))
        self.index+=1;self.sent=False;self.focus_phase=0
