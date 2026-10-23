"""Read-only build preflight; preserve working space without deleting evidence."""
from pathlib import Path
import shutil

# Recent optical qualification runs can write more than the former 512 MiB
# floor. Budget a typical run separately from space needed for other work.
# This is admission control, not a filesystem quota or a space reservation.
WORKING_SPACE_RESERVE = 10 * 1024 * 1024 * 1024
BUILD_HEADROOM = 2 * 1024 * 1024 * 1024
USER_BUILD_MINIMUM = WORKING_SPACE_RESERVE + BUILD_HEADROOM


def require_space(destination: Path, minimum_bytes: int = USER_BUILD_MINIMUM) -> dict:
    if type(minimum_bytes) is not int or minimum_bytes <= 0:
        raise ValueError("positive integer storage floor required")
    ancestor = destination.resolve()
    while not ancestor.exists():
        parent = ancestor.parent
        if parent == ancestor:
            raise ValueError("no existing destination ancestor")
        ancestor = parent
    if not ancestor.is_dir():
        ancestor = ancestor.parent
    free = shutil.disk_usage(ancestor).free
    if free < minimum_bytes:
        raise ValueError(f"insufficient build storage: available={free} required={minimum_bytes}; "
                         "stop new builds and preserve evidence before retry")
    return {"minimum_bytes": minimum_bytes, "available_bytes": free,
        "checked_before_output_creation": True, "space_reserved": False,
        "retention_performed": False}


def main(argv=None) -> int:
    """Provide the same preflight for older/manual build commands."""
    import argparse
    import json
    import sys
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", nargs="?", type=Path,
                        default=Path(__file__).resolve().parents[1] / "outputs")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(require_space(args.destination), indent=2))
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
