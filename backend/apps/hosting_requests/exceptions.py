from rest_framework.exceptions import APIException


class HostingRequestConflict(APIException):
    """A state-machine refusal: the row is not in a state that allows this change.

    Field problems are DRF ``ValidationError`` (400) and unknown tokens are ``Http404``;
    only a disallowed transition is a 409, so a client can tell "fix your input" from
    "refresh, someone else already moved this request".
    """

    status_code = 409
    default_detail = "This hosting request cannot make that change in its current state."
    default_code = "invalid_transition"

    def __init__(self, detail=None, code=None):
        super().__init__(
            {"detail": detail or self.default_detail, "code": code or self.default_code}
        )
