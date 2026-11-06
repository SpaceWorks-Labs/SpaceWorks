"""Membership terms: creation, cancellation and the renewal/expiry sweep.

Renewal charges are raised through `apps.payments.services.create_payment` with subject
type `MEMBERSHIP_TERM` and the term pk as subject id, so the Payment table's one-row-per-
subject constraint is what guarantees "exactly one renewal charge per term". A payment
failure never rolls back a recorded debt. Optional automation tracks bounded retries,
promised grace and one successor behind the compatibility exports at the end of this file.
"""

from django.utils.translation import gettext
from apps.accounts.account_kind_guards import require_member_account
import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from apps.accounts.account_obligations import lock_obligation_owner
from apps.makerspaces.guards import require_module_locked
from apps.makerspaces import membership_plan_types as plan_types, membership_term_history as term_history
from apps.makerspaces.models import MakerspaceMembership, MembershipTerm

logger = logging.getLogger(__name__)

# Compatibility window for plans that have not opted in to automation.
RENEWAL_WINDOW = timedelta(days=7)

term_end = plan_types.term_end


def _start_for(membership, plan, now):
    """Where a staff-opened term starts when no date is given: after the current term,
    else after a predecessor still in grace (the plan's late-renewal rule), else now."""
    current = (
        membership.terms.filter(status=MembershipTerm.Status.ACTIVE, ends_at__gt=now)
        .select_related("plan").order_by("-ends_at").first()
    )
    if current is not None:
        if current.is_lifetime:
            raise ValidationError({"detail": gettext("This membership already holds a lifetime term.")})
        return current.ends_at
    latest = plan_types.previous_term(membership)
    if latest is not None and plan_types.in_staff_grace(latest, now):
        return plan_types.late_renewal_start(plan, latest, now)
    return now


def create_term(actor, membership, plan, starts_at=None, *, kind=None, price=None, joining_fee=None,
                renewed_from=None, admission_request=None, ends_at=None):
    """Open a term for an active membership; a new term follows the current one.

    The price, joining fee, currency and plan type are frozen on the term (X6); the
    kind is derived from the membership's earlier terms unless the caller knows it.
    `ends_at` is only for an imported term whose dates came from the file (G18).
    """
    require_member_account(membership.user)
    with transaction.atomic():
        from apps.tenant_migration.gate_runtime import assert_write_allowed
        assert_write_allowed(membership.makerspace_id)
        # Makerspace lock first, then the membership -- the order `_activate_membership`
        # mandates -- and the module gate re-checked under that lock (plan A8).
        makerspace = require_module_locked(membership.makerspace_id, "membership")
        membership = (
            MakerspaceMembership.objects.select_for_update(of=("self",))
            .select_related("user")
            .get(pk=membership.pk)
        )
        membership.user = lock_obligation_owner(membership.user)
        if plan.makerspace_id != makerspace.pk:
            raise ValidationError({"plan_id": gettext("Plan must belong to this makerspace.")})
        if not plan.is_active or plan.archived_at is not None:
            raise ValidationError({"plan_id": gettext("This plan is no longer active.")})
        if membership.status != "active":
            raise ValidationError({"detail": gettext("Only an active membership can hold a term.")})
        now = timezone.now()
        if starts_at is None:
            starts_at = _start_for(membership, plan, now)
        plan.makerspace = makerspace
        local_start = _local_start(makerspace, starts_at)
        if ends_at is None:
            plan_types.require_openable(plan, local_start)
            ends_at = term_end(plan, local_start)
        elif ends_at <= starts_at:
            raise ValidationError({"ends_on": gettext("The term must end after it starts.")})
        kind = kind or plan_types.derive_kind(membership, starts_at, renewed_from=renewed_from)
        from apps.makerspaces.membership_number import assign as assign_number
        assign_number(membership, source=None)
        term = MembershipTerm.objects.create(
            membership=membership,
            plan=plan,
            starts_at=starts_at,
            ends_at=ends_at,
            created_by=actor,
            renewed_from=renewed_from,
            kind=kind,
            price=plan_types.price_for(plan, kind) if price is None else price,
            joining_fee=joining_fee or 0,
            currency=plan.currency,
            plan_type=plan.plan_type,
            admission_request=admission_request,
        )
        audit.record(
            actor,
            "membership.term_created",
            makerspace=makerspace,
            target=term,
            meta={"membership_id": membership.pk, "plan_id": plan.pk, "term_id": term.pk},
        )
        term.membership = membership
        term_history.record_opened(term, actor=actor, now=now)
    return term


