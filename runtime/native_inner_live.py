"""Independent oracle for the PooleBoot retained inner-artifact parse boundary."""

from __future__ import annotations

import hashlib
import struct
from collections.abc import Sequence
from typing import Any, Final

from runtime import (
    native_boot_artifact as pbart1,
    native_firmware as pfwm1,
    native_initial_system as pinit1,
    native_microcode as pmcu1,
    native_policy as ppol1,
    native_recovery as prec1,
    native_symbols as psym1,
)


PROOF_ID: Final = "N5-INNER-LIVE-PARSE-001"
ARTIFACT_COUNT: Final = 6
PARSER_COUNT: Final = 6
CROSS_BINDING_COUNT: Final = 6
DEVELOPMENT_DENIAL_COUNT: Final = 6
SET_DOMAIN: Final = b"POOLEOS/INNER-LIVE-SET/V1\0"
EXPECTED_DENIALS: Final = (
    "pinit_activation_outer_signature_verified",
    "prec_activation_outer_signature",
    "psym_activation_outer_signature",
    "pmcu_activation_outer_signature",
    "pfwm_activation_outer_signature",
    "ppol_activation_outer_signature",
)


class InnerLiveError(RuntimeError):
    """Raised when retained bytes violate the bounded live-parse proof."""


def retained_set_sha256(files: Sequence[bytes]) -> str:
    if len(files) != ARTIFACT_COUNT:
        raise InnerLiveError("inner artifact count changed")
    digest = hashlib.sha256()
    digest.update(SET_DOMAIN)
    for role, data in zip(pbart1.ROLES, files, strict=True):
        digest.update(struct.pack("<IQ", role, len(data)))
        digest.update(data)
    return digest.hexdigest().upper()


def _first_denial(errors: Sequence[str], expected: str, role: str) -> str:
    if not errors or errors[0] != expected:
        raise InnerLiveError(f"{role} development denial ordering changed")
    return errors[0]


def validate_development_set(files: Sequence[bytes]) -> dict[str, Any]:
    if len(files) != ARTIFACT_COUNT:
        raise InnerLiveError("inner artifact count changed")
    artifacts = [
        pbart1.parse_bound(data, role, 1)
        for role, data in zip(pbart1.ROLES, files, strict=True)
    ]
    initial = pinit1.parse(artifacts[0].payload)
    recovery = prec1.parse(artifacts[1].payload)
    symbols = psym1.parse(artifacts[2].payload)
    microcode = pmcu1.parse(artifacts[3].payload)
    firmware = pfwm1.parse(artifacts[4].payload)
    policy = ppol1.parse(artifacts[5].payload)

    expected_payload_digests = (
        policy.initial_system_sha256,
        policy.recovery_sha256,
        policy.symbols_sha256,
        policy.microcode_sha256,
        policy.firmware_sha256,
    )
    observed_payload_digests = tuple(
        hashlib.sha256(artifact.payload).hexdigest().upper()
        for artifact in artifacts[:5]
    )
    if observed_payload_digests != expected_payload_digests:
        raise InnerLiveError("PPOL1 retained payload identity changed")
    ppol1.validate_initial_system(policy, initial)

    denials = (
        _first_denial(
            pinit1.activation_errors(initial, pinit1.development_activation_context()),
            EXPECTED_DENIALS[0],
            "initial_system",
        ),
        _first_denial(
            prec1.activation_errors(recovery, prec1.development_activation_context()),
            EXPECTED_DENIALS[1],
            "recovery",
        ),
        _first_denial(
            psym1.consumption_errors(
                symbols, psym1.development_consumption_context(symbols)
            ),
            EXPECTED_DENIALS[2],
            "symbols",
        ),
        _first_denial(
            pmcu1.apply_plan_errors(
                microcode,
                pmcu1.development_apply_context(
                    microcode, outer_file_sha256=artifacts[3].file_sha256
                ),
            ),
            EXPECTED_DENIALS[3],
            "microcode",
        ),
        _first_denial(
            pfwm1.activation_errors(
                firmware,
                pfwm1.development_activation_context(
                    firmware, outer_file_sha256=artifacts[4].file_sha256
                ),
            ),
            EXPECTED_DENIALS[4],
            "firmware",
        ),
        _first_denial(
            ppol1.activation_errors(
                policy,
                ppol1.development_activation_context(
                    policy, outer_file_sha256=artifacts[5].file_sha256
                ),
            ),
            EXPECTED_DENIALS[5],
            "policy",
        ),
    )
    return {
        "proof_id": PROOF_ID,
        "artifact_count": ARTIFACT_COUNT,
        "parser_count": PARSER_COUNT,
        "cross_binding_count": CROSS_BINDING_COUNT,
        "development_denial_count": DEVELOPMENT_DENIAL_COUNT,
        "file_bytes": sum(len(data) for data in files),
        "payload_bytes": sum(len(artifact.payload) for artifact in artifacts),
        "retained_set_sha256": retained_set_sha256(files),
        "exact_retained_bytes": True,
        "policy_payload_digests_bound": True,
        "initial_routes_cross_bound": True,
        "development_denials": list(denials),
        "authority_grants": 0,
        "actions_authorized": 0,
        "state_writes": 0,
        "hardware_observations": 0,
    }
