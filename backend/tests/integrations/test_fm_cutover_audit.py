"""Cutover state and secret-free checkpoint evidence commit or roll back together."""
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.integrations import notification_cutover as cutover
from .reconciliation_helpers import account

pytestmark = pytest.mark.django_db
SIGNOFFS = {"producer_coverage": True, "push": True, "registries": True}


def audit_rows():
    return AuditLog.objects.filter(action__startswith="notification.cutover_").order_by("pk")


def test_management_checkpoints_capture_operator_and_no_snapshot_secrets(receipt_only_cutover, monkeypatch):
    monkeypatch.setattr("apps.integrations.notification_conversion_snapshot.snapshot", lambda _: {"secret": "DO-NOT-LOG"})
    monkeypatch.setattr("apps.integrations.notification_conversion_snapshot.verify_reconciliation", lambda *args: None)
    operator = account("fm-operator", account_kind="platform", role="superadmin")
    output = StringIO()
    options = {"operator_id": operator.pk, "stdout": output}
    call_command("notification_cutover", "barrier", old_instances_drained=True, **options)
    gate = cutover.state()
    gate.copied_at = timezone.now()
    gate.save(update_fields=["copied_at"])
    call_command("notification_cutover", "route", **options)
    call_command("notification_cutover", "verify", producer_coverage_reviewed=True,
        push_reviewed=True, registries_reviewed=True, **options)
    call_command("notification_cutover", "activate", **options)
    rows = list(audit_rows())
    assert [row.action for row in rows] == ["notification.cutover_" + name for name in
        ("barrier_established", "canonical_routed", "signoffs_recorded", "verified", "activated")]
    assert all(row.actor_id == operator.pk and row.meta["attribution"] == "operator" for row in rows)
    assert rows[2].meta["signoffs"] == SIGNOFFS
    allowed = {"attribution", "route", "sending_enabled", "receipt_watermark", "replay_watermark",
        "old_instances_drained", "signoffs", "receipt_count", "mapping_count"}
    assert all(set(row.meta) <= allowed for row in rows)
    assert "DO-NOT-LOG" not in str([row.meta for row in rows]) + output.getvalue()
    gate.refresh_from_db()
    assert gate.sending_enabled and gate.activated_at
    # An idempotent activation has no second checkpoint transition to audit.
    call_command("notification_cutover", "activate", **options)
    assert audit_rows().count() == 5


def test_omitted_command_operator_records_system_attribution(receipt_only_cutover, monkeypatch):
    monkeypatch.setattr("apps.integrations.notification_conversion_snapshot.snapshot", lambda _: {})
    call_command("notification_cutover", "barrier", old_instances_drained=True, stdout=StringIO())
    row = audit_rows().get()
    assert row.actor_id is None and row.meta["attribution"] == "system"


@pytest.mark.parametrize("stage", ["barrier", "route", "verify", "activate"])
def test_audit_failure_rolls_back_checkpoint(receipt_only_cutover, monkeypatch, stage):
    gate = receipt_only_cutover
    if stage != "barrier":
        gate.barrier_at = gate.copied_at = timezone.now()
    if stage in {"verify", "activate"}:
        gate.route = "canonical"
    if stage == "activate":
        gate.reconciled_at = timezone.now()
    gate.snapshot = {"marker": "original"}
    gate.save()
    before = {field.attname: getattr(gate, field.attname) for field in gate._meta.fields}
    monkeypatch.setattr("apps.integrations.notification_conversion_snapshot.snapshot", lambda _: {})
    monkeypatch.setattr("apps.integrations.notification_conversion_snapshot.verify_reconciliation", lambda *args: None)

    def failed_audit(*args, **kwargs):
        raise ValueError("audit unavailable")

    monkeypatch.setattr("apps.audit.services.record", failed_audit)
    operation = {"barrier": lambda: cutover.establish_barrier(drained=True),
        "route": cutover.switch_to_canonical, "verify": lambda: cutover.verify(signoffs=SIGNOFFS),
        "activate": cutover.activate}[stage]
    with pytest.raises(ValueError, match="audit unavailable"):
        operation()
    gate.refresh_from_db()
    assert {field.attname: getattr(gate, field.attname) for field in gate._meta.fields} == before
    assert not audit_rows().exists()


def test_failed_verification_rolls_back_signoffs_and_emits_no_success(receipt_only_cutover, monkeypatch):
    gate = receipt_only_cutover
    gate.route, gate.copied_at = "canonical", timezone.now()
    gate.save()

    def unresolved(*args):
        raise ValueError("Unresolved authenticated receipts")

    monkeypatch.setattr("apps.integrations.notification_conversion_snapshot.verify_reconciliation", unresolved)
    with pytest.raises(CommandError, match="Unresolved"):
        call_command("notification_cutover", "verify", producer_coverage_reviewed=True,
            push_reviewed=True, registries_reviewed=True, stdout=StringIO())
    gate.refresh_from_db()
    assert "_signoffs" not in gate.snapshot and gate.reconciled_at is None
    assert not audit_rows().exists()


def test_command_refuses_nonoperator_account_for_attribution(receipt_only_cutover):
    user = account()
    with pytest.raises(CommandError, match="active platform superadmin"):
        call_command("notification_cutover", "barrier", old_instances_drained=True,
            operator_id=user.pk, stdout=StringIO())
    assert not audit_rows().exists()
