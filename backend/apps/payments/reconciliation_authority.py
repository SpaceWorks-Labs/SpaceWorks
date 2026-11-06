"""Who may reconcile a payment: subject-type authority and machine scoping.

Split out of `reconciliation.py` at the 300-line ceiling. Import through the
`reconciliation` barrel -- `views_refunds` already imports `_require_subject_authority`
from there, so the name must keep resolving at its old path.
"""

from rest_framework.exceptions import PermissionDenied

from apps.accounts import rbac
from apps.payments.models import Payment

SUBJECT_ACTIONS = {
    Payment.SubjectType.MACHINE_SERVICE_REQUEST: rbac.Action.MANAGE_MACHINES,
    Payment.SubjectType.BOOKING: rbac.Action.MANAGE_BOOKINGS,
    Payment.SubjectType.EVENT_REGISTRATION: rbac.Action.MANAGE_EVENTS,
    Payment.SubjectType.MAKERSPACE_MEMBERSHIP: rbac.Action.MANAGE_MAKERSPACE,
    # A renewal charge is membership money like the dues above, so it takes the same
    # authority. Its absence here meant `_require_subject_authority` fell through to the
    # unsupported-subject refusal below and NO actor could ever reconcile a renewal --
    # a space collecting renewals in cash had no way to mark one paid.
    Payment.SubjectType.MEMBERSHIP_TERM: rbac.Action.MANAGE_MAKERSPACE,
    Payment.SubjectType.MEMBERSHIP_REQUEST: rbac.Action.MANAGE_MEMBERS,
    # #184: whoever may open a term (manage_members) settles the charge it raised.
    Payment.SubjectType.MEMBERSHIP_TERM_START: rbac.Action.MANAGE_MEMBERS,
    # Loan charges follow the handover job: whoever may issue settles the deposit,
    # whoever may take a return settles the late fee.
    Payment.SubjectType.LOAN_DEPOSIT: rbac.Action.ISSUE_REQUEST,
    Payment.SubjectType.LOAN_LATE_FEE: rbac.Action.RETURN_REQUEST,
    # Lane L15: rental, damage and lost are settled or waived by whoever takes returns,
    # the same authority that raises damage/lost charges and waives loan fees (A14).
    Payment.SubjectType.LOAN_RENTAL: rbac.Action.RETURN_REQUEST,
    Payment.SubjectType.LOAN_DAMAGE: rbac.Action.RETURN_REQUEST,
    Payment.SubjectType.LOAN_LOST: rbac.Action.RETURN_REQUEST,
    # Lane L23: a machine session is settled by whoever manages that machine's type.
    Payment.SubjectType.MACHINE_SESSION: rbac.Action.MANAGE_MACHINES,
    # Lane L6: event money follows the Event Manager, like a registration charge.
    Payment.SubjectType.EVENT_ORDER: rbac.Action.MANAGE_EVENTS,
    Payment.SubjectType.EVENT_VENUE_FEE: rbac.Action.MANAGE_EVENTS,
    # Lane L18: no area manager owns gifts or sponsor money; finance staff do.
    Payment.SubjectType.DONATION: rbac.Action.RECORD_PAYMENT,
    Payment.SubjectType.SPONSORSHIP: rbac.Action.RECORD_PAYMENT,
    # Lane L21b: entry fees and team charges, like every other events charge.
    Payment.SubjectType.SUBMISSION_FEE: rbac.Action.MANAGE_EVENTS,
    Payment.SubjectType.TEAM_REGISTRATION: rbac.Action.MANAGE_EVENTS,
    Payment.SubjectType.EVENT_DEPOSIT: rbac.Action.MANAGE_EVENTS,  # hack-money G10
    # Lane L22 (Q-S7, #137): the Shop Manager settles and decides refunds on shop orders.
    Payment.SubjectType.SHOP_ORDER: rbac.Action.MANAGE_SHOP,
}
#: Lane L22 (#137): subjects whose cash (a desk refund handed back in person) may also be
#: recorded by their own area's manager, not only by RECORD_PAYMENT holders. The Shop
#: Manager refunds shop sales and nothing else.
CASH_RECORD_ACTIONS = {
    Payment.SubjectType.SHOP_ORDER: rbac.Action.MANAGE_SHOP,
}


def may_record_cash(actor, payment):
    """RECORD_PAYMENT, or the subject's own cash authority (`CASH_RECORD_ACTIONS`)."""
    if rbac.can(actor, rbac.Action.RECORD_PAYMENT, payment.makerspace_id):
        return True
    action = CASH_RECORD_ACTIONS.get(payment.subject_type)
    return action is not None and rbac.can(actor, action, payment.makerspace_id)


def payment_list_action(actor, makerspace_id, *, for_recording=False, subject_type=None):
    """The one action that admits a payment LISTING in one makerspace.

    Finance staff keep their cross-domain view: VIEW_FINANCE, or RECORD_PAYMENT for the
    counter (`for_recording`). An Event Manager holds neither, yet is the person who
    settles registration fees by hand when the online rail is off -- so a listing
    explicitly filtered to event registrations is also admitted by MANAGE_EVENTS. Only
    that listing: every other subject stays finance money, and an unfiltered request
    from the same actor still scopes to nothing (404). Used by both the view's
    makerspace lookup and `list_payments`, so the two can never disagree.
    """
    finance = rbac.Action.RECORD_PAYMENT if for_recording else rbac.Action.VIEW_FINANCE
    if (
        subject_type in Payment.EVENT_SUBJECT_TYPES
        and not rbac.can(actor, finance, makerspace_id)
        and rbac.can(actor, rbac.Action.MANAGE_EVENTS, makerspace_id)
    ):
        return rbac.Action.MANAGE_EVENTS
    return finance


