"""Operator cancellation preserves unknown acceptance; it never releases quota."""
import hashlib
import json
import re

from django.conf import settings
from django.db import transaction

from apps.audit.services import record
from .tick_locks import task_guard

DECISION = "cancel_unknown_without_replay_or_release"


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _model(kind):
    from django.apps import apps
    labels = {"personal": "NotificationDelivery", "channel": "NotificationDeliveryLog", "legacy": "NotificationEnvelope"}
    if kind not in labels:
        raise ValueError("unsupported_cancellation_kind")
    return apps.get_model("integrations", labels[kind])


def _bindings(kind, row):
    if kind == "personal":
        envelope = row.envelope
        source = {"maker": row.makerspace_id, "recipient": envelope.recipient_id,
            "envelope": envelope.pk, "source_kind": envelope.source_kind, "source_id": envelope.source_id,
            "revision": envelope.revision, "context": envelope.context, "body": envelope.message_body}
        config = {"channel": row.channel, "provider": row.provider, "endpoint": row.endpoint_id,
            "generation": row.integration_generation, "identity": row.integration_identity}
        attempt = row.attempt_count
    elif kind == "channel":
        source = {"maker": row.makerspace_id, "feature": row.feature, "event": row.event,
                  "payload": row.payload, "body": row.text_body}
        config = {"channel": row.channel, "destination": row.destination_id, "label": row.destination_label}
        attempt = row.attempts
    else:
        source = {"maker": row.makerspace_id, "source_kind": row.source_kind,
            "source_id": row.source_id, "revision": row.revision, "context": row.context,
            "body": row.message_body, "dedup_key": row.dedup_key}
        config, attempt = {"scope": row.scope}, 0
    return {"version": 1, "kind": kind, "id": str(row.pk), "attempt": attempt,
            "source_sha256": _digest(source), "configuration_sha256": _digest(config)}


def describe(actor, kind, object_id):
    from apps.operations.cloud_quotas.operator import require_operator
    require_operator(actor)
    if settings.SPACEWORKS_DEPLOYMENT_MODE != "managed" or settings.SPACEWORKS_DEPLOYMENT_PROFILE != "free":
        raise ValueError("free_managed_profile_required")
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    from apps.encryption.write_fence import assert_mapped_write_allowed
    model = _model(kind)
    maker_id = model.objects.values_list("makerspace_id", flat=True).get(pk=object_id)
    with transaction.atomic():
        assert_write_allowed(maker_id)
        assert_mapped_write_allowed(maker_id)
        result = _bindings(kind, model.objects.get(pk=object_id, makerspace_id=maker_id))
    return {**result, "decision": "REVIEW_REQUIRED"}


def validate(actor, evidence):
    required = {"version", "kind", "id", "attempt", "source_sha256", "configuration_sha256", "decision"}
    if (not isinstance(evidence, dict) or set(evidence) != required or evidence["decision"] != DECISION
            or type(evidence["version"]) is not int or type(evidence["attempt"]) is not int
            or evidence["attempt"] < 0 or not isinstance(evidence["id"], str)):
        raise ValueError("explicit_terminal_cancellation_required")
    for key in ("source_sha256", "configuration_sha256"):
        if not isinstance(evidence[key], str) or re.fullmatch("[0-9a-f]{64}", evidence[key]) is None:
            raise ValueError("cancellation_binding_digest_invalid")
    expected = describe(actor, evidence["kind"], evidence["id"])
    expected["decision"] = DECISION
    if expected != evidence:
        raise ValueError("cancellation_attempt_or_binding_changed")


def cancel(actor, evidence):
    from apps.operations.cloud_quotas.operator import require_operator
    actor = require_operator(actor)
    validate(actor, evidence)
    from apps.backup.cloud_continuity import current_operation
    from apps.backup.managed.models import ManagedCaptureState
    from apps.backup.managed.writers import assert_capture_drained
    operation = current_operation()
    capture = ManagedCaptureState.objects.get(pk=1)
    if operation is None or capture.paused_by is None:
        raise ValueError("proved_writer_drain_required")
    assert_capture_drained(capture.paused_by, operation)
    with task_guard("notification-contract-outbox", 10) as guard:
        if guard is None:
            raise ValueError("outbox_task_still_active")
        with transaction.atomic():
            kind = evidence["kind"]
            from apps.tenant_migration.gate_runtime import assert_write_allowed
            from apps.encryption.write_fence import assert_mapped_write_allowed
            model = _model(kind)
            maker_id = model.objects.values_list("makerspace_id", flat=True).get(pk=evidence["id"])
            assert_write_allowed(maker_id)
            assert_mapped_write_allowed(maker_id)
            row = model.objects.select_for_update().get(pk=evidence["id"], makerspace_id=maker_id)
            expected = _bindings(kind, row)
            if any(evidence[key] != value for key, value in expected.items()):
                raise ValueError("cancellation_attempt_or_binding_changed")
            guard.check()
            assert_capture_drained(capture.paused_by, operation)
            if kind == "personal":
                if row.state in {"accepted", "sent", "delivered", "read", "skipped"}:
                    raise ValueError("delivery_already_terminal")
                row.state, row.retryable, row.last_error = "skipped", False, "operator_cancelled_unknown"
                row.claim_until, row.next_attempt_at = None, None
                row.save(update_fields=["state", "retryable", "last_error", "claim_until", "next_attempt_at", "updated_at"])
            elif kind == "channel":
                if row.status not in {"sending", "failed", "pending"}:
                    raise ValueError("delivery_already_terminal")
                row.status, row.error = "skipped", "operator_cancelled_unknown"
                row.save(update_fields=["status", "error", "updated_at"])
            else:
                if row.source_kind != "legacy.lifecycle" or row.processed_at is not None:
                    raise ValueError("legacy_intent_not_pending")
                row.context = {**row.context, "free_fanout_state": "operator_cancelled",
                               "cancellation_evidence_sha256": _digest(evidence)}
                row.save(update_fields=["context"])
            record(actor, "cloud.delivery_cancelled", target=row, meta={"kind": kind,
                "delivery_id": str(row.pk), "attempt_count": expected["attempt"],
                "source_sha256": expected["source_sha256"], "configuration_sha256": expected["configuration_sha256"],
                "evidence_sha256": _digest(evidence), "status": "operator_cancelled_unknown"})
            guard.check()
            assert_capture_drained(capture.paused_by, operation)
    return "operator_cancelled_unknown"
