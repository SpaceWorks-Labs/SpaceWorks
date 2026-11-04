"""The work record of a repair: visits, remarks, parts, the quote, approval and payout.

* Visits and remarks (with photos) by the assigned Technician or a manager.
* Parts USED come out of stock only through `inventory/availability.py` (Q-T3: the
  Technician may record them; audited there and here). Parts NEEDED become To-Buy rows
  under the matching parent (`machines.tobuy` / `inventory.tobuy`) when that switch is
  on; rooms have no To-Buy (#137 Q-C3), so they are only recorded.
* The quote is approved by the area manager or the Space Manager, no threshold (C-5).
* A payout is recorded only by staff with finance authority in that area, only after an
  approved quote, and only through the ledger (`record_expense`, source `repairs.payout`).
  Money never moves here (#59, #93); the Technician never records a payout.
"""

from decimal import Decimal, InvalidOperation

from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit import services as audit

from . import areas, errors, history, notify, photos
from .services_issues import _expect, _require_manager, _require_worker

OPEN = ("triaged", "assigned", "in_progress")


def _contact(issue, contact_id):
    from apps.maintenance.models import TechnicianContact
    if contact_id is None:
        return None
    row = TechnicianContact.objects.filter(makerspace_id=issue.makerspace_id, pk=contact_id).first()
    if row is None:
        raise ValidationError({"contact_id": "Choose a technician of this makerspace."})
    return row


def log_work(actor, issue, *, kind, note="", occurred_on=None, contact_id=None, photo_tokens=(), owner=None):
    """A visit (date, who) or a remark, with optional photos."""
    if kind not in ("visit", "remark"):
        raise ValidationError({"kind": "Log a visit or a remark."})
    validated = photos.validate(issue.makerspace, photo_tokens, owner) if photo_tokens else []
    with transaction.atomic():
        issue = history.lock(issue)
        _require_worker(actor, issue)
        areas.require(issue.makerspace, areas.REPAIRS[issue.area])
        _expect(issue, *OPEN)
        note = str(note or "").strip()
        if not note and not validated:
            raise ValidationError({"note": "Add a note or a photo."})
        if kind == "visit" and occurred_on is None:
            raise ValidationError({"occurred_on": "Give the visit date."})
        photos.attach(issue, validated, "work", actor)
        history.step(issue, kind, actor, f"repair.{kind}_logged", contact=_contact(issue, contact_id), note=note,
                     occurred_on=occurred_on, meta={"photos": len(validated)})
    return issue


def _product(issue, product_id):
    from apps.inventory.models import InventoryProduct, TrackingMode
    product = InventoryProduct.objects.filter(makerspace_id=issue.makerspace_id, pk=product_id,
                                              is_archived=False).first()
    if product is None:
        raise ValidationError({"product_id": "Choose an inventory item of this makerspace."})
    if product.tracking_mode == TrackingMode.INDIVIDUAL:
        raise ValidationError({"product_id": "Units tracked one by one cannot be used up as parts."})
    return product


def _to_buy(actor, issue, name, quantity):
    from apps.procurement.models import ToBuyItem
    key = areas.TOBUY.get(issue.area)
    if key is None or not areas.on(issue.makerspace, key):
        return None
    machines = issue.area == areas.MACHINES
    item = ToBuyItem.objects.create(
        makerspace=issue.makerspace, kind=ToBuyItem.Kind.PRINTING if machines else ToBuyItem.Kind.HARDWARE,
        machine_type_id=areas.machine_type_id(issue) if machines else None, name=name, quantity=quantity,
        created_by=actor)
    audit.record(actor, "procurement.item_added", makerspace=issue.makerspace, target=item,
                 meta={"source": "repair", "issue_id": issue.pk})
    return item


@transaction.atomic
def record_part(actor, issue, *, kind, quantity, product_id=None, name=""):
    from apps.inventory import availability
    from apps.maintenance.models import RepairPart
    issue = history.lock(issue)
    _require_worker(actor, issue)
    areas.require(issue.makerspace, areas.REPAIRS[issue.area])
    _expect(issue, *OPEN)
    if type(quantity) is not int or quantity < 1:
        raise ValidationError({"quantity": "Give a whole number of parts."})
    product = _product(issue, product_id) if product_id else None
    name = (str(name or "").strip() or getattr(product, "name", ""))[:200]
    if not name:
        raise ValidationError({"name": "Name the part."})
    item = None
    if kind == "used":
        if product is None:
            raise ValidationError({"product_id": "Choose the inventory item the part came from."})
        try:
            availability.consume_available(product, quantity, f"Repair issue #{issue.pk}", actor)
        except availability.InsufficientStock:
            raise errors.bad_state("Not enough of that item is available.", "insufficient_stock")
    elif kind == "needed":
        item = _to_buy(actor, issue, name, quantity)
    else:
        raise ValidationError({"kind": "A part is used or needed."})
    part = RepairPart.objects.create(issue=issue, kind=kind, product=product, name=name, quantity=quantity,
                                     to_buy_item=item)
    history.step(issue, f"parts_{kind}", actor, f"repair.parts_{kind}", note=f"{quantity} x {name}",
                 meta={"part_id": part.pk, "product_id": getattr(product, "pk", None), "quantity": quantity,
                       "to_buy_item_id": getattr(item, "pk", None)})
    return part


