"""The hosting-request state machine. The ONLY module that writes ``HostingRequest.status``.

    public:  create -> pending_verification -verify-> submitted -accept-> accepted
    invited: create -> invited -answer-> pending_verification -verify-> submitted
             invited | pending_verification(invited) -inviter cancels-> withdrawn
             pending_verification(invited) -answer again-> pending_verification
    submitted | accepted (no makerspace linked) -reject(reason)-> rejected

Unverified public submissions are not audited (anonymous input must not grow the
append-only log); every later transition is. Lock order: makerspace -> organization ->
organization membership -> hosting row.
"""

from datetime import timedelta

from django.db import transaction
from django.http import Http404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from apps.hosting_requests import authority, notifications, tokens
from apps.hosting_requests.applicant import (
    apply_applicant_fields, clean_reason, invitation_row, require_superadmin,
)
from apps.hosting_requests.exceptions import HostingRequestConflict
from apps.hosting_requests.models import HostingRequest

S = HostingRequest.Status
VERIFICATION_TTL = timedelta(hours=48)
INVITE_TTL = timedelta(days=14)
ALLOWED = frozenset({
    (S.INVITED, S.PENDING_VERIFICATION),
    (S.PENDING_VERIFICATION, S.PENDING_VERIFICATION),
    (S.PENDING_VERIFICATION, S.SUBMITTED),
    (S.INVITED, S.WITHDRAWN),
    (S.PENDING_VERIFICATION, S.WITHDRAWN),
    (S.SUBMITTED, S.ACCEPTED),
    (S.SUBMITTED, S.REJECTED),
    (S.ACCEPTED, S.REJECTED),
})


def _transition(row, to):
    if (row.status, to) not in ALLOWED:
        raise HostingRequestConflict()
    row.status = to


def _locked(**lookup):
    row = HostingRequest.objects.select_for_update().filter(**lookup).first()
    if row is None:
        raise Http404()
    return row


def _rotate_access_token(row, now):
    raw, row.access_token_digest = tokens.mint()
    row.verification_expires_at = now + VERIFICATION_TTL
    return raw


@transaction.atomic
def create_public(data):
    now = timezone.now()
    row = HostingRequest(status=S.PENDING_VERIFICATION, source=HostingRequest.Source.PUBLIC)
    apply_applicant_fields(row, data)
    raw = _rotate_access_token(row, now)
    row.save()
    notifications.schedule_verify(row, raw)
    return row, raw


def create_invitation(actor, *, makerspace_id=None, organization_id=None, invitee_email,
                      space_name="", note=""):
    if (makerspace_id is None) == (organization_id is None):
        raise ValidationError({"detail": "Name exactly one inviting makerspace or organization."})
    with transaction.atomic():
        if makerspace_id is not None:
            makerspace = authority.resolve_makerspace_inviter(actor, makerspace_id)
            organization = authority.offerable_owner_organization(actor, makerspace)
            kind, inviter_name = HostingRequest.InviterKind.MAKERSPACE, makerspace.name
        else:
            makerspace = None
            organization = authority.resolve_organization_inviter(actor, organization_id)
            kind, inviter_name = HostingRequest.InviterKind.ORGANIZATION, organization.name
        raw, digest = tokens.mint()
        row = invitation_row(
            kind=kind, makerspace=makerspace, organization=organization, actor=actor,
            invitee_email=invitee_email, space_name=space_name, note=note,
            invite_token_digest=digest, invite_expires_at=timezone.now() + INVITE_TTL,
        )
        row.status = S.INVITED
        row.save()
        audit.record(
            actor, "hosting_request.invitation_created", makerspace=makerspace, target=row,
            meta={
                "inviter_makerspace_id": row.inviter_makerspace_id,
                "inviter_organization_id": row.inviter_organization_id,
            },
        )
    url, status = notifications.send_invitation(row, raw, inviter_name)
    return row, url, status


@transaction.atomic
def cancel_invitation(actor, *, pk, makerspace_id=None, organization_id=None):
    if (makerspace_id is None) == (organization_id is None):
        raise ValidationError({"detail": "Name exactly one inviting makerspace or organization."})
    kind = (HostingRequest.InviterKind.MAKERSPACE if makerspace_id is not None
            else HostingRequest.InviterKind.ORGANIZATION)
    scope = ({"inviter_makerspace_id": makerspace_id} if makerspace_id is not None
             else {"inviter_organization_id": organization_id})
    if not HostingRequest.objects.filter(pk=pk, inviter_kind=kind, **scope).exists():
        raise Http404()
    if makerspace_id is not None:
        authority.resolve_makerspace_inviter(actor, makerspace_id)
    else:
        authority.resolve_organization_inviter(actor, organization_id)
    row = _locked(pk=pk)
    if row.inviter_kind != kind or any(getattr(row, k) != v for k, v in scope.items()):
        raise HostingRequestConflict("This invitation changed. Refresh and try again.")
    _transition(row, S.WITHDRAWN)
    row.withdrawn_at = timezone.now()
    row.save(update_fields=["status", "withdrawn_at", "updated_at"])
    audit.record(
        actor, "hosting_request.invitation_cancelled",
        makerspace=row.inviter_makerspace, target=row, meta={},
    )
    return row


