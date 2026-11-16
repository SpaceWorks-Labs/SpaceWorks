"""Decision 245(a): every release-0.12 model, field and trigger is classified for backup and tenant moves.

The whole-deployment archive is a physical database dump, so these rows ride along by construction; what
needs a guard is (1) the per-space archive and tenant dump classification, (2) platform- and credential-level
models never travelling, (3) scoped-PII fields registered for encryption, and (4) every new SQL guard
function being catalogued so a restored database keeps its immutability triggers. Not run in source preparation.
"""
import re
from pathlib import Path

import pytest

from apps.backup.managed.function_catalog import APPLICATION_FUNCTIONS
from apps.backup.slice_rows import SLICE_ROW_SPECS
from apps.backup.space_restore_plan import restorable_labels
from apps.data_export.models import EXPORTED_MODEL_FIELDS, MODELS, OMITTED_MODELS
from apps.encryption.registry import fields_for_label

# Tenant history or configuration: travels with the space and is restored by a one-space restore.
TENANT_MODELS = (
    "bookings.BookingConsumablePlanContext", "bookings.BookingLoanContext",
    "bookings.IncludedHoursUsage", "events.EventBookingDecision", "events.EventConsumablePlanContext",
    "events.EventLoanContext", "events.EventMachineBookingLink", "events.MachineEventCostApproval",
    "events.MachineEventLink", "inventory.EquipmentConsumablePlan",
    "inventory.EquipmentConsumableUseReceipt", "inventory.EquipmentKitAllocation", "inventory.EquipmentKitTemplate",
    "inventory.EquipmentKitVersion", "inventory.EquipmentProposalReceipt", "machines.EventInductionLink",
    "machines.GuestCertificationGrant", "machines.SupervisedParticipant", "machines.SupervisedSession",
    "machines.SupervisedUse", "maintenance.Incident", "maintenance.IncidentAction", "makerspaces.CommunityPolicy",
    "makerspaces.DayPassProduct", "makerspaces.GuardianConsent", "makerspaces.GuardianConsentTerms",
    "makerspaces.GuestPass", "makerspaces.GuestPassPolicy", "makerspaces.MinorProfile",
    "makerspaces.VolunteerCredit", "makerspaces.VolunteerHourEntry", "shop.ShopEventOffer",
)
# Platform level or per-space secrets: never in a tenant dump, never in a one-space archive.
NEVER_TRAVEL = (
    "managed_hosting.PlatformThrottleRate", "managed_hosting.SpaceHostingType",
    "managed_hosting.PlatformLimitDefault", "managed_hosting.SpaceLimitThreshold",
    "card_designs.PlatformWalletCredentials", "card_designs.MakerspaceWalletCredentials",
    "notifications.BrowserFirebaseInstallation", "notifications.BrowserFirebaseRegistration",
)
# Reference a deployment-global organization (decision 223 k): omitted from the tenant export by design, so the booking and its charge travel without the link.
ORGANIZATION_LINKED_OMITTED = ("bookings.BookingOrganizationLink", "bookings.OrganizationHoursAllowance", "bookings.OrganizationHoursLedger")
SECRET_FIELD = re.compile(r"(_pem|service_account|secret|private_key|password|api_key)")
SCOPED_PII = {
    "makerspaces.MinorProfile": {"date_of_birth", "guardian_name", "guardian_email", "guardian_phone"},
    "makerspaces.GuardianConsent": {"signed_name"},
    "maintenance.Incident": {"involved_note"},
}
# Release-0.12 migrations that create SQL guard functions (the owner guard was missing from the catalog).
GUARD_MIGRATIONS = (
    "events/migrations/0088_event_booking_decision_guard.py",
    "inventory/migrations/0019_equipment_snapshot_guards.py",
    "makerspaces/migrations/0139_guest_pass_immutability.py",
)


@pytest.mark.parametrize("label", TENANT_MODELS)
def test_tenant_model_is_exported_and_restored_with_its_space(label):
    assert label in EXPORTED_MODEL_FIELDS, f"{label} is not an exported tenant model"
    assert label in SLICE_ROW_SPECS, f"{label} has no tenant dataset, so a one-space archive would drop it"
    assert label in restorable_labels()


@pytest.mark.parametrize("label", NEVER_TRAVEL + ORGANIZATION_LINKED_OMITTED)
def test_platform_and_secret_models_never_travel(label):
    assert label in MODELS and label in OMITTED_MODELS
    assert label not in EXPORTED_MODEL_FIELDS
    assert label not in SLICE_ROW_SPECS


def test_no_exported_release_0120_field_is_secret_material():
    leaked = {
        (label, name)
        for label in TENANT_MODELS
        for name in EXPORTED_MODEL_FIELDS[label].split()
        if SECRET_FIELD.search(name)
    }
    assert leaked == set()


@pytest.mark.parametrize("label,names", sorted(SCOPED_PII.items()))
def test_scoped_pii_fields_are_registered_for_encryption(label, names):
    assert names <= {field.field_name for field in fields_for_label(label)}


def test_every_release_0120_guard_function_is_catalogued():
    backend = Path(__file__).resolve().parents[2] / "apps"
    created = set()
    for relative in GUARD_MIGRATIONS:
        created |= set(re.findall(r"CREATE (?:OR REPLACE )?FUNCTION\s+([a-z_0-9]+)", (backend / relative).read_text()))
    assert created, "the guard migrations define no functions: update GUARD_MIGRATIONS"
    assert sorted(created - APPLICATION_FUNCTIONS) == []
