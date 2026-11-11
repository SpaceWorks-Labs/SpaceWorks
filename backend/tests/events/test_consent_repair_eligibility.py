"""The private advisory exposes owned consent repair without reopening registration."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.events.models import Event
from apps.organizations.models import OrganizationMembership
from tests.events.collab_helpers import client_for
from tests.events.organization_audience_helpers import direct
from tests.events.test_waiver_consent_repair_cutoff import consent, queued_fixture, unchanged_fields
from tests.events.ticketing_helpers import public_url, signup

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("state", ["pending_approval", "waitlisted", "registered"])
@pytest.mark.parametrize("cutoff", ["explicit", "lead"])
def test_owned_live_registration_exposes_current_waiver_after_cutoff(state, cutoff):
    _, event, _, user, row, waiver, _ = queued_fixture(cutoff=cutoff)
    row.status = state
    row.save(update_fields=["status"])
    before, audits = unchanged_fields(row), AuditLog.objects.count()
    path = public_url(event, "public-event-organization-eligibility")
    response = client_for(user).get(path)
    assert response.status_code == 200, response.data
    assert response.data == {
        "eligible": False, "reason": "registration_closed", "consent_repair_required": True,
        "host_waiver": {"id": waiver.pk, "version": "v2", "body": "Renewed host terms"},
    }
    assert response["Cache-Control"] == "private, no-store"
    assert {"Cookie", "Authorization"} <= set(response["Vary"].split(", "))
    row.refresh_from_db()
    assert unchanged_fields(row) == before and row.host_waiver_version_accepted == "v1"
    assert AuditLog.objects.count() == audits
    # The same browser route accepts only consent; required answers remain saved.
    repaired = signup(event, user, **consent(waiver))
    assert repaired.status_code == 201, repaired.data
    row.refresh_from_db()
    assert unchanged_fields(row) == before
    response = client_for(user).get(path)
    assert response.data == {"eligible": False, "reason": "registration_closed",
                             "consent_repair_required": False, "host_waiver": None}


@pytest.mark.parametrize("state", ["new", "cancelled", "rejected", "attended", "ineligible", "anonymous"])
def test_closed_signup_does_not_expose_another_person_or_terminal_consent_repair(state):
    _, event, _, user, row, _, _ = queued_fixture()
    if state == "new":
        user = direct(OrganizationMembership.objects.get(user=user).organization, "new-browser-user")
    elif state in ("cancelled", "rejected", "attended"):
        row.status = state
        row.save(update_fields=["status"])
    elif state == "ineligible":
        OrganizationMembership.objects.filter(user=user).update(status="suspended")
    elif state == "anonymous":
        user = None
    response = client_for(user).get(public_url(event, "public-event-organization-eligibility"))
    assert response.status_code == (401 if user is None else 200), response.data
    if user:
        assert response.data["eligible"] is False
        assert response.data["consent_repair_required"] is False
        assert response.data["host_waiver"] is None


@pytest.mark.parametrize("state", ["draft", "cancelled", "ended"])
def test_terminal_or_unpublished_event_has_no_consent_repair_advisory(state):
    _, event, _, user, _, _, _ = queued_fixture()
    if state == "ended":
        event.ends_at = timezone.now() - timedelta(seconds=1)
        event.starts_at = event.ends_at - timedelta(hours=1)
        event.registration_cutoff_at = event.starts_at
        event.save(update_fields=["starts_at", "ends_at", "registration_cutoff_at"])
    else:
        event.status = Event.Status.DRAFT if state == "draft" else Event.Status.CANCELLED
        event.save(update_fields=["status"])
    response = client_for(user).get(public_url(event, "public-event-organization-eligibility"))
    assert response.status_code == 404, response.data
