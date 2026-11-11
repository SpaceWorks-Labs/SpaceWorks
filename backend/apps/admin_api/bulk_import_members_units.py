"""Parity O-B1: member import into a unit, and the "verify" mode where the unit lead approves each row first.

* `resolve_import_unit(actor, space, unit_id, verify)` -- the unit rows land in (None when no unit was chosen).
  Needs `membership.units`; the unit must be active, in this space and inside the importer's own subtree.
* `attach_unit(imported, unit, verify)` -- records the unit. In verify mode the row is a RECORD_ONLY entry
  (no invitation, no email) with review `pending`; nothing reaches the person until a lead approves it.
* `approve_review` / `reject_review` -- the unit lead's decision (audited as `member_unit.import_reviewed`).
  Approval sends the normal invitation; the unit is copied to the membership when the person accepts.
"""
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext

from apps.audit import services as audit
from apps.makerspaces import member_unit_scope as scope
from apps.makerspaces.member_units import UnitError
from apps.makerspaces.membership_features import membership_feature_on
from apps.makerspaces.models import ImportedMember
from apps.makerspaces.models_member_units import ImportedMemberUnit, MemberUnit, MembershipRequestUnit

REVIEW = ImportedMemberUnit.Review


def resolve_import_unit(actor, space, unit_id, verify):
    if unit_id in (None, ""):
        if verify:
            raise UnitError("import_verify_needs_unit", gettext("Verify mode needs the unit that will review the rows."))
        return None
    if not membership_feature_on(space, "units"):
        raise UnitError("member_units_off", gettext("Member units are not switched on for this space."))
    unit = MemberUnit.objects.filter(makerspace=space, pk=unit_id, archived_at__isnull=True).first()
    if unit is None or not scope.unit_in_scope(actor, space.pk, unit, "manage_members"):
        raise UnitError("member_unit_missing", gettext("Choose an active unit you may place members in."))
    return unit


def attach_unit(imported, unit, verify):
    ImportedMemberUnit.objects.update_or_create(imported=imported, defaults={
        "makerspace": imported.makerspace, "unit": unit,
        "review_status": REVIEW.PENDING if verify else REVIEW.NOT_REQUIRED})
    if imported.invitation_id and not verify:
        MembershipRequestUnit.objects.update_or_create(request_id=imported.invitation_id, defaults={
            "makerspace": imported.makerspace, "unit": unit})


def _locked_pending(space, imported_id):
    row = ImportedMemberUnit.objects.select_for_update().select_related("imported", "unit").filter(
        makerspace=space, imported_id=imported_id, review_status=REVIEW.PENDING).first()
    if row is None:
        raise UnitError("import_review_missing", gettext("No row is waiting for review."))
    return row


def approve_review(actor, space, imported_id):
    from apps.admin_api.bulk_import_members_apply import _invite
    from apps.makerspaces.membership_helpers import _member_role
    with transaction.atomic():
        from apps.tenant_migration.gate_runtime import assert_write_allowed
        assert_write_allowed(space.pk)
        row = _locked_pending(space, imported_id)
        imported = ImportedMember.objects.select_for_update().get(pk=row.imported_id)
        invited = _invite(actor, space, imported, _member_role(space))
        if invited:
            imported.status = ImportedMember.Status.INVITED
            imported.save(update_fields=["status", "updated_at"])
            MembershipRequestUnit.objects.update_or_create(request_id=imported.invitation_id, defaults={
                "makerspace": space, "unit": row.unit})
        row.review_status, row.reviewed_at = REVIEW.APPROVED, timezone.now()
        row.save(update_fields=["review_status", "reviewed_at"])
        audit.record(actor, "member_unit.import_reviewed", makerspace=space, target=imported,
                     meta={"imported_member_id": imported.pk, "unit_id": row.unit_id, "decision": "approved",
                           "invited": invited})
    return row


def reject_review(actor, space, imported_id):
    with transaction.atomic():
        from apps.tenant_migration.gate_runtime import assert_write_allowed
        assert_write_allowed(space.pk)
        row = _locked_pending(space, imported_id)
        imported = ImportedMember.objects.select_for_update().get(pk=row.imported_id)
        imported.status = ImportedMember.Status.CANCELLED
        imported.save(update_fields=["status", "updated_at"])
        row.review_status, row.reviewed_at = REVIEW.REJECTED, timezone.now()
        row.save(update_fields=["review_status", "reviewed_at"])
        audit.record(actor, "member_unit.import_reviewed", makerspace=space, target=imported,
                     meta={"imported_member_id": imported.pk, "unit_id": row.unit_id, "decision": "rejected"})
    return row
