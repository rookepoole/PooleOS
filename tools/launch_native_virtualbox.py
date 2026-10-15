"""Use the verified native ISO in a disposable VirtualBox serial-terminal session."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import secrets
import signal
import socket
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime import native_virtualbox as vbox, native_app_session as apps
from runtime import native_console as console, native_session as session, native_live_boot_handoff as handoff
from tools import qualify_native_app_session as qualification, qualify_native_user_entry as source
from tools.launch_native_userspace_iso import check_preview, local_file, Terminal, manual_summary, LOG_LIMIT


def installed_virtualbox() -> Path:
    if sys.platform != 'win32':
        raise ValueError('this preview profile requires Windows VirtualBox7.2.20')
    import winreg
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Oracle\VirtualBox',
                       access=winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
        directory, kind = winreg.QueryValueEx(key, 'InstallDir')
    if kind != winreg.REG_SZ or not isinstance(directory, str):
        raise ValueError('VirtualBox installation directory is not a string')
    return Path(directory) / 'VBoxManage.exe'


def listener_socket():
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        listener.setblocking(False)
        return listener
    except BaseException:
        listener.close()
        raise


def run_session(receipt: Path, work: Path, executable: Path, interaction, self_test: bool):
    report, iso, disk = check_preview(receipt)
    profile = json.loads((ROOT / 'specs/native-virtualbox-preview-profile.json').read_bytes())
    tool_hashes = vbox.verify_runtime(executable, profile)
    work = work.resolve()
    if not work.is_relative_to((ROOT / 'outputs').resolve()) or work == (ROOT / 'outputs').resolve():
        raise ValueError('new workspace output session directory required')
    work.mkdir(parents=True, exist_ok=False)
    command = vbox.Command(executable.resolve(strict=True))
    owner = vbox.OwnedVm(work, command)
    before = source.source_bindings()
    if before != report['source_bindings']:
        raise ValueError('source changed after preview admission')
    result = dict(contract_id=vbox.CONTRACT, status='fail', self_test=self_test,
        scope='strict_serial_application_self_test' if self_test else 'manual_serial_session_not_qualification',
        production_ready=False, native_gui=False, source_bindings=before, tool_hashes=tool_hashes,
        runtime_origin=profile['origin'], runtime_scope=profile['scope'],
        guest_bound_seconds=240 if self_test else 900, command_bound_seconds=vbox.COMMAND_SECONDS,
        iso_sha256=report['optical_images']['applications-1']['iso_sha256'],
        vm_uuid=owner.identity, vm_name=owner.name, no_guest_network=True,
        no_host_shares=True, no_guest_disk=True, no_physical_media=True)
    listener = None
    log = b''
    code = 1
    try:
        result['virtualbox_version'] = owner.checked('--version').strip()
        if result['virtualbox_version'] != profile['version']:
            raise ValueError('VirtualBox version differs; requalification required')
        listener = listener_socket()
        port = listener.getsockname()[1]
        owner.create(iso, port)
        result['effective_configuration_verified'] = True
        owner.start()
        started = time.monotonic()
        result['stop_reason'] = 'guest_deadline'
        while time.monotonic() - started < result['guest_bound_seconds']:
            if interaction.sock is None:
                try:
                    connection, address = listener.accept()
                except BlockingIOError:
                    pass
                else:
                    if address[0] != '127.0.0.1':
                        connection.close()
                        raise ValueError('serial peer is not loopback')
                    connection.setblocking(False)
                    interaction.sock = connection
            com1 = work / 'com1.log'
            raw = vbox.bounded_read(com1, LOG_LIMIT) if com1.exists() else b''
            log = vbox.serial_payload(raw, partial=True)
            if b'POOLEBOOT/0.1 ERROR ' in log or re.search(rb'POOLEOS:[^\r\n]*(?: FAIL |ERROR|PANIC:|DENIED stage=)', log):
                raise ValueError('native boot or kernel failure observed')
            if interaction.sock is not None and interaction.poll(log):
                owner.pause()
                log = vbox.serial_payload(vbox.bounded_read(com1, LOG_LIMIT))
                markers = session.extract_markers(log)
                result['markers'] = markers
                if self_test:
                    summary = apps.validate_markers(markers, file_waits=report.get('file_waits', False))
                    case = interaction.case
                    _, output = console.split_output(bytes(interaction.received))
                    if (interaction.payload[:interaction.sent] != case.sent or output != case.expected
                            or not interaction.sustained_evidence):
                        raise ValueError('inexact native application interaction')
                    prefix = summary['transfer_prefix']
                    # Bind actual boot transcript fields to the inspected optical payload.
                    transcript = handoff.extract_transcript(log).summary
                    qualification.shared.load.validate_oracle_binding(prefix['boot_prefix'],
                        qualification.shared.load.inspect_media_bytes(disk), transcript)
                    result.update(marker_summary=summary,
                        pbp1_transcript=transcript,
                        transcript_binding=qualification.shared.transfer.validate_transcript_binding(prefix, transcript),
                        hostile_marker_cases_rejected=apps.negative_controls(markers, file_waits=report.get('file_waits', False)),
                        sustained_window=interaction.sustained_evidence,
                        interaction=dict(nonce=case.nonce, input_hex=case.sent.hex(),
                            output_hex=bytes(interaction.received).hex(), exact=True))
                else:
                    result['marker_summary'] = manual_summary(markers)
                result.update(status='pass', stop_reason='exact_application_session' if self_test else 'terminal_session_stopped')
                code = 0
                break
            time.sleep(0.01)
        result['observation_seconds'] = round(time.monotonic() - started, 3)
        if result['status'] != 'pass':
            raise TimeoutError('native session did not finish within its bound')
    except KeyboardInterrupt:
        result.update(status='cancelled', stop_reason='host_interrupt')
        code = 130
    except Exception as error:
        result['status'], code = 'fail', 1
        result['failure'] = f'{type(error).__name__}: {error}'
        print('VirtualBox preview failed: ' + result['failure'], file=sys.stderr)
    finally:
        # A second Ctrl+C must not abandon the owned VM halfway through shutdown.
        handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            for resource in (interaction, listener):
                if resource is not None:
                    try:
                        resource.close()
                    except Exception as error:
                        result.setdefault('close_errors', []).append(type(error).__name__)
                        result['status'], code = 'fail', 1
            result['cleanup'] = owner.cleanup()
            if not all(result['cleanup'][key] for key in ('stopped', 'unregistered', 'prior_registrations_unchanged')):
                result['status'], code = 'fail', 1
                print('VM cleanup unconfirmed; retained identity and logs: ' + str(work), file=sys.stderr)
            result['source_unchanged'] = before == source.source_bindings()
            try:
                result['runtime_unchanged'] = tool_hashes == vbox.verify_runtime(executable, profile)
                result['iso_unchanged'] = hashlib.sha256(local_file(iso, 128 * 1024 * 1024)).hexdigest().upper() == result['iso_sha256']
            except (OSError, ValueError) as error:
                result['identity_failure'] = str(error)
                result['runtime_unchanged'] = result['iso_unchanged'] = False
            if not all(result[key] for key in ('source_unchanged', 'runtime_unchanged', 'iso_unchanged')):
                result['status'], code = 'fail', 1
            (work / 'console-input.bin').write_bytes(interaction.payload[:interaction.sent])
            (work / 'console-output.bin').write_bytes(bytes(interaction.received))
            result['commands'] = command.records
            (work / 'receipt.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')
        finally:
            signal.signal(signal.SIGINT, handler)
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', type=Path)
    parser.add_argument('--work-dir', type=Path)
    parser.add_argument('--virtualbox', type=Path)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    interaction = None
    try:
        receipt = args.receipt or ROOT / json.loads(local_file(ROOT / 'outputs/native-userspace-preview.json', 4096))['receipt']
        executable = args.virtualbox or installed_virtualbox()
        work = args.work_dir or ROOT / 'outputs' / ('virtualbox-session-' + str(time.time_ns()))
        if args.self_test:
            interaction = qualification.Interaction(apps.scenario(secrets.token_hex(8)), sustained=True)
        else:
            if sys.platform != 'win32' or not sys.stdin.isatty():
                raise ValueError('interactive Windows terminal required')
            import msvcrt
            print('PooleOS unsigned native preview in VirtualBox. Serial terminal; no desktop.\n'
                  'Ctrl+] closes this VM. Session limit: 15 minutes. No persistent storage.\n', flush=True)
            def emit(text):
                sys.stdout.write(text)
                sys.stdout.flush()
            interaction = Terminal(lambda: msvcrt.getwch() if msvcrt.kbhit() else None, emit)
        return run_session(receipt, work, executable, interaction, args.self_test)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print('Preview refused: ' + str(error), file=sys.stderr)
        return 1
    finally:
        if interaction is not None:
            interaction.close()


if __name__ == '__main__':
    raise SystemExit(main())
