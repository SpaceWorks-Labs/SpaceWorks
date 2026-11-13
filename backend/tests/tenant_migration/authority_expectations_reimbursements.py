"""Literal §3a dispositions for event reimbursements and staged-form assets."""

from apps.tenant_migration.tenant_dump_types import AuthorityDisposition as D


def _fields(label, names):
    return [((label, name), (D.RESET,)) for name in names.split()]


REIMBURSEMENT_EXPECTED = dict(
    [
        # Imported programmes and stage assignments arrive paused, with no live window.
        *_fields("event_reimbursements.ReimbursementProgramme",
                 "enabled imported_paused request_opens_at request_closes_at"),
        *_fields("events.StageFormAssignment", "creation_operation_id imported_paused"),
        # Source upload leases and bucket version identities never apply on the target.
        *_fields("events.StageFormAsset", "lease_token lease_until attempts staging_version_id final_version_id"),
        *_fields("payments.FinanceAttachment", "lease_token lease_until attempts staging_version_id final_version_id"),
    ]
)
