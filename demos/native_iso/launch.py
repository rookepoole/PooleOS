"""Show one bounded demo boot; never attach a host disk or network."""

from __future__ import annotations

import argparse
import json
import queue
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from demos.native_iso import qualify
from runtime import native_tier0


def show_demo(lock, base, directory, iso, launch_root, oracle, auto_close):
    import tkinter as tk
    from PIL import Image, ImageTk

    window = tk.Tk()
    window.title("PooleOS Native Demo - host viewer of actual QEMU frames")
    window.configure(background="#0C0F14")
    status = tk.StringVar(value="Starting real native ISO | Unsigned QEMU demo | No physical disk or network")
    tk.Label(window, textvariable=status, background="#181C22", foreground="#EEF2F5",
             anchor="w", padx=16, pady=12).pack(fill="x")
    screen = tk.Label(window, background="#0C0F14", borderwidth=0)
    screen.pack(fill="both", expand=True)
    width = min(1280, window.winfo_screenwidth() - 100)
    height = min(840, window.winfo_screenheight() - 100)
    window.geometry(f"{width}x{height}")
    messages = queue.Queue()
    cancel = threading.Event()
    closing = False
    finished = False
    failure = []
    captured = None

    def frame(path, label):
        messages.put(("frame", path, label))

    def worker():
        try:
            qualify.execute_once(lock, qualify.optical_profile(base), directory, iso,
                                 launch_root / "run", oracle, 120, on_frame=frame, cancel=cancel)
            messages.put(("done", None, "PKLOCK1 PASS | Emulator stopped | Actual captured kernel console"))
        except Exception as error:
            failure.append(error)
            messages.put(("error", None, f"Demo stopped: {error}"))

    def redraw(_event=None):
        if captured is not None:
            copy = captured.copy()
            copy.thumbnail((max(screen.winfo_width(), 1), max(screen.winfo_height(), 1)), Image.Resampling.LANCZOS)
            screen.photo = ImageTk.PhotoImage(copy)
            screen.configure(image=screen.photo)

    def close():
        nonlocal closing
        closing = True
        cancel.set()
        status.set("Stopping this demo's emulator...")
        if finished:
            window.destroy()

    def poll():
        nonlocal captured, finished
        try:
            while True:
                kind, path, label = messages.get_nowait()
                status.set(label)
                if kind == "frame":
                    with Image.open(path) as source:
                        captured = source.convert("RGB")
                    redraw()
                else:
                    finished = True
                    if closing:
                        window.destroy()
                        return
                    if auto_close:
                        window.after(2000, close)
        except queue.Empty:
            pass
        window.after(30, poll)

    window.protocol("WM_DELETE_WINDOW", close)
    screen.bind("<Configure>", redraw)
    thread = threading.Thread(target=worker, name="pooleos-demo", daemon=False)
    thread.start()
    window.after(30, poll)
    try:
        window.mainloop()
    finally:
        cancel.set()
        thread.join()
    if failure:
        raise failure[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", type=Path, default=ROOT / "outputs/native-demo-iso-pooleglass-v1")
    parser.add_argument("--auto-close", action="store_true", help="Close host viewer after the test finishes")
    args = parser.parse_args()
    directory, iso, _, inspection = qualify.validate_local_package(args.package_dir)
    receipt = json.loads((directory / "qualification.json").read_text(encoding="utf-8"))
    if receipt.get("iso_sha256") != inspection["sha256"] or receipt.get("status") != "pass_two_fresh_optical_boots" or receipt.get("production_ready") is not False:
        raise ValueError("This exact ISO has no passing local demo qualification")
    oracle = directory / "boot-builds/host/x86_64-pc-windows-msvc/debug/examples/render.exe"
    if not oracle.is_file():
        raise ValueError("Build the demo's local pixel oracle before launch")
    lock, base = native_tier0.validate_contracts(ROOT)
    native_tier0.verify_local_launch_runtime(lock, native_tier0.DEFAULT_QEMU_ROOT, ROOT)
    launch_root = Path(tempfile.mkdtemp(prefix="visible-demo-", dir=directory))
    print("PooleOS native demo: read-only CD-ROM, no host disk, no network, unsigned.", flush=True)
    show_demo(lock, base, directory, iso, launch_root, oracle, args.auto_close)
    print("Demo finished. No firmware or physical media was modified.")


if __name__ == "__main__":
    main()
