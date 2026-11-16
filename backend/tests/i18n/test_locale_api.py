"""Persistence, API and tenancy of the two locale fields (phase 8 i18n)."""
import pytest
from rest_framework.test import APIClient

from apps.accounts.claim_route_types import Refused
from apps.accounts.claim_routes import policy_for
from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.audit.presentation_catalog import PRESENTATION_CATALOG
from apps.makerspaces.models import Makerspace
from tests.return_helpers import make_space, make_user

pytestmark = pytest.mark.django_db
ME = "/api/v1/auth/me"


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_defaults():
    space = make_space("i18n-defaults")
    user = make_user("i18n-defaults-user")
    assert space.default_locale == "en"
    assert user.preferred_locale is None


def test_me_get_and_patch_round_trip_with_one_audit_row():
    user = make_user("i18n-me", access_status=User.AccessStatus.ACTIVE)
    client = _client(user)
    body = client.get(ME).json()
    assert body["preferred_locale"] is None
    assert body["effective_locale"] == "en"
    assert body["supported_locales"] == [{"code": "en", "label": "English"}]

    response = client.patch(ME, {"preferred_locale": "en"}, format="json")
    assert response.status_code == 200 and response.json()["preferred_locale"] == "en"
    user.refresh_from_db()
    assert user.preferred_locale == "en"
    rows = AuditLog.objects.filter(action="account.locale_changed", target_id=str(user.pk))
    assert rows.count() == 1 and rows.get().meta == {"before": "default", "after": "en"}

    assert client.patch(ME, {"preferred_locale": "en"}, format="json").status_code == 200
    assert rows.count() == 1  # idempotent: no write, no audit

    assert client.patch(ME, {"preferred_locale": None}, format="json").status_code == 200
    user.refresh_from_db()
    assert user.preferred_locale is None and rows.count() == 2


@pytest.mark.parametrize("body", [{"preferred_locale": ""}, {"preferred_locale": "fr"},
                                  {"preferred_locale": "en", "user_id": 1}, {}])
def test_me_patch_refuses_bad_bodies(body):
    user = make_user(f"i18n-bad-{len(body)}-{body.get('preferred_locale')}")
    assert _client(user).patch(ME, body, format="json").status_code == 400
    user.refresh_from_db()
    assert user.preferred_locale is None


def test_me_patch_requires_authentication():
    assert APIClient().patch(ME, {"preferred_locale": "en"}, format="json").status_code == 401


def test_claim_sessions_are_refused_and_gate_is_classified():
    assert isinstance(policy_for("auth-me", "PATCH"), Refused)
    from apps.tenant_migration.gate_policy import HTTP_EXEMPTIONS
    assert "auth-me" in HTTP_EXEMPTIONS
    from apps.backup.route_policy import QUARANTINE_ALLOWED
    assert ("auth-me", "PATCH") not in QUARANTINE_ALLOWED


def test_audit_presentation_entries():
    for action in ("account.locale_changed", "makerspace.default_locale_changed"):
        assert PRESENTATION_CATALOG[action].permitted_meta_paths == ("before", "after")


def test_bootstrap_exposes_default_and_list():
    space = make_space("i18n-bootstrap")
    from django.urls import reverse
    response = APIClient().get(reverse("tenant-bootstrap"), {"slug": space.slug})
    assert response.status_code == 200, response.content
    assert response.json()["default_locale"] == "en"
    assert response.json()["supported_locales"] == [{"code": "en", "label": "English"}]


def test_makerspace_serializer_accepts_only_supported():
    from rest_framework.exceptions import ValidationError
    from apps.admin_api.serializers_makerspaces import MakerspaceSerializer
    field = MakerspaceSerializer().fields["default_locale"]
    assert field.run_validation("en") == "en"
    with pytest.raises(ValidationError):
        field.run_validation("fr")


def test_tenant_dump_and_export_classification():
    from apps.data_export.fields import FIELDS, USER_PROJECTIONS
    from apps.data_export.types import Emitted, Fidelity
    from apps.tenant_migration.tenant_dump_catalog import validate_catalog
    from apps.tenant_migration.tenant_dump_field_snapshot import FIRST_PARTY_FIELD_NAMES
    from apps.tenant_migration.tenant_dump_user_rows import _stub_values
    validate_catalog()
    assert "default_locale" in FIRST_PARTY_FIELD_NAMES["makerspaces.Makerspace"]
    assert "preferred_locale" in FIRST_PARTY_FIELD_NAMES["accounts.User"]
    for fidelity in Fidelity:
        assert "preferred_locale" in USER_PROJECTIONS[fidelity]
        assert isinstance(FIELDS[(fidelity, "accounts.User", "preferred_locale")], Emitted)
        assert isinstance(FIELDS[(fidelity, "makerspaces.Makerspace", "default_locale")], Emitted)
    assert _stub_values("x")["preferred_locale"] is None
    from apps.encryption import registry
    assert "default_locale" not in str(getattr(registry, "__dict__", {}))
