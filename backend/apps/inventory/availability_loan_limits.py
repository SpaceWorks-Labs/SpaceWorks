"""Borrow-limit quantity math, kept in the Inventory Availability module."""

from django.utils.translation import gettext
from django.db.models import F, Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts import rbac
from apps.hardware_requests.models import HardwareRequest, HardwareRequestItem
from apps.makerspaces.models import MembershipTerm
from apps.makerspaces.models_loan_policy import MakerspaceLoanPolicy
from apps.makerspaces.platform import feature_enabled, module_enabled


def _borrower_caps(makerspace, borrower):
    """``(max_active, max_items)``: the space policy, overridden by the borrower's active plan."""
    policy = MakerspaceLoanPolicy.for_makerspace(makerspace)
    max_active, max_items = policy.loan_max_active, policy.loan_max_items
    if module_enabled(makerspace, "membership"):
        terms = rbac.scope_by_borrower(
            borrower, MembershipTerm.objects.select_related("plan"), makerspace=makerspace,
            owner_field="membership__user", field="membership__makerspace_id",
        ).filter(status="active", starts_at__lte=timezone.now(), ends_at__gt=timezone.now()).order_by("-ends_at", "-pk")
        term = terms.first()
        if term:
            if term.plan.loan_max_active is not None:
                max_active = term.plan.loan_max_active
            if term.plan.loan_max_items is not None:
                max_items = term.plan.loan_max_items
    return max_active, max_items


def _active_loans(makerspace, borrower, contact_key=""):
    active = rbac.scope_by_borrower(borrower, HardwareRequest.objects.all(), makerspace=makerspace).filter(
        status__in=[HardwareRequest.Status.ISSUED, HardwareRequest.Status.PARTIALLY_RETURNED],
    )
    return active.filter(anonymous_payload_fingerprint=contact_key) if contact_key else active


def _outstanding_items(makerspace, borrower, active):
    items = rbac.scope_by_borrower(
        borrower, HardwareRequestItem.objects.all(), makerspace=makerspace,
        field="request__makerspace_id", owner_field="request__requester",
    ).filter(request__in=active)
    return items.aggregate(total=Sum(
        F("issued_quantity") - F("returned_quantity") - F("damaged_quantity") - F("missing_quantity"),
    ))["total"] or 0


def enforce_borrow_limits(makerspace, borrower, incoming_quantity, *, contact_key=""):
    """Call under the tenant row lock before creating/issuing a loan.

    Pending requests do not occupy a loan slot. Submission checks are advisory;
    issue/checkout/handout checks enforce the current ceiling at the actual handover.

    ``contact_key`` narrows an account-less borrower (#80/#91): every such loan shares the
    makerspace's inert principal, so the person is their confirmed-email fingerprint,
    stored on the request as ``anonymous_payload_fingerprint``.
    """
    if not feature_enabled(makerspace, "loans.limits"):
        return
    max_active, max_items = _borrower_caps(makerspace, borrower)
    active = _active_loans(makerspace, borrower, contact_key)
    if max_active and active.count() >= max_active:
        raise ValidationError({"code": "loan_limit", "detail": gettext("The borrower has reached the active-loan limit.")})
    outstanding = _outstanding_items(makerspace, borrower, active)
    if max_items and outstanding + incoming_quantity > max_items:
        raise ValidationError({"code": "item_limit", "detail": gettext("This handover exceeds the borrower item limit.")})


def borrower_allowance(makerspace, borrower):
    """Read-only twin of ``enforce_borrow_limits`` for the member's own allowance card (#234).

    ``None`` while ``loans.limits`` is off; otherwise each cap with what is in use (``limit``
    None = no cap). Same caps and counters as enforcement, so the card cannot disagree with it.
    """
    if not feature_enabled(makerspace, "loans.limits"):
        return None
    max_active, max_items = _borrower_caps(makerspace, borrower)
    active = _active_loans(makerspace, borrower)
    return {"active_loans": {"used": active.count(), "limit": max_active or None},
            "items_out": {"used": _outstanding_items(makerspace, borrower, active), "limit": max_items or None}}


def enforce_request_borrow_limits(request, rejects_by_item=None):
    rejects_by_item = rejects_by_item or {}
    quantity = sum(item.accepted_quantity - rejects_by_item.get(item.pk, (0,))[0]
                   for item in request.items.all())
    enforce_borrow_limits(request.makerspace, request.requester, quantity,
                          contact_key=request.anonymous_payload_fingerprint)


def enforce_product_borrow_limits(makerspace, borrower, product_quantities, *, contact_key=""):
    enforce_borrow_limits(makerspace, borrower, sum(product_quantities.values()), contact_key=contact_key)


def enforce_submission_borrow_limits(makerspace, borrower, items, *, contact_key=""):
    enforce_borrow_limits(makerspace, borrower, sum(item["quantity"] for item in items), contact_key=contact_key)


def outstanding_request_items(queryset):
    return queryset.filter(issued_quantity__gt=(
        F("returned_quantity") + F("damaged_quantity") + F("missing_quantity")
    ))
