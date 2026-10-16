"""Phase 2 bookings rows for module purge, tenant purge and storage accounting.

Departure history is append-only (trigger-protected) and PROTECT-linked to its booking,
so purges delete issues, then departure events, before bookings -- inside the callers'
`app.allow_immutable_delete` scope. Place photos cascade from their space; their public
image keys are listed so the purge deletes the bytes and storage accounting counts them.
"""


def delete_departure_history(makerspace):
    from .models_departure import BookingDepartureEvent, BookingIssue
    issues, issue_labels = BookingIssue.objects.filter(makerspace=makerspace).delete()
    events, event_labels = BookingDepartureEvent.objects.filter(makerspace=makerspace).delete()
    labels = frozenset(issue_labels) | frozenset(event_labels) | {
        BookingIssue._meta.label, BookingDepartureEvent._meta.label}
    return issues + events, labels


def photo_keys(makerspace):
    from .models_gallery import BookableSpacePhoto
    return list(BookableSpacePhoto.objects.filter(space__makerspace=makerspace).values_list("object_key", flat=True))
