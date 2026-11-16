"""Decision 510: document recovery cannot change other callers' deduplication."""
import pytest
from django.utils import timezone

from apps.integrations.models import EmailLog, NotificationPreference as Matrix
from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.notification_tasks import deliver_envelope
from apps.notifications.models_preferences import NotificationPreference
from tests.billing_docs.test_email_recovery import set_switch

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("event", ["joined", "verified"])
@pytest.mark.parametrize("routed", [False, True])
def test_membership_same_key_disabled_skip_stays_terminal_after_reenable(
        lane, event, routed, django_capture_on_commit_callbacks, mailoutbox):
    from apps.audit.services import record
    from apps.makerspaces.notifications_p2_members import notify_member
    Matrix.objects.update_or_create(makerspace=lane.space, feature="members", channel="email",
                                    defaults={"enabled": routed})
    NotificationPreference.objects.filter(makerspace=lane.space, user=lane.owner,
                                          category="members").update(channels=["email"], email_fallback=False)
    if event == "verified":
        lane.membership.verified_at = timezone.now()
        lane.membership.verified_by = lane.manager
        lane.membership.save(update_fields=["verified_at", "verified_by"])
        record(lane.manager, "membership.verified", makerspace=lane.space, target=lane.membership)
    set_switch(lane.space, "email", False)
    with django_capture_on_commit_callbacks(execute=True):
        notify_member(lane.membership, event, staff=False)
    envelope = NotificationEnvelope.objects.get(source_kind="membership.lifecycle", event=event,
                                                recipient=lane.owner)
    deliver_envelope(envelope.pk)
    logs = EmailLog.objects.filter(event=event, source_id=str(envelope.pk))
    assert logs.count() == 1
    assert (logs.get().status, logs.get().error) == ("skipped", "Email is disabled for this makerspace.")
    history = list(logs.values())
    queued = lane.enqueued.count(envelope.pk)
    set_switch(lane.space, "email", True)
    lane.membership.makerspace.refresh_from_db()
    for _ in range(2):
        with django_capture_on_commit_callbacks(execute=True):
            notify_member(lane.membership, event, staff=False)
        deliver_envelope(envelope.pk)
    assert mailoutbox == []
    assert list(logs.values()) == history
    assert envelope.deliveries.count() == 0
    assert lane.enqueued.count(envelope.pk) == queued


def test_accountless_repair_same_key_disabled_skip_stays_terminal_after_reenable(
        lane, django_capture_on_commit_callbacks, mailoutbox):
    from apps.hardware_requests.models import HardwareRequest, RequesterAccountability
    from apps.maintenance.models import IssueReport
    from apps.maintenance.repairs.loan_borrower_notices import notify_borrower
    from apps.makerspaces.anonymous_requesters import get_or_create_anonymous_requester
    from tests.return_helpers import make_product
    # Repairs requires its maintenance parent; isolate the email switch below.
    set_switch(lane.space, "inventory.maintenance", True)
    set_switch(lane.space, "inventory.repairs", True)
    from apps.integrations.notification_catalog_sources import event_live
    assert event_live(lane.space, "hardware_requests", "repair_closed") is True
    set_switch(lane.space, "email", False)
    principal = get_or_create_anonymous_requester(lane.space)
    loan = HardwareRequest.objects.create(makerspace=lane.space, requester=principal,
        requester_username=principal.username, requester_contact_email="contact-borrower@example.test",
        requester_contact_verified=True, status="closed_with_issue")
    line = RequesterAccountability.objects.create(makerspace=lane.space, request=loan, requester=principal,
        issue_type="damaged", quantity=1, created_by=lane.manager)
    issue = IssueReport.objects.create(makerspace=lane.space, area="inventory", subject_type="inventory_product",
        product=make_product(lane.space), source="loan", loan=loan, return_line=line,
        title="Damaged tool", description="Cracked case", state="fixed")
    with django_capture_on_commit_callbacks(execute=True):
        notify_borrower(issue, "fixed")
    logs = EmailLog.objects.filter(event="repair_closed", makerspace=lane.space)
    assert logs.count() == 1
    skipped = logs.get()
    assert (skipped.status, skipped.error, skipped.recipient_id, skipped.to_email) == (
        "skipped", "Email is disabled for this makerspace.", None, "contact-borrower@example.test")
    history = list(logs.values())
    set_switch(lane.space, "email", True)
    issue.makerspace.refresh_from_db()
    for _ in range(2):
        with django_capture_on_commit_callbacks(execute=True):
            notify_borrower(issue, "fixed")
    assert mailoutbox == [] and list(logs.values()) == history
    assert NotificationEnvelope.objects.filter(source_kind="maintenance.repair_borrower").count() == 0
