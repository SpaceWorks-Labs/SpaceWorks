"""Presentation entries: release-2 lane L23 (metered machine sessions).

``permitted`` lists only reviewed non-personal leaf paths (ids, minutes, amounts). No
`reason` leaf is presented (the free-text guard forbids it): stop and skip reasons and a
staff correction reason stay in the raw audit row for auditors."""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

_SESSION = ("session_id", "machine_id")

ENTRIES = (
    P("machine_session.started", gettext_noop("Machine session started"),
      (*_SESSION, "source", "billable", "member_id", "service_request_id")),
    P("machine_session.stopped", gettext_noop("Machine session stopped"), (*_SESSION, "minutes")),
    P("machine_session.auto_stopped", gettext_noop("Machine session stopped automatically"), (*_SESSION, "minutes")),
    P("machine_session.amended", gettext_noop("Machine session time corrected"), (*_SESSION, "minutes_before", "minutes_after")),
    P("machine_session.assigned", gettext_noop("Machine session assigned to a member"), (*_SESSION, "member_id")),
    P("machine_session.confirmed", gettext_noop("Machine session confirmed"), (*_SESSION, "minutes")),
    P("machine_session.charge_raised", gettext_noop("Machine session charge raised"),
      (*_SESSION, "payment_id", "amount", "currency", "minutes")),
    P("machine_session.device_skipped", gettext_noop("Device session not opened"), ("machine_id", "service_request_id")),
    P("machine_type.session_settings_updated", gettext_noop("Machine type session settings changed"),
      ("machine_type_id", "session_max_minutes")),
)
