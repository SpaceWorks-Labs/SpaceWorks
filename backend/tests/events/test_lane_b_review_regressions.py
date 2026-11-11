"""Boundary findings from the Lane B review are pinned by behavioral regressions."""

import pytest
from django.db import transaction
from django.utils import timezone
from icalendar import Calendar

from apps.events import notifications, services
from apps.events.invites import create_invite
from apps.events.promos import create_promo
from apps.events.serializers_registration_admin import EventRegistrationAdminSerializer
from apps.events.services_calendar import render_public_event_calendar, render_public_series_calendar
from apps.events.services_clone import duplicate_event
from apps.events.services_registration_tools import restore_registration
from apps.integrations import notify
from apps.integrations.models import NotificationPreference
from apps.integrations.models_recipients import NotificationRecipient
from apps.makerspaces.models import MakerspaceMembership, MakerspaceRole
from apps.makerspaces.resource_clone import OwnedImage, clone_transaction
from apps.inventory import public_image_storage
from apps.operations.cancellation_restore import RestoreRefused
from tests.events.collab_helpers import make_staff
from tests.events.lane_b_helpers import fake_storage
from tests.events.ticketing_helpers import account, event_space, open_event
from tests.events.test_lane_b_clone import attach_source_series

pytestmark = pytest.mark.django_db


def scenario():
    space = event_space("lane-b-review")
    staff, owner = make_staff(space), account("review-owner")
    event = open_event(space)
    row = services.register(event, member=owner, actor=staff, staff_registration=True)
    return space, staff, owner, event, row


def test_changed_invitation_audience_cannot_restore_an_originally_public_admission():
    _, staff, _, event, row = scenario()
    cancelled = services.cancel_registration(row, actor=staff)
    event.registration_audience = "invite"; event.save(update_fields=["registration_audience"])
    with pytest.raises(RestoreRefused) as failure:
        restore_registration(cancelled, actor=staff)
    assert str(failure.value.detail["code"]) == "invite_required"
    assert EventRegistrationAdminSerializer(cancelled).data["restore_until"] is None


@pytest.mark.parametrize("kind", ["invite", "promo"])
def test_original_code_consumption_survives_free_reregistration_that_clears_quote_fks(kind):
    _, staff, owner, event, row = scenario()
    services.cancel_registration(row, actor=staff)
    if kind == "invite":
        consumed, code = create_invite(event, actor=staff)
        credential = {"invite_code": code}
        event.registration_audience = "invite"; event.save(update_fields=["registration_audience"])
    else:
        consumed, code = create_promo(event, actor=staff, percent_off=100)
        credential = {"promo_code": code}
    with_code = services.register(event, member=owner, actor=staff, staff_registration=True, **credential)
    assert (with_code.invite_id if kind == "invite" else with_code.promo_code_id) == consumed.pk
    services.cancel_registration(with_code, actor=staff)
    event.registration_audience = "accounts"; event.save(update_fields=["registration_audience"])
    clean_quote = services.register(event, member=owner, actor=staff, staff_registration=True)
    assert clean_quote.pk == row.pk and clean_quote.invite_id is None and clean_quote.promo_code_id is None
    cancelled = services.cancel_registration(clean_quote, actor=staff)
    with pytest.raises(RestoreRefused) as failure:
        restore_registration(cancelled, actor=staff)
    assert str(failure.value.detail["code"]) == "consumed_code"
    assert EventRegistrationAdminSerializer(cancelled).data["restore_until"] is None
    consumed.refresh_from_db(); assert consumed.uses == 1


@pytest.mark.django_db(transaction=True)
def test_post_commit_callback_failure_does_not_cleanup_committed_clone_assets(monkeypatch):
    space = event_space("review-clone-commit")
    key, objects, _, deleted = fake_storage(monkeypatch, space)

    def fail():
        raise RuntimeError("callback failed after commit")

    with pytest.raises(RuntimeError, match="after commit"):
        with clone_transaction() as assets:
            copied = assets.copy_image(space, OwnedImage(source_key=key, source_prefix=f"event/{space.pk}/",
                destination_prefix=f"event/{space.pk}/", max_bytes=1000), storage=public_image_storage)
            transaction.on_commit(fail)
    assert copied in objects and key in objects and deleted.call_count == 0
    space.refresh_from_db(); assert space.storage_bytes_used == 123


