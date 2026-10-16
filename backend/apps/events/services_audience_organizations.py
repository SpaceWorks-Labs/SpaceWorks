"""Audited replace-the-set boundary for an event's selected audience organizations."""

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.makerspaces.guards import require_module_locked

from . import event_authority
from .audience_models import EventAudienceOrganization
from .directories import discoverable_organizations
from .event_permissions import EDIT_DETAILS
from .exceptions import EventInvalidTransition
from .models import Event
from .services_core import _audit, _locked_event
from .staff_grant_locks import lock_authority

MAX_AUDIENCE_ORGANIZATIONS = 50


def audience_rows(event):
    return list(
        EventAudienceOrganization.objects.filter(event=event)
        .select_related("organization").order_by("organization__name", "organization_id")
    )


@transaction.atomic
def replace_audience_organizations(event, *, actor, organization_ids):
    """Admit exactly these organizations' members. Grants no event authority.

    Event lock first, the same order as organizer writers, so registration's
    ``lock_admission_sources`` fence sees either the old or the new set, never half.
    A newly added organization must be one the actor could find in the directory;
    an already-listed one may stay even after it stops being discoverable.
    """
    requested = list(organization_ids)
    if len(requested) != len(set(requested)):
        raise ValidationError({"organization_ids": "Organization IDs must be unique."})
    if len(requested) > MAX_AUDIENCE_ORGANIZATIONS:
        raise ValidationError({"organization_ids": f"At most {MAX_AUDIENCE_ORGANIZATIONS} organizations are allowed."})
    locked = _locked_event(event.pk)
    locked.makerspace = require_module_locked(locked.makerspace, "events")
    actor = lock_authority(actor, locked)
    event_authority.require(actor, locked, EDIT_DETAILS)
    if locked.status not in (Event.Status.DRAFT, Event.Status.PUBLISHED):
        raise EventInvalidTransition("Terminal events cannot be updated.")

    existing = list(EventAudienceOrganization.objects.select_for_update().filter(event=locked).order_by("pk"))
    old_ids = sorted(row.organization_id for row in existing)
    added = set(requested) - set(old_ids)
    findable = set(discoverable_organizations(actor).filter(pk__in=added).values_list("pk", flat=True))
    if findable != added:
        raise ValidationError({"organization_ids": "An organization is unavailable."})
    if old_ids != sorted(requested):
        EventAudienceOrganization.objects.filter(event=locked).exclude(organization_id__in=requested).delete()
        EventAudienceOrganization.objects.bulk_create([
            EventAudienceOrganization(event=locked, organization_id=pk, added_by=actor)
            for pk in sorted(added)
        ])
        _audit(locked, actor, "event.audience_organizations_updated", locked, {
            "old_organization_ids": old_ids, "organization_ids": sorted(requested),
        })
    return audience_rows(locked)
