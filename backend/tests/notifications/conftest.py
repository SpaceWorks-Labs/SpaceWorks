"""Domain tests opt into an explicitly activated canonical deployment."""
import pytest
from django.utils import timezone


@pytest.fixture(autouse=True)
def activated_push_deployment(request):
    if not request.node.get_closest_marker("django_db") or "push_migration_case" in request.fixturenames:
        return
    request.getfixturevalue("db")
    from apps.integrations.models_cutover import NotificationCutover
    now = timezone.now()
    NotificationCutover.objects.update_or_create(pk=1, defaults={
        "route": "canonical", "sending_enabled": True, "barrier_at": now,
        "copied_at": now, "reconciled_at": now, "activated_at": now})
