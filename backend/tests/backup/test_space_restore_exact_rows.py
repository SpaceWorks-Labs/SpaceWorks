"""A one-space restore can replace rows whose guards only release ONE exact row (decision 245(a)).

`events_booking_decision_guard` and `inventory_equipment_snapshot_guard` ignore the generic
`app.allow_immutable_delete` scope. The restore's raw delete used to hit "not authorized" and roll back.
Real PostgreSQL; not run in source preparation.
"""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from apps.backup import space_restore_exact_rows as exact_rows
from apps.backup.space_restore_graph import raw_delete
from apps.events.models import Event
from apps.events.models_booking_decision import EventBookingDecision
from apps.makerspaces.models import Makerspace

pytestmark = pytest.mark.django_db(transaction=True)


def _decision(slug):
    maker = Makerspace.objects.create(name=slug, slug=slug)
    start = timezone.now() + timedelta(days=2)
    event = Event.objects.create(makerspace=maker, title="Workshop", starts_at=start, ends_at=start + timedelta(hours=1))
    return maker, EventBookingDecision.objects.create(makerspace=maker, event=event, operation_id=uuid4(), intent={})


def test_generic_restore_scope_alone_is_refused_by_the_decision_guard():
    _maker, row = _decision("exact-rows-refused")
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SET LOCAL app.allow_immutable_delete = 'on'")
        cursor.execute("DELETE FROM events_eventbookingdecision WHERE id = %s", [row.pk])
    assert EventBookingDecision.objects.filter(pk=row.pk).exists()


def test_raw_delete_releases_a_decision_under_its_exact_row_permit():
    maker, row = _decision("exact-rows-deleted")
    other_maker, other = _decision("exact-rows-untouched")
    assert exact_rows.guarded(EventBookingDecision)
    with transaction.atomic():
        raw_delete(EventBookingDecision, [row.pk])
        with connection.cursor() as cursor:  # the permit is cleared straight after the statement
            cursor.execute("SELECT current_setting('app.booking_decision_purge_id', true)")
            assert cursor.fetchone()[0] in ("", None)
    assert not EventBookingDecision.objects.filter(pk=row.pk).exists()
    assert EventBookingDecision.objects.filter(pk=other.pk, makerspace=other_maker).exists()
    with pytest.raises(DatabaseError), transaction.atomic():
        EventBookingDecision.objects.filter(pk=other.pk)._raw_delete(using="default")
    assert maker.pk != other_maker.pk


def test_a_missing_row_is_skipped_not_fatal():
    _maker, row = _decision("exact-rows-missing")
    with transaction.atomic():
        raw_delete(EventBookingDecision, [row.pk, row.pk + 10_000])
    assert not EventBookingDecision.objects.filter(pk=row.pk).exists()


def test_booking_link_is_cleared_only_through_the_detach_permit():
    _maker, row = _decision("exact-rows-detach")
    fk = EventBookingDecision._meta.get_field("booking")
    with transaction.atomic():
        assert exact_rows.null_reference(EventBookingDecision, fk, row.pk) is True
    other_fk = EventBookingDecision._meta.get_field("creator")
    assert exact_rows.null_reference(EventBookingDecision, other_fk, row.pk) is False
