from django.utils.translation import gettext
from rest_framework.exceptions import APIException


class SavedDetailsError(APIException):
    def __init__(self, code, detail, status=400, **extra):
        self.status_code = status
        super().__init__({"code": code, "detail": detail, "fields": {}})
        self.detail.update(extra)


def unavailable(code="saved_details_unavailable"):
    return SavedDetailsError(code, gettext("Saved details are temporarily unavailable. Try again."), 503)
