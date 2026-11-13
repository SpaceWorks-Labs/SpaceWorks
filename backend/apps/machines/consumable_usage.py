"""What a job used, per the machine type's consumable profile (decision 341).

* Estimates (member at intake, staff when quoting, or from the job file) are append-only; the
  latest per consumable is the one a quote prices.
* An actual is recorded ONCE per job and consumable (DB-enforced): staff at completion, the
  member for consumables the type lets members report, or the machine adapter's `job.report`.
  Recording it draws stock in the same transaction -- a linked pool through the pool ledger
  (low-stock alerts included), a linked inventory item through Inventory Availability -- unless
  the pool is the one the job already reserved, which the legacy reconcile path debits.
* Money is not moved here: `priced_items` feeds the pricing kernel, and the charge is raised
  by the existing machine-service charge seam.
"""

from django.core.exceptions import ValidationError as ModelValidationError
from django.db import IntegrityError, transaction
from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit

from .consumable_profiles import parse_quantity, selected_attributes
from .models_consumable_profiles import MachineTypeConsumable, ServiceRequestConsumableUsage as Usage
from .service_errors import ServiceConsumptionInvalid

ESTIMATE, ACTUAL = Usage.Phase.ESTIMATE, Usage.Phase.ACTUAL
MAX_ENTRIES = 32


def type_of(service_request):
    return service_request.queue.machine_type if service_request.queue_id else service_request.bucket.machine.machine_type


def definitions(space, machine_type, *, active_only=True):
    rows = MachineTypeConsumable.objects.filter(makerspace=space, machine_type=machine_type)
    return rows.filter(is_active=True) if active_only else rows


def member_definitions(space, machine_type):
    """What the member's request form asks for: consumables estimated by the member or the file."""
    return definitions(space, machine_type).filter(estimate_by__in=("member", "file"))


def parse_entries(space, machine_type, entries, *, field="consumables"):
    """`[{key, quantity, attributes?}]` -> `[(definition, quantity, attributes)]`, all-or-nothing."""
    if entries in (None, []):
        return []
    if not isinstance(entries, list) or len(entries) > MAX_ENTRIES:
        raise ValidationError({field: gettext("Send up to 32 consumables as a list.")})
    by_key = {row.key: row for row in definitions(space, machine_type)}
    parsed, seen = [], set()
    for entry in entries:
        key = entry.get("key") if isinstance(entry, dict) else None
        definition = by_key.get(key)
        if definition is None:
            raise ValidationError({field: gettext("{key} is not a consumable of this machine type.").format(key=key),
                                   "code": "unknown_consumable_key"})
        if key in seen:
            raise ValidationError({field: gettext("Each consumable may appear only once.")})
        seen.add(key)
        try:
            quantity = parse_quantity(entry.get("quantity"), definition.unit)
            attributes = selected_attributes(definition.attributes, entry.get("attributes"))
        except ModelValidationError as exc:
            raise ValidationError({field: exc.messages, "key": key}) from exc
        parsed.append((definition, quantity, attributes))
    return parsed


def _row(service_request, definition, quantity, attributes, *, phase, source, device_ref=""):
    return Usage.objects.create(
        makerspace_id=service_request.makerspace_id, service_request=service_request, definition=definition,
        key=definition.key, name=definition.name, kind=definition.kind, unit=definition.unit, phase=phase,
        quantity=quantity, attributes=attributes, source=source, device_ref=device_ref,
        unit_price=definition.unit_price if phase == ACTUAL else None)


def record_estimates(service_request, actor, entries, *, source):
    machine_type = type_of(service_request)
    parsed = parse_entries(service_request.makerspace, machine_type, entries, field="consumable_estimates")
    if source == "member":
        allowed = {"member", "file"}
        if any(definition.estimate_by not in allowed for definition, _, _ in parsed):
            raise ValidationError({"consumable_estimates": gettext("Staff estimate that consumable, not you.")})
        missing = member_definitions(service_request.makerspace, machine_type).filter(required=True).exclude(
            key__in=[definition.key for definition, _, _ in parsed])
        if missing.exists():
            raise ValidationError({"consumable_estimates": gettext("Estimate {name} for this job.").format(
                name=missing.first().name), "code": "consumable_estimate_required"})
    rows = [_row(service_request, d, q, a, phase=ESTIMATE, source=source) for d, q, a in parsed]
    if rows:
        audit.record(actor, "machine_service.consumables_estimated", makerspace=service_request.makerspace,
                     target=service_request, meta={"source": source, "keys": [row.key for row in rows]})
    return rows


