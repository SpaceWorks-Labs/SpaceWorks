"""Account settings, intentionally independent of the notifications module."""
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.openapi_errors import errors
from .consent import grant_consent, member_payload, member_space
from .serializers import ConsentWriteSerializer, MemberMessagingSerializer


class MemberMessagingView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Messaging"], description="Own sender-bound consent for a member with a tenant tie or active staff in their fixed tenant; platform accounts are refused.", parameters=[OpenApiParameter("makerspace", int, required=True)],
                   responses={200: MemberMessagingSerializer, **errors(400, 401, 404)})
    def get(self, request):
        field = serializers.IntegerField(min_value=1)
        space = member_space(request.user, field.run_validation(request.query_params.get("makerspace")))
        return Response(member_payload(space, request.user))


class MemberMessagingConsentView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Messaging"], request=ConsentWriteSerializer,
                   description="Record this account's consent only. SMS requires its own currently verified phone; staff consent is restricted to the fixed staff tenant. WhatsApp requires a signed endpoint proof.",
                   responses={200: MemberMessagingSerializer, **errors(400, 401, 404, 409, 423, 503)})
    def post(self, request):
        serializer = ConsentWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        return Response(grant_consent(user=request.user, makerspace_id=values["makerspace"],
                                      channel=values["channel"], action=values["action"],
                                      source="native_app" if getattr(request, "device_grant", None) else "member_settings"))
