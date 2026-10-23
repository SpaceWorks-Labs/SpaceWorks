"""Conservative authorization-input drift guard for portable tenant imports.

The mechanical part scans attribute access, ORM lookup names, ``getattr`` field names,
and ``values_list``/``only`` field strings in the ``accounts/rbac*.py`` implementation
modules, the locked makerspace role-authority/assignment modules and ``machines/access.py``.
It then intersects those names with a reviewed set of
exported authorization models. The explicit declarations also cover
authority/disclosure inputs identified by the migration threat model.

This cannot see authorization assembled dynamically, raw SQL, fields consulted only in
other modules, semantic changes to a declared field, or a new authorization module.  It
also deliberately over-approximates where the AST cannot infer an expression's model.
Code review remains necessary; this guard makes the mechanically visible subset fail
closed instead of claiming whole-program authorization analysis.
"""

import ast
from pathlib import Path

import apps as project_apps
from django.apps import apps

from apps.data_export.models import EXPORTED_MODEL_FIELDS

from .target_projection import TARGET_FIELD_PROJECTION
from .tenant_dump_authority_loans import LOAN_AUTHORITY_FIELDS
from .authority_wp4 import AUTHORITY_FIELDS as WP4_AUTHORITY_FIELDS
from .authority_resource_fields import RESOURCE_AUTHORITY_FIELDS, RESOURCE_SCANNED_MODEL_LABELS


class AuthorityRegistryError(AssertionError):
    pass


APPS_DIR = Path(project_apps.__file__).resolve().parent
AUTHORIZATION_SOURCES = (
    APPS_DIR / "accounts" / "surface_policy.py",
    APPS_DIR / "accounts" / "credential_locks.py",
    APPS_DIR / "accounts" / "session_issuance.py",
    APPS_DIR / "accounts" / "services_staff_authority.py",
    APPS_DIR / "organizations" / "governance.py",
    APPS_DIR / "organizations" / "access.py",
    APPS_DIR / "events" / "organizer_authority.py",
    APPS_DIR / "events" / "series_authority.py",
    APPS_DIR / "bookings" / "booking_authority_page.py",
    APPS_DIR / "integrations" / "recipients_addressed.py",
    APPS_DIR / "integrations" / "recipients_owners.py",
    APPS_DIR / "integrations" / "notification_sources.py",
    APPS_DIR / "integrations" / "dispatch_policy.py",
    APPS_DIR / "integrations" / "messaging" / "eligibility.py",
    APPS_DIR / "integrations" / "messaging" / "ties.py",
    APPS_DIR / "integrations" / "messaging" / "consent.py",
    APPS_DIR / "accounts" / "staff_account_policy.py",
    APPS_DIR / "accounts" / "staff_account_services.py",
    APPS_DIR / "accounts" / "staff_account_lifecycle.py",
    APPS_DIR / "accounts" / "services_staff_invitations.py",
    APPS_DIR / "accounts" / "staff_invitation_acceptance.py",
    APPS_DIR / "accounts" / "account_restore.py",
    APPS_DIR / "accounts" / "account_restore_email.py",
    APPS_DIR / "accounts" / "account_restore_phone.py",
    APPS_DIR / "accounts" / "account_restore_social.py",
    APPS_DIR / "accounts" / "account_deletion.py",
    APPS_DIR / "accounts" / "account_deletion_blockers.py",
    APPS_DIR / "accounts" / "account_obligations.py",
    APPS_DIR / "bookings" / "broadcasts.py",
    APPS_DIR / "bookings" / "communication_recipients.py",
    APPS_DIR / "bookings" / "reminder_delivery.py",
    APPS_DIR / "accounts" / "reauthentication.py",
    APPS_DIR / "accounts" / "reauthentication_intents.py",
    APPS_DIR / "accounts" / "reauthentication_factors.py",
    APPS_DIR / "accounts" / "reauthentication_providers.py",
    APPS_DIR / "accounts" / "reauthentication_phone.py",
    APPS_DIR / "accounts" / "reauthentication_methods.py",
    APPS_DIR / "accounts" / "reauthentication_control.py",
    APPS_DIR / "apiclients" / "read_contract.py",
    APPS_DIR / "apiclients" / "scope_registry_reads.py",
    APPS_DIR / "events" / "views_integration.py",
    APPS_DIR / "organizations" / "services_governance.py",
    APPS_DIR / "organizations" / "services_self_service.py",
    APPS_DIR / "events" / "broadcasts.py",
    APPS_DIR / "events" / "report_subject.py",
    APPS_DIR / "integrations" / "broadcasts_delivery.py",
    APPS_DIR / "operations" / "report_subjects.py",
    APPS_DIR / "operations" / "views_platform_tenant_reports.py",
    APPS_DIR / "events" / "event_authority.py",
    APPS_DIR / "events" / "event_authority_page.py",
    APPS_DIR / "events" / "staff_grant_locks.py",
    APPS_DIR / "events" / "organization_audience.py",
    APPS_DIR / "organizations" / "audience.py",
    APPS_DIR / "makerspaces" / "resource_grant_sources.py",
    APPS_DIR / "makerspaces" / "resource_grant_locks.py",
    APPS_DIR / "makerspaces" / "resource_grants_services.py",
    APPS_DIR / "accounts" / "rbac.py",
    APPS_DIR / "accounts" / "rbac_catalogue.py",
    APPS_DIR / "accounts" / "rbac_notifications.py",
    APPS_DIR / "accounts" / "rbac_bookings.py",
    APPS_DIR / "accounts" / "rbac_actions.py",
    APPS_DIR / "accounts" / "rbac_roles.py",
    APPS_DIR / "accounts" / "membership_context.py",
    APPS_DIR / "makerspaces" / "role_membership_writes.py",
    APPS_DIR / "makerspaces" / "staff_authority.py",
    APPS_DIR / "machines" / "role_scope_resolution.py",
    APPS_DIR / "machines" / "role_scope_grants.py",
    APPS_DIR / "machines" / "member_scope_services.py",
    APPS_DIR / "admin_api" / "recipient_rule_identities.py",
    APPS_DIR / "admin_api" / "recipient_rule_common.py",
    APPS_DIR / "makerspaces" / "role_catalog.py",
    APPS_DIR / "accounts" / "rbac_memberships.py",
    APPS_DIR / "accounts" / "rbac_borrowers.py",
    APPS_DIR / "accounts" / "rbac_organizations.py",
    APPS_DIR / "accounts" / "rbac_superadmin.py",
    APPS_DIR / "makerspaces" / "role_authority.py",
    APPS_DIR / "makerspaces" / "role_assignments.py",
    APPS_DIR / "accounts" / "mfa_policy.py",
    APPS_DIR / "machines" / "access.py",
    APPS_DIR / "bookings" / "booking_authority.py",
)
from .authority_reconciliation import SOURCE_PATHS, AUTHORITY_FIELDS as RECONCILIATION_FIELDS
AUTHORIZATION_SOURCES += tuple(APPS_DIR / path for path in SOURCE_PATHS)
SCANNED_MODEL_LABELS = frozenset({
    "makerspaces.MembershipAdditionalRole",
    "machines.MembershipMachineTypeScope",
    "makerspaces.Makerspace",
    "makerspaces.MakerspaceMembership",
    "makerspaces.MakerspaceRole",
    "machines.Machine",
    "machines.MachineOperator",
    "machines.MachineType",
}) | RESOURCE_SCANNED_MODEL_LABELS


