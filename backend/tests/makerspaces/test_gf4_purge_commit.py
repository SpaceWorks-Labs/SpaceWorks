"""Storage cleanup never inherits the presentation or caller's row transaction."""
from contextlib import contextmanager

import pytest
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.makerspaces.models import Makerspace
from apps.makerspaces import module_purge, lifecycle_purge

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("whole_tenant", [False, True])
def test_purge_storage_is_deferred_until_every_database_transaction_commits(monkeypatch, whole_tenant):
    tenant = Makerspace.objects.create(name="Purge commit", slug="purge-commit", enabled_modules=[],
        archived_at=timezone.now() if whole_tenant else None)
    actor = User.objects.create_superuser(username="purge-commit-operator")
    active = []
    calls = []
    @contextmanager
    def source_scope(*args, **kwargs):
        with transaction.atomic():
            active.append(True)
            try:
                yield
            finally:
                active.pop()
    def cleanup(*args, **kwargs):
        assert not active and not connection.in_atomic_block
        calls.append(True)
        return set()
    target = lifecycle_purge if whole_tenant else module_purge
    monkeypatch.setattr(target, "presentation_purge_scope", source_scope)
    if whole_tenant:
        from apps.makerspaces import lifecycle
        monkeypatch.setattr(lifecycle, "_delete_storage_keys", cleanup)
        monkeypatch.setattr(lifecycle, "_delete_public_image_keys", cleanup)
        monkeypatch.setattr(lifecycle_purge, "_delete_object_graph", lambda *args: None)
    else:
        monkeypatch.setattr(module_purge, "_delete_private_keys", cleanup)
        monkeypatch.setattr(module_purge, "_delete_public_images_and_free_storage", cleanup)
        monkeypatch.setattr(module_purge, "_purge", lambda *args: {})
    with transaction.atomic():
        if whole_tenant:
            lifecycle_purge.purge(tenant, actor)
        else:
            module_purge.purge_module(tenant, "membership", actor)
        assert calls == []
    assert len(calls) == 2


def test_missing_events_app_does_not_import_models_or_block_core_purge_scope(monkeypatch):
    from apps.events.profile_photos import purge_scope
    lookups = []
    original = purge_scope.apps.get_model
    def absent(app_label, model_name, *args, **kwargs):
        lookups.append((app_label, model_name))
        if app_label == "events":
            raise LookupError("Events is tombstoned")
        return original(app_label, model_name, *args, **kwargs)
    monkeypatch.setattr(purge_scope.apps, "get_model", absent)
    with purge_scope.presentation_purge_scope(123):
        assert not connection.in_atomic_block
    assert lookups == [("events", "EventMemberPresentation")]
