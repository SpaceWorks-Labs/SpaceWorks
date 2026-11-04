"""Per-space erasure requests (X29): a member asks ONE space to anonymise their data.

Behind `membership.erasure`. The member asks (with an optional note) and may withdraw an
open request; staff with `manage_members` approve or reject with a note. The decision is
sent to the member.

Approval anonymises what THIS space holds about the membership and ends it:
* the membership is ended as a voluntary departure (`membership.left`), which also ends
  its terms (paid ones open a refund due under the policy, #68), its card and sessions;
* the record (state code, GSTIN, staff notes), titles, member profile, application
  answers and any imported-row details are blanked or removed;
* money rows (payments, refunds, settlements) and the audit log are KEPT, and the
  account itself is never deleted (account deletion belongs to U-C).
"""
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from apps.audit import services as audit
from apps.makerspaces.membership_features import require_membership_feature_locked
from apps.makerspaces.models import MakerspaceMembership, MembershipErasureRequest

REASON = "Erasure request approved"


def _lock(makerspace_id):
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    assert_write_allowed(makerspace_id)
    return require_membership_feature_locked(makerspace_id, "erasure")


def request_erasure(member, membership, note=""):
    try:
        with transaction.atomic():
            space = _lock(membership.makerspace_id)
            membership = MakerspaceMembership.objects.select_for_update().get(pk=membership.pk)
            if membership.user_id != member.pk:
                raise NotFound("Membership not found.")
            row = MembershipErasureRequest.objects.create(
                makerspace=space, membership=membership, member_note=(note or "").strip()[:1000])
            audit.record(member, "membership.erasure_requested", makerspace=space, target=row,
                         meta={"membership_id": membership.pk, "request_id": row.pk})
    except IntegrityError as exc:
        raise ValidationError({"detail": "An erasure request is already open."}) from exc
    return row


def withdraw(member, row):
    with transaction.atomic():
        space = _lock(row.makerspace_id)
        row = MembershipErasureRequest.objects.select_for_update().select_related("membership").get(pk=row.pk)
        if row.membership.user_id != member.pk or row.status != row.Status.REQUESTED:
            raise ValidationError({"detail": "This request can no longer be withdrawn."})
        row.status, row.decided_at = row.Status.WITHDRAWN, timezone.now()
        row.save(update_fields=["status", "decided_at", "updated_at"])
        audit.record(member, "membership.erasure_withdrawn", makerspace=space, target=row,
                     meta={"membership_id": row.membership_id, "request_id": row.pk})
    return row


def _open(row):
    row = MembershipErasureRequest.objects.select_for_update().select_related("membership__user").get(pk=row.pk)
    if row.status != row.Status.REQUESTED:
        raise ValidationError({"detail": "This request has already been decided."})
    return row


def reject(actor, row, note):
    note = (note or "").strip()
    if not note:
        raise ValidationError({"note": "Tell the member why their request was rejected."})
    with transaction.atomic():
        space = _lock(row.makerspace_id)
        row = _open(row)
        row.status, row.decision_note = row.Status.REJECTED, note[:500]
        row.decided_by, row.decided_at = actor, timezone.now()
        row.save(update_fields=["status", "decision_note", "decided_by", "decided_at", "updated_at"])
        audit.record(actor, "membership.erasure_rejected", makerspace=space, target=row,
                     meta={"membership_id": row.membership_id, "request_id": row.pk})
        from apps.makerspaces.notifications_l4 import notify_erasure_decision
        notify_erasure_decision(row)
    return row


def approve(actor, row, note=""):
    with transaction.atomic():
        space = _lock(row.makerspace_id)
        row = _open(row)
        membership = MakerspaceMembership.objects.select_for_update().get(pk=row.membership_id)
        if membership.status == "active":
            from apps.makerspaces.membership_revocation import _revoke_locked
            _revoke_locked(actor, membership, space, REASON, self_leave=True)
        anonymise(membership)
        row.status, row.decision_note, row.member_note = row.Status.APPROVED, (note or "").strip()[:500], ""
        row.decided_by, row.decided_at = actor, timezone.now()
        row.save()
        audit.record(actor, "membership.erasure_approved", makerspace=space, target=row,
                     meta={"membership_id": membership.pk, "request_id": row.pk})
        from apps.makerspaces.notifications_l4 import notify_erasure_decision
        notify_erasure_decision(row)
    return row


def anonymise(membership):
    """Blank this space's personal data about the membership. Money and audit stay."""
    from apps.makerspaces.membership_records import clear_record
    from apps.makerspaces.membership_titles import clear_titles
    from apps.makerspaces.models import ImportedMember, MemberProfile, MembershipRequest
    clear_record(membership)
    clear_titles(membership)
    MemberProfile.objects.filter(membership=membership).delete()
    for request in MembershipRequest.objects.filter(makerspace_id=membership.makerspace_id, user_id=membership.user_id):
        if request.application_answers:
            request.application_answers = None
            request.save()
    for imported in ImportedMember.objects.filter(membership=membership):
        imported.name = imported.email = imported.phone = imported.gstin = imported.staff_notes = ""
        imported.external_number = ""
        imported.save()
