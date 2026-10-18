from rest_framework.exceptions import APIException


class SubmissionError(APIException):
    def __init__(self, code, status=400):
        self.status_code = status
        self.status = status
        super().__init__({"code": code, "detail": code.replace("_", " ")}, code=code)
