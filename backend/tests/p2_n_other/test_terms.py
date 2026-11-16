from datetime import timedelta

import pytest
from django.utils import timezone

from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.notification_sources import source_eligible
from apps.makerspaces.models import MembershipPlan, MembershipTerm
from apps.makerspaces.membership_renewal_notifications import notify_membership, notify_term

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("event", ["renewal_due", "lapsed", "renewal_failed", "renewed", "grace_started", "cancelled"])
def test_term_rows_are_personal_only_and_revoke_with_membership(lane, event):
    now = timezone.now()
    plan = MembershipPlan.objects.create(makerspace=lane.space, name="Annual", amount="0", interval="yearly")
    term = MembershipTerm.objects.create(membership=lane.membership, plan=plan,
        starts_at=now-timedelta(days=400), ends_at=now-timedelta(days=1), renewal_attempts=1)
    if event == "renewed":
        term = MembershipTerm.objects.create(membership=lane.membership, plan=plan,
            starts_at=now-timedelta(days=1), ends_at=now+timedelta(days=30), renewed_from=term)
    if event == "grace_started":
        term.grace_until = now+timedelta(days=1)
        term.save(update_fields=["grace_until"])
    if event == "cancelled":
        lane.membership.renewal_cancelled_at = now
        lane.membership.save(update_fields=["renewal_cancelled_at"])
        notify_membership(lane.membership, event)
    else:
        notify_term(term, event)
    envelope = lane.deliver(event)
    assert source_eligible(envelope)
    assert not NotificationEnvelope.objects.filter(audience="staff").exists()
    lane.membership.status = "revoked"
    lane.membership.save(update_fields=["status"])
    assert not source_eligible(envelope)


def test_cancelled_renewal_suppresses_queued_failure(lane):
    now = timezone.now()
    plan = MembershipPlan.objects.create(makerspace=lane.space, name="Monthly", amount="0", interval="monthly")
    term = MembershipTerm.objects.create(membership=lane.membership, plan=plan,
        starts_at=now-timedelta(days=30), ends_at=now, renewal_attempts=1)
    notify_term(term, "renewal_failed")
    envelope = NotificationEnvelope.objects.get()
    lane.membership.renewal_cancelled_at = now
    lane.membership.save(update_fields=["renewal_cancelled_at"])
    assert not source_eligible(envelope)
