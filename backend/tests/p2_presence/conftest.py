from types import SimpleNamespace

import pytest
from django.db import transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MemberProfile, MemberProject, default_enabled_modules


@pytest.fixture(autouse=True)
def no_external_delivery(monkeypatch):
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", lambda *_: None)
    monkeypatch.setattr("apps.events.services.notify_event_lifecycle", lambda *_: None)
    def refused(*args, **kwargs):
        raise AssertionError("Presence tests must never make real HTTP requests")
    monkeypatch.setattr("requests.sessions.Session.request", refused)


@pytest.fixture
def lane(settings):
    settings.API_CLIENT_AUTH_REQUIRED = False
    settings.PLATFORM_STAFF_ORIGINS = ["http://localhost:5000"]
    space = Makerspace.objects.create(name="Presence", slug="p2-presence",
        enabled_modules=sorted(set(default_enabled_modules()) | {"presence", "membership", "events", "notifications", "email"}),
        geofence_enabled=True, geofence_latitude=0, geofence_longitude=0, geofence_radius_m=100)
    space.enabled_features = sorted(set(space.enabled_features) | {"presence.geofence", "notifications.member_inbox"})
    space.save(update_fields=["enabled_features"])
    @transaction.atomic
    def person(username, *, manager=False, guest=False, target=None):
        target = target or space
        user = User.objects.create_user(username=username, email=f"{username}@example.test",
            account_kind="staff" if manager else "member", staff_makerspace=target if manager else None,
            display_name=f"Name {username}", access_status="active", role="space_manager" if manager else "requester")
        if not guest:
            slug = "space_manager" if manager else "member"
            MakerspaceMembership.objects.create(makerspace=target, user=user,
                assigned_role=target.roles.get(slug=slug), role="space_manager" if manager else "custom", status="active")
        return user
    owner, staff, guest = person("owner"), person("staff", manager=True), person("guest", guest=True)
    membership = owner.makerspace_memberships.get(makerspace=space)
    profile = MemberProfile.objects.create(membership=membership, public_visible=True,
                                           public_consented_at=timezone.now(), show_projects=True)
    project = MemberProject.objects.create(profile=profile, title="Public rover", public_visible=True)
    def client(user=None):
        api = APIClient(HTTP_ORIGIN="http://localhost:5000")
        if user:
            api.force_authenticate(user)
        return api
    return SimpleNamespace(space=space, owner=owner, staff=staff, guest=guest, profile=profile,
                           project=project, person=person, client=client)
