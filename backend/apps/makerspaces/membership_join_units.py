"""Parity O-B1: which unit a joiner lands in, and which plans a unit may be offered.

Precedence for the unit of a join request (inert while `membership.units` is off for the space):
1. an explicit `?unit=CODE` / `unit_code` the joiner chose;
2. the unit an invite link preselects;
3. the unit the person already has in this space (a re-join keeps their place).

A plan with unit links is only for those units and everything beneath them. The chosen unit is stored on
`MembershipRequestUnit` and copied to the membership when it activates (`apply_request_unit`), so approval,
payment and import acceptance all end in the same place.
"""
from django.utils.translation import gettext

from apps.audit import services as audit
from apps.makerspaces.membership_admission_settings import AdmissionError
from apps.makerspaces.membership_features import membership_feature_on
from apps.makerspaces.models_member_units import MemberUnit, MembershipRequestUnit, MembershipUnit, PlanUnit


def unit_by_code(space, code):
    code = str(code or "").strip().upper()
    return MemberUnit.objects.filter(makerspace=space, code=code, archived_at__isnull=True).first() if code else None


def _invite_unit(space, invite_code):
    from apps.makerspaces.models import MembershipInviteLink
    from apps.makerspaces.membership_invite_links import code_digest
    link = MembershipInviteLink.objects.filter(makerspace=space, code_digest=code_digest(invite_code)).select_related(
        "unit").first() if invite_code else None
    unit = link.unit if link is not None else None
    return unit if unit is not None and unit.archived_at is None else None


def _existing_unit(space, user):
    row = MembershipUnit.objects.filter(makerspace=space, membership__user=user).select_related("unit").first()
    return row.unit if row is not None and row.unit.archived_at is None else None


def plan_unit_paths(plan):
    if plan is None:
        return []
    return list(PlanUnit.objects.filter(plan=plan).values_list("unit__path", flat=True))


def plan_allows_unit(plan, unit):
    """True for an unrestricted plan; otherwise the unit must sit inside one of the plan's units."""
    paths = plan_unit_paths(plan)
    return not paths or (unit is not None and any(unit.path.startswith(path) for path in paths))


def plans_for_unit(queryset, unit):
    """Narrow a `MembershipPlan` queryset to the plans offered in `unit` (all plans when `unit` is None)."""
    if unit is None:
        return queryset.filter(unit_links__isnull=True)
    from django.db.models import Q
    ancestors = [int(part) for part in unit.path.strip("/").split("/") if part]
    return queryset.filter(Q(unit_links__isnull=True) | Q(unit_links__unit_id__in=ancestors)).distinct()


def resolve_join_unit(space, user, plan, unit_code=None, invite_code=None):
    """The unit for a join request, or None. Raises `AdmissionError` for a bad code or a plan/unit mismatch."""
    if not membership_feature_on(space, "units"):
        return None
    unit = None
    if unit_code:
        unit = unit_by_code(space, unit_code)
        if unit is None:
            raise AdmissionError("membership_unit_invalid", gettext("This unit is not available."))
    unit = unit or _invite_unit(space, invite_code) or _existing_unit(space, user)
    if not plan_allows_unit(plan, unit):
        if unit is None:
            raise AdmissionError("membership_unit_required", gettext("Choose your unit to join this plan."))
        raise AdmissionError("membership_unit_not_allowed", gettext("This plan is not offered in your unit."))
    return unit


def record_request_unit(request, unit):
    if unit is not None:
        MembershipRequestUnit.objects.update_or_create(request=request, defaults={
            "makerspace": request.makerspace, "unit": unit})


def apply_request_unit(membership, request, actor=None):
    """On activation: give the new member the unit their request chose (never overwrites an existing placement)."""
    if request is None or not membership_feature_on(membership.makerspace, "units"):
        return None
    choice = MembershipRequestUnit.objects.filter(request=request).select_related("unit").first()
    if choice is None or choice.unit.archived_at is not None:
        return None
    row, created = MembershipUnit.objects.get_or_create(
        membership=membership, defaults={"makerspace": membership.makerspace, "unit": choice.unit})
    if created:
        audit.record(actor, "membership.unit_changed", makerspace=membership.makerspace, target=membership,
                     meta={"membership_id": membership.pk, "from_unit_id": None, "to_unit_id": choice.unit_id,
                           "source": "join"})
    return row if created else None


def unit_for_membership(membership):
    row = MembershipUnit.objects.filter(membership=membership).select_related("unit").first()
    return row.unit if row else None
