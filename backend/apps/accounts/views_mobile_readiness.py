from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.mobile_readiness import mobile_readiness
from apps.admin_api.permissions import IsActiveSuperAdmin
from apps.openapi_errors import errors


class ReadinessItemSerializer(serializers.Serializer):
    ready = serializers.BooleanField()
    hint = serializers.CharField()


class RegistrationReadinessSerializer(serializers.Serializer):
    hint = serializers.CharField()
    production = serializers.BooleanField()
    login_ready = serializers.BooleanField()
    login = serializers.DictField(child=ReadinessItemSerializer())
    optional = serializers.DictField(child=ReadinessItemSerializer())


class PlatformReadinessSerializer(serializers.Serializer):
    hint = serializers.CharField()
    login_ready = serializers.BooleanField()
    push_ready = serializers.BooleanField()
    apple_revocation_ready = serializers.BooleanField()
    associations_ready = serializers.BooleanField()
    registrations = RegistrationReadinessSerializer(many=True)


class MobileReadinessSerializer(serializers.Serializer):
    platforms = serializers.DictField(child=PlatformReadinessSerializer())


class MobileReadinessView(APIView):
    permission_classes = [IsActiveSuperAdmin]
    http_method_names = ["get", "head", "options"]

    @extend_schema(tags=["Platform"], summary="Native mobile integration readiness",
                   description="Read-only configuration checks, grouped by registration/environment and platform. No provider probes or secret values.",
                   responses={200: MobileReadinessSerializer, **errors(401, 403)})
    def get(self, request):
        response = Response(mobile_readiness())
        response["Cache-Control"] = "no-store"
        return response
