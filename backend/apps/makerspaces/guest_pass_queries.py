"""Decision 223: what is a holder allowed right now. The read API lane L1b enforces against.

* `active_pass_for(user, makerspace, at)` -- the pass that currently counts, or None.
* `pass_entitlements(guest_pass)` -- its borrowing and machine modes, and the on-site due time.
* `require_waiver(user, makerspace, guest_pass)` -- the non-member waiver gate (decision 223(j)).
* `visit_summary(user, makerspace)` -- the soft "join us" prompt counter.

None of these writes. A pass counts only while the capability is on, the holder is still an
unrestricted account, the window contains `at`, the status is live, and (for a priced day pass)
its charge is settled or waived.
"""
from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone

from apps.makerspaces.guest_pass_policy import guest_passes_on, policy_for
from apps.makerspaces.models import GuestPass, MakerspaceWaiver

_CLEARED = ("paid_online", "paid_offline", "waived")


@dataclass(frozen=True)
class PassEntitlements:
    presence: bool
    borrow: str            # "none" | "on_site" | "full_with_deposit"
    machines: str          # "none" | "supervised" | "after_induction_cert"
    due_by: object         # the pass end: on-site loans are due no later than this
    on_site_only: bool


def payment_cleared(guest_pass):
    """A pass with no charge is always cleared; a priced day pass only once its charge is settled or waived.

    "Priced" means a `guest_pass` Payment exists for this pass (written in the sale transaction), never
    the product's CURRENT amount: repricing a product later neither unlocks sold passes nor locks free ones.
    """
    if guest_pass.kind != GuestPass.Kind.DAY:
        return True
    from apps.payments.models import Payment
    status = Payment.objects.filter(
        makerspace_id=guest_pass.makerspace_id, subject_id=guest_pass.pk,
        subject_type=Payment.SubjectType.GUEST_PASS).values_list("status", flat=True).first()
    return True if status is None else status in _CLEARED


def active_pass_for(user, makerspace, at=None):
    if user is None or not getattr(user, "is_active", False) or user.access_status != "active":
        return None
    if not guest_passes_on(makerspace):
        return None
    at = at or timezone.now()
    rows = GuestPass.objects.select_related("product").filter(
        makerspace=makerspace, holder=user, status__in=GuestPass.LIVE_STATUSES,
        valid_from__lte=at, valid_until__gt=at,
    ).order_by("-valid_from", "-pk")
    return next((row for row in rows if payment_cleared(row)), None)


def pass_entitlements(guest_pass):
    snapshot = guest_pass.entitlements or {}
    borrow = snapshot.get("borrow", "none")
    return PassEntitlements(
        presence=bool(snapshot.get("presence", True)), borrow=borrow, machines=snapshot.get("machines", "none"),
        due_by=guest_pass.valid_until, on_site_only=borrow == "on_site",
    )


def require_waiver(user, makerspace, guest_pass=None):
    """Raise `WaiverAcceptanceRequired` unless a non-member holder accepted the CURRENT waiver.

    No-op when the space does not require one or publishes none. Members are the membership
    guards' business, not this one's. The stamp lives on the pass, so it is re-asked whenever
    the space publishes a new waiver version.
    """
    from apps.presence.guard import WaiverAcceptanceRequired

    policy = policy_for(makerspace)
    # decision 226(a): pre-0.12 behaviour while passes are off, unless the space kept the gate on (B12).
    if not guest_passes_on(makerspace) and not policy.waiver_gate_without_passes:
        return
    if not policy.waiver_required_on_site:
        return
    waiver = MakerspaceWaiver.objects.filter(makerspace=makerspace, is_active=True).first()
    if waiver is None:
        return
    if guest_pass is None or guest_pass.accepted_waiver_id != waiver.pk:
        raise WaiverAcceptanceRequired()


def visit_summary(user, makerspace, now=None):
    """Passes plus guest presence sessions over a rolling 30 days, and whether the join prompt applies."""
    now = now or timezone.now()
    since = now - timedelta(days=30)
    visits = GuestPass.objects.filter(makerspace=makerspace, holder=user, valid_from__gte=since).exclude(
        status=GuestPass.Status.REVOKED).count()
    try:
        from apps.presence.models import PresenceSession
        visits += PresenceSession.objects.filter(
            makerspace=makerspace, account=user, status="guest", started_at__gte=since).count()
    except (LookupError, ImportError):  # presence tombstoned: passes alone count
        pass
    policy = policy_for(makerspace)
    return {"visits_30d": visits, "join_threshold": policy.visits_before_join_prompt,
            "should_prompt_join": visits >= policy.visits_before_join_prompt,
            "hard_cap_reached": bool(policy.hard_visit_cap and visits >= policy.hard_visit_cap)}