@pytest.mark.django_db(transaction=True)
def test_attached_duplicate_has_a_fresh_ics_identity_and_draft_does_not_leak_into_public_series():
    space, staff, _, event, _ = scenario()
    series = attach_source_series(event, space)
    series.is_public = True; series.save(update_fields=["is_public"])
    clone = duplicate_event(event, actor=staff, attach_series=True)
    standalone = Calendar.from_ical(render_public_event_calendar(clone)).walk("VEVENT")
    assert len(standalone) == 1 and standalone[0]["uid"] == f"event-{clone.calendar_uid}@spaceworks"
    assert "recurrence-id" not in standalone[0] and "rrule" not in standalone[0]
    draft_feed = Calendar.from_ical(render_public_series_calendar(series)).walk("VEVENT")
    assert len(draft_feed) == 1 and clone.title not in str(draft_feed)
    clone.series_override_fields = []; clone.save(update_fields=["series_override_fields"])
    services.publish(clone, actor=staff)
    public_feed = Calendar.from_ical(render_public_series_calendar(series)).walk("VEVENT")
    extra = [row for row in public_feed if str(row["uid"]) == f"event-{clone.calendar_uid}@spaceworks"]
    assert len(extra) == 1 and "recurrence-id" not in extra[0] and "rrule" not in extra[0]
    services.cancel(clone, actor=staff)
    series.revision += 1; series.save(update_fields=["revision"])
    revised_feed = Calendar.from_ical(render_public_series_calendar(series)).walk("VEVENT")
    cancellation = [row for row in revised_feed if str(row["uid"]) == f"event-{clone.calendar_uid}@spaceworks"]
    assert len(cancellation) == 1 and str(cancellation[0]["status"]) == "CANCELLED"
    assert "recurrence-id" not in cancellation[0]


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("cancelled", [False, True])
@pytest.mark.parametrize("new_revision", [False, True])
def test_published_copy_made_private_emits_sanitized_independent_cancellation(cancelled, new_revision):
    from datetime import timedelta

    space, staff, _, event, _ = scenario()
    series = attach_source_series(event, space)
    series.is_public, series.status = True, "published"
    series.calendar_sequence = 4
    series.description, series.location = "Public series description", "Public series venue"
    series.save(update_fields=["is_public", "status", "description", "location", "calendar_sequence"])
    clone = services.publish(duplicate_event(event, actor=staff, attach_series=True), actor=staff)
    uid = f"event-{clone.calendar_uid}@spaceworks"
    published = Calendar.from_ical(render_public_series_calendar(series)).walk("VEVENT")
    original = next(row for row in published if str(row["uid"]) == uid)
    assert str(original["status"]) == "CONFIRMED"
    private_start = clone.starts_at + timedelta(days=3)
    clone = services.update_event(clone, actor=staff, is_public=False,
        title="Private copy sentinel", description="Private copy description sentinel",
        location="Private copy venue sentinel", starts_at=private_start,
        ends_at=private_start + timedelta(hours=2))
    if cancelled:
        services.cancel(clone, actor=staff)
    if new_revision:
        series.revision += 1
        series.save(update_fields=["revision"])
    payload = render_public_series_calendar(series)
    components = Calendar.from_ical(payload).walk("VEVENT")
    cancellations = [row for row in components if str(row["uid"]) == uid]
    assert len(cancellations) == 1
    hidden = cancellations[0]
    assert str(hidden["status"]) == "CANCELLED" and hidden["sequence"] > original["sequence"]
    assert "recurrence-id" not in hidden and "rrule" not in hidden
    assert hidden["summary"] == series.title
    assert hidden["description"] == series.description and hidden["location"] == series.location
    assert hidden.decoded("dtstart") == components[0].decoded("dtstart")
    assert hidden.decoded("dtend") == components[0].decoded("dtend")
    assert b"Private copy" not in payload and hidden.decoded("dtstart") != private_start
    if not cancelled:
        services.update_event(clone, actor=staff, is_public=True)
        visible = Calendar.from_ical(render_public_series_calendar(series)).walk("VEVENT")
        restored = next(row for row in visible if str(row["uid"]) == uid)
        assert str(restored["status"]) == "CONFIRMED" and restored["sequence"] > hidden["sequence"]


@pytest.mark.parametrize("restriction", ["staff_selection", "revoked_membership", "membership_optout"])
def test_restored_owner_email_honors_recipient_selection_and_membership_eligibility(restriction, monkeypatch):
    space, staff, owner, event, row = scenario()
    owner.email_verified_at = timezone.now(); owner.save(update_fields=["email_verified_at"])
    if restriction == "staff_selection":
        NotificationRecipient.objects.create(makerspace=space, feature="events", event="registration_restored",
                                             kind="user", user=staff)
    else:
        membership = MakerspaceMembership.objects.create(makerspace=space, user=owner, role="custom",
            assigned_role=MakerspaceRole.objects.get(makerspace=space, slug="member"))
        if restriction == "revoked_membership":
            membership.status = "revoked"; membership.save(update_fields=["status"])
        else:
            membership.receives_notifications = False; membership.save(update_fields=["receives_notifications"])
    NotificationPreference.objects.create(makerspace=space, feature="events", channel="email", enabled=True)
    deliveries = []

    def record(**kwargs):
        deliveries.append(kwargs)
        from types import SimpleNamespace
        return SimpleNamespace(status="sent")

    monkeypatch.setattr(notify, "dispatch_email", record)
    notifications.notify_event_lifecycle(event, "registration_restored", row.pk, sync=True)
    assert all(delivery["to_email"] != owner.email for delivery in deliveries)
