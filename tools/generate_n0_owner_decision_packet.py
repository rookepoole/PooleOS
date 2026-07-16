#!/usr/bin/env python3
"""Generate the deterministic PooleOS N0 owner decision packet and review document."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import n0_owner_decision_packet as owner_packet  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-json", type=Path, default=ROOT / owner_packet.PACKET_RELATIVE)
    parser.add_argument("--out-markdown", type=Path, default=ROOT / owner_packet.PACKET_DOCUMENT_RELATIVE)
    args = parser.parse_args(argv)

    try:
        packet = owner_packet.build_packet(ROOT)
        owner_packet.write_packet(packet, args.out_json, args.out_markdown)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"FAIL {type(error).__name__}: {error}")
        return 1

    validation = packet["validation"]
    print(
        f"wrote {args.out_json} and {args.out_markdown}: "
        f"sources={packet['source_set']['binding_count']} "
        f"targets={packet['current_state']['objective_target_count']} "
        f"owner_actions={packet['current_state']['pending_owner_action_count']} "
        f"negatives={validation['negative_control_pass_count']}/{validation['negative_control_count']} "
        "acceptance=false signing=false publication=false promotion=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
