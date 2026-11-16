"""Lane fixtures: real ownership/provenance rows, no external network."""

from datetime import timedelta
from types import ModuleType, SimpleNamespace
import sys
from uuid import uuid4

import pytest
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from apps.accounts.models import User
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.makerspaces.models_account_profile import AccountProfile
from apps.makerspaces.models_profiles import PublicHandle
from apps.makerspaces.profile_activity_public import daily_activity
from apps.makerspaces.profile_github_views import PublicProfileGitHubView
from apps.makerspaces.public_profile_views import PublicProfileEventsView


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("A lane test attempted real network I/O")
    monkeypatch.setattr("urllib.request.urlopen", refuse)


GITHUB_SUB = "4242"


@pytest.fixture
def published(settings, monkeypatch):
    settings.INFRA_HOSTS = ["testserver", "localhost"]
    settings.ALLOWED_HOSTS = ["testserver", "localhost", ".example.test"]
    settings.PLATFORM_STAFF_ORIGINS = ["https://platform.example.test"]
    space = Makerspace.objects.create(name="Profile lab", slug="profile-lab", timezone="Asia/Kolkata",
                                     public_site_enabled=True)
    user = User.objects.create_user(username="profile-maker", email="member@example.test")
    membership = MakerspaceMembership.objects.create(
        makerspace=space, user=user, role="custom", assigned_role=space.roles.get(slug="member"),
    )
    profile = AccountProfile.objects.create(user=user, public_visible=True,
        public_consented_at=timezone.now(), show_activity_graph=True, github_username="octocat")
    # The tests below were written for the per-membership profile and read `profile.membership`; the
    # global profile spans spaces, so the fixture keeps ONE membership reachable under that name.
    profile.membership = membership
    PublicHandle.objects.create(user=user, handle="public.maker", changed_at=timezone.now())
    # Decision 338: a GitHub calendar needs a linked GitHub sign-in whose account id owns the username.
    from apps.accounts.models_social import SocialIdentity
    SocialIdentity.objects.create(user=user, provider="github", provider_sub=GITHUB_SUB)
    monkeypatch.setattr("apps.makerspaces.profile_github.fetch_database_id", lambda username: int(GITHUB_SUB))
    return profile


@pytest.fixture
def other_user():
    return User.objects.create_user(username="different-maker", email="different@example.test")


@pytest.fixture
def other_space():
    return Makerspace.objects.create(name="Other lab", slug="other-lab", timezone="UTC")


@pytest.fixture
def moment():
    return (timezone.now() - timedelta(days=2)).replace(hour=12, minute=0, second=0, microsecond=0)


def enable(profile, **consents):
    for field, value in consents.items():
        setattr(profile, field, value)
    profile.save(update_fields=[*consents, "updated_at"])


def graph(profile, moment):
    from zoneinfo import ZoneInfo
    profile.refresh_from_db()
    day = moment.astimezone(ZoneInfo(profile.membership.makerspace.timezone)).date().isoformat()
    return daily_activity(profile, {"from": day, "to": day})["days"][0]


def public_get(kind="github", handle="public.maker", **headers):
    request = APIRequestFactory().get(f"/api/v1/public/profiles/{handle}/{kind}", **headers)
    view = PublicProfileGitHubView if kind == "github" else PublicProfileEventsView
    return view.as_view()(request, handle=handle)


@pytest.fixture
def speaker_source(monkeypatch):
    module = ModuleType("apps.events.speaker_history")
    calls, rows = [], []
    def contributions_for(user, makerspace):
        calls.append((user.pk, makerspace.pk))
        return iter(rows)
    module.contributions_for = contributions_for
    monkeypatch.setitem(sys.modules, module.__name__, module)
    return SimpleNamespace(rows=rows, calls=calls, module=module)


def make_event(profile, moment, **kwargs):
    from apps.events.models import Event
    values = dict(makerspace=profile.membership.makerspace, title="A public event", starts_at=moment,
                  ends_at=moment + timedelta(hours=2), is_public=True, status="published")
    values.update(kwargs)
    return Event.objects.create(**values)


def registration(profile, event, *, user=None, via=None, status="attended", scan=True):
    from apps.events.models import EventCheckInEvent, EventRegistration
    row = EventRegistration.objects.create(event=event, member=user or profile.membership.user,
        registered_via_makerspace=via, status=status, name="Private person", email="private@example.test", phone="")
    if scan:
        EventCheckInEvent.objects.create(makerspace=event.makerspace, event=event, registration=row,
            source="online", actor=profile.membership.user, attended_at=event.starts_at)
    return row


def request_row(profile, moment, **kwargs):
    from apps.hardware_requests.models import HardwareRequest
    values = dict(makerspace=profile.membership.makerspace, requester=profile.membership.user,
                  requester_username="private", status="issued", issued_at=moment)
    values.update(kwargs)
    return HardwareRequest.objects.create(**values)


def return_row(profile, request):
    from apps.evidence.models import EvidencePhoto
    from apps.hardware_requests.models import ReturnEvent
    evidence = EvidencePhoto.objects.create(makerspace=request.makerspace, evidence_type="return",
        uploaded_by=profile.membership.user, object_key=f"test/{uuid4()}.jpg")
    return ReturnEvent.objects.create(makerspace=request.makerspace, request=request, evidence=evidence,
                                    actor=profile.membership.user, remark="Private remark")
