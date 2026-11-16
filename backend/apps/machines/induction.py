"""Induction events: one-click certification grant after a workshop (decision 223 (k), P1).

An event is marked as an induction for one or more certification types (`link`). After the
event, staff who may grant that certification see who checked in (`attendees`) and grant
it to the people they pick (`grant_from_induction`): one audited grant per person, naming
the event as its source. Nothing is ever granted without that staff call.

A member gets an ordinary `CertificationGrant` through `issue_grant`. A guest-pass holder
has no membership, so they get a `GuestCertificationGrant` (decision 223 (d), mode
"after_induction_cert"); the pass itself is asked of the guest-pass module through
`guest_pass_window` (`guest_pass_queries.active_pass_for`).
"""

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.account_kind_guards import require_member_account
from apps.audit.services import record
from apps.makerspaces.guards import feature_off, require_module
from apps.makerspaces.platform import feature_enabled

from . import access
from .certification_grants import issue_grant
from .certifications import active_grant
from .models import CertificationType, EventInductionLink, GuestCertificationGrant

FEATURE = "machines.induction_events"


def require_induction(makerspace):
    require_module(makerspace, "machines")
    require_module(makerspace, "events")
    if not feature_enabled(makerspace, FEATURE):
        raise feature_off(FEATURE)
    return makerspace


def _may_grant(actor, certification_type):
    return access.can_create_machine(actor, certification_type.makerspace_id, certification_type.machine_type)


def guest_pass_window(user, makerspace, at=None):
    """The user's live guest pass in this space, or None (the guest-pass module owns the rule)."""
    from apps.makerspaces.guest_pass_queries import active_pass_for
    return active_pass_for(user, makerspace, at or timezone.now())


def _event_types(event):
    return CertificationType.objects.filter(induction_links__event=event, is_active=True).select_related(
        "machine_type", "makerspace")


@transaction.atomic
def link(event, certification_type, *, actor):
    require_induction(event.makerspace)
    if certification_type.makerspace_id != event.makerspace_id:
        raise ValidationError({"certification_type_id": gettext("Choose a certification of this makerspace.")})
    if not certification_type.is_active:
        raise ValidationError({"certification_type_id": gettext("This certification type is inactive.")})
    if not _may_grant(actor, certification_type):
        raise PermissionDenied()
    row, created = EventInductionLink.objects.get_or_create(
        event=event, certification_type=certification_type,
        defaults={"makerspace": event.makerspace, "created_by": actor})
    if created:
        record(actor, "certification.induction_linked", makerspace=event.makerspace, target=row, meta={
            "event_id": event.pk, "certification_type_id": certification_type.pk,
            "machine_type_id": certification_type.machine_type_id})
    return row


@transaction.atomic
def unlink(link_row, *, actor):
    require_induction(link_row.makerspace)
    if not _may_grant(actor, link_row.certification_type):
        raise PermissionDenied()
    meta = {"event_id": link_row.event_id, "certification_type_id": link_row.certification_type_id,
            "machine_type_id": link_row.certification_type.machine_type_id}
    record(actor, "certification.induction_unlinked", makerspace=link_row.makerspace, target=link_row, meta=meta)
    link_row.delete()


def attendees(event):
    """Registrations that checked in with an account, newest check-in last (the grant list)."""
    from apps.events.models import EventRegistration
    return EventRegistration.objects.filter(
        event=event, status=EventRegistration.Status.ATTENDED, member__isnull=False,
    ).select_related("member").order_by("created_at", "pk")


def holds_type(user, certification_type, at=None, *, include_guest=True):
    """True when `user` holds a live grant of exactly this certification type."""
    moment = at or timezone.now()
    from apps.makerspaces.models import MakerspaceMembership
    membership = MakerspaceMembership.objects.filter(
        makerspace_id=certification_type.makerspace_id, user=user, status="active").first()
    if membership is not None and active_grant(membership, certification_type, moment) is not None:
        return True
    return include_guest and any(row.is_active(moment) for row in GuestCertificationGrant.objects.filter(
        certification_type=certification_type, user=user, revoked_at__isnull=True))


def holds_certification(user, machine_type, makerspace, at=None, *, include_guest=True):
    """True when `user` holds a live certification for any active type of `machine_type`.

    The single predicate guest machine modes call (decision 223 (d)). A member counts via
    their `CertificationGrant`, a guest via a `GuestCertificationGrant`; this never checks
    the guest pass itself, which the caller owns. A machine type with no certification
    type configured yields False: there is nothing to hold.
    """
    if user is None or machine_type is None or makerspace is None or not getattr(user, "pk", None):
        return False
    # Decision 218: guest certifications come only from induction events, so with that switch off
    # (or Events off) they stop unlocking anything; the rows are kept for a later re-enable.
    include_guest = include_guest and feature_enabled(makerspace, FEATURE)
    types = CertificationType.objects.filter(makerspace=makerspace, machine_type=machine_type, is_active=True)
    return any(holds_type(user, row, at, include_guest=include_guest) for row in types)


