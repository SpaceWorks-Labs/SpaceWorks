import pytest
from apps.events.models import Event, EventBroadcast, EventBroadcastDelivery
from apps.integrations.models import EmailLog
from apps.tenant_migration.materialization import materialize_tenant
from tests.data_export.portable_helpers import make_space, make_user
from tests.encryption.conftest import enabled_encryption
from tests.tenant_migration.materialization_helpers import portable_import_case

pytestmark = pytest.mark.django_db(transaction=True)


def test_encrypted_campaign_history_roundtrips_inert_without_send_authority():
    def history(space, user, request):
        event = Event.objects.get(makerspace=space, title="Portable workshop")
        campaign = EventBroadcast.objects.create(event=event, makerspace=space, created_by=user,
            subject="Private announcement", body="Private content", statuses=["registered"], status="sending")
        delivery = EventBroadcastDelivery.objects.create(campaign=campaign, recipient=user)
        outbox = EmailLog.objects.create(makerspace=space, recipient=user, to_email=user.email,
            subject="Broadcast", source_kind="event_broadcast", source_id=delivery.pk)
        delivery.outbox = outbox; delivery.save()
        EventBroadcast.objects.create(event=event, makerspace=space, created_by=user,
            subject="Terminal history", body="Done", statuses=["registered"], status="sent")
        return campaign.pk

    with enabled_encryption():
        user = make_user("campaign-roundtrip")
        source = make_space("campaign-roundtrip")
        with portable_import_case(source, user, prepare_source=history) as case:
            case.decide_walk_in(user)
            result = materialize_tenant(case.root, case.job, case.carried,
                                       target_identity={"slug": "campaign-roundtrip-target"})
        imported = EventBroadcast.objects.get(makerspace_id=result.target_makerspace_id, subject__isnull=False,
                                              status="cancelled")
        assert imported.subject == "Private announcement" and imported.body == "Private content"
        assert imported.recipients_complete and imported.recipient_cursor == 0
        delivery = imported.deliveries.get()
        assert delivery.status == "skipped" and delivery.outbox_id is None
        assert not EmailLog.objects.filter(makerspace_id=result.target_makerspace_id, source_kind="event_broadcast").exists()
        terminal = EventBroadcast.objects.get(makerspace_id=result.target_makerspace_id, status="sent")
        assert terminal.subject == "Terminal history"
