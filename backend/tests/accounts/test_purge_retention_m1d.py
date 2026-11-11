"""Deletion removes identity copies while retaining the disclosed evidence ledger."""

import pytest
from django.utils import timezone

from apps.audit import services as audit
from apps.boxes.models import Box, BoxScan
from apps.evidence.models import EvidencePhoto
from apps.events.models import EventAttendanceCertificate, EventFeedbackResponse, EventFeedbackSurvey
from apps.hardware_requests.models import RequesterAccountability, ReturnEvent
from apps.integrations.models import EmailLog, NotificationDeliveryLog
from apps.machines.models import MachineUsageEntry
from apps.makerspaces.models import MemberCard
from apps.payments.models import ManualSettlement, PaymentDocument
from apps.payments.services_refunds_offline import record_offline_refund
from tests.accounts import deletion_factories as f
from tests.accounts.account_factories import make_membership
from tests.accounts.test_support_m1d import account, due, m1d_config, purge
from tests.payments.test_offline_refunds import cash_deposit, payload
from tests.test_machine_service_workflow import machine

pytestmark = pytest.mark.django_db


def test_every_disclosed_retained_record_survives_purge_byte_for_byte():
    tenant, staff, payment = cash_deposit("m1d-retained")
    user = due(payment.member)
    refund = record_offline_refund(payment, actor=staff, **payload("10.00"))
    settlement = ManualSettlement.objects.get(payment=payment)
    # Offline settlement already issued the immutable receipt in this integration.
    document = PaymentDocument.objects.get(settlement=settlement, kind="receipt")
    hardware = f.request(user, tenant)
    evidence = EvidencePhoto.objects.create(makerspace=tenant, uploaded_by=user,
        evidence_type="return", object_key="evidence/m1d-retained.jpg")
    box = Box.objects.create(makerspace=tenant, label="Evidence box")
    scan = BoxScan.objects.create(makerspace=tenant, box=box, request=hardware, actor=staff, context="return")
    returned = ReturnEvent.objects.create(makerspace=tenant, request=hardware, evidence=evidence,
        box=box, remark="Returned with a scratch", actor=staff)
    accountability = RequesterAccountability.objects.create(makerspace=tenant, request=hardware,
        requester=user, issue_type="damaged", description="Historical resolved damage", quantity=1,
        evidence_photo=evidence, created_by=staff)
    job = f.service_job(user, tenant, status="collected")
    usage = MachineUsageEntry.objects.create(machine=machine(tenant), service_request=job, logged_by=user,
        requester_name="Private historical snapshot", contact_email=user.email, contact_phone="123", note="Retained")
    registration = f.registration(user, tenant, status="attended")
    event = registration.event
    survey = EventFeedbackSurvey.objects.create(event=event, title="Feedback",
        questions=[{"id": "q", "label": "Rating", "type": "number", "options": [], "required": True}])
    feedback = EventFeedbackResponse.objects.create(survey=survey, registration=registration,
        answers_snapshot='{"version":1,"answers":[{"id":"q","value":5}]}', certificate_requested=True)
    certificate = EventAttendanceCertificate.objects.create(response=feedback, registration=registration,
        revision=1, recipient_name="Private historical certificate", event_title=event.title,
        event_starts_at=event.starts_at, event_ends_at=event.ends_at, issuer_name=tenant.name,
        object_key="certificates/m1d-retained.pdf")
    delivery = NotificationDeliveryLog.objects.create(makerspace=tenant, channel="telegram", feature="events",
        event="registered", text_body="Private historical notification", status="sent")
    staff_email = EmailLog.objects.create(makerspace=tenant, recipient=staff, to_email=staff.email,
        subject="Member activity", text_body="Private historical staff notification")
    member = make_membership(user, tenant, status="revoked")
    card = MemberCard.objects.create(membership=member, makerspace=tenant, card_number=1,
        printed_name="", revoked_at=timezone.now(), revoked_reason="account_deletion")
    provenance = {"actor_username": user.username, "actor_display": "Private Person",
                  "source_user_id": str(user.pk), "recorded_at": timezone.now().isoformat()}
    other_membership = make_membership(account(), tenant,
        activated_by=user, activated_actor_snapshot=provenance)
    entry = audit.record(user, "account.retention_test", makerspace=tenant, target=hardware,
        meta={"historical_name": "Private Person"})
    retained = [payment, refund, settlement, document, evidence, scan, returned, accountability,
                usage, feedback, certificate, delivery, staff_email, card, other_membership, entry]
    snapshots = [(row, type(row).objects.filter(pk=row.pk).values().get()) for row in retained]
    assert purge(user)["purged"] == 1
    assert purge(user)["purged"] == 0
    for row, expected in snapshots:
        assert type(row).objects.filter(pk=row.pk).values().get() == expected, row._meta.label
    document.refresh_from_db()
    assert document.payer_label != user.username
    assert document.payer_label == snapshots[3][1]["payer_label"]


def test_member_card_redaction_occurs_at_departure_and_purge_keeps_redacted_row(monkeypatch):
    from apps.accounts.account_deletion import request_deletion
    from tests.accounts.test_support_m1d import proven
    from tests.fixed_roles.helpers import assign_builtin_roles

    user, tenant = account(), f.space()
    membership = assign_builtin_roles(user, tenant, "member")
    card = MemberCard.objects.create(membership=membership, makerspace=tenant, card_number=1,
        printed_name="Private Person", photo_object_key="private/face.jpg", photo_content_type="image/jpeg",
        photo_size_bytes=99, photo_consent_at=timezone.now(), photo_consent_version="v1")
    deleted = []
    monkeypatch.setattr("apps.makerspaces.member_card_storage.delete_photo", lambda row: deleted.append(row.photo_object_key))
    request_deletion(proven(user))
    card.refresh_from_db()
    assert deleted == ["private/face.jpg"] and card.revoked_at
    assert card.printed_name == card.photo_object_key == card.photo_content_type == card.photo_consent_version == ""
    assert card.photo_size_bytes is None and card.photo_consent_at is None
    before = MemberCard.objects.filter(pk=card.pk).values().get()
    user.refresh_from_db()
    due(user)
    assert purge(user)["purged"] == 1
    assert MemberCard.objects.filter(pk=card.pk).values().get() == before
    assert deleted == ["private/face.jpg"]
