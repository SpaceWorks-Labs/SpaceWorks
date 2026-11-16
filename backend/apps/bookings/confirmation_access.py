"""Live feature and owner checks for private confirmations."""
from rest_framework.exceptions import NotFound
from apps.makerspaces.platform import feature_enabled


def require_feature(makerspace, key):
    if not feature_enabled(makerspace, key):
        raise NotFound()


def owned_confirmation(request, slug, token):
    from .views_member import own_booking
    booking = own_booking(request, slug, token)
    require_feature(booking.space.makerspace, "bookings.confirmations")
    return booking


from apps.makerspaces.confirmation_privacy import private_response  # explicit compatibility export