def _local_start(makerspace, starts_at):
    from apps.makerspaces.local_time import to_local
    return to_local(makerspace, starts_at)


def cancel_term(actor, term, *, reason="", hold_charges=True):
    with transaction.atomic():
        term = (
            MembershipTerm.objects.select_for_update(of=("self",))
            .select_related("membership__makerspace")
            .get(pk=term.pk)
        )
        if term.status != MembershipTerm.Status.ACTIVE:
            raise ValidationError({"detail": gettext("This term is not active.")})
        term.status = MembershipTerm.Status.CANCELLED
        term.save(update_fields=["status"])
        makerspace = term.membership.makerspace
        audit.record(
            actor,
            "membership.term_cancelled",
            makerspace=makerspace,
            target=term,
            meta={"membership_id": term.membership_id, "term_id": term.pk},
        )
        term_history.record(term, term_history.TermStanding.CANCELLED, effective_at=timezone.now(),
                            actor=actor, reason=reason)
        if hold_charges:
            _cancel_term_charges(makerspace, term, actor)
        else:
            _cancel_pending_renewal(makerspace, term, actor)
    return term


def cancel_terms_for_membership(actor, membership):
    """Cancel every ACTIVE term of a membership that has just been revoked, with its renewal.

    Called from `revoke_membership`, which is core RBAC and runs with the module off too,
    so there is no module gate here. Without it a revoked member kept an active term and a
    PENDING renewal charge that the sweep had raised for a membership that no longer exists.
    """
    for term in MembershipTerm.objects.filter(
        membership=membership, status=MembershipTerm.Status.ACTIVE
    ):
        cancel_term(actor, term)


def _cancel_pending_renewal(makerspace, term, actor):
    """Void a pending renewal only: "do not renew" keeps the current term and its money."""
    from apps.payments.models import Payment
    from apps.payments.reconciliation import cancel_pending

    try:
        with transaction.atomic():
            cancel_pending(makerspace=makerspace, subject_type=Payment.SubjectType.MEMBERSHIP_TERM,
                           subject_id=term.pk, actor=actor)
    except Exception:  # noqa: BLE001 - money must never block the membership workflow
        logger.exception("membership_renewal_cancel_failed", extra={"term_id": term.pk})


def _cancel_term_charges(makerspace, term, actor):
    """A cancelled term: void its pending renewal; a PAID one, and the payment that bought this term,
    get a refund case under the membership policy instead (owner decision 68).

    The term's own renewal charge pays for its successor, and `renewed_from`'s renewal
    paid for this term; both are assessed against the term they cover. Each runs in its
    own savepoint so a payment failure never undoes the cancellation; the refund sweep
    rebuilds a case it missed.
    """
    from apps.payments.models import Payment, RefundCase
    from apps.payments.refund_cancellation import cancel_or_hold, hold_settled

    reason = RefundCase.ReasonCode.MEMBERSHIP_CANCELLED
    try:
        with transaction.atomic():
            cancel_or_hold(makerspace=makerspace, subject_type=Payment.SubjectType.MEMBERSHIP_TERM,
                           subject_id=term.pk, actor=actor, reason_code=reason)
            if term.renewed_from_id:
                hold_settled(makerspace=makerspace, subject_type=Payment.SubjectType.MEMBERSHIP_TERM,
                             subject_id=term.renewed_from_id, actor=actor, reason_code=reason)
    except Exception:  # noqa: BLE001 - money must never block the membership workflow
        logger.exception("membership_renewal_cancel_failed", extra={"term_id": term.pk})



# Explicit compatibility exports for the scheduled seam.
from .membership_renewals import run_membership_renewals, _expire
from .membership_renewal_charges import raise_renewal as _raise_renewal
