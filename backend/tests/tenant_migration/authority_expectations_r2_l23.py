"""Literal section 3a dispositions for lane L23's machine-session rows (local only)."""

from apps.tenant_migration.tenant_dump_types import AuthorityDisposition as D


def _fields(label, names, dispositions):
    return [((label, name), (dispositions,)) for name in names.split()]


L23_EXPECTED = dict([
    *_fields("machines.MachineSession", "source started_at ended_at stop_reason flagged duration_minutes billable "
             "quote_snapshot quote_digest created_at", D.PRESERVE),
    *_fields("machines.MachineSession", "device_job_ref", D.RESET),
    *_fields("machines.MachineSessionAmendment", "kind minutes reason created_at", D.PRESERVE),
    *_fields("machines.MakerspaceMachineTypePolicy", "session_max_minutes", D.PRESERVE),
])
