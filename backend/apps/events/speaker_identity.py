"""Link an account to an event as its speaker, by staff assignment or by an invite claim.

Both directions are audited with the person who acted: the staff member who assigned or
invited, and the account that claimed. Speaker credit is never authority by itself; the
optional check-in grant is created through the same event staff-grant model the Team tab
shows, and only when the linking authority could have granted it directly.
"""

from django.utils.translation import gettext
import secrets
from datetime import timedelta
from urllib.parse import quote

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.accounts.staff_identity import person_q
from apps.audit.services import record
from apps.makerspaces.resource_grants_services import _audit as grant_audit, credential_digest

from . import event_authority
from .event_permissions import CHECK_IN, EDIT_DETAILS
from .models import EventPageSection, EventStaffGrant, EventSpeaker
from .services_staff_grants import ADAPTER, _locked_target

CLAIM_LIFETIME = timedelta(days=14)
NAMESPACE = "events.speaker"


def _digest(token):
    return credential_digest(token, namespace=NAMESPACE, purpose="invite")


def display_name(user):
    return (user.get_full_name() or user.username or "").strip()[:200]


def candidates_q(event):
    """Community accounts known through membership, registration or a delegate grant."""
    return person_q() & (Q(makerspace_memberships__makerspace_id=event.makerspace_id,
              makerspace_memberships__status="active")
            | Q(event_registrations__event_id=event.pk)
            | Q(event_staff_grants__event_id=event.pk, event_staff_grants__revoked_at__isnull=True))


def candidate_accounts(event, search):
    from apps.accounts.models import User
    search = (search or "").strip()
    if len(search) < 2:
        return User.objects.none()
    terms = Q(username__icontains=search) | Q(first_name__icontains=search) | Q(last_name__icontains=search)
    return (User.objects.filter(candidates_q(event)).filter(terms)
            .filter(is_active=True, access_status="active", is_tenant_dump_stub=False)
            .distinct().order_by("first_name", "last_name", "username", "pk"))


def _section(event, slug):
    if not slug:
        return None
    section = EventPageSection.objects.filter(page__event=event, kind=EventPageSection.Kind.SPEAKER,
                                             slug=slug, is_working=True).first()
    if section is None:
        raise ValidationError({"section_slug": gettext("No speaker section with this slug on the event website.")})
    return section


def _require_link_authority(actor, event, grant_check_in):
    event_authority.require(actor, event, EDIT_DETAILS)
    if grant_check_in and not (event_authority.can_manage_grants(actor, event)
                               and event_authority.can(actor, event, CHECK_IN)):
        raise PermissionDenied(gettext("Only an event manager can also grant check-in access."))


def _ensure_check_in_grant(event, user, granted_by):
    grant = EventStaffGrant.objects.select_for_update().filter(
        event=event, user=user, revoked_at__isnull=True).first()
    if grant is None:
        grant = EventStaffGrant.objects.create(
            makerspace=event.makerspace, event=event, user=user, permissions=[CHECK_IN],
            granted_by=granted_by, role_label="speaker")
        grant_audit(ADAPTER, granted_by, "created", grant)
    elif CHECK_IN not in grant.permissions:
        grant.permissions = sorted({*grant.permissions, CHECK_IN})
        grant.save(update_fields=["permissions"])
        grant_audit(ADAPTER, granted_by, "updated", grant)
    return grant


def _create(**values):
    try:
        with transaction.atomic():
            return EventSpeaker.objects.create(**values)
    except IntegrityError as exc:
        raise ValidationError({"user_id": gettext("This account is already a speaker at this event.")}) from exc