def _guest_expiry(row, pass_row, now, expires_at):
    expiry = expires_at
    if expiry is None and row.validity_days:
        try:
            expiry = now + timedelta(days=row.validity_days)
        except OverflowError as exc:
            raise ValidationError({"validity_days": gettext("Validity is outside the supported date range.")}) from exc
    ends = getattr(pass_row, "valid_until", None)
    if ends is not None and (expiry is None or ends < expiry):
        expiry = ends
    if expiry is not None and expiry <= now:
        raise ValidationError({"expires_at": gettext("Expiry must be in the future.")})
    return expiry


def _grant_guest(row, user, *, actor, event, expires_at, notes):
    require_member_account(user)
    now = timezone.now()
    # Lock the certification type row so two concurrent grants for one guest serialise: the second
    # sees the first's grant below and reports it as already certified instead of duplicating it.
    CertificationType.objects.select_for_update().filter(pk=row.pk).first()
    pass_row = guest_pass_window(user, row.makerspace, now)
    if pass_row is None:
        raise ValidationError({"code": "guest_pass_required",
                               "detail": gettext("This person is not a member and holds no active guest pass.")})
    if any(held.is_active(now) for held in GuestCertificationGrant.objects.filter(
            makerspace=row.makerspace, user=user, certification_type=row, revoked_at__isnull=True)):
        return None
    grant = GuestCertificationGrant.objects.create(
        makerspace=row.makerspace, certification_type=row, user=user, source_event=event, granted_by=actor,
        granted_at=now, expires_at=_guest_expiry(row, pass_row, now, expires_at), notes=notes)
    record(actor, "certification.guest_granted", makerspace=row.makerspace, target=grant, meta={
        "certification_type_id": row.pk, "machine_type_id": row.machine_type_id, "user_id": user.pk,
        "source_event_id": event.pk, "expires_at": grant.expires_at.isoformat() if grant.expires_at else None})
    from .notifications_p2_certifications import notify_guest
    notify_guest(grant, "granted")
    return grant


def _grant_one(row, user, *, actor, event, expires_at, notes):
    from apps.makerspaces.models import MakerspaceMembership
    membership = MakerspaceMembership.objects.filter(makerspace=row.makerspace, user=user, status="active").first()
    if membership is not None:
        if active_grant(membership, row):
            return None
        return issue_grant(row, membership, actor=actor, expires_at=expires_at, notes=notes, source_event=event)
    return _grant_guest(row, user, actor=actor, event=event, expires_at=expires_at, notes=notes)


def grant_from_induction(event, user_ids, *, actor, certification_type_ids=None, expires_at=None):
    """Grant the event's linked certifications to the chosen attendees; one audit row each.

    Returns one result per (person, certification): `granted`, `already_certified` or
    `refused` with a typed `code`. A refusal for one person never undoes another's grant.
    """
    require_induction(event.makerspace)
    types = list(_event_types(event))
    if certification_type_ids is not None:
        types = [row for row in types if row.pk in set(certification_type_ids)]
    if not types:
        raise ValidationError({"certification_type_ids": gettext("This event is not an induction for that certification.")})
    if event.starts_at > timezone.now():
        raise ValidationError({"detail": gettext("Grant after the event has started."), "code": "event_not_started"})
    for row in types:
        if not _may_grant(actor, row):
            raise PermissionDenied()
    present = {reg.member_id: reg.member for reg in attendees(event)}
    unknown = sorted(set(user_ids) - set(present))
    if unknown:
        raise ValidationError({"user_ids": gettext("Only attendees who checked in can be certified."),
                               "unknown": unknown})
    notes = f"Induction event {event.pk}"
    results = []
    for user_id in dict.fromkeys(user_ids):
        for row in types:
            result = {"user_id": user_id, "certification_type_id": row.pk}
            try:
                with transaction.atomic():
                    grant = _grant_one(row, present[user_id], actor=actor, event=event, expires_at=expires_at,
                                       notes=notes)
                result.update(status="already_certified" if grant is None else "granted",
                              grant_id=getattr(grant, "pk", None), guest=isinstance(grant, GuestCertificationGrant))
            except (ValidationError, PermissionDenied) as exc:
                detail = exc.detail if isinstance(exc.detail, dict) else {"detail": exc.detail}
                result.update(status="refused", code=str(detail.get("code", "refused")))
            except IntegrityError:
                # A concurrent grant won the unique row: report it as a typed refusal, never a 500.
                result.update(status="refused", code="grant_conflict")
            results.append(result)
    return results


@transaction.atomic
def revoke_guest_grant(grant, *, actor):
    grant = GuestCertificationGrant.objects.select_for_update(of=("self",)).select_related(
        "certification_type__machine_type", "makerspace").get(pk=grant.pk)
    require_induction(grant.makerspace)
    if not _may_grant(actor, grant.certification_type):
        raise PermissionDenied()
    if grant.revoked_at is not None:
        raise ValidationError(gettext("This certification is already revoked."))
    grant.revoked_at, grant.revoked_by = timezone.now(), actor
    grant.save(update_fields=["revoked_at", "revoked_by"])
    record(actor, "certification.guest_revoked", makerspace=grant.makerspace, target=grant, meta={
        "certification_type_id": grant.certification_type_id, "machine_type_id": grant.certification_type.machine_type_id,
        "user_id": grant.user_id})
    from .notifications_p2_certifications import notify_guest
    notify_guest(grant, "revoked")
    return grant
