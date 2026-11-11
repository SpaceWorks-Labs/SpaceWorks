"""How a plan plugs INTO the existing fair-use limits (#187A); it never replaces them.

* ``plan_limit`` is consulted by ``limits_core.resource_limit`` after the per-space
  override: override > plan > unlimited (#236 addendum: no built-in defaults are enforced).
  Every answer is "not set" for an OWN space (decision 236).
* The monthly keys (emails, SMS, WhatsApp, events) are plan-only: enforced at the same
  seams the daily caps use (``check_quota``, ``reserve_notification_quota``, the email
  outbox), each a no-op with the switch off.
* ``disallowed_modules`` is consulted by ``module_install.install_module``.

Every function returns its "not set" answer first when ``plans_enabled()`` is false, so
the self-host and switch-off paths run exactly the code they ran before.
"""

from datetime import UTC, datetime

from rest_framework import serializers

from apps.makerspaces.limits_core import (
    EXTRA_QUOTA_LIMIT_KEYS, NUMERIC_LIMIT_KEYS, PLATFORM_CREDENTIAL_LIMIT_KEYS, SPACE_QUOTA_LIMIT_KEYS,
)

from .availability import plans_enabled

NOT_SET = object()
# Existing fair-use keys a plan may set, plus the plan-only monthly keys.
# #234: every per-space fair-use key can be set by a plan; the superadmin console lists them all.
SHARED_KEYS = NUMERIC_LIMIT_KEYS
MONTHLY_KEYS = frozenset({"email_monthly", "sms_monthly", "whatsapp_monthly", "events_monthly"})
# Owner rule 261: a plan may carry ANY registry limit (the monthly quotas, platform-credential and extra
# keys too); each family's resolver falls back to the plan when the space has no override of its own.
PLAN_LIMIT_KEYS = (SHARED_KEYS | MONTHLY_KEYS | SPACE_QUOTA_LIMIT_KEYS | PLATFORM_CREDENTIAL_LIMIT_KEYS
                   | EXTRA_QUOTA_LIMIT_KEYS)
MONTHLY_LABELS = {"email_monthly": "emails this month", "sms_monthly": "SMS messages this month",
                  "whatsapp_monthly": "WhatsApp messages this month", "events_monthly": "new events this month"}


def _assignment(makerspace):
    from .models import SpacePlanAssignment

    return SpacePlanAssignment.objects.select_related("plan").filter(makerspace_id=makerspace.pk).first()


def plan_limit(makerspace, key):
    """The plan's limit for ``key`` (an int, or None = unlimited), or ``NOT_SET``."""
    if not plans_enabled() or key not in PLAN_LIMIT_KEYS:
        return NOT_SET
    from .hosting_type import is_hosted

    if not is_hosted(makerspace):
        return NOT_SET  # decision 236: an own space has no plan limits
    row = _assignment(makerspace)
    if row is None or key not in (row.plan.limits or {}):
        return NOT_SET
    value = row.plan.limits[key]
    return None if value is None or value == -1 else int(value)


def plan_name_for_limit(makerspace, key):
    """The plan's name when ``key``'s effective limit comes from the plan, else None."""
    if not plans_enabled() or key in (makerspace.resource_limit_overrides or {}):
        return None
    if plan_limit(makerspace, key) is NOT_SET:
        return None
    return _assignment(makerspace).plan.name


def plan_limit_error(plan_name, label, limit):
    message = (f"This space has reached the {label} included in its {plan_name} plan ({limit}). "
               "Ask the platform operator to change the plan.")
    return serializers.ValidationError({"limit": message, "code": "plan_limit_reached"}, code="plan_limit_reached")


def _month_start():
    now = datetime.now(UTC)
    return datetime(now.year, now.month, 1, tzinfo=UTC)


def monthly_used(makerspace, key):
    start = _month_start()
    if key == "events_monthly":
        from apps.events.models import Event
        return Event.objects.filter(makerspace=makerspace, created_at__gte=start).count()
    if key == "email_monthly":
        from apps.integrations.models import EmailLog
        return EmailLog.objects.filter(makerspace=makerspace, created_at__gte=start).exclude(
            status=EmailLog.Status.SKIPPED).count()
    from apps.integrations.models_contract import NotificationDelivery
    channel = key.removesuffix("_monthly")
    return NotificationDelivery.objects.filter(makerspace=makerspace, channel=channel, created_at__gte=start).exclude(
        state="skipped").count()


def monthly_refusal(makerspace, key, adding=1):
    """The refusal message when a monthly plan allowance is used up, else None."""
    if not plans_enabled():
        return None
    limit = plan_limit(makerspace, key)
    if limit is NOT_SET or limit is None:
        return None
    if monthly_used(makerspace, key) + adding > limit:
        return f"This space has used the {MONTHLY_LABELS[key]} included in its plan ({limit})."
    return None


def check_monthly(makerspace, key, *, adding=1):
    """Raise the typed plan error when a monthly allowance would be exceeded."""
    if monthly_refusal(makerspace, key, adding) is not None:
        raise plan_limit_error(_assignment(makerspace).plan.name, MONTHLY_LABELS[key], plan_limit(makerspace, key))


def disallowed_modules(makerspace, keys):
    """Module keys (outside core) the space's plan does not include; [] when off."""
    from .hosting_type import is_hosted

    if not plans_enabled() or not is_hosted(makerspace):
        return []
    row = _assignment(makerspace)
    allowed = set((row.plan.allowed_modules or []) if row else [])
    if not allowed:
        return []
    from apps.makerspaces.module_registry import core_module_keys
    return sorted(set(keys) - allowed - set(core_module_keys()))
