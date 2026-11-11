"""Clones retain declared configuration and never share deletable assets or participation."""

from datetime import time

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.events import services_clone
from apps.events.models import (
    Event, EventAttendanceCertificate, EventFeedbackResponse, EventFeedbackSurvey,
    EventInvite, EventPromoCode, EventSeries, EventStaffGrant, EventTicketType,
)
from apps.events.services_clone import duplicate_event
from apps.events.services_registration import register
from apps.makerspaces.models import MakerspaceMembership
from tests.events.collab_helpers import client_for
from tests.events.lane_b_helpers import fake_storage
from tests.events.staff_grant_helpers import grant_fixture
from tests.events.ticketing_helpers import account

pytestmark = pytest.mark.django_db(transaction=True)

QUESTIONS = [{"id": "comment", "label": "Your feedback", "type": "paragraph", "options": [], "required": False}]


@pytest.mark.parametrize("role", ["space_manager", "event_manager"])
def test_clone_copies_configuration_fresh_tokens_assets_and_declared_children_only(monkeypatch, role):
    space, manager, grantee, source, grant = grant_fixture("edit_details")
    membership = MakerspaceMembership.objects.get(user=manager, makerspace=space)
    membership.role = role
    membership.assigned_role = space.roles.get(slug=role)
    membership.save(update_fields=["role", "assigned_role"])
    key, objects, copied, deleted = fake_storage(monkeypatch, space)
    source.image_key = key
    source.custom_form = QUESTIONS
    source.badge_template = {"version": 1, "fields": ["name", "event_title"]}
    source.show_registration_count = False
    source.save(update_fields=["image_key", "custom_form", "badge_template", "show_registration_count"])
    ticket = EventTicketType.objects.create(makerspace=space, event=source, name="Public", capacity=10, amount=0)
    register(source, member=account("clone-owner"), actor=manager, staff_registration=True,
             ticket_type_id=ticket.pk, custom_answers={"comment": "Private registration answer"})
    EventInvite.objects.create(makerspace=space, event=source, max_uses=10, uses=3)
    EventPromoCode.objects.create(makerspace=space, event=source, percent_off=10, max_uses=10, uses=2)
    survey = EventFeedbackSurvey.objects.create(event=source, title="Closed review", questions=QUESTIONS)
    EventFeedbackResponse.objects.create(survey=survey, answers_snapshot='{"version":1,"answers":[]}', certificate_requested=False)

    response = client_for(manager).post(f"/api/v1/admin/events/{source.pk}/duplicate/", {}, format="json")

    assert response.status_code == 201, response.data
    clone = Event.objects.get(pk=response.data["id"])
    assert clone.status == "draft" and clone.title == source.title + " (copy)"
    assert clone.series_id is None and clone.public_token != source.public_token
    assert clone.calendar_uid != source.calendar_uid and clone.created_by == manager
    assert clone.custom_form == source.custom_form and clone.badge_template == source.badge_template
    assert not clone.show_registration_count
    assert clone.image_key != source.image_key and objects[clone.image_key] == objects[key]
    assert clone.image_key.startswith(f"event/{space.pk}/") and copied.call_count == 1
    assert deleted.call_count == 0
    space.refresh_from_db(); assert space.storage_bytes_used == 123
    child = clone.ticket_types.get()
    assert child.pk != ticket.pk and (child.name, child.capacity, child.amount) == (ticket.name, ticket.capacity, ticket.amount)
    assert not clone.registrations.exists() and not clone.invites.exists() and not clone.promo_codes.exists()
    assert not EventStaffGrant.objects.filter(event=clone).exists()
    assert not EventAttendanceCertificate.objects.filter(registration__event=clone).exists()
    assert clone.feedback_survey.questions == survey.questions and not clone.feedback_survey.is_open
    assert not clone.feedback_survey.responses.exists()
    log = AuditLog.objects.get(action="event.duplicated")
    assert log.actor == manager and log.meta == {"source_event_id": source.pk}
    assert "Private registration answer" not in str(log.meta)


@pytest.mark.parametrize("permission", ["edit_details", "manage_registrations", "manage_invitations", "check_in", "publish_schedule"])
def test_clone_requires_tenant_management_even_for_edit_details_grant(permission):
    # A standalone draft drops the source grant; it requires tenant create authority.
    _, _, grantee, source, _ = grant_fixture(permission)
    response = client_for(grantee).post(f"/api/v1/admin/events/{source.pk}/duplicate/", {}, format="json")
    assert response.status_code in (403, 404)
    assert Event.objects.count() == 1 and not AuditLog.objects.filter(action="event.duplicated").exists()


def test_open_feedback_is_not_copied():
    _, manager, _, source, _ = grant_fixture()
    EventFeedbackSurvey.objects.create(event=source, title="Open", questions=QUESTIONS, is_open=True)
    clone = duplicate_event(source, actor=manager)
    assert not EventFeedbackSurvey.objects.filter(event=clone).exists()


