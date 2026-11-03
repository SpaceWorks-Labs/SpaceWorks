"""RBAC action vocabulary and role-to-action resolution."""

import logging

from apps.makerspaces.models import MakerspaceMembership


ALL = object()  # sentinel: unrestricted (superadmin)


class Action:
    MANAGE_EVENTS = "manage_events"
    MANAGE_BOOKINGS = "manage_bookings"
    VIEW_INVENTORY = "view_inventory"
    EDIT_INVENTORY = "edit_inventory"
    ACCEPT_REQUEST = "accept_request"
    REJECT_REQUEST = "reject_request"
    ASSIGN_BOX = "assign_box"
    ISSUE_REQUEST = "issue_request"
    ISSUE_DIRECT_LOAN = "issue_direct_loan"  # create a handout with NO reviewed request
    RETURN_REQUEST = "return_request"
    UPLOAD_EVIDENCE = "upload_evidence"
    # Hand a finished machine-service job (a print, a laser cut) to its requester, and
    # nothing else about that job. Separate from MANAGE_MACHINES because collection is a
    # front-desk act while MANAGE_MACHINES is the whole machine lifecycle -- retiring a
    # printer, editing maintenance, reading usage. Requiring the latter to perform the
    # former is why a handover-only staffer previously could not hand over a print.
    COLLECT_SERVICE_REQUEST = "collect_service_request"
    MANAGE_QR = "manage_qr"
    MANAGE_PRINTING = "manage_printing"
    MANAGE_MACHINES = "manage_machines"
    # Member ID cards (phase 5). SCAN resolves a card to minimal identity; MANAGE issues,
    # reissues, revokes and prints, and implies SCAN. Deliberately not part of
    # VIEW_INVENTORY: an inventory-only role must never resolve a person from a QR.
    SCAN_MEMBER_CARDS = "scan_member_cards"
    MANAGE_MEMBER_CARDS = "manage_member_cards"
    # Enrolled devices (phase 7a): enroll, rotate, revoke and rename printers/label
    # printers. Space Manager by default; never organization-grantable, because a
    # device key is physical trust inside ONE space and must be granted there.
    MANAGE_DEVICES = "manage_devices"
    # Delegate the community roster and the core money ledger independently of settings.
    MANAGE_MEMBERS = "manage_members"
    VIEW_FINANCE = "view_finance"
    RECORD_PAYMENT = "record_payment"
    RECORD_REIMBURSEMENT_PAYOUT = "record_reimbursement_payout"
    VIEW_AUDIT = "view_audit"
    TRANSFER_STOCK = "transfer_stock"        # superadmin only
    MANAGE_STAFF = "manage_staff"            # superadmin only
    MANAGE_MAKERSPACE = "manage_makerspace"  # superadmin only
    # Release 2 L3: organisation ID programmes on the HOST space (VIEW masks holder PII),
    # and approving card designs saved by others (#128 C-28, #136). Grantable to custom
    # roles and through the organisation branch; the Space Manager holds all three
    # through MANAGE_MAKERSPACE below, so no stored role changes.
    VIEW_ID_PROGRAMMES = "view_id_programmes"
    MANAGE_ID_PROGRAMMES = "manage_id_programmes"
    APPROVE_CARD_DESIGNS = "approve_card_designs"


IMPLIED_ACTIONS = {
    # Collection is implied rather than granted, which is what makes this change carry no
    # migration and no regression: every Space Manager and Machine Manager already holds
    # MANAGE_MACHINES, so they keep collect authority without a single stored role
    # changing. Only a role that holds *neither* has to be given the narrow action.
    Action.MANAGE_MACHINES: {Action.MANAGE_PRINTING, Action.COLLECT_SERVICE_REQUEST},
    Action.MANAGE_MEMBER_CARDS: {Action.SCAN_MEMBER_CARDS},
    Action.MANAGE_MEMBERS: {Action.MANAGE_MEMBER_CARDS},
    # Release 2 L3.
    Action.MANAGE_ID_PROGRAMMES: {Action.VIEW_ID_PROGRAMMES},
    Action.MANAGE_MAKERSPACE: {Action.MANAGE_ID_PROGRAMMES, Action.APPROVE_CARD_DESIGNS},
}


def expand_implied_actions(actions) -> set:
    """Materialize the authority implied by an already-granted action set."""
    expanded = set(actions)
    pending = list(expanded)
    while pending:
        action = pending.pop()
        for implied in IMPLIED_ACTIONS.get(action, ()):
            if implied not in expanded:
                expanded.add(implied)
                pending.append(implied)
    return expanded


def actions_satisfying(requested_action) -> frozenset:
    """Return actions whose grant satisfies ``requested_action``.

    This is the reverse direction of ``expand_implied_actions`` for database
    filtering, where a JSON containment query can only inspect stored grants.
    """
    satisfying = {requested_action}
    pending = [requested_action]
    while pending:
        action = pending.pop()
        for grant, implied in IMPLIED_ACTIONS.items():
            if action in implied and grant not in satisfying:
                satisfying.add(grant)
                pending.append(grant)
    return frozenset(satisfying)


