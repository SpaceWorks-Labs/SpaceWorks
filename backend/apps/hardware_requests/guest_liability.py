"""Decision 223 (f): who answers for a sponsored guest's loan, and the incident record.

* `liable_member(request)` -- the account a loan CHARGE is billed to. Always the requester (the
  per-person accountability row and the loan itself never move), except when a SPONSORED guest
  pass covered the loan and the space set `sponsored_liability=sponsor`: then the sponsor is
  billed. Called by `loan_charges_common._get_or_create`, so the deposit, rental, late fee,
  damage and lost charge all follow it and each redirect is audited.
* `on_accountability_created` -- post-commit, for every new damage/loss row: the sponsor is
  notified (`incident`) and an incident is recorded on the sponsor's and guest's record.
* `record_outstanding_at_pass_end` -- the sweep step for a sponsored pass that ended with items
  still out: one incident and one sponsor notice per (pass, loan), never repeated.

All of it is inert while `membership.guest_passes` is off (the loan then bills the requester).
"""
import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext

from apps.makerspaces.guest_pass_policy import guest_passes_on, policy_for
from apps.makerspaces.models import GuestPass

logger = logging.getLogger(__name__)


def covering_pass(request):
    """The pass whose window contained the moment this loan began (unless revoked before it).

    A pass revoked AFTER the loan began still covers it: otherwise a sponsor could shift
    liability onto their guest by revoking the pass once the damage is known (final audit 0.12.0).
    """
    moment = request.issued_at or request.created_at
    if request.requester_id is None or moment is None:
        return None
    return GuestPass.objects.filter(
        makerspace_id=request.makerspace_id, holder_id=request.requester_id,
        valid_from__lte=moment, valid_until__gt=moment,
    ).exclude(status=GuestPass.Status.REVOKED, revoked_at__lte=moment).select_related("sponsor").order_by("-valid_from", "-pk").first()


def liable_member(request):
    """The account a charge for this loan is billed to (the requester unless the sponsor answers)."""
    requester = request.requester
    if not guest_passes_on(request.makerspace):
        return requester
    guest_pass = covering_pass(request)
    sponsor = getattr(guest_pass, "sponsor", None)
    if (guest_pass is None or guest_pass.kind != GuestPass.Kind.SPONSORED or sponsor is None
            or not sponsor.is_active or sponsor.access_status != "active"):
        return requester
    if policy_for(request.makerspace).sponsored_liability != "sponsor":
        return requester
    return sponsor


def _incident(guest_pass, request, *, title, description, severity, force_record=False):
    from apps.maintenance.incidents.services import record_incident
    return record_incident(
        guest_pass.makerspace, title=title, kind="incident", severity=severity, description=description,
        force_record=force_record,
        involved_user=guest_pass.holder, sponsor_user=guest_pass.sponsor, guest_pass=guest_pass, loan=request)


def on_accountability_created(accountability_id):
    """Post-commit hook for a new damage/loss row; never raises into the return flow."""
    from apps.hardware_requests.models import RequesterAccountability
    from apps.makerspaces.notifications_guest_passes import notify_sponsor
    try:
        row = RequesterAccountability.objects.select_related("request__makerspace", "makerspace").get(pk=accountability_id)
        if not guest_passes_on(row.makerspace):
            return None
        guest_pass = covering_pass(row.request)
        if guest_pass is None:
            return None
        kind = gettext("lost") if row.issue_type == "missing" else gettext("damaged")
        incident = _incident(guest_pass, row.request, severity="medium",
                             title=gettext("Guest pass: %(kind)s item") % {"kind": kind},
                             description=gettext("Loan #%(request)s, accountability #%(row)s.") % {
                                 "request": row.request_id, "row": row.pk},
                             force_record=True)  # decision 226(f): retained even while safety.incidents is off
        if guest_pass.sponsor_id:
            notify_sponsor(guest_pass, "incident")
        return incident
    except Exception:
        logger.exception("guest_pass_accountability_hook_failed", extra={"accountability_id": accountability_id})
        return None


def schedule_accountability_hook(accountability_id):
    transaction.on_commit(lambda: on_accountability_created(accountability_id))


def record_outstanding_at_pass_end(now=None, *, limit=200, makerspace=None):
    """Sponsored passes that ended while the guest still holds items: one incident + notice per loan.

    Charging stays with the ordinary overdue path (late fee), which `liable_member` already routes to
    the sponsor when the space set `sponsored_liability=sponsor`.
    """
    from apps.hardware_requests.models import HardwareRequest
    from apps.maintenance.incidents.models import Incident
    from apps.makerspaces.notifications_guest_passes import notify_sponsor
    now = now or timezone.now()
    count = 0
    passes = GuestPass.objects.select_related("makerspace", "holder", "sponsor").filter(
        kind=GuestPass.Kind.SPONSORED, sponsor__isnull=False, valid_until__lte=now,
        valid_until__gte=now - timedelta(days=14),
    ).exclude(status=GuestPass.Status.REVOKED)
    if makerspace is not None:
        passes = passes.filter(makerspace=makerspace)
    handled = 0
    for guest_pass in passes.order_by("valid_until", "pk").iterator(chunk_size=100):
        # m18: the cap bounds passes that still needed an incident, not passes examined, so settled
        # passes at the front of the order cannot starve later ones.
        if handled >= limit:
            break
        if not guest_passes_on(guest_pass.makerspace):
            continue
        loans = HardwareRequest.objects.filter(
            makerspace_id=guest_pass.makerspace_id, requester_id=guest_pass.holder_id,
            status__in=(HardwareRequest.Status.ISSUED, HardwareRequest.Status.PARTIALLY_RETURNED),
            issued_at__gte=guest_pass.valid_from, issued_at__lt=guest_pass.valid_until)
        for loan in loans:
            if Incident.objects.filter(guest_pass=guest_pass, loan=loan).exists():
                continue
            handled += 1
            _incident(guest_pass, loan, severity="low",
                      title=gettext("Guest pass ended with items outstanding"),
                      description=gettext("Loan #%(request)s is still out.") % {"request": loan.pk})
            notify_sponsor(guest_pass, "items_outstanding")  # idempotent per pass (the envelope revision)
            count += 1
    return count
