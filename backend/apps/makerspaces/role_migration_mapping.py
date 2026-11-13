"""Pure, frozen policy shared by migration 0089 and its pre-upgrade preview.

These definitions MUST NEVER CHANGE. A later catalogue edit needs a new migration.
No live catalogue, Django model, RBAC resolver or implication expansion is used:
qualification and the never-widen assertion compare DIRECT stored grants only.
"""

from types import MappingProxyType


# (slug, display name, legacy mirror, raw grants), frozen as of migration 0089.
FROZEN_CATALOG = (
    ("space_manager", "Space Manager", "space_manager", frozenset({
        "accept_request", "assign_box", "edit_inventory", "issue_direct_loan",
        "issue_request", "manage_bookings", "manage_events", "manage_devices",
        "manage_machines", "manage_makerspace", "manage_members", "manage_member_cards",
        "manage_printing", "manage_qr", "record_payment", "reject_request",
        "return_request", "upload_evidence", "view_audit", "view_finance", "view_inventory",
    })),
    ("inventory_manager", "Inventory Manager", "inventory_manager", frozenset({
        "accept_request", "assign_box", "edit_inventory", "issue_direct_loan",
        "issue_request", "manage_qr", "reject_request", "return_request",
        "upload_evidence", "view_audit", "view_inventory",
    })),
    ("machine_manager", "Machine Manager", "machine_manager", frozenset({"manage_machines"})),
    ("event_manager", "Event Manager", "event_manager", frozenset({"manage_events"})),
    ("booking_manager", "Booking Manager", "booking_manager", frozenset({"manage_bookings"})),
    ("handover", "Handover", "handover", frozenset({
        "view_inventory", "assign_box", "issue_request", "issue_direct_loan",
        "return_request", "upload_evidence", "collect_service_request",
    })),
    ("member", "Member", None, frozenset()),
)
FROZEN_BY_SLUG = MappingProxyType({entry[0]: entry for entry in FROZEN_CATALOG})
OLD_DEFAULT_SLUGS = frozenset({"space_manager", "inventory_manager", "machine_manager", "member"})
COMBINABLE_SLUGS = tuple(entry[0] for entry in FROZEN_CATALOG[1:-1])
LEGACY_HANDOUT_ACTIONS = frozenset({
    "view_inventory", "assign_box", "issue_request", "issue_direct_loan",
    "return_request", "upload_evidence",
})


def classify_role(role, makerspace_id):
    """Classify the original row; even protected print_manager is obsolete."""
    if role is None:
        return "legacy"
    if role["makerspace_id"] != makerspace_id:
        return "foreign"
    if role["is_default"] and role["slug"] in OLD_DEFAULT_SLUGS:
        return "catalogue_default"
    return "obsolete"


def map_role(*, classification, slug=None, raw_grants=(), type_ids=(), machine_ids=(),
             all_type_ids=()):
    """Return JSON-ready role/action/scope evidence, without reading or writing data.

    ``None`` primary means leave a null-FK legacy membership untouched. Stored type
    links copy verbatim; ``all_type_ids`` for exemption enumeration is bounded to
    tenant + global. Individual machine links never become type grants.
    """
    if classification not in {"legacy", "foreign", "catalogue_default", "obsolete"}:
        raise ValueError(f"Unknown original role classification: {classification}")
    raw = frozenset(raw_grants)
    types, machines = sorted(set(type_ids)), sorted(set(machine_ids))
    tags, allowed_gains = [], set()
    old_exempt = classification not in {"legacy", "foreign"} and "manage_makerspace" in raw
    if classification == "legacy":
        return {
            "primary_slug": None, "additional_slugs": [], "to_roles": [],
            "dropped_actions": [], "gained_actions": [], "exception_tags": [],
            "machine_scope_outcome": "legacy_untouched",
            "machine_scope": {"from": "exempt", "to": {"types": [], "machines": []},
                              "exempt_enumerated": False, "dropped_machine_ids": []},
        }
    if classification == "foreign":
        chosen = ["member"]
    elif classification == "catalogue_default" and slug == "space_manager":
        chosen = [slug]
        if not FROZEN_BY_SLUG[slug][3] <= raw:
            tags.append("E1")
            allowed_gains.update(FROZEN_BY_SLUG[slug][3] - raw)
    else:
        # Every non-Space-Manager row -- an edited default included -- maps to each
        # built-in it fully covers, so a default an administrator widened keeps the
        # extra built-ins it now spans instead of collapsing to its own slug.
        chosen = [key for key in COMBINABLE_SLUGS if FROZEN_BY_SLUG[key][3] <= raw]
        # E2 is for handover-SHAPED roles only. A row that already qualifies as
        # Inventory Manager covers the legacy six through that role; adding Handover
        # there would hand every inventory manager collection authority (a widening).
        if LEGACY_HANDOUT_ACTIONS <= raw and "inventory_manager" not in chosen:
            if "handover" not in chosen:
                chosen.append("handover")
            if "collect_service_request" not in raw:
                tags.append("E2")
                allowed_gains.add("collect_service_request")
        chosen = [key for key in chosen if not any(
            key != other and FROZEN_BY_SLUG[key][3] <= FROZEN_BY_SLUG[other][3]
            for other in chosen
        )]

    copied, enumerated = [], False
    outcome = "not_applicable"
    if "space_manager" in chosen:
        outcome = "exempt_unchanged" if old_exempt else "exempt_restored"
    elif "machine_manager" in chosen:
        if old_exempt:
            copied, enumerated = sorted(set(all_type_ids)), True
            outcome = "enumerate_all_types"
        elif machines and not types:
            chosen.remove("machine_manager")
            outcome = "machine_manager_dropped: machine-only scope"
        elif types:
            copied, outcome = types, "copy_type_ids"
        else:
            outcome = "unchanged_empty"
    chosen = [key for key in FROZEN_BY_SLUG if key in chosen] or ["member"]
    new_grants = frozenset().union(*(FROZEN_BY_SLUG[key][3] for key in chosen))
    # A foreign reference already resolves to no authority. Report stored grants as
    # dropped provenance, but never infer authority from that foreign row.
    gained = new_grants - raw
    assert gained <= allowed_gains, f"Unapproved role escalation: {sorted(gained)}"
    return {
        "primary_slug": chosen[0], "additional_slugs": chosen[1:], "to_roles": chosen,
        "dropped_actions": sorted(raw - new_grants), "gained_actions": sorted(gained),
        "exception_tags": tags, "machine_scope_outcome": outcome,
        "machine_scope": {
            "from": "exempt" if old_exempt else {"types": types, "machines": machines},
            "to": {"types": copied, "machines": []}, "exempt_enumerated": enumerated,
            "dropped_machine_ids": machines if classification != "foreign" else [],
        },
    }
