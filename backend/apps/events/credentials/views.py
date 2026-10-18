from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.events.serializers_staff_tools import StrictSerializer
from apps.events.throttles import CredentialRenderThrottle
from apps.hardware_requests.exceptions import ErrorSerializer
from .workflow import command

ERRORS = {code: ErrorSerializer for code in (400, 401, 403, 404, 409, 423, 429, 503)}


class CredentialCommandSerializer(StrictSerializer):
    operation_id = serializers.UUIDField()
    expected_version = serializers.IntegerField(min_value=0)


class CommandResultSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    event_id = serializers.IntegerField()
    version = serializers.IntegerField()
    state = serializers.ChoiceField(choices=("applied",))
    allowed_actions = serializers.ListField(child=serializers.CharField())
    credential_generation = serializers.IntegerField(allow_null=True, required=False)


class CredentialRotateView(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [CredentialRenderThrottle]
    action = "rotate"

    @extend_schema(tags=["Event credentials"], request=CredentialCommandSerializer,
                   responses={200: CommandResultSerializer, **ERRORS})
    def post(self, request, pk, registration_id):
        serializer = CredentialCommandSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = command(pk, registration_id, actor=request.user, action=self.action, **serializer.validated_data)
        response = Response(result)
        response["Cache-Control"] = "private, no-store"
        return response


class CredentialRevokeView(CredentialRotateView):
    action = "revoke"
