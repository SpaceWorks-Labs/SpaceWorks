"""A person's remembered devices (lane S-B): list and forget.

A remembered device only spares the unusual-login check; it never skips a second factor.
"""

from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts import device_memory
from apps.openapi_errors import errors


class KnownDeviceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    label = serializers.CharField(source="ua_label", help_text='A coarse label such as "Firefox on Windows".')
    created_at = serializers.DateTimeField()
    last_verified_at = serializers.DateTimeField(help_text="The last completed sign-in on this device.")
    current = serializers.SerializerMethodField(help_text="This browser or app.")

    def get_current(self, obj) -> bool:
        return obj.pk == self.context.get("current_id")


class KnownDeviceListSerializer(serializers.Serializer):
    devices = KnownDeviceSerializer(many=True)
    remembered_days = serializers.IntegerField(
        help_text="How long a device stays remembered without a sign-in (the strictest across your staff spaces).")


class _Person(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "mfa_manage"


class KnownDeviceListView(_Person):
    @extend_schema(tags=["Auth"], summary="List your remembered devices",
                   responses={200: KnownDeviceListSerializer, **errors(401, 403, 429)})
    def get(self, request):
        current = device_memory.lookup(request, request.user)
        rows = device_memory.live_devices(request.user)[:100]
        data = KnownDeviceListSerializer({"devices": rows, "remembered_days": device_memory.remembered_days(
            request.user)}, context={"current_id": getattr(current, "pk", None)}).data
        response = Response(data)
        response["Cache-Control"] = "no-store"
        return response


class KnownDeviceDetailView(_Person):
    @extend_schema(tags=["Auth"], summary="Forget one of your remembered devices",
                   description="Its next sign-in is checked as unusual again. 404 when it is not yours.",
                   responses={204: None, **errors(401, 403, 404, 429)})
    def delete(self, request, device_id):
        if not device_memory.forget(request.user, device_id, request=request):
            raise Http404
        return Response(status=204)
