"""Pre-insert typed remap for retained event booking decisions."""
from uuid import UUID
from django.apps import apps
from django.core.exceptions import ValidationError

from apps.backup.capture_managers import every_row
from apps.separability.booking_decision_intent import canonical_intent, validate_intent
from .insertion_errors import ArchiveFormatError, PrimaryKeyMapUnavailable

_TOMBSTONE = {"version": 1, "unavailable": True}


def _retained(label, source_id, owner_path, target_id, pk_map, references):
    model = apps.get_model(label)
    mapped = pk_map.lookup(model, source_id)
    if not references.equipment_materialized(label, source_id, mapped):
        raise PrimaryKeyMapUnavailable("Decision reference was not materialized.")
    if not every_row(model).filter(pk=mapped, **{owner_path: target_id}).exists():
        raise PrimaryKeyMapUnavailable("Decision reference was not retained.")
    return mapped


def prepare(row, *, job, pk_map, references, target):
    """Validate source identity before clearing optional refs for generic FK mapping."""
    if not isinstance(row["generation"], UUID) or row["generation"].version != 4:
        raise ArchiveFormatError("Invalid retained decision generation.")
    if row["intent_version"] != 1 or row["revision"] != 1 or row["billing_owner"] != "booking":
        raise ArchiveFormatError("Unsupported retained decision state.")
    raw = row["intent"]
    creator, booking, event = row["creator_id"], row["booking_id"], row["event_id"]
    if raw == _TOMBSTONE:
        if creator is not None and booking is not None:
            raise ArchiveFormatError("A replayable decision has a tombstone intent.")
        sticky = True
    else:
        try:
            value = validate_intent(raw)
        except (ValidationError, ValueError, TypeError) as exc:
            raise ArchiveFormatError("Invalid retained decision intent.") from exc
        if (value["makerspace_id"] != int(job.source_makerspace_id) or value["event_id"] != event
                or (creator is not None and value["creator_id"] != creator)
                or (booking is not None and value["booking_id"] != booking)):
            raise ArchiveFormatError("Retained decision intent disagrees with its source references.")
        sticky = creator is None or booking is None
    try:
        _retained("events.Event", event, "makerspace_id", target.pk, pk_map, references)
    except PrimaryKeyMapUnavailable as exc:
        raise ArchiveFormatError("Required decision event was not retained.") from exc
    if creator is not None:
        try:
            User = apps.get_model("accounts", "User")
            mapped_creator = pk_map.lookup(User, creator)
            if not references.equipment_identity_resolved(creator, mapped_creator) or not every_row(User).filter(pk=mapped_creator, account_purged_at__isnull=True, deletion_requested_at__isnull=True).exists():
                raise PrimaryKeyMapUnavailable("Decision creator was not retained.")
        except PrimaryKeyMapUnavailable:
            row["creator_id"] = None
            sticky = True
    if booking is not None:
        try:
            _retained("bookings.Booking", booking, "space__makerspace_id", target.pk, pk_map, references)
        except PrimaryKeyMapUnavailable:
            row["booking_id"] = None
            sticky = True
    return sticky


def finish(row, sticky):
    if sticky:
        row["intent"] = dict(_TOMBSTONE)
    else:
        row["intent"] = canonical_intent(makerspace_id=row["makerspace_id"], event_id=row["event_id"],
            booking_id=row["booking_id"], creator_id=row["creator_id"])
