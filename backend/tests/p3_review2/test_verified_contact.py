from types import SimpleNamespace

import pytest

from apps.hardware_requests.models import HardwareRequest
from apps.hardware_requests.notifications_p2_email import proven_address
from apps.encryption.crypto import is_envelope
from tests.encryption.conftest import enabled_encryption
from tests.return_helpers import make_space, make_user

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("kind", ["hardware.request", "hardware.loan_reminder"])
def test_encrypted_verified_contact_proves_only_the_same_owner_mailbox(kind):
    space, other = make_space("encrypted-contact"), make_space("other-contact")
    user, stranger = make_user("contact-owner"), make_user("contact-stranger")
    assert user.email_verified_at is None
    with enabled_encryption():
        row = HardwareRequest.objects.create(makerspace=space, requester=user, requester_username=user.username,
            requester_contact_email=user.email, requester_contact_verified=True)
        assert is_envelope(HardwareRequest.objects.filter(pk=row.pk).values_list("requester_contact_email", flat=True).get())
        envelope = SimpleNamespace(source_kind=kind, audience="requester", source_id=row.pk,
                                   makerspace_id=space.pk, recipient_id=user.pk, recipient=user)
        assert proven_address(envelope)
        envelope.makerspace_id = other.pk
        assert not proven_address(envelope)
        envelope.makerspace_id, envelope.recipient_id = space.pk, stranger.pk
        assert not proven_address(envelope)
        envelope.recipient_id = user.pk
        user.email = "different@example.test"
        assert not proven_address(envelope)
        user.email = row.requester_contact_email
        row.requester_contact_verified = False
        row.save(update_fields=["requester_contact_verified"])
        assert not proven_address(envelope)
