"""Independent pixel oracle for the PDISPLAY1 local terminal, not the boot splash."""
import hashlib


def inspect_rgb(width: int, height: int, pixels: bytes) -> dict:
    if not 320 <= width <= 4096 or not 200 <= height <= 2160 or len(pixels) != width * height * 3:
        raise ValueError('local console geometry or pixel payload differs')
    def pixel(x, y):
        start = (y * width + x) * 3
        return pixels[start:start + 3]
    if pixel(0, 0) != bytes.fromhex('F8FAF9') or pixel(0, height - 1) != bytes.fromhex('E8EEEB'):
        raise ValueError('local console frame bands missing or color order wrong')
    columns, rows = min((width - 48) // 12, 80), min((height - 104) // 16, 24)
    counts = {c: 0 for c in ('18221E', 'DCE9E3', '79C9A8')}
    for y in range(72, 72 + rows * 16):
        for x in range(24, 24 + columns * 12):
            key = pixel(x, y).hex().upper()
            if key in counts:
                counts[key] += 1
    title = sum(pixel(x, y) == bytes.fromhex('235B4B') for y in range(16, 30) for x in range(24, 108))
    if title < 100 or counts['18221E'] < columns * rows * 96 or counts['DCE9E3'] < 100 or counts['79C9A8'] != 20:
        raise ValueError('native title, readable terminal ink, background or single cursor missing')
    return dict(width=width, height=height, pixel_count=width * height, columns=columns, rows=rows,
                nonblank=True, native_terminal_palette_observed=True, title_pixels=title,
                terminal_pixels=counts)


def inspect_ppm(data: bytes) -> dict:
    header = data.split(b'\n', 3)
    if len(header) != 4 or header[0] != b'P6' or header[2] != b'255':
        raise ValueError('binary RGB PPM required')
    size = header[1].split()
    if len(size) != 2:
        raise ValueError('invalid PPM dimensions')
    result = inspect_rgb(int(size[0]), int(size[1]), header[3])
    return dict(result, sha256=hashlib.sha256(data).hexdigest().upper(), byte_count=len(data))
