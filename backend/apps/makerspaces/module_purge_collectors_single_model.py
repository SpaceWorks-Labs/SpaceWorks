"""Purge collectors whose deletion is a single filtered queryset, in dependency order.

Split from `module_purge_collectors` because that module had already outgrown the 300-line
ceiling. The dividing line is a real one rather than mere size: everything here deletes one
model (or reads one model's storage keys) with no ordering constraint against another table,
while the collectors left behind coordinate several models whose delete order matters --
Payment before its generic subject, waiver-acceptance fields before waivers, provenance
before the rows it points at.

`_counts` is defined here and imported by that module rather than the reverse, because the
import already runs in that direction and duplicating it would let the two drift.
"""


class PurgeResult(dict):
    """Public row counts plus model labels owned by the plan's delete operations."""

    def __init__(self, pairs, model_labels):
        super().__init__((name, value) for name, value in pairs.items() if value)
        self.model_labels = frozenset(model_labels)


def _counts(*, model_labels=(), **pairs):
    return PurgeResult(pairs, model_labels)


def _delete(queryset):
    count, per_model = queryset.delete()
    return count, frozenset(per_model) | _cascade_model_labels(queryset.model)


def _cascade_model_labels(model, seen=None):
    """Labels this root delete owns, even when its scoped queryset is empty."""
    from django.db import models

    seen = set() if seen is None else seen
    if model in seen:
        return frozenset()
    seen.add(model)
    labels = {model._meta.label}
    for relation in model._meta.related_objects:
        if relation.field.remote_field.on_delete is models.CASCADE:
            labels.update(_cascade_model_labels(relation.related_model, seen))
    return frozenset(labels)


def bookings_delete(makerspace, cursor):
    from apps.accounts import rbac
    from apps.bookings.models import BookableSpace, Booking, BookingCalendarFeed
    from apps.bookings.models_staff_grants import BookingSpaceStaffGrant, BookingSpaceStaffGrantInvite
    from apps.bookings.models_broadcasts import BookingBroadcast
    from apps.integrations.models import EmailLog
    # Summaries can reference other domains: remove booking entries, then let
    # shared digest delivery rebuild the survivors; do not delete foreign mail.
    rbac.scope_notification_policy(EmailLog.objects.all(), makerspace_id=makerspace.pk).filter(
        source_kind__in=["booking_broadcast", "bookings.booking", "bookings.owner_mailbox", "bookings.guest_mailbox"]).delete()
    campaigns, campaign_labels = _delete(BookingBroadcast.objects.filter(makerspace=makerspace))
    grants, grant_labels = _delete(BookingSpaceStaffGrant.objects.filter(makerspace=makerspace))
    invites, invite_labels = _delete(BookingSpaceStaffGrantInvite.objects.filter(makerspace=makerspace))
    feeds, feed_labels = _delete(rbac.scope_notification_policy(BookingCalendarFeed.objects.all(), makerspace_id=makerspace.pk))

    from apps.bookings.models_arrival import BookingCheckInEvent
    arrivals, arrival_labels = _delete(BookingCheckInEvent.objects.filter(booking__space__makerspace=makerspace))
    from apps.bookings.purge_p2 import delete_departure_history
    departures, departure_labels = delete_departure_history(makerspace)
    bookings, booking_labels = _delete(
        rbac.scope_notification_policy(Booking.objects.all(), makerspace_id=makerspace.pk, field='space__makerspace_id')
    )
    spaces, space_labels = _delete(rbac.scope_notification_policy(BookableSpace.objects.all(), makerspace_id=makerspace.pk))
    return _counts(
        model_labels=(booking_labels | space_labels | feed_labels | grant_labels | invite_labels | arrival_labels
                      | campaign_labels | departure_labels),
        arrivals=arrivals, departures=departures,
        broadcasts=campaigns,
        staff_grants=grants, staff_invites=invites,
        calendar_feeds=feeds,
        bookings=bookings,
        bookable_spaces=spaces,
    )


def bookings_public_images(makerspace):
    from apps.bookings.models import BookableSpace

    from apps.bookings.purge_p2 import photo_keys
    return list(
        BookableSpace.objects.filter(makerspace=makerspace).values_list(
            "image_key", flat=True
        )
    ) + photo_keys(makerspace)


def machine_service_private_keys(makerspace, add):
    from apps.machines.service_lifecycle import collect_private_object_keys

    collect_private_object_keys(makerspace, add)


def machine_service_private_key_sizes(makerspace):
    """Return charged bytes, released only after confirmed object deletion."""
    from apps.machines.models import ServiceRequestFile

    return {
        key: size
        for key, size in ServiceRequestFile.objects.filter(
            makerspace=makerspace,
            service_request__isnull=False,
        ).values_list("object_key", "size_bytes")
        if key
    }


def stocktake_delete(makerspace, cursor):
    from apps.operations.models import StocktakeSession, StocktakePolicy, StocktakeSchedule

    deleted, labels = _delete(StocktakeSession.objects.filter(makerspace=makerspace))
    policies, policy_labels = _delete(StocktakePolicy.objects.filter(makerspace=makerspace))
    schedules, schedule_labels = _delete(StocktakeSchedule.objects.filter(makerspace=makerspace))
    return _counts(model_labels=labels | policy_labels | schedule_labels, stocktake_sessions=deleted,
                   stocktake_policies=policies, stocktake_schedules=schedules)


def stock_transfers_delete(makerspace, cursor):
    from django.db.models import Q

    from apps.operations.models import StockTransfer

    deleted, labels = _delete(
        StockTransfer.objects.filter(
            Q(makerspace=makerspace)
            | Q(source_makerspace=makerspace)
            | Q(destination_makerspace=makerspace)
        )
        .distinct()
    )
    return _counts(model_labels=labels, stock_transfers=deleted)


def qr_print_batches_delete(makerspace, cursor):
    from apps.operations.models import QrPrintBatch

    deleted, labels = _delete(QrPrintBatch.objects.filter(makerspace=makerspace))
    return _counts(model_labels=labels, qr_print_batches=deleted)
