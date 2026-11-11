"""Real database tests for G to run AFTER installing models/receipt/PII registries."""

from contextlib import contextmanager
from uuid import uuid4

import pytest
from django.http import Http404
from rest_framework.exceptions import PermissionDenied

from apps.events.judging import ports
from apps.events.judging.definitions_workflow import save_definition
from apps.events.judging.errors import ProgrammeError
from apps.events.judging.models_definitions import HackathonTrack
from tests.events.staff_grant_helpers import grant_fixture


class DefinitionsPorts:
    def require_programme(self, event, **kwargs):
        pass  # This test isolates D's domain writes; G's gate tests exercise its adapter.

    def lock_authority(self, *, actor_id, event):
        from django.contrib.auth import get_user_model
        # The real adapter must additionally lock all role/grant/org sources.
        return get_user_model().objects.get(pk=actor_id)

    @contextmanager
    def fences(self, *, tenant_ids, account_ids):
        from apps.encryption.write_fence import assert_mapped_write_allowed
        for tenant_id in tenant_ids:
            assert_mapped_write_allowed(tenant_id)
        yield


@pytest.mark.django_db
def test_create_retry_stale_and_changed_digest_never_duplicate_a_track(monkeypatch):
    _, manager, _, event, _ = grant_fixture()
    monkeypatch.setattr(ports, "_installed", DefinitionsPorts())
    operation = str(uuid4())
    data = {"operation_id": operation, "expected_version": 0, "name": "Hardware", "capacity": 20}
    first = save_definition(event.pk, actor=manager, kind="tracks", data=data)
    assert save_definition(event.pk, actor=manager, kind="tracks", data=data) == first
    assert HackathonTrack.objects.filter(event=event).count() == 1
    with pytest.raises(ProgrammeError) as error:
        save_definition(event.pk, actor=manager, kind="tracks", data={**data, "name": "Changed"})
    assert error.value.detail["code"] == "idempotency_conflict"
    with pytest.raises(ProgrammeError) as error:
        save_definition(event.pk, actor=manager, kind="tracks", object_id=first["id"],
            data={"operation_id": str(uuid4()), "expected_version": 0, "description": "stale"})
    assert error.value.detail["code"] == "stale_version"
    assert HackathonTrack.objects.get(pk=first["id"]).description == ""


@pytest.mark.django_db
def test_scoped_edit_grant_cannot_manage_judging_definitions(monkeypatch):
    _, _, grantee, event, _ = grant_fixture()
    monkeypatch.setattr(ports, "_installed", DefinitionsPorts())
    with pytest.raises((PermissionDenied, Http404)):
        save_definition(event.pk, actor=grantee, kind="tracks",
                        data={"operation_id": str(uuid4()), "expected_version": 0, "name": "Private"})
    assert not HackathonTrack.objects.filter(event=event).exists()
