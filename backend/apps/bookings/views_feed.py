"""Revocable private ICS capabilities; tokens and contact fields never enter the feed."""

import hmac
import re
import secrets

from django.db import transaction
from django.db.models import Case, DateTimeField, F, IntegerField, Value, When
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import serializers
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.audit import services as audit
from apps.bookings.models import Booking
from apps.bookings.models_feed import BookingCalendarFeed
from apps.bookings.views_member import own_bookings
from apps.makerspaces.lookup import get_public_makerspace
from apps.makerspaces.guards import require_module_for_servable, require_module_locked
from apps.openapi_errors import errors
from apps.presence.guard import require_active_account
from apps.tenant_migration.gate_runtime import tenant_write


def digest(raw):
    # Import the existing pattern, without installing events as a booking prerequisite.
    # events' services import an Event model; with events tombstoned use its exact
    # SHA-256 format locally rather than importing an unavailable model module.
    from apps.separability.registry import runtime_active
    if runtime_active('events'):
        from apps.events.services_calendar_feeds import token_digest
        return token_digest(raw)
    import hashlib
    return hashlib.sha256(raw.encode('ascii')).digest()


class FeedStateSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    token_hint = serializers.CharField(allow_null=True)


class FeedIssuedSerializer(serializers.Serializer):
    feed_url = serializers.URLField()
    token_hint = serializers.CharField()


def _feeds(space):
    return rbac.scope_notification_policy(BookingCalendarFeed.objects.all(), makerspace_id=space.pk)


def _require_switch(space):
    """Release 2 L18: `bookings.calendar_feed` (on by default) switches the private feed off."""
    from apps.makerspaces.platform import feature_enabled
    if not feature_enabled(space, 'bookings.calendar_feed'):
        raise NotFound({'detail': 'The booking calendar feed is turned off here.', 'code': 'feature_disabled'})


def _require_owner(user, space):
    _require_switch(space)
    require_active_account(user, space)
    if user.is_tenant_dump_stub or rbac.personal_notification_membership_refused(user, space.pk):
        raise PermissionDenied('An active account in good standing is required.')


class BookingFeedSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Member bookings'], responses={200: FeedStateSerializer, **errors(400, 401, 403, 404)})
    def get(self, request, makerspace_slug):
        own_bookings(request, makerspace_slug)
        space = get_public_makerspace(makerspace_slug)
        _require_owner(request.user, space)
        row = _feeds(space).filter(user=request.user, revoked_at__isnull=True).first()
        return Response({'enabled': row is not None, 'token_hint': row.token_hint if row else None})

    @extend_schema(tags=['Member bookings'], request=None,
                   responses={200: FeedIssuedSerializer, **errors(400, 401, 403, 404, 423, 503)})
    def post(self, request, makerspace_slug):
        own_bookings(request, makerspace_slug)
        space = get_public_makerspace(makerspace_slug)
        _require_owner(request.user, space)
        with tenant_write(space.pk):
            require_module_locked(space, 'bookings')
            # Serialize first issuance and rotations on the owning account; no nullable join.
            owner = type(request.user).objects.select_for_update().get(pk=request.user.pk)
            _require_owner(owner, space)
            raw = secrets.token_urlsafe(32)
            row, created = _feeds(space).get_or_create(makerspace=space, user=request.user,
                defaults={'token_digest': digest(raw), 'token_hint': raw[-8:]})
            if not created:
                row.token_digest, row.token_hint = digest(raw), raw[-8:]
                row.rotated_at, row.revoked_at = timezone.now(), None
                row.save(update_fields=['token_digest', 'token_hint', 'rotated_at', 'revoked_at'])
            audit.record(request.user, 'booking.feed_created' if created else 'booking.feed_rotated',
                         makerspace=space, target=row)
        path = reverse('public-booking-feed', kwargs={'makerspace_slug': space.slug, 'raw_token': raw})
        return Response({'feed_url': request.build_absolute_uri(path), 'token_hint': row.token_hint},
                        headers={'Cache-Control': 'private, no-store', 'Referrer-Policy': 'no-referrer'})

    @extend_schema(tags=['Member bookings'], request=None,
                   responses={204: None, **errors(400, 401, 403, 404, 423, 503)})
    def delete(self, request, makerspace_slug):
        own_bookings(request, makerspace_slug)
        space = get_public_makerspace(makerspace_slug)
        _require_owner(request.user, space)
        with tenant_write(space.pk):
            require_module_locked(space, 'bookings')
            owner = type(request.user).objects.select_for_update().get(pk=request.user.pk)
            _require_owner(owner, space)
            row = _feeds(space).select_for_update().filter(user=request.user, revoked_at__isnull=True).first()
            if row:
                row.revoked_at = timezone.now()
                row.save(update_fields=['revoked_at'])
                audit.record(request.user, 'booking.feed_revoked', makerspace=space, target=row)
        return Response(status=204)


from .throttles_feed import BookingFeedIpThrottle, BookingFeedTokenThrottle


class PublicBookingFeedView(APIView):
    throttle_classes = [BookingFeedTokenThrottle, BookingFeedIpThrottle]
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(tags=['Member bookings'], auth=[], responses={
        (200, 'text/calendar'): OpenApiResponse({'type': 'string'}, description='Own reservations as RFC 5545 ICS.'),
        **errors(400, 403, 404, 429),
    })
    def get(self, request, makerspace_slug, raw_token):
        space = get_public_makerspace(makerspace_slug)
        require_module_for_servable(space, 'bookings')
        _require_switch(space)
        if not re.fullmatch(r'[A-Za-z0-9_-]{43}', raw_token or ''):
            raise NotFound()
        hashed = digest(raw_token)
        row = _feeds(space).select_related('user').filter(token_digest=hashed, revoked_at__isnull=True).first()
        if row is None or not hmac.compare_digest(bytes(row.token_digest), hashed):
            raise NotFound()
        require_active_account(row.user, space)
        if rbac.personal_notification_membership_refused(row.user, space.pk):
            raise NotFound()
        from .calendar_render import booking_calendar
        rows = rbac.scope_personal_bookings(row.user, Booking.objects.select_related('space').filter(
            member=row.user, space__makerspace=space,
        ), makerspace_id=space.pk)
        # Bound the response without letting years of old reservations crowd out
        # upcoming ones. Fill spare slots with the most recent history.
        now = timezone.now()
        rows = rows.annotate(
            history=Case(When(ends_at__lt=now, then=Value(1)), default=Value(0), output_field=IntegerField()),
            upcoming_start=Case(When(ends_at__gte=now, then=F('starts_at')), output_field=DateTimeField()),
        ).order_by('history', 'upcoming_start', '-starts_at', 'pk')
        response = HttpResponse(booking_calendar(rows[:1000]), content_type='text/calendar; charset=utf-8')
        response['Cache-Control'] = 'private, no-store'
        response['Referrer-Policy'] = 'no-referrer'
        return response
