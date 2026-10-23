"""Explicit diagnostic-only UART recovery evidence; ordinary oracles stay strict."""
from __future__ import annotations

import re
from runtime import native_app_session as apps

PREFIX = 'POOLEOS:APPS SERIAL '
PATTERN = re.compile(
    PREFIX + r'contract=PAPPSESSION1 dispatches=64 withheld=4096 timeouts=1 '
    r'pending=0 rejected=0 transmitted=([0-9]+) cpl=3 production=0'
)


def separate(markers: list[str]) -> tuple[list[str], dict]:
    positions = [i for i, marker in enumerate(markers) if marker.startswith(PREFIX)]
    if len(positions) != 1:
        raise ValueError('exactly one explicit serial challenge required')
    i = positions[0]
    match = PATTERN.fullmatch(markers[i])
    if match is None or i == 0:
        raise ValueError('malformed or failed serial recovery')
    prior = apps.parse(markers[i-1], 'RUN')
    transmitted = int(match[1])
    if prior['dispatches'] != 64 or transmitted != len(markers[i-1].encode('ascii')) + 2:
        raise ValueError('serial challenge did not deliver the exact preceding CRLF record')
    return markers[:i] + markers[i+1:], dict(
        dispatches=64, withheld_status_reads=4096, bounded_timeouts=1,
        pending=0, rejected=0, transmitted=transmitted, diagnostic_only=True,
        historical_failure_cause_proven=False,
    )


def validate_markers(markers: list[str], **profile) -> dict:
    ordinary, evidence = separate(markers)
    result = apps.validate_markers(ordinary, **profile)
    result['serial_recovery'] = evidence
    return result


def negative_controls(markers: list[str]) -> int:
    i = next(i for i, marker in enumerate(markers) if marker.startswith(PREFIX))
    variants = [markers[:i]+markers[i+1:], markers[:i]+[markers[i]]+markers[i:]]
    for old, new in [('withheld=4096','withheld=4095'), ('timeouts=1','timeouts=0'),
                     ('pending=0','pending=1'), ('rejected=0','rejected=1'),
                     ('dispatches=64','dispatches=128'), ('production=0','production=1')]:
        changed = list(markers)
        changed[i] = changed[i].replace(old, new)
        variants.append(changed)
    changed = list(markers)
    changed[i] = re.sub(r'transmitted=[0-9]+', 'transmitted=1', changed[i])
    variants.append(changed)
    changed = list(markers)
    changed[i-1], changed[i] = changed[i], changed[i-1]
    variants.append(changed)
    for variant in variants:
        try:
            separate(variant)
        except ValueError:
            continue
        raise ValueError('serial challenge negative control accepted')
    return len(variants)
