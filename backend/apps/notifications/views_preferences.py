from django.utils.translation import gettext
from django.core import signing
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.accounts.models import User
from apps.audit import services as audit
from apps.integrations.email_preferences import decode_unsubscribe, unsubscribe_page_url
from apps.notifications import unsubscribe_landing as landing
from apps.makerspaces.platform import feature_enabled
from apps.makerspaces.guards import require_module
from apps.makerspaces.servability import servable_queryset
from apps.notifications.access import personal_space
from apps.notifications.models_inbox import MemberNotificationPreference
from apps.notifications.preferences import channel_available, preference_cells
from apps.notifications.serializers_inbox import (
    PreferenceResponseSerializer, PreferenceWriteSerializer,
    UnsubscribeResultSerializer,
)
from apps.openapi_errors import errors
from apps.tenant_migration.gate_runtime import tenant_write


def save_preference(user, space, data, *, unsubscribe=False):
    # Signed links resolve their tenant after HTTP middleware, so hold the late gate.
    with tenant_write(space.pk):
        rbac.scope_notification_policy(MemberNotificationPreference.objects.all(), makerspace_id=space.pk).update_or_create(
            user=user, makerspace=space, feature=data["feature"], channel=data["channel"],
            defaults={key: data[key] for key in ("enabled", "daily_digest") if key in data},
        )
        audit.record(
            user, "notification.unsubscribed" if unsubscribe else "notification.preference_updated",
            makerspace=space, target=space, meta=data,
        )


class MemberPreferenceView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Personal notifications"], responses={200: PreferenceResponseSerializer, **errors(400, 401, 403, 404)})
    def get(self, request, makerspace_id):
        space = personal_space(request.user, makerspace_id, preferences=True)
        return Response({"cells": preference_cells(space, request.user)})

    @extend_schema(tags=["Personal notifications"], request=PreferenceWriteSerializer,
                   responses={200: PreferenceResponseSerializer, **errors(400, 401, 403, 404, 423, 503)})
    def patch(self, request, makerspace_id):
        space = personal_space(request.user, makerspace_id, preferences=True)
        serializer = PreferenceWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data["enabled"] and not channel_available(space, data["feature"], data["channel"]):
            raise ValidationError({"channel": gettext("This family/channel is disabled by the makerspace.")})
        if data.get("daily_digest") and (data["channel"] != "email" or not feature_enabled(space, "notifications.digests")):
            raise ValidationError({"daily_digest": gettext("Daily digests are disabled or this is not an email channel.")})
        save_preference(request.user, space, data)
        return Response({"cells": preference_cells(space, request.user)})


class OneClickUnsubscribeView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [FormParser, JSONParser]
    http_method_names = ["get", "post", "options"]

    @extend_schema(tags=["Personal notifications"], auth=[], description=(
        "A person who opens the List-Unsubscribe link in a browser. Changes nothing (mail scanners "
        "prefetch links): 302 to the website's /unsubscribe/<token> confirm page, or, with no website "
        "origin configured (API-only), a minimal HTML form that POSTs the RFC 8058 one-click body here."),
        responses={302: OpenApiResponse(description="Redirect to the website confirm page."),
                   200: OpenApiResponse(OpenApiTypes.STR, description="API-only HTML confirm form."),
                   400: OpenApiResponse(OpenApiTypes.STR, description="Invalid or expired token (HTML).")})
    def get(self, request, token):
        # Signature/shape only: no tenant, module or user lookup, and never a write.
        try:
            decode_unsubscribe(token)
        except (signing.BadSignature, TypeError, ValueError):
            return landing.invalid()
        url = unsubscribe_page_url(token)
        return HttpResponseRedirect(url) if url else landing.confirm_form()

    # A dict ``request`` is a media-type -> schema map, so the body schema is keyed by the
    # two types the parsers accept (RFC 8058 mail clients POST it form-encoded).
    @extend_schema(tags=["Personal notifications"], auth=[], request={
        media_type: {"type": "object", "required": ["List-Unsubscribe"],
                     "properties": {"List-Unsubscribe": {"type": "string", "enum": ["One-Click"]}}}
        for media_type in ("application/x-www-form-urlencoded", "application/json")
    }, responses={200: UnsubscribeResultSerializer, **errors(400, 404, 415, 423, 503)})
    def post(self, request, token):
        try:
            data = decode_unsubscribe(token)
        except (signing.BadSignature, TypeError, ValueError):
            raise ValidationError({"token": gettext("Invalid or expired unsubscribe token.")})
        if request.data.get("List-Unsubscribe") != "One-Click":
            raise ValidationError({"List-Unsubscribe": gettext("Expected One-Click.")})
        space = get_object_or_404(rbac.scope_notification_policy(
            servable_queryset(), makerspace_id=data["space"], field="pk",
        ))
        require_module(space, "notifications")
        if not feature_enabled(space, "notifications.member_preferences"):
            from apps.makerspaces.guards import feature_off
            raise feature_off("notifications.member_preferences", "Member preferences are turned off.")
        user = get_object_or_404(User, pk=data["user"], is_active=True, is_tenant_dump_stub=False)
        # The signature is the authority here; no browser login and no CSRF cookie.
        # Actor is the user who received the capability, never a provider/device.
        save_preference(user, space, {"feature": data["feature"], "channel": "email", "enabled": False},
                        unsubscribe=True)
        return Response({"detail": gettext("Optional emails for this family are disabled. Safety emails remain enabled.")})
