"""Loan fee waivers (lane L15, A14): staff make a loan's fees free, with a reason.

* `waive_loan` writes an append-only `LoanFeeWaiver`. Every PENDING loan charge it covers
  becomes `waived` through the existing `reconciliation.waive` (its own authority check,
  audit and checkout expiry). A charge already PAID is never reversed: the waiver opens a
  staff `RefundCase` in area loans for the refundable balance, and money moves only when a
  staff member approves it (#59). Charges raised later resolve to 0 (`apply_waivers`).
* The deposit is never waivable -- it has its own release path.
* `revoke_waiver` writes a revocation row pointing at the waiver; it affects only charges
  not yet raised. Nothing already waived or refunded is reopened.

Authority is `return_request` in the loan's space (the loan-charge subject action),
scoped through rbac. The waiver's existence is never gated on a switch once written:
turning `loans.fee_waivers` off hides the tools, it does not start charging waived loans.
"""

from dataclasses import replace

from django.db import transaction
from rest_framework.exceptions import PermissionDenied

from apps.accounts import rbac
from apps.audit import services as audit
from apps.payments.models_pricing_rules import LoanFeeWaiver
from apps.payments.pricing.components import WAIVER_SUBJECTS
from apps.payments.pricing.errors import WaiverExists, WaiverReasonRequired
from apps.payments.pricing.quotes import ZERO

SUBJECT_WAIVER = {subject: key for key, subject in WAIVER_SUBJECTS.items()}
WAIVERS_FEATURE = "loans.fee_waivers"


def active_waivers(request):
    return list(LoanFeeWaiver.objects.filter(request=request, revokes__isnull=True, revocation__isnull=True))


def waived_components(request):
    """{component: waiver} for every loan fee an active waiver covers."""
    covered = {}
    for waiver in active_waivers(request):
        for key in waiver.covered():
            covered.setdefault(key, waiver)
    return covered


def apply_waivers(quote, request):
    covered = waived_components(request)
    if not covered:
        return quote
    lines, used = [], {}
    for line in quote.lines:
        key = SUBJECT_WAIVER.get(line.subject_type)
        waiver = covered.get(key)
        if waiver is None or line.gross <= 0:
            lines.append(line)
            continue
        used[waiver.pk] = waiver
        lines.append(replace(line, gross=ZERO, discount=ZERO, source="waived",
                             detail={**line.detail, "waived_amount": str(line.gross), "waiver_id": waiver.pk}))
    if not used:
        return quote
    first = next(iter(used.values()))
    return replace(quote, lines=tuple(lines),
                   waiver={"id": first.pk, "ids": sorted(used), "components": sorted(covered)})


def loan_charges(request, subject_types):
    """The Payment rows of one loan for the given subject types (rental/late by request,
    damage/lost by its accountability rows)."""
    from apps.hardware_requests.models import RequesterAccountability
    from apps.payments.models import Payment

    by_request = [subject for subject in subject_types if subject in Payment.LOAN_SUBJECT_TYPES]
    by_row = [subject for subject in subject_types if subject in Payment.LOAN_ACCOUNTABILITY_SUBJECT_TYPES]
    rows = list(Payment.objects.filter(makerspace_id=request.makerspace_id, subject_type__in=by_request,
                                       subject_id=request.pk))
    if by_row:
        ids = list(RequesterAccountability.objects.filter(request=request).values_list("pk", flat=True))
        rows += list(Payment.objects.filter(makerspace_id=request.makerspace_id, subject_type__in=by_row,
                                            subject_id__in=ids))
    return rows


def _authorize(actor, request):
    if not rbac.can(actor, rbac.Action.RETURN_REQUEST, request.makerspace_id):
        raise PermissionDenied("Waiving loan fees needs the return permission in this space.")


@transaction.atomic
def waive_loan(request, actor, *, components=(), reason=""):
    from apps.hardware_requests.models import HardwareRequest
    from apps.payments.models import Payment
    from apps.payments.reconciliation import waive
    from apps.payments.pricing.waiver_refunds import open_waiver_case
    from apps.tenant_migration.gate_runtime import assert_write_allowed

    assert_write_allowed(request.makerspace_id)
    request = HardwareRequest.objects.select_for_update().get(pk=request.pk)
    _authorize(actor, request)
    reason = (reason or "").strip()
    if not reason:
        raise WaiverReasonRequired()
    components = sorted(set(components or ()))
    wanted = frozenset(components or LoanFeeWaiver.Component.values)
    overlap = sorted(wanted & set(waived_components(request)))
    if overlap:
        raise WaiverExists(components=overlap)
    waiver = LoanFeeWaiver.objects.create(makerspace_id=request.makerspace_id, request=request,
                                          components=components, reason=reason[:500], created_by=actor)
    waived, cases = [], []
    for payment in loan_charges(request, [WAIVER_SUBJECTS[key] for key in sorted(wanted)]):
        if payment.status == Payment.Status.PENDING:
            waive(payment, actor)
            waived.append(payment.pk)
        elif payment.status in (Payment.Status.PAID_ONLINE, Payment.Status.PAID_OFFLINE):
            case = open_waiver_case(payment, waiver, actor)
            if case is not None:
                cases.append(case.pk)
    audit.record(actor, "loan.fee_waived", makerspace=request.makerspace, target=request, meta={
        "request_id": request.pk, "waiver_id": waiver.pk, "components": sorted(wanted), "reason": waiver.reason,
        "payment_ids": waived, "refund_case_ids": cases,
    })
    from apps.hardware_requests import notifications
    notifications.notify_loan_fees_waived(request, waiver)
    return {"waiver": waiver, "waived_payment_ids": waived, "refund_case_ids": cases}


@transaction.atomic
def revoke_waiver(waiver, actor, *, reason=""):
    from apps.hardware_requests.models import HardwareRequest
    from apps.tenant_migration.gate_runtime import assert_write_allowed

    assert_write_allowed(waiver.makerspace_id)
    request = HardwareRequest.objects.select_for_update().get(pk=waiver.request_id)
    _authorize(actor, request)
    reason = (reason or "").strip()
    if not reason:
        raise WaiverReasonRequired()
    waiver = LoanFeeWaiver.objects.select_for_update().get(pk=waiver.pk)
    if waiver.is_revocation or LoanFeeWaiver.objects.filter(revokes=waiver).exists():
        raise WaiverExists("This waiver has already been revoked.")
    revocation = LoanFeeWaiver.objects.create(makerspace_id=request.makerspace_id, request=request,
                                              components=waiver.components, reason=reason[:500],
                                              revokes=waiver, created_by=actor)
    audit.record(actor, "loan.fee_waiver_revoked", makerspace=request.makerspace, target=request, meta={
        "request_id": request.pk, "waiver_id": waiver.pk, "revocation_id": revocation.pk,
        "components": sorted(waiver.covered()), "reason": revocation.reason,
    })
    return revocation
