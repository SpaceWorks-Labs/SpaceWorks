"""Exact host targets for reimbursement, stage-form and core payout routes.

Event routes resolve the event's own host first and refuse a mismatched makerspace_id
path segment; payout routes resolve the obligation's retained host, which survives Events
or reimbursement removal. There is never a selected-tenant fallback.
"""
from django.apps import apps

from apps.accounts.reimbursement_route_catalog import BY_NAME
from apps.separability.registry import runtime_active


def reimbursement_route_targets(name, kwargs):
    declaration = BY_NAME.get(name)
    if declaration is None:
        return None
    _, kind, _ = declaration
    if kind == "account":
        return name, set(), False, True
    if kind == "tenant":
        tenant = kwargs.get("makerspace_id")
        exists = apps.get_model("makerspaces.Makerspace").objects.filter(pk=tenant).exists()
        return name, {tenant} if exists else set(), not exists, True
    if kind == "event":
        if not runtime_active("events"):
            return name, set(), True, True
        owner = apps.get_model("events.Event").objects.filter(pk=kwargs.get("pk")).values_list(
            "makerspace_id", flat=True).first()
    else:
        owner = apps.get_model("payments.EventPayoutObligation").objects.filter(
            pk=kwargs.get("obligation_id")).values_list("makerspace_id", flat=True).first()
    requested = kwargs.get("makerspace_id")
    invalid = owner is None or (requested is not None and requested != owner)
    return name, {owner} if not invalid else set(), invalid, True
