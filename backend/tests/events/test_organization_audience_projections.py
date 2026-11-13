"""Authority, public/private projections, historical tickets and recurrence."""
from tests.events.manual_grant_fixture import create_manual_grant

from datetime import time

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.models import AuditLog
from apps.events import services
from apps.events.models import Event, EventOrganizer, EventSeries, EventStaffGrant
from apps.events.organization_audience import AUDIENCE, FEATURE
from apps.events.services_clone import duplicate_event
from apps.events.services_organizers import replace_organizers
from apps.events.services_series import create_series, extend_series, update_series
from apps.events.services_series_organizers import add_series_organizer, remove_series_organizer
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.setup_areas import features_for
from apps.organizations.models import OrganizationMembership
from tests.events.collab_helpers import client_for
from tests.events.organization_audience_helpers import audience_fixture, direct
from tests.events.ticketing_helpers import account, open_event, public_url, signup

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("permission", ["edit_details", "check_in", "manage_registrations", "revoked", "foreign"])
def test_only_live_correct_edit_details_grant_can_configure_audience(permission):
    venue, orgs, _, event, manager = audience_fixture()
    grantee = account("editor")
    target = open_event(venue) if permission == "foreign" else event
    grant = create_manual_grant(
        makerspace=venue, event=target, user=grantee, granted_by=manager,
        permissions=["edit_details" if permission in ("foreign", "revoked") else permission],
        revoked_at=timezone.now() if permission == "revoked" else None,
    )
    if permission != "edit_details":
        with pytest.raises(PermissionDenied):
            services.update_event(event, actor=grantee, registration_audience=AUDIENCE)
        return
    services.update_event(event, actor=grantee, registration_audience=AUDIENCE)
    audit = AuditLog.objects.get(action="event.audience_updated")
    assert audit.meta == {"old_audience": AUDIENCE, "new_audience": AUDIENCE, "organization_ids": sorted(org.pk for org in orgs)}
    with pytest.raises(PermissionDenied):
        replace_organizers(event, actor=grantee, organization_ids=[orgs[0].pk])
    url = reverse("admin-event-detail", kwargs={"pk": event.pk})
    assert client_for(grantee).patch(url, {"organization_ids": [orgs[0].pk]}, format="json").status_code == 400
    assert EventOrganizer.objects.filter(event=event).count() == 2


def test_feature_pickup_and_existing_defaults_are_unchanged():
    venue, _, _, event, manager = audience_fixture()
    assert FEATURE in features_for({"events"})
    assert Event._meta.get_field("registration_audience").default == "members"
    assert venue.event_default_registration_audience == "members"
    venue.enabled_features.remove(FEATURE); venue.save(update_fields=["enabled_features"])
    with pytest.raises(ValidationError):
        services.update_event(event, actor=manager, registration_audience=AUDIENCE)


def test_public_names_and_private_eligibility_do_not_publish_membership_or_contacts():
    _, orgs, _, event, _ = audience_fixture()
    eligible, outsider = direct(orgs[0]), account("outsider")
    listed = client_for(None).get(public_url(event, "public-event-detail"))
    assert listed.status_code == 200
    assert listed.data["audience_label"] == "Open to members of A, B, C"
    assert listed.data["participating_organizations"] == [{"id": org.pk, "name": org.name} for org in orgs]
    assert "eligible" not in listed.data and eligible.email not in str(listed.data)
    path = public_url(event, "public-event-organization-eligibility")
    for user, expected in ((eligible, True), (outsider, False)):
        response = client_for(user).get(path)
        assert response.status_code == 200 and response.data["eligible"] is expected
        assert response["Cache-Control"] == "private, no-store"
        assert set(response.data) == {"eligible", "reason", "host_waiver", "consent_repair_required"}
        assert "membership" not in str(response.data)
    anonymous = client_for(None).get(path)
    assert anonymous.status_code == 401 and anonymous["Cache-Control"] == "private, no-store"


def test_own_ticket_png_qr_calendar_and_cancel_survive_membership_and_organizer_loss():
    venue, orgs, _, event, manager = audience_fixture()
    user, outsider = direct(orgs[0]), account("outsider")
    assert signup(event, user).status_code == 201
    registration = event.registrations.get()
    OrganizationMembership.objects.filter(user=user).update(status="suspended")
    replace_organizers(event, actor=manager, organization_ids=[])
    paths = [reverse(name, args=[venue.pk, registration.pk]) for name in (
        "member-event-checkin-qr", "member-event-ticket", "member-event-ticket-png", "member-event-registration-calendar",
    )]
    for path in paths:
        assert client_for(user).get(path).status_code == 200
        assert client_for(outsider).get(path).status_code == 404
    roster = client_for(manager).get(reverse("admin-event-registration-list", kwargs={"pk": event.pk}))
    assert roster.data["results"][0]["no_longer_eligible"] is True
    assert client_for(user).post(reverse("member-event-registration-cancel", args=[venue.pk, registration.pk]), {}, format="json").status_code == 200
    assert not MakerspaceMembership.objects.filter(user=user, makerspace=venue).exists()


def test_series_projected_organizers_feature_validation_block_inheritance_and_clone():
    venue, orgs, _, _, manager = audience_fixture()
    series, occurrences = create_series(makerspace=venue, actor=manager, title="Series", description="",
        location="", location_kind="other", capacity=0, is_public=True, registration_audience=AUDIENCE,
        recurrence_timezone="UTC", dtstart_local_date=timezone.now().date(), dtstart_local_time=time(23),
        recurrence_rule="FREQ=DAILY;COUNT=3", duration_minutes=60)
    source = add_series_organizer(series, actor=manager, organization=orgs[0])
    assert all(EventOrganizer.objects.filter(event=row, organization=orgs[0]).exists() for row in occurrences)
    user = direct(orgs[0])
    from apps.events.services_series import publish_series
    publish_series(series, actor=manager)
    assert signup(occurrences[-1], user).status_code == 201
    source_id = source.pk
    remove_series_organizer(source, actor=manager)
    assert not EventOrganizer.objects.filter(source_series_organizer_id=source_id).exists()
    series.refresh_from_db()
    series.organization_admission_blocked = True; series.recurrence_rule = "FREQ=DAILY;COUNT=4"
    series.save(update_fields=["organization_admission_blocked", "recurrence_rule"])
    added = extend_series(series, actor=manager)[1]
    assert added and all(row.organization_admission_blocked for row in added)
    series = update_series(series, actor=manager, registration_audience=AUDIENCE)[0]
    assert not series.organization_admission_blocked
    clone = duplicate_event(occurrences[-1], actor=manager)
    assert clone.registration_audience == AUDIENCE and clone.status == "draft"
    assert not clone.registrations.exists() and not clone.organizers.exists()
    assert clone.makerspace_id == venue.pk
    venue.enabled_features.remove(FEATURE); venue.save(update_fields=["enabled_features"])
    with pytest.raises(ValidationError):
        extend_series(series, actor=manager)
