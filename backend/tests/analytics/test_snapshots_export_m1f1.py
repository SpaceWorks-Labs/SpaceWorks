from datetime import timedelta
import json
from types import SimpleNamespace
from uuid import uuid4
import zipfile

import pytest
from django.apps import apps
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.utils import timezone

from apps.accounts.device_activity import record_device_activity
from apps.accounts.models_activity import DeviceActivityDay
from apps.data_export.datasets import DATASET_SPECS
from apps.data_export.subject_runtime import RUNTIME_FIELDS, runtime_projections, runtime_record
from apps.data_export.subject_selectors import subject_query
from apps.integrations.models import PushDevice, NotificationDeliveryLog
from apps.integrations.models_tracking import PushDeliveryAttempt
from apps.inventory.availability_stock import observe_stock
from apps.inventory.models_tracking import InventoryStockSnapshot
from apps.machines import services
from apps.notifications.models_inbox import NotificationInboxRow
from apps.notifications.models_push import MemberPushDelivery
from tests.return_helpers import make_product, make_space
from tests.test_machine_service_workflow import machine
from tests.accounts.push_factories import push_parent
from tests.test_native_push import device_client, push_member

pytestmark = pytest.mark.django_db


def test_stock_observations_use_tenant_day_are_unique_and_do_not_backfill():
    space = make_space("stock-observed")
    space.timezone = "America/Los_Angeles"
    product = make_product(space, total_quantity=5, available_quantity=0, issued_quantity=5, reorder_point=2)
    now = timezone.datetime(2026, 10, 17, 1, tzinfo=timezone.get_fixed_timezone(0))
    assert observe_stock(space, now=now) == 1
    assert observe_stock(space, now=now) == 0
    row = InventoryStockSnapshot.objects.get()
    assert row.local_day.isoformat() == "2026-10-16"
    assert (row.available, row.issued, row.total, row.out_of_stock, row.below_reorder) == (0, 5, 5, True, True)
    assert observe_stock(space, now=now + timedelta(days=2)) == 1
    assert InventoryStockSnapshot.objects.count() == 2
    with pytest.raises(IntegrityError), transaction.atomic():
        InventoryStockSnapshot.objects.create(makerspace=space, product=product, local_day=row.local_day,
            available=0, issued=5, total=5, out_of_stock=True, below_reorder=True)
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("UPDATE inventory_inventorystocksnapshot SET available=1 WHERE id=%s", [row.pk])


def test_scheduler_and_source_gate_parity(settings):
    from apps.operations.management.commands.run_scheduled_tasks import SCHEDULED_TASKS
    from apps.tenant_migration.gate_policy_tasks import TASK_INTERNAL_PARTICIPANTS, FANOUT_GATE_PARTICIPANTS
    path = "apps.inventory.tasks.snapshot_stock_task"
    assert settings.CELERY_BEAT_SCHEDULE["inventory-stock-snapshot"]["task"] == path
    assert ("inventory-stock-snapshot", path, 1440) in SCHEDULED_TASKS
    assert path in TASK_INTERNAL_PARTICIPANTS
    assert "apps.inventory.stock_snapshots.snapshot_inventory_stock" in FANOUT_GATE_PARTICIPANTS


def test_cost_source_id_is_remapped_with_its_domain_source():
    from unittest.mock import Mock
    from apps.tenant_migration.semantic_remap import remap_semantic_references
    from apps.tenant_migration.tracking_references import COST_SOURCE_MODELS
    choices = apps.get_model("machines.ConsumableCostRecord")._meta.get_field("source_kind").choices
    assert {key for key, _ in choices} == set(COST_SOURCE_MODELS)
    for kind, label in COST_SOURCE_MODELS.items():
        source = {"id": 12, "source_kind": kind, "source_id": 123}
        row = dict(source)
        pk_map = SimpleNamespace(lookup=Mock(return_value=456))
        assert remap_semantic_references("machines.ConsumableCostRecord", source, row, pk_map, None)
        assert row["source_id"] == 456
        pk_map.lookup.assert_called_once_with(apps.get_model(label), 123)


def runtime_rows():
    space, foreign = make_space("export-runtime"), make_space("export-runtime-foreign")
    user = push_member("export-runtime-member", space)
    _, grant = device_client(user, space)
    membership = user.makerspace_memberships.get(makerspace=space)
    record_device_activity(grant, membership)
    record_device_activity(grant)
    # A browser-session day in the space and one with no selected space; the archive carries both.
    from apps.accounts.models_activity import WebSessionActivityDay
    today = timezone.localdate()
    WebSessionActivityDay.objects.create(user=user, session_hash="a" * 32, makerspace=space, local_day=today)
    WebSessionActivityDay.objects.create(user=user, session_hash="b" * 32, makerspace=None, local_day=today)
    device = PushDevice.objects.create(makerspace=space, user=user, device_grant=grant,
        provider="apns", environment="development", token_fingerprint="private", token_ciphertext="private-token")
    inbox = NotificationInboxRow.objects.create(makerspace=space, user=user, title="Private message",
        event_key=uuid4(), audience="member", feature="hardware_requests", event="accepted")
    MemberPushDelivery.objects.create(envelope_delivery=push_parent(space, user), inbox_row=inbox,
                                      push_device=device, status="sent", platform="apple")
    log = NotificationDeliveryLog.objects.create(makerspace=space, channel="native_push", feature="hardware_requests", event="submitted")
    PushDeliveryAttempt.objects.create(delivery_log=log, push_device=device, recipient=user, status="sent", platform="apple")
    return space, foreign, user, grant


