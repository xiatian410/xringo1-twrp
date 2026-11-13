"""Reserve named local evidence outputs before an expensive OTA execution."""
from pathlib import Path
import re


def output_prefix(base, run_name=None):
    if run_name is None:
        return base
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', run_name):
        raise ValueError('run name must be 1–80 ASCII letters, digits, underscores or hyphens')
    return base + '-' + run_name


def reserve_outputs(logs, prefix, suffixes):
    """Refuse old files and competing runs; reservations survive failed runs.

    All runners sharing a prefix must use this reservation. No stale lock is
    removed automatically: failed attempts also deserve preserved evidence.
    """
    logs = Path(logs)
    logs.mkdir(parents=True, exist_ok=True)
    for suffix in suffixes:
        path = logs / (prefix + suffix)
        if path.exists() or path.is_symlink():
            raise FileExistsError(f'Preserve existing evidence: {path}; choose a new --run-name')
    reservation = logs / (prefix + '.reservation')
    try:
        reservation.mkdir()
    except FileExistsError:
        raise FileExistsError(f'Run already reserved: {reservation}; choose a new --run-name') from None
    return prefix
