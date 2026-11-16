"""Decision 14: the whole volunteer lifecycle over the real HTTP surface.

Public "volunteers needed" listing -> role application -> organizer approval -> shift signup
with capacity and a FIFO waitlist -> desk check-in / self check-out -> independent hours
verification -> thank-you certificate issued and visible to the volunteer. Every call goes
through the mounted DRF routes with the production ``ContributorPorts`` adapter installed;
nothing below substitutes a hook. Module-off and unauthorized actors are checked separately.
"""
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.events.contributions import ports as contributor_ports
from apps.events.contributions.models_roles import EventRoleAssignment
from apps.events.contributions.models_shifts import (EventContributionHours, EventContributionHoursEntry,
    EventShiftAttendance, EventShiftSignup)
from apps.events.contributions.runtime import ContributorPorts
from apps.events.models import Event
from apps.events.models_certificates import EventAttendanceCertificate
from tests.events.collab_helpers import client_for, make_staff
from tests.events.ticketing_helpers import account, event_space

FORM = {"schema_version": 2, "form_id": "volunteer", "revision": 1, "questions": []}
DESCRIPTOR = {"schema_version": 2, "form_id": "volunteer", "revision": 1}


@pytest.fixture(autouse=True)
def production_ports(monkeypatch, settings):
    # Other suites install a fake adapter into this module global; use the real one here.
    settings.PII_ENCRYPTION_ENABLED = False
    monkeypatch.setattr(contributor_ports, "_adapter", ContributorPorts())


def command(client, path, version=0, **fields):
    operation = str(uuid4())
    return client.post(path, {"operation_id": operation, "expected_version": version, **fields},
                       format="json", HTTP_IDEMPOTENCY_KEY=operation)


def world(slug):
    space = event_space(f"d14-{slug}-{uuid4().hex[:6]}")
    space.enabled_features += ["events.volunteering"]
    space.save(update_fields=["enabled_features"])
    now = timezone.now()
    event = Event.objects.create(makerspace=space, title="Repair cafe", starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(hours=5), registration_audience="accounts", is_public=True, status="published")
    manager, verifier = make_staff(space, username=f"d14-lead-{slug}"), make_staff(space, username=f"d14-verify-{slug}")
    return SimpleNamespace(space=space, event=event, manager=manager, verifier=verifier,
        admin=f"/api/v1/admin/events/{event.pk}",
        member=f"/api/v1/member/makerspaces/{space.pk}/events/{event.pk}",
        public=f"/api/v1/public/event-programmes/{event.public_token}/volunteer-postings/")


def open_posting_and_shift(w):
    lead, now = client_for(w.manager), timezone.now()
    posting = command(lead, f"{w.admin}/volunteer-postings/", role="volunteer", title="Bench crew",
        description="Help visitors fix things.", visibility="public", approval_required=True, state="open",
        opens_at=(now - timedelta(minutes=5)).isoformat(), closes_at=(w.event.ends_at - timedelta(minutes=1)).isoformat(),
        form_schema=FORM)
    assert posting.status_code == 201, posting.content
    shift = command(lead, f"{w.admin}/shifts/", posting_id=posting.data["id"], task="Front desk",
        starts_at=(now + timedelta(minutes=30)).isoformat(), ends_at=(now + timedelta(hours=3)).isoformat(),
        signup_deadline=(now + timedelta(minutes=20)).isoformat(), capacity=1, grace_minutes=60,
        waitlist_enabled=True, approval_required=False)
    assert shift.status_code == 201, shift.content
    return posting.data["id"], shift.data["id"]


def approved_volunteer(w, posting_id, name):
    user = account(f"d14-{name}-{uuid4().hex[:6]}")
    client = client_for(user)
    revision = Event.objects.get(pk=w.event.pk).event_date_revision
    form = {"form": DESCRIPTOR, "answers": {}, "event_date_revision": revision}
    draft = command(client, f"{w.member}/role-postings/{posting_id}/application/", **form)
    assert draft.status_code == 201, draft.content
    assert draft.data["state"] == "draft"
    submitted = command(client, f"{w.member}/role-applications/{draft.data['id']}/submit/", draft.data["version"], **form)
    assert submitted.status_code == 200, submitted.content
    assert submitted.data["state"] == "applied"
    # Approval is an organizer decision, never a client-side grant.
    assert command(client, f"{w.admin}/roles/{draft.data['id']}/approve/", submitted.data["version"]).status_code in (403, 404)
    approved = command(client_for(w.manager), f"{w.admin}/roles/{draft.data['id']}/approve/", submitted.data["version"])
    assert approved.status_code == 200, approved.content
    assert approved.data["state"] == "approved"
    return SimpleNamespace(user=user, client=client, role_id=draft.data["id"])


def apply(w, volunteer, shift_id):
    version = client_for(w.manager).get(f"{w.admin}/shifts/{shift_id}/").data["version"]
    response = command(volunteer.client, f"{w.member}/shifts/{shift_id}/apply/", version, role_assignment_id=volunteer.role_id)
    assert response.status_code == 201, response.content
    return response.data


