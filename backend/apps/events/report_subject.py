"""Event subject policy used by manual reports, saved views and every builder call."""

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.operations.report_subjects import ReportSubject, register
from . import event_authority
from .event_permissions import MANAGE_REGISTRATIONS
from .models import Event

KEYS = ("event-attendance", "event-registrations", "event-feedback", "event-attendance-pdf")


def resolve(space, pk):
    return get_object_or_404(Event.objects.select_related("makerspace"), makerspace=space, pk=pk)


def authorize(actor, event, definition):
    event_authority.require(actor, event, None if definition.key.endswith("-pdf") else MANAGE_REGISTRATIONS)
    if definition.key.endswith("-pdf") and event.ends_at > timezone.now():
        raise ValidationError("Post-event PDF is available after the event ends.")


def register_subject():
    register("event", ReportSubject(KEYS, resolve, authorize))
