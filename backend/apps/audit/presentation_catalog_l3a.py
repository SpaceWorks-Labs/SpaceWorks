"""Presentation entries: release 0.12.0 lane L3a (induction events, supervised sessions, incidents).

``permitted`` lists only reviewed non-personal leaf paths (ids, enum values, counts). No
description, resolution note or involved-person text is ever presented."""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

_TYPE = ("certification_type_id", "machine_type_id")

ENTRIES = (
    P("certification.induction_linked", gettext_noop("Event marked as an induction"), ("event_id", *_TYPE)),
    P("certification.guest_granted", gettext_noop("Guest certification granted"),
      (*_TYPE, "user_id", "source_event_id", "expires_at")),
    P("certification.guest_revoked", gettext_noop("Guest certification revoked"), (*_TYPE, "user_id")),
    P("incident.action_added", gettext_noop("Incident follow-up action added"),
      ("incident_id", "action_id", "assignee_id")),
    P("incident.action_done", gettext_noop("Incident follow-up action updated"), ("incident_id", "action_id", "done")),
    # Metadata withheld: these sites build `meta` with a helper (presentation_r0120_dynamic).
    P("certification.induction_unlinked", gettext_noop("Induction marking removed")),
    P("machine_session.supervised_opened", gettext_noop("Supervised session opened")),
    P("machine_session.supervised_closed", gettext_noop("Supervised session closed")),
    P("machine_session.supervisee_added", gettext_noop("Supervisee added")),
    P("machine_session.supervisee_removed", gettext_noop("Supervisee removed")),
    P("machine_session.supervised_use_started", gettext_noop("Supervised use started")),
    P("machine_session.supervised_use_ended", gettext_noop("Supervised use ended")),
    P("incident.reported", gettext_noop("Incident reported")),
    P("incident.status_changed", gettext_noop("Incident status changed")),
    P("incident.updated", gettext_noop("Incident updated")),
)
