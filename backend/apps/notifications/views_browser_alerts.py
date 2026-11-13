"""Browser-notification opt-in per person per space (X38). 404 while `notifications.web_push` is off."""

from django.utils.translation import gettext
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit import services as audit
from apps.makerspaces.platform import feature_enabled
from apps.openapi_errors import errors
from apps.tenant_migration.gate_runtime import tenant_write

from .access import personal_space
from .browser_alerts import FEATURE, allowed_endpoint, configured, endpoint_hash, public_key
from .models_browser_alerts import BrowserAlertSubscription


class BrowserAlertKeySerializer(serializers.Serializer):
    configured = serializers.BooleanField()
    public_key = serializers.CharField(allow_blank=True, help_text="VAPID applicationServerKey (base64url).")


class SubscriptionKeysSerializer(serializers.Serializer):
    p256dh = serializers.RegexField(r"^[A-Za-z0-9_-]{80,100}$")
    auth = serializers.RegexField(r"^[A-Za-z0-9_-]{16,32}$")


class SubscriptionWriteSerializer(serializers.Serializer):
    endpoint = serializers.URLField(max_length=1024)
    keys = SubscriptionKeysSerializer(required=False)


class SubscriptionStateSerializer(serializers.Serializer):
    subscribed_browsers = serializers.IntegerField(min_value=0)


class BrowserAlertKeyView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Personal notifications"], responses={200: BrowserAlertKeySerializer, **errors(401)})
    def get(self, request):
        return Response({"configured": configured(), "public_key": public_key()})


class BrowserAlertSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def space(self, request, makerspace_id):
        space = personal_space(request.user, makerspace_id)
        if not feature_enabled(space, FEATURE) or not configured():
            raise NotFound()
        return space

    def _state(self, request, space):
        count = BrowserAlertSubscription.objects.filter(makerspace=space, user=request.user,
                                                        revoked_at__isnull=True).count()
        return Response({"subscribed_browsers": count})

    @extend_schema(tags=["Personal notifications"], responses={200: SubscriptionStateSerializer, **errors(401, 403, 404)})
    def get(self, request, makerspace_id):
        return self._state(request, self.space(request, makerspace_id))

    @extend_schema(tags=["Personal notifications"], request=SubscriptionWriteSerializer,
                   responses={200: SubscriptionStateSerializer, **errors(400, 401, 403, 404)},
                   description="Opt this browser in. Only public push services are accepted as endpoints.")
    def post(self, request, makerspace_id):
        space = self.space(request, makerspace_id)
        payload = SubscriptionWriteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        if not allowed_endpoint(data["endpoint"]) or "keys" not in data:
            raise ValidationError({"endpoint": gettext("Use a browser push subscription from a supported browser.")})
        with tenant_write(space.pk):
            row = BrowserAlertSubscription.objects.filter(makerspace=space, user=request.user,
                                                          endpoint_sha256=endpoint_hash(data["endpoint"])).first()
            row = row or BrowserAlertSubscription(makerspace=space, user=request.user,
                                                  endpoint_sha256=endpoint_hash(data["endpoint"]))
            row.set_secrets(data["endpoint"], data["keys"]["auth"])
            row.p256dh, row.revoked_at, row.failures = data["keys"]["p256dh"], None, 0
            row.save()
            audit.record(request.user, "notification.browser_alert_subscribed", makerspace=space, target=space)
        return self._state(request, space)

    @extend_schema(tags=["Personal notifications"], request=SubscriptionWriteSerializer,
                   responses={200: SubscriptionStateSerializer, **errors(400, 401, 403, 404)},
                   description="Opt this browser out (send the same endpoint).")
    def delete(self, request, makerspace_id):
        space = self.space(request, makerspace_id)
        payload = SubscriptionWriteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        with tenant_write(space.pk):
            BrowserAlertSubscription.objects.filter(
                makerspace=space, user=request.user, endpoint_sha256=endpoint_hash(payload.validated_data["endpoint"]),
                revoked_at__isnull=True).update(revoked_at=timezone.now())
            audit.record(request.user, "notification.browser_alert_unsubscribed", makerspace=space, target=space)
        return self._state(request, space)
