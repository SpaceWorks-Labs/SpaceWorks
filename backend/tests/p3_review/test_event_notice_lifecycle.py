import pytest

from apps.events.notification_envelopes import _emit, new_intent
from apps.events.services_calendar import calendar_event_changed, calendar_registration_changed
from apps.integrations.notification_sources import source_eligible
from tests.p2_events.helpers import account, event, make_staff, registration, space

pytestmark = pytest.mark.django_db


def notice(row, entry, recipient, *, audience="requester", name="registration_approved", kind="events.lifecycle"):
    return _emit(row.makerspace, recipient, audience=audience, event_name=name, source_kind=kind,
        source_id=f"r{entry.pk}" if entry else f"e{row.pk}", intent=new_intent(), event=row,
        registration=entry, rendered={"subject": "Notice", "text": "Current state", "link": ""})


@pytest.mark.parametrize("audience", ["requester", "staff", "member"])
def test_approval_is_invalidated_by_registration_cancellation(audience, monkeypatch):
    home = space(f"review-lifecycle-{audience}")
    row, owner = event(home), account()
    entry = registration(row, owner)
    recipient = owner if audience == "requester" else make_staff(home)
    kind = "events.grant_staff" if audience == "member" else "events.lifecycle"
    monkeypatch.setattr("apps.events.grant_recipients.holds_registration_grant", lambda *_: True)
    envelope = notice(row, entry, recipient, audience=audience, kind=kind)
    assert source_eligible(envelope)
    entry.status = "cancelled"
    entry.save(update_fields=["status"])
    assert not source_eligible(envelope)
    entry.status = "registered"
    entry.save(update_fields=["status"])
    calendar_registration_changed(entry)
    assert not source_eligible(envelope)  # restoration cannot revive an old approval


def test_publication_notice_checks_current_event_and_revision():
    home = space("review-publication")
    row, actor = event(home), make_staff(home)
    envelope = notice(row, None, actor, audience="staff", name="published")
    assert source_eligible(envelope)
    row.status = "cancelled"
    row.save(update_fields=["status"])
    assert not source_eligible(envelope)
    row.status = "published"
    row.save(update_fields=["status"])
    calendar_event_changed(row)
    assert not source_eligible(envelope)
    assert source_eligible(notice(row, None, actor, audience="staff", name="published"))


def test_owner_change_invalidates_notice():
    home = space("review-owner")
    row, owner = event(home), account()
    entry = registration(row, owner)
    envelope = notice(row, entry, owner)
    entry.member = account("other-owner")
    entry.save(update_fields=["member"])
    assert not source_eligible(envelope)
