"""Release 0.12.0 lane L3a (induction events, supervised sessions, incident register): export classification.

All eight models are the space's own accountability history and export with it: which event
inducted for which certification, who was certified as a guest and from which event, who led
a supervised session and who used the machine under it, and the incident register with its
follow-up actions. People are relational account references. The free text (a supervised
session's note, an incident's description, location, involved note and resolution) is
exported as written, like a machine-session correction reason.
"""

from .types import TenantPredicate as P

EXPORTED_FIELDS = {
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
    "maintenance.IncidentAction": ("id incident description assignee due_date done_at done_by created_by created_at"),
}
OMITTED_MODELS = {}
DATASET_SPECS = {
    "machines.EventInductionLink": ("machines/induction_links.csv", P(("makerspace",))),
    "machines.GuestCertificationGrant": ("machines/guest_certification_grants.csv", P(("makerspace",))),
    "machines.MachineAccessGrant": ("machines/machine_access_grants.csv", P(("makerspace",))),
    "machines.SupervisedSession": ("machines/supervised_sessions.csv", P(("makerspace",))),
    "machines.SupervisedParticipant": ("machines/supervised_participants.csv", P(("session__makerspace",))),
    "machines.SupervisedUse": ("machines/supervised_uses.csv", P(("session__makerspace",))),
    "maintenance.Incident": ("maintenance/incidents.csv", P(("makerspace",))),
    "maintenance.IncidentAction": ("maintenance/incident_actions.csv", P(("incident__makerspace",))),
}
RELATIONAL_USER_FIELDS = frozenset({
    ("machines.EventInductionLink", "created_by"),
    ("machines.GuestCertificationGrant", "user"),
    ("machines.GuestCertificationGrant", "granted_by"),
    ("machines.GuestCertificationGrant", "revoked_by"),
    ("machines.MachineAccessGrant", "member"),
    ("machines.MachineAccessGrant", "granted_by"),
    ("machines.MachineAccessGrant", "revoked_by"),
    ("machines.SupervisedSession", "instructor"),
    ("machines.SupervisedSession", "closed_by"),
    ("machines.SupervisedParticipant", "user"),
    ("machines.SupervisedParticipant", "added_by"),
    ("machines.SupervisedUse", "user"),
    ("machines.SupervisedUse", "instructor"),
    ("maintenance.Incident", "reporter"),
    ("maintenance.Incident", "involved_user"),
    ("maintenance.Incident", "sponsor_user"),
    ("maintenance.Incident", "triaged_by"),
    ("maintenance.IncidentAction", "assignee"),
    ("maintenance.IncidentAction", "done_by"),
    ("maintenance.IncidentAction", "created_by"),
})


def extend(fields):
    fields.update(EXPORTED_FIELDS)
    return fields
