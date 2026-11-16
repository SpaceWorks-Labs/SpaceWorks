"""A machine type's per-space setup: booking defaults and training notes (decision 343 follow-up).

Authority is the per-type settings rule (`consumable_profile_services.space_and_type`). Booking defaults
are read by `bookings.services_spaces.create_space` for a new space of this type, and pushed to existing
spaces only through `bookings.services_rules.update_booking_rules`, which re-checks the actor's own
booking authority -- so a Machine Manager without it can set the defaults but not rewrite rooms.
"""

from django.db import transaction
from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit

from .models_type_setup import MachineTypeSetup

FIELDS = ("booking_slot_minutes", "booking_buffer_before_minutes", "booking_buffer_after_minutes",
          "booking_approval_mode", "training_notes", "notes_at_session_start", "notes_at_job_request")
MAX_NOTES = 10000


def setup_for(space, machine_type):
    return MachineTypeSetup.objects.filter(makerspace=space, machine_type=machine_type).first() or MachineTypeSetup(
        makerspace=space, machine_type=machine_type)


@transaction.atomic
def update(actor, space, machine_type, data):
    if len(str(data.get("training_notes") or "")) > MAX_NOTES:
        raise ValidationError({"training_notes": gettext("Keep training notes under 10,000 characters.")})
    row, _ = MachineTypeSetup.objects.select_for_update().get_or_create(makerspace=space, machine_type=machine_type)
    changed = sorted(key for key in FIELDS if key in data and getattr(row, key) != data[key])
    for key in changed:
        setattr(row, key, data[key])
    row.save()
    if changed:
        audit.record(actor, "machine_type_setup.updated", makerspace=space, target=machine_type,
                     meta={"fields": changed})
    return row


def booking_defaults(space_id, machine_type_id):
    """The bookings rule fields this type sets for a new space, or {} when it sets none."""
    row = MachineTypeSetup.objects.filter(makerspace_id=space_id, machine_type_id=machine_type_id).first()
    if row is None:
        return {}
    values = {"min_booking_duration_minutes": row.booking_slot_minutes,
              "buffer_before_minutes": row.booking_buffer_before_minutes,
              "buffer_after_minutes": row.booking_buffer_after_minutes,
              "approval_mode": row.booking_approval_mode or None}
    return {key: value for key, value in values.items() if value is not None}


def type_spaces(space, machine_type):
    """Active bookable machine spaces of this type in this space (a machine's space carries its type)."""
    from django.db.models import Q
    from apps.bookings.models import BookableSpace
    return BookableSpace.objects.filter(makerspace=space, is_active=True).filter(
        Q(machine_type=machine_type) | Q(machine__machine_type=machine_type)).order_by("id")


def apply_booking_defaults(actor, space, machine_type):
    """Push the type's booking defaults to its existing spaces through the bookings rule service."""
    from apps.bookings.services_rules import update_booking_rules
    defaults = booking_defaults(space.pk, machine_type.pk)
    if not defaults:
        raise ValidationError({"detail": gettext("This machine type has no booking defaults to apply.")})
    updated = [update_booking_rules(row, actor=actor, **defaults).pk for row in type_spaces(space, machine_type)]
    audit.record(actor, "machine_type_setup.booking_defaults_applied", makerspace=space, target=machine_type,
                 meta={"spaces": len(updated), "fields": sorted(defaults)})
    return updated
