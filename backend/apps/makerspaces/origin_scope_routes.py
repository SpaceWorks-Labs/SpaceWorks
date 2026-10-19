from django.apps import apps

from apps.makerspaces.origin_scope_model_lookups import (
    BASE_MODEL_LOOKUPS,
    TARGET_SET_LOOKUPS,
)

PUBLIC_SLUG_ROUTES = {"public-presence-now", "presence-start", "presence-current", "presence-end", "presence-renew", "presence-projects", "presence-preferences", "public-booking-resource", "public-booking-website", "public-booking-website-image", "member-booking-pass", "member-booking-confirmation", "member-booking-confirmation-png", "member-booking-calendar", "member-booking-rotate-checkin", "public-event-organization-eligibility"}

REPLAY_TOKEN_ROUTES = {"kiosk-replay-prepare", "kiosk-replay-execute"}

# Scanner routes carry their tenant inside the scanned QR payload, not the path. The
# target is the QR's makerspace, so a native staff session cannot scan another space's
# QR under its selected header. An unknown payload adds no target; the view 404s.
QR_PAYLOAD_ROUTES = {"qr-resolve", "qr-scan"}

# Only these creation routes take their authoritative tenant from the body.
BODY_SCOPED_ROUTES = {"qr-boxes", "qr-containers", "qr-tools"}

MAKERSPACE_KWARG_ROUTES = {
    **{name: "makerspace_id" for name in (
        "admin-staff-accounts", "admin-staff-account-policy", "admin-staff-account-change",
        "admin-staff-account-deactivate", "admin-staff-account-reactivate",
        "admin-staff-account-set-password", "admin-staff-account-resend-invite",
    )},
    "whatsapp-meta-webhook": "makerspace_id",
    "website-origins": "makerspace_id",
    'admin-booking-machine-types': 'makerspace_id',
    'admin-makerspace-setup-state': 'makerspace_id',
    'admin-maintenance-overdue': 'makerspace_id',
    'admin-makerspace-profile': 'makerspace_id',
    'admin-makerspace-domain-settings': 'makerspace_id',
    'admin-makerspace-usage': 'makerspace_id',
    'admin-kiosk-replay-list': 'makerspace_id',
    'admin-maintenance-schedule-list-create': 'makerspace_id',
    'admin-maintenance-log-list-create': 'makerspace_id',
    'admin-bookable-space-list-create': 'makerspace_id',
    'admin-event-list-create': 'makerspace_id',
    'admin-event-series-list-create': 'makerspace_id',
    'admin-event-series-collaboration-inbox': 'makerspace_id',
    'admin-role-list-create': 'makerspace_id',
    'admin-membership-machine-scope': 'makerspace_id',
    'admin-machine-types': 'makerspace_id',
    'admin-machine-type-detail': 'makerspace_id',
    'admin-makerspace-provision-subdomain': 'makerspace_id',
    'admin-makerspace-subdomain-request': 'makerspace_id',
    'admin-api-settings': 'makerspace_id',
    'admin-notification-recipients': 'makerspace_id',
    'admin-notification-rules': 'makerspace_id',
    'admin-machine-service-request-list-create': 'makerspace_id',
    'admin-audit-verifications': 'makerspace_id',
    'admin-audit-verification-detail': 'makerspace_id',
    'admin-kiosk-station-list-create': 'makerspace_id',
}
from .origin_scope_routes_7b import PRINTER_MAKERSPACE_ROUTES

MAKERSPACE_KWARG_ROUTES.update(PRINTER_MAKERSPACE_ROUTES)
MAKERSPACE_KWARG_ROUTES.update({name: "makerspace_id" for name in (
    "messaging-settings", "messaging-test", "whatsapp-template-list",
    "whatsapp-template-detail", "whatsapp-template-catalog",
)})
from .origin_scope_routes_wp4 import MAKERSPACE_ROUTES as WP4_ROUTES
MAKERSPACE_KWARG_ROUTES.update(WP4_ROUTES)
MAKERSPACE_KWARG_ROUTES.update({name: "makerspace_id" for name in (
    "contract-channels", "contract-channel", "contract-endpoints", "contract-endpoint-start",
    "contract-endpoint-verify", "contract-endpoint-revoke", "contract-preferences",
    "contract-deliveries", "contract-test",
)})

