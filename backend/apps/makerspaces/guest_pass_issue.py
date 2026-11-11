"""Decision 223(b): the three ways a guest pass is issued, through one locked creator.

* `issue_sponsored_pass` -- a member brings a guest (present, tenured, within the limits).
* `issue_staff_pass` -- staff (manage_members) issue one directly, optionally naming a sponsor.
* `issue_event_pass` -- the events adapter (lane L1b) calls this for a non-member registrant.
  It is idempotent: a holder who already has a live pass that day gets that pass back.

Every path runs inside `transaction.atomic()` under the makerspace lock
(`require_membership_feature_locked`), so concurrent issuance cannot overshoot a sponsor's
guest limit or a daily cap. A pass is never a `MakerspaceMembership`.
"""
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.makerspaces.limits import check_quota
from apps.makerspaces.guest_pass_policy import GuestPassError, frozen_entitlements, policy_for
from apps.makerspaces.guest_pass_queries import visit_summary
from apps.makerspaces.local_time import local_day_bounds, to_local
from apps.makerspaces.membership_features import require_membership_feature_locked
from apps.makerspaces.models import GuestPass, MakerspaceMembership
from apps.makerspaces.platform import module_enabled


def day_window(makerspace, day=None, now=None):
    """`(valid_from, valid_until, pass_date)` for one makerspace-local calendar day (today by default)."""
    now = now or timezone.now()
    today = to_local(makerspace, now).date()
    day = day or today
    if day < today:
        raise GuestPassError("pass_day_in_past", "A pass cannot start on a day that has already passed.")
    start, end = local_day_bounds(makerspace, day)
    return (max(start, now) if day == today else start), end, day


def event_window(starts_at, ends_at, return_hours=0):
    """An event pass runs from one hour before the start to the end plus the equipment-return buffer."""
    return starts_at - timedelta(hours=1), ends_at + timedelta(hours=return_hours or 0)


def check_holder(holder, makerspace):
    """A pass holder is an unrestricted person account that is not already a member here."""
    if (getattr(holder, "account_kind", None) != "member" or not holder.is_active
            or holder.access_status != "active" or holder.retired_at is not None
            or getattr(holder, "merged_into_id", None) is not None):
        raise GuestPassError("guest_not_eligible", "That account cannot receive a guest pass.")
    if MakerspaceMembership.objects.filter(makerspace=makerspace, user=holder, status="active").exists():
        raise GuestPassError("already_member", "This person is already a member and does not need a pass.")
    from apps.makerspaces.minors_guard import require_minor_clearance  # decision 223 (k)
    require_minor_clearance(holder, makerspace, "guest_pass")


def _check_visit_cap(holder, makerspace, policy):
    if policy.hard_visit_cap and visit_summary(holder, makerspace)["hard_cap_reached"]:
        raise GuestPassError("visit_cap_reached", "This guest has reached the visit limit; membership is required.")


def replay_pass(makerspace, holder, operation_id):
    """The pass an earlier call with this `operation_id` already created, or None.

    Checked BEFORE the window, holder and cap guards: a retry after a lost response must get the same
    pass back, not "sold out" because the first call itself used the last seat. The same id used for a
    different holder is a client bug and answers 409.
    """
    if not operation_id:
        return None
    existing = GuestPass.objects.filter(makerspace=makerspace, operation_id=operation_id).first()
    if existing is None:
        return None
    if existing.holder_id != holder.pk:
        raise GuestPassError("operation_id_reused", "That operation id belongs to a different guest.",
                             status_code=409)
    return existing


def create_pass(makerspace, holder, kind, valid_from, valid_until, pass_date, *, issuer, sponsor=None,
                sponsor_membership=None, product=None, operation_id=None, policy=None, template=None):
    """The single creator. Call inside the locked transaction; returns `(pass, created)`."""
    policy = policy or policy_for(makerspace)
    existing = replay_pass(makerspace, holder, operation_id)
    if existing is not None:
        return existing, False
    check_holder(holder, makerspace)
    _check_visit_cap(holder, makerspace, policy)
    check_quota(makerspace, "guest_passes", adding=1)  # managed fair-use; a no-op on self-host
    try:
        with transaction.atomic():
            row = GuestPass.objects.create(
                makerspace=makerspace, holder=holder, kind=kind, valid_from=valid_from, valid_until=valid_until,
                pass_date=pass_date, sponsor=sponsor, sponsor_membership=sponsor_membership, product=product,
                entitlements=frozen_entitlements(policy, template), issued_by=issuer, operation_id=operation_id,
            )
    except IntegrityError as exc:
        raise GuestPassError("pass_exists_today", "This guest already has a pass for that day.") from exc
    audit.record(issuer, "membership.guest_pass_issued", makerspace=makerspace, target=row,
                 meta={"kind": kind, "holder_id": holder.pk, "sponsor_id": sponsor.pk if sponsor else None})
    from apps.makerspaces.notifications_guest_passes import notify_pass_issued
    notify_pass_issued(row)
    return row, True


