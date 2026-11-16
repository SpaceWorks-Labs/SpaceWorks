from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.core.mail import get_connection
from django.utils import timezone
from django.db import transaction
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tokens import SpaceWorksRefreshToken
from apps.bookings.models import BookableSpace, Booking
from apps.integrations.models_endpoints import ChannelConfiguration, NotificationEndpointChallenge
from apps.integrations.notification_outbox import emit
from apps.integrations.notification_proofs import digest
from apps.makerspaces.models import Makerspace, MakerspaceMembership


@pytest.fixture(autouse=True)
def isolated_notifications(monkeypatch, settings):
    settings.API_CLIENT_AUTH_REQUIRED = False
    settings.INFRA_HOSTS = ["testserver", "localhost"]
    settings.ALLOWED_HOSTS = ["testserver", "localhost", ".example.test"]
    settings.PLATFORM_STAFF_ORIGINS = ["http://localhost:5000"]
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", lambda *_: None)
    monkeypatch.setattr("apps.integrations.dispatch_outbox._enqueue", lambda *_: None)
    monkeypatch.setattr("apps.integrations.email.makerspace_mail_connection", lambda *_: (
        get_connection("django.core.mail.backends.locmem.EmailBackend"), "lab@example.test"))
    def refuse(*args, **kwargs):
        raise AssertionError("No real provider calls in p3_wire tests")
    monkeypatch.setattr("requests.sessions.Session.request", refuse)
    monkeypatch.setattr("http.client.HTTPSConnection.connect", refuse)


@pytest.fixture
def world():
    space = Makerspace.objects.create(name="Wire lab", slug="p3-wire", public_site_enabled=True)
    space.enabled_features = sorted(set(space.enabled_features) | {"notifications.member_inbox", "membership.broadcasts"})
    space.save(update_fields=["enabled_features"])
    @transaction.atomic
    def person(name, role="member", tenant=None, verified=False):
        tenant = tenant or space
        user = User.objects.create_user(username=name, email=f"{name}@example.test", display_name=name,
            access_status="active", role="requester",
            email_verified_at=timezone.now() if verified else None)
        # One account per person (U-A1): staff authority is a staff-track row on the same account.
        manager = MakerspaceMembership.objects if role == "member" else MakerspaceMembership.staff_tracks
        manager.create(makerspace=tenant, user=user, status="active",
            **({} if role == "member" else {"track": "staff"}),
            assigned_role=tenant.roles.get(slug=role), role=role if role != "member" else "custom")
        return user
    owner = person("wire-owner")
    staff = person("wire-staff", "space_manager")
    other = person("wire-other")
    def client(user=None, jwt=False):
        api = APIClient()
        if user and jwt:
            token = SpaceWorksRefreshToken.for_user(user).access_token
            token["surface"] = "member"
            api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        elif user:
            api.force_authenticate(user)
        return api
    def config(channel="discord", **kwargs):
        values = {"makerspace": space, "channel": channel, "provider": channel,
                  "enabled": True, "personal_enabled": True, "integration_identity": f"{channel}-identity"}
        values.update(kwargs)
        return ChannelConfiguration.objects.create(**values)
    def challenge(configuration, user=None):
        code = uuid4().hex
        row = NotificationEndpointChallenge.objects.create(makerspace=configuration.makerspace,
            user=user or owner, configuration=configuration, integration_generation=configuration.generation,
            integration_identity=configuration.integration_identity, code_digest=digest(code),
            expires_at=timezone.now() + timedelta(minutes=10), consented_at=timezone.now(), consent_version="v1")
        return row, code
    def envelope(user=None, **kwargs):
        values = dict(makerspace=space, recipient=user or owner, feature="bookings", stream="bookings",
            event="confirmed", audience="requester", source_kind="bookings.lifecycle", source_id="1", revision="0",
            dedup_key=f"wire:{uuid4().hex}", rendered={"subject": "Booking update", "text": "Your booking changed."})
        values.update(kwargs)
        return emit(**values)
    resource = BookableSpace.objects.create(makerspace=space, name="Wire room", requester_notifications_enabled=True)
    start = timezone.now() + timedelta(days=2)
    booking = Booking.objects.create(space=resource, member=owner, name="Owner", email=owner.email,
        phone="1234567890", starts_at=start, ends_at=start + timedelta(hours=1), status="confirmed")
    return SimpleNamespace(space=space, owner=owner, staff=staff, other=other, person=person, client=client,
        config=config, challenge=challenge, envelope=envelope, booking=booking, resource=resource)
