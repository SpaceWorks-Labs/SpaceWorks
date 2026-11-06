"""Hosting billing per space (#187A): recorded invoices, offline receipts, void, and the
non-payment enforcement that only runs when the superadmin turned it on.

Money never moves here: an invoice is a record of what the space owes the platform, a
receipt records money the platform already received (offline, or through a checkout
the payer opened). Every write is superadmin-only (the online settlement is the
provider's signed callback) and audited at platform level and in the space.
"""

from django.utils.translation import gettext
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from apps.makerspaces.lifecycle_authority import require_platform_superadmin
from apps.makerspaces.models import Makerspace
from apps.space_controls.errors import SpaceControlConflict

from .availability import require_plans_enabled
from .models import HostingInvoice, HostingInvoiceReceipt, PlatformHostingBillingSettings

OVERDUE_REASON = ("A hosting invoice for this space is overdue. Pay it, or contact the platform operator, "
                  "to end read-only mode.")


def _number():
    year = timezone.now().year
    last = HostingInvoice.objects.filter(number__startswith=f"SWH-{year}-").aggregate(top=Max("number"))["top"]
    sequence = int(last.rsplit("-", 1)[1]) + 1 if last else 1
    return f"SWH-{year}-{sequence:05d}"


def create_invoice(actor, data):
    require_platform_superadmin(actor)
    require_plans_enabled()
    with transaction.atomic():
        space = Makerspace.objects.select_for_update().get(pk=data["makerspace_id"])
        from .enforcement import _assignment
        assignment = _assignment(space)
        row = HostingInvoice.objects.create(
            number=_number(), makerspace=space, makerspace_id_snapshot=space.pk, makerspace_name=space.name,
            plan=assignment.plan if assignment else None, description=data["description"],
            amount_minor=data["amount_minor"], currency=data["currency"].upper(), due_on=data["due_on"],
            period_start=data.get("period_start"), period_end=data.get("period_end"), created_by=actor)
        audit.record(actor, "managed_hosting.invoice_created", makerspace=space, target=row,
                     meta={"amount_minor": row.amount_minor, "currency": row.currency, "due_on": str(row.due_on)})
    return row


def _settle(invoice, *, method, reference, received_on, amount_minor, note, actor):
    HostingInvoiceReceipt.objects.create(invoice=invoice, method=method, reference=reference[:200],
                                         received_on=received_on, amount_minor=amount_minor,
                                         note=note[:300], recorded_by=actor)
    invoice.status, invoice.paid_at = HostingInvoice.Status.PAID, timezone.now()
    invoice.save(update_fields=["status", "paid_at"])
    audit.record(actor, "managed_hosting.invoice_paid", makerspace=invoice.makerspace, target=invoice,
                 meta={"method": method, "amount_minor": amount_minor})
    if invoice.makerspace_id:
        transaction.on_commit(lambda: lift_if_settled(invoice.makerspace_id))


def record_payment(actor, invoice_id, *, method, reference, received_on, note=""):
    require_platform_superadmin(actor)
    require_plans_enabled()
    if method.startswith("online_"):
        raise ValidationError({"method": gettext("Online payments are recorded by the provider's callback.")})
    with transaction.atomic():
        invoice = HostingInvoice.objects.select_for_update().get(pk=invoice_id)
        if invoice.status != HostingInvoice.Status.OPEN:
            raise SpaceControlConflict("invoice_not_open", "Only an open invoice can be marked paid.")
        _settle(invoice, method=method, reference=reference, received_on=received_on,
                amount_minor=invoice.amount_minor, note=note, actor=actor)
    return invoice


def void(actor, invoice_id, reason):
    require_platform_superadmin(actor)
    require_plans_enabled()
    reason = str(reason or "").strip()
    if not 3 <= len(reason) <= 300:
        raise ValidationError({"reason": gettext("Give a reason of 3 to 300 characters.")})
    with transaction.atomic():
        invoice = HostingInvoice.objects.select_for_update().get(pk=invoice_id)
        if invoice.status != HostingInvoice.Status.OPEN:
            raise SpaceControlConflict("invoice_not_open", "Only an open invoice can be voided.")
        invoice.status, invoice.voided_at, invoice.void_reason = HostingInvoice.Status.VOID, timezone.now(), reason
        invoice.save(update_fields=["status", "voided_at", "void_reason"])
        audit.record(actor, "managed_hosting.invoice_voided", makerspace=invoice.makerspace, target=invoice, meta={})
    if invoice.makerspace_id:
        transaction.on_commit(lambda: lift_if_settled(invoice.makerspace_id))
    return invoice


def overdue_q(today, grace_days):
    from datetime import timedelta
    return {"status": HostingInvoice.Status.OPEN, "due_on__lt": today - timedelta(days=grace_days)}


def is_overdue(invoice, today=None):
    today = today or timezone.localdate()
    return invoice.status == HostingInvoice.Status.OPEN and invoice.due_on < today


def lift_if_settled(makerspace_id):
    """End payment-overdue read-only once nothing is overdue past the grace period."""
    from apps.space_controls.models import SpaceControlState
    from apps.space_controls.services_access import lift_read_only

    settings_row = PlatformHostingBillingSettings.load()
    if HostingInvoice.objects.filter(makerspace_id=makerspace_id,
                                     **overdue_q(timezone.localdate(), settings_row.grace_days)).exists():
        return None
    return lift_read_only(None, makerspace_id, source=SpaceControlState.ReadOnlySource.PAYMENT_OVERDUE)


def enforce_overdue(today=None):
    """Read-only after the grace period, ONLY when the superadmin enabled auto-enforcement."""
    from apps.space_controls.models import SpaceControlState
    from apps.space_controls.services_access import set_read_only

    settings_row = PlatformHostingBillingSettings.load()
    if not settings_row.auto_enforce_enabled:
        return 0
    today = today or timezone.localdate()
    space_ids = set(HostingInvoice.objects.filter(makerspace__isnull=False, **overdue_q(today, settings_row.grace_days))
                    .values_list("makerspace_id", flat=True))
    changed = 0
    for space_id in sorted(space_ids):
        try:
            if set_read_only(None, space_id, OVERDUE_REASON, source=SpaceControlState.ReadOnlySource.PAYMENT_OVERDUE):
                changed += 1
        except SpaceControlConflict:
            continue  # archived or importing: nothing to restrict
    return changed
