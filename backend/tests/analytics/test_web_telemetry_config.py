"""Focused candidate tests; execution is separately admitted."""
import copy

import pytest
from django.test import override_settings
from django.urls import reverse

from apps.analytics.models import AnalyticsConnection
from apps.makerspaces.telemetry_defaults import defaults
from apps.makerspaces.telemetry_public import effective_telemetry
from apps.makerspaces.telemetry_schema import TelemetryEnvelopeSerializer
from tests.analytics_l25.helpers import client_for, inventory_manager, manager, space, superadmin

pytestmark = pytest.mark.django_db


def test_diagnostics_default_off_with_useful_rates_and_zero_is_valid():
    config = defaults()
    assert config["diagnostics"]["sentry"]["enabled"] is False
    assert config["diagnostics"]["sentry"]["sample_rate"] == 1.0
    assert config["diagnostics"]["firebase_performance"]["enabled"] is False
    assert config["diagnostics"]["firebase_performance"]["sample_rate"] == 0.1
    config["diagnostics"]["sentry"]["sample_rate"] = 0
    config["diagnostics"]["firebase_performance"]["sample_rate"] = 0
    assert TelemetryEnvelopeSerializer(data={"config": config}).is_valid()


def url(makerspace):
    return reverse("admin-makerspace-telemetry", kwargs={"makerspace_id": makerspace.pk})


def test_module_off_and_foreign_space_are_not_visible():
    disabled = space(analytics=False)
    assert client_for(manager(disabled)).get(url(disabled)).status_code == 404
    first, second = space(), space()
    assert client_for(manager(second)).get(url(first)).status_code == 404
    assert effective_telemetry(disabled) == defaults()


def test_manager_atomic_update_and_safe_public_projection():
    makerspace = space()
    client = client_for(manager(makerspace))
    config = defaults()
    config["pageview"] = {"provider": "ga4", "site_id": "G-ABC123", "endpoint": ""}
    response = client.patch(url(makerspace), {"config": config}, format="json")
    assert response.status_code == 200, response.data
    assert effective_telemetry(makerspace) == config
    bad = copy.deepcopy(config)
    bad["pageview"]["endpoint"] = "https://evil.example/script.js?secret=x"
    assert client.patch(url(makerspace), {"config": bad}, format="json").status_code == 400
    assert effective_telemetry(makerspace) == config
    assert client.get(url(makerspace))["Cache-Control"] == "no-store"


def test_invalid_stored_data_fails_closed_and_platform_is_separate():
    makerspace = space()
    AnalyticsConnection.objects.create(makerspace=makerspace, telemetry_config={"unexpected": "value"})
    assert effective_telemetry(makerspace) == defaults()
    route = reverse("admin-platform-telemetry")
    assert client_for(manager(makerspace)).get(route).status_code == 403
    assert client_for(superadmin()).get(route).data["config"] == defaults()


def test_legacy_only_when_analytics_available_and_never_explicitly_configured():
    from apps.makerspaces.telemetry_public import legacy_allowed
    enabled, disabled = space(), space(analytics=False)
    assert legacy_allowed(enabled) is True
    assert legacy_allowed(disabled) is False
    row = AnalyticsConnection.objects.create(makerspace=enabled, telemetry_config=defaults())
    assert legacy_allowed(enabled) is False
    row.telemetry_config = ["invalid"]
    row.save(update_fields=["telemetry_config"])
    assert legacy_allowed(enabled) is False


def test_viewer_cannot_patch_and_inactive_account_is_refused(monkeypatch):
    from apps.accounts import rbac
    makerspace = space()
    viewer = inventory_manager(makerspace)
    monkeypatch.setattr(rbac, "can", lambda actor, action, makerspace_id=None: action == rbac.Action.VIEW_ANALYTICS)
    client = client_for(viewer)
    assert client.get(url(makerspace)).status_code == 200
    assert client.patch(url(makerspace), {"config": defaults()}, format="json").status_code == 403
    viewer.is_active = False
    assert client.get(url(makerspace)).status_code == 403


def test_missing_app_and_malformed_row_fail_closed_and_can_be_repaired(monkeypatch):
    from apps.makerspaces import telemetry_public
    makerspace = space()
    monkeypatch.setattr(telemetry_public.apps, "is_installed", lambda name: False)
    assert telemetry_public.effective_telemetry(makerspace) == defaults()
    assert telemetry_public.platform_telemetry() == defaults()
    monkeypatch.undo()
    AnalyticsConnection.objects.create(makerspace=makerspace, telemetry_config=["invalid"])
    assert effective_telemetry(makerspace) == defaults()
    assert client_for(manager(makerspace)).patch(url(makerspace), {"config": defaults()}, format="json").status_code == 200


def test_audit_contains_no_provider_identifiers():
    from apps.audit.models import AuditLog
    makerspace = space()
    config = defaults()
    config["pageview"] = {"provider": "ga4", "site_id": "G-PRIVATE123", "endpoint": ""}
    assert client_for(manager(makerspace)).patch(url(makerspace), {"config": config}, format="json").status_code == 200
    event = AuditLog.objects.filter(makerspace=makerspace, action="analytics.telemetry_updated").latest("created_at")
    assert "PRIVATE123" not in str(event.meta)


