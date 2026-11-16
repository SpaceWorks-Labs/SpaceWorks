from types import SimpleNamespace

import pytest
from django.apps import apps
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.test import APIClient

from apps.accounts import mfa_policy, rbac
from apps.accounts.models import User
from apps.accounts.serializers_payload import user_payload
from apps.accounts.serializers_refresh import SpaceWorksTokenRefreshSerializer
from apps.accounts.services_social_identity import SocialResolutionError
from apps.accounts.services_social_login import assert_staff_authority
from apps.bookings.models import BookingSpaceStaffGrant, BookingSpaceStaffGrantInvite
from apps.bookings.services_staff_grants import create_invite, revoke_grant
from apps.data_export.datasets import DATASET_SPECS
from apps.data_export.models import EXPORTED_MODELS, MODELS
from apps.data_export.references import USER_EDGES
from apps.data_export.types import Fidelity, OmittedModel
from apps.makerspaces.lifecycle_purge import purge
from apps.makerspaces.module_install import uninstall_module
from apps.makerspaces.module_purge import purge_module
from apps.tenant_migration.audit_references import AUDIT_TARGET_DISPOSITIONS, AuditReferenceDisposition
from apps.tenant_migration.tenant_dump_catalog import FIELD_POLICIES, validate_catalog
from apps.tenant_migration.tenant_dump_field_snapshot import FIRST_PARTY_FIELD_NAMES
from apps.tenant_migration.tenant_dump_model_catalog import FIRST_PARTY_MODEL_RULES
from apps.tenant_migration.tenant_dump_types import AuthorityDisposition, ModelDisposition
from tests.bookings.staff_grant_helpers import grant_fixture

pytestmark = pytest.mark.django_db
LABELS = ("bookings.BookingSpaceStaffGrant", "bookings.BookingSpaceStaffGrantInvite")


def test_sign_in_payload_refresh_and_mfa_use_live_booking_source():
    tenant, manager, user, resource, grant, _ = grant_fixture()
    response = APIClient().post(reverse("auth-login"), {
        "username": user.username, "password": "Grant-password-123!", "surface": "delegated",
    }, format="json")
    assert response.status_code == 200, response.data
    assert response.data["user"]["makerspaces"] == []
    assert response.data["user"]["booking_grants"][0]["space_id"] == resource.pk
    assert response.data["user"]["booking_grants"][0]["source"] == "booking_grant"
    assert not rbac.effective_actions(user, tenant.pk)
    tenant.enabled_features.append("security.staff_mfa_required")
    # Security keys change only through the security service; write the fixture row directly.
    type(tenant).objects.filter(pk=tenant.pk).update(enabled_features=tenant.enabled_features)
    assert mfa_policy.required(user)
    enrollment = APIClient().post(reverse("auth-login"), {
        "username": user.username, "password": "Grant-password-123!", "surface": "delegated",
    }, format="json")
    # S-A (#128 C-1): no forced enrolment at sign-in; a member session plus the grace banner.
    assert enrollment.status_code == 200 and enrollment.data["user"]["mfa_enrolment_due"] is True
    revoke_grant(grant, actor=manager)
    assert not mfa_policy.required(user)
    signed_in = APIClient().post(reverse("auth-login"), {
        "username": user.username, "password": "Grant-password-123!", "surface": "delegated",
    }, format="json")
    assert signed_in.status_code == 200, signed_in.data
    assert signed_in.data["user"]["booking_grants"] == []
    refreshed = SpaceWorksTokenRefreshSerializer().validate({"refresh": signed_in.cookies["refresh_token"].value})
    assert refreshed["user"]["booking_grants"] == []
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refreshed['access']}")
    assert client.get(reverse("admin-bookable-space-detail", args=[resource.pk])).status_code == 403


@pytest.mark.parametrize("origin_scope", ["own", "other"])
def test_staff_discovery_and_password_origin_are_narrow(origin_scope):
    tenant, _, user, resource, _, _ = grant_fixture()
    if origin_scope == "own":
        selected = tenant
    else:
        selected, *_ = grant_fixture(slug="other-booking-origin")
    selected.frontend_domain = selected.slug + ".example.test"
    selected.frontend_domain_status = "verified"
    selected.save(update_fields=["frontend_domain", "frontend_domain_status"])
    request = SimpleNamespace(headers={}, META={}, selected_makerspace_id=selected.pk)
    response = APIClient().post(reverse("auth-login"), {
        "username": user.username, "password": "Grant-password-123!", "surface": "delegated",
    }, format="json", HTTP_ORIGIN=f"https://{selected.frontend_domain}")
    if origin_scope == "own":
        assert_staff_authority(user, request)
        assert user_payload(user, request=request)["booking_grants"][0]["space_id"] == resource.pk
        assert response.status_code == 200, response.data
    else:
        with pytest.raises(SocialResolutionError):
            assert_staff_authority(user, request)
        assert user_payload(user, request=request)["booking_grants"] == []
        assert response.status_code == 200
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        assert client.get(reverse("admin-bookable-space-detail", args=[resource.pk]),
                          HTTP_ORIGIN=f"https://{selected.frontend_domain}").status_code == 403


