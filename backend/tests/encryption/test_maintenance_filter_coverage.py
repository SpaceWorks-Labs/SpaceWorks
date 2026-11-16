"""Every registered PII model has a valid, tenant-bound maintenance path."""

from datetime import timedelta

import pytest
from django.apps import apps
from django.core.management import call_command
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.encryption.crypto import is_envelope
from apps.encryption.management.commands.backfill_scoped_pii import FILTERS
from apps.encryption.management.commands.decrypt_scoped_pii import _FILTERS
from apps.encryption.registry import fields_for_label, registered_labels
from apps.encryption.write_fence import close_global, reopen
from apps.events.models import Event, EventBroadcast
from apps.makerspaces.models import Makerspace
from tests.encryption.conftest import enabled_encryption


def test_both_commands_cover_the_entire_registered_model_set():
    assert set(FILTERS) == set(registered_labels())
    assert set(_FILTERS) == set(registered_labels())


@pytest.mark.parametrize("label", registered_labels())
def test_command_filters_match_registered_tenant_relationships(label):
    paths = {field.makerspace_path.replace(".", "__") for field in fields_for_label(label)}
    assert len(paths) == 1
    path = paths.pop()
    assert FILTERS[label] == {path: None}
    assert _FILTERS[label] == path
    # Resolving the ORM lookup catches invalid relationships without running SQL.
    apps.get_model(label).objects.filter(**{path: 1})


def make_campaign(slug):
    tenant = Makerspace.objects.create(name=slug, slug=slug)
    start = timezone.now() + timedelta(days=1)
    event = Event.objects.create(
        makerspace=tenant, title=slug, starts_at=start, ends_at=start + timedelta(hours=1),
    )
    return tenant, EventBroadcast.objects.create(
        makerspace=tenant, event=event, subject="Campaign subject", body="Campaign body",
    )


def raw_content(row):
    return EventBroadcast.objects.values_list("subject", "body").get(pk=row.pk)


@pytest.mark.django_db
def test_event_campaign_backfill_and_rollback_are_tenant_scoped():
    tenant, campaign = make_campaign("pii-campaign")
    other_tenant, other = make_campaign("other-pii-campaign")
    actor = User.objects.create_superuser(username="campaign-pii-operator", is_active=True, is_superuser=True)
    plain = ("Campaign subject", "Campaign body")
    with enabled_encryption():
        call_command("backfill_scoped_pii", makerspace=tenant.pk,
                     model="events.EventBroadcast", dry_run=True)
        assert raw_content(campaign) == plain
        call_command("backfill_scoped_pii", makerspace=tenant.pk,
                     model="events.EventBroadcast", batch_size=1)
        assert all(is_envelope(value) for value in raw_content(campaign))
        assert raw_content(other) == plain
        campaign.refresh_from_db()
        assert (campaign.subject, campaign.body) == plain
        call_command("backfill_scoped_pii", makerspace=other_tenant.pk,
                     model="events.EventBroadcast", batch_size=1)
        other_encrypted = raw_content(other)
        assert all(is_envelope(value) for value in other_encrypted)
        operation = close_global("decrypt_rollback", actor.pk, all_makerspaces=True)
        try:
            call_command("decrypt_scoped_pii", makerspace=tenant.pk,
                         model="events.EventBroadcast", actor_id=actor.pk, dry_run=True)
            assert all(is_envelope(value) for value in raw_content(campaign))
            call_command("decrypt_scoped_pii", makerspace=tenant.pk,
                         model="events.EventBroadcast", actor_id=actor.pk, batch_size=1,
                         confirm_makerspace=tenant.pk, fence_operation=str(operation))
            assert raw_content(campaign) == plain
            assert raw_content(other) == other_encrypted
            call_command("decrypt_scoped_pii", makerspace=tenant.pk,
                         model="events.EventBroadcast", actor_id=actor.pk, verify_only=True)
        finally:
            reopen(operation, actor.pk)
    assert AuditLog.objects.filter(
        action="encryption.scoped_pii_decrypted", makerspace=tenant,
        meta__model="events.EventBroadcast",
    ).exists()