def record_actuals(service_request, actor, entries, *, source, device_ref=""):
    """Record actual use once per consumable; an identical replay is a no-op, a different one is refused."""
    parsed = parse_entries(service_request.makerspace, type_of(service_request), entries)
    created = []
    with transaction.atomic():
        for definition, quantity, attributes in parsed:
            if source != "staff" and source not in definition.record_by:
                raise ValidationError({"consumables": gettext("{name} is recorded by staff.").format(
                    name=definition.name), "code": "consumable_recorder_not_allowed"})
            existing = Usage.objects.filter(service_request=service_request, definition=definition,
                                            phase=ACTUAL).first()
            if existing is not None:
                if existing.quantity == quantity and existing.source == source:
                    continue
                raise ValidationError({"consumables": gettext("{name} was already recorded for this job.").format(
                    name=definition.name), "code": "consumable_already_recorded"})
            try:
                with transaction.atomic():
                    row = _row(service_request, definition, quantity, attributes, phase=ACTUAL, source=source,
                               device_ref=device_ref)
            except IntegrityError as exc:
                raise ValidationError({"consumables": gettext("{name} was already recorded for this job.").format(
                    name=definition.name), "code": "consumable_already_recorded"}) from exc
            from .consumable_stock import draw
            draw(service_request, actor, definition, quantity)
            created.append(row)
        if created:
            audit.record(actor, "machine_service.consumables_recorded", makerspace=service_request.makerspace,
                         target=service_request, meta={"source": source, "keys": [row.key for row in created],
                                                       "quantities": [str(row.quantity) for row in created]})
    return created


MEMBER_REPORT_STATUSES = ("accepted", "in_progress", "completed")


def member_reportable(service_request):
    """Consumables the member may report on their own job, each with its recorded actual (or None)."""
    if service_request.status not in MEMBER_REPORT_STATUSES:
        return []
    actuals = {row.definition_id: row.quantity for row in latest(service_request, ACTUAL)}
    rows = [row for row in definitions(service_request.makerspace, type_of(service_request))
            if "member" in row.record_by]
    for row in rows:
        row.recorded_quantity = actuals.get(row.pk)
    return rows


def require_required(service_request):
    """A required consumable must have its actual before the job completes."""
    recorded = Usage.objects.filter(service_request=service_request, phase=ACTUAL).values_list("definition_id", flat=True)
    missing = definitions(service_request.makerspace, type_of(service_request)).filter(required=True).exclude(
        pk__in=list(recorded)).first()
    if missing is not None:
        raise ServiceConsumptionInvalid(f"Record how much {missing.name} this job used.")


def latest(service_request, phase):
    """One row per consumable: the actual, or the newest estimate."""
    rows = {}
    for row in Usage.objects.filter(service_request=service_request, phase=phase).select_related("definition"):
        rows[row.definition_id] = row
    return list(rows.values())


def priced_items(service_request, phase):
    """Lines for the pricing kernel; an estimate is priced at today's rate, an actual at its snapshot."""
    items = []
    for row in latest(service_request, phase):
        price = row.unit_price if phase == ACTUAL else row.definition.unit_price
        if price is not None and price > 0 and (phase == ACTUAL or row.definition.is_active):
            items.append({"definition_id": row.definition_id, "key": row.key, "name": row.name, "kind": row.kind,
                          "unit": row.unit, "quantity": row.quantity, "unit_price": price})
    return items


def event_consumables(request_ids):
    """Profile actuals per job for event machine-use views, as `{label, unit, quantity}` lines.

    The legacy ledger already measures a job's reserved pool (`MachineUsageEntry`), so an actual that
    restates it is left out: one drawn from that same pool, or the upgrade-seeded primary "material"
    row (key `material`, no stock link) on a job that reserved a pool.
    """
    out = {}
    rows = Usage.objects.filter(service_request_id__in=list(request_ids), phase=ACTUAL).select_related(
        "definition", "service_request").order_by("id")
    for row in rows:
        reserved = row.service_request.run_consumable_pool_id
        definition = row.definition
        if reserved and (definition.consumable_pool_id == reserved or (
                definition.key == "material" and not definition.consumable_pool_id and not definition.product_id)):
            continue
        out.setdefault(row.service_request_id, []).append(
            {"label": row.name, "unit": row.unit, "quantity": str(row.quantity)})
    return out