@override_settings(WEB_TELEMETRY_ALLOWED_ORIGINS=["https://example.test"])
def test_strict_nested_fields_and_operator_origin():
    config = defaults()
    config["pageview"] = {"provider": "umami", "site_id": "12345678-1234-1234-1234-123456789abc", "endpoint": "https://example.test"}
    assert TelemetryEnvelopeSerializer(data={"config": config}).is_valid()
    config["pageview"]["surprise"] = True
    assert not TelemetryEnvelopeSerializer(data={"config": config}).is_valid()
    del config["pageview"]["surprise"]
    config["pageview"]["endpoint"] = "https://example.test/foreign.js"
    assert not TelemetryEnvelopeSerializer(data={"config": config}).is_valid()


@override_settings(WEB_TELEMETRY_ALLOWED_ORIGINS=["https://example.test"])
@pytest.mark.parametrize("endpoint", [
    "http://example.test", "https://user@example.test", "https://user:pw@example.test",
    "https://example.test?", "https://example.test#", "https://example.test/?a=1", "https://example.test:8443",
    " https://example.test", "https://exam\tple.test", "https://example.test\\@evil.test", "https://evil.test",
    "https://example.test.evil.test", "javascript:alert(1)", "//example.test",
])
def test_endpoint_rejects_scheme_credential_and_parser_tricks(endpoint):
    config = defaults()
    config["pageview"] = {"provider": "umami", "site_id": "12345678-1234-1234-1234-123456789abc", "endpoint": endpoint}
    assert not TelemetryEnvelopeSerializer(data={"config": config}).is_valid()


@override_settings(WEB_TELEMETRY_ALLOWED_ORIGINS=["https://example.test"])
def test_endpoint_is_stored_as_canonical_origin():
    config = defaults()
    config["pageview"] = {"provider": "umami", "site_id": "12345678-1234-1234-1234-123456789abc", "endpoint": "https://EXAMPLE.test/"}
    serializer = TelemetryEnvelopeSerializer(data={"config": config})
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["config"]["pageview"]["endpoint"] == "https://example.test"


@override_settings(WEB_TELEMETRY_ALLOWED_ORIGINS=["https://ingest.example.test"])
def test_sentry_requires_public_key_project_and_finite_sampling():
    config = defaults()
    sentry = config["diagnostics"]["sentry"]
    sentry.update(enabled=True, dsn="https://ingest.example.test/123", sample_rate=0.5)
    assert not TelemetryEnvelopeSerializer(data={"config": config}).is_valid()
    sentry["dsn"] = "https://publickey@ingest.example.test/123"
    assert TelemetryEnvelopeSerializer(data={"config": config}).is_valid()
    sentry["sample_rate"] = float("nan")
    assert not TelemetryEnvelopeSerializer(data={"config": config}).is_valid()


def test_posthog_shared_instance_requires_same_project():
    config = defaults()
    config["pageview"] = {"provider": "posthog", "site_id": "phc_alpha", "endpoint": ""}
    config["replay"] = {"provider": "posthog", "site_id": "phc_beta", "endpoint": ""}
    assert not TelemetryEnvelopeSerializer(data={"config": config}).is_valid()
    config["replay"]["site_id"] = "phc_alpha"
    assert TelemetryEnvelopeSerializer(data={"config": config}).is_valid()


def test_firebase_pageviews_require_only_canonical_measurement_id():
    config = defaults()
    config["pageview"]["provider"] = "firebase"
    config["firebase"].update(api_key="public_key", project_id="project-id", app_id="1:123:web:abc")
    assert not TelemetryEnvelopeSerializer(data={"config": config}).is_valid()
    config["firebase"]["measurement_id"] = "G-TEST123"
    assert TelemetryEnvelopeSerializer(data={"config": config}).is_valid()
    config["pageview"]["site_id"] = "G-OTHER"
    assert not TelemetryEnvelopeSerializer(data={"config": config}).is_valid()
    config["pageview"]["site_id"] = ""
    config["firebase"]["measurement_id"] = "not-an-id"
    assert not TelemetryEnvelopeSerializer(data={"config": config}).is_valid()


def test_manual_firebase_performance_does_not_require_measurement_id():
    config = defaults()
    config["firebase"].update(api_key="public_key", project_id="project-id", app_id="1:123:web:abc")
    config["diagnostics"]["firebase_performance"]["enabled"] = True
    assert TelemetryEnvelopeSerializer(data={"config": config}).is_valid()


def test_ga4_still_requires_its_own_pageview_measurement_id():
    config = defaults()
    config["pageview"]["provider"] = "ga4"
    config["firebase"]["measurement_id"] = "G-FIREBASE"
    assert not TelemetryEnvelopeSerializer(data={"config": config}).is_valid()
    config["pageview"]["site_id"] = "G-GA4"
    assert TelemetryEnvelopeSerializer(data={"config": config}).is_valid()
