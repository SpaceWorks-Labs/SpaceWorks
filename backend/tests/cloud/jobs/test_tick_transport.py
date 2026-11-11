from unittest.mock import Mock

import pytest
from rest_framework.test import APIRequestFactory

from apps.operations.cloud_jobs import tick_views
from apps.operations.cloud_jobs.tick_policy import TickRateExceeded


@pytest.fixture
def endpoint(settings, monkeypatch):
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "free"
    settings.FREE_TICK_SECRET = "correct-secret"
    rate = Mock()
    monkeypatch.setattr(tick_views, "consume_rate", rate)
    run = Mock(return_value=({"run_id": "00000000-0000-0000-0000-000000000001"}, 200))
    monkeypatch.setattr(tick_views, "run_tick", run)
    return tick_views.FreeTickView.as_view(), rate, run


def request(endpoint, method="post", secure=True, **headers):
    factory = APIRequestFactory()
    # .post(data=None) renders an empty multipart form, which is still a body.
    return endpoint[0](factory.generic(method.upper(), "/api/v1/internal/free/tick", data=b"", secure=secure, **headers))


@pytest.mark.parametrize("profile", ["full", "host", ""])
def test_defensive_full_404_even_with_secret(endpoint, settings, profile):
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = profile
    assert request(endpoint, HTTP_X_CRON_SECRET="correct-secret").status_code == 404
    endpoint[1].assert_not_called()
    endpoint[2].assert_not_called()


def test_unset_secret_404_before_database(endpoint, settings):
    settings.FREE_TICK_SECRET = ""
    assert request(endpoint).status_code == 404
    endpoint[1].assert_not_called()


@pytest.mark.parametrize("secret", ["", "wrong", "non-ascii-\u2603"])
def test_bad_secret_is_generic_403_and_never_runs(endpoint, secret):
    response = request(endpoint, HTTP_X_CRON_SECRET=secret)
    assert response.status_code == 403
    assert response.data == {"code": "forbidden"}
    endpoint[2].assert_not_called()


@pytest.mark.parametrize("headers,secure", [
    ({}, False), ({"HTTP_ORIGIN": "https://app.example"}, True),
    ({"HTTP_SEC_FETCH_SITE": "same-origin"}, True),
    ({"HTTP_AUTHORIZATION": "Bearer ordinary-client"}, True),
])
def test_browser_and_plain_http_requests_are_denied(endpoint, headers, secure):
    assert request(endpoint, secure=secure, HTTP_X_CRON_SECRET="correct-secret", **headers).status_code == 403
    endpoint[2].assert_not_called()


@pytest.mark.parametrize("method", ["get", "put", "delete", "options", "head"])
def test_non_post_405_when_mounted(endpoint, method):
    assert request(endpoint, method=method).status_code == 405
    endpoint[2].assert_not_called()


def test_atomic_rate_failure_never_allows_work(endpoint):
    endpoint[1].side_effect = RuntimeError("postgres://secret")
    response = request(endpoint, HTTP_X_CRON_SECRET="correct-secret")
    assert response.status_code == 503
    assert "secret" not in str(response.data)
    endpoint[2].assert_not_called()


def test_rate_limit_has_retry_after(endpoint):
    endpoint[1].side_effect = TickRateExceeded(42)
    response = request(endpoint, HTTP_X_CRON_SECRET="correct-secret")
    assert response.status_code == 429
    assert response["Retry-After"] == "42"
    endpoint[2].assert_not_called()


def test_valid_https_request_runs_and_is_not_cached(endpoint):
    response = request(endpoint, HTTP_X_CRON_SECRET="correct-secret")
    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store"
    assert endpoint[1].call_count == 2
    endpoint[2].assert_called_once()


@pytest.mark.parametrize("body", [b"{}", b"  { }\n", b" " * 1022 + b"{}"])
def test_shipped_scheduler_empty_json_runs(endpoint, body):
    # Worker tick.mjs, cron-job.org.json, tick.py, Actions and Cloud Run send {}.
    response = endpoint[0](APIRequestFactory().generic(
        "POST", "/api/v1/internal/free/tick", data=body,
        content_type="application/json", secure=True, HTTP_X_CRON_SECRET="correct-secret",
    ))
    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store"
    assert endpoint[1].call_count == 2
    endpoint[2].assert_called_once()


@pytest.mark.parametrize("body,content_type,extra", [
    (b'{"task":"arbitrary"}', "application/json", {}),
    (b"[]", "application/json", {}), (b"null", "application/json", {}),
    (b"false", "application/json", {}), (b"0", "application/json", {}),
    (b"{", "application/json", {}), (b"\xff", "application/json", {}),
    (b"{}", "text/plain", {}), (b"{}", "application/x-www-form-urlencoded", {}),
    (b" " * 1023 + b"{}", "application/json", {}),
    (b"{}", "application/json", {"CONTENT_LENGTH": "-1"}),
    (b"{}", "application/json", {"CONTENT_LENGTH": "invalid"}),
    (b"{}", "application/json", {"CONTENT_LENGTH": "+2"}),
    (b"{}", "application/json", {"CONTENT_LENGTH": " 2"}),
    (b"{}", "application/json", {"CONTENT_LENGTH": "02"}),
    (b"{}", "application/json", {"HTTP_TRANSFER_ENCODING": "chunked"}),
    (b"{}", "application/json", {"HTTP_ORIGIN": "https://app.example"}),
    (b"{}", "application/json", {"HTTP_SEC_FETCH_SITE": "same-origin"}),
    (b"{}", "application/json", {"HTTP_AUTHORIZATION": "Bearer ordinary-client"}),
])
def test_nonempty_invalid_or_browser_json_remains_forbidden(endpoint, body, content_type, extra):
    response = endpoint[0](APIRequestFactory().generic(
        "POST", "/api/v1/internal/free/tick", data=body, content_type=content_type,
        secure=True, HTTP_X_CRON_SECRET="correct-secret", **extra,
    ))
    assert response.status_code == 403
    assert response.data == {"code": "forbidden"}
    endpoint[2].assert_not_called()


@pytest.mark.parametrize("url,data", [
    ("/api/v1/internal/free/tick?task=arbitrary", None),
    ("/api/v1/internal/free/tick", {"task": "arbitrary"}),
])
def test_caller_cannot_select_a_command_in_query_or_body(endpoint, url, data):
    response = endpoint[0](APIRequestFactory().post(
        url, data=data, secure=True, HTTP_X_CRON_SECRET="correct-secret",
    ))
    assert response.status_code == 403
    endpoint[2].assert_not_called()
