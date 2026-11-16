"""G supplies the existing shared scan policy, including an explicit disabled mode.

No finance-specific scanner switch or removable Events import is introduced.
The installed reader is query-free and performs no network I/O.
"""
from dataclasses import dataclass, field
from .attachment_content import ContentError


@dataclass(frozen=True)
class ScannerPolicy:
    backend: str
    host: str | None = field(default=None, repr=False)
    port: int = 3310

    def __post_init__(self):
        if (self.backend not in ("none", "clamav") or type(self.port) is not int or not 1 <= self.port <= 65535
                or self.backend == "clamav" and (not isinstance(self.host, str) or not self.host)):
            raise ContentError("scanner_unavailable", 503)


_provider = None


def install(provider):
    global _provider
    if _provider is not None and _provider is not provider:
        raise RuntimeError("Shared finance scan policy already installed.")
    _provider = provider


def current():
    if _provider is None:
        raise ContentError("scanner_unavailable", 503)
    value = _provider()
    if not isinstance(value, ScannerPolicy):
        raise ContentError("scanner_unavailable", 503)
    return value
