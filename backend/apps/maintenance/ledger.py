"""Maintenance spending reaches the finance ledger (#94, #100, #102).

A maintenance run that cost money posts ONE `maintenance` expense through L5's
`record_expense`, inside the same transaction as its append-only log row. The row is
tagged with the area's domain so finance visibility follows rbac (`finance_scope`):
machines (with the machine type, so a type-scoped Machine Manager sees only their types),
items and units under `inventory`, rooms under `bookings`.

Spending is always recorded (#128 C-15): whoever may log the maintenance (the area
manager, the Space Manager or a covering Technician, #102) records its cost; the
`finance.ledger` switch only hides the screens. The log is the ledger row's source
(`maintenance.log` or `maintenance.subject_log` plus its id), so a retried call never
records the money twice. A cost of zero or none records nothing.
"""

from django.utils.translation import gettext
from decimal import Decimal

from rest_framework.exceptions import ValidationError

SOURCE_MACHINE = "maintenance.log"
SOURCE_SUBJECT = "maintenance.subject_log"
DEFAULT_METHOD = "other"
#: Item and room subjects to their ledger domain (machines carry their own).
SUBJECT_DOMAIN = {"inventory_product": "inventory", "inventory_asset": "inventory", "bookable_space": "bookings"}


def clean_method(value):
    from apps.payments.models_ledger_entries import LedgerEntry
    value = str(value or DEFAULT_METHOD).strip().lower()
    if value not in LedgerEntry.Method.values:
        raise ValidationError({"cost_method": gettext("Choose how the maintenance was paid.")})
    return value


def clean_currency(space, value):
    """The given three-letter code, else the space's default payment currency."""
    if value in (None, ""):
        from apps.payments.models_settings import MakerspacePaymentSettings
        value = MakerspacePaymentSettings.objects.filter(makerspace=space).values_list(
            "default_currency", flat=True).first() or "usd"
    value = str(value).strip().lower()
    if len(value) != 3 or not value.isalpha():
        raise ValidationError({"cost_currency": gettext("Use a three-letter currency code.")})
    return value


def post_cost(actor, space, *, domain, machine_type, cost, method, currency, source_kind, source_id, description):
    """Record the run's cost as a maintenance expense; None when nothing was spent."""
    if cost is None or Decimal(cost) <= 0:
        return None
    from apps.payments import ledger_api
    return ledger_api.record_expense(
        space, domain, machine_type, Decimal(cost), clean_currency(space, currency), clean_method(method), "",
        None, source_kind, source_id, actor, category="maintenance", description=description[:300])


def post_machine_log(actor, log, *, method=None, currency=None):
    machine = log.machine
    return post_cost(actor, machine.makerspace, domain="machines", machine_type=machine.machine_type_id,
                     cost=log.cost, method=method, currency=currency, source_kind=SOURCE_MACHINE, source_id=log.pk,
                     description=f"Maintenance: {machine.name} - {log.summary}")


def post_subject_log(actor, log, subject_name, *, method=None, currency=None):
    return post_cost(actor, log.makerspace, domain=SUBJECT_DOMAIN[log.subject_type], machine_type=None,
                     cost=log.cost, method=method, currency=currency, source_kind=SOURCE_SUBJECT, source_id=log.pk,
                     description=f"Maintenance: {subject_name} - {log.summary}")
