"""Release 0.12.0 lane L3a (induction events, supervised sessions, incident register): tenant-dump snapshot and authority.

The seven models are the space's own accountability history (data_export `classification_l3a`)
and travel with it; foreign keys remap like any other. Times, severities, statuses and the
recorded free text are history and are preserved as written.
"""

# Kept literal (not imported from data_export): the dump snapshot is a pinned, independent record.
_FIELDS = {
    "machines.EventInductionLink": "id makerspace event certification_type created_by created_at",
    "machines.GuestCertificationGrant": ("id makerspace certification_type user source_event granted_by granted_at "
                                         "expires_at revoked_at revoked_by notes"),
    "machines.MachineAccessGrant": "id makerspace member machine machine_type granted_by granted_at expires_at note source revoked_at revoked_by expiry_notice_sent_at",
    "machines.SupervisedSession": "id makerspace machine instructor event note opened_at closed_at closed_by",
    "machines.SupervisedParticipant": "id session user added_by added_at removed_at",
    "machines.SupervisedUse": "id session user instructor started_at ended_at note",
    "maintenance.Incident": ("id makerspace kind severity status area title description location occurred_at reporter "
                             "involved_user involved_note sponsor_user machine room event loan booking repair_issue "
                             "guest_pass triaged_by resolution_note closed_at created_at updated_at"),
    "maintenance.IncidentAction": "id incident description assignee due_date done_at done_by created_by created_at",
}
FIELD_NAMES = {label: frozenset(fields.split()) for label, fields in _FIELDS.items()}
PROJECTED_LABELS = frozenset(FIELD_NAMES)

_PRESERVED = {
    "machines.EventInductionLink": "created_at",
    "machines.GuestCertificationGrant": "granted_at expires_at revoked_at notes",
    "machines.MachineAccessGrant": "granted_at expires_at note source revoked_at expiry_notice_sent_at",
    "machines.SupervisedSession": "note opened_at closed_at",
    "machines.SupervisedParticipant": "added_at removed_at",
    "machines.SupervisedUse": "started_at ended_at note",
    "maintenance.Incident": ("kind severity status area title description location occurred_at involved_note "
                             "resolution_note closed_at created_at updated_at"),
    "maintenance.IncidentAction": "description due_date done_at created_at",
}


def authority_entries(authority, disposition):
    keep = disposition.PRESERVE
    return tuple(
        ((label, name), authority(keep, "The space's own induction, supervision or incident history."))
        for label, names in _PRESERVED.items() for name in names.split())
