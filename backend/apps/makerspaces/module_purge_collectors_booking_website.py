"""Retention survives Bookings tombstoning; rows cascade from BookableSpace."""


def bookings_private_keys(makerspace, add):
    for key in bookings_private_key_sizes(makerspace):
        add(key)


def bookings_private_key_sizes(makerspace):
    from apps.bookings.models_website import BookingResourcePageAsset
    return dict(BookingResourcePageAsset.objects.filter(
        page__space__makerspace=makerspace,
    ).values_list("object_key", "size_bytes"))
