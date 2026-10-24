"""Fixed immutable programme maintenance; no general history-write bypass."""
from django.core.exceptions import ValidationError
from django.db import connection

from .models import PiiGlobalWriteFence, PiiMakerspaceWriteFence
from .registry import fields_for, makerspace_id_for
from .write_fence import assert_mapped_write_allowed

IMMUTABLE_LABELS = frozenset({
    "events.SubmissionSnapshot", "events.HackathonApplicationAnswerRevision",
    "events.ApplicationReview", "events.TeamComment", "events.EventContributionHoursEntry",
    "events.EventShiftAttendanceCorrection", "events.EventHelpAction", "events.EventHelpComment",
    "events.MentorRoundCheckin", "events.OfficeHoursChange", "events.EventRoleAnswerRevision",
    "events.EventRequirementOverride", "events.JudgingReason", "events.JudgeScore",
})
MANDATORY_SOURCE_LABEL = "events.EventAnswerDerivation"
MANDATORY_SOURCE_ERROR = ("Birth-date source evidence requires ciphertext; scoped PII rollback is refused while it is retained. "
    "Keep scoped PII enabled and retain tenant keys until authorized event retention or purge removes that evidence.")


def assert_immutable_maintenance(row, changed, operation_kind):
    if row._meta.label not in IMMUTABLE_LABELS:
        return
    fields = fields_for(row)
    if not set(changed) <= {field.field_name for field in fields}:
        raise ValidationError("Maintenance can change only fixed mapped PII columns.")
    tenant_id = makerspace_id_for(row, fields[0])
    # Acquire the persistent global/tenant fences before checking the operation.
    assert_mapped_write_allowed(tenant_id)
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.pii_fence_operation', true)")
        operation = cursor.fetchone()[0]
    fences = (PiiGlobalWriteFence.objects.filter(pk=1).first(),
              PiiMakerspaceWriteFence.objects.filter(makerspace_id=tenant_id).first())
    if operation_kind not in {"enable_transition", "decrypt_rollback"} or not operation or any(
        fence is None or fence.state != "closed" or str(fence.operation_id) != operation
        or fence.operation_kind != operation_kind for fence in fences
    ):
        raise ValidationError("Matching closed global and tenant maintenance fences are required.")


def encrypt_immutable(row):
    from .crypto import encrypt, is_envelope
    from .maintenance import write_legacy_values
    from .preparation import prepared_keys

    if row._meta.label not in IMMUTABLE_LABELS:
        raise ValueError("Use the mapped immutable programme allowlist.")
    fields = fields_for(row)
    assert_immutable_maintenance(row, [field.field_name for field in fields], "enable_transition")
    tenant_id = makerspace_id_for(row, fields[0])
    active, keys = prepared_keys(tenant_id)
    values = {}
    for item in fields:
        raw = row.__dict__.get(item.field_name)
        if raw not in (None, "") and not is_envelope(raw):
            values[item.field_name] = encrypt(raw.encode("utf-8"), keys[active.version],
                key_version=active.version, makerspace_id=tenant_id, table=row._meta.db_table,
                pk=row.pk, field=item.field_name)
    return write_legacy_values(row, values, operation_kind="enable_transition")
