"""Public "Hosted at" venue block for a public event: host makerspace + place photos.

Events carry a free-text location, not a resource link, so the venue is resolved by
matching that label against the host's PUBLIC, active bookable spaces (name first, then
the space's own location label). Without a match the block still names the host and
falls back to the host's public cover image. Only already-public fields are returned.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.apiclients.throttling import ClientTierRateThrottle
from apps.inventory.public_image_storage import public_url
from apps.makerspaces.guards import require_module_for_servable
from apps.makerspaces.lookup import get_public_makerspace
from apps.makerspaces.platform import module_enabled

from .serializers_public import PublicSpacePhotoSerializer
from .services_gallery import public_photos
from .views_public import PUBLIC_BOOKING_ERRORS
from .website_visibility import public_spaces


class VenueHostSerializer(serializers.Serializer):
    name = serializers.CharField()
    slug = serializers.CharField()
    location = serializers.CharField(allow_blank=True)
    map_url = serializers.CharField(allow_blank=True)
    logo_url = serializers.CharField(allow_blank=True)


class VenueSpaceSerializer(serializers.Serializer):
    public_token = serializers.UUIDField()
    name = serializers.CharField()
    kind = serializers.CharField()
    location = serializers.CharField(allow_blank=True)
    capacity = serializers.IntegerField()


class PublicEventVenueSerializer(serializers.Serializer):
    host = VenueHostSerializer()
    space = VenueSpaceSerializer(allow_null=True)
    photos = PublicSpacePhotoSerializer(many=True)


def venue_space(makerspace, label):
    label = (label or "").strip()
    if not label or not module_enabled(makerspace, "bookings"):
        return None
    spaces = public_spaces(makerspace).prefetch_related("photos")
    return spaces.filter(name__iexact=label).first() or spaces.filter(location__iexact=label).first()


def venue_payload(makerspace, label):
    space = venue_space(makerspace, label)
    photos = public_photos(space) if space else []
    if not photos and makerspace.cover_image_key:
        photos = [{"id": 0, "url": public_url(makerspace.cover_image_key), "caption": makerspace.name}]
    return {
        "host": {"name": makerspace.name, "slug": makerspace.slug, "location": makerspace.location,
                 "map_url": makerspace.map_url, "logo_url": public_url(makerspace.logo_key) if makerspace.logo_key else ""},
        "space": space and {"public_token": space.public_token, "name": space.name, "kind": space.kind,
                            "location": space.location, "capacity": space.capacity},
        "photos": photos,
    }


class PublicEventVenueView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ClientTierRateThrottle]
    throttle_scope = "public_read"

    @extend_schema(tags=["Public bookings"], auth=[], request=None, summary="Hosted-at venue for a public event",
                   responses={200: PublicEventVenueSerializer, **PUBLIC_BOOKING_ERRORS})
    def get(self, request, makerspace_slug, public_token):
        from django.http import Http404
        from apps.separability.tombstones import app_is_tombstoned
        if app_is_tombstoned("events"):  # bookings must keep working without the events app
            raise Http404
        from apps.events.website_visibility import public_events
        makerspace = get_public_makerspace(makerspace_slug)
        require_module_for_servable(makerspace, "events")
        event = get_object_or_404(public_events(makerspace), public_token=public_token)
        return Response(PublicEventVenueSerializer(venue_payload(makerspace, event.location)).data)
