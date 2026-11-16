"""Atomic kit version and publication updates; callers enforce staff authority."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404

from apps.audit import services as audit
from apps.accounts import rbac
from apps.admin_api.permissions import require_action
from apps.encryption.write_fence import assert_mapped_write_allowed
from apps.inventory.equipment_kit_validation import normalize_lines
from apps.inventory.models import InventoryProduct
from apps.inventory.models_equipment_proposals import EquipmentKitTemplate, EquipmentKitVersion
from apps.makerspaces.models import Makerspace
from apps.makerspaces.guards import require_module_locked
from apps.tenant_migration.gate_runtime import assert_write_allowed
from django.utils.translation import gettext

MAX_SAFE_REVISION = 9007199254740991
MAX_VERSION = 2147483647


class KitRevisionConflict(Exception):
    pass


def _locked_lines(makerspace_id, lines):
    ids = [line.get("product_id") for line in lines if isinstance(line, dict)] if isinstance(lines, list) else []
    valid_ids = [item for item in ids if type(item) is int and item > 0]
    products = {
        item.pk: item for item in InventoryProduct.objects.select_for_update(nowait=True, of=("self",))
        .filter(makerspace_id=makerspace_id, pk__in=valid_ids).order_by("pk")
    }
    return normalize_lines(lines, products, makerspace_id)


def _refresh_actor(actor):
    try:
        actor.refresh_from_db()
    except type(actor).DoesNotExist:  # The account row went away mid-request.
        raise Http404 from None


@transaction.atomic
def create_template(*, actor, makerspace_id, name, lines):
    """Caller must enforce EDIT_INVENTORY before invoking this mutation."""
    assert_write_allowed(makerspace_id)
    assert_mapped_write_allowed(makerspace_id)
    maker = Makerspace.objects.select_for_update(nowait=True, no_key=True, of=("self",)).get(pk=makerspace_id)
    _refresh_actor(actor)
    require_module_locked(maker, "staff_admin")
    require_action(actor, rbac.Action.EDIT_INVENTORY, maker.pk)
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 200:
        raise ValidationError(gettext("A valid kit name is required."))
    normalized = _locked_lines(maker.pk, lines)
    template = EquipmentKitTemplate.objects.create(makerspace=maker, name=name.strip())
    version = EquipmentKitVersion.objects.create(template=template, version=1, name=template.name, lines=normalized)
    audit.record(actor, "inventory.equipment_kit_created", makerspace=maker, target=template,
                 meta={"version": version.version})
    return template, version


def _locked_template(actor, makerspace_id, template_id, expected_revision):
    assert_write_allowed(makerspace_id)
    assert_mapped_write_allowed(makerspace_id)
    maker = Makerspace.objects.select_for_update(nowait=True, no_key=True, of=("self",)).get(pk=makerspace_id)
    _refresh_actor(actor)
    require_module_locked(maker, "staff_admin")
    require_action(actor, rbac.Action.EDIT_INVENTORY, maker.pk)
    template = EquipmentKitTemplate.objects.select_for_update(nowait=True, of=("self",)).filter(
        pk=template_id, makerspace_id=makerspace_id,
    ).first()
    if template is None:
        raise Http404
    if type(expected_revision) is not int or template.revision != expected_revision:
        raise KitRevisionConflict("revision_changed")
    return template


def _advance(template):
    if template.revision >= MAX_SAFE_REVISION:
        raise KitRevisionConflict("revision_exhausted")
    template.revision += 1


@transaction.atomic
def append_version(*, actor, makerspace_id, template_id, expected_revision, name, lines):
    template = _locked_template(actor, makerspace_id, template_id, expected_revision)
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 200:
        raise ValidationError(gettext("A valid kit name is required."))
    normalized = _locked_lines(makerspace_id, lines)
    if template.current_version >= MAX_VERSION:
        raise KitRevisionConflict("version_exhausted")
    _advance(template)
    template.current_version += 1
    version = EquipmentKitVersion.objects.create(
        template=template, version=template.current_version, name=name.strip(), lines=normalized,
    )
    template.name = name.strip()
    template.save(update_fields=["name", "current_version", "revision", "updated_at"])
    audit.record(actor, "inventory.equipment_kit_version_created", makerspace=template.makerspace,
                 target=template, meta={"version": version.version})
    return template, version


@transaction.atomic
def set_flag(*, actor, makerspace_id, template_id, expected_revision, field, value):
    if field not in {"published_for_contexts", "archived"} or type(value) is not bool:
        raise ValidationError(gettext("Invalid kit setting."))
    template = _locked_template(actor, makerspace_id, template_id, expected_revision)
    if getattr(template, field) == value:
        return template
    _advance(template)
    setattr(template, field, value)
    template.save(update_fields=[field, "revision", "updated_at"])
    audit.record(actor, "inventory.equipment_kit_changed", makerspace=template.makerspace,
                 target=template, meta={"field": field, "value": value})
    return template
