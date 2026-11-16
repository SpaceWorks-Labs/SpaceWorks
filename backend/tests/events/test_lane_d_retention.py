from apps.accounts.models import User
import pytest
from apps.data_export.classification import EXPORTED_MODEL_FIELDS
from apps.data_export.datasets import DATASET_SPECS
from apps.data_export.references import USER_EDGES
from apps.data_export.types import Fidelity
from apps.encryption.registry import fields_for_label
from apps.tenant_migration.target_projection import TARGET_FIELD_PROJECTION
from apps.tenant_migration.unique_values import DEPLOYMENT_GLOBAL_UNIQUE_RULES


def test_history_and_inert_projection_are_explicit():
    for label in ("events.EventBroadcast", "events.EventBroadcastDelivery"):
        assert label in EXPORTED_MODEL_FIELDS and label in DATASET_SPECS
    for label, name in (("events.EventBroadcast", "created_by"), ("events.EventBroadcastDelivery", "recipient")):
        assert USER_EDGES[(Fidelity.PORTABLE, label, name)].included
    assert {f.field_name for f in fields_for_label("events.EventBroadcast")} == {"subject", "body"}
    assert TARGET_FIELD_PROJECTION[("events.EventBroadcast", "status")].value == "cancelled"
    assert TARGET_FIELD_PROJECTION[("events.EventBroadcastDelivery", "outbox")].value is None
    assert ("events.EventBroadcastDelivery", "field:outbox") in DEPLOYMENT_GLOBAL_UNIQUE_RULES


@pytest.mark.django_db
def test_events_module_purge_deletes_only_event_campaign_outboxes(monkeypatch):
    from django.db import connection, transaction
    from apps.integrations.models import EmailLog
    from apps.makerspaces.module_purge_collectors_events import events_delete
    from tests.events.lane_d_helpers import fixture, queued
    space, actor, user, event, registration = fixture(monkeypatch)
    campaign, delivery, log = queued(event, actor, statuses=["registered"])
    unrelated = EmailLog.objects.create(makerspace=space, to_email=user.email, subject="Other domain", source_kind="booking_broadcast")
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SET LOCAL app.allow_immutable_delete = 'on'")
        events_delete(space, cursor)
    assert not type(campaign).objects.filter(pk=campaign.pk).exists()
    assert not EmailLog.objects.filter(pk=log.pk).exists()
    assert EmailLog.objects.filter(pk=unrelated.pk).exists()


@pytest.mark.django_db
def test_whole_tenant_purge_removes_campaigns_and_delivery_links(monkeypatch):
    from django.utils import timezone
    from apps.makerspaces.lifecycle_purge import purge
    from tests.events.lane_d_helpers import fixture, queued
    space, actor, user, event, registration = fixture(monkeypatch)
    campaign, delivery, log = queued(event, actor, statuses=["registered"])
    actor = User.objects.create_superuser(username="event-purge-root", password=None)
    space.archived_at = timezone.now(); space.save()
    monkeypatch.setattr("apps.makerspaces.lifecycle._delete_storage_keys", lambda *args: None)
    monkeypatch.setattr("apps.makerspaces.lifecycle._delete_public_image_keys", lambda *args: None)
    purge(space, actor)
    assert not type(campaign).objects.filter(pk=campaign.pk).exists()
    assert not type(delivery).objects.filter(pk=delivery.pk).exists()