def _live_invitation(raw_invite_token, *, lock):
    digest = tokens.digest(raw_invite_token)
    rows = HostingRequest.objects.select_for_update() if lock else HostingRequest.objects
    row = rows.filter(
        invite_token_digest=digest, source=HostingRequest.Source.INVITED,
        status__in=(S.INVITED, S.PENDING_VERIFICATION), invite_expires_at__gt=timezone.now(),
    ).first()
    if row is None:
        raise Http404()
    return row


def resolve_invitation(raw_invite_token):
    return _live_invitation(raw_invite_token, lock=False)


def join_available(row):
    organization = row.inviter_organization
    return bool(organization is not None and organization.is_active)


@transaction.atomic
def submit_invited(raw_invite_token, data):
    row = _live_invitation(raw_invite_token, lock=True)
    choice = data.get("organization_choice") or HostingRequest.OrganizationChoice.OWN
    if choice == HostingRequest.OrganizationChoice.JOIN and not join_available(row):
        raise ValidationError({"organization_choice": "Joining the inviting organization is not offered."})
    apply_applicant_fields(row, data)
    row.organization_choice = choice
    if choice == HostingRequest.OrganizationChoice.JOIN:
        row.new_organization_name = ""
    _transition(row, S.PENDING_VERIFICATION)
    raw = _rotate_access_token(row, timezone.now())
    row.save()
    audit.record(
        None, "hosting_request.invitation_answered",
        makerspace=row.inviter_makerspace, target=row, meta={},
    )
    notifications.schedule_verify(row, raw)
    return row


@transaction.atomic
def open_by_token(raw_access_token):
    row = _locked(access_token_digest=tokens.digest(raw_access_token))
    now = timezone.now()
    if row.status != S.PENDING_VERIFICATION:
        return row
    if row.verification_expires_at is None or row.verification_expires_at <= now:
        raise Http404()
    _transition(row, S.SUBMITTED)
    row.verified_at = now
    row.save(update_fields=["status", "verified_at", "updated_at"])
    audit.record(
        None, "hosting_request.submitted", makerspace=row.inviter_makerspace, target=row,
        meta={"source": row.source},
    )
    notifications.schedule_new(row)
    return row


@transaction.atomic
def accept(actor, row_id):
    require_superadmin(actor)
    row = _locked(pk=row_id)
    _transition(row, S.ACCEPTED)
    row.decided_at, row.decided_by = timezone.now(), actor
    row.save(update_fields=["status", "decided_at", "decided_by", "updated_at"])
    audit.record(actor, "hosting_request.accepted", target=row, meta={})
    notifications.schedule_accepted(row)
    return row


@transaction.atomic
def reject(actor, row_id, reason):
    require_superadmin(actor)
    reason = clean_reason(reason)
    row = _locked(pk=row_id)
    if row.created_makerspace_id is not None:
        raise HostingRequestConflict("A makerspace was already created from this request.")
    _transition(row, S.REJECTED)
    row.decided_at, row.decided_by, row.rejection_reason = timezone.now(), actor, reason
    row.save(update_fields=["status", "decided_at", "decided_by", "rejection_reason", "updated_at"])
    audit.record(actor, "hosting_request.rejected", target=row, meta={})
    notifications.schedule_rejected(row)
    return row


def link_created_makerspace(actor, request_id, makerspace):
    """Record which makerspace a superadmin created from an accepted request.

    Runs inside the /control/ add view's transaction, after owner assignment locked
    makerspace -> organization. A refusal raises and rolls the whole creation back.
    The chosen owner is deliberately not compared with the applicant's choice.
    """
    require_superadmin(actor)
    row = HostingRequest.objects.select_for_update().filter(pk=request_id).first()
    if row is None or row.status != S.ACCEPTED or row.created_makerspace_id is not None:
        raise HostingRequestConflict("Only an accepted request with no makerspace can be linked.")
    row.created_makerspace = makerspace
    row.save(update_fields=["created_makerspace", "updated_at"])
    audit.record(
        actor, "hosting_request.makerspace_linked", target=row,
        meta={"makerspace_id": makerspace.pk},
    )
    return row
