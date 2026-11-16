"""Exact-row retained-decision purge operations under the existing tenant fence."""
from django.apps import apps
from django.db import IntegrityError, connection, transaction
from django.db.models import F


def _decision_model():
    if not apps.is_installed("apps.events"):
        return None
    return apps.get_model("events", "EventBookingDecision")


def _perform(makerspace, *, detach):
    if not connection.in_atomic_block:
        raise RuntimeError("Booking decision purge requires the tenant transaction.")
    Decision = _decision_model()
    if Decision is None:
        return 0
    rows = Decision.objects.filter(makerspace_id=makerspace.pk)
    if rows.exclude(event__makerspace_id=F("makerspace_id")).exists():
        raise IntegrityError("Invalid retained event ownership.")
    if detach:
        rows = rows.filter(booking__isnull=False)
        if rows.exclude(booking__space__makerspace_id=F("makerspace_id")).exists():
            raise IntegrityError("Invalid retained booking ownership.")
    ids = rows.order_by("pk").values_list("pk", flat=True).iterator(chunk_size=128)
    count = 0
    for pk in ids:
        # The savepoint restores transaction-local settings on any failed operation.
        with transaction.atomic():
            row = Decision.objects.select_for_update(of=("self",)).get(pk=pk, makerspace_id=makerspace.pk)
            action = "detach" if detach else "delete"
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.booking_decision_purge_id', %s, true)", [str(pk)])
                cursor.execute("SELECT set_config('app.booking_decision_purge_maker', %s, true)", [str(makerspace.pk)])
                cursor.execute("SELECT set_config('app.booking_decision_purge_action', %s, true)", [action])
            if detach:
                count += Decision.objects.filter(pk=row.pk, makerspace_id=makerspace.pk, booking__isnull=False).update(booking=None)
            else:
                deleted, _ = Decision.objects.filter(pk=row.pk, makerspace_id=makerspace.pk).delete()
                count += deleted
            with connection.cursor() as cursor:
                for key in ("app.booking_decision_purge_id", "app.booking_decision_purge_maker", "app.booking_decision_purge_action"):
                    cursor.execute("SELECT set_config(%s, '', true)", [key])
    return count


def detach_booking_decisions(makerspace):
    return _perform(makerspace, detach=True)


def delete_booking_decisions(makerspace):
    return _perform(makerspace, detach=False)
