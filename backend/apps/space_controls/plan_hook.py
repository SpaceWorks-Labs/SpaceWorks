"""The health card's managed-plan field (#187A). ``False`` means "omit the key": with
MANAGED_PLANS_ENABLED off the card is byte-for-byte what it was without the limiter."""


def plan_summary(space):
    from apps.managed_hosting.availability import plans_enabled

    if not plans_enabled():
        return False
    from apps.managed_hosting.models import SpacePlanAssignment

    row = SpacePlanAssignment.objects.select_related("plan").filter(makerspace=space).first()
    if row is None:
        return None
    return {"key": row.plan.key, "name": row.plan.name, "trial_ends_at": row.trial_ends_at}