def _sponsor_membership(sponsor, makerspace, policy, now):
    membership = MakerspaceMembership.objects.filter(
        makerspace=makerspace, user=sponsor, status="active", user__is_active=True, user__access_status="active",
    ).first()
    if membership is None:
        raise GuestPassError("sponsor_not_member", "Only an active member can bring a guest.", status_code=403)
    since = membership.activated_at or membership.created_at
    if since > now - timedelta(days=policy.sponsor_min_tenure_days):
        raise GuestPassError("sponsor_tenure", "You have not been a member long enough to bring a guest.")
    return membership


def _sponsor_present(sponsor, makerspace):
    if not module_enabled(makerspace, "presence"):
        return True
    from apps.presence.services import current_session
    return current_session(sponsor, makerspace) is not None


def _concurrent_guests(sponsor, makerspace, now):
    return GuestPass.objects.filter(
        makerspace=makerspace, sponsor=sponsor, status__in=GuestPass.LIVE_STATUSES, valid_until__gt=now,
    ).count()


def issue_sponsored_pass(sponsor, makerspace, guest, *, operation_id=None, now=None):
    """A member brings a guest for the rest of today. Sponsor checks run BEFORE the guest is looked at."""
    now = now or timezone.now()
    with transaction.atomic():
        makerspace = require_membership_feature_locked(makerspace, "guest_passes")
        policy = policy_for(makerspace)
        replay = replay_pass(makerspace, guest, operation_id)
        if replay is not None:
            return replay, False
        membership = _sponsor_membership(sponsor, makerspace, policy, now)
        if sponsor.pk == guest.pk:
            raise GuestPassError("guest_not_eligible", "You cannot sponsor yourself.")
        if policy.sponsor_must_be_present and not _sponsor_present(sponsor, makerspace):
            raise GuestPassError("sponsor_presence_required", "Check in at the space before bringing a guest.")
        if _concurrent_guests(sponsor, makerspace, now) >= policy.max_concurrent_guests_per_sponsor:
            raise GuestPassError("sponsor_limit", "You already have the maximum number of guests.")
        start, end, day = day_window(makerspace, now=now)
        return create_pass(makerspace, guest, GuestPass.Kind.SPONSORED, start, end, day, issuer=sponsor,
                           sponsor=sponsor, sponsor_membership=membership, operation_id=operation_id, policy=policy)


def issue_staff_pass(actor, makerspace, holder, *, day=None, sponsor=None, operation_id=None, now=None):
    """Staff (manage_members) issue a free pass directly; a named sponsor makes it a sponsored pass.

    Staff are not held to the sponsor's tenure, presence or guest limit (they are the override),
    but the sponsor must still be an active member of this space.
    """
    now = now or timezone.now()
    with transaction.atomic():
        makerspace = require_membership_feature_locked(makerspace, "guest_passes")
        policy = policy_for(makerspace)
        replay = replay_pass(makerspace, holder, operation_id)
        if replay is not None:
            return replay, False
        membership = None
        if sponsor is not None:
            membership = MakerspaceMembership.objects.filter(
                makerspace=makerspace, user=sponsor, status="active").first()
            if membership is None:
                raise GuestPassError("sponsor_not_member", "The sponsor must be an active member.")
        start, end, pass_day = day_window(makerspace, day, now)
        kind = GuestPass.Kind.SPONSORED if sponsor is not None else GuestPass.Kind.DAY
        return create_pass(makerspace, holder, kind, start, end, pass_day, issuer=actor, sponsor=sponsor,
                           sponsor_membership=membership, operation_id=operation_id, policy=policy)


def issue_event_pass(makerspace, holder, valid_from, valid_until, *, issuer=None, operation_id=None):
    """Called by the events adapter (lane L1b). Returns the pass; an existing live pass that day is reused.

    `valid_from`/`valid_until` come from `event_window(...)`. `issuer` is the checking-in staff
    member, or None for an automatic issue at registration.
    """
    with transaction.atomic():
        makerspace = require_membership_feature_locked(makerspace, "guest_passes")
        policy = policy_for(makerspace)
        pass_date = to_local(makerspace, valid_from).date()
        live = GuestPass.objects.filter(
            makerspace=makerspace, holder=holder, pass_date=pass_date, status__in=GuestPass.LIVE_STATUSES,
        ).first()
        if live is not None:
            return live, False
        return create_pass(makerspace, holder, GuestPass.Kind.EVENT, valid_from, valid_until, pass_date,
                           issuer=issuer, operation_id=operation_id, policy=policy)


def sponsor_guests(sponsor, makerspace):
    """The sponsor's own guests: name, date, status only (decision 223 privacy; the view trims the rest)."""
    return GuestPass.objects.filter(makerspace=makerspace, sponsor=sponsor).select_related("holder").order_by("-pk")
