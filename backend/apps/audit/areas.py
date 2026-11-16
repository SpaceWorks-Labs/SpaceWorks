"""Which AREA of a space each audit action belongs to (owner decision 219(e)).

An action's area comes from its namespace -- the text before the first dot -- because
every catalogued action and every dynamic emitter prefix is namespaced by its domain.
A few exact actions override their namespace. An action whose namespace is not listed
here belongs to ``platform``, which only the Space Manager and superadmin read, so a
new namespace fails CLOSED until someone places it (``tests/test_audit_area_scope.py``
holds every catalogue action and every dynamic prefix to an explicit entry).

``repairs`` is not unlocked by an action: its rows are split by subject (machines,
inventory, rooms) in ``area_scope``.
"""

from apps.accounts import rbac

A = rbac.Action
LENDING, HANDOVER, MACHINES, EVENTS, BOOKINGS = "lending", "handover", "machines", "events", "bookings"
SHOP, REPAIRS, FINANCE, PEOPLE, PLATFORM = "shop", "repairs", "finance", "people", "platform"
DONATIONS = "donations"  # decision 252: Fundraising (manage_donations) reads donation and sponsor rows
AREAS = (LENDING, HANDOVER, MACHINES, EVENTS, BOOKINGS, SHOP, REPAIRS, FINANCE, DONATIONS, PEOPLE, PLATFORM)

# Holding ANY of these in a space opens the area's rows there to an audit reader
# (``area_scope.audit_reader_spaces``: VIEW_AUDIT or a READER_ACTIONS grant).
AREA_ACTIONS = {
    LENDING: (A.EDIT_INVENTORY, A.ACCEPT_REQUEST, A.REJECT_REQUEST, A.MANAGE_QR),
    HANDOVER: (A.ASSIGN_BOX, A.ISSUE_REQUEST, A.ISSUE_DIRECT_LOAN, A.RETURN_REQUEST, A.UPLOAD_EVIDENCE),
    MACHINES: (A.MANAGE_MACHINES, A.MANAGE_PRINTING),
    EVENTS: (A.MANAGE_EVENTS,),
    BOOKINGS: (A.MANAGE_BOOKINGS,),
    SHOP: (A.MANAGE_SHOP,),
    FINANCE: (A.VIEW_FINANCE,),
    DONATIONS: (A.MANAGE_DONATIONS,),
    PEOPLE: (A.MANAGE_MEMBERS,),
    PLATFORM: (A.MANAGE_MAKERSPACE,),
}
# Repairs: the manager of each subject area, or a Technician whose coverage names it.
REPAIR_SUBJECT_ACTIONS = {"machines": A.MANAGE_MACHINES, "inventory": A.EDIT_INVENTORY,
                          "rooms": A.MANAGE_BOOKINGS}
TECHNICIAN_ACTIONS = (A.WORK_REPAIRS, A.RUN_MAINTENANCE, A.SET_SERVICE_STATE)
# #219(e-1): holding any of these admits a reader to the audit log and the audit reports
# WITHOUT `view_audit`, narrowed to their areas. Handover-desk actions alone do not: the
# counter console stays narrow (217c). Every other `view_audit` surface is unchanged.
READER_ACTIONS = tuple(sorted(
    {a for area, needed in AREA_ACTIONS.items() if area != HANDOVER for a in needed} | set(TECHNICIAN_ACTIONS)))


def _areas(area, *names):
    return {name: area for name in names}


NAMESPACE_AREAS = {
    **_areas((LENDING,), "asset", "asset_units", "category", "container", "equipment", "inventory",
             "kiosk", "loan", "problem_report", "public_problem", "public_tool", "qr", "qr_print_batch",
             "request", "stock_transfer", "stocktake"),
    # Counter work: the handover rows themselves (direct handouts, boxes, evidence, kits).
    **_areas((LENDING, HANDOVER), "admin_direct", "box", "evidence", "item", "kit"),
    # To-Buy, vendors and consumable costs are folded per parent (#97): both areas.
    **_areas((LENDING, MACHINES), "procurement", "vendor"),
    **_areas((MACHINES,), "certification", "certification_type", "consumable", "machine", "machine_access",
             "machine_consumable_pool", "machine_downtime", "machine_service", "machine_session",
             "machine_type", "machine_type_consumable", "machine_type_document", "machine_type_pricing",
             "machine_type_setup", "machine_type_template"),
    # Decision 342: a machine session or job logged for an event belongs to both areas' managers.
    **_areas((MACHINES, EVENTS), "machine_event"),
    **_areas((EVENTS,), "calendar_feed", "event", "event_badge", "event_card", "events", "mentor"),
    **_areas((BOOKINGS,), "booking"),
    **_areas((SHOP,), "shop"),
    **_areas((REPAIRS,), "dispatch", "issue", "maintenance", "repair", "service_state", "technician",
             "warranty", "work_order"),
    **_areas((FINANCE,), "billing", "charge", "finance", "ledger", "payment", "payments", "perk", "pricing"),
    # Donation, sponsorship and pledge rows: finance readers keep them, Fundraising reads them too (decision 252).
    **_areas((FINANCE, DONATIONS), "donation", "pledge", "sponsor"),
    **_areas((PEOPLE,), "account", "card", "card_design", "card_job", "card_number_scheme", "card_photo_batch",
             "card_template", "card_verification", "id_programme", "invitation_request",
             "member", "member_card", "member_unit", "staff_card", "membership", "membership_plan", "organization", "presence",
             "user", "wallet_pass"),
    **_areas((PLATFORM,), "access_token", "account_pii", "analytics", "api_client", "api_integration",
             "api_key_request", "audit", "auth", "backup", "chat_template", "cloud", "control",
             "data_export", "deployment", "devices", "email", "email_template", "encryption",
             "hosting_request", "image_adapter", "incident", "makerspace", "managed_hosting", "messaging", "native_app",
             "notification", "notification_destination", "oauth_app", "oauth_consent", "platform",
             "platform_credential_limit", "public_page", "push", "report",
             "report_schedule", "rls", "saved_view", "selfhost_move", "settings", "space_control",
             "staff", "staff_invitation", "staff_role", "station_credentials", "storage",
             "subject_export", "telegram", "tenant_migration"),
}
EXACT_AREAS = {
    # The request steps a handover desk performs; decisions stay with lending.
    **_areas((LENDING, HANDOVER), "request.issued", "request.returned", "request.partially_returned",
             "request.closed_with_issue", "asset.issued", "public_tool.checked_out", "public_tool.returned"),
    # L12 machine maintenance carries no subject metadata; it is machine lifecycle work.
    **_areas((MACHINES,), "maintenance.logged", "maintenance.schedule_created", "maintenance.schedule_updated",
             "maintenance.schedule_deactivated", "maintenance.schedule_completed",
             "maintenance.document_added", "maintenance.document_deleted"),
    # Personal calendar-feed credentials, not repair work.
    **_areas((PLATFORM,), "maintenance.feed_rotated", "maintenance.feed_revoked"),
}


def namespace(action):
    return str(action).split(".", 1)[0]


def areas_for_action(action):
    """The areas one stored action belongs to; unknown namespaces are ``platform``."""
    return EXACT_AREAS.get(action) or NAMESPACE_AREAS.get(namespace(action), (PLATFORM,))


def areas_for_actions(actions):
    """The action-opened areas (all but ``repairs``) a set of effective actions opens."""
    if A.MANAGE_MAKERSPACE in actions:
        return set(AREAS)
    return {area for area, needed in AREA_ACTIONS.items() if set(needed) & set(actions)}
