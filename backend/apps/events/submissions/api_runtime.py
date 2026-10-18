"""Explicit G installation seam; importing this package enables no route/gate."""
from dataclasses import dataclass
from .errors import SubmissionError


@dataclass(frozen=True)
class SubmissionRuntime:
    storage: object
    asset_reader: object
    participant_reader: object
    storage_reader: object
    scan_options: dict
    sandbox_command: tuple[str, ...]
    admin_read_purpose: object
    public_asset_resolver: object
    saved_resume_provider: object


_runtime = None


def install_runtime(value: SubmissionRuntime):
    global _runtime
    if _runtime is not None and _runtime is not value:
        raise RuntimeError("Submission runtime already installed")
    _runtime = value


def runtime():
    if _runtime is None:
        raise SubmissionError("programme_adapter_unavailable", 503)
    return _runtime
