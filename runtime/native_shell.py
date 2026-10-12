"""Independent host challenge scripts for the first native PooleShell, not an ISO."""
from __future__ import annotations
from dataclasses import dataclass
import re
from runtime.native_console import split_output

BANNER = b"PooleOS native shell\r\nPooleOS> "
PROMPT = b"PooleOS> "

@dataclass(frozen=True)
class Scenario:
    name: str
    nonce: str
    steps: tuple[tuple[bytes, bytes], ...]

    @property
    def sent(self):
        return b"".join(a for a, _ in self.steps)

    @property
    def expected(self):
        return BANNER + b"".join(b for _, b in self.steps)

def scenario(name: str, nonce: str) -> Scenario:
    if name not in ("commands", "editing") or re.fullmatch(r"[0-9a-f]{16}", nonce) is None:
        raise ValueError("unknown shell scenario or invalid independent challenge")
    steps = []
    def typing(text: bytes):
        if any(not 32 <= b <= 126 for b in text): raise ValueError("printable input required")
        steps.extend((bytes([b]), bytes([b])) for b in text)
    def enter(result: bytes, prompt=True):
        steps.append((b"\r", b"\r\n" + result + (PROMPT if prompt else b"")))
    def command(line: bytes, result: bytes):
        typing(line); enter(result)
    challenge = nonce.encode("ascii")
    if name == "commands":
        command(b"help", b"help  version  echo TEXT  exit\r\n")
        command(b"version", b"PooleOS native development / PooleShell 0.1\r\n")
        command(b"echo " + challenge, challenge + b"\r\n")
        command(b"echo POOLEOS:PANIC untrusted", b"POOLEOS:PANIC untrusted\r\n")
        command(b"exitjunk", b"Unknown command.\r\n")
        typing(b"exit"); steps.append((b"\0", b"\x07")); enter(b"Invalid line.\r\n")
        enter(b"")
        typing(b"exit"); enter(b"Bye.\r\n", prompt=False)
    else:
        typing(b"echx"); steps.append((b"\x08", b"\x08 \x08")); typing(b"o " + challenge + b"X")
        steps.append((b"\x7f", b"\x08 \x08")); enter(challenge + b"\r\n")
        steps.append((b"\n", b""))
        command(b"echo " + b"x" * 59, b"x" * 59 + b"\r\n")
        typing(b"echo " + b"y" * 59); steps.append((b"z", b"\x07"))
        steps.append((b"\x08", b"\x08 \x08")); enter(b"Invalid line.\r\n")
        typing(b"exit"); steps.append((b"\xff", b"\x07")); steps.append((b"\x03", b"^C\r\n" + PROMPT))
        typing(b"echo kept"); steps.append((b"\x04", b"")); enter(b"kept\r\n")
        steps.append((b"\x04", b"Bye.\r\n"))
    return Scenario(name, nonce, tuple(steps))

def validate_interaction(case: Scenario | None, sent: bytes, output: bytes) -> dict:
    if type(sent) is not bytes or type(output) is not bytes:
        raise ValueError("exact shell byte captures required")
    prefix, application = split_output(output)
    if case is None:
        if sent or application: raise ValueError("wrong peer produced shell traffic")
    elif sent != case.sent or application != case.expected:
        raise ValueError("shell input/output differs from independent challenge script")
    return dict(contract_id="PSHELL1", scenario=case.name if case else "bad-peer",
        nonce=case.nonce if case else None, input_bytes=len(sent), output_bytes=len(application),
        launch_prefix_bytes=len(prefix), exact_interaction=True,
        kernel_evidence_from_com2=False, native_execution_requires_guest_binding=True,
        command_shell=case is not None, application_launch=False, bundled_files=False,
        iso_built=False, production_ready=False)
