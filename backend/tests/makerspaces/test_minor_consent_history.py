"""Release 0.12.0 (R1 report): staff list every consent of a minor and revoke an OLDER one."""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.makerspaces import minors
from apps.makerspaces.models import CommunityPolicy, GuardianConsent
from tests.makerspaces.l4_helpers import features_on
from tests.makerspaces.test_membership_j1 import manager, space, user
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db(transaction=True)


def _world(slug):
    makerspace = space(slug)
    makerspace.enabled_modules = sorted(set(makerspace.enabled_modules or []) | {"membership"})
    makerspace.save(update_fields=["enabled_modules"])
    features_on(makerspace, "minors")
    CommunityPolicy.objects.create(makerspace=makerspace, minors_admitted=True)
    staff, child = manager(makerspace, f"{slug}-staff"), user(f"{slug}-child")
    minors.publish_terms(staff, makerspace, "I consent.", "v1")
    today = timezone.localdate()
    profile = minors.record_minor(staff, makerspace, child, date_of_birth=today.replace(year=today.year - 15, day=1).isoformat())
    return makerspace, staff, profile


def test_consent_history_lists_every_consent_and_an_older_live_one_can_be_revoked():
    makerspace, staff, profile = _world("hist-a")
    now = timezone.now()
    older = minors.sign_consent(staff, profile, "First Guardian", accepted=True,
                                method=GuardianConsent.Method.STAFF_RECORDED, now=now - timedelta(days=10))
    newer = minors.sign_consent(staff, profile, "Second Guardian", accepted=True,
                                method=GuardianConsent.Method.STAFF_RECORDED, now=now - timedelta(days=1))
    client = authenticated_client(staff)
    url = reverse("admin-minor-consent-record", kwargs={"makerspace_id": makerspace.pk, "profile_id": profile.pk})
    rows = client.get(url).json()
    assert [row["id"] for row in rows] == [newer.pk, older.pk]
    assert rows[1]["signer"] == "First Guardian" and rows[1]["terms_version"] == "v1"
    assert rows[1]["signed_at"] and rows[1]["revoked_at"] is None and rows[1]["is_live"] is True
    revoke = reverse("admin-guardian-consent-revoke", kwargs={"makerspace_id": makerspace.pk, "consent_id": older.pk})
    assert client.post(revoke).status_code == 200
    rows = client.get(url).json()
    assert rows[1]["revoked_at"] and rows[1]["is_live"] is False and rows[0]["is_live"] is True
    assert AuditLog.objects.filter(action="membership.guardian_consent_revoked", target_id=str(older.pk)).exists()


def test_consent_history_is_scoped_to_the_space_and_to_staff_with_manage_members():
    makerspace, staff, profile = _world("hist-b")
    other, other_staff, _other_profile = _world("hist-c")
    url = reverse("admin-minor-consent-record", kwargs={"makerspace_id": makerspace.pk, "profile_id": profile.pk})
    # Another space's staff never read this minor's consents (404, not a list).
    assert authenticated_client(other_staff).get(url).status_code in {403, 404}
    # A member without staff authority is refused.
    assert authenticated_client(profile.user).get(url).status_code in {403, 404}
    # The profile id resolves only inside its own space.
    cross = reverse("admin-minor-consent-record", kwargs={"makerspace_id": other.pk, "profile_id": profile.pk})
    assert authenticated_client(other_staff).get(cross).status_code == 404