# These routes have no tenant-bearing path segment by design: each is a listing whose
# queryset is explicitly narrowed by the named makerspace query parameter.
QUERY_SCOPED_ROUTES = {
    "member-messaging",
    "member-messaging-consent",
    'admin-accessible-events',
    'admin-accessible-booking-spaces',
    'admin-search',                # ?makerspace_id= is mandatory
    'admin-api-key-requests',       # requester-owned API-key requests; ?makerspace=
    'admin-audit-logs',             # tenant audit-log listing; ?makerspace=
    'admin-membership-requests',    # tenant join-request queue; ?makerspace_id=
    'admin-memberships-roster',     # tenant membership roster; ?makerspace_id=
    'admin-needs-fix-shelf',        # tenant repair shelf; ?makerspace=
    'ledger-aggregate',             # superadmin aggregate listing; ?makerspace=
    'ledger-export-aggregate',      # matching aggregate export; ?makerspace=
}
NATIVE_HEADER_GLOBAL_ROUTES = {
    'auth-me',
    'device-grants',
    'device-grant-detail',
    'push-device-list-create',
    'push-device-detail',
    'auth-logout-all', 'auth-logout', 'device-logout', 'auth-reauth',
    'auth-reauth-phone-start', 'auth-reauth-phone-confirm', 'auth-reauth-social-factor',
}
REQUEST_ACTIONS = {
    'request-accept',
    'request-reject',
    'request-assign-box',
    'request-issue',
    'request-return-due',
    'request-return',
    'guest-admin-request-return',
    'request-timeline',
}
MACHINE_SERVICE_ACTIONS = {
    'admin-machine-service-request-detail',
    'admin-machine-service-request-accept',
    'admin-machine-service-request-reject',
    'admin-machine-service-request-start',
    'admin-machine-service-request-complete',
    'admin-machine-service-request-fail',
    'admin-machine-service-request-collect',
    'admin-machine-service-file-presign',
    'admin-machine-service-file-finalize',
}
from .origin_scope_routes_w7_events import EVENT_MODEL_LOOKUPS
from .origin_scope_routes_p2_events import P2_EVENT_MODEL_LOOKUPS
MAKERSPACE_KWARG_ROUTES["admin-event-categories"] = "makerspace_id"

MODEL_LOOKUPS = {
    **EVENT_MODEL_LOOKUPS, **P2_EVENT_MODEL_LOOKUPS,
    **BASE_MODEL_LOOKUPS,
    **{name: ('hardware_requests.HardwareRequest', 'makerspace_id') for name in REQUEST_ACTIONS},
    **{name: ('machines.MachineServiceRequest', 'makerspace_id') for name in MACHINE_SERVICE_ACTIONS},
}
from .origin_scope_routes_p2_bookings import MODEL_LOOKUPS as P2_BOOKING_LOOKUPS
MODEL_LOOKUPS.update(P2_BOOKING_LOOKUPS)

def request_route_targets(request, view=None):
    url_name, targets, invalid, route_recognized = _authoritative_route_targets(
        request, view
    )
    from .origin_scope_routes_public_pages import GLOBAL_ROUTES
    if url_name in GLOBAL_ROUTES:
        return url_name, set(), invalid, route_recognized
    hints = []
    query = getattr(request, 'query_params', None)
    if query is None:
        query = getattr(request, 'GET', {})
    for key in ('makerspace', 'makerspace_id'):
        value = query.get(key)
        if value in (None, ''):
            continue
        parsed = _positive_int(value)
        invalid = invalid or parsed is None
        if parsed is not None:
            hints.append(parsed)
    if getattr(request, "method", "GET") not in {"GET", "HEAD", "OPTIONS", "TRACE"}:
        body = getattr(request, "data", {})
        if hasattr(body, "get"):
            for key in ("makerspace", "makerspace_id"):
                value = body.get(key)
                if value in (None, ""):
                    continue
                parsed = _positive_int(value)
                invalid = invalid or parsed is None
                if parsed is not None:
                    hints.append(parsed)

    hint_set = set(hints)
    if url_name in TARGET_SET_LOOKUPS:
        invalid = invalid or bool(hint_set - targets)
    else:
        invalid = invalid or len(targets | hint_set) > 1
    target_set = targets | hint_set
    return url_name, target_set, invalid, route_recognized


def authoritative_route_resolution(request, view=None):
    """Return non-raising authoritative targets plus whether the route is known."""
    try:
        _name, targets, invalid, recognized = _authoritative_route_targets(
            request, view
        )
    except Exception:
        return set(), False
    return (targets if recognized and not invalid else set()), recognized


