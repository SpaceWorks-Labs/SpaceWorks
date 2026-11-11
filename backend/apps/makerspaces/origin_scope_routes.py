from django.apps import apps

# Thin barrel over the route tables: every table is re-exported here, so
# `from apps.makerspaces.origin_scope_routes import X` keeps resolving.
from .origin_scope_routes_catalog import (  # noqa: F401 - re-exported tables
    BASE_MODEL_LOOKUPS,
    TARGET_SET_LOOKUPS,
    PUBLIC_SLUG_ROUTES,
    REPLAY_TOKEN_ROUTES,
    SERVICE_TOKEN_ROUTES,
    QR_PAYLOAD_ROUTES,
    BODY_SCOPED_ROUTES,
    MAKERSPACE_KWARG_ROUTES,
    PRINTER_MAKERSPACE_ROUTES,
    WP4_ROUTES,
    QUERY_SCOPED_ROUTES,
    NATIVE_HEADER_GLOBAL_ROUTES,
    REQUEST_ACTIONS,
    MACHINE_SERVICE_ACTIONS,
    EVENT_MODEL_LOOKUPS,
    P2_EVENT_MODEL_LOOKUPS,
    MODEL_LOOKUPS,
    P2_BOOKING_LOOKUPS,
)


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
        or url_name in QR_PAYLOAD_ROUTES or url_name in BODY_SCOPED_ROUTES
        or url_name in SERVICE_TOKEN_ROUTES)
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
    if url_name in SERVICE_TOKEN_ROUTES:
        token = kwargs.get("public_token")
        resolved = apps.get_model("machines.MachineServiceRequest").objects.filter(
            public_token=token,
        ).values_list("makerspace_id", flat=True).first() if token else None
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

    # A pinned `makerspace_id` bounds the whole lookup in the view (external label values
    # are unique only per makerspace), so it is the target; otherwise the payload's space.
    pinned = _positive_int(body.get("makerspace_id"))
    if pinned is not None:
        return pinned
    return inventory_qr_codes().filter(
        payload=payload.strip(), status=QrCode.Status.ACTIVE,
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
