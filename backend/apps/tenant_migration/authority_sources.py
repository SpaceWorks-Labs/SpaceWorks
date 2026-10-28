"""The source files the authority drift guard scans (split from `authority_guards.py`).

``AUTHORIZATION_SOURCES`` is the whole-file pin list: any module that reads an exported
authorization input must be named here, or ``authority_guards`` goes silently blind to it
rather than failing. When code moves out of a listed file, list its new home too.
Re-exported from ``authority_guards``; import it from there.
"""
from pathlib import Path

import apps as project_apps

from .authority_events_programme import SOURCE_PATHS as _PROGRAMME_SOURCES
from .authority_reconciliation import SOURCE_PATHS as _RECONCILIATION_SOURCES
from .authority_reimbursements import SOURCE_PATHS as _REIMBURSEMENT_SOURCES

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
AUTHORIZATION_SOURCES += tuple(APPS_DIR / path for path in _RECONCILIATION_SOURCES)
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
AUTHORIZATION_SOURCES += tuple(APPS_DIR / path for path in _PROGRAMME_SOURCES)
AUTHORIZATION_SOURCES += tuple(APPS_DIR / path for path in _REIMBURSEMENT_SOURCES)
