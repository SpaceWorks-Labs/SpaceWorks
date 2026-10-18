from rest_framework.exceptions import APIException


class ProgrammeError(APIException):
    def __init__(self, code, detail, *, status=409, current_version=None, **extra):
        self.status_code = status
        payload = {"code": code, "detail": detail, "fields": {}, **extra}
        if current_version is not None:
            payload["current_version"] = current_version
        super().__init__(payload)
        # DRF's default coercion turns integer versions/conflict IDs into text.
        # Keep the frozen wire types while retaining APIException handling.
        self.detail = payload


def check_version(row, expected):
    if row.version != expected:
        raise ProgrammeError("stale_version", "This item changed.", current_version=row.version)


def require_state(row, *states):
    if row.state not in states:
        raise ProgrammeError("invalid_transition", "This action is unavailable in the current state.")
