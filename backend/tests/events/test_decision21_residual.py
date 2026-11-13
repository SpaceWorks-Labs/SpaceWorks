"""Decision 21 residual outcomes the assertion audits left open (#4 show-if, #9 live ticket).

* Show-if: a Space Manager authors a real condition through the form editor routes, previews
  it, and a member then registers through the public route; the condition decides both
  requiredness and what is stored. Module-off removes the editor and the registration.
* Live ticket: the member ticket read the browser polls reflects real desk attendance, the
  QR is served only while it can still admit, and module-off removes both reads.
"""
import base64
import json
from uuid import uuid4

import pytest
from django.urls import reverse

from apps.events.models import EventRegistration
from apps.events.services_checkin import mark_attended
from tests.events.collab_helpers import client_for, make_staff
from tests.events.ticketing_helpers import account, event_space, open_event, public_url

pytestmark = pytest.mark.django_db

CONDITIONAL = {"schema_version": 2, "form_id": "registration", "revision": 1, "questions": [
    {"id": "diet", "type": "single_choice", "label": "Dietary needs", "required": False,
     "options": [{"id": "none", "label": "None"}, {"id": "other", "label": "Other"}]},
    {"id": "diet_note", "type": "long_text", "label": "Tell us more", "required": True,
     "show_if": {"all": [{"field_id": "diet", "op": "eq", "value": "other"}]}},
]}


@pytest.fixture
def credential_keys(settings):
    settings.PII_ENCRYPTION_ENABLED = False
    settings.EVENT_REGISTRATION_CREDENTIAL_KEY_VERSION = 1
    settings.EVENT_REGISTRATION_CREDENTIAL_KEYS = {"1": base64.b64encode(b"q" * 32).decode()}
    settings.EVENT_REGISTRATION_CREDENTIAL_DIGEST_KEY = base64.b64encode(b"h" * 32).decode()


def disable_events(space):
    space.enabled_modules = [key for key in space.enabled_modules if key != "events"]
    space.save(update_fields=["enabled_modules"])


def author_condition(event, manager):
    """Save the conditional form through the editor wire the staff form builder uses."""
    client = client_for(manager)
    form_url = f"/api/v1/admin/events/{event.pk}/forms/registration/"
    current = client.get(form_url)
    assert current.status_code == 200, current.content
    saved = client.put(form_url, {"operation_id": str(uuid4()), "expected_version": current.data["version"],
                                  "schema": CONDITIONAL}, format="json")
    assert saved.status_code == 200, saved.content
    stored = client.get(form_url).data["schema"]
    assert stored["questions"][1]["show_if"] == CONDITIONAL["questions"][1]["show_if"]
    return client, form_url, stored


def register(event, user, answers, date_revision):
    # The saved schema is revision 1 (the first editor save); the date revision is the event's.
    body = {"operation_id": str(uuid4()), "answers": answers, "event_date_revision": date_revision,
            "form": {"schema_version": 2, "form_id": "registration", "revision": 1}}
    return client_for(user).post(public_url(event), body, format="json")


def test_authored_show_if_condition_controls_preview_requiredness_and_stored_answers(credential_keys):
    space = event_space(f"d21-showif-{uuid4().hex[:6]}")
    event, manager = open_event(space), make_staff(space, username="d21-forms")
    client, form_url, stored = author_condition(event, manager)
    assert stored["revision"] == 1

    # The builder preview evaluates the condition without a member submission.
    preview = lambda answers: client.post(f"{form_url}validate/", {"schema": CONDITIONAL, "sample_answers": answers},
                                          format="json")
    shown = preview({"diet": {"option_id": "other"}})
    assert shown.status_code == 200, shown.content
    assert shown.data["visible_question_ids"] == ["diet", "diet_note"]
    hidden = preview({"diet": {"option_id": "none"}})
    assert hidden.data["visible_question_ids"] == ["diet"]

    event.refresh_from_db()
    revision = event.event_date_revision
    # Shown + required: a member who picks "Other" must answer the follow-up.
    refused = register(event, account(f"d21-refused-{uuid4().hex[:6]}"), {"diet": {"option_id": "other"}}, revision)
    assert refused.status_code == 400, refused.content
    assert "diet_note" in json.dumps(refused.data)
    assert not EventRegistration.objects.filter(event=event).exists()

    # Shown + answered: stored with the follow-up.
    detailed = account(f"d21-detailed-{uuid4().hex[:6]}")
    accepted = register(event, detailed, {"diet": {"option_id": "other"}, "diet_note": "No nuts"}, revision)
    assert accepted.status_code == 201, accepted.content
    answers = EventRegistration.objects.get(event=event, member=detailed).custom_answers["answers"]
    assert [row["id"] for row in answers] == ["diet", "diet_note"]

    # Hidden: a stale answer left in the draft is neither required nor stored.
    plain = account(f"d21-plain-{uuid4().hex[:6]}")
    stale = register(event, plain, {"diet": {"option_id": "none"}, "diet_note": "left over"}, revision)
    assert stale.status_code == 201, stale.content
    answers = EventRegistration.objects.get(event=event, member=plain).custom_answers["answers"]
    assert [row["id"] for row in answers] == ["diet"]
    assert "left over" not in json.dumps(answers)


