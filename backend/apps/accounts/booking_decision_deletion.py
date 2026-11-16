"""Exact-row creator erasure before authorized hard deletion of a person."""
from django.apps import apps
from django.db import connection, transaction


def clear_booking_decision_creators(user_ids):
    """Caller holds the person rows and wraps clearing plus deletion in one atomic block."""
    model = apps.get_model("events", "EventBookingDecision")  # Retention model remains installed.
    rows = model.objects.select_for_update(of=("self",)).filter(creator_id__in=user_ids).order_by("pk")
    for row in rows.iterator():
        # Rollback to this savepoint restores transaction-local settings even on SQL failure.
        with transaction.atomic():
            with connection.cursor() as cursor:
                for key, value in (("row", row.pk), ("maker", row.makerspace_id), ("user", row.creator_id)):
                    cursor.execute("SELECT set_config(%s, %s, true)", ["app.booking_decision_creator_" + key, str(value)])
            changed = model.objects.filter(pk=row.pk, makerspace_id=row.makerspace_id,
                                           creator_id=row.creator_id).update(creator_id=None, intent={"version": 1, "unavailable": True})
            if changed != 1:
                raise RuntimeError("Booking decision creator changed during deletion.")
            with connection.cursor() as cursor:
                for key in ("row", "maker", "user"):
                    cursor.execute("SELECT set_config(%s, '', true)", ["app.booking_decision_creator_" + key])
