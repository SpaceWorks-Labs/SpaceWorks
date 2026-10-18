"""Frozen historical-model conversion. No live source reconstruction or provider calls."""
import hashlib
import json
from contextlib import contextmanager

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone

from apps.makerspaces.secrets import decrypt_value, encrypt_value

LEGACY = "MemberPushDelivery"
TERMINAL = {"sent", "failed", "skipped", "canceled"}


def disposition(row):
    if row["status"] in TERMINAL:
        return "terminal_history", row["status"]
    if (row["status"] == "pending" and row["attempts"] == 0
            and not row["lease_token"] and not row["lease_until"] and not row["sent_at"]):
        return "canceled_unattempted", "canceled"
    return "held_unknown_outcome", "held"


def original_rows(registry, alias, expected):
    Push = registry.get_model("notifications", LEGACY)
    Mapping = registry.get_model("integrations", "NotificationLegacyMapping")
    saved = Mapping.objects.using(alias).filter(legacy_model=LEGACY)
    fields = expected.get("fields") or [f.attname for f in Push._meta.concrete_fields]
    for row in Push.objects.using(alias).order_by("pk").values().iterator(chunk_size=500):
        mapping = saved.filter(legacy_id=row["id"]).first()
        if mapping:
            if not mapping.snapshot:
                raise RuntimeError("Original push snapshot was redacted; manual review is required")
            row = json.loads(decrypt_value(mapping.snapshot))
        yield {name: row[name] for name in fields}


def assert_snapshot(registry, alias, expected):
    digest, count, maximum = hashlib.sha256(), 0, 0
    for row in original_rows(registry, alias, expected):
        digest.update(json.dumps(row, cls=DjangoJSONEncoder, sort_keys=True).encode())
        count += 1
        maximum = row["id"]
    if {"count": count, "max_id": maximum, "sha256": digest.hexdigest()} != {
            key: expected[key] for key in ("count", "max_id", "sha256")}:
        raise RuntimeError("Push snapshot differs from the shared cutover barrier")


def copy_row(registry, alias, old):
    Mapping = registry.get_model("integrations", "NotificationLegacyMapping")
    Push = registry.get_model("notifications", LEGACY)
    Envelope = registry.get_model("integrations", "NotificationEnvelope")
    Delivery = registry.get_model("integrations", "NotificationDelivery")
    with transaction.atomic(using=alias):
        old = Push.objects.using(alias).select_for_update().get(pk=old.pk)
        if Mapping.objects.using(alias).filter(legacy_model=LEGACY, legacy_id=old.pk).exists():
            if not old.envelope_delivery_id:
                raise RuntimeError("Mapped push row lost its parent")
            return
        if old.envelope_delivery_id:
            raise RuntimeError("Push parent has no original mapping")
        original = {f.attname: getattr(old, f.attname) for f in old._meta.concrete_fields}
        decision, status = disposition(original)
        inbox = registry.get_model("notifications", "NotificationInboxRow").objects.using(alias).filter(
            pk=old.inbox_row_id).first()
        device = registry.get_model("integrations", "PushDevice").objects.using(alias).get(pk=old.push_device_id)
        tenant = inbox.makerspace_id if inbox else device.makerspace_id
        user = inbox.user_id if inbox else device.user_id
        # Inbox content cannot prove a current source/revision. Each original row
        # gets a distinct inert parent; collisions retain every attempt's provenance.
        envelope = Envelope.objects.using(alias).create(
            makerspace_id=tenant, recipient_id=user,
            feature=inbox.feature if inbox else "", event=inbox.event if inbox else "legacy_push",
            audience=inbox.audience if inbox and inbox.audience in {"staff", "member"} else "member",
            source_kind="migration.history", source_id=str(old.pk),
            dedup_key=f"migration:MemberPushDelivery:{old.pk}",
            context={"legacy_model": LEGACY, "legacy_id": old.pk}, processed_at=timezone.now())
        state = status if status in {"sent", "failed", "skipped", "held"} else "skipped"
        parent = Delivery.objects.using(alias).create(
            makerspace_id=tenant, envelope=envelope, channel="native_push", target_key="native_push",
            provider="builtin", historical=True, state=state, retryable=False,
            attempt_count=min(old.attempts, 32767), sent_at=old.sent_at,
            last_error="migration_unknown_outcome" if status == "held" else "migration_history")
        Envelope.objects.using(alias).filter(pk=envelope.pk).update(created_at=old.created_at)
        Delivery.objects.using(alias).filter(pk=parent.pk).update(created_at=old.created_at)
        Push.objects.using(alias).filter(pk=old.pk).update(
            envelope_delivery_id=parent.pk, status=status, retryable=False)
        Mapping.objects.using(alias).create(legacy_model=LEGACY, legacy_id=old.pk,
            canonical_model=LEGACY, canonical_id=old.pk, makerspace_id=tenant,
            disposition=decision, snapshot=encrypt_value(json.dumps(original,
                cls=DjangoJSONEncoder, sort_keys=True)))


