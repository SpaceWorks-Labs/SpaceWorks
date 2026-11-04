"""Typed integration refusals; the code names the reason, never a submitted payload."""
from rest_framework.exceptions import APIException


class IntegrationConflict(APIException):
    """409 with a stable code: job_unknown, job_conflict, job_not_started, job_not_reported_started."""

    status_code = 409
    default_detail = "The job report conflicts with the job's state."
    default_code = "integration_conflict"

    def __init__(self, detail=None, code=None):
        super().__init__({"detail": detail or self.default_detail, "code": code or self.default_code}, code)
        self.default_code = code or self.default_code
