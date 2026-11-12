"""One typed error for everything that can go wrong talking to a provider."""
from .contract import ALL_ERROR_CODES, RETRYABLE


class AdapterError(Exception):
    def __init__(self, code, message="", *, retryable=None):
        if code not in ALL_ERROR_CODES:
            code = "invalid_response"
        super().__init__(code)
        self.code = code
        self.message = (message or "")[:200]
        self.retryable = code in RETRYABLE if retryable is None else bool(retryable)