def intersect_preferences(registry, alias):
    Selection = registry.get_model("notifications", "NotificationPreference")
    Legacy = registry.get_model("notifications", "MemberNotificationPreference")
    for saved in Selection.objects.using(alias).all().iterator(chunk_size=500):
        disabled = set(Legacy.objects.using(alias).filter(makerspace_id=saved.makerspace_id,
            user_id=saved.user_id, feature=saved.category, enabled=False).values_list("channel", flat=True))
        channels = saved.channels
        valid = isinstance(channels, list) and all(isinstance(c, str) for c in channels)
        Selection.objects.using(alias).filter(pk=saved.pk).update(
            channels=[c for c in channels if c not in disabled] if valid else [],
            email_fallback=valid and saved.email_fallback and "email" not in disabled)
    # Do not create selections for missing T rows: that would replace its product
    # defaults and could enable channels. Retained legacy negatives constrain reads.


@contextmanager
def cutover_lock(connection):
    # Frozen lock identity shared with the deployed ingress/activation boundary.
    # A separate connection holds it across per-row application commits.
    import psycopg2
    boundary = psycopg2.connect(**connection.get_connection_params())
    try:
        with boundary.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [62839674110218])
        yield
    finally:
        boundary.close()


def convert(registry, schema_editor):
    with cutover_lock(schema_editor.connection):
        _convert(registry, schema_editor)


def _convert(registry, schema_editor):
    alias = schema_editor.connection.alias
    Gate = registry.get_model("integrations", "NotificationCutover")
    Push = registry.get_model("notifications", LEGACY)
    gate, _ = Gate.objects.using(alias).get_or_create(pk=1)
    populated = Push.objects.using(alias).exists()
    if populated and (gate.route != "receipt_only" or gate.sending_enabled
                      or not gate.barrier_at or not gate.copied_at):
        raise RuntimeError("Push copy requires drained writers, shared barrier and completed M0042 copy")
    # Empty fresh graphs may apply P before M0042. Do not seed a partial M
    # snapshot: M must still initialize its complete original-model fingerprints.
    if not populated and not gate.copied_at:
        with transaction.atomic(using=alias):
            intersect_preferences(registry, alias)
        return
    expected = gate.snapshot.get("_push")
    if populated and expected is None:
        raise RuntimeError("Shared barrier has no original push snapshot")
    if expected:
        assert_snapshot(registry, alias, expected)
    for old in Push.objects.using(alias).order_by("pk").iterator(chunk_size=500):
        copy_row(registry, alias, old)
    with transaction.atomic(using=alias):
        intersect_preferences(registry, alias)
        gate = Gate.objects.using(alias).select_for_update().get(pk=1)
        gate.snapshot = {**gate.snapshot, "_push_copy_complete": True}
        gate.save(using=alias, update_fields=["snapshot"])


def verify(registry, schema_editor):
    with cutover_lock(schema_editor.connection):
        _verify(registry, schema_editor)


def _verify(registry, schema_editor):
    alias = schema_editor.connection.alias
    Push = registry.get_model("notifications", LEGACY)
    Mapping = registry.get_model("integrations", "NotificationLegacyMapping")
    gate = registry.get_model("integrations", "NotificationCutover").objects.using(alias).get(pk=1)
    if not Push.objects.using(alias).exists():
        return
    if not gate.snapshot.get("_push_copy_complete") or Push.objects.using(alias).filter(envelope_delivery=None).exists():
        raise RuntimeError("Every push row must have a mapped parent before constraints")
    for row in Push.objects.using(alias).select_related("envelope_delivery").iterator(chunk_size=500):
        mapped = Mapping.objects.using(alias).filter(legacy_model=LEGACY, legacy_id=row.pk,
            canonical_model=LEGACY, canonical_id=row.pk).exists()
        if not mapped or row.envelope_delivery.channel != "native_push" or not row.envelope_delivery.historical:
            raise RuntimeError("Push mapping/parent is incomplete or dispatchable")
        if row.status not in TERMINAL | {"held"} or row.retryable:
            raise RuntimeError("Dispatchable legacy push child remains")
    if gate.snapshot.get("_push"):
        assert_snapshot(registry, alias, gate.snapshot["_push"])
