"""Resolve a request's URL match once per request (split from `scope_registry.py`).

Re-exported from ``scope_registry``; import from there.
"""
from django.urls import resolve


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
