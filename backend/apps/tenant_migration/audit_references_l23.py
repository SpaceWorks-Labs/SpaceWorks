"""Audit metadata IDs written by release-2 lane L23 (metered machine sessions).

Sessions, machines, types, jobs and charges travel with the space, so their ids remap; a
member id stays source provenance, like every other account id in audit metadata.
"""

from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP
S = AuditReferenceDisposition.SOURCE_LOCAL_SNAPSHOT

_ACTIONS = ("started", "stopped", "auto_stopped", "amended", "assigned", "confirmed", "charge_raised")


def _remap(model, *edges):
    return {edge: AuditReference(R, model) for edge in edges}


EDGES = {
    **_remap("machines.MachineSession", *((f"machine_session.{action}", "session_id") for action in _ACTIONS)),
    **_remap("machines.Machine", *((f"machine_session.{action}", "machine_id") for action in
                                   (*_ACTIONS, "device_skipped"))),
    **_remap("machines.MachineServiceRequest", ("machine_session.started", "service_request_id"),
             ("machine_session.device_skipped", "service_request_id")),
    **_remap("payments.Payment", ("machine_session.charge_raised", "payment_id")),
    **_remap("machines.MachineType", ("machine_type.session_settings_updated", "machine_type_id")),
    ("machine_session.started", "member_id"): AuditReference(S, "accounts.User"),
    ("machine_session.assigned", "member_id"): AuditReference(S, "accounts.User"),
}
