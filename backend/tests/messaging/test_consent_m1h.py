from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from rest_framework.exceptions import NotFound

from apps.integrations.messaging.consent import VerifiedPhoneRequired, grant_consent, live_consent
from apps.integrations.messaging.protections import recipient_hash
from apps.integrations.models import (
    MessagingConsent, MessagingRecipientAlias, MessagingRecipientCorrelation, MessagingSuppression,
)
from tests.messaging.canonical_helpers import (
    PLATFORM_WA_KEY, platform_sms, platform_whatsapp, sms_channel, verified_endpoint, whatsapp_channel,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def sms_sender(space):
    # Consent binds to the canonical configured sender; there is none by default.
    platform_sms()
    return sms_channel(space)


def grant(member, space, action="opted_in", channel="sms"):
    return grant_consent(user=member, makerspace_id=space.pk, channel=channel, action=action)


def test_phone_a_b_a_needs_new_consent(member, space):
    grant(member, space)
    assert live_consent(space, member, "sms")
    original_phone = member.phone_e164
    original_verification = member.phone_verified_at
    member.phone_e164 = "+14155552672"
    member.save()
    assert member.phone_verified_at is None
    assert not live_consent(space, member, "sms")
    # Identity edits clear verification; OTP confirmation is a separate write.
    member.phone_verified_at = original_verification + timedelta(seconds=1)
    member.save(update_fields=["phone_verified_at"])
    assert not live_consent(space, member, "sms")
    member.phone_e164 = original_phone
    member.save()
    assert member.phone_verified_at is None
    assert not live_consent(space, member, "sms")
    member.phone_verified_at = original_verification + timedelta(seconds=2)
    member.save(update_fields=["phone_verified_at"])
    assert not live_consent(space, member, "sms")
    grant(member, space)
    assert live_consent(space, member, "sms")


def test_unverified_optout_and_nonmember_admission(member, space):
    member.phone_verified_at = None
    member.save()
    with pytest.raises(VerifiedPhoneRequired):
        grant(member, space)
    grant(member, space, "opted_out")
    member.makerspace_memberships.update(status="revoked")
    with pytest.raises(NotFound):
        grant(member, space, "opted_out")


def test_consent_is_immutable_at_model_and_database(member, space):
    grant(member, space)
    row = MessagingConsent.objects.get(user=member)
    with pytest.raises(ValidationError):
        row.save()
    with pytest.raises(ValidationError):
        row.delete()
    with pytest.raises(DatabaseError), transaction.atomic():
        MessagingConsent.objects.filter(pk=row.pk).update(action="opted_out")
    with pytest.raises(DatabaseError), transaction.atomic():
        MessagingConsent.objects.filter(pk=row.pk).delete()
    # Purge DELETE authorization never authorizes an UPDATE of history.
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SET LOCAL app.allow_immutable_delete = 'on'")
        cursor.execute("UPDATE integrations_messagingconsent SET action='opted_out' WHERE id=%s", [row.pk])


def test_reconsent_lifts_phone_and_every_mapped_alias_and_resets_blocked(member, manager, space):
    platform_whatsapp()
    # WhatsApp consent needs this account's own signed endpoint proof, never SMS consent.
    verified_endpoint(member, whatsapp_channel(space, manager))
    key, phone = PLATFORM_WA_KEY, recipient_hash("phone", member.phone_e164)
    aliases = [recipient_hash("alias", value) for value in ("one", "two")]
    for alias in aliases:
        MessagingRecipientAlias.objects.create(sender_key=key, alias_hash=alias, phone_hash=phone)
    ids = [MessagingSuppression.objects.create(channel="whatsapp", sender_key=key, recipient_hash=value,
             reason="inbound_stop", recipient_kind="phone" if value == phone else "alias").pk for value in (phone, *aliases)]
    other = MessagingSuppression.objects.create(channel="whatsapp", sender_key="other", recipient_hash=phone, reason="inbound_stop")
    MessagingRecipientCorrelation.objects.create(sender_key=key, phone_hash=phone, state="blocked")
    grant(member, space, channel="whatsapp")
    assert set(MessagingConsent.objects.latest("id").lifted_suppression_id) == set(ids)
    assert not MessagingRecipientCorrelation.objects.filter(sender_key=key, phone_hash=phone).exists()
    assert not MessagingSuppression.objects.filter(pk__in=ids, lifted_at__isnull=True).exists()
    other.refresh_from_db()
    assert other.lifted_at is None