@pytest.mark.parametrize("label", LABELS)
def test_credentials_have_total_drop_policy_and_no_user_closure_or_storage(label):
    assert isinstance(MODELS[label], OmittedModel)
    assert label not in EXPORTED_MODELS and label not in DATASET_SPECS
    assert FIRST_PARTY_MODEL_RULES[label].disposition is ModelDisposition.DROP
    fields = {field.name for field in apps.get_model(label)._meta.get_fields() if field.concrete or field.many_to_many}
    assert FIRST_PARTY_FIELD_NAMES[label] == fields
    assert all(FIELD_POLICIES[(label, field)].dispositions == (AuthorityDisposition.DROP,) for field in fields)
    assert AUDIT_TARGET_DISPOSITIONS[label.lower()].disposition is AuditReferenceDisposition.SOURCE_LOCAL_SNAPSHOT
    user_fields = {field.name for field in apps.get_model(label)._meta.fields if field.is_relation and field.related_model is User}
    for field in user_fields:
        for fidelity in Fidelity:
            edge = USER_EDGES[(fidelity, label, field)]
            assert not edge.included and not edge.raw
    validate_catalog()


@pytest.mark.django_db(transaction=True)
def test_module_purge_and_tenant_purge_remove_credentials_only_in_target_tenant():
    tenant, manager, user, resource, grant, _ = grant_fixture()
    invite, _ = create_invite(resource, actor=manager, permissions=["check_in"])
    other, _, _, other_resource, other_grant, _ = grant_fixture(slug="retained-booking-grants")
    root = User.objects.create_superuser(username="booking-purge-root", email="root@example.test", password="pw")
    uninstall_module(tenant, "bookings")
    assert BookingSpaceStaffGrant.objects.filter(pk=grant.pk).exists()
    result = purge_module(tenant, "bookings", root)
    assert result["staff_grants"] == 1 and result["staff_invites"] == 1
    assert not BookingSpaceStaffGrant.objects.filter(pk=grant.pk).exists()
    assert not BookingSpaceStaffGrantInvite.objects.filter(pk=invite.pk).exists()
    assert BookingSpaceStaffGrant.objects.filter(pk=other_grant.pk).exists()
    other.archived_at = timezone.now()
    other.save(update_fields=["archived_at"])
    purge(other, root)
    assert not BookingSpaceStaffGrant.objects.filter(pk=other_grant.pk).exists()


def test_bookings_authority_survives_without_events_membership_or_rail(monkeypatch):
    from apps.bookings.booking_authority import can
    from apps.makerspaces import resource_grant_sources as sources
    tenant, _, user, resource, _, _ = grant_fixture("check_in")
    tenant.enabled_modules = [key for key in tenant.enabled_modules if key not in {"events", "membership", "payments"}]
    tenant.save(update_fields=["enabled_modules"])
    monkeypatch.setattr(sources, "_sources", {})
    monkeypatch.setattr("apps.separability.tombstones.app_is_tombstoned", lambda label: label == "events")
    monkeypatch.setattr("apps.separability.tombstones.register_separable_app", lambda label: None)
    apps.get_app_config("bookings").ready()
    apps.get_app_config("events").ready()
    assert [source.key for source in sources.registered_sources()] == ["booking_grants"]
    assert sources.has_authority(user)
    assert sources.payload_entries(user)["booking_grants"][0]["space_id"] == resource.pk
    resource.makerspace = tenant
    assert can(user, resource, "check_in")


def test_installer_picks_up_opt_in_bookings_feature_without_events_dependency():
    from apps.makerspaces.capabilities import FEATURES
    from apps.makerspaces.setup_areas import features_for, modules_for
    feature = FEATURES["bookings.staff_grants"]
    assert feature.parent_module == "bookings" and not feature.default_enabled
    assert feature.requires_modules == ("bookings",)
    assert "bookings.staff_grants" in features_for({"bookings"})
    modules = set(modules_for({"bookings"})) - {"bookings"}
    assert "bookings.staff_grants" not in features_for({"bookings"}, modules)
