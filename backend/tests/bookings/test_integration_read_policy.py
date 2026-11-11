"""Cursor, grant policy, tombstone and installer boundaries for BK-H."""
from urllib.parse import urlencode

import pytest
from django.core import signing
from django.core.exceptions import ValidationError

from apps.apiclients.checks import check_scope_registry
from apps.apiclients.scope_grants import scope_catalog, validate_grantable_scopes
from apps.apiclients.scope_registry import BROWSER_SCOPES, validate_registry
from apps.apiclients.scope_registry_booking_reads import booking_read_routes, booking_read_scopes
from apps.bookings.models import BookableSpace, Booking
from tests.bookings.integration_read_helpers import PREFIX, SCOPES, principal, read_world, signed

pytestmark = pytest.mark.django_db


def test_keyset_orders_by_immutable_id_and_binds_client_subject_and_projection(read_world):
    w = read_world
    second = BookableSpace.objects.create(makerspace=w.tenant, name="A sorts before Private")
    path = PREFIX + "resources/"
    first = signed(w.client, path + "?page_size=1").json()
    cursor = first["next_cursor"]
    assert [row["id"] for row in first["results"]] == [w.resource.pk]
    third = BookableSpace.objects.create(makerspace=w.tenant, name="New insertion")
    next_path = path + "?" + urlencode({"cursor": cursor})
    page = signed(w.client, next_path).json()
    assert [row["id"] for row in page["results"]] == [second.pk, third.pk]
    assert page["next_cursor"] is None
    assert signed(principal(w.tenant), next_path).status_code == 400
    assert signed(w.client, PREFIX + "bookings/?" + urlencode({"cursor": cursor})).status_code == 400
    assert signed(w.client, path + "?cursor=tampered").status_code == 400
    for size in ["0", "201", "abc"]:
        assert signed(w.client, path + "?page_size=" + size).status_code == 400


def test_booking_cursor_rejects_attendance_change_and_expiry(read_world, monkeypatch):
    w = read_world
    Booking.objects.create(space=w.resource, name="Second", email="second@example.test", phone="123",
                           starts_at=w.booking.starts_at, ends_at=w.booking.ends_at)
    path = PREFIX + "bookings/"
    cursor = signed(w.client, path + "?page_size=1").json()["next_cursor"]
    w.client.scopes = ["bookings:read"]
    w.client.save(update_fields=["scopes"])
    assert signed(w.client, path + "?" + urlencode({"cursor": cursor})).status_code == 400
    w.client.scopes = SCOPES
    w.client.save(update_fields=["scopes"])
    def expired(*args, **kwargs):
        raise signing.SignatureExpired("expired")
    monkeypatch.setattr(signing, "loads", expired)
    assert signed(w.client, path + "?" + urlencode({"cursor": cursor})).status_code == 400


def test_privileged_grant_policy_and_browser_exclusion(read_world):
    for scope in SCOPES:
        values = ["bookings:read", scope] if scope.endswith("attendance:read") else [scope]
        assert validate_grantable_scopes(values, privileged=True) == values
        with pytest.raises(ValueError):
            validate_grantable_scopes(values, privileged=False)
        assert scope not in BROWSER_SCOPES
    with pytest.raises(ValueError, match="requires bookings:read"):
        validate_grantable_scopes(["bookings:attendance:read"], privileged=True)
    catalog = {row["value"]: row for row in scope_catalog(privileged=False)}
    assert all(not catalog[scope]["grantable"] for scope in SCOPES)
    # Issuance/model validation cannot mint browser/global signed-read principals.
    for kwargs in [{"client_type": "browser"}, {"makerspace": None}]:
        row = principal(kwargs.get("makerspace", read_world.tenant), client_type=kwargs.get("client_type", "server"))
        with pytest.raises(ValidationError):
            row.full_clean()


def test_tombstones_are_independent_and_core_metadata_never_imports_events(monkeypatch):
    from apps.apiclients.read_prefixes import mandatory_hmac_prefixes
    from apps.apiclients.scope_registry_reads import read_scope_vocabulary, read_route_entries
    monkeypatch.setattr("apps.separability.tombstones.tombstoned_app_labels", lambda: {"events"})
    assert booking_read_scopes() == frozenset(SCOPES)
    assert read_scope_vocabulary() == frozenset(SCOPES)
    assert len(read_route_entries()) == 10
    assert mandatory_hmac_prefixes() == [PREFIX]
    monkeypatch.setattr("apps.separability.tombstones.tombstoned_app_labels", lambda: {"bookings"})
    assert not booking_read_scopes() and not booking_read_routes()
    assert not any(name.startswith("integration-booking") for name, _ in read_route_entries())
    assert PREFIX not in mandatory_hmac_prefixes()


def test_registry_complete_with_settings_prefix_override(read_world, settings):
    settings.HMAC_PROTECTED_PATH_PREFIXES = ["/api/public/", "/api/v1/public/"]
    assert validate_registry() == ([], [])
    assert check_scope_registry(app_configs=None) == []


def test_installer_feature_is_booking_parent_without_unintended_dependencies():
    from apps.makerspaces.capability_definitions import FEATURE_DEFINITIONS
    from apps.makerspaces.setup_areas import features_for, modules_for
    feature = next(item for item in FEATURE_DEFINITIONS if item.key == "bookings.api_read")
    assert feature.parent_module == "bookings"
    assert feature.requires_modules == ("bookings",)
    assert not feature.default_enabled
    assert feature.key in features_for(["bookings"], modules_for(["bookings"]))
    assert feature.key not in features_for(["events"], modules_for(["events"]))


def test_model_graph_and_retention_catalog_require_no_new_pin():
    from apps.tenant_migration.tenant_dump_catalog import CATALOG_SCHEMA_SHA256, schema_digest
    assert schema_digest() == CATALOG_SCHEMA_SHA256


def test_read_throttle_and_audit_failure_do_not_disclose(read_world, settings, monkeypatch):
    w = read_world
    def unavailable(*args, **kwargs):
        raise RuntimeError("audit unavailable")
    monkeypatch.setattr("apps.bookings.views_integration.record", unavailable)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        signed(w.client, PREFIX + "bookings/")
    settings.INTEGRATION_READ_RATE = "1/min"
    assert signed(w.client, PREFIX + "resources/").status_code == 429


def test_frozen_source_refuses_audited_reservation_get_and_head(read_world):
    from datetime import timedelta
    from uuid import uuid4
    from django.utils import timezone
    from apps.tenant_migration.models_source_gate import SourceMigrationGate
    now = timezone.now()
    SourceMigrationGate.objects.update_or_create(makerspace=read_world.tenant, defaults={
        "state": "quiesced", "owner_id": uuid4(), "heartbeat_at": now,
        "lease_expires_at": now + timedelta(minutes=10),
    })
    for method in ("GET", "HEAD"):
        assert signed(read_world.client, PREFIX + "bookings/", method=method).status_code == 423
    # Pure resource reads append no tenant history.
    assert signed(read_world.client, PREFIX + "resources/").status_code == 200


def test_server_origin_and_scope_revocation_apply_to_next_request(read_world):
    w = read_world
    w.client.allowed_origins = ["https://allowed.example.test"]
    w.client.save(update_fields=["allowed_origins"])
    path = PREFIX + "bookings/"
    assert signed(w.client, path, HTTP_ORIGIN="https://wrong.example.test").status_code == 401
    assert signed(w.client, path, HTTP_ORIGIN="https://allowed.example.test").status_code == 200
    w.client.scopes = ["booking_resources:read"]
    w.client.save(update_fields=["scopes"])
    assert signed(w.client, path).status_code == 401
