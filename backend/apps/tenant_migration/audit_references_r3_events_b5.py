"""Audit metadata IDs written by parity lane E-B5 (series allowlists, pay window, check-in list upkeep)."""

from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP


def _remap(model, *edges):
    return {edge: AuditReference(R, model) for edge in edges}


_LISTS = tuple(f"event.checkin_list.{action}" for action in ("restored", "scan_undone", "override"))

EDGES = {
    **_remap("events.EventSeries", ("event.deleted", "series_id"), ("event.series_invite.created", "series_id"),
             ("event.series_invite.revoked", "series_id")),
    **_remap("events.EventInvite", ("event.series_invite.revoked", "invite_id")),
    **_remap("events.Event", ("event.checkin_list.reordered", "event_id"),
             *((action, "event_id") for action in _LISTS)),
    **_remap("events.EventCheckInList", *((action, "list_id") for action in _LISTS)),
    **_remap("events.EventRegistration", ("event.registration.pay_window_opened", "registration_id"),
             ("event.registration.pay_window_expired", "registration_id"),
             ("event.checkin_list.scan_undone", "registration_id"), ("event.checkin_list.override", "registration_id")),
}
