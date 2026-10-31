"""The finance ledger's write API, the ONE way money-out (and non-charge money-in) is recorded.

Stable contract for every lane that moves money (#94, LANE-RULES §12):

    record_expense(makerspace, domain, machine_type, amount, currency, method, reference,
                   receipt, source_kind, source_id, actor, *, category="other_expense",
                   description="", entry_date=None, counterparty="", event=None) -> LedgerEntry
    record_receipt(...same shape..., category="other_income") -> LedgerEntry
    void(entry, actor, reason) -> LedgerEntry

* Always recorded (#128 C-15): `finance.ledger` hides only the screens and reports, so
  these functions never consult it. Money never moves here; they record that it moved.
* `domain` is one of `LedgerEntry.Domain` (inventory, loans, machines, bookings, events,
  membership, donations, shop, general); `machine_type` (a MachineType or id, or None) is
  only allowed with domain `machines`. Together they decide who sees the row (#100).
* `method` is one of `LedgerEntry.Method`; cash lands in the cash account, every other
  method in the bank account (the receipts-and-payments split per financial year).
* `receipt` is an optional `evidence.EvidencePhoto` of this space (a photo of the bill),
  uploaded through the staging-key presign; it is finalized and marked consumed here, in
  the same transaction, and can back exactly one entry.
* `source_kind`/`source_id` name what caused the row (`procurement.to_buy` + item id,
  `repairs.payout` + job id, ...). A second call for the same live source returns the
  first row when the amount and currency match and refuses (`ledger_source_conflict`)
  otherwise, so a retried caller never records spending twice. Use `source_kind="manual"`
  with no id only for rows staff type in.
* Callers authorize the actor in their own workflow first; `finance_scope.finance_view(
  actor, space).may_record(domain, machine_type_id)` is the shared answer.
* Every write emits `ledger.expense_recorded` / `ledger.entry_created` / `ledger.entry_voided`.
"""

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.makerspaces.local_time import local_now
from apps.payments.exceptions_ledger import LedgerConflict
from apps.payments.models_ledger_entries import LedgerEntry


def _machine_type(machine_type):
    if machine_type is None or machine_type == "":
        return None
    from apps.machines.models import MachineType

    if isinstance(machine_type, MachineType):
        return machine_type
    found = MachineType.objects.filter(pk=machine_type).first()
    if found is None:
        raise LedgerConflict("That machine type does not exist.", "machine_type_invalid")
    return found


def _staged_receipt(makerspace, receipt):
    """(photo, finalized size) for an uploaded receipt, promoted OUTSIDE any row lock."""
    if receipt is None or receipt == "":
        return None, None
    from django.conf import settings

    from apps.tenant_migration.gate_runtime import assert_write_allowed

    from apps.evidence import storage
    from apps.evidence.models import EvidencePhoto

    photo = receipt if isinstance(receipt, EvidencePhoto) else EvidencePhoto.objects.filter(pk=receipt).first()
    if photo is None or photo.makerspace_id != makerspace.pk or photo.evidence_type != "receipt":
        raise LedgerConflict("That receipt upload is not in this space.", "receipt_invalid")
    assert_write_allowed(makerspace.pk)
    try:
        finalized = storage.finalize_upload(photo, settings.EVIDENCE_MAX_BYTES)
    except storage.EvidenceObjectValidationError:
        raise LedgerConflict("The receipt upload is invalid, expired or too large.", "receipt_invalid")
    if finalized is None:
        raise LedgerConflict("The receipt has not been uploaded yet.", "receipt_not_uploaded")
    return photo, getattr(finalized, "size", None)


def _attach_receipt(photo, size):
    """Inside the recording transaction: retention lock order, quota once, consumed mark."""
    if photo is None:
        return None
    from apps.evidence.consumption import mark_consumed
    from apps.evidence.finalization import charge_storage_once, lock_evidence_for_attachment

    if not lock_evidence_for_attachment(photo.pk):
        raise LedgerConflict("The receipt has expired under the retention policy.", "receipt_invalid")
    if LedgerEntry.objects.filter(receipt=photo).exists():
        raise LedgerConflict("That receipt is already attached to another entry.", "receipt_in_use")
    charge_storage_once(photo, size or photo.size_bytes or 0)
    mark_consumed(photo)
    return photo


def account_for(method):
    return LedgerEntry.Account.CASH if method == LedgerEntry.Method.CASH else LedgerEntry.Account.BANK


