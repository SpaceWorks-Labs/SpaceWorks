import pytest
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.makerspaces.models import AccountProfile, AccountTimelineEntry, MakerspaceMembership, MemberProfile
from apps.audit.models import AuditLog

pytestmark = pytest.mark.django_db


def test_profile_patch_handle_and_timeline_crud(membership):
    client = APIClient(); client.force_authenticate(user=membership.user)
    base = f"/api/v1/member/makerspaces/{membership.makerspace_id}/profile"
    assert client.get(base).status_code == 200
    assert not MemberProfile.objects.filter(membership=membership).exists()
    assert not AccountProfile.objects.filter(user=membership.user).exists()  # a read never creates the row
    response = client.patch(base, {"public_visible": True, "publication_consent": True,
        "domains": ["Robotics"], "skills": [{"name": "Python", "level": 3}],
        "links": [{"kind": "github", "url": "https://github.com/example"}]}, format="json")
    assert response.status_code == 200, response.data
    # Decision 549: master consent fields are retired; content still round-trips exactly.
    assert response.data["domains"] == ["Robotics"]
    assert response.data["skills"] == [{"name": "Python", "level": 3}]
    assert response.data["links"] == [{"kind": "github", "url": "https://github.com/example"}]
    assert {"public_visible", "public_consented_at", "publication_consent", "is_visible"}.isdisjoint(response.data)
    assert client.post(base + "/handle", {"handle": "self.maker"}, format="json").status_code == 200
    created = client.post(base + "/timeline", {"kind": "experience", "title": "Maker",
        "organization": "Lab", "start": "2025-01-01"}, format="json")
    assert created.status_code == 201, created.data
    detail = base + f"/timeline/{created.data['id']}"
    assert client.get(detail).status_code == 200
    invalid = client.patch(detail, {"end": "2024-01-01"}, format="json")
    assert invalid.status_code == 400
    assert invalid.data["end"][0].code == "invalid"
    assert client.patch(detail, {"title": "Senior maker"}, format="json").status_code == 200
    assert client.get(base + "/timeline").data["count"] == 1
    assert client.delete(detail).status_code == 204
    assert client.delete(base + "/handle").status_code == 204
    actions = set(AuditLog.objects.filter(actor=membership.user).values_list("action", flat=True))
    assert {"member.public_handle_claimed", "member.public_handle_released",
            "member.profile_timeline_created", "member.profile_timeline_updated",
            "member.profile_timeline_deleted"} <= actions
    assert all("Senior maker" not in str(meta) for meta in AuditLog.objects.filter(
        actor=membership.user).values_list("meta", flat=True))


def test_timeline_is_scoped_to_authenticated_membership(membership):
    profile = AccountProfile.objects.create(user=membership.user)
    entry = AccountTimelineEntry.objects.create(profile=profile, kind="education", title="Private", start="2025-01-01")
    other = User.objects.create_user(username="other-timeline-owner")
    MakerspaceMembership.objects.create(user=other, makerspace=membership.makerspace, assigned_role=membership.makerspace.roles.get(slug="member"), role="custom")
    client = APIClient(); client.force_authenticate(user=other)
    path = f"/api/v1/member/makerspaces/{membership.makerspace_id}/profile/timeline/{entry.pk}"
    for response in (client.get(path), client.patch(path, {"title": "Stolen"}, format="json"), client.delete(path)):
        assert response.status_code == 404
        assert response.data["code"] == "not_found"