def test_runtime_personal_projection_contains_own_activity_without_destinations():
    space, foreign, user, grant = runtime_rows()
    # Projections yield model rows so scoped PII decrypts; runtime_record is the export shape.
    rows = {label: [runtime_record(label, row) for row in query] for label, query in runtime_projections(user, space.pk)}
    assert len(rows["accounts.DeviceActivityDay"]) == 2
    assert len(rows["accounts.WebSessionActivityDay"]) == 2
    assert len(rows["notifications.MemberPushDelivery"]) == len(rows["integrations.PushDeliveryAttempt"]) == 1
    for label, values in rows.items():
        assert all(set(value) == set(RUNTIME_FIELDS[label]) for value in values)
        assert label not in DATASET_SPECS
    assert not list(dict(runtime_projections(user, foreign.pk))["notifications.MemberPushDelivery"])
    payload = json.dumps(rows, default=str)
    assert "private-token" not in payload and "Private message" not in payload
    assert "lease_token" not in payload and "push_device" not in payload
    from apps.tenant_migration.tenant_dump_model_catalog import FIRST_PARTY_MODEL_RULES
    from apps.tenant_migration.tenant_dump_types import ModelDisposition
    assert all(FIRST_PARTY_MODEL_RULES[label].disposition is ModelDisposition.DROP for label in RUNTIME_FIELDS)


def test_device_reassignment_cannot_transfer_personal_delivery_history():
    space, _, owner, _ = runtime_rows()
    recipient = push_member("runtime-reassigned-member", space)
    _, grant = device_client(recipient, space)
    PushDevice.objects.filter(user=owner).update(user=recipient, device_grant=grant)
    old = dict(runtime_projections(owner, space.pk))
    new = dict(runtime_projections(recipient, space.pk))
    for label in ("notifications.MemberPushDelivery", "integrations.PushDeliveryAttempt"):
        assert old[label].count() == 1 and new[label].count() == 0


@pytest.mark.django_db(transaction=True)
def test_personal_archive_includes_allowlisted_runtime_activity_section():
    from apps.data_export.subject_archive import build_subject_archive
    space, _, user, _ = runtime_rows()
    job = SimpleNamespace(makerspace_id=space.pk, requested_by=user, requested_by_id=user.pk,
                          deadline_at=timezone.now() + timedelta(minutes=2))
    path, manifest, directory = build_subject_archive(job)
    try:
        with zipfile.ZipFile(path) as archive:
            for label in RUNTIME_FIELDS:
                values = json.loads(archive.read("runtime_activity/" + label + ".json"))
                # runtime_rows() seeds device, canonical push and push-ledger activity;
                # legacy messaging deliveries and verified endpoints are covered by
                # tests/messaging and may be empty here, as may the login-security (S-B)
                # sign-in memory, which runtime_rows() does not seed.
                from apps.data_export.subject_runtime_security import FIELDS as SECURITY_FIELDS
                assert values or label in {"integrations.MessagingDelivery", "integrations.NotificationEndpoint",
                                           *SECURITY_FIELDS}
                assert all(set(value) == set(RUNTIME_FIELDS[label]) for value in values)
        assert manifest["row_counts"]["accounts.DeviceActivityDay"] == 2
    finally:
        directory.cleanup()


def test_manual_usage_personal_selector_includes_member_and_excludes_other_people():
    space = make_space("usage-personal")
    # Attribution names member accounts; the logging actor is not validated here.
    user, other = push_member("usage-personal-member", space), push_member("usage-personal-other", space)
    target = machine(space)
    own = services.log_usage(target, other, 1, member=user)
    services.log_usage(target, user, 1, member=other)
    assert list(subject_query(type(own), user, space.pk).values_list("pk", flat=True)) == [own.pk]


def test_runtime_rows_cascade_with_grant_purge_and_anonymous_ledgers_have_no_user_fk():
    space, _, _, grant = runtime_rows()
    grant.delete()
    assert not DeviceActivityDay.objects.exists()
    assert not PushDeliveryAttempt.objects.exists() and not MemberPushDelivery.objects.exists()
    for label in ("integrations.SmsSendLog", "accounts.AttestationVerificationLog",
                  "inventory.InventoryStockSnapshot", "machines.MachineStatusEvent", "machines.ConsumableCostRecord"):
        model = apps.get_model(label)
        assert not any(f.is_relation and f.related_model and f.related_model._meta.label == "accounts.User"
                       for f in model._meta.concrete_fields)