EXPLICIT_AUTHORITY_FIELDS = {
    **RECONCILIATION_FIELDS,
    ("makerspaces.MakerspaceMembership", "renewal_cancelled_at"): (
        "Historical cancellation stops source renewal; target automation resets independently."
    ),
    ("makerspaces.MembershipAdditionalRole", "membership"): "Dropped membership role authority.",
    ("makerspaces.MembershipAdditionalRole", "role"): "Dropped additional role authority.",
    ("makerspaces.MembershipAdditionalRole", "assigned_by"): "Dropped role assignment provenance.",
    ("makerspaces.MembershipAdditionalRole", "assigned_at"): "Dropped role assignment time.",
    ("machines.MembershipMachineTypeScope", "membership"): "Dropped membership machine authority.",
    ("machines.MembershipMachineTypeScope", "machine_type"): "Dropped membership type authority.",
    **WP4_AUTHORITY_FIELDS,
    **RESOURCE_AUTHORITY_FIELDS,
    **LOAN_AUTHORITY_FIELDS,
    ("makerspaces.Makerspace", "location"): "AST over-approximation from broadcast rendering; portable location grants no authority.",
    ("machines.Machine", "location"): "AST over-approximation from broadcast rendering; portable location grants no authority.",
    ("machines.MakerspaceMachineTypePolicy", "makerspace"): "Tenant boundary for reminder policy; preserved data does not grant staff authority.",
    ("machines.MakerspaceMachineTypePolicy", "machine_type"): "Remapped type boundary for reminder policy, never an authorization scope grant.",
    ("machines.MakerspaceMachineTypePolicy", "cert_reminder_days"): "Portable certification disclosure timing; target-owned feature and channel gates still apply.",
    ("machines.MakerspaceMachineTypePolicy", "reminder_lead_days"): "Portable maintenance disclosure timing; recipients require live target machine authority.",
    ("machines.MakerspaceMachineTypePolicy", "grace_days"): "Portable overdue disclosure timing; grants no access or automatic lockout bypass.",
    ("maintenance.MaintenanceSchedule", "anchor"): "Portable recurrence preference; completion still requires target actor authority.",
    ("makerspaces.Makerspace", "lifecycle_state"): (
        "Scheduled-work visibility is target-owned; Lane D resets lifecycle state."
    ),
    ("makerspaces.MakerspaceMembership", "makerspace"): "Tenant boundary for membership authority.",
    ("makerspaces.MakerspaceMembership", "user"): "Identity receiving the membership grant.",
    ("makerspaces.MakerspaceMembership", "role"): "Legacy fallback authority is reduced to Member/CUSTOM.",
    ("makerspaces.MakerspaceMembership", "assigned_role"): "Remapped only to the target Member role.",
    ("makerspaces.MakerspaceMembership", "status"): "Preserved only as inert pending-membership evidence until target proof.",
    ("makerspaces.MakerspaceRole", "makerspace"): "Target-seeded role ownership boundary.",
    ("makerspaces.MakerspaceRole", "slug"): "Identifies the target-seeded Member role.",
    ("makerspaces.MakerspaceRole", "granted_actions"): "Archived role rows are dropped; target grants are kept.",
    ("makerspaces.MakerspaceRole", "legacy_role"): "Archived role rows are dropped; target identity is kept.",
    ("makerspaces.MakerspaceRole", "is_default"): "Required when resolving the protected target Member role.",
    ("makerspaces.MakerspaceRole", "is_protected"): "Required when resolving the protected target Member role.",
    ("machines.Machine", "makerspace"): "Machine authorization is bounded by this tenant relation.",
    ("machines.Machine", "machine_type"): "Type-level authority follows this remapped relation.",
    ("machines.Machine", "status"): "AST over-approximation: operational state remains archive evidence.",
    ("machines.Machine", "is_active"): "AST over-approximation: lifecycle state remains archive evidence.",
    ("machines.MachineType", "makerspace"): "Distinguishes target globals from tenant custom types.",
    ("machines.MachineType", "is_builtin"): "Discriminator for global resolution versus projected custom insertion.",
    ("machines.MachineType", "slug"): "Resolves target built-in types; custom type identifiers stay tenant-scoped.",
    ("makerspaces.Makerspace", "slug"): "Portable routing identifier is resolved for the new tenant; it grants no actor authority.",
    ("makerspaces.Makerspace", "public_inventory_enabled"): "Portable catalogue publication choice remains bounded by target modules, loan visibility and servability.",
    ("machines.MachineOperator", "machine"): "Owner decision 22 preserves this live authority relation.",
    ("machines.MachineOperator", "user"): "Owner decision 22 preserves the identity receiving authority.",
    ("machines.MachineOperator", "access_level"): "Owner decision 22 preserves the operate/manage/full grant.",
    ("machines.MachineOperator", "assigned_by"): "Owner decision 22 preserves assignment provenance with FK closure.",
    ("machines.MachineOperator", "assigned_at"): "Owner decision 22 preserves assignment-time provenance.",
    ("makerspaces.MembershipRequest", "assigned_role"): "Remapped to target Member, never a source role.",
    ("integrations.NotificationRecipient", "makerspace"): "Dropped disclosure-rule tenant boundary.",
    ("integrations.NotificationRecipient", "feature"): "Dropped disclosure-rule discriminator.",
    ("integrations.NotificationRecipient", "event"): "Dropped disclosure-rule discriminator.",
    ("integrations.NotificationRecipient", "kind"): "Every recipient kind is dropped.",
    ("integrations.NotificationRecipient", "role"): "Dropped role-directed disclosure rule.",
    ("integrations.NotificationRecipient", "user"): "Dropped named-user disclosure rule.",
    ("integrations.NotificationDestination", "channel"): "Selects credential and delivery semantics.",
    ("integrations.NotificationDestination", "telegram_chat_id"): "Target-bot disclosure destination.",
}

