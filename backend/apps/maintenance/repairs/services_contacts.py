"""The technician directory, coverage and per-area defaults (#98, Q-T1 a).

* Any area manager (or the Space Manager) keeps the directory for the areas they manage.
* An IN-HOUSE contact's coverage is that person's Technician scope, so only the Space
  Manager sets coverage on a contact that names a person -- the same authority that sets
  a Machine Manager's machine types. External contractors' coverage only pre-selects
  them, so their area's manager may set it.
* Archiving keeps every dispatch and assignment; nothing is deleted.
"""

from django.utils.translation import gettext
from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts import rbac
from apps.audit import services as audit

from . import areas
from .models_contacts import CHANNELS

EDITABLE = ("name", "email", "phone", "telegram_handle", "notes", "channels")


def may_manage_directory(actor, space_id):
    return areas.manages_any(actor, space_id)


def _require(actor, space_id):
    if not may_manage_directory(actor, space_id):
        raise PermissionDenied()


def _person(space, person_id):
    from apps.accounts.models import User
    from apps.makerspaces.models import MakerspaceMembership
    if person_id is None:
        return None
    if not MakerspaceMembership.both_tracks().filter(makerspace=space, user_id=person_id, status="active").exists():
        raise ValidationError({"person_id": gettext("Choose a person of this makerspace.")})
    return User.objects.get(pk=person_id)


def _clean(values):
    cleaned = {}
    for name in EDITABLE:
        if name not in values:
            continue
        value = values[name]
        if name == "channels":
            if not isinstance(value, list) or any(item not in CHANNELS for item in value):
                raise ValidationError({"channels": gettext('Choose from {value}.').format(value=', '.join(CHANNELS))})
            value = sorted(set(value) | {"email"}, key=CHANNELS.index)
        else:
            value = str(value or "").strip()
        cleaned[name] = value
    if "name" in cleaned and not cleaned["name"]:
        raise ValidationError({"name": gettext("Give the technician a name.")})
    return cleaned


def _coverage(space, actor, contact, rows):
    """Replace coverage: [{"kind": "machine_type"|"inventory"|"room", "id": n}]."""
    from apps.bookings.models import BookableSpace
    from apps.machines.member_scope_services import assignable_machine_types
    from apps.maintenance.models import TechnicianCoverage
    if contact.person_id and not rbac.can(actor, rbac.Action.MANAGE_MAKERSPACE, space.pk):
        raise PermissionDenied(gettext("Only the Space Manager sets an in-house technician's coverage."))
    built = []
    for row in rows if isinstance(rows, list) else [None]:
        kind = row.get("kind") if isinstance(row, dict) else None
        if kind == "machine_type":
            found = assignable_machine_types(space).filter(pk=row.get("id")).first()
            if found is None:
                raise ValidationError({"coverage": gettext("Unknown machine type.")})
            built.append(TechnicianCoverage(contact=contact, kind=kind, machine_type=found))
        elif kind == "room":
            found = BookableSpace.objects.filter(makerspace=space, pk=row.get("id")).first()
            if found is None:
                raise ValidationError({"coverage": gettext("Unknown room.")})
            built.append(TechnicianCoverage(contact=contact, kind=kind, room=found))
        elif kind == "inventory":
            built.append(TechnicianCoverage(contact=contact, kind=kind))
        else:
            raise ValidationError({"coverage": gettext("Each row is a machine type, inventory or a room.")})
    TechnicianCoverage.objects.filter(contact=contact).delete()
    TechnicianCoverage.objects.bulk_create(built, ignore_conflicts=True)


@transaction.atomic
def create_contact(actor, space, values):
    from apps.maintenance.models import TechnicianContact
    _require(actor, space.pk)
    person = _person(space, values.get("person_id"))
    kind = TechnicianContact.Kind.IN_HOUSE if person is not None else TechnicianContact.Kind.EXTERNAL
    if person is not None and TechnicianContact.objects.filter(makerspace=space, person=person).exists():
        raise ValidationError({"person_id": gettext("This person already has a technician entry.")})
    fields = _clean({"channels": ["email"], **values})
    if person is not None and not fields.get("name"):
        fields["name"] = person.display_name or person.get_full_name() or person.username
    contact = TechnicianContact.objects.create(makerspace=space, kind=kind, person=person, **fields)
    if "coverage" in values:
        _coverage(space, actor, contact, values["coverage"])
    audit.record(actor, "technician.created", makerspace=space, target=contact,
                 meta={"contact_id": contact.pk, "kind": kind})
    return contact


