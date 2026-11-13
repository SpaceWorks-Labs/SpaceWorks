"""Event create/update service; explicit validation and transactional authority."""


from django.utils.translation import gettext
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.makerspaces import limits
from apps.makerspaces.guards import require_module_locked
from apps.makerspaces.models import Makerspace
from .capacity import CONFIRMED_STATUSES
from .exceptions import CapacityConflict, EventInvalidTransition
from .models import Event, EventRegistration
from .services_core import (EVENT_FIELDS, INHERITABLE_FIELDS, _locked_event, _validate,
                       _canonical_form, _audit, _refresh, _may_promote)
from .services_registration_state import promote_automatically
from .services_write_boundary import event_write

@transaction.atomic
def create_event(
    *, makerspace, actor, title, description, starts_at, ends_at, location,
    capacity, is_public, location_kind=Event.LocationKind.OTHER, custom_form=None,
    payment_amount=0, registration_requires_approval=False,
    registration_cutoff_at=None, registration_cutoff_lead_minutes=None,
    timezone_name=None, cancellation_cutoff_hours=None,
    registration_audience=None, category_id=None, tags=None, show_registration_count=True,
    organization_ids=None, collaborator_slugs=None, audience_organization_ids=None, accent_preset="",
    listing=Event.Listing.LISTED, page_state=Event.PageState.LIVE, delivery_mode=Event.DeliveryMode.IN_PERSON,
    join_url="", venue_address="", venue_map_url="",
):
    """Create a draft; organizers, partners and audience land in the SAME transaction.

    Every partner space is locked here, with the host, in primary-key order. The later
    ``invite_collaborators`` locks the brand-new event first and those spaces second;
    nobody else can see the uncommitted event, so taking the spaces up front cannot
    deadlock against it, while acquiring a partner AFTER the host (as the event-first
    path would) could deadlock against a reciprocal create in the partner space.
    """
    partner_ids = set(Makerspace.objects.filter(slug__in=set(collaborator_slugs or ())).values_list("pk", flat=True))
    locked_spaces = list(Makerspace.objects.select_for_update().filter(pk__in={makerspace.pk, *partner_ids}).order_by("pk"))
    locked_space = next(row for row in locked_spaces if row.pk == makerspace.pk)
    require_module_locked(locked_space, "events")
    event = Event(
        makerspace=locked_space,
        registration_audience=registration_audience or locked_space.event_default_registration_audience, category_id=category_id, tags=tags or [],
        created_by=actor,
        accent_preset=accent_preset,
        show_registration_count=show_registration_count,
        title=title,
        description=description,
        starts_at=starts_at,
        ends_at=ends_at,
        location=location,
        location_kind=location_kind, venue_address=venue_address, venue_map_url=venue_map_url,
        custom_form=_canonical_form(custom_form),
        capacity=capacity,
        payment_amount=payment_amount,
        registration_requires_approval=registration_requires_approval,
        cancellation_cutoff_hours=cancellation_cutoff_hours,
        registration_cutoff_at=registration_cutoff_at,
        registration_cutoff_lead_minutes=registration_cutoff_lead_minutes,
        is_public=is_public, listing=listing, page_state=page_state, delivery_mode=delivery_mode,
        **({"timezone_name": timezone_name} if timezone_name else {}),
    )
    if join_url or delivery_mode != Event.DeliveryMode.IN_PERSON:
        from apps.makerspaces.folded_capabilities import require_capability
        from apps.makerspaces.secrets import encrypt_value
        from .online_delivery import FEATURE, validate_join_url
        require_capability(locked_space, FEATURE)
        cleaned = validate_join_url(join_url)
        event.join_url_encrypted = encrypt_value(cleaned) if cleaned else ""
    from .registration_access import validate_event_audience
    validate_event_audience(event)
    _validate(event)
    event.save()
    _audit(event, actor, "event.created", event)
    if organization_ids:
        from .services_organizers import replace_organizers
        replace_organizers(event, actor=actor, organization_ids=organization_ids)
    if audience_organization_ids:
        from .services_audience_organizations import replace_audience_organizations
        replace_audience_organizations(event, actor=actor, organization_ids=audience_organization_ids)
    if collaborator_slugs:
        from .collaborator_services import invite_collaborators
        invite_collaborators(event, actor=actor, slugs=collaborator_slugs)
    return _refresh(event)


