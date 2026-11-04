"""Series edits and projection onto locked future occurrences."""

from django.utils import timezone
from rest_framework import serializers
from apps.audit import services as audit
from apps.makerspaces.guards import require_module_locked
from . import services
from .exceptions import EventInvalidTransition
from .models import Event, EventSeries
from .services_write_boundary import event_write
from .services_calendar import CALENDAR_SERIES_FIELDS, calendar_series_changed
from .services_series_templates import (SERIES_FIELDS, RECURRENCE_FIELDS, _validate,
                              _apply_template, _materialize_locked)

@event_write
def update_series(series, *, actor, effective_from=None, **changes):
    locked = EventSeries.objects.select_for_update().get(pk=series.pk)
    if locked.status not in (EventSeries.Status.DRAFT, EventSeries.Status.PUBLISHED):
        raise EventInvalidTransition("Terminal series cannot be updated.")
    unknown = set(changes) - SERIES_FIELDS
    if unknown:
        raise serializers.ValidationError({field: "This field cannot be updated." for field in unknown})
    from .event_authority import require
    if set(changes) & RECURRENCE_FIELDS:
        require(actor, locked, "publish_schedule")
    if set(changes) - RECURRENCE_FIELDS or not changes:
        require(actor, locked, "edit_details")
    if "payment_amount" in changes:
        require(actor, locked, None)
    recurrence_changed = bool(set(changes) & RECURRENCE_FIELDS)
    if recurrence_changed and locked.status == EventSeries.Status.PUBLISHED and effective_from is None:
        raise serializers.ValidationError({"effective_from": "Required for a published schedule change."})
    cutoff = effective_from or timezone.now()
    old_revision = locked.revision
    old_audience = locked.registration_audience
    if "registration_audience" in changes:
        from . import event_authority
        from .event_permissions import EDIT_DETAILS
        # Series writers take series -> occurrences -> makerspace before authority.
        occurrences = list(locked.occurrences.select_for_update(of=("self",)).order_by("pk"))
        from .services_series_admission import lock_series_admission_sources
        lock_series_admission_sources(locked, occurrences, changes["registration_audience"], actor)
        require_module_locked(locked.makerspace_id, "events")
        from .staff_grant_locks import lock_authority
        actor = lock_authority(actor, locked)
        event_authority.require(actor, locked, EDIT_DETAILS)
        locked.organization_admission_blocked = False
    for field, value in changes.items():
        setattr(locked, field, value)
    if recurrence_changed:
        locked.revision += 1
    _validate(locked)
    locked.save(update_fields=(*sorted(changes), "revision", "organization_admission_blocked", "updated_at"))
    from .website_revisions import refresh_owner_anchor
    refresh_owner_anchor(locked, actor)
    if set(changes) & CALENDAR_SERIES_FIELDS:
        calendar_series_changed(locked)

    future = list(Event.objects.select_for_update().filter(
        series=locked, starts_at__gte=cutoff,
        status__in=(Event.Status.DRAFT, Event.Status.PUBLISHED),
    ).order_by("pk"))
    require_module_locked(locked.makerspace_id, "events")
    removed = []
    if recurrence_changed:
        for event in future:
            # Immutable designs and owned artwork must survive recurrence edits.
            # Keep those old occurrences as cancelled history; never cascade-delete
            # a private artifact or break a protected template reference.
            website = getattr(event, "website_page", None)
            keep_history = (event.certificate_template_revisions.exists() or event.certificate_artworks.exists()
                          or event.hackathon_applications.exists() or event.eventroleassignment_set.exists()
                          or event.registrations.exists() or bool(website and website.revisions.exists()))
            if event.status == Event.Status.PUBLISHED:
                services.cancel(event, actor=actor, notify=False)
            elif keep_history:
                event.status = Event.Status.CANCELLED
                event.version += 1
                # Cancelled occurrences have public calendars. A retained draft
                # has never been published, so retirement must also keep it private.
                event.is_public = False
                event.save(update_fields=("status", "is_public", "version", "updated_at"))
                from .programme_locks import current_locks
                from .hackathons.admission_lifecycle import cancel_event_locked
                from .contributions.admission_adapter import cancel_event_locked as cancel_roles
                locks = current_locks(event.pk)
                cancel_event_locked(event_id=event.pk, actor=actor, locks=locks)
                cancel_roles(event=event, actor=actor, locks=locks)
                services._audit(event, actor, "event.cancelled", event,
                                {"old_status": Event.Status.DRAFT, "new_status": Event.Status.CANCELLED})
            else:
                event_id = event.pk
                from .services_website_assets import schedule_occurrence_asset_cleanup
                schedule_occurrence_asset_cleanup(event)
                event.delete()
                removed.append(event_id)
                audit.record(
                    actor, "event.series_occurrence_removed", makerspace=locked.makerspace,
                    target=locked, meta={"event_id": event_id, "old_revision": old_revision},
                )
    else:
        for event in future:
            _apply_template(locked, event, set(changes), actor=actor)
    created = _materialize_locked(locked, actor=actor, now=timezone.now())
    audit.record(
        actor, "event.series_updated", makerspace=locked.makerspace, target=locked,
        meta={
            "changed_fields": sorted(changes), "old_revision": old_revision,
            "new_revision": locked.revision, "removed_ids": removed,
            "created_ids": [event.pk for event in created],
        },
    )
    if "registration_audience" in changes:
        from .organization_audience import candidate_ids
        audit.record(actor, "event.series_audience_updated", makerspace=locked.makerspace, target=locked,
                     meta={"old_audience": old_audience, "new_audience": locked.registration_audience,
                           "organization_ids": sorted(candidate_ids(locked))})
    return locked, created, removed
