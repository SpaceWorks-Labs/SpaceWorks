"""Strict reads distinguish in-memory edits from legacy plaintext in storage."""

from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from apps.bookings.models import BookableSpace, Booking
from apps.encryption.crypto import LegacyPlaintextRejected, is_envelope
from tests.encryption.conftest import enabled_encryption
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db


def booking():
    resource = BookableSpace.objects.create(makerspace=make_space("strict-booking"), name="Room")
    now = timezone.now()
    return Booking.objects.create(space=resource, name="Member", email="member@example.test",
                                  phone="123", starts_at=now, ends_at=now + timedelta(hours=1))


@pytest.mark.parametrize("reload", [False, True])
def test_strict_booking_normalization_and_reassignment_encrypt_the_new_values(reload):
    with enabled_encryption(dual_read=False):
        row = booking()
        if reload:
            row = Booking.objects.get(pk=row.pk)
        assert row.name == "Member"  # Populate the old decrypt cache.
        row.name, row.email, row.phone = "  Deleted member  ", "DELETED@INVALID.INVALID", "Deleted"
        row.note = "new private note"
        row.save(update_fields=["name", "email", "phone", "note"])
        row.refresh_from_db()
        assert (row.name, row.email, row.phone, row.note) == (
            "Deleted member", "deleted@invalid.invalid", "Deleted", "new private note")
        with connection.cursor() as cursor:
            cursor.execute('SELECT name, email, phone, note FROM bookings_booking WHERE id = %s', [row.pk])
            assert all(is_envelope(value) for value in cursor.fetchone())
        row.refresh_from_db(fields=["note"])
        assert row.name == "Deleted member" and row.note == "new private note"


def test_strict_booking_reads_still_reject_persisted_plaintext_after_refresh():
    row = booking()
    with enabled_encryption(dual_read=False):
        loaded = Booking.objects.get(pk=row.pk)
        with pytest.raises(LegacyPlaintextRejected):
            _ = loaded.name
        # refresh_from_db assigns loaded attributes internally; it must not
        # make persisted legacy plaintext look like a caller's fresh edit.
        with pytest.raises(LegacyPlaintextRejected):
            row.refresh_from_db()
