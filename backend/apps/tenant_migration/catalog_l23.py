"""Release-2 lane L23 (metered machine sessions): tenant-dump field snapshot and authority.

Sessions and amendments are the space's own machine-usage history (data_export
`classification_l23`) and travel with it; foreign keys remap like any other. The frozen
rate is the session's own price history and is never recomputed. A device session's run
identity names a printer job of the source deployment's device fleet, so it is reset.
"""

SESSION_FIELDS = ("id makerspace machine machine_type member source started_at ended_at stop_reason flagged "
                  "duration_minutes billable quote_snapshot quote_digest service_request device_job_ref started_by "
                  "stopped_by created_at")
AMENDMENT_FIELDS = "id makerspace session kind minutes member reason actor created_at"
FIELD_NAMES = {
    "machines.MachineSession": frozenset(SESSION_FIELDS.split()),
    "machines.MachineSessionAmendment": frozenset(AMENDMENT_FIELDS.split()),
}
EXTRA_FIELDS = {
    "machines.MakerspaceMachineTypePolicy": frozenset({"session_max_minutes"}),
}
PROJECTED_LABELS = frozenset(FIELD_NAMES)


def authority_entries(authority, disposition):
    def same(label, names, chosen, reason):
        return tuple(((label, name), authority(chosen, reason)) for name in names.split())

    keep = disposition.PRESERVE
    return (
        *same("machines.MachineSession", "source started_at ended_at stop_reason flagged duration_minutes billable "
              "quote_snapshot quote_digest created_at", keep,
              "A session's times, source, frozen rate and flag are the machine's own usage history."),
        *same("machines.MachineSession", "device_job_ref", disposition.RESET,
              "A printer run identity belongs to the source deployment's device fleet."),
        *same("machines.MachineSessionAmendment", "kind minutes reason created_at", keep,
              "A staff correction, assignment or confirmation is append-only history."),
        *same("machines.MakerspaceMachineTypePolicy", "session_max_minutes", keep,
              "The per-type session length is the space's own configuration."),
    )
