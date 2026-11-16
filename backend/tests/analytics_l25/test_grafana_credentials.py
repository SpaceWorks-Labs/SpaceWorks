"""Decision 263: the Grafana token is encrypted at rest and never returned; create, rotate,
revoke and view are audited without the token or the URL; the rows never travel."""

import json

import pytest

from apps.analytics.models import AnalyticsConnection, PlatformAnalyticsConnection
from apps.audit.models import AuditLog

from .grafana_helpers import BOARDS, PUBLIC_TOKEN, TOKEN, g_platform_url, g_space_url
from .helpers import client_for, manager, space, superadmin

pytestmark = pytest.mark.django_db


def _actions(makerspace=None):
    rows = AuditLog.objects.filter(action__startswith="analytics.grafana_")
    rows = rows.filter(makerspace=makerspace) if makerspace else rows.filter(makerspace__isnull=True)
    return list(rows.order_by("id").values_list("action", flat=True))


def _audit_text():
    return json.dumps(list(AuditLog.objects.filter(action__startswith="analytics.").values("meta")), default=str)


def test_the_token_is_ciphertext_never_returned_and_its_lifecycle_is_audited():
    makerspace = space()
    client = client_for(manager(makerspace))
    saved = client.post(g_space_url("-token", makerspace), {"token": TOKEN}, format="json")
    assert saved.status_code == 200, saved.data
    assert saved["Cache-Control"] == "no-store"
    assert saved.data["token_set"] is True and TOKEN not in json.dumps(saved.data, default=str)
    row = AnalyticsConnection.objects.get(makerspace=makerspace)
    assert TOKEN not in row.grafana_token and row.grafana_token.startswith("fernet:")
    assert row.get_grafana_token() == TOKEN
    rotated = client.post(g_space_url("-token", makerspace), {"token": TOKEN + "x"}, format="json")
    assert rotated.status_code == 200
    read = client.get(g_space_url("-connection", makerspace))
    assert TOKEN not in json.dumps(read.data, default=str)
    assert client.delete(g_space_url("-token", makerspace)).status_code == 204
    assert AnalyticsConnection.objects.get(makerspace=makerspace).grafana_token == ""
    assert client.delete(g_space_url("-token", makerspace)).data["code"] == "grafana_token_missing"
    assert _actions(makerspace) == [
        "analytics.grafana_token_created", "analytics.grafana_credentials_viewed",
        "analytics.grafana_token_rotated", "analytics.grafana_credentials_viewed",
        "analytics.grafana_credentials_viewed", "analytics.grafana_token_revoked",
    ]
    assert TOKEN not in _audit_text()


def test_connection_changes_are_validated_and_audited_by_field_name():
    makerspace = space()
    client = client_for(manager(makerspace))
    body = {"provider": "both", "grafana_url": "https://grafana.example.org/", "org_id": 2, "dashboards": BOARDS}
    response = client.patch(g_space_url("-connection", makerspace), body, format="json")
    assert response.status_code == 200, response.data
    assert response.data["grafana_url"] == "https://grafana.example.org" and response.data["provider"] == "both"
    entry = AuditLog.objects.get(makerspace=makerspace, action="analytics.grafana_connection_updated")
    assert entry.meta["fields"] == ["dashboards", "grafana_url", "org_id", "provider"]
    assert "grafana.example.org" not in _audit_text() and PUBLIC_TOKEN not in _audit_text()


@pytest.mark.parametrize("body", [
    {"grafana_url": "ftp://grafana.example.org"},
    {"grafana_url": "https://user:pw@grafana.example.org"},
    {"org_id": 0},
    {"provider": "looker"},
    {"dashboards": [{"uid": "bad uid", "title": "x", "mode": "public", "public_token": PUBLIC_TOKEN}]},
    {"dashboards": [{"uid": "a", "title": "x", "mode": "public", "public_token": ""}]},
    {"dashboards": [{"uid": "a", "title": "x", "mode": "render", "public_token": PUBLIC_TOKEN}]},
    {"dashboards": [{"uid": "a", "title": "x", "mode": "render"}, {"uid": "a", "title": "y", "mode": "render"}]},
])
def test_invalid_connection_values_are_400(body):
    makerspace = space()
    response = client_for(manager(makerspace)).patch(g_space_url("-connection", makerspace), body, format="json")
    assert response.status_code == 400


@pytest.mark.parametrize("token", ["short", "has space inside token", "x" * 600])
def test_invalid_tokens_are_400(token):
    makerspace = space()
    response = client_for(manager(makerspace)).post(g_space_url("-token", makerspace), {"token": token}, format="json")
    assert response.status_code == 400


def test_the_platform_token_is_separate_from_every_space():
    makerspace = space()
    client_for(manager(makerspace)).post(g_space_url("-token", makerspace), {"token": TOKEN}, format="json")
    root = client_for(superadmin())
    assert root.get(g_platform_url("-connection")).data["token_set"] is False
    assert root.post(g_platform_url("-token"), {"token": "glsa_platform_token"}, format="json").status_code == 200
    assert PlatformAnalyticsConnection.load().get_grafana_token() == "glsa_platform_token"
    assert AnalyticsConnection.objects.get(makerspace=makerspace).get_grafana_token() == TOKEN
    assert _actions(None)[0] == "analytics.grafana_credentials_viewed"


def test_the_rows_are_never_exported_and_the_field_snapshot_is_complete():
    from apps.data_export.classification_r2_l25 import OMITTED_MODELS
    from apps.tenant_migration.catalog_r2_l25 import FIELD_NAMES

    for label, model in (("analytics.AnalyticsConnection", AnalyticsConnection),
                         ("analytics.PlatformAnalyticsConnection", PlatformAnalyticsConnection)):
        assert label in OMITTED_MODELS
        names = {field.attname.removesuffix("_id") if field.is_relation else field.name
                 for field in model._meta.concrete_fields}
        assert names == set(FIELD_NAMES[label])
        assert {"grafana_token", "grafana_dashboards", "provider"} <= set(FIELD_NAMES[label])
