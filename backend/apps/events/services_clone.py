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
    OwnedImage, bounded_children, copy_fields,
)
from apps.makerspaces.event_asset_transaction import event_asset_transaction

TICKET_FIELDS = ("name", "amount", "audience", "capacity", "sales_start_at", "sales_end_at", "is_active")
SURVEY_FIELDS = ("title", "thank_you_text", "questions")


def duplicate_event(event, *, actor, attach_series=False):
    return event_asset_transaction(lambda assets: _duplicate_event(event, actor, attach_series, assets))


def _duplicate_event(event, actor, attach_series, assets):
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    assert_write_allowed(event.makerspace_id)
    # Series mutations lock the series before occurrences. Preserve that order
    # even for standalone copies using an inherited series cover image.
    series_id = Event.objects.values_list("series_id", flat=True).get(pk=event.pk)
    series = EventSeries.objects.select_for_update().get(pk=series_id) if series_id else None
    source = _locked_event(event.pk)
    source.makerspace = require_module_locked(source.makerspace, "events")
    from .staff_grant_locks import lock_authority
    actor = lock_authority(actor, source)
    from .website_visibility import effective_page
    if effective_page(source) is not None:
        from apps.makerspaces.public_page_authority import reject_platform
        reject_platform(actor)
    event_authority.require(actor, source, EDIT_DETAILS)
    # Standalone copies inherit neither scoped grants nor organizers. Only
    # tenant managers retain authority over the resulting draft.
    event_authority.require_tenant(actor, source.makerspace)
    assets.watch("source_event", source)
    assets.watch("source_series", series)
    assets.watch("source_tickets", bounded_children(source.ticket_types.order_by("pk").values()))
    assets.watch("source_surveys", list(EventFeedbackSurvey.objects.filter(event=source).order_by("pk").values()))
    values = copy_fields(source, EVENT_FIELDS | {"badge_template", "timezone_name"})
    values["title"] = source.title[:193].rstrip() + " (copy)"
    clone = Event(makerspace=source.makerspace, created_by=actor,
                  organization_admission_blocked=source.organization_admission_blocked, **values)
    attachment = None
    if attach_series:
        if not source.series_id:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"attach_series": "The source has no series."})
        event_authority.require(actor, series, None)
        local_start = source.starts_at.astimezone(ZoneInfo(series.recurrence_timezone))
        attachment = {
            "series": series, "series_revision": series.revision,
            "series_occurrence_key": f"copy{uuid4().hex[:16]}:{local_start:%Y%m%dT%H%M%S}",
            "series_override_fields": sorted(INHERITABLE_FIELDS),
        }
    from .registration_access import validate_event_audience
    validate_event_audience(clone)
    key = source.image_key
    source_prefix = f"event/{source.makerspace_id}/"
    if source.series_id and "image_key" not in (source.series_override_fields or []):
        key = series.image_key
        source_prefix = f"event-series/{series.makerspace_id}/"
    clone.image_key = assets.copy_image(source.makerspace, OwnedImage(
        source_key=key, source_prefix=source_prefix,
        destination_prefix=f"event/{source.makerspace_id}/",
        max_bytes=settings.PUBLIC_IMAGE_MAX_BYTES,
    ), storage=public_image_storage, journal_page=source)
    _validate(clone)
    clone.pk = assets.identities.get("event")
    clone.save(force_insert=True)
    assets.remember("event", clone.pk)
    for ticket in bounded_children(source.ticket_types.all()):
        child = EventTicketType(event=clone, makerspace=clone.makerspace,
                                **copy_fields(ticket, TICKET_FIELDS))
        _validate(child)
        child.save()
    survey = EventFeedbackSurvey.objects.select_for_update().filter(event=source).first()
    if survey is not None and not survey.is_open:
        EventFeedbackSurvey.objects.create(event=clone, **copy_fields(survey, SURVEY_FIELDS))
    from .website_copy import copy_page
    copy_page(source, clone, copies=assets)
    # Materialize the private override before attachment: its window may be
    # deliberately shorter than the inherited series programme.
    if attachment:
        for field, value in attachment.items():
            setattr(clone, field, value)
        _validate(clone)
        clone.save(update_fields=[*attachment, "updated_at"])
    if assets.phase == "finalize" or not assets.plans:
        _audit(clone, actor, "event.duplicated", clone, {"source_event_id": source.pk})
    return clone
