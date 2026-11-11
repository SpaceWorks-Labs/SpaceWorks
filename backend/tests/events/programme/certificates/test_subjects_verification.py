from datetime import timedelta
from uuid import uuid4
import pytest
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.events.certificates.issuance import create_for_subject_locked
from apps.events.certificates.preparation import prepare_issuance
from apps.events.certificates.models import EventCertificatePublicationPolicy
from apps.events.certificates.subjects import require_read
from apps.events.certificates.verification import project
from apps.events.credentials.boundary import event_command
from apps.events.models_certificates import EventAttendanceCertificate
from tests.events.checkin_helpers import make_space, make_event, make_member, make_staff, register

pytestmark = pytest.mark.django_db(transaction=True)


def certificate():
    space = make_space("programme-cert-verify")
    event = make_event(space, starts_at=timezone.now()-timedelta(days=4), ends_at=timezone.now()-timedelta(days=3),
                       status="completed", is_public=False)
    member = make_member(space)
    registration = register(event, member, status="attended")
    EventCertificatePublicationPolicy.objects.create(event=event, enabled=True)
    prepared = prepare_issuance(event.pk, [{"subject_kind": "registration", "subject_id": registration.pk}])
    with event_command(event.pk, account_ids=prepared.account_ids, revalidate=prepared.revalidate) as (locked, _):
        row = create_for_subject_locked(locked, subject_kind="registration", subject_id=registration.pk, prepared=prepared)
    # Transition through the same state shape as the renderer, without object I/O.
    row.status = "rendering"; row.save(update_fields=("status",))
    row.status = "active"; row.save(update_fields=("status",))
    return event, member, row


def test_private_ended_event_verifies_only_explicit_event_date_status_without_identity():
    event, member, row = certificate()
    result = project(row.serial)
    # r2-idcards-best C9: issuer, kind, award, note, serial and the PDF fingerprint are public too;
    # the holder's name only after they opt in.
    assert set(result) == {"event", "date", "status", "issuer", "kind", "kind_title", "award", "recipient_name",
                           "status_note", "serial", "sha256"} and result["status"] == "valid"
    assert result["recipient_name"] is None
    assert member.email not in str(result) and member.display_name not in str(result)
    row.status, row.revoked_at, row.revocation_reason = "revoked", timezone.now(), "staff_revoked"
    row.save(update_fields=("status", "revoked_at", "revocation_reason"))
    assert project(row.serial)["status"] == "revoked"


def test_unknown_private_pending_and_withdrawn_publication_all_refuse_uniformly():
    event, member, row = certificate()
    with pytest.raises(NotFound):
        project(uuid4())
    row.public_verification_enabled = False
    row.save(update_fields=("public_verification_enabled",))
    with pytest.raises(NotFound):
        project(row.serial)
    row.public_verification_enabled = True
    row.save(update_fields=("public_verification_enabled",))
    EventCertificatePublicationPolicy.objects.filter(event=event).update(enabled=False)
    with pytest.raises(NotFound):
        project(row.serial)


def test_private_download_requires_exact_owner_or_full_manager():
    event, member, row = certificate()
    require_read(row, member)
    other = make_member(event.makerspace, "other-certificate-member")
    with pytest.raises(PermissionDenied):
        require_read(row, other)
    require_read(row, make_staff(event.makerspace))


def test_bulk_attendance_creates_no_synthetic_feedback_and_retries_reuse_certificate():
    event, member, row = certificate()
    assert row.response_id is None
    prepared = prepare_issuance(event.pk, [{"subject_kind": "registration", "subject_id": row.registration_id}])
    with event_command(event.pk, account_ids=prepared.account_ids, revalidate=prepared.revalidate) as (locked, _):
        again = create_for_subject_locked(locked, subject_kind="registration", subject_id=row.registration_id, prepared=prepared)
    assert row.pk == again.pk
    assert EventAttendanceCertificate.objects.count() == 1
