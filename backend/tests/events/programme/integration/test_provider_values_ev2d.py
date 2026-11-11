from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.http import Http404
from django.utils import timezone

from apps.events.contributions.models_roles import EventGrantEntitlement, EventRoleAssignment
from apps.events.judging.provider_runtime import JudgingProviders
from apps.events.contracts.providers import ReadPurpose
from apps.events.contracts.read_registration import AssetPolicy
from tests.events.staff_grant_helpers import grant_fixture


@pytest.mark.django_db
def test_judge_value_uses_live_source_instead_of_cached_permission_union():
    space, manager, member, event, grant = grant_fixture("judge")
    # A live role source needs its approving issuer, matching tracks and the programme feature.
    space.enabled_features = sorted({*(space.enabled_features or []), "events.hackathons"})
    space.save(update_fields=["enabled_features"])
    role = EventRoleAssignment.objects.create(event=event, makerspace=space, member=member,
        role="judge", state="approved", track_ids=[12], approved_by=manager)
    provider = JudgingProviders()
    assert not provider.judge(role.pk).active
    source = EventGrantEntitlement.objects.create(event=event, makerspace=space, grant=grant, source_kind="role",
        role_assignment=role, permissions=["judge"], track_ids=[12], created_by=manager,
        valid_until=timezone.now()+timedelta(hours=1))
    value = provider.judge(role.pk)
    assert value.active and value.track_ids == (12,)
    source.valid_until = timezone.now()-timedelta(seconds=1)
    source.save(update_fields=["valid_until"])
    assert not provider.judge(role.pk).active
    assert grant.permissions == ["judge"]


@pytest.mark.django_db
def test_numeric_public_reader_denies_without_exact_opaque_entry_callback(monkeypatch):
    _, _, _, event, _ = grant_fixture()
    from apps.events.contracts import read_registration
    monkeypatch.setattr(read_registration, "runtime", lambda: SimpleNamespace(require_programme=lambda *a, **kw: None))
    with pytest.raises(Http404):
        AssetPolicy().require(actor_id=None, asset=SimpleNamespace(event_id=event.pk),
                              snapshot_id=1, purpose=ReadPurpose.PUBLIC_GALLERY)
