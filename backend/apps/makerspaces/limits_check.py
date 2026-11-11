"""The managed fair-use quota check (split from `limits_usage`, which re-exports it)."""
from rest_framework import serializers

from apps.makerspaces.limits_core import RESOURCE_LABELS


def check_quota(makerspace, key, *, adding=1, count_monthly=True, monthly_adding=None) -> None:
    """Raise when a managed limit would be exceeded.

    ``count_monthly=False`` skips the superadmin's MONTHLY quota: a booking restored from cancelled was
    already counted when it was first created (cancelled rows keep counting), so it must not count twice.
    ``monthly_adding`` overrides ``adding`` for that monthly quota only: publishing a draft created this
    month is already in the count (events are counted from creation), so it adds 0 there.

    The caller must wrap this check and its create operation in
    ``transaction.atomic()`` so the makerspace row lock serializes creators.
    """
    from apps.makerspaces import limits
    from apps.makerspaces.limits_usage import _COUNTERS
    from apps.managed_hosting.enforcement import check_monthly

    if key in ("events", "bookings") and count_monthly:
        # Owner 2026-11-11: the superadmin's monthly quota applies to EVERY space (typed 409).
        from apps.managed_hosting.space_quotas import check_space_quota
        check_space_quota(makerspace, f"{key}_monthly", adding=adding if monthly_adding is None else monthly_adding)
    if key == "events":
        # #187A: a plan's monthly allowance applies even where the base limit is unlimited;
        # a no-op while MANAGED_PLANS_ENABLED is off.
        check_monthly(makerspace, "events_monthly", adding=adding)
    limit = limits.resource_limit(makerspace, key)
    if limit is None:
        return

    counter = _COUNTERS.get(key)
    if counter is None:
        raise NotImplementedError(f"No quota counter is registered for {key!r}.")

    from apps.makerspaces.models import Makerspace

    # NO KEY UPDATE, like require_module_locked: creators still serialize with each other
    # and with module install/uninstall, and a caller already holding the fence never has
    # to upgrade to FOR UPDATE (which would wait on commit-time FOR KEY SHARE holders).
    locked = Makerspace.objects.select_for_update(no_key=True).get(pk=makerspace.pk)
    current = counter(locked)
    from apps.managed_hosting.enforcement import plan_limit_error, plan_name_for_limit
    if current + adding > limit:
        resource = RESOURCE_LABELS.get(key, key.replace("_", " "))
        plan_name = plan_name_for_limit(locked, key)
        if plan_name is not None:
            raise plan_limit_error(plan_name, resource, limit)
        message = (
            f"You've reached the free {resource} limit for this space — "
            "ask the operator to raise it or self-host."
        )
        raise serializers.ValidationError(
            {"limit": message}, code="limit_reached"
        )