@transaction.atomic
def assign_speaker(event, *, actor, user, name="", section_slug="", grant_check_in=False):
    from apps.accounts.models import User
    event = _locked_target(event)
    _require_link_authority(actor, event, grant_check_in)
    account = User.objects.filter(candidates_q(event), pk=getattr(user, "pk", user),
                                  is_active=True, access_status="active").distinct().first()
    if account is None:
        raise ValidationError({"user_id": gettext("Choose a member account known to this event.")})
    speaker = _create(makerspace=event.makerspace, event=event, user=account,
                      section=_section(event, section_slug), display_name=(name or display_name(account))[:200],
                      linked_via=EventSpeaker.LinkedVia.STAFF_ASSIGNED, grants_check_in=grant_check_in,
                      assigned_by=actor)
    record(actor, "event.speaker_assigned", makerspace=event.makerspace, target=speaker,
           meta={"linked_via": "staff_assigned", "grants_check_in": grant_check_in})
    if grant_check_in:
        _ensure_check_in_grant(event, account, actor)
    return speaker


@transaction.atomic
def invite_speaker(event, *, actor, name, section_slug="", grant_check_in=False):
    from apps.makerspaces.platform import member_area_url
    event = _locked_target(event)
    _require_link_authority(actor, event, grant_check_in)
    if not (name or "").strip():
        raise ValidationError({"display_name": gettext("A display name is required.")})
    token = secrets.token_urlsafe(32)
    speaker = EventSpeaker.objects.create(
        makerspace=event.makerspace, event=event, section=_section(event, section_slug),
        display_name=name.strip()[:200], grants_check_in=grant_check_in, assigned_by=actor,
        claim_token_digest=_digest(token), claim_expires_at=timezone.now() + CLAIM_LIFETIME)
    record(actor, "event.speaker_invited", makerspace=event.makerspace, target=speaker,
           meta={"grants_check_in": grant_check_in})
    # A fragment keeps the bearer out of referrers and server access logs.
    return speaker, f"{member_area_url(event.makerspace).rstrip('/')}/speaker-claim#token={quote(token)}"


@transaction.atomic
def claim_speaker(token, *, actor):
    if not event_authority._active(actor):
        raise PermissionDenied()
    candidate = EventSpeaker.objects.filter(claim_token_digest=_digest(token or "")).first() if token else None
    if candidate is None:
        raise NotFound(gettext("Speaker invitation not found."))
    event = _locked_target(candidate.event)
    speaker = EventSpeaker.objects.select_for_update().get(pk=candidate.pk)
    if (speaker.removed_at or speaker.user_id or speaker.claimed_at
            or not speaker.claim_expires_at or speaker.claim_expires_at <= timezone.now()):
        raise NotFound(gettext("Speaker invitation not found."))
    if EventSpeaker.objects.filter(event=event, user=actor, removed_at__isnull=True).exists():
        raise ValidationError({"token": gettext("You are already a speaker at this event.")})
    speaker.user, speaker.claimed_at = actor, timezone.now()
    speaker.linked_via = EventSpeaker.LinkedVia.CLAIMED
    speaker.save(update_fields=["user", "claimed_at", "linked_via"])
    record(actor, "event.speaker_claimed", makerspace=event.makerspace, target=speaker,
           meta={"linked_via": "claimed"})
    if speaker.grants_check_in:
        from apps.accounts.models import User
        # Like an invite redemption: the creator's CURRENT authority must still cover it.
        creator = User.objects.filter(pk=speaker.assigned_by_id).first()
        if creator and event_authority.can_manage_grants(creator, event) and event_authority.can(creator, event, CHECK_IN):
            _ensure_check_in_grant(event, actor, creator)
    return speaker


@transaction.atomic
def remove_speaker(speaker, *, actor):
    event = _locked_target(speaker.event)
    event_authority.require(actor, event, EDIT_DETAILS)
    row = EventSpeaker.objects.select_for_update().get(pk=speaker.pk)
    if row.removed_at is None:
        row.removed_at, row.removed_by = timezone.now(), actor
        row.save(update_fields=["removed_at", "removed_by"])
        record(actor, "event.speaker_removed", makerspace=event.makerspace, target=row)
    return row