def _authoritative_route_targets(request, view=None):
    match = getattr(request, 'resolver_match', None)
    url_name = getattr(match, 'url_name', '')
    kwargs = dict(getattr(match, 'kwargs', {}) or {})
    kwargs.update(getattr(view, 'kwargs', {}) or {})
    from .origin_scope_routes_public_pages import page_route_targets
    page_target = page_route_targets(url_name, kwargs, request)
    if page_target is not None:
        return page_target
    from .origin_scope_account_routes import account_route_targets
    account_target = account_route_targets(url_name, kwargs)
    if account_target is not None:
        return account_target
    if url_name == "notification-media":
        from .origin_scope_notification_media import media_grant_targets
        targets = media_grant_targets(kwargs.get("token"))
        return url_name, targets, not bool(targets), True
    targets = set()
    invalid = False
    # Domain adapters register targets without widening any user RBAC scope.
    # This resolver is advisory for origin/source-gate scoping; HMAC authorization
    # independently verifies the signature, server client and required scopes.
    from apps.apiclients.read_contract import read_target_registered, resolve_read_target
    if match is not None and read_target_registered(match.view_name):
        target, resolved = resolve_read_target(request, match)
        return url_name, {target.pk} if resolved else set(), not resolved, True
    registered = MAKERSPACE_KWARG_ROUTES.get(url_name)
    route_recognized = bool(
        registered or 'makerspace_id' in kwargs
        or (url_name == 'admin-makerspace' and 'pk' in kwargs)
        or url_name in MODEL_LOOKUPS or url_name in TARGET_SET_LOOKUPS
        or url_name in QUERY_SCOPED_ROUTES or url_name in NATIVE_HEADER_GLOBAL_ROUTES
        or url_name in REPLAY_TOKEN_ROUTES or url_name in PUBLIC_SLUG_ROUTES
        or url_name in QR_PAYLOAD_ROUTES or url_name in BODY_SCOPED_ROUTES)
    if url_name in BODY_SCOPED_ROUTES:
        body = getattr(request, "data", {})
        target = _positive_int(body.get("makerspace_id")) if hasattr(body, "get") else None
        invalid = target is None
        if target is not None:
            targets.add(target)
    if url_name in QR_PAYLOAD_ROUTES:
        resolved = _qr_payload_makerspace_id(request)
        if resolved is not None:
            targets.add(resolved)
    if url_name in PUBLIC_SLUG_ROUTES:
        from .lookup import get_public_makerspace
        from django.http import Http404
        try:
            targets.add(get_public_makerspace(kwargs.get("makerspace_slug")).pk)
        except Http404:
            invalid = True
    if url_name in REPLAY_TOKEN_ROUTES:
        token = kwargs.get("public_token")
        resolved = apps.get_model("makerspaces.StationCredential").objects.filter(
            public_token=token,
        ).values_list("station__makerspace_id", flat=True).first() if token else None
        if resolved is not None:
            targets.add(resolved)
        else:
            invalid = True
    route_value = None
    if registered:
        route_value = kwargs.get(registered)
        invalid = route_value is None
    elif 'makerspace_id' in kwargs:
        route_value = kwargs.get('makerspace_id')
    elif url_name == 'admin-makerspace' and 'pk' in kwargs:
        route_value = kwargs.get('pk')
    if route_value is not None:
        parsed = _positive_int(route_value)
        invalid = invalid or parsed is None
        if parsed is not None:
            targets.add(parsed)

    if url_name in MODEL_LOOKUPS:
        pk = kwargs.get('pk')
        resolved = _lookup_makerspace_id(url_name, pk) if pk is not None else None
        invalid = invalid or resolved is None
        if resolved is not None:
            targets.add(resolved)
    elif url_name in TARGET_SET_LOOKUPS:
        pk = kwargs.get('pk')
        invalid = invalid or pk is None
        if pk is not None:
            targets.update(_lookup_makerspace_ids(url_name, pk))
    return url_name, targets, invalid, route_recognized


def _qr_payload_makerspace_id(request):
    body = getattr(request, "data", None)
    payload = body.get("payload") if hasattr(body, "get") else None
    if not isinstance(payload, str) or not payload:
        return None
    from apps.boxes.access import inventory_qr_codes
    from apps.boxes.models import QrCode

    return inventory_qr_codes().filter(
        payload=payload, status=QrCode.Status.ACTIVE,
    ).values_list("makerspace_id", flat=True).first()


def _positive_int(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 and str(parsed) == str(value).strip() else None


def _lookup_makerspace_id(url_name, pk):
    model_path, field = MODEL_LOOKUPS[url_name]
    model = apps.get_model(model_path)
    try:
        return model.objects.values_list(field, flat=True).get(pk=pk)
    except model.DoesNotExist:
        return None


def _lookup_makerspace_ids(url_name, pk):
    model_path, owner_field, tenant_field = TARGET_SET_LOOKUPS[url_name]
    model = apps.get_model(model_path)
    return set(
        model.objects.filter(**{owner_field: pk})
        .values_list(tenant_field, flat=True)
    )
