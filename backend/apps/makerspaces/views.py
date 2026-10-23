from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.makerspaces.models import Makerspace
from apps.makerspaces.platform import bootstrap_payload, resolve_frontend
from apps.makerspaces.opening_hours_schema import OpeningHoursField

TenantBootstrapSerializer = inline_serializer(
    name="TenantBootstrap",
    fields={
        "makerspace": inline_serializer(
            name="TenantBootstrapMakerspace",
            fields={
                "id": serializers.IntegerField(),
                "name": serializers.CharField(),
                "slug": serializers.CharField(),
                "public_code": serializers.CharField(),
                "location": serializers.CharField(allow_blank=True),
                "timezone": serializers.CharField(),
                "opening_hours": OpeningHoursField(),
                "map_url": serializers.URLField(allow_blank=True),
                "geofence_enabled": serializers.BooleanField(required=False),
                "logo_url": serializers.CharField(allow_blank=True, allow_null=True),
                "cover_image_url": serializers.CharField(
                    allow_blank=True, allow_null=True
                ),
                "public_stats_enabled": serializers.BooleanField(),
                "public_site_enabled": serializers.BooleanField(),
                "public_inventory_enabled": serializers.BooleanField(),
                "public_landing_page": serializers.ChoiceField(choices=["auto", "inventory", "events", "machines", "bookings", "membership"]),
                "membership_policy": serializers.ChoiceField(
                    choices=Makerspace.MembershipPolicy.choices
                ),
                # Present only for a space without member accounts (#80): borrow
                # requests then take name, phone, email and an email code, no account.
                "request_access": serializers.ChoiceField(
                    choices=[("contact", "contact")], required=False
                ),
            },
        ),
        "frontend": inline_serializer(
            name="TenantBootstrapFrontend",
            fields={
                "type": serializers.CharField(),
                "hostname": serializers.CharField(allow_blank=True),
                "allowed_origins": serializers.ListField(
                    child=serializers.CharField()
                ),
            },
        ),
        "modules": serializers.ListField(child=serializers.CharField()),
        "edition": serializers.CharField(),
        "features": serializers.ListField(child=serializers.CharField()),
        "workflows": serializers.ListField(child=serializers.CharField()),
        "theme": serializers.JSONField(),
        "branding": serializers.JSONField(),
        "email_enabled": serializers.BooleanField(),
        "messaging": inline_serializer(name="TenantMessagingAvailability", fields={
            "sms": serializers.BooleanField(), "whatsapp": serializers.BooleanField(),
        }),
        "public_api": inline_serializer(
            name="TenantBootstrapPublicApi",
            fields={
                "base_url": serializers.CharField(),
                "publishable_key": serializers.CharField(),
                "inventory_path": serializers.CharField(),
            },
        ),
    },
)


class BootstrapView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Tenant bootstrap"],
        summary="Resolve tenant and frontend-safe configuration",
        parameters=[
            OpenApiParameter("tenant", str, OpenApiParameter.QUERY),
            OpenApiParameter("slug", str, OpenApiParameter.QUERY),
        ],
        responses={
            200: OpenApiResponse(
                response=TenantBootstrapSerializer,
                description="Frontend-safe tenant bootstrap payload.",
            ),
            404: OpenApiResponse(description="No active tenant frontend matched."),
        },
    )
    def get(self, request, *args, **kwargs):
        makerspace = resolve_frontend(
            tenant=request.query_params.get("tenant"),
            slug=request.query_params.get("slug"),
            origin=request.headers.get("Origin"),
            host=request.get_host(),
        )
        if makerspace is None:
            return Response(
                {"detail": "No active tenant frontend matched."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(bootstrap_payload(makerspace))
