"""Resolve which tenant a protected request targets (split from `scope_registry.py`).

Re-exported from ``scope_registry``. ``resolve_target_once`` and ``classify`` stay in
the barrel and call ``resolve_target`` through it, so the barrel name remains the one
seam every caller (and every override of it) goes through.
"""
from django.urls import resolve

from apps.apiclients.scope_registry_routes import (
    TARGET_CLIENT_SUBJECT,
    TARGET_GLOBAL,
    TARGET_PUBLIC_HANDLE,
    TARGET_TENANT_SLUG,
    TARGET_TENANT_TOKEN,
)

from .scope_registry_public_pages import resolve_handle_target


def _request_match(request):
    match = getattr(request, "resolver_match", None)
    if match is not None:
        return match
    if hasattr(request, "_scope_registry_resolver_match"):
        return request._scope_registry_resolver_match
    try:
        match = resolve(request.path_info)
    except Exception:
        match = None
    request._scope_registry_resolver_match = match
    return match


def resolve_view_name(request):
    try:
        match = _request_match(request)
        return getattr(match, "view_name", None) if match is not None else None
    except Exception:
        return None


def resolve_target(request, entry):
    if entry.target_mode == TARGET_GLOBAL:
        return None, True
    try:
        match = _request_match(request)
        kwargs = getattr(match, "kwargs", {}) or {}
        if entry.target_mode == TARGET_PUBLIC_HANDLE:
            return resolve_handle_target(request, match)
        if entry.target_mode == TARGET_CLIENT_SUBJECT:
            from .read_contract import resolve_read_target
            return resolve_read_target(request, match)
        if entry.target_mode == TARGET_TENANT_SLUG:
            from apps.makerspaces.lookup import get_public_makerspace

            # get_public_makerspace raises Http404 for an unknown or unservable
            # identifier, which the outer except turns into resolved=False. The
            # explicit None check keeps that contract if it ever starts returning
            # None instead: an unresolved tenant must never read as resolved, or
            # the fail-open this registry exists to close comes straight back.
            target = get_public_makerspace(kwargs.get("makerspace_slug"))
            return (target, True) if target is not None else (None, False)
        if entry.target_mode != TARGET_TENANT_TOKEN:
            return None, False
        token = kwargs.get("public_token")
        view_name = getattr(match, "view_name", None)
        from apps.accounts.programme_route_catalog import BY_NAME
        if view_name in BY_NAME:
            from apps.makerspaces.origin_scope_programme import programme_route_targets
            from apps.makerspaces.models import Makerspace
            _, targets, invalid, _ = programme_route_targets(view_name, kwargs)
            if invalid or len(targets) != 1:
                return None, False
            target = Makerspace.objects.filter(pk=next(iter(targets))).first()
            return target, target is not None
        if view_name in {"public-profile", "public-profile-activity", "public-profile-events", "public-profile-projects", "public-profile-github"}:
            from apps.makerspaces.public_profile_access import resolve_public_profile
            claim, _ = resolve_public_profile(kwargs.get("handle"), request)
            return claim.profile.membership.makerspace, True
        if view_name == "public-event-code":
            from apps.events.website_visibility import resolve as resolve_event
            from apps.makerspaces.public_page_access import require_scope
            event = resolve_event(None, token)
            require_scope("makerspace", event.makerspace, request)
            return event.makerspace, True
        if view_name == "hardware_requests:request-status":
            from apps.hardware_requests.models import HardwareRequest

            row = HardwareRequest.objects.select_related("makerspace").filter(
                public_token=token
            ).first()
        elif view_name in {"public-printer-service-status", "public-machine-service-status"}:
            from apps.machines.models import MachineServiceRequest

            row = MachineServiceRequest.objects.select_related("makerspace").filter(
                public_token=token
            ).first()
        else:
            return None, False
        return (row.makerspace, True) if row is not None else (None, False)
    except Exception:
        return None, False
