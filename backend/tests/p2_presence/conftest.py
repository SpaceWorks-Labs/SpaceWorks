from types import SimpleNamespace

import pytest
from django.db import transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.makerspaces.models import Makerspace, MakerspaceMembership, default_enabled_modules


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
            display_name=f"Name {username}", access_status="active", role="space_manager" if manager else "requester")
        if manager:
            # Decision 63: one account per person; staff authority is a staff-track membership row.
            from tests.accounts.account_factories import grant_staff_role
            grant_staff_role(user, target, role_slug="space_manager")
        elif not guest:
            MakerspaceMembership.objects.create(makerspace=target, user=user,
                assigned_role=target.roles.get(slug="member"), role="custom", status="active")
        return user
    owner, staff, guest = person("owner"), person("staff", manager=True), person("guest", guest=True)
    membership = owner.makerspace_memberships.get(makerspace=space)
    from apps.makerspaces.models_account_profile import AccountProfile, AccountProject
    from apps.makerspaces.models_profiles import PublicHandle
    # Decision 304: one global account profile; presence projects are AccountProject rows.
    profile, _ = AccountProfile.objects.update_or_create(user=owner, defaults={
        "public_visible": True, "public_consented_at": timezone.now(), "show_projects": True})
    PublicHandle.objects.get_or_create(user=owner, defaults={"handle": "presence.owner", "changed_at": timezone.now()})
    project = AccountProject.objects.create(profile=profile, title="Public rover", public_visible=True)
    def client(user=None):
        api = APIClient(HTTP_ORIGIN="http://localhost:5000")
        if user:
            api.force_authenticate(user)
        return api
    return SimpleNamespace(space=space, owner=owner, staff=staff, guest=guest, profile=profile,
                           project=project, person=person, client=client)