def _require_record_authority(actor, payments):
    """Finance staff record cash across domains; existing domain staff keep their scope.

    Waives and online refunds still use _require_subject_authority. A receipt records
    money moved in person, whereas those actions change debt or send provider money.
    """
    ids = {payment.pk for payment in payments}
    allowed = set(rbac.scope_by_action(
        actor, rbac.Action.RECORD_PAYMENT, Payment.objects.filter(pk__in=ids),
        field="makerspace_id",
    ).values_list("pk", flat=True))
    remaining = [payment for payment in payments if payment.pk not in allowed]
    _require_subject_authority(actor, remaining)


def _require_subject_authority(actor, payments):
    for subject_type, action in SUBJECT_ACTIONS.items():
        ids = [payment.pk for payment in payments if payment.subject_type == subject_type]
        if not ids:
            continue
        visible = set(
            rbac.scope_by_action(
                actor,
                action,
                Payment.objects.filter(pk__in=ids),
                field="makerspace_id",
            ).values_list("pk", flat=True)
        )
        if visible != set(ids):
            raise PermissionDenied("Payment action is not permitted.")
        if subject_type == Payment.SubjectType.MACHINE_SERVICE_REQUEST:
            _require_machine_scope(actor, payments)
        if subject_type == Payment.SubjectType.MACHINE_SESSION:
            _require_session_scope(actor, payments)
    if any(payment.subject_type not in SUBJECT_ACTIONS for payment in payments):
        raise PermissionDenied("Payment subject type is not supported.")


def _require_machine_scope(actor, payments):
    """MANAGE_MACHINES is scoped per role, so reconciling a charge follows the job.

    Imported locally: `apps.machines` reaches into `apps.payments` for service pricing, so
    a module-level edge back would close the cycle.
    """
    from apps.machines.models import MachineServiceRequest
    from apps.machines.role_scope import EXEMPT, manage_scopes_for, scoped_service_requests

    machine_payments = [
        payment
        for payment in payments
        if payment.subject_type == Payment.SubjectType.MACHINE_SERVICE_REQUEST
    ]
    subject_ids = {payment.subject_id for payment in machine_payments}
    if not subject_ids:
        return
    requests = MachineServiceRequest.objects.filter(pk__in=subject_ids)
    live_ids = set(requests.values_list("pk", flat=True))
    covered = set(
        scoped_service_requests(
            actor,
            requests,
            set(requests.values_list("makerspace_id", flat=True)),
        ).values_list("pk", flat=True)
    )
    if covered != live_ids:
        raise PermissionDenied("Payment action is not permitted.")

    # A charge whose service request was purged names no machine, type or team, so there is
    # nothing left for machine scoping to answer. Comparing against `subject_ids` here made
    # the set unequal for every actor, so a pending charge could never be waived or marked
    # paid in cash -- stranding it forever, which is the exact failure that preserving the
    # payment exists to prevent. Failing OPEN to every `MANAGE_MACHINES` holder would
    # silently widen a scoped role, and scoping is documented as failing closed. So the
    # orphan is actionable only by the actor machine scoping already exempts -- a space
    # manager, a superadmin, or the null-`assigned_role` legacy fallback -- all of whom are
    # unscoped everywhere else in this mechanism.
    orphaned = subject_ids - live_ids
    if not orphaned:
        return
    orphan_makerspace_ids = {
        payment.makerspace_id
        for payment in machine_payments
        if payment.subject_id in orphaned
    }
    scopes = manage_scopes_for(actor, orphan_makerspace_ids)
    if any(scopes.get(ms_id) is not EXEMPT for ms_id in orphan_makerspace_ids):
        raise PermissionDenied("Payment action is not permitted.")


def _require_session_scope(actor, payments):
    """Lane L23: a session charge follows its machine's type scope, like a job's.

    A charge whose session was purged is actionable only by an actor machine scoping
    already exempts (the same fail-closed rule as an orphaned job charge above).
    """
    from apps.machines.models import MachineSession
    from apps.machines.role_scope import EXEMPT, manage_scopes_for, scope_covers_machine

    rows = [payment for payment in payments if payment.subject_type == Payment.SubjectType.MACHINE_SESSION]
    if not rows:
        return
    sessions = {row.pk: row for row in MachineSession.objects.select_related("machine").filter(
        pk__in={payment.subject_id for payment in rows})}
    scopes = manage_scopes_for(actor, {payment.makerspace_id for payment in rows})
    for payment in rows:
        scope = scopes.get(payment.makerspace_id)
        session = sessions.get(payment.subject_id)
        if session is None or session.makerspace_id != payment.makerspace_id:
            if scope is not EXEMPT:
                raise PermissionDenied("Payment action is not permitted.")
        elif scope is None or not scope_covers_machine(scope, session.machine):
            raise PermissionDenied("Payment action is not permitted.")
