"""Account-merge dispositions for release 0.12.0 lane L3a (induction, supervised sessions, incidents)."""

from .merge_registry_types import KEEP_ON_SHELL as K, REPOINT as R

_ATTRIBUTION = "Mutable ownership or attribution; moves to the survivor."
_HISTORY = "Supervision history; actor_ids_for follows the alias."

ROWS = (
    (R, "machines.EventInductionLink", "created_by", _ATTRIBUTION),
    (R, "machines.GuestCertificationGrant", "user granted_by revoked_by", _ATTRIBUTION),
    (R, "machines.MachineAccessGrant", "member granted_by revoked_by", _ATTRIBUTION),
    (K, "machines.SupervisedSession", "instructor closed_by", _HISTORY),
    (K, "machines.SupervisedParticipant", "user added_by", "One row per session and person; history stays on the shell."),
    (K, "machines.SupervisedUse", "user instructor", _HISTORY),
    (R, "maintenance.Incident", "reporter involved_user sponsor_user triaged_by", _ATTRIBUTION),
    (R, "maintenance.IncidentAction", "assignee done_by created_by", _ATTRIBUTION),
)
