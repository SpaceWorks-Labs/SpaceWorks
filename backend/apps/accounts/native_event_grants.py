"""The route gate and payload for native event-role grants (#173).

An ``event`` grant admits exactly one family of routes: the event-targeted programme routes in
``programme_route_catalog`` (target kind ``event``) whose ``pk`` is the grant's event and whose native
decision is not ``web_only``. Everything else is decided as for a member grant, so staff routes,
tenant routes, other events and organization governance all keep refusing. The grant carries no
staff authority (``limit_staff_authority`` gives it none), so the view's own ``event_authority``
check is answered by the person's event staff grants alone.
"""

from django.utils.translation import gettext
from rest_framework.exceptions import PermissionDenied

EVENT = "event"


def is_event_grant(grant):
    return getattr(grant, "authority", None) == EVENT


def session_authority_for(grant):
    authority = getattr(grant, "authority", None)
    return {"staff": "native_staff", EVENT: "native_event"}.get(authority, "member")


def native_event_route(name):
    """True for a programme route an event grant may use natively."""
    from apps.accounts.programme_route_catalog import BY_NAME, NATIVE_WEB_ONLY
    declaration = BY_NAME.get(name)
    return bool(declaration and declaration[1] == EVENT and name not in NATIVE_WEB_ONLY)


def admits_event_route(user, token, request, name, grant):
    """Admit an event grant to one of its event's delegable programme routes, or return False
    (member and public routes are then decided exactly as for a member grant)."""
    from apps.accounts.delegated_routes import DELEGABLE, route_class
    if not is_event_grant(grant) or route_class(name) != DELEGABLE or not native_event_route(name):
        return False
    kwargs = getattr(getattr(request, "resolver_match", None), "kwargs", {}) or {}
    if str(kwargs.get("pk")) != str(grant.event_id):
        raise PermissionDenied(gettext("This event grant is limited to its own event."))
    if token.get("mfa_source") != "verified":
        raise PermissionDenied(gettext("Native event sessions require MFA."))
    if request.headers.get("X-Makerspace-Id") is not None:
        raise PermissionDenied(gettext("Native event routes take their event, not a makerspace selection."))
    return True


def native_event_grant_entries(user, grant):
    """``event_grants`` for a native payload: every live event role (a member grant lists where the
    person may step up), or only the grant's own event (an event grant). Other grant kinds: none."""
    from apps.makerspaces.resource_grant_sources import registered_sources
    keys = {source.key: [] for source in registered_sources()}
    if "event_grants" not in keys or grant is None or getattr(grant, "authority", None) == "staff":
        return keys
    from apps.events.staff_payload import granted_event_entries
    entries = granted_event_entries(user)
    if is_event_grant(grant):
        entries = [entry for entry in entries if entry["event_id"] == grant.event_id]
    keys["event_grants"] = entries
    return keys
