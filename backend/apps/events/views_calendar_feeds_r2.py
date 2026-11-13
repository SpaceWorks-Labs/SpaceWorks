"""Shift, combined and public listed-events calendar feeds (release 2 L18, #96, #128 C-14e/f).

Member routes create, rotate and revoke a person's own link; the token routes serve the feed
to a calendar app with the existing per-token and per-IP throttles. Every switch off -- and an
account that is no longer active or in good standing -- answers 404 like an unknown token.
"""

from django.utils.translation import gettext
from django.http import Http404
from django.urls import reverse
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.apiclients.throttling import ClientTierRateThrottle
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.editions import public_surface_available
from apps.makerspaces.lookup import get_public_makerspace
from apps.makerspaces.platform import feature_enabled, module_enabled
from apps.tenant_migration.gate_runtime import tenant_write

from . import calendar_feed_tokens as tokens
from .throttles import EventCalendarFeedIpThrottle, EventCalendarFeedTokenThrottle
from .views_calendar import CALENDAR_ERRORS, CALENDAR_SUCCESS, _calendar_response

KINDS = {"shifts": "events.shifts_feed", "combined": "calendar.combined_feed"}
ROUTES = {"shifts": "public-shift-calendar-feed", "combined": "public-combined-calendar-feed"}
ERRORS = {400: OpenApiResponse(ErrorSerializer), 401: OpenApiResponse(ErrorSerializer),
          403: OpenApiResponse(ErrorSerializer), 404: OpenApiResponse(ErrorSerializer)}


class PersonalFeedStateSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    token_hint = serializers.CharField(allow_null=True)
    created_at = serializers.DateTimeField(allow_null=True)
    rotated_at = serializers.DateTimeField(allow_null=True)


class PersonalFeedIssuedSerializer(serializers.Serializer):
    feed_url = serializers.URLField()
    token_hint = serializers.CharField()


def _in_good_standing(user, space):
    from apps.accounts import rbac
    from apps.presence.guard import require_active_account

    require_active_account(user, space)
    if user.is_tenant_dump_stub or rbac.personal_notification_membership_refused(user, space.pk):
        raise PermissionDenied(gettext("An active account in good standing is required."))


def _space(makerspace_id, kind):
    from apps.makerspaces.models import Makerspace
    from apps.makerspaces.servability import servable_queryset

    space = servable_queryset(Makerspace.objects.filter(pk=makerspace_id)).first()
    if space is None or kind not in KINDS or not feature_enabled(space, KINDS[kind]):
        raise NotFound({"detail": gettext("This calendar is not available here."), "code": "feature_disabled"})
    return space


class PersonalFeedSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Member events"], summary="My shift or combined calendar link (state)",
                   responses={200: PersonalFeedStateSerializer, **ERRORS})
    def get(self, request, makerspace_id, kind):
        space = _space(makerspace_id, kind)
        _in_good_standing(request.user, space)
        return Response(PersonalFeedStateSerializer(tokens.feed_state(space, request.user, kind)).data)

    @extend_schema(tags=["Member events"], summary="Create or rotate my shift or combined calendar link",
                   description="The private URL is shown once; rotating kills the old one. Audited "
                               "`calendar_feed.created|rotated`.", request=None,
                   responses={200: PersonalFeedIssuedSerializer, **ERRORS})
    def post(self, request, makerspace_id, kind):
        space = _space(makerspace_id, kind)
        _in_good_standing(request.user, space)
        with tenant_write(space.pk):
            row, raw = tokens.issue_or_rotate(space, request.user, kind)
        path = reverse(ROUTES[kind], kwargs={"makerspace_slug": space.slug, "raw_token": raw})
        return Response({"feed_url": request.build_absolute_uri(path), "token_hint": row.token_hint},
                        headers={"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer"})

    @extend_schema(tags=["Member events"], summary="Revoke my shift or combined calendar link",
                   description="Audited `calendar_feed.revoked`.", request=None, responses={204: None, **ERRORS})
    def delete(self, request, makerspace_id, kind):
        space = _space(makerspace_id, kind)
        with tenant_write(space.pk):
            tokens.revoke(space, request.user, kind)
        return Response(status=status.HTTP_204_NO_CONTENT)


class _TokenFeedView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [EventCalendarFeedTokenThrottle, EventCalendarFeedIpThrottle]
    kind = ""

    def render(self, space, user):
        raise NotImplementedError

    def get(self, request, makerspace_slug, raw_token):
        try:
            space = get_public_makerspace(makerspace_slug)
        except Http404 as exc:
            raise NotFound() from exc
        if not feature_enabled(space, KINDS[self.kind]):
            raise NotFound()
        row = tokens.resolve(space, raw_token, self.kind)
        if row is None:
            raise NotFound()
        try:
            _in_good_standing(row.user, space)
        except Exception as exc:  # noqa: BLE001 - a lapsed account reads exactly like an unknown token
            raise NotFound() from exc
        return _calendar_response(self.render(space, row.user), f"{self.kind}.ics", request, private=True)


class PublicShiftFeedView(_TokenFeedView):
    kind = "shifts"

    @extend_schema(tags=["Public events"], auth=[], request=None, summary="A person's shift calendar (bearer link)",
                   responses={**CALENDAR_SUCCESS, 404: CALENDAR_ERRORS[404], 429: CALENDAR_ERRORS[429]})
    def get(self, request, makerspace_slug, raw_token):
        return super().get(request, makerspace_slug, raw_token)

    def render(self, space, user):
        from .calendar_feed_shifts import render_shift_calendar

        if not module_enabled(space, "events") or not public_surface_available("events"):
            raise NotFound()
        return render_shift_calendar(space, user)


class PublicCombinedFeedView(_TokenFeedView):
    kind = "combined"

    @extend_schema(tags=["Public events"], auth=[], request=None,
                   summary="A person's combined calendar: bookings, events and shifts (bearer link)",
                   description="Own bookings, registrations and shifts; opaque `Unavailable` / `Space closed` "
                               "blocks only where they overlap the person's own upcoming bookings; and, for a "
                               "person with machine scope while `machines.maintenance` is on, the dated "
                               "maintenance schedules of the machines in that scope.",
                   responses={**CALENDAR_SUCCESS, 404: CALENDAR_ERRORS[404], 429: CALENDAR_ERRORS[429]})
    def get(self, request, makerspace_slug, raw_token):
        return super().get(request, makerspace_slug, raw_token)

    def render(self, space, user):
        from .calendar_feed_combined import render_combined_calendar

        return render_combined_calendar(space, user)


class PublicListedEventsFeedView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ClientTierRateThrottle]
    throttle_scope = "public_read"

    @extend_schema(tags=["Public events"], auth=[], request=None, summary="The space's public events calendar",
                   description="Listed, published events only (`events.public_feed`); 404 while off.",
                   responses={**CALENDAR_SUCCESS, 404: CALENDAR_ERRORS[404], 429: CALENDAR_ERRORS[429]})
    def get(self, request, makerspace_slug):
        from .calendar_feed_combined import render_public_listing

        space = get_public_makerspace(makerspace_slug)
        if (not module_enabled(space, "events") or not public_surface_available("events")
                or not feature_enabled(space, "events.public_feed")):
            raise NotFound()
        return _calendar_response(render_public_listing(space), f"{space.slug}-events.ics", request)
