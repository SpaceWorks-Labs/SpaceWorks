"""Registration boundary validation and the real control-plane audit path."""

import json

import pytest
from django.urls import reverse

from apps.accounts.forms_native_apps import NativeAppRegistrationForm
from apps.accounts.models import NativeAppRegistration, User
from apps.audit.models import AuditLog
from tests.accounts.control_mfa_helpers import force_control_mfa_login
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db
APP = "org.spaceworks.validation"
DIGEST = "ab" * 32
PREFIX = "TEAMID1234"


def registration_data(**overrides):
    data = {
        "platform": "android", "app_id": APP, "environment": "production",
        "verifier_config_key": APP, "status": "approved",
        "signing_identities": json.dumps([DIGEST]), "min_supported_version": "1.2.0",
        "makerspace": "", "approved_by": "", "revoked_at_0": "", "revoked_at_1": "",
    }
    data.update(overrides)
    return data


@pytest.mark.parametrize("platform,app_id", [
    ("android", "org.spaceworks.app"), ("android", "org.space_works.App2"),
    ("apple", "org.space-works.app"), ("apple", "123.spaceworks.app"),
])
def test_valid_package_and_bundle_names(platform, app_id):
    identity = PREFIX if platform == "apple" else DIGEST
    form = NativeAppRegistrationForm(data=registration_data(
        platform=platform, app_id=app_id, signing_identities=json.dumps([identity]),
    ))
    assert form.is_valid(), form.errors


@pytest.mark.parametrize("changes,field", [
    ({"app_id": "spaceworks"}, "app_id"),
    ({"app_id": "org.1invalid"}, "app_id"),
    ({"app_id": "org..app"}, "app_id"),
    ({"app_id": "org.app/other"}, "app_id"),
    ({"platform": "apple", "app_id": "org.bad_bundle"}, "app_id"),
    ({"signing_identities": "not-json"}, "signing_identities"),
    ({"signing_identities": "[]"}, "signing_identities"),
    ({"signing_identities": json.dumps([DIGEST] * 6)}, "signing_identities"),
    ({"signing_identities": json.dumps({"digest": DIGEST})}, "signing_identities"),
    ({"signing_identities": json.dumps([None])}, "signing_identities"),
    ({"signing_identities": json.dumps(["ab:cd"])}, "signing_identities"),
    ({"signing_identities": json.dumps(["ag" * 32])}, "signing_identities"),
    ({"platform": "apple", "signing_identities": json.dumps([PREFIX, PREFIX])}, "signing_identities"),
    ({"platform": "apple", "signing_identities": '["teamid1234"]'}, "signing_identities"),
    ({"platform": "apple", "signing_identities": '["TEAMID123"]'}, "signing_identities"),
    ({"platform": "apple", "signing_identities": '["TEAMID12345"]'}, "signing_identities"),
    ({"platform": "apple", "signing_identities": '["TEAMID123!"]'}, "signing_identities"),
    *[({"min_supported_version": version}, "min_supported_version")
      for version in ("1", "v1.2", "1..2", "1.2-beta", "1.2.", "-1.2")],
])
def test_invalid_registration_inputs_fail_on_the_relevant_field(changes, field):
    form = NativeAppRegistrationForm(data=registration_data(**changes))
    assert not form.is_valid()
    assert field in form.errors


@pytest.mark.parametrize("version", ["", "1.0", "1.10.2", "01.002.3.0"])
def test_signers_normalise_and_versions_are_optional_dotted_numbers(version):
    identities = [":".join(["AB"] * 32), DIGEST.upper(), "cd" * 32]
    form = NativeAppRegistrationForm(data=registration_data(
        signing_identities=json.dumps(identities), min_supported_version=version,
    ))
    assert form.is_valid(), form.errors
    row = form.save()
    assert row.signing_identities == [DIGEST, "cd" * 32]
    assert row.min_supported_version == (version or None)


def test_five_distinct_distribution_signers_are_accepted():
    identities = [f"{value:02x}" * 32 for value in range(5)]
    form = NativeAppRegistrationForm(data=registration_data(signing_identities=json.dumps(identities)))
    assert form.is_valid(), form.errors
    assert form.cleaned_data["signing_identities"] == identities


@pytest.mark.parametrize("edit", [
    "app_id", "platform", "environment", "verifier_config_key", "signing_identities",
    "min_supported_version", "approved", "pending", "revoked", "makerspace", "approved_by", "revoked_at",
])
def test_every_kind_of_registration_edit_emits_a_control_audit(client, edit):
    actor = User.objects.create_superuser(username="m1e-registration-auditor", password="strong-admin-pw")
    force_control_mfa_login(client, actor)
    data = registration_data()
    if edit == "approved":
        data["status"] = "pending"
    response = client.post(reverse("admin:accounts_nativeappregistration_add"), data)
    assert response.status_code == 302
    assert response.url == reverse("admin:accounts_nativeappregistration_changelist")
    row = NativeAppRegistration.objects.get(app_id=APP)
    events = AuditLog.objects.filter(actor=actor, action="native_app.registration_updated", target_id=str(row.pk))
    created = events.get()
    assert created.meta["created"] is True
    assert created.meta["via"] == "control"
    expected_field = edit
    if edit == "platform":
        data.update(platform="apple", signing_identities=json.dumps([PREFIX]))
    elif edit in {"approved", "pending", "revoked"}:
        data["status"] = edit
        expected_field = "status"
    elif edit == "makerspace":
        data[edit] = str(make_space("m1e-admin-scope").pk)
    elif edit == "approved_by":
        data[edit] = str(actor.pk)
    elif edit == "revoked_at":
        data.update(revoked_at_0="2026-10-16", revoked_at_1="12:00:00")
    else:
        data[edit] = {
            "app_id": "org.spaceworks.changed", "environment": "development",
            "verifier_config_key": "new-verifier", "signing_identities": json.dumps(["cd" * 32]),
            "min_supported_version": "2.0.0",
        }[edit]
    response = client.post(reverse("admin:accounts_nativeappregistration_change", args=[row.pk]), data)
    assert response.status_code == 302
    assert response.url == reverse("admin:accounts_nativeappregistration_changelist")
    assert events.count() == 2
    updated = events.exclude(pk=created.pk).get()
    assert updated.meta["created"] is False
    assert updated.meta["via"] == "control"
    assert expected_field in updated.meta["changed_fields"]
    row.refresh_from_db()
    if edit == "revoked":
        assert row.revoked_at is not None
        assert AuditLog.objects.filter(actor=actor, action="native_app.revoked", target_id=str(row.pk)).exists()
    elif edit == "revoked_at":
        assert row.revoked_at is not None
    elif edit == "makerspace":
        assert str(row.makerspace_id) == data[edit]
    elif edit == "approved_by":
        assert row.approved_by_id == actor.pk
    elif edit == "signing_identities":
        assert row.signing_identities == json.loads(data[edit])
    else:
        assert getattr(row, expected_field) == data[expected_field]
