"""In-app notice when a platform-credential or space quota is FIRST reached in a month (decision 281).

Once per (space, key, month): the caller (`platform_limits.note_reached`) only calls this after it has
proven no ``platform_credential_limit.reached`` audit row exists for that period, and the inbox rows
use a deterministic ``event_key`` so a retry can never double-post. Recipients: the space's Space
Managers (staff memberships holding MANAGE_MAKERSPACE) and every superadmin. Fail-safe: a notice never
breaks delivery. Staff-feed reach is by area (`legacy_feed_scope`): this event is an unplaced key, so
only a Space Manager or superadmin sees it.
"""
import logging
from uuid import NAMESPACE_URL, uuid5

from django.utils.translation import gettext

logger = logging.getLogger(__name__)
EVENT = "platform_limit.reached"
USAGE_LINK = "/admin/usage"


def _link_for(space, user):
    from apps.accounts.models import User
    if user.is_superuser or user.role == User.Role.SUPERADMIN:
        return "/admin/platform-spaces"
    return USAGE_LINK


def recipients(space):
    from apps.accounts import rbac
    from apps.accounts.models import User
    from apps.makerspaces.models import MakerspaceMembership
    managers = [m.user for m in MakerspaceMembership.staff_tracks.filter(
        makerspace=space, status="active", user__is_active=True,
        user__access_status=User.AccessStatus.ACTIVE).select_related("user")
        if rbac.can(m.user, rbac.Action.MANAGE_MAKERSPACE, space.pk)]
    admins = list(User.objects.filter(is_active=True, role=User.Role.SUPERADMIN))
    seen, out = set(), []
    for user in managers + admins:
        if user.pk not in seen:
            seen.add(user.pk)
            out.append(user)
    return out


def notify_reached(space, key, period, label, *, quota=False):
    """``quota`` is a decision 284 space quota (events, bookings, payments); otherwise a 281 channel limit."""
    try:
        from apps.makerspaces.platform import module_enabled
        if not module_enabled(space, "notifications"):
            return
        from apps.notifications.models_inbox import NotificationInboxRow
        from apps.tenant_migration.gate_runtime import tenant_write
        title = gettext("Monthly allowance reached") if quota else gettext("Platform allowance reached")
        summary = (gettext("This space has reached its monthly allowance of %(what)s. New ones are refused until "
                           "next month; anything already started can still be paid, settled and refunded.")
                   if quota else
                   gettext("This space has used the %(what)s allowed by the platform. "
                           "The in-app inbox keeps working; the limited channel is paused until next month.")
                   ) % {"what": gettext(label)}
        with tenant_write(space.pk):
            for user in recipients(space):
                NotificationInboxRow.objects.get_or_create(
                    makerspace=space, user=user,
                    event_key=uuid5(NAMESPACE_URL, f"platform-limit:{space.pk}:{key}:{period}:{user.pk}"),
                    defaults={"feature": "api_access", "event": EVENT, "title": title, "summary": summary,
                              "link": _link_for(space, user)})
    except Exception:
        logger.warning("platform_limit_notice_failed", extra={"makerspace_id": getattr(space, "pk", None)})
