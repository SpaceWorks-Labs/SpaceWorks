"""Anonymous projection: allowlist fields, live visibility checks, bounded cache."""
from django.utils import timezone

from apps.makerspaces.platform import module_enabled
from apps.makerspaces.public_profile_access import account_is_open_web
from . import cache
from .models import PresenceSession
from .policy import require_enabled
from .privacy import settings_for


def present_rows(space):
    return PresenceSession.objects.filter(makerspace=space, ended_at=None, expires_at__gt=timezone.now(),
        account__is_active=True, account__access_status="active", account__is_tenant_dump_stub=False
    ).select_related("account", "makerspace", "membership__assigned_role", "account_project__profile",
                     "event_registration__event__makerspace"
    ).order_by("started_at", "pk")


def _project_title(row, space):
    # The anonymous TV is the logged-out audience: the account profile must be open to the web, its
    # projects section switched on, and the project itself shown (decisions 303/304).
    project = row.account_project
    if (project and row.status == "working" and project.public_visible and project.profile.show_projects
            and project.profile.user_id == row.account_id and account_is_open_web(row.account)):
        return project.title
    return None


def _event_title(row, space):
    registration = row.event_registration
    if not registration or row.status != "attending_event" or not module_enabled(space, "events"):
        return None
    event = registration.event
    if (registration.member_id == row.account_id and registration.status == "attended"
            and event.makerspace_id == space.pk and event.is_public
            and event.status in {"published", "completed"}):
        return event.title
    return None


def tv_payload(space, *, use_cache=True):
    require_enabled(space)
    policy = settings_for(space)
    # The generation is bumped inside the same transaction as every session, privacy,
    # preference, project/profile and event save, so a committed change always reads a
    # new key. Writes that bypass signals (queryset.update) are bounded by the 30 s TTL.
    key = f"presence:tv:{space.pk}:{policy.display_version}"
    cached = cache.read(key) if use_cache else None
    if cached is not None:
        return cached
    rows = list(present_rows(space))
    payload = []
    for row in rows:
        if row.membership_id and row.membership.status != "active":
            continue
        anonymous = not policy.show_names or (policy.allow_personal_opt_out and row.hide_on_display)
        name = "A guest" if row.status == "guest" or row.membership_id is None else "A member"
        if not anonymous:
            name = row.account.display_name or name
        item = {"display_name": name, "status": row.status, "since": row.started_at.isoformat()}
        if not anonymous:
            project, event = _project_title(row, space), _event_title(row, space)
            if project:
                item["project_title"] = project
            if event:
                item["event_title"] = event
        payload.append(item)
    if use_cache:
        cache.write(key, payload)
    return payload
