"""Independent fixed-layout frame oracle for the PWS1 pre-mouse application run."""
import hashlib


def inspect_rgb(width: int, height: int, pixels: bytes, *, expected=(True,True)) -> dict:
    return inspect_ppm(f'P6\n{width} {height}\n255\n'.encode('ascii')+pixels, expected=expected)


def inspect_ppm(data: bytes, *, expected=(True,True)) -> dict:
    if type(expected) is not tuple or len(expected)!=2 or any(type(v) is not bool for v in expected):
        raise ValueError('two explicit application visibility states required')
    parts=data.split(b'\n',3)
    if len(parts)!=4 or parts[0]!=b'P6' or parts[2]!=b'255': raise ValueError('RGB PPM required')
    size=parts[1].split()
    if len(size)!=2: raise ValueError('window frame dimensions')
    w,h=map(int,size); pixels=parts[3]
    if not 640<=w<=4096 or not 480<=h<=2160 or len(pixels)!=w*h*3: raise ValueError('window frame geometry')
    def pixel(x,y):
        at=(y*w+x)*3
        return pixels[at:at+3]
    def count(x,y,width,height,color):
        c=bytes.fromhex(color)
        return sum(pixel(xx,yy)==c for yy in range(y,y+height) for xx in range(x,x+width))
    if pixel(0,0)!=bytes.fromhex('F7FAF9') or pixel(0,40)!=bytes.fromhex('D3DFDF') or pixel(0,h-1)!=bytes.fromhex('F7FAF9'):
        raise ValueError('window desktop bands or color order')
    windows=[]
    for present,(x,y,title_width) in zip(expected,[(w-320,72,108),(w-336,264,144)]):
        title=count(x+10,y+6,title_width,16,'253E37')
        ink=count(x+8,y+36,288,128,'293B35')
        if not present:
            if title or ink or count(x+1,y+28,302,147,'F8FAF9') or (x>=608 and count(x,y,304,176,'D3DFDF')!=304*176):
                raise ValueError('retired application surface remains visible')
            continue
        if title<100 or ink<100 or pixel(x+2,y+30)!=bytes.fromhex('F8FAF9'):
            raise ValueError('application title and retained result surface missing')
        windows.append(dict(x=x,y=y,title_pixels=title,content_pixels=ink))
    terminal=count(24,84,264,304,'DCE9E3')
    if terminal<100: raise ValueError('native terminal content missing')
    return dict(width=w,height=h,sha256=hashlib.sha256(data).hexdigest().upper(),byte_count=len(data),
                nonblank=True,application_surfaces_observed=windows,terminal_ink_pixels=terminal,
                mouse_interaction_verified=False,production_ready=False)
