"""Canonical source-backed intents layered onto the shared real HTTP fixture."""
from uuid import NAMESPACE_URL, uuid4, uuid5
from unittest.mock import Mock

from apps.integrations.models_contract import NotificationDelivery
from apps.integrations.notification_delivery import ensure_deliveries
from apps.integrations.notification_outbox import emit
from apps.integrations.notification_sources import SOURCES, NotificationSource
from apps.makerspaces.models import MakerspaceMembership
from apps.notifications.models_inbox import NotificationInboxRow
from apps.notifications.models_preferences import NotificationPreference
from apps.payments.models import Payment


def install_envelopes(case, monkeypatch, capture):
    case.source_active = True
    case.rendered = {"subject": "Your booking", "text": case.summary,
                     "link": f"/m/{case.space.slug}/member"}
    # A real, same-tenant subject: Payment.full_clean validates the subject and the
    # lowercase ISO currency before any notification source can reference it.
    membership = MakerspaceMembership.objects.get(makerspace=case.space, user=case.user)
    case.charge = Payment.objects.create(makerspace=case.space, member=case.user,
        created_by=case.user, provider="unclaimed", subject_type="makerspace_membership",
        subject_id=membership.pk, amount="10.00", currency="inr")
    monkeypatch.setitem(SOURCES, "test.push", NotificationSource(
        eligible=lambda e: case.source_active and Payment.objects.filter(
            pk=e.source_id, member_id=e.recipient_id, makerspace_id=e.makerspace_id).exists(),
        render=lambda e: dict(case.rendered),
    ))
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", Mock())
    case.parent_queue = Mock()
    monkeypatch.setattr("apps.integrations.notification_tasks.deliver_envelope.delay", case.parent_queue)
    NotificationPreference.objects.create(makerspace=case.space, user=case.user,
        category="bookings", channels=["native_push", "in_app"], email_fallback=False)

    def prepare(*, inbox=True, key=None, audience="member", scope=None):
        dedup = f"test-push:{key or uuid4()}"
        with capture(execute=True):
            envelope = emit(makerspace=case.space, recipient=case.user, feature="bookings",
                stream="bookings", event="confirmed", audience=audience, dedup_key=dedup,
                source_kind="test.push", source_id=str(case.charge.pk), scope=scope,
                rendered=case.rendered)
        ensure_deliveries(envelope)
        parent = NotificationDelivery.objects.get(envelope=envelope, channel="native_push")
        row = None
        if inbox:
            row, _ = NotificationInboxRow.objects.get_or_create(makerspace=case.space,
                user=case.user, event_key=uuid5(NAMESPACE_URL, dedup), defaults={
                    "feature": envelope.feature, "event": envelope.event, "audience": "member",
                    "title": case.rendered["subject"], "summary": case.rendered["text"],
                    "link": case.rendered["link"]})
        case.envelope, case.parent, case.inbox = envelope, parent, row
        return parent

    case.prepare = prepare
