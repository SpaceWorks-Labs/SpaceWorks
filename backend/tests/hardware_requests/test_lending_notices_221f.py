"""Decision 221(f): lending notices through the one pipeline -- renewed, pickup expiring, returns.

A renewal tells the borrower the new due date (and staff only when the borrower renewed
themselves); an accepted request nearing its pickup deadline gets exactly one reminder bound to
that deadline; the return confirmation words partial and closed-with-issue returns differently.
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.hardware_requests import pickup_reminders
from apps.hardware_requests.models import HardwareRequest
from apps.hardware_requests.notifications_loans import eligible_renewal, notify_renewed
from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.notification_catalog import FEATURE_EVENTS
from apps.integrations.notification_catalog_sources import EVENT_SOURCES
from tests.hardware_requests.loan_policy_helpers import setup_loan

pytestmark = pytest.mark.django_db(transaction=True)


def envelopes(event, **filters):
    return list(NotificationEnvelope.objects.filter(feature="hardware_requests", event=event, **filters)
                .order_by("pk"))


def test_new_lending_types_are_catalogued_and_mapped_to_their_capability():
    assert {"renewed", "pickup_expiring", "repair_closed"} <= set(FEATURE_EVENTS["hardware_requests"])
    assert EVENT_SOURCES[("hardware_requests", "renewed")] == "loans.renewals"
    assert EVENT_SOURCES[("hardware_requests", "pickup_expiring")] == "loans.pickup_windows"


def test_a_member_renewal_tells_the_borrower_and_staff_once_per_new_due_date():
    space, member, _membership, _product, loan, _policy, client = setup_loan("n221-renew")
    response = client.post(f"/api/v1/member/makerspaces/{space.pk}/loans/{loan.pk}/renew", {}, format="json")
    assert response.status_code == 200
    rows = envelopes("renewed")
    assert [row.recipient_id for row in rows if row.audience == "requester"] == [member.pk]
    assert all(row.source_id == str(loan.pk) for row in rows)
    loan.refresh_from_db()
    assert loan.return_due_at.strftime("%Y-%m-%d") in rows[0].message_body
    notify_renewed(loan, by_staff=False)  # the same revision reserves the same intent
    assert len(envelopes("renewed")) == len(rows)


def test_a_staff_renewal_tells_the_borrower_only():
    from tests.return_helpers import make_member
    space, member, _m, _p, loan, _policy, client = setup_loan("n221-staff-renew", linked=False)
    client.force_authenticate(make_member("n221-staff-renew-mgr", space))
    assert client.post(f"/api/v1/admin/makerspace/{space.pk}/loans/{loan.pk}/renew", {}, format="json").status_code == 200
    assert {row.audience for row in envelopes("renewed")} == {"requester"}


def test_a_renewal_notice_is_stale_once_the_loan_was_renewed_again_or_returned():
    space, member, _m, _p, loan, _policy, _client = setup_loan("n221-stale")
    loan.renewal_count = 1
    loan.save(update_fields=["renewal_count"])
    notify_renewed(loan, by_staff=True)
    envelope = envelopes("renewed", audience="requester")[0]
    assert eligible_renewal(envelope)
    HardwareRequest.objects.filter(pk=loan.pk).update(renewal_count=2)
    assert not eligible_renewal(envelope)
    HardwareRequest.objects.filter(pk=loan.pk).update(renewal_count=1, status="returned")
    assert not eligible_renewal(envelope)


def accepted(loan, *, window, left):
    now = timezone.now()
    HardwareRequest.objects.filter(pk=loan.pk).update(
        status="accepted", accepted_at=now - (window - left), pickup_until=now + left)
    return HardwareRequest.objects.get(pk=loan.pk)


def test_pickup_reminder_goes_out_once_when_the_deadline_is_near():
    space, member, _m, _p, loan, _policy, _client = setup_loan("n221-pickup", linked=False)
    space.enabled_features = sorted(set(space.enabled_features) | {"loans.pickup_windows"})
    space.save(update_fields=["enabled_features"])
    row = accepted(loan, window=timedelta(days=3), left=timedelta(hours=20))
    assert pickup_reminders.remind_expiring_pickups()["reminded"] == 1
    rows = envelopes("pickup_expiring")
    assert [r.recipient_id for r in rows] == [member.pk]
    assert pickup_reminders.remind_expiring_pickups()["reminded"] == 0  # same deadline: same intent
    assert len(envelopes("pickup_expiring")) == 1
    assert pickup_reminders.eligible(rows[0])
    HardwareRequest.objects.filter(pk=row.pk).update(pickup_until=row.pickup_until + timedelta(hours=1))
    assert not pickup_reminders.eligible(rows[0])  # a moved deadline is a new reminder


def test_a_far_deadline_is_not_reminded_and_a_short_window_reminds_at_half():
    space, _member, _m, _p, loan, _policy, _client = setup_loan("n221-pickup-far", linked=False)
    space.enabled_features = sorted(set(space.enabled_features) | {"loans.pickup_windows"})
    space.save(update_fields=["enabled_features"])
    accepted(loan, window=timedelta(days=5), left=timedelta(days=4))
    assert pickup_reminders.remind_expiring_pickups()["reminded"] == 0
    row = accepted(loan, window=timedelta(hours=10), left=timedelta(hours=6))
    assert pickup_reminders.lead_for(row) == timedelta(hours=5)
    assert pickup_reminders.remind_expiring_pickups()["reminded"] == 0
    accepted(loan, window=timedelta(hours=10), left=timedelta(hours=4))
    assert pickup_reminders.remind_expiring_pickups()["reminded"] == 1


def test_pickup_reminders_are_silent_with_the_capability_off():
    space, _member, _m, _p, loan, _policy, _client = setup_loan("n221-pickup-off", linked=False)
    space.enabled_features = sorted(set(space.enabled_features) - {"loans.pickup_windows"})
    space.save(update_fields=["enabled_features"])
    accepted(loan, window=timedelta(days=3), left=timedelta(hours=2))
    assert pickup_reminders.remind_expiring_pickups()["reminded"] == 0
    assert not envelopes("pickup_expiring")


@pytest.mark.parametrize("status,phrase", [
    ("partially_returned", "partial return"),
    ("closed_with_issue", "closed with an issue"),
    ("returned", "returned and closed"),
])
def test_return_confirmation_wording_follows_the_outcome(status, phrase):
    from apps.integrations.email_templates import hardware_context, render
    space, _member, _m, _p, loan, _policy, _client = setup_loan(f"n221-ret-{status}", linked=False)
    HardwareRequest.objects.filter(pk=loan.pk).update(status=status)
    loan.refresh_from_db()
    message = render(space, "hardware", "requester", "request_returned", hardware_context(loan, staff=False))
    assert phrase in message["text_body"]
