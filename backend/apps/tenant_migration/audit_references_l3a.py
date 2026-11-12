"""Audit metadata IDs written by release 0.12.0 lane L3a (induction, supervised sessions, incidents).

Machines, types, events, certifications, supervised sessions and incidents travel with the
space, so their ids remap; a person's id stays source provenance, like every other account
id in audit metadata.
"""

from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP
S = AuditReferenceDisposition.SOURCE_LOCAL_SNAPSHOT

_INDUCTION = ("certification.induction_linked", "certification.induction_unlinked")
_GUEST = ("certification.guest_granted", "certification.guest_revoked")
_SUPERVISED = ("machine_session.supervised_opened", "machine_session.supervised_closed",
               "machine_session.supervisee_added", "machine_session.supervisee_removed",
               "machine_session.supervised_use_started", "machine_session.supervised_use_ended")
_INCIDENT = ("incident.reported", "incident.status_changed", "incident.updated", "incident.action_added",
             "incident.action_done")


def _remap(model, *edges):
    return {edge: AuditReference(R, model) for edge in edges}


def _snapshot(model, *edges):
    return {edge: AuditReference(S, model) for edge in edges}


_ACCESS = ("machine_access.granted", "machine_access.renewed", "machine_access.revoked")
EDGES = {
    **_remap("machines.Machine", *((a, "machine_id") for a in _ACCESS)),
    **_remap("machines.MachineType", *((a, "machine_type_id") for a in _ACCESS)),
    **_snapshot("accounts.User", *((a, "member_id") for a in _ACCESS)),
    **_remap("events.Event", *((a, "event_id") for a in _INDUCTION), ("certification.guest_granted", "source_event_id"),
             ("certification.granted", "source_event_id"), ("certification.renewed", "source_event_id"),
             ("machine_session.supervised_opened", "event_id"), ("incident.reported", "event_id")),
    **_remap("machines.CertificationType", *((a, "certification_type_id") for a in (*_INDUCTION, *_GUEST))),
    **_remap("machines.MachineType", *((a, "machine_type_id") for a in (*_INDUCTION, *_GUEST, *_SUPERVISED))),
    **_remap("machines.Machine", *((a, "machine_id") for a in _SUPERVISED), ("incident.reported", "machine_id")),
    **_remap("machines.SupervisedSession", *((a, "supervised_session_id") for a in _SUPERVISED)),
    **_remap("machines.SupervisedUse", ("machine_session.supervised_use_started", "use_id"),
             ("machine_session.supervised_use_ended", "use_id")),
    **_remap("maintenance.Incident", *((a, "incident_id") for a in _INCIDENT)),
    **_remap("maintenance.IncidentAction", ("incident.action_added", "action_id"), ("incident.action_done", "action_id")),
    **_snapshot("accounts.User", ("certification.guest_granted", "user_id"), ("certification.guest_revoked", "user_id"),
                ("machine_session.supervisee_added", "user_id"), ("machine_session.supervisee_removed", "user_id"),
                ("machine_session.supervised_use_started", "user_id"),
                ("machine_session.supervised_use_ended", "user_id"),
                ("incident.reported", "sponsor_user_id"), ("incident.action_added", "assignee_id")),
}
