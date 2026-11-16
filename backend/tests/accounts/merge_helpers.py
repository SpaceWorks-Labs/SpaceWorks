"""Fixtures for the U-C account-merge tests (local only)."""

import json
import os
import re
import uuid
from types import SimpleNamespace

import pytest
from django.conf import settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.models_account_merge import AccountMergeRecord
from apps.makerspaces.models import Makerspace
from apps.makerspaces.secrets import encrypt_value
from tests.accounts.account_factories import grant_staff_role, make_membership
from tests.accounts.mfa_helpers import _TEST_KEY
from tests.accounts.reauth_helpers import force_recent_authenticate

PASSWORD = "merge-Password-123!"
START = "/api/v1/auth/account-merge/start"


def url(intent_id, step):
    return f"/api/v1/auth/account-merge/{intent_id}/{step}"


@pytest.fixture(autouse=True)
def keys_and_clean_cache():
    from django.core.cache import cache

    if not settings.API_CLIENT_ENC_KEY:
        settings.API_CLIENT_ENC_KEY = _TEST_KEY
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def outbox(monkeypatch):
    sent = []

    def dispatch(**kwargs):
        sent.append(kwargs)
        return SimpleNamespace(status="sent")

    monkeypatch.setattr("apps.integrations.dispatch.dispatch_email", dispatch)
    return sent


_PHRASE = {"survivor": "link another account to the one", "source": "link this account to"}


def codes_to(outbox, address, side=None):
    return [re.search(r"is (\d{6})\.", mail["text_body"]).group(1)
            for mail in outbox if mail["to_email"] == address and mail["event"] == "account_merge_code"
            and (side is None or _PHRASE[side] in mail["text_body"])]


def space(slug):
    return Makerspace.objects.create(name=slug, slug=slug)


def person(username, **fields):
    fields.setdefault("email", f"{username}@example.test")
    return User.objects.create_user(username, password=PASSWORD, **fields)


def converted(username, *, email=None, held_email=None, makerspace=None, role="inventory_manager"):
    """A former staff account the way unification left it: a person with a converted record."""
    user = User.objects.create_user(username, email="" if held_email else (email or f"{username}@staff.test"),
                                    password=PASSWORD)
    if makerspace is not None:
        grant_staff_role(user, makerspace, role_slug=role)
    snapshot = {"email": held_email or user.email, "first_name": "", "last_name": "", "display_name": "",
                "phone": "", "phone_e164": "", "telegram_user_id": ""}
    AccountMergeRecord.objects.create(
        decision="converted", source=user, proof_method="migration", run_id=uuid.uuid4(),
        snapshot_scheme="deployment", snapshot_ciphertext=encrypt_value(json.dumps(snapshot)),
        held_fields=["email"] if held_email else [], state="completed", completed_at=timezone.now())
    return user


def client_for(user):
    client = APIClient()
    force_recent_authenticate(client, user)
    return client


def start(client, identifier, method="email_codes"):
    return client.post(START, {"identifier": identifier, "method": method}, format="json")


def proved_by_codes(client, outbox, survivor, source_address, identifier):
    response = start(client, identifier)
    assert response.status_code == 201, response.data
    intent = response.data["intent_id"]
    survivor_code = codes_to(outbox, survivor.email, "survivor")[-1]
    source_code = codes_to(outbox, source_address, "source")[-1]
    proved = client.post(url(intent, "prove"), {"survivor_code": survivor_code, "source_code": source_code},
                         format="json")
    assert proved.status_code == 200, proved.data
    return intent


def confirm(client, intent):
    preview = client.get(url(intent, "preview"))
    assert preview.status_code == 200, preview.data
    return preview, client.post(url(intent, "confirm"), {"preview_sha256": preview.data["preview_sha256"]},
                                format="json")


def feed(makerspace, user):
    from apps.bookings.models_feed import BookingCalendarFeed

    return BookingCalendarFeed.objects.create(makerspace=makerspace, user=user, token_digest=os.urandom(32),
                                              token_hint="hint1234")


__all__ = ["PASSWORD", "client_for", "codes_to", "confirm", "converted", "feed", "keys_and_clean_cache",
           "make_membership", "outbox", "person", "proved_by_codes", "space", "start", "url"]
