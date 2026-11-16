"""Speaker identity: staff assignment, invite claim, audit both ways, history export."""

from datetime import timedelta
from urllib.parse import unquote

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.events.models import EventSpeaker, EventStaffGrant
from apps.events.speaker_history import contributions_for
from apps.events.speaker_identity import assign_speaker, claim_speaker, invite_speaker, remove_speaker
from tests.p2_events.helpers import account, client_for, event, make_member, make_staff, registration, space

pytestmark = pytest.mark.django_db


def _token(url):
    return unquote(url.split("#token=", 1)[1])


def test_staff_assigns_a_member_with_check_in_grant_and_audit():
    home = space("spk-assign")
    staff, member = make_staff(home), make_member(home, "spk-a")
    row = assign_speaker(event(home), actor=staff, user=member, grant_check_in=True)
    assert row.user == member and row.linked_via == "staff_assigned" and row.status == "linked"
    audit = AuditLog.objects.get(action="event.speaker_assigned")
    assert audit.actor == staff and audit.target_id == str(row.pk)
    grant = EventStaffGrant.objects.get(user=member, event=row.event, revoked_at__isnull=True)
    assert grant.permissions == ["check_in"] and grant.role_label == "speaker"


def test_assignment_refuses_accounts_outside_the_event_scope():
    home = space("spk-scope")
    staff, stranger = make_staff(home), account("spk-stranger")
    with pytest.raises(Exception) as exc:
        assign_speaker(event(home), actor=staff, user=stranger)
    assert "user_id" in str(exc.value.detail)
    assert not EventSpeaker.objects.exists()


def test_registrant_without_membership_is_in_scope():
    home = space("spk-registrant")
    staff, guest = make_staff(home), account("spk-guest")
    row = event(home)
    registration(row, guest)
    assert assign_speaker(row, actor=staff, user=guest).user == guest


def test_invite_claim_is_single_use_audited_with_the_claimant():
    home = space("spk-claim")
    staff, claimant = make_staff(home), account("spk-claimant")
    speaker, url = invite_speaker(event(home), actor=staff, name="Dr. Ada", grant_check_in=True)
    assert speaker.status == "invited" and "/speaker-claim#token=" in url and speaker.claim_token_digest
    token = _token(url)
    assert token not in speaker.claim_token_digest
    claimed = claim_speaker(token, actor=claimant)
    assert claimed.user == claimant and claimed.linked_via == "claimed"
    assert AuditLog.objects.get(action="event.speaker_claimed").actor == claimant
    assert AuditLog.objects.get(action="event.speaker_invited").actor == staff
    assert EventStaffGrant.objects.filter(user=claimant, event=speaker.event, revoked_at__isnull=True).exists()
    with pytest.raises(Exception):
        claim_speaker(token, actor=account("spk-second"))


def test_expired_or_removed_invitation_is_not_found():
    home = space("spk-expired")
    staff = make_staff(home)
    speaker, url = invite_speaker(event(home), actor=staff, name="Late")
    EventSpeaker.objects.filter(pk=speaker.pk).update(claim_expires_at=timezone.now() - timedelta(minutes=1))
    with pytest.raises(Exception) as exc:
        claim_speaker(_token(url), actor=account("spk-late"))
    assert getattr(exc.value, "status_code", None) == 404
    other, other_url = invite_speaker(event(home, title="Other"), actor=staff, name="Gone")
    remove_speaker(other, actor=staff)
    with pytest.raises(Exception) as exc:
        claim_speaker(_token(other_url), actor=account("spk-gone"))
    assert getattr(exc.value, "status_code", None) == 404
    assert AuditLog.objects.filter(action="event.speaker_removed").count() == 1


def test_contributions_for_counts_only_published_past_linked_rows_in_the_host():
    home, elsewhere = space("spk-history"), space("spk-elsewhere")
    staff, member = make_staff(home), make_member(home, "spk-h")
    past = event(home, days=-3, title="Past talk")
    future = event(home, days=3, title="Future talk")
    draft = event(home, days=-2, status="draft", title="Draft talk")
    removed = event(home, days=-4, title="Removed talk")
    for row in (past, future, draft, removed):
        assign_speaker(row, actor=staff, user=member)
    remove_speaker(EventSpeaker.objects.get(event=removed), actor=staff)
    history = list(contributions_for(member, home))
    assert [item.event.pk for item in history] == [past.pk]
    assert history[0].role == "speaker" and history[0].occurred_at == past.starts_at
    assert list(contributions_for(member, elsewhere)) == []


def test_api_routes_list_search_assign_invite_remove_and_claim():
    home = space("spk-api")
    staff, member = make_staff(home), make_member(home, "spk-api-member")
    row = event(home)
    client = client_for(staff)
    found = client.get(f"/api/v1/admin/events/{row.pk}/speaker-candidates/?search=spk-api-member")
    assert found.status_code == 200 and [item["id"] for item in found.data["results"]] == [member.pk]
    assert found.data["results"][0]["relation"] == "member" and "email" not in found.data["results"][0]
    created = client.post(f"/api/v1/admin/events/{row.pk}/speakers/", {"user_id": member.pk}, format="json")
    assert created.status_code == 201 and created.data["status"] == "linked"
    invited = client.post(f"/api/v1/admin/events/{row.pk}/speakers/invite/", {"display_name": "Guest"}, format="json")
    assert invited.status_code == 201 and invited.data["claim_url"]
    listing = client.get(f"/api/v1/admin/events/{row.pk}/speakers/")
    assert listing.status_code == 200 and listing.data["count"] == 2
    assert "claim_token_digest" not in str(listing.data)
    removed = client.post(f"/api/v1/admin/event-speakers/{created.data['id']}/remove/", {}, format="json")
    assert removed.status_code == 200 and removed.data["status"] == "removed"
    claimant = account("spk-api-claimant")
    claim = client_for(claimant).post("/api/v1/member/event-speaker-claims/",
                                      {"token": _token(invited.data["claim_url"])}, format="json")
    assert claim.status_code == 200 and claim.data["event"]["id"] == row.pk
    assert client_for(member).get(f"/api/v1/admin/events/{row.pk}/speakers/").status_code in (403, 404)
