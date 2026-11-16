"""Decision 223 (k), lane L3b: the attendee to guest to member join funnel (prefill, follow-up notice, report)."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.events import join_followup
from apps.events.models import EventRegistration
from apps.makerspaces import guest_pass_issue, join_funnel
from apps.makerspaces.community_policy import CommunityError
from apps.makerspaces.models import CommunityPolicy, MakerspaceMembership
from apps.makerspaces.reports_join_funnel import build_join_funnel
from tests.events.checkin_helpers import make_event, register
from tests.makerspaces.l4_helpers import features_off, features_on
from tests.makerspaces.test_guest_passes import _space, _sponsor
from tests.makerspaces.test_membership_j1 import manager, member_role, user

pytestmark = pytest.mark.django_db(transaction=True)


def _world(slug, *, funnel=True):
    makerspace = _space(slug)
    makerspace.enabled_modules = sorted(set(makerspace.enabled_modules or []) | {"events"})
    makerspace.save(update_fields=["enabled_modules"])
    if funnel:
        features_on(makerspace, "join_funnel")
    return makerspace


def _attended(makerspace, person, *, ended_hours_ago=48):
    event = make_event(makerspace, starts_at=timezone.now() - timedelta(hours=ended_hours_ago + 2),
                       ends_at=timezone.now() - timedelta(hours=ended_hours_ago))
    return register(event, person, status=EventRegistration.Status.ATTENDED)


def test_prefill_from_an_attended_registration_and_from_a_guest_pass_and_refusals():
    makerspace = _world("jf-prefill")
    guest = user("jf-guest")
    registration = _attended(makerspace, guest)
    found = join_funnel.join_prefill(guest, makerspace, registration_id=registration.pk)
    assert found["source"] == "event" and found["source_ref"] == registration.pk and found["email"] == guest.email
    row, _ = guest_pass_issue.issue_staff_pass(manager(makerspace), makerspace, guest)
    assert join_funnel.join_prefill(guest, makerspace, guest_pass_id=row.pk)["source"] == "guest_pass"
    with pytest.raises(CommunityError) as other:
        join_funnel.join_prefill(user("jf-other"), makerspace, registration_id=registration.pk)
    assert other.value.error_code == "source_not_found"
    MakerspaceMembership.objects.create(makerspace=makerspace, user=guest, assigned_role=member_role(makerspace),
                                        role="custom", status="active")
    with pytest.raises(CommunityError) as already:
        join_funnel.join_prefill(guest, makerspace, registration_id=registration.pk)
    assert already.value.error_code == "already_member"


def test_prefill_is_off_with_the_switch():
    makerspace = _world("jf-off", funnel=False)
    guest = user("jf-off-guest")
    registration = _attended(makerspace, guest)
    with pytest.raises(CommunityError) as refused:
        join_funnel.join_prefill(guest, makerspace, registration_id=registration.pk)
    assert refused.value.error_code == "join_funnel_off"


def test_funnel_counts_attendees_guests_and_joiners():
    makerspace = _world("jf-counts")
    visitor, guest, joiner = user("jf-visitor"), user("jf-guest2"), user("jf-joiner")
    for person in (visitor, guest, joiner):
        _attended(makerspace, person)
    guest_pass_issue.issue_staff_pass(manager(makerspace), makerspace, guest)
    MakerspaceMembership.objects.create(makerspace=makerspace, user=joiner, assigned_role=member_role(makerspace),
                                        role="custom", status="active", activated_at=timezone.now())
    assert join_funnel.funnel_counts(makerspace) == {"attendees": 3, "guests": 1, "joined": 1}
    result = build_join_funnel(makerspace.pk)
    assert result.records[0]["attendees"] == 3 and result.records[0]["join_rate_percent"] == 33.3
    features_off(makerspace, "join_funnel")
    assert build_join_funnel(makerspace.pk).records == []


def test_followup_goes_once_to_non_member_attendees_of_an_opted_in_space(monkeypatch):
    makerspace = _world("jf-followup")
    CommunityPolicy.objects.create(makerspace=makerspace, join_followup_enabled=True, join_followup_delay_hours=24)
    visitor, member = user("jf-f-visitor"), _sponsor(makerspace, "jf-f-member")
    _attended(makerspace, visitor, ended_hours_ago=30)
    _attended(makerspace, member, ended_hours_ago=30)
    _attended(makerspace, user("jf-f-recent"), ended_hours_ago=1)  # inside the delay: not yet
    sent = []
    monkeypatch.setattr(join_followup, "notify_join_followup", lambda row: sent.append(row.member_id))
    assert join_followup.send_join_followups() == 1 and sent == [visitor.pk]
    CommunityPolicy.objects.filter(makerspace=makerspace).update(join_followup_enabled=False)
    assert join_followup.send_join_followups() == 0