@transaction.atomic
def _record(kind, makerspace, domain, machine_type, amount, currency, method, reference, receipt, source_kind,
            source_id, actor, *, category, description, entry_date, counterparty, event):
    from apps.tenant_migration.gate_runtime import assert_write_allowed

    assert_write_allowed(makerspace.pk)
    source_id = str(source_id or "")
    currency = (currency or "").lower()
    amount = Decimal(amount)
    if source_id:
        existing = LedgerEntry.objects.select_for_update().filter(
            makerspace=makerspace, kind=kind, source_kind=source_kind, source_id=source_id,
            voided_at__isnull=True).first()
        if existing is not None:
            if existing.amount == amount and existing.currency == currency:
                return existing
            raise LedgerConflict("This source already has a different live ledger entry; void it first.",
                                 "ledger_source_conflict")
    machine_type = _machine_type(machine_type)
    if machine_type is not None and domain != LedgerEntry.Domain.MACHINES:
        raise LedgerConflict("A machine type belongs on a machines entry.", "machine_type_invalid")
    from django.core.exceptions import ValidationError
    try:
        with transaction.atomic():
            entry = LedgerEntry.objects.create(
                makerspace=makerspace, kind=kind, domain=domain, machine_type=machine_type,
                machine_type_label=getattr(machine_type, "name", "")[:120] if machine_type else "",
                event=event, category=category, method=method, account=account_for(method), amount=amount,
                currency=currency, entry_date=entry_date or local_now(makerspace).date(),
                description=(description or "")[:300] or category.replace("_", " ").capitalize(),
                counterparty=(counterparty or "")[:150],
                reference=(reference or "")[:64], source_kind=source_kind, source_id=source_id,
                receipt=_attach_receipt(*receipt), created_by=actor)
    except ValidationError as exc:
        raise LedgerConflict("; ".join(exc.messages), "ledger_entry_invalid")
    except IntegrityError:
        raise LedgerConflict("This source already has a live ledger entry.", "ledger_source_conflict")
    if kind == LedgerEntry.Kind.EXPENSE:
        audit.record(actor, "ledger.expense_recorded", makerspace=makerspace, target=entry, meta={
            "domain": domain, "machine_type_id": entry.machine_type_id, "category": category,
            "source_kind": source_kind, "source_id": source_id, "currency": currency, "account": entry.account})
    else:
        audit.record(actor, "ledger.entry_created", makerspace=makerspace, target=entry, meta={
            "domain": domain, "machine_type_id": entry.machine_type_id, "category": category,
            "source_kind": source_kind, "source_id": source_id, "currency": currency, "account": entry.account})
    return entry


def record_expense(makerspace, domain, machine_type, amount, currency, method, reference, receipt, source_kind,
                   source_id, actor, *, category="other_expense", description="", entry_date=None, counterparty="",
                   event=None):
    """Record money the space paid out. See the module docstring for the contract."""
    return _record(LedgerEntry.Kind.EXPENSE, makerspace, domain, machine_type, amount, currency, method,
                   reference, _staged_receipt(makerspace, receipt), source_kind, source_id, actor,
                   category=category, description=description, entry_date=entry_date,
                   counterparty=counterparty, event=event)


def record_receipt(makerspace, domain, machine_type, amount, currency, method, reference, receipt, source_kind,
                   source_id, actor, *, category="other_income", description="", entry_date=None, counterparty="",
                   event=None):
    """Record money the space received that is not a member charge (a donation, a grant)."""
    return _record(LedgerEntry.Kind.RECEIPT, makerspace, domain, machine_type, amount, currency, method,
                   reference, _staged_receipt(makerspace, receipt), source_kind, source_id, actor,
                   category=category, description=description, entry_date=entry_date,
                   counterparty=counterparty, event=event)


@transaction.atomic
def void(entry, actor, reason):
    """Void a live entry with a reason. The row stays; it drops out of every total."""
    entry = LedgerEntry.objects.select_for_update().get(pk=getattr(entry, "pk", entry))
    if entry.voided_at is not None:
        raise LedgerConflict("This entry is already void.", "ledger_entry_voided")
    reason = (reason or "").strip()[:300]
    if not reason:
        raise LedgerConflict("Say why the entry is void.", "void_reason_required")
    entry.voided_at, entry.voided_by, entry.void_reason = timezone.now(), actor, reason
    entry.save(update_fields=["voided_at", "voided_by", "void_reason"])
    audit.record(actor, "ledger.entry_voided", makerspace=entry.makerspace, target=entry,
                 meta={"kind": entry.kind, "domain": entry.domain, "category": entry.category,
                       "source_kind": entry.source_kind})
    return entry
