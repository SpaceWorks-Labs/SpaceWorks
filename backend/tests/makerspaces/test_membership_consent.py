"""X10: the consent ledger. Purposes are published by the space; members give and withdraw."""
import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.makerspaces.membership_admission_settings import update_settings
from apps.makerspaces.models import MembershipConsent
from tests.makerspaces.l4_helpers import features_off, features_on, member, space_with_manager
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db
PURPOSES = [{"key": "photos", "label": "Photos at events", "description": "We may post photos."}]


def _space():
    space, manager = space_with_manager("consent")
    features_on(space, "consent")
    update_settings(manager, space, {"consent_purposes": PURPOSES, "privacy_notice_version": "v2"})
    return space, manager


def test_give_withdraw_and_give_again_keeps_every_period():
    space, manager = _space()
    membership = member("consent", space)
    client = authenticated_client(membership.user)
    url = reverse("member-membership-consents", args=[space.pk])
    ledger = client.get(url).json()
    assert ledger["purposes"][0]["key"] == "photos" and ledger["notice_version"] == "v2"
    assert client.post(url, {"purpose": "photos"}, format="json").status_code == 200
    assert client.post(url, {"purpose": "photos"}, format="json").status_code == 200  # idempotent
    assert client.delete(url, {"purpose": "photos"}, format="json").status_code == 200
    client.post(url, {"purpose": "photos"}, format="json")
    rows = MembershipConsent.objects.filter(membership=membership).order_by("pk")
    assert [row.withdrawn_at is None for row in rows] == [False, True]
    assert rows[0].notice_version == "v2"
    assert AuditLog.objects.filter(action="membership.consent_given").count() == 2
    assert AuditLog.objects.filter(action="membership.consent_withdrawn").count() == 1
    staff = authenticated_client(manager).get(reverse("admin-membership-consents", args=[membership.pk]))
    assert len(staff.json()) == 2


def test_unknown_purpose_is_refused_and_other_members_cannot_write():
    space, _manager = _space()
    membership = member("consent-unknown", space)
    url = reverse("member-membership-consents", args=[space.pk])
    assert authenticated_client(membership.user).post(url, {"purpose": "marketing"}, format="json").status_code == 400


def test_off_switch_hides_the_ledger_and_keeps_the_rows():
    space, _manager = _space()
    membership = member("consent-off", space)
    client = authenticated_client(membership.user)
    url = reverse("member-membership-consents", args=[space.pk])
    client.post(url, {"purpose": "photos"}, format="json")
    features_off(space, "consent")
    assert client.get(url).status_code == 404
    assert MembershipConsent.objects.filter(membership=membership).count() == 1
    features_on(space, "consent")
    assert len(client.get(url).json()["consents"]) == 1


def test_purposes_need_the_switch_to_change():
    space, manager = space_with_manager("consent-gate")
    response = authenticated_client(manager).patch(
        reverse("admin-membership-admission", args=[space.pk]), {"consent_purposes": PURPOSES}, format="json")
    assert response.status_code == 403
