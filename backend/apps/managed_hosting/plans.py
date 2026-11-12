"""Plan tiers and per-space assignment (#187A). Superadmin-only, audited.

Assigning a plan starts its trial when the plan (or the call) gives trial days; a trial
that ended turns the space read-only through #185's read-only mode, and choosing a plan
again (with no trial) lifts exactly that read-only source, never a manual one.
"""

from django.utils.translation import gettext
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from apps.makerspaces.lifecycle_authority import require_platform_superadmin
from apps.makerspaces.models import Makerspace

from .availability import require_plans_enabled
from .enforcement import PLAN_LIMIT_KEYS
from .models import HostingPlan, SpacePlanAssignment

PLAN_FIELDS = ("key", "name", "description", "is_active", "trial_days", "price_minor", "currency",
               "billing_period", "limits", "allowed_modules")


def validate_limits(value):
    if not isinstance(value, dict):
        raise ValidationError({"limits": gettext("Use an object of limit keys.")})
    for key, limit in value.items():
        if key not in PLAN_LIMIT_KEYS:
            raise ValidationError({"limits": gettext('Unknown plan limit: {key}.').format(key=key)})
        if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < -1):
            raise ValidationError({"limits": gettext('{key}: use a whole number, -1 or null.').format(key=key)})
    return value


def validate_modules(value):
    from apps.makerspaces.module_aliases import canonical_module_keys
    from apps.makerspaces.module_registry import BY_KEY

    if not isinstance(value, list) or not all(isinstance(key, str) for key in value):
        raise ValidationError({"allowed_modules": gettext("Use known module keys.")})
    value = canonical_module_keys(value)  # a retired key (`printing`) means its live key
    if any(key not in BY_KEY for key in value):
        raise ValidationError({"allowed_modules": gettext("Use known module keys.")})
    return sorted(set(value))


def save_plan(actor, data, plan=None):
    require_platform_superadmin(actor)
    require_plans_enabled()
    with transaction.atomic():
        created = plan is None
        plan = plan or HostingPlan(created_by=actor)
        for name in PLAN_FIELDS:
            if name in data:
                setattr(plan, name, data[name])
        plan.save()
        fields = sorted(name for name in PLAN_FIELDS if name in data)
        if created:
            audit.record(actor, "managed_hosting.plan_created", makerspace=None, target=plan, meta={"fields": fields})
        else:
            audit.record(actor, "managed_hosting.plan_updated", makerspace=None, target=plan, meta={"fields": fields})
    return plan


def assign(actor, makerspace_id, plan_id, *, trial_days=None):
    require_platform_superadmin(actor)
    require_plans_enabled()
    from apps.space_controls.models import SpaceControlState
    from apps.space_controls.services_access import lift_read_only

    with transaction.atomic():
        space = Makerspace.objects.select_for_update().get(pk=makerspace_id)
        from .hosting_type import require_hosted
        require_hosted(space)  # decision 236: plans and trials are for hosted spaces only
        plan = HostingPlan.objects.filter(pk=plan_id, is_active=True).first()
        if plan is None:
            raise ValidationError({"plan_id": gettext("Choose an active plan.")})
        days = plan.trial_days if trial_days is None else trial_days
        if type(days) is not int or not 0 <= days <= 365:
            raise ValidationError({"trial_days": gettext("Use 0 to 365 days.")})
        row, _ = SpacePlanAssignment.objects.update_or_create(makerspace=space, defaults={
            "plan": plan, "assigned_by": actor, "trial_expired_at": None, "reminders_sent": [],
            "trial_ends_at": timezone.now() + timedelta(days=days) if days else None,
        })
        audit.record(actor, "managed_hosting.plan_assigned", makerspace=space, target=space,
                     meta={"plan_id": plan.pk, "trial_days": days})
        lifted = SpaceControlState.ReadOnlySource.TRIAL_EXPIRED
    lift_read_only(None, space.pk, source=lifted)
    return row


def unassign(actor, makerspace_id):
    require_platform_superadmin(actor)
    require_plans_enabled()
    from apps.space_controls.models import SpaceControlState
    from apps.space_controls.services_access import lift_read_only

    with transaction.atomic():
        space = Makerspace.objects.select_for_update().get(pk=makerspace_id)
        deleted, _ = SpacePlanAssignment.objects.filter(makerspace=space).delete()
        if deleted:
            audit.record(actor, "managed_hosting.plan_removed", makerspace=space, target=space, meta={})
    lift_read_only(None, makerspace_id, source=SpaceControlState.ReadOnlySource.TRIAL_EXPIRED)
    return deleted