def test_events_module_off_removes_the_form_editor_and_the_registration(credential_keys):
    space = event_space(f"d21-formoff-{uuid4().hex[:6]}")
    event, manager = open_event(space), make_staff(space, username="d21-formoff")
    client, form_url, _ = author_condition(event, manager)
    disable_events(space)
    assert client.get(form_url).status_code in (403, 404)
    assert client.put(form_url, {"operation_id": str(uuid4()), "expected_version": 1, "schema": CONDITIONAL},
                      format="json").status_code in (403, 404)
    member = account(f"d21-offmember-{uuid4().hex[:6]}")
    assert register(event, member, {"diet": {"option_id": "none"}}, 1).status_code == 404
    assert not EventRegistration.objects.filter(event=event).exists()


def test_live_ticket_read_follows_desk_attendance_and_qr_stops_once_it_cannot_admit():
    space = event_space(f"d21-ticket-{uuid4().hex[:6]}")
    event, staff, user = open_event(space), make_staff(space, username="d21-desk"), account(f"d21-holder-{uuid4().hex[:6]}")
    assert client_for(user).post(public_url(event), {}, format="json").status_code == 201
    registration = EventRegistration.objects.get(event=event, member=user)
    owner = client_for(user)
    ticket_url = reverse("member-event-ticket", args=[space.pk, registration.pk])
    qr_url = reverse("member-event-checkin-qr", args=[space.pk, registration.pk])

    before = owner.get(ticket_url)
    assert before.status_code == 200, before.content
    assert (before.data["status"], before.data["attended_at"]) == ("registered", None)
    assert before.data["ticket_png_available"] is True
    assert before["Cache-Control"].startswith("private")
    qr = owner.get(qr_url)
    assert qr.status_code == 200 and qr["Content-Type"] == "image/svg+xml"
    assert qr["Cache-Control"] == "private, no-store"
    mode = before.data["credential_mode"]

    # Another account polling the same URL never sees the ticket or its code.
    outsider = client_for(account(f"d21-outsider-{uuid4().hex[:6]}"))
    assert outsider.get(ticket_url).status_code == 404 and outsider.get(qr_url).status_code == 404

    # The desk checks the holder in; the very next poll shows the torn ticket.
    mark_attended(registration, actor=staff)
    after = owner.get(ticket_url)
    assert after.status_code == 200
    assert after.data["status"] == "attended" and after.data["attended_at"] is not None
    assert after.data["credential_mode"] == mode
    if mode == "legacy":
        # A legacy check-in token admits once; after attendance it is no longer served.
        assert owner.get(qr_url).status_code == 404

    # Events off for the space: both reads disappear instead of serving a stale ticket.
    disable_events(space)
    assert owner.get(ticket_url).status_code == 404
    assert owner.get(qr_url).status_code == 404


def test_cancelled_event_keeps_the_ticket_read_but_withdraws_png_and_qr():
    from apps.events.models import Event
    space = event_space(f"d21-cancel-{uuid4().hex[:6]}")
    event, user = open_event(space), account(f"d21-cancel-holder-{uuid4().hex[:6]}")
    assert client_for(user).post(public_url(event), {}, format="json").status_code == 201
    registration = EventRegistration.objects.get(event=event, member=user)
    Event.objects.filter(pk=event.pk).update(status="cancelled")
    owner = client_for(user)
    ticket = owner.get(reverse("member-event-ticket", args=[space.pk, registration.pk]))
    assert ticket.status_code == 200 and ticket.data["ticket_png_available"] is False
    assert ticket.data["event"]["status"] == "cancelled"
    assert owner.get(reverse("member-event-checkin-qr", args=[space.pk, registration.pk])).status_code == 404
