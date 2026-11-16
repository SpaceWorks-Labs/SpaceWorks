"""Decision 242(a)(b)(c): the own-area Payments queue.

Each charge's SUBJECT OWNER may already record an offline payment and waive it (`reconciliation_authority`,
decision 217(a)). This module is the queue that lets them FIND those charges: every pending/owed charge the
actor owns, in every area (job charges, sessions, loans, all six event charge types, bookings, shop,
membership), grouped by finance domain. It grants nothing. A row appears only when the same
`SUBJECT_ACTIONS` authority that `reconcile_payments` re-checks would admit it, narrowed by machine-type
scope for a scoped Machine Manager. Finance staff (`view_finance`) see every domain; donations and
sponsorships stay `record_payment` money and never reach an area manager.

The Finance views (decision 241) read totals through `finance_scope`; this queue acts. It only READS
`finance_scope.PAYMENT_DOMAINS` and `finance_view`.
"""

from django.db.models import Count, Q, Sum

from apps.accounts import rbac
from apps.payments.due_dates import filter_due
from apps.payments.finance_scope import PAYMENT_DOMAINS, finance_view
from apps.payments.models import Payment
from apps.payments.reconciliation_authority import SUBJECT_ACTIONS

#: Money that is never an area manager's, whatever their other grants.
FINANCE_ONLY = frozenset({Payment.SubjectType.DONATION, Payment.SubjectType.SPONSORSHIP})
AREAS = ("lending", "machines", "events", "bookings", "shop", "membership", "general")
_AREA_OF_DOMAIN = {"loans": "lending", "inventory": "lending", "machines": "machines", "events": "events",
                   "bookings": "bookings", "shop": "shop", "membership": "membership"}


def area_of(subject_type):
    return _AREA_OF_DOMAIN.get(PAYMENT_DOMAINS.get(subject_type, "general"), "general")


def _machine_ids(actor, makerspace_id, model_name):
    """Subject ids of machine charges the actor's machine scope covers (None = unscoped)."""
    from apps.machines import role_scope
    from apps.machines.models import MachineServiceRequest, MachineSession

    scope = role_scope.manage_scope_for(actor, makerspace_id)
    if scope is role_scope.EXEMPT:
        return None
    if model_name == "request":
        rows = role_scope.scoped_service_requests(
            actor, MachineServiceRequest.objects.filter(makerspace_id=makerspace_id), [makerspace_id])
    else:
        rows = MachineSession.objects.filter(makerspace_id=makerspace_id).filter(role_scope.scope_q_for(
            scope, machine_id_paths=("machine_id",), type_id_paths=("machine_type_id",)))
    return list(rows.values_list("pk", flat=True))


def owned_subject_types(actor, makerspace_id):
    """The subject types the actor owns here; `None` means every type (finance staff)."""
    if finance_view(actor, makerspace_id).everything:
        return None
    return sorted(t for t, action in SUBJECT_ACTIONS.items()
                  if t not in FINANCE_ONLY and rbac.can(actor, action, makerspace_id))


def area_payments(actor, makerspace_id, *, area=None, status=None, subject_type=None):
    """The actor's own-area charges in one space (not yet ordered or due-filtered)."""
    rows = Payment.objects.select_related("makerspace").filter(makerspace_id=makerspace_id)
    owned = owned_subject_types(actor, makerspace_id)
    if owned is not None:
        q = Q(subject_type__in=owned)
        if not owned:
            return rows.none()
        for kind, model_name in ((Payment.SubjectType.MACHINE_SERVICE_REQUEST, "request"),
                                 (Payment.SubjectType.MACHINE_SESSION, "session")):
            if kind in owned:
                ids = _machine_ids(actor, makerspace_id, model_name)
                if ids is not None:
                    q &= ~Q(subject_type=kind) | Q(subject_id__in=ids)
        rows = rows.filter(q)
    if area:
        rows = rows.filter(subject_type__in=[t for t in Payment.SubjectType.values if area_of(t) == area])
    if subject_type:
        rows = rows.filter(subject_type=subject_type)
    return rows.filter(status=status) if status else rows


def in_queue(actor, makerspace_id, payment_id):
    return area_payments(actor, makerspace_id).filter(pk=payment_id).first()


def summary(actor, makerspace, now=None):
    """Per-area totals for the pending queue: count, overdue, owed per currency, open claims."""
    from apps.payments.models import PaymentClaim

    pending = area_payments(actor, makerspace.pk, status=Payment.Status.PENDING)
    groups = {}
    for row in pending.values("subject_type", "currency").annotate(n=Count("pk"), total=Sum("amount")):
        group = groups.setdefault(area_of(row["subject_type"]), {"pending": 0, "owed": {}})
        group["pending"] += row["n"]
        group["owed"][row["currency"]] = group["owed"].get(row["currency"], 0) + row["total"]
    overdue = filter_due(pending, makerspace, "overdue", now=now)
    for row in overdue.values("subject_type").annotate(n=Count("pk")):
        groups.setdefault(area_of(row["subject_type"]), {"pending": 0, "owed": {}})["overdue"] = row["n"]
    claims = PaymentClaim.objects.filter(
        makerspace_id=makerspace.pk, status__in=PaymentClaim.OPEN_STATUSES, payment__in=pending.values("pk"))
    for row in claims.values("payment__subject_type").annotate(n=Count("pk")):
        groups.setdefault(area_of(row["payment__subject_type"]), {"pending": 0, "owed": {}})["claims"] = row["n"]
    return [{"area": area, "pending": g["pending"], "overdue": g.get("overdue", 0), "claims": g.get("claims", 0),
             "owed": {currency: str(total) for currency, total in g["owed"].items()}}
            for area, g in sorted(groups.items(), key=lambda item: AREAS.index(item[0]))]
