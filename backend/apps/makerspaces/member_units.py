"""Parity O-B1: the member-unit tree (districts, chapters, branches) inside one makerspace.

Every writer runs inside one transaction under the makerspace row lock (`require_membership_feature_locked`),
checks the tenant write gate and the `membership.units` switch, and audits ids and counts only -- never a
unit's name or payment instructions. A unit is archived, never deleted, once anything points at it.

Public surface (the unit picker and the scope helper read these):

* `LEVEL_TEMPLATES`, `level_names(space)`, `set_level_names(actor, space, names)`
* `tree(space, include_archived=False)` -> flat list of dicts in display order
* `create_unit`, `update_unit`, `move_unit`, `archive_unit`, `restore_unit`
* `effective_payment_instructions(unit)` -> (text, source_unit_or_None) from the nearest ancestor that has any
* `subtree_ids(unit)`
"""
import re

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext, gettext_noop
from rest_framework.exceptions import APIException

from apps.audit import services as audit
from apps.makerspaces.membership_features import require_membership_feature_locked
from apps.makerspaces.models_member_units import MAX_LEVELS, MemberUnit, MemberUnitSettings

# Ready-made level names an organisation can start from; every name stays editable.
LEVEL_TEMPLATES = (
    {"key": "area_unit", "label": gettext_noop("Area and unit"), "levels": ("Area", "Unit")},
    {"key": "state_district_chapter", "label": gettext_noop("State, district and chapter"),
     "levels": ("State", "District", "Chapter")},
    {"key": "branches", "label": gettext_noop("Branches only"), "levels": ("Branch",)},
)
_CODE = re.compile(r"^[A-Z0-9]{1,6}$")


class UnitError(APIException):
    status_code = 400

    def __init__(self, code, detail):
        super().__init__({"code": code, "detail": detail}, code=code)


def _locked(space):
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    assert_write_allowed(space.pk)
    return require_membership_feature_locked(space.pk, "units")


def level_names(space):
    row = MemberUnitSettings.objects.filter(makerspace=space).first()
    return list(row.level_names) if row else []


def max_levels(space):
    """How many levels this space may use: its named levels, or the platform ceiling until it names any."""
    return len(level_names(space)) or MAX_LEVELS


def set_level_names(actor, space, names):
    names = [str(name).strip() for name in (names or [])]
    if len(names) > MAX_LEVELS or any(not 1 <= len(name) <= 40 for name in names):
        raise UnitError("member_unit_levels_invalid", gettext("Name between 0 and 4 levels, each 1 to 40 characters."))
    with transaction.atomic():
        space = _locked(space)
        deepest = MemberUnit.objects.filter(makerspace=space).order_by("-level").values_list("level", flat=True).first()
        if names and deepest is not None and deepest >= len(names):
            raise UnitError("member_unit_levels_in_use", gettext("A unit already uses a level you are removing."))
        row, _ = MemberUnitSettings.objects.get_or_create(makerspace=space)
        row.level_names = names
        row.save(update_fields=["level_names", "updated_at"])
        audit.record(actor, "member_unit.levels_updated", makerspace=space, target=row, meta={"levels": len(names)})
    return names


def code_base(name):
    return re.sub(r"[^A-Z0-9]", "", str(name).upper())[:6] or "U"


def free_code(space, base):
    """The base code, else the base shortened to fit a number (AB2, AB3, ...)."""
    taken = set(MemberUnit.objects.filter(makerspace=space).values_list("code", flat=True))
    if base not in taken:
        return base
    number = 2
    while True:
        suffix = str(number)
        candidate = f"{base[:6 - len(suffix)]}{suffix}"
        if candidate not in taken:
            return candidate
        number += 1


def _slug(space, name):
    base = slugify(name)[:70] or "unit"
    taken = set(MemberUnit.objects.filter(makerspace=space).values_list("slug", flat=True))
    slug, number = base, 2
    while slug in taken:
        slug, number = f"{base}-{number}", number + 1
    return slug