def plan(w):
    response = client_for(w.manager).post(f"{w.admin}/certificates/issue-plan/", {"groups": ["roles"]}, format="json")
    assert response.status_code == 200, response.content
    return response.data


@pytest.mark.django_db(transaction=True)
def test_volunteer_journey_from_public_listing_to_issued_thank_you_certificate(monkeypatch):
    monkeypatch.setattr("apps.events.certificates.tasks.dispatch_batch", lambda batch_id: None)
    w = world("journey")
    posting_id, shift_id = open_posting_and_shift(w)

    # 1. "Volunteers needed" is public and anonymous, and names only the role.
    listing = APIClient().get(w.public)
    assert listing.status_code == 200, listing.content
    assert [row["title"] for row in listing.data["results"]] == ["Bench crew"]
    assert not {"briefing", "permission_preset", "form_schema"} & set(listing.data["results"][0])

    # 2. Three people apply and are approved; the one-place shift takes the first, then queues FIFO.
    first, second, third = (approved_volunteer(w, posting_id, name) for name in ("ada", "grace", "katherine"))
    assert apply(w, first, shift_id)["state"] == "approved"
    assert apply(w, second, shift_id)["state"] == "waitlisted"
    assert apply(w, third, shift_id)["state"] == "waitlisted"
    shifts = second.client.get(f"{w.member}/shifts/").data["results"]
    assert [(row["id"], row["available"], row["signup"]["state"]) for row in shifts] == [(shift_id, 0, "waitlisted")]

    # 3. The first volunteer withdraws before the shift: the EARLIEST waiter is promoted, not the later one.
    mine = EventShiftSignup.objects.get(shift_id=shift_id, member=first.user)
    withdrawn = command(first.client, f"{w.member}/shift-signups/{mine.pk}/withdraw/", mine.version)
    assert withdrawn.status_code == 200 and withdrawn.data["state"] == "withdrawn", withdrawn.content
    states = dict(EventShiftSignup.objects.filter(shift_id=shift_id).values_list("member_id", "state"))
    assert states == {first.user.pk: "withdrawn", second.user.pk: "approved", third.user.pk: "waitlisted"}

    # 4. Desk check-in (a corrected time needs a reason), then the volunteer checks out themselves.
    signup = EventShiftSignup.objects.get(shift_id=shift_id, member=second.user)
    desk = client_for(w.manager)
    started = (timezone.now() - timedelta(minutes=25)).isoformat()
    assert command(desk, f"{w.admin}/shift-signups/{signup.pk}/check-in/", signup.version,
                   occurred_at=started).data["code"] == "reason_required"
    checked_in = command(desk, f"{w.admin}/shift-signups/{signup.pk}/check-in/", signup.version,
                         occurred_at=started, reason="Badge printer was down at arrival.")
    assert checked_in.status_code == 200 and checked_in.data["attendance"] == "checked_in", checked_in.content
    # The volunteer cannot act on somebody else's duty.
    other = EventShiftSignup.objects.get(shift_id=shift_id, member=third.user)
    assert command(second.client, f"{w.member}/shift-signups/{other.pk}/check-out/", other.version).status_code == 404
    signup.refresh_from_db()
    checked_out = command(second.client, f"{w.member}/shift-signups/{signup.pk}/check-out/", signup.version)
    assert checked_out.status_code == 200 and checked_out.data["attendance"] == "checked_out", checked_out.content
    hours = EventContributionHours.objects.get(signup=signup)
    assert hours.state == "pending" and hours.minutes == 25

    # 5. Pending hours earn nothing yet; the volunteer cannot verify their own work.
    before = plan(w)
    assert second.role_id in {row["subject_id"] for row in before["skipped"]}
    assert second.role_id not in {row["subject_id"] for row in before["recipients"]}
    signup.refresh_from_db()
    assert command(second.client, f"{w.admin}/shift-signups/{signup.pk}/verify-hours/", signup.version).status_code in (403, 404)
    verified = command(client_for(w.verifier), f"{w.admin}/shift-signups/{signup.pk}/verify-hours/", signup.version)
    assert verified.status_code == 200 and verified.data["verified_minutes"] == 25, verified.content
    entry = EventContributionHoursEntry.objects.get(hours=hours)
    assert (entry.actor_id, entry.kind, entry.minutes) == (w.verifier.pk, "verified", 25)

    # 6. Verified work makes exactly that volunteer a thank-you recipient; the others are skipped.
    after = plan(w)
    recipients = [(row["subject_kind"], row["subject_id"], row["kind"]) for row in after["recipients"]]
    assert recipients == [("role_assignment", second.role_id, "volunteer_thanks")]
    assert {first.role_id, third.role_id} <= {row["subject_id"] for row in after["skipped"]}
    subject = {"subject_kind": "role_assignment", "subject_id": second.role_id, "kind": "volunteer_thanks"}
    bulk = client_for(w.manager).post(f"{w.admin}/certificates/bulk/", {"operation_id": str(uuid4()),
        "expected_version": after["event_version"], "subjects": [subject], "confirmed_count": 1,
        "publish_event_details": False}, format="json")
    assert bulk.status_code == 202, bulk.content
    from apps.events.certificates.batches import run_chunk
    from apps.events.certificates.lifecycle import render_certificate
    assert run_chunk(bulk.data["id"]).state == "completed"
    certificate = EventAttendanceCertificate.objects.get(role_assignment_id=second.role_id)
    assert certificate.layout_snapshot["contribution_proof"]["minutes"] == 25
    assert render_certificate(certificate).status == "active"

    # 7. The volunteer sees their certificate; nobody else does.
    mine = second.client.get(f"/api/v1/member/makerspaces/{w.space.pk}/certificates/")
    assert mine.status_code == 200, mine.content
    assert [(row["kind"], row["status"]) for row in mine.data] == [("volunteer_thanks", "active")]
    assert first.client.get(f"/api/v1/member/makerspaces/{w.space.pk}/certificates/").data == []

    # 8. Correcting hours afterwards revokes the issued certificate instead of leaving stale proof.
    signup.refresh_from_db()
    adjusted = command(client_for(w.verifier), f"{w.admin}/shift-signups/{signup.pk}/adjust-hours/", signup.version,
                       minutes=20, reason="Left early for a break that was not logged.")
    assert adjusted.status_code == 200 and adjusted.data["verified_minutes"] == 20, adjusted.content
    certificate.refresh_from_db()
    assert certificate.status == "revoked" and certificate.revocation_reason == "attendance_corrected"


