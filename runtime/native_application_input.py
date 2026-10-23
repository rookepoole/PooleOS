"""Frozen 5x7 glyph fixture and exact surface-row oracle for native input."""
import hashlib

GLYPHS = {
    ' ': (0,0,0,0,0,0,0), ',': (0,0,0,0,0,4,8), '-': (0,0,0,31,0,0,0),
    '0': (14,17,19,21,25,17,14), '1': (4,12,4,4,4,4,14), '2': (14,17,1,2,4,8,31),
    '3': (30,1,1,14,1,1,30), '4': (2,6,10,18,31,2,2), '5': (31,16,16,30,1,1,30),
    '6': (14,16,16,30,17,17,14), '7': (31,1,2,4,8,8,8), '8': (14,17,17,14,17,17,14),
    '9': (14,17,17,15,1,1,14),
    'A': (14,17,17,31,17,17,17), 'B': (30,17,17,30,17,17,30),
    'I': (14,4,4,4,4,4,14), 'J': (7,2,2,2,2,18,12), 'L': (16,16,16,16,16,16,31),
    'M': (17,27,21,21,17,17,17), 'O': (14,17,17,17,17,17,14),
    'P': (30,17,17,30,16,16,16), 'R': (30,17,17,30,20,18,17),
    'S': (15,16,16,14,1,1,30), 'W': (17,17,17,21,21,27,17), 'X': (17,17,10,4,10,17,17),
    'a': (0,0,14,1,15,17,15), 'b': (16,16,30,17,17,17,30),
    'c': (0,0,15,16,16,16,15), 'd': (1,1,15,17,17,17,15),
    'e': (0,0,14,17,31,16,14), 'f': (6,9,8,28,8,8,8),
    'h': (16,16,30,17,17,17,17), 'i': (4,0,12,4,4,4,14),
    'l': (12,4,4,4,4,4,14), 'm': (0,0,26,21,21,21,21),
    'n': (0,0,30,17,17,17,17), 'o': (0,0,14,17,17,17,14),
    'p': (0,30,17,17,30,16,16), 'r': (0,0,22,25,16,16,16),
    's': (0,0,15,16,14,1,30), 't': (8,8,28,8,8,9,6),
    'u': (0,0,17,17,17,17,15), 'v': (0,0,17,17,17,10,4),
    'w': (0,0,17,17,21,21,10), 'x': (0,0,17,10,4,10,17),
    'y': (0,17,17,17,15,1,14),
}
INK = bytes.fromhex('293B35')
PAPER = bytes.fromhex('F8FAF9')


def frame(data):
    parts=data.split(b'\n',3)
    if len(parts)!=4 or parts[0]!=b'P6' or parts[2]!=b'255':raise ValueError('RGB PPM required')
    size=parts[1].split()
    if len(size)!=2:raise ValueError('frame dimensions')
    w,h=map(int,size)
    if not 1000<=w<=4096 or not 600<=h<=2160 or len(parts[3])!=w*h*3:raise ValueError('input frame geometry')
    return w,h,parts[3]


def row_bytes(text):
    if type(text) is not str or len(text)>24 or any(c not in GLYPHS for c in text):
        raise ValueError('unsupported exact row')
    rows=[]
    for y in range(16):
        row=bytearray()
        for char in text.ljust(24):
            bits=GLYPHS[char][y//2] if y<14 else 0
            for x in range(12):
                row.extend(INK if x<10 and bits & (1 << (4-x//2)) else PAPER)
        rows.append(bytes(row))
    return b''.join(rows)


def inspect_rows(data, expected):
    """Compare every pixel, including blank padding, not just counts or OCR."""
    w,h,pixels=frame(data)
    if not isinstance(expected,dict) or not expected:raise ValueError('explicit rows required')
    count=0
    for app, rows in expected.items():
        if type(app) is not int or app not in (0,1) or not isinstance(rows,dict) or not rows:
            raise ValueError('explicit application index and rows required')
        x,y=(w-320+8,72+36) if app==0 else (w-336+8,264+36)
        for row,text in rows.items():
            if type(row) is not int or not 0<=row<8:raise ValueError('row outside surface')
            raw=row_bytes(text)
            for line in range(16):
                at=((y+row*16+line)*w+x)*3
                if pixels[at:at+288*3]!=raw[line*288*3:(line+1)*288*3]:
                    raise ValueError(f'application {app} row {row} differs')
            count+=1
    return dict(width=w,height=h,rows_verified=count,pixels_verified=count*288*16,
                frame_sha256=hashlib.sha256(data).hexdigest().upper())


def result_rows(app, values):
    if app not in (0,1) or len(values)!=(3 if app==0 else 4):raise ValueError('result shape')
    names=('Bytes','Words','Lines') if app==0 else ('Rows','Sum','Min','Max')
    result={0:'Result snapshot',1:'',5:''}
    for i,(name,value) in enumerate(zip(names,values)):
        result[i+2]=name.ljust(6)+str(value).rjust(18)
    return result


def compact_scenario(case):
    """Keep both generations and all four file waits; omit unrelated shell tests."""
    commands=[];pending=[]
    for step in case.steps:
        pending.append(step)
        if step[0]==b'\r':commands.append(pending);pending=[]
    if pending:raise ValueError('incomplete shell command')
    selected=[];tail=False;first_text=False;first_numbers=False
    for command in commands:
        line=b''.join(s[0] for s in command)[:-1]
        if line==b'fault numbers':tail=True
        keep=tail or len(selected)<4
        if not tail and line==b'text /readme.txt' and len(selected)>=4 and not first_text:
            keep=True;first_text=True
        if not tail and line==b'numbers /numbers.csv' and not first_numbers:
            keep=True;first_numbers=True
        if keep:selected.append(command)
    if not first_text or not first_numbers or not tail:raise ValueError('input lifecycle scenario incomplete')
    return type(case)('native-application-input',case.nonce,tuple(s for group in selected for s in group))