def _clean_code(space, code, *, exclude=None):
    code = str(code).strip().upper()
    if not _CODE.match(code):
        raise UnitError("member_unit_code_invalid", gettext("Use 1 to 6 capital letters or digits."))
    clash = MemberUnit.objects.filter(makerspace=space, code=code)
    if exclude is not None:
        clash = clash.exclude(pk=exclude.pk)
    if clash.exists():
        raise UnitError("member_unit_code_taken", gettext("Another unit already uses this code."))
    return code


def tree(space, include_archived=False):
    rows = list(MemberUnit.objects.filter(makerspace=space).order_by("path"))
    if not include_archived:
        rows = [row for row in rows if row.archived_at is None]
    names = level_names(space)
    return [{"id": row.pk, "parent_id": row.parent_id, "name": row.name, "slug": row.slug, "code": row.code,
             "level": row.level, "level_name": names[row.level] if row.level < len(names) else "",
             "path": row.path, "sort_order": row.sort_order, "archived": row.archived_at is not None,
             "has_payment_instructions": bool(row.payment_instructions)} for row in rows]


def create_unit(actor, space, *, name, parent_id=None, code=None, payment_instructions="", sort_order=0):
    from apps.managed_hosting.extra_quotas import check_extra_quota
    name = str(name).strip()
    if not 1 <= len(name) <= 120:
        raise UnitError("member_unit_name_invalid", gettext("Give the unit a name of 1 to 120 characters."))
    with transaction.atomic():
        space = _locked(space)
        parent = None
        if parent_id is not None:
            parent = MemberUnit.objects.select_for_update().filter(makerspace=space, pk=parent_id).first()
            if parent is None:
                raise UnitError("member_unit_parent_missing", gettext("Choose a unit in this makerspace."))
            if parent.archived_at is not None:
                raise UnitError("member_unit_archived", gettext("An archived unit cannot get new units."))
        level = parent.level + 1 if parent else 0
        if level >= max_levels(space):
            raise UnitError("member_unit_depth", gettext("This is the deepest level the space has named."))
        check_extra_quota(space, "member_units")  # decision 284: typed 409 `member_units_quota_reached`
        code = _clean_code(space, code) if code else free_code(space, code_base(name))
        unit = MemberUnit.objects.create(
            makerspace=space, parent=parent, name=name, slug=_slug(space, name), level=level, sort_order=sort_order,
            code=code, path=f"{parent.path if parent else '/'}{code}/",
            payment_instructions=str(payment_instructions or "")[:2000])
        audit.record(actor, "member_unit.created", makerspace=space, target=unit,
                     meta={"unit_id": unit.pk, "parent_id": parent.pk if parent else None, "level": level})
    return unit


def is_used(unit):
    # A code is part of every descendant's path, so a unit with children is "in use" too.
    return (unit.children.exists() or unit.member_rows.exists() or unit.staff_scopes.exists()
            or unit.plan_links.exists() or unit.request_rows.exists() or unit.imported_rows.exists())


def update_unit(actor, unit, data):
    """Rename, re-code (only while nothing uses the unit), reorder or change payment instructions."""
    with transaction.atomic():
        space = _locked(unit.makerspace)
        unit = MemberUnit.objects.select_for_update().get(pk=unit.pk, makerspace=space)
        changed = []
        if "name" in data and str(data["name"]).strip() != unit.name:
            name = str(data["name"]).strip()
            if not 1 <= len(name) <= 120:
                raise UnitError("member_unit_name_invalid", gettext("Give the unit a name of 1 to 120 characters."))
            unit.name = name
            changed.append("name")
        if "code" in data and str(data["code"]).strip().upper() != unit.code:
            if is_used(unit):
                raise UnitError("member_unit_code_locked", gettext("A unit's code cannot change once it is in use."))
            unit.code = _clean_code(space, data["code"], exclude=unit)
            unit.path = f"{unit.parent.path if unit.parent_id else '/'}{unit.code}/"
            changed.append("code")
        if "sort_order" in data and int(data["sort_order"]) != unit.sort_order:
            unit.sort_order = int(data["sort_order"])
            changed.append("sort_order")
        if "payment_instructions" in data and str(data["payment_instructions"]) != unit.payment_instructions:
            unit.payment_instructions = str(data["payment_instructions"])[:2000]
            changed.append("payment_instructions")
        if changed:
            unit.save()
            audit.record(actor, "member_unit.updated", makerspace=space, target=unit,
                         meta={"unit_id": unit.pk, "fields": sorted(changed)})
    return unit


