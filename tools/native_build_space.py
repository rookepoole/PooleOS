"""Read-only free-space preflight; retention/deletion is never implicit."""
from pathlib import Path
import shutil

USER_BUILD_MINIMUM = 512 * 1024 * 1024


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
        raise ValueError(f"insufficient build storage: available={free} required={minimum_bytes}; preserve evidence before retry")
    return {"minimum_bytes": minimum_bytes, "available_bytes": free,
        "checked_before_output_creation": True, "space_reserved": False,
        "retention_performed": False}
