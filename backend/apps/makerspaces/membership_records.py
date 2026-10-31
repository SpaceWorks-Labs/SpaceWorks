"""The staff-side member record (X13): state code, GSTIN, staff notes, and the source.

Behind `membership.records`, under `manage_members` in the membership's space. GSTIN and
notes are scoped PII on `MembershipRecord`; the notes are staff-only and are never sent
to the member. L5 reads `gstin_for`/`state_code_for` for the place of supply. Each change
is audited by field NAME only -- the values are personal data and stay out of the log.
"""
from django.core.exceptions import ValidationError as ModelValidationError
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from apps.makerspaces.membership_features import require_membership_feature_locked
from apps.makerspaces.models import MakerspaceMembership, MembershipRecord

FIELDS = ("state_code", "gstin", "staff_notes")


def record_for(membership):
    """The membership's record, or an unsaved empty one (nothing recorded yet)."""
    row = MembershipRecord.objects.filter(membership=membership).first()
    return row or MembershipRecord(makerspace_id=membership.makerspace_id, membership=membership)


def gstin_for(membership):
    return (record_for(membership).gstin or "").upper()


def state_code_for(membership):
    return record_for(membership).state_code or ""


def update_record(actor, membership, values):
    values = {name: (values[name] or "").strip() for name in FIELDS if name in values}
    if "gstin" in values:
        values["gstin"] = values["gstin"].upper()
    with transaction.atomic():
        from apps.tenant_migration.gate_runtime import assert_write_allowed
        assert_write_allowed(membership.makerspace_id)
        makerspace = require_membership_feature_locked(membership.makerspace_id, "records")
        membership = MakerspaceMembership.objects.select_for_update().get(pk=membership.pk)
        row = record_for(membership)
        changed = sorted(name for name, value in values.items() if getattr(row, name) != value)
        for name in changed:
            setattr(row, name, values[name])
        try:
            row.clean()
        except ModelValidationError as exc:
            raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else {"detail": exc.messages})
        if changed or row.pk is None:
            row.updated_by = actor
            row.save()
            audit.record(actor, "membership.record_updated", makerspace=makerspace, target=membership,
                         meta={"membership_id": membership.pk, "fields": changed})
    return row


def clear_record(membership):
    """Erasure (X29): blank every personal field this space holds on the record."""
    row = MembershipRecord.objects.filter(membership=membership).first()
    if row is not None:
        row.state_code, row.gstin, row.staff_notes = "", "", ""
        row.save()