def attach_source_series(source, space):
    series = EventSeries.objects.create(makerspace=space, title="Weekly", recurrence_timezone="UTC",
        dtstart_local_date=timezone.now().date(), dtstart_local_time=time(12),
        recurrence_rule="FREQ=DAILY;COUNT=2", duration_minutes=60)
    source.series = series; source.series_revision = series.revision; source.series_occurrence_key = "original"
    source.save(update_fields=["series", "series_revision", "series_occurrence_key"])
    return series


def test_series_attachment_is_explicit_and_requires_series_management():
    space, manager, grantee, source, _ = grant_fixture()
    series = attach_source_series(source, space)
    assert duplicate_event(source, actor=manager).series_id is None
    clone = duplicate_event(source, actor=manager, attach_series=True)
    assert clone.series_id == series.pk and clone.series_occurrence_key != source.series_occurrence_key
    response = client_for(grantee).post(f"/api/v1/admin/events/{source.pk}/duplicate/", {"attach_series": True}, format="json")
    assert response.status_code in (403, 404)


@pytest.mark.parametrize("attach_series", [False, True])
@pytest.mark.parametrize("override_image", [False, True])
def test_occurrence_clone_copies_cover_from_its_owner(monkeypatch, attach_series, override_image):
    space, manager, _, source, _ = grant_fixture()
    series = attach_source_series(source, space)
    series_key, objects, copied, deleted = fake_storage(
        monkeypatch, space, f"event-series/{space.pk}/series.png",
    )
    series.image_key = series_key
    series.save(update_fields=["image_key"])
    occurrence_key = f"event/{space.pk}/occurrence.png"
    objects[occurrence_key] = 321
    source.image_key = occurrence_key
    source.series_override_fields = ["image_key"] if override_image else []
    source.save(update_fields=["image_key", "series_override_fields"])

    response = client_for(manager).post(
        f"/api/v1/admin/events/{source.pk}/duplicate/",
        {"attach_series": attach_series}, format="json",
    )

    assert response.status_code == 201, response.data
    clone = Event.objects.get(pk=response.data["id"])
    expected_key = occurrence_key if override_image else series_key
    assert clone.series_id == (series.pk if attach_series else None)
    assert clone.image_key.startswith(f"event/{space.pk}/")
    assert clone.image_key not in (series_key, occurrence_key)
    copied.assert_called_once_with(expected_key, clone.image_key)
    assert objects[clone.image_key] == objects[expected_key]
    if attach_series:
        assert "image_key" in clone.series_override_fields
        assert clone.series_occurrence_key != source.series_occurrence_key
    space.refresh_from_db()
    assert space.storage_bytes_used == objects[expected_key]
    source.refresh_from_db()
    series.refresh_from_db()
    assert source.image_key == occurrence_key and series.image_key == series_key
    assert objects[series_key] == 123 and objects[occurrence_key] == 321
    deleted.assert_not_called()


@pytest.mark.parametrize("attach_series", [False, True])
@pytest.mark.parametrize("foreign_tenant", [False, True])
def test_inherited_cover_rejects_keys_outside_series_namespace(monkeypatch, attach_series, foreign_tenant):
    space, manager, _, source, _ = grant_fixture()
    series = attach_source_series(source, space)
    key = (f"event-series/{space.pk + 999}/foreign.png" if foreign_tenant
           else f"event/{space.pk}/wrong-owner.png")
    _, objects, copied, deleted = fake_storage(monkeypatch, space, key)
    series.image_key = key
    series.save(update_fields=["image_key"])

    response = client_for(manager).post(
        f"/api/v1/admin/events/{source.pk}/duplicate/",
        {"attach_series": attach_series}, format="json",
    )

    assert response.status_code == 400, response.data
    assert Event.objects.count() == 1 and objects == {key: 123}
    space.refresh_from_db()
    assert space.storage_bytes_used == 0
    assert not AuditLog.objects.filter(action="event.duplicated").exists()
    copied.assert_not_called()
    deleted.assert_not_called()


def test_failure_after_copy_rolls_back_quota_and_rows_and_deletes_only_fresh_objects(monkeypatch):
    space, manager, _, source, _ = grant_fixture()
    key, objects, copied, deleted = fake_storage(monkeypatch, space)
    source.image_key = key; source.save(update_fields=["image_key"])

    def fail(*args, **kwargs):
        raise RuntimeError("audit failed")

    monkeypatch.setattr(services_clone, "_audit", fail)
    with pytest.raises(RuntimeError, match="audit failed"):
        duplicate_event(source, actor=manager)
    assert Event.objects.count() == 1 and objects == {key: 123}
    space.refresh_from_db(); assert space.storage_bytes_used == 0
    assert copied.call_count == deleted.call_count == 1
    assert deleted.call_args.args[0] != key


def test_clone_rejects_foreign_image_key_before_storage_copy(monkeypatch):
    space, manager, _, source, _ = grant_fixture()
    _, _, copied, _ = fake_storage(monkeypatch, space)
    source.image_key = f"event/{space.pk + 999}/foreign.png"; source.save(update_fields=["image_key"])
    response = client_for(manager).post(f"/api/v1/admin/events/{source.pk}/duplicate/", {}, format="json")
    assert response.status_code == 400 and copied.call_count == 0
    assert Event.objects.count() == 1
