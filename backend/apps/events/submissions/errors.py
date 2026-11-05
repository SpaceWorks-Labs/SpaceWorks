from rest_framework.exceptions import APIException


class SubmissionError(APIException):
    """A typed submission error. Extra keyword values (e.g. the missing link ``kinds``) join the body."""

    def __init__(self, code, status=400, **extra):
        self.code = code
        self.status_code = status
        self.status = status
        self.extra = extra
        super().__init__({"code": code, "detail": code.replace("_", " "), **extra}, code=code)
