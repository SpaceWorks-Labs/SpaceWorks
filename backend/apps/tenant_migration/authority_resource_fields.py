"""Authority-discovery declarations for resource (event/booking) authority sources.

Split from `authority_guards.py` to keep it under the size ceiling. The AST scan in
`authority_guards` over-approximates: any attribute name read anywhere in an
authorization source counts as a candidate input for every scanned model that exports
a field of that name. Each entry below says whether the field really selects authority
or is a harmless over-approximation (display, scheduling or provenance data).
"""

_DISPLAY = "AST over-approximation: display or notification content, never an authority selector."
_PROVENANCE = "AST over-approximation: creator provenance is evidence, never a grant of authority."
_SCHEDULE = "AST over-approximation: scheduling/calendar data gates timing, never actor authority."


def _fields(label, names, reason):
    return {(label, name): reason for name in names.split()}


RESOURCE_AUTHORITY_FIELDS = {
    **_fields("machines.Machine", "is_public", "Portable publication choice remains bounded by target visibility and servability."),
    **_fields("events.Event", "is_public", "Portable event publication choice, never a staff authority grant."),
    **_fields("events.EventSeries", "is_public", "Portable series publication choice, never a staff authority grant."),
    **_fields("bookings.BookableSpace", "is_public", "Portable resource publication choice, never a staff authority grant."),
    **_fields("events.EventSeries", "revision", _PROVENANCE),
    **_fields("makerspaces.Makerspace", "presence_preset_minutes", _SCHEDULE),
    **_fields("machines.Machine", "name image_key", _DISPLAY),
    **_fields("machines.Machine", "created_by", _PROVENANCE),
    **_fields("machines.MachineType", "name", _DISPLAY),
    **_fields("makerspaces.Makerspace", "name logo_key timezone branding_config cover_image_key map_url theme_config", _DISPLAY),
    ("makerspaces.Makerspace", "public_site_enabled"): (
        "Portable site visibility remains bounded by target servability, modules and reset page publication."
    ),
    **_fields("makerspaces.Makerspace", "created_by", _PROVENANCE),
    ("makerspaces.Makerspace", "booking_requester_notifications_enabled"): (
        "Portable tenant notification preference; delivery still requires live target recipients."
    ),
    ("makerspaces.MakerspaceMembership", "revoked_at"): (
        "Revocation evidence; imported memberships are reduced to Member and target status rules apply."
    ),
    ("makerspaces.MakerspaceMembership", "revoked_by"): _PROVENANCE,
    ("makerspaces.MakerspaceMembership", "revocation_reason"): (
        "Revocation explanation is preserved history, never a grant or target credential."
    ),
    ("makerspaces.MakerspaceRole", "name"): "Archived role rows are dropped; target role names are kept.",
    # Event and booking resources: their tenant/series/type relations bound resource
    # authority; staff grants themselves are never portable and are reissued on the target.
    ("events.Event", "makerspace"): "Tenant boundary for event authority; remapped to the target.",
    ("events.Event", "series"): "Series grants reach occurrences through this remapped relation.",
    ("events.Event", "series_override_fields"): (
        "Selects inherited public artwork/content, never actor authority; target event and website gates still apply."
    ),
    ("events.Event", "public_token"): "Source event tokens reset to fresh target-local identifiers.",
    ("events.Event", "status"): "Lifecycle state gates actions; target authority still decides who acts.",
    ("events.Event", "registration_audience"): "Who may register; never staff authority.",
    **_fields("events.Event", "title description location category tags image_key", _DISPLAY),
    **_fields("events.Event", "starts_at ends_at calendar_sequence", _SCHEDULE),
    **_fields("events.Event", "created_by", _PROVENANCE),
    ("events.EventSeries", "makerspace"): "Tenant boundary for series authority; remapped to the target.",
    ("events.EventSeries", "public_token"): "Source series tokens reset to fresh target-local identifiers.",
    ("events.EventSeries", "status"): "Lifecycle state gates actions; target authority still decides who acts.",
    ("events.EventSeries", "registration_audience"): "Who may register; never staff authority.",
    **_fields("events.EventSeries", "title description location image_key", _DISPLAY),
    **_fields("events.EventSeries", "calendar_sequence duration_minutes", _SCHEDULE),
    **_fields("events.EventSeries", "created_by", _PROVENANCE),
    ("bookings.BookableSpace", "makerspace"): "Tenant boundary for booking authority; remapped to the target.",
    ("bookings.BookableSpace", "public_token"): "Source resource tokens reset to fresh target-local identifiers.",
    ("bookings.BookableSpace", "machine_type"): "Remapped type relation; never a staff authority scope.",
    ("bookings.BookableSpace", "is_active"): "Lifecycle state gates bookings; target authority decides who acts.",
    ("bookings.BookableSpace", "requester_notifications_enabled"): (
        "Portable notification preference; delivery still requires live target recipients."
    ),
    **_fields("bookings.BookableSpace", "name description kind location image_key", _DISPLAY),
    **_fields("bookings.BookableSpace", "created_by", _PROVENANCE),
}

RESOURCE_SCANNED_MODEL_LABELS = frozenset({"events.Event", "events.EventSeries", "bookings.BookableSpace"})
