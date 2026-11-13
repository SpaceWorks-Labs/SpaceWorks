"""Event subject policy used by manual reports, saved views and every builder call."""

from django.utils.translation import gettext
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.operations.report_subjects import ReportSubject, register
from . import event_authority
from .event_permissions import MANAGE_REGISTRATIONS, VIEW
from .models import Event

KEYS = ("event-attendance", "event-registrations", "event-feedback", "event-attendance-pdf", "event-orders", "event-equipment",
        "event-consumables", "event-loan-timeline", "event-machine-use")


def resolve(space, pk):
    return get_object_or_404(Event.objects.select_related("makerspace"), makerspace=space, pk=pk)


def authorize(actor, event, definition):
    if definition.key in ("event-equipment", "event-consumables", "event-loan-timeline"):
        event_authority.require(actor, event, VIEW)
        return
    if definition.key == "event-orders":
        from .feature_gates import require_feature
        require_feature(event, "events.orders")
    event_authority.require(actor, event, None if definition.key.endswith("-pdf") else MANAGE_REGISTRATIONS)
    if definition.key.endswith("-pdf") and event.ends_at > timezone.now():
        raise ValidationError(gettext("Post-event PDF is available after the event ends."))


def grantee_gate(actor, makerspace_id):
    """EB1: a co-organizer or other grantee holding any live event grant in this space may ask for an event's
    reports; `authorize` then demands manage_registrations (or the event view) on that one event."""
    return event_authority.active_grants(actor, makerspace_id=makerspace_id).exists()


def register_subject():
    from apps.accounts import rbac
    register("event", ReportSubject(KEYS, resolve, authorize, rbac.Action.MANAGE_EVENTS, grantee_gate))
