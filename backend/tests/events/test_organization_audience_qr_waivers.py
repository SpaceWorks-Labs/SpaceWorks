"""QR and PNG authorization recognize both locations of host-waiver evidence."""

from io import BytesIO

import pytest
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.audit.models import AuditLog
from apps.events.checkin_roster import host_waiver_state
from apps.events.models import EventCollaborator
from apps.makerspaces.models import MakerspaceMembership, MakerspaceWaiver
from apps.makerspaces.member_activity_service import _event_registrations
from tests.events.collab_helpers import client_for, make_member
from tests.events.organization_audience_helpers import audience_fixture, local
from tests.events.ticketing_helpers import event_space

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("audience", ["members", "participating_organizations"])
@pytest.mark.parametrize("evidence", ["current", "superseded", "missing", "not_required"])
@pytest.mark.parametrize("evidence_source", ["membership", "witnessed", "registration"])
def test_partner_qr_and_png_honor_both_host_waiver_locations(audience, evidence, evidence_source):
    venue, _, _, event, manager = audience_fixture()
    venue.enabled_modules += ["membership"]
    venue.save(update_fields=["enabled_modules"])
    event.registration_audience = audience
    event.save(update_fields=["registration_audience"])
    partner = event_space("qr-partner", membership=True)
    user = local(venue)
    make_member(partner, user=user)
    EventCollaborator.objects.create(event=event, makerspace=partner, status="accepted")
    consent = {}
    if evidence != "not_required":
        waiver = MakerspaceWaiver.objects.create(
            makerspace=venue, version="v1", body="Host terms", is_active=True,
        )
        if evidence_source == "membership":
            MakerspaceMembership.objects.filter(user=user, makerspace=venue).update(
                accepted_waiver=waiver, waiver_accepted_at=timezone.now(), waiver_version_accepted="v1",
            )
        elif evidence_source == "witnessed":
            MakerspaceMembership.objects.filter(user=user, makerspace=venue).update(
                witnessed_waiver=waiver, witnessed_at=timezone.now(),
                witnessed_waiver_version="v1", witnessed_by=manager,
            )
        else:
            consent = {"host_waiver_id": waiver.pk, "host_waiver_version": "v1", "host_waiver_accepted": True}
    registration_path = reverse("member-collaborative-event-register", args=[partner.pk, event.pk])
    created = client_for(user).post(registration_path, consent, format="json")
    assert created.status_code == 201, created.data
    registration = event.registrations.get()
    assert registration.registered_via_makerspace_id == partner.pk
    assert registration.host_waiver_id == (waiver.pk if consent else None)
    if evidence == "superseded":
        waiver.is_active = False
        waiver.save(update_fields=["is_active"])
        MakerspaceWaiver.objects.create(makerspace=venue, version="v2", body="New terms", is_active=True)
    elif evidence == "missing":
        MakerspaceMembership.objects.filter(user=user, makerspace=venue).update(
            accepted_waiver=None, waiver_accepted_at=None, waiver_version_accepted=None,
            witnessed_waiver=None, witnessed_at=None, witnessed_waiver_version=None, witnessed_by=None,
        )
        registration.host_waiver = None
        registration.host_waiver_accepted_at = None
        registration.host_waiver_version_accepted = None
        registration.save(update_fields=["host_waiver", "host_waiver_accepted_at", "host_waiver_version_accepted"])
    expected_state = {"missing": "missing", "not_required": "not_required"}.get(evidence, "on_file")
    assert host_waiver_state(registration) == expected_state
    dashboard_row = next(row for row in _event_registrations(partner, user)
                         if row["registration_id"] == registration.pk)
    assert dashboard_row["checkin_token"] == (
        None if evidence == "missing" else str(registration.checkin_token)
    )
    qr_path = reverse("member-event-checkin-qr", args=[partner.pk, registration.pk])
    response = client_for(user).get(qr_path)
    assert response.status_code == (404 if evidence == "missing" else 200)
    if evidence != "missing":
        assert response["Content-Type"] == "image/svg+xml"
        assert response["Cache-Control"] == "private, no-store"

    client = client_for(user)
    details = client.get(reverse("member-event-ticket", args=[partner.pk, registration.pk]))
    assert details.status_code == 200, details.data
    assert details.data["ticket_png_available"] is (evidence != "missing")
    png = client.get(reverse("member-event-ticket-png", args=[partner.pk, registration.pk]))
    assert png.status_code == (404 if evidence == "missing" else 200)
    downloads = AuditLog.objects.filter(action="event.ticket_downloaded", target_id=str(registration.pk))
    if evidence == "missing":
        assert not downloads.exists()
    else:
        assert png["Content-Type"] == "image/png"
        assert png["Cache-Control"] == "private, no-store"
        with Image.open(BytesIO(png.content)) as image:
            assert image.format == "PNG"
            image.verify()
        assert downloads.get().actor_id == user.pk


@pytest.mark.parametrize("provenance", ["host", "legacy"])
def test_host_organization_registration_without_evidence_has_no_dashboard_qr(provenance):
    from tests.events.ticketing_helpers import signup

    venue, _, _, event, _ = audience_fixture()
    user = local(venue)
    assert signup(event, user).status_code == 201
    registration = event.registrations.get()
    if provenance == "legacy":
        registration.registered_via_makerspace = None
        registration.save(update_fields=["registered_via_makerspace"])
    MakerspaceWaiver.objects.create(makerspace=venue, version="v1", body="Host terms", is_active=True)
    row = _event_registrations(venue, user)[0]
    assert row["registration_id"] == registration.pk and row["checkin_token"] is None
    assert client_for(user).get(reverse("member-event-checkin-qr", args=[venue.pk, registration.pk])).status_code == 404
