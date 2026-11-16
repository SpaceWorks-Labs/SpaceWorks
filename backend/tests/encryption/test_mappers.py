import pytest
from django.contrib.auth import get_user_model
from django.db import connection

from apps.encryption.crypto import PiiAuthenticationFailed, decrypt_with_key_loader
from apps.encryption.registry import ALL_FIELDS, SECONDARY_FIELDS, SOURCE_FIELDS
from apps.encryption.services import get_dek
from apps.hardware_requests.models import HardwareRequest
from apps.makerspaces.models import Makerspace


pytestmark = pytest.mark.django_db


@pytest.fixture
def space():
    return Makerspace.objects.create(name="Mapper Space", slug="mapper-space")


@pytest.fixture
def requester():
    return get_user_model().objects.create_user(username="mapper-requester")


@pytest.fixture
def enabled():
    from tests.encryption.conftest import enabled_encryption

    with enabled_encryption():
        yield


def make_request(space, requester):
    return HardwareRequest.objects.create(
        makerspace=space, requester=requester, requester_username="mapper-requester",
        requester_name="Ada Lovelace", requester_contact_email="ada@example.test",
        requester_contact_phone="+91 9999900000", requested_for="oscilloscope",
    )


def test_registry_matches_the_post_b7c_source_and_secondary_allowlists():
    # 18 at B7c, plus the two post-event source fields:
    # EventFeedbackResponse.answers_snapshot and EventAttendanceCertificate.recipient_name.
    # The counts are asserted so that encrypting a new column is a visible decision here.
    # 21 with makerspaces.MemberCard.printed_name (forward plan phase 5).
    # 21 -> 24 with InvitationRequest name/email/phone (forward plan phase 6).
    # 24 -> 25 with PrinterJob.failure_reason (forward plan phase 7b).
    # Membership applications add one source field; inbox and broadcasts add four secondary fields.
    # Booking departure remarks are source evidence; personal envelope bodies and
    # proven endpoint/challenge addresses are secondary scoped PII too.
    # lane/events-final: reimbursement (33) + G-final programme document fields (6),
    # plus integrations.MessagingConsent.phone_e164 (mobile SMS consent ledger).
    # Release 2: membership lifecycle (L4), repairs (L16), ID cards (L3), ticketing (L6), donations (L18),
    # participation (L21a), shop (L22) and prize claims (hack money) add 47 source fields.
    # 0.12.0: +8 (EquipmentProposalReceipt/UseReceipt intent_snapshot, MinorProfile x4, GuardianConsent.signed_name, Incident.involved_note).
    assert len(SOURCE_FIELDS) == 149
    # Event campaigns add secondary subject/body fields (Lane D).
    assert len(SECONDARY_FIELDS) == 16
    assert len(ALL_FIELDS) == 165
    assert {item.model_label for item in SECONDARY_FIELDS} == {
        "integrations.EmailLog", "notifications.NotificationInboxRow", "notifications.MemberBroadcast",
        "events.EventBroadcast",
        "bookings.BookingBroadcast",
        "integrations.NotificationEnvelope", "integrations.NotificationEndpoint",
        "integrations.NotificationEndpointChallenge",
    }
    campaign_fields = [item for item in SECONDARY_FIELDS if item.model_label == "events.EventBroadcast"]
    assert {item.field_name for item in campaign_fields} == {"subject", "body"}
    assert all(item.makerspace_path == "makerspace_id" and item.index_kind == "none" for item in campaign_fields)
    assert all(item.classification == "secondary" for item in campaign_fields)


def test_flag_off_is_byte_for_byte_plaintext(space, requester):
    request = make_request(space, requester)
    with connection.cursor() as cursor:
        cursor.execute("SELECT requester_name FROM hardware_requests_hardwarerequest WHERE id = %s", [request.pk])
        assert cursor.fetchone()[0] == "Ada Lovelace"


def test_enabled_save_encrypts_and_round_trips_with_row_bound_aad(enabled, space, requester):
    request = make_request(space, requester)
    with connection.cursor() as cursor:
        cursor.execute("SELECT requester_name FROM hardware_requests_hardwarerequest WHERE id = %s", [request.pk])
        raw = cursor.fetchone()[0]
    assert raw.startswith("pii:gcm:v1:")
    assert request.requester_name == "Ada Lovelace"
    loaded = HardwareRequest.objects.get(pk=request.pk)
    assert loaded.requester_name == "Ada Lovelace"
    with pytest.raises(PiiAuthenticationFailed):
        decrypt_with_key_loader(raw, makerspace_id=space.pk, table=loaded._meta.db_table, pk=loaded.pk + 1, field="requester_name", load_dek=lambda version: get_dek(space.pk, version))


def test_enabled_mapped_bulk_writes_are_rejected(enabled, space, requester):
    request = make_request(space, requester)
    with pytest.raises(RuntimeError):
        HardwareRequest.objects.filter(pk=request.pk).update(requester_name="other")
    with pytest.raises(RuntimeError):
        HardwareRequest.objects.bulk_update([request], ["requester_name"])
