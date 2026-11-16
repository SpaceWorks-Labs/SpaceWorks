"""Parity O-B1: what a purge removes of the member-unit tables.

Every pointer at a unit PROTECTs it, so the pointers go first, then the units deepest level first (a unit
PROTECTs its children's `parent` link), then the level names. The people, plans and payments themselves
are never touched here: removing the unit layer leaves memberships, plans and the ledger exactly as they are.
"""


def _querysets(makerspace):
    from apps.makerspaces.models import (
        ImportedMemberUnit, MemberUnit, MemberUnitSettings, MembershipRequestUnit, MembershipUnit, PlanUnit,
        StaffUnitScope,
    )
    for model in (PlanUnit, MembershipRequestUnit, ImportedMemberUnit, MembershipUnit, StaffUnitScope):
        yield model.objects.filter(makerspace=makerspace)
    for level in range(3, -1, -1):
        yield MemberUnit.objects.filter(makerspace=makerspace, level=level)
    yield MemberUnitSettings.objects.filter(makerspace=makerspace)


def module_delete(makerspace):
    """`(units_deleted, model_labels)` in the shape the module purge collectors use."""
    from apps.makerspaces.models import MemberUnit
    from apps.makerspaces.module_purge_collectors_single_model import _delete
    units, labels = 0, frozenset()
    for queryset in _querysets(makerspace):
        is_unit = queryset.model is MemberUnit
        count, model_labels = _delete(queryset)
        labels = labels | model_labels
        units += count if is_unit else 0
    return units, labels


def preview(makerspace):
    from apps.makerspaces.models import MemberUnit, MembershipUnit, StaffUnitScope
    return {"member_units": MemberUnit.objects.filter(makerspace=makerspace).count(),
            "unit_assignments": MembershipUnit.objects.filter(makerspace=makerspace).count(),
            "staff_unit_scopes": StaffUnitScope.objects.filter(makerspace=makerspace).count()}
