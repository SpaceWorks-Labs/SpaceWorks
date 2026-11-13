"""Ordinary domain tests exercise an explicitly activated deployment, as before cutover."""
import pytest
from django.utils import timezone


@pytest.fixture(autouse=True)
def activated_notification_deployment(request):
    if not request.node.get_closest_marker("django_db") or "receipt_only_cutover" in request.fixturenames:
        return
    request.getfixturevalue("db")
    from apps.integrations.models_cutover import NotificationCutover
    now = timezone.now()
    NotificationCutover.objects.update_or_create(pk=1, defaults={"route": "canonical", "sending_enabled": True,
        "barrier_at": now, "copied_at": now, "reconciled_at": now, "activated_at": now})


@pytest.fixture
def receipt_only_cutover(db):
    from apps.integrations.models_cutover import NotificationCutover
    row, _ = NotificationCutover.objects.update_or_create(pk=1, defaults={"route": "receipt_only",
        "sending_enabled": False, "barrier_at": None, "copied_at": None,
        "reconciled_at": None, "activated_at": None, "snapshot": {}})
    return row