@event_write
def update_event(event, *, actor, inherit_fields=(), **changes):
    from apps.events.services_calendar import CALENDAR_EVENT_FIELDS, calendar_event_changed

    # Website template edits and occurrence windows serialize series -> occurrence.
    from .models import EventSeries
    series_id = Event.objects.values_list("series_id", flat=True).get(pk=event.pk)
    if series_id:
        EventSeries.objects.select_for_update().get(pk=series_id)

    locked = _locked_event(event.pk, lock_makerspace=False)
    from .programme_locks import lock_admission_sources
    original_audience = locked.registration_audience
    prospective_audience = changes.get("registration_audience", original_audience)
    if "registration_audience" in inherit_fields and locked.series_id:
        prospective_audience = locked.series.registration_audience
    locked.registration_audience = prospective_audience
    # Promotion fences every participant; acquire the same complete account set now.
    participant_ids = locked.registrations.values_list("member_id", flat=True)
    lock_admission_sources(locked, [*participant_ids, getattr(actor, "pk", None)], include_authority=True)
    locked.registration_audience = original_audience
    locked.makerspace = require_module_locked(locked.makerspace, "events")
    if locked.status not in (Event.Status.DRAFT, Event.Status.PUBLISHED):
        raise EventInvalidTransition("Terminal events cannot be updated.")
    unknown = set(changes) - EVENT_FIELDS
    if unknown:
        raise serializers.ValidationError(
            {field: "This field cannot be updated." for field in sorted(unknown)}
        )
    inherit_fields = set(inherit_fields or ())
    invalid_inherit = inherit_fields - INHERITABLE_FIELDS
    if invalid_inherit:
        raise serializers.ValidationError(
            {field: "This field cannot inherit from a series." for field in invalid_inherit}
        )
    if inherit_fields & set(changes):
        raise serializers.ValidationError(
            {field: "A field cannot be changed and inherited together." for field in inherit_fields & set(changes)}
        )
    if inherit_fields and locked.series_id is None:
        raise serializers.ValidationError({"inherit_fields": gettext("This event is not in a series.")})
    from .event_authority import require
    affected = set(changes) | inherit_fields
    if affected & {"starts_at", "ends_at"}:
        require(actor, locked, "publish_schedule")
    if affected - {"starts_at", "ends_at"} or not affected:
        require(actor, locked, "edit_details")
    if "payment_amount" in affected:
        require(actor, locked, None)
    if "registration_audience" in changes or "registration_audience" in inherit_fields:
        from . import event_authority
        from .event_permissions import EDIT_DETAILS
        from .staff_grant_locks import lock_authority
        actor = lock_authority(actor, locked)
        event_authority.require(actor, locked, EDIT_DETAILS)
    old_audience = locked.registration_audience
    if inherit_fields:
        from apps.events.services_series import occurrence_inherited_value

        for field in inherit_fields:
            changes[field] = occurrence_inherited_value(locked, field)

    if 'custom_form' in changes:
        changes['custom_form'] = _canonical_form(changes['custom_form'])
    if (
        "registration_requires_approval" in changes
        and changes["registration_requires_approval"]
        != locked.registration_requires_approval
        and locked.status != Event.Status.DRAFT
    ):
        raise EventInvalidTransition(
            "Approval policy can only be changed while the event is a draft."
        )

    now = timezone.now()
    previous_date_source = (locked.starts_at, locked.timezone_name)
    old_capacity, old_ends_at, old_image_key = locked.capacity, locked.ends_at, locked.image_key
    for field, value in changes.items():
        setattr(locked, field, value)
    from .registration_access import validate_event_audience
    validate_event_audience(locked)
    _validate(locked)

    confirmed = EventRegistration.objects.filter(
        event=locked, status__in=CONFIRMED_STATUSES
    ).count()
    if locked.capacity > 0 and confirmed > locked.capacity:
        raise CapacityConflict("Capacity cannot be below confirmed occupancy.")
    if (
        locked.status == Event.Status.PUBLISHED
        and old_ends_at < now <= locked.ends_at
    ):
        limits.check_quota(locked.makerspace, "events", adding=1, count_monthly=False)  # same event, already counted

    if "registration_audience" in changes:
        # Explicit local review resumes admission for existing waiters in this transaction.
        locked.organization_admission_blocked = False
    promoted = []
    capacity_changed = "capacity" in changes and locked.capacity != old_capacity

    if changes:
        update_fields = set(changes)
        locked.version += 1
        update_fields.add("version")
        if (locked.starts_at, locked.timezone_name) != previous_date_source:
            locked.event_date_revision += 1
            update_fields.add("event_date_revision")
        if "registration_audience" in changes:
            update_fields.add("organization_admission_blocked")
        if locked.series_id:
            overrides = set(locked.series_override_fields or [])
            overrides.update((set(changes) & INHERITABLE_FIELDS) - inherit_fields)
            overrides.difference_update(inherit_fields)
            locked.series_override_fields = sorted(overrides)
            update_fields.add("series_override_fields")
        locked.save(update_fields=[*sorted(update_fields), "updated_at"])
        from .website_revisions import refresh_owner_anchor
        refresh_owner_anchor(locked, actor)
        if "event_date_revision" in update_fields:
            from .hackathons.admission_dates import date_changed_locked
            from .programme_locks import current_locks
            date_changed_locked(event=locked, actor=actor, locks=current_locks(locked.pk))
        if set(changes) & CALENDAR_EVENT_FIELDS:
            calendar_event_changed(locked)
        if (locked.starts_at, locked.ends_at) != (previous_date_source[0], old_ends_at):
            from .linked_change_notices import event_changed  # decision 216: flag, never move the booking
            event_changed(locked, "moved")
            from .guest_pass_event_changes import schedule_moved  # audit M5: passes follow the new dates
            schedule_moved(locked)
        if "image_key" in inherit_fields and old_image_key:
            from apps.inventory import public_image_storage

            public_image_storage.release_public_image_on_commit(
                locked.makerspace, old_image_key
            )
    if (
        _may_promote(locked, now)
        and (locked.capacity == 0 or locked.capacity > confirmed)
    ):
        from .hackathons.admission_bridge import requires_admission
        if requires_admission(locked.pk) or not locked.registration_requires_approval:
            promoted = promote_automatically(
                locked,
                actor,
                None if locked.capacity == 0 else locked.capacity - confirmed,
            )

    if "payment_amount" in changes:
        # Lane L24: a lowered event price opens refund cases for paid seats without a ticket type.
        from apps.payments.price_drop.triggers import after_event_price
        after_event_price(actor, locked)
    meta = {"changed_fields": sorted(changes)}
    if "registration_audience" in changes:
        from .organization_audience import candidate_ids
        _audit(locked, actor, "event.audience_updated", locked,
               {"old_audience": old_audience, "new_audience": locked.registration_audience,
                "organization_ids": sorted(candidate_ids(locked))})
    if inherit_fields:
        meta["inherited_fields"] = sorted(inherit_fields)
    if capacity_changed:
        meta.update(
            old_capacity=old_capacity,
            new_capacity=locked.capacity,
        )
    if capacity_changed or promoted:
        meta["promoted_registration_ids"] = [row.pk for row in promoted]
    _audit(locked, actor, "event.updated", locked, meta)
    return _refresh(locked)