def _amount(value, field="amount"):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError):
        raise ValidationError({field: "Enter an amount."})
    if not amount.is_finite() or amount < 0 or amount.as_tuple().exponent < -2:
        raise ValidationError({field: "Enter a positive amount with at most two decimals."})
    return amount


@transaction.atomic
def quote(actor, issue, *, amount, currency, contact_id=None, note=""):
    issue = history.lock(issue)
    _require_worker(actor, issue)
    areas.require(issue.makerspace, areas.REPAIRS[issue.area])
    _expect(issue, *OPEN)
    amount, currency = _amount(amount), str(currency or "").strip().lower()
    if len(currency) != 3 or not currency.isalpha():
        raise ValidationError({"currency": "Use a three-letter currency code."})
    contact = _contact(issue, contact_id)
    issue.quote_state, issue.quote_amount, issue.quote_currency = issue.QuoteState.PENDING, amount, currency
    issue.quote_contact, issue.quote_note = contact, str(note or "").strip()[:2000]
    issue.save(update_fields=["quote_state", "quote_amount", "quote_currency", "quote_contact", "quote_note",
                              "updated_at"])
    history.step(issue, "quote", actor, "repair.quote_recorded", contact=contact, note=note, amount=amount,
                 currency=currency, meta={"currency": currency, "contact_id": getattr(contact, "pk", None)})
    notify.staff(issue, "repair_quote_pending")
    return issue


@transaction.atomic
def decide_quote(actor, issue, *, approve, note=""):
    issue = history.lock(issue)
    _require_manager(actor, issue)  # C-5: the area manager or the Space Manager
    if issue.quote_state != issue.QuoteState.PENDING:
        raise errors.bad_state("There is no quote waiting for a decision.", "quote_not_pending")
    issue.quote_state = issue.QuoteState.APPROVED if approve else issue.QuoteState.DECLINED
    issue.save(update_fields=["quote_state", "updated_at"])
    kind = "quote_approved" if approve else "quote_declined"
    history.step(issue, kind, actor, f"repair.{kind}", note=note, amount=issue.quote_amount,
                 currency=issue.quote_currency)
    return issue


def record_payout(actor, issue, *, amount, currency, method, reference="", receipt_id=None, entry_date=None):
    from apps.payments import ledger_api
    from apps.payments.finance_scope import finance_view
    with transaction.atomic():
        issue = history.lock(issue)
        domain = areas.LEDGER_DOMAIN[issue.area]
        machine_type_id = areas.machine_type_id(issue)
        if not finance_view(actor, issue.makerspace_id).may_record(domain, machine_type_id):
            raise PermissionDenied("You cannot record spending in this area.")
        if issue.quote_state != issue.QuoteState.APPROVED:
            raise errors.quote_not_approved()
        if issue.payout_entry_id:
            raise errors.bad_state("This repair's payout is already recorded.", "payout_recorded")
        amount = _amount(amount)
        if amount <= 0:
            raise ValidationError({"amount": "Enter what was paid."})
        payee = issue.quote_contact.name if issue.quote_contact_id else ""
        entry = ledger_api.record_expense(
            issue.makerspace, domain, machine_type_id, amount, currency or issue.quote_currency, method, reference,
            receipt_id, "repairs.payout", issue.pk, actor, category="repair",
            description=f"Repair: {issue.title}"[:300], entry_date=entry_date, counterparty=payee[:150])
        issue.payout_entry = entry
        issue.save(update_fields=["payout_entry", "updated_at"])
        history.step(issue, "payout", actor, "repair.payout_recorded", amount=amount, currency=entry.currency,
                     meta={"ledger_entry_id": entry.pk, "domain": domain, "machine_type_id": machine_type_id,
                           "method": method})
    return issue
