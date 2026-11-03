"""Release-2 lane L23 (metered machine sessions): literal export classification.

Sessions and their amendments are the space's own machine-usage record and export with
the space: who used which machine when, the source, the stop reason and flag, the frozen
L15 rate (component names, prices and rule ids only), the job a device session ran, and
staff corrections, assignments and confirmations (with the staff reason). Members and
staff are relational account references. The per-type maximum length is configuration.
"""

from .types import TenantPredicate as P

SESSION_FIELDS = ("id makerspace machine machine_type member source started_at ended_at stop_reason flagged "
                  "duration_minutes billable quote_snapshot quote_digest service_request device_job_ref started_by "
                  "stopped_by created_at")
AMENDMENT_FIELDS = "id makerspace session kind minutes member reason actor created_at"
EXPORTED_FIELDS = {
    "machines.MachineSession": SESSION_FIELDS,
    "machines.MachineSessionAmendment": AMENDMENT_FIELDS,
}
FIELD_ADDITIONS = {
    "machines.MakerspaceMachineTypePolicy": "session_max_minutes",
}
OMITTED_MODELS = {}
# The digest of the frozen rate the member was shown at Start; it authenticates nothing.
NON_CREDENTIAL = {
    ("machines.MachineSession", "quote_digest"): "Integrity digest of the session's frozen rate, not a secret.",
}
DATASET_SPECS = {
    "machines.MachineSession": ("machines/sessions.csv", P(("makerspace",))),
    "machines.MachineSessionAmendment": ("machines/session_amendments.csv", P(("makerspace",))),
}
RELATIONAL_USER_FIELDS = frozenset({
    ("machines.MachineSession", "member"),
    ("machines.MachineSession", "started_by"),
    ("machines.MachineSession", "stopped_by"),
    ("machines.MachineSessionAmendment", "member"),
    ("machines.MachineSessionAmendment", "actor"),
})
# A frozen quote: component names, prices and rule ids only.
JSON_FIELDS = frozenset({("machines.MachineSession", "quote_snapshot")})


def extend(fields):
    fields.update(EXPORTED_FIELDS)
    for label, extra in FIELD_ADDITIONS.items():
        fields[label] += " " + extra
    return fields