_SPACE_MANAGER_ACTIONS = {
    Action.VIEW_INVENTORY, Action.EDIT_INVENTORY, Action.ACCEPT_REQUEST,
    Action.REJECT_REQUEST, Action.ASSIGN_BOX, Action.ISSUE_REQUEST,
    Action.ISSUE_DIRECT_LOAN, Action.RETURN_REQUEST, Action.UPLOAD_EVIDENCE,
    Action.MANAGE_QR, Action.MANAGE_PRINTING, Action.VIEW_AUDIT,
    Action.MANAGE_MAKERSPACE, Action.MANAGE_MACHINES, Action.MANAGE_EVENTS,
    Action.MANAGE_BOOKINGS, Action.MANAGE_MEMBER_CARDS, Action.MANAGE_DEVICES,
    Action.MANAGE_MEMBERS, Action.VIEW_FINANCE, Action.RECORD_PAYMENT,
    Action.RECORD_REIMBURSEMENT_PAYOUT,
}
_PRINT_MANAGER_ACTIONS = {
    Action.MANAGE_PRINTING,
}
# Machine Manager: makerspace-wide machine authority. MANAGE_MACHINES alone unlocks the
# full machine lifecycle plus maintenance/warranty/usage/docs, which already gate on
# machine access -- so no extra action is required (Part I).
_MACHINE_MANAGER_ACTIONS = {
    Action.MANAGE_MACHINES,
}
_INVENTORY_MANAGER_ACTIONS = {
    Action.VIEW_INVENTORY, Action.EDIT_INVENTORY, Action.ACCEPT_REQUEST,
    Action.REJECT_REQUEST, Action.ASSIGN_BOX, Action.ISSUE_REQUEST,
    Action.ISSUE_DIRECT_LOAN, Action.RETURN_REQUEST, Action.UPLOAD_EVIDENCE,
    Action.MANAGE_QR, Action.VIEW_AUDIT,
}
# Authority for non-superadmins is keyed on the PER-MAKERSPACE membership role,
# NOT the global User.role (review fix #3). A user who is globally `space_manager` but only
# an inventory_manager member of makerspace B gets only inventory_manager actions in B.
_MEMBERSHIP_ROLE_ACTIONS = {
    MakerspaceMembership.Role.SPACE_MANAGER: _SPACE_MANAGER_ACTIONS,
    MakerspaceMembership.Role.INVENTORY_MANAGER: _INVENTORY_MANAGER_ACTIONS,
    # Retained vocabulary for historical displays/migration tests. Null-primary
    # memberships no longer grant authority after account separation.
    "print_manager": _PRINT_MANAGER_ACTIONS,
    MakerspaceMembership.Role.MACHINE_MANAGER: _MACHINE_MANAGER_ACTIONS,
}


ALL_ACTIONS = frozenset(
    value
    for name, value in vars(Action).items()
    if name.isupper() and isinstance(value, str)
)
ROLE_FORBIDDEN_ACTIONS = frozenset({
    Action.TRANSFER_STOCK,
    Action.MANAGE_STAFF,
})
ROLE_GRANTABLE_ACTIONS = frozenset(ALL_ACTIONS - ROLE_FORBIDDEN_ACTIONS)
ORGANIZATION_GRANTABLE_ACTIONS = frozenset(
    ROLE_GRANTABLE_ACTIONS - {Action.MANAGE_MACHINES, Action.MANAGE_DEVICES}
)
ROLE_SUPERADMIN_ASSIGNABLE_ACTIONS = frozenset({Action.MANAGE_MAKERSPACE})
# What counts as handover-only work: taking an accepted request or a finished machine job
# to the counter, handing it over, taking it back, and photographing both ends of that.
#
# This is a description, not a grant or ceiling. Handover is a built-in role;
# its grants live in role_catalog. This set only tells `is_handout_only` how
# narrow to render the console, including staff who also collect cash receipts.
# Adding an action here grants nothing to anyone.
HANDOUT_ACTIONS = frozenset({
    Action.VIEW_INVENTORY, Action.ASSIGN_BOX, Action.ISSUE_REQUEST,
    Action.ISSUE_DIRECT_LOAN, Action.RETURN_REQUEST, Action.UPLOAD_EVIDENCE,
    Action.COLLECT_SERVICE_REQUEST,
    Action.RECORD_PAYMENT,  # cash receipts are counter work, not full finance visibility
})
_HANDOUT_MUTATIONS = frozenset(HANDOUT_ACTIONS - {Action.VIEW_INVENTORY})


def actions_for_membership(membership) -> set:
    """Resolve role actions for a membership, failing closed on invalid role data."""
    if membership is None or getattr(membership, "status", "active") != "active":
        return set()
    from .rbac_roles import stored_actions_for_membership

    return expand_implied_actions(stored_actions_for_membership(membership))


def actions_for_organization_membership(membership) -> set:
    """Resolve one organization grant with the same fail-closed action rules."""
    if (
        membership is None
        or getattr(membership, "status", "active") != "active"
        or not getattr(getattr(membership, "organization", None), "is_active", False)
    ):
        return set()
    value = membership.granted_actions
    if not isinstance(value, list):
        logging.getLogger("apps.accounts.rbac").warning(
            "Ignoring malformed granted actions on an organization membership."
        )
        return set()
    return expand_implied_actions({
        action
        for action in value
        if isinstance(action, str)
        and action in ORGANIZATION_GRANTABLE_ACTIONS
    })


def _action_scope_filters(action):
    """Build assigned-role and legacy-role filters for an action scope query."""
    satisfying = actions_satisfying(action)
    from .rbac_roles import direct_role_filter

    assigned_filter = direct_role_filter(satisfying)
    # Null-primary rows have no validated account/role context after the split.
    return assigned_filter, []
