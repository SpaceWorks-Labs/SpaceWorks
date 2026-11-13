"""L25: create, rotate, revoke and view of the credentials are audited, secrets are never
echoed after creation, and every failure is typed (never a 500)."""

import json

import pytest
from django.db import connection

from apps.analytics import provisioning
from apps.analytics.models import AnalyticsConnection
from apps.audit.models import AuditLog
from apps.tenant_rls.models import FixedRoleScope

from .helpers import SECRET, client_for, manager, platform_url, space, space_url, superadmin

pytestmark = pytest.mark.django_db


def _actions(makerspace=None):
    rows = AuditLog.objects.filter(action__startswith="analytics.")
    rows = rows.filter(makerspace=makerspace) if makerspace else rows.filter(makerspace__isnull=True)
    return list(rows.order_by("id").values_list("action", flat=True))


def _all_audit_text():
    return json.dumps(list(AuditLog.objects.filter(action__startswith="analytics.").values("meta")), default=str)


def _role_exists(role):
    with connection.cursor() as cursor:
        cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = %s)", [role])
        return cursor.fetchone()[0]


def test_the_provisioning_functions_exist_on_the_test_database():
    assert provisioning.availability() == (True, "")


def test_create_returns_the_password_once_and_stores_only_ciphertext():
    makerspace = space()
    client = client_for(manager(makerspace))
    created = client.post(space_url("-login", makerspace))
    assert created.status_code == 201, created.data
    password, role = created.data["password"], created.data["role"]
    assert created["Cache-Control"] == "no-store"
    assert role.startswith("sw_an_") and f"_s{makerspace.pk}_" in role
    assert created.data["schema"] == "spaceworks_analytics"
    assert _role_exists(role)
    row = AnalyticsConnection.objects.get(makerspace=makerspace)
    assert row.login_role == role and password not in row.login_password and row.login_password.startswith("fernet:")
    assert FixedRoleScope.objects.get(role_name=role).makerspace_id == makerspace.pk
    read = client.get(space_url("-connection", makerspace))
    assert read.status_code == 200
    assert password not in json.dumps(read.data, default=str)
    assert read.data["login"]["role"] == role and read.data["login"]["exists"] is True
    assert password not in _all_audit_text()
    assert _actions(makerspace) == ["analytics.login_created", "analytics.credentials_viewed"]


def test_create_twice_is_a_typed_conflict():
    makerspace = space()
    client = client_for(manager(makerspace))
    assert client.post(space_url("-login", makerspace)).status_code == 201
    second = client.post(space_url("-login", makerspace))
    assert (second.status_code, second.data["code"]) == (409, "analytics_login_exists")


def test_rotate_changes_the_password_keeps_the_role_and_audits():
    makerspace = space()
    client = client_for(manager(makerspace))
    first = client.post(space_url("-login", makerspace)).data
    rotated = client.post(space_url("-login-rotate", makerspace))
    assert rotated.status_code == 200
    assert rotated.data["role"] == first["role"] and rotated.data["password"] != first["password"]
    assert AnalyticsConnection.objects.get(makerspace=makerspace).login_rotated_at is not None
    assert "analytics.login_rotated" in _actions(makerspace)
    assert first["password"] not in _all_audit_text() and rotated.data["password"] not in _all_audit_text()


def test_revoke_drops_the_role_and_the_fixed_scope_row():
    makerspace = space()
    client = client_for(manager(makerspace))
    role = client.post(space_url("-login", makerspace)).data["role"]
    assert client.delete(space_url("-login", makerspace)).status_code == 204
    assert not _role_exists(role)
    assert not FixedRoleScope.objects.filter(role_name=role).exists()
    row = AnalyticsConnection.objects.get(makerspace=makerspace)
    assert (row.login_role, row.login_password) == ("", "")
    assert _actions(makerspace)[-1] == "analytics.login_revoked"
    missing = client.delete(space_url("-login", makerspace))
    assert (missing.status_code, missing.data["code"]) == (409, "analytics_login_missing")