DECLARED_AUTHORITY_FIELDS = {
    **{edge: policy.reason for edge, policy in TARGET_FIELD_PROJECTION.items()},
    **EXPLICIT_AUTHORITY_FIELDS,
}


from .catalog_p2_presence import FIELD_NAMES as PRESENCE_FIELDS
AUTHORIZATION_SOURCES += tuple(APPS_DIR / "presence" / name for name in (
    "policy.py", "services.py", "privacy.py", "display.py", "event_attendance.py", "notifications.py",
))
AUTHORIZATION_SOURCES += tuple(APPS_DIR / app / name for app, name in (
    ("makerspaces", "public_page_authority.py"), ("makerspaces", "public_page_services.py"),
    ("makerspaces", "public_page_access.py"), ("makerspaces", "public_page_projection.py"),
    ("makerspaces", "public_page_derived.py"), ("makerspaces", "public_page_assets.py"),
    ("makerspaces", "public_page_asset_cleanup.py"), ("makerspaces", "public_page_revisions.py"),
    ("events", "website_revisions.py"), ("events", "website_delays.py"),
    ("events", "website_revision_projection.py"), ("organizations", "public_catalog.py"),
    ("apiclients", "scope_registry_public_pages.py"),
    ("makerspaces", "origin_scope_routes_public_pages.py"),
))
from .catalog_public_pages import EXPORTED_FIELDS as PAGE_EXPORTED_FIELDS
SCANNED_MODEL_LABELS |= PAGE_EXPORTED_FIELDS.keys()
DECLARED_AUTHORITY_FIELDS.update({
    (label, field): "Authored page history is remapped with reset publication/disclosures and locked target-side owner authority."
    for label, fields in PAGE_EXPORTED_FIELDS.items() for field in fields.split() if field != "id"
})
DECLARED_AUTHORITY_FIELDS.update({
    ("events.EventPage", field): "Selected publication and editorial content travel only with reviewed page-pointer/disclosure resets."
    for field in ("draft_revision", "published_revision", "editorial_document")
})
SCANNED_MODEL_LABELS |= PRESENCE_FIELDS.keys()
DECLARED_AUTHORITY_FIELDS.update({
    (label, field): "Source-local presence/disclosure input; the entire model is DROP on tenant import."
    for label, fields in PRESENCE_FIELDS.items() for field in fields if field != "id"
})


