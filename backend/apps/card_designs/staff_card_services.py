"""Issue, reissue, revoke and print staff ID cards (O-B4 part 2). Every step is audited.

Authority is `MANAGE_MEMBER_CARDS` (or `MANAGE_STAFF`) in the space. One live card per active staff membership.
A card exists only for an ACTIVE staff-track membership of an active, unrestricted account; a reissue keeps the
number and rotates the public check token (the old printed card then verifies as "a newer card was issued").
"""
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

from apps.accounts import rbac
from apps.audit import services as audit
from apps.makerspaces.guards import require_module_locked
from apps.makerspaces.models import MakerspaceMembership

from . import staff_card_numbering
from .lifecycle import on_issue, on_reissue, on_revoke
from .models_staff_cards import StaffCard
from .staff_card_roles import role_slugs
from .switches import staff_cards_on

QUOTA = "staff_cards_issued_monthly"  # limit key (decision 284)


def can_manage(actor, makerspace_id):
    return rbac.can(actor, rbac.Action.MANAGE_MEMBER_CARDS, makerspace_id) or rbac.can(
        actor, rbac.Action.MANAGE_STAFF, makerspace_id)


def require_manage(actor, makerspace_id):
    if not can_manage(actor, makerspace_id):
        raise DjangoPermissionDenied()


def eligible(membership):
    user = membership.user
    return (membership.track == MakerspaceMembership.Track.STAFF and membership.status == "active"
            and user.is_active and user.access_status == "active")


def live_card(membership):
    return StaffCard.objects.filter(membership=membership, revoked_at__isnull=True).first()


def _next_card_number(makerspace_id):
    return (StaffCard.objects.filter(makerspace_id=makerspace_id).aggregate(top=Max("card_number"))["top"] or 0) + 1


def _lock(membership):
    return MakerspaceMembership.staff_tracks.select_for_update().select_related("makerspace", "user").get(
        pk=membership.pk)


def _create(actor, membership, *, automatic):
    card = StaffCard.objects.create(
        makerspace_id=membership.makerspace_id, membership=membership,
        card_number=_next_card_number(membership.makerspace_id),
        number_text=staff_card_numbering.next_number(membership), roles=role_slugs(membership))
    on_issue("staff_card", card)
    audit.record(actor, "staff_card.auto_issued" if automatic else "staff_card.issued",
                 makerspace=membership.makerspace, target=card,
                 meta={"card_id": card.pk, "card_number": card.card_number, "membership_id": membership.pk})
    return card


@transaction.atomic
def issue(actor, membership):
    """Manual issue. Typed errors: 409 quota (ExtraQuotaReached), 409 number exhausted, 400 not eligible."""
    require_manage(actor, membership.makerspace_id)
    membership = _lock(membership)
    require_module_locked(membership.makerspace_id, "membership")
    if not staff_cards_on(membership.makerspace):
        raise ValidationError({"detail": gettext("Staff ID cards are switched off for this space.")})
    if not eligible(membership):
        raise ValidationError({"detail": gettext("Only an active staff member with an active account holds a staff card.")})
    if live_card(membership) is not None:
        raise ValidationError({"detail": gettext("This person already holds a staff card; reissue it instead.")})
    from apps.managed_hosting.extra_quotas import check_extra_quota
    check_extra_quota(membership.makerspace, QUOTA)
    return _create(actor, membership, automatic=False)


@transaction.atomic
def auto_issue(membership):
    """System issue when a staff role is granted and `membership.staff_cards_auto_issue` is on; idempotent."""
    from apps.managed_hosting.extra_quotas import ExtraQuotaReached, check_extra_quota
    from .numbering import CardNumberExhausted
    membership = _lock(membership)
    if not (staff_cards_on(membership.makerspace) and eligible(membership)) or live_card(membership) is not None:
        return None
    try:
        check_extra_quota(membership.makerspace, QUOTA)
        return _create(None, membership, automatic=True)
    except (ExtraQuotaReached, CardNumberExhausted) as exc:
        audit.record(None, "staff_card.auto_issue_skipped", makerspace=membership.makerspace, target=membership,
                     meta={"membership_id": membership.pk, "reason": getattr(exc, "default_code", None) or "quota"})
        return None


def reissue_locked(actor, card, *, reason):
    """Same number, new check token; the held roles are re-recorded. `reason` is audit meta only."""
    card = StaffCard.objects.select_for_update(of=("self",)).select_related("membership").get(pk=card.pk)
    if card.revoked_at is not None:
        raise ValidationError({"detail": gettext("A revoked card cannot be reissued; issue a new one.")})
    card.issued_at = timezone.now()
    card.roles = role_slugs(card.membership)
    card.save(update_fields=["issued_at", "roles", "updated_at"])
    on_reissue("staff_card", card)
    audit.record(actor, "staff_card.reissued", makerspace=card.makerspace, target=card,
                 meta={"card_id": card.pk, "card_number": card.card_number, "reason": reason})
    return card


@transaction.atomic
def reissue(actor, card, *, reason="manual"):
    require_manage(actor, card.makerspace_id)
    return reissue_locked(actor, card, reason=reason)


def revoke_locked(actor, card, *, reason):
    card = StaffCard.objects.select_for_update().get(pk=card.pk)
    if card.revoked_at is not None:
        return card
    card.revoked_at, card.revoked_reason = timezone.now(), reason[:32]
    card.save(update_fields=["revoked_at", "revoked_reason", "updated_at"])
    on_revoke("staff_card", card)
    audit.record(actor, "staff_card.revoked", makerspace=card.makerspace, target=card,
                 meta={"card_id": card.pk, "card_number": card.card_number, "reason": reason})
    return card


@transaction.atomic
def revoke(actor, card, *, reason="revoked"):
    require_manage(actor, card.makerspace_id)
    return revoke_locked(actor, card, reason=reason)


def record_print(actor, card):
    card.print_count += 1
    card.last_printed_at = timezone.now()
    card.save(update_fields=["print_count", "last_printed_at", "updated_at"])
    audit.record(actor, "staff_card.printed", makerspace=card.makerspace, target=card,
                 meta={"card_id": card.pk, "card_number": card.card_number, "count": card.print_count})


def bulk_issue(actor, makerspace_id, membership_ids):
    """Issue for each listed staff membership; returns {"issued": [cards], "skipped": [{"membership_id", "reason"}]}.

    Each membership is its own transaction, so one quota or eligibility refusal never blocks the rest.
    """
    from apps.managed_hosting.extra_quotas import ExtraQuotaReached
    require_manage(actor, makerspace_id)
    issued, skipped = [], []
    rows = {row.pk: row for row in MakerspaceMembership.staff_tracks.filter(
        makerspace_id=makerspace_id, pk__in=membership_ids).select_related("user", "makerspace")}
    for membership_id in membership_ids:
        row = rows.get(membership_id)
        if row is None:
            skipped.append({"membership_id": membership_id, "reason": "not_found"})
            continue
        try:
            issued.append(issue(actor, row))
        except ExtraQuotaReached:
            skipped.append({"membership_id": membership_id, "reason": "quota"})
        except ValidationError as exc:
            skipped.append({"membership_id": membership_id, "reason": _reason(exc)})
    return {"issued": issued, "skipped": skipped}


def _reason(exc):
    return "already_issued" if "already" in str(exc.detail) else "not_eligible"
