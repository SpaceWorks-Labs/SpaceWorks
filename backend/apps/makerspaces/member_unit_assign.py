"""Parity O-B1: who sits in which unit, which unit a staff member is confined to, which units a plan is for.

* `assign_member_unit(actor, membership, unit_id)` -- put a community member in a unit (None removes them).
* `set_staff_unit_scope(actor, staff_membership, unit_id)` -- confine a STAFF membership to a unit's subtree
  (None lifts the narrowing). Needs `membership.unit_scoped_staff`.
* `set_plan_units(actor, plan, unit_ids)` -- limit a plan to units; the subtree inherits; an empty list means
  "every unit".

A unit-scoped actor may only place people in their own subtree, and may not change another actor's scope
(that is a space-wide act, `unit_scope_forbids`). Audit meta carries ids only.
"""
from django.db import transaction
from django.utils.translation import gettext

from apps.audit import services as audit
from apps.makerspaces import member_unit_scope as scope
from apps.makerspaces.member_units import UnitError, _locked
from apps.makerspaces.membership_features import require_membership_feature_locked
from apps.makerspaces.models import MakerspaceMembership, MembershipPlan
from apps.makerspaces.models_member_units import MemberUnit, MembershipUnit, PlanUnit, StaffUnitScope


def _live_unit(space, unit_id):
    unit = MemberUnit.objects.select_for_update().filter(makerspace=space, pk=unit_id).first()
    if unit is None:
        raise UnitError("member_unit_missing", gettext("Choose a unit in this makerspace."))
    if unit.archived_at is not None:
        raise UnitError("member_unit_archived", gettext("An archived unit cannot get new members."))
    return unit


def assign_member_unit(actor, membership, unit_id, *, action=None):
    with transaction.atomic():
        space = _locked(membership.makerspace)
        membership = MakerspaceMembership.all_tracks.select_for_update().get(pk=membership.pk, makerspace=space)
        scope.require_member_in_scope(actor, membership, action)
        current = MembershipUnit.objects.filter(membership=membership).first()
        if unit_id is None:
            if current is not None:
                current.delete()
                audit.record(actor, "membership.unit_changed", makerspace=space, target=membership,
                             meta={"membership_id": membership.pk, "from_unit_id": current.unit_id, "to_unit_id": None})
            return None
        unit = _live_unit(space, unit_id)
        if not scope.unit_in_scope(actor, space.pk, unit, action):
            raise UnitError("unit_scope_forbids", gettext("You can only place members in your own unit."))
        if current is not None and current.unit_id == unit.pk:
            return current
        row = current or MembershipUnit(makerspace=space, membership=membership)
        previous = current.unit_id if current else None
        row.unit = unit
        row.save()
        audit.record(actor, "membership.unit_changed", makerspace=space, target=membership,
                     meta={"membership_id": membership.pk, "from_unit_id": previous, "to_unit_id": unit.pk})
        return row


def set_staff_unit_scope(actor, staff_membership, unit_id):
    with transaction.atomic():
        space = _locked(staff_membership.makerspace)
        require_membership_feature_locked(space.pk, "unit_scoped_staff")
        scope.require_space_wide(actor, space.pk)
        membership = MakerspaceMembership.staff_tracks.select_for_update().filter(
            pk=staff_membership.pk, makerspace=space).first()
        if membership is None:
            raise UnitError("staff_membership_required", gettext("Only a staff membership can be unit-scoped."))
        current = StaffUnitScope.objects.filter(membership=membership).first()
        if unit_id is None:
            if current is not None:
                current.delete()
                audit.record(actor, "staff.unit_scope_changed", makerspace=space, target=membership,
                             meta={"membership_id": membership.pk, "from_unit_id": current.unit_id,
                                   "to_unit_id": None})
            return None
        unit = _live_unit(space, unit_id)
        previous = current.unit_id if current else None
        if previous == unit.pk:
            return current
        row = current or StaffUnitScope(makerspace=space, membership=membership)
        row.unit = unit
        row.save()
        audit.record(actor, "staff.unit_scope_changed", makerspace=space, target=membership,
                     meta={"membership_id": membership.pk, "from_unit_id": previous, "to_unit_id": unit.pk})
        return row


def set_plan_units(actor, plan, unit_ids):
    ids = sorted({int(value) for value in (unit_ids or [])})
    with transaction.atomic():
        space = _locked(plan.makerspace)
        scope.require_space_wide(actor, space.pk)
        plan = MembershipPlan.objects.select_for_update().get(pk=plan.pk, makerspace=space)
        units = {unit.pk: unit for unit in MemberUnit.objects.select_for_update().filter(makerspace=space, pk__in=ids)}
        if set(units) != set(ids) or any(unit.archived_at is not None for unit in units.values()):
            raise UnitError("member_unit_missing", gettext("Choose active units in this makerspace."))
        before = set(PlanUnit.objects.filter(plan=plan).values_list("unit_id", flat=True))
        if before == set(ids):
            return ids
        PlanUnit.objects.filter(plan=plan).exclude(unit_id__in=ids).delete()
        PlanUnit.objects.bulk_create([PlanUnit(makerspace=space, plan=plan, unit_id=pk) for pk in ids if pk not in before])
        audit.record(actor, "membership_plan.units_changed", makerspace=space, target=plan,
                     meta={"plan_id": plan.pk, "unit_ids": ids})
        return ids


def plan_unit_ids(plan):
    return sorted(PlanUnit.objects.filter(plan=plan).values_list("unit_id", flat=True))
