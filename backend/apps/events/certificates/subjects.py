"""One adapter for nullable certificate subjects; no blind registration dereference."""

from dataclasses import dataclass
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.events import event_authority
from apps.events.models_registration import EventRegistration
from apps.events.credentials.errors import ProgrammeConflict
from apps.encryption.account_write_fence import assert_account_fence_held

_role_eligibility = None
_award_eligibility = None


@dataclass(frozen=True)
class EligibleSubject:
    subject_kind: str
    subject_id: int
    event_id: int
    member_id: int
    recipient_name: str


def install_eligibility(*, roles, awards):
    """G installs C verified-contribution and D result/recipient providers."""
    global _role_eligibility, _award_eligibility
    _role_eligibility, _award_eligibility = roles, awards


def require_subject(event, *, subject_kind, subject_id, kind, award_id=None, result_revision_id=None, prepared=None):
    if prepared is None or (prepared.kind, prepared.subject_id) != (subject_kind, subject_id):
        raise ProgrammeConflict("Prepare the exact recipient before the event lock.", code="subject_changed")
    assert_account_fence_held(prepared.member_id)
    if subject_kind == "registration":
        row = EventRegistration.objects.select_for_update().filter(event=event, pk=subject_id).first()
        if row is None:
            raise NotFound()
        if row.status not in ("registered", "attended") or not row.member_id:
            raise ProgrammeConflict("Attendance and a member account are required.", code="certificate_ineligible")
        if kind == "attendance" and row.status != "attended":
            raise ProgrammeConflict("Attendance is required.", code="certificate_ineligible")
        if kind not in ("attendance", "participant", "finalist", "winner"):
            raise ProgrammeConflict("Certificate kind does not match the subject.", code="certificate_ineligible")
        assert_account_fence_held(row.member_id)
        if prepared.member_id != row.member_id:
            raise ProgrammeConflict("Prepare the recipient before the event lock.", code="subject_changed")
        if row.__dict__["name"] != prepared.raw_name:
            raise ProgrammeConflict("Recipient changed. Retry preparation.", code="subject_changed")
        result = EligibleSubject("registration", row.pk, event.pk, row.member_id, prepared.name)
    elif subject_kind == "role_assignment":
        if _role_eligibility is None:
            raise ProgrammeConflict("Verified contribution provider is unavailable.", code="certificate_ineligible")
        result = _role_eligibility(event_id=event.pk, assignment_id=subject_id, kind=kind)
        if not isinstance(result, EligibleSubject):
            raise ProgrammeConflict("Verified contribution is required.", code="certificate_ineligible")
    else:
        raise NotFound()
    if result.event_id != event.pk or result.subject_kind != subject_kind or result.subject_id != subject_id:
        raise NotFound()
    assert_account_fence_held(result.member_id)
    from apps.accounts.models import User
    if not User.objects.filter(pk=result.member_id, account_kind="member", is_active=True,
            access_status="active", is_tenant_dump_stub=False, retired_at__isnull=True).exists():
        raise ProgrammeConflict("Recipient account is unavailable.", code="certificate_ineligible")
    if (prepared.member_id, prepared.name) != (result.member_id, result.recipient_name):
        raise ProgrammeConflict("Recipient changed. Retry preparation.", code="subject_changed")
    if kind in ("finalist", "winner", "participant"):
        if (kind != "participant" and (not award_id or not result_revision_id)) or _award_eligibility is None or _award_eligibility(
                event_id=event.pk, member_id=result.member_id, award_id=award_id,
                result_revision_id=result_revision_id, kind=kind) is not True:
            raise ProgrammeConflict("A current result award is required.", code="certificate_ineligible")
    elif award_id or result_revision_id:
        raise ProgrammeConflict("This certificate kind cannot carry a prize.", code="certificate_ineligible")
    return result


def require_read(certificate, actor):
    event = certificate.event
    if not event_authority._active(actor):
        raise PermissionDenied()
    if actor.account_kind == "member" and certificate.recipient_member_id == actor.pk:
        from apps.makerspaces.guards import require_module
        require_module(event.makerspace, "events")
    else:
        event_authority.require(actor, event, None)
    if certificate.status != "revoked" and (certificate.role_assignment_id or certificate.kind in ("participant", "finalist", "winner")):
        from .lifecycle import _eligible
        from .locked import certificate_command
        with certificate_command(certificate.pk) as (_, _, checked, prepared):
            _eligible(checked, prepared)


def recipient(certificate):
    return certificate.recipient_member