@pytest.mark.django_db
def test_volunteering_switch_and_module_off_remove_every_volunteer_surface():
    w = world("off")
    posting_id, shift_id = open_posting_and_shift(w)
    volunteer = approved_volunteer(w, posting_id, "linus")
    w.space.enabled_features = [key for key in w.space.enabled_features if key != "events.volunteering"]
    w.space.save(update_fields=["enabled_features"])
    assert APIClient().get(w.public).status_code == 404
    shifts = volunteer.client.get(f"{w.member}/shifts/")
    assert shifts.status_code == 404 and shifts.data["code"] == "feature_disabled"
    refused = command(volunteer.client, f"{w.member}/shifts/{shift_id}/apply/", 1, role_assignment_id=volunteer.role_id)
    assert refused.status_code == 404 and not EventShiftSignup.objects.filter(shift_id=shift_id).exists()
    assert command(client_for(w.manager), f"{w.admin}/shifts/", posting_id=posting_id, task="Late",
        starts_at=(timezone.now() + timedelta(hours=1)).isoformat(),
        ends_at=(timezone.now() + timedelta(hours=2)).isoformat(),
        signup_deadline=(timezone.now() + timedelta(minutes=30)).isoformat()).status_code == 404
    w.space.enabled_features += ["events.volunteering"]
    w.space.enabled_modules = [key for key in w.space.enabled_modules if key != "events"]
    w.space.save(update_fields=["enabled_features", "enabled_modules"])
    assert volunteer.client.get(f"{w.member}/role-postings/").status_code == 404
    assert volunteer.client.get(f"{w.member}/shifts/").status_code == 404
    assert APIClient().get(w.public).status_code == 404


@pytest.mark.django_db
def test_unauthorized_actors_cannot_run_volunteer_management():
    w = world("authz")
    posting_id, shift_id = open_posting_and_shift(w)
    volunteer = approved_volunteer(w, posting_id, "barbara")
    signup = apply(w, volunteer, shift_id)
    foreign = make_staff(event_space(f"d14-foreign-{uuid4().hex[:6]}"), username="d14-foreign")
    stranger = account(f"d14-stranger-{uuid4().hex[:6]}")
    for actor in (volunteer.user, stranger, foreign):
        client = client_for(actor)
        assert client.get(f"{w.admin}/shifts/{shift_id}/").status_code in (403, 404)
        assert command(client, f"{w.admin}/shift-signups/{signup['id']}/check-in/", signup["version"]).status_code in (403, 404)
        assert command(client, f"{w.admin}/volunteer-postings/", role="volunteer", title="Rogue",
            opens_at=timezone.now().isoformat(), closes_at=w.event.ends_at.isoformat()).status_code in (403, 404)
    # A stranger cannot read or withdraw another volunteer's signup.
    assert client_for(stranger).get(f"{w.member}/shift-signups/{signup['id']}/").status_code == 404
    assert command(client_for(stranger), f"{w.member}/shift-signups/{signup['id']}/withdraw/", signup["version"]).status_code == 404
    assert EventShiftAttendance.objects.get(signup_id=signup["id"]).state == "scheduled"
    assert EventRoleAssignment.objects.get(pk=volunteer.role_id).state == "approved"
