from types import SimpleNamespace as Bag

import pytest
from django.utils import timezone

from apps.integrations.models import EmailLog
from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.notification_resolution import resolve
from apps.notifications.models_preferences import NotificationPreference

pytestmark = pytest.mark.django_db


def test_direct_mail_reserves_email_and_rechecks_source_on_retry(world, monkeypatch, django_capture_on_commit_callbacks):
    from apps.operations.notifications_p2 import direct_mail_unless_routed, fanout
    from apps.integrations.notification_direct_mail import prepare
    from apps.integrations.delivery_content import content
    from apps.integrations.notification_links import local_link
    from apps.makerspaces.website_directory import public_url
    monkeypatch.setattr("apps.integrations.notification_resolution.source_eligible", lambda _: True)
    own = {"subject": "Welcome", "text": "Membership active", "html": "<p>Membership active</p>",
           "link": local_link(world.space, "member")}
    monkeypatch.setattr("apps.integrations.notification_sources.render", lambda _: own)
    # The owner keeps email on: since w2-notify the direct mail honours a member's email
    # opt-out (a skipped log reserves nothing). The envelope still cannot email yet because
    # the owner's address is unverified, so the direct mail owns the email leg.
    choice = NotificationPreference.objects.create(makerspace=world.space, user=world.owner,
        category="bookings", channels=["in_app", "email"], email_fallback=False)
    with django_capture_on_commit_callbacks(execute=True):
        fanout(row=world.booking, space=world.space, feature="bookings", stream="bookings", event="confirmed",
            source_kind="bookings.lifecycle", revision="0", owner=world.owner, owner_body=own, staff=False)
        direct_mail_unless_routed(space=world.space, source_kind="bookings.lifecycle", row=world.booking,
            revision="0", event="confirmed", owner=world.owner, to_email=world.owner.email,
            subject="Welcome", text="Membership active", stream="bookings", audience="requester", feature="bookings")
    envelope = NotificationEnvelope.objects.get(source_kind="bookings.lifecycle")
    log = EmailLog.objects.get(source_kind="notification.direct", source_id=envelope.pk)
    assert log.status != "skipped", log.error
    world.owner.email_verified_at = timezone.now()
    world.owner.save()
    choice.channels = ["email"]
    choice.save()
    assert not any(target.channel == "email" for target in resolve(envelope))
    assert prepare(log)
    url = public_url(world.space, "member", "").rstrip("/")
    assert url in content(log).text_body and url in content(log).html_body
    world.space.archived_at = timezone.now()
    world.space.save()
    assert not prepare(log)


def test_room_intents_persist_context_needed_for_live_revalidation(world, monkeypatch):
    from apps.operations.notifications_p2 import fanout
    captured = []
    monkeypatch.setattr("apps.integrations.notification_catalog.is_notification_enabled", lambda *_: True)
    monkeypatch.setattr("apps.integrations.dispatch_channels.dispatch_channel", lambda **kwargs: captured.append(kwargs))
    monkeypatch.setattr("apps.integrations.chat_templates.render_chat_text", lambda *args: args[3])
    world.space.staff_notifications_enabled = True
    world.space.save()
    fanout(row=world.booking, space=world.space, feature="bookings", stream="bookings", event="confirmed",
        source_kind="bookings.lifecycle", revision="0", context={"verification_id": 17},
        staff_body={"subject": "Notice", "text": "Summary"})
    assert captured
    for call in captured:
        assert call["payload"]["context"] == {"verification_id": 17}
        assert call["payload"]["source_kind"] == "bookings.lifecycle"
        assert "scope" in call["payload"]


def test_legacy_recovery_keeps_its_source_revision(world, monkeypatch):
    from apps.integrations.notification_legacy import persist, snapshot, recover
    from apps.integrations.notify import LifecyclePayload
    from uuid import uuid4
    source = {"source_kind": "bookings.lifecycle", "source_id": str(world.booking.pk),
              "revision": str(world.booking.calendar_sequence), "context": {}}
    key = uuid4()
    envelope = persist(world.space, "bookings", "confirmed", None, key, timezone.now().isoformat())
    snapshot(envelope, LifecyclePayload("Staff summary", source=source))
    captured = []
    monkeypatch.setattr("apps.integrations.notify._run_guarded", lambda *args: captured.append(args[3]()))
    recover(envelope)
    assert captured[0].source == source


def test_guest_mail_is_removed_by_booking_purge_only(world):
    from apps.makerspaces.module_purge_collectors_single_model import bookings_delete
    log = EmailLog.objects.create(makerspace=world.space, to_email="guest@example.test", subject="Booking",
                                  source_kind="bookings.guest_mailbox")
    other = EmailLog.objects.create(makerspace=world.space, to_email="other@example.test", subject="Other",
                                    source_kind="other.domain")
    bookings_delete(world.space, None)
    assert not EmailLog.objects.filter(pk=log.pk).exists()
    assert EmailLog.objects.filter(pk=other.pk).exists()


@pytest.mark.parametrize("custom", [False, True])
def test_event_campaign_ticket_urls_use_the_registered_via_spaces_route_mode(world, monkeypatch, custom):
    from apps.events import broadcasts
    from apps.makerspaces.website_directory import public_url
    from unittest.mock import Mock
    entry = Bag(pk=7, registered_via_makerspace=world.space)
    if custom:
        world.space.frontend_domain, world.space.frontend_domain_status = "custom.example.test", "verified"
    query = Mock()
    query.filter.return_value.select_related.return_value.order_by.return_value.first.return_value = entry
    monkeypatch.setattr(broadcasts, "registrations", lambda _: query)
    monkeypatch.setattr(broadcasts, "render", lambda subject, body, context: context)
    campaign = Bag(event=Bag(makerspace=world.space, title="Workshop", starts_at=timezone.now(), location="Hall"),
                   subject="Ticket", body="{{ticket_url}}")
    result = broadcasts.render_recipient(campaign, world.owner)
    assert result["ticket_url"] == public_url(world.space, "member", "events/7/ticket")


@pytest.mark.parametrize("custom", [False, True])
def test_printer_email_tracking_uses_the_canonical_route_mode(world, monkeypatch, custom):
    from apps.machines import service_printing_emails as printer
    from apps.makerspaces.website_directory import public_url
    from urllib.parse import urlencode
    if custom:
        world.space.frontend_domain, world.space.frontend_domain_status = "custom.example.test", "verified"
    row = Bag(makerspace=world.space, contact_email=world.owner.email, requester=world.owner, public_token="opaque-token")
    monkeypatch.setattr(printer, "_projection", lambda _: None)
    monkeypatch.setattr(printer, "_request_machine_type", lambda _: None)
    monkeypatch.setattr(printer, "printing_context", lambda _, status_url, token: {"status_url": status_url})
    monkeypatch.setattr(printer, "render", lambda *args, **kwargs: args[4])
    recipient, rendered = printer._requester_render("completed", row)
    assert recipient == world.owner.email
    expected = public_url(world.space, "print", "").rstrip("/") + "?" + urlencode({"token": row.public_token})
    assert rendered["status_url"] == expected
