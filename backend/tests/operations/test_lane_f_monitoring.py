import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory
from rest_framework.test import APIClient

from apps.accounts.models import User

from apps.operations.control_storage import control_storage, storage_summary
from apps.operations.route_metrics import RouteMetricsMiddleware, exposition, route_label
from config.web_analytics import analytics_settings


def test_route_labels_are_templates_even_for_bearers():
    request = RequestFactory().get("/tickets/very-private-token?key=private")
    request.resolver_match = SimpleNamespace(route="tickets/<str:token>")
    assert route_label(request) == "tickets/<str:token>"
    request.resolver_match = None
    assert route_label(request) == "unmatched"


def test_latency_and_error_count_omit_arbitrary_method_and_raw_paths(settings):
    settings.ROUTE_METRICS_ENABLED = True
    settings.PROMETHEUS_MULTIPROC_DIR = ""
    request = RequestFactory().get("/route-metric-secret?token=route-metric-secret")
    request.method = "route-metric-secret"
    request.resolver_match = SimpleNamespace(route="metrics-test/<str:token>")
    result = RouteMetricsMiddleware(lambda _: HttpResponse(status=503))(request)
    assert result.status_code == 503
    rendered = exposition()
    assert 'method="OTHER"' in rendered
    assert 'status="503"' in rendered
    assert 'route="metrics-test/<str:token>"' in rendered
    assert "route-metric-secret" not in rendered
    assert "spaceworks_http_request_duration_seconds_bucket" in rendered


def test_disabled_metrics_do_not_collect(settings, monkeypatch):
    settings.ROUTE_METRICS_ENABLED = False
    def forbidden(*args):
        pytest.fail("disabled metrics must not touch collectors")
    monkeypatch.setattr("apps.operations.route_metrics.route_label", forbidden)
    assert RouteMetricsMiddleware(lambda _: HttpResponse())(RequestFactory().get("/")).status_code == 200


def test_multiprocess_collects_workers_and_retains_dead_worker_counters(settings, tmp_path, monkeypatch):
    settings.PROMETHEUS_MULTIPROC_DIR = str(tmp_path)
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(tmp_path))
    environment = {**os.environ, "PROMETHEUS_MULTIPROC_DIR": str(tmp_path)}
    code = (
        "from prometheus_client import Counter; "
        "c=Counter('spaceworks_test_workers','test',('route',)); "
        "c.labels('events/<int:id>').inc()"
    )
    for _ in range(2):
        subprocess.run([sys.executable, "-c", code], env=environment, check=True, capture_output=True)
    rendered = exposition()
    assert 'spaceworks_test_workers_total{route="events/<int:id>"} 2.0' in rendered


def test_gunicorn_master_retires_only_old_prometheus_process_files(tmp_path, monkeypatch):
    from config.gunicorn_metrics import on_starting
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(tmp_path))
    (tmp_path / "counter_123.db").write_bytes(b"old worker")
    (tmp_path / "histogram_456.db").write_bytes(b"old worker")
    (tmp_path / "operator-note.txt").write_text("keep")
    on_starting(None)
    assert sorted(path.name for path in tmp_path.iterdir()) == ["operator-note.txt"]


@pytest.mark.django_db
def test_protected_metrics_never_advertise_or_release_data_without_token(settings):
    client = APIClient()
    settings.METRICS_TOKEN = ""
    assert client.get("/api/v1/metrics/").status_code == 404
    settings.METRICS_TOKEN = "metrics-secret"
    assert client.get("/api/v1/metrics/").status_code == 401
    assert client.get("/api/v1/metrics/", HTTP_AUTHORIZATION="Bearer incorrect").status_code == 401
    settings.ROUTE_METRICS_ENABLED = True
    response = client.get("/api/v1/metrics/", HTTP_AUTHORIZATION="Bearer metrics-secret")
    assert response.status_code == 200
    assert response["Cache-Control"] == "private, no-store"
    assert b"spaceworks_http_requests" in response.content
    assert b"metrics-secret" not in response.content


@pytest.mark.django_db
def test_storage_uses_existing_totals_and_lists_every_tenant():
    from tests.return_helpers import make_space
    small, large = make_space("storage-small"), make_space("storage-large")
    type(small).objects.filter(pk=small.pk).update(storage_bytes_used=123)
    type(large).objects.filter(pk=large.pk).update(storage_bytes_used=999)
    summary = storage_summary()
    assert summary["database_bytes"] > 0
    assert summary["tables"]
    assert summary["object_bytes"] == 123 + 999
    assert [row["id"] for row in summary["tenants"]] == [large.pk, small.pk]