def test_the_embed_secret_is_write_only_and_changes_are_audited_by_field_name():
    makerspace = space()
    client = client_for(manager(makerspace))
    response = client.patch(space_url("-connection", makerspace), {
        "metabase_url": "https://metabase.example.org/", "embed_secret": SECRET,
        "dashboards": [{"id": 4, "title": "Loans"}], "show_member_details": True,
    }, format="json")
    assert response.status_code == 200, response.data
    assert response.data["metabase_url"] == "https://metabase.example.org"
    assert response.data["embed_secret_set"] is True and "embed_secret" not in response.data
    assert SECRET not in json.dumps(response.data) and SECRET not in _all_audit_text()
    row = AnalyticsConnection.objects.get(makerspace=makerspace)
    assert row.get_embed_secret() == SECRET and SECRET not in row.embed_secret
    updated = AuditLog.objects.filter(action="analytics.connection_updated").get()
    assert updated.meta["fields"] == ["dashboards", "embed_secret", "metabase_url", "show_member_details"]


@pytest.mark.parametrize("url", ["javascript:alert(1)", "https://user:pw@metabase.example.org",
                                 "https://metabase.example.org/?x=1", "ftp://metabase.example.org"])
def test_bad_metabase_urls_are_refused(url):
    makerspace = space()
    response = client_for(manager(makerspace)).patch(space_url("-connection", makerspace), {"metabase_url": url},
                                                     format="json")
    assert response.status_code == 400


def test_a_short_embed_secret_is_refused():
    makerspace = space()
    response = client_for(manager(makerspace)).patch(space_url("-connection", makerspace), {"embed_secret": "short"},
                                                     format="json")
    assert response.status_code == 400


def test_not_available_on_this_hosting_is_a_typed_409(monkeypatch):
    makerspace = space()
    monkeypatch.setattr(provisioning, "availability", lambda using="default": (False, "not_available_on_hosting"))
    response = client_for(manager(makerspace)).post(space_url("-login", makerspace))
    assert (response.status_code, response.data["code"]) == (409, "analytics_not_available")
    # A refused attempt rolls its whole transaction back, including the lazily created connection row.
    assert not AnalyticsConnection.objects.filter(makerspace=makerspace).exclude(login_role="").exists()
    assert "analytics.login_created" not in _actions(makerspace)


def test_a_database_refusal_is_a_typed_503_and_changes_nothing(monkeypatch):
    makerspace = space()

    def refuse(*args, **kwargs):
        raise provisioning.ProvisioningFailed()

    monkeypatch.setattr(provisioning, "ensure_login", refuse)
    response = client_for(manager(makerspace)).post(space_url("-login", makerspace))
    assert (response.status_code, response.data["code"]) == (503, "analytics_login_failed")
    assert not AnalyticsConnection.objects.filter(makerspace=makerspace).exclude(login_role="").exists()


def test_provisioning_errors_never_log_the_verifier(caplog):
    with pytest.raises(provisioning.ProvisioningFailed):
        provisioning.ensure_login("not-an-analytics-role", "pw-should-not-appear", None)
    assert "pw-should-not-appear" not in caplog.text and "SCRAM" not in caplog.text


def test_the_functions_refuse_another_spaces_or_a_foreign_role_name():
    a, b = space(), space()
    role = provisioning.generate_login_name(a.pk)
    with pytest.raises(provisioning.ProvisioningFailed):
        provisioning.ensure_login(role, "x" * 20, b.pk)
    with pytest.raises(provisioning.ProvisioningFailed):
        provisioning.drop_login("postgres")


def test_platform_login_lifecycle_is_audited_without_a_space():
    client = client_for(superadmin())
    created = client.post(platform_url("-login"))
    assert created.status_code == 201, created.data
    assert created.data["schema"] == "spaceworks_analytics_platform" and "_p_" in created.data["role"]
    assert not FixedRoleScope.objects.filter(role_name=created.data["role"]).exists()
    assert client.delete(platform_url("-login")).status_code == 204
    assert _actions() == ["analytics.login_created", "analytics.login_revoked"]


def test_deleting_the_connection_drops_the_login_after_commit(django_capture_on_commit_callbacks):
    makerspace = space()
    role = client_for(manager(makerspace)).post(space_url("-login", makerspace)).data["role"]
    with django_capture_on_commit_callbacks(execute=True):
        AnalyticsConnection.objects.filter(makerspace=makerspace).delete()
    assert not _role_exists(role)
