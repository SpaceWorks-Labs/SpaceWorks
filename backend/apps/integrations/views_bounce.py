"""Provider adapters sign `timestamp.raw-body` with the tenant's inbound secret."""

import hashlib
import hmac
import time

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.audit import services as audit
from apps.integrations.email_preferences import address_hash
from apps.integrations.models_suppression import EmailSuppression
from apps.integrations.models_timing import NotificationTimingPolicy
from apps.makerspaces.servability import servable_queryset
from apps.openapi_errors import errors
from apps.tenant_migration.gate_runtime import tenant_write


class BounceSerializer(serializers.Serializer):
    event_id = serializers.CharField(max_length=200)
    address = serializers.EmailField(max_length=254)
    reason = serializers.ChoiceField(choices=('bounce', 'complaint'))


class BounceResultSerializer(serializers.Serializer):
    accepted = serializers.BooleanField()


class BounceWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(tags=['Notifications'], auth=[], request=BounceSerializer,
                   parameters=[OpenApiParameter('X-SpaceWorks-Timestamp', str, location='header', required=True),
                               OpenApiParameter('X-SpaceWorks-Signature', str, location='header', required=True)],
                   responses={200: BounceResultSerializer, **errors(400, 403, 404, 423, 429, 503)},
                   description='HMAC-SHA256 hex of ASCII timestamp + dot + raw JSON body. Five-minute replay window. Hard bounces/complaints only.')
    def post(self, request, makerspace_id):
        space = get_object_or_404(rbac.scope_notification_policy(servable_queryset(), makerspace_id=makerspace_id, field='pk'))
        raw = request.body
        stamp = request.headers.get('X-SpaceWorks-Timestamp', '')
        signature = request.headers.get('X-SpaceWorks-Signature', '')
        policy = rbac.scope_notification_policy(NotificationTimingPolicy.objects.all(), makerspace_id=space.pk).first()
        try:
            if len(raw) > 16384 or not stamp.isascii() or not stamp.isdigit() or abs(time.time() - int(stamp)) > 300:
                raise ValueError()
            secret = policy.get_bounce_secret() if policy else ''
            expected = hmac.new(secret.encode(), stamp.encode('ascii') + b'.' + raw, hashlib.sha256).hexdigest()
            valid = bool(secret) and signature.isascii() and hmac.compare_digest(expected, signature)
        except Exception:
            valid = False
        if not valid:
            raise PermissionDenied('Invalid webhook signature.')
        serializer = BounceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        with tenant_write(space.pk):
            row, created = rbac.scope_notification_policy(EmailSuppression.objects.all(), makerspace_id=space.pk).get_or_create(
                makerspace=space, address_hash=address_hash(space.pk, values['address']),
                defaults={'reason': values['reason']},
            )
            row = rbac.scope_notification_policy(EmailSuppression.objects.select_for_update(), makerspace_id=space.pk).get(pk=row.pk)
            changed = values['reason'] == 'complaint' and row.reason != 'complaint'
            if changed:
                row.reason = 'complaint'
                row.save(update_fields=['reason'])
            if created or changed:
                audit.record(None, 'email.suppressed_provider', makerspace=space, target=row,
                             meta={'reason': row.reason})
        return Response({'accepted': True})


class ProviderBounceWebhookView(APIView):
    """Optional native callbacks. I mounts the route and regenerates schema/client."""
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(tags=['Notifications'], auth=[], request={'application/json': {'type': 'object', 'additionalProperties': True}},
                   parameters=[OpenApiParameter('svix-id', str, location='header'),
                               OpenApiParameter('svix-timestamp', str, location='header'),
                               OpenApiParameter('svix-signature', str, location='header')],
                   responses={200: BounceResultSerializer, **errors(400, 403, 404, 423, 429, 503)},
                   description='Opt-in native Resend (Svix headers) / Mailgun (signed JSON) callbacks. '
                   'Five-minute signature window, durable replay receipts and scoped opaque message mapping. '
                   'API acceptance and observed delivery are separate. Disabled by default.')
    def post(self, request, makerspace_id, provider):
        from django.conf import settings
        from rest_framework.exceptions import NotFound
        from .mail_providers.selection import stored_config
        from .mail_providers.webhook_signatures import verify
        from .mail_providers.webhooks import observe
        if not getattr(settings, 'EMAIL_PROVIDER_WEBHOOKS_ENABLED', False) or provider not in {'resend', 'mailgun'}:
            raise NotFound()
        space = get_object_or_404(rbac.scope_notification_policy(servable_queryset(), makerspace_id=makerspace_id, field='pk'))
        try:
            config = stored_config(space, tenant=True)
            if config is None or config.provider != provider:
                raise ValueError()
            # Header signatures authenticate exact raw bytes; no raw body enters logs.
            event = verify(provider, request.body, request.headers, config.credentials)
        except Exception:
            raise PermissionDenied('Invalid webhook signature.') from None
        from django.db import DatabaseError
        try:
            observed = observe(space, provider, event)
        except DatabaseError:
            observed = False
        if not observed:
            return Response({'detail': 'Email observation is not ready.', 'code': 'email_observation_not_ready'}, status=503)
        return Response({'accepted': True})
