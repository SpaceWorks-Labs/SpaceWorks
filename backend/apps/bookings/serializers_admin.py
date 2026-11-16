"""Compatibility imports for the focused staff booking serializer contracts."""

from .serializers_admin_actions import (
    BookableSpaceListResponseSerializer,
    BookingListFilterSerializer,
    BookingListResponseSerializer,
    EmptyActionSerializer,
    SpaceImageFinalizeRequestSerializer,
    SpaceImagePresignRequestSerializer,
    SpaceImagePresignResponseSerializer,
    SpaceImageUploadSerializer,
)
from .serializers_reservation import BookingAdminSerializer
from .serializers_space_admin import BookableSpaceAdminSerializer
from .serializers_space_write import (
    BookableSpaceBookingRulesSerializer,
    BookableSpaceWriteSerializer,
)