def _normalise_field_name(name, model_fields):
    root = name.split("__", 1)[0]
    if root.endswith("_id") and root[:-3] in model_fields:
        return root[:-3]
    return root


from .authority_events_programme import FIELDS as PROGRAMME_AUTHORITY_FIELDS, SCANNED_LABELS, SOURCE_PATHS
AUTHORIZATION_SOURCES += tuple(APPS_DIR / path for path in SOURCE_PATHS)
SCANNED_MODEL_LABELS |= SCANNED_LABELS
DECLARED_AUTHORITY_FIELDS.update(PROGRAMME_AUTHORITY_FIELDS)
from .authority_reimbursements import FIELDS as REIMBURSEMENT_AUTHORITY_FIELDS, SOURCE_PATHS as _REIMBURSEMENT_SOURCES
AUTHORIZATION_SOURCES += tuple(APPS_DIR / path for path in _REIMBURSEMENT_SOURCES)
DECLARED_AUTHORITY_FIELDS.update(REIMBURSEMENT_AUTHORITY_FIELDS)


def discover_authorization_field_names(paths=AUTHORIZATION_SOURCES):
    names = set()
    for path in paths:
        tree = ast.parse(Path(path).read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, ast.keyword) and node.arg:
                names.update(node.arg.split("__"))
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "getattr" and len(node.args) > 1:
                    value = node.args[1]
                    if isinstance(value, ast.Constant) and isinstance(value.value, str):
                        names.add(value.value)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in {"values_list", "only", "defer"}:
                    for value in node.args:
                        if isinstance(value, ast.Constant) and isinstance(value.value, str):
                            names.update(value.value.split("__"))
    return frozenset(names)


def discover_exported_authority_fields(paths=AUTHORIZATION_SOURCES):
    names = discover_authorization_field_names(paths)
    discovered = set()
    for label in SCANNED_MODEL_LABELS:
        exported = set(EXPORTED_MODEL_FIELDS[label].split())
        for name in names:
            normalized = _normalise_field_name(name, exported)
            if normalized in exported and normalized not in {"id", "created_at", "updated_at"}:
                discovered.add((label, normalized))
    return frozenset(discovered)


def validate_authority_registry(
    declarations=DECLARED_AUTHORITY_FIELDS,
    *,
    paths=AUTHORIZATION_SOURCES,
    required_fields=None,
):
    required = (
        set(TARGET_FIELD_PROJECTION) | set(EXPLICIT_AUTHORITY_FIELDS)
        if required_fields is None
        else set(required_fields)
    )
    missing_required = required - set(declarations)
    if missing_required:
        raise AuthorityRegistryError(
            f"required authority declarations are missing: {sorted(missing_required)}"
        )
    discovered = discover_exported_authority_fields(paths)
    missing = discovered - set(declarations)
    if missing:
        raise AuthorityRegistryError(
            f"exported authorization inputs are undeclared: {sorted(missing)}"
        )
    for label, field_name in declarations:
        model = apps.get_model(label)
        try:
            model._meta.get_field(field_name)
        except Exception as exc:
            raise AuthorityRegistryError(
                f"declared authority field no longer exists: {label}.{field_name}"
            ) from exc