@transaction.atomic
def update_contact(actor, contact, values):
    from apps.maintenance.models import TechnicianContact
    contact = TechnicianContact.objects.select_for_update().select_related("makerspace").get(pk=contact.pk)
    _require(actor, contact.makerspace_id)
    fields = _clean(values)
    if "phone" in fields and fields["phone"] != contact.phone:
        # A new number has not opted in: chat consent was given for the old one.
        contact.whatsapp_opted_in_at = contact.sms_opted_in_at = None
        fields.update({"whatsapp_opted_in_at": None, "sms_opted_in_at": None})
    for name, value in fields.items():
        setattr(contact, name, value)
    if fields:
        contact.save()
    if "coverage" in values:
        _coverage(contact.makerspace, actor, contact, values["coverage"])
    audit.record(actor, "technician.updated", makerspace=contact.makerspace, target=contact,
                 meta={"contact_id": contact.pk, "fields": sorted([*fields, *(["coverage"] if "coverage" in values
                                                                                else [])])})
    return contact


@transaction.atomic
def archive_contact(actor, contact):
    _require(actor, contact.makerspace_id)
    if not contact.is_archived:
        contact.is_archived = True
        contact.save(update_fields=["is_archived", "updated_at"])
        audit.record(actor, "technician.archived", makerspace=contact.makerspace, target=contact,
                     meta={"contact_id": contact.pk})
    return contact


@transaction.atomic
def withdraw_consent(actor, contact, channel):
    _require(actor, contact.makerspace_id)
    field = {"telegram": "telegram_opted_in_at", "whatsapp": "whatsapp_opted_in_at", "sms": "sms_opted_in_at"}
    if channel not in field:
        raise ValidationError({"channel": gettext("Withdraw Telegram, WhatsApp or SMS.")})
    setattr(contact, field[channel], None)
    if channel == "telegram":
        contact.telegram_chat_id = ""
    contact.save()
    audit.record(actor, "technician.consent_withdrawn", makerspace=contact.makerspace, target=contact,
                 meta={"contact_id": contact.pk, "channel": channel})
    return contact


@transaction.atomic
def set_default(actor, space, *, area, contact, machine_type=None, room=None, remove=False):
    from apps.maintenance.models import TechnicianDefault
    if area not in areas.AREAS:
        raise ValidationError({"area": gettext("Choose machines, inventory or rooms.")})
    if not rbac.can(actor, areas.MANAGER_ACTION[area], space.pk):
        raise PermissionDenied()
    if contact.makerspace_id != space.pk:
        raise ValidationError({"contact_id": gettext("Choose a technician of this makerspace.")})
    lookup = {"makerspace": space, "area": area, "machine_type": machine_type if area == areas.MACHINES else None,
              "room": room if area == areas.ROOMS else None, "contact": contact}
    if remove:
        TechnicianDefault.objects.filter(**lookup).delete()
    else:
        TechnicianDefault.objects.get_or_create(**lookup)
    audit.record(actor, "technician.default_removed" if remove else "technician.default_set", makerspace=space,
                 target=contact, meta={"contact_id": contact.pk, "area": area,
                                       "machine_type_id": getattr(lookup["machine_type"], "pk", None),
                                       "room_id": getattr(lookup["room"], "pk", None)})


def defaults_for(issue):
    """Contact ids pre-ticked for this issue: its area, its machine type, its room."""
    from django.db.models import Q
    from apps.maintenance.models import TechnicianDefault
    narrow = Q(machine_type__isnull=True, room__isnull=True)
    if issue.area == areas.MACHINES:
        narrow |= Q(machine_type_id=areas.machine_type_id(issue))
    if issue.area == areas.ROOMS:
        narrow |= Q(room_id=issue.room_id)
    return sorted(set(TechnicianDefault.objects.filter(makerspace_id=issue.makerspace_id, area=issue.area,
                                                       contact__is_archived=False).filter(narrow)
                      .values_list("contact_id", flat=True)))