def move_unit(actor, unit, new_parent_id):
    """Re-parent a unit (and its subtree): no cycle, no deeper than the named levels, never under an archived unit."""
    with transaction.atomic():
        space = _locked(unit.makerspace)
        unit = MemberUnit.objects.select_for_update().get(pk=unit.pk, makerspace=space)
        parent = None
        if new_parent_id is not None:
            parent = MemberUnit.objects.select_for_update().filter(makerspace=space, pk=new_parent_id).first()
            if parent is None:
                raise UnitError("member_unit_parent_missing", gettext("Choose a unit in this makerspace."))
            if parent.archived_at is not None:
                raise UnitError("member_unit_archived", gettext("An archived unit cannot get new units."))
            if parent.pk == unit.pk or parent.path.startswith(unit.path):
                raise UnitError("member_unit_cycle", gettext("A unit cannot move under itself."))
        new_level = parent.level + 1 if parent else 0
        subtree = list(MemberUnit.objects.select_for_update().filter(makerspace=space, path__startswith=unit.path))
        height = max(row.level for row in subtree) - unit.level
        if new_level + height >= max_levels(space):
            raise UnitError("member_unit_depth", gettext("That move would go deeper than the space's named levels."))
        old_prefix, new_prefix = unit.path, f"{parent.path if parent else '/'}{unit.code}/"
        shift = new_level - unit.level
        for row in subtree:
            row.path = new_prefix + row.path[len(old_prefix):]
            row.level += shift
            if row.pk == unit.pk:
                row.parent = parent
        MemberUnit.objects.bulk_update(subtree, ["path", "level", "parent"])
        audit.record(actor, "member_unit.moved", makerspace=space, target=unit,
                     meta={"unit_id": unit.pk, "parent_id": parent.pk if parent else None,
                           "descendants": len(subtree) - 1})
    return MemberUnit.objects.get(pk=unit.pk)


def archive_unit(actor, unit):
    with transaction.atomic():
        space = _locked(unit.makerspace)
        unit = MemberUnit.objects.select_for_update().get(pk=unit.pk, makerspace=space)
        if unit.archived_at is None:
            if unit.children.filter(archived_at__isnull=True).exists():
                raise UnitError("member_unit_has_children", gettext("Archive the units beneath it first."))
            unit.archived_at = timezone.now()
            unit.save(update_fields=["archived_at", "updated_at"])
            audit.record(actor, "member_unit.archived", makerspace=space, target=unit, meta={"unit_id": unit.pk})
    return unit


def restore_unit(actor, unit):
    with transaction.atomic():
        space = _locked(unit.makerspace)
        unit = MemberUnit.objects.select_for_update().get(pk=unit.pk, makerspace=space)
        if unit.archived_at is not None:
            if unit.parent_id and unit.parent.archived_at is not None:
                raise UnitError("member_unit_archived", gettext("Restore its parent unit first."))
            unit.archived_at = None
            unit.save(update_fields=["archived_at", "updated_at"])
            audit.record(actor, "member_unit.restored", makerspace=space, target=unit, meta={"unit_id": unit.pk})
    return unit


def effective_payment_instructions(unit):
    """The unit's own instructions, else the nearest ancestor's: `(text, source_unit)`; `("", None)` when none."""
    node = unit
    while node is not None:
        if node.payment_instructions.strip():
            return node.payment_instructions, node
        node = node.parent
    return "", None


def subtree_ids(unit):
    return list(MemberUnit.objects.filter(makerspace_id=unit.makerspace_id, path__startswith=unit.path)
                .values_list("pk", flat=True))
