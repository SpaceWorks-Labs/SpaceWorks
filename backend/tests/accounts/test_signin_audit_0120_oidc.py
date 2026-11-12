"""REDIS-AUTH-AUDIT (decision 339b): an OIDC provider edit never re-points or strands sign-ins.

A linked identity is ``oidc:<slug>`` + ``sub``. Renaming the slug orphaned every one; changing
the issuer let a person at the NEW server whose ``sub`` matched sign into someone else's
account. Disabling a provider that was somebody's only way in was never checked at all.
"""

import pytest

from apps.accounts.admin_social import OidcProviderForm
from apps.accounts.models import User
from apps.accounts.models_oidc import OidcProvider
from apps.accounts.models_social import SocialIdentity
from apps.audit.models import AuditLog
from tests.r2_superadmin_local.helpers import api, superadmin

pytestmark = pytest.mark.django_db
URL = "/api/v1/admin/platform/oidc-providers/{}"


@pytest.fixture
def campus():
    return OidcProvider.objects.create(slug="campus", display_name="Campus", issuer="https://id.example.test",
                                       jwks_url="https://id.example.test/jwks", client_id="spaceworks")


def linked(campus, name="oidc-member", *, password=None):
    user = User.objects.create_user(username=name, email=f"{name}@example.test", password=password)
    SocialIdentity.objects.create(user=user, provider=campus.provider_key, provider_sub=f"sub-{name}")
    return user


def patch(campus, body):
    return api(superadmin("oidc-audit-root")).patch(URL.format(campus.pk), body, format="json")


@pytest.mark.parametrize("change", [{"slug": "renamed"}, {"issuer": "https://other.example.test"}])
def test_slug_and_issuer_are_fixed_once_anyone_has_linked(campus, change):
    linked(campus, password="Member password 77!")
    refused = patch(campus, change)
    assert refused.status_code == 400 and refused.json()["code"] == "oidc_provider_change_refused"
    campus.refresh_from_db()
    assert campus.slug == "campus" and campus.issuer == "https://id.example.test"
    assert not AuditLog.objects.filter(action="platform.oidc_provider_saved").exists()


def test_slug_and_issuer_change_freely_before_anyone_links(campus):
    changed = patch(campus, {"slug": "campus-two", "issuer": "https://other.example.test"})
    assert changed.status_code == 200, changed.json()
    assert changed.json()["slug"] == "campus-two"


def test_disabling_a_providers_only_member_is_refused(campus):
    linked(campus)  # no password, no other way in
    refused = patch(campus, {"is_enabled": False})
    assert refused.status_code == 400 and "lock out" in refused.json()["detail"]
    campus.refresh_from_db()
    assert campus.is_enabled


def test_disabling_is_allowed_when_members_keep_a_password_and_renaming_display_is_free(campus):
    linked(campus, password="Member password 77!")
    assert patch(campus, {"display_name": "Campus SSO"}).status_code == 200
    assert patch(campus, {"is_enabled": False}).status_code == 200


def test_the_control_form_applies_the_same_refusals(campus):
    linked(campus)
    data = {"slug": "campus", "display_name": "Campus", "issuer": "https://other.example.test",
            "jwks_url": "https://id.example.test/jwks", "client_id": "spaceworks",
            "is_enabled": True, "allow_auto_link": True}
    form = OidcProviderForm(data=data, instance=campus)
    assert not form.is_valid() and "cannot change" in str(form.errors)
    data.update(issuer="https://id.example.test", is_enabled=False)
    form = OidcProviderForm(data=data, instance=campus)
    assert not form.is_valid() and "lock out" in str(form.errors)
