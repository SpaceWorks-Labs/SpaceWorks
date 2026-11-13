"""X37: invitations also go to the invitee's own chat channels; never a room, never email twice."""
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.integrations.invite_chat import dispatch_invite_chat, invite_eligible
from apps.integrations.models_contract import NotificationDelivery, NotificationEnvelope
from tests.events.ticketing_helpers import account, event_space

pytestmark = pytest.mark.django_db
LINK = "https://space.example/staff/event-invite#token=abc"


def test_an_existing_verified_account_gets_a_personal_envelope_with_email_pre_skipped():
    space = event_space("invite-chat")
    person = account("invitee")
    person.email_verified_at = timezone.now()
    person.save(update_fields=["email_verified_at"])
    invite = SimpleNamespace(pk=41)
    envelope = dispatch_invite_chat(space, feature="events", invite=invite, email="INVITEE@example.test",
                                    label="You are invited", link=LINK)
    assert envelope is not None and envelope.audience == "member" and envelope.recipient_id == person.pk
    assert NotificationDelivery.objects.get(envelope=envelope, channel="email").state == "skipped"
    assert "token" not in str(envelope.context)


def test_unknown_or_unverified_addresses_get_email_only():
    space = event_space("invite-none")
    account("unverified")
    invite = SimpleNamespace(pk=42)
    assert dispatch_invite_chat(space, feature="events", invite=invite, email="unverified@example.test",
                                label="x", link=LINK) is None
    assert dispatch_invite_chat(space, feature="events", invite=invite, email="nobody@example.test",
                                label="x", link=LINK) is None
    assert not NotificationEnvelope.objects.filter(source_kind="integrations.invitation").exists()


def test_redeemed_revoked_or_expired_invites_stop_the_chat_message(monkeypatch):
    rows = {"open": SimpleNamespace(makerspace_id=1, redeemed_at=None, revoked_at=None,
                                    expires_at=timezone.now() + timedelta(days=1))}

    class Model:
        class objects:
            @staticmethod
            def filter(pk):
                return SimpleNamespace(first=lambda: rows.get(pk))
    monkeypatch.setattr("django.apps.apps.get_model", lambda label: Model)
    envelope = SimpleNamespace(context={"invite_feature": "events"}, audience="member", source_id="open",
                               makerspace_id=1)
    assert invite_eligible(envelope)
    rows["open"].redeemed_at = timezone.now()
    assert not invite_eligible(envelope)
    assert not invite_eligible(SimpleNamespace(context={"invite_feature": "rooms"}, audience="member",
                                               source_id="open", makerspace_id=1))
