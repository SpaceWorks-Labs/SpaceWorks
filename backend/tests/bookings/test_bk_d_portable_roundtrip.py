"""Real encrypted archive -> target import, with inert campaign history."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.bookings.models import BookableSpace, BookingBroadcast
from tests.accounts.account_factories import make_staff
from apps.bookings.services_bookings import create_booking
from apps.bookings.services_broadcasts import compose, change
from apps.integrations.broadcasts_worker import broadcast_batch
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.tenant_migration.materialization import materialize_tenant
from tests.data_export.portable_helpers import make_space, make_user
from tests.encryption.conftest import enabled_encryption
from tests.tenant_migration.materialization_helpers import portable_import_case

pytestmark = pytest.mark.django_db(transaction=True)


def test_campaign_history_round_trips_but_source_send_authority_does_not(monkeypatch):
    monkeypatch.setattr("apps.integrations.dispatch_outbox._enqueue", lambda pk: None)
    monkeypatch.setattr("apps.integrations.broadcasts_worker.enqueue", lambda *args: None)
    monkeypatch.setattr("apps.integrations.quiet_hours.quiet_until", lambda *args: None)
    monkeypatch.setattr("apps.integrations.digests.digest_due", lambda *args: None)
    with enabled_encryption():
        user = make_user("bk-d-roundtrip")
        type(user).objects.filter(pk=user.pk).update(email_verified_at=timezone.now(), phone="123")
        user.refresh_from_db()
        source = make_space("bk-d-roundtrip")
        source.enabled_modules = ["bookings", "notifications", "email"]
        source.enabled_features = ["bookings.broadcasts"]
        source.booking_requester_notifications_enabled = True
        source.save()
        def prepare(tenant, owner, request):
            manager = make_staff(tenant, username="portable-booking-manager", role_slug="space_manager")
            resource = BookableSpace.objects.create(makerspace=tenant, name="Portable resource", approval_mode="instant")
            start = timezone.now()+timedelta(days=2)
            create_booking(resource, actor=manager, member=owner, starts_at=start, ends_at=start+timedelta(hours=1))
            campaign = compose(resource, manager, subject="Notice", body="Private history {{ name }}",
                window_start=timezone.now(), window_end=start+timedelta(days=1))
            change(campaign, manager, "queue")
            broadcast_batch("booking_broadcast", campaign.pk)
            assert campaign.deliveries.count() == 1
            return campaign
        with portable_import_case(source, user, prepare_source=prepare) as case:
            case.decide_walk_in(user)
            case.decide_walk_in(case.source_data.created_by)
            result = materialize_tenant(case.root, case.job, case.carried,
                target_identity={"name": "Imported booking history", "slug": "bk-d-imported"}, batch_size=2)
        target = Makerspace.objects.get(pk=result.target_makerspace_id)
        campaign = BookingBroadcast.objects.get(makerspace=target)
        assert campaign.space.makerspace_id == target.pk
        assert campaign.status == "cancelled" and campaign.recipients_complete
        assert campaign.recipient_cursor == 0 and campaign.body == "Private history {{ name }}"
        delivery = campaign.deliveries.get()
        assert delivery.status == "skipped" and delivery.outbox_id is None
        from apps.makerspaces.models import MakerspaceMembership
        assert campaign.created_by.account_kind == "member"  # one account per person: staff authority is a staff-track row
        assert MakerspaceMembership.staff_tracks.get(makerspace=target, user=campaign.created_by).assigned_role.slug == "space_manager"
        assert campaign.created_by_id != delivery.recipient_id
        assert delivery.recipient_id == target.memberships.get(user__account_kind="member").user_id
        assert not campaign.created_by.has_usable_password()
        assert not target.email_logs.exists()
