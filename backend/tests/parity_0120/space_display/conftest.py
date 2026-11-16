"""SPACE-DISPLAY fixtures (decision 307): a space with presence, events and machines, and a switch helper."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.db import transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.machines.models import Machine, MachineType
from apps.makerspaces.models import Makerspace, MakerspaceMembership, default_enabled_modules
from apps.makerspaces.models_account_profile import AccountProfile
from apps.makerspaces.models_profiles import PublicHandle
from apps.presence import services


@pytest.fixture(autouse=True)
def isolate(settings, monkeypatch):
    settings.API_CLIENT_AUTH_REQUIRED = False
    settings.PLATFORM_STAFF_ORIGINS = ["http://localhost:5000"]
    settings.INFRA_HOSTS = {*settings.INFRA_HOSTS, "testserver"}
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", lambda *_: None)


@pytest.fixture
def lane():
    space = Makerspace.objects.create(
        name="Display", slug="display-lane",
        enabled_modules=sorted(set(default_enabled_modules()) | {"presence", "membership", "events", "machines"}),
        geofence_enabled=True, geofence_latitude=0, geofence_longitude=0, geofence_radius_m=100)
    space.enabled_features = sorted(set(space.enabled_features) | {"presence.public_display", "presence.geofence"})
    space.save(update_fields=["enabled_features"])

    @transaction.atomic
    def person(username, *, manager=False, member=True, target=None):
        target = target or space
        if manager:  # a staff row is a staff-track membership (accounts are people; staff roles are granted)
            from tests.return_helpers import make_member
            return make_member(username, target)
        user = User.objects.create_user(
            username=username, email=f"{username}@example.test",
            account_kind="member",
            display_name=f"Name {username}", access_status="active", role="requester")
        if member:
            slug = "space_manager" if manager else "member"
            MakerspaceMembership.objects.create(
                makerspace=target, user=user, assigned_role=target.roles.get(slug=slug),
                role="space_manager" if manager else "custom", status="active")
        return user

    def profile(user, *, public=False, headline="Maker", **fields):
        PublicHandle.objects.get_or_create(user=user, defaults={"handle": user.username if len(user.username) > 2 else f"{user.username}-x", "changed_at": timezone.now()})
        return AccountProfile.objects.create(
            user=user, headline=headline, public_visible=public,
            public_consented_at=timezone.now() if public else None, **fields)

    def check_in(user, **kwargs):
        return services.start_session(user, space, 60, latitude=0, longitude=0, accuracy=5, **kwargs)

    def machine(name, status):
        kind = MachineType.objects.create(makerspace=space, slug=f"k-{uuid4().hex[:6]}", name="Printer")
        return Machine.objects.create(makerspace=space, machine_type=kind, name=name, status=status, is_public=True)

    def client(user=None):
        api = APIClient(HTTP_ORIGIN="http://localhost:5000")
        if user:
            api.force_authenticate(user)
        return api

    return SimpleNamespace(space=space, person=person, profile=profile, check_in=check_in, machine=machine,
                           client=client, staff=person("manager", manager=True))
