"""Apply a machine-type template: the ONE service behind "Add a machine type" (decision 343).

It writes what a template owns -- the type itself (new custom types only: name, icon, metering
unit, booking flag, intake fields) and the type's consumable profile in this space -- and hands
back every other step's suggested values as `prefill`. The wizard saves those steps through the
endpoints that already own them (pricing, job and session settings, adapter safety profile,
maintenance schedules, access grants, bookings), so no setting gains a second writer.

Re-applying never overwrites: an existing consumable key is skipped, and an existing type's
intake fields are only filled when it has none.
"""

import re

from django.db import IntegrityError, transaction
from django.utils.translation import gettext
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.accounts import rbac
from apps.audit import services as audit

from . import consumable_profile_services as profiles
from .models import MachineType
from .template_spec import resolve, validate_spec

PREFILL = ("pricing", "access", "bookings", "safety", "maintenance", "job", "notifications", "documents")


def _slug(text):
    slug = re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")[:50]
    return slug or "machine-type"


def _new_type(actor, space, template, name, slug):
    if not rbac.is_space_manager_identity(actor, space.pk):
        raise PermissionDenied(gettext("Only the Space Manager adds machine types."))
    spec = template["spec"]
    basics = spec.get("basics", {})
    name = str(name or template["name"]).strip()[:200]
    if not name:
        raise ValidationError({"name": gettext("Give the machine type a name.")})
    slug = _slug(slug or name)
    if MachineType.objects.filter(makerspace=space, slug=slug).exists():
        raise ValidationError({"slug": gettext("A machine type with this slug already exists.")})
    if MachineType.objects.filter(makerspace=space, name__iexact=name).exists():
        raise ValidationError({"name": gettext("A machine type with this name already exists in this makerspace.")})
    fields = spec.get("intake_fields") or []
    try:
        with transaction.atomic():
            return MachineType.objects.create(
                makerspace=space, slug=slug, name=name, icon=str(template.get("icon") or "")[:50],
                is_builtin=False, managing_action="",
                capability_config={"metering_unit": basics.get("metering_unit", "minutes"),
                                   "requires_booking": bool(basics.get("requires_booking", False))},
                intake_schema={"version": 1, "fields": fields} if fields else {})
    except IntegrityError as exc:
        raise ValidationError({"slug": gettext("A machine type with this name or slug already exists.")}) from exc


@transaction.atomic
def apply_template(actor, space, key, *, machine_type=None, name="", slug=""):
    template = resolve(space, key)
    if template is None:
        raise NotFound()
    validate_spec(template["spec"])
    spec = template["spec"]
    created_type = machine_type is None
    if created_type:
        machine_type = _new_type(actor, space, template, name, slug)
        audit.record(actor, "machine_type.created", makerspace=space, target=machine_type,
                     target_type="machine_type")
    else:
        profiles.space_and_type(actor, space.pk, machine_type.pk, write=True)
        fields = spec.get("intake_fields") or []
        if machine_type.makerspace_id == space.pk and not machine_type.intake_schema and fields:
            machine_type.intake_schema = {"version": 1, "fields": fields}
            machine_type.save(update_fields=["intake_schema"])
    existing = set(profiles.profile(space, machine_type).values_list("key", flat=True))
    created, skipped = [], []
    for position, row in enumerate(spec.get("consumables") or []):
        if row["key"] in existing:
            skipped.append(row["key"])
            continue
        data = {field: row[field] for field in ("key", "name", "kind", "unit", "required", "estimate_by",
                                                "record_by", "attributes") if field in row}
        profiles.create(actor, space, machine_type, {**data, "position": position}, template_key=template["key"])
        created.append(row["key"])
    audit.record(actor, "machine_type.template_applied", makerspace=space, target=machine_type, meta={
        "template_key": template["key"], "created_type": created_type, "consumables_added": len(created),
        "consumables_skipped": len(skipped)})
    return {"machine_type": machine_type, "created_type": created_type, "template_key": template["key"],
            "consumables_added": created, "consumables_skipped": skipped,
            "prefill": {section: spec.get(section, {} if section != "maintenance" else []) for section in PREFILL}}
