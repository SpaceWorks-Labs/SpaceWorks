from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.organizations.models import Organization
from apps.organizations.serializers_admin import OrganizationDetailSerializer
from apps.organizations.services_self_service import create_self_service, creation_policy
from apps.organizations.views_console import console_errors


class OrganizationSelfCreateSerializer(serializers.ModelSerializer):
    description = serializers.CharField(max_length=10000, allow_blank=True, required=False)

    class Meta:
        model = Organization
        fields = ("name", "slug", "description", "website")


class OrganizationCreationPolicySerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    eligible = serializers.BooleanField()
    max_owned = serializers.IntegerField()
    max_per_day = serializers.IntegerField()
    reason = serializers.CharField(allow_blank=True)


class OrganizationCreationThrottle(SimpleRateThrottle):
    scope = "organization_creation"
    rate = "10/hour"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": str(request.user.pk)}


class OrganizationCreationIpThrottle(OrganizationCreationThrottle):
    scope = "organization_creation_ip"
    rate = "30/hour"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class OrganizationSelfServiceView(APIView):
    # Global operations are refused on a makerspace's custom origin, just as the
    # organization console is. An ordinary active account does not need local RBAC.
    permission_classes = [IsActiveStaff]
    throttle_classes = [OrganizationCreationThrottle, OrganizationCreationIpThrottle]

    @extend_schema(tags=["Auth"], request=None, responses={
        200: OrganizationCreationPolicySerializer, **console_errors(401, 403, 429),
    })
    def get(self, request):
        return Response(creation_policy(request.user))

    @extend_schema(tags=["Auth"], request=OrganizationSelfCreateSerializer, responses={
        201: OrganizationDetailSerializer, **console_errors(400, 401, 403, 409, 429),
    })
    def post(self, request):
        payload = OrganizationSelfCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        row = create_self_service(request.user, **payload.validated_data)
        return Response(OrganizationDetailSerializer(row, context={"actor": request.user}).data,
                        status=201)
