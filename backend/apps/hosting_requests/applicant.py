"""Field helpers for the workflow. Nothing here writes ``status``."""

from django.utils.translation import gettext
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.hosting_requests.availability import admin_available
from apps.hosting_requests.models import HostingRequest
from apps.organizations.access import is_superadmin

APPLICANT_FIELDS = (
    "applicant_name", "applicant_phone", "space_name", "proposed_slug", "location",
    "space_website_url", "description", "new_organization_name",
)
REASON_MIN, REASON_MAX = 10, 2000


def normalize_email(value):
    return str(value or "").strip().lower()


def apply_applicant_fields(row, data):
    """Copy serializer-validated applicant fields onto the row."""
    for name in APPLICANT_FIELDS:
        setattr(row, name, str(data.get(name) or "").strip())
    row.applicant_email = normalize_email(data.get("applicant_email"))
    kind = data.get("requested_kind")
    if kind in HostingRequest.RequestedKind.values:
        row.requested_kind = kind
    members = data.get("expected_members")
    row.expected_members = members if type(members) is int and members > 0 else None


def invitation_row(*, kind, makerspace, organization, actor, invitee_email, space_name, note,
                   invite_token_digest, invite_expires_at):
    return HostingRequest(
        source=HostingRequest.Source.INVITED,
        inviter_kind=kind,
        inviter_makerspace=makerspace,
        inviter_organization=organization,
        invited_by=actor,
        applicant_email=normalize_email(invitee_email),
        space_name=str(space_name or "").strip(),
        invite_note=str(note or "").strip(),
        organization_choice=(
            HostingRequest.OrganizationChoice.JOIN if organization is not None
            else HostingRequest.OrganizationChoice.OWN
        ),
        invite_token_digest=invite_token_digest,
        invite_expires_at=invite_expires_at,
    )


def clean_reason(reason):
    value = str(reason or "").strip()
    if not REASON_MIN <= len(value) <= REASON_MAX:
        raise ValidationError(
            {"rejection_reason": gettext('Give a reason of {REASON_MIN} to {REASON_MAX} characters.').format(REASON_MIN=REASON_MIN, REASON_MAX=REASON_MAX)}
        )
    return value


def require_superadmin(actor):
    if not admin_available():
        raise PermissionDenied(gettext("Hosting requests exist only on a managed deployment."))
    if not is_superadmin(actor):
        raise PermissionDenied()
