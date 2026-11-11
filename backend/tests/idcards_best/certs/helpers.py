"""Local certificate fixtures for the r2-idcards-best certificate parts (never committed)."""
from datetime import timedelta

from django.utils import timezone

from apps.events.certificates.issuance import create_for_subject_locked
from apps.events.certificates.models import EventCertificatePublicationPolicy
from apps.events.certificates.preparation import prepare_issuance
from apps.events.credentials.boundary import event_command
from tests.events.checkin_helpers import make_event, make_member, make_space, register


def ended_event(slug="cert-best", **values):
    space = make_space(slug)
    event = make_event(space, starts_at=timezone.now() - timedelta(days=4),
                       ends_at=timezone.now() - timedelta(days=3), status="completed", **values)
    return space, event


def issue(event, subject_kind, subject_id, *, kind="attendance", award_id=None, result_revision_id=None,
          activate=True):
    prepared = prepare_issuance(event.pk, [{"subject_kind": subject_kind, "subject_id": subject_id, "kind": kind}])
    with event_command(event.pk, account_ids=prepared.account_ids, revalidate=prepared.revalidate) as (locked, _):
        row = create_for_subject_locked(locked, subject_kind=subject_kind, subject_id=subject_id, kind=kind,
                                        award_id=award_id, result_revision_id=result_revision_id,
                                        prepared=prepared)
    if activate:
        row.status = "rendering"
        row.save(update_fields=("status",))
        row.status = "active"
        row.save(update_fields=("status",))
    return row


def attended_certificate(slug="cert-best", *, publish=True, name="Ada Lovelace"):
    space, event = ended_event(slug)
    member = make_member(space, display_name=name)
    registration = register(event, member, status="attended")
    if publish:
        EventCertificatePublicationPolicy.objects.create(event=event, enabled=True)
    return event, member, issue(event, "registration", registration.pk)
