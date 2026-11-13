"""Event responses that carry the venue offers (decision 223 (m))."""

from rest_framework import serializers

from .serializers_admin import EventAdminSerializer
from .venue_offers import VenueOfferSerializer, venue_offers


class EventAdminWithOffersSerializer(EventAdminSerializer):
    class Meta(EventAdminSerializer.Meta):
        fields = (*EventAdminSerializer.Meta.fields, "venue_offers")

    venue_offers = VenueOfferSerializer(
        many=True, required=False, read_only=True,
        help_text="Decision 223 (m): actions to take next on the linked room booking or venue fee after a "
                  "cancel or a move. Offers only; nothing was changed automatically.")


def with_offers(request, event, *, offers=True):
    """EventAdminSerializer data plus `venue_offers` (empty when nothing is linked)."""
    data = dict(EventAdminSerializer(event, context={"request": request}).data)
    data["venue_offers"] = venue_offers(request.user, event) if offers else []
    return data
