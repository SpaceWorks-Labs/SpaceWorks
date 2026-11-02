"""End the departing member's presence through its existing audited domain writer."""

from apps.accounts.account_deletion_discovery import _model


def end_owned_presence(user, spaces, now):
    """Caller already holds every tenant and User, in lifecycle lock order.

    Presence may outlive module enablement or an active membership. In particular,
    account-only guest sessions need the same departure cleanup as member sessions.
    The low-level presence writer avoids re-entering public admission/module gates.
    """
    model = _model("presence.PresenceSession")
    if model is None:
        return
    from apps.presence.services import _end

    from apps.backup.capture_managers import every_row

    rows = every_row(model).select_for_update().filter(
        account=user, makerspace_id__in=[space.pk for space in spaces], ended_at__isnull=True,
    ).order_by("makerspace_id", "pk")
    for row in rows:
        _end(row, user, "user_ended", now)
