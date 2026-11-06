"""Create, change, close and delete ID programmes (SPEC §4.3, §5.2). Every change audited.

A programme is hosted by a space its organisation OWNS (Q12: not possible otherwise).
Deleting is allowed only while no card was ever approved; otherwise close it, and its
cards keep verifying until revoked or expired (Q10).
"""
from django.utils.translation import gettext
from django.db import transaction
from django.utils.text import slugify
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit import services as audit

from .models import IdProgramme, IdProgrammeCard
from .numbering import prefix_from, validate_prefix
from .questions import validate_schema

EDITABLE = ("name", "description", "registration_open", "requires_approval", "id_prefix", "validity_mode",
            "valid_until", "validity_days", "photo_mode", "form_schema", "public_verify", "email_daily_cap", "status")
PRESETS = {
    "students": {"name": "Student ID", "requires_approval": True, "photo_mode": "required", "validity_mode": "days",
                 "validity_days": 365},
    "volunteers": {"name": "Volunteer ID", "requires_approval": True, "photo_mode": "optional"},
    "staff": {"name": "Staff ID", "requires_approval": True, "photo_mode": "required"},
}


def require_owner(organization, makerspace):
    from apps.organizations.models import OrganizationMakerspace
    if not OrganizationMakerspace.objects.filter(organization=organization, makerspace=makerspace,
                                                 relationship="owner").exists():
        raise ValidationError({"makerspace_id": gettext("Programmes are hosted by a space this organisation owns.")})


def _clean(values, current=None):
    data = dict(values)
    if "id_prefix" in data:
        validate_prefix(data["id_prefix"])
    if "form_schema" in data:
        data["form_schema"] = validate_schema(data["form_schema"])
    mode = data.get("validity_mode", current.validity_mode if current else "none")
    if mode == "fixed_date" and not data.get("valid_until", getattr(current, "valid_until", None)):
        raise ValidationError({"valid_until": gettext("Choose the date cards stop being valid.")})
    if mode == "days" and not data.get("validity_days", getattr(current, "validity_days", None)):
        raise ValidationError({"validity_days": gettext("Choose for how many days a card is valid.")})
    status = data.get("status", current.status if current else "draft")
    if status != "active":
        data["registration_open"] = False
    return data


def _unique_slug(organization, name):
    base = slugify(name)[:70] or "programme"
    slug, n = base, 2
    while IdProgramme.objects.filter(organization=organization, slug=slug).exists():
        slug, n = f"{base}-{n}", n + 1
    return slug


@transaction.atomic
def create(actor, organization, makerspace, values):
    from apps.accounts import rbac
    from apps.card_designs.resolution import get_or_create
    require_owner(organization, makerspace)
    if not rbac.can(actor, rbac.Action.MANAGE_ID_PROGRAMMES, makerspace.pk):
        raise PermissionDenied(gettext("You cannot create programmes for this space."))
    preset = PRESETS.get(values.pop("preset", ""), {})
    data = _clean({**preset, **values})
    data.setdefault("name", preset.get("name", "ID programme"))
    data.setdefault("id_prefix", prefix_from(data["name"]))
    programme = IdProgramme.objects.create(organization=organization, makerspace=makerspace, created_by=actor,
                                           slug=_unique_slug(organization, data["name"]),
                                           **{key: value for key, value in data.items() if key in EDITABLE})
    get_or_create(makerspace, "id_programme", actor=actor, programme=programme)
    audit.record(actor, "id_programme.created", makerspace=makerspace, target=programme,
                 meta={"programme_id": programme.pk})
    return programme


@transaction.atomic
def update(actor, programme, values):
    programme = IdProgramme.objects.select_for_update().get(pk=programme.pk)
    data = _clean(values, programme)
    changed = [key for key, value in data.items() if key in EDITABLE and getattr(programme, key) != value]
    for key in changed:
        setattr(programme, key, data[key])
    if changed:
        programme.save()
        action_fields = "fields_updated" if changed == ["form_schema"] else "updated"
        if action_fields == "fields_updated":
            audit.record(actor, "id_programme.fields_updated", makerspace=programme.makerspace, target=programme,
                         meta={"programme_id": programme.pk})
        else:
            audit.record(actor, "id_programme.updated", makerspace=programme.makerspace, target=programme,
                         meta={"programme_id": programme.pk, "fields": changed})
        if programme.status == "closed" and "status" in changed:
            audit.record(actor, "id_programme.closed", makerspace=programme.makerspace, target=programme,
                         meta={"programme_id": programme.pk})
    return programme


@transaction.atomic
def delete(actor, programme):
    if IdProgrammeCard.objects.filter(programme=programme, sequence__isnull=False).exists():
        raise ValidationError({"detail": gettext("Cards in this programme were approved. Close it instead.")})
    from apps.card_designs.storage import delete_quietly
    keys = list(programme.cards.exclude(photo_object_key="").values_list("photo_object_key", flat=True))
    audit.record(actor, "id_programme.deleted", makerspace=programme.makerspace, target=programme,
                 meta={"programme_id": programme.pk})
    programme.delete()
    transaction.on_commit(lambda: [delete_quietly(key) for key in keys])
