from uuid import uuid4

import pytest

from apps.accounts.models import User
from apps.data_export.subject_runtime import RUNTIME_FIELDS, runtime_record, runtime_subject_query
from apps.integrations.models_contract import NotificationDelivery, NotificationEnvelope
from apps.makerspaces.models import Makerspace
from tests.encryption.conftest import enabled_encryption
from tests.fixed_roles.helpers import staff_account

pytestmark = pytest.mark.django_db


def envelope(space, user, body="Personal content"):
    return NotificationEnvelope.objects.create(
        makerspace=space, recipient=user, feature="bookings", stream="bookings", event="confirmed",
        audience="requester", message_body=body, source_kind="bookings.booking", source_id="1",
        dedup_key=uuid4().hex,
    )


def test_consolidated_history_binds_account_id_and_tenant_instead_of_shared_contact():
    space = Makerspace.objects.create(name="Subject", slug="recon-subject")
    other = Makerspace.objects.create(name="Other", slug="recon-subject-other")
    member = User.objects.create_user(username="recon-subject-member", email="shared@example.test")
    # U-A1 makes email unique per person, so a second account cannot share it; the binding
    # under test is account id and tenant, which distinct emails exercise the same way.
    staff = staff_account(space, "recon-subject-staff", email="shared-staff@example.test")
    own = envelope(space, member)
    envelope(space, staff, "Another account")
    envelope(other, member, "Another tenant")
    for item in NotificationEnvelope.objects.all():
        NotificationDelivery.objects.create(
            makerspace=item.makerspace, envelope=item, channel="email", target_key="email", provider="smtp",
        )
    assert list(runtime_subject_query(NotificationEnvelope, member, space.pk).values_list("pk", flat=True)) == [own.pk]
    assert list(runtime_subject_query(NotificationDelivery, member, space.pk).values_list("envelope_id", flat=True)) == [own.pk]


def test_personal_body_uses_authenticated_decryption_and_an_explicit_safe_field_list():
    with enabled_encryption():
        space = Makerspace.objects.create(name="Encrypted", slug="recon-subject-encrypted")
        user = User.objects.create_user(username="recon-subject-encrypted")
        item = envelope(space, user, "Readable only by the subject")
        label = "integrations.NotificationEnvelope"
        raw = NotificationEnvelope.objects.filter(pk=item.pk).values_list("message_body", flat=True).get()
        assert raw != "Readable only by the subject"
        row = runtime_subject_query(NotificationEnvelope, user, space.pk).only(*RUNTIME_FIELDS[label]).get()
        projected = runtime_record(label, row)
        assert projected["message_body"] == "Readable only by the subject"
        assert {"routing_snapshot", "credentials", "provider_id", "target_key"}.isdisjoint(projected)
