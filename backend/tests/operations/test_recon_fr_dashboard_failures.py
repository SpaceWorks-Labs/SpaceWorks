"""Retained staff push children and pre-device failures contribute exactly once."""
import uuid

import pytest
from django.utils import timezone

from apps.accounts.models import NativeAppRegistration
from apps.integrations.models import EmailLog, NotificationDeliveryLog, PushDevice
from apps.integrations.models_tracking import PushDeliveryAttempt
from apps.operations.platform_dashboard import build_platform_dashboard
from tests.accounts.account_factories import device_grant
from tests.operations.reconciliation_report_helpers import delivery, report_space
from tests.return_helpers import make_member

pytestmark = pytest.mark.django_db


def staff_push_log(space, *, status="failed", outcomes=()):
    log = NotificationDeliveryLog.objects.create(makerspace=space, channel="native_push",
        feature="bookings", event="confirmed", text_body="PRIVATE BODY", status=status)
    if not outcomes:
        return log
    user = make_member("fr-staff-" + uuid.uuid4().hex, space)
    registration, _ = NativeAppRegistration.objects.get_or_create(makerspace=None,
        app_id="fr.staff", platform="android", environment="development",
        defaults={"verifier_config_key": "test", "status": "approved"})
    for outcome in outcomes:
        # device_grant() supplies the MFA a native staff grant requires (DB-enforced).
        grant = device_grant(user, registration, signing_identity="fr-signer",
            attestation_subject_fingerprint=uuid.uuid4().hex * 2)
        device = PushDevice.objects.create(makerspace=space, user=user, device_grant=grant, provider="fcm",
            environment="development", token_ciphertext="PRIVATE TOKEN", token_fingerprint=uuid.uuid4().hex * 2)
        PushDeliveryAttempt.objects.create(delivery_log=log, push_device=device, recipient=user,
            status=outcome, platform="android", provider_source="platform")
    return log


def test_dashboard_counts_device_failures_and_parent_fallback_without_double_counting(monkeypatch):
    space = report_space("fr-dashboard")
    # A failing parent with two failed devices is two failures, not three.
    staff_push_log(space, outcomes=("failed", "failed", "sent", "skipped", "pending", "sending"))
    # Invalid-token device failures may leave the parent sent rather than failed.
    sent = staff_push_log(space, status="sent", outcomes=("failed",))
    PushDeliveryAttempt.objects.filter(delivery_log=sent).update(last_error="invalid_token")
    staff_push_log(space)  # Provider/configuration error before the first device row.
    staff_push_log(space, outcomes=("sent",))  # Stale failed parent must not add a failure.
    NotificationDeliveryLog.objects.create(makerspace=space, channel="telegram", feature="bookings",
        event="confirmed", text_body="PRIVATE ROOM", status="failed")
    delivery(space, state="failed", channel="telegram")
    delivery(space, state="failed", channel="email")  # Email's physical ledger owns this failure.
    EmailLog.objects.create(makerspace=space, to_email="PRIVATE@example.test", subject="PRIVATE", status="failed")
    delivery(space, state="skipped", channel="native_push")  # Deliberate staff compatibility skip.

    archived = report_space("fr-dashboard-archived")
    staff_push_log(archived, outcomes=("failed",))
    type(archived).objects.filter(pk=archived.pk).update(archived_at=timezone.now())
    monkeypatch.setattr("apps.operations.platform_dashboard.usage_snapshot", lambda _: {"resources": []})

    result = build_platform_dashboard()

    assert result["failed_deliveries"] == {"email": 1, "notifications": 6}
    assert [row["id"] for row in result["tenants"]] == [space.pk]
    assert "PRIVATE" not in str(result)
