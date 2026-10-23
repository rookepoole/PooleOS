"""Final-frame oracle for the opt-in lifecycle profile after both apps stop."""
from runtime import native_windows

def inspect_ppm(data: bytes) -> dict:
    return native_windows.inspect_ppm(data, expected=(False,False))

def inspect_rgb(width: int, height: int, pixels: bytes) -> dict:
    return native_windows.inspect_rgb(width,height,pixels,expected=(False,False))
