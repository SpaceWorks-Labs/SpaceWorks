"""Frozen conversion on real rows, without reversing irreversible history migrations."""
import importlib
import json
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.utils import timezone

from apps.integrations.models_cutover import NotificationCutover, NotificationLegacyMapping
from apps.integrations.notification_cutover import establish_barrier
from apps.makerspaces.secrets import decrypt_value, encrypt_value
from apps.notifications.models_push import MemberPushDelivery
from tests.notifications.test_support_m1b import push_case  # noqa: F401

pytestmark = pytest.mark.django_db(transaction=True)
conversion = importlib.import_module("apps.notifications.migrations._push_conversion_v1")


@pytest.fixture
def push_migration_case(push_case):
    # Temporarily expose exactly the expanded nullable column. Keep migration
    # history intact: reverse-converting held attempts would invent send authority.
    loader = MigrationLoader(connection)
    registry = loader.project_state([
        ("notifications", "0008_envelope_push_expansion"),
        ("integrations", "0042_notification_history_conversion"),
    ]).apps
    old_field = MemberPushDelivery._meta.get_field("envelope_delivery")
    nullable = registry.get_model("notifications", "MemberPushDelivery")._meta.get_field("envelope_delivery")
    with connection.schema_editor() as editor:
        editor.alter_field(MemberPushDelivery, old_field, nullable, strict=True)
    try:
        yield SimpleNamespace(case=push_case, registry=registry, editor=SimpleNamespace(connection=connection),
                              Push=registry.get_model("notifications", "MemberPushDelivery"))
    finally:
        MemberPushDelivery.objects.filter(envelope_delivery=None).delete()
        with connection.schema_editor() as editor:
            editor.alter_field(MemberPushDelivery, nullable, old_field, strict=True)


def legacy(ctx, **values):
    inbox = ctx.case.enqueue()
    return ctx.Push.objects.create(inbox_row_id=inbox.pk, push_device_id=ctx.case.device.pk,
                                   platform="android", provider_source="platform", **values)


def barrier():
    NotificationCutover.objects.update_or_create(pk=1, defaults={
        "route": "receipt_only", "sending_enabled": False, "activated_at": None,
        "barrier_at": None, "copied_at": None, "reconciled_at": None, "snapshot": {}})
    gate = establish_barrier(drained=True)
    # P copies after M0042. Its conversion behavior is covered by M's own tests;
    # this fixture isolates P's historical helper and exact original push snapshot.
    NotificationCutover.objects.filter(pk=1).update(copied_at=timezone.now())
    return gate


@pytest.mark.parametrize("status,attempts,lease,expected,decision", [
    ("sent", 2, False, "sent", "terminal_history"),
    ("skipped", 0, False, "skipped", "terminal_history"),
    ("failed", 1, False, "failed", "terminal_history"),
    ("pending", 0, False, "canceled", "canceled_unattempted"),
    ("pending", 1, False, "held", "held_unknown_outcome"),
    ("pending", 0, True, "held", "held_unknown_outcome"),
    ("sending", 1, True, "held", "held_unknown_outcome"),
    ("sending", 1, False, "held", "held_unknown_outcome"),
])
def test_every_old_attempt_has_inert_parent_and_exact_snapshot(push_migration_case, status, attempts, lease, expected, decision):
    ctx = push_migration_case
    old = legacy(ctx, status=status, attempts=attempts, last_error="old_provider_error",
        lease_token=uuid4() if lease else None,
        lease_until=timezone.now() - timedelta(minutes=1) if lease else None,
        sent_at=timezone.now() if status == "sent" else None)
    original = {f.attname: getattr(old, f.attname) for f in old._meta.concrete_fields}
    gate = barrier()
    conversion.convert(ctx.registry, ctx.editor)
    conversion.verify(ctx.registry, ctx.editor)
    current = MemberPushDelivery.objects.select_related("envelope_delivery__envelope").get(pk=old.pk)
    parent = current.envelope_delivery
    assert current.status == expected and not current.retryable
    assert current.attempts == attempts and current.created_at == old.created_at
    assert current.lease_token == old.lease_token and current.lease_until == old.lease_until
    assert current.last_error == "old_provider_error" and current.sent_at == old.sent_at
    assert parent.historical and parent.channel == "native_push" and not parent.retryable
    assert parent.envelope.source_kind == "migration.history"
    assert parent.created_at == old.created_at
    mapping = NotificationLegacyMapping.objects.get(legacy_model="MemberPushDelivery", legacy_id=old.pk)
    assert mapping.canonical_id == old.pk and mapping.disposition == decision
    assert mapping.snapshot.startswith("fernet:")
    from django.core.serializers.json import DjangoJSONEncoder
    assert json.loads(decrypt_value(mapping.snapshot)) == json.loads(json.dumps(original, cls=DjangoJSONEncoder))
    from apps.integrations.notification_conversion_snapshot import verify_original_mapping
    verify_original_mapping(NotificationLegacyMapping.objects.filter(legacy_model="MemberPushDelivery"), gate.snapshot["_push"])
    conversion.convert(ctx.registry, ctx.editor)
    assert NotificationLegacyMapping.objects.filter(legacy_model="MemberPushDelivery").count() == 1
    assert MemberPushDelivery.objects.get(pk=old.pk).envelope_delivery_id == parent.pk
    assert ctx.case.calls == []


