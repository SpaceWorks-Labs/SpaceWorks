from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from .models import EventMemberCard
from .policy import public_profile
from .snapshot import prepare_photo
from .views import ERRORS, private
import hashlib
from datetime import timedelta
from django.utils import timezone


class PublicPhotoThrottle(AnonRateThrottle):
    rate = "60/min"


class PublicCardPhotoView(APIView):
    permission_classes = [AllowAny]
    # No authentication: AnonRateThrottle skips signed-in callers, so a bearer would lift the limit.
    authentication_classes = []
    throttle_classes = [PublicPhotoThrottle]

    def finalize_response(self, request, response, *args, **kwargs):
        return private(super().finalize_response(request, response, *args, **kwargs))

    @extend_schema(tags=["Event presentation"], responses={(200, "image/png"): OpenApiTypes.BINARY, **ERRORS})
    def get(self, request, public_token, card_public_id):
        card = get_object_or_404(EventMemberCard.objects.select_related("presentation__event__makerspace"),
                                 public_id=card_public_id, presentation__event__public_token=public_token)
        from apps.makerspaces.public_profile_access import _request_tenant_ids
        if any(pk != card.presentation.event.makerspace_id for pk in _request_tenant_ids(request)):
            raise NotFound()
        selected = public_profile(card.presentation, card.scope)
        if not selected or not selected[0].avatar_key:
            raise NotFound()
        photo = prepare_photo(selected[0])
        # Storage never runs under locks; re-read all consents before releasing bytes.
        card.refresh_from_db()
        card.presentation.refresh_from_db()
        selected = public_profile(card.presentation, card.scope)
        if (not selected or selected[0].updated_at.isoformat().replace("+00:00", "Z") != photo.source_revision
                or hashlib.sha256(selected[0].avatar_key.encode()).hexdigest() != photo.source_key_digest):
            raise NotFound()
        from apps.events.credentials.streaming import private_bytes
        def authorize():
            try:
                card.refresh_from_db()
            except EventMemberCard.DoesNotExist as exc:
                raise NotFound() from exc
            current = public_profile(card.presentation, card.scope)
            if (not current or current[0].updated_at.isoformat().replace("+00:00", "Z") != photo.source_revision
                    or hashlib.sha256(current[0].avatar_key.encode()).hexdigest() != photo.source_key_digest):
                raise NotFound()
        return private_bytes(request, photo.pixels, authorize=authorize,
            expires_at=timezone.now()+timedelta(minutes=2), mime="image/png", locator_key=f"event-card:{card.public_id}")
