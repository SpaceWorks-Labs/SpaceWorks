"""Explicit event clone adapter; identities and participation never travel."""

from uuid import uuid4
from zoneinfo import ZoneInfo

from django.conf import settings

from apps.events import event_authority
from apps.events.event_permissions import EDIT_DETAILS
from apps.events.models import Event, EventFeedbackSurvey, EventSeries, EventTicketType
from apps.events.services import EVENT_FIELDS, INHERITABLE_FIELDS, _audit, _locked_event, _validate
from apps.inventory import public_image_storage
from apps.makerspaces.guards import require_module_locked
from apps.makerspaces.resource_clone import (
    OwnedImage, bounded_children, clone_transaction, copy_fields,
)

TICKET_FIELDS = ("name", "amount", "audience", "capacity", "sales_start_at", "sales_end_at", "is_active")
SURVEY_FIELDS = ("title", "thank_you_text", "questions")


def duplicate_event(event, *, actor, attach_series=False):
    with clone_transaction() as assets:
        from apps.tenant_migration.gate_runtime import assert_write_allowed
        assert_write_allowed(event.makerspace_id)
        # Series mutations lock the series before occurrences. Preserve that order
        # even for standalone copies using an inherited series cover image.
        series_id = Event.objects.values_list("series_id", flat=True).get(pk=event.pk)
        series = EventSeries.objects.select_for_update().get(pk=series_id) if series_id else None
        source = _locked_event(event.pk)
        source.makerspace = require_module_locked(source.makerspace, "events")
        event_authority.require(actor, source, EDIT_DETAILS)
        values = copy_fields(source, EVENT_FIELDS | {"badge_template", "timezone_name"})
        values["title"] = source.title[:193].rstrip() + " (copy)"
        clone = Event(makerspace=source.makerspace, created_by=actor, **values)
        if attach_series:
            if not source.series_id:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({"attach_series": "The source has no series."})
            event_authority.require(actor, series, None)
            clone.series = series
            clone.series_revision = series.revision
            local_start = source.starts_at.astimezone(ZoneInfo(series.recurrence_timezone))
            clone.series_occurrence_key = f"copy{uuid4().hex[:16]}:{local_start:%Y%m%dT%H%M%S}"
            clone.series_override_fields = sorted(INHERITABLE_FIELDS)
        key = source.image_key
        source_prefix = f"event/{source.makerspace_id}/"
        if source.series_id and "image_key" not in (source.series_override_fields or []):
            key = series.image_key
            source_prefix = f"event-series/{series.makerspace_id}/"
        clone.image_key = assets.copy_image(source.makerspace, OwnedImage(
            source_key=key, source_prefix=source_prefix,
            destination_prefix=f"event/{source.makerspace_id}/",
            max_bytes=settings.PUBLIC_IMAGE_MAX_BYTES,
        ), storage=public_image_storage)
        _validate(clone)
        clone.save()
        for ticket in bounded_children(source.ticket_types.all()):
            child = EventTicketType(event=clone, makerspace=clone.makerspace,
                                    **copy_fields(ticket, TICKET_FIELDS))
            _validate(child)
            child.save()
        survey = EventFeedbackSurvey.objects.select_for_update().filter(event=source).first()
        if survey is not None and not survey.is_open:
            EventFeedbackSurvey.objects.create(event=clone, **copy_fields(survey, SURVEY_FIELDS))
        _audit(clone, actor, "event.duplicated", clone, {"source_event_id": source.pk})
        return clone
