"""Acquire the one hash-pinned host-only ISO library without installing it."""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
import zipfile
from email.parser import Parser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCK_PATH = Path(__file__).with_name("toolchain.json")
TOOLS = (ROOT / ".toolchains/native-demo-iso").resolve()


def lock_data() -> dict:
    return json.loads(LOCK_PATH.read_text(encoding="utf-8"))


def wheel_path() -> Path:
    return TOOLS / lock_data()["filename"]


def verify_wheel(path: Path) -> None:
    lock = lock_data()
    raw = path.read_bytes()
    if len(raw) != lock["byte_count"] or hashlib.sha256(raw).hexdigest().upper() != lock["sha256"]:
        raise ValueError("Demo ISO tool wheel does not match its pinned size/hash")
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("Demo ISO tool wheel CRC failure")
        metadata = Parser().parsestr(archive.read("pycdlib-1.20.0.dist-info/METADATA").decode("utf-8"))
        if metadata["Version"] != lock["version"] or metadata["License"] != lock["license"]:
            raise ValueError("Demo ISO tool version/license identity changed")


def load_library():
    path = wheel_path()
    verify_wheel(path)
    existing = sys.modules.get("pycdlib")
    if existing is not None and not str(existing.__file__).startswith(str(path)):
        raise ValueError("Refusing an unpinned pycdlib already loaded by the host")
    sys.path.insert(0, str(path))
    import pycdlib

    return pycdlib


def main() -> int:
    lock = lock_data()
    path = wheel_path()
    if not path.exists():
        TOOLS.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(lock["url"], timeout=30) as response:
            raw = response.read(lock["byte_count"] + 1)
        if len(raw) != lock["byte_count"] or hashlib.sha256(raw).hexdigest().upper() != lock["sha256"]:
            raise ValueError("Downloaded wheel size/hash mismatch; nothing installed")
        with path.open("xb") as stream:
            stream.write(raw)
    verify_wheel(path)
    print(f"DEMO_ISO_TOOL PASS {lock['name']} {lock['version']} {lock['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