def test_barrier_and_m_copy_are_required_before_populated_conversion(push_migration_case):
    ctx = push_migration_case
    legacy(ctx)
    NotificationCutover.objects.filter(pk=1).update(route="receipt_only", sending_enabled=False, barrier_at=None, copied_at=None)
    with pytest.raises(RuntimeError, match="requires drained writers"):
        conversion.convert(ctx.registry, ctx.editor)
    assert not NotificationLegacyMapping.objects.exists()


def test_row_drift_after_barrier_is_refused(push_migration_case):
    ctx = push_migration_case
    old = legacy(ctx)
    barrier()
    ctx.Push.objects.filter(pk=old.pk).update(attempts=1)
    with pytest.raises(RuntimeError, match="differs from"):
        conversion.convert(ctx.registry, ctx.editor)
    assert not NotificationLegacyMapping.objects.exists()


def test_crash_after_first_mapping_resumes_without_replay(push_migration_case, monkeypatch):
    ctx = push_migration_case
    first, second = legacy(ctx), legacy(ctx)
    barrier()
    copy = conversion.copy_row

    def interrupted(registry, alias, row):
        if row.pk == second.pk:
            raise RuntimeError("crash after committed mapping")
        copy(registry, alias, row)

    monkeypatch.setattr(conversion, "copy_row", interrupted)
    with pytest.raises(RuntimeError, match="crash"):
        conversion.convert(ctx.registry, ctx.editor)
    first_parent = MemberPushDelivery.objects.get(pk=first.pk).envelope_delivery_id
    monkeypatch.setattr(conversion, "copy_row", copy)
    conversion.convert(ctx.registry, ctx.editor)
    conversion.verify(ctx.registry, ctx.editor)
    assert MemberPushDelivery.objects.get(pk=first.pk).envelope_delivery_id == first_parent
    assert NotificationLegacyMapping.objects.filter(legacy_model="MemberPushDelivery").count() == 2
    # Never merge historical device collisions or discard an attempt.
    assert MemberPushDelivery.objects.values("envelope_delivery_id").distinct().count() == 2
    assert ctx.case.calls == []


def test_constraint_preflight_refuses_unmapped_or_tampered_history(push_migration_case):
    ctx = push_migration_case
    old = legacy(ctx)
    barrier()
    conversion.convert(ctx.registry, ctx.editor)
    mapping = NotificationLegacyMapping.objects.get(legacy_model="MemberPushDelivery", legacy_id=old.pk)
    original = json.loads(decrypt_value(mapping.snapshot))
    original["attempts"] = 100
    mapping.snapshot = encrypt_value(json.dumps(original))
    mapping.save(update_fields=["snapshot"])
    with pytest.raises(RuntimeError, match="differs from"):
        conversion.verify(ctx.registry, ctx.editor)


def test_final_graph_has_parent_constraint_and_both_histories():
    loader = MigrationLoader(connection)
    leaf = ("notifications", "0010_envelope_push_constraints")
    plan = loader.graph.forwards_plan(leaf)
    for parent in [("notifications", "0006_messaging_m1h"), ("notifications", "0004_notification_preferences"),
                   ("accounts", "0041_reconcile_native_account_context"),
                   ("integrations", "0041_notification_cutover_expansion")]:
        assert parent in plan
    # L2 added notifications/0011 on top; the reconciliation leaf must stay in its history.
    assert loader.graph.leaf_nodes("notifications") == [("notifications", "0011_inbox_snooze_browser_alerts")]
    assert leaf in loader.graph.forwards_plan(("notifications", "0011_inbox_snooze_browser_alerts"))
    final = loader.project_state([leaf]).apps.get_model("notifications", "MemberPushDelivery")
    assert not final._meta.get_field("envelope_delivery").null
    assert final._meta.get_field("inbox_row").null
    assert {c.name for c in final._meta.constraints} == {"uniq_envelope_push_device"}


def test_empty_p_before_m_copy_does_not_seed_a_partial_shared_snapshot(push_migration_case):
    ctx = push_migration_case
    NotificationCutover.objects.update_or_create(pk=1, defaults={"route": "receipt_only",
        "sending_enabled": False, "snapshot": {}, "copied_at": None, "barrier_at": None})
    conversion.convert(ctx.registry, ctx.editor)
    conversion.verify(ctx.registry, ctx.editor)
    gate = NotificationCutover.objects.get(pk=1)
    assert gate.snapshot == {} and gate.copied_at is None
