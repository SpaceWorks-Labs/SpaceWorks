"""Optional invitation and malformed write-payload regression coverage."""

from datetime import time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.events.invites import create_invite, resolve_for_account
from apps.events.models import EventInvite, EventSeries
from apps.events.serializers_admin import EventWriteSerializer
from apps.events.serializers_series import EventSeriesWriteSerializer
from tests.events.collab_helpers import client_for
from tests.events.organization_audience_helpers import audience_fixture, direct
from tests.events.ticketing_helpers import signup

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("state", ["missing", "expired", "revoked", "exhausted", "other_email"])
def test_verified_eligible_account_can_register_without_usable_optional_invite(state):
    _, orgs, _, event, manager = audience_fixture()
    user = direct(orgs[0])
    user.email_verified_at = timezone.now()
    user.save(update_fields=["email_verified_at"])
    if state != "missing":
        invite, _ = create_invite(event, actor=manager, email=(
            "someone-else@example.test" if state == "other_email" else user.email
        ))
        changes = {
            "expired": {"expires_at": timezone.now() - timedelta(seconds=1)},
            "revoked": {"revoked_at": timezone.now()},
            "exhausted": {"uses": invite.max_uses},
        }.get(state, {})
        if changes:
            EventInvite.objects.filter(pk=invite.pk).update(**changes)
        before_uses = invite.max_uses if state == "exhausted" else 0
    assert resolve_for_account(event, user, actor=user) is None
    response = signup(event, user)
    assert response.status_code == 201, response.data
    row = event.registrations.get()
    assert row.member_id == user.pk and row.invite_id is None
    assert row.status == "registered"
    assert not AuditLog.objects.filter(action="event.invite_consumed").exists()
    assert not AuditLog.objects.filter(action="event.invite_redeemed").exists()
    if state != "missing":
        invite.refresh_from_db()
        assert invite.uses == before_uses


def test_matching_optional_email_invite_is_consumed_and_audited_once_on_registration():
    _, orgs, _, event, manager = audience_fixture()
    user = direct(orgs[0])
    user.email_verified_at = timezone.now()
    user.save(update_fields=["email_verified_at"])
    invite, _ = create_invite(event, actor=manager, email=user.email, max_uses=2)
    for _ in range(2):
        response = signup(event, user)
        assert response.status_code == 201, response.data
    invite.refresh_from_db()
    assert invite.uses == 1
    assert event.registrations.get().invite_id == invite.pk
    entry = AuditLog.objects.get(action="event.invite_consumed")
    assert entry.meta == {"uses": 1}
    assert entry.actor_id == user.pk


@pytest.mark.parametrize("serializer_class", [EventWriteSerializer, EventSeriesWriteSerializer])
@pytest.mark.parametrize("partial", [False, True])
@pytest.mark.parametrize("payload", [[{}], ["title"], 123, 1.5, True, "title", None])
def test_non_mapping_write_payloads_return_drf_validation_errors(serializer_class, partial, payload):
    serializer = serializer_class(data=payload, partial=partial)
    assert not serializer.is_valid()
    assert "non_field_errors" in serializer.errors


@pytest.mark.parametrize("serializer_class", [EventWriteSerializer, EventSeriesWriteSerializer])
def test_mapping_write_payloads_still_reject_unknown_fields(serializer_class):
    serializer = serializer_class(data={"organization_ids": [123]}, partial=True)
    assert not serializer.is_valid()
    assert serializer.errors == {"organization_ids": "Unexpected field."}
    valid = serializer_class(data={"title": "Updated"}, partial=True)
    assert valid.is_valid(), valid.errors
    assert valid.validated_data == {"title": "Updated"}


@pytest.mark.parametrize("payload", [[{}], 123])
@pytest.mark.parametrize("kind", ["event", "series"])
def test_post_and_patch_non_object_json_return_400_without_mutations(payload, kind):
    venue, _, _, event, manager = audience_fixture()
    if kind == "series":
        target = EventSeries.objects.create(
            makerspace=venue, title="Series", recurrence_timezone="UTC",
            dtstart_local_date=timezone.now().date(), dtstart_local_time=time(23),
            recurrence_rule="FREQ=DAILY;COUNT=2", duration_minutes=60,
        )
        list_name, detail_name = "admin-event-series-list-create", "admin-event-series-detail"
    else:
        target = event
        list_name, detail_name = "admin-event-list-create", "admin-event-detail"
    client = client_for(manager)
    before_count = type(target).objects.count()
    before_audits = AuditLog.objects.count()
    for method, path in (
        (client.post, reverse(list_name, kwargs={"makerspace_id": venue.pk})),
        (client.patch, reverse(detail_name, kwargs={"pk": target.pk})),
    ):
        response = method(path, payload, format="json")
        assert response.status_code == 400, response.data
        assert "non_field_errors" in response.data
    assert type(target).objects.count() == before_count
    assert AuditLog.objects.count() == before_audits
    original_title = target.title
    target.refresh_from_db()
    assert target.title == original_title
