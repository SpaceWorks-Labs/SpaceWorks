"""Delete a draft event that never took part in any money or registration (parity E-B5, B9).

A published or cancelled event is never deleted: its history, charges and evidence belong to the audit
trail, so staff cancel it instead. A draft may go only while nothing refers to it: no registration, no
ticket order, no payment of any kind. The public cover image is released after commit, so the managed
storage allowance is freed. The audit row is written first and carries ids only.
"""
from django.db.models import ProtectedError

from apps.audit import services as audit
from apps.inventory import public_image_storage
from apps.payments.models import Payment

from .exceptions import EventInvalidTransition
from .models import Event, EventRegistration
from .models_orders import EventOrder
from .services_write_boundary import event_write

REFUSAL = ("Only an empty draft can be deleted. Cancel the event instead: it has been published, or it "
           "holds registrations, orders or charges.")


def blockers(event):
    """Why this event cannot be deleted, as short machine codes (empty = deletable)."""
    found = []
    if event.status != Event.Status.DRAFT:
        found.append("not_draft")
    if EventRegistration.objects.filter(event=event).exists():
        found.append("registrations")
    if EventOrder.objects.filter(event=event).exists():
        found.append("orders")
    registration_ids = EventRegistration.objects.filter(event=event).values("pk")
    order_ids = EventOrder.objects.filter(event=event).values("pk")
    owed = Payment.objects.filter(makerspace=event.makerspace).filter(
        subject_type=Payment.SubjectType.EVENT_REGISTRATION, subject_id__in=registration_ids,
    ) | Payment.objects.filter(
        makerspace=event.makerspace, subject_type=Payment.SubjectType.EVENT_ORDER, subject_id__in=order_ids,
    )
    if owed.exists():
        found.append("charges")
    return found


@event_write(permission="edit_details")
def delete_draft(event, *, actor):
    found = blockers(event)
    if found:
        raise EventInvalidTransition(REFUSAL)
    makerspace, event_id, image_key = event.makerspace, event.pk, event.image_key
    audit.record(actor, "event.deleted", makerspace=makerspace, target=event,
                 meta={"series_id": event.series_id})
    from apps.operations.models_saved_views import SavedView
    SavedView.objects.filter(makerspace=makerspace, state__event=str(event_id)).delete()  # its own saved filters
    try:
        event.delete()
    except ProtectedError as exc:  # another record still points at it: refuse rather than half-delete
        raise EventInvalidTransition(REFUSAL) from exc
    if image_key:
        public_image_storage.release_public_image_on_commit(makerspace, image_key)
    return event_id
