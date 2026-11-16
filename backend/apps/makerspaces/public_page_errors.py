"""Stable conflict codes shared by page mutation services and OpenAPI."""

from rest_framework.exceptions import APIException


class PageConflict(APIException):
    status_code = 409

    def __init__(self, code, message):
        super().__init__({"code": code, "detail": message}, code=code)


class PagePayloadTooLarge(APIException):
    status_code = 413
    default_detail = "Page content or image exceeds the permitted size."
    default_code = "payload_too_large"
