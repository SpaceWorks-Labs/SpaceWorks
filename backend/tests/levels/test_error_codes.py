"""Contract level: every error body carries `code` (decision 481(2)).

The shared `HardwareRequestError` component marks `code` required, so a generated (Android/iOS) client
cannot decode an error that has only `detail`. Errors DRF raises itself now carry DRF's own code;
`detail` and field-keyed validation bodies are unchanged.
"""
import pytest
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions
from rest_framework.test import APIClient

from apps.hardware_requests.exceptions import workflow_exception_handler

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("exc,status,code", [
    (exceptions.NotAuthenticated(), 401, "not_authenticated"),
    (exceptions.AuthenticationFailed(), 401, "authentication_failed"),
    (exceptions.PermissionDenied(), 403, "permission_denied"),
    (exceptions.PermissionDenied("Only staff.", code="staff_only"), 403, "staff_only"),
    (exceptions.NotFound(), 404, "not_found"),
    (Http404("No Makerspace matches the given query."), 404, "not_found"),
    (DjangoPermissionDenied(), 403, "permission_denied"),
    (exceptions.MethodNotAllowed("PUT"), 405, "method_not_allowed"),
    (exceptions.NotAcceptable(), 406, "not_acceptable"),
    (exceptions.UnsupportedMediaType("text/plain"), 415, "unsupported_media_type"),
    (exceptions.Throttled(wait=7), 429, "throttled"),
    (exceptions.ParseError(), 400, "parse_error"),
    (exceptions.ValidationError({"detail": "Invalid or expired verification code."}), 400, "invalid"),
])
def test_a_framework_error_carries_drf_s_own_code(exc, status, code):
    response = workflow_exception_handler(exc, {"view": None, "request": None})
    assert response.status_code == status
    assert response.data["code"] == code
    assert response.data["detail"]


def test_an_explicit_code_and_a_field_keyed_body_are_left_alone():
    typed = workflow_exception_handler(
        exceptions.PermissionDenied({"detail": "Verify the account email.", "code": "email_verification_required"}),
        {"view": None, "request": None})
    assert typed.data == {"detail": "Verify the account email.", "code": "email_verification_required"}
    fields = workflow_exception_handler(exceptions.ValidationError({"name": ["This field is required."]}),
                                        {"view": None, "request": None})
    assert fields.data == {"name": ["This field is required."]}


def test_real_framework_refusals_carry_their_code():
    anonymous = APIClient().get("/api/v1/auth/me")
    assert anonymous.status_code == 401
    assert anonymous.json()["code"] == "not_authenticated"
    assert anonymous.json()["detail"]
