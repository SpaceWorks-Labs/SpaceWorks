"""Booking campaign rollout and rollback use the supported tenant-scoped commands."""

from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from apps.bookings.models import BookableSpace, BookingBroadcast
from apps.encryption.crypto import LegacyPlaintextRejected, is_envelope
from apps.encryption.write_fence import close_global, reopen
from apps.makerspaces.models import Makerspace
from tests.encryption.conftest import enabled_encryption


pytestmark = pytest.mark.django_db
LABEL = "bookings.BookingBroadcast"
CONTENT = ("Workshop update", "Please bring your booking confirmation.")


def _campaign(slug):
    tenant = Makerspace.objects.create(name=slug, slug=slug)
    resource = BookableSpace.objects.create(makerspace=tenant, name="Workshop")
    start = timezone.now()
    return BookingBroadcast.objects.create(
        makerspace=tenant, space=resource, subject=CONTENT[0], body=CONTENT[1],
        window_start=start, window_end=start + timedelta(days=1),
    )


def _stored(campaign):
    # values_list bypasses the mapped attribute reader, so these are DB values.
    return BookingBroadcast.objects.filter(pk=campaign.pk).values_list("subject", "body").get()


def test_backfill_encrypts_legacy_booking_broadcast_for_strict_reads_in_one_tenant():
    with override_settings(PII_ENCRYPTION_ENABLED=False):
        campaign = _campaign("booking-backfill")
        other = _campaign("booking-backfill-other")
    assert _stored(campaign) == _stored(other) == CONTENT

    with enabled_encryption():
        call_command(
            "backfill_scoped_pii", makerspace=campaign.makerspace_id, model=LABEL,
            dry_run=True, stdout=StringIO(),
        )
        assert _stored(campaign) == CONTENT
        call_command(
            "backfill_scoped_pii", makerspace=campaign.makerspace_id, model=LABEL,
            batch_size=1, stdout=StringIO(),
        )
        assert all(is_envelope(value) for value in _stored(campaign))
        assert _stored(other) == CONTENT

        with override_settings(PII_ENCRYPTION_DUAL_READ=False):
            restored = BookingBroadcast.objects.get(pk=campaign.pk)
            assert (restored.subject, restored.body) == CONTENT
            call_command(
                "backfill_scoped_pii", makerspace=campaign.makerspace_id, model=LABEL,
                verify_only=True, stdout=StringIO(),
            )
            with pytest.raises(LegacyPlaintextRejected):
                _ = BookingBroadcast.objects.get(pk=other.pk).subject


def test_fenced_rollback_decrypts_booking_broadcast_only_in_requested_tenant():
    actor = get_user_model().objects.create_superuser(
        username="booking-rollback-operator", is_active=True, is_superuser=True,
    )
    with enabled_encryption():
        campaign = _campaign("booking-rollback")
        other = _campaign("booking-rollback-other")
        before, other_before = _stored(campaign), _stored(other)
        assert all(is_envelope(value) for value in (*before, *other_before))
        operation = close_global("decrypt_rollback", actor.pk, all_makerspaces=True)
        try:
            call_command(
                "decrypt_scoped_pii", makerspace=campaign.makerspace_id, model=LABEL,
                actor_id=actor.pk, dry_run=True, stdout=StringIO(),
            )
            assert _stored(campaign) == before
            call_command(
                "decrypt_scoped_pii", makerspace=campaign.makerspace_id, model=LABEL,
                actor_id=actor.pk, confirm_makerspace=campaign.makerspace_id,
                fence_operation=str(operation), batch_size=1, stdout=StringIO(),
            )
            assert _stored(campaign) == CONTENT
            assert _stored(other) == other_before
            call_command(
                "decrypt_scoped_pii", makerspace=campaign.makerspace_id, model=LABEL,
                actor_id=actor.pk, verify_only=True, stdout=StringIO(),
            )
            with override_settings(PII_ENCRYPTION_ENABLED=False):
                restored = BookingBroadcast.objects.get(pk=campaign.pk)
                assert (restored.subject, restored.body) == CONTENT
        finally:
            reopen(operation, actor.pk)
