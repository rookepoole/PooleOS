from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tools import qualify_native_pooleboot as boot


READY = b"POOLEBOOT/0.1 FRAME READY\n"
DONE = b"POOLEOS:TEST TERMINAL"


class NativeBootCaptureTests(unittest.TestCase):
    def execute(self, stages, *, missing_frame=False, invalid_frame=False, quit_code=0, exited=False):
        self.calls = []
        self.process = mock.Mock(returncode=3 if exited else None, stderr=io.BytesIO())
        self.process.poll.side_effect = lambda: self.process.returncode
        self.process.kill.side_effect = lambda: setattr(self.process, "returncode", -1)
        self.client = mock.Mock()
        clock = [0.0]
        stage = [0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_dir = root / "run"
            run_dir.mkdir()
            (root / "vars.fd").write_bytes(b"fresh-vars-template")
            debug = run_dir / "debug.log"
            serial = run_dir / "serial.log"

            def publish():
                debug.write_bytes(stages[stage[0]])
                serial.write_bytes(stages[stage[0]])

            def sleep(seconds):
                clock[0] += seconds
                stage[0] = min(stage[0] + 1, len(stages) - 1)
                publish()

            def command(name, arguments=None):
                self.calls.append((name, stage[0]))
                if name == "screendump" and not missing_frame:
                    frame = b"terminal-frame" if DONE in stages[stage[0]] else b"initial-frame"
                    Path(arguments["filename"]).write_bytes(frame)
                if name == "quit":
                    self.process.returncode = quit_code
                return {}

            publish()
            self.client.execute.side_effect = command
            inspect = mock.Mock(return_value={"nonblank": True})
            if invalid_frame:
                inspect.side_effect = boot.native_pooleboot.PooleBootError("invalid frame")
            lock = {"firmware": {"files": [{"role": "vars_template_copy_only", "relative_path": "vars.fd"}]}}
            profile = {"evidence_contract": {"vars_copy": "vars-copy.fd", "debugcon_log": "debug.log", "serial_log": "serial.log"}}
            transcript = SimpleNamespace(data=b"handoff", summary={"valid": True})
            with mock.patch.object(boot.native_tier0, "_actual_command", return_value=["fake-qemu"]), \
                 mock.patch.object(boot, "_available_port", return_value=12345), \
                 mock.patch.object(boot.subprocess, "Popen", return_value=self.process), \
                 mock.patch.object(boot._QmpClient, "connect", return_value=(self.client, {})), \
                 mock.patch.object(boot.time, "monotonic", side_effect=lambda: clock[0]), \
                 mock.patch.object(boot.time, "sleep", side_effect=sleep), \
                 mock.patch.object(boot.native_live_boot_handoff, "extract_transcript", return_value=transcript), \
                 mock.patch.object(boot.native_pooleboot, "inspect_ppm", inspect):
                return boot._execute_once("unit", lock, profile, root, root / "media.img", run_dir, 1,
                    marker_validator=lambda markers: {"valid": True},
                    marker_extractor=lambda raw: raw.decode().splitlines(), completion_marker=DONE)

    def test_frame_is_captured_after_terminal_not_early_frame_ready(self):
        _, frame, _ = self.execute([READY, READY + DONE])
        self.assertEqual(frame, b"terminal-frame")
        self.assertEqual([call for call in self.calls if call[0] == "screendump"], [("screendump", 1)])
        self.process.kill.assert_not_called()
        self.client.close.assert_called_once()

    def test_ready_and_terminal_in_one_observation_capture_once(self):
        run, frame, handoff = self.execute([READY + DONE])
        self.assertEqual((frame, handoff), (b"terminal-frame", b"handoff"))
        self.assertEqual(sum(name == "screendump" for name, _ in self.calls), 1)
        self.assertEqual(run["qemu_exit_code"], 0)

    def test_ready_without_terminal_times_out_without_capturing(self):
        with self.assertRaisesRegex(boot.QualificationError, "timed out"):
            self.execute([READY])
        self.assertNotIn("screendump", [name for name, _ in self.calls])
        self.process.kill.assert_called_once()
        self.client.close.assert_called_once()

    def test_terminal_without_ready_fails_without_capturing(self):
        with self.assertRaisesRegex(boot.QualificationError, "timed out"):
            self.execute([DONE])
        self.assertNotIn("screendump", [name for name, _ in self.calls])
        self.process.kill.assert_called_once()

    def test_panic_before_terminal_prevents_capture(self):
        with self.assertRaisesRegex(boot.QualificationError, "panic marker"):
            self.execute([READY, READY + b"POOLEOS:PANIC\n" + DONE])
        self.assertNotIn("screendump", [name for name, _ in self.calls])
        self.process.kill.assert_called_once()

    def test_missing_dump_is_not_a_success(self):
        with self.assertRaisesRegex(boot.QualificationError, "did not create"):
            self.execute([READY + DONE], missing_frame=True)
        self.process.kill.assert_called_once()

    def test_invalid_dump_preserves_failure_and_cleans_up(self):
        with self.assertRaisesRegex(boot.native_pooleboot.PooleBootError, "invalid frame"):
            self.execute([READY + DONE], invalid_frame=True)
        self.process.kill.assert_called_once()
        self.client.close.assert_called_once()

    def test_nonzero_quit_is_rejected(self):
        with self.assertRaisesRegex(boot.QualificationError, "exit code 7"):
            self.execute([READY + DONE], quit_code=7)
        self.process.kill.assert_not_called()
        self.client.close.assert_called_once()

    def test_early_qemu_exit_is_rejected_without_capture(self):
        with self.assertRaisesRegex(boot.QualificationError, "exited before"):
            self.execute([READY], exited=True)
        self.assertNotIn("screendump", [name for name, _ in self.calls])
        self.process.kill.assert_not_called()
        self.client.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