@pytest.mark.parametrize("overrides", [
    {"is_superuser": False}, {"is_active": False}, {"access_status": "restricted"},
    {"must_change_password": True},
])
def test_storage_refuses_non_superadmin_and_restricted_accounts(overrides):
    request = RequestFactory().get("/control/storage/")
    request.user = SimpleNamespace(**{**dict(is_active=True, is_superuser=True, access_status="active", must_change_password=False), **overrides})
    with pytest.raises(PermissionDenied):
        control_storage(request)


def test_storage_does_not_accept_mutating_http_method():
    assert control_storage(RequestFactory().post("/control/storage/")).status_code == 405


@pytest.mark.django_db
def test_storage_uses_control_mfa_gate_and_success_is_no_store(client, monkeypatch):
    user = User.objects.create_superuser("storage-superadmin", role="superadmin", is_superuser=True, is_staff=True, access_status="active")
    client.force_login(user, backend="apps.accounts.auth_backends.SpaceWorksModelBackend")
    monkeypatch.setattr("apps.accounts.control_mfa.session_verified", lambda request: False)
    assert client.get("/control/storage/")["Location"] == "/mfa/control/"
    monkeypatch.setattr("apps.accounts.control_mfa.session_verified", lambda request: True)
    response = client.get("/control/storage/")
    assert response.status_code == 200
    assert "no-store" in response["Cache-Control"]
    assert b"Deployment storage" in response.content


@pytest.mark.parametrize("values", [
    {"WEB_ANALYTICS_SCRIPT_URL": "https://analytics.example/script.manual.js"},
    {"WEB_ANALYTICS_SCRIPT_URL": "https://analytics.example/script.js", "WEB_ANALYTICS_COLLECT_URL": "https://analytics.example/api/event", "WEB_ANALYTICS_DOMAIN": "space.example"},
    {"WEB_ANALYTICS_SCRIPT_URL": "https://user:secret@analytics.example/script.manual.js", "WEB_ANALYTICS_COLLECT_URL": "https://analytics.example/api/event", "WEB_ANALYTICS_DOMAIN": "space.example"},
])
def test_analytics_settings_refuse_partial_automatic_or_credential_urls(values):
    with pytest.raises(ImproperlyConfigured):
        analytics_settings(lambda key, default="": values.get(key, default), {"DIRECTIVES": {"script-src": ["'self'"]}})


def test_analytics_settings_extend_only_configured_origins():
    policy = {"DIRECTIVES": {"script-src": ["'self'"]}}
    assert analytics_settings(lambda key, default="": default, policy) == ("", "", "")
    assert policy == {"DIRECTIVES": {"script-src": ["'self'"]}}
    values = dict(WEB_ANALYTICS_SCRIPT_URL="https://scripts.example/script.manual.js", WEB_ANALYTICS_COLLECT_URL="https://collect.example/api/event", WEB_ANALYTICS_DOMAIN="space.example")
    analytics_settings(lambda key, default="": values.get(key, default), policy)
    assert policy["DIRECTIVES"]["script-src"] == ["'self'", "https://scripts.example"]
    assert policy["DIRECTIVES"]["connect-src"] == ["'self'", "https://collect.example"]


def test_early_signature_refusal_still_uses_compiled_route_template():
    request = RequestFactory().get("/api/v1/events/123456789/?cursor=PRIVATE")
    assert getattr(request, "resolver_match", None) is None
    assert route_label(request) == "api/v1/events/<int:pk>/"
    assert "123456789" not in route_label(request)
    assert "PRIVATE" not in route_label(request)


def test_metric_storage_failure_preserves_the_original_response(settings, monkeypatch):
    settings.ROUTE_METRICS_ENABLED = True
    def unavailable(*args):
        raise OSError("metrics directory unavailable")
    monkeypatch.setattr("apps.operations.route_metrics.REQUESTS.labels", unavailable)
    response = RouteMetricsMiddleware(lambda request: HttpResponse(status=401))(
        RequestFactory().get("/api/v1/events/"))
    assert response.status_code == 401
