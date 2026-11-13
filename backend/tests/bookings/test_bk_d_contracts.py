"""Retention, encrypted drafts, opt-in installer and API contracts."""
from datetime import timedelta

import pytest
from django.apps import apps
from django.db import connection, transaction
from django.urls import reverse
from django.utils import timezone
from drf_spectacular.generators import SchemaGenerator

from apps.data_export.classification import EXPORTED_MODEL_FIELDS
from apps.data_export.datasets import DATASET_SPECS
from apps.data_export.references import USER_EDGES
from apps.data_export.types import Fidelity
from apps.encryption.crypto import is_envelope
from apps.encryption.registry import fields_for_label
from apps.integrations.models import EmailLog
from apps.tenant_migration.target_projection import TARGET_FIELD_PROJECTION
from tests.bookings.bk_d_helpers import draft, fixture, queued
from tests.bookings.staff_grant_helpers import client_for


def test_history_is_exported_with_closed_user_edges_and_inert_sends():
    for label in ("bookings.BookingBroadcast", "bookings.BookingBroadcastDelivery"):
        assert label in EXPORTED_MODEL_FIELDS and label in DATASET_SPECS
    for label, field in (("bookings.BookingBroadcast", "created_by"), ("bookings.BookingBroadcastDelivery", "recipient")):
        assert USER_EDGES[(Fidelity.PORTABLE, label, field)].included
    assert {field.field_name for field in fields_for_label("bookings.BookingBroadcast")} == {"subject", "body"}
    for field, value in (("status", "cancelled"), ("recipient_cursor", 0), ("recipients_complete", True)):
        assert TARGET_FIELD_PROJECTION[("bookings.BookingBroadcast", field)].value == value
    assert TARGET_FIELD_PROJECTION[("bookings.BookingBroadcastDelivery", "outbox")].value is None
    from apps.tenant_migration.tenant_dump_catalog import validate_catalog
    validate_catalog()


@pytest.mark.django_db
def test_encrypted_compose_and_database_write_fence(monkeypatch):
    from tests.encryption.conftest import enabled_encryption
    from apps.encryption.write_fence import PiiWriteFenced
    from apps.bookings.models import BookingBroadcast
    with enabled_encryption(dual_read=False):
        tenant, manager, sender, resource, grant, user, booking = fixture(monkeypatch)
        campaign = draft(resource, sender)
        stored = BookingBroadcast.objects.filter(pk=campaign.pk).values_list("subject", "body").get()
        assert all(is_envelope(value) for value in stored)
        assert campaign.subject == "Hi {{ name }}"
        from django.db import DatabaseError
        from apps.encryption.models import PiiMakerspaceWriteFence
        from apps.encryption.write_fence import close_makerspace, reopen
        operation = close_makerspace(tenant.pk, PiiMakerspaceWriteFence.OperationKind.DECRYPT_ROLLBACK, manager.pk)
        try:
            with pytest.raises(PiiWriteFenced):
                draft(resource, sender)
            with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
                cursor.execute("UPDATE bookings_bookingbroadcast SET body = body WHERE id = %s", [campaign.pk])
        finally:
            reopen(operation, manager.pk)


@pytest.mark.django_db
def test_bookings_purge_preserves_other_domain_sources(monkeypatch):
    tenant, manager, sender, resource, grant, user, booking = fixture(monkeypatch)
    campaign, delivery, log = queued(resource, sender)
    other = EmailLog.objects.create(makerspace=tenant, to_email=user.email, subject="Other domain", source_kind="event_broadcast")
    from apps.makerspaces.module_purge_collectors_single_model import bookings_delete
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SET LOCAL app.allow_immutable_delete = 'on'")
        bookings_delete(tenant, cursor)
    assert not type(campaign).objects.filter(pk=campaign.pk).exists()
    assert not type(delivery).objects.filter(pk=delivery.pk).exists()
    assert not EmailLog.objects.filter(pk=log.pk).exists()
    assert EmailLog.objects.filter(pk=other.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_whole_tenant_purge_removes_booking_campaign_history(monkeypatch):
    from apps.accounts.models import User
    from apps.makerspaces.lifecycle_purge import purge
    tenant, manager, sender, resource, grant, user, booking = fixture(monkeypatch)
    campaign, delivery, log = queued(resource, sender)
    root = User.objects.create_superuser(username="bk-d-purge", email="root@example.test", password="pw")
    tenant.archived_at = timezone.now(); tenant.save()
    monkeypatch.setattr("apps.makerspaces.lifecycle._delete_storage_keys", lambda *args: None)
    monkeypatch.setattr("apps.makerspaces.lifecycle._delete_public_image_keys", lambda *args: None)
    purge(tenant, root)
    assert not type(campaign).objects.filter(pk=campaign.pk).exists()
    assert not type(delivery).objects.filter(pk=delivery.pk).exists()


def test_installer_feature_prunes_missing_prerequisites():
    from apps.makerspaces.capabilities import FEATURES
    from apps.makerspaces.setup_areas import features_for
    feature = FEATURES["bookings.broadcasts"]
    assert feature.parent_module == "bookings" and not feature.default_enabled
    assert "bookings.broadcasts" in features_for({"bookings"}, {"bookings", "notifications", "email"})
    for installed in ({"bookings"}, {"bookings", "notifications"}, {"bookings", "email"}):
        assert "bookings.broadcasts" not in features_for({"bookings"}, installed)


@pytest.mark.django_db
def test_booking_broadcast_openapi_has_isolated_schemas_and_all_routes():
    schema = SchemaGenerator().get_schema(request=None, public=True)
    components = schema["components"]["schemas"]
    for name in ("BookingBroadcastInput", "BookingBroadcast", "BookingBroadcastList"):
        assert name in components
    assert set(components["BookingBroadcastInput"]["required"]) == {"subject", "body", "window_end"}
    for path in ("/api/v1/admin/spaces/{id}/broadcasts/", "/api/v1/admin/spaces/{id}/broadcasts/{campaign_id}/queue/", "/api/v1/admin/spaces/{id}/broadcasts/{campaign_id}/cancel/"):
        operation = schema["paths"][path]["post"]
        assert {"400", "401", "403", "404", "409", "423", "429", "503"} <= set(operation["responses"])
    assert "broadcasts_enabled" in components["BookableSpaceAdmin"]["properties"]
