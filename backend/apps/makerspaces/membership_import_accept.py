"""Accepting an imported membership (G18, #128 C-13): the only moment it links.

`claim_invitation` hands an invitation that came from an import here, inside its own
transaction and makerspace lock, AFTER it has checked that the signed-in person's
VERIFIED email equals the invitation's. Only then is the membership activated (source
`import`, no dues -- the space already counted this person as a member), the imported
term opened with the file's dates and an unknown price, and the record fields copied.
An imported term that had already ended is not reopened.
"""
from datetime import timedelta

from django.utils import timezone

from apps.audit import services as audit
from apps.makerspaces.local_time import local_day_bounds
from apps.makerspaces.models import ImportedMember, MembershipRecord, MembershipTerm


def pending_import_for(row):
    return ImportedMember.objects.select_for_update().filter(
        invitation=row, status=ImportedMember.Status.INVITED).first()


def _open_term(user, membership, imported, space):
    from apps.makerspaces.membership_plan_services import create_term
    plan, now = imported.plan, timezone.now()
    if plan is None or not plan.is_active or plan.archived_at is not None:
        return None
    starts_at = local_day_bounds(space, imported.starts_on)[0] if imported.starts_on else now
    ends_at = local_day_bounds(space, imported.ends_on)[1] if imported.ends_on else None
    if ends_at is not None and ends_at <= now:
        return None
    if ends_at is not None and ends_at <= starts_at:
        starts_at = ends_at - timedelta(days=1)
    term = create_term(user, membership, plan, starts_at=starts_at, ends_at=ends_at,
                       kind=MembershipTerm.Kind.NEW)
    # What the member paid before the import was never stored here (X6: price unknown).
    MembershipTerm.objects.filter(pk=term.pk).update(price=None)
    return term


def accept_import(user, makerspace, row, imported):
    """Activate `imported` for `user`. Caller holds the makerspace and invitation locks."""
    from apps.makerspaces.membership_activation import _activate_membership
    from apps.makerspaces.membership_helpers import _member_role
    membership = _activate_membership(user, makerspace, user, row.assigned_role or _member_role(makerspace),
                                       request=row, source="import", skip_dues=True)
    term = _open_term(user, membership, imported, makerspace)
    if imported.state_code or imported.gstin or imported.staff_notes:
        record = MembershipRecord.objects.filter(membership=membership).first() or MembershipRecord(
            makerspace=makerspace, membership=membership)
        record.state_code = record.state_code or imported.state_code
        record.gstin = record.gstin or imported.gstin
        record.staff_notes = record.staff_notes or imported.staff_notes
        record.save()
    imported.status, imported.membership, imported.accepted_at = (
        ImportedMember.Status.ACCEPTED, membership, timezone.now())
    imported.save()
    audit.record(user, "membership.import_accepted", makerspace=makerspace, target=membership,
                 meta={"membership_id": membership.pk, "imported_member_id": imported.pk,
                       "term_id": term.pk if term else None})
    return membership
