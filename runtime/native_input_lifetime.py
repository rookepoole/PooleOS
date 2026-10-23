"""Independent fixed-layout observations for focused application retirement."""
from runtime import native_application_input as cells, native_windows as windows


def pixel(data, x, y):
    w, h, raw = cells.frame(data)
    if type(x) is not int or type(y) is not int or not 0 <= x < w or not 0 <= y < h:
        raise ValueError('pixel outside frame')
    offset = (y*w+x)*3
    return raw[offset:offset+3]


def boundary(data, retired, focused_terminal=False):
    if type(retired) is not int or retired not in (0, 1) or type(focused_terminal) is not bool:
        raise ValueError('exact retired application and focus state required')
    visible = tuple(i != retired for i in range(2))
    frame = windows.inspect_ppm(data, expected=visible)
    w, h = frame['width'], frame['height']
    terminal = bytes.fromhex('508D78' if focused_terminal else '829090')
    for x, y in ((16, 48), (607, 48), (16, 399), (607, 399)):
        if pixel(data, x, y) != terminal:
            raise ValueError('terminal moved or implicit focus transferred')
    peer = 1-retired
    if pixel(data, w-(320 if peer == 0 else 336), 72 if peer == 0 else 264) != bytes.fromhex('829090'):
        raise ValueError('surviving app received implicit focus')
    for index in range(3):
        color = '508D78' if index == 0 and focused_terminal else 'F7FAF9'
        if pixel(data, index*160+12, h-3) != bytes.fromhex(color):
            raise ValueError('unexpected taskbar focus')
    draft = cells.inspect_rows(data, {peer: {6: '', 7: ''}})
    return dict(frame=frame, peer_draft=draft, retired=retired,
                focused_terminal=focused_terminal, implicit_focus_absent=not focused_terminal)


def controls(payload):
    result = []
    for command, status, target in ((b'fault numbers\r', b'status numbers\r', 1),
                                    (b'stop text\r', b'status text\r', 0)):
        start = payload.index(command)
        end = start+len(command)
        if start and payload[start-1:start] != b'\r':
            raise ValueError('control must start at a command boundary')
        if payload[end:end+len(status)] != status:
            raise ValueError('status must immediately follow control')
        result.append(dict(command=command, start=start, end=end,
                           status_end=end+len(status), target=target, generation=1))
    if result[0]['status_end'] > result[1]['start']:
        raise ValueError('retirement controls must be distinct and ordered')
    return result
