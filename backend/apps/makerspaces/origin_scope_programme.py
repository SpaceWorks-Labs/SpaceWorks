"""Resolve exact programme hosts; global account utilities have no tenant fallback."""
from django.apps import apps

from apps.accounts.programme_route_catalog import BY_NAME, NATIVE_WEB_ONLY
from apps.separability.registry import runtime_active


def programme_route_targets(name, kwargs):
    declaration = BY_NAME.get(name)
    if declaration is None:
        return None
    _, kind = declaration
    # Lane L21a (#173): event-role desks stay web-only until the native event-role contract.
    native = name not in NATIVE_WEB_ONLY
    if kind == "account":
        return name, set(), False, native
    if not runtime_active("events"):
        return name, set(), True, native
    if kind == "tenant":
        tenant = kwargs.get("makerspace_id")
        exists = apps.get_model("makerspaces.Makerspace").objects.filter(pk=tenant).exists()
        return name, {tenant} if exists else set(), not exists, native
    label, lookup, value, path = {
        "event": ("events.Event", "pk", kwargs.get("pk"), "makerspace_id"),
        "series": ("events.EventSeries", "pk", kwargs.get("pk"), "makerspace_id"),
        "public_event": ("events.Event", "public_token", kwargs.get("public_token"), "makerspace_id"),
        "certificate": ("events.EventAttendanceCertificate", "serial", kwargs.get("verification_id"), "event__makerspace_id"),
    }[kind]
    owner = apps.get_model(label).objects.filter(**{lookup: value}).values_list(path, flat=True).first()
    requested = kwargs.get("makerspace_id")
    invalid = owner is None or (requested is not None and requested != owner)
    return name, {owner} if not invalid else set(), invalid, native
