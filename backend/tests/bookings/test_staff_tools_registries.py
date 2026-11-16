"""Scalar provenance and new routes remain in existing portability/install registries."""

import pytest
from django.urls import resolve, reverse

from apps.bookings.models import Booking
from apps.data_export.classification import EXPORTED_MODEL_FIELDS
from apps.makerspaces.capabilities import FEATURES, feature_required_modules
from apps.makerspaces.origin_scope_model_lookups import BASE_MODEL_LOOKUPS
from apps.makerspaces.setup_areas import features_for, modules_for
from apps.tenant_migration.audit_references_meta import AUDIT_META_REFERENCES
from apps.tenant_migration.audit_references_targets import AuditReferenceDisposition
from apps.tenant_migration.tenant_dump_authority import AUTHORITY_FIELD_OVERRIDES
from apps.tenant_migration.tenant_dump_catalog import CATALOG_SCHEMA_SHA256, schema_digest
from apps.tenant_migration.tenant_dump_field_snapshot import FIRST_PARTY_FIELD_NAMES
from apps.tenant_migration.tenant_dump_types import AuthorityDisposition


@pytest.mark.parametrize("key", ["bookings.clone", "bookings.staff_tools"])
def test_staff_tool_capabilities_are_booking_parented_and_installer_discovered(key):
    assert FEATURES[key].parent_module == "bookings"
    assert set(feature_required_modules(key)) == {"bookings"}
    assert key in features_for(["bookings"], modules_for(["bookings"]))
    assert key not in features_for(["events"], modules_for(["events"]))


@pytest.mark.parametrize("field", ["cancelled_at", "status_before_cancel"])
def test_cancellation_provenance_is_portable_preserved_scalar_history(field):
    assert field in EXPORTED_MODEL_FIELDS["bookings.Booking"].split()
    assert field in FIRST_PARTY_FIELD_NAMES["bookings.Booking"]
    assert AUTHORITY_FIELD_OVERRIDES[("bookings.Booking", field)].dispositions == (AuthorityDisposition.PRESERVE,)
    concrete = Booking._meta.get_field(field)
    assert not concrete.is_relation


def test_reviewed_catalog_hash_matches_complete_model_graph():
    assert schema_digest() == CATALOG_SCHEMA_SHA256


@pytest.mark.parametrize("action,path,model", [
    ("booking.space_cloned", "source_space_id", "bookings.BookableSpace"),
    ("booking.restored", "booking_id", "bookings.Booking"),
])
def test_new_audit_metadata_uses_registered_remappable_subjects(action, path, model):
    rule = AUDIT_META_REFERENCES[(action, path)]
    assert rule.disposition == AuditReferenceDisposition.REMAP and rule.target_model_label == model


@pytest.mark.parametrize("route,model,scope", [
    ("admin-bookable-space-clone", "bookings.BookableSpace", "makerspace_id"),
    ("admin-booking-details-edit", "bookings.Booking", "space__makerspace_id"),
    ("admin-booking-time-edit", "bookings.Booking", "space__makerspace_id"),
    ("admin-booking-restore", "bookings.Booking", "space__makerspace_id"),
])
def test_all_new_routes_resolve_to_registered_model_origin_scope(route, model, scope):
    assert BASE_MODEL_LOOKUPS[route] == (model, scope)
    match = resolve(reverse(route, kwargs={"pk": 123}))
    assert match.url_name == route and match.kwargs == {"pk": 123}
