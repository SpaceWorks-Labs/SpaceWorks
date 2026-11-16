from rest_framework.exceptions import APIException


class ProgrammeConflict(APIException):
    status_code = 409
    default_detail = "The event changed. Refresh before trying again."
    default_code = "stale_version"


class CredentialKeyUnavailable(APIException):
    status_code = 503
    default_detail = "Event credentials are temporarily unavailable."
    default_code = "credential_key_unavailable"
