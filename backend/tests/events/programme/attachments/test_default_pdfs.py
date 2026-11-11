"""Real owner/source/endpoint rows; storage and providers are explicit fakes."""
from datetime import timedelta
import hashlib
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from django.utils import timezone
from apps.integrations.models import NotificationPreference as Matrix
from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.notification_delivery import ensure_deliveries, send
from apps.integrations.notification_providers import PROVIDERS, ProviderResult
from apps.notifications.models_preferences import NotificationPreference
from tests.billing_docs.conftest import document, document_mail  # noqa: F401
from tests.p2_n_other.conftest import lane, payment  # noqa: F401

pytestmark = pytest.mark.django_db


class DocumentChat:
    def __init__(self):
        self.documents, self.texts = [], []

    def send_document(self, delivery, **kwargs):
        self.documents.append(kwargs)
        return ProviderResult(True, "private-document")

    def send(self, delivery, rendered):
        self.texts.append(rendered)
        return ProviderResult(True, "private-navigation")


def test_payment_receipt_stays_default_on_with_events_tombstoned(lane, document, document_mail, monkeypatch, settings):
    settings.TOMBSTONED_APPS = frozenset({"events"})
    chat = DocumentChat()
    monkeypatch.setitem(PROVIDERS, ("telegram", "telegram"), lambda _: chat)
    envelope = NotificationEnvelope.objects.get(source_kind="payments.document", source_id=str(document.pk))
    ensure_deliveries(envelope)
    delivery = envelope.deliveries.get(channel="telegram")
    send(delivery.pk)
    send(delivery.pk)
    assert len(chat.documents) == 1 and chat.texts == []
    assert chat.documents[0]["pdf_bytes"].startswith(b"%PDF-")


@pytest.fixture
def certificate(lane, monkeypatch):
    from apps.events.models import Event, EventRegistration, EventFeedbackSurvey, EventFeedbackResponse
    from apps.events.services_certificates import create_pending, render_certificate
    lane.space.enabled_modules = sorted(set(lane.space.enabled_modules or []) | {"events", "notifications", "telegram"})
    lane.space.save(update_fields=["enabled_modules"])
    now = timezone.now()
    event = Event.objects.create(makerspace=lane.space, title="Workshop", starts_at=now + timedelta(days=1),
        ends_at=now + timedelta(days=1, hours=2), status="published", created_by=lane.manager)
    registration = EventRegistration.objects.create(event=event, member=lane.owner, status="attended",
        name="Member", email=lane.owner.email, phone="+919876543210")
    survey = EventFeedbackSurvey.objects.create(event=event, title="Feedback", questions=[{"id": "comment", "label": "Your feedback", "type": "paragraph",
            "options": [], "required": False}], certificate_enabled=True)
    response = EventFeedbackResponse.objects.create(survey=survey, registration=registration,
        answers_snapshot='{"version":1,"answers":[]}', certificate_requested=True)
    pdf = b"%PDF-1.7\nimmutable-private-certificate"
    monkeypatch.setattr("apps.events.services_certificates.render_certificate_pdf", lambda _: pdf)
    monkeypatch.setattr("apps.events.services_certificates.store_immutable_pdf",
        lambda key, value: (len(value), hashlib.sha256(value).hexdigest()))
    Matrix.objects.update_or_create(makerspace=lane.space, feature="events", channel="telegram", defaults={"enabled": True})
    NotificationPreference.objects.update_or_create(makerspace=lane.space, user=lane.owner, category="events",
        defaults={"channels": ["telegram"], "email_fallback": False})
    row = render_certificate(create_pending(response))
    monkeypatch.setattr("boto3.client", lambda *a, **kw: SimpleNamespace(get_object=lambda **kwargs:
        {"ContentLength": len(pdf), "Body": BytesIO(pdf)}))
    return row


def test_fresh_certificate_ready_attaches_immutable_owner_pdf(lane, certificate, monkeypatch):
    chat = DocumentChat()
    monkeypatch.setitem(PROVIDERS, ("telegram", "telegram"), lambda _: chat)
    envelope = NotificationEnvelope.objects.get(source_kind="events.certificate", source_id=str(certificate.pk),
        event="certificate_ready")
    ensure_deliveries(envelope)
    delivery = envelope.deliveries.get(channel="telegram")
    send(delivery.pk)
    send(delivery.pk)
    assert len(chat.documents) == 1 and chat.texts == []
    assert hashlib.sha256(chat.documents[0]["pdf_bytes"]).hexdigest() == certificate.sha256


@pytest.mark.parametrize("change", ["wrong_owner", "wrong_tenant", "revision", "restricted", "revoked"])
def test_live_certificate_attachment_rejects_owner_scope_revision_or_standing(lane, certificate, change):
    from apps.integrations.notification_attachment_sources import AttachmentReference, DocumentDeliveryError, authorized_attachment
    recipient, space, revision = lane.owner.pk, lane.space.pk, str(certificate.revision)
    if change == "wrong_owner":
        recipient = lane.manager.pk
    elif change == "wrong_tenant":
        space += 99999
    elif change == "revision":
        revision = str(certificate.revision + 1)
    elif change == "restricted":
        lane.owner.access_status = "restricted"
        lane.owner.save(update_fields=["access_status"])
    else:
        from apps.events.services_certificates import revoke
        revoke(certificate, actor=lane.manager, reason="staff_revoked")
    with pytest.raises(DocumentDeliveryError):
        authorized_attachment(AttachmentReference("events.certificate", certificate.pk, "certificate", revision),
            makerspace_id=space, recipient_id=recipient)


def test_collaborative_notification_provenance_can_read_only_its_attendees_certificate(lane, certificate):
    from apps.events.models import EventRegistration
    from apps.integrations.notification_attachment_sources import AttachmentReference, authorized_attachment
    from tests.return_helpers import make_space
    origin = make_space("certificate-collaboration-origin")
    origin.enabled_modules = sorted(set(origin.enabled_modules or []) | {"events"})
    origin.save(update_fields=["enabled_modules"])
    # Registering via a partner space implies the attendee belongs to it; the owner
    # query authorizes the certificate through that live origin membership.
    from tests.events.collab_helpers import make_member
    make_member(origin, user=lane.owner)
    EventRegistration.objects.filter(pk=certificate.registration_id).update(registered_via_makerspace=origin)
    document = authorized_attachment(AttachmentReference("events.certificate", certificate.pk, "certificate",
        str(certificate.revision)), makerspace_id=origin.pk, recipient_id=lane.owner.pk)
    assert document.event_id == certificate.registration.event_id
    assert document.makerspace_id == origin.pk and document.owner_member_id == lane.owner.pk
